"""Learned corner classifier (Hoshyari et al. 2018, Section 4).

A Random Forest predicts, for each vertex of a region's pixel-corner boundary
polyline, the likelihood that a viewer perceives it as a C0 corner.  Training mixes
synthetic primitives, corpus icons and font words (structural labels), small smooth
negatives, and — the gold standard — HUMAN annotations (ours, cleaned by
_clean_corners_on_loop) plus the paper's released 157-example GT (_paper_dataset).
The feature of vertex p_i is the local neighbourhood f_i = [p_{i-s}-p_i, ...,
p_{i+s}-p_i] plus turning/log-resolution extras; 8 dihedral transforms of each
sample teach rotation/reflection invariance.  In the production pipeline this RF is
the FALLBACK detector — the corner_cnn 1D CNN is primary.

The detector is deliberately high-recall (a lax over-detected set); the paper's
iterated corner removal (Section 5) then prunes it.  Corners are detected at the
NATIVE image resolution the model was trained on, not on a 4x-upscaled boundary.

    python corner_classifier.py --train          # train and save models/corner_rf.joblib
"""

from __future__ import annotations

import argparse
import hashlib
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from vectorize_papers import mask_loops

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "corner_rf.joblib"
TRAIN_RES = [16, 20, 24, 32, 48, 64, 96, 128, 180, 256]  # incl. TINY (paper trains 8-256); small
                                                          # smooth shapes here teach "tiny+smooth=no corner"
NEIGHBORHOOD = 14  # s: half-window of the local feature, in boundary vertices

# 8 elements of the dihedral group applied to 2D offsets (a b / c e).
_DIHEDRAL = [(1, 0, 0, 1), (0, -1, 1, 0), (-1, 0, 0, -1), (0, 1, -1, 0),
             (-1, 0, 0, 1), (1, 0, 0, -1), (0, 1, 1, 0), (0, -1, -1, 0)]


def _regular_points(cx, cy, r, n, ang, inner=None):
    pts = []
    steps = n if inner is None else 2 * n
    for i in range(steps):
        rr = r if inner is None or i % 2 == 0 else inner
        a = ang + 2 * math.pi * i / steps
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def _synth_shape(rng: random.Random, resolution: int,
                 forced_kind: str | None = None) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """A random shape rasterized at `resolution`, with its known true corners."""
    image = Image.new("1", (resolution, resolution), 0)
    draw = ImageDraw.Draw(image)
    margin = resolution * rng.uniform(0.12, 0.2)
    x0, y0 = rng.uniform(margin, resolution * 0.4), rng.uniform(margin, resolution * 0.4)
    x1, y1 = rng.uniform(resolution * 0.6, resolution - margin), rng.uniform(resolution * 0.6, resolution - margin)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    kind = forced_kind or rng.choice([
        "rect", "rrect", "ellipse", "circle", "poly", "star", "tri", "stadium", "halfdisk", "Lshape",
        # mixed straight+curved and obtuse shapes — the ones real logos/letters are made of,
        # where a corner is only a SHARP tangent break, not a smooth curve-to-line join:
        "dshape", "arc_segment", "chamfer", "rounded_poly", "capsule_flat", "cross", "wedge",
        # Focused paper-style extension: small/thin and concave primitives are far
        # cheaper to label exactly than whole logos and cover the geometry used by
        # glyphs, badges and line-art wordmarks.
        "thin_rect", "diamond", "trapezoid", "chevron", "notch", "zigzag",
    ])
    corners: list[tuple[float, float]] = []
    if kind == "rect":
        draw.rectangle((x0, y0, x1, y1), fill=1)
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    elif kind in ("rrect", "stadium"):
        radius = min(x1 - x0, y1 - y0) * (0.5 if kind == "stadium" else rng.uniform(0.15, 0.35))
        draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=1)  # rounded joins = NO corners
    elif kind in ("ellipse", "circle"):
        if kind == "circle":
            side = min(x1 - x0, y1 - y0)
            x1, y1 = x0 + side, y0 + side
        draw.ellipse((x0, y0, x1, y1), fill=1)
    elif kind in ("poly", "star", "tri"):
        n = 3 if kind == "tri" else rng.randint(4, 8)
        r = 0.5 * min(x1 - x0, y1 - y0)
        inner = r * rng.uniform(0.4, 0.6) if kind == "star" else None
        corners = _regular_points(cx, cy, r, n, rng.random() * math.pi, inner)
        draw.polygon(corners, fill=1)
    elif kind == "halfdisk":
        draw.pieslice((x0, y0, x1, y1), start=0, end=180, fill=1)
        corners = [(x0, cy), (x1, cy)]
    elif kind == "Lshape":
        ax = rng.uniform(x0 + (x1 - x0) * 0.35, x0 + (x1 - x0) * 0.6)
        ay = rng.uniform(y0 + (y1 - y0) * 0.35, y0 + (y1 - y0) * 0.6)
        corners = [(x0, y0), (ax, y0), (ax, ay), (x1, ay), (x1, y1), (x0, y1)]
        draw.polygon(corners, fill=1)
    elif kind == "dshape":
        # straight left/top/bottom + a semicircular right bump: corners ONLY at the two
        # left vertices; the flat-to-arc joins on the right are tangent (smooth).
        xm = rng.uniform(x0 + (x1 - x0) * 0.3, x0 + (x1 - x0) * 0.6)
        r = (y1 - y0) / 2
        draw.rectangle((x0, y0, xm, y1), fill=1)
        draw.ellipse((xm - r, y0, xm + r, y1), fill=1)
        corners = [(x0, y0), (x0, y1)]
    elif kind == "arc_segment":
        end = rng.uniform(70, 150)                       # a circular segment: 2 sharp chord ends
        draw.pieslice((x0, y0, x1, y1), start=90 - end / 2, end=90 + end / 2, fill=1)
        for a in (90 - end / 2, 90 + end / 2):
            corners.append((cx + 0.5 * (x1 - x0) * math.cos(math.radians(a)),
                            cy + 0.5 * (y1 - y0) * math.sin(math.radians(a))))
    elif kind == "chamfer":
        c = min(x1 - x0, y1 - y0) * rng.uniform(0.15, 0.3)  # cut corners -> 8 obtuse (~135°) corners
        corners = [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c),
                   (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c)]
        draw.polygon(corners, fill=1)
    elif kind == "rounded_poly":
        # a convex polygon whose corners are all ROUNDED off -> a smooth blob, 0 corners
        n = rng.randint(5, 9)
        r = 0.5 * min(x1 - x0, y1 - y0)
        pts = _regular_points(cx, cy, r, n, rng.random() * math.pi)
        dense = []
        for i in range(len(pts)):
            p, q = np.array(pts[i]), np.array(pts[(i + 1) % len(pts)])
            for t in np.linspace(0, 1, 12):
                dense.append(tuple(p + (q - p) * t))
        # smooth by a couple of averaging passes so vertices become gentle bends
        arr = np.array(dense)
        for _ in range(3):
            arr = 0.5 * arr + 0.25 * (np.roll(arr, 1, 0) + np.roll(arr, -1, 0))
        draw.polygon([tuple(p) for p in arr], fill=1)
    elif kind == "capsule_flat":
        # a stadium (both ends round) with one FLAT-cut end: 2 corners at the cut
        r = (y1 - y0) / 2
        draw.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=1)
        draw.rectangle((x0, y0, x0 + r, y1), fill=1)  # square off the left end
        corners = [(x0, y0), (x0, y1)]
    elif kind == "cross":
        t = min(x1 - x0, y1 - y0) * rng.uniform(0.25, 0.38)
        mx0, mx1 = cx - t / 2, cx + t / 2
        my0, my1 = cy - t / 2, cy + t / 2
        corners = [(mx0, y0), (mx1, y0), (mx1, my0), (x1, my0), (x1, my1), (mx1, my1),
                   (mx1, y1), (mx0, y1), (mx0, my1), (x0, my1), (x0, my0), (mx0, my0)]
        draw.polygon(corners, fill=1)
    elif kind == "wedge":
        corners = [(x0, y1), (cx, y0), (x1, y1)]          # triangle-ish wedge, 3 sharp corners
        draw.polygon(corners, fill=1)
    elif kind == "thin_rect":
        # A rotated 1--4px bar with four genuine square corners.  Thin stems are
        # badly under-represented by the old bbox generator and dominate tiny text.
        length = resolution * rng.uniform(0.42, 0.72)
        width = rng.uniform(max(1.0, resolution * 0.018), max(2.0, resolution * 0.065))
        angle = rng.uniform(0.0, math.pi)
        u = np.array([math.cos(angle), math.sin(angle)]) * (length / 2)
        v = np.array([-math.sin(angle), math.cos(angle)]) * (width / 2)
        center = np.array([resolution / 2, resolution / 2])
        corners = [tuple(center - u - v), tuple(center + u - v),
                   tuple(center + u + v), tuple(center - u + v)]
        draw.polygon(corners, fill=1)
    elif kind == "diamond":
        corners = [(cx, y0), (x1, cy), (cx, y1), (x0, cy)]
        draw.polygon(corners, fill=1)
    elif kind == "trapezoid":
        inset = (x1 - x0) * rng.uniform(0.12, 0.32)
        corners = [(x0 + inset, y0), (x1 - inset, y0), (x1, y1), (x0, y1)]
        draw.polygon(corners, fill=1)
    elif kind == "chevron":
        # Thick V/arrow stroke: common in A/V/W/M glyphs and logo marks.
        t = max(1.2, min(x1 - x0, y1 - y0) * rng.uniform(0.10, 0.20))
        corners = [(x0, y0), (cx, y1 - t), (x1, y0), (x1 - t, y0),
                   (cx, y1 - 3 * t), (x0 + t, y0)]
        draw.polygon(corners, fill=1)
    elif kind == "notch":
        # Concave rectangular notch: four convex and three concave events.
        nx0 = rng.uniform(x0 + (x1 - x0) * 0.25, x0 + (x1 - x0) * 0.42)
        nx1 = rng.uniform(x0 + (x1 - x0) * 0.58, x0 + (x1 - x0) * 0.75)
        ny = rng.uniform(y0 + (y1 - y0) * 0.25, y0 + (y1 - y0) * 0.55)
        corners = [(x0, y0), (nx0, y0), (nx0, ny), (nx1, ny),
                   (nx1, y0), (x1, y0), (x1, y1), (x0, y1)]
        draw.polygon(corners, fill=1)
    elif kind == "zigzag":
        # A thin lightning/ribbon primitive with both acute and obtuse corners.
        t = max(1.2, (x1 - x0) * rng.uniform(0.07, 0.13))
        corners = [(x0, y0), (cx + t, y0), (cx - t, cy - t),
                   (x1, cy - t), (x1, cy + t), (cx + t, cy + t),
                   (cx - t, y1), (x0, y1)]
        draw.polygon(corners, fill=1)
    return np.asarray(image, dtype=np.uint8), corners


def _synth_smooth_mask(rng: random.Random, resolution: int,
                       forced_kind: str | None = None) -> np.ndarray:
    """Rasterize a known-smooth negative, including thin curved strokes.

    The old CNN negatives were mostly circles and rounded rectangles.  That leaves
    long round-capped curves (PensPiral, handwriting, glyph bowls) out of domain and
    encourages false corners along their raster staircases.  These shapes have zero
    perceptual C0 events by construction.
    """
    image = Image.new("1", (resolution, resolution), 0)
    draw = ImageDraw.Draw(image)
    margin = resolution * rng.uniform(0.08, 0.17)
    x0, y0 = margin, rng.uniform(margin, resolution * 0.35)
    x1, y1 = resolution - margin, rng.uniform(resolution * 0.65, resolution - margin)
    kind = forced_kind or rng.choice([
        "circle", "ellipse", "rrect", "stadium", "ring",
        "linebar", "curvebar", "curvebar", "sbar", "sbar",
    ])
    if kind == "circle":
        side = min(x1 - x0, y1 - y0)
        draw.ellipse((x0, y0, x0 + side, y0 + side), fill=1)
    elif kind == "ellipse":
        draw.ellipse((x0, y0, x1, y1), fill=1)
    elif kind in ("rrect", "stadium"):
        radius = min(x1 - x0, y1 - y0) * (0.5 if kind == "stadium" else rng.uniform(0.25, 0.48))
        draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=1)
    elif kind == "ring":
        draw.ellipse((x0, y0, x1, y1), fill=1)
        t = min(x1 - x0, y1 - y0) * rng.uniform(0.12, 0.28)
        if x1 - x0 > 2 * t and y1 - y0 > 2 * t:
            draw.ellipse((x0 + t, y0 + t, x1 - t, y1 - t), fill=0)
    else:
        width = max(1, int(round(resolution * rng.uniform(0.035, 0.10))))
        if kind == "linebar":
            points = [(x0, rng.uniform(y0, y1)), (x1, rng.uniform(y0, y1))]
        elif kind == "curvebar":
            p0 = np.array([x0, rng.uniform(y0, y1)])
            p1 = np.array([(x0 + x1) / 2, rng.uniform(margin, resolution - margin)])
            p2 = np.array([x1, rng.uniform(y0, y1)])
            points = [tuple((1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2)
                      for t in np.linspace(0, 1, 28)]
        else:  # cubic S-stroke, smooth everywhere including the inflection
            p0 = np.array([x0, rng.uniform(y0, y1)])
            p1 = np.array([x0 + (x1 - x0) * 0.32, margin])
            p2 = np.array([x0 + (x1 - x0) * 0.68, resolution - margin])
            p3 = np.array([x1, rng.uniform(y0, y1)])
            points = [tuple((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1
                            + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3)
                      for t in np.linspace(0, 1, 36)]
        draw.line(points, fill=1, width=width, joint="curve")
        radius = width / 2
        for px, py in (points[0], points[-1]):
            draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=1)
    return np.asarray(image, dtype=np.uint8)


def outer_loop(mask: np.ndarray) -> np.ndarray | None:
    """The largest closed pixel-corner boundary polyline of a binary mask."""
    loops = mask_loops(mask)
    if not loops:
        return None
    loop = max(loops, key=len)
    if len(loop) > 1 and np.allclose(loop[0], loop[-1]):
        loop = loop[:-1]
    return loop.astype(np.float64)


_TURN_SCALES = (3, 6, 10, 14)   # px windows for the multi-scale turning features
N_EXTRA = len(_TURN_SCALES) + 3  # + 2 saturation ratios + 1 RESOLUTION (scale) feature


def _turning_features(loop: np.ndarray) -> np.ndarray:
    """Per-vertex ROTATION/REFLECTION-INVARIANT features: the exterior turn angle over
    several ± px windows (0=straight .. 180=hairpin), two saturation ratios (small/large
    window), and the loop's log-RESOLUTION (bbox diagonal).  The turning features give a
    staircase-robust, scale-consistent corner signal; the resolution feature lets ONE RF
    modulate its corner decision by scale (per-resolution behaviour in a single model — so a
    ~2px rounded cap reads 'smooth' at 48px but a real corner reads 'sharp' at 200px), which
    is the cheap alternative to the paper's separate per-resolution models."""
    n = len(loop)
    turns = []
    for w in _TURN_SCALES:
        a = loop - np.roll(loop, w, axis=0)          # direction INTO each vertex
        b = np.roll(loop, -w, axis=0) - loop         # direction OUT of each vertex
        na = np.linalg.norm(a, axis=1); nb = np.linalg.norm(b, axis=1)
        cos = np.clip(np.sum(a * b, axis=1) / np.maximum(na * nb, 1e-9), -1.0, 1.0)
        turns.append(np.degrees(np.arccos(cos)))     # exterior turn, deg
    T = np.stack(turns, axis=1)                       # (n, len(scales))
    sat1 = T[:, 0] / np.maximum(T[:, 2], 1e-6)        # concentration: small vs large window
    sat2 = T[:, 1] / np.maximum(T[:, 3], 1e-6)
    diag = float(np.hypot(*(loop.max(axis=0) - loop.min(axis=0))))   # loop bbox diagonal (px)
    scale = np.full(n, math.log2(max(diag, 1.0)) / 10.0)             # log-resolution, ~[0.5,0.85]
    return np.column_stack([T / 180.0, np.clip(sat1, 0, 4), np.clip(sat2, 0, 4), scale])


def featurize(loop: np.ndarray, s: int = NEIGHBORHOOD) -> np.ndarray:
    """Per-vertex feature: local neighbourhood offsets f_i=[p_{i±s}-p_i] (dihedral-augmentable)
    CONCATENATED with invariant multi-scale turning/saturation features (see _turning_features)."""
    n = len(loop)
    index = (np.arange(n)[:, None] + np.arange(-s, s + 1)[None, :]) % n
    feature = loop[index] - loop[:, None, :]
    feature = np.delete(feature, s, axis=1).reshape(n, -1)   # (n, 4s) offsets
    return np.concatenate([feature, _turning_features(loop)], axis=1)  # + N_EXTRA invariant


_HUMAN_MIN_TURN = 40.0   # drop human corners whose boundary turn is softer than this (deg): they
                         # are gentle CURVATURE marks the paper never labels and are the proven
                         # source of the false-positive flood on smooth arcs (held-out F1 0.63->0.71)
_HUMAN_RECENTER = 4      # re-centre each human corner onto the local turning MAX within +/- this


def _clean_corners_on_loop(loop: np.ndarray, corners, min_turn: float = _HUMAN_MIN_TURN,
                           recenter: int = _HUMAN_RECENTER, w: int = 4) -> np.ndarray:
    """Clean HUMAN corners for a specific rendered loop: snap each to the nearest local turning
    MAXIMUM within `recenter` vertices, then DROP those whose turn is below `min_turn` (soft
    curvature-corners).  Corners not near this loop (belong to another region) are dropped."""
    pts = np.asarray(corners, dtype=float).reshape(-1, 2)
    if len(pts) == 0 or len(loop) < 2 * w + 3:
        return pts[:0]
    t = np.array([_corner_turn(loop, i, w) for i in range(len(loop))])
    n = len(loop)
    out = []
    for c in pts:
        d = np.linalg.norm(loop - c, axis=1); i0 = int(d.argmin())
        if d[i0] > 3.0:                                  # corner belongs to a different loop
            continue
        j = max(((i0 + dd) % n for dd in range(-recenter, recenter + 1)), key=lambda q: t[q])
        if t[j] >= min_turn:
            out.append(loop[j])
    return np.asarray(out, dtype=float).reshape(-1, 2)


def _labels(loop: np.ndarray, corners, snap: float = 3.0, tol: float = 1.0) -> np.ndarray:
    """One positive per corner: its single NEAREST loop vertex (plus any within `tol`px,
    which on a ~1px-spaced pixel-corner loop is the paper's §4.2.1 mark-both-endpoints-of-
    a-1-2px-corner rule).  A metric radius of 1.8px instead tagged ~4 vertices per corner
    (mean 3.9), teaching the RF a blurry band around each corner and inflating the lax set
    ~4x — the dominant label-excess cause."""
    y = np.zeros(len(loop), np.int8)
    points = np.asarray(corners, dtype=float).reshape(-1, 2)
    if len(points) == 0:
        return y
    for p in points:
        d = np.linalg.norm(loop - p, axis=1)
        i = int(np.argmin(d))
        if d[i] <= snap:
            y[i] = 1
            y[d <= tol] = 1
    return y


def _corner_turn(loop: np.ndarray, i: int, w: int) -> float:
    """Turn angle (deg; 0=straight, 90=right angle) of the raster boundary at vertex i,
    measured over a ±w-pixel window so pixel-staircase noise averages out."""
    n = len(loop)
    a = loop[i] - loop[(i - w) % n]
    b = loop[(i + w) % n] - loop[i]
    na = math.hypot(a[0], a[1]); nb = math.hypot(b[0], b[1])
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    cos = max(-1.0, min(1.0, float(a[0] * b[0] + a[1] * b[1]) / (na * nb)))
    return math.degrees(math.acos(cos))


def _validate_svg_corners(loop: np.ndarray, corners, w: int = 6,
                          min_turn: float = 22.0, snap: float = 4.0) -> np.ndarray:
    """Keep a detected path corner only if the RASTERIZED boundary also turns sharply there
    at this resolution (a corner is perceived at the operating scale, Sec 4) — this drops
    corners that rasterize away / cram below the feature scale at tiny resolutions.  Snaps
    each candidate to THIS loop (a fill path's holes share one corner list).  snap is 4px
    (not 2.5) because rasterisation BLUNTS an acute spike tip, offsetting the pixel-corner
    boundary a few px from the analytic tip — a tighter snap dropped e.g. the Nike swoosh
    tail (2.6px off) even though its raster turn is a clean 162 deg."""
    pts = np.asarray(corners, float).reshape(-1, 2)
    if len(pts) == 0 or len(loop) < 2 * w + 3:
        return pts[:0]
    dist = np.linalg.norm(loop[:, None, :] - pts[None, :, :], axis=2)
    kept = []
    for k in range(len(pts)):
        i = int(np.argmin(dist[:, k]))
        if dist[i, k] > snap:
            continue
        if _corner_turn(loop, i, w) >= min_turn:
            kept.append(pts[k])
    return np.asarray(kept, float).reshape(-1, 2)


def _region_too_dense(loop: np.ndarray, corners: np.ndarray) -> bool:
    """Corners packed closer than the detector can resolve (< ~9 px apart on average with
    several of them) -> labels unreliable at this resolution; skip the region."""
    k = len(corners)
    return k > 4 and (len(loop) / max(1, k)) < 9.0


def _to_ccw(loop: np.ndarray) -> np.ndarray:
    """Consistent winding so convex/concave feature signs match across all loops
    (outer vs hole), which mask_loops returns with opposite orientation."""
    x, y = loop[:, 0], loop[:, 1]
    area = float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
    return loop[::-1] if area < 0 else loop


def _augment(feature: np.ndarray, s: int) -> list[np.ndarray]:
    """Dihedral-augment the OFFSET part; the trailing invariant turning features are copied
    unchanged (they are rotation/reflection invariant by construction)."""
    ncols = 4 * s
    offsets = feature[:, :ncols].reshape(len(feature), 2 * s, 2)
    extra = feature[:, ncols:]
    out = []
    for a, b, c, e in _DIHEDRAL:
        transformed = np.empty_like(offsets)
        transformed[..., 0] = a * offsets[..., 0] + b * offsets[..., 1]
        transformed[..., 1] = c * offsets[..., 0] + e * offsets[..., 1]
        out.append(np.concatenate([transformed.reshape(len(feature), -1), extra], axis=1))
    return out


SVG_GROUND_TRUTH = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/ground truth/Default")
CORPUS_ROOT = Path(r"C:/Users/nirrt/Toolset/v-ize train/dataset")
CORPUS_GLOBS = ["icons/local/**/*.svg", "icons/iconify/**/*.svg"]
TEXT_CORPUS_ROOT = CORPUS_ROOT / "text_shapes" / "svg"
CORPUS_RES = [16, 20, 24, 32, 48, 64, 96, 130, 180, 256, 340]  # ALL sizes incl. tiny icons


def _corpus_files(n: int, seed: int) -> list[Path]:
    import glob
    files: list[str] = []
    for pattern in CORPUS_GLOBS:
        files.extend(glob.glob(str(CORPUS_ROOT / pattern), recursive=True))
        if len(files) > 8 * n:
            break
    rng = random.Random(seed)
    rng.shuffle(files)
    return [Path(f) for f in files[:n]]


def _text_corpus_files(n: int, seed: int, split: str = "train") -> list[Path]:
    """Balanced sample from the on-disk 150k wordmark/font SVG bank.

    This corpus used to be present but unreachable: ``_corpus_files`` only
    globbed the two icon trees.  Sample each font directory separately so Arial
    cannot dominate, and hash the relative path before sampling so future
    validation/test readers can use disjoint files deterministically.
    """
    if n <= 0 or not TEXT_CORPUS_ROOT.exists():
        return []
    ranges = {"train": range(0, 80), "val": range(80, 90), "test": range(90, 100)}
    if split not in ranges:
        raise ValueError(f"unknown text-corpus split: {split}")
    allowed = ranges[split]
    rng = random.Random(seed)
    font_dirs = sorted(path for path in TEXT_CORPUS_ROOT.iterdir() if path.is_dir())
    per_font = max(1, math.ceil(n / max(1, len(font_dirs))))
    picked: list[Path] = []
    for font_dir in font_dirs:
        files = []
        for path in font_dir.glob("*.svg"):
            rel = path.relative_to(TEXT_CORPUS_ROOT).as_posix()
            bucket = int(hashlib.sha1(rel.encode("utf-8")).hexdigest()[:8], 16) % 100
            if bucket in allowed:
                files.append(path)
        rng.shuffle(files)
        picked.extend(files[:per_font])
    rng.shuffle(picked)
    return picked[:n]


def _corpus_dataset(files: list[Path], s: int, seed: int, max_rows: int = 700_000) -> tuple[np.ndarray, np.ndarray]:
    """Features+labels from a sample of the big SVG corpus; one random resolution per
    file (avoids re-parsing) so the detector sees corners at many scales.  Caps total
    accumulated rows so a large file sample cannot blow up memory (each loop's 8 dihedral
    augmentations are heavy); the caller subsamples this down further."""
    from svg_corners import svg_region_masks

    rng = random.Random(seed)
    features, labels = [], []
    total = 0
    for f in files:
        if total >= max_rows:
            break
        res = rng.choice(CORPUS_RES)
        try:
            regions = svg_region_masks(str(f), target=res)
        except Exception:
            continue
        for mask, corners in regions:
            for loop in mask_loops(mask):
                if len(loop) > 1 and np.allclose(loop[0], loop[-1]):
                    loop = loop[:-1]
                loop = _to_ccw(loop.astype(np.float64))
                if len(loop) < 4 * s + 4:
                    continue
                vcorners = _validate_svg_corners(loop, corners)
                if _region_too_dense(loop, vcorners):
                    continue
                base = featurize(loop, s)
                target = _labels(loop, vcorners)
                for variant in _augment(base, s):
                    features.append(variant)
                    labels.append(target)
                total += len(base)
    if not features:
        return np.zeros((0, 4 * s + N_EXTRA), np.float64), np.zeros(0, np.int8)
    return np.vstack(features), np.concatenate(labels)


def _svg_dataset(svg_dir: Path, resolutions: list[int], s: int, files: list[Path]) -> tuple[np.ndarray, np.ndarray]:
    """Features+labels from REAL logo SVGs: each fill path -> region mask + its true
    corners (tangent discontinuities), each boundary loop featurized and labelled."""
    from svg_corners import svg_region_masks

    features, labels = [], []
    for f in files:
        for res in resolutions:
            try:
                regions = svg_region_masks(str(f), target=res)
            except Exception:
                continue
            for mask, corners in regions:
                for loop in mask_loops(mask):
                    if len(loop) > 1 and np.allclose(loop[0], loop[-1]):
                        loop = loop[:-1]
                    loop = _to_ccw(loop.astype(np.float64))
                    if len(loop) < 4 * s + 4:
                        continue
                    vcorners = _validate_svg_corners(loop, corners)
                    if _region_too_dense(loop, vcorners):
                        continue
                    base = featurize(loop, s)
                    target = _labels(loop, vcorners)
                    for variant in _augment(base, s):
                        features.append(variant)
                        labels.append(target)
    if not features:
        return np.zeros((0, 4 * s + N_EXTRA), np.float64), np.zeros(0, np.int8)
    return np.vstack(features), np.concatenate(labels)


def _smooth_negatives(n: int, s: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Small SMOOTH shapes (circle/ellipse/rounded-rect/stadium) at SMALL resolutions, all
    labelled 0.  Real small icons rasterise to a coarse staircase and the detector was firing
    on those staircase steps (spotify/apple/flag @ 32-48px got 5-22 false corners).  The
    corpus at small res is dominated by DETAILED (cornered) icons, so the 'small smooth
    boundary = NOT a corner' signal is under-represented; this floods it to rebalance."""
    rng = random.Random(seed)
    res_choices = [16, 20, 24, 32, 40, 48, 64, 96, 128]
    features, labels = [], []
    tries = 0
    while len(labels) < n and tries < n * 4:
        tries += 1
        res = rng.choice(res_choices)
        img = Image.new("1", (res, res), 0); dr = ImageDraw.Draw(img)
        m = res * rng.uniform(0.08, 0.18)
        x0, y0 = rng.uniform(m, res * 0.35), rng.uniform(m, res * 0.35)
        x1, y1 = rng.uniform(res * 0.62, res - m), rng.uniform(res * 0.62, res - m)
        # incl. ROUND-CAP strokes + RINGS (spotify-bar / chrome-ring patterns) — the model
        # was firing on rounded arc/stroke END-CAPS thinking a U-turn cap is a corner.
        kind = rng.choice(["circle", "ellipse", "rrect", "stadium", "ring", "curvebar", "curvebar", "linebar"])
        if kind == "circle":
            side = min(x1 - x0, y1 - y0); dr.ellipse((x0, y0, x0 + side, y0 + side), fill=1)
        elif kind == "ellipse":
            dr.ellipse((x0, y0, x1, y1), fill=1)
        elif kind == "rrect":
            r = min(x1 - x0, y1 - y0) * rng.uniform(0.3, 0.5)
            dr.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=1)
        elif kind == "stadium":
            r = min(x1 - x0, y1 - y0) * 0.5
            dr.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=1)
        elif kind == "ring":                            # annulus: two concentric ellipses
            dr.ellipse((x0, y0, x1, y1), fill=1)
            t = min(x1 - x0, y1 - y0) * rng.uniform(0.18, 0.34)
            dr.ellipse((x0 + t, y0 + t, x1 - t, y1 - t), fill=0)
        else:                                           # round-capped stroke (spotify-bar-like)
            w = max(2.0, min(x1 - x0, y1 - y0) * rng.uniform(0.12, 0.22))
            if kind == "linebar":
                pts = [(x0, rng.uniform(y0, y1)), (x1, rng.uniform(y0, y1))]
            else:                                       # gentle arc via 3-point quad sampling
                ax, ay = x0, rng.uniform(y0, y1); bx, by = x1, rng.uniform(y0, y1)
                mx, my = (ax + bx) / 2, rng.uniform(y0, y1)
                pts = [(ax + (mx - ax) * 2 * t + (ax - 2 * mx + bx) * t * t,
                        ay + (my - ay) * 2 * t + (ay - 2 * my + by) * t * t) for t in np.linspace(0, 1, 16)]
            dr.line(pts, fill=1, width=int(round(w)), joint="curve")
            for px, py in (pts[0], pts[-1]):            # round caps
                dr.ellipse((px - w/2, py - w/2, px + w/2, py + w/2), fill=1)
        loop = outer_loop(np.asarray(img, np.uint8))
        if loop is None or len(loop) < 4 * s + 4:
            continue
        loop = _to_ccw(loop)
        base = featurize(loop, s)
        target = np.zeros(len(loop), np.int8)          # smooth everywhere -> all negative
        for variant in _augment(base, s):
            features.append(variant)
            labels.append(target)
    if not features:
        return np.zeros((0, 4 * s + N_EXTRA), np.float64), np.zeros(0, np.int8)
    return np.vstack(features), np.concatenate(labels)


def _build_dataset(seed: int, shapes: int, s: int) -> tuple[np.ndarray, np.ndarray]:
    rng = random.Random(seed)
    features, labels = [], []
    for _ in range(shapes):
        resolution = rng.choice(TRAIN_RES)
        mask, corners = _synth_shape(rng, resolution)
        loop = outer_loop(mask)
        if loop is None or len(loop) < 4 * s + 4:
            continue
        base = featurize(loop, s)
        target = _labels(loop, corners)
        for variant in _augment(base, s):
            features.append(variant)
            labels.append(target)
    return np.vstack(features), np.concatenate(labels)


# Real logos are largely WORDMARKS, so the detector must see text.  We render random short
# strings from real fonts, take their glyph OUTLINES (fontTools -> svgpathtools segments),
# and label corners with the SAME structural path detector used for logos — so serifs,
# stems, junctions, counters and (crucially) fillet-built corners are all learned with
# clean, resolution-aware labels.  No manual annotation.
_FONTS = [r"C:/Windows/Fonts/" + n for n in (
    "arial.ttf", "arialbd.ttf", "times.ttf", "timesbd.ttf", "georgia.ttf", "verdana.ttf",
    "calibri.ttf", "tahoma.ttf", "trebuc.ttf", "segoeui.ttf", "cour.ttf", "consola.ttf",
    "impact.ttf", "comic.ttf")]
_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz0123456789"
# Tiny wordmarks are the hard production case.  SVG outlines can be rasterized at
# these sizes without needing new source assets; 12--32px is where counters and thin
# stems currently disappear.
_TEXT_RES = [12, 16, 20, 24, 32, 48, 64, 96, 128, 180, 256]
_FONT_CACHE: dict = {}


def _glyphset(fp: str):
    if fp not in _FONT_CACHE:
        from fontTools.ttLib import TTFont
        f = TTFont(fp)
        _FONT_CACHE[fp] = (f.getGlyphSet(), f.getBestCmap())
    return _FONT_CACHE[fp]


def _synth_text(rng: random.Random, res: int, text: str | None = None,
                font_path: str | None = None):
    """A random short string in a random font, rasterized at `res`, with its structural
    glyph-outline corners.  Returns (mask uint8 HxW, corners (k,2)) like svg_region_masks."""
    from fontTools.pens.svgPathPen import SVGPathPen
    from svgpathtools import parse_path, Path as SPath
    from svg_corners import _path_corners, _sample_subpath

    avail = [fp for fp in _FONTS if Path(fp).exists()]
    if not avail:
        return None
    chosen_font = font_path if font_path and Path(font_path).exists() else rng.choice(avail)
    gs, cmap = _glyphset(chosen_font)
    text = text if text is not None else "".join(rng.choice(_ALPHABET) for _ in range(rng.randint(1, 6)))
    segs, penx = [], 0.0
    for ch in text:
        if ord(ch) not in cmap:
            continue
        name = cmap[ord(ch)]
        pen = SVGPathPen(gs)
        gs[name].draw(pen)
        d = pen.getCommands()
        if d.strip():
            segs.extend(list(parse_path(d).translated(complex(penx, 0))))
        penx += gs[name].width
    if not segs:
        return None
    P = SPath(*segs)
    try:
        xmin, xmax, ymin, ymax = P.bbox()
    except Exception:
        return None
    span = max(xmax - xmin, ymax - ymin, 1e-6)
    scale = res / span
    margin = res * 0.10
    W = max(8, int(round((xmax - xmin) * scale + 2 * margin)))
    H = max(8, int(round((ymax - ymin) * scale + 2 * margin)))
    to_px = lambda z: ((z.real - xmin) * scale + margin, (ymax - z.imag) * scale + margin)  # y-up
    acc = np.zeros((H, W), np.uint8)
    corners = []
    for sub in P.continuous_subpaths():
        poly = [to_px(z) for z in _sample_subpath(sub, scale)]
        if len(poly) >= 3:
            layer = Image.new("1", (W, H), 0)
            ImageDraw.Draw(layer).polygon(poly, fill=1)
            acc ^= np.asarray(layer, np.uint8)          # even-odd -> counters (holes)
        for z in _path_corners(sub, scale):
            corners.append(to_px(z))
    if acc.sum() < 4:
        return None
    return acc, np.asarray(corners, float).reshape(-1, 2)


def _text_dataset(n: int, s: int, seed: int, max_rows: int = 400_000) -> tuple[np.ndarray, np.ndarray]:
    rng = random.Random(seed)
    features, labels = [], []
    total = 0
    for _ in range(n):
        if total >= max_rows:
            break
        out = _synth_text(rng, rng.choice(_TEXT_RES))
        if out is None:
            continue
        mask, corners = out
        for loop in mask_loops(mask):
            if len(loop) > 1 and np.allclose(loop[0], loop[-1]):
                loop = loop[:-1]
            loop = _to_ccw(loop.astype(np.float64))
            if len(loop) < 4 * s + 4:
                continue
            vcorners = _validate_svg_corners(loop, corners)
            if _region_too_dense(loop, vcorners):
                continue
            base = featurize(loop, s)
            target = _labels(loop, vcorners)
            for variant in _augment(base, s):
                features.append(variant)
                labels.append(target)
            total += len(base)
    if not features:
        return np.zeros((0, 4 * s + N_EXTRA), np.float64), np.zeros(0, np.int8)
    return np.vstack(features), np.concatenate(labels)


HUMAN_ANN = ROOT / "corner_annotations.json"


_HUMAN_PROJ_RES = [32, 64, 128, 256]   # project human corners onto these (multi-res GT)


def _human_dataset(s: int, repeat: int = 30, max_rows: int = 12_000_000) -> tuple[np.ndarray, np.ndarray]:
    """HUMAN-annotated perceptual corners (from annotate_corners.py) — the gold-standard GT
    the paper has and geometric labelling cannot match (proven inseparable).  Corners are
    stored NORMALISED (per logo, resolution-independent); we PROJECT them onto every
    _HUMAN_PROJ_RES, re-render, snap to loop vertices, and upweight (`repeat`x) — one human
    annotation thus yields multi-resolution gold labels (the 'interpolation').  Also reads
    the legacy per-(logo,res) format.  Zero-corner annotations (all-smooth) are kept as
    valuable all-negative examples.  Logos are processed in RANDOM order and accumulation
    stops at `max_rows` so a large annotation set x high `repeat` cannot blow up memory
    (358 logos x repeat 25 x 8 aug once tried to allocate 138 GiB)."""
    import json
    from svg_corners import svg_region_masks
    empty = (np.zeros((0, 4 * s + N_EXTRA), np.float64), np.zeros(0, np.int8))
    if not HUMAN_ANN.exists():
        return empty
    ann = json.loads(HUMAN_ANN.read_text())
    new_stems = {k for k, v in ann.items() if "corners_norm" in v}   # dedup: new-format wins
    prepared = []                                                    # featurize each logo-loop once
    for k, rec in ann.items():
        file = rec.get("file")
        if not file:
            continue
        if "corners_norm" in rec:                                    # new normalised format
            norm = np.asarray(rec["corners_norm"], float).reshape(-1, 2)
            proj_res = _HUMAN_PROJ_RES
        elif "corners" in rec and rec.get("W"):                      # legacy per-res format
            if k.split("@")[0] in new_stems:                         # same logo re-annotated -> skip
                continue
            norm = np.asarray(rec["corners"], float).reshape(-1, 2) / [rec["W"], rec["H"]]
            proj_res = [int(rec.get("res", 200))]
        else:
            continue
        for res in proj_res:
            try:
                regions = svg_region_masks(file, target=res)
            except Exception:
                continue
            for mask, _ in regions:
                H2, W2 = mask.shape
                corners = norm * [W2, H2] if len(norm) else norm    # project -> this frame
                for loop in mask_loops(mask):
                    if len(loop) > 1 and np.allclose(loop[0], loop[-1]):
                        loop = loop[:-1]
                    loop = _to_ccw(loop.astype(np.float64))
                    if len(loop) < 4 * s + 4:
                        continue
                    clean = _clean_corners_on_loop(loop, corners)      # re-centre + drop soft
                    prepared.append((featurize(loop, s), _labels(loop, clean)))
    random.Random(0).shuffle(prepared)                              # fair subsample under the cap
    features, labels, total = [], [], 0
    for _ in range(repeat):                                          # whole rounds keep all logos
        for base, target in prepared:
            for variant in _augment(base, s):
                features.append(variant)
                labels.append(target)
                total += len(variant)
        if total >= max_rows:
            break
    if not features:
        return empty
    return np.vstack(features), np.concatenate(labels)


def _paper_dataset(s: int, repeat: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """The Hoshyari 2018 released training set (Paper_training/): real human corner GT already
    in boundary-loop + corner-index form, so labels sit on the EXACT vertex (no snap error).
    One example per (shape, resolution); the per-resolution re-annotation is the paper's own
    fix for corners shifting under downsampling."""
    empty = (np.zeros((0, 4 * s + N_EXTRA), np.float64), np.zeros(0, np.int8))
    try:
        import paper_data
    except Exception:
        return empty
    max_rows = 2_000_000
    prepared = []                                                    # featurize each example once
    for loop, cxy, res, name in paper_data.paper_examples():
        loop = _to_ccw(loop.astype(np.float64))
        if len(loop) < 4 * s + 4:
            continue
        prepared.append((featurize(loop, s), _labels(loop, cxy)))
    random.Random(1).shuffle(prepared)
    features, labels, total = [], [], 0
    for _ in range(repeat):                                          # whole rounds -> fair under cap
        for base, target in prepared:
            for variant in _augment(base, s):
                features.append(variant)
                labels.append(target)
                total += len(variant)
        if total >= max_rows:
            break
    if not features:
        return empty
    return np.vstack(features), np.concatenate(labels)


def train(out_path: Path = MODEL_PATH, shapes: int = 1200, s: int = NEIGHBORHOOD,
          svg_dir: Path = SVG_GROUND_TRUTH, cap: int = 260_000, corpus_n: int = 0,
          text_n: int = 0, neg_n: int = 0, human_repeat: int = 0, paper_repeat: int = 0) -> dict:
    from sklearn.ensemble import RandomForestClassifier
    import joblib

    x_syn, y_syn = _build_dataset(1, shapes, s)
    # REAL logo SVGs (Sec 4.2): held out per-file for an honest real-data test report.
    svg_files = sorted(svg_dir.glob("*.svg")) if svg_dir and svg_dir.is_dir() else []
    n_test = max(1, len(svg_files) // 6)
    svg_train_files, svg_test_files = svg_files[n_test:], svg_files[:n_test]
    x_real, y_real = _svg_dataset(svg_dir, [128, 190, 300], s, svg_train_files) if svg_train_files else (
        np.zeros((0, 4 * s + N_EXTRA)), np.zeros(0, np.int8))
    parts_x, parts_y = [x_syn, x_real], [y_syn, y_real]
    # Big 700k-SVG corpus (icons/logos) across resolutions — the volume that drives down
    # spurious corners on curves.
    if corpus_n > 0:
        cfiles = _corpus_files(corpus_n, seed=7)
        x_corp, y_corp = _corpus_dataset(cfiles, s, seed=11)
        parts_x.append(x_corp); parts_y.append(y_corp)
        print(f"corpus: {len(cfiles)} files -> {len(y_corp)} samples", flush=True)
    # Synthetic WORDS (real fonts) with clean structural corner labels — the text signal
    # real wordmark logos need but the icon corpus/primitives lack.
    if text_n > 0:
        x_txt, y_txt = _text_dataset(text_n, s, seed=23)
        parts_x.append(x_txt); parts_y.append(y_txt)
        print(f"text: {text_n} strings -> {len(y_txt)} samples", flush=True)
    # Small SMOOTH negatives to rebalance small-resolution data (stop false corners on
    # small icons' staircase boundaries).
    if neg_n > 0:
        x_neg, y_neg = _smooth_negatives(neg_n, s, seed=31)
        parts_x.append(x_neg); parts_y.append(y_neg)
        print(f"smooth-neg: {neg_n} -> {len(y_neg)} samples", flush=True)
    # HUMAN-annotated perceptual corners (gold; upweighted) — overrides geometric labels.
    if human_repeat > 0:
        x_h, y_h = _human_dataset(s, repeat=human_repeat)
        parts_x.append(x_h); parts_y.append(y_h)
        print(f"human: {len(y_h)} samples (repeat={human_repeat})", flush=True)
    # PAPER human GT (Hoshyari 2018) — clean per-resolution corner labels; strong at the low
    # resolutions where our single model is weakest.
    if paper_repeat > 0:
        x_p, y_p = _paper_dataset(s, repeat=paper_repeat)
        parts_x.append(x_p); parts_y.append(y_p)
        print(f"paper: {len(y_p)} samples (repeat={paper_repeat})", flush=True)
    parts_x = [a for a in parts_x if len(a)]
    parts_y = [a for a in parts_y if len(a)]
    x_train = np.vstack(parts_x)
    y_train = np.concatenate(parts_y)

    # Test on held-out REAL logos (the metric that matters) + a synthetic set.
    x_rtest, y_rtest = _svg_dataset(svg_dir, [200], s, svg_test_files) if svg_test_files else (
        np.zeros((0, 4 * s + N_EXTRA)), np.zeros(0, np.int8))
    x_stest, y_stest = _build_dataset(9999, max(200, shapes // 4), s)

    # Subsample + capped depth/leaf keep the serialized forest manageable; this is only
    # the lax high-recall set — corner removal (paper Sec 5) restores precision downstream.
    if len(y_train) > cap:
        pick = np.random.default_rng(0).choice(len(y_train), cap, replace=False)
        x_train, y_train = x_train[pick], y_train[pick]
    model = RandomForestClassifier(
        n_estimators=100, max_depth=22, min_samples_leaf=10, max_features="sqrt",
        class_weight="balanced", n_jobs=-1, random_state=0,
    )
    model.fit(x_train, y_train)
    report = {"s": s, "train_samples": int(len(y_train)), "positive_rate": round(float(y_train.mean()), 4),
              "real_train_files": len(svg_train_files), "real_test_files": len(svg_test_files)}
    for name, xt, yt in (("real", x_rtest, y_rtest), ("synth", x_stest, y_stest)):
        if len(yt) == 0:
            continue
        prob = model.predict_proba(xt)[:, 1]
        for threshold in (0.125, 0.3, 0.5):
            pred = prob >= threshold
            tp = int((pred & (yt == 1)).sum()); fp = int((pred & (yt == 0)).sum()); fn = int((~pred & (yt == 1)).sum())
            report[f"{name}_thr_{threshold}"] = {"precision": round(tp / max(1, tp + fp), 3),
                                                 "recall": round(tp / max(1, tp + fn), 3)}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "s": s, "resolutions": TRAIN_RES, "report": report}, out_path)
    return {"path": str(out_path), **report}


def _val_by_res(s: int, resolutions: list[int], files: list[Path]) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Validation features+labels (NO augmentation) from real logos, grouped by the
    render resolution — for per-resolution operating-point calibration (Fig 7)."""
    from svg_corners import svg_region_masks

    out: dict[int, tuple[list, list]] = {r: ([], []) for r in resolutions}
    for f in files:
        for res in resolutions:
            try:
                regions = svg_region_masks(str(f), target=res)
            except Exception:
                continue
            for mask, corners in regions:
                for loop in mask_loops(mask):
                    if len(loop) > 1 and np.allclose(loop[0], loop[-1]):
                        loop = loop[:-1]
                    loop = _to_ccw(loop.astype(np.float64))
                    if len(loop) < 4 * s + 4:
                        continue
                    vcorners = _validate_svg_corners(loop, corners)
                    if _region_too_dense(loop, vcorners):
                        continue
                    out[res][0].append(featurize(loop, s))
                    out[res][1].append(_labels(loop, vcorners))
    return {r: (np.vstack(fx), np.concatenate(fy)) for r, (fx, fy) in out.items() if fx}


def calibrate_thresholds(model, s: int, target_recall: float = 0.95,
                         svg_dir: Path = SVG_GROUND_TRUTH, n_files: int = 120) -> dict[int, float]:
    """Paper Fig 7: the initial LAX corner set is taken at the operating point giving
    ~95% recall, chosen PER RESOLUTION.  For each resolution find the probability cutoff
    at which target_recall of true corners survive (the 5th percentile of positive-class
    probabilities); store a {resolution: threshold} table."""
    files = sorted(svg_dir.glob("*.svg"))[:n_files]
    resolutions = [16, 24, 32, 48, 64, 96, 128, 200, 300]
    table: dict[int, float] = {}
    for res, (x, y) in _val_by_res(s, resolutions, files).items():
        if len(y) == 0 or int(y.sum()) < 20:
            continue
        prob = model.predict_proba(x)[:, 1]
        thr = float(np.quantile(prob[y == 1], 1.0 - target_recall))
        # CLAMP into [0.50, 0.60]: where the model is UNSURE (small resolutions), the raw
        # 95%-recall point drops very low (e.g. 32px -> 0.2) and FLOODS the lax set with false
        # corners on small smooth icons.  NOTE: the RF is only the pipeline FALLBACK now (the
        # CNN is primary); HPO measured its held-out optimum near 0.65, so if the fallback ever
        # matters again this clamp ceiling should be revisited.
        table[res] = float(min(0.6, max(0.50, thr)))
    return table


def load(path: Path = MODEL_PATH):
    import joblib

    bundle = joblib.load(path)
    return bundle["model"], int(bundle["s"])


def load_thresholds(path: Path = MODEL_PATH) -> dict[int, float]:
    import joblib

    try:
        return joblib.load(path).get("thresholds", {}) or {}
    except Exception:
        return {}


def predict_corners(loop: np.ndarray, model, s: int = NEIGHBORHOOD, threshold: float = 0.4, nms_radius: float = 2.5) -> np.ndarray:
    """Boolean per-vertex corner mask for a native-resolution boundary loop.

    Non-maximum suppression keeps the highest-probability vertex within any
    `nms_radius` window so a single corner is not reported several times.
    """
    n = len(loop)
    if n < 4 * s + 4:
        return np.zeros(n, bool)
    # normalize winding like training (_to_ccw) and map the mask back — holes arrive CW
    x_, y_ = loop[:, 0], loop[:, 1]
    _area = float(np.sum(x_ * np.roll(y_, -1) - np.roll(x_, -1) * y_))
    _rev = _area < 0
    if _rev:
        loop = loop[::-1]
    probability = model.predict_proba(featurize(loop, s))[:, 1]
    order = np.argsort(-probability)
    chosen: list[int] = []
    result = np.zeros(n, bool)
    for i in order:
        if probability[i] < threshold:
            break
        if all(np.linalg.norm(loop[i] - loop[c]) >= nms_radius for c in chosen):
            chosen.append(int(i))
    result[chosen] = True
    return result[::-1].copy() if _rev else result


def native_mask(mask: np.ndarray, scale: int) -> np.ndarray:
    """Downscale a 4x analysis mask back to the native resolution the model expects."""
    if scale <= 1:
        return mask.astype(bool)
    h, w = mask.shape
    nh, nw = h // scale, w // scale
    block = mask[: nh * scale, : nw * scale].reshape(nh, scale, nw, scale).mean(axis=(1, 3))
    return block >= 0.5


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--calibrate", action="store_true", help="compute per-resolution thresholds (Fig 7) into the model bundle")
    parser.add_argument("--shapes", type=int, default=1200)
    parser.add_argument("--corpus", type=int, default=0, help="sample this many SVGs from the big corpus")
    parser.add_argument("--text", type=int, default=0, help="add this many synthetic font-word samples")
    parser.add_argument("--neg", type=int, default=0, help="add this many small smooth-negative shapes")
    parser.add_argument("--human", type=int, default=0, help="upweight (repeat Nx) human-annotated corners")
    parser.add_argument("--paper", type=int, default=0, help="upweight (repeat Nx) the Hoshyari 2018 paper GT")
    parser.add_argument("--cap", type=int, default=260_000)
    parser.add_argument("--out", type=Path, default=MODEL_PATH)
    args = parser.parse_args()
    if args.train:
        import json

        print(json.dumps(train(args.out, args.shapes, cap=args.cap, corpus_n=args.corpus, text_n=args.text, neg_n=args.neg, human_repeat=args.human, paper_repeat=args.paper), indent=2))
    elif args.calibrate:
        import joblib, json

        bundle = joblib.load(args.out)
        table = calibrate_thresholds(bundle["model"], int(bundle["s"]))
        bundle["thresholds"] = table
        joblib.dump(bundle, args.out)
        print(json.dumps({"thresholds": {str(k): round(v, 3) for k, v in sorted(table.items())}}, indent=2))
    else:
        parser.error("Use --train (inference is called from the pipeline).")


if __name__ == "__main__":
    main()

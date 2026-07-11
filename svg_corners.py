"""Ground-truth corner extraction from real logo SVGs (for training the Sec 4 corner
detector on REAL data, as the paper does).

An SVG path already encodes where corners are: at a junction between two segments
where the unit tangents disagree (a line meeting a line/curve at an angle, or two
curves meeting non-smoothly) there is a C0 corner; a tangent-continuous join is
smooth (no corner).  We rasterize each fill path to a region mask and return the
corner points in raster coordinates, so corner_classifier can featurize+label real
boundaries exactly like the synthetic ones.
"""
from __future__ import annotations

import cmath
import math

import numpy as np
from PIL import Image, ImageDraw

CORNER_ANGLE = 28.0  # deg: tangent discontinuity above this is a perceived C0 corner


def _seg_len(seg) -> float:
    try:
        return float(abs(seg.length()))
    except Exception:
        return float(abs(seg.end - seg.start))


def _sample_subpath(sub, px_per_unit: float) -> list[complex]:
    pts: list[complex] = []
    for seg in sub:
        n = max(2, int(_seg_len(seg) * px_per_unit / 1.5))
        for k in range(n):
            pts.append(seg.point(k / n))
    return pts


def _wrap(a: float) -> float:
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def _path_corners(sub, px_per_unit: float, step_px: float = 0.4, w_inner: float = 1.5,
                  t_min: float = 30.0, rho: float = 0.85, nms_px: float = 2.6) -> list[complex]:
    """Perceptual corners of a continuous subpath by WINDOWED ACCUMULATED TURNING with a
    two-window SATURATION test (IPAN99 / AutoTrace / potrace-alphamax family; confirmed by
    a literature survey as the standard tool for exactly this problem).

    We densely sample the ANALYTIC path (no raster staircase noise) and accumulate the
    SIGNED tangent turn over a small inner window (+/- w_inner px) and a wider outer window
    (+/- 2*w_inner).  A point is a corner iff:
      (a) |inner turn| >= t_min  — it actually bends enough, AND
      (b) |inner turn| >= rho * |outer turn|  — the turning SATURATES: the inner window
          already holds most of it, so the bend is LOCAL.  A smooth or merely tight curve
          keeps accumulating turn as the window grows (outer ~= 2*inner -> ratio ~0.5), so
          it fails (b) and is rejected — this is what separates a fillet/vertex from an
          S/O/B bowl.  Signed accumulation cancels at inflections, so a smooth S-reversal
          never fires.  Windows are in OUTPUT PIXELS, so a physical rounding fillet flips
          from 'corner' to 'smooth round' as the render grows — the paper's 'corner is
          perceived at the operating scale'.  Greedy NMS by strength -> one label/corner
          (a thin bar keeps a corner at each end; a wider-than-nms fillet never doubles)."""
    pts: list[complex] = []
    angs: list[float] = []
    for seg in sub:
        L = _seg_len(seg) * px_per_unit
        n = max(2, int(L / step_px))
        for k in range(n):
            t = k / n
            pts.append(seg.point(t))
            try:
                tg = seg.unit_tangent(t)
            except (ValueError, ZeroDivisionError, AssertionError):
                p2 = seg.point(min(1.0, t + 1e-3)) - seg.point(t)
                tg = p2 if abs(p2) > 1e-12 else complex(1.0, 0.0)
            angs.append(math.atan2(tg.imag, tg.real))
    m = len(pts)
    if m < 6:
        return []
    step = np.array([abs(pts[(i + 1) % m] - pts[i]) * px_per_unit for i in range(m)])
    dth = np.array([_wrap(angs[(i + 1) % m] - angs[i]) for i in range(m)])
    w_out = 2.0 * w_inner
    w_far = 2.0 * w_out                                  # widest window: total turn = acuteness
    din = np.zeros(m)
    dout = np.zeros(m)
    dfar = np.zeros(m)
    for i in range(m):
        acc = 0.0; d = 0.0; j = i                       # backward
        while d < w_far:
            j = (j - 1) % m
            acc += dth[j]; d += step[j]
            if d <= w_inner:
                din[i] += dth[j]
            if d <= w_out:
                dout[i] += dth[j]
            if j == i:
                break
        dfar[i] = acc
        acc = 0.0; d = 0.0; k = i                       # forward
        while d < w_far:
            acc += dth[k]; d += step[k]
            if d <= w_inner:
                din[i] += dth[k]
            if d <= w_out:
                dout[i] += dth[k]
            k = (k + 1) % m
            if k == i:
                break
        dfar[i] += acc
    turn = np.abs(np.degrees(din))
    farturn = np.abs(np.degrees(dfar))
    # A corner is EITHER a locally-sharp bend (turning SATURATES in the inner window: small
    # fillet / clean vertex) OR an ACUTE POINT (a sharp tip whose TOTAL turn is large, e.g.
    # a diamond/ribbon/swoosh tip, even if its fillet is a few px so it fails saturation).
    # The acute test needs a guard so a small SMOOTH circle (also high total turn) is not
    # flagged: on a circle the turn grows ~linearly with window, so din/dfar ~ w_inner/w_far
    # ~ 0.25; on a real point the turn is front-loaded, so din/dfar stays high (>=0.4).
    saturated = np.abs(din) >= rho * np.abs(dout)
    acute = (farturn >= 110.0) & (np.abs(din) >= 0.4 * np.maximum(np.abs(dfar), 1e-9))
    cand = np.flatnonzero((turn >= t_min) & (saturated | acute))
    if len(cand) == 0:
        return []
    adth = np.abs(dth)

    def refine(i: int) -> int:
        # The window turn is a PLATEAU across +/-w_inner of a sharp corner (all its turn is
        # in one step), so the candidate index is poorly localised.  Snap to the sharpest
        # actual turning step in the window: exact vertex for a sharp corner, apex for a
        # fillet.  Returns the index of the point AFTER the sharpest step (the turn's site).
        best_k, best = i, adth[i]
        d = 0.0; j = i
        while d < w_inner:
            j = (j - 1) % m; d += step[j]
            if adth[j] > best:
                best, best_k = adth[j], j
            if j == i:
                break
        d = 0.0; k = i
        while d < w_inner:
            if adth[k] > best:
                best, best_k = adth[k], k
            d += step[k]; k = (k + 1) % m
            if k == i:
                break
        return (best_k + 1) % m

    order = cand[np.argsort(-turn[cand])]               # greedy NMS by sharpness
    kept_pos: list[complex] = []
    for i in order:
        p = pts[refine(int(i))]
        if all(abs(p - q) * px_per_unit > nms_px for q in kept_pos):
            kept_pos.append(p)
    return kept_pos


def svg_region_masks(svg_path: str, target: int = 200, margin_frac: float = 0.06):
    """Return (mask, corners_xy) for each fill path of the SVG, sharing one raster frame
    ~`target` px on its long side.  mask is uint8 HxW; corners_xy is (k,2) float."""
    from svgpathtools import svg2paths

    paths, _ = svg2paths(svg_path)
    if not paths:
        return []
    boxes = []
    for p in paths:
        try:
            boxes.append(p.bbox())
        except Exception:
            pass
    if not boxes:
        return []
    xmin = min(b[0] for b in boxes); xmax = max(b[1] for b in boxes)
    ymin = min(b[2] for b in boxes); ymax = max(b[3] for b in boxes)
    span = max(xmax - xmin, ymax - ymin, 1e-6)
    scale = target / span
    margin = target * margin_frac
    W = int(round((xmax - xmin) * scale + 2 * margin))
    H = int(round((ymax - ymin) * scale + 2 * margin))
    W, H = max(W, 8), max(H, 8)

    def to_px(z: complex) -> tuple[float, float]:
        return ((z.real - xmin) * scale + margin, (z.imag - ymin) * scale + margin)

    out = []
    for p in paths:
        subs = p.continuous_subpaths()
        if not subs:
            continue
        acc = np.zeros((H, W), np.uint8)
        corners: list[tuple[float, float]] = []
        for sub in subs:
            poly = [to_px(z) for z in _sample_subpath(sub, scale)]
            if len(poly) >= 3:
                layer = Image.new("1", (W, H), 0)
                ImageDraw.Draw(layer).polygon(poly, fill=1)
                acc ^= np.asarray(layer, np.uint8)  # even-odd across subpaths (holes)
            for z in _path_corners(sub, scale):
                corners.append(to_px(z))
        if acc.sum() < 4:
            continue
        out.append((acc, np.asarray(corners, float).reshape(-1, 2)))
    return out

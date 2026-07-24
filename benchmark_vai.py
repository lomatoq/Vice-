"""Stage-0 harness (METHOD_ICE_BY.md §4): paired A/B against real vectorizer.ai output.

Corpus: C:/Users/nirrt/Toolset/v-ice pictures/vai/<stem>_vai.svg  (real VAI SVGs)
        C:/Users/nirrt/Toolset/v-ice pictures/CORPUS_REVIEW/<stem>.png  (sources)

Per image, both OUR SVG and the VAI SVG get the same artifact meters:
  geometry (from path data, resolution-normalized to native px):
    wobble        mean of (dkappa/ds)^2 integrated inside segments, per unit length
    g2_steps      mean |delta kappa| across G1-smooth joins (tangent jump < 4 deg)
    kinks_per_100px  joins with tangent jump in [4, 25) deg — unintended kinks
    staircase_runs   runs of >=4 consecutive sub-2.2px segments with alternating
                     near-orthogonal turns — vectorized jaggies
    micro_segs    segments with chord < 0.75px
  raster (render vs source):
    ink_iou, mae, rmse (sanity floor only — idealization legally moves pixels)
    seam_px       native-px^2 area of thin enclosed background-colored cracks
                  at 4x that are NOT background in the source
    ssim          grayscale SSIM at native scale
    roundness     mean relative radial RMS over circle-intent subpaths
    mirror_iou    best vertical/horizontal mirror self-IoU of the ink (source
                  column shows the intent ceiling)

Usage:
  python benchmark_vai.py [--mode paper-regions] [--n 50] [--all] [--reuse]
                          [--stems a,b,c]
Snapshot: benchmarks/vai_snapshot.json (previous kept as vai_snapshot_prev.json).
Primary gates per METHOD_ICE: staircase_runs, seam_px, wobble, judge win-rate.
MAE/RMSE are diagnostics, never acceptance criteria.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
from PIL import Image

VAI_DIR = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/vai")
SRC_DIRS = [Path(r"C:/Users/nirrt/Toolset/v-ice pictures/problem cases/Small"),
            ROOT / "web_preview/uploads"]
OUT = ROOT / "benchmarks"
WORK = OUT / "vai_work"

_SRC_INDEX: dict[str, Path] | None = None


def _source_index() -> dict[str, Path]:
    """stem -> the ACTUAL raster VAI processed (NNN_<stem>_src.png files).

    CORPUS_REVIEW/<stem>.png files are often different renditions (e.g.
    betsoft_512.png is 2548x420 while the VAI svg viewBox is 512x256), so only
    *_src.png files are trusted, validated by viewBox aspect at pairing time.
    """
    global _SRC_INDEX
    if _SRC_INDEX is None:
        import re as _re
        _SRC_INDEX = {}
        for d in SRC_DIRS:
            if not d.exists():
                continue
            for f in sorted(d.glob("*_src.png")):
                m = _re.match(r"^\d+_(.+)_src$", f.stem)
                key = m.group(1) if m else f.stem[:-4]
                _SRC_INDEX.setdefault(key, f)
    return _SRC_INDEX


def find_source(stem: str) -> Path | None:
    idx = _source_index()
    src = idx.get(stem) or idx.get(stem + "_vai")
    if src is None:
        return None
    import re as _re
    vai_svg = VAI_DIR / f"{stem}_vai.svg"
    m = _re.search(r'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)',
                   vai_svg.read_text(encoding="utf-8", errors="replace"))
    if m:
        vb_w, vb_h = float(m.group(1)), float(m.group(2))
        W, H = Image.open(src).size
        if vb_w > 0 and vb_h > 0 and abs((W / H) / (vb_w / vb_h) - 1.0) > 0.05:
            return None  # aspect mismatch: not the raster VAI actually saw
    return src


# ------------------------------------------------------------------ rendering
def render_svg(svg_path: Path, width: int) -> Image.Image:
    import resvg_py
    png = resvg_py.svg_to_bytes(svg_string=svg_path.read_text(encoding="utf-8"),
                                width=width)
    img = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    base = Image.new("RGB", img.size, (255, 255, 255))
    base.paste(img, mask=img.split()[3])
    return base


def _bg_of(arr: np.ndarray) -> np.ndarray:
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    return np.median(border, axis=0)


# ------------------------------------------------------------------ eye-aligned meters (Council N1)
def _delta_e_map(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """CIEDE2000 map with a deterministic Lab-distance fallback."""
    try:
        from skimage.color import deltaE_ciede2000, rgb2lab
        lab_a = rgb2lab(np.clip(first, 0, 255).astype(np.uint8))
        lab_b = rgb2lab(np.clip(second, 0, 255).astype(np.uint8))
        return np.asarray(deltaE_ciede2000(lab_a, lab_b), np.float32)
    except Exception:
        a = cv2.cvtColor(np.clip(first, 0, 255).astype(np.uint8),
                         cv2.COLOR_RGB2LAB).astype(np.float32)
        b = cv2.cvtColor(np.clip(second, 0, 255).astype(np.uint8),
                         cv2.COLOR_RGB2LAB).astype(np.float32)
        return np.linalg.norm(a - b, axis=2)


def local_defeat_meter(ren: np.ndarray, src_img: np.ndarray,
                       window_px: int = 32, stride_px: int = 8) -> dict:
    """Worst local colour error: the eye max-pools defects, unlike global MAE.

    Council N1 contract: 32px windows on an 8px stride.  Small images use the
    largest full-image window available.  Coordinates name the winning window
    centre so the crop court can show the exact defect rather than a whole icon.
    """
    de = _delta_e_map(ren, src_img)
    h, w = de.shape
    wh, ww = min(window_px, h), min(window_px, w)
    ys = list(range(0, max(1, h - wh + 1), max(1, stride_px)))
    xs = list(range(0, max(1, w - ww + 1), max(1, stride_px)))
    if ys[-1] != h - wh:
        ys.append(h - wh)
    if xs[-1] != w - ww:
        xs.append(w - ww)
    integral = cv2.integral(de, sdepth=cv2.CV_64F)
    y = np.asarray(ys, dtype=int)[:, None]
    x = np.asarray(xs, dtype=int)[None, :]
    sums = (integral[y + wh, x + ww] - integral[y, x + ww]
            - integral[y + wh, x] + integral[y, x])
    means = sums / float(wh * ww)
    iy, ix = np.unravel_index(int(np.argmax(means)), means.shape)
    return {
        "local_de_max": round(float(means[iy, ix]), 4),
        "local_de_x": int(xs[ix] + ww // 2),
        "local_de_y": int(ys[iy] + wh // 2),
        "local_de_window": [int(ww), int(wh)],
    }


def _bbox_iou(first, second) -> float:
    ax0, ay0, ax1, ay1 = map(float, first)
    bx0, by0, bx1, by1 = map(float, second)
    iw = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    ih = max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = iw * ih
    union = max(0.0, (ax1 - ax0) * (ay1 - ay0)) + max(0.0, (bx1 - bx0) * (by1 - by0)) - inter
    return inter / union if union > 0 else 0.0


def _normal_text(text: str) -> str:
    return "".join(ch.upper() for ch in text if ch.isalnum())


def _normal_levenshtein(first: str, second: str) -> float:
    """Normalized edit distance in [0,1], dependency-free."""
    a, b = _normal_text(first), _normal_text(second)
    if not a and not b:
        return 0.0
    if not a or not b:
        return 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return float(prev[-1]) / max(len(a), len(b))


def ocr_legibility_meter(source: Image.Image, rendered: Image.Image) -> dict:
    """OCR line loss after symmetric 2x LANCZOS rendering.

    Source lines are the obligations.  A missing line or bbox-IoU below 0.5
    costs 1.0; matched lines pay normalized Levenshtein distance.  This makes
    destroyed tiny glyphs visible even when whole-image SSIM barely moves.
    """
    from text_substitution import ocr_lines
    scale = 2
    size = (source.width * scale, source.height * scale)
    src_lines = ocr_lines(source.convert("RGB").resize(size, Image.Resampling.LANCZOS))
    ren_lines = ocr_lines(rendered.convert("RGB").resize(size, Image.Resampling.LANCZOS))
    if not src_lines:
        return {"ocr_legibility": None, "ocr_source_lines": 0,
                "ocr_render_lines": len(ren_lines), "ocr_matched_lines": 0}
    unused = set(range(len(ren_lines)))
    losses: list[float] = []
    matched = 0
    for src_line in src_lines:
        candidates = [(float(_bbox_iou(src_line["bbox"], ren_lines[j]["bbox"])), j)
                      for j in unused]
        overlap, best = max(candidates, default=(0.0, -1))
        if best < 0 or overlap < 0.5:
            losses.append(1.0)
            continue
        unused.remove(best)
        matched += 1
        losses.append(_normal_levenshtein(src_line["text"], ren_lines[best]["text"]))
    return {"ocr_legibility": round(float(np.mean(losses)), 4),
            "ocr_source_lines": len(src_lines), "ocr_render_lines": len(ren_lines),
            "ocr_matched_lines": matched}


def _component_holes(mask: np.ndarray) -> int:
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP,
                                           cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None or not contours:
        return 0
    return int(np.count_nonzero(hierarchy[0, :, 3] >= 0))


def _palette_components(labels: np.ndarray, background: int,
                        area_floor: int = 4) -> list[dict]:
    out: list[dict] = []
    for anchor in np.unique(labels):
        anchor = int(anchor)
        if anchor == background:
            continue
        count, component_labels, stats, _ = cv2.connectedComponentsWithStats(
            (labels == anchor).astype(np.uint8), connectivity=8)
        for component in range(1, count):
            area = int(stats[component, cv2.CC_STAT_AREA])
            if area < area_floor:
                continue
            mask = component_labels == component
            out.append({"anchor": anchor, "mask": mask, "area": area,
                        "holes": _component_holes(mask)})
    return out


def component_census_meter(ren: np.ndarray, src_img: np.ndarray,
                           area_floor: int = 4) -> dict:
    """Two-sided component/hole census after projection to source anchors."""
    from subpixel_mininet import compact_palette
    src_u8 = np.clip(src_img, 0, 255).astype(np.uint8)
    ren_u8 = np.clip(ren, 0, 255).astype(np.uint8)
    anchors = np.asarray(compact_palette(Image.fromarray(src_u8), colors=16), np.float32)
    if not len(anchors):
        return {"census_errors": None}
    src_dist = np.sum((src_u8[..., None, :].astype(np.float32) - anchors) ** 2, axis=3)
    ren_dist = np.sum((ren_u8[..., None, :].astype(np.float32) - anchors) ** 2, axis=3)
    src_labels = np.argmin(src_dist, axis=2).astype(np.int16)
    ren_labels = np.argmin(ren_dist, axis=2).astype(np.int16)
    bg = _bg_of(src_u8)
    background = int(np.argmin(np.sum((anchors - bg) ** 2, axis=1)))
    source_components = _palette_components(src_labels, background, area_floor)
    render_components = _palette_components(ren_labels, background, area_floor)

    overlaps: dict[tuple[int, int], float] = {}
    reverse: dict[int, list[int]] = {}
    for si, source_component in enumerate(source_components):
        for ri, render_component in enumerate(render_components):
            if source_component["anchor"] != render_component["anchor"]:
                continue
            inter = int(np.count_nonzero(source_component["mask"] & render_component["mask"]))
            if inter:
                overlaps[(si, ri)] = inter / float(source_component["area"])
                if inter / float(render_component["area"]) >= 0.20:
                    reverse.setdefault(ri, []).append(si)

    vanished = fused = holes_lost = holes_gained = 0
    matched_render: set[int] = set()
    for si, source_component in enumerate(source_components):
        choices = [(score, ri) for (source_index, ri), score in overlaps.items()
                   if source_index == si]
        score, best = max(choices, default=(0.0, -1))
        if best < 0 or score < 0.30:
            vanished += 1
            continue
        matched_render.add(best)
        source_holes = int(source_component["holes"])
        render_holes = int(render_components[best]["holes"])
        holes_lost += max(0, source_holes - render_holes)
        holes_gained += max(0, render_holes - source_holes)
    for source_indices in reverse.values():
        fused += max(0, len(set(source_indices)) - 1)
    added = sum(1 for ri in range(len(render_components))
                if ri not in matched_render and not reverse.get(ri))
    errors = vanished + fused + holes_lost + holes_gained + added
    return {"census_errors": int(errors), "components_source": len(source_components),
            "components_render": len(render_components), "components_vanished": vanished,
            "components_fused": fused, "components_added": added,
            "holes_lost": holes_lost, "holes_gained": holes_gained}


def _ink_from_background(image: np.ndarray, background: np.ndarray,
                         threshold: float) -> np.ndarray:
    """Perceptual foreground mask at a CIEDE2000 distance from the background."""
    rgb = np.clip(image, 0, 255).astype(np.uint8)
    bg = np.broadcast_to(np.asarray(background, np.uint8), rgb.shape)
    return _delta_e_map(rgb, bg) >= float(threshold)


def _clean_ink(mask: np.ndarray, area_floor: int) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8)
    clean = np.zeros(mask.shape, np.uint8)
    for component in range(1, count):
        if int(stats[component, cv2.CC_STAT_AREA]) >= area_floor:
            clean[labels == component] = 1
    return clean.astype(bool)


def _betti_numbers(mask: np.ndarray, area_floor: int) -> tuple[int, int]:
    clean = _clean_ink(mask, area_floor)
    count, _ = cv2.connectedComponents(clean.astype(np.uint8), connectivity=8)
    return max(0, int(count) - 1), _component_holes(clean)


def persistent_topology_meter(ren: np.ndarray, src_img: np.ndarray) -> dict:
    """Persistent beta0/beta1 signature over perceptual foreground levels.

    The levels are multiples of the standard CIEDE2000 just-noticeable distance,
    so topology has to survive more than one arbitrary binary threshold.  We
    report the full curves and their integrated discrepancy; downstream gates
    can distinguish a one-level AA flicker from a persistent lost counter.
    """
    background = _bg_of(src_img)
    levels = (2.3, 4.6, 9.2, 18.4)
    area_floor = max(2, int(round(src_img.shape[0] * src_img.shape[1] / 32768.0)))
    source_curve: list[tuple[int, int]] = []
    render_curve: list[tuple[int, int]] = []
    for level in levels:
        source_curve.append(_betti_numbers(
            _ink_from_background(src_img, background, level), area_floor))
        render_curve.append(_betti_numbers(
            _ink_from_background(ren, background, level), area_floor))

    beta0_delta = [abs(a[0] - b[0]) for a, b in zip(source_curve, render_curve)]
    beta1_delta = [abs(a[1] - b[1]) for a, b in zip(source_curve, render_curve)]
    lost_components = [max(0, a[0] - b[0]) for a, b in zip(source_curve, render_curve)]
    lost_holes = [max(0, a[1] - b[1]) for a, b in zip(source_curve, render_curve)]
    gained_holes = [max(0, b[1] - a[1]) for a, b in zip(source_curve, render_curve)]
    persistent_counter_loss = sum(value > 0 for value in lost_holes)
    return {
        "topology_levels_de": list(levels),
        "source_betti_curve": [[int(a), int(b)] for a, b in source_curve],
        "render_betti_curve": [[int(a), int(b)] for a, b in render_curve],
        "persistent_beta0_error": round(float(np.mean(beta0_delta)), 4),
        "persistent_beta1_error": round(float(np.mean(beta1_delta)), 4),
        "persistent_components_lost": round(float(np.mean(lost_components)), 4),
        "persistent_holes_lost": round(float(np.mean(lost_holes)), 4),
        "persistent_holes_gained": round(float(np.mean(gained_holes)), 4),
        "any_counter_failure": bool(persistent_counter_loss >= 2),
    }


def _cvar(values: np.ndarray | list[float], fraction: float = 0.10) -> float:
    samples = np.asarray(values, np.float64).reshape(-1)
    samples = samples[np.isfinite(samples)]
    if not len(samples):
        return 0.0
    count = max(1, int(math.ceil(len(samples) * float(fraction))))
    return float(np.mean(np.partition(samples, len(samples) - count)[-count:]))


def catastrophic_locus_meter(ren: np.ndarray, src_img: np.ndarray) -> dict:
    """Worst-locus structural damage rather than whole-image mean error.

    Boundary samples are measured in native pixels in both directions.  A
    locus is catastrophic when it misses the opposite boundary by more than
    one native pixel; the continuous CVaR and p99 stay available for calibration
    instead of hiding the result behind only a boolean threshold.
    """
    background = _bg_of(src_img)
    source_ink = _clean_ink(
        _ink_from_background(src_img, background, 4.6), 2)
    render_ink = _clean_ink(
        _ink_from_background(ren, background, 4.6), 2)
    kernel = np.ones((3, 3), np.uint8)
    source_edge = source_ink & ~cv2.erode(
        source_ink.astype(np.uint8), kernel, iterations=1).astype(bool)
    render_edge = render_ink & ~cv2.erode(
        render_ink.astype(np.uint8), kernel, iterations=1).astype(bool)

    distances: list[np.ndarray] = []
    damage_map = np.zeros(source_ink.shape, np.float32)
    if source_edge.any() and render_edge.any():
        to_render = cv2.distanceTransform((~render_edge).astype(np.uint8),
                                          cv2.DIST_L2, 5)
        to_source = cv2.distanceTransform((~source_edge).astype(np.uint8),
                                          cv2.DIST_L2, 5)
        distances.extend((to_render[source_edge], to_source[render_edge]))
        damage_map[source_edge] = to_render[source_edge]
        damage_map[render_edge] = np.maximum(
            damage_map[render_edge], to_source[render_edge])
    elif source_edge.any() or render_edge.any():
        diagonal = float(math.hypot(*source_ink.shape))
        edge = source_edge | render_edge
        damage_map[edge] = diagonal
        distances.append(np.full(int(edge.sum()), diagonal, np.float32))

    boundary_distances = (np.concatenate(distances) if distances
                          else np.zeros(1, np.float32))
    catastrophic = damage_map > 1.0
    locus_count = 0
    worst_locus = 0.0
    if catastrophic.any():
        grown = cv2.dilate(catastrophic.astype(np.uint8), kernel, iterations=1)
        count, labels = cv2.connectedComponents(grown, connectivity=8)
        locus_count = max(0, int(count) - 1)
        for label in range(1, count):
            support = labels == label
            values = damage_map[support & (damage_map > 0)]
            if len(values):
                worst_locus = max(worst_locus, float(np.percentile(values, 95)))

    de = _delta_e_map(ren, src_img)
    salient = source_ink | render_ink | source_edge | render_edge
    salient_de = de[salient] if salient.any() else de.reshape(-1)
    boundary_total = max(1, int(np.count_nonzero(source_edge | render_edge)))
    return {
        "catastrophic_locus_count": int(locus_count),
        "catastrophic_locus_rate": round(
            float(np.count_nonzero(catastrophic)) / boundary_total, 5),
        "worst_locus_severity": round(float(worst_locus), 4),
        "boundary_cvar10": round(_cvar(boundary_distances), 4),
        "boundary_p99": round(float(np.percentile(boundary_distances, 99)), 4),
        "detail_de_cvar10": round(_cvar(salient_de), 4),
    }


def _component_geometry(mask: np.ndarray, area_floor: int = 4) -> tuple[np.ndarray, list[dict]]:
    count, labels, stats, cents = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8)
    items: list[dict] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < area_floor:
            continue
        x = float(stats[label, cv2.CC_STAT_LEFT])
        y = float(stats[label, cv2.CC_STAT_TOP])
        width = float(stats[label, cv2.CC_STAT_WIDTH])
        height = float(stats[label, cv2.CC_STAT_HEIGHT])
        items.append({"label": label, "x": x, "y": y, "w": width, "h": height,
                      "cx": float(cents[label, 0]), "cy": float(cents[label, 1]),
                      "area": float(area), "radius": math.sqrt(area / math.pi)})
    return labels, items


def group_regularity_meter(ren: np.ndarray, src_img: np.ndarray) -> dict:
    """Continuous violations of repeated widths, heights, radii and gaps.

    Source components define the candidate group law.  Pair weights decay with
    source log-shape distance, then only *additional* irregularity in the render
    is charged.  This prevents the meter from idealizing a deliberately varied
    source while exposing one odd stem/circle in an otherwise repeated family.
    """
    background = _bg_of(src_img)
    source_ink = _clean_ink(_ink_from_background(src_img, background, 4.6), 4)
    render_ink = _clean_ink(_ink_from_background(ren, background, 4.6), 4)
    source_labels, source = _component_geometry(source_ink)
    render_labels, rendered = _component_geometry(render_ink)
    render_by_label = {int(item["label"]): item for item in rendered}
    matched: list[dict | None] = []
    kernel = np.ones((3, 3), np.uint8)
    for item in source:
        support = source_labels == int(item["label"])
        support = cv2.dilate(support.astype(np.uint8), kernel, iterations=1).astype(bool)
        labels, counts = np.unique(render_labels[support], return_counts=True)
        choices = [(int(count), int(label)) for label, count in zip(labels, counts)
                   if int(label) > 0 and int(label) in render_by_label]
        matched.append(render_by_label[max(choices)[1]] if choices else None)

    totals = {"width": 0.0, "height": 0.0, "radius": 0.0}
    weights = {key: 0.0 for key in totals}
    repeated_pairs = 0
    for i in range(len(source)):
        if matched[i] is None:
            continue
        for j in range(i + 1, len(source)):
            if matched[j] is None:
                continue
            a, b = source[i], source[j]
            shape_distance = math.hypot(
                math.log(max(a["w"], 1.0) / max(b["w"], 1.0)),
                math.log(max(a["h"], 1.0) / max(b["h"], 1.0)))
            weight = math.exp(-0.5 * (shape_distance / 0.18) ** 2)
            if weight < 0.05:
                continue
            repeated_pairs += int(weight >= 0.50)
            ra, rb = matched[i], matched[j]
            for key, field in (("width", "w"), ("height", "h")):
                source_delta = abs(math.log(max(a[field], 1.0) / max(b[field], 1.0)))
                render_delta = abs(math.log(max(ra[field], 1.0) / max(rb[field], 1.0)))
                totals[key] += weight * max(0.0, render_delta - source_delta)
                weights[key] += weight
            if 0.75 <= a["w"] / max(a["h"], 1.0) <= 1.33 and 0.75 <= b["w"] / max(b["h"], 1.0) <= 1.33:
                source_delta = abs(math.log(a["radius"] / b["radius"]))
                render_delta = abs(math.log(ra["radius"] / rb["radius"]))
                totals["radius"] += weight * max(0.0, render_delta - source_delta)
                weights["radius"] += weight

    violations = {key: totals[key] / weights[key] if weights[key] else 0.0
                  for key in totals}

    gap_deltas: list[float] = []
    for axis, cross, extent in (("x", "cy", "h"), ("y", "cx", "w")):
        order = sorted(range(len(source)), key=lambda index: source[index][cross])
        groups: list[list[int]] = []
        for index in order:
            for group in groups:
                centre = float(np.median([source[k][cross] for k in group]))
                tolerance = float(np.median([source[k][extent] for k in group + [index]])) * 0.55
                if abs(source[index][cross] - centre) <= max(1.0, tolerance):
                    group.append(index)
                    break
            else:
                groups.append([index])
        for group in groups:
            group = [index for index in group if matched[index] is not None]
            if len(group) < 3:
                continue
            group.sort(key=lambda index: source[index][axis])
            source_gaps, render_gaps = [], []
            for left, right in zip(group, group[1:]):
                end_field = "w" if axis == "x" else "h"
                source_gaps.append(source[right][axis] -
                                   (source[left][axis] + source[left][end_field]))
                render_gaps.append(matched[right][axis] -
                                   (matched[left][axis] + matched[left][end_field]))
            source_scale = max(1.0, float(np.mean(np.abs(source_gaps))))
            render_scale = max(1.0, float(np.mean(np.abs(render_gaps))))
            source_cv = float(np.std(source_gaps)) / source_scale
            render_cv = float(np.std(render_gaps)) / render_scale
            gap_deltas.append(max(0.0, render_cv - source_cv))

    gap_violation = max(gap_deltas, default=0.0)
    overall = max(violations["width"], violations["height"],
                  violations["radius"], gap_violation)
    return {
        "repeated_component_pairs": int(repeated_pairs),
        "equal_width_violation": round(float(violations["width"]), 5),
        "equal_height_violation": round(float(violations["height"]), 5),
        "repeated_radius_violation": round(float(violations["radius"]), 5),
        "equal_gap_violation": round(float(gap_violation), 5),
        "group_regularity_violation": round(float(overall), 5),
    }


def region_color_meter(ren: np.ndarray, src_img: np.ndarray,
                       area_floor: int = 4) -> dict:
    """Council N2 colour commitment on source-anchored region interiors.

    Geometry/AA disagreement at silhouettes must not masquerade as a palette
    error, so each compact-palette component is eroded by one pixel whenever
    it leaves a usable core.  The global p95 catches broad colour drift; the
    maximum component median catches one categorically wrong small element.
    """
    from subpixel_mininet import compact_palette

    src_u8 = np.clip(src_img, 0, 255).astype(np.uint8)
    ren_u8 = np.clip(ren, 0, 255).astype(np.uint8)
    anchors = np.asarray(compact_palette(Image.fromarray(src_u8), colors=16), np.float32)
    if not len(anchors):
        return {"region_de2000_p95": None, "de_region_max": None,
                "color_regions": 0}
    src_dist = np.sum((src_u8[..., None, :].astype(np.float32) - anchors) ** 2, axis=3)
    labels = np.argmin(src_dist, axis=2).astype(np.int16)
    background = int(np.argmin(np.sum((anchors - _bg_of(src_u8)) ** 2, axis=1)))
    de = _delta_e_map(ren_u8, src_u8)
    kernel = np.ones((3, 3), np.uint8)
    samples: list[np.ndarray] = []
    region_medians: list[float] = []
    for component in _palette_components(labels, background, area_floor):
        mask = component["mask"].astype(np.uint8)
        core = cv2.erode(mask, kernel, iterations=1).astype(bool)
        if int(core.sum()) < area_floor:
            core = mask.astype(bool)
        values = np.asarray(de[core], np.float32)
        if not len(values):
            continue
        samples.append(values)
        region_medians.append(float(np.median(values)))
    if not samples:
        return {"region_de2000_p95": None, "de_region_max": None,
                "color_regions": 0}
    all_values = np.concatenate(samples)
    return {"region_de2000_p95": round(float(np.percentile(all_values, 95)), 4),
            "de_region_max": round(float(max(region_medians)), 4),
            "color_regions": len(region_medians)}


def eye_meters(svg_path: Path, src: Path) -> dict:
    """Council N1 battery for one candidate SVG against its source raster."""
    source = Image.open(src).convert("RGB")
    src_img = np.asarray(source, float)
    h, w = src_img.shape[:2]
    rendered = render_svg(svg_path, w)
    if rendered.size != (w, h):
        rendered = rendered.resize((w, h), Image.Resampling.LANCZOS)
    ren = np.asarray(rendered, float)
    out = {}
    out.update(local_defeat_meter(ren, src_img))
    out.update(ocr_legibility_meter(source, rendered))
    out.update(component_census_meter(ren, src_img))
    out.update(region_color_meter(ren, src_img))
    bg = _bg_of(src_img)
    src_ink = np.sum(np.abs(src_img - bg), axis=2) > 90
    ren_ink = np.sum(np.abs(ren - bg), axis=2) > 90
    source_symmetry = round(mirror_iou(src_ink), 4)
    render_symmetry = round(mirror_iou(ren_ink), 4)
    source_rot90 = round(rot90_iou(src_ink), 4)
    render_rot90 = round(rot90_iou(ren_ink), 4)
    out.update({"source_mirror_iou": source_symmetry,
                "render_mirror_iou": render_symmetry,
                "sym_break": round(max(0.0, source_symmetry - render_symmetry), 4),
                "source_rot90_iou": source_rot90,
                "render_rot90_iou": render_rot90,
                "rot90_sym_break": round(max(0.0, source_rot90 - render_rot90), 4)})
    return out


# ------------------------------------------------------------------ geometry meters
def _svg_scale(svg_path: Path, native_w: int) -> float:
    import re
    text = svg_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)', text)
    if not m:
        return 1.0
    vb_w = float(m.group(1))
    return native_w / vb_w if vb_w > 0 else 1.0


def _parse_paths(svg_path: Path):
    """Parse rendered SVG geometry, including native shapes and transforms.

    The old regex counted only literal ``<path d>`` coordinates and silently
    ignored group transforms, circles, rects, ellipses, polygons and ``use``.
    That made geometry metrics depend on serialization style rather than the
    vector actually shown to the user.
    """
    import re as _re
    import xml.etree.ElementTree as ET
    from svgpathtools import (Arc, CubicBezier, Line, Path as SvgPath,
                              QuadraticBezier, parse_path)

    text = svg_path.read_text(encoding="utf-8", errors="replace")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        # Keep a fail-soft diagnostic path for malformed third-party SVG.
        result = []
        for d in _re.findall(r'<path\b[^>]*?\bd="([^"]+)"', text):
            try:
                value = parse_path(d)
                if len(value):
                    result.append(value)
            except Exception:
                continue
        return result

    identity = np.eye(3, dtype=np.float64)
    id_map = {element.attrib["id"]: element for element in root.iter()
              if "id" in element.attrib}
    paths = []

    def number(value, default=0.0):
        if value is None:
            return float(default)
        match = _re.search(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", value)
        return float(match.group(0)) if match else float(default)

    def local_name(element):
        return element.tag.rsplit("}", 1)[-1].lower()

    def transform_matrix(value):
        matrix = identity.copy()
        for name, payload in _re.findall(r"([A-Za-z]+)\s*\(([^)]*)\)", value or ""):
            values = [float(item) for item in _re.findall(
                r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", payload)]
            item = identity.copy()
            key = name.lower()
            if key == "matrix" and len(values) >= 6:
                a, b, c, d, e, f = values[:6]
                item = np.array(((a, c, e), (b, d, f), (0, 0, 1)), np.float64)
            elif key == "translate" and values:
                item[0, 2] = values[0]
                item[1, 2] = values[1] if len(values) > 1 else 0.0
            elif key == "scale" and values:
                item[0, 0] = values[0]
                item[1, 1] = values[1] if len(values) > 1 else values[0]
            elif key == "rotate" and values:
                angle = math.radians(values[0])
                c, s = math.cos(angle), math.sin(angle)
                rotation = np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)), np.float64)
                if len(values) >= 3:
                    cx, cy = values[1:3]
                    before = np.array(((1, 0, cx), (0, 1, cy), (0, 0, 1)), np.float64)
                    after = np.array(((1, 0, -cx), (0, 1, -cy), (0, 0, 1)), np.float64)
                    item = before @ rotation @ after
                else:
                    item = rotation
            elif key in {"skewx", "skewy"} and values:
                tangent = math.tan(math.radians(values[0]))
                item[0 if key == "skewx" else 1,
                     1 if key == "skewx" else 0] = tangent
            matrix = matrix @ item
        return matrix

    def map_point(value, matrix):
        row = matrix @ np.array((value.real, value.imag, 1.0), np.float64)
        return complex(float(row[0] / row[2]), float(row[1] / row[2]))

    def transformed(path, matrix):
        segments = []
        for segment in path:
            source = (segment.as_cubic_curves(
                curves=max(1, int(math.ceil(abs(segment.delta) / 90.0))))
                if isinstance(segment, Arc) else (segment,))
            for item in source:
                if isinstance(item, Line):
                    segments.append(Line(map_point(item.start, matrix),
                                         map_point(item.end, matrix)))
                elif isinstance(item, QuadraticBezier):
                    segments.append(QuadraticBezier(
                        map_point(item.start, matrix), map_point(item.control, matrix),
                        map_point(item.end, matrix)))
                elif isinstance(item, CubicBezier):
                    segments.append(CubicBezier(
                        map_point(item.start, matrix), map_point(item.control1, matrix),
                        map_point(item.control2, matrix), map_point(item.end, matrix)))
        return SvgPath(*segments)

    def shape_path(element, name):
        a = element.attrib
        if name == "path":
            return a.get("d", "")
        if name == "line":
            return f"M {number(a.get('x1'))} {number(a.get('y1'))} L {number(a.get('x2'))} {number(a.get('y2'))}"
        if name in {"polyline", "polygon"}:
            values = [number(item) for item in _re.findall(
                r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", a.get("points", ""))]
            if len(values) < 4:
                return ""
            commands = [f"M {values[0]} {values[1]}"]
            commands.extend(f"L {values[i]} {values[i + 1]}" for i in range(2, len(values) - 1, 2))
            if name == "polygon":
                commands.append("Z")
            return " ".join(commands)
        if name == "circle":
            cx, cy, radius = number(a.get("cx")), number(a.get("cy")), number(a.get("r"))
            return (f"M {cx-radius} {cy} A {radius} {radius} 0 1 0 {cx+radius} {cy} "
                    f"A {radius} {radius} 0 1 0 {cx-radius} {cy} Z")
        if name == "ellipse":
            cx, cy = number(a.get("cx")), number(a.get("cy"))
            rx, ry = number(a.get("rx")), number(a.get("ry"))
            return (f"M {cx-rx} {cy} A {rx} {ry} 0 1 0 {cx+rx} {cy} "
                    f"A {rx} {ry} 0 1 0 {cx-rx} {cy} Z")
        if name == "rect":
            x, y = number(a.get("x")), number(a.get("y"))
            width, height = number(a.get("width")), number(a.get("height"))
            rx = min(number(a.get("rx"), number(a.get("ry"), 0.0)), width * .5)
            ry = min(number(a.get("ry"), rx), height * .5)
            if rx <= 0 or ry <= 0:
                return f"M {x} {y} H {x+width} V {y+height} H {x} Z"
            return (f"M {x+rx} {y} H {x+width-rx} A {rx} {ry} 0 0 1 {x+width} {y+ry} "
                    f"V {y+height-ry} A {rx} {ry} 0 0 1 {x+width-rx} {y+height} "
                    f"H {x+rx} A {rx} {ry} 0 0 1 {x} {y+height-ry} "
                    f"V {y+ry} A {rx} {ry} 0 0 1 {x+rx} {y} Z")
        return ""

    skipped = {"defs", "clippath", "mask", "pattern", "metadata", "title", "desc"}

    def walk(element, parent_matrix, seen=()):
        name = local_name(element)
        style = element.attrib.get("style", "").replace(" ", "").lower()
        if element.attrib.get("display", "").lower() == "none" or "display:none" in style:
            return
        matrix = parent_matrix @ transform_matrix(element.attrib.get("transform", ""))
        if name == "use":
            href = (element.attrib.get("href") or
                    element.attrib.get("{http://www.w3.org/1999/xlink}href") or "")
            target_id = href[1:] if href.startswith("#") else ""
            if target_id and target_id in id_map and target_id not in seen:
                placement = identity.copy()
                placement[0, 2] = number(element.attrib.get("x"))
                placement[1, 2] = number(element.attrib.get("y"))
                walk(id_map[target_id], matrix @ placement, seen + (target_id,))
            return
        data = shape_path(element, name)
        if data:
            try:
                value = transformed(parse_path(data), matrix)
                if len(value):
                    paths.append(value)
            except Exception:
                pass
        if name in skipped and not seen:
            return
        for child in element:
            walk(child, matrix, seen)

    walk(root, identity)
    return paths


def geometry_meters(svg_path: Path, native_w: int) -> dict:
    """Path-space meters, coordinates normalized so 1 unit == 1 native pixel."""
    paths = _parse_paths(svg_path)
    if not paths:
        return {"wobble": None, "g2_steps": None, "kinks_per_100px": None,
                "staircase_runs": None, "micro_segs": None, "total_len": None,
                "segments": None}
    s = _svg_scale(svg_path, native_w)

    wobble_num = 0.0
    total_len = 0.0
    g2_steps: list[float] = []
    subcrease_angles: list[float] = []
    short_detail_severity: list[float] = []
    kinks = 0
    micro = 0
    stair_runs = 0
    n_segs = 0
    K = 8

    for path in paths:
        segs = [seg for seg in path if seg.length() > 1e-9]
        if not segs:
            continue
        n_segs += len(segs)
        # Per-segment analytic curvature -> wobble inside segments.
        seg_info = []  # (chord_px, tan_in, tan_out, k_in, k_out)
        for seg in segs:
            try:
                L = seg.length() * s
            except Exception:
                continue
            chord = abs(seg.end - seg.start) * s
            if chord < 0.75:
                micro += 1
            short_detail_severity.append(max(0.0, (2.2 - chord) / 2.2))
            total_len += L
            ts = [(i + 0.5) / K for i in range(K)]
            ks = []
            for t in ts:
                try:
                    ks.append(seg.curvature(t) / s)  # 1/px
                except Exception:
                    ks.append(0.0)
            ds = max(L / K, 1e-6)
            for a, b in zip(ks, ks[1:]):
                wobble_num += ((b - a) / ds) ** 2 * ds
            try:
                tan_in = seg.unit_tangent(0.02)
                tan_out = seg.unit_tangent(0.98)
            except Exception:
                d = seg.end - seg.start
                tan_in = tan_out = d / abs(d) if abs(d) > 0 else 1 + 0j
            seg_info.append((chord, tan_in, tan_out, ks[0], ks[-1]))

        # Joins (closed loop -> wrap around).
        m = len(seg_info)
        for i in range(m):
            j = (i + 1) % m
            if m == 1:
                break
            _, _, t_out, _, k_out = seg_info[i]
            _, t_in, _, k_in, _ = seg_info[j]
            dot = (t_out.real * t_in.real + t_out.imag * t_in.imag)
            ang = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
            if 0.0 < ang < 25.0:
                subcrease_angles.append(ang)
            if ang < 4.0:
                g2_steps.append(abs(k_in - k_out))
            elif ang < 25.0:
                kinks += 1

        # Staircase runs: >=4 consecutive short segments, alternating turns.
        chords = [c for c, *_ in seg_info]
        tangs = [(t_in, t_out) for _, t_in, t_out, _, _ in seg_info]
        run = 0
        last_cross_sign = 0
        for i in range(m):
            j = (i + 1) % m
            short = chords[i] < 2.2 and chords[j] < 2.2
            t_a, t_b = tangs[i][1], tangs[j][0]
            cross = t_a.real * t_b.imag - t_a.imag * t_b.real
            dot = t_a.real * t_b.real + t_a.imag * t_b.imag
            ang = math.degrees(math.atan2(abs(cross), dot))
            alternating = 55.0 <= ang <= 125.0 and (
                last_cross_sign == 0 or (cross > 0) != (last_cross_sign > 0))
            if short and alternating:
                run += 1
                last_cross_sign = 1 if cross > 0 else -1
                if run == 3:  # 4 segments = 3 alternating short joins
                    stair_runs += 1
            else:
                run = 0
                last_cross_sign = 0

    return {
        "wobble": round(wobble_num / total_len, 4) if total_len else None,
        "g2_steps": round(float(np.mean(g2_steps)), 4) if g2_steps else 0.0,
        "kinks_per_100px": round(100.0 * kinks / total_len, 3) if total_len else None,
        "kink_cvar10_deg": round(_cvar(subcrease_angles), 4),
        "detail_cvar10": round(_cvar(short_detail_severity), 5),
        "staircase_runs": stair_runs,
        "micro_segs": micro,
        "total_len": round(total_len, 1),
        "segments": n_segs,
    }


def roundness_meter(svg_path: Path, native_w: int) -> dict:
    """Circle-intent subpaths: relative radial RMS of the Taubin fit."""
    from vectorize_papers import fit_circle

    paths = _parse_paths(svg_path)
    if not paths:
        return {"roundness": None, "circles": 0}
    s = _svg_scale(svg_path, native_w)
    residuals = []
    for path in paths:
        for sub in path.continuous_subpaths():
            if not sub.isclosed():
                continue
            try:
                L = sub.length() * s
            except Exception:
                continue
            if L < 12.0:
                continue
            pts = np.array([[sub.point(i / 64).real * s, sub.point(i / 64).imag * s]
                            for i in range(64)])
            fit = fit_circle(pts)
            if fit is None:
                continue
            _center, r, rms = fit
            if r < 2.0 or r > 4.0 * native_w:
                continue
            rel = float(rms / r)
            if rel < 0.04:  # reads as an intended circle
                residuals.append(rel)
    return {"roundness": round(float(np.mean(residuals)), 5) if residuals else None,
            "circles": len(residuals)}


# ------------------------------------------------------------------ raster meters
def raster_meters(svg_path: Path, src: Path) -> dict:
    src_img = np.asarray(Image.open(src).convert("RGB"), float)
    H, W = src_img.shape[:2]
    render = render_svg(svg_path, W)
    if render.size != (W, H):
        render = render.resize((W, H), Image.LANCZOS)
    ren = np.asarray(render, float)

    mae = float(np.mean(np.abs(ren - src_img)))
    rmse = float(np.sqrt(np.mean((ren - src_img) ** 2)))
    bg = _bg_of(src_img)
    ink_src = np.sum(np.abs(src_img - bg), axis=2) > 90
    ink_ren = np.sum(np.abs(ren - bg), axis=2) > 90
    union = int(np.sum(ink_src | ink_ren))
    iou = float(np.sum(ink_src & ink_ren)) / union if union else 1.0

    try:
        from skimage.metrics import structural_similarity
        gray_s = np.mean(src_img, axis=2)
        gray_r = np.mean(ren, axis=2)
        ssim = float(structural_similarity(gray_s, gray_r, data_range=255.0))
    except Exception:
        ssim = None

    out = {"mae": round(mae, 2), "rmse": round(rmse, 2),
           "ink_iou": round(iou, 4),
           "ssim": round(ssim, 4) if ssim is not None else None,
           "seam_px": seam_meter(svg_path, src_img, bg),
           "mirror_iou": round(mirror_iou(ink_ren), 4)}
    out.update(region_color_meter(ren, src_img))
    src_rot90 = rot90_iou(ink_src)
    ren_rot90 = rot90_iou(ink_ren)
    out.update({"source_rot90_iou": round(src_rot90, 4),
                "rot90_iou": round(ren_rot90, 4),
                "rot90_sym_break": round(max(0.0, src_rot90 - ren_rot90), 4)})
    out.update(boundary_meters(ren, src_img))
    out.update(local_defeat_meter(ren, src_img))
    out.update(component_census_meter(ren, src_img))
    out.update(persistent_topology_meter(ren, src_img))
    out.update(catastrophic_locus_meter(ren, src_img))
    out.update(group_regularity_meter(ren, src_img))
    return out


def boundary_meters(ren: np.ndarray, src_img: np.ndarray,
                    tolerance_px: float = 1.5) -> dict:
    """BSDS-style boundary precision/recall/F + 95% Hausdorff (wave B: judge
    GEOMETRY separately from palette choices — mae punishes a different shade
    split even when every boundary sits in the right place, which is exactly
    what froze the route arbiter's native wins on items 075/079).

    Edges: Scharr gradient magnitude of the grayscale, thresholded at 12% of
    each image's OWN max (a q30 source has soft edges; self-normalising keeps
    the masks comparable).  Match: distance-transform tolerance 1.5px."""
    def edge_mask(img: np.ndarray) -> np.ndarray:
        gray = np.mean(img, axis=2).astype(np.float32)
        gx = cv2.Scharr(gray, cv2.CV_32F, 1, 0)
        gy = cv2.Scharr(gray, cv2.CV_32F, 0, 1)
        mag = np.hypot(gx, gy)
        peak = float(mag.max())
        if peak < 1e-6:
            return np.zeros(gray.shape, bool)
        return mag >= 0.12 * peak
    e_ren = edge_mask(ren)
    e_src = edge_mask(src_img)
    if not e_src.any() or not e_ren.any():
        return {"boundary_f": None, "hausdorff95": None}
    dt_src = cv2.distanceTransform((~e_src).astype(np.uint8), cv2.DIST_L2, 3)
    dt_ren = cv2.distanceTransform((~e_ren).astype(np.uint8), cv2.DIST_L2, 3)
    precision = float(np.mean(dt_src[e_ren] <= tolerance_px))
    recall = float(np.mean(dt_ren[e_src] <= tolerance_px))
    f = 2 * precision * recall / max(1e-9, precision + recall)
    h95 = float(max(np.percentile(dt_src[e_ren], 95), np.percentile(dt_ren[e_src], 95)))
    return {"boundary_f": round(f, 4), "hausdorff95": round(h95, 2)}


def seam_meter(svg_path: Path, src_img: np.ndarray, src_bg: np.ndarray) -> float:
    """Thin enclosed background-colored cracks at 4x that the source does not have.

    Red-team spec: gate on CONNECTED crack areas, not single AA samples; 'exactly
    zero uncovered pixels' is unachievable under anti-aliasing.
    """
    import cv2
    H, W = src_img.shape[:2]
    hi = np.asarray(render_svg(svg_path, W * 4), float)
    hb = _bg_of(hi)
    bgish = np.sum(np.abs(hi - hb), axis=2) < 75  # near-background at 4x
    n, lab, stats, cent = cv2.connectedComponentsWithStats(
        bgish.astype(np.uint8), connectivity=8)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    seam_area_hi = 0
    for i in range(1, n):
        if i in border:
            continue
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 4:
            continue
        w_box = stats[i, cv2.CC_STAT_WIDTH]
        h_box = stats[i, cv2.CC_STAT_HEIGHT]
        comp = (lab == i).astype(np.uint8)
        thickness = float(cv2.distanceTransform(comp, cv2.DIST_L2, 3).max())
        if thickness > 2.0:  # >0.5 native px thick: a real hole, not a seam
            continue
        if max(w_box, h_box) < 8:  # <2 native px long: AA noise
            continue
        cx, cy = cent[i]
        sx = min(int(cx / 4), src_img.shape[1] - 1)
        sy = min(int(cy / 4), src_img.shape[0] - 1)
        if np.sum(np.abs(src_img[sy, sx] - src_bg)) < 75:
            continue  # source really is background here
        seam_area_hi += int(area)
    return round(seam_area_hi / 16.0, 2)  # native px^2


def mirror_iou(ink: np.ndarray) -> float:
    """Best vertical/horizontal mirror self-IoU of the ink mask."""
    ys, xs = np.nonzero(ink)
    if not len(xs):
        return 1.0
    best = 0.0
    for axis in (0, 1):
        lo, hi = (xs.min(), xs.max()) if axis == 0 else (ys.min(), ys.max())
        center0 = (lo + hi) / 2.0
        for off in np.arange(-2.0, 2.01, 0.5):
            c = center0 + off
            if axis == 0:
                ref_x = np.clip(np.round(2 * c - xs).astype(int), 0, ink.shape[1] - 1)
                refl = np.zeros_like(ink)
                refl[ys, ref_x] = True
            else:
                ref_y = np.clip(np.round(2 * c - ys).astype(int), 0, ink.shape[0] - 1)
                refl = np.zeros_like(ink)
                refl[ref_y, xs] = True
            union = np.sum(ink | refl)
            if union:
                best = max(best, float(np.sum(ink & refl)) / union)
    return best


def rot90_iou(ink: np.ndarray) -> float:
    """Best 90-degree rotational self-IoU around the ink-bbox centre.

    Half-pixel centre offsets absorb raster phase without granting a shape a
    free translation.  Coordinates are rotated in-place, so rectangular
    canvases do not distort or resize the mask.
    """
    ys, xs = np.nonzero(ink)
    if not len(xs):
        return 1.0
    cx0 = (float(xs.min()) + float(xs.max())) / 2.0
    cy0 = (float(ys.min()) + float(ys.max())) / 2.0
    best = 0.0
    h, w = ink.shape
    for dx in np.arange(-1.0, 1.01, 0.5):
        for dy in np.arange(-1.0, 1.01, 0.5):
            cx, cy = cx0 + float(dx), cy0 + float(dy)
            rx = np.round(cx - (ys - cy)).astype(int)
            ry = np.round(cy + (xs - cx)).astype(int)
            valid = (rx >= 0) & (rx < w) & (ry >= 0) & (ry < h)
            rotated = np.zeros_like(ink)
            rotated[ry[valid], rx[valid]] = True
            union = int(np.count_nonzero(ink | rotated))
            if union:
                best = max(best, float(np.count_nonzero(ink & rotated)) / union)
    return best


# ------------------------------------------------------------------ driver
def frozen_stems(n: int) -> list[str]:
    """Deterministic reference subset: sha1-sorted stems with validated sources."""
    stems = []
    for svg in sorted(VAI_DIR.glob("*_vai.svg")):
        stem = svg.name[:-8]
        if find_source(stem) is not None:
            stems.append(stem)
    stems.sort(key=lambda s: hashlib.sha1(s.encode()).hexdigest())
    return stems[:n]


def measure_one(stem: str, mode: str, reuse: bool, run_tag: str | None = None,
                cached_vai: dict | None = None) -> dict | None:
    src = find_source(stem)
    if src is None:
        return {"stem": stem, "error": "no validated source raster"}
    vai_svg = VAI_DIR / f"{stem}_vai.svg"
    with Image.open(src) as source_image:
        W, H = source_image.size

    out_dir = WORK / (run_tag or mode) / stem
    ours_svg = out_dir / src.stem / "03_rebuilt_filled.svg"
    max_extent = max(W, H)
    scale_condition = ("tiny" if max_extent <= 128 else
                       "medium" if max_extent <= 512 else "large")
    aspect = max(W, H) / max(1, min(W, H))
    layout_condition = "strip" if aspect >= 3.0 else "compact"
    row: dict = {
        "stem": stem,
        "conditions": {
            "scale": scale_condition,
            "layout": layout_condition,
            "source_format": src.suffix.lower().lstrip("."),
        },
    }
    t0 = time.time()
    if not (reuse and ours_svg.exists()):
        try:
            if mode == "scene":
                from vice_scene.pipeline import process_scene
                rep = process_scene(src, out_dir)
            else:
                import geometry_vectorizer as gv
                rep = gv.process(src, out_dir, smoothing=mode)
        except Exception as exc:
            return {"stem": stem, "error": f"{type(exc).__name__}: {exc}"}
        row["fallback_loops"] = sum(v for k, v in rep["templates"].items()
                                    if k.endswith("-fallback"))
        row["prims"] = rep.get("rendered_primitive_count")
    else:
        report = out_dir / src.stem / "report.json"
        if report.exists():
            rep = json.loads(report.read_text(encoding="utf-8"))
            row["fallback_loops"] = sum(v for k, v in rep.get("templates", {}).items()
                                        if k.endswith("-fallback"))
            row["prims"] = rep.get("rendered_primitive_count")
    row["secs"] = round(time.time() - t0, 1)

    for tag, svg in (("ours", ours_svg), ("vai", vai_svg)):
        if tag == "vai" and cached_vai is not None:
            row[tag] = dict(cached_vai)
            continue
        if not svg.exists():
            row[tag] = {"error": "missing svg"}
            continue
        meters = {}
        meters.update(geometry_meters(svg, W))
        meters.update(roundness_meter(svg, W))
        meters.update(raster_meters(svg, src))
        row[tag] = meters

    # Source's own symmetry = the intent ceiling for mirror_iou.
    src_img = np.asarray(Image.open(src).convert("RGB"), float)
    ink = np.sum(np.abs(src_img - _bg_of(src_img)), axis=2) > 90
    row["src_mirror_iou"] = round(mirror_iou(ink), 4)
    return row


KEY_METERS = ["staircase_runs", "seam_px", "wobble", "g2_steps",
              "kinks_per_100px", "micro_segs", "roundness", "ink_iou",
              "ssim", "mae", "boundary_f", "hausdorff95",
              "region_de2000_p95", "de_region_max", "rot90_sym_break",
              "kink_cvar10_deg", "detail_cvar10", "boundary_cvar10",
              "detail_de_cvar10", "catastrophic_locus_rate",
              "worst_locus_severity", "persistent_beta0_error",
              "persistent_beta1_error", "group_regularity_violation"]
LOWER_BETTER = {"staircase_runs", "seam_px", "wobble", "g2_steps",
                "kinks_per_100px", "micro_segs", "roundness", "mae",
                "hausdorff95", "region_de2000_p95", "de_region_max",
                "rot90_sym_break", "kink_cvar10_deg", "detail_cvar10",
                "boundary_cvar10", "detail_de_cvar10",
                "catastrophic_locus_rate", "worst_locus_severity",
                "persistent_beta0_error", "persistent_beta1_error",
                "group_regularity_violation"}


def aggregate(rows: list[dict]) -> dict:
    agg: dict = {"n": len(rows), "wins": {}, "means": {}, "tails": {}}
    for meter in KEY_METERS:
        ours_vals, vai_vals, wins, ties, total = [], [], 0, 0, 0
        for row in rows:
            o = row.get("ours", {}).get(meter)
            v = row.get("vai", {}).get(meter)
            if o is None or v is None:
                continue
            total += 1
            ours_vals.append(o)
            vai_vals.append(v)
            if abs(o - v) < 1e-9:
                ties += 1
            elif (o < v) == (meter in LOWER_BETTER):
                wins += 1
        if total:
            agg["wins"][meter] = f"{wins}+{ties}t/{total}"
            # Mean AND median: wobble-class meters are unbounded, so one
            # degenerate micro-segment icon can dominate the mean while the
            # median tells the population truth (SalsaStarter night case).
            agg["means"][meter] = {"ours": round(float(np.mean(ours_vals)), 4),
                                   "vai": round(float(np.mean(vai_vals)), 4)}
            agg.setdefault("medians", {})[meter] = {
                "ours": round(float(np.median(ours_vals)), 4),
                "vai": round(float(np.median(vai_vals)), 4)}
            if meter in LOWER_BETTER:
                agg["tails"][meter] = {
                    "ours_p95": round(float(np.percentile(ours_vals, 95)), 4),
                    "vai_p95": round(float(np.percentile(vai_vals, 95)), 4),
                    "ours_cvar10": round(_cvar(ours_vals), 4),
                    "vai_cvar10": round(_cvar(vai_vals), 4),
                }

    condition_rows: dict[str, list[dict]] = {}
    for row in rows:
        for dimension, value in row.get("conditions", {}).items():
            condition_rows.setdefault(f"{dimension}:{value}", []).append(row)
    for condition, subset in condition_rows.items():
        if len(subset) < 2:
            continue
        condition_report = {"n": len(subset), "meters": {}, "catastrophic_items": {}}
        for meter in ("catastrophic_locus_rate", "boundary_cvar10",
                      "persistent_beta0_error", "persistent_beta1_error",
                      "group_regularity_violation"):
            ours_values = [float(row["ours"][meter]) for row in subset
                           if row.get("ours", {}).get(meter) is not None]
            vai_values = [float(row["vai"][meter]) for row in subset
                          if row.get("vai", {}).get(meter) is not None]
            if ours_values and vai_values:
                condition_report["meters"][meter] = {
                    "ours_cvar10": round(_cvar(ours_values), 4),
                    "vai_cvar10": round(_cvar(vai_values), 4),
                    "ours_median": round(float(np.median(ours_values)), 4),
                    "vai_median": round(float(np.median(vai_values)), 4),
                }
        for side in ("ours", "vai"):
            condition_report["catastrophic_items"][side] = sum(
                bool(row.get(side, {}).get("any_counter_failure")) or
                float(row.get(side, {}).get("catastrophic_locus_rate") or 0) > 0
                for row in subset)
        agg.setdefault("by_condition", {})[condition] = condition_report
    return agg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="paper-regions")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--reuse", action="store_true",
                    help="reuse existing outputs in benchmarks/vai_work")
    ap.add_argument("--stems", default=None, help="comma list overrides the subset")
    ap.add_argument("--fit-profile", default=None,
                    choices=["production", "text-safe"])
    ap.add_argument("--corner-policy", default=None,
                    choices=["production", "tiny-safe", "cnn-conservative"])
    ap.add_argument("--snapshot", default="vai_snapshot.json",
                    help="snapshot filename under benchmarks/")
    ap.add_argument("--vai-cache", default=None,
                    help="prior snapshot whose immutable VAI-side meters are reused")
    args = ap.parse_args()

    if args.fit_profile or args.corner_policy:
        import geometry_vectorizer as gv
        if args.fit_profile:
            gv._PAPER_FIT_PROFILE = args.fit_profile
        if args.corner_policy:
            gv._CORNER_POSTPROCESS_POLICY = args.corner_policy
        print(f"A/B overrides: fit_profile={args.fit_profile} "
              f"corner_policy={args.corner_policy}")

    if args.stems:
        stems = [s.strip() for s in args.stems.split(",") if s.strip()]
    else:
        stems = frozen_stems(10_000 if args.all else args.n)
    OUT.mkdir(exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    run_tag = args.mode
    if args.fit_profile or args.corner_policy:
        run_tag += f"_{args.fit_profile or 'prod'}_{args.corner_policy or 'prod'}"

    cached_vai_by_stem: dict[str, dict] = {}
    if args.vai_cache:
        cache_path = Path(args.vai_cache)
        if not cache_path.is_absolute():
            cache_path = OUT / cache_path
        cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
        cached_vai_by_stem = {
            row["stem"]: row["vai"] for row in cache_payload.get("rows", [])
            if row.get("stem") and isinstance(row.get("vai"), dict)
        }
        print(f"VAI meter cache: {cache_path} ({len(cached_vai_by_stem)} stems)")

    rows = []
    for i, stem in enumerate(stems, 1):
        row = measure_one(stem, args.mode, args.reuse, run_tag,
                          cached_vai=cached_vai_by_stem.get(stem))
        if row is None:
            continue
        rows.append(row)
        o, v = row.get("ours", {}), row.get("vai", {})
        print(f"[{i:3}/{len(stems)}] {stem:28} "
              f"stair {o.get('staircase_runs')}|{v.get('staircase_runs')}  "
              f"seam {o.get('seam_px')}|{v.get('seam_px')}  "
              f"wob {o.get('wobble')}|{v.get('wobble')}  "
              f"iou {o.get('ink_iou')}|{v.get('ink_iou')}  "
              f"fb {row.get('fallback_loops')}  {row.get('secs')}s", flush=True)

    agg = aggregate([r for r in rows if "error" not in r])
    print("\n=== OURS vs VAI (wins+ties/total; median ours|vai; mean ours|vai) ===")
    for meter in KEY_METERS:
        if meter in agg["wins"]:
            m = agg["means"][meter]
            md = agg.get("medians", {}).get(meter, {})
            print(f"  {meter:18} {agg['wins'][meter]:>10}   "
                  f"med {md.get('ours')} | {md.get('vai')}   "
                  f"mean {m['ours']} | {m['vai']}")

    snap = OUT / args.snapshot
    if snap.exists():
        snap.replace(snap.with_name(snap.stem + "_prev.json"))
    snap.write_text(json.dumps({"mode": args.mode, "rows": rows, "aggregate": agg},
                               indent=1), encoding="utf-8")
    print(f"\nSnapshot -> {snap}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

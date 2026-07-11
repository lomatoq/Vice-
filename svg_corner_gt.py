"""High-precision corner ground truth extracted from flat SVG artwork.

The important distinction is structural, not raster: a positive corner is a
C0 tangent discontinuity in the SVG geometry, or a new visible corner created
by occlusion.  Rounded joins, Bezier extrema and raster staircases are kept as
negative boundary vertices.

This module deliberately rejects SVG features that cannot yet be interpreted
without ambiguity (transforms, masks, clip paths and ``use`` references).  A
smaller clean dataset is substantially more useful than silently noisy labels.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Iterator

import cv2
import numpy as np
from PIL import Image, ImageDraw

from vectorize_papers import mask_loops


LABEL_NEGATIVE = 0
LABEL_STRUCTURAL = 1
LABEL_OCCLUSION = 2

# A classifier still receives vertex labels, as in the paper, but fitting must
# reason about perceptual corner *events*.  A short raster plateau can therefore
# have two positive endpoint vertices that belong to one latent corner.
EVENT_NONE = 0
EVENT_POINT = 1
EVENT_SHORT_SPAN = 2
EVENT_OCCLUSION = 3


@dataclass(frozen=True)
class CornerCandidate:
    x: float
    y: float
    kind: int
    angle: float


@dataclass
class VisibleRegion:
    mask: np.ndarray
    candidates: list[CornerCandidate]
    source_index: int


@dataclass
class SvgFrame:
    width: int
    height: int
    regions: list[VisibleRegion]
    path_count: int
    overlap_pixels: int


@dataclass
class LoopExample:
    points: np.ndarray
    labels: np.ndarray
    region_index: int
    event_ids: np.ndarray
    event_kinds: np.ndarray


class UnsupportedSvg(ValueError):
    pass


_UNSUPPORTED = (
    (re.compile(r"\btransform\s*=", re.I), "transform"),
    (re.compile(r"<\s*clipPath\b", re.I), "clipPath"),
    (re.compile(r"<\s*mask\b", re.I), "mask"),
    (re.compile(r"<\s*use\b", re.I), "use"),
    (re.compile(r"<\s*filter\b|\bfilter\s*=", re.I), "filter"),
)


def unsupported_reason(svg_path: str | Path) -> str | None:
    text = Path(svg_path).read_text(encoding="utf-8", errors="ignore")
    for pattern, reason in _UNSUPPORTED:
        if pattern.search(text):
            return reason
    return None


def _style_map(attrs: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in attrs.get("style", "").split(";"):
        if ":" in item:
            key, value = item.split(":", 1)
            out[key.strip().lower()] = value.strip()
    return out


def _painted_fill(attrs: dict) -> bool:
    style = _style_map(attrs)
    if attrs.get("display", style.get("display", "")).strip().lower() == "none":
        return False
    fill = attrs.get("fill", style.get("fill", "black")).strip().lower()
    if fill in {"none", "transparent"}:
        return False
    try:
        opacity = float(attrs.get("opacity", style.get("opacity", "1")))
        fill_opacity = float(attrs.get("fill-opacity", style.get("fill-opacity", "1")))
        return opacity * fill_opacity > 0.01
    except ValueError:
        return True


def _segment_length(segment) -> float:
    try:
        return float(segment.length(error=1e-6))
    except TypeError:
        try:
            return float(segment.length())
        except Exception:
            return float(abs(segment.end - segment.start))
    except Exception:
        return float(abs(segment.end - segment.start))


def _unit_tangent(segment, t: float) -> complex:
    for probe in (t, 1e-6 if t == 0 else 1 - 1e-6, 1e-4 if t == 0 else 1 - 1e-4):
        try:
            value = segment.derivative(probe)
        except Exception:
            value = 0j
        if abs(value) > 1e-12:
            return value / abs(value)
    chord = segment.end - segment.start
    return chord / abs(chord) if abs(chord) > 1e-12 else 1 + 0j


def _signed_turn(first: complex, second: complex) -> float:
    return math.degrees(math.atan2(
        first.real * second.imag - first.imag * second.real,
        first.real * second.real + first.imag * second.imag,
    ))


def _closed_segments(subpath) -> list:
    from svgpathtools import Line

    segments = list(subpath)
    if not segments:
        return []
    if abs(segments[-1].end - segments[0].start) > 1e-9:
        segments.append(Line(segments[-1].end, segments[0].start))
    return segments


def structural_corners(subpath, px_per_unit: float, min_turn: float = 20.0) -> list[tuple[complex, float]]:
    """Exact C0 joins, with a short zig-zag coherence veto.

    The veto matters for SVGs whose diagonal/curve was exported as a tiny
    horizontal/vertical staircase.  At a real corner the nearby signed turning
    is coherent; in a staircase it alternates and cancels.
    """
    segments = _closed_segments(subpath)
    n = len(segments)
    if n < 2:
        return []
    lengths = np.asarray([_segment_length(seg) * px_per_unit for seg in segments], dtype=float)
    turns = np.asarray([
        _signed_turn(_unit_tangent(segments[i], 1.0), _unit_tangent(segments[(i + 1) % n], 0.0))
        for i in range(n)
    ])
    out: list[tuple[complex, float]] = []
    for i, signed in enumerate(turns):
        angle = abs(float(signed))
        if angle < min_turn:
            continue
        before = lengths[i]
        after = lengths[(i + 1) % n]
        # Features smaller than a pixel at this operating scale do not form a
        # reliable perceptual corner.
        if max(before, after) < 0.85:
            continue
        if min(before, after) < 1.6:
            local = turns[[(i - 1) % n, i, (i + 1) % n]]
            coherence = abs(float(local.sum())) / max(float(np.abs(local).sum()), 1e-9)
            if coherence < 0.72:
                continue
            if angle < 32.0 and min(before, after) < 1.2:
                continue
        point = segments[i].end
        if all(abs(point - old) * px_per_unit > 0.55 for old, _ in out):
            out.append((point, angle))
    return out


def _sample_subpath(subpath, px_per_unit: float, step_px: float = 0.45) -> list[complex]:
    points: list[complex] = []
    for segment in subpath:
        count = max(2, int(math.ceil(_segment_length(segment) * px_per_unit / step_px)))
        points.extend(segment.point(k / count) for k in range(count))
    return points


def _boundary(mask: np.ndarray) -> np.ndarray:
    kernel = np.ones((3, 3), np.uint8)
    eroded = cv2.erode(mask.astype(np.uint8), kernel, iterations=1).astype(bool)
    return mask.astype(bool) & ~eroded


def _near(mask: np.ndarray, x: float, y: float, radius: int) -> bool:
    xi, yi = int(round(x)), int(round(y))
    y0, y1 = max(0, yi - radius), min(mask.shape[0], yi + radius + 1)
    x0, x1 = max(0, xi - radius), min(mask.shape[1], xi + radius + 1)
    return y0 < y1 and x0 < x1 and bool(mask[y0:y1, x0:x1].any())


def _dedupe_candidates(candidates: list[CornerCandidate], radius: float = 1.4) -> list[CornerCandidate]:
    ordered = sorted(candidates, key=lambda c: (c.kind != LABEL_STRUCTURAL, -c.angle))
    kept: list[CornerCandidate] = []
    for candidate in ordered:
        if all(math.hypot(candidate.x - old.x, candidate.y - old.y) > radius for old in kept):
            kept.append(candidate)
    return kept


def _intersection_candidates(base: np.ndarray, occluders: np.ndarray, visible: np.ndarray,
                             supersample: int) -> list[CornerCandidate]:
    if not base.any() or not occluders.any() or not visible.any():
        return []
    kernel = np.ones((3, 3), np.uint8)
    base_edge = cv2.morphologyEx(base.astype(np.uint8), cv2.MORPH_GRADIENT, kernel)
    occ_edge = cv2.morphologyEx(occluders.astype(np.uint8), cv2.MORPH_GRADIENT, kernel)
    cross = cv2.dilate(base_edge, kernel, iterations=1).astype(bool)
    cross &= cv2.dilate(occ_edge, kernel, iterations=1).astype(bool)
    count, labels, stats, centers = cv2.connectedComponentsWithStats(cross.astype(np.uint8), connectivity=8)
    visible_edge = cv2.dilate(_boundary(visible).astype(np.uint8), kernel, iterations=1).astype(bool)
    out: list[CornerCandidate] = []
    for component in range(1, count):
        width = int(stats[component, cv2.CC_STAT_WIDTH])
        height = int(stats[component, cv2.CC_STAT_HEIGHT])
        # A long coincident boundary is not an intersection corner.
        if max(width, height) > 5 * supersample:
            continue
        cx, cy = centers[component]
        if _near(visible_edge, cx, cy, 2 * supersample):
            out.append(CornerCandidate(cx / supersample, cy / supersample, LABEL_OCCLUSION, 180.0))
    return out


def visible_svg_regions(svg_path: str | Path, target: int, supersample: int = 4,
                        margin_frac: float = 0.06) -> SvgFrame:
    """Rasterize paint-ordered visible SVG regions and their exact corner GT."""
    from svgpathtools import svg2paths2

    reason = unsupported_reason(svg_path)
    if reason:
        raise UnsupportedSvg(reason)
    paths, attributes, _ = svg2paths2(str(svg_path))
    selected = [(path, attrs) for path, attrs in zip(paths, attributes) if _painted_fill(attrs)]
    if not selected:
        raise UnsupportedSvg("no-filled-paths")
    boxes = []
    for path, _ in selected:
        try:
            boxes.append(path.bbox())
        except Exception:
            continue
    if not boxes:
        raise UnsupportedSvg("no-bounds")
    xmin = min(box[0] for box in boxes)
    xmax = max(box[1] for box in boxes)
    ymin = min(box[2] for box in boxes)
    ymax = max(box[3] for box in boxes)
    span = max(xmax - xmin, ymax - ymin, 1e-6)
    scale = target / span
    margin = target * margin_frac
    width = max(8, int(round((xmax - xmin) * scale + 2 * margin)))
    height = max(8, int(round((ymax - ymin) * scale + 2 * margin)))
    hi_width, hi_height = width * supersample, height * supersample
    hi_scale, hi_margin = scale * supersample, margin * supersample

    def to_high(point: complex) -> tuple[float, float]:
        return ((point.real - xmin) * hi_scale + hi_margin,
                (point.imag - ymin) * hi_scale + hi_margin)

    masks: list[np.ndarray] = []
    structural: list[list[CornerCandidate]] = []
    for path, _ in selected:
        mask = np.zeros((hi_height, hi_width), dtype=np.uint8)
        corners: list[CornerCandidate] = []
        for subpath in path.continuous_subpaths():
            polygon = [to_high(point) for point in _sample_subpath(subpath, hi_scale)]
            if len(polygon) >= 3:
                layer = Image.new("1", (hi_width, hi_height), 0)
                ImageDraw.Draw(layer).polygon(polygon, fill=1)
                mask ^= np.asarray(layer, dtype=np.uint8)
            for point, angle in structural_corners(subpath, hi_scale):
                x, y = to_high(point)
                corners.append(CornerCandidate(x / supersample, y / supersample,
                                                LABEL_STRUCTURAL, angle))
        masks.append(mask)
        structural.append(_dedupe_candidates(corners))

    covered = np.zeros_like(masks[0], dtype=np.uint8)
    later_corners: list[CornerCandidate] = []
    visible_regions_reversed: list[VisibleRegion] = []
    overlap_pixels = 0
    for source_index in range(len(masks) - 1, -1, -1):
        full = masks[source_index]
        overlap = full & covered
        overlap_area = int(np.count_nonzero(overlap))
        # At tiny resolutions two analytically separate smooth shapes can
        # touch by a single supersample pixel.  That is raster coincidence,
        # not an occlusion event and must not manufacture a corner label.
        meaningful_overlap = overlap_area >= supersample * supersample
        effective_covered = covered if meaningful_overlap else np.zeros_like(covered)
        if meaningful_overlap:
            overlap_pixels += overlap_area
        visible_hi = full & ~effective_covered
        if int(visible_hi.sum()) >= 4 * supersample * supersample:
            visible_edge_hi = cv2.dilate(_boundary(visible_hi).astype(np.uint8),
                                         np.ones((3, 3), np.uint8), iterations=1).astype(bool)
            candidates = []
            for candidate in structural[source_index]:
                if _near(visible_edge_hi, candidate.x * supersample,
                         candidate.y * supersample, 2 * supersample):
                    candidates.append(candidate)
            if meaningful_overlap:
                for candidate in later_corners:
                    hx, hy = candidate.x * supersample, candidate.y * supersample
                    if _near(full, hx, hy, 1) and _near(visible_edge_hi, hx, hy, 2 * supersample):
                        candidates.append(CornerCandidate(candidate.x, candidate.y,
                                                          LABEL_OCCLUSION, candidate.angle))
            candidates.extend(_intersection_candidates(full, effective_covered, visible_hi, supersample))

            coverage = cv2.resize(visible_hi.astype(np.float32), (width, height),
                                  interpolation=cv2.INTER_AREA)
            visible = coverage >= 0.5
            if visible.any():
                low_edge = cv2.dilate(_boundary(visible).astype(np.uint8),
                                      np.ones((3, 3), np.uint8), iterations=1).astype(bool)
                candidates = [candidate for candidate in _dedupe_candidates(candidates)
                              if _near(low_edge, candidate.x, candidate.y, 3)]
                visible_regions_reversed.append(
                    VisibleRegion(visible, candidates, source_index)
                )
        covered |= full
        later_corners.extend(structural[source_index])
    visible_regions_reversed.reverse()
    return SvgFrame(width, height, visible_regions_reversed, len(selected),
                    int(round(overlap_pixels / (supersample * supersample))))


def _turn(loop: np.ndarray, index: int, window: int) -> float:
    n = len(loop)
    window = max(1, min(window, max(1, n // 4)))
    incoming = loop[index] - loop[(index - window) % n]
    outgoing = loop[(index + window) % n] - loop[index]
    norm = float(np.linalg.norm(incoming) * np.linalg.norm(outgoing))
    if norm < 1e-9:
        return 0.0
    cosine = float(np.clip(np.dot(incoming, outgoing) / norm, -1.0, 1.0))
    return math.degrees(math.acos(cosine))


def _short_corner_span(loop: np.ndarray, point: np.ndarray, nearest: int,
                       nearest_distance: float) -> list[int] | None:
    """Return endpoints of a 1--2 px raster plateau centred on a true SVG corner.

    This is the convention used by the paper's human data: if the perceived
    corner falls on a tiny flat edge rather than on a contour vertex, both edge
    endpoints are positive.  Requiring a straight sub-chain centred on the
    analytic SVG corner prevents ordinary diagonal staircases from producing
    extra positives.
    """
    n = len(loop)
    best: tuple[float, int, int] | None = None
    neighbourhood = [(nearest + delta) % n for delta in range(-4, 5)]
    for first in neighbourhood:
        for gap in (1, 2):
            last = (first + gap) % n
            chain = np.asarray([loop[(first + step) % n] for step in range(gap + 1)])
            steps = np.linalg.norm(np.diff(chain, axis=0), axis=1)
            arc = float(steps.sum())
            chord = float(np.linalg.norm(chain[-1] - chain[0]))
            if arc > 2.1 or chord < 0.8 or chord / max(arc, 1e-9) < 0.985:
                continue
            if gap == 2 and _turn(loop, (first + 1) % n, 1) > 8.0:
                continue
            midpoint_distance = float(np.linalg.norm((chain[0] + chain[-1]) * 0.5 - point))
            first_turn, last_turn = _turn(loop, first, 2), _turn(loop, last, 2)
            if midpoint_distance > 0.7 or midpoint_distance > nearest_distance + 0.2:
                continue
            if min(first_turn, last_turn) < 16.0:
                continue
            score = midpoint_distance + 0.004 * abs(first_turn - last_turn) + 0.03 * (2 - gap)
            if best is None or score < best[0]:
                best = (score, first, last)
    return [best[1], best[2]] if best is not None else None


def _candidate_indices(loop: np.ndarray, candidate: CornerCandidate) -> list[int]:
    point = np.array([candidate.x, candidate.y], dtype=float)
    distance = np.linalg.norm(loop - point, axis=1)
    nearest = int(np.argmin(distance))
    if float(distance[nearest]) > 3.25:
        return []
    if candidate.kind == LABEL_STRUCTURAL:
        span = _short_corner_span(loop, point, nearest, float(distance[nearest]))
        if span is not None:
            return span
    neighbourhood = [(nearest + delta) % len(loop) for delta in range(-3, 4)]
    index = max(neighbourhood, key=lambda i: _turn(loop, i, 2))
    small = _turn(loop, index, 2)
    large = _turn(loop, index, 6)
    if candidate.kind == LABEL_STRUCTURAL:
        if small < 16.0 or large < 18.0:
            return []
    else:
        concentration = small / max(large, 1e-6)
        if small < 24.0 or (small < 65.0 and concentration < 0.45):
            return []
    return [index]


def infer_corner_events(points: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Infer loop-local perceptual events from paper-compatible vertex labels.

    Two isolated structural positives joined by a straight 1--2 px chain form
    one short-span event.  This exactly captures the released paper convention
    while keeping ordinary point corners and occlusion events separate.
    """
    n = len(points)
    event_ids = np.full(n, -1, dtype=np.int32)
    event_kinds = np.zeros(n, dtype=np.uint8)
    structural = [int(i) for i in np.flatnonzero(labels == LABEL_STRUCTURAL)]
    neighbours: dict[int, list[int]] = {index: [] for index in structural}
    structural_set = set(structural)
    for first in structural:
        for gap in (1, 2):
            last = (first + gap) % n
            if last not in structural_set:
                continue
            chain = np.asarray([points[(first + step) % n] for step in range(gap + 1)])
            arc = float(np.linalg.norm(np.diff(chain, axis=0), axis=1).sum())
            chord = float(np.linalg.norm(chain[-1] - chain[0]))
            if arc <= 2.1 and chord >= 0.8 and chord / max(arc, 1e-9) >= 0.985:
                neighbours[first].append(last)
                neighbours[last].append(first)

    next_event = 0
    used: set[int] = set()
    for first in structural:
        if first in used or len(neighbours[first]) != 1:
            continue
        last = neighbours[first][0]
        if last in used or len(neighbours[last]) != 1 or neighbours[last][0] != first:
            continue
        event_ids[[first, last]] = next_event
        event_kinds[[first, last]] = EVENT_SHORT_SPAN
        used.update((first, last))
        next_event += 1
    for index in structural:
        if index in used:
            continue
        event_ids[index] = next_event
        event_kinds[index] = EVENT_POINT
        next_event += 1
    for index in np.flatnonzero(labels == LABEL_OCCLUSION):
        event_ids[index] = next_event
        event_kinds[index] = EVENT_OCCLUSION
        next_event += 1
    return event_ids, event_kinds


def frame_loop_examples(frame: SvgFrame) -> list[LoopExample]:
    examples: list[LoopExample] = []
    for region_index, region in enumerate(frame.regions):
        for raw in mask_loops(region.mask):
            loop = raw[:-1] if len(raw) > 1 and np.allclose(raw[0], raw[-1]) else raw
            if len(loop) < 8:
                continue
            labels = np.zeros(len(loop), dtype=np.uint8)
            event_ids = np.full(len(loop), -1, dtype=np.int32)
            event_kinds = np.zeros(len(loop), dtype=np.uint8)
            next_event = 0
            for candidate in region.candidates:
                indices = _candidate_indices(loop, candidate)
                if not indices:
                    continue
                # Structural wins only on its own region; on a lower clipped
                # region the same location correctly remains an occlusion label.
                kind = (EVENT_SHORT_SPAN if candidate.kind == LABEL_STRUCTURAL and len(indices) == 2
                        else EVENT_POINT if candidate.kind == LABEL_STRUCTURAL else EVENT_OCCLUSION)
                for index in indices:
                    if event_ids[index] < 0 or candidate.kind >= labels[index]:
                        labels[index] = max(labels[index], candidate.kind)
                        event_ids[index] = next_event
                        event_kinds[index] = kind
                next_event += 1
            examples.append(LoopExample(loop.astype(np.float32), labels, region_index,
                                        event_ids, event_kinds))
    return examples


def render_frame_base(frame: SvgFrame, display: int = 300) -> tuple[Image.Image, float]:
    palette = ((231, 238, 255), (229, 250, 238), (255, 239, 220), (241, 229, 255),
               (255, 230, 239), (229, 247, 247))
    image = Image.new("RGB", (frame.width, frame.height), (20, 24, 31))
    pixels = np.asarray(image).copy()
    for index, region in enumerate(frame.regions):
        pixels[region.mask] = palette[index % len(palette)]
    image = Image.fromarray(pixels)
    scale = display / max(frame.width, frame.height)
    size = (max(1, int(round(frame.width * scale))), max(1, int(round(frame.height * scale))))
    # Upscale the raster first, then draw annotations at a constant screen
    # size.  Otherwise a 1px dot at 32px becomes a giant 9px block and hides
    # the very staircase we want to inspect.
    image = image.resize(size, Image.Resampling.NEAREST)
    return image, scale


def render_frame_preview(frame: SvgFrame, examples: list[LoopExample], display: int = 300) -> Image.Image:
    image, scale = render_frame_base(frame, display)
    draw = ImageDraw.Draw(image)
    radius = 3
    for example in examples:
        closed = np.vstack((example.points, example.points[0])) * scale
        draw.line([tuple(point) for point in closed], fill=(55, 135, 255), width=1)
        for point, label in zip(example.points, example.labels):
            if label == LABEL_NEGATIVE:
                continue
            color = (255, 55, 55) if label == LABEL_STRUCTURAL else (255, 45, 220)
            x, y = point * scale
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    return image


def iter_shard_examples(dataset_dir: str | Path, splits: set[str] | None = None) -> Iterator[tuple[np.ndarray, np.ndarray, dict]]:
    """Yield loops from a dataset produced by ``build_corner_dataset.py``."""
    import json

    root = Path(dataset_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    review_path = root / "review.json"
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
    decisions = review.get("decisions", {})
    corrections = review.get("corrections", {})
    for shard in manifest["shards"]:
        data = np.load(root / shard["file"])
        offsets = data["offsets"]
        for index in range(len(offsets) - 1):
            file_index = int(data["file_index"][index])
            file_record = files[file_index]
            if splits and file_record["split"] not in splits:
                continue
            if decisions.get(file_record["id"]) == "reject":
                continue
            start, end = int(offsets[index]), int(offsets[index + 1])
            labels = data["labels"][start:end].copy()
            loop_index = int(data["loop_index"][index]) if "loop_index" in data else index
            view_id = f"{file_record['id']}@{int(data['resolution'][index])}"
            for key, value in corrections.get(view_id, {}).items():
                corrected_loop, vertex = (int(part) for part in key.split(":", 1))
                if corrected_loop == loop_index and 0 <= vertex < len(labels):
                    labels[vertex] = int(value)
            if view_id in corrections or "event_ids" not in data or "event_kinds" not in data:
                event_ids, event_kinds = infer_corner_events(data["points"][start:end], labels)
            else:
                event_ids = data["event_ids"][start:end].copy()
                event_kinds = data["event_kinds"][start:end].copy()
            meta = {
                "file_index": file_index,
                "path": file_record["path"],
                "split": file_record["split"],
                "source_layer": file_record.get("source_layer", "svg-extended"),
                "resolution": int(data["resolution"][index]),
                "region_index": int(data["region_index"][index]),
                "loop_index": loop_index,
                "event_ids": event_ids,
                "event_kinds": event_kinds,
            }
            yield data["points"][start:end], labels, meta

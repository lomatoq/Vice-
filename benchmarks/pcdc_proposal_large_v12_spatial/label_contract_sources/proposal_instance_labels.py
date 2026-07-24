"""Source-disjoint SVG instance labels for ProposalNet training.

The raster/vector corpus stores one clean SVG per source but historically used
one degraded full-scene foreground mask for every macro family.  That teaches
compound wordmarks to be ``whole_shape`` queries and cannot supervise the
separate mark/text owners used by the proof-carrying compiler.  This module
derives conservative owner masks from the clean SVG, then applies the recorded
pair augmentation and registers the result to the observed raster support.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import io
import math
import re
import xml.etree.ElementTree as ET

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class SvgOwnerTemplates:
    full_mask: np.ndarray
    text_masks: tuple[np.ndarray, ...]
    mark_masks: tuple[np.ndarray, ...]

    def validate(self) -> None:
        shape = self.full_mask.shape
        if self.full_mask.ndim != 2 or self.full_mask.flags.writeable:
            raise ValueError("full SVG template must be an immutable mask")
        for mask in (*self.text_masks, *self.mark_masks):
            if mask.shape != shape or mask.flags.writeable or not np.any(mask):
                raise ValueError("SVG owner template is malformed")


def _number(value: str | None, default: float) -> float:
    if not value:
        return float(default)
    match = re.match(r"\s*([-+0-9.eE]+)", str(value))
    try:
        return float(match.group(1)) if match else float(default)
    except ValueError:
        return float(default)


def _svg_aspect(svg: str) -> float:
    root = ET.fromstring(svg)
    view_box = str(root.attrib.get("viewBox", "")).replace(",", " ").split()
    if len(view_box) == 4:
        width = _number(view_box[2], 1.0)
        height = _number(view_box[3], 1.0)
    else:
        width = _number(root.attrib.get("width"), 256.0)
        height = _number(root.attrib.get("height"), 256.0)
    return max(1e-3, width / max(1e-3, height))


def _freeze(mask: np.ndarray) -> np.ndarray:
    result = np.ascontiguousarray(mask, dtype=bool)
    result.setflags(write=False)
    return result


def _render_svg_foreground(svg: str, render_width: int) -> np.ndarray:
    import resvg_py

    aspect = _svg_aspect(svg)
    width = max(64, int(render_width))
    height = max(16, int(round(width / aspect)))
    payload = resvg_py.svg_to_bytes(
        svg_string=svg, width=width, height=height,
    )
    alpha = np.asarray(Image.open(io.BytesIO(payload)).convert("RGBA"))[..., 3]
    foreground = alpha >= 48
    if not np.any(foreground):
        raise ValueError("SVG has no rendered foreground")
    return foreground


def _component_rows(mask: np.ndarray) -> list[dict[str, int]]:
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), 8,
    )
    rows = []
    for label in range(1, count):
        x, y, width, height, area = (
            int(value) for value in stats[label]
        )
        if area < 2:
            continue
        rows.append({
            "id": label, "x": x, "y": y, "w": width, "h": height,
            "area": area, "right": x + width, "bottom": y + height,
        })
    return rows


def _candidate_text_boxes(
    foreground: np.ndarray, components: list[dict[str, int]],
) -> tuple[tuple[int, int, int, int], ...]:
    """Find conservative horizontal owner rows from exact SVG components."""
    candidates: dict[
        tuple[int, ...], tuple[float, tuple[int, int, int, int], tuple[int, ...]]
    ] = {}
    for anchor in components:
        compatible = []
        for row in components:
            height_ratio = row["h"] / max(1, anchor["h"])
            overlap = max(
                0,
                min(anchor["bottom"], row["bottom"])
                - max(anchor["y"], row["y"]),
            ) / max(1, min(anchor["h"], row["h"]))
            center_delta = abs(
                (row["y"] + 0.5 * row["h"])
                - (anchor["y"] + 0.5 * anchor["h"])
            ) / max(row["h"], anchor["h"])
            if 0.45 <= height_ratio <= 2.20 and (
                overlap >= 0.35 or center_delta <= 0.40
            ):
                compatible.append(row)
        compatible.sort(key=lambda row: (row["x"], row["y"], row["id"]))
        # Enumerating contiguous runs separates a large emblem from a nearby
        # word even when both occupy the same vertical band.  Real letter
        # spacing is internally regular; the mark-to-word gap is an outlier.
        for start in range(len(compatible)):
            maximum = min(len(compatible), start + 24)
            for stop in range(start + 4, maximum + 1):
                group = compatible[start:stop]
                heights = np.asarray([row["h"] for row in group], np.float64)
                baselines = np.asarray(
                    [row["bottom"] for row in group], np.float64,
                )
                x1 = min(row["x"] for row in group)
                y1 = min(row["y"] for row in group)
                x2 = max(row["right"] for row in group)
                y2 = max(row["bottom"] for row in group)
                aspect = (x2 - x1) / max(1, y2 - y1)
                gaps = np.asarray([
                    group[index + 1]["x"] - group[index]["right"]
                    for index in range(len(group) - 1)
                ], np.float64)
                positive = gaps[gaps >= 0]
                median_gap = float(np.median(positive)) if len(positive) else 0.0
                gap_deviation = (
                    float(np.max(np.abs(positive - median_gap)))
                    / max(3.0, float(np.median(heights)))
                    if len(positive) else 0.0
                )
                density = sum(row["area"] for row in group) / max(
                    1, (x2 - x1) * (y2 - y1),
                )
                if (
                    aspect < 2.20
                    or float(np.std(baselines))
                        > 0.35 * float(np.median(heights))
                    or float(np.std(heights))
                        > 0.65 * float(np.mean(heights))
                    or gap_deviation > 0.45 or density > 0.78
                ):
                    continue
                ids = tuple(sorted(row["id"] for row in group))
                score = len(group) + 0.10 * aspect - 1.50 * gap_deviation
                candidates[ids] = (score, (x1, y1, x2, y2), ids)

    # A connected cursive word can be a single component.  Admit it only when
    # it spans most of the scene and contains real counter evidence.
    full_width = foreground.shape[1]
    for row in components:
        aspect = row["w"] / max(1, row["h"])
        if aspect < 3.0 or row["w"] < 0.55 * full_width:
            continue
        local = foreground[
            row["y"]:row["bottom"], row["x"]:row["right"],
        ]
        contours, hierarchy = cv2.findContours(
            local.astype(np.uint8), cv2.RETR_CCOMP,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        holes = 0 if hierarchy is None else int(np.sum(hierarchy[0, :, 3] >= 0))
        if holes >= 1:
            ids = (row["id"],)
            candidates[ids] = (
                1.0 + 0.10 * aspect,
                (row["x"], row["y"], row["right"], row["bottom"]),
                ids,
            )

    selected: list[
        tuple[float, tuple[int, int, int, int], tuple[int, ...]]
    ] = []
    for candidate in sorted(
        candidates.values(), key=lambda row: (-row[0], row[1], row[2]),
    ):
        ids = set(candidate[2])
        if any(
            len(ids & set(other[2])) / max(1, min(len(ids), len(other[2])))
            >= 0.50
            for other in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= 4:
            break
    return tuple(row[1] for row in sorted(selected, key=lambda row: row[1]))


@lru_cache(maxsize=256)
def svg_owner_templates(svg: str, *, render_width: int = 512) -> SvgOwnerTemplates:
    foreground = _render_svg_foreground(svg, render_width)
    components = _component_rows(foreground)
    boxes = _candidate_text_boxes(foreground, components)
    text_masks = []
    for x1, y1, x2, y2 in boxes:
        row = np.zeros_like(foreground)
        row[y1:y2, x1:x2] = foreground[y1:y2, x1:x2]
        if np.any(row):
            text_masks.append(_freeze(row))
    text_union = np.zeros_like(foreground)
    for row in text_masks:
        text_union |= row
    remainder = foreground & ~text_union
    mark_masks: list[np.ndarray] = []
    if np.any(remainder) and int(np.sum(remainder)) >= max(
        4, int(0.02 * np.sum(foreground)),
    ):
        mark_masks.append(_freeze(remainder))
    elif not text_masks:
        mark_masks.append(_freeze(foreground))
    result = SvgOwnerTemplates(
        _freeze(foreground), tuple(text_masks), tuple(mark_masks),
    )
    result.validate()
    return result


@lru_cache(maxsize=4096)
def svg_full_template(svg: str, *, render_width: int = 256) -> np.ndarray:
    """Return the clean full-scene support used as the ideal proposal target."""
    return _freeze(_render_svg_foreground(svg, render_width))


def _project_mask(
    mask: np.ndarray, *, size: int, scale: float, shift_x: int,
    shift_y: int, rotate_degrees: float,
) -> np.ndarray:
    height, width = mask.shape
    aspect = width / max(1, height)
    extent = max(int(math.floor(size * scale)), 8)
    if aspect >= 1.0:
        render_width = extent
        render_height = max(int(math.floor(extent / aspect)), 1)
    else:
        render_height = extent
        render_width = max(int(math.floor(extent * aspect)), 1)
    resized = cv2.resize(
        mask.astype(np.uint8) * 255, (render_width, render_height),
        interpolation=cv2.INTER_AREA,
    )
    if abs(rotate_degrees) > 1e-8:
        resized = np.asarray(Image.fromarray(resized).rotate(
            float(rotate_degrees), resample=Image.Resampling.BICUBIC,
            expand=True, fillcolor=0,
        ))
    overlay_height, overlay_width = resized.shape
    left = max(0, min(
        size - overlay_width,
        int(math.floor((size - overlay_width) / 2.0 + shift_x)),
    ))
    top = max(0, min(
        size - overlay_height,
        int(math.floor((size - overlay_height) / 2.0 + shift_y)),
    ))
    result = np.zeros((size, size), bool)
    x2 = min(size, left + overlay_width)
    y2 = min(size, top + overlay_height)
    if x2 > left and y2 > top:
        result[top:y2, left:x2] = (
            resized[:y2 - top, :x2 - left] >= 48
        )
    return result


def _shift(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    height, width = mask.shape
    result = np.zeros_like(mask)
    sx1 = max(0, -dx); sx2 = min(width, width - dx)
    sy1 = max(0, -dy); sy2 = min(height, height - dy)
    if sx2 > sx1 and sy2 > sy1:
        result[sy1 + dy:sy2 + dy, sx1 + dx:sx2 + dx] = mask[sy1:sy2, sx1:sx2]
    return result


def _register_projection(
    projected: np.ndarray, observed_support: np.ndarray,
) -> tuple[np.ndarray, float, int, int]:
    observed = np.asarray(observed_support, bool)
    best = (-1.0, 0, 0)
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            shifted = _shift(projected, dx, dy)
            union = int(np.sum(shifted | observed))
            iou = int(np.sum(shifted & observed)) / max(1, union)
            key = (iou, -abs(dx) - abs(dy), -dy * 100 - dx)
            incumbent_key = (
                best[0], -abs(best[1]) - abs(best[2]),
                -best[2] * 100 - best[1],
            )
            if key > incumbent_key:
                best = (float(iou), dx, dy)
    alignment_iou, dx, dy = best
    return _shift(projected, dx, dy), float(alignment_iou), dx, dy


def augmented_svg_full_support(
    svg: str, row: dict, observed_support: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Project exact clean SVG support through the recorded raster transform."""
    size = int(row["size"])
    augmentation = row.get("augmentation", {})
    projected = _project_mask(
        svg_full_template(svg), size=size,
        scale=float(augmentation.get("scale", 0.75)),
        shift_x=int(augmentation.get("shift_x", 0)),
        shift_y=int(augmentation.get("shift_y", 0)),
        rotate_degrees=float(augmentation.get("rotate_degrees") or 0.0),
    )
    registered, alignment_iou, _dx, _dy = _register_projection(
        projected, observed_support,
    )
    return _freeze(registered), alignment_iou


def augmented_svg_owner_targets(
    templates: SvgOwnerTemplates, row: dict, observed_support: np.ndarray,
) -> tuple[tuple[tuple[str, np.ndarray], ...], float]:
    """Project clean owners into one recorded raster-pair augmentation."""
    size = int(row["size"])
    augmentation = row.get("augmentation", {})
    kwargs = {
        "size": size,
        "scale": float(augmentation.get("scale", 0.75)),
        "shift_x": int(augmentation.get("shift_x", 0)),
        "shift_y": int(augmentation.get("shift_y", 0)),
        "rotate_degrees": float(augmentation.get("rotate_degrees") or 0.0),
    }
    projected_full = _project_mask(templates.full_mask, **kwargs)
    _registered, alignment_iou, dx, dy = _register_projection(
        projected_full, observed_support,
    )
    # A malformed transform must not manufacture confident instance labels.
    if alignment_iou < 0.35:
        return (), float(alignment_iou)
    targets: list[tuple[str, np.ndarray]] = []
    for mask in templates.text_masks:
        projected = _shift(_project_mask(mask, **kwargs), dx, dy)
        if int(np.sum(projected)) >= 3:
            targets.append(("text_line", _freeze(projected)))
            targets.append(("glyph_group", _freeze(projected)))
    for mask in templates.mark_masks:
        projected = _shift(_project_mask(mask, **kwargs), dx, dy)
        if int(np.sum(projected)) >= 3:
            targets.append(("whole_shape", _freeze(projected)))
    return tuple(targets), float(alignment_iou)

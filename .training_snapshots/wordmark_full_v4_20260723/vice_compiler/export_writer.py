"""Deterministic editable writers for selected proof-carrying scenes."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import html
import io
import math
from pathlib import Path
import re
from functools import lru_cache
from typing import Iterable

import cv2
import numpy as np
from PIL import Image

from .appearance_macros import (
    AppearanceFitRecord, oklab_alpha_to_linear_premultiplied,
)
from .cleanup_macros import CodecCounterfactualRecord
from .certificates import topology_signature
from .curve_geometry import closed_catmull_rom_svg_path
from .design_program import DesignProgramIR, adapt_export_ir
from .evidence_ir import RasterEvidenceIR
from .layer_solver import LayeredScene
from .macro_ir import CandidateMacroIR, MacroCandidate, MacroKind
from .phase5_macros import Phase5MacroBundle
from .text_macros import TextMacroSet, materialize_font_free_geometry
from .shape_macros import materialize_repeated_group_members
from .visible_scene import VisibleSceneIR


@dataclass(frozen=True)
class ExportArtifact:
    target: str
    path: str
    sha256: str
    bytes: int
    native_primitives: int
    fallback_paths: int
    raster_images_embedded: int
    editable_score: float
    provenance: tuple[str, ...]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=128)
def _legacy_svg_document(
    path_text: str, expected_sha256: str,
) -> tuple[str, str, int]:
    """Return a verified document plus embeddable vector children."""
    path = Path(path_text)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("frozen V-ICE Best artifact hash mismatch")
    payload = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    if re.search(
        r"<(?:image|script|foreignObject)\b", payload, flags=re.IGNORECASE,
    ):
        raise ValueError("legacy fallback is not a self-contained vector SVG")
    opening = re.search(r"<svg\b[^>]*>", payload, flags=re.IGNORECASE)
    closing = payload.lower().rfind("</svg>")
    if opening is None or closing < opening.end():
        raise ValueError("invalid legacy fallback SVG")
    inner = payload[opening.end():closing]
    primitive_count = len(re.findall(
        r"<(?:path|circle|ellipse|rect|polygon|polyline|line)\b",
        inner, flags=re.IGNORECASE,
    ))
    group = f'<g data-pcdc-origin="v-ice-best">{inner}</g>'
    return payload, group, primitive_count


def _candidate_support(
    reir: RasterEvidenceIR, candidate: MacroCandidate,
) -> np.ndarray:
    certificate = candidate.certificates
    width, height = certificate.support_size
    count = width * height
    if certificate.support_bits:
        mask = np.unpackbits(
            np.frombuffer(certificate.support_bits, np.uint8),
            count=count, bitorder="little",
        ).astype(bool).reshape((height, width))
    elif certificate.support_rle:
        flat = np.zeros(count, bool)
        for start, length in certificate.support_rle:
            flat[int(start):int(start) + int(length)] = True
        mask = flat.reshape((height, width))
    else:
        leaf_ids = [
            index for index in range(reir.hierarchy.leaf_count)
            if candidate.core_bits & (1 << index)
        ]
        mask = np.isin(reir.hierarchy.leaf_labels, leaf_ids)
    if mask.shape != (reir.height, reir.width):
        mask = cv2.resize(
            mask.astype(np.uint8), (reir.width, reir.height),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    return mask


def _candidate_core_mask(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR,
    candidate: MacroCandidate,
) -> np.ndarray:
    """Decode the exact visible-owner cells of one selected column."""
    if cmir.leaf_count == reir.hierarchy.leaf_count:
        leaf_ids = [
            index for index in range(cmir.leaf_count)
            if candidate.core_bits & (1 << index)
        ]
        return np.isin(reir.hierarchy.leaf_labels, leaf_ids)
    result = np.zeros((reir.height, reir.width), bool)
    remaining = candidate.core_bits
    by_bit = {
        row.core_bits: row for row in cmir.candidates
        if row.kind is MacroKind.ATOMIC_FALLBACK
        and row.core_bits.bit_count() == 1
    }
    while remaining:
        bit = remaining & -remaining; remaining ^= bit
        atomic = by_bit.get(bit)
        if atomic is None:
            raise ValueError("refined visible owner has no atomic child support")
        result |= _candidate_support(reir, atomic)
    return result


def _rgba(reir: RasterEvidenceIR, mask: np.ndarray) -> tuple[int, int, int, float]:
    values = reir.raster.straight_rgba[mask]
    return _rgba_from_samples(values)


def _rgba_from_samples(values: np.ndarray) -> tuple[int, int, int, float]:
    if not len(values):
        return 0, 0, 0, 0.0
    median = np.clip(np.median(values, axis=0), 0.0, 1.0)
    return (
        int(round(float(median[0]) * 255)),
        int(round(float(median[1]) * 255)),
        int(round(float(median[2]) * 255)), float(median[3]),
    )


def _paint(color: tuple[int, int, int, float]) -> str:
    red, green, blue, alpha = color
    opacity = "" if alpha >= 0.9995 else f' fill-opacity="{alpha:.6g}"'
    return f'fill="#{red:02x}{green:02x}{blue:02x}"{opacity}'


def _pixel_run_path(mask: np.ndarray) -> str:
    """Exact union of pixel cells, used when centre contours collapse ink."""
    run_rows: list[str] = []
    binary = np.asarray(mask, bool)
    for y in range(binary.shape[0]):
        values = binary[y].astype(np.int8)
        transitions = np.diff(np.pad(values, (1, 1)))
        starts = np.flatnonzero(transitions == 1)
        ends = np.flatnonzero(transitions == -1)
        for start, end in zip(starts.tolist(), ends.tolist()):
            run_rows.append(f"M{start},{y}H{end}V{y + 1}H{start}Z")
    return " ".join(run_rows)


def _pixel_coordinate_run_path(
    coordinates: Iterable[tuple[int, int]], *, offset_x: int = 0,
    offset_y: int = 0,
) -> str:
    """Encode sparse local pixel coordinates without a canvas-sized mask."""
    by_row: dict[int, list[int]] = {}
    for y, x in coordinates:
        by_row.setdefault(int(y), []).append(int(x))
    rows = []
    for local_y in sorted(by_row):
        values = sorted(set(by_row[local_y]))
        if not values:
            continue
        start = previous = values[0]
        for value in (*values[1:], values[-1] + 2):
            if value != previous + 1:
                x_start = start + int(offset_x)
                x_end = previous + 1 + int(offset_x)
                y = local_y + int(offset_y)
                rows.append(
                    f"M{x_start},{y}H{x_end}V{y + 1}H{x_start}Z"
                )
                start = value
            previous = value
    return " ".join(rows)


def _mask_path(mask: np.ndarray, *, epsilon: float = 0.18) -> str:

    contours, hierarchy = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE,
    )
    if hierarchy is None:
        return _pixel_run_path(mask)
    rows = []
    contour_area = 0.0
    for contour in contours:
        contour_area += abs(float(cv2.contourArea(contour)))
        if len(contour) < 3:
            continue
        points = cv2.approxPolyDP(contour, epsilon, True).reshape((-1, 2))
        if len(points) < 3:
            continue
        rows.append(
            "M" + " ".join(
                f"{int(point[0])},{int(point[1])}" for point in points
            ) + "Z"
        )
    # OpenCV contours pass through pixel centres.  On thin glyphs/AA bands
    # their enclosed area can be far smaller than the actual union of pixel
    # cells, collapsing one-pixel stems and counters.  The run encoding is
    # exact and remains compact for these sparse masks.
    pixel_area = float(np.sum(mask))
    if (
        not rows
        or contour_area < 0.75 * pixel_area
        or contour_area > 1.25 * pixel_area
    ):
        return _pixel_run_path(mask)
    return " ".join(rows)


def _mask_boundary_f(first: np.ndarray, second: np.ndarray) -> float:
    kernel = np.ones((3, 3), np.uint8)
    first_edge = cv2.morphologyEx(
        first.astype(np.uint8), cv2.MORPH_GRADIENT, kernel,
    ) > 0
    second_edge = cv2.morphologyEx(
        second.astype(np.uint8), cv2.MORPH_GRADIENT, kernel,
    ) > 0
    if not np.any(first_edge) or not np.any(second_edge):
        return float(not np.any(first_edge) and not np.any(second_edge))
    to_first = cv2.distanceTransform((~first_edge).astype(np.uint8), cv2.DIST_L2, 3)
    to_second = cv2.distanceTransform((~second_edge).astype(np.uint8), cv2.DIST_L2, 3)
    precision = float(np.mean(to_first[second_edge] <= 1.5))
    recall = float(np.mean(to_second[first_edge] <= 1.5))
    return 2.0 * precision * recall / max(1e-9, precision + recall)


@lru_cache(maxsize=64)
def _fitted_mask_path_cached(
    height: int, width: int, payload: bytes, density_proof: bool,
) -> str:
    """Bounded corner-aware G1 fit with a mandatory local raster proof."""
    mask = np.frombuffer(payload, np.uint8).reshape((height, width)) > 0
    try:
        import resvg_py
        contours, _hierarchy = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE,
        )
        if not contours:
            return ""

        def render_path(path: str, *, render_width: int = width) -> np.ndarray:
            proof_svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
                f'height="{height}" viewBox="0 0 {width} {height}">'
                f'<path d="{path}" fill="#000" fill-rule="evenodd"/></svg>'
            )
            proof = np.asarray(Image.open(io.BytesIO(bytes(
                resvg_py.svg_to_bytes(svg_string=proof_svg, width=render_width)
            ))).convert("RGBA"))
            return proof[..., 3] >= 128

        def fidelity(rendered: np.ndarray) -> tuple[float, float]:
            intersection = int(np.sum(rendered & mask))
            union = int(np.sum(rendered | mask))
            return (
                intersection / max(1, union),
                _mask_boundary_f(rendered, mask),
            )

        # The raw path is the transactional incumbent.  A visually smoother
        # path is not an improvement if it loses more raster evidence.  Court
        # every fitted hypothesis against that incumbent, not only against a
        # permissive absolute threshold.
        raw_path = _mask_path(mask)
        raw_rendered = render_path(raw_path)
        raw_iou, raw_boundary = fidelity(raw_rendered)
        source_topology = topology_signature(mask)
        density_width = width
        density_incumbent: np.ndarray | None = None
        density_topology: tuple[int, int] | None = None
        if density_proof:
            density_scale = max(2, min(4, 1024 // max(1, width)))
            density_width = width * density_scale
            density_incumbent = render_path(
                _pixel_run_path(mask), render_width=density_width,
            )
            density_topology = topology_signature(density_incumbent)

        def encode(points: np.ndarray) -> str:
            ring = np.asarray(points, np.float64).reshape((-1, 2))
            if len(ring) < 3:
                return ""
            previous = np.roll(ring, 1, axis=0)
            following = np.roll(ring, -1, axis=0)
            incoming = ring - previous
            outgoing = following - ring
            incoming /= np.maximum(
                np.linalg.norm(incoming, axis=1, keepdims=True), 1e-9,
            )
            outgoing /= np.maximum(
                np.linalg.norm(outgoing, axis=1, keepdims=True), 1e-9,
            )
            turn = np.degrees(np.arccos(np.clip(
                np.sum(incoming * outgoing, axis=1), -1.0, 1.0,
            )))
            smooth = turn < 38.0
            tangents = following - previous
            tangents /= np.maximum(
                np.linalg.norm(tangents, axis=1, keepdims=True), 1e-9,
            )
            rows = [f"M{ring[0,0]:.4g},{ring[0,1]:.4g}"]
            for index in range(len(ring)):
                following_index = (index + 1) % len(ring)
                start = ring[index]; end = ring[following_index]
                chord = float(np.linalg.norm(end - start))
                if smooth[index] or smooth[following_index]:
                    c1 = (
                        start + tangents[index] * chord / 3.0
                        if smooth[index] else start
                    )
                    c2 = (
                        end - tangents[following_index] * chord / 3.0
                        if smooth[following_index] else end
                    )
                    rows.append(
                        f"C{c1[0]:.4g},{c1[1]:.4g} {c2[0]:.4g},{c2[1]:.4g} "
                        f"{end[0]:.4g},{end[1]:.4g}"
                    )
                else:
                    rows.append(f"L{end[0]:.4g},{end[1]:.4g}")
            rows.append("Z")
            return " ".join(rows)

        for epsilon in (1.0, 0.72, 0.50, 0.32):
            paths = []
            for contour in contours:
                perimeter = float(cv2.arcLength(contour, True))
                reduced = cv2.approxPolyDP(
                    contour, max(0.18, epsilon * min(1.0, perimeter / 48.0)), True,
                )
                path = encode(reduced)
                if path:
                    paths.append(path)
            if not paths:
                continue
            fitted_path = " ".join(paths)
            rendered = render_path(fitted_path)
            iou, boundary = fidelity(rendered)
            if (
                topology_signature(rendered) == source_topology
                and iou >= max(0.97, raw_iou - 2e-4)
                and boundary >= max(0.97, raw_boundary - 2e-4)
            ):
                if not density_proof:
                    return fitted_path
                assert density_incumbent is not None
                density_rendered = render_path(
                    fitted_path, render_width=density_width,
                )
                density_intersection = int(np.sum(
                    density_rendered & density_incumbent
                ))
                density_union = int(np.sum(
                    density_rendered | density_incumbent
                ))
                if (
                    topology_signature(density_rendered) == density_topology
                    and density_intersection / max(1, density_union) >= 0.94
                    and _mask_boundary_f(
                        density_rendered, density_incumbent,
                    ) >= 0.92
                ):
                    return fitted_path
        return ""
    except Exception:
        return ""


def _fitted_mask_path(
    mask: np.ndarray, *, density_proof: bool = False,
) -> str:
    source = np.ascontiguousarray(mask, np.uint8)
    return _fitted_mask_path_cached(
        source.shape[0], source.shape[1], source.tobytes(),
        bool(density_proof),
    )


def _free_curve_element(
    reir: RasterEvidenceIR, candidate: MacroCandidate,
    support: np.ndarray | None = None,
) -> str | None:
    """Return the one proof-checked free-curve element used by every caller."""
    if candidate.program.operator != "Shape/free_curve":
        return None
    visible = (
        _candidate_support(reir, candidate)
        if support is None else np.asarray(support, bool)
    )
    if visible.shape != (reir.height, reir.width) or not np.any(visible):
        return None
    fitted = closed_catmull_rom_svg_path(candidate.program.parameters)
    if fitted:
        proof_svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{reir.width}" '
            f'height="{reir.height}" viewBox="0 0 {reir.width} {reir.height}">'
            f'<path d="{fitted}" fill="#000" fill-rule="evenodd"/></svg>'
        )
        rendered = render_svg_roundtrip(
            proof_svg, width=reir.width,
        )[..., 3] >= 128
        intersection = int(np.sum(rendered & visible))
        union = int(np.sum(rendered | visible))
        if not (
            topology_signature(rendered) == topology_signature(visible)
            and intersection / max(1, union) >= 0.82
            and _mask_boundary_f(rendered, visible) >= 0.86
        ):
            fitted = ""
    if not fitted and "refined_source_id" not in dict(
        candidate.program.parameters
    ):
        fitted = _fitted_mask_path(visible)
    if not fitted:
        return None
    return (
        f'<path d="{fitted}" fill-rule="evenodd" '
        f'{_paint(_rgba(reir, visible))}/>'
    )


def render_shape_delivery(
    reir: RasterEvidenceIR, candidate: MacroCandidate,
) -> np.ndarray | None:
    """Render the exact free-curve element serialized by production.

    Returning ``None`` is a hard delivery-proof failure.  In particular, this
    function never substitutes the generic mask path after a fitted path has
    failed its own raster/topology proof.
    """
    element = _free_curve_element(reir, candidate)
    if element is None:
        return None
    document = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{reir.width}" '
        f'height="{reir.height}" viewBox="0 0 {reir.width} {reir.height}">'
        f'{element}</svg>'
    )
    return render_svg_roundtrip(document, width=reir.width)


def _leaf_rows(
    reir: RasterEvidenceIR, candidate: MacroCandidate,
) -> list[tuple[np.ndarray, tuple[int, int, int, float]]]:
    if candidate.program.operator == "AtomicRefinedFallback":
        support = _candidate_support(reir, candidate)
        parent = dict(candidate.program.parameters).get("parent_leaf_id")
        if not isinstance(parent, int) or not (
            0 <= parent < reir.hierarchy.leaf_count
        ):
            return []
        # A derived child is a geometric clip of its incumbent hierarchy leaf,
        # not a new colour-estimation problem.  Re-clustering each tiny child
        # independently changed colours and topology even when no typed macro
        # was selected.  Compute the parent's frozen paint decomposition once
        # and intersect it with this exact child support.
        parent_candidate = replace(
            candidate, core_bits=1 << parent,
            program=replace(
                candidate.program, operator="RefinedParentFallbackPaint",
            ),
        )
        return [
            (np.ascontiguousarray(mask & support, bool), color)
            for mask, color in _leaf_rows(reir, parent_candidate)
            if np.any(mask & support)
        ]
    rows = []
    labels = reir.hierarchy.leaf_labels
    rgba = np.asarray(reir.raster.straight_rgba, np.float32)
    border = np.concatenate((rgba[0], rgba[-1], rgba[:, 0], rgba[:, -1]))
    background = np.median(border, axis=0)
    masks = []
    bits = candidate.core_bits
    while bits:
        low = bits & -bits; leaf = low.bit_length() - 1; bits ^= low
        if leaf < reir.hierarchy.leaf_count:
            masks.append(labels == leaf)
    for mask in masks:
        if not np.any(mask):
            continue
        values = rgba[mask]
        quantized = np.concatenate((
            np.rint(np.clip(values[:, :3], 0.0, 1.0) * 31.0).astype(np.int16),
            np.rint(np.clip(values[:, 3:4], 0.0, 1.0) * 15.0).astype(np.int16),
        ), axis=1)
        unique, inverse, counts = np.unique(
            quantized, axis=0, return_inverse=True, return_counts=True,
        )
        rgb_distance = np.linalg.norm(
            values[:, :3] - background[None, :3], axis=1,
        )
        # A leaf that mixes canvas colour with strong ink is normally an
        # antialiased edge/text fragment.  Treating every sampled AA shade as
        # an independent opaque shape creates checkerboard holes and false
        # components.  Preserve a dark/core layer plus at most two edge
        # layers; retain more bands only for genuinely non-background smooth
        # appearance regions (which may be a gradient fallback).
        ink_like = bool(
            np.mean(rgb_distance <= 0.08) >= 0.08
            and float(np.max(rgb_distance, initial=0.0)) >= 0.24
        )
        maximum = 3 if ink_like else 8
        if len(unique) > maximum:
            dominant = np.argsort(-counts, kind="stable")[:maximum]
            background_quantized = np.concatenate((
                np.rint(np.clip(background[:3], 0.0, 1.0) * 31.0),
                np.rint(np.clip(background[3:4], 0.0, 1.0) * 15.0),
            ))
            normalized = unique / np.asarray((31.0, 31.0, 31.0, 15.0))
            normalized_background = (
                background_quantized
                / np.asarray((31.0, 31.0, 31.0, 15.0))
            )
            extreme = int(np.argmax(np.sum(np.square(
                normalized - normalized_background,
            ), axis=1)))
            if extreme not in dominant:
                dominant[-1] = extreme
            centers = unique[dominant].astype(np.float64)
            scale = np.asarray((31.0, 31.0, 31.0, 15.0), np.float64)
            distance = np.sum(np.square(
                unique[:, None, :] / scale
                - centers[None, :, :] / scale
            ), axis=2)
            assignment = np.argmin(distance, axis=1)
            cluster_ids = assignment[inverse]
            cluster_count = maximum
        else:
            cluster_ids = inverse
            cluster_count = len(unique)
        flat_indices = np.flatnonzero(mask)
        for cluster in range(cluster_count):
            members = cluster_ids == cluster
            if not np.any(members):
                continue
            submask = np.zeros(mask.shape, bool)
            submask.ravel()[flat_indices[members]] = True
            color = np.median(values[members], axis=0)
            if (
                float(np.linalg.norm(color[:3] - background[:3])) < 0.035
                and abs(float(color[3] - background[3])) < 0.02
            ):
                continue
            rows.append((submask, (
                int(round(float(color[0]) * 255)),
                int(round(float(color[1]) * 255)),
                int(round(float(color[2]) * 255)),
                float(color[3]),
            )))
    return rows


def _number(parameters: dict[str, object], key: str, default: float = 0.0) -> float:
    value = parameters.get(key, default)
    return float(value) if isinstance(value, (float, int)) else float(default)


def _delivery_source_id(candidate: MacroCandidate) -> str:
    """Resolve the immutable Phase-4/5 record behind a refined candidate."""

    value = dict(candidate.program.parameters).get("refined_source_id")
    return str(value) if isinstance(value, str) and value else candidate.id


def _polygon_parameters(parameters: tuple[tuple[str, object], ...]) -> list[tuple[float, float]]:
    values = dict(parameters); rows = []
    for index in range(64):
        x = values.get(f"p{index}_x"); y = values.get(f"p{index}_y")
        if not isinstance(x, (float, int)) or not isinstance(y, (float, int)):
            break
        rows.append((float(x), float(y)))
    return rows


def _native_element(
    candidate: MacroCandidate, paint: str, mask: np.ndarray,
) -> str | None:
    operator = candidate.program.operator
    parameters = dict(candidate.program.parameters)
    if operator == "Shape/circle":
        return (
            f'<circle cx="{_number(parameters, "cx"):.8g}" '
            f'cy="{_number(parameters, "cy"):.8g}" '
            f'r="{max(0.0, _number(parameters, "radius")):.8g}" {paint}/>'
        )
    if operator == "Shape/ring":
        cx = _number(parameters, "cx"); cy = _number(parameters, "cy")
        outer = max(0.0, _number(parameters, "radius"))
        inner = max(0.0, _number(parameters, "inner_radius"))
        if inner <= 0 or outer <= inner:
            return None
        path = (
            f"M{cx-outer:.8g},{cy:.8g}a{outer:.8g},{outer:.8g} 0 1,0 "
            f"{2*outer:.8g},0a{outer:.8g},{outer:.8g} 0 1,0 {-2*outer:.8g},0Z "
            f"M{cx-inner:.8g},{cy:.8g}a{inner:.8g},{inner:.8g} 0 1,1 "
            f"{2*inner:.8g},0a{inner:.8g},{inner:.8g} 0 1,1 {-2*inner:.8g},0Z"
        )
        return f'<path d="{path}" fill-rule="evenodd" {paint}/>'
    if operator == "Shape/ellipse":
        cx = _number(parameters, "cx"); cy = _number(parameters, "cy")
        rx = max(0.0, _number(parameters, "rx")); ry = max(0.0, _number(parameters, "ry"))
        angle = _number(parameters, "angle")
        transform = "" if abs(angle) < 1e-9 else f' transform="rotate({angle:.8g} {cx:.8g} {cy:.8g})"'
        return f'<ellipse cx="{cx:.8g}" cy="{cy:.8g}" rx="{rx:.8g}" ry="{ry:.8g}"{transform} {paint}/>'
    if operator in {"Shape/rectangle", "Shape/rounded_rectangle"}:
        x = _number(parameters, "x"); y = _number(parameters, "y")
        width = max(0.0, _number(parameters, "width")); height = max(0.0, _number(parameters, "height"))
        radius = max(0.0, _number(parameters, "radius")) if operator.endswith("rounded_rectangle") else 0.0
        rounded = "" if radius <= 0 else f' rx="{radius:.8g}" ry="{radius:.8g}"'
        return f'<rect x="{x:.8g}" y="{y:.8g}" width="{width:.8g}" height="{height:.8g}"{rounded} {paint}/>'
    if operator in {"Shape/triangle", "Shape/quadrilateral", "Shape/star"}:
        points = _polygon_parameters(candidate.program.parameters)
        if points:
            encoded = " ".join(f"{x:.8g},{y:.8g}" for x, y in points)
            return f'<polygon points="{encoded}" {paint}/>'
    return None


def _linear_premult_to_stop(
    values: np.ndarray,
) -> tuple[str, float]:
    row = np.asarray(values, np.float64)
    alpha = float(np.clip(row[3], 0.0, 1.0))
    linear = np.clip(row[:3] / max(alpha, 1e-8), 0.0, 1.0)
    srgb = np.where(
        linear <= 0.0031308, 12.92 * linear,
        1.055 * np.power(linear, 1.0 / 2.4) - 0.055,
    )
    encoded = "#" + "".join(
        f"{int(round(float(np.clip(value, 0.0, 1.0)) * 255)):02x}"
        for value in srgb
    )
    return encoded, alpha


def _support_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("cannot export an empty appearance support")
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _appearance_element(
    reir: RasterEvidenceIR, record: AppearanceFitRecord,
    candidate: MacroCandidate | None = None,
) -> str | None:
    support = np.asarray(record.support_mask, bool)
    path = _mask_path(support)
    if not path:
        return None
    rendered = oklab_alpha_to_linear_premultiplied(
        record.rendered_oklab_alpha,
    )
    parameters = dict(
        candidate.program.parameters if candidate is not None
        else record.parameters
    )
    model = record.model
    if model == "ordered_translucent_stack":
        if not 2 <= len(record.stack_layers) <= 3:
            return None
        rows = []
        for index, layer in enumerate(record.stack_layers):
            layer_path = _mask_path(np.asarray(layer.support_mask, bool))
            if not layer_path:
                return None
            color, alpha = _linear_premult_to_stop(np.asarray(
                layer.linear_premultiplied_rgba, np.float32,
            ))
            rows.append(
                f'<path d="{layer_path}" fill-rule="evenodd" fill="{color}" '
                f'fill-opacity="{alpha:.8g}" data-pcdc-stack-layer="{index}"/>'
            )
        return (
            f'<g data-pcdc-appearance="ordered-translucent-stack" '
            f'data-pcdc-stack-k="{len(rows)}">{"".join(rows)}</g>'
        )
    if model in {"solid", "translucent_solid"}:
        if candidate is not None and all(
            name in parameters for name in (
                "oklab_l", "oklab_a", "oklab_b", "alpha",
            )
        ):
            oklab_alpha = np.asarray([[[
                _number(parameters, "oklab_l"),
                _number(parameters, "oklab_a"),
                _number(parameters, "oklab_b"),
                _number(parameters, "alpha", 1.0),
            ]]], np.float32)
            color, alpha = _linear_premult_to_stop(
                oklab_alpha_to_linear_premultiplied(oklab_alpha)[0, 0],
            )
        else:
            color, alpha = _linear_premult_to_stop(
                np.median(rendered[support], axis=0),
            )
        opacity = "" if alpha >= 0.9995 else f' fill-opacity="{alpha:.8g}"'
        return f'<path d="{path}" fill-rule="evenodd" fill="{color}"{opacity}/>'
    if model == "flat_albedo_smooth_shade":
        # A quadratic 2-D shade field has no faithful compact SVG 1.1 native
        # primitive.  Keep it out of the certified delivery path until a mesh
        # gradient writer and the same renderer exist.
        return None

    y, x = np.indices(support.shape, dtype=np.float64)
    x1, y1, x2, y2 = _support_bbox(support)
    if "radial" in model:
        cx = float(parameters.get("cx", 0.5 * (x1 + x2)))
        cy = float(parameters.get("cy", 0.5 * (y1 + y2)))
        coordinate = np.hypot(x - cx, y - cy)
        maximum = float(np.max(coordinate[support]))
        if maximum <= 1e-8:
            return None
        t = np.clip(coordinate / maximum, 0.0, 1.0)
        gradient_tag = "radialGradient"
        geometry = f'cx="{cx:.8g}" cy="{cy:.8g}" r="{maximum:.8g}"'
    else:
        angle = math.radians(float(parameters.get("angle_deg", 0.0)))
        dx = math.cos(angle); dy = math.sin(angle)
        projection = x * dx + y * dy
        low = float(np.min(projection[support])); high = float(np.max(projection[support]))
        if high - low <= 1e-8:
            return None
        t = np.clip((projection - low) / (high - low), 0.0, 1.0)
        gradient_tag = "linearGradient"
        geometry = (
            f'x1="{low * dx:.8g}" y1="{low * dy:.8g}" '
            f'x2="{high * dx:.8g}" y2="{high * dy:.8g}"'
        )
    identifier = "appearance-" + re.sub(r"[^A-Za-z0-9_-]", "-", record.candidate.id)
    stop_rows = []
    for offset in np.linspace(0.0, 1.0, 9):
        band = support & (np.abs(t - offset) <= 0.075)
        if not np.any(band):
            nearest = np.abs(t - offset) + (~support) * 2.0
            iy, ix = np.unravel_index(int(np.argmin(nearest)), nearest.shape)
            value = rendered[iy, ix]
        else:
            value = np.median(rendered[band], axis=0)
        color, alpha = _linear_premult_to_stop(value)
        opacity = "" if alpha >= 0.9995 else f' stop-opacity="{alpha:.8g}"'
        stop_rows.append(
            f'<stop offset="{offset:.8g}" stop-color="{color}"{opacity}/>'
        )
    definition = (
        f'<defs><{gradient_tag} id="{identifier}" gradientUnits="userSpaceOnUse" '
        f'{geometry}>{"".join(stop_rows)}</{gradient_tag}></defs>'
    )
    return (
        definition
        + f'<path d="{path}" fill-rule="evenodd" fill="url(#{identifier})"/>'
    )


def render_appearance_delivery(
    reir: RasterEvidenceIR, record: AppearanceFitRecord,
    candidate: MacroCandidate | None = None,
) -> np.ndarray | None:
    """Render the exact same SVG appearance element used by production."""
    element = _appearance_element(reir, record, candidate)
    if element is None:
        return None
    document = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{reir.width}" '
        f'height="{reir.height}" viewBox="0 0 {reir.width} {reir.height}">'
        f'{element}</svg>'
    )
    return render_svg_roundtrip(document, width=reir.width)


def _codec_elements(
    reir: RasterEvidenceIR, record: CodecCounterfactualRecord,
) -> list[str]:
    """Serialize the proved codec patch as bounded, raster-free pixel runs.

    A codec counterfactual is only entitled to repaint its certified locus,
    not the padded context used to score the local renderer posterior.  The
    patch is quantized through the exact SVG colour model and equal colours
    are merged into pixel-run paths.  This is deliberately a fallback vector
    representation: it is faithful and editable enough for a micro-locus,
    while never pretending that a JPEG cleanup patch is an analytic shape.
    """
    support = np.asarray(record.support_mask, bool)
    if support.shape != (reir.height, reir.width) or not np.any(support):
        return []
    x1, y1, x2, y2 = record.render_roi_xyxy
    patch = np.asarray(record.rendered_premultiplied_patch, np.float32)
    if patch.shape != (y2 - y1, x2 - x1, 4):
        return []
    local_support = support[y1:y2, x1:x2]
    colors: dict[tuple[int, int, int, int], list[tuple[int, int]]] = {}
    for local_y, local_x in np.argwhere(local_support):
        value = patch[int(local_y), int(local_x)]
        alpha = float(np.clip(value[3], 0.0, 1.0))
        alpha8 = int(round(alpha * 255.0))
        if alpha8 <= 0:
            continue
        linear = np.clip(value[:3] / max(alpha, 1e-8), 0.0, 1.0)
        srgb = np.where(
            linear <= 0.0031308, 12.92 * linear,
            1.055 * np.power(linear, 1.0 / 2.4) - 0.055,
        )
        # Five-bit colour is an explicit bounded codec model, not an implicit
        # exporter approximation.  Court renders these exact same values, so
        # a quantized cleanup that loses visible evidence simply cannot win.
        key = (
            *(int(round(round(float(channel) * 31.0) * 255.0 / 31.0))
              for channel in srgb),
            alpha8,
        )
        colors.setdefault(key, []).append((int(local_y), int(local_x)))
    rows = []
    for red, green, blue, alpha8 in sorted(colors):
        path = _pixel_coordinate_run_path(
            colors[(red, green, blue, alpha8)],
            offset_x=x1, offset_y=y1,
        )
        if not path:
            continue
        rows.append(
            f'<path d="{path}" fill-rule="evenodd" '
            f'shape-rendering="crispEdges" '
            f'data-pcdc-color-bits="5" '
            f'data-pcdc-codec="{html.escape(record.counterfactual, quote=True)}" '
            f'{_paint((red, green, blue, alpha8 / 255.0))}/>'
        )
    return rows


def render_codec_delivery(
    reir: RasterEvidenceIR, record: CodecCounterfactualRecord,
) -> np.ndarray | None:
    """Render the exact raster-free SVG elements used by production export."""
    elements = _codec_elements(reir, record)
    if not elements:
        return None
    document = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{reir.width}" '
        f'height="{reir.height}" viewBox="0 0 {reir.width} {reir.height}">'
        f'<g data-pcdc-codec-locus="{html.escape(record.locus_id, quote=True)}">'
        f'{"".join(elements)}</g></svg>'
    )
    return render_svg_roundtrip(document, width=reir.width)


def _stroke_elements(
    candidate: MacroCandidate, paint_color: tuple[int, int, int, float],
    bundle: Phase5MacroBundle | None,
) -> list[str]:
    if bundle is None:
        return []
    record = next((
        row for row in bundle.strokes.records
        if row.candidate.id == _delivery_source_id(candidate)
    ), None)
    if record is None:
        return []
    red, green, blue, alpha = paint_color
    opacity = "" if alpha >= 0.9995 else f' stroke-opacity="{alpha:.6g}"'
    dash = (
        ' stroke-dasharray="'
        + " ".join(f"{value:.8g}" for value in record.graph.dash_pattern)
        + '"'
        if record.graph.dash_pattern else ""
    )
    rows = []
    marker_attributes = ""
    if record.graph.markers:
        marker_base = "pcdc-marker-" + hashlib.sha256(
            candidate.id.encode("utf-8")
        ).hexdigest()[:12]
        marker_paint = f'fill="#{red:02x}{green:02x}{blue:02x}"'
        if alpha < 0.9995:
            marker_paint += f' fill-opacity="{alpha:.6g}"'
        definitions = []
        if "arrow-start" in record.graph.markers:
            marker_id = marker_base + "-start"
            definitions.append(
                f'<marker id="{marker_id}" markerWidth="4" markerHeight="4" '
                'refX="0" refY="2" orient="auto-start-reverse" '
                'markerUnits="strokeWidth">'
                f'<path d="M4 0L0 2L4 4Z" {marker_paint}/></marker>'
            )
            marker_attributes += f' marker-start="url(#{marker_id})"'
        if "arrow-end" in record.graph.markers:
            marker_id = marker_base + "-end"
            definitions.append(
                f'<marker id="{marker_id}" markerWidth="4" markerHeight="4" '
                'refX="4" refY="2" orient="auto" markerUnits="strokeWidth">'
                f'<path d="M0 0L4 2L0 4Z" {marker_paint}/></marker>'
            )
            marker_attributes += f' marker-end="url(#{marker_id})"'
        rows.append("<defs>" + "".join(definitions) + "</defs>")
    target_width = max(
        0.25, _number(
            dict(candidate.program.parameters), "width",
            record.width_median_px,
        ),
    )
    width_scale = target_width / max(0.25, record.width_median_px)
    for edge in record.graph.edges:
        points = " ".join(f"{x:.8g},{y:.8g}" for x, y in edge.centerline)
        width = (
            float(np.median(edge.width_profile))
            if edge.width_profile else record.width_median_px
        ) * width_scale
        rows.append(
            f'<polyline points="{points}" fill="none" stroke="#{red:02x}{green:02x}{blue:02x}" '
            f'stroke-width="{width:.8g}" stroke-linecap="{record.graph.cap}" '
            f'stroke-linejoin="{record.graph.join}"{dash}'
            f'{marker_attributes}{opacity}/>'
        )
    return rows


def render_stroke_delivery(
    reir: RasterEvidenceIR, candidate: MacroCandidate,
    bundle: Phase5MacroBundle,
) -> np.ndarray | None:
    support = _candidate_support(reir, candidate)
    rows = _stroke_elements(candidate, _rgba(reir, support), bundle)
    if not rows:
        return None
    document = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{reir.width}" '
        f'height="{reir.height}" viewBox="0 0 {reir.width} {reir.height}">'
        + "".join(rows) + "</svg>"
    )
    return render_svg_roundtrip(document, width=reir.width)


def _group_elements(
    reir: RasterEvidenceIR, candidate: MacroCandidate,
    bundle: Phase5MacroBundle | None,
) -> list[str]:
    if bundle is None or not candidate.program.operator.startswith("RepeatGroup/"):
        return []
    group = next((
        row for row in bundle.shapes.groups
        if row.candidate.id == _delivery_source_id(candidate)
    ), None)
    if group is None:
        return []
    members = materialize_repeated_group_members(
        group, bundle.shapes.records,
        shared_scale=_number(
            dict(candidate.program.parameters), "shared_scale",
            float(dict(group.shared_parameters).get("scale", 1.0)),
        ),
        shared_gap=(
            _number(
                dict(candidate.program.parameters), "shared_gap",
                float(dict(group.shared_parameters)["gap"]),
            )
            if "gap" in dict(group.shared_parameters) else None
        ),
    )
    rows: list[str] = []
    for member in members:
        support = _candidate_support(reir, member)
        if not np.any(support):
            return []
        element = _native_element(member, _paint(_rgba(reir, support)), support)
        if element is None:
            return []
        rows.append(element)
    return rows


def render_group_delivery(
    reir: RasterEvidenceIR, candidate: MacroCandidate,
    bundle: Phase5MacroBundle,
) -> np.ndarray | None:
    rows = _group_elements(reir, candidate, bundle)
    if not rows:
        return None
    document = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{reir.width}" '
        f'height="{reir.height}" viewBox="0 0 {reir.width} {reir.height}">'
        + "".join(rows) + "</svg>"
    )
    return render_svg_roundtrip(document, width=reir.width)


def _loop_path(points: tuple[tuple[float, float], ...]) -> str:
    if len(points) < 3:
        return ""
    return (
        f"M{points[0][0]:.8g},{points[0][1]:.8g} "
        + " ".join(f"L{x:.8g},{y:.8g}" for x, y in points[1:])
        + " Z"
    )


@lru_cache(maxsize=64)
def _exact_font_outline_path_cached(
    font_file: str, text: str, tracking_em: float,
    x_scale: float, y_scale: float, offset_x: float, offset_y: float,
    roi_xyxy: tuple[int, int, int, int],
    ink_bbox_xyxy: tuple[int, int, int, int],
) -> str:
    """Materialise the retrieved font's real quadratic/cubic outlines.

    The affine is the vector equivalent of ``font_match.compose_candidate``:
    glyph outlines are first placed on the matcher's 192 px font lattice,
    cropped to the same tight ink bounds, then scaled/centred in the proved
    TextLine ROI.  The caller still rerenders and certifies the resulting path;
    a missing font or a mapping disagreement therefore fails closed.
    """
    path = Path(font_file)
    if not path.is_file() or not text:
        return ""
    try:
        import font_match
        from PIL import ImageFont
        from fontTools.misc.transform import Transform
        from fontTools.pens.boundsPen import BoundsPen
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.transformPen import TransformPen
        from fontTools.ttLib import TTFont

        font_size = 192
        pil_font = ImageFont.truetype(str(path), font_size)
        ascent, _descent = pil_font.getmetrics()
        font = TTFont(str(path), fontNumber=0, lazy=True)
        try:
            units_per_em = float(font["head"].unitsPerEm)
            cmap = font.getBestCmap() or {}
            glyph_set = font.getGlyphSet()
            font_scale = font_size / units_per_em
            glyph_rows = []
            bounds = []
            for index, character in enumerate(text):
                glyph_name = cmap.get(ord(character))
                if character.isspace() or glyph_name is None:
                    continue
                x_position = (
                    float(pil_font.getlength(text[:index]))
                    + index * float(tracking_em) * font_size
                )
                base = Transform(
                    font_scale, 0.0, 0.0, -font_scale,
                    x_position, float(ascent),
                )
                bounds_pen = BoundsPen(glyph_set)
                glyph_set[glyph_name].draw(TransformPen(bounds_pen, base))
                if bounds_pen.bounds is None:
                    continue
                glyph_rows.append((glyph_name, base))
                bounds.append(bounds_pen.bounds)
            if not glyph_rows:
                return ""

            source_alpha = font_match.render_tracked_text(
                str(path), text, float(tracking_em), font_size=font_size,
            )
            source_height, source_width = source_alpha.shape
            ix1, iy1, ix2, iy2 = ink_bbox_xyxy
            if source_height <= 0 or source_width <= 0 or iy2 <= iy1:
                return ""
            scale = (iy2 - iy1) / float(source_height)
            sx = scale * float(x_scale)
            sy = scale * float(y_scale)
            center_x = 0.5 * (ix1 + ix2) + float(offset_x)
            center_y = 0.5 * (iy1 + iy2) + float(offset_y)
            roi_x1, roi_y1, _roi_x2, _roi_y2 = roi_xyxy
            left = roi_x1 + center_x - 0.5 * source_width * sx
            top = roi_y1 + center_y - 0.5 * source_height * sy
            minimum_x = min(row[0] for row in bounds)
            minimum_y = min(row[1] for row in bounds)
            target = Transform(
                sx, 0.0, 0.0, sy,
                left - minimum_x * sx, top - minimum_y * sy,
            )
            commands = []
            for glyph_name, base in glyph_rows:
                svg_pen = SVGPathPen(glyph_set)
                glyph_set[glyph_name].draw(TransformPen(
                    TransformPen(svg_pen, target), base,
                ))
                command = svg_pen.getCommands()
                if command:
                    commands.append(command)
            return " ".join(commands)
        finally:
            font.close()
    except Exception:
        return ""


def _exact_font_element(
    reir: RasterEvidenceIR, candidate: MacroCandidate,
    line: object, paint: str,
) -> str | None:
    parameters = dict(candidate.program.parameters)
    required = (
        "text", "font_file", "tracking_em", "x_scale", "y_scale",
        "offset_x", "offset_y",
    )
    if any(name not in parameters for name in required):
        return None
    support = _candidate_support(reir, candidate)
    roi = tuple(int(value) for value in getattr(line, "roi_xyxy"))
    x1, y1, x2, y2 = roi
    # Font-match parameters were fitted against the source TextLine support,
    # not against the already composed candidate silhouette.  Reusing the
    # latter's bbox would apply the placement transform a second time.
    line_support = np.asarray(getattr(line, "support_mask"), bool)
    if line_support.shape != (reir.height, reir.width):
        return None
    local = line_support[y1:y2, x1:x2]
    ys, xs = np.nonzero(local)
    if not len(xs):
        return None
    ink_bbox = (
        int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1,
    )
    path = _exact_font_outline_path_cached(
        str(parameters["font_file"]), str(parameters["text"]),
        float(parameters["tracking_em"]), float(parameters["x_scale"]),
        float(parameters["y_scale"]), float(parameters["offset_x"]),
        float(parameters["offset_y"]), roi, ink_bbox,
    )
    if not path:
        return None
    font_name = html.escape(Path(str(parameters["font_file"])).name, quote=True)
    element = (
        f'<path d="{path}" fill-rule="nonzero" '
        f'data-pcdc-text-geometry="exact-font-outline" '
        f'data-pcdc-font-source="{font_name}" {paint}/>'
    )
    proof_svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{reir.width}" '
        f'height="{reir.height}" viewBox="0 0 {reir.width} {reir.height}">'
        f'{element}</svg>'
    )
    rendered = render_svg_roundtrip(proof_svg, width=reir.width)[..., 3] >= 128
    intersection = int(np.sum(rendered & support))
    union = int(np.sum(rendered | support))
    if (
        topology_signature(rendered) != topology_signature(support)
        or intersection / max(1, union) < 0.82
        or _mask_boundary_f(rendered, support) < 0.90
    ):
        return None
    return element


def _text_elements(
    reir: RasterEvidenceIR, candidate: MacroCandidate,
    paint: str, generated: TextMacroSet | None,
) -> list[str]:
    if generated is None:
        return []
    record = next((
        row for row in generated.records
        if row.candidate.id == _delivery_source_id(candidate)
    ), None)
    if record is None:
        return []
    line = next((
        row for row in generated.proposals if row.id == record.line_id
    ), None)
    if line is None:
        return []
    parameters = dict(candidate.program.parameters)

    def transformed(
        fragments: list[str], *, glyph_fragments: bool = False,
    ) -> list[str]:
        if (
            not fragments
            or record.path in {"exact-font", "semantic-font-idealization"}
        ):
            return fragments
        baseline = _number(parameters, "baseline", float(line.baseline))
        x_height = max(
            0.25, _number(parameters, "x_height", float(line.x_height)),
        )
        cap_height = max(
            0.25, _number(parameters, "cap_height", float(line.cap_height)),
        )
        scale_y = 0.5 * (
            x_height / max(0.25, float(line.x_height))
            + cap_height / max(0.25, float(line.cap_height))
        )
        shear = _number(parameters, "slant", float(line.slant)) - float(
            line.slant
        )
        overshoot = _number(
            parameters, "overshoot", float(line.overshoot),
        )
        tracking = _number(
            parameters, "tracking", float(line.tracking),
        )
        measured_stem = float(np.median([
            glyph.stem_width for glyph in line.glyphs
        ]))
        shared_stem_width = _number(
            parameters, "shared_stem_width", measured_stem,
        )
        stem_delta = shared_stem_width - measured_stem
        stem_adjusted = fragments
        if stem_delta > 1e-12:
            # A positive SDF offset is exactly a same-ink outline around each
            # positive/negative loop.  Express the subpixel remainder as a
            # native SVG stroke so 0.25 px weight refinements do not disappear
            # on the integer evidence lattice.  The Phase-7 exact rerender and
            # topology certificate still decide whether the offset commits.
            def thicken(fragment: str) -> str:
                match = re.search(r'\bfill="([^"]+)"', fragment)
                if match is None or "<path " not in fragment:
                    return fragment
                opacity = re.search(r'\bfill-opacity="([^"]+)"', fragment)
                opacity_row = (
                    f' stroke-opacity="{opacity.group(1)}"'
                    if opacity is not None else ""
                )
                attributes = (
                    f'stroke="{match.group(1)}" stroke-width="{stem_delta:.12g}" '
                    'stroke-linejoin="round" paint-order="stroke fill"'
                    f'{opacity_row} '
                )
                return fragment.replace("<path ", f"<path {attributes}", 1)

            stem_adjusted = [thicken(fragment) for fragment in fragments]
        tracking_delta = tracking - float(line.tracking)
        tracked = stem_adjusted
        scale_x = 1.0
        if abs(tracking_delta) > 1e-12 and len(line.glyphs) >= 2:
            if glyph_fragments and len(fragments) == len(line.glyphs):
                order = sorted(
                    range(len(line.glyphs)),
                    key=lambda index: (
                        line.glyphs[index].bbox_xyxy[0],
                        line.glyphs[index].bbox_xyxy[1],
                    ),
                )
                rank = {
                    glyph_index: value
                    for value, glyph_index in enumerate(order)
                }
                centre_rank = 0.5 * (len(line.glyphs) - 1)
                tracked = [
                    '<g data-pcdc-glyph-tracking="true" '
                    f'transform="translate('
                    f'{(rank[index] - centre_rank) * tracking_delta:.12g} 0)">'
                    f'{fragment}</g>'
                    for index, fragment in enumerate(stem_adjusted)
                ]
            else:
                x1, _y1, x2, _y2 = line.roi_xyxy
                width = max(1.0, float(x2 - x1))
                scale_x = float(np.clip(
                    1.0 + (len(line.glyphs) - 1) * tracking_delta / width,
                    0.5, 1.5,
                ))
        base = float(line.baseline)
        x1, _y1, x2, _y2 = line.roi_xyxy
        centre_x = 0.5 * float(x1 + x2)
        translate_x = centre_x * (1.0 - scale_x) - shear * base
        target_baseline = baseline + overshoot - float(line.overshoot)
        translate_y = target_baseline - scale_y * base
        if (
            tracked is fragments
            and abs(scale_x - 1.0) <= 1e-12
            and abs(scale_y - 1.0) <= 1e-12
            and abs(shear) <= 1e-12
            and abs(target_baseline - base) <= 1e-12
        ):
            return fragments
        return [
            '<g data-pcdc-text-refinement="baseline+xheight+capheight+'
            'overshoot+slant+tracking+stem" '
            f'transform="matrix({scale_x:.12g} 0 {shear:.12g} {scale_y:.12g} '
            f'{translate_x:.12g} {translate_y:.12g})">'
            + "".join(tracked) + "</g>"
        ]
    if record.path in {"exact-font", "semantic-font-idealization"}:
        element = _exact_font_element(reir, candidate, line, paint)
        return [element] if element is not None else []
    if record.effect_layers:
        delivery_support = np.asarray(line.support_mask, bool)
        layer_masks = [
            np.asarray(layer.support_mask, bool)
            for layer in record.effect_layers
        ]
        # A deferred font-free fill first idealises the line geometry.  Extend
        # the source-observed colour partition to that geometry by nearest
        # labelled ink; never collapse a multi-colour wordmark to one median
        # paint, and never leave the reconstructed stems unpainted.
        if (
            record.path in {"font-free-dual-loop", "conservative-outline"}
            and len(layer_masks) >= 2
            and all(layer.role == "fill" for layer in record.effect_layers)
        ):
            try:
                delivery_support, _glyphs, _prototypes = (
                    materialize_font_free_geometry(reir, line)
                )
                distances = np.stack([
                    cv2.distanceTransform(
                        (~mask).astype(np.uint8), cv2.DIST_L2, 3,
                    )
                    for mask in layer_masks
                ], axis=0)
                ownership = np.argmin(distances, axis=0)
                layer_masks = [
                    delivery_support & (ownership == index)
                    for index in range(len(layer_masks))
                ]
            except Exception:
                return []
        effect_rows: list[str] = []
        for layer, layer_mask in zip(record.effect_layers, layer_masks):
            path = _fitted_mask_path(layer_mask, density_proof=True)
            geometry = "court-proven-g1"
            if not path:
                path = _pixel_run_path(layer_mask)
                geometry = "topology-safe-outline"
            if not path:
                return []
            rgba = tuple(
                int(round(float(value) * 255.0)) for value in layer.straight_rgba[:3]
            ) + (float(layer.straight_rgba[3]),)
            dx, dy = layer.offset_xy
            effect_rows.append(
                f'<path d="{path}" fill-rule="evenodd" '
                f'data-pcdc-text-effect="{layer.role}" '
                f'data-pcdc-effect-offset="{dx},{dy}" '
                f'data-pcdc-text-geometry="{geometry}" {_paint(rgba)}/>'
            )
        proof_svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{reir.width}" '
            f'height="{reir.height}" viewBox="0 0 {reir.width} {reir.height}">'
            + "".join(effect_rows) + "</svg>"
        )
        rendered = render_svg_roundtrip(
            proof_svg, width=reir.width,
        )[..., 3] >= 128
        intersection = int(np.sum(rendered & delivery_support))
        union = int(np.sum(rendered | delivery_support))
        if (
            topology_signature(rendered) == topology_signature(delivery_support)
            and intersection / max(1, union) >= 0.82
        ):
            return transformed(effect_rows)
        return []
    try:
        line_mask, glyphs, _prototypes = materialize_font_free_geometry(reir, line)
    except Exception:
        return []
    # The dual-loop program is the topology-safe fallback, but shipping its
    # pixel-contour vertices directly makes letters visibly angular.  Reuse
    # the same bounded G1 fitter as free curves and accept it only after its
    # local raster proof preserves topology, IoU and boundary F relative to
    # the raw outline.  This changes delivered text geometry, not a preview.
    fitted = _fitted_mask_path(line_mask, density_proof=True)
    if fitted:
        return transformed([
            f'<path d="{fitted}" fill-rule="evenodd" '
            f'data-pcdc-text-geometry="court-proven-g1" {paint}/>'
        ])
    rows = []
    for glyph in glyphs:
        paths = [
            path for loop in (*glyph.positive_loops, *glyph.negative_loops)
            if (path := _loop_path(loop))
        ]
        if paths:
            rows.append(
                f'<path d="{" ".join(paths)}" fill-rule="evenodd" {paint}/>'
            )
    def delivery_is_topology_safe(fragments: list[str]) -> bool:
        if not fragments:
            return False
        proof_svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{reir.width}" '
            f'height="{reir.height}" viewBox="0 0 {reir.width} {reir.height}">'
            + "".join(fragments) + "</svg>"
        )
        rendered = render_svg_roundtrip(proof_svg, width=reir.width)[..., 3] >= 128
        intersection = int(np.sum(rendered & line_mask))
        union = int(np.sum(rendered | line_mask))
        return bool(
            topology_signature(rendered) == topology_signature(line_mask)
            and intersection / max(1, union) >= 0.82
        )

    if delivery_is_topology_safe(rows):
        return transformed(rows, glyph_fragments=True)
    # Pixel-centre contours collapse one-pixel stems and counters at native
    # resolution.  The run/contour serializer has an exact thin-feature
    # fallback; use it transactionally when the nominal dual loops fail their
    # own delivered-raster proof.
    faithful = _pixel_run_path(line_mask)
    fallback = ([
        f'<path d="{faithful}" fill-rule="evenodd" '
        f'data-pcdc-text-geometry="topology-safe-outline" {paint}/>'
    ] if faithful else [])
    return transformed(fallback) if delivery_is_topology_safe(fallback) else []


def text_delivery_svg_document(
    reir: RasterEvidenceIR, candidate: MacroCandidate,
    generated: TextMacroSet, *,
    source_roi: tuple[int, int, int, int] | None = None,
    include_background: bool = False,
) -> str | None:
    """Return the exact production text fragments in a review-safe document.

    With no ROI this is the canonical processing-coordinate document used for
    delivery proofs and digest binding.  ``source_roi`` only changes the outer
    viewport: the exact same fragments are scaled into oriented source-space,
    so a blind court cannot accidentally compare an independent retrace.
    """
    support = _candidate_support(reir, candidate)
    if not np.any(support):
        return None
    paint = _paint(_rgba(reir, support))
    rows = _text_elements(reir, candidate, paint, generated)
    if not rows:
        record = next((
            row for row in generated.records
            if row.candidate.id == _delivery_source_id(candidate)
        ), None)
        if record is not None and record.path in {
            "exact-font", "semantic-font-idealization",
        }:
            return None
        path = _mask_path(support)
        if not path:
            return None
        rows = [f'<path d="{path}" fill-rule="evenodd" {paint}/>']

    if source_roi is None:
        width, height = reir.width, reir.height
        view_box = f"0 0 {width} {height}"
        body = "".join(rows)
        background = ""
    else:
        source_width, source_height = reir.raster.transform.oriented_size
        sx = source_width / max(1, reir.width)
        sy = source_height / max(1, reir.height)
        x1, y1, x2, y2 = (int(value) for value in source_roi)
        width, height = max(1, x2 - x1), max(1, y2 - y1)
        view_box = f"{x1} {y1} {width} {height}"
        body = (
            f'<g transform="scale({sx:.12g} {sy:.12g})">'
            + "".join(rows) + "</g>"
        )
        background = ""
        if include_background:
            samples = reir.raster.straight_rgba[~support]
            if not len(samples):
                samples = reir.raster.straight_rgba.reshape((-1, 4))
            background = (
                f'<rect x="{x1}" y="{y1}" width="{width}" height="{height}" '
                f'{_paint(_rgba_from_samples(samples))}/>'
            )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="{view_box}" '
        f'shape-rendering="geometricPrecision">{background}{body}</svg>\n'
    )


def mask_review_svg_document(
    reir: RasterEvidenceIR, mask: np.ndarray, *,
    source_roi: tuple[int, int, int, int],
) -> str:
    """Serialize a certified mask without a second contour-fitting pipeline."""
    support = np.asarray(mask, bool)
    if support.shape != (reir.height, reir.width):
        raise ValueError("review mask shape does not match REIR")
    source_width, source_height = reir.raster.transform.oriented_size
    sx = source_width / max(1, reir.width)
    sy = source_height / max(1, reir.height)
    x1, y1, x2, y2 = (int(value) for value in source_roi)
    width, height = max(1, x2 - x1), max(1, y2 - y1)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        support.astype(np.uint8), 8,
    )
    rows: list[str] = []
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) <= 0:
            continue
        component = labels == label
        path = _pixel_run_path(component)
        if path:
            rows.append(
                f'<path d="{path}" fill-rule="evenodd" '
                f'{_paint(_rgba(reir, component))}/>'
            )
    px1 = max(0, int(math.floor(x1 / max(sx, 1e-12))))
    py1 = max(0, int(math.floor(y1 / max(sy, 1e-12))))
    px2 = min(reir.width, int(math.ceil(x2 / max(sx, 1e-12))))
    py2 = min(reir.height, int(math.ceil(y2 / max(sy, 1e-12))))
    local_support = support[py1:py2, px1:px2]
    local_rgba = reir.raster.straight_rgba[py1:py2, px1:px2]
    samples = local_rgba[~local_support]
    if not len(samples):
        samples = reir.raster.straight_rgba[~support]
    if not len(samples):
        samples = reir.raster.straight_rgba.reshape((-1, 4))
    background = _paint(_rgba_from_samples(samples))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="{x1} {y1} {width} {height}" '
        f'shape-rendering="geometricPrecision">'
        f'<rect x="{x1}" y="{y1}" width="{width}" height="{height}" '
        f'{background}/><g transform="scale({sx:.12g} {sy:.12g})">'
        + "".join(rows) + "</g></svg>\n"
    )


def render_text_delivery(
    reir: RasterEvidenceIR, candidate: MacroCandidate,
    generated: TextMacroSet, *, width: int | None = None,
) -> np.ndarray | None:
    """Render the exact text fragments that the production SVG will ship.

    ``width`` is normally the native raster width used by the production
    court.  A larger width is allowed for density-invariant evaluation of the
    *same SVG fragments*; it never changes candidate selection or proof.
    """
    document = text_delivery_svg_document(reir, candidate, generated)
    if document is None:
        return None
    return render_svg_roundtrip(
        document, width=reir.width if width is None else int(width),
    )


def _ordered_ids(
    scene: VisibleSceneIR, layered: LayeredScene | None,
) -> tuple[str, ...]:
    if layered is None:
        return scene.selected_macro_ids
    if layered.visible_scene.owner_by_leaf != scene.owner_by_leaf:
        raise ValueError("layered export belongs to another visible scene")
    layered.order_graph.validate()
    # The sparse DAG proves which analytic carriers must sit behind visible
    # occluders.  It does not license reordering all fallback/color cells:
    # doing so turns weak T-junction cues into paint-order changes between AA
    # bands.  Move certified hidden carriers to the back and preserve the
    # already validated visible order for every other owner.
    carriers = tuple(dict.fromkeys(
        row.source_macro_id for row in layered.hidden_completions
    ))
    carrier_set = set(carriers)
    return carriers + tuple(
        candidate_id for candidate_id in scene.selected_macro_ids
        if candidate_id not in carrier_set
    )


def _full_completion_masks(
    layered: LayeredScene | None,
) -> dict[str, np.ndarray]:
    rows: dict[str, np.ndarray] = {}
    if layered is None:
        return rows
    for completion in layered.hidden_completions:
        previous = rows.get(completion.source_macro_id)
        if previous is None:
            rows[completion.source_macro_id] = completion.full_mask
        elif not np.array_equal(previous, completion.full_mask):
            raise ValueError("one macro has inconsistent hidden completions")
    return rows


def _semantic_program_rows(
    program: DesignProgramIR,
    macro_rows: dict[str, list[str]],
    ordered_ids: tuple[str, ...],
) -> list[str]:
    """Serialize the reachable SVG XIR hierarchy around exact leaf markup."""
    program.validate()
    xir = adapt_export_ir(program, target="svg", mode="native")
    lookup = program.by_id()
    xir_lookup = {row.id: row for row in xir.nodes}
    root = lookup[program.root_id]
    emitted: set[str] = set()
    rows: list[str] = []

    def macro_group(macro_id: str) -> list[str]:
        fragments = macro_rows.get(macro_id, [])
        if not fragments or macro_id in emitted:
            return []
        emitted.add(macro_id)
        escaped = html.escape(macro_id, quote=True)
        return [
            f'<g data-pcdc-macro="{escaped}">', *fragments, "</g>",
        ]

    semantic_operators = {
        "Repeat", "Mirror", "RotationalGroup", "GlyphPrototypeMap",
        "Symbol", "Ring", "AnalyticArc", "RoundedRect", "CustomGlyph",
        "KnockoutText", "OutlinedTextGroup", "ShadowedTextGroup",
    }
    for node_id in root.children:
        node = lookup[node_id]
        macro_ids = tuple(dict.fromkeys(node.source_macro_ids))
        if node.operator in semantic_operators and macro_ids:
            payload = []
            for macro_id in macro_ids:
                payload.extend(macro_group(macro_id))
            if payload:
                operator = xir_lookup[node_id].operator
                rows.append(
                    '<g data-pcdc-xir="'
                    + html.escape(operator, quote=True)
                    + '" data-pcdc-program-node="'
                    + html.escape(node.id, quote=True) + '">'
                )
                rows.extend(payload); rows.append("</g>")
        else:
            for macro_id in macro_ids:
                rows.extend(macro_group(macro_id))
    for macro_id in ordered_ids:
        rows.extend(macro_group(macro_id))
    return rows


def scene_to_svg(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
    *, phase5_bundle: Phase5MacroBundle | None = None,
    text_macros: TextMacroSet | None = None,
    layered_scene: LayeredScene | None = None,
    design_program: DesignProgramIR | None = None,
) -> tuple[str, int, int]:
    reir.validate(); cmir.validate(); scene.validate(cmir)
    lookup = cmir.by_id()
    # A rejected transaction must reproduce the incumbent exactly.  Wrapping
    # a whole-scene V-ICE SVG in another canvas would duplicate its background
    # rectangle and inflate path complexity even if pixels happened to match.
    if len(scene.selected_macro_ids) == 1:
        only = lookup[scene.selected_macro_ids[0]]
        if only.program.operator == "LegacyBestScene":
            parameters = dict(only.program.parameters)
            payload, _group, count = _legacy_svg_document(
                str(parameters["svg_path"]), str(parameters["svg_sha256"]),
            )
            return payload, 0, max(1, count)
    border = np.concatenate((
        reir.raster.straight_rgba[0], reir.raster.straight_rgba[-1],
        reir.raster.straight_rgba[:, 0], reir.raster.straight_rgba[:, -1],
    ))
    background = np.clip(np.median(border, axis=0), 0.0, 1.0)
    bg = (
        int(round(float(background[0]) * 255)),
        int(round(float(background[1]) * 255)),
        int(round(float(background[2]) * 255)), float(background[3]),
    )
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{reir.width}" height="{reir.height}" viewBox="0 0 {reir.width} {reir.height}">',
        '<metadata>PCDC proof-carrying deterministic export; no embedded raster</metadata>',
        f'<rect width="{reir.width}" height="{reir.height}" {_paint(bg)}/>',
    ]
    native = fallback = 0
    completion_masks = _full_completion_masks(layered_scene)
    ordered_ids = _ordered_ids(scene, layered_scene)
    selected_typed = tuple(
        lookup[candidate_id] for candidate_id in ordered_ids
        if not lookup[candidate_id].is_base
    )
    legacy_underlay = next((
        candidate for candidate in cmir.candidates
        if candidate.program.operator == "LegacyBestScene"
        and candidate.id not in scene.selected_macro_ids
    ), None) if selected_typed else None
    if legacy_underlay is not None:
        parameters = dict(legacy_underlay.program.parameters)
        _payload, group, count = _legacy_svg_document(
            str(parameters["svg_path"]), str(parameters["svg_sha256"]),
        )
        rows.append(group); fallback += max(1, count)
        replacement = np.zeros((reir.height, reir.width), bool)
        for candidate in selected_typed:
            replacement |= _candidate_core_mask(reir, cmir, candidate)
        # Replacement ownership is a transactional cut in the incumbent, not
        # an aesthetic contour.  Pixel-centre contour serialization leaves
        # subpixel legacy slivers under the new macro and creates ghost holes;
        # the cell-union path clears exactly the pixels certified by court.
        erase = _pixel_run_path(replacement)
        if not erase:
            raise ValueError("typed legacy overlay has empty replacement ownership")
        rows.append(
            f'<path d="{erase}" fill-rule="evenodd" '
            f'data-pcdc-role="clear-incumbent-ownership" {_paint(bg)}/>'
        )
        fallback += 1
    if design_program is not None:
        if design_program.source_sha256 != cmir.source_sha256:
            raise ValueError("Design Program IR belongs to another source")
        if design_program.selected_macro_ids != scene.selected_macro_ids:
            raise ValueError("Design Program IR belongs to another selected scene")
    base_kinds = {
        MacroKind.ATOMIC_FALLBACK, MacroKind.HIERARCHY_REGION,
    }
    base_masks: dict[tuple[int, int, int, float], np.ndarray] = {}
    macro_rows: dict[str, list[str]] = {}
    if legacy_underlay is None:
        for candidate_id in ordered_ids:
            candidate = lookup[candidate_id]
            if candidate.kind not in base_kinds:
                continue
            for leaf_mask, leaf_color in _leaf_rows(reir, candidate):
                previous = base_masks.get(leaf_color)
                base_masks[leaf_color] = (
                    leaf_mask.copy() if previous is None else previous | leaf_mask
                )
    # All hierarchy/atomic owners share the same raster-derived paint plane.
    # Merge equal-colour subregions before contouring so internal hierarchy
    # cuts cannot become visible one-pixel seams in the SVG.
    for color, mask in sorted(base_masks.items(), key=lambda row: row[0]):
        path = _mask_path(mask)
        if path:
            rows.append(
                f'<path d="{path}" fill-rule="evenodd" {_paint(color)}/>'
            )
            fallback += 1

    for candidate_id in ordered_ids:
        candidate = lookup[candidate_id]
        if candidate.kind in base_kinds:
            continue
        if candidate.program.operator == "LegacyBestScene":
            parameters = dict(candidate.program.parameters)
            _payload, group, count = _legacy_svg_document(
                str(parameters["svg_path"]), str(parameters["svg_sha256"]),
            )
            macro_rows[candidate_id] = [group]
            fallback += max(1, count)
            continue
        support = _candidate_support(reir, candidate)
        if not np.any(support):
            continue
        color = _rgba(reir, support); paint = _paint(color)
        # A hidden analytic carrier may expand beyond visible ownership only
        # after Phase 6 has certified at least one front owner and a complete
        # back-to-front order.  Without that proof, export the visible support.
        allow_full_geometry = (
            candidate.hidden_geometry is None
            or candidate_id in completion_masks
        )
        if candidate.program.operator.startswith("Appearance/") and phase5_bundle is not None:
            appearance = next((
                row for row in phase5_bundle.appearances.records
                if row.candidate.id == _delivery_source_id(candidate)
            ), None)
            appearance_row = (
                _appearance_element(reir, appearance, candidate)
                if appearance is not None and allow_full_geometry else None
            )
            if appearance_row is not None:
                macro_rows[candidate_id] = [appearance_row]
                native += 1; continue
        if candidate.program.operator.startswith("CodecDetail/"):
            cleanup = next((
                row for row in (
                    () if phase5_bundle is None
                    else phase5_bundle.cleanup.records
                )
                if row.candidate.id == candidate.id
            ), None)
            codec_rows = (
                _codec_elements(reir, cleanup)
                if cleanup is not None else []
            )
            if not codec_rows:
                raise ValueError(
                    "selected codec counterfactual lacks proof-checked SVG delivery"
                )
            macro_rows[candidate_id] = codec_rows
            fallback += len(codec_rows); continue
        group_rows = (
            _group_elements(reir, candidate, phase5_bundle)
            if allow_full_geometry else []
        )
        if group_rows:
            macro_rows[candidate_id] = list(group_rows)
            native += len(group_rows); continue
        element = _native_element(candidate, paint, support) if allow_full_geometry else None
        if element is not None:
            macro_rows[candidate_id] = [element]
            native += 1; continue
        if candidate.kind is MacroKind.TEXT_LINE:
            text_rows = _text_elements(reir, candidate, paint, text_macros)
            if text_rows:
                macro_rows[candidate_id] = list(text_rows)
                native += len(text_rows); continue
            text_record = next((
                row for row in (() if text_macros is None else text_macros.records)
                if row.candidate.id == _delivery_source_id(candidate)
            ), None)
            if (
                text_record is not None
                and text_record.path in {
                    "exact-font", "semantic-font-idealization",
                }
            ):
                raise ValueError(
                    "selected font-outline text lacks proof-checked outlines"
                )
        if candidate.program.operator == "Shape/free_curve":
            element = _free_curve_element(reir, candidate, support)
            if element is None:
                raise ValueError(
                    "selected free-curve lacks proof-checked SVG delivery"
                )
            macro_rows[candidate_id] = [element]
            fallback += 1
            continue
        if candidate.kind is MacroKind.STROKE_NETWORK:
            strokes = _stroke_elements(candidate, color, phase5_bundle)
            if strokes:
                macro_rows[candidate_id] = list(strokes)
                native += len(strokes); continue
        # Hierarchy/legacy/fallback are editable groups of leaf paths.  A
        # hierarchy node is never flattened to one median colour.
        if candidate.kind is MacroKind.LEGACY_REGION:
            fragments = []
            for leaf_mask, leaf_color in _leaf_rows(reir, candidate):
                path = _mask_path(leaf_mask)
                if path:
                    fragments.append(
                        f'<path d="{path}" fill-rule="evenodd" {_paint(leaf_color)}/>'
                    )
                    fallback += 1
            if fragments:
                macro_rows[candidate_id] = fragments
            continue
        path = _mask_path(support)
        if path:
            macro_rows[candidate_id] = [
                f'<path d="{path}" fill-rule="evenodd" {paint}/>'
            ]
            fallback += 1
    if design_program is None:
        for candidate_id in ordered_ids:
            rows.extend(macro_rows.get(candidate_id, ()))
    else:
        rows.extend(_semantic_program_rows(
            design_program, macro_rows, ordered_ids,
        ))
    rows.append("</svg>")
    return "\n".join(rows), native, fallback


def _dxf_from_scene(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
    layered: LayeredScene | None = None,
) -> str:
    lookup = cmir.by_id(); rows = ["0", "SECTION", "2", "ENTITIES"]
    completion = _full_completion_masks(layered)
    for candidate_id in _ordered_ids(scene, layered):
        mask = completion.get(
            candidate_id, _candidate_support(reir, lookup[candidate_id])
        )
        contours, _hierarchy = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE,
        )
        for contour in contours:
            points = contour.reshape((-1, 2))
            if len(points) < 2:
                continue
            rows.extend(("0", "LWPOLYLINE", "8", "PCDC", "90", str(len(points)), "70", "1"))
            for x, y in points:
                rows.extend(("10", str(float(x)), "20", str(float(reir.height - y))))
    rows.extend(("0", "ENDSEC", "0", "EOF"))
    return "\n".join(rows) + "\n"


def _painted_masks(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
    layered: LayeredScene | None = None,
) -> Iterable[tuple[np.ndarray, tuple[int, int, int, float]]]:
    lookup = cmir.by_id()
    completion = _full_completion_masks(layered)
    for candidate_id in _ordered_ids(scene, layered):
        candidate = lookup[candidate_id]
        if candidate_id in completion:
            visible = _candidate_support(reir, candidate)
            yield completion[candidate_id], _rgba(reir, visible)
            continue
        if candidate.kind in {
            MacroKind.ATOMIC_FALLBACK, MacroKind.LEGACY_REGION,
            MacroKind.HIERARCHY_REGION,
        }:
            yield from _leaf_rows(reir, candidate)
        else:
            mask = _candidate_support(reir, candidate)
            if np.any(mask):
                yield mask, _rgba(reir, mask)


def _write_pdf(
    destination: Path, reir: RasterEvidenceIR,
    cmir: CandidateMacroIR, scene: VisibleSceneIR,
    layered: LayeredScene | None = None,
) -> None:
    from reportlab.pdfgen.canvas import Canvas

    canvas = Canvas(str(destination), pagesize=(reir.width, reir.height), pageCompression=1)
    for mask, (red, green, blue, alpha) in _painted_masks(
        reir, cmir, scene, layered
    ):
        # PDF 1.4 supports fill alpha, but old viewers may ignore it.  Geometry
        # stays vector either way.
        canvas.setFillColorRGB(red / 255.0, green / 255.0, blue / 255.0)
        try:
            canvas.setFillAlpha(alpha)
        except Exception:
            pass
        contours, _hierarchy = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE,
        )
        path = canvas.beginPath()
        used = False
        for contour in contours:
            points = contour.reshape((-1, 2))
            if len(points) < 3:
                continue
            path.moveTo(float(points[0, 0]), float(reir.height - points[0, 1]))
            for x, y in points[1:]:
                path.lineTo(float(x), float(reir.height - y))
            path.close(); used = True
        if used:
            canvas.drawPath(path, stroke=0, fill=1, fillMode=0)
    canvas.showPage(); canvas.save()


def _postscript_from_scene(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
    layered: LayeredScene | None = None,
) -> str:
    rows = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        f"%%BoundingBox: 0 0 {reir.width} {reir.height}",
        "%%LanguageLevel: 2", "1 setlinejoin 1 setlinecap",
    ]
    for mask, (red, green, blue, alpha) in _painted_masks(
        reir, cmir, scene, layered
    ):
        # EPS has no portable alpha.  Composite the fill over white while
        # retaining vector geometry.
        rgb = np.asarray((red, green, blue), np.float64) / 255.0
        rgb = alpha * rgb + (1.0 - alpha)
        rows.append(f"{rgb[0]:.8g} {rgb[1]:.8g} {rgb[2]:.8g} setrgbcolor")
        contours, _hierarchy = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE,
        )
        rows.append("newpath")
        for contour in contours:
            points = contour.reshape((-1, 2))
            if len(points) < 3:
                continue
            rows.append(f"{float(points[0,0]):.8g} {float(reir.height-points[0,1]):.8g} moveto")
            rows.extend(
                f"{float(x):.8g} {float(reir.height-y):.8g} lineto"
                for x, y in points[1:]
            )
            rows.append("closepath")
        rows.append("eofill")
    rows.extend(("showpage", "%%EOF"))
    return "\n".join(rows) + "\n"


def export_scene(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR, scene: VisibleSceneIR,
    path: str | Path, *, target: str | None = None,
    phase5_bundle: Phase5MacroBundle | None = None,
    text_macros: TextMacroSet | None = None,
    layered_scene: LayeredScene | None = None,
    design_program: DesignProgramIR | None = None,
) -> ExportArtifact:
    destination = Path(path); destination.parent.mkdir(parents=True, exist_ok=True)
    output_target = (target or destination.suffix.lstrip(".")).lower()
    if output_target not in {"svg", "png", "pdf", "eps", "dxf"}:
        raise ValueError("unsupported export target")
    svg, native, fallback = scene_to_svg(
        reir, cmir, scene, phase5_bundle=phase5_bundle,
        text_macros=text_macros, layered_scene=layered_scene,
        design_program=design_program,
    )
    if output_target == "svg":
        destination.write_text(svg, "utf-8")
    elif output_target == "png":
        import resvg_py
        destination.write_bytes(bytes(resvg_py.svg_to_bytes(
            svg_string=svg, width=reir.width,
        )))
    elif output_target == "pdf":
        _write_pdf(destination, reir, cmir, scene, layered_scene)
    elif output_target == "eps":
        destination.write_text(
            _postscript_from_scene(reir, cmir, scene, layered_scene), "ascii",
        )
    else:
        destination.write_text(
            _dxf_from_scene(reir, cmir, scene, layered_scene), "ascii"
        )
    total = max(1, native + fallback)
    artifact = ExportArtifact(
        target=output_target, path=str(destination.resolve()),
        sha256=_sha256(destination), bytes=destination.stat().st_size,
        native_primitives=native, fallback_paths=fallback,
        raster_images_embedded=len(re.findall(r"<image\b", svg)),
        editable_score=float((native + 0.55 * fallback) / total),
        provenance=(
            "selected-proof-carrying-scene", "deterministic-export",
            "no-preview-only-geometry-in-production",
            (
                "DPIR-XIR-semantic-groups"
                if design_program is not None else "direct-CMIR-scene"
            ),
        ),
    )
    if artifact.raster_images_embedded:
        raise RuntimeError("vector export embedded a raster image")
    return artifact


def render_svg_roundtrip(svg: str, *, width: int) -> np.ndarray:
    import resvg_py
    payload = resvg_py.svg_to_bytes(svg_string=svg, width=int(width))
    return np.asarray(Image.open(io.BytesIO(bytes(payload))).convert("RGBA"))


def render_svg_roundtrip_roi(
    svg: str, *, roi_xyxy: tuple[int, int, int, int],
) -> np.ndarray:
    """Render a native-coordinate crop of a deterministic SVG exactly.

    Continuous T3 verification reuses the one cached T2 full render and only
    rerenders the bounded region whose certified geometry changed.  Removing
    the generated document's outer root and installing a cropped viewBox keeps
    every primitive in its original coordinate system without rasterizing the
    unchanged scene a second time.
    """
    x1, y1, x2, y2 = (int(value) for value in roi_xyxy)
    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
        raise ValueError("invalid exact SVG ROI")
    opening = re.search(r"<svg\b[^>]*>", svg, flags=re.IGNORECASE)
    closing = svg.lower().rfind("</svg>")
    if opening is None or closing < opening.end():
        raise ValueError("invalid SVG document for exact ROI render")
    width = x2 - x1; height = y2 - y1
    cropped = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">'
        f'<g transform="translate({-x1} {-y1})">'
        + svg[opening.end():closing]
        + "</g></svg>"
    )
    rendered = render_svg_roundtrip(cropped, width=width)
    if rendered.shape != (height, width, 4):
        raise ValueError("exact SVG ROI render has the wrong shape")
    return rendered

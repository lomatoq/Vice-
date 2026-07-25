"""Foundational Experiment 4: real TextLine topology and runtime gate.

The experiment is deliberately source-only at selection time.  Frozen review
support is revealed only after both scenes have been solved.  ``legacy`` is
the reproducible pre-Phase-4 REIR text-token lane; ``candidate`` adds the new
TextLine columns while retaining every legacy column as a fail-open fallback.
The report also records an oracle ceiling, but oracle values never participate
in selection or in the pass/fail decision.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
import re
from pathlib import Path
import statistics
import time
from typing import Any, Iterable

import cv2
import numpy as np
from PIL import Image

from .build_identity import bind_report
from .svg_fragment_renderer import RENDERER_VERSION
from .vector_program import SERIALIZER_VERSION

from .certificates import mask_sha256
from .evidence_ir import EvidenceCache, RasterEvidenceIR
from .exact_font_provider import ReirExactFontProvider
from .experiment_inputs import (
    font_catalog_input_identity, real_locus_input_identity,
    trocr_model_input_identity,
)
from .export_writer import (
    mask_review_svg_document, render_text_delivery,
    text_delivery_svg_document,
)
from .experiment1_evidence_coverage import decode_support_rle
from .macro_extractor import extract_visible_scene
from .macro_ir import MacroCandidate, MacroKind
from .macro_registry import (
    build_base_registry, candidate_from_token, extend_registry,
)
from .glyph_prior import resolve_glyph_prior_checkpoint
from .wordmark_runtime import resolve_wordmark_prior_checkpoint
from .text_macros import (
    TextMacroRecord, generate_text_macros, materialize_font_free_geometry,
    enclosed_negative_loops, glyph_catastrophe_count,
    select_text_line_with_court,
)


PROJECT = Path(__file__).resolve().parents[1]
CORPUS = PROJECT / "datasets" / "pcdc_real_loci_v1"
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_experiment4" / "report.json"
REVIEW = PROJECT / "datasets" / "pcdc_textline_pairs_v1" / "review.json"
EXACT_REVIEW = PROJECT / "datasets" / "pcdc_textline_pairs_v2" / "review.json"


@dataclass(frozen=True)
class TextLineReviewArtifacts:
    """Exact alternatives produced by the same solve as Experiment 4."""

    source_roi: tuple[int, int, int, int]
    legacy_mask: np.ndarray
    candidate_mask: np.ndarray
    legacy_svg: str
    candidate_svg: str

    def validate(self, reir: RasterEvidenceIR) -> None:
        shape = (reir.height, reir.width)
        if self.legacy_mask.shape != shape or self.candidate_mask.shape != shape:
            raise ValueError("review masks do not match the solved REIR")
        if self.legacy_mask.flags.writeable or self.candidate_mask.flags.writeable:
            raise ValueError("review masks must be immutable")
        if not self.legacy_svg or not self.candidate_svg:
            raise ValueError("review SVG alternatives must be non-empty")


def _percentile(values: Iterable[float], percentile: float) -> float:
    rows = np.asarray(tuple(values), dtype=np.float64)
    return float(np.percentile(rows, percentile)) if len(rows) else float("nan")


def _fidelity_tail_metrics(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Expose low-IoU failures that topology and the mean can both hide."""
    rows = tuple(rows)
    legacy = sorted(float(row["legacy_iou"]) for row in rows)
    candidate = sorted(float(row["candidate_iou"]) for row in rows)
    tail_count = max(1, int(math.ceil(0.10 * len(rows))))
    regressions = [
        float(row["legacy_iou"]) - float(row["candidate_iou"])
        for row in rows
    ]
    metrics = {
        "legacy_min_iou": min(legacy, default=0.0),
        "candidate_min_iou": min(candidate, default=0.0),
        "legacy_cvar10_iou": statistics.fmean(legacy[:tail_count]),
        "candidate_cvar10_iou": statistics.fmean(candidate[:tail_count]),
        "max_iou_regression": max(regressions, default=0.0),
        "large_iou_regression_count": sum(delta > 0.05 for delta in regressions),
        "severe_low_iou_count": sum(value < 0.25 for value in candidate),
    }
    metrics["pixel_fidelity_gate"] = bool(
        metrics["candidate_min_iou"] >= 0.25
        and metrics["candidate_cvar10_iou"] + 1.0e-9
            >= metrics["legacy_cvar10_iou"]
        and metrics["large_iou_regression_count"] == 0
    )
    return metrics


def _glyph_prior_identity() -> dict[str, Any] | None:
    checkpoint = resolve_glyph_prior_checkpoint()
    if checkpoint is None:
        return None
    return {
        "path": str(checkpoint.resolve()),
        "sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "bytes": checkpoint.stat().st_size,
    }


def _wordmark_prior_identity() -> dict[str, Any] | None:
    checkpoint = resolve_wordmark_prior_checkpoint()
    if checkpoint is None:
        return None
    return {
        "path": str(checkpoint.resolve()),
        "sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "bytes": checkpoint.stat().st_size,
    }


def _materialization_identity() -> dict[str, Any]:
    """Bind the Materialization v2 route identity into the report (M2-10)."""
    return {
        "materialization_v2": os.environ.get(
            "VICE_TEXT_MATERIALIZATION_V2",
        ) == "1",
        "fair_geometry": os.environ.get("VICE_TEXT_FAIR_GEOMETRY", "1") == "1",
        "serializer_version": SERIALIZER_VERSION,
        "renderer_version": RENDERER_VERSION,
    }


def _delivered_materialization(svg: str | None) -> dict[str, Any]:
    """Read the delivered geometry family straight out of the fragment.

    The report must describe what was SHIPPED, not what was intended, so
    the family is parsed from the delivered SVG rather than assumed.
    """
    if not svg:
        return {"family": None, "span_commands": 0, "primitive_census": {}}
    families = sorted(set(re.findall(
        r'data-pcdc-text-geometry="([^"]+)"', svg,
    )))
    census = {
        "line": svg.count("L"), "cubic": svg.count("C"),
        "arc": svg.count("A"), "horizontal": svg.count("H"),
        "vertical": svg.count("V"),
    }
    return {
        "family": families[0] if len(families) == 1 else families or None,
        "families": families,
        "span_commands": int(sum(census.values())),
        "primitive_census": census,
    }


def _stage_d_identity() -> dict[str, Any]:
    """Bind the Stage-D upstream-lane model identity into the report.

    The 2026-07-25 cache/provenance audit found reports carrying glyph and
    wordmark prior identities but NO Stage-D checkpoint hash, so two runs
    with different VICE_STAGE_D_CHECKPOINT values were indistinguishable
    from the report alone.  Mirrors the resolution in
    text_macros._stage_d_support_refinements exactly.
    """
    enabled = os.environ.get("VICE_STAGE_D_UPSTREAM") == "1"
    identity: dict[str, Any] = {"upstream_enabled": enabled}
    for label, env_name, default_name in (
        ("checkpoint", "VICE_STAGE_D_CHECKPOINT",
         "stage_d_realft_from_lumbg.pt"),
        ("line_checkpoint", "VICE_STAGE_D_LINE_CHECKPOINT",
         "stage_d_line_realft_candidate.pt"),
    ):
        override = os.environ.get(env_name, "").strip()
        path = Path(override) if override else (
            PROJECT / "models" / default_name
        )
        identity[label] = (
            {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
            if enabled and path.is_file() else None
        )
    return identity


def _line_gcr_reduction(
    rows: Iterable[dict[str, Any]], baseline_key: str, candidate_key: str,
) -> tuple[int, int, float]:
    """Return catastrophic-line counts and their relative rate reduction."""
    rows = tuple(rows)
    baseline = sum(int(row[baseline_key]) > 0 for row in rows)
    candidate = sum(int(row[candidate_key]) > 0 for row in rows)
    reduction = (
        (baseline - candidate) / baseline
        if baseline > 0 else float(candidate == 0)
    )
    return baseline, candidate, float(reduction)


def _resize_mask(mask: np.ndarray, width: int, height: int) -> np.ndarray:
    if mask.shape == (height, width):
        return np.asarray(mask, bool)
    return cv2.resize(
        mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST,
    ) > 0


def _scaled_roi(
    roi: Iterable[int], source_size: tuple[int, int], target_size: tuple[int, int]
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = (int(value) for value in roi)
    sw, sh = source_size; tw, th = target_size
    if (sw, sh) != (tw, th):
        sx, sy = tw / max(1, sw), th / max(1, sh)
        x1, x2 = int(round(x1 * sx)), int(round(x2 * sx))
        y1, y2 = int(round(y1 * sy)), int(round(y2 * sy))
    return (
        max(0, min(tw, x1)), max(0, min(th, y1)),
        max(0, min(tw, x2)), max(0, min(th, y2)),
    )


def _roi_mask(
    shape: tuple[int, int], roi: tuple[int, int, int, int]
) -> np.ndarray:
    result = np.zeros(shape, bool)
    x1, y1, x2, y2 = roi
    if x2 > x1 and y2 > y1:
        result[y1:y2, x1:x2] = True
    return result


def _topology(mask: np.ndarray) -> tuple[int, int]:
    source = np.asarray(mask, np.uint8)
    components = int(cv2.connectedComponents(source, 8)[0] - 1)
    contours, hierarchy = cv2.findContours(
        source, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE,
    )
    holes = 0
    if hierarchy is not None:
        for index in range(len(contours)):
            depth = 0; parent = int(hierarchy[0, index, 3])
            while parent >= 0:
                depth += 1; parent = int(hierarchy[0, parent, 3])
            holes += int(depth % 2 == 1)
    return components, holes


def _catastrophes(reference: np.ndarray, candidate: np.ndarray) -> int:
    return glyph_catastrophe_count(reference, candidate)


def _iou(reference: np.ndarray, candidate: np.ndarray) -> float:
    intersection = int(np.sum(reference & candidate))
    union = int(np.sum(reference | candidate))
    return intersection / max(1, union)


def _exact_delivery_gcr_mask(
    reir: RasterEvidenceIR, decision: Any, generated: Any,
    *, target_shape: tuple[int, int], fallback_mask: np.ndarray,
) -> np.ndarray:
    """Render the selected production text SVG on the GCR lattice.

    Owned-SVG references are evaluated at >=512 px to avoid sampling-density
    topology loss.  Upscaling a native binary proxy with nearest-neighbour
    cannot reveal subpixel separation or counters carried by the delivered
    vector program.  This helper renders the exact writer fragments at the
    reference width and only uses a conservative nearest-neighbour mask for
    the explicitly preserved fallback portion.
    """
    height, width = (int(value) for value in target_shape)
    delivered = np.zeros((height, width), bool)
    selected_id = getattr(decision, "selected_id", None)
    if selected_id is not None:
        record = next((
            row for row in generated.records
            if row.candidate.id == selected_id
        ), None)
        if record is not None:
            try:
                rgba = render_text_delivery(
                    reir, record.candidate, generated, width=width,
                )
            except Exception:
                rgba = None
            if rgba is not None:
                alpha = np.asarray(rgba)[..., 3] >= 128
                delivered |= _resize_mask(alpha, width, height)
    preserved = getattr(decision, "preserved_fallback_mask", None)
    if preserved is not None:
        delivered |= _resize_mask(
            np.asarray(preserved, bool), width, height,
        )
    if not np.any(delivered):
        delivered = _resize_mask(
            np.asarray(fallback_mask, bool), width, height,
        )
    return np.ascontiguousarray(delivered, dtype=bool)


def _owned_svg_density_invariant_reference(
    locus: dict[str, Any], *, target_size: tuple[int, int],
    roi_xyxy: tuple[int, int, int, int],
) -> tuple[np.ndarray, np.ndarray] | None:
    """Render an owned aligned SVG on a topology-stable evaluation lattice.

    The native h24/h48 raster is still the IoU target and is never exposed to
    selection.  GCR, however, must not call an antialiased counter a missing
    hole merely because it vanished at one sampling density.  Ground-truth-
    derived rows have a recorded owned source/alignment proof, so render that
    source at >=512 px high and compare both delivered masks on this common
    lattice.  Evidence-reviewed rows retain their human topology mask.
    """
    source = Path(str(locus.get("source", {}).get("source_asset") or ""))
    if source.suffix.lower() != ".svg" or not source.is_file():
        return None
    try:
        import resvg_py
        native_width, native_height = target_size
        height = max(512, min(2048, int(native_height) * 8))
        payload = resvg_py.svg_to_bytes(
            svg_string=source.read_text("utf-8"), height=height,
        )
        rgba = np.asarray(
            Image.open(io.BytesIO(bytes(payload))).convert("RGBA"),
            np.float32,
        ) / 255.0
    except Exception:
        return None
    alpha = np.clip(rgba[..., 3:4], 0.0, 1.0)
    visible = rgba[..., :3] * alpha + (1.0 - alpha)
    border = np.concatenate((
        visible[0], visible[-1], visible[:, 0], visible[:, -1],
    ))
    background = np.median(border, axis=0)
    distance = np.max(np.abs(visible - background), axis=2)
    support = distance >= 0.10
    if not np.any(support) or float(np.mean(support)) > 0.90:
        return None
    high_height, high_width = support.shape
    high_roi = _scaled_roi(
        roi_xyxy, (native_width, native_height),
        (high_width, high_height),
    )
    high_scope = _roi_mask(support.shape, high_roi)
    support &= high_scope
    if not np.any(support):
        return None
    return np.ascontiguousarray(support, dtype=bool), high_scope


def _semantic_text_reference(
    support: np.ndarray, *, explicit_topology: bool,
    oklab: np.ndarray | None = None,
) -> tuple[np.ndarray, str]:
    """Normalize a reviewed dense knockout carrier to its glyph cutouts.

    Human locus review marks the visible text-bearing object.  For ordinary
    ink this is the glyph support; for knockout logos it can be the single
    dense carrier whose enclosed negative loops *are* the letters.  GCR must
    compare glyphs with glyphs, never a positive carrier with its complement.
    An explicit topology mask always wins over this deterministic inference.
    """
    source = np.asarray(support, bool)
    if explicit_topology or not np.any(source):
        return source, "reviewed-positive-support"
    components, holes = _topology(source)
    ys, xs = np.nonzero(source)
    density = float(np.mean(source[ys.min():ys.max() + 1, xs.min():xs.max() + 1]))
    if components != 1 or holes < 2 or density < 0.68:
        return source, "reviewed-positive-support"
    if oklab is not None:
        if oklab.shape[:2] != source.shape:
            raise ValueError("review support and colour evidence differ in size")
        pixels = np.asarray(oklab[source], np.float64)
        median = np.median(pixels, axis=0)
        colour_spread_p90 = float(np.quantile(
            np.linalg.norm(pixels - median, axis=1), 0.90,
        ))
        # A carrier is one appearance field with negative glyph loops.  If the
        # reviewed positive support already contains two strong colours (for
        # example red plate + black positive word), its holes are only glyph
        # counters and must not replace the reviewed support.
        if colour_spread_p90 > 0.06:
            return source, "reviewed-positive-support"
    negative = enclosed_negative_loops(source)
    negative_components, _negative_holes = _topology(negative)
    if negative_components < 2:
        return source, "reviewed-positive-support"
    return negative, "dense-knockout-carrier-negative-loops"


def _remove_canvas_edge_contamination(
    support: np.ndarray,
) -> tuple[np.ndarray, bool]:
    """Remove crop/container-edge fragments from a reviewed text support.

    Some ground-truth-derived problem-case ROIs contain a clean interior word
    plus antialiased pieces of a surrounding plate at the canvas edge.  Those
    pieces are not glyphs and made GCR reward reproducing crop artefacts.  The
    cleanup activates only when at least three large, interior components own
    >=94% of the reviewed ink and a separate small component touches the
    canvas.  Small punctuation inside the vertical text body is retained.
    """
    source = np.asarray(support, bool)
    if not np.any(source) or max(source.shape) < 256:
        return source, False
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        source.astype(np.uint8), 8,
    )
    if count <= 4:
        return source, False
    total = int(np.sum(source))
    anchor_floor = max(8, int(math.ceil(0.01 * total)))
    anchors = [
        label for label in range(1, count)
        if int(stats[label, cv2.CC_STAT_AREA]) >= anchor_floor
    ]
    if len(anchors) < 3:
        return source, False
    anchor_area = sum(int(stats[label, cv2.CC_STAT_AREA]) for label in anchors)
    if anchor_area / max(1, total) < 0.94:
        return source, False
    height, width = source.shape

    def touches_canvas(label: int) -> bool:
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        w = int(stats[label, cv2.CC_STAT_WIDTH])
        h = int(stats[label, cv2.CC_STAT_HEIGHT])
        return x <= 0 or y <= 0 or x + w >= width or y + h >= height

    # A cropped glyph can legitimately touch the canvas; in that case the
    # required interior-anchor premise is absent and review support wins.
    if any(touches_canvas(label) for label in anchors):
        return source, False
    nonanchors = [label for label in range(1, count) if label not in anchors]
    if not any(touches_canvas(label) for label in nonanchors):
        return source, False
    body_y1 = min(int(stats[label, cv2.CC_STAT_TOP]) for label in anchors)
    body_y2 = max(
        int(stats[label, cv2.CC_STAT_TOP] + stats[label, cv2.CC_STAT_HEIGHT])
        for label in anchors
    )
    result = np.zeros(source.shape, bool)
    for label in anchors:
        result |= labels == label
    for label in nonanchors:
        if touches_canvas(label):
            continue
        y = int(stats[label, cv2.CC_STAT_TOP])
        h = int(stats[label, cv2.CC_STAT_HEIGHT])
        overlap = max(0, min(y + h, body_y2) - max(y, body_y1))
        if overlap / max(1, h) >= 0.50:
            result |= labels == label
    if np.array_equal(result, source) or not np.any(result):
        return source, False
    return result, True


def _candidate_mask(candidate: MacroCandidate, shape: tuple[int, int]) -> np.ndarray:
    width, height = candidate.certificates.support_size
    count = width * height
    flat = np.zeros(count, bool)
    if candidate.certificates.support_bits:
        flat = np.unpackbits(
            np.frombuffer(candidate.certificates.support_bits, np.uint8),
            count=count, bitorder="little",
        ).astype(bool, copy=False)
    else:
        for start, length in candidate.certificates.support_rle:
            flat[start:start + length] = True
    return _resize_mask(flat.reshape((height, width)), shape[1], shape[0])


def _selected_text_mask(
    reir: RasterEvidenceIR, candidates: tuple[MacroCandidate, ...],
    *, time_budget_ms: float = 1000.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    base = build_base_registry(reir)
    cmir = extend_registry(reir, base, candidates)
    solution = extract_visible_scene(
        cmir, reir.hierarchy, exact_component_limit=18,
        time_budget_ms=time_budget_ms,
    )
    lookup = cmir.by_id()
    selected = tuple(
        lookup[candidate_id] for candidate_id in solution.selected_ids
        if lookup[candidate_id].kind is MacroKind.TEXT_LINE
    )
    result = np.zeros((reir.height, reir.width), bool)
    for candidate in selected:
        result |= _candidate_mask(candidate, result.shape)
    return result, {
        "feasible": bool(solution.feasible),
        "exact_cover": bool(solution.exact_cover),
        "selected_text_columns": len(selected),
        "selected_text_ids": [candidate.id for candidate in selected],
        "solve_ms": float(solution.solve_ms),
        "fallback_reason": solution.fallback_reason,
    }


def _legacy_candidates(reir: RasterEvidenceIR) -> tuple[MacroCandidate, ...]:
    rows = []
    for token in reir.proposal_tokens:
        if token.family != "text":
            continue
        candidate = candidate_from_token(reir, token)
        if candidate is not None:
            rows.append(candidate)
    return tuple(rows)


def _oracle_ceiling(
    records: tuple[TextMacroRecord, ...], reference_topology: np.ndarray,
    reference_support: np.ndarray, scope: np.ndarray,
    *, gcr_scope: np.ndarray | None = None,
) -> dict[str, Any]:
    rows = []
    for record in records:
        mask = _candidate_mask(record.candidate, reference_support.shape) & scope
        topology_mask = mask
        if mask.shape != reference_topology.shape:
            topology_mask = _resize_mask(
                mask, reference_topology.shape[1], reference_topology.shape[0],
            )
            if gcr_scope is not None:
                topology_mask &= gcr_scope
        rows.append((
            _catastrophes(reference_topology, topology_mask),
            -_iou(reference_support, mask),
            record.path, record.line_id,
        ))
    if not rows:
        return {"gcr": None, "iou": 0.0, "path": None, "line_id": None}
    gcr, negative_iou, path, line_id = min(rows)
    return {
        "gcr": int(gcr), "iou": float(-negative_iou),
        "path": path, "line_id": line_id,
    }


def evaluate_locus(
    locus: dict[str, Any], review: dict[str, Any], cache: EvidenceCache,
    *, exact_font: bool = False, template_lane: bool = False,
    stage_d_booster: bool = False,
    review_artifacts: list[TextLineReviewArtifacts] | None = None,
) -> dict[str, Any]:
    reir, cache_hit = cache.get_or_build(locus["source"]["path"])
    source_width, source_height = (int(value) for value in review["support_size"])
    reference_support = decode_support_rle(
        review["support_rle"], source_width, source_height,
    )
    reference_support = _resize_mask(
        reference_support, reir.width, reir.height,
    )
    explicit_topology = bool(review.get("topology_rle"))
    topology_runs = review.get("topology_rle") or review["support_rle"]
    reference_topology = decode_support_rle(
        topology_runs, source_width, source_height,
    )
    reference_topology = _resize_mask(
        reference_topology, reir.width, reir.height,
    )
    roi = _scaled_roi(
        review["roi_xyxy"], (source_width, source_height),
        (reir.width, reir.height),
    )
    scope = _roi_mask(reference_support.shape, roi)
    reference_support &= scope
    reference_topology &= scope
    raw_review_topology = _topology(reference_topology)
    reference_support, support_edge_cleaned = (
        _remove_canvas_edge_contamination(reference_support)
    )
    reference_topology, topology_edge_cleaned = (
        _remove_canvas_edge_contamination(reference_topology)
    )
    if not explicit_topology:
        reference_support, reference_semantics = _semantic_text_reference(
            reference_support, explicit_topology=False,
            oklab=reir.raster.oklab,
        )
        reference_topology = np.asarray(reference_support, bool).copy()
    else:
        reference_semantics = "explicit-reviewed-topology"
    if support_edge_cleaned or topology_edge_cleaned:
        reference_semantics += "+canvas-edge-contamination-removed"
    gcr_reference = reference_topology
    gcr_scope = scope
    if review.get("status") == "ground_truth_derived":
        idealized = _owned_svg_density_invariant_reference(
            locus, target_size=(reir.width, reir.height), roi_xyxy=roi,
        )
        if idealized is not None:
            gcr_reference, gcr_scope = idealized
            reference_semantics += "+owned-svg-density-invariant-topology"

    legacy = _legacy_candidates(reir)
    legacy_mask, legacy_solution = _selected_text_mask(reir, legacy)

    started = time.perf_counter()
    generated = generate_text_macros(
        reir, exact_font_provider=None, max_line_proposals=32,
        validate_reir=False,
    )
    generated_at = time.perf_counter()
    decision = select_text_line_with_court(
        reir, generated, legacy_support=legacy_mask, validate_reir=False,
    )
    court_at = time.perf_counter()
    candidate_mask = np.asarray(decision.support_mask, bool).copy()
    materialized_glyphs = 0
    materialized_loops = 0
    if decision.selected_id is not None and decision.selected_path in {
        "font-free-dual-loop", "conservative-outline",
    }:
        selected_record = next(
            record for record in generated.records
            if record.candidate.id == decision.selected_id
        )
        selected_line = next(
            line for line in generated.proposals
            if line.id == selected_record.line_id
        )
        candidate_mask, loops, _prototypes = materialize_font_free_geometry(
            reir, selected_line,
        )
        if decision.preserved_fallback_mask is not None:
            candidate_mask = (
                np.asarray(decision.preserved_fallback_mask, bool)
                | np.asarray(candidate_mask, bool)
            )
        materialized_glyphs = len(selected_line.glyphs)
        materialized_loops = sum(
            len(row.positive_loops) + len(row.negative_loops) for row in loops
        )
    materialized_at = time.perf_counter()
    warm_line_ms = (materialized_at - started) * 1000.0
    warm_candidate_mask = np.asarray(candidate_mask, bool).copy()
    warm_decision = decision
    warm_record = next((
        row for row in generated.records
        if row.candidate.id == warm_decision.selected_id
    ), None)
    oriented_size = reir.raster.transform.oriented_size
    review_source_roi = _scaled_roi(
        review["roi_xyxy"], (source_width, source_height), oriented_size,
    )
    legacy_review_svg = mask_review_svg_document(
        reir, legacy_mask, source_roi=review_source_roi,
    )
    candidate_review_svg = (
        text_delivery_svg_document(
            reir, warm_record.candidate, generated,
            source_roi=review_source_roi, include_background=True,
        )
        if warm_record is not None else None
    )
    if candidate_review_svg is None:
        candidate_review_svg = mask_review_svg_document(
            reir, warm_candidate_mask, source_roi=review_source_roi,
        )
    warm_candidate_svg_digest = hashlib.sha256(
        candidate_review_svg.encode("utf-8")
    ).hexdigest()
    legacy_svg_digest = hashlib.sha256(
        legacy_review_svg.encode("utf-8")
    ).hexdigest()
    pre_exact_mask_digest = mask_sha256(candidate_mask)

    # Exact-font retrieval is an optional anytime refinement.  T2 already has
    # a fully valid font-free/legacy scene; OCR and catalog search may improve
    # it later but cannot delay the <200 ms valid-line return.  Only strictly
    # admitted exact-font rows and independently physical OCR lines enter this
    # second court, so the valid T2 result exists before any Max refinement.
    exact_provider = None
    refinement_records: tuple[TextMacroRecord, ...] = ()
    optional_line_proposals = optional_text_columns = 0
    exact_attempted = exact_admitted = ocr_hint_count = 0
    exact_audits: list[dict[str, Any]] = []
    optional_court_steps: list[dict[str, Any]] = []
    optional_selected_ids: list[str] = []
    delivery_generated = generated
    if exact_font:
        exact_provider = ReirExactFontProvider(
            reir, max_fonts=2, top_k=1, refine_rounds=0,
            allow_upscale_ocr=True,
            # The calibrated 100-locus cascade admitted 0/172 catalog fits
            # while spending 61.8 s in retrieval.  Keep OCR/neural glyph
            # proposals, but do not price catalog fitting without a future
            # cheap font-identity certificate.
            enable_font_search=False,
        )
        if template_lane:
            # v9.5 bridge lane (audit S9): style retrieval buys bounded
            # affine fits that the exact lane's pricing wall never buys;
            # rows enter only through the unchanged admission walls.
            from .template_warp_provider import ApproximateTemplateProvider

            exact_provider = ApproximateTemplateProvider(
                reir, inner=exact_provider,
                stage_d_checkpoint=(
                    Path(os.environ.get(
                        "VICE_STAGE_D_CHECKPOINT",
                        PROJECT / "models" / "stage_d_full_candidate_v1.pt",
                    ))
                    if stage_d_booster else None
                ),
            )
        exact_generated = generate_text_macros(
            reir, exact_font_provider=exact_provider,
            max_line_proposals=32, validate_reir=False,
        )
        exact_attempted = exact_generated.exact_font_attempted
        exact_admitted = exact_generated.exact_font_admitted
        optional_line_proposals = len(exact_generated.proposals)
        optional_text_columns = len(exact_generated.records)
        ocr_hint_count = len(exact_provider.line_hints())
        exact_audits = [audit.__dict__ for audit in exact_provider.audits]
        optional_line_ids = {
            line.id for line in exact_generated.proposals
            if "OCR" in line.sources
        }
        optional_records = tuple(
            record for record in exact_generated.records
            if record.path == "exact-font" or record.line_id in optional_line_ids
        )
        refinement_records = optional_records
        if optional_records:
            # One logo can own several disjoint text rows.  Apply a bounded,
            # deterministic local court cascade: every accepted row rewrites
            # only its certified ownership ROI, all other pixels are carried
            # forward byte-for-byte, and all alternative programs for that
            # same line are removed before the next pass.
            remaining_records = list(optional_records)
            for _pass in range(min(8, len(optional_records))):
                exact_only = replace(
                    exact_generated, records=tuple(remaining_records),
                )
                exact_decision = select_text_line_with_court(
                    reir, exact_only, legacy_support=candidate_mask,
                    validate_reir=False,
                    # A complete-line rewrite is a transaction against the
                    # original warm owner.  After any local OCR rewrite the
                    # incumbent is already composite; reinterpreting that
                    # composite as a fresh complete line can erase the first
                    # accepted row (observed on STORMCRAFT + STUDIOS).
                    allow_complete_line_recovery=not optional_selected_ids,
                )
                if exact_decision.fallback_used:
                    break
                previous_digest = mask_sha256(candidate_mask)
                selected_record = next(
                    record for record in remaining_records
                    if record.candidate.id == exact_decision.selected_id
                )
                decision = exact_decision
                delivery_generated = exact_generated
                if exact_decision.selected_path in {
                    "font-free-dual-loop", "conservative-outline",
                }:
                    selected_line = next(
                        line for line in exact_generated.proposals
                        if line.id == selected_record.line_id
                    )
                    candidate_mask, loops, _prototypes = (
                        materialize_font_free_geometry(reir, selected_line)
                    )
                    if exact_decision.preserved_fallback_mask is not None:
                        candidate_mask = (
                            np.asarray(
                                exact_decision.preserved_fallback_mask, bool,
                            ) | np.asarray(candidate_mask, bool)
                        )
                    materialized_glyphs += len(selected_line.glyphs)
                    materialized_loops += sum(
                        len(row.positive_loops) + len(row.negative_loops)
                        for row in loops
                    )
                else:
                    candidate_mask = np.asarray(
                        exact_decision.support_mask, bool,
                    ).copy()
                optional_selected_ids.append(str(exact_decision.selected_id))
                optional_court_steps.append({
                    "selected_id": exact_decision.selected_id,
                    "line_id": selected_record.line_id,
                    "path": exact_decision.selected_path,
                    "reason": exact_decision.reason,
                    "selected_score": exact_decision.selected_score,
                    "fallback_score": exact_decision.fallback_score,
                })
                remaining_records = [
                    record for record in remaining_records
                    if record.line_id != selected_record.line_id
                ]
                if (
                    not remaining_records
                    or mask_sha256(candidate_mask) == previous_digest
                ):
                    break
    optional_at = time.perf_counter()
    exact_changed = mask_sha256(candidate_mask) != pre_exact_mask_digest
    candidate_solution = {
        "feasible": True,
        "exact_cover": bool(legacy_solution["exact_cover"]),
        "selected_text_columns": int(np.any(candidate_mask)),
        "selected_text_ids": (
            optional_selected_ids
            if optional_selected_ids else
            [decision.selected_id] if decision.selected_id is not None
            else legacy_solution["selected_text_ids"]
        ),
        "solve_ms": 0.0,
        "fallback_reason": None,
        "fallback_used": decision.fallback_used,
        "selected_path": decision.selected_path,
        "selected_score": decision.selected_score,
        "fallback_score": decision.fallback_score,
        "reason": decision.reason,
        "exact_candidates_evaluated": decision.exact_candidates_evaluated,
    }

    legacy_mask = np.asarray(legacy_mask, bool).copy() & scope
    warm_candidate_mask = np.asarray(warm_candidate_mask, bool).copy() & scope
    candidate_mask = np.asarray(candidate_mask, bool).copy() & scope
    # Bind the human court to the *final* result of this exact solve.  The old
    # report accidentally retained the warm SVG digest while recording the
    # post-OCR/exact mask digest, so one row could certify two different
    # candidates.  A local multi-line ownership cascade currently materialises
    # a composite support; serialize that exact composite rather than
    # pretending the last selected row is the whole delivered scene.
    final_record = next((
        row for row in delivery_generated.records
        if row.candidate.id == decision.selected_id
    ), None)
    final_candidate_review_svg = None
    if len(optional_selected_ids) <= 1 and decision.preserved_fallback_mask is None:
        final_candidate_review_svg = (
            text_delivery_svg_document(
                reir, final_record.candidate, delivery_generated,
                source_roi=review_source_roi, include_background=True,
            )
            if final_record is not None else None
        )
    if final_candidate_review_svg is None:
        final_candidate_review_svg = mask_review_svg_document(
            reir, candidate_mask, source_roi=review_source_roi,
        )
    candidate_svg_digest = hashlib.sha256(
        final_candidate_review_svg.encode("utf-8")
    ).hexdigest()
    if review_artifacts is not None:
        frozen_legacy = np.ascontiguousarray(legacy_mask, dtype=bool)
        frozen_candidate = np.ascontiguousarray(candidate_mask, dtype=bool)
        frozen_legacy.setflags(write=False)
        frozen_candidate.setflags(write=False)
        artifact = TextLineReviewArtifacts(
            source_roi=review_source_roi,
            legacy_mask=frozen_legacy,
            candidate_mask=frozen_candidate,
            legacy_svg=legacy_review_svg,
            candidate_svg=final_candidate_review_svg,
        )
        artifact.validate(reir)
        review_artifacts.append(artifact)
    legacy_gcr_mask = legacy_mask
    warm_gcr_mask = _exact_delivery_gcr_mask(
        reir, warm_decision, generated, target_shape=gcr_reference.shape,
        fallback_mask=warm_candidate_mask,
    ) & gcr_scope
    candidate_gcr_mask = _exact_delivery_gcr_mask(
        reir, decision, delivery_generated, target_shape=gcr_reference.shape,
        fallback_mask=candidate_mask,
    ) & gcr_scope
    if gcr_reference.shape != legacy_mask.shape:
        legacy_gcr_mask = _resize_mask(
            legacy_mask, gcr_reference.shape[1], gcr_reference.shape[0],
        ) & gcr_scope
    legacy_gcr = _catastrophes(gcr_reference, legacy_gcr_mask)
    warm_candidate_gcr = _catastrophes(gcr_reference, warm_gcr_mask)
    candidate_gcr = _catastrophes(gcr_reference, candidate_gcr_mask)
    return {
        "id": locus["id"],
        "category": locus["source"].get("category"),
        "review_status": review.get("status"),
        "cache_hit": bool(cache_hit),
        "processing_size": [reir.width, reir.height],
        "roi_xyxy": list(roi),
        "reference_topology": list(_topology(gcr_reference)),
        "native_reference_topology": list(_topology(reference_topology)),
        "raw_review_topology": list(raw_review_topology),
        "reference_semantics": reference_semantics,
        "review_topology_claim": [
            int(review["components"]), int(review["holes"]),
        ],
        "legacy_topology": list(_topology(legacy_mask)),
        "warm_candidate_topology": list(_topology(warm_candidate_mask)),
        "candidate_topology": list(_topology(candidate_mask)),
        # Component-level severity is retained for diagnosis, while the
        # experiment's primary GCR is a *line rate*: one line is catastrophic
        # when at least one persistent glyph component/counter is damaged.
        "legacy_gcr": int(legacy_gcr),
        "warm_candidate_gcr": int(warm_candidate_gcr),
        "candidate_gcr": int(candidate_gcr),
        "legacy_line_catastrophe": bool(legacy_gcr > 0),
        "warm_candidate_line_catastrophe": bool(warm_candidate_gcr > 0),
        "candidate_line_catastrophe": bool(candidate_gcr > 0),
        "not_worse": bool(candidate_gcr <= legacy_gcr),
        "warm_not_worse": bool(warm_candidate_gcr <= legacy_gcr),
        "legacy_iou": _iou(reference_support, legacy_mask),
        "warm_candidate_iou": _iou(reference_support, warm_candidate_mask),
        "candidate_iou": _iou(reference_support, candidate_mask),
        "gcr_evaluation": "exact-production-text-svg-at-reference-density/v1",
        "legacy_solution": legacy_solution,
        "candidate_solution": candidate_solution,
        "line_proposals": len(generated.proposals),
        "text_columns": len(generated.records) + len(refinement_records),
        "exact_font_attempted": exact_attempted,
        "exact_font_admitted": exact_admitted,
        "optional_line_proposals": optional_line_proposals,
        "optional_text_columns": optional_text_columns,
        "ocr_hint_count": ocr_hint_count,
        "exact_font_audits": exact_audits,
        "optional_court_steps": optional_court_steps,
        "exact_font_changed_output": exact_changed,
        "pre_exact_mask_digest": pre_exact_mask_digest,
        "legacy_mask_digest": mask_sha256(legacy_mask),
        "candidate_mask_digest": mask_sha256(candidate_mask),
        "warm_candidate_mask_digest": mask_sha256(warm_candidate_mask),
        "candidate_svg_digest": candidate_svg_digest,
        "delivered_materialization": _delivered_materialization(
            final_candidate_review_svg,
        ),
        "warm_candidate_svg_digest": warm_candidate_svg_digest,
        "legacy_svg_digest": legacy_svg_digest,
        "warm_line_ms": warm_line_ms,
        "optional_exact_ms": (optional_at - materialized_at) * 1000.0,
        "full_line_ms": (optional_at - started) * 1000.0,
        "generate_ms": (generated_at - started) * 1000.0,
        "court_ms": (court_at - generated_at) * 1000.0,
        "materialize_ms": (materialized_at - court_at) * 1000.0,
        "materialized_glyphs": materialized_glyphs,
        "materialized_loops": materialized_loops,
        "oracle_ceiling": _oracle_ceiling(
            generated.records + refinement_records,
            gcr_reference, reference_support, scope, gcr_scope=gcr_scope,
        ),
    }


def _human_status(
    path: Path = REVIEW, *, rows: Iterable[dict[str, Any]] = (),
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Return only reviews tied to the exact rendered alternatives.

    A blind choice is evidence about two particular SVGs, not about a locus
    name forever.  Earlier reports reused answers after candidate output had
    changed, which could make a new algorithm inherit an unrelated human
    pass.  The private manifest therefore carries both mask digests and every
    answer is admitted only while those digests still match this run.
    """
    if not path.is_file():
        return {
            "required": 0, "reviewed": 0, "candidate_preferred": 0,
            "preference_rate": None, "gate_pass": False, "stale": 0,
            "digest_validated": False, "review_sha256": None,
            "manifest_sha256": None,
        }
    payload = json.loads(path.read_text("utf-8"))
    answers = payload.get("answers", {})
    current = {str(row["id"]): row for row in rows}
    manifest_file = manifest_path or path.with_name("human_manifest.json")
    cases: dict[str, dict[str, Any]] = {}
    if manifest_file.is_file():
        manifest = json.loads(manifest_file.read_text("utf-8"))
        cases = {str(row["id"]): row for row in manifest.get("cases", [])}
    digest_contract = bool(cases) and all(
        case.get("candidate_mask_digest") and case.get("legacy_mask_digest")
        and case.get("candidate_svg_digest") and case.get("legacy_svg_digest")
        for case in cases.values()
    )
    valid = []
    stale = 0
    for locus_id, answer in answers.items():
        if answer.get("choice") not in {"legacy", "candidate", "tie"}:
            continue
        row = current.get(str(locus_id))
        case = cases.get(str(locus_id))
        digest_match = bool(
            digest_contract and row is not None and case is not None
            and case.get("candidate_mask_digest")
            == row.get("candidate_mask_digest")
            and case.get("legacy_mask_digest") == row.get("legacy_mask_digest")
            and case.get("candidate_svg_digest") == row.get("candidate_svg_digest")
            and case.get("legacy_svg_digest") == row.get("legacy_svg_digest")
            and answer.get("candidate_side") == case.get("candidate_side")
            and answer.get("candidate_mask_digest")
            == case.get("candidate_mask_digest")
            and answer.get("legacy_mask_digest") == case.get("legacy_mask_digest")
            and answer.get("candidate_svg_digest") == case.get("candidate_svg_digest")
            and answer.get("legacy_svg_digest") == case.get("legacy_svg_digest")
        )
        if digest_match:
            valid.append(answer)
        else:
            stale += 1
    preferred = sum(row.get("choice") == "candidate" for row in valid)
    decisive = sum(row.get("choice") in {"legacy", "candidate"} for row in valid)
    required = int(payload.get("required", len(answers)))
    rate = preferred / max(1, decisive)
    return {
        "required": required, "reviewed": len(valid),
        "candidate_preferred": preferred, "decisive": decisive,
        "preference_rate": rate if decisive else None,
        "gate_pass": bool(len(valid) >= required > 0 and rate >= 0.75),
        "stale": stale, "digest_validated": digest_contract,
        "review_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "manifest_sha256": (
            hashlib.sha256(manifest_file.read_bytes()).hexdigest()
            if manifest_file.is_file() else None
        ),
    }


def build_report(
    corpus_dir: Path = CORPUS, *, exact_font: bool = True,
    template_lane: bool = False, stage_d_booster: bool = False,
) -> dict[str, Any]:
    input_identity = real_locus_input_identity(corpus_dir)
    font_catalog_identity = font_catalog_input_identity() if exact_font else None
    ocr_model_identity = trocr_model_input_identity() if exact_font else None
    manifest = json.loads((corpus_dir / "manifest.json").read_text("utf-8"))
    reviews = json.loads((corpus_dir / "review.json").read_text("utf-8"))["reviews"]
    loci = [row for row in manifest["loci"] if row["semantic_class"] == "text"]
    admitted = [
        row for row in loci
        if row["id"] in reviews and reviews[row["id"]].get("status") in {
            "ground_truth_derived", "evidence_reviewed", "complete",
        }
    ]
    if not 100 <= len(admitted) <= 200:
        return {
            "schema": "pcdc-experiment4-textline/v3",
            "input_identity": input_identity,
            "font_catalog_identity": font_catalog_identity,
            "ocr_model_identity": ocr_model_identity,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "blocked_invalid_dataset_size", "gate_pass": False,
            "required_range": [100, 200], "observed": len(admitted), "rows": [],
        }
    cache = EvidenceCache()
    rows = [
        evaluate_locus(
            row, reviews[row["id"]], cache, exact_font=exact_font,
            template_lane=template_lane, stage_d_booster=stage_d_booster,
        )
        for row in admitted
    ]
    legacy_gcr = sum(row["legacy_gcr"] for row in rows)
    warm_candidate_gcr = sum(row["warm_candidate_gcr"] for row in rows)
    candidate_gcr = sum(row["candidate_gcr"] for row in rows)
    legacy_catastrophic_lines, warm_catastrophic_lines, warm_reduction = (
        _line_gcr_reduction(rows, "legacy_gcr", "warm_candidate_gcr")
    )
    _legacy_again, candidate_catastrophic_lines, reduction = (
        _line_gcr_reduction(rows, "legacy_gcr", "candidate_gcr")
    )
    warm_severity_reduction = (
        (legacy_gcr - warm_candidate_gcr) / legacy_gcr if legacy_gcr > 0
        else float(warm_candidate_gcr == 0)
    )
    severity_reduction = (
        (legacy_gcr - candidate_gcr) / legacy_gcr if legacy_gcr > 0
        else float(candidate_gcr == 0)
    )
    p95 = _percentile((row["warm_line_ms"] for row in rows), 95)
    machine = {
        "dataset_size": len(rows),
        "legacy_glyph_catastrophes": legacy_gcr,
        "warm_candidate_glyph_catastrophes": warm_candidate_gcr,
        "legacy_catastrophic_lines": legacy_catastrophic_lines,
        "warm_candidate_catastrophic_lines": warm_catastrophic_lines,
        "candidate_catastrophic_lines": candidate_catastrophic_lines,
        "legacy_gcr_rate": legacy_catastrophic_lines / len(rows),
        "warm_candidate_gcr_rate": warm_catastrophic_lines / len(rows),
        "candidate_gcr_rate": candidate_catastrophic_lines / len(rows),
        "warm_gcr_reduction": warm_reduction,
        "warm_component_severity_reduction": warm_severity_reduction,
        "candidate_glyph_catastrophes": candidate_gcr,
        "gcr_reduction": reduction,
        "component_severity_reduction": severity_reduction,
        "warm_not_worse_count": sum(row["warm_not_worse"] for row in rows),
        "all_warm_lines_not_worse": all(
            row["warm_not_worse"] for row in rows
        ),
        "not_worse_count": sum(row["not_worse"] for row in rows),
        "all_reviewed_lines_not_worse": all(row["not_worse"] for row in rows),
        "legacy_mean_iou": statistics.fmean(row["legacy_iou"] for row in rows),
        "warm_candidate_mean_iou": statistics.fmean(
            row["warm_candidate_iou"] for row in rows
        ),
        "candidate_mean_iou": statistics.fmean(row["candidate_iou"] for row in rows),
        "warm_p50_ms_per_line": _percentile(
            (row["warm_line_ms"] for row in rows), 50,
        ),
        "warm_p95_ms_per_line": p95,
        "fallback_feasible": all(
            row["candidate_solution"]["feasible"] for row in rows
        ),
        "exact_font_attempted": sum(
            row["exact_font_attempted"] for row in rows
        ),
        "exact_font_admitted": sum(
            row["exact_font_admitted"] for row in rows
        ),
        "rows_with_ocr": sum(row["ocr_hint_count"] > 0 for row in rows),
        "exact_font_changed_rows": sum(
            row["exact_font_changed_output"] for row in rows
        ),
        "optional_exact_p95_ms_per_line": _percentile(
            (row["optional_exact_ms"] for row in rows), 95,
        ),
        "full_p95_ms_per_line": _percentile(
            (row["full_line_ms"] for row in rows), 95,
        ),
    }
    machine.update(_fidelity_tail_metrics(rows))
    machine["gate_pass"] = bool(
        reduction >= 0.70
        and machine["all_reviewed_lines_not_worse"]
        and machine["pixel_fidelity_gate"]
        and machine["candidate_mean_iou"] + 1.0e-9
            >= machine["legacy_mean_iou"]
        and p95 < 200.0 and machine["fallback_feasible"]
    )
    glyph_prior_checkpoint = _glyph_prior_identity()
    wordmark_prior_checkpoint = _wordmark_prior_identity()
    reuse_font_free_court = bool(
        exact_font and machine["exact_font_changed_rows"] == 0
        and glyph_prior_checkpoint is None
        and wordmark_prior_checkpoint is None
    )
    human_path = (
        REVIEW if not exact_font or reuse_font_free_court else EXACT_REVIEW
    )
    human = _human_status(human_path, rows=rows)
    human["review_source"] = str(human_path)
    human["reused_from_font_free_court"] = reuse_font_free_court
    gate = bool(machine["gate_pass"] and human["gate_pass"])
    return {
        "schema": "pcdc-experiment4-textline/v3",
        "input_identity": input_identity,
        "font_catalog_identity": font_catalog_identity,
        "ocr_model_identity": ocr_model_identity,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "passed" if gate else
            "blocked_pending_human_preference" if machine["gate_pass"] else
            "machine_gate_failed"
        ),
        "selection_blinding": (
            "legacy and candidate solved from REIR only; frozen support revealed "
            "after both selections; oracle ceiling excluded from selection/gate; "
            "optional exact-font refinement runs only after a valid T2 return"
        ),
        "legacy_definition": "pre-Phase-4 REIR text-token CMIR lane",
        "candidate_definition": (
            "legacy fail-open plus Phase-4 TextLine CMIR columns with bounded "
            "OCR/exact-font lane"
            if exact_font else
            "legacy fail-open plus Phase-4 font-free TextLine CMIR columns"
        ),
        "exact_font_mode": (
            "approximate-template-top8" if exact_font and template_lane
            else "fast-catalog-2" if exact_font else "disabled"
        ),
        "glyph_prior_checkpoint": glyph_prior_checkpoint,
        "wordmark_prior_checkpoint": wordmark_prior_checkpoint,
        "stage_d_identity": _stage_d_identity(),
        "materialization_identity": _materialization_identity(),
        "machine": machine, "human": human, "gate_pass": gate, "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--font-free-only", action="store_true")
    parser.add_argument("--approximate-template", action="store_true")
    parser.add_argument("--stage-d-booster", action="store_true")
    parser.add_argument("--stage-d-upstream", action="store_true")
    args = parser.parse_args()
    if args.stage_d_upstream:
        # Upstream recovery lives at proposal birth (text_macros reads the
        # env), so it needs no provider threading; default checkpoint is the
        # real-domain fine-tune, overridable via VICE_STAGE_D_CHECKPOINT.
        os.environ["VICE_STAGE_D_UPSTREAM"] = "1"
    report = bind_report(
        build_report(
            exact_font=not args.font_free_only,
            template_lane=args.approximate_template,
            stage_d_booster=args.stage_d_booster,
        ),
        evaluator_source=__file__,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8",
    )
    print(json.dumps({
        "status": report["status"], "machine": report.get("machine"),
        "human": report.get("human"), "gate_pass": report["gate_pass"],
        "path": str(args.out),
    }, ensure_ascii=False, indent=2))
    return int(not report.get("machine", {}).get("gate_pass", False))


if __name__ == "__main__":
    raise SystemExit(main())

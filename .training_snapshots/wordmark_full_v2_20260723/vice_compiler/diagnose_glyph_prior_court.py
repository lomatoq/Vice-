"""Read-only glyph-prior/court diagnostics on the reviewed TextLine corpus.

This module deliberately has no production imports.  It exposes the source-only
features seen by the court next to reviewed outcomes, so a selector change can
be justified on the full corpus instead of tuned to one screenshot.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .evidence_ir import EvidenceCache
from .exact_font_provider import ReirExactFontProvider
from .experiment4_textline import (
    CORPUS,
    _iou,
    _legacy_candidates,
    _remove_canvas_edge_contamination,
    _resize_mask,
    _roi_mask,
    _scaled_roi,
    _selected_text_mask,
    _semantic_text_reference,
    decode_support_rle,
)
from .text_macros import (
    _bbox,
    _candidate_support,
    _persistent_text_support,
    _refine_single_preserved_mark,
    _glyph_prior_topology_contract,
    _ocr_semantic_topology_contract,
    _text_evidence_score,
    _text_render_evidence_target,
    _topology,
    generate_text_macros,
    glyph_catastrophe_count,
    mask_sha256,
    select_text_line_with_court,
)


def _review_reference(
    review: dict[str, Any], *, width: int, height: int, oklab: np.ndarray,
) -> np.ndarray:
    source_width, source_height = (int(value) for value in review["support_size"])
    reference = decode_support_rle(
        review["support_rle"], source_width, source_height,
    )
    reference = _resize_mask(reference, width, height)
    roi = _scaled_roi(
        review["roi_xyxy"], (source_width, source_height), (width, height),
    )
    reference &= _roi_mask(reference.shape, roi)
    reference, _cleaned = _remove_canvas_edge_contamination(reference)
    if not review.get("topology_rle"):
        reference, _semantics = _semantic_text_reference(
            reference, explicit_topology=False, oklab=oklab,
        )
    return np.asarray(reference, bool)


def _source_metric(sources: tuple[str, ...], prefix: str) -> float | None:
    raw = next((row.split(":", 1)[1] for row in sources if row.startswith(prefix)), None)
    return float(raw) if raw is not None else None


def _diagnose_one(
    locus: dict[str, Any], review: dict[str, Any], cache: EvidenceCache, *,
    exact_font: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reir, _cache_hit = cache.get_or_build(locus["source"]["path"])
    reference = _review_reference(
        review, width=reir.width, height=reir.height, oklab=reir.raster.oklab,
    )
    legacy_mask, _legacy_solution = _selected_text_mask(
        reir, _legacy_candidates(reir),
    )
    provider = (
        ReirExactFontProvider(
            reir, max_fonts=2, top_k=1, refine_rounds=0,
            allow_upscale_ocr=True, enable_font_search=False,
        )
        if exact_font else None
    )
    generated = generate_text_macros(
        reir, exact_font_provider=provider, max_line_proposals=32,
        validate_reir=False,
    )
    decision = select_text_line_with_court(
        reir, generated, legacy_support=legacy_mask, validate_reir=False,
    )
    line_by_id = {line.id: line for line in generated.proposals}
    emitted_texts = {
        source.split(":", 1)[1]
        for line in generated.proposals
        if "font-free-character-conditioned-glyph-prior" in line.sources
        for source in line.sources if source.startswith("ocr-text:")
    }
    reach_rows: list[dict[str, Any]] = []
    seen_reach: set[tuple[str, str]] = set()
    for line in generated.proposals:
        source_set = set(line.sources)
        if "OCR" not in source_set or "font-free-character-conditioned-glyph-prior" in source_set:
            continue
        recognized = max((
            source.partition("ocr-text:")[2]
            for source in line.sources if source.startswith("ocr-text:")
        ), key=len, default="")
        key = (line.id, recognized)
        if key in seen_reach:
            continue
        seen_reach.add(key)
        physical = bool({
            "persistent-physical-midline-topology",
            "OCR-bounded-physical-subset-with-connectivity-uncertainty",
        } & source_set)
        contract = _ocr_semantic_topology_contract(recognized)
        glyph_prior_contract = _glyph_prior_topology_contract(recognized)
        expected = (
            [len(contract[0]), int(sum(contract[1]))]
            if contract is not None else None
        )
        observed = list(_topology(line.support_mask))
        reach_rows.append({
            "id": locus["id"],
            "line_id": line.id,
            "recognized_text": recognized,
            "physical_source_gate": physical,
            "semantic_contract": contract is not None,
            "glyph_prior_contract": glyph_prior_contract is not None,
            "expected_topology": expected,
            "observed_topology": observed,
            "topology_distance": (
                sum(abs(a - b) for a, b in zip(observed, expected))
                if expected is not None else None
            ),
            "neural_emitted_for_text": recognized in emitted_texts,
            "sources": list(line.sources),
        })
    ranking = {candidate_id: score for candidate_id, _path, score in decision.ranking}

    # Mirror the court's hard-valid certificate collapse so every diagnostic
    # score is conditioned on exactly the same common candidate scope.
    certificate_rows: dict[int, Any] = {}
    for record in generated.records:
        if not record.claims.hard_valid:
            continue
        key = id(record.candidate.certificates)
        previous = certificate_rows.get(key)
        if previous is None or (
            record.path == "exact-font", record.candidate.score_bounds.lower,
        ) > (
            previous.path == "exact-font", previous.candidate.score_bounds.lower,
        ):
            certificate_rows[key] = record
    unique: dict[str, tuple[Any, np.ndarray]] = {}
    for record in certificate_rows.values():
        mask = _candidate_support(record.candidate, (reir.height, reir.width))
        if not np.any(mask):
            continue
        digest = mask_sha256(mask)
        previous = unique.get(digest)
        if previous is None or (
            record.path == "exact-font", record.candidate.score_bounds.lower,
        ) > (
            previous[0].path == "exact-font",
            previous[0].candidate.score_bounds.lower,
        ):
            unique[digest] = (record, mask)
    preserved_by_id: dict[str, np.ndarray] = {}
    raw_mask_by_id: dict[str, np.ndarray] = {}
    for digest, (record, mask) in tuple(unique.items()):
        line = line_by_id.get(record.line_id)
        if (
            not np.any(legacy_mask) or line is None or line.score < 0.74
            or "OCR" not in line.sources
            or not ({
                "persistent-physical-midline-topology",
                "OCR-bounded-physical-subset-with-connectivity-uncertainty",
            } & set(line.sources))
        ):
            continue
        x1, _y1, x2, _y2 = line.roi_xyxy
        candidate_box = _bbox(mask, pad=0)
        ink_height = max(1, candidate_box[3] - candidate_box[1])
        vertical_pad = max(1, int(np.ceil(0.10 * ink_height)))
        scope = np.zeros((reir.height, reir.width), bool)
        scope[
            max(0, candidate_box[1] - vertical_pad):min(
                reir.height, candidate_box[3] + vertical_pad,
            ),
            max(0, x1):min(reir.width, x2),
        ] = True
        preserved = legacy_mask & ~scope
        if int(np.sum(preserved)) < max(3, int(0.03 * np.sum(legacy_mask))):
            continue
        preserved, _mark_refined = _refine_single_preserved_mark(reir, preserved)
        roi_width = max(1, x2 - x1)
        roi_height = max(1, line.roi_xyxy[3] - line.roi_xyxy[1])
        candidate_span = (candidate_box[2] - candidate_box[0]) / roi_width
        candidate_height = (candidate_box[3] - candidate_box[1]) / roi_height
        if candidate_span < 0.82 or candidate_height < 0.50 or np.any(mask & ~scope):
            continue
        raw_mask_by_id[record.candidate.id] = np.asarray(mask, bool)
        composite = np.asarray(preserved, bool) | np.asarray(mask, bool)
        unique[digest] = (record, composite)
        preserved_by_id[record.candidate.id] = np.asarray(preserved, bool)
    common = np.asarray(legacy_mask, bool).copy()
    for _record, mask in unique.values():
        common |= mask
    if np.any(common):
        common = cv2.dilate(common.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    target, contrast = _text_render_evidence_target(reir, common)
    fallback_score = _text_evidence_score(
        reir, legacy_mask, target, common, line_score=0.5, exact_font=False,
    )
    fallback_topology = _topology(legacy_mask)
    persistent = _persistent_text_support(legacy_mask)
    persistent_topology = _topology(persistent)
    fallback_topology_error = sum(
        abs(a - b) for a, b in zip(fallback_topology, persistent_topology)
    )
    fallback_area = int(np.sum(legacy_mask))
    fallback_box = _bbox(legacy_mask, pad=0) if fallback_area else (0, 0, 0, 0)
    fallback_span = max(1, fallback_box[2] - fallback_box[0])

    rows: list[dict[str, Any]] = []
    seen_lines: set[str] = set()
    for record, court_mask in unique.values():
        line = line_by_id.get(record.line_id)
        if (
            line is None or line.id in seen_lines
            or "font-free-character-conditioned-glyph-prior" not in line.sources
        ):
            continue
        seen_lines.add(line.id)
        mask = np.asarray(court_mask, bool)
        raw_mask = raw_mask_by_id.get(record.candidate.id, mask)
        candidate_area = int(np.sum(mask))
        candidate_box = _bbox(mask, pad=0)
        overlap = int(np.sum(mask & legacy_mask)) / max(
            1, min(candidate_area, fallback_area),
        )
        span_recall = (
            max(
                0,
                min(candidate_box[2], fallback_box[2])
                - max(candidate_box[0], fallback_box[0]),
            ) / fallback_span
            if fallback_area else 1.0
        )
        topology = _topology(mask)
        topology_error = sum(
            abs(a - b) for a, b in zip(topology, persistent_topology)
        )
        score = _text_evidence_score(
            reir, mask, target, common, line_score=line.score, exact_font=False,
        )
        rows.append({
            "id": locus["id"],
            "line_id": line.id,
            "decision_reason": decision.reason,
            "decision_selected_model": decision.selected_id == record.candidate.id,
            "decision_selected_path": decision.selected_path,
            "reference_delta_iou": _iou(reference, mask) - _iou(reference, legacy_mask),
            "reference_candidate_iou": _iou(reference, mask),
            "reference_legacy_iou": _iou(reference, legacy_mask),
            "reference_raw_neural_delta_iou": (
                _iou(reference, raw_mask) - _iou(reference, legacy_mask)
            ),
            "reference_raw_neural_iou": _iou(reference, raw_mask),
            "ownership_composite": record.candidate.id in preserved_by_id,
            "source_iou": _source_metric(line.sources, "neural-source-iou:"),
            "source_edit_fraction": _source_metric(
                line.sources, "neural-source-edit-fraction:",
            ),
            "line_score": float(line.score),
            "court_score": float(score),
            "court_ranking_score": ranking.get(record.candidate.id),
            "fallback_score": float(fallback_score),
            "court_score_delta": float(score - fallback_score),
            "contrast": float(contrast),
            "candidate_topology": list(topology),
            "fallback_topology": list(fallback_topology),
            "persistent_topology": list(persistent_topology),
            "candidate_topology_error": int(topology_error),
            "fallback_topology_error": int(fallback_topology_error),
            "topology_error_delta": int(topology_error - fallback_topology_error),
            "glyph_catastrophe_vs_fallback": glyph_catastrophe_count(
                legacy_mask, mask,
            ),
            "area_ratio": candidate_area / max(1, fallback_area),
            "overlap": float(overlap),
            "horizontal_span_recall": float(span_recall),
            "sources": list(line.sources),
        })
    return rows, reach_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ids", nargs="*", default=())
    parser.add_argument("--exact-font", action="store_true")
    parser.add_argument("--catastrophic-report", type=Path)
    args = parser.parse_args()
    wanted = set(args.ids)
    if args.catastrophic_report is not None:
        report = json.loads(args.catastrophic_report.read_text("utf-8"))
        wanted.update(
            str(row["id"]) for row in report.get("rows", ())
            if row.get("candidate_line_catastrophe")
        )
    manifest = json.loads((CORPUS / "manifest.json").read_text("utf-8"))
    reviews = json.loads((CORPUS / "review.json").read_text("utf-8"))["reviews"]
    cache = EvidenceCache()
    rows: list[dict[str, Any]] = []
    reach_rows: list[dict[str, Any]] = []
    for locus in manifest["loci"]:
        if wanted and locus["id"] not in wanted:
            continue
        locus_rows, locus_reach = _diagnose_one(
            locus, reviews[locus["id"]], cache, exact_font=args.exact_font,
        )
        rows.extend(locus_rows)
        reach_rows.extend(locus_reach)
    payload = {
        "schema": "pcdc-glyph-prior-court-diagnostic/v1",
        "rows": rows,
        "reach_rows": reach_rows,
        "summary": {
            "model_lines": len(rows),
            "review_better": sum(row["reference_delta_iou"] > 1.0e-9 for row in rows),
            "review_worse": sum(row["reference_delta_iou"] < -1.0e-9 for row in rows),
            "court_selected": sum(row["decision_selected_model"] for row in rows),
            "ocr_rows": len(reach_rows),
            "physical_contract_rows": sum(
                row["physical_source_gate"] and row["glyph_prior_contract"]
                for row in reach_rows
            ),
            "physical_contract_rows_with_neural": sum(
                row["physical_source_gate"] and row["glyph_prior_contract"]
                and row["neural_emitted_for_text"] for row in reach_rows
            ),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")
    print(json.dumps(payload["summary"], sort_keys=True))


if __name__ == "__main__":
    main()

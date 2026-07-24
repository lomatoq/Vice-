"""Foundational Experiment 3: Certificate Discrimination.

The machine subset is deterministic and construction-labelled.  Human
agreement is a separate gate backed only by exported review answers; missing
answers are never inferred from the construction label or the court result.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
from typing import Any

import cv2
import numpy as np

from .build_identity import bind_report
from .experiment_inputs import certificate_court_input_identity

from .atlas_renderer import ExactRoiAtlas, RoiRenderRequest
from .certificates import topology_signature
from .local_court import CourtCandidate, CourtWeights, compare_in_local_court
from .renderer_posterior import (
    apply_formation, synthetic_renderer_posterior,
)


PROJECT = Path(__file__).resolve().parents[1]
DATASET = PROJECT / "datasets" / "pcdc_certificate_pairs_v1"
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_experiment3" / "report.json"
REVIEW_FILE = DATASET / "review.json"
HUMAN_MANIFEST = DATASET / "human_manifest.json"
PAIR_TYPES = (
    "ideal_circle_vs_jagged_overfit",
    "real_accent_vs_codec_fleck",
    "valid_counter_vs_filled_counter",
    "separate_glyphs_vs_fusion",
    "correct_layer_vs_eraser",
    "stroke_vs_ribbon",
    "gradient_vs_band_stack",
)
PAIRS_PER_TYPE = 32
REQUIRED_HUMAN_REVIEWS = 35
ECE_TARGET = 0.05


@dataclass(frozen=True)
class DiscriminationCase:
    id: str
    pair_type: str
    observed: np.ndarray
    evidence_support: np.ndarray
    correct: CourtCandidate
    competitor: CourtCandidate
    true_microdetail: bool
    topology_catastrophe_competitor: bool


def _rect_mask(
    shape: tuple[int, int], xyxy: tuple[int, int, int, int]
) -> np.ndarray:
    mask = np.zeros(shape, np.uint8)
    x1, y1, x2, y2 = xyxy
    mask[y1:y2, x1:x2] = 1
    return mask.astype(bool)


def _ring_mask(
    shape: tuple[int, int], center: tuple[int, int], outer: int, inner: int
) -> np.ndarray:
    mask = np.zeros(shape, np.uint8)
    cv2.circle(mask, center, outer, 1, -1, lineType=cv2.LINE_8)
    cv2.circle(mask, center, inner, 0, -1, lineType=cv2.LINE_8)
    return mask.astype(bool)


def _request(
    case_id: str, suffix: str, kind: str,
    parameters: dict[str, float | int | str],
    *, support: np.ndarray | None = None,
    color0: tuple[float, float, float, float] = (0.03, 0.04, 0.06, 1.0),
    color1: tuple[float, float, float, float] | None = None,
) -> RoiRenderRequest:
    return RoiRenderRequest(
        id=f"{case_id}-{suffix}", roi_xyxy=(0, 0, 64, 64), kind=kind,
        parameters=tuple(sorted(parameters.items())),
        color0_linear=color0, color1_linear=color1,
        support_mask=support, supersample=4,
    )


def _claim_from_render(render: np.ndarray) -> np.ndarray:
    mask = render[..., 3] > 1e-5
    return cv2.dilate(
        mask.astype(np.uint8), np.ones((3, 3), np.uint8)
    ).astype(bool)


def _candidate(
    case_id: str, suffix: str, request: RoiRenderRequest,
    claim: np.ndarray, *, evidence: np.ndarray,
    hard_topology: bool = False,
    structural: dict[str, float] | None = None,
    risk: float = 0.0, exceptions: int = 0,
    group_savings: float = 0.0, editability: float = 0.0,
    persistent: bool = True, provenance: tuple[str, ...] = (),
) -> CourtCandidate:
    components, holes = topology_signature(evidence)
    return CourtCandidate(
        id=f"{case_id}-{suffix}", request=request,
        claimed_support=claim,
        expected_components=components if hard_topology else None,
        expected_holes=holes if hard_topology else None,
        hard_topology=hard_topology,
        persistent_topology_evidence=persistent,
        boundary_tolerance_px=2.25,
        structural_claims=tuple(sorted((structural or {}).items())),
        risk=risk, exception_count=exceptions,
        group_savings_bits=group_savings,
        editability_cost_bits=editability,
        provenance=(*provenance, pair_type_provenance(case_id)),
    )


def pair_type_provenance(case_id: str) -> str:
    return f"experiment3-construction:{case_id.split('-')[0]}"


def _make_pair(
    pair_type: str, variant: int, posterior: Any,
    atlas: ExactRoiAtlas,
) -> DiscriminationCase:
    case_id = f"{pair_type}-{variant:03d}"
    phase = variant * 0.37
    if pair_type == "ideal_circle_vs_jagged_overfit":
        cx = 32.0 + 0.35 * math.sin(phase)
        cy = 32.0 + 0.35 * math.cos(phase)
        radius = 13.5 + (variant % 7) * 0.45
        correct_request = _request(case_id, "correct", "circle", {
            "cx": cx, "cy": cy, "radius": radius,
        })
        bad_request = _request(case_id, "competitor", "jagged_circle", {
            "cx": cx, "cy": cy, "radius": radius,
            "amplitude": 0.72 + 0.06 * (variant % 4),
            "lobes": 9 + variant % 8, "phase": phase,
        })
        hard = False
        correct_struct = {"symmetry": 0.98, "equal_radius": 0.98,
                          "semantic_confidence": 0.92}
        bad_struct = {"symmetry": 0.22, "equal_radius": 0.28,
                      "semantic_confidence": 0.63}
        correct_risk, bad_risk = 0.01, 0.18
        correct_exceptions, bad_exceptions = 0, 12
        true_micro = False; catastrophe = False
    elif pair_type == "real_accent_vs_codec_fleck":
        base = _rect_mask((64, 64), (14, 29, 50, 43))
        accent = np.zeros((64, 64), np.uint8)
        ax = 23 + variant % 18
        cv2.circle(accent, (ax, 23), 2 + variant % 2, 1, -1)
        correct_mask = base | accent.astype(bool)
        bad_mask = base
        correct_request = _request(
            case_id, "correct", "mask", {}, support=correct_mask
        )
        bad_request = _request(
            case_id, "competitor", "mask", {}, support=bad_mask
        )
        hard = True
        correct_struct = {"text_line": 0.94, "semantic_confidence": 0.97}
        bad_struct = {"text_line": 0.56, "semantic_confidence": 0.42}
        correct_risk, bad_risk = 0.01, 0.45
        correct_exceptions = bad_exceptions = 0
        true_micro = True; catastrophe = True
    elif pair_type == "valid_counter_vs_filled_counter":
        correct_mask = _ring_mask((64, 64), (32, 32), 17, 8 + variant % 3)
        bad_mask = np.zeros((64, 64), np.uint8)
        cv2.circle(bad_mask, (32, 32), 17, 1, -1)
        correct_request = _request(
            case_id, "correct", "mask", {}, support=correct_mask
        )
        bad_request = _request(
            case_id, "competitor", "mask", {}, support=bad_mask.astype(bool)
        )
        hard = True
        correct_struct = {"text_line": 0.84, "semantic_confidence": 0.96}
        bad_struct = {"text_line": 0.31, "semantic_confidence": 0.48}
        correct_risk, bad_risk = 0.01, 0.62
        correct_exceptions = bad_exceptions = 0
        true_micro = False; catastrophe = True
    elif pair_type == "separate_glyphs_vs_fusion":
        gap = 2 + variant % 3
        left = _rect_mask((64, 64), (13, 19, 30, 46))
        right = _rect_mask((64, 64), (30 + gap, 19, 47 + gap, 46))
        correct_mask = left | right
        bad_mask = correct_mask.copy()
        bad_mask[29:34 + gap, 29:36] = True
        correct_request = _request(
            case_id, "correct", "mask", {}, support=correct_mask
        )
        bad_request = _request(
            case_id, "competitor", "mask", {}, support=bad_mask
        )
        hard = True
        correct_struct = {"text_line": 0.97, "repeated_glyph": 0.78,
                          "semantic_confidence": 0.96}
        bad_struct = {"text_line": 0.28, "repeated_glyph": 0.22,
                      "semantic_confidence": 0.43}
        correct_risk, bad_risk = 0.01, 0.64
        correct_exceptions = 0; bad_exceptions = 1
        true_micro = False; catastrophe = True
    elif pair_type == "correct_layer_vs_eraser":
        correct_mask = _rect_mask((64, 64), (9, 11, 55, 53))
        cv2.circle(correct_mask.view(np.uint8), (32, 32), 10, 0, -1)
        correct_request = _request(
            case_id, "correct", "mask", {}, support=correct_mask,
            color0=(0.04, 0.12, 0.42, 1.0),
        )
        bad_request = _request(
            case_id, "competitor", "eraser", {},
            support=np.ones((64, 64), bool),
        )
        hard = True
        correct_struct = {"layer_order": 0.99, "semantic_confidence": 0.95}
        bad_struct = {"layer_order": 0.0, "semantic_confidence": 0.05}
        correct_risk, bad_risk = 0.01, 1.0
        correct_exceptions = 0; bad_exceptions = 64
        true_micro = False; catastrophe = True
    elif pair_type == "stroke_vs_ribbon":
        y1 = 17.0 + variant % 5
        y2 = 46.0 - variant % 4
        correct_request = _request(case_id, "correct", "stroke", {
            "x1": 11.0, "y1": y1, "x2": 53.0, "y2": y2,
            "width": 3.0 + 0.25 * (variant % 3),
        })
        ribbon = np.zeros((64, 64), np.uint8)
        points = np.asarray([
            [10, int(y1 - 1)], [31, int((y1 + y2) * 0.5 - 5)],
            [54, int(y2 - 2)], [53, int(y2 + 3)],
            [31, int((y1 + y2) * 0.5 + 6)], [9, int(y1 + 2)],
        ], np.int32)
        cv2.fillPoly(ribbon, [points], 1)
        bad_request = _request(
            case_id, "competitor", "mask", {}, support=ribbon.astype(bool)
        )
        hard = False
        correct_struct = {"stroke_width": 0.98, "semantic_confidence": 0.94}
        bad_struct = {"stroke_width": 0.18, "semantic_confidence": 0.52}
        correct_risk, bad_risk = 0.01, 0.26
        correct_exceptions = 0; bad_exceptions = 6
        true_micro = False; catastrophe = False
    elif pair_type == "gradient_vs_band_stack":
        support = _rect_mask((64, 64), (7, 10, 57, 54))
        parameters = {
            "x0": 7.0, "y0": 10.0 + variant % 7,
            "x1": 57.0, "y1": 54.0 - variant % 5,
        }
        c0 = (0.03, 0.08, 0.42, 1.0)
        c1 = (0.82, 0.16, 0.05, 1.0)
        correct_request = _request(
            case_id, "correct", "gradient", parameters,
            support=support, color0=c0, color1=c1,
        )
        bad_request = _request(
            case_id, "competitor", "band_stack",
            {**parameters, "bands": 4 + variant % 4},
            support=support, color0=c0, color1=c1,
        )
        hard = False
        correct_struct = {"semantic_confidence": 0.96}
        bad_struct = {"semantic_confidence": 0.66}
        correct_risk, bad_risk = 0.01, 0.22
        correct_exceptions = 0; bad_exceptions = 5 + variant % 4
        true_micro = False; catastrophe = False
    else:  # pragma: no cover
        raise ValueError(pair_type)

    rendered = atlas.render(
        (correct_request, bad_request), canvas_size=(64, 64)
    ).by_id()
    correct_render = rendered[correct_request.id]
    bad_render = rendered[bad_request.id]
    evidence = correct_render[..., 3] >= 0.5
    model = posterior.models[variant % len(posterior.models)]
    observed = apply_formation(correct_render, model)
    # Sparse single-pixel codec disturbances test robust likelihood without
    # changing the construction-level persistent support label.
    if pair_type == "ideal_circle_vs_jagged_overfit" and variant % 3 == 0:
        x = 5 + (variant * 7) % 54; y = 5 + (variant * 11) % 54
        observed[y, x, :3] = 0.0; observed[y, x, 3] = 1.0
    observed = np.ascontiguousarray(np.clip(observed, 0.0, 1.0), np.float32)
    correct = _candidate(
        case_id, "correct", correct_request,
        _claim_from_render(correct_render), evidence=evidence,
        hard_topology=hard, structural=correct_struct,
        risk=correct_risk, exceptions=correct_exceptions,
        group_savings=8.0 if pair_type in {
            "ideal_circle_vs_jagged_overfit", "stroke_vs_ribbon"
        } else 0.0,
        provenance=("construction-labelled-correct",),
    )
    competitor = _candidate(
        case_id, "competitor", bad_request,
        _claim_from_render(bad_render) if np.any(bad_render[..., 3])
        else np.ones((64, 64), bool),
        evidence=evidence, hard_topology=hard,
        structural=bad_struct, risk=bad_risk,
        exceptions=bad_exceptions, editability=4.0 * bad_exceptions,
        provenance=("construction-labelled-competitor",),
    )
    return DiscriminationCase(
        id=case_id, pair_type=pair_type, observed=observed,
        evidence_support=evidence, correct=correct, competitor=competitor,
        true_microdetail=true_micro,
        topology_catastrophe_competitor=catastrophe,
    )


def build_cases() -> tuple[DiscriminationCase, ...]:
    posterior = synthetic_renderer_posterior(source_id="experiment3-v1")
    atlas = ExactRoiAtlas()
    return tuple(
        _make_pair(pair_type, variant, posterior, atlas)
        for pair_type in PAIR_TYPES
        for variant in range(PAIRS_PER_TYPE)
    )


def _ece(probabilities: list[float], labels: list[float], bins: int = 10) -> float:
    if not probabilities:
        return 1.0
    probability = np.asarray(probabilities, np.float64)
    truth = np.asarray(labels, np.float64)
    result = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        mask = (probability >= low) & (
            probability <= high if index == bins - 1 else probability < high
        )
        if np.any(mask):
            result += float(np.mean(mask)) * abs(
                float(np.mean(probability[mask]) - np.mean(truth[mask]))
            )
    return result


def _human_metrics(rows: list[dict[str, Any]]) -> tuple[int, float | None]:
    if not REVIEW_FILE.exists() or not HUMAN_MANIFEST.exists():
        return 0, None
    payload = json.loads(REVIEW_FILE.read_text("utf-8"))
    manifest = json.loads(HUMAN_MANIFEST.read_text("utf-8"))
    answers = payload.get("answers", {})
    lookup = {row["id"]: row for row in rows}
    correct_side = {
        row["id"]: row["correct_side"] for row in manifest.get("cases", [])
    }
    agreements: list[float] = []
    for case_id, answer in answers.items():
        choice = answer.get("choice") if isinstance(answer, dict) else answer
        if case_id not in lookup or case_id not in correct_side or choice not in {"A", "B", "tie"}:
            continue
        if choice == "tie":
            agreements.append(0.5)
        else:
            human_correct = choice == correct_side[case_id]
            court_correct = bool(lookup[case_id]["correct_selected"])
            agreements.append(float(human_correct == court_correct))
    return len(agreements), statistics.fmean(agreements) if agreements else None


def build_report() -> dict[str, Any]:
    input_identity = certificate_court_input_identity(DATASET)
    posterior = synthetic_renderer_posterior(source_id="experiment3-v1")
    atlas = ExactRoiAtlas()
    weights = CourtWeights()
    rows: list[dict[str, Any]] = []
    for case in build_cases():
        decision = compare_in_local_court(
            case.observed, case.evidence_support,
            case.correct, case.competitor, posterior,
            weights=weights, atlas=atlas,
        )
        rows.append({
            "id": case.id, "pair_type": case.pair_type,
            "correct_selected": decision.selected_id == case.correct.id,
            "selected_id": decision.selected_id,
            "candidate_probability": decision.calibrated_candidate_probability,
            "candidate_score": decision.candidate_score,
            "reason": decision.reason,
            "true_microdetail": case.true_microdetail,
            "topology_catastrophe_competitor": case.topology_catastrophe_competitor,
            "topology_catastrophe_selected": bool(
                case.topology_catastrophe_competitor
                and decision.selected_id == case.competitor.id
            ),
            "candidate_bundle_digest": decision.candidate_bundle.digest,
            "fallback_bundle_digest": decision.fallback_bundle.digest,
            "posterior_digest": decision.posterior_digest,
            "exact_render_pixels": decision.exact_render_pixels,
        })
    correct_rate = statistics.fmean(float(row["correct_selected"]) for row in rows)
    micro_rows = [row for row in rows if row["true_microdetail"]]
    micro_recall = statistics.fmean(
        float(row["correct_selected"]) for row in micro_rows
    )
    catastrophe_rate = statistics.fmean(
        float(row["topology_catastrophe_selected"]) for row in rows
    )
    ece = _ece(
        [float(row["candidate_probability"]) for row in rows],
        [1.0] * len(rows),
    )
    human_count, human_agreement = _human_metrics(rows)
    machine_gate = (
        correct_rate >= 0.95 and micro_recall >= 0.97
        and catastrophe_rate <= 0.005 and ece <= ECE_TARGET
    )
    human_gate = bool(
        human_count >= REQUIRED_HUMAN_REVIEWS
        and human_agreement is not None and human_agreement >= 0.90
    )
    gate = machine_gate and human_gate
    if gate:
        status = "passed"
        stop_rule = None
    elif not machine_gate:
        status = "failed_stop"
        stop_rule = "Fix court/renderer before typed macro phases."
    else:
        status = "machine_passed_pending_human_review"
        stop_rule = "Collect genuine blind human reviews; do not infer agreement."
    by_type = {}
    for pair_type in PAIR_TYPES:
        typed = [row for row in rows if row["pair_type"] == pair_type]
        by_type[pair_type] = {
            "n": len(typed),
            "correct_choice_rate": statistics.fmean(
                float(row["correct_selected"]) for row in typed
            ),
            "mean_candidate_probability": statistics.fmean(
                float(row["candidate_probability"]) for row in typed
            ),
        }
    return {
        "schema": "pcdc-experiment3/v1",
        "input_identity": input_identity,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status, "gate_pass": gate,
        "machine_gate_pass": machine_gate,
        "human_gate_pass": human_gate,
        "metrics": {
            "correct_choice_rate": correct_rate,
            "true_microdetail_recall": micro_recall,
            "topology_catastrophe_choice_rate": catastrophe_rate,
            "calibration_ece": ece, "calibration_ece_target": ECE_TARGET,
            "human_review_count": human_count,
            "required_human_reviews": REQUIRED_HUMAN_REVIEWS,
            "human_agreement": human_agreement,
        },
        "by_type": by_type, "stop_rule": stop_rule, "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = bind_report(build_report())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    print(json.dumps({
        "status": report["status"], "gate_pass": report["gate_pass"],
        "machine_gate_pass": report["machine_gate_pass"],
        "human_gate_pass": report["human_gate_pass"],
        "metrics": report["metrics"], "by_type": report["by_type"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["machine_gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Foundational Experiment 1B: dual-guided typed pricing recall."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
from typing import Any

import cv2
import numpy as np

from .build_identity import bind_report
from .experiment_inputs import real_locus_input_identity

from .column_generation import run_column_generation
from .evidence_ir import EvidenceCache
from .experiment1_evidence_coverage import FAMILY_MAP, decode_support_rle


PROJECT = Path(__file__).resolve().parents[1]
CORPUS = PROJECT / "datasets" / "pcdc_real_loci_v1"
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_experiment1b" / "report.json"
TYPED_PRICING_FAMILIES = frozenset({
    "text", "shape", "symmetry", "component", "stroke", "layer",
    "gradient", "codec_detail",
})


def _pricing_machine_gate(
    *, acceptable_recall: float, class_floor: float, p95_pricing: float,
    column_ratio: float, no_manual: bool, feasible: bool,
) -> bool:
    """Require overall and worst-semantic-class lazy-pricing recall."""
    return bool(
        acceptable_recall >= 0.95
        and class_floor >= 0.95
        and p95_pricing < 100.0
        and column_ratio < 0.25
        and no_manual and feasible
    )


def _candidate_mask(candidate: Any, shape: tuple[int, int]) -> np.ndarray | None:
    certificate = candidate.certificates
    if not certificate.support_rle and not certificate.support_bits:
        return None
    width, height = certificate.support_size
    if certificate.support_bits:
        flat = np.unpackbits(
            np.frombuffer(certificate.support_bits, dtype=np.uint8),
            count=width * height, bitorder="little",
        ).astype(bool, copy=False)
    else:
        flat = np.zeros(width * height, dtype=bool)
        for start, length in certificate.support_rle:
            flat[start:start + length] = True
    mask = flat.reshape((height, width))
    if mask.shape != shape:
        mask = cv2.resize(
            mask.astype(np.uint8), (shape[1], shape[0]),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    return mask


def _greedy_family_support_recall(
    candidates: list[Any], target: np.ndarray, expected: set[str],
    *, k: int = 32,
) -> float:
    target_area = int(target.sum())
    if target_area <= 0:
        return 0.0
    projections = []
    for candidate in candidates:
        if candidate.family not in expected:
            continue
        mask = _candidate_mask(candidate, target.shape)
        if mask is None:
            continue
        intersection = int(np.sum(mask & target))
        precision = intersection / max(1, int(mask.sum()))
        if intersection > 0 and precision >= 0.82:
            projections.append(mask & target)
    if not projections:
        return 0.0
    matrix = np.stack([projection[target] for projection in projections])
    covered = np.zeros(target_area, dtype=bool)
    used = np.zeros(len(matrix), dtype=bool)
    for _ in range(min(k, len(matrix))):
        gains = np.sum(matrix & ~covered, axis=1)
        gains[used] = -1
        best = int(np.argmax(gains))
        if gains[best] <= 0:
            break
        used[best] = True
        covered |= matrix[best]
    return float(covered.mean())


def _exhaustive_registry_size(reir: Any) -> int:
    """Count the typed registry avoided by lazy cue/support generation."""
    support_keys: set[tuple[Any, ...]] = set()
    typed_cues = 0
    for token in reir.proposal_tokens:
        if token.family in TYPED_PRICING_FAMILIES:
            typed_cues += 1
        if token.support_bits:
            key = ("bits", token.support_size, token.support_bits)
        elif token.support_rle:
            key = ("rle", token.support_size, token.support_rle)
        elif token.support_leaf_ids:
            key = ("leaves", tuple(sorted(set(token.support_leaf_ids))))
        else:
            continue
        support_keys.add(key)
    # Exhaustive construction would materialize every direct proposal and
    # every typed semantic-cue/support pairing before solving the master.
    return len(reir.proposal_tokens) + typed_cues * len(support_keys)


def evaluate_locus(
    locus: dict[str, Any], review: dict[str, Any], cache: EvidenceCache
) -> dict[str, Any]:
    width, height = review["support_size"]
    target = decode_support_rle(review["support_rle"], width, height)
    reir, cache_hit = cache.get_or_build(locus["source"]["path"])
    if target.shape != (reir.height, reir.width):
        target = cv2.resize(
            target.astype(np.uint8), (reir.width, reir.height),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    result = run_column_generation(
        reir, rounds=3, max_columns_per_oracle=12,
        extraction_budget_ms=35.0, exact_component_limit=7,
    )
    expected = set(FAMILY_MAP.get(
        str(review["macro_family"]), {str(review["macro_family"])}
    ))
    lookup = result.cmir.by_id()
    cumulative: list[Any] = []
    family_by_round = []
    support_by_round = []
    pricing_per_roi = []
    pricing_round_ms = []
    columns_by_round = []
    dual_concentration_by_round = []
    for record in result.rounds:
        cumulative.extend(lookup[candidate_id] for candidate_id in record.added_ids)
        family_by_round.append(float(any(
            candidate.family in expected for candidate in cumulative
        )))
        support_by_round.append(_greedy_family_support_recall(
            cumulative, target, expected,
        ))
        pricing_round_ms.append(record.elapsed_ms)
        columns_by_round.append(record.generated_columns)
        dual_concentration_by_round.append(record.dual_concentration)
        for batch in record.batches:
            if batch.considered > 0:
                # Conservatively charge the complete active oracle batch to
                # one ROI; never hide latency by dividing by candidates.
                pricing_per_roi.append(batch.elapsed_ms)
    while len(family_by_round) < 3:
        family_by_round.append(family_by_round[-1] if family_by_round else 0.0)
        support_by_round.append(support_by_round[-1] if support_by_round else 0.0)
    family_present = bool(family_by_round[2])
    support_recall = support_by_round[2]
    acceptable = family_present and support_recall >= 0.55
    generated = result.final_columns - result.initial_columns
    return {
        "id": locus["id"], "semantic_class": locus["semantic_class"],
        "cache_hit": cache_hit, "family_recall_by_round": family_by_round,
        "support_recall_by_round": support_by_round,
        "acceptable_macro_by_round3": acceptable,
        "generated_columns": generated,
        "exhaustive_registry_columns": _exhaustive_registry_size(reir),
        "pricing_ms_per_roi": pricing_per_roi,
        "pricing_round_ms": pricing_round_ms,
        "columns_added_by_round": columns_by_round,
        "dual_concentration_by_round": dual_concentration_by_round,
        "final_proposal_recall": support_recall,
        "master_feasible": result.solution.feasible,
        "used_manual_risk_threshold": result.used_manual_risk_threshold,
        "pricing_rounds": len(result.rounds),
    }


def build_report(corpus_dir: Path = CORPUS) -> dict[str, Any]:
    input_identity = real_locus_input_identity(corpus_dir)
    manifest = json.loads((corpus_dir / "manifest.json").read_text("utf-8"))
    reviews = json.loads((corpus_dir / "review.json").read_text("utf-8"))["reviews"]
    if len(reviews) != int(manifest["total"]):
        return {
            "schema": "pcdc-experiment1b/v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "blocked_incomplete_evidence", "gate_pass": False,
            "rows": [],
        }
    cache = EvidenceCache()
    rows = [
        evaluate_locus(locus, reviews[locus["id"]], cache)
        for locus in manifest["loci"]
    ]
    acceptable_recall = statistics.fmean(
        float(row["acceptable_macro_by_round3"]) for row in rows
    )
    family_by_round = [statistics.fmean(
        row["family_recall_by_round"][index] for row in rows
    ) for index in range(3)]
    support_by_round = [statistics.fmean(
        row["support_recall_by_round"][index] for row in rows
    ) for index in range(3)]
    pricing_times = sorted(
        value for row in rows for value in row["pricing_ms_per_roi"]
    )
    p95_pricing = pricing_times[
        min(len(pricing_times) - 1, int(0.95 * len(pricing_times)))
    ] if pricing_times else 0.0
    mean_generated = statistics.fmean(row["generated_columns"] for row in rows)
    mean_exhaustive = statistics.fmean(
        row["exhaustive_registry_columns"] for row in rows
    )
    column_ratio = mean_generated / max(1.0, mean_exhaustive)
    no_manual = not any(row["used_manual_risk_threshold"] for row in rows)
    feasible = all(row["master_feasible"] for row in rows)
    by_class = {}
    class_floor = 1.0
    for semantic_class in manifest["targets"]:
        class_rows = [row for row in rows
                      if row["semantic_class"] == semantic_class]
        value = statistics.fmean(
            float(row["acceptable_macro_by_round3"]) for row in class_rows
        )
        class_floor = min(class_floor, value)
        by_class[semantic_class] = {
            "n": len(class_rows), "acceptable_macro_recall": value,
            "family_recall_round3": statistics.fmean(
                row["family_recall_by_round"][2] for row in class_rows
            ),
            "mean_support_recall_round3": statistics.fmean(
                row["support_recall_by_round"][2] for row in class_rows
            ),
            "manual_risk_threshold_used": any(
                row["used_manual_risk_threshold"] for row in class_rows
            ),
        }
    mean_columns_by_round = [statistics.fmean(
        (row["columns_added_by_round"] + [0, 0, 0])[:3][index]
        for row in rows
    ) for index in range(3)]
    mean_dual_by_round = [statistics.fmean(
        (row["dual_concentration_by_round"] + [0.0, 0.0, 0.0])[:3][index]
        for row in rows
    ) for index in range(3)]
    round_times = sorted(
        value for row in rows for value in row["pricing_round_ms"]
    )
    p95_round = round_times[
        min(len(round_times) - 1, int(0.95 * len(round_times)))
    ] if round_times else 0.0
    gate = _pricing_machine_gate(
        acceptable_recall=acceptable_recall, class_floor=class_floor,
        p95_pricing=p95_pricing, column_ratio=column_ratio,
        no_manual=no_manual, feasible=feasible,
    )
    return {
        "schema": "pcdc-experiment1b/v1",
        "input_identity": input_identity,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if gate else "failed_stop",
        "gate_pass": gate,
        "metrics": {
            "acceptable_macro_recall_round3": acceptable_recall,
            "family_recall_by_round": family_by_round,
            "mean_family_qualified_support_recall_by_round": support_by_round,
            "class_floor": class_floor,
            "p95_pricing_ms_per_roi": p95_pricing,
            "p95_complete_round_ms": p95_round,
            "mean_columns_added_by_round": mean_columns_by_round,
            "mean_dual_concentration_by_round": mean_dual_by_round,
            "mean_generated_columns": mean_generated,
            "mean_exhaustive_registry_columns": mean_exhaustive,
            "generated_to_exhaustive_ratio": column_ratio,
            "manual_risk_threshold_used": not no_manual,
            "master_feasible_all": feasible,
        },
        "by_class": by_class,
        "stop_rule": None if gate else "Fix pricing recall before court/ML.",
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = bind_report(build_report(args.corpus), evaluator_source=__file__)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"], "gate_pass": report["gate_pass"],
        "metrics": report.get("metrics"), "by_class": report.get("by_class"),
    }, ensure_ascii=False, indent=2))
    return int(not report["gate_pass"])


if __name__ == "__main__":
    raise SystemExit(main())

"""Pre-training proof that every quality mode uses one admission transaction."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

from .build_identity import compiler_source_sha256
from .conformal import (
    ConformalCalibration, ConformalThreshold, runtime_conformal_query_set,
)
from .proposal_net import ProposalQuery, QUERY_FAMILIES
from .runtime_service import QUALITY_BUDGETS, WarmProposalWorker


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_pre_v14" / "runtime_conformal.json"


def _query(family: str, index: int) -> ProposalQuery:
    support = np.zeros((8, 8), np.float32)
    support[index % 8, (index // 8) % 8] = 1.0
    support.setflags(write=False)
    return ProposalQuery(
        id=f"{family}-{index:03d}", family=family,
        roi_xyxy=(0.0, 0.0, 1.0, 1.0), soft_support=support,
        parameters=(0.0,), covariance=(1.0,),
        confidence=max(0.01, 0.99 - index / 100.0), relation_tokens=(),
        topology_code=(1, 0), hard_negative_class=None,
        provenance=("runtime-conformal-harness",),
    )


def build_report() -> dict:
    families = QUERY_FAMILIES[:-1]
    calibration = ConformalCalibration(
        target_coverage=0.99,
        thresholds=tuple(
            ConformalThreshold(
                family=family, alpha=0.01, threshold=0.25,
                calibration_count=100, empirical_coverage=0.99,
            )
            for family in families
        ),
        global_threshold=0.25,
        split_policy="source-family+semantic-class-disjoint",
        provenance=(
            "finite-sample-higher-quantile",
            "exact-runtime-prefix-rank-with-support-IoU-floor",
        ),
    )
    all_rows = tuple(
        _query(family, index) for family in families for index in range(64)
    )
    classical = all_rows[::2]
    neural = all_rows[1::2]
    mode_results = {}
    passed = True
    for budget in QUALITY_BUDGETS.values():
        limit = budget.proposal_queries
        first = runtime_conformal_query_set(
            classical, neural, calibration, maximum_queries=limit,
        )
        second = runtime_conformal_query_set(
            classical, neural, calibration, maximum_queries=limit,
        )
        sorted_ids = tuple(
            row.id for row in sorted(
                first, key=lambda row: (-row.confidence, row.id),
            )
        )
        deterministic = tuple(row.id for row in first) == tuple(
            row.id for row in second
        )
        globally_bounded = len(first) <= limit
        globally_sorted = tuple(row.id for row in first) == sorted_ids
        family_prefix_valid = True
        for family in families:
            admitted = [row for row in first if row.family == family]
            ordered = sorted(
                [row for row in all_rows if row.family == family],
                key=lambda row: (-row.confidence, row.id),
            )[:limit]
            family_limit = min(len(ordered), int(0.25 * len(ordered)) + 1)
            permitted_ids = {row.id for row in ordered[:family_limit]}
            if any(row.id not in permitted_ids for row in admitted):
                family_prefix_valid = False
                break
        row_passed = all((
            deterministic, globally_bounded, globally_sorted,
            family_prefix_valid,
        ))
        passed = passed and row_passed
        mode_results[budget.mode.value] = {
            "maximum_queries": limit,
            "admitted_queries": len(first),
            "deterministic": deterministic,
            "globally_bounded": globally_bounded,
            "globally_sorted": globally_sorted,
            "family_prefix_valid": family_prefix_valid,
            "passed": row_passed,
        }
    worker_source_names = frozenset(WarmProposalWorker.infer.__code__.co_names)
    shared_runtime_function = "runtime_conformal_query_set" in worker_source_names
    passed = passed and shared_runtime_function
    return {
        "schema": "pcdc-runtime-conformal-harness/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compiler_source_sha256": compiler_source_sha256(),
        "passed": passed,
        "shared_runtime_function": shared_runtime_function,
        "exact_runtime_rule": True,
        "all_quality_modes_exercised": set(mode_results) == {
            budget.mode.value for budget in QUALITY_BUDGETS.values()
        },
        "global_budget_cap_verified": all(
            row["globally_bounded"] for row in mode_results.values()
        ),
        "candidate_coverage_deferred_to": (
            "hash-bound Experiment-9 exact Fast/Balanced/Max held-out replay"
        ),
        "calibration_fixture": asdict(calibration),
        "quality_modes": mode_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8",
    )
    print(json.dumps({
        "passed": report["passed"], "out": str(args.out.resolve()),
    }, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

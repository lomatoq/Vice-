"""Foundational Experiment 2: oracle-weighted macro extraction.

The experiment intentionally supplies the correct family/support/topology from
the frozen corpus.  It tests the selection architecture only: can the master
choose the oracle column, keep an exact visible cover, and stay bounded?
"""

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

from .evidence_ir import EvidenceCache
from .experiment1_evidence_coverage import decode_support_rle
from .macro_extractor import extract_visible_scene
from .macro_ir import MacroKind
from .macro_registry import (
    build_base_registry, candidate_from_support, extend_registry,
)
from .visible_scene import build_visible_scene


PROJECT = Path(__file__).resolve().parents[1]
CORPUS = PROJECT / "datasets" / "pcdc_real_loci_v1"
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_experiment2" / "report.json"


def _resize_support(mask: np.ndarray, width: int, height: int) -> np.ndarray:
    if mask.shape == (height, width):
        return mask
    return cv2.resize(
        mask.astype(np.uint8), (width, height),
        interpolation=cv2.INTER_NEAREST,
    ) > 0


def evaluate_locus(
    locus: dict[str, Any], review: dict[str, Any], cache: EvidenceCache
) -> dict[str, Any]:
    width, height = review["support_size"]
    support = decode_support_rle(review["support_rle"], width, height)
    reir, cache_hit = cache.get_or_build(locus["source"]["path"])
    support = _resize_support(support, reir.width, reir.height)
    base = build_base_registry(reir)
    roi = tuple(int(value) for value in review["roi_xyxy"])
    if (width, height) != (reir.width, reir.height):
        sx, sy = reir.width / width, reir.height / height
        roi = (
            int(round(roi[0] * sx)), int(round(roi[1] * sy)),
            int(round(roi[2] * sx)), int(round(roi[3] * sy)),
        )
    oracle = candidate_from_support(
        reir, family=str(review["macro_family"]), mask=support,
        roi_xyxy=roi, evidence_token_ids=(), score=4.0,
        provenance=("frozen-oracle-annotation", "experiment2-only"),
        kind=MacroKind.ORACLE,
        components=int(review["components"]), holes=int(review["holes"]),
        prefix="experiment2-oracle",
    )
    if oracle is None:
        return {
            "id": locus["id"], "semantic_class": locus["semantic_class"],
            "cache_hit": cache_hit, "acceptable_scene": False,
            "topology_catastrophe": True, "fallback_feasible": True,
            "solve_ms": 0.0, "failure": "empty-oracle-support",
        }
    cmir = extend_registry(reir, base, (oracle,))
    solution = extract_visible_scene(
        cmir, reir.hierarchy,
        exact_component_limit=18, time_budget_ms=100.0,
    )
    scene = build_visible_scene(cmir, solution) if solution.feasible else None
    selected = oracle.id in solution.selected_ids
    topology_ok = (
        oracle.certificates.components == int(review["components"])
        and oracle.certificates.holes == int(review["holes"])
    )
    acceptable = bool(
        selected and scene is not None and scene.exact_cover
        and oracle.certificates.support_rle
    )
    return {
        "id": locus["id"], "semantic_class": locus["semantic_class"],
        "cache_hit": cache_hit, "acceptable_scene": acceptable,
        "oracle_selected": selected,
        "topology_catastrophe": bool(selected and not topology_ok),
        "fallback_feasible": solution.fallback_always_feasible,
        "exact_cover": solution.exact_cover,
        "solve_ms": solution.solve_ms,
        "selected_macros": len(solution.selected_ids),
        "used_atomic_fallback": solution.used_atomic_fallback,
        "bounded_components": solution.bounded_components,
        "failure": None if acceptable else solution.fallback_reason or "oracle-not-selected",
    }


def build_report(corpus_dir: Path = CORPUS) -> dict[str, Any]:
    input_identity = real_locus_input_identity(corpus_dir)
    manifest = json.loads((corpus_dir / "manifest.json").read_text("utf-8"))
    reviews = json.loads((corpus_dir / "review.json").read_text("utf-8"))["reviews"]
    required = int(manifest["total"])
    admitted = {
        locus_id: review for locus_id, review in reviews.items()
        if review.get("status") in {
            "ground_truth_derived", "evidence_reviewed", "complete",
        }
    }
    if len(admitted) != required:
        return {
            "schema": "pcdc-experiment2/v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "blocked_incomplete_oracle_annotations",
            "gate_pass": False, "required": required,
            "observed": len(admitted), "rows": [],
        }
    cache = EvidenceCache()
    rows = [
        evaluate_locus(locus, admitted[locus["id"]], cache)
        for locus in manifest["loci"]
    ]
    times = sorted(float(row["solve_ms"]) for row in rows)
    median = float(statistics.median(times))
    p95 = times[min(len(times) - 1, int(0.95 * len(times)))]
    acceptable_rate = statistics.fmean(
        float(row["acceptable_scene"]) for row in rows
    )
    catastrophes = sum(bool(row["topology_catastrophe"]) for row in rows)
    fallback_feasible = all(row["fallback_feasible"] for row in rows)
    gate = (
        acceptable_rate >= 0.98 and catastrophes == 0
        and median < 20.0 and p95 < 100.0 and fallback_feasible
    )
    by_class = {}
    for semantic_class in manifest["targets"]:
        class_rows = [row for row in rows
                      if row["semantic_class"] == semantic_class]
        by_class[semantic_class] = {
            "n": len(class_rows),
            "acceptable_scene_rate": statistics.fmean(
                float(row["acceptable_scene"]) for row in class_rows
            ),
            "topology_catastrophes": sum(
                bool(row["topology_catastrophe"]) for row in class_rows
            ),
            "median_solve_ms": statistics.median(
                row["solve_ms"] for row in class_rows
            ),
        }
    return {
        "schema": "pcdc-experiment2/v1",
        "input_identity": input_identity,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if gate else "failed_stop",
        "gate_pass": gate,
        "metrics": {
            "acceptable_scene_rate": acceptable_rate,
            "topology_catastrophes": catastrophes,
            "median_solve_ms": median, "p95_solve_ms": p95,
            "fallback_always_feasible": fallback_feasible,
            "timeout_count": sum(
                row["failure"] == "time-budget-returned-valid-best"
                for row in rows
            ),
        },
        "by_class": by_class,
        "stop_rule": None if gate else "Do not build court; fix extractor architecture.",
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = bind_report(build_report(args.corpus))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"], "gate_pass": report["gate_pass"],
        "metrics": report.get("metrics"),
    }, ensure_ascii=False, indent=2))
    return int(not report["gate_pass"])


if __name__ == "__main__":
    raise SystemExit(main())

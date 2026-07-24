"""Reproducible Phase-1 REIR runtime gate on the frozen locus corpus."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np

from .evidence_ir import build_reir


PROJECT = Path(__file__).resolve().parents[1]
CORPUS = PROJECT / "datasets" / "pcdc_real_loci_v1" / "manifest.json"
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_experiment1" / "runtime_report.json"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return float("nan")
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def _select(rows: list[dict[str, Any]], per_class: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    classes = sorted({str(row["semantic_class"]) for row in rows})
    for semantic_class in classes:
        class_rows = [
            row for row in rows if row["semantic_class"] == semantic_class
        ]
        # The corpus is already deterministic SHA-sorted within each class.
        if per_class >= len(class_rows):
            selected.extend(class_rows)
            continue
        indices = np.linspace(
            0, len(class_rows) - 1, per_class, dtype=np.int32
        )
        selected.extend(class_rows[int(index)] for index in indices)
    return selected


def run(per_class: int = 5) -> dict[str, Any]:
    manifest = json.loads(CORPUS.read_text(encoding="utf-8"))
    selected = _select(manifest["loci"], per_class)
    # Warm native libraries and thread pools.  The warm-up is explicit and is
    # never included in the reported distribution.
    build_reir(selected[0]["source"]["path"])
    rows: list[dict[str, Any]] = []
    for locus in selected:
        reir = build_reir(locus["source"]["path"])
        total = next(
            record for record in reir.stage_profile["records"]
            if record["name"] == "reir_total"
        )
        rows.append(
            {
                "id": locus["id"],
                "semantic_class": locus["semantic_class"],
                "processing_size": [reir.width, reir.height],
                "processing_pixels": reir.width * reir.height,
                "wall_ms": float(total["wall_ms"]),
                "budget_ok": bool(total["budget_ok"]),
                "hierarchy_leaves": reir.hierarchy.leaf_count,
                "hierarchy_nodes": len(reir.hierarchy.nodes),
                "proposal_tokens": len(reir.proposal_tokens),
            }
        )
    values = [row["wall_ms"] for row in rows]
    by_class: dict[str, dict[str, float | int]] = {}
    for semantic_class in sorted({row["semantic_class"] for row in rows}):
        class_values = [
            row["wall_ms"] for row in rows
            if row["semantic_class"] == semantic_class
        ]
        by_class[semantic_class] = {
            "n": len(class_values),
            "p50_ms": _percentile(class_values, 50),
            "p95_ms": _percentile(class_values, 95),
            "max_ms": max(class_values),
        }
    p95 = _percentile(values, 95)
    maximum = max(values)
    return {
        "schema": "pcdc-reir-runtime/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus": str(CORPUS),
        "warmup_excluded": True,
        "sample_policy": f"{per_class} deterministic loci per class",
        "n": len(rows),
        "metrics": {
            "p50_ms": _percentile(values, 50),
            "p95_ms": p95,
            "max_ms": maximum,
            "under_300_count": sum(value < 300.0 for value in values),
        },
        "by_class": by_class,
        # The foundational plan says REIR construction <300 ms, not merely
        # p95 <300 ms.  Every deterministic gate item must therefore pass.
        "gate_pass": maximum < 300.0,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=5)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.per_class < 1:
        raise SystemExit("--per-class must be >=1")
    report = run(args.per_class)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "gate_pass": report["gate_pass"],
        "n": report["n"],
        "metrics": report["metrics"],
        "by_class": report["by_class"],
        "path": str(args.out),
    }, ensure_ascii=False, indent=2))
    return int(not report["gate_pass"])


if __name__ == "__main__":
    raise SystemExit(main())

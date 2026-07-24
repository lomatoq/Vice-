"""Phase-10 cold-evidence performance and anytime-contract campaign."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import tempfile
import time

import numpy as np

from .build_identity import bind_report, runtime_model_identity
from .evidence_ir import EvidenceCache
from .experiment_inputs import real_locus_input_identity
from .runtime_service import PersistentCompilerService, QualityMode


PROJECT = Path(__file__).resolve().parents[1]
CORPUS = PROJECT / "datasets" / "pcdc_real_loci_v1"
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_experiment10" / "report.json"
VALID_REVIEW = {"ground_truth_derived", "evidence_reviewed", "complete"}


def _cases(per_class: int = 2) -> list[dict[str, str]]:
    manifest = json.loads((CORPUS / "manifest.json").read_text("utf-8"))
    reviews = json.loads((CORPUS / "review.json").read_text("utf-8"))["reviews"]
    grouped: dict[str, list[dict]] = {}
    seen_paths: set[str] = set()
    for row in manifest["loci"]:
        path = str(row["source"]["path"])
        if reviews[row["id"]].get("status") not in VALID_REVIEW or path in seen_paths:
            continue
        grouped.setdefault(row["semantic_class"], []).append(row)
        seen_paths.add(path)
    result = []
    for semantic_class in sorted(grouped):
        for row in sorted(grouped[semantic_class], key=lambda value: value["id"])[:per_class]:
            result.append({
                "id": row["id"], "semantic_class": semantic_class,
                "path": str(row["source"]["path"]),
            })
    return result


def _percentile(values: list[float], q: float) -> float:
    return float(np.quantile(np.asarray(values, np.float64), q, method="higher"))


def build_report(*, per_class: int = 2) -> dict:
    model_identity = runtime_model_identity()
    input_identity = real_locus_input_identity(CORPUS)
    cases = _cases(per_class)
    modes = (QualityMode.FAST, QualityMode.BALANCED, QualityMode.MAX)
    mode_rows = {}
    with tempfile.TemporaryDirectory(prefix="pcdc-exp10-") as directory:
        root = Path(directory)
        for mode in modes:
            rows = []
            with PersistentCompilerService(
                evidence_cache=EvidenceCache(root / mode.value / "evidence"),
                recycle_after=8,
            ) as service:
                for case in cases:
                    started = time.perf_counter()
                    try:
                        result = service.compile(case["path"], mode=mode)
                        result.validate()
                        elapsed_ms = (time.perf_counter() - started) * 1000.0
                        rows.append({
                            **case, "status": "ok", "error": None,
                            "elapsed_ms": elapsed_ms,
                            "runtime_elapsed_ms": result.elapsed_ms,
                            "best_stage": result.best_stage,
                            "deadline_exceeded": result.deadline_exceeded,
                            "selected_macros": len(result.solution.selected_ids),
                            "typed_rois": result.contract.typed_rois,
                            "typed_columns": result.contract.generated_typed_columns,
                            "native_backend": result.contract.native_backend,
                            "profile": result.stage_profile["by_stage"],
                            "warnings": list(result.warnings),
                        })
                        del result
                    except Exception as error:
                        rows.append({
                            **case, "status": "error",
                            "error": f"{type(error).__name__}: {error}",
                            "elapsed_ms": (time.perf_counter() - started) * 1000.0,
                        })
                    gc.collect()
            times = [row["elapsed_ms"] for row in rows if row["status"] == "ok"]
            mode_rows[mode.value] = {
                "count": len(rows), "ok": len(times),
                "p50_ms": _percentile(times, 0.50) if times else None,
                "p95_ms": _percentile(times, 0.95) if times else None,
                "max_ms": max(times) if times else None,
                "rows": rows,
            }

    fast = mode_rows["fast"]; balanced = mode_rows["balanced"]; maximum = mode_rows["max"]
    all_ok = all(row["ok"] == row["count"] for row in mode_rows.values())
    gate = {
        "all_requests_valid": all_ok,
        "fast_p50_lt_1s": bool(fast["p50_ms"] is not None and fast["p50_ms"] < 1000.0),
        "fast_p95_lt_2s": bool(fast["p95_ms"] is not None and fast["p95_ms"] < 2000.0),
        "balanced_p50_lt_2s": bool(
            balanced["p50_ms"] is not None and balanced["p50_ms"] < 2000.0
        ),
        "balanced_p95_lt_5s": bool(
            balanced["p95_ms"] is not None and balanced["p95_ms"] < 5000.0
        ),
        "max_has_no_minute_tail": bool(
            maximum["max_ms"] is not None and maximum["max_ms"] < 60000.0
        ),
        "native_backend_active": all(
            row.get("native_backend", {}).get("language") == "rust"
            for mode in mode_rows.values() for row in mode["rows"]
            if row["status"] == "ok"
        ),
    }
    passed = all(gate.values())
    return {
        "schema": "pcdc-experiment10/v1",
        "input_identity": input_identity,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed", "gate_pass": passed,
        "measurement": (
            "cold content-addressed REIR per mode; warm persistent ProposalNet; "
            "end-to-end compile through best valid anytime checkpoint"
        ),
        "runtime_model_identity": model_identity,
        "case_count": len(cases), "gate": gate, "modes": mode_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--per-class", type=int, default=2)
    args = parser.parse_args()
    report = bind_report(build_report(per_class=max(1, args.per_class)))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    print(json.dumps({
        "status": report["status"], "gate": report["gate"],
        "out": str(args.out),
        "summary": {
            mode: {key: value for key, value in rows.items() if key != "rows"}
            for mode, rows in report["modes"].items()
        },
    }, indent=2))


if __name__ == "__main__":
    main()

"""Compile the immutable Scene Engine validation ledger.

This script does not run or tune the vectorizer.  It only joins already-written
benchmark snapshots, per-item DecisionTrace/resource reports, and explicit
resource failures into one auditable campaign artifact.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from benchmark_vai import aggregate


ROOT = Path(__file__).resolve().parent
BENCHMARKS = ROOT / "benchmarks"
DEFAULT_CAMPAIGN = BENCHMARKS / "scene_validation" / "33bc0d63e4b82734"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    rows = sorted(float(value) for value in values)
    position = (len(rows) - 1) * percentile / 100.0
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return rows[lower]
    weight = position - lower
    return rows[lower] * (1.0 - weight) + rows[upper] * weight


def _report_for(stem: str) -> tuple[Path | None, dict | None]:
    root = BENCHMARKS / "vai_work" / "scene" / stem
    reports = sorted(root.glob("*/report.json"), key=lambda item: item.stat().st_mtime,
                     reverse=True)
    if not reports:
        return None, None
    return reports[0], _read(reports[0])


def _resource_row(stem: str) -> dict:
    report_path, report = _report_for(stem)
    if report is None or report_path is None:
        return {"status": "missing-report"}
    trace_path = report_path.parent / str(report.get("artifacts", {}).get(
        "trace", "decision_trace.json"))
    trace = _read(trace_path) if trace_path.is_file() else {}
    resource = report.get("resource", {})
    return {
        "status": "completed",
        "report": str(report_path.relative_to(ROOT)),
        "wall_seconds": resource.get("wall_seconds"),
        "tracemalloc_peak_mib": round(float(resource.get("tracemalloc_peak_bytes", 0))
                                      / (1024.0 * 1024.0), 3),
        "regions": report.get("regions"),
        "primitives": report.get("rendered_primitive_count"),
        "templates": report.get("templates", {}),
        "render_nll": report.get("render_nll"),
        "render_map_nll": report.get("render_map_nll"),
        "abstained": bool(report.get("abstained", False)),
        "stage_seconds": trace.get("stage_seconds", {}),
    }


def compile_ledger(campaign_root: Path, snapshot_paths: list[Path]) -> dict:
    snapshots = [_read(path) for path in snapshot_paths if path.is_file()]
    rows_by_stem: dict[str, dict] = {}
    duplicate_stems: list[str] = []
    for snapshot in snapshots:
        for row in snapshot.get("rows", []):
            stem = str(row["stem"])
            if stem in rows_by_stem:
                duplicate_stems.append(stem)
            rows_by_stem[stem] = row

    failures_path = campaign_root / "resource_failures.json"
    failures = _read(failures_path).get("failures", []) if failures_path.is_file() else []
    failure_stems = {str(item["stem"]) for item in failures}
    item_rows = []
    for stem, metrics in rows_by_stem.items():
        ours = metrics.get("ours", {})
        vai = metrics.get("vai", {})
        resource = _resource_row(stem)
        ours_catastrophic = bool(ours.get("any_counter_failure")) or float(
            ours.get("catastrophic_locus_rate") or 0) > 0
        vai_catastrophic = bool(vai.get("any_counter_failure")) or float(
            vai.get("catastrophic_locus_rate") or 0) > 0
        item_rows.append({
            "stem": stem,
            "conditions": metrics.get("conditions", {}),
            "quality": {
                "ours": ours,
                "vai": vai,
                "ours_catastrophic": ours_catastrophic,
                "vai_catastrophic": vai_catastrophic,
            },
            "resource": resource,
        })

    wall = [float(item["resource"]["wall_seconds"]) for item in item_rows
            if item["resource"].get("wall_seconds") is not None]
    stage_totals: defaultdict[str, float] = defaultdict(float)
    templates: Counter[str] = Counter()
    for item in item_rows:
        for stage, seconds in item["resource"].get("stage_seconds", {}).items():
            stage_totals[str(stage)] += float(seconds)
        templates.update(item["resource"].get("templates", {}))

    complete_quality_rows = list(rows_by_stem.values())
    quality = aggregate(complete_quality_rows) if complete_quality_rows else {"n": 0}
    completed = len(item_rows)
    expected = 50
    resource_failure_count = len(failures)
    missing = max(0, expected - completed - resource_failure_count)
    ours_catastrophic = sum(item["quality"]["ours_catastrophic"] for item in item_rows)
    vai_catastrophic = sum(item["quality"]["vai_catastrophic"] for item in item_rows)
    abstained = sum(bool(item["resource"].get("abstained")) for item in item_rows)

    performance = {
        "completed_with_reports": len(wall),
        "wall_seconds_p50": round(float(_percentile(wall, 50) or 0), 3),
        "wall_seconds_p95": round(float(_percentile(wall, 95) or 0), 3),
        "wall_seconds_max": round(max(wall), 3) if wall else None,
        "over_120_seconds": sum(value > 120 for value in wall),
        "over_1200_seconds": sum(value > 1200 for value in wall),
        "abstained": abstained,
        "resource_failures": failures,
        "stage_seconds_total": dict(sorted(stage_totals.items(),
                                           key=lambda row: row[1], reverse=True)),
        "template_totals": dict(templates.most_common()),
    }
    gates = {
        "coverage_50": {
            "passed": completed + resource_failure_count == expected and missing == 0,
            "completed": completed,
            "resource_failures": resource_failure_count,
            "missing": missing,
        },
        "no_resource_exhaustion": {"passed": resource_failure_count == 0},
        "no_ours_catastrophic_items": {
            "passed": ours_catastrophic == 0,
            "count_completed": ours_catastrophic,
        },
        "performance_under_120_seconds": {
            "passed": bool(wall) and max(wall) <= 120,
            "max_seconds": performance["wall_seconds_max"],
        },
        "external_ink_iou_population_win": {
            "passed": quality.get("wins", {}).get("ink_iou", "0+").startswith("25+"),
            "observed": quality.get("wins", {}).get("ink_iou"),
            "note": "Final denominator is available only after all 50 cases are accounted for.",
        },
    }
    promotable = all(bool(gate.get("passed")) for gate in gates.values())
    return {
        "schema": "vice-scene-freeze-ledger/1",
        "freeze_hash": "33bc0d63e4b82734bcb5349f5d19385ac16b0fbdc6e31074814728c90238758f",
        "policy": "record-only after BUILD_FREEZE; no tuning represented here",
        "snapshot_inputs": [str(path.relative_to(ROOT)) for path in snapshot_paths
                            if path.is_file()],
        "duplicate_stems": sorted(set(duplicate_stems)),
        "coverage": {"expected": expected, "completed": completed,
                     "resource_failures": resource_failure_count, "missing": missing},
        "quality_aggregate_completed": quality,
        "catastrophic_completed": {"ours": ours_catastrophic, "vai": vai_catastrophic,
                                   "vai_new_tail_metrics_available": any(
                                       item["quality"]["vai"].get("catastrophic_locus_rate") is not None
                                       for item in item_rows)},
        "performance": performance,
        "gates": gates,
        "promotion": {"passed": promotable,
                      "decision": "PROMOTE" if promotable else "DO_NOT_PROMOTE"},
        "items": sorted(item_rows, key=lambda item: item["stem"]),
        "explicit_failures": failures,
        "failed_stems": sorted(failure_stems),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument("--snapshot", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    snapshots = args.snapshot or [
        BENCHMARKS / "scene_vai50_freeze_first28.json",
        BENCHMARKS / "scene_vai50_freeze_remaining.json",
    ]
    output = args.output or args.campaign_root / "vai50_freeze_ledger.json"
    ledger = compile_ledger(args.campaign_root, snapshots)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    coverage = ledger["coverage"]
    print(f"ledger={output}")
    print(f"coverage={coverage['completed']} completed + "
          f"{coverage['resource_failures']} resource failure + {coverage['missing']} missing")
    print(f"promotion={ledger['promotion']['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

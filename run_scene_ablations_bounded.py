"""Run every frozen Scene module ablation with equal per-item resource budgets."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import benchmark_vai
from run_scene_vai50_bounded import _run_monitored
from validate_scene_campaign import ABLATIONS
from vice_scene.freeze import verify_freeze


ROOT = Path(__file__).resolve().parent
CAMPAIGN = ROOT / "benchmarks" / "scene_validation" / "33bc0d63e4b82734"
FREEZE = ROOT / "BUILD_FREEZE.json"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False,
                                    sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _payload(rows: list[dict], stems: tuple[str, ...], budget: float) -> dict:
    counts = {}
    for row in rows:
        status = str(row.get("status"))
        counts[status] = counts.get(status, 0) + 1
    baseline = {row["stem"]: row for row in rows if row["variant"] == "baseline"}
    enriched = []
    for row in rows:
        output = dict(row)
        base = baseline.get(row["stem"])
        if (base and row.get("render_nll") is not None
                and base.get("render_nll") is not None):
            output["render_nll_delta"] = round(
                float(row["render_nll"]) - float(base["render_nll"]), 8)
        enriched.append(output)
    return {
        "schema": "vice-scene-bounded-ablation-matrix/1",
        "freeze_hash": json.loads(FREEZE.read_text(encoding="utf-8"))["freeze_hash"],
        "budget_seconds": budget,
        "stems": list(stems),
        "variants": {name: list(modules) for name, modules in ABLATIONS.items()},
        "expected": len(stems) * len(ABLATIONS),
        "accounted": len(rows),
        "status_counts": counts,
        "rows": enriched,
        "promotion_gate": "PASS" if (len(rows) == len(stems) * len(ABLATIONS)
                                      and counts == {"completed": len(rows)}) else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-seconds", type=float, default=60.0)
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()
    okay, errors = verify_freeze(FREEZE)
    if not okay:
        raise SystemExit("BUILD_FREEZE invalid: " + "; ".join(errors))

    stems = tuple(benchmark_vai.frozen_stems(args.count))
    root = CAMPAIGN / "ablations_bounded"
    report_path = root / "ablation_matrix.json"
    prior = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    rows_by_key = {(row["variant"], row["stem"]): row
                   for row in prior.get("rows", [])}
    sequence = 0
    expected = len(stems) * len(ABLATIONS)
    for variant, modules in ABLATIONS.items():
        for stem in stems:
            sequence += 1
            key = (variant, stem)
            if key in rows_by_key:
                print(f"[{sequence:02}/{expected}] {variant}:{stem}: resume "
                      f"{rows_by_key[key]['status']}", flush=True)
                continue
            source = benchmark_vai.find_source(stem)
            if source is None:
                rows_by_key[key] = {"variant": variant, "ablations": list(modules),
                                    "stem": stem, "status": "missing-source"}
                _write(report_path, _payload(list(rows_by_key.values()), stems,
                                             args.budget_seconds))
                continue
            destination = root / variant / stem
            command = [sys.executable, "-X", "utf8", "-m", "vice_scene",
                       str(source), "--out", str(destination)]
            for module in modules:
                command.extend(("--ablate", module))
            completed = _run_monitored(command, args.budget_seconds)
            elapsed = float(completed["seconds"])
            if not completed["timed_out"]:
                status = "completed" if completed["return_code"] == 0 else "benchmark-error"
                error = None if completed["return_code"] == 0 else (
                    completed["stderr"] or completed["stdout"])[-500:]
            else:
                status, error = "timeout", f"budget {args.budget_seconds:g}s exceeded"
            report = destination / source.stem / "report.json"
            row = {"variant": variant, "ablations": list(modules), "stem": stem,
                   "status": status, "attempt_seconds": round(elapsed, 3),
                   "peak_rss_mib": round(float(completed["peak_rss_mib"]), 3)}
            if error:
                row["error"] = error
            if status == "completed" and report.is_file():
                item = json.loads(report.read_text(encoding="utf-8"))
                row.update({
                    "render_nll": item.get("render_nll"),
                    "regions": item.get("regions"),
                    "primitives": item.get("rendered_primitive_count"),
                    "engine_wall_seconds": item.get("resource", {}).get("wall_seconds"),
                    "abstained": item.get("abstained"),
                    "report": str(report.relative_to(ROOT)),
                })
            elif status == "completed":
                row.update({"status": "invalid-output", "error": "report.json missing"})
            rows_by_key[key] = row
            _write(report_path, _payload(list(rows_by_key.values()), stems,
                                         args.budget_seconds))
            print(f"[{sequence:02}/{expected}] {variant}:{stem}: {row['status']} "
                  f"{elapsed:.1f}s", flush=True)

    payload = _payload(list(rows_by_key.values()), stems, args.budget_seconds)
    _write(report_path, payload)
    print(f"report={report_path}")
    print(f"accounted={payload['accounted']}/{payload['expected']} "
          f"statuses={payload['status_counts']}")
    return 0 if payload["accounted"] == payload["expected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

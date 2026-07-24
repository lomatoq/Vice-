"""Finish the frozen VAI50 ledger with a strict per-item wall-time budget.

Every requested stem is either represented by a completed metric row or by an
explicit timeout/error in the campaign resource-failure artifact.  This avoids
silently dropping hard cases and prevents one failed build from monopolizing the
machine for hours.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
import psutil

import benchmark_vai
from vice_scene.freeze import verify_freeze


ROOT = Path(__file__).resolve().parent
BENCHMARKS = ROOT / "benchmarks"
CAMPAIGN = BENCHMARKS / "scene_validation" / "33bc0d63e4b82734"
FREEZE = ROOT / "BUILD_FREEZE.json"
STEMS = (
    "icon_group_3_2", "icon_group_1", "icon_group_6", "icon_group_4_47",
    "red7slots_512", "icon_group_4_13", "icon_group_2_1", "icon_group_4",
    "icon_group_4_50", "icon_group_4_41", "icon_group_4_4", "icon_group_4_52",
    "icon_group_4_61", "icon_group_4_34", "icon_group_2_5", "icon_group_4_78",
    "platipus_512", "icon_group_3_3", "icon_group_4_1", "icon_group_4_70",
    "icon_group",
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _failure(stem: str, status: str, seconds: float, detail: str,
             peak_rss_mib: float | None = None) -> dict:
    source = benchmark_vai.find_source(stem)
    size = list(Image.open(source).size) if source and source.is_file() else None
    row = {
        "stem": stem,
        "source": str(source) if source else None,
        "source_size": size,
        "status": status,
        "elapsed_seconds_lower_bound": round(float(seconds), 3),
        "guard_action": detail,
        "completed_output": False,
        "promotion_gate": "FAIL",
    }
    if peak_rss_mib is not None:
        row["worker_peak_working_set_gib"] = round(float(peak_rss_mib) / 1024.0, 3)
    return row


def _run_monitored(command: list[str], budget_seconds: float) -> dict:
    started = time.monotonic()
    process = subprocess.Popen(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    tracked = psutil.Process(process.pid)
    peak_mib = 0.0
    timed_out = False
    while process.poll() is None:
        rss = 0
        try:
            members = [tracked] + tracked.children(recursive=True)
            for member in members:
                try:
                    rss += int(member.memory_info().rss)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        peak_mib = max(peak_mib, rss / (1024.0 * 1024.0))
        if time.monotonic() - started >= budget_seconds:
            timed_out = True
            try:
                for child in tracked.children(recursive=True):
                    try:
                        child.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            process.kill()
            break
        time.sleep(.2)
    stdout, stderr = process.communicate()
    return {
        "return_code": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "seconds": time.monotonic() - started,
        "timed_out": timed_out,
        "peak_rss_mib": peak_mib,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-seconds", type=float, default=120.0)
    parser.add_argument("--output", type=Path,
                        default=BENCHMARKS / "scene_vai50_freeze_remaining.json")
    args = parser.parse_args()
    okay, errors = verify_freeze(FREEZE)
    if not okay:
        raise SystemExit("BUILD_FREEZE invalid: " + "; ".join(errors))

    failure_path = CAMPAIGN / "resource_failures.json"
    failure_payload = _read(failure_path)
    failures = failure_payload.setdefault("failures", [])
    failed_stems = {str(row["stem"]) for row in failures}
    work = CAMPAIGN / "vai50_bounded"
    work.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    attempts: list[dict] = []
    for index, stem in enumerate(STEMS, 1):
        snapshot = work / f"{index:02}_{stem}.json"
        if snapshot.is_file():
            cached_rows = _read(snapshot).get("rows", [])
            if len(cached_rows) == 1 and cached_rows[0].get("stem") == stem:
                rows.extend(cached_rows)
                attempts.append({"stem": stem, "status": "resumed-completed",
                                 "snapshot": str(snapshot)})
                print(f"[{index:02}/{len(STEMS)}] {stem}: resumed completed snapshot",
                      flush=True)
                continue
        if stem in failed_stems:
            print(f"[{index:02}/{len(STEMS)}] {stem}: recorded resource failure", flush=True)
            attempts.append({"stem": stem, "status": "recorded-failure"})
            continue
        command = [
            sys.executable, "-X", "utf8", str(ROOT / "benchmark_vai.py"),
            "--mode", "scene", "--stems", stem, "--reuse",
            "--snapshot", str(snapshot.relative_to(BENCHMARKS)),
            "--vai-cache", "vai_snapshot_production_fresh50_final.json",
        ]
        completed = _run_monitored(command, args.budget_seconds)
        elapsed = float(completed["seconds"])
        if completed["timed_out"]:
            failure = _failure(
                stem, "timeout", elapsed,
                f"per-item frozen validation budget {args.budget_seconds:g}s exceeded; "
                "subprocess killed and accounted, not skipped",
                completed["peak_rss_mib"],
            )
            failures.append(failure)
            failed_stems.add(stem)
            _write(failure_path, failure_payload)
            attempts.append({"stem": stem, "status": "timeout",
                             "seconds": round(elapsed, 3)})
            print(f"[{index:02}/{len(STEMS)}] {stem}: TIMEOUT {elapsed:.1f}s", flush=True)
            continue

        if completed["return_code"] != 0 or not snapshot.is_file():
            detail = (completed["stderr"] or completed["stdout"] or "no snapshot")[-1000:]
            failure = _failure(stem, "benchmark-error", elapsed,
                               f"return code {completed['return_code']}: {detail}",
                               completed["peak_rss_mib"])
            failures.append(failure)
            failed_stems.add(stem)
            _write(failure_path, failure_payload)
            attempts.append({"stem": stem, "status": "benchmark-error",
                             "seconds": round(elapsed, 3),
                             "return_code": completed["return_code"],
                             "peak_rss_mib": round(completed["peak_rss_mib"], 3)})
            print(f"[{index:02}/{len(STEMS)}] {stem}: ERROR rc={completed['return_code']}",
                  flush=True)
            continue

        snapshot_payload = _read(snapshot)
        item_rows = snapshot_payload.get("rows", [])
        if len(item_rows) != 1 or item_rows[0].get("stem") != stem:
            failure = _failure(stem, "invalid-snapshot", elapsed,
                               "per-item benchmark did not return exactly the requested stem")
            failures.append(failure)
            failed_stems.add(stem)
            _write(failure_path, failure_payload)
            attempts.append({"stem": stem, "status": "invalid-snapshot",
                             "seconds": round(elapsed, 3)})
            print(f"[{index:02}/{len(STEMS)}] {stem}: INVALID SNAPSHOT", flush=True)
            continue
        rows.extend(item_rows)
        attempts.append({"stem": stem, "status": "completed",
                         "seconds": round(elapsed, 3), "snapshot": str(snapshot),
                         "peak_rss_mib": round(completed["peak_rss_mib"], 3)})
        print(f"[{index:02}/{len(STEMS)}] {stem}: completed {elapsed:.1f}s", flush=True)

    payload = {
        "mode": "scene",
        "schema": "vice-scene-bounded-vai50-continuation/1",
        "freeze_hash": _read(FREEZE)["freeze_hash"],
        "budget_seconds": args.budget_seconds,
        "requested_stems": list(STEMS),
        "rows": rows,
        "aggregate": benchmark_vai.aggregate(rows),
        "attempts": attempts,
        "resource_failures": [row for row in failures if row.get("stem") in STEMS],
    }
    _write(args.output, payload)
    _write(failure_path, failure_payload)
    print(f"output={args.output}")
    print(f"completed={len(rows)} failed={len(payload['resource_failures'])} "
          f"accounted={len(rows) + len(payload['resource_failures'])}/{len(STEMS)}")
    return 0 if len(rows) + len(payload["resource_failures"]) == len(STEMS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

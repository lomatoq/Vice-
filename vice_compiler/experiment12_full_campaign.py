"""One resumable, failure-accounted Phase-12 PCDC campaign.

The campaign never silently drops a difficult item.  Every requested VAI50 or
Challenge115 case ends as an immutable success, timeout, crash, or meter error
row tied to the compiler fingerprint that produced it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

import benchmark_vai

from .build_freeze import DEFAULT_OUT as FREEZE_PATH
from .build_freeze import verify_freeze
from .build_identity import (
    compiler_source_sha256,
    evaluation_source_sha256,
    native_runtime_identity,
    runtime_model_identity,
)

PROJECT = Path(__file__).resolve().parents[1]
PICTURES = Path(r"C:/Users/nirrt/Toolset/v-ice pictures")
CHALLENGE = PICTURES / "challenge_pack"
DEFAULT_ROOT = PROJECT / "benchmarks" / "pcdc_experiment12"
PROPOSAL_REAL_REPORT = PROJECT / "benchmarks" / "pcdc_experiment9" / "report.json"
BLIND_VAI_REVIEW = DEFAULT_ROOT / "blind_vai_court" / "review.json"


LOWER_BETTER = (
    "mae", "rmse", "hausdorff95", "local_de_max", "census_errors",
    "catastrophic_locus_rate", "worst_locus_severity", "boundary_cvar10",
    "detail_de_cvar10", "kinks_per_100px", "g2_steps", "wobble",
    "micro_segs", "segments",
)
HIGHER_BETTER = ("ink_iou", "ssim", "boundary_f")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _compiler_fingerprint(
    candidate_checkpoint: Path | None = None,
    candidate_manifest: Path | None = None,
) -> str:
    digest = hashlib.sha256(b"pcdc-phase12-fingerprint/v2\0")
    digest.update(compiler_source_sha256().encode("ascii"))
    digest.update(evaluation_source_sha256(__file__).encode("ascii"))
    digest.update(native_runtime_identity()["sha256"].encode("ascii"))
    # These modules define the locked meter itself rather than compiler
    # output.  Changing them must invalidate resumable snapshots just as a
    # compiler edit does, otherwise old and new scores can coexist in one run.
    for path in (
        PROJECT / "benchmark_vai.py",
        PROJECT / "subpixel_mininet.py",
        PROJECT / "vectorize_papers.py",
    ):
        digest.update(path.name.encode("utf-8")); digest.update(b"\0")
        digest.update(path.read_bytes()); digest.update(b"\0")
    model_identity = runtime_model_identity(
        proposal_checkpoint=candidate_checkpoint,
        proposal_manifest=candidate_manifest,
    )
    digest.update(model_identity["sha256"].encode("ascii"))
    return digest.hexdigest()


def _read(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        "utf-8",
    )
    temporary.replace(path)


def _cases(suite: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if suite in {"vai50", "all"}:
        frozen = _read(
            PROJECT / "benchmarks/vai_snapshot_production_fresh50_final.json"
        )
        for position, frozen_row in enumerate(frozen["rows"]):
            stem = str(frozen_row["stem"])
            source = benchmark_vai.find_source(stem)
            rows.append({
                "id": f"vai50-{position:02d}-{stem}", "suite": "vai50",
                "position": position, "stem": stem,
                "category": frozen_row.get("conditions", {}).get("scale"),
                "source": str(source) if source is not None else None,
                "reference": str(PICTURES / "vai" / f"{stem}_vai.svg"),
                "reference_metrics": frozen_row.get("vai"),
            })
    if suite in {"challenge115", "all"}:
        layout = _read(CHALLENGE / "plates/plate_layout.json")
        frozen = _read(CHALLENGE / "eval/report_blind_FROZEN.json")
        by_item = {int(row["item"]): row for row in frozen["rows"]}
        for item in range(115):
            rows.append({
                "id": f"challenge115-{item:03d}", "suite": "challenge115",
                "position": item, "stem": f"item{item:03d}",
                "category": layout[item].get("category"),
                "source": str(CHALLENGE / "eval/crops" / f"item{item:03d}.png"),
                "reference": str(
                    CHALLENGE / "eval/items" / f"item{item:03d}_vai.svg"
                ),
                "reference_metrics": by_item[item].get("vai"),
            })
    return rows


def _run_monitored(command: list[str], timeout_s: float) -> dict[str, Any]:
    started = time.perf_counter()
    # Windows anonymous pipes are small enough that the worker's full JSON
    # report can fill stdout and deadlock before the parent calls communicate.
    # Seekable temporary files preserve monitoring without that false timeout.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout_file, \
            tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_file:
        process = subprocess.Popen(
            command, cwd=PROJECT, stdout=stdout_file, stderr=stderr_file,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        root = psutil.Process(process.pid); peak = 0
        timed_out = False
        while process.poll() is None:
            try:
                members = [root, *root.children(recursive=True)]
                peak = max(peak, sum(
                    member.memory_info().rss for member in members
                    if member.is_running()
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if time.perf_counter() - started >= timeout_s:
                timed_out = True
                try:
                    for child in root.children(recursive=True):
                        child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                process.kill()
                break
            time.sleep(0.1)
        process.wait()
        stdout_file.seek(0); stderr_file.seek(0)
        stdout, stderr = stdout_file.read(), stderr_file.read()
    return {
        "returncode": process.returncode, "stdout": stdout, "stderr": stderr,
        "wall_ms": (time.perf_counter() - started) * 1000.0,
        "peak_working_set_mib": peak / (1024.0 * 1024.0),
        "timed_out": timed_out,
    }


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    low = int(position); high = min(len(ordered) - 1, low + 1)
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _numeric(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for metric in (*LOWER_BETTER, *HIGHER_BETTER):
        pairs = []
        for row in rows:
            ours = _numeric(row.get("ours", {}).get(metric))
            reference = _numeric(row.get("reference_metrics", {}).get(metric))
            if ours is not None and reference is not None:
                pairs.append((ours, reference))
        if not pairs:
            continue
        lower = metric in LOWER_BETTER
        wins = sum((ours < ref) if lower else (ours > ref) for ours, ref in pairs)
        ties = sum(abs(ours - ref) <= 1e-12 for ours, ref in pairs)
        result[metric] = {
            "count": len(pairs), "ours_median": statistics.median(x for x, _ in pairs),
            "reference_median": statistics.median(y for _, y in pairs),
            "median_delta": statistics.median(x - y for x, y in pairs),
            "wins": wins, "ties": ties, "losses": len(pairs) - wins - ties,
        }
    return result


def _proposal_calibration_evidence(
    path: Path = PROPOSAL_REAL_REPORT,
) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "present": False, "passed": False}
    report = _read(path)
    current_evaluator = evaluation_source_sha256(
        "vice_compiler/experiment9_proposal_calibration.py",
    )
    coverage = report.get("test_conformal_coverage_by_family", {})
    required = tuple(report.get("conformal_required_families") or (
        "text_line", "whole_shape",
    ))
    non_vacuous = not report.get("conformal_vacuous_classes", ["missing"])
    label_contract_version = str(report.get("label_contract_version", ""))
    runtime_admission = report.get("runtime_conformal_admission") or {}
    runtime_passed = bool(
        runtime_admission.get("contract")
        == "exact-production-union+family-prefix+global-cap/v1"
        and runtime_admission.get("exact_runtime_rule") is True
        and runtime_admission.get(
            "all_quality_modes_coverage_ge_99pct"
        ) is True
    )
    passed = bool(
        report.get("gate_pass") is True
        and report.get("evaluation_source_sha256") == current_evaluator
        and non_vacuous
        and all(float(coverage.get(family, 0.0)) >= 0.99 for family in required)
        and (runtime_passed or not label_contract_version.endswith("/v4"))
    )
    return {
        "path": str(path), "present": True, "passed": passed,
        "gate_pass": bool(report.get("gate_pass")),
        "evaluation_hash_current": (
            report.get("evaluation_source_sha256") == current_evaluator
        ),
        "current_evaluation_source_sha256": current_evaluator,
        "checkpoint_sha256": report.get("checkpoint_sha256"),
        "required_families": required, "coverage": coverage,
        "non_vacuous": non_vacuous,
        "runtime_fast_balanced_max_passed": runtime_passed,
    }


def _bound_proposal_calibration_evidence(
    proposal_evaluation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Read calibration bound to the exact candidate evaluation manifest."""
    if proposal_evaluation is None:
        return _proposal_calibration_evidence()
    try:
        manifest_path = Path(str(proposal_evaluation["manifest"]))
        if _sha256(manifest_path) != str(
            proposal_evaluation.get("manifest_sha256", "")
        ).lower():
            raise ValueError("candidate evaluation manifest checksum mismatch")
        evaluation = _read(manifest_path)
        report_path = Path(str(evaluation["real_report"]))
        if _sha256(report_path) != str(
            evaluation.get("real_report_sha256", "")
        ).lower():
            raise ValueError("candidate calibration report checksum mismatch")
        report = _read(report_path)
        if str(report.get("checkpoint_sha256", "")).lower() != str(
            proposal_evaluation.get("checkpoint_sha256", "")
        ).lower():
            raise ValueError("candidate calibration belongs to another checkpoint")
    except (KeyError, OSError, ValueError, TypeError) as error:
        return {
            "present": False, "passed": False,
            "error": str(error), "candidate_bound": False,
        }
    return {
        **_proposal_calibration_evidence(report_path),
        "candidate_bound": True,
    }


def _blind_parity_evidence(path: Path = BLIND_VAI_REVIEW) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "present": False, "passed": False}
    review = _read(path)
    if review.get("schema") != "pcdc-phase12-blind-vai-court/v1":
        return {
            "path": str(path), "present": True, "passed": False,
            "error": "unsupported review schema",
        }
    answers = list(review.get("answers", {}).values())
    expected = int(review.get("expected_count", 0))
    valid_choices = {"ours", "vai", "tie"}
    complete = bool(
        review.get("locked") is True and expected > 0
        and len(answers) == expected
        and all(row.get("choice") in valid_choices for row in answers)
    )
    by_slice: dict[str, list[dict]] = {}
    for answer in answers:
        by_slice.setdefault(str(answer.get("slice", "unknown")), []).append(answer)

    def score(rows: list[dict]) -> float:
        if not rows:
            return 0.0
        return sum(
            1.0 if row["choice"] == "ours"
            else 0.5 if row["choice"] == "tie" else 0.0
            for row in rows
        ) / len(rows)

    parity = score(answers)
    slice_scores = {name: score(rows) for name, rows in by_slice.items()}
    display = review.get("display_contract", {})
    display_valid = bool(
        display.get("live_svg") is True
        and display.get("equal_viewport") is True
        and display.get("zoom_pan") is True
        and display.get("raster_downsample_forbidden") is True
    )
    passed = bool(
        complete and display_valid and parity >= 0.50
        and slice_scores and min(slice_scores.values()) >= 0.45
    )
    return {
        "path": str(path), "present": True, "passed": passed,
        "complete": complete, "display_valid": display_valid,
        "expected_count": expected, "answer_count": len(answers),
        "parity_score": parity, "slice_scores": slice_scores,
    }


def _human_evidence() -> dict[str, Any]:
    certificate = _read(PROJECT / "datasets/pcdc_certificate_pairs_v1/review.json")
    text = _read(PROJECT / "datasets/pcdc_textline_pairs_v1/review.json")
    legacy = _read(
        PROJECT / "benchmarks/scene_validation/33bc0d63e4b82734/"
        "LEGACY_BEST_HUMAN_COURT.json"
    )
    blind = _blind_parity_evidence()
    return {
        "certificate_answers": len(certificate.get("answers", {})),
        "textline_answers": len(text.get("answers", {})),
        "legacy_vai_court": legacy,
        "phase12_blind_vai_court": blind,
        "phase12_blind_vai_court_complete": bool(blind.get("complete")),
        "note": (
            "Existing VAI court is diagnostic-only and its display contract was "
            "rejected; only the locked live-SVG Phase-12 court can promote."
        ),
    }


def _aggregate(
    cases: list[dict[str, Any]], rows: list[dict[str, Any]],
    *, fingerprint: str, freeze: dict[str, Any] | None,
    proposal_evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    okay = [row for row in rows if row.get("status") == "ok"]
    runtime_ms = [float(row["runtime"]["elapsed_ms"]) for row in okay]
    worker_ms = [float(row.get("worker_wall_ms", row.get("wall_ms", 0.0))) for row in okay]
    topology_failures = [
        row["id"] for row in okay
        if int(row.get("ours", {}).get("census_errors") or 0) != 0
        or bool(row.get("ours", {}).get("any_counter_failure"))
    ]
    stage_counts = Counter(str(row.get("best_stage")) for row in okay)
    deterministic = all(bool(row.get("deterministic_export")) for row in okay)
    full_canonical = (
        sum(row["suite"] == "vai50" for row in cases) == 50
        and sum(row["suite"] == "challenge115" for row in cases) == 115
    )
    speed = {
        "runtime_p50_ms": _percentile(runtime_ms, 0.50),
        "runtime_p95_ms": _percentile(runtime_ms, 0.95),
        "runtime_max_ms": max(runtime_ms) if runtime_ms else None,
        "metered_worker_p50_ms": _percentile(worker_ms, 0.50),
        "peak_working_set_mib": max(
            (float(row.get("peak_working_set_mib", 0.0)) for row in okay),
            default=None,
        ),
    }
    speed_pass = bool(
        speed["runtime_p50_ms"] is not None
        and speed["runtime_p50_ms"] <= 2000.0
        and speed["runtime_p95_ms"] <= 5000.0
        and speed["runtime_max_ms"] <= 15000.0
    )
    proposal_calibration = _bound_proposal_calibration_evidence(
        proposal_evaluation,
    )
    human_evidence = _human_evidence()
    blind = human_evidence["phase12_blind_vai_court"]
    gates = {
        "valid_complete_build_freeze": bool(
            freeze is not None
            and freeze.get("valid") is True
            and freeze.get("complete") is True
        ),
        "canonical_50_plus_115": full_canonical,
        "all_requested_completed": len(okay) == len(cases),
        "zero_timeout_or_error": len(okay) == len(rows) == len(cases),
        "deterministic_export": deterministic and bool(okay),
        "zero_whole_scene_topology_failures": not topology_failures,
        "balanced_speed": speed_pass,
        "non_vacuous_99pct_conformal_calibration": bool(
            proposal_calibration.get("passed")
        ),
        "locked_blind_vai_parity_at_least_50pct": bool(blind.get("passed")),
    }
    return {
        "schema": "pcdc-experiment12/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compiler_fingerprint": fingerprint,
        "evaluation_source_sha256": evaluation_source_sha256(__file__),
        "proposal_evaluation": proposal_evaluation,
        "build_freeze": freeze,
        "requested": len(cases), "completed": len(okay),
        "failures": len(rows) - len(okay),
        "suite_counts": dict(Counter(row["suite"] for row in cases)),
        "stage_counts": dict(stage_counts), "speed": speed,
        "topology_failure_ids": topology_failures,
        "metrics": _metric_summary(okay),
        "proposal_calibration_evidence": proposal_calibration,
        "human_evidence": human_evidence,
        "gates": gates, "promotion_ready": all(gates.values()),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("vai50", "challenge115", "all"), default="all")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--mode", default="balanced")
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    parser.add_argument("--run-id", default="working")
    parser.add_argument("--export-samples", type=int, default=0)
    parser.add_argument("--require-freeze", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--proposal-checkpoint", type=Path)
    parser.add_argument("--proposal-manifest", type=Path)
    parser.add_argument("--candidate-evaluation", action="store_true")
    args = parser.parse_args()

    freeze_summary = None
    if FREEZE_PATH.is_file():
        freeze_payload = _read(FREEZE_PATH)
        valid, errors = verify_freeze(freeze_payload)
        freeze_summary = {
            "path": str(FREEZE_PATH), "valid": valid,
            "complete": bool(freeze_payload.get("complete")),
            "freeze_hash": freeze_payload.get("freeze_hash"), "errors": list(errors),
        }
        if args.require_freeze and not valid:
            raise SystemExit("BUILD_FREEZE invalid: " + "; ".join(errors))
    elif args.require_freeze:
        raise SystemExit("BUILD_FREEZE missing")

    cases = _cases(args.suite)
    if args.limit is not None:
        cases = cases[:max(0, args.limit)]
    if args.candidate_evaluation and not (
        args.proposal_checkpoint is not None and args.proposal_manifest is not None
    ):
        raise SystemExit(
            "--candidate-evaluation requires --proposal-checkpoint and --proposal-manifest"
        )
    candidate_checkpoint = args.proposal_checkpoint if args.candidate_evaluation else None
    candidate_manifest = args.proposal_manifest if args.candidate_evaluation else None
    fingerprint = _compiler_fingerprint(candidate_checkpoint, candidate_manifest)
    proposal_evaluation = None
    if candidate_checkpoint is not None and candidate_manifest is not None:
        proposal_evaluation = {
            "mode": "candidate-evaluation",
            "checkpoint": str(candidate_checkpoint.resolve()),
            "checkpoint_sha256": _sha256(candidate_checkpoint),
            "manifest": str(candidate_manifest.resolve()),
            "manifest_sha256": _sha256(candidate_manifest),
        }
    run_root = DEFAULT_ROOT / "runs" / args.run_id
    item_root = run_root / "items"; snapshot_root = run_root / "snapshots"
    rows = []
    for index, case in enumerate(cases, 1):
        snapshot = snapshot_root / f"{case['id']}.json"
        if snapshot.is_file() and not args.no_resume:
            cached = _read(snapshot)
            if cached.get("compiler_fingerprint") == fingerprint:
                rows.append(cached)
                print(f"[{index}/{len(cases)}] {case['id']}: resumed", flush=True)
                continue
        source = Path(str(case["source"])) if case.get("source") else Path("missing")
        reference = Path(str(case["reference"]))
        if not source.is_file() or not reference.is_file():
            row = {
                **case, "status": "error", "compiler_fingerprint": fingerprint,
                "error": "missing source or reference",
            }
        else:
            output = item_root / case["id"]
            command = [
                sys.executable, "-X", "utf8", "-m",
                "vice_compiler.eval_runtime_item", "--source", str(source),
                "--reference", str(reference), "--output", str(output),
                "--mode", args.mode, "--no-reference-meters",
            ]
            if candidate_checkpoint is not None and candidate_manifest is not None:
                command.extend([
                    "--proposal-checkpoint", str(candidate_checkpoint),
                    "--proposal-manifest", str(candidate_manifest),
                    "--candidate-evaluation",
                ])
            if index <= args.export_samples:
                command.append("--all-exports")
            monitored = _run_monitored(command, args.timeout_seconds)
            if monitored["timed_out"]:
                worker = {"status": "timeout", "error": "worker timeout"}
            else:
                lines = [line for line in monitored["stdout"].splitlines() if line.strip()]
                try:
                    worker = json.loads(lines[-1]) if lines else {
                        "status": "error", "error": "worker emitted no JSON",
                    }
                except json.JSONDecodeError as error:
                    worker = {"status": "error", "error": f"invalid worker JSON: {error}"}
            row = {
                **case, **worker, "reference_metrics": case["reference_metrics"],
                "compiler_fingerprint": fingerprint,
                "worker_wall_ms": monitored["wall_ms"],
                "peak_working_set_mib": monitored["peak_working_set_mib"],
                "worker_returncode": monitored["returncode"],
                "worker_stderr_tail": monitored["stderr"][-2000:],
            }
        _write(snapshot, row); rows.append(row)
        print(
            f"[{index}/{len(cases)}] {case['id']}: {row.get('status')} "
            f"stage={row.get('best_stage')} ms={row.get('worker_wall_ms', 0):.0f}",
            flush=True,
        )
        _write(
            run_root / "report.partial.json",
            _aggregate(
                cases, rows, fingerprint=fingerprint, freeze=freeze_summary,
                proposal_evaluation=proposal_evaluation,
            ),
        )

    report = _aggregate(
        cases, rows, fingerprint=fingerprint, freeze=freeze_summary,
        proposal_evaluation=proposal_evaluation,
    )
    _write(run_root / "report.json", report)
    print(json.dumps({
        "report": str(run_root / "report.json"), "requested": report["requested"],
        "completed": report["completed"], "failures": report["failures"],
        "stage_counts": report["stage_counts"], "speed": report["speed"],
        "gates": report["gates"], "promotion_ready": report["promotion_ready"],
    }, ensure_ascii=False, indent=2))
    return int(report["failures"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())

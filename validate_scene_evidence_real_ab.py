"""Fresh-process real-image A/B gate for a learned evidence candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from vice_scene.neural_evidence import HybridEvidenceModel


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("synthetic_report", type=Path)
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "benchmarks" / "scene_evidence_real_ab_manifest.json")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "benchmarks" / "scene_evidence_real_ab.json")
    parser.add_argument("--work", type=Path,
                        default=ROOT / "benchmarks" / "scene_evidence_real_ab_artifacts")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("schema") != "vice-scene-evidence-real-ab-manifest/1":
        raise ValueError("unsupported real A/B manifest schema")
    synthetic = json.loads(args.synthetic_report.read_text(encoding="utf-8"))
    candidate_hash = hashlib.sha256(args.candidate.read_bytes()).hexdigest()
    if synthetic.get("candidate_sha256") != candidate_hash:
        raise ValueError("synthetic report belongs to a different candidate")
    if not synthetic.get("passed") or not synthetic.get("independent_evaluation_dataset"):
        raise ValueError("a passing manifest-disjoint synthetic report is required")

    args.work.mkdir(parents=True, exist_ok=True)
    rows = []
    failures = []
    with tempfile.TemporaryDirectory(prefix="vice-scene-evidence-stage-") as temp_name:
        staging = Path(temp_name) / "scene_evidence.staging-promoted.pt"
        _write_staging_checkpoint(args.candidate, staging, synthetic)
        for item in manifest.get("items", ()):
            source = Path(item["source"])
            if not source.is_file():
                failures.append(f"missing real A/B source: {source}")
                continue
            row = {"id": item["id"], "source": str(source)}
            for route in ("candidate", "deterministic"):
                output_root = args.work / route
                command = [sys.executable, "-X", "utf8", "-m", "vice_scene",
                           str(source), "--out", str(output_root), "--topology-k", "2"]
                if route == "candidate":
                    command += ["--evidence-checkpoint", str(staging)]
                else:
                    command.append("--deterministic-evidence")
                completed = subprocess.run(
                    command, cwd=ROOT, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=args.timeout,
                    env={**os.environ, "PYTHONUTF8": "1"},
                )
                if completed.returncode != 0:
                    failures.append(
                        f"{item['id']}/{route} failed: "
                        f"{(completed.stderr or completed.stdout)[-500:]}")
                    continue
                row[route] = _measure(source, output_root / source.stem)
            if "candidate" in row and "deterministic" in row:
                item_failures = _gate_item(row, manifest["gates"])
                row["failures"] = item_failures
                failures.extend(f"{item['id']}: {value}" for value in item_failures)
            rows.append(row)

    summary = _summary(rows)
    gates = manifest["gates"]
    if gates.get("require_one_aggregate_win", True) and not _has_aggregate_win(summary):
        failures.append("candidate has no aggregate SSIM/IoU/MAE/catastrophe win")
    payload = {
        "schema": "vice-scene-evidence-real-ab/1",
        "policy": "fresh process per route/item; source rasters only",
        "candidate": str(args.candidate),
        "candidate_sha256": candidate_hash,
        "synthetic_report": str(args.synthetic_report),
        "manifest": str(args.manifest),
        "rows": rows,
        "summary": summary,
        "failures": failures,
        "passed": not failures,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n", encoding="utf-8")
    print("REAL A/B: PASS" if not failures else "REAL A/B: FAIL")
    for row in rows:
        if "candidate" in row and "deterministic" in row:
            print(f"{row['id']}: candidate SSIM={row['candidate']['ssim']:.4f} "
                  f"det={row['deterministic']['ssim']:.4f}; "
                  f"candidate {row['candidate']['wall_seconds']:.2f}s "
                  f"det={row['deterministic']['wall_seconds']:.2f}s")
    for failure in failures:
        print(f"FAIL: {failure}")
    print(f"report -> {args.out}")
    return 0 if not failures else 1


def _write_staging_checkpoint(candidate: Path, staging: Path, synthetic: dict) -> None:
    import torch

    payload = torch.load(candidate, map_location="cpu", weights_only=True)
    if payload.get("schema") != "vice-scene-evidence-checkpoint/1":
        raise ValueError("candidate checkpoint schema mismatch")
    if payload.get("status") != "candidate":
        raise ValueError("real A/B expects the original candidate checkpoint")
    payload["status"] = "promoted"
    payload["routing_version"] = HybridEvidenceModel.routing_version
    canonical = json.dumps(synthetic, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True).encode("utf-8")
    payload["promotion_validation_sha256"] = hashlib.sha256(canonical).hexdigest()
    torch.save(payload, staging)


def _measure(source: Path, output: Path) -> dict:
    import benchmark_vai as benchmark

    svg = output / "03_rebuilt_filled.svg"
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    with Image.open(source) as image:
        width = image.width
    metrics = {}
    metrics.update(benchmark.raster_meters(svg, source))
    metrics.update(benchmark.geometry_meters(svg, width))
    metrics["wall_seconds"] = float(report["resource"]["wall_seconds"])
    metrics["model_version"] = report["extractor_used"]
    return metrics


def _gate_item(row: dict, gates: dict) -> list[str]:
    candidate, baseline = row["candidate"], row["deterministic"]
    failures = []
    if candidate["ssim"] + gates["ssim_tolerance"] < baseline["ssim"]:
        failures.append("SSIM regression")
    if candidate["ink_iou"] + gates["ink_iou_tolerance"] < baseline["ink_iou"]:
        failures.append("ink IoU regression")
    if candidate["mae"] > baseline["mae"] + gates["mae_tolerance"]:
        failures.append("MAE regression")
    if (gates.get("require_no_catastrophe_increase", True)
            and candidate["catastrophic_locus_count"] > baseline["catastrophic_locus_count"]):
        failures.append("catastrophic locus increase")
    latency_limit = (gates["latency_factor"] * baseline["wall_seconds"]
                     + gates["latency_slack_seconds"])
    if candidate["wall_seconds"] > latency_limit:
        failures.append("latency regression")
    return failures


def _summary(rows: list[dict]) -> dict:
    complete = [row for row in rows if "candidate" in row and "deterministic" in row]
    result = {"items": len(complete)}
    for route in ("candidate", "deterministic"):
        result[route] = {
            name: float(np.mean([row[route][name] for row in complete])) if complete else None
            for name in ("ssim", "ink_iou", "mae", "catastrophic_locus_count",
                         "wall_seconds")
        }
    return result


def _has_aggregate_win(summary: dict) -> bool:
    if not summary.get("items"):
        return False
    candidate, baseline = summary["candidate"], summary["deterministic"]
    return bool(candidate["ssim"] > baseline["ssim"] + .001
                or candidate["ink_iou"] > baseline["ink_iou"] + .001
                or candidate["mae"] < baseline["mae"] - .1
                or candidate["catastrophic_locus_count"]
                < baseline["catastrophic_locus_count"])


if __name__ == "__main__":
    raise SystemExit(main())

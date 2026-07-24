"""Promote a whole-line wordmark candidate only after bound runtime proof."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import torch

from .build_identity import compiler_source_sha256, native_runtime_identity
from .wordmark_prior import wordmark_prior_source_sha256
from .wordmark_runtime import (
    DEFAULT_WORDMARK_PRIOR_CHECKPOINT, DEFAULT_WORDMARK_PRIOR_PROMOTION,
)


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = PROJECT / "models" / "wordmark_prior_candidate_v1.pt"
DEFAULT_TRAINING_REPORT = (
    PROJECT / "benchmarks/pcdc_pre_v14/wordmark_prior_full_v1.json"
)
DEFAULT_EXPERIMENT4 = PROJECT / "benchmarks/pcdc_experiment4/report.json"
DEFAULT_FULL_TESTS = PROJECT / "benchmarks/pcdc_pre_v14/full_tests.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def promote(
    *, candidate: Path, training_report: Path, experiment4: Path,
    full_tests: Path, output: Path, manifest: Path,
) -> dict:
    compiler_sha = compiler_source_sha256()
    candidate_sha = _sha256(candidate)
    checkpoint = torch.load(candidate, map_location="cpu", weights_only=False)
    current_contract = wordmark_prior_source_sha256()
    if not (
        checkpoint.get("schema") == "pcdc-wordmark-prior-checkpoint/v1"
        and checkpoint.get("model_data_contract_sha256") == current_contract
    ):
        raise RuntimeError("wordmark candidate model/data contract is stale")
    training = json.loads(training_report.read_text("utf-8"))
    held_out = training.get("held_out_test", {})
    if not (
        training.get("schema") == "pcdc-wordmark-prior-training/v1"
        and training.get("status") == "candidate-passed"
        and training.get("gate_pass") is True
        and training.get("checkpoint_sha256") == candidate_sha
        and training.get("model_data_contract_sha256") == current_contract
        and float(held_out.get("decoded_support_iou", 0.0)) >= 0.88
        and float(held_out.get("decoded_topology_accuracy", 0.0)) >= 0.95
        and float(held_out.get("decoded_complex_topology_accuracy", 0.0)) >= 0.90
        and float(held_out.get("component_head_accuracy", 0.0)) >= 0.90
        and float(held_out.get("hole_head_accuracy", 0.0)) >= 0.90
        and int(training.get("training_variants", 0)) >= 2_000_000
        and int(training.get("held_out_samples_per_split", 0)) >= 20_000
        and checkpoint.get("config") == training.get("config")
        and checkpoint.get("font_manifest_sha256")
        == training.get("font_manifest_sha256")
        and checkpoint.get("family_split_sha256")
        == training.get("family_split_sha256")
        and int(checkpoint.get("epoch", -1))
        == int(training.get("selected_epoch", -2))
        and 0.0 < float(checkpoint.get("support_threshold", 0.0)) < 1.0
        and float(checkpoint.get(
            "topology_repair_confidence_threshold", 0.0,
        )) >= 0.5
    ):
        raise RuntimeError("wordmark held-out training proof is not promotable")
    phase4 = json.loads(experiment4.read_text("utf-8"))
    identity = phase4.get("wordmark_prior_checkpoint") or {}
    if not (
        phase4.get("schema") == "pcdc-experiment4-textline/v2"
        and phase4.get("status") == "passed"
        and phase4.get("gate_pass") is True
        and phase4.get("compiler_source_sha256") == compiler_sha
        and phase4.get("machine", {}).get("gate_pass") is True
        and phase4.get("human", {}).get("gate_pass") is True
        and identity.get("sha256") == candidate_sha
    ):
        raise RuntimeError("wordmark candidate did not pass bound Experiment 4")
    regression = json.loads(full_tests.read_text("utf-8"))
    if not (
        regression.get("schema") == "pcdc-full-regression-suite/v1"
        and regression.get("passed") is True
        and regression.get("compiler_source_sha256") == compiler_sha
        and regression.get("native_runtime_identity", {}).get("sha256")
        == native_runtime_identity()["sha256"]
    ):
        raise RuntimeError("current full regression proof is missing")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    shutil.copy2(candidate, temporary)
    temporary.replace(output)
    payload = {
        "schema": "pcdc-wordmark-prior-promotion/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compiler_source_sha256": compiler_sha,
        "model_data_contract_sha256": current_contract,
        "checkpoint": str(output.resolve()),
        "checkpoint_sha256": _sha256(output),
        "candidate_sha256": candidate_sha,
        "training_report": str(training_report.resolve()),
        "training_report_sha256": _sha256(training_report),
        "experiment4_report": str(experiment4.resolve()),
        "experiment4_report_sha256": _sha256(experiment4),
        "full_tests_report": str(full_tests.resolve()),
        "full_tests_report_sha256": _sha256(full_tests),
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary_manifest = manifest.with_suffix(manifest.suffix + ".tmp")
    temporary_manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8",
    )
    temporary_manifest.replace(manifest)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--training-report", type=Path, default=DEFAULT_TRAINING_REPORT,
    )
    parser.add_argument("--experiment4", type=Path, default=DEFAULT_EXPERIMENT4)
    parser.add_argument("--full-tests", type=Path, default=DEFAULT_FULL_TESTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_WORDMARK_PRIOR_CHECKPOINT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_WORDMARK_PRIOR_PROMOTION)
    args = parser.parse_args()
    print(json.dumps(promote(
        candidate=args.candidate, training_report=args.training_report,
        experiment4=args.experiment4, full_tests=args.full_tests,
        output=args.output, manifest=args.manifest,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""Promote a glyph-prior candidate only after bound Phase-4 proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import torch

from .audit_full_regression import regression_suite_source_sha256
from .build_identity import (
    compiler_source_sha256,
    evaluation_source_sha256,
    native_runtime_identity,
)
from .glyph_prior import (
    DEFAULT_GLYPH_PRIOR_CHECKPOINT,
    DEFAULT_GLYPH_PRIOR_PROMOTION,
    glyph_prior_contract_compatibility,
    glyph_prior_source_sha256,
)

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = PROJECT / "models" / "glyph_prior_candidate_v1.pt"
DEFAULT_TRAINING_REPORT = (
    PROJECT / "benchmarks" / "pcdc_pre_v14" / "glyph_prior_training.json"
)
DEFAULT_EXPERIMENT4 = PROJECT / "benchmarks" / "pcdc_experiment4" / "report.json"
DEFAULT_FULL_TESTS = PROJECT / "benchmarks" / "pcdc_pre_v14" / "full_tests.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def promote(
    *, candidate: Path, training_report: Path, experiment4: Path,
    full_tests: Path, output: Path, manifest: Path,
) -> dict:
    compiler_sha = compiler_source_sha256()
    candidate_sha = _sha256(candidate)
    checkpoint_payload = torch.load(
        candidate, map_location="cpu", weights_only=False,
    )
    if not (
        checkpoint_payload.get("schema") == "pcdc-glyph-prior-checkpoint/v1"
        and glyph_prior_contract_compatibility(
            checkpoint_payload.get("model_contract_sha256")
        ) is not None
    ):
        raise RuntimeError("candidate checkpoint model/data contract is stale")
    training = json.loads(training_report.read_text("utf-8"))
    checkpoint_config = dict(checkpoint_payload.get("config", {}))
    training_contract = training.get("contract", {})
    if not (
        training.get("schema") == "pcdc-glyph-prior-training/v1"
        and training.get("status") == "candidate-passed"
        and training.get("gate_pass") is True
        and training.get("compiler_source_sha256") == compiler_sha
        and training.get("checkpoint_sha256") == candidate_sha
        and float(training.get("held_out_test", {}).get(
            "topology_accuracy", 0.0,
        )) >= 0.97
        and float(training.get("held_out_test", {}).get(
            "support_iou", 0.0,
        )) >= 0.90
        and float(training.get("held_out_test", {}).get(
            "mask_topology_accuracy", 0.0,
        )) >= 0.97
        and float(training.get("held_out_test", {}).get(
            "topology_head_accuracy", 0.0,
        )) >= 0.97
        and int(training.get("training_variants", 0)) >= 2_000_000
        and int(training.get("held_out_samples_per_split", 0)) >= 20_000
        and checkpoint_config == training_contract.get("config")
        and int(checkpoint_config.get("image_size", 0)) >= 64
        and int(checkpoint_config.get("base_channels", 0)) >= 24
        and int(checkpoint_config.get("character_embedding_dim", 0)) >= 16
        and checkpoint_payload.get("font_manifest_sha256")
        == training_contract.get("font_manifest_sha256")
        and checkpoint_payload.get("family_split_sha256")
        == training_contract.get("family_split_sha256")
        and checkpoint_payload.get("training_contract_sha256")
        == training.get("training_contract_sha256")
        and int(checkpoint_payload.get("epoch", -1))
        == int(training.get("selected_epoch", -2))
    ):
        raise RuntimeError("glyph-prior held-out training proof is not promotable")
    phase4 = json.loads(experiment4.read_text("utf-8"))
    current_phase4_evaluator = evaluation_source_sha256(
        "vice_compiler/experiment4_textline.py",
    )
    identity = phase4.get("glyph_prior_checkpoint") or {}
    if not (
        phase4.get("schema") == "pcdc-experiment4-textline/v2"
        and phase4.get("status") == "passed"
        and phase4.get("gate_pass") is True
        and phase4.get("compiler_source_sha256") == compiler_sha
        and phase4.get("evaluation_source_sha256") == current_phase4_evaluator
        and phase4.get("machine", {}).get("gate_pass") is True
        and phase4.get("human", {}).get("gate_pass") is True
        and identity.get("sha256") == candidate_sha
    ):
        raise RuntimeError("candidate did not pass its bound Experiment 4 court")
    regression = json.loads(full_tests.read_text("utf-8"))
    if not (
        regression.get("schema") == "pcdc-full-regression-suite/v1"
        and regression.get("passed") is True
        and regression.get("compiler_source_sha256") == compiler_sha
        and regression.get("evaluation_source_sha256")
        == regression_suite_source_sha256()
        and regression.get("native_runtime_identity", {}).get("sha256")
        == native_runtime_identity()["sha256"]
    ):
        raise RuntimeError("current full regression proof is missing")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    shutil.copy2(candidate, temporary)
    temporary.replace(output)
    output_sha = _sha256(output)
    payload = {
        "schema": "pcdc-glyph-prior-promotion/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compiler_source_sha256": compiler_sha,
        "model_contract_sha256": glyph_prior_source_sha256(),
        "checkpoint_contract_compatibility": glyph_prior_contract_compatibility(
            checkpoint_payload.get("model_contract_sha256")
        ),
        "checkpoint": str(output.resolve()),
        "checkpoint_sha256": output_sha,
        "candidate_sha256": candidate_sha,
        "training_report": str(training_report.resolve()),
        "training_report_sha256": _sha256(training_report),
        "experiment4_report": str(experiment4.resolve()),
        "experiment4_report_sha256": _sha256(experiment4),
        "full_tests_report": str(full_tests.resolve()),
        "full_tests_report_sha256": _sha256(full_tests),
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest_tmp = manifest.with_suffix(manifest.suffix + ".tmp")
    manifest_tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    manifest_tmp.replace(manifest)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--training-report", type=Path, default=DEFAULT_TRAINING_REPORT)
    parser.add_argument("--experiment4", type=Path, default=DEFAULT_EXPERIMENT4)
    parser.add_argument("--full-tests", type=Path, default=DEFAULT_FULL_TESTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_GLYPH_PRIOR_CHECKPOINT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_GLYPH_PRIOR_PROMOTION)
    args = parser.parse_args()
    payload = promote(
        candidate=args.candidate, training_report=args.training_report,
        experiment4=args.experiment4, full_tests=args.full_tests,
        output=args.output, manifest=args.manifest,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

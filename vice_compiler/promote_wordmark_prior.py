"""Promote a whole-line wordmark candidate only after bound runtime proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import torch

from .audit_full_regression import regression_suite_source_sha256
from .audit_wordmark_short_logo import (
    MINIMUM_SAMPLES_PER_LENGTH,
    SHORT_LOGO_LENGTHS,
    short_logo_audit_source_sha256,
    short_logo_gate,
)
from .build_identity import (
    compiler_source_sha256,
    evaluation_source_sha256,
    native_runtime_identity,
)
from .train_wordmark_prior import wordmark_trainer_source_sha256
from .wordmark_prior import WORDMARK_CHARACTERS, wordmark_prior_source_sha256
from .wordmark_runtime import (
    DEFAULT_WORDMARK_PRIOR_CHECKPOINT,
    DEFAULT_WORDMARK_PRIOR_PROMOTION,
)

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = PROJECT / "models" / "wordmark_prior_candidate_v1.pt"
DEFAULT_TRAINING_REPORT = (
    PROJECT / "benchmarks/pcdc_pre_v14/wordmark_prior_full_v1.json"
)
DEFAULT_PREFLIGHT_REPORT = (
    PROJECT / "benchmarks/pcdc_pre_v14/wordmark_prior_preflight_v4.json"
)
DEFAULT_SHORT_LOGO_AUDIT = (
    PROJECT / "benchmarks/pcdc_pre_v14/wordmark_short_logo_audit.json"
)
DEFAULT_EXPERIMENT4 = PROJECT / "benchmarks/pcdc_experiment4/report.json"
DEFAULT_EXPERIMENT4_BASELINE = (
    PROJECT / "benchmarks/pcdc_experiment4/report_wordmark_off.json"
)
DEFAULT_FULL_TESTS = PROJECT / "benchmarks/pcdc_pre_v14/full_tests.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def promote(
    *, candidate: Path, training_report: Path, preflight_report: Path,
    short_logo_audit: Path,
    experiment4: Path,
    experiment4_baseline: Path, full_tests: Path, output: Path, manifest: Path,
) -> dict:
    compiler_sha = compiler_source_sha256()
    candidate_sha = _sha256(candidate)
    checkpoint = torch.load(candidate, map_location="cpu", weights_only=False)
    current_contract = wordmark_prior_source_sha256()
    current_trainer = wordmark_trainer_source_sha256()
    if not (
        checkpoint.get("schema") == "pcdc-wordmark-prior-checkpoint/v1"
        and checkpoint.get("model_data_contract_sha256") == current_contract
    ):
        raise RuntimeError("wordmark candidate model/data contract is stale")
    training = json.loads(training_report.read_text("utf-8"))
    preflight = json.loads(preflight_report.read_text("utf-8"))
    held_out = training.get("held_out_test", {})
    recipe = training.get("data_recipe", {})
    training_contract = training.get("training_contract", {})
    required_preflight_checks = (
        "family_disjoint", "procedural_determinism",
        "serving_vocabulary_fully_covered",
        "serving_length_range_fully_covered", "topology_diversity",
        "connected_wordmarks_present", "high_counter_wordmarks_present",
        "tiny_overfit", "cuda_training_reproducible",
    )
    preflight_checks = preflight.get("checks", {})
    tiny = preflight.get("tiny_overfit", {})
    tiny_repeat = preflight.get("tiny_overfit_repeat", {})
    preflight_families = preflight.get("font_families", {})
    preflight_faces = preflight.get("font_faces", {})
    training_faces = training.get("font_faces", {})
    preflight_vocabulary = preflight.get("serving_vocabulary", {})
    reproducibility_hashes_match = all(
        isinstance(tiny.get(key), str)
        and len(tiny[key]) == 64
        and tiny.get(key) == tiny_repeat.get(key)
        for key in ("loss_trace_sha256", "final_state_sha256")
    )
    if not (
        training.get("schema") == "pcdc-wordmark-prior-training/v1"
        and training.get("status") == "candidate-passed"
        and training.get("gate_pass") is True
        and training.get("checkpoint_sha256") == candidate_sha
        and training.get("model_data_contract_sha256") == current_contract
        and training.get("trainer_source_sha256") == current_trainer
        and checkpoint.get("trainer_source_sha256") == current_trainer
        and checkpoint.get("training_contract", {}).get(
            "trainer_source_sha256"
        ) == current_trainer
        and checkpoint.get("training_contract") == training_contract
        and preflight.get("schema") == "pcdc-wordmark-prior-preflight/v1"
        and preflight.get("status") == "passed"
        and preflight.get("gate_pass") is True
        and all(preflight_checks.get(key) is True for key in required_preflight_checks)
        and preflight.get("model_data_contract_sha256") == current_contract
        and preflight.get("trainer_source_sha256") == current_trainer
        and preflight.get("font_manifest_sha256")
        == training.get("font_manifest_sha256")
        and preflight.get("family_split_sha256")
        == training.get("family_split_sha256")
        and preflight.get("data_recipe") == recipe
        and int(preflight.get("sample_count", 0)) >= 256
        and preflight.get("observed_text_lengths") == list(range(1, 33))
        and preflight_vocabulary.get("characters") == WORDMARK_CHARACTERS
        and preflight_vocabulary.get("missing_characters") == ""
        and preflight_vocabulary.get("covered_token_ids")
        == list(range(1, len(WORDMARK_CHARACTERS) + 1))
        and preflight_faces == training_faces
        and sum(int(preflight_faces.get(split, 0)) for split in (
            "train", "calibration", "test",
        )) >= 240
        and int(preflight_families.get("train", 0)) >= 64
        and int(preflight_families.get("calibration", 0)) >= 8
        and int(preflight_families.get("test", 0)) >= 8
        and reproducibility_hashes_match
        and recipe.get("schema") == "pcdc-wordmark-procedural-data/v9"
        and recipe.get("text_length") == [1, 32]
        and training_contract.get("deterministic_algorithms") is True
        and training_contract.get("cudnn_benchmark") is False
        and training_contract.get("cudnn_deterministic") is True
        and training_contract.get("cublas_workspace_config") == ":4096:8"
        and training_contract.get("resolved_device") == "cuda"
        and training_contract.get("automatic_mixed_precision") is True
        and preflight.get("device") == "cuda"
        and int(training_contract.get("unique_training_variants", 0))
        == int(training.get("training_variants", -1))
        and int(training_contract.get("training_sample_presentations", 0))
        == int(training.get("training_sample_presentations", -1))
        and int(training_contract.get("held_out_samples_per_split", 0))
        == int(training.get("held_out_samples_per_split", -1))
        and int(training_contract.get("epochs", 0)) >= 4
        and int(training_contract.get("training_sample_presentations", 0))
        >= 8_000_000
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
    short_logo = json.loads(short_logo_audit.read_text("utf-8"))
    short_slices = short_logo.get("slices", {})
    short_slice_metrics_pass = short_logo_gate(short_slices)
    if not (
        short_logo.get("schema") == "pcdc-wordmark-short-logo-audit/v1"
        and short_logo.get("status") == "passed"
        and short_logo.get("gate_pass") is True
        and short_logo.get("audit_source_sha256")
        == short_logo_audit_source_sha256()
        and short_logo.get("checkpoint_sha256") == candidate_sha
        and short_logo.get("training_report_sha256") == _sha256(training_report)
        and short_logo.get("model_data_contract_sha256") == current_contract
        and short_logo.get("trainer_source_sha256") == current_trainer
        and short_logo.get("font_manifest_sha256")
        == training.get("font_manifest_sha256")
        and short_logo.get("family_split_sha256")
        == training.get("family_split_sha256")
        and short_logo.get("lengths") == list(SHORT_LOGO_LENGTHS)
        and int(short_logo.get("samples_per_length", 0))
        >= MINIMUM_SAMPLES_PER_LENGTH
        and short_logo.get("visible_serving_alphabet")
        == WORDMARK_CHARACTERS.rstrip(" ")
        and short_slice_metrics_pass
    ):
        raise RuntimeError("wordmark one/two-symbol held-out proof is not promotable")
    phase4 = json.loads(experiment4.read_text("utf-8"))
    phase4_baseline = json.loads(experiment4_baseline.read_text("utf-8"))
    current_native = native_runtime_identity()
    current_phase4_evaluator = evaluation_source_sha256(
        "vice_compiler/experiment4_textline.py",
    )
    identity = phase4.get("wordmark_prior_checkpoint") or {}
    baseline_identity = phase4_baseline.get("wordmark_prior_checkpoint")
    candidate_rows = {
        str(row.get("id")): row for row in phase4.get("rows", ())
        if isinstance(row, dict) and row.get("id") is not None
    }
    baseline_rows = {
        str(row.get("id")): row for row in phase4_baseline.get("rows", ())
        if isinstance(row, dict) and row.get("id") is not None
    }
    delivered_rows_changed = (
        sum(
            candidate_rows[row_id].get("candidate_svg_digest")
            != baseline_rows[row_id].get("candidate_svg_digest")
            or candidate_rows[row_id].get("candidate_mask_digest")
            != baseline_rows[row_id].get("candidate_mask_digest")
            for row_id in candidate_rows
        )
        if candidate_rows.keys() == baseline_rows.keys() else 0
    )
    candidate_machine = phase4.get("machine", {})
    baseline_machine = phase4_baseline.get("machine", {})
    candidate_human = phase4.get("human", {})
    bound_inputs_match = all(
        isinstance(phase4.get(key), dict)
        and isinstance(phase4[key].get("sha256"), str)
        and len(phase4[key]["sha256"]) == 64
        and phase4.get(key) == phase4_baseline.get(key)
        for key in (
            "input_identity", "font_catalog_identity", "ocr_model_identity",
        )
    )
    digests_are_bound = all(
        isinstance(row.get(key), str) and len(row[key]) == 64
        for rows in (candidate_rows, baseline_rows)
        for row in rows.values()
        for key in ("candidate_mask_digest", "candidate_svg_digest")
    )
    if not (
        phase4.get("schema") == "pcdc-experiment4-textline/v2"
        and phase4.get("status") == "passed"
        and phase4.get("gate_pass") is True
        and phase4.get("compiler_source_sha256") == compiler_sha
        and phase4.get("evaluation_source_sha256") == current_phase4_evaluator
        and phase4.get("machine", {}).get("gate_pass") is True
        and candidate_human.get("gate_pass") is True
        and int(candidate_human.get("required", 0)) > 0
        and int(candidate_human.get("reviewed", 0))
        >= int(candidate_human.get("required", 0))
        and int(candidate_human.get("stale", 1)) == 0
        and candidate_human.get("digest_validated") is True
        and isinstance(candidate_human.get("review_sha256"), str)
        and len(candidate_human["review_sha256"]) == 64
        and isinstance(candidate_human.get("manifest_sha256"), str)
        and len(candidate_human["manifest_sha256"]) == 64
        and identity.get("sha256") == candidate_sha
        and phase4_baseline.get("schema")
        == "pcdc-experiment4-textline/v2"
        and phase4_baseline.get("compiler_source_sha256") == compiler_sha
        and phase4_baseline.get("evaluation_source_sha256")
        == current_phase4_evaluator
        and phase4.get("native_runtime_identity") == current_native
        and phase4_baseline.get("native_runtime_identity") == current_native
        and not baseline_identity
        and phase4.get("glyph_prior_checkpoint")
        == phase4_baseline.get("glyph_prior_checkpoint")
        and bound_inputs_match
        and len(phase4.get("rows", ())) == 100
        and len(phase4_baseline.get("rows", ())) == 100
        and len(candidate_rows) == 100
        and candidate_rows.keys() == baseline_rows.keys()
        and digests_are_bound
        and delivered_rows_changed > 0
        and candidate_machine.get("all_reviewed_lines_not_worse") is True
        and float(candidate_machine.get("candidate_mean_iou", -1.0))
        >= float(baseline_machine.get("candidate_mean_iou", 0.0)) - 1.0e-12
        and float(candidate_machine.get("warm_p95_ms_per_line", 1.0e30))
        < 200.0
    ):
        raise RuntimeError(
            "wordmark candidate did not pass its exact model-OFF/model-ON "
            "Experiment 4 ablation"
        )
    regression = json.loads(full_tests.read_text("utf-8"))
    if not (
        regression.get("schema") == "pcdc-full-regression-suite/v1"
        and regression.get("passed") is True
        and regression.get("compiler_source_sha256") == compiler_sha
        and regression.get("evaluation_source_sha256")
        == regression_suite_source_sha256()
        and regression.get("native_runtime_identity", {}).get("sha256")
        == current_native["sha256"]
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
        "preflight_report": str(preflight_report.resolve()),
        "preflight_report_sha256": _sha256(preflight_report),
        "short_logo_audit_report": str(short_logo_audit.resolve()),
        "short_logo_audit_report_sha256": _sha256(short_logo_audit),
        "experiment4_report": str(experiment4.resolve()),
        "experiment4_report_sha256": _sha256(experiment4),
        "experiment4_baseline_report": str(experiment4_baseline.resolve()),
        "experiment4_baseline_report_sha256": _sha256(experiment4_baseline),
        "experiment4_delivered_rows_changed": delivered_rows_changed,
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
    parser.add_argument(
        "--preflight-report", type=Path, default=DEFAULT_PREFLIGHT_REPORT,
    )
    parser.add_argument(
        "--short-logo-audit", type=Path, default=DEFAULT_SHORT_LOGO_AUDIT,
    )
    parser.add_argument("--experiment4", type=Path, default=DEFAULT_EXPERIMENT4)
    parser.add_argument(
        "--experiment4-baseline", type=Path,
        default=DEFAULT_EXPERIMENT4_BASELINE,
    )
    parser.add_argument("--full-tests", type=Path, default=DEFAULT_FULL_TESTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_WORDMARK_PRIOR_CHECKPOINT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_WORDMARK_PRIOR_PROMOTION)
    args = parser.parse_args()
    print(json.dumps(promote(
        candidate=args.candidate, training_report=args.training_report,
        preflight_report=args.preflight_report,
        short_logo_audit=args.short_logo_audit,
        experiment4=args.experiment4,
        experiment4_baseline=args.experiment4_baseline,
        full_tests=args.full_tests,
        output=args.output, manifest=args.manifest,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import torch

from vice_compiler.audit_full_regression import regression_suite_source_sha256
from vice_compiler.audit_wordmark_short_logo import (
    short_logo_audit_source_sha256,
)
from vice_compiler.build_identity import (
    compiler_source_sha256,
    evaluation_source_sha256,
    native_runtime_identity,
)
from vice_compiler.promote_wordmark_prior import promote
from vice_compiler.train_wordmark_prior import wordmark_trainer_source_sha256
from vice_compiler.wordmark_prior import (
    WORDMARK_CHARACTERS,
    WordmarkPriorConfig,
    WordmarkPriorNet,
    checkpoint_payload,
    wordmark_prior_source_sha256,
)
from vice_compiler.wordmark_runtime import validate_wordmark_prior_promotion


class WordmarkPromotionTests(unittest.TestCase):
    def test_promotion_requires_and_seals_training_court_and_regression(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = WordmarkPriorConfig(base_channels=8, text_embedding_dim=16)
            model = WordmarkPriorNet(config)
            payload = checkpoint_payload(
                model, epoch=4, font_manifest_sha256="fonts",
                family_split_sha256="split", support_threshold=0.85,
                selection_key=(0.96, 0.91, 0.90),
            )
            payload["topology_repair_confidence_threshold"] = 0.70
            trainer_sha = wordmark_trainer_source_sha256()
            payload["trainer_source_sha256"] = trainer_sha
            training_contract = {
                "trainer_source_sha256": trainer_sha,
                "deterministic_algorithms": True,
                "cudnn_benchmark": False,
                "cudnn_deterministic": True,
                "cublas_workspace_config": ":4096:8",
                "resolved_device": "cuda",
                "automatic_mixed_precision": True,
                "unique_training_variants": 2_000_000,
                "training_sample_presentations": 8_000_000,
                "held_out_samples_per_split": 20_000,
                "epochs": 4,
            }
            payload["training_contract"] = training_contract
            candidate = root / "candidate.pt"
            torch.save(payload, candidate)
            candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
            training = root / "training.json"
            training.write_text(json.dumps({
                "schema": "pcdc-wordmark-prior-training/v1",
                "status": "candidate-passed", "gate_pass": True,
                "checkpoint_sha256": candidate_sha,
                "model_data_contract_sha256": wordmark_prior_source_sha256(),
                "trainer_source_sha256": trainer_sha,
                "training_contract": training_contract,
                "data_recipe": {
                    "schema": "pcdc-wordmark-procedural-data/v9",
                    "text_length": [1, 32],
                },
                "config": payload["config"],
                "font_manifest_sha256": "fonts",
                "family_split_sha256": "split",
                "font_faces": {
                    "train": 186, "calibration": 20, "test": 35,
                },
                "selected_epoch": 4, "training_variants": 2_000_000,
                "training_sample_presentations": 8_000_000,
                "held_out_samples_per_split": 20_000,
                "held_out_test": {
                    "decoded_support_iou": 0.90,
                    "decoded_topology_accuracy": 0.96,
                    "decoded_complex_topology_accuracy": 0.91,
                    "component_head_accuracy": 0.95,
                    "hole_head_accuracy": 0.94,
                },
            }), "utf-8")
            preflight = root / "preflight.json"
            preflight.write_text(json.dumps({
                "schema": "pcdc-wordmark-prior-preflight/v1",
                "status": "passed", "gate_pass": True,
                "model_data_contract_sha256": wordmark_prior_source_sha256(),
                "trainer_source_sha256": trainer_sha,
                "font_manifest_sha256": "fonts",
                "family_split_sha256": "split",
                "data_recipe": {
                    "schema": "pcdc-wordmark-procedural-data/v9",
                    "text_length": [1, 32],
                },
                "sample_count": 256,
                "device": "cuda",
                "observed_text_lengths": list(range(1, 33)),
                "serving_vocabulary": {
                    "characters": WORDMARK_CHARACTERS,
                    "covered_token_ids": list(
                        range(1, len(WORDMARK_CHARACTERS) + 1)
                    ),
                    "missing_characters": "",
                },
                "font_families": {
                    "train": 65, "calibration": 8, "test": 8,
                },
                "font_faces": {
                    "train": 186, "calibration": 20, "test": 35,
                },
                "checks": {
                    "family_disjoint": True,
                    "procedural_determinism": True,
                    "serving_vocabulary_fully_covered": True,
                    "serving_length_range_fully_covered": True,
                    "topology_diversity": True,
                    "connected_wordmarks_present": True,
                    "high_counter_wordmarks_present": True,
                    "tiny_overfit": True,
                    "cuda_training_reproducible": True,
                },
                "tiny_overfit": {
                    "loss_trace_sha256": "9" * 64,
                    "final_state_sha256": "a" * 64,
                },
                "tiny_overfit_repeat": {
                    "loss_trace_sha256": "9" * 64,
                    "final_state_sha256": "a" * 64,
                },
            }), "utf-8")
            short_logo = root / "short-logo.json"
            short_logo_payload = {
                "schema": "pcdc-wordmark-short-logo-audit/v1",
                "status": "passed", "gate_pass": True,
                "audit_source_sha256": short_logo_audit_source_sha256(),
                "model_data_contract_sha256": wordmark_prior_source_sha256(),
                "trainer_source_sha256": trainer_sha,
                "checkpoint_sha256": candidate_sha,
                "training_report_sha256": hashlib.sha256(
                    training.read_bytes(),
                ).hexdigest(),
                "font_manifest_sha256": "fonts",
                "family_split_sha256": "split",
                "lengths": [1, 2], "samples_per_length": 2048,
                "visible_serving_alphabet": WORDMARK_CHARACTERS.rstrip(" "),
                "slices": {
                    str(length): {
                        "samples": 2048,
                        "decoded_support_iou": 0.90,
                        "decoded_topology_accuracy": 0.96,
                        "component_head_accuracy": 0.95,
                        "hole_head_accuracy": 0.94,
                        "symbol_fidelity": {
                            "support_iou_cvar10": 0.80,
                            "minimum_symbol_mean_support_iou": 0.85,
                            "minimum_symbol_topology_accuracy": 0.90,
                            "minimum_symbol_component_head_accuracy": 0.85,
                            "minimum_symbol_hole_head_accuracy": 0.85,
                        },
                    }
                    for length in (1, 2)
                },
            }
            short_logo.write_text(json.dumps(short_logo_payload), "utf-8")
            compiler_sha = compiler_source_sha256()
            phase4_evaluator_sha = evaluation_source_sha256(
                "vice_compiler/experiment4_textline.py",
            )
            native_identity = native_runtime_identity()
            input_identity = {"sha256": "1" * 64}
            font_identity = {"sha256": "2" * 64}
            ocr_identity = {"sha256": "3" * 64}
            baseline_rows = [
                {
                    "id": f"text-{index:03d}",
                    "candidate_mask_digest": "4" * 64,
                    "candidate_svg_digest": "5" * 64,
                }
                for index in range(100)
            ]
            candidate_rows = [dict(row) for row in baseline_rows]
            candidate_rows[7]["candidate_svg_digest"] = "6" * 64
            experiment4_baseline = root / "experiment4-baseline.json"
            experiment4_baseline.write_text(json.dumps({
                "schema": "pcdc-experiment4-textline/v2",
                "compiler_source_sha256": compiler_sha,
                "evaluation_source_sha256": phase4_evaluator_sha,
                "native_runtime_identity": native_identity,
                "input_identity": input_identity,
                "font_catalog_identity": font_identity,
                "ocr_model_identity": ocr_identity,
                "wordmark_prior_checkpoint": None,
                "machine": {"candidate_mean_iou": 0.90},
                "rows": baseline_rows,
            }), "utf-8")
            experiment4 = root / "experiment4.json"
            experiment4.write_text(json.dumps({
                "schema": "pcdc-experiment4-textline/v2",
                "status": "passed", "gate_pass": True,
                "compiler_source_sha256": compiler_sha,
                "evaluation_source_sha256": phase4_evaluator_sha,
                "native_runtime_identity": native_identity,
                "input_identity": input_identity,
                "font_catalog_identity": font_identity,
                "ocr_model_identity": ocr_identity,
                "machine": {
                    "gate_pass": True,
                    "all_reviewed_lines_not_worse": True,
                    "candidate_mean_iou": 0.91,
                    "warm_p95_ms_per_line": 75.0,
                },
                "human": {
                    "gate_pass": True, "required": 1, "reviewed": 1,
                    "stale": 0, "digest_validated": True,
                    "review_sha256": "7" * 64,
                    "manifest_sha256": "8" * 64,
                },
                "wordmark_prior_checkpoint": {"sha256": candidate_sha},
                "rows": candidate_rows,
            }), "utf-8")
            regression = root / "full.json"
            regression.write_text(json.dumps({
                "schema": "pcdc-full-regression-suite/v1", "passed": True,
                "compiler_source_sha256": compiler_sha,
                "evaluation_source_sha256": regression_suite_source_sha256(),
                "native_runtime_identity": native_runtime_identity(),
            }), "utf-8")
            output = root / "wordmark_prior.pt"
            manifest = root / "wordmark_prior_promotion.json"
            result = promote(
                candidate=candidate, training_report=training,
                preflight_report=preflight,
                short_logo_audit=short_logo,
                experiment4=experiment4,
                experiment4_baseline=experiment4_baseline,
                full_tests=regression,
                output=output, manifest=manifest,
            )
            self.assertEqual(result["candidate_sha256"], candidate_sha)
            self.assertEqual(result["checkpoint_sha256"], candidate_sha)
            self.assertEqual(result["experiment4_delivered_rows_changed"], 1)
            validated = validate_wordmark_prior_promotion(output, manifest)
            self.assertEqual(validated["checkpoint_sha256"], candidate_sha)
            valid_short_logo_report = short_logo.read_text("utf-8")
            weak_single_symbol = json.loads(valid_short_logo_report)
            weak_single_symbol["slices"]["1"]["decoded_support_iou"] = 0.20
            short_logo.write_text(json.dumps(weak_single_symbol), "utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "one/two-symbol held-out proof",
            ):
                promote(
                    candidate=candidate, training_report=training,
                    preflight_report=preflight,
                    short_logo_audit=short_logo,
                    experiment4=experiment4,
                    experiment4_baseline=experiment4_baseline,
                    full_tests=regression, output=output, manifest=manifest,
                )
            short_logo.write_text(valid_short_logo_report, "utf-8")
            valid_preflight_report = preflight.read_text("utf-8")
            incomplete_lengths = json.loads(valid_preflight_report)
            incomplete_lengths["observed_text_lengths"].remove(17)
            preflight.write_text(json.dumps(incomplete_lengths), "utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "held-out training proof is not promotable",
            ):
                promote(
                    candidate=candidate, training_report=training,
                    preflight_report=preflight,
                    short_logo_audit=short_logo,
                    experiment4=experiment4,
                    experiment4_baseline=experiment4_baseline,
                    full_tests=regression, output=output, manifest=manifest,
                )
            preflight.write_text(valid_preflight_report, "utf-8")
            valid_candidate_report = experiment4.read_text("utf-8")
            no_delta = json.loads(valid_candidate_report)
            no_delta["rows"] = baseline_rows
            experiment4.write_text(json.dumps(no_delta), "utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "model-OFF/model-ON Experiment 4 ablation",
            ):
                promote(
                    candidate=candidate, training_report=training,
                    preflight_report=preflight,
                    short_logo_audit=short_logo,
                    experiment4=experiment4,
                    experiment4_baseline=experiment4_baseline,
                    full_tests=regression, output=output, manifest=manifest,
                )
            experiment4.write_text(valid_candidate_report, "utf-8")
            stale_evaluator = json.loads(valid_candidate_report)
            stale_evaluator["evaluation_source_sha256"] = "0" * 64
            experiment4.write_text(json.dumps(stale_evaluator), "utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "model-OFF/model-ON Experiment 4 ablation",
            ):
                promote(
                    candidate=candidate, training_report=training,
                    preflight_report=preflight,
                    short_logo_audit=short_logo,
                    experiment4=experiment4,
                    experiment4_baseline=experiment4_baseline,
                    full_tests=regression, output=output, manifest=manifest,
                )
            experiment4.write_text(valid_candidate_report, "utf-8")
            valid_regression_report = regression.read_text("utf-8")
            stale_regression = json.loads(valid_regression_report)
            stale_regression["evaluation_source_sha256"] = "0" * 64
            regression.write_text(json.dumps(stale_regression), "utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "current full regression proof is missing",
            ):
                promote(
                    candidate=candidate, training_report=training,
                    preflight_report=preflight,
                    short_logo_audit=short_logo,
                    experiment4=experiment4,
                    experiment4_baseline=experiment4_baseline,
                    full_tests=regression, output=output, manifest=manifest,
                )
            regression.write_text(valid_regression_report, "utf-8")
            valid_promotion_manifest = manifest.read_text("utf-8")
            stale_runtime_regression = json.loads(valid_regression_report)
            stale_runtime_regression["evaluation_source_sha256"] = "0" * 64
            regression.write_text(json.dumps(stale_runtime_regression), "utf-8")
            resealed_manifest = json.loads(valid_promotion_manifest)
            resealed_manifest["full_tests_report_sha256"] = hashlib.sha256(
                regression.read_bytes(),
            ).hexdigest()
            manifest.write_text(json.dumps(resealed_manifest), "utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "full_regression_evaluator",
            ):
                validate_wordmark_prior_promotion(output, manifest)
            regression.write_text(valid_regression_report, "utf-8")
            manifest.write_text(valid_promotion_manifest, "utf-8")
            valid_baseline_report = experiment4_baseline.read_text("utf-8")
            experiment4_baseline.write_text("{}", "utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "wordmark-prior promotion mismatch",
            ):
                validate_wordmark_prior_promotion(output, manifest)
            experiment4_baseline.write_text(valid_baseline_report, "utf-8")
            training.write_text("{}", "utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "wordmark-prior promotion mismatch",
            ):
                validate_wordmark_prior_promotion(output, manifest)


if __name__ == "__main__":
    unittest.main()

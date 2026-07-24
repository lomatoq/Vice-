from __future__ import annotations

import hashlib
import json
import os
import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import torch
from torch.utils.data import DataLoader

import vice_compiler.experiment12_full_campaign as campaign_module
import vice_compiler.glyph_prior as glyph_prior_module
import vice_compiler.pre_v14_readiness as readiness_module
from vice_compiler.audit_full_regression import regression_suite_source_sha256
from vice_compiler.build_identity import (
    compiler_source_sha256,
    evaluation_source_sha256,
    native_runtime_identity,
)
from vice_compiler.glyph_prior import (
    GLYPH_CHARACTER_SHA256,
    GlyphPriorConfig,
    GlyphPriorNet,
    checkpoint_payload,
    glyph_prior_contract_compatibility,
    glyph_prior_source_sha256,
    load_glyph_prior,
    propose_glyph_mask,
    topology_constrained_support,
)
from vice_compiler.glyph_prior_data import (
    GlyphFontRecord,
    _topology_corruption,
    glyph_observation_features,
    split_font_families,
)
from vice_compiler.promote_glyph_prior import promote
from vice_compiler.train_glyph_prior import (
    _balanced_cross_entropy,
    _checkpoint_selection_key,
    _evaluate,
)


class GlyphPriorTests(unittest.TestCase):
    def test_legacy_checkpoint_contract_is_semantically_bound(self) -> None:
        self.assertEqual(
            glyph_prior_contract_compatibility(
                glyph_prior_module.LEGACY_GLYPH_PRIOR_RAW_CONTRACT_SHA256
            ),
            "legacy-raw-v1-to-semantic-v2",
        )
        with patch.object(
            glyph_prior_module,
            "LEGACY_GLYPH_PRIOR_SEMANTIC_CONTRACT_SHA256",
            "0" * 64,
        ):
            self.assertIsNone(glyph_prior_contract_compatibility(
                glyph_prior_module.LEGACY_GLYPH_PRIOR_RAW_CONTRACT_SHA256
            ))

    def test_v14_readiness_binds_glyph_training_to_semantics_not_compiler(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            checkpoint = project / "models" / "glyph_prior_candidate_v1.pt"
            checkpoint.parent.mkdir(parents=True)
            legacy = glyph_prior_module.LEGACY_GLYPH_PRIOR_RAW_CONTRACT_SHA256
            torch.save({
                "schema": "pcdc-glyph-prior-checkpoint/v1",
                "model_contract_sha256": legacy,
            }, checkpoint)
            row = {
                "gate_pass": True,
                "status": "candidate-passed",
                "checkpoint_sha256": hashlib.sha256(
                    checkpoint.read_bytes()
                ).hexdigest(),
                "training_variants": 2_000_000,
                "held_out_samples_per_split": 20_000,
                "contract": {"glyph_prior_source_sha256": legacy},
                "held_out_test": {
                    "topology_accuracy": 0.98,
                    "support_iou": 0.91,
                    "mask_topology_accuracy": 0.98,
                    "topology_head_accuracy": 0.98,
                },
                # Deliberately stale: downstream current-hash experiments,
                # rather than a redundant retrain, cover serving changes.
                "compiler_source_sha256": "historical-compiler",
            }
            with patch.object(readiness_module, "PROJECT", project):
                self.assertTrue(
                    readiness_module._glyph_prior_artifact_passed(row)
                )
            row["contract"]["glyph_prior_source_sha256"] = "0" * 64
            with patch.object(readiness_module, "PROJECT", project):
                self.assertFalse(
                    readiness_module._glyph_prior_artifact_passed(row)
                )

    def test_family_split_is_deterministic_and_disjoint(self) -> None:
        records = tuple(
            GlyphFontRecord(f"family-{index}", Path(f"font-{index}.ttf"), f"{index:064x}", "OFL-1.1")
            for index in range(20)
        )
        first = split_font_families(records, seed=9)
        second = split_font_families(reversed(records), seed=9)
        self.assertEqual(first.family_assignment, second.family_assignment)
        self.assertEqual(first.digest, second.digest)
        sets = [
            {row.family for row in getattr(first, name)}
            for name in ("train", "calibration", "test")
        ]
        self.assertFalse(sets[0] & sets[1])
        self.assertFalse(sets[0] & sets[2])
        self.assertFalse(sets[1] & sets[2])

    def test_features_are_source_only_finite_and_bounded(self) -> None:
        image = np.full((21, 17, 3), 240, np.uint8)
        image[4:18, 7:11] = (20, 80, 160)
        features = glyph_observation_features(image, 64)
        self.assertEqual(features.shape, (3, 64, 64))
        self.assertTrue(np.isfinite(features).all())
        self.assertGreaterEqual(float(features.min()), 0.0)
        self.assertLessEqual(float(features.max()), 1.0)

    def test_training_corruptions_force_non_identity_topology_cases(self) -> None:
        coverage = np.zeros((32, 32), np.float32)
        coverage[7:25, 10:22] = 1.0
        original = glyph_prior_module.topology_signature(coverage >= 0.5)
        profiles = set()
        for seed in range(24):
            corrupted, profile = _topology_corruption(
                coverage, np.random.default_rng(seed),
            )
            profiles.add(profile)
            self.assertNotEqual(
                glyph_prior_module.topology_signature(corrupted >= 0.5),
                original,
            )
        self.assertGreaterEqual(len(profiles), 3)

    def test_topology_decoder_uses_nearest_certified_threshold(self) -> None:
        probability = np.zeros((16, 16), np.float32)
        probability[2:14, 2:14] = 0.9
        probability[6:10, 6:10] = 0.6
        at_half, _threshold, matched = topology_constrained_support(
            probability, (1, 1), 0.5,
        )
        self.assertTrue(matched)
        self.assertEqual(glyph_prior_module.topology_signature(at_half), (1, 1))
        self.assertFalse(at_half[7, 7])

    def test_model_has_support_sdf_skeleton_and_topology_heads(self) -> None:
        config = GlyphPriorConfig(image_size=32, base_channels=8, character_embedding_dim=4)
        model = GlyphPriorNet(config)
        output = model(
            torch.rand(2, 3, 32, 32), torch.tensor((0, 1)),
            torch.tensor((1, 1)), torch.tensor((0, 1)),
        )
        self.assertEqual(output["support_logits"].shape, (2, 1, 32, 32))
        self.assertEqual(output["sdf"].shape, (2, 1, 32, 32))
        self.assertEqual(output["skeleton_logits"].shape, (2, 1, 32, 32))
        self.assertEqual(output["prior_support_logits"].shape, (2, 1, 32, 32))
        self.assertEqual(output["prior_sdf"].shape, (2, 1, 32, 32))
        self.assertEqual(
            output["prior_skeleton_logits"].shape, (2, 1, 32, 32),
        )
        self.assertEqual(output["component_logits"].shape, (2, 6))
        self.assertEqual(output["hole_logits"].shape, (2, 5))
        self.assertTrue(all(torch.isfinite(value).all() for value in output.values()))

    def test_training_topology_gate_checks_decoded_mask_not_only_head(self) -> None:
        class PerfectHeadBrokenMask(torch.nn.Module):
            def forward(
                self, observed, character_ids, component_ids, hole_ids,
            ):
                batch, _channels, height, width = observed.shape
                components = torch.full(
                    (batch, 6), -20.0, device=observed.device,
                )
                holes = torch.full(
                    (batch, 5), -20.0, device=observed.device,
                )
                components[:, 1] = 20.0
                holes[:, 0] = 20.0
                return {
                    "support_logits": torch.full(
                        (batch, 1, height, width), -20.0,
                        device=observed.device,
                    ),
                    "sdf": torch.zeros(
                        (batch, 1, height, width), device=observed.device,
                    ),
                    "skeleton_logits": torch.full(
                        (batch, 1, height, width), -20.0,
                        device=observed.device,
                    ),
                    "prior_support_logits": torch.full(
                        (batch, 1, height, width), -20.0,
                        device=observed.device,
                    ),
                    "prior_sdf": torch.zeros(
                        (batch, 1, height, width), device=observed.device,
                    ),
                    "prior_skeleton_logits": torch.full(
                        (batch, 1, height, width), -20.0,
                        device=observed.device,
                    ),
                    "component_logits": components,
                    "hole_logits": holes,
                }

        support = torch.zeros(1, 16, 16)
        support[:, 3:13, 6:10] = 1.0
        sample = {
            "observed": torch.zeros(3, 16, 16),
            "support": support,
            "sdf": torch.zeros(1, 16, 16),
            "skeleton": support.clone(),
            "character_id": torch.tensor(0),
            "components": torch.tensor(1),
            "holes": torch.tensor(0),
        }
        metrics = _evaluate(
            PerfectHeadBrokenMask(), DataLoader([sample], batch_size=1),
            torch.device("cpu"),
        )
        self.assertEqual(metrics["topology_head_accuracy"], 1.0)
        self.assertEqual(metrics["mask_topology_accuracy"], 0.0)
        self.assertEqual(metrics["topology_accuracy"], 0.0)

    def test_checkpoint_selection_uses_weakest_normalized_hard_gate(self) -> None:
        topology_heavy = _checkpoint_selection_key(
            {"topology_accuracy": 0.98, "support_iou": 0.81},
            minimum_topology=0.97, minimum_support_iou=0.90,
        )
        balanced = _checkpoint_selection_key(
            {"topology_accuracy": 0.96, "support_iou": 0.90},
            minimum_topology=0.97, minimum_support_iou=0.90,
        )
        self.assertGreater(balanced, topology_heavy)

    def test_balanced_topology_loss_gives_rare_class_bounded_leverage(self) -> None:
        logits = torch.zeros(8, 3, requires_grad=True)
        targets = torch.tensor((0, 0, 0, 0, 0, 0, 0, 2))
        loss = _balanced_cross_entropy(logits, targets)
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertTrue(torch.isfinite(logits.grad).all())
        self.assertGreater(float(logits.grad[7].abs().sum()), 0.0)

    def test_missing_or_wrong_checkpoint_fails_open(self) -> None:
        image = np.full((20, 20, 3), 255, np.uint8)
        support = np.zeros((20, 20), bool)
        support[4:16, 7:13] = True
        with TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.pt"
            self.assertIsNone(load_glyph_prior(missing))
            self.assertIsNone(propose_glyph_mask(image, "I", support, checkpoint=missing))
            wrong = Path(directory) / "wrong.pt"
            torch.save({"schema": "wrong"}, wrong)
            self.assertIsNone(load_glyph_prior(wrong))

    def test_checkpoint_is_manifest_and_split_bound(self) -> None:
        config = GlyphPriorConfig(image_size=32, base_channels=8, character_embedding_dim=4)
        model = GlyphPriorNet(config)
        payload = checkpoint_payload(
            model, epoch=3, manifest_sha256="a" * 64,
            split_sha256="b" * 64, selection_key=(0.9, 0.8),
        )
        self.assertEqual(payload["config"], asdict(config))
        self.assertEqual(payload["character_vocab_sha256"], GLYPH_CHARACTER_SHA256)
        self.assertEqual(payload["font_manifest_sha256"], "a" * 64)
        self.assertEqual(payload["family_split_sha256"], "b" * 64)
        self.assertEqual(payload["model_contract_sha256"], glyph_prior_source_sha256())

    def test_runtime_proposal_requires_expected_topology_and_source_overlap(self) -> None:
        config = GlyphPriorConfig(image_size=32, base_channels=8, character_embedding_dim=4)
        model = GlyphPriorNet(config)
        for parameter in model.parameters():
            torch.nn.init.zeros_(parameter)
        with torch.no_grad():
            model.pixel_heads.bias[0] = 8.0
            model.component_head.bias[1] = 8.0
            model.hole_head.bias[0] = 8.0
        payload = checkpoint_payload(
            model, epoch=1, manifest_sha256="a" * 64,
            split_sha256="b" * 64, selection_key=(1.0, 1.0),
        )
        image = np.full((20, 20, 3), 250, np.uint8)
        image[:, :] = 20
        support = np.ones((20, 20), bool)
        with TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "glyph.pt"
            torch.save(payload, checkpoint)
            accepted = propose_glyph_mask(
                image, "I", support, checkpoint=checkpoint,
                expected_topology=(1, 0),
            )
            self.assertIsNotNone(accepted)
            self.assertEqual(accepted.topology_code, (1, 0))
            self.assertIsNone(propose_glyph_mask(
                image, "I", support, checkpoint=checkpoint,
                expected_topology=(1, 1),
            ))

    def test_default_runtime_checkpoint_requires_current_promotion_manifest(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "glyph_prior.pt"
            checkpoint.write_bytes(b"checkpoint")
            manifest = root / "glyph_prior_promotion.json"
            with patch.object(
                glyph_prior_module, "DEFAULT_GLYPH_PRIOR_CHECKPOINT", checkpoint,
            ), patch.object(
                glyph_prior_module, "DEFAULT_GLYPH_PRIOR_PROMOTION", manifest,
            ), patch.dict(os.environ, {}, clear=False):
                os.environ.pop("VICE_GLYPH_PRIOR_CHECKPOINT", None)
                self.assertIsNone(glyph_prior_module.resolve_glyph_prior_checkpoint())
                training = root / "training.json"
                training.write_text("{}", "utf-8")
                experiment4 = root / "experiment4.json"
                experiment4.write_text(json.dumps({
                    "evaluation_source_sha256": evaluation_source_sha256(
                        "vice_compiler/experiment4_textline.py",
                    ),
                }), "utf-8")
                regression = root / "full.json"
                regression.write_text(json.dumps({
                    "evaluation_source_sha256": regression_suite_source_sha256(),
                }), "utf-8")
                manifest.write_text(json.dumps({
                    "schema": "pcdc-glyph-prior-promotion/v1",
                    "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
                    "model_contract_sha256": glyph_prior_source_sha256(),
                    "compiler_source_sha256": compiler_source_sha256(),
                    "training_report": str(training),
                    "training_report_sha256": hashlib.sha256(
                        training.read_bytes(),
                    ).hexdigest(),
                    "experiment4_report": str(experiment4),
                    "experiment4_report_sha256": hashlib.sha256(
                        experiment4.read_bytes(),
                    ).hexdigest(),
                    "full_tests_report": str(regression),
                    "full_tests_report_sha256": hashlib.sha256(
                        regression.read_bytes(),
                    ).hexdigest(),
                }), "utf-8")
                glyph_prior_module._glyph_promotion_evidence_paths_cached.cache_clear()
                glyph_prior_module._validate_glyph_prior_promotion_cached.cache_clear()
                with patch.object(
                    glyph_prior_module, "validate_glyph_prior_promotion",
                    wraps=glyph_prior_module.validate_glyph_prior_promotion,
                ) as validate:
                    self.assertEqual(
                        glyph_prior_module.resolve_glyph_prior_checkpoint(),
                        checkpoint.resolve(),
                    )
                    self.assertEqual(
                        glyph_prior_module.resolve_glyph_prior_checkpoint(),
                        checkpoint.resolve(),
                    )
                    self.assertEqual(validate.call_count, 1)
                    stale_regression = {
                        "evaluation_source_sha256": "0" * 64,
                    }
                    regression.write_text(json.dumps(stale_regression), "utf-8")
                    resealed = json.loads(manifest.read_text("utf-8"))
                    resealed["full_tests_report_sha256"] = hashlib.sha256(
                        regression.read_bytes(),
                    ).hexdigest()
                    manifest.write_text(json.dumps(resealed), "utf-8")
                    self.assertIsNone(
                        glyph_prior_module.resolve_glyph_prior_checkpoint()
                    )
                    self.assertEqual(validate.call_count, 2)

    def test_promotion_requires_training_phase4_and_regression_proofs(self) -> None:
        config = GlyphPriorConfig()
        model = GlyphPriorNet(config)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate.pt"
            torch.save(checkpoint_payload(
                model, epoch=4, manifest_sha256="a" * 64,
                split_sha256="b" * 64, selection_key=(0.99, 0.95),
                training_contract_sha256="c" * 64,
            ), candidate)
            candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
            compiler_sha = compiler_source_sha256()
            training = root / "training.json"
            training.write_text(json.dumps({
                "schema": "pcdc-glyph-prior-training/v1",
                "status": "candidate-passed", "gate_pass": True,
                "compiler_source_sha256": compiler_sha,
                "checkpoint_sha256": candidate_sha,
                "training_contract_sha256": "c" * 64,
                "selected_epoch": 4,
                "training_variants": 2_000_000,
                "held_out_samples_per_split": 20_000,
                "contract": {
                    "config": asdict(config),
                    "font_manifest_sha256": "a" * 64,
                    "family_split_sha256": "b" * 64,
                },
                "held_out_test": {
                    "topology_accuracy": 0.98,
                    "mask_topology_accuracy": 0.98,
                    "topology_head_accuracy": 0.99,
                    "support_iou": 0.92,
                },
            }), "utf-8")
            phase4 = root / "experiment4.json"
            phase4.write_text(json.dumps({
                "schema": "pcdc-experiment4-textline/v2",
                "status": "passed", "gate_pass": True,
                "compiler_source_sha256": compiler_sha,
                "evaluation_source_sha256": evaluation_source_sha256(
                    "vice_compiler/experiment4_textline.py",
                ),
                "machine": {"gate_pass": True},
                "human": {"gate_pass": True},
                "glyph_prior_checkpoint": {"sha256": candidate_sha},
            }), "utf-8")
            regression = root / "full.json"
            regression.write_text(json.dumps({
                "schema": "pcdc-full-regression-suite/v1",
                "passed": True, "compiler_source_sha256": compiler_sha,
                "evaluation_source_sha256": regression_suite_source_sha256(),
                "native_runtime_identity": native_runtime_identity(),
            }), "utf-8")
            output = root / "glyph_prior.pt"
            manifest = root / "promotion.json"
            result = promote(
                candidate=candidate, training_report=training,
                experiment4=phase4, full_tests=regression,
                output=output, manifest=manifest,
            )
            self.assertEqual(result["checkpoint_sha256"], candidate_sha)
            self.assertTrue(output.is_file())
            self.assertTrue(manifest.is_file())

    def test_phase12_fingerprint_changes_with_promoted_glyph_model(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "glyph.pt"
            checkpoint.write_bytes(b"first")
            manifest = root / "glyph.json"
            manifest.write_text("{}", "utf-8")
            with patch.object(
                campaign_module, "runtime_model_identity",
                side_effect=lambda **_kwargs: {
                    "sha256": hashlib.sha256(
                        checkpoint.read_bytes() + manifest.read_bytes()
                    ).hexdigest(),
                },
            ):
                first = campaign_module._compiler_fingerprint()
                checkpoint.write_bytes(b"second")
                second = campaign_module._compiler_fingerprint()
            self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
from PIL import Image, ImageDraw

from vice_compiler.authorize_proposal_candidate import authorize_candidate
from vice_compiler.build_identity import evaluation_source_sha256
from vice_compiler.build_phase12_blind_court import build_court
from vice_compiler.evidence_ir import EvidenceCache
from vice_compiler.experiment12_full_campaign import (
    _blind_parity_evidence,
    _bound_proposal_calibration_evidence,
    _compiler_fingerprint,
    _proposal_calibration_evidence,
)
from vice_compiler.extraction_profiles import ExtractionProfile
from vice_compiler.master_problem import DualPrices, reduced_gain
from vice_compiler.native_core import (
    available,
    backend_summary,
    circle_sdf,
    conflict_masks,
    pack_atlas,
)
from vice_compiler.promote_proposal_checkpoint import promote_candidate
from vice_compiler.runtime_service import (
    QUALITY_BUDGETS,
    FontGlyphCache,
    PersistentCompilerService,
    QualityMode,
    WarmProposalWorker,
    _validate_proposal_candidate_evaluation,
    _validate_proposal_promotion,
)
from vice_compiler.visible_damage import damage_regressed, visible_damage_metrics
from web_preview.server import _phase12_blind_payload

EXPERIMENT9_EVALUATOR_SHA = evaluation_source_sha256(
    "vice_compiler/experiment9_proposal_calibration.py",
)


class NativePhase10Tests(unittest.TestCase):
    def test_rust_bitsets_sdf_and_atlas_are_exact(self) -> None:
        self.assertTrue(available(), backend_summary())
        self.assertEqual(conflict_masks((0b001, 0b010, 0b011, 0b1000)), (4, 4, 3, 0))
        distances = circle_sdf(
            np.asarray(((0.0, 0.0), (3.0, 4.0))), (0.0, 0.0), 2.0,
        )
        np.testing.assert_allclose(distances, (-2.0, 3.0), atol=1e-12)
        placements, size = pack_atlas(
            ((10, 5), (8, 4), (20, 2)), target_width=20, padding=1,
        )
        self.assertEqual(placements, ((0, 0, 10, 5), (11, 0, 19, 4), (0, 6, 20, 8)))
        self.assertEqual(size, (20, 8))

    def test_font_glyph_cache_binds_reir_math_identity(self) -> None:
        cache = FontGlyphCache()
        first_reir = type("Reir", (), {
            "source_sha256": "same-raster",
            "config_fingerprint": "implementation-a",
        })()
        changed_reir = type("Reir", (), {
            "source_sha256": "same-raster",
            "config_fingerprint": "implementation-b",
        })()
        budget = QUALITY_BUDGETS[QualityMode.FAST]
        with patch(
            "vice_compiler.runtime_service.generate_text_macros",
            side_effect=("first", "changed"),
        ) as generate:
            first, first_hit = cache.get_or_build(first_reir, budget)
            changed, changed_hit = cache.get_or_build(changed_reir, budget)
            repeated, repeated_hit = cache.get_or_build(changed_reir, budget)
        self.assertEqual((first, changed, repeated), ("first", "changed", "changed"))
        self.assertEqual((first_hit, changed_hit, repeated_hit), (False, False, True))
        self.assertEqual(generate.call_count, 2)


class ProposalPromotionPhase10Tests(unittest.TestCase):
    def test_candidate_evaluation_is_gate_bound_but_not_production_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); candidate = root / "candidate.pt"
            label_sha = "b" * 64
            torch.save({
                "label_contract_version": "pcdc-source-disjoint-svg-owner-labels/v1",
                "label_contract_sha256": label_sha,
            }, candidate)
            candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
            large = root / "large.json"; real = root / "real.json"
            large.write_text(json.dumps({
                "gate_pass": True, "checkpoint_sha256": "c" * 64,
            }), "utf-8")
            real.write_text(json.dumps({
                "gate_pass": True, "checkpoint_sha256": candidate_sha,
                "initialization_sha256": "c" * 64,
                "evaluation_source_sha256": EXPERIMENT9_EVALUATOR_SHA,
            }), "utf-8")
            manifest_path = root / "candidate.evaluation.json"
            manifest = authorize_candidate(
                candidate, large, real, manifest_path,
            )
            self.assertEqual(
                manifest["authorization_scope"],
                "phase12-candidate-evaluation-only-not-production",
            )
            _validate_proposal_candidate_evaluation(candidate, manifest_path)
            with self.assertRaisesRegex(RuntimeError, "unsupported proposal promotion"):
                _validate_proposal_promotion(candidate, manifest_path)
            valid_evaluation_manifest = manifest_path.read_text("utf-8")
            stale_evaluation_manifest = json.loads(valid_evaluation_manifest)
            stale_evaluation_manifest[
                "experiment9_evaluation_source_sha256"
            ] = "0" * 64
            manifest_path.write_text(json.dumps(stale_evaluation_manifest), "utf-8")
            with self.assertRaisesRegex(RuntimeError, "evaluation code is stale"):
                _validate_proposal_candidate_evaluation(candidate, manifest_path)
            manifest_path.write_text(valid_evaluation_manifest, "utf-8")
            stale_real = json.loads(real.read_text("utf-8"))
            stale_real["evaluation_source_sha256"] = "0" * 64
            real.write_text(json.dumps(stale_real), "utf-8")
            with self.assertRaisesRegex(RuntimeError, "evaluation code is stale"):
                authorize_candidate(candidate, large, real, manifest_path)

    def test_v2_candidate_contract_is_supported_but_still_gate_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); candidate = root / "candidate.pt"
            version = "pcdc-explicit-owner-typed-mixed-replay-labels/v2"
            label_sha = "d" * 64
            torch.save({
                "label_contract_version": version,
                "label_contract_sha256": label_sha,
            }, candidate)
            candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
            large = root / "large.json"; real = root / "real.json"
            large.write_text(json.dumps({
                "gate_pass": True, "checkpoint_sha256": "c" * 64,
                "label_contract": {
                    "version": version, "source_sha256": label_sha,
                },
            }), "utf-8")
            real.write_text(json.dumps({
                "gate_pass": True, "checkpoint_sha256": candidate_sha,
                "initialization_sha256": "c" * 64,
                "evaluation_source_sha256": EXPERIMENT9_EVALUATOR_SHA,
            }), "utf-8")
            manifest_path = root / "candidate.evaluation.json"
            authorize_candidate(candidate, large, real, manifest_path)
            _validate_proposal_candidate_evaluation(candidate, manifest_path)
            with self.assertRaisesRegex(RuntimeError, "unsupported proposal promotion"):
                _validate_proposal_promotion(candidate, manifest_path)

    def test_v4_candidate_requires_hash_bound_runtime_conformal_admission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); candidate = root / "candidate.pt"
            version = "pcdc-explicit-owner-counterfactual-mixed-replay-labels/v4"
            label_sha = "e" * 64
            torch.save({
                "label_contract_version": version,
                "label_contract_sha256": label_sha,
            }, candidate)
            candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
            large = root / "large.json"; real = root / "real.json"
            large.write_text(json.dumps({
                "gate_pass": True, "checkpoint_sha256": "c" * 64,
                "label_contract": {
                    "version": version, "source_sha256": label_sha,
                },
            }), "utf-8")
            base_real = {
                "gate_pass": True, "checkpoint_sha256": candidate_sha,
                "initialization_sha256": "c" * 64,
                "evaluation_source_sha256": EXPERIMENT9_EVALUATOR_SHA,
                "label_contract_version": version,
                "label_contract_sha256": label_sha,
            }
            real.write_text(json.dumps(base_real), "utf-8")
            manifest_path = root / "candidate.evaluation.json"
            with self.assertRaisesRegex(RuntimeError, "runtime conformal"):
                authorize_candidate(candidate, large, real, manifest_path)
            calibration = {
                "target_coverage": 0.99,
                "thresholds": [{
                    "family": "whole_shape", "alpha": 0.01,
                    "threshold": 0.25, "calibration_count": 100,
                    "empirical_coverage": 0.99,
                }],
                "global_threshold": 0.25,
                "split_policy": "unit-source-disjoint",
                "provenance": [
                    "finite-sample-higher-quantile",
                    "exact-runtime-prefix-rank-with-support-IoU-floor",
                ],
            }
            real.write_text(json.dumps({
                **base_real,
                "conformal_admission_contract": (
                    "exact-family-prefix-rank/support-IoU>=0.50/v1"
                ),
                "calibration": calibration,
                "runtime_conformal_admission": {
                    "contract": (
                        "exact-production-union+family-prefix+global-cap/v1"
                    ),
                    "exact_runtime_rule": True,
                    "all_quality_modes_coverage_ge_99pct": True,
                },
            }), "utf-8")
            manifest = authorize_candidate(
                candidate, large, real, manifest_path,
            )
            self.assertEqual(manifest["conformal_calibration"], calibration)
            self.assertTrue(manifest[
                "runtime_conformal_admission"
            ]["all_quality_modes_coverage_ge_99pct"])
            _validate_proposal_candidate_evaluation(candidate, manifest_path)

    def test_phase12_court_keeps_live_svg_mapping_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); assets = root / "assets"; court = root / "court"
            source = root / "source.png"
            Image.new("RGB", (48, 32), "white").save(source)
            ours = root / "ours.svg"; vai = root / "vai.svg"
            ours.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 32">'
                '<circle cx="16" cy="16" r="10"/></svg>', "utf-8",
            )
            vai.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 32">'
                '<rect x="6" y="6" width="20" height="20"/></svg>', "utf-8",
            )
            report = root / "report.json"
            report.write_text(json.dumps({
                "schema": "pcdc-experiment12/v1",
                "compiler_fingerprint": "f" * 64,
                "rows": [{
                    "id": "case-1", "status": "ok", "suite": "vai50",
                    "category": "text", "source": str(source),
                    "reference": str(vai), "size": [48, 32],
                    "exports": {"svg": {"path": str(ours)}},
                }],
            }), "utf-8")
            private = build_court(
                report, seed=7, court_root=court, web_assets=assets,
            )
            self.assertEqual(private["expected_count"], 1)
            self.assertIn(private["cases"][0]["ours_side"], {"A", "B"})
            self.assertTrue(all(path.suffix == ".svg" for path in assets.glob("*_?.svg")))
            with patch("web_preview.server.PHASE12_BLIND_ROOT", court):
                public, review = _phase12_blind_payload()
            self.assertNotIn("ours_side", public["cases"][0])
            self.assertNotIn("ours_sha256", public["cases"][0])
            self.assertTrue(public["display_contract"]["live_svg"])
            self.assertEqual(review["answers"], {})

    def test_final_campaign_reads_real_calibration_and_locked_live_svg_court(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calibration = root / "calibration.json"
            calibration.write_text(json.dumps({
                "gate_pass": True, "conformal_vacuous_classes": [],
                "evaluation_source_sha256": EXPERIMENT9_EVALUATOR_SHA,
                "test_conformal_coverage_by_family": {
                    "text_line": 1.0, "whole_shape": 0.99,
                },
            }), "utf-8")
            self.assertTrue(
                _proposal_calibration_evidence(calibration)["passed"],
            )
            calibration.write_text(json.dumps({
                "gate_pass": True, "conformal_vacuous_classes": [],
                "evaluation_source_sha256": EXPERIMENT9_EVALUATOR_SHA,
                "conformal_required_families": (
                    "text_line", "whole_shape", "appearance_model",
                ),
                "test_conformal_coverage_by_family": {
                    "text_line": 1.0, "whole_shape": 1.0,
                    "appearance_model": 0.98,
                },
            }), "utf-8")
            self.assertFalse(
                _proposal_calibration_evidence(calibration)["passed"],
            )
            review = root / "review.json"
            review.write_text(json.dumps({
                "schema": "pcdc-phase12-blind-vai-court/v1",
                "locked": True, "expected_count": 4,
                "display_contract": {
                    "live_svg": True, "equal_viewport": True,
                    "zoom_pan": True, "raster_downsample_forbidden": True,
                },
                "answers": {
                    "a": {"choice": "ours", "slice": "text"},
                    "b": {"choice": "vai", "slice": "text"},
                    "c": {"choice": "tie", "slice": "shape"},
                    "d": {"choice": "tie", "slice": "shape"},
                },
            }), "utf-8")
            evidence = _blind_parity_evidence(review)
            self.assertTrue(evidence["passed"])
            self.assertEqual(evidence["parity_score"], 0.5)

    def test_campaign_calibration_is_bound_to_candidate_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); report = root / "real.json"
            report.write_text(json.dumps({
                "gate_pass": True, "checkpoint_sha256": "a" * 64,
                "evaluation_source_sha256": EXPERIMENT9_EVALUATOR_SHA,
                "conformal_vacuous_classes": [],
                "test_conformal_coverage_by_family": {
                    "text_line": 1.0, "whole_shape": 1.0,
                },
            }), "utf-8")
            evaluation = root / "evaluation.json"
            evaluation.write_text(json.dumps({
                "real_report": str(report),
                "real_report_sha256": hashlib.sha256(
                    report.read_bytes(),
                ).hexdigest(),
            }), "utf-8")
            evidence = _bound_proposal_calibration_evidence({
                "manifest": str(evaluation),
                "manifest_sha256": hashlib.sha256(
                    evaluation.read_bytes(),
                ).hexdigest(),
                "checkpoint_sha256": "b" * 64,
            })
            self.assertFalse(evidence["passed"])
            self.assertFalse(evidence["candidate_bound"])

    def test_v2_promotion_binds_candidate_calibration_campaign_and_blind_court(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); candidate = root / "candidate.pt"
            version = "pcdc-explicit-owner-typed-mixed-replay-labels/v2"
            label_sha = "e" * 64
            torch.save({
                "label_contract_version": version,
                "label_contract_sha256": label_sha,
            }, candidate)
            candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
            real = root / "real.json"
            real.write_text(json.dumps({
                "gate_pass": True, "checkpoint_sha256": candidate_sha,
                "evaluation_source_sha256": EXPERIMENT9_EVALUATOR_SHA,
                "conformal_vacuous_classes": [],
                "conformal_required_families": ("text_line", "whole_shape"),
                "test_conformal_coverage_by_family": {
                    "text_line": 1.0, "whole_shape": 1.0,
                },
            }), "utf-8")
            evaluation = root / "evaluation.json"
            evaluation.write_text(json.dumps({
                "schema": "pcdc-proposal-candidate-evaluation/v1",
                "evaluation_ready": True,
                "large_training_gate_passed": True,
                "real_locus_gate_passed": True,
                "checkpoint_sha256": candidate_sha,
                "label_contract_version": version,
                "label_contract_sha256": label_sha,
                "experiment9_evaluation_source_sha256": (
                    EXPERIMENT9_EVALUATOR_SHA
                ),
                "real_report": str(real),
                "real_report_sha256": hashlib.sha256(
                    real.read_bytes(),
                ).hexdigest(),
            }), "utf-8")
            campaign = root / "campaign.json"
            campaign.write_text(json.dumps({
                "schema": "pcdc-experiment12/v1",
                "compiler_fingerprint": _compiler_fingerprint(
                    candidate, evaluation,
                ),
                "evaluation_source_sha256": evaluation_source_sha256(
                    "vice_compiler/experiment12_full_campaign.py",
                ),
                "proposal_evaluation": {
                    "mode": "candidate-evaluation",
                    "checkpoint_sha256": candidate_sha,
                },
                "gates": {
                    name: True for name in (
                        "valid_complete_build_freeze", "canonical_50_plus_115",
                        "all_requested_completed", "zero_timeout_or_error",
                        "deterministic_export", "zero_whole_scene_topology_failures",
                        "balanced_speed",
                    )
                },
            }), "utf-8")
            blind = root / "blind.json"
            blind.write_text(json.dumps({
                "schema": "pcdc-phase12-blind-vai-court/v1",
                "locked": True, "expected_count": 2,
                "display_contract": {
                    "live_svg": True, "equal_viewport": True,
                    "zoom_pan": True, "raster_downsample_forbidden": True,
                },
                "answers": {
                    "a": {"choice": "ours", "slice": "text"},
                    "b": {"choice": "tie", "slice": "shape"},
                },
            }), "utf-8")
            output = root / "promoted.pt"
            manifest = promote_candidate(
                candidate, evaluation, campaign, blind, output,
            )
            self.assertTrue(manifest["all_promotion_gates_passed"])
            self.assertEqual(manifest["label_contract_version"], version)
            _validate_proposal_promotion(
                output, output.with_suffix(output.suffix + ".promotion.json"),
            )

    def test_runtime_rejects_checkpoint_without_frozen_promotion_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "candidate.pt"
            checkpoint.write_bytes(b"candidate model bytes")
            worker = WarmProposalWorker(checkpoint)
            self.assertIsNone(worker.model)
            self.assertIn("unpromoted proposal checkpoint", worker.error or "")

    def test_promotion_sidecar_is_bound_to_exact_checkpoint_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "candidate.pt"
            manifest = Path(str(checkpoint) + ".promotion.json")
            label_sha = "a" * 64
            torch.save({
                "label_contract_version": "pcdc-source-disjoint-svg-owner-labels/v1",
                "label_contract_sha256": label_sha,
            }, checkpoint)
            manifest.write_text(json.dumps({
                "schema": "pcdc-proposal-runtime-promotion/v1",
                "promotion_ready": True,
                "all_promotion_gates_passed": True,
                "label_contract_version": "pcdc-source-disjoint-svg-owner-labels/v1",
                "label_contract_sha256": label_sha,
                "experiment9_evaluation_source_sha256": (
                    EXPERIMENT9_EVALUATOR_SHA
                ),
                "phase12_evaluation_source_sha256": evaluation_source_sha256(
                    "vice_compiler/experiment12_full_campaign.py",
                ),
                "checkpoint_sha256": hashlib.sha256(
                    checkpoint.read_bytes(),
                ).hexdigest(),
            }), encoding="utf-8")
            _validate_proposal_promotion(checkpoint, manifest)
            valid_manifest = manifest.read_text("utf-8")
            stale_manifest = json.loads(valid_manifest)
            stale_manifest["phase12_evaluation_source_sha256"] = "0" * 64
            manifest.write_text(json.dumps(stale_manifest), "utf-8")
            with self.assertRaisesRegex(RuntimeError, "evaluation code is stale"):
                _validate_proposal_promotion(checkpoint, manifest)
            manifest.write_text(valid_manifest, "utf-8")
            checkpoint.write_bytes(b"different candidate bytes")
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                _validate_proposal_promotion(checkpoint, manifest)

    def test_all_quality_tiers_have_hard_contracts(self) -> None:
        self.assertEqual(set(QUALITY_BUDGETS), set(QualityMode))
        for budget in QUALITY_BUDGETS.values():
            budget.validate()
            self.assertLessEqual(budget.exact_render_limit, 256)
            self.assertLessEqual(budget.phase5.shapes_per_roi, 4)
            self.assertLessEqual(budget.phase5.appearances_per_roi, 4)
        self.assertLess(QUALITY_BUDGETS[QualityMode.FAST].target_p95_ms, 2000.1)
        self.assertLess(QUALITY_BUDGETS[QualityMode.BALANCED].target_p95_ms, 5000.1)

    def test_worst_locus_damage_is_a_strict_incumbent_gate(self) -> None:
        source = np.full((96, 160, 3), 255, np.uint8)
        source[15:70, 20:130] = 20
        source[28:55, 42:108] = 255
        baseline = source.copy()
        candidate = source.copy()
        candidate[28:55, 75:108] = 20
        candidate[14:18, 130:145] = 20
        baseline_damage = visible_damage_metrics(baseline, source)
        candidate_damage = visible_damage_metrics(candidate, source)
        self.assertEqual(candidate_damage.catastrophic_locus_count, 2)
        self.assertGreater(
            candidate_damage.catastrophic_locus_count,
            baseline_damage.catastrophic_locus_count,
        )
        self.assertTrue(damage_regressed(candidate_damage, baseline_damage))

    def test_interface_dual_is_consumed_once_by_pricing(self) -> None:
        prices = DualPrices(
            cell_prices=(1.0, 2.0), interface_prices=(3.0, 4.0),
            topology_price=5.0, layer_price=7.0,
            provenance="test-single-interface-factor",
        )
        self.assertEqual(
            reduced_gain(0b11, 0.5, prices, (1, 1)),
            7.5,
        )
        self.assertEqual(
            reduced_gain(
                0b01, 0.0, prices, (),
                topology_claim=True, layer_claim=True,
            ),
            13.0,
        )
        with self.assertRaises(ValueError):
            reduced_gain(0b01, 0.0, prices, (2,))


class PersistentRuntimePhase10Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.path = root / "runtime.png"
        image = Image.new("RGB", (160, 96), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 54, 54), fill=(220, 30, 40))
        draw.rectangle((75, 14, 146, 50), outline=(20, 40, 100), width=4)
        draw.text((22, 68), "ABBA", fill="black")
        image.save(self.path)
        self.service = PersistentCompilerService(
            evidence_cache=EvidenceCache(root / "evidence"), recycle_after=2,
        )

    def tearDown(self) -> None:
        self.service.close(); self.temp.cleanup()

    def test_balanced_commits_typed_stages_only_after_full_render_gate(self) -> None:
        result = self.service.compile(self.path, mode="balanced")
        result.validate()
        self.assertIn(result.best_stage, {"T1", "T2", "T3", "T4"})
        if result.visible_render_audit is None:
            # A now-stronger exact fallback may Pareto-dominate every typed
            # proposal in the local court.  In that case no full-scene typed
            # transaction is needed or allowed.
            self.assertEqual(result.best_stage, "T1")
            self.assertIsNotNone(result.production_court_audit)
            self.assertEqual(result.production_court_audit.certified, 0)
            self.assertEqual(result.contract.visible_extractions, 0)
            self.assertEqual(result.contract.final_full_renders, 0)
        elif result.visible_render_audit.passed:
            stages = tuple(row.stage for row in result.checkpoints)
            self.assertIn(stages, {
                ("T0", "T1", "T2"),
                ("T0", "T1", "T2", "T3"),
                ("T0", "T1", "T2", "T4"),
                ("T0", "T1", "T2", "T3", "T4"),
            })
            self.assertEqual(result.contract.hidden_extractions, 1)
            self.assertEqual(len(result.finalists), 3)
            self.assertEqual(
                {row.profile for row in result.finalists},
                set(ExtractionProfile),
            )
            self.assertTrue(any(row.pareto for row in result.finalists))
            self.assertIsNotNone(result.extraction_profile)
            self.assertIsNotNone(result.design_program)
            self.assertIsNotNone(result.abstraction)
            if result.best_stage == "T3":
                self.assertTrue(result.refinement.committed)
                self.assertTrue(any(
                    "production-court-certified-delivery" in row
                    for row in result.refinement.provenance
                ))
        else:
            self.assertEqual(
                tuple(row.stage for row in result.checkpoints), ("T0", "T1")
            )
            self.assertEqual(result.contract.hidden_extractions, 0)
            self.assertIsNone(result.design_program)
            self.assertIsNone(result.abstraction)
        self.assertTrue(result.contract.one_reir_pass)
        self.assertEqual(
            result.contract.visible_extractions,
            int(result.visible_render_audit is not None),
        )
        self.assertEqual(
            result.contract.final_full_renders,
            int(result.visible_render_audit is not None),
        )
        self.assertLessEqual(result.contract.typed_rois, 64)
        self.assertEqual(result.contract.native_backend["language"], "rust")

    def test_expired_deadline_returns_complete_t1_not_partial_work(self) -> None:
        # Populate the evidence cache first; the second call proves that an
        # already-expired request still returns a complete hierarchy scene.
        self.service.compile(self.path, mode="fast")
        result = self.service.compile(self.path, mode="fast", deadline_ms=0.0)
        result.validate()
        self.assertTrue(result.deadline_exceeded)
        self.assertEqual(result.best_stage, "T1")
        self.assertEqual(result.contract.visible_extractions, 0)
        self.assertTrue(result.solution.fallback_always_feasible)
        self.assertIsNone(result.phase5_bundle)


if __name__ == "__main__":
    unittest.main()

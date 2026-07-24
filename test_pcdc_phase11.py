from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from vice_compiler.build_freeze import (
    _promotion_evidence_paths,
    build_freeze,
    verify_freeze,
)
from vice_compiler.build_identity import (
    compiler_source_sha256,
    production_compiler_sources,
)


class BuildFreezePhase11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_freeze()

    def test_freeze_covers_every_required_surface(self) -> None:
        # Phase 9 has no promoted checkpoint yet.  A BUILD_FREEZE that omits
        # the required hash-bound decision must stay explicitly incomplete.
        self.assertFalse(self.payload["complete"])
        self.assertTrue(any(
            Path(row).name == "proposal_net_v1.pt.promotion.json"
            for row in self.payload["missing"]
        ))
        self.assertEqual(len(self.payload["canonical_plan_sha256"]), 64)
        files = self.payload["files"]
        self.assertTrue(files["compiler_source"])
        self.assertTrue(files["native_core"])
        self.assertEqual({
            Path(row["path"]).name for row in files["models"]
        }, {
            "proposal_net_v1.pt", "proposal_net_v1.pt.promotion.json",
            "glyph_prior.pt", "glyph_prior_promotion.json",
            "wordmark_prior.pt", "wordmark_prior_promotion.json",
        })
        model_rows = {
            Path(row["path"]).name: row for row in files["models"]
        }
        self.assertFalse(model_rows["glyph_prior.pt"]["required"])
        self.assertFalse(model_rows["glyph_prior_promotion.json"]["required"])
        self.assertTrue(model_rows["wordmark_prior.pt"].get("required", True))
        self.assertTrue(model_rows[
            "wordmark_prior_promotion.json"
        ].get("required", True))
        self.assertGreaterEqual(len(files["ocr_model"]), 5)
        self.assertTrue(all(row["exists"] for row in files["ocr_model"]))
        self.assertGreaterEqual(len(files["font_catalog"]), 100)
        self.assertTrue(all(row["exists"] for row in files["font_catalog"]))
        self.assertEqual(len(files["canonical_experiment_reports"]), 8)
        canonical = {
            row["path"] for row in files["canonical_experiment_reports"]
        }
        stale = set(self.payload["stale_experiment_reports"])
        self.assertTrue(stale <= canonical)
        failed = set(self.payload["failed_experiment_reports"])
        self.assertTrue(failed <= canonical)
        current = compiler_source_sha256()
        for relative in stale:
            report = json.loads(Path(relative).read_text("utf-8"))
            compiler_stale = report.get("compiler_source_sha256") != current
            native_stale = bool(
                report.get("native_runtime_identity", {}).get("sha256")
                != self.payload["native_runtime_identity"]["sha256"]
            )
            runtime_stale = bool(
                Path(relative).parent.name == "pcdc_experiment10"
                and report.get("runtime_model_identity", {}).get("sha256")
                != self.payload["runtime_model_identity"]["sha256"]
            )
            evaluator_stale = bool(
                report.get("evaluation_source_sha256")
                != self.payload["canonical_evaluation_source_sha256"][
                    Path(relative).parent.name
                ]
            )
            expected_inputs = (
                self.payload["canonical_input_identities"]["real_locus"]
                if Path(relative).parent.name in {
                    "pcdc_experiment1", "pcdc_experiment1b",
                    "pcdc_experiment2", "pcdc_experiment4",
                    "pcdc_experiment9", "pcdc_experiment10",
                }
                else self.payload["canonical_input_identities"][
                    "certificate_court"
                ]
                if Path(relative).parent.name == "pcdc_experiment3"
                else None
            )
            inputs_stale = bool(
                expected_inputs is not None
                and report.get("input_identity", {}).get("sha256")
                != expected_inputs["sha256"]
            )
            glyph_artifact = self.payload["runtime_model_identity"].get(
                "artifacts", {}
            ).get("glyph:glyph_prior.pt")
            glyph_stale = bool(
                Path(relative).parent.name == "pcdc_experiment4"
                and glyph_artifact is not None
                and report.get("glyph_prior_checkpoint", {}).get("sha256")
                != glyph_artifact.get("sha256")
            )
            wordmark_artifact = self.payload["runtime_model_identity"].get(
                "artifacts", {}
            ).get("wordmark:wordmark_prior.pt")
            wordmark_stale = bool(
                Path(relative).parent.name == "pcdc_experiment4"
                and wordmark_artifact is not None
                and report.get("wordmark_prior_checkpoint", {}).get("sha256")
                != wordmark_artifact.get("sha256")
            )
            font_stale = bool(
                Path(relative).parent.name == "pcdc_experiment4"
                and report.get("font_catalog_identity", {}).get("sha256")
                != self.payload["canonical_input_identities"][
                    "font_catalog"
                ]["sha256"]
            )
            ocr_stale = bool(
                Path(relative).parent.name == "pcdc_experiment4"
                and report.get("ocr_model_identity", {}).get("sha256")
                != self.payload["runtime_model_identity"]["trocr"]["sha256"]
            )
            human = report.get("human", {})
            review_source = human.get("review_source")
            review_path = Path(str(review_source)) if review_source else None
            manifest_path = (
                review_path.with_name("human_manifest.json")
                if review_path is not None else None
            )
            human_stale = bool(
                review_path is None or manifest_path is None
                or not review_path.is_file() or not manifest_path.is_file()
                or human.get("review_sha256") != (
                    hashlib.sha256(review_path.read_bytes()).hexdigest()
                )
                or human.get("manifest_sha256") != (
                    hashlib.sha256(manifest_path.read_bytes()).hexdigest()
                )
            )
            self.assertTrue(
                compiler_stale or native_stale or runtime_stale or inputs_stale
                or glyph_stale or wordmark_stale or font_stale or ocr_stale
                or human_stale or evaluator_stale
            )
        for relative in failed:
            report = json.loads(Path(relative).read_text("utf-8"))
            self.assertIsNot(report.get("gate_pass"), True)
        self.assertEqual(self.payload["annotation_status"]["real_loci"]["count"], 300)
        self.assertEqual(self.payload["annotation_status"]["real_loci"]["pending"], 0)

    def test_compiler_identity_is_the_production_import_closure(self) -> None:
        relative = {
            path.relative_to(Path(__file__).resolve().parent).as_posix()
            for path in production_compiler_sources()
        }
        self.assertIn("vice_compiler/runtime_service.py", relative)
        self.assertIn("vice_compiler/text_macros.py", relative)
        self.assertIn("vice_compiler/export_writer.py", relative)
        self.assertIn("font_match.py", relative)
        self.assertNotIn("vice_compiler/audit_plan_traceability.py", relative)
        self.assertNotIn("vice_compiler/train_proposal_net_large.py", relative)
        self.assertNotIn("vice_compiler/experiment4_textline.py", relative)

    def test_promotion_reports_are_part_of_the_frozen_artifact_closure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            training = root / "training.json"
            preflight = root / "preflight.json"
            short_logo = root / "short_logo.json"
            experiment = root / "experiment4.json"
            experiment_baseline = root / "experiment4_baseline.json"
            regression = root / "full_tests.json"
            for path in (
                training, preflight, short_logo, experiment, experiment_baseline,
                regression,
            ):
                path.write_text("{}", "utf-8")
            manifest = root / "promotion.json"
            manifest.write_text(json.dumps({
                "training_report": str(training),
                "preflight_report": str(preflight),
                "short_logo_audit_report": str(short_logo),
                "experiment4_report": str(experiment),
                "experiment4_baseline_report": str(experiment_baseline),
                "full_tests_report": str(regression),
                "unrelated": str(root / "not-evidence.bin"),
            }), "utf-8")
            self.assertEqual(set(_promotion_evidence_paths((manifest,))), {
                training.resolve(), preflight.resolve(), short_logo.resolve(),
                experiment.resolve(),
                experiment_baseline.resolve(), regression.resolve(),
            })

    def test_thresholds_calibration_renderers_and_human_courts_are_sealed(self) -> None:
        self.assertEqual(len(self.payload["thresholds_sha256"]), 64)
        self.assertEqual(self.payload["calibration"]["target_coverage"], 0.99)
        self.assertTrue(self.payload["calibration"]["vacuous_classes"])
        # Certificate, warm TextLine and exact/OCR/neural-text TextLine
        # courts each freeze their private manifest and answer ledger.
        self.assertEqual(
            len(self.payload["files"]["human_court_manifests_and_answers"]), 6,
        )
        self.assertTrue(self.payload["files"]["human_court_assets"])
        self.assertFalse(self.payload["human_court_asset_errors"])
        self.assertEqual(len(self.payload["files"]["renderer_sources"]), 3)
        self.assertFalse(self.payload["promotion_ready"])
        self.assertFalse(self.payload["proposal_runtime"]["enabled"])
        self.assertIn(
            "unpromoted proposal checkpoint",
            self.payload["proposal_runtime"]["validation_error"],
        )
        self.assertFalse(self.payload["glyph_prior_runtime"]["enabled"])
        self.assertIn(
            "production glyph prior or promotion manifest is missing",
            self.payload["glyph_prior_runtime"]["validation_error"],
        )
        self.assertFalse(any(
            "glyph prior" in blocker
            for blocker in self.payload["promotion_blockers"]
        ))
        self.assertFalse(self.payload["wordmark_prior_runtime"]["enabled"])
        self.assertIn(
            "production wordmark prior or promotion is missing",
            self.payload["wordmark_prior_runtime"]["validation_error"],
        )

    def test_written_freeze_verifies_and_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "freeze.json"
            path.write_text(json.dumps(self.payload), "utf-8")
            loaded = json.loads(path.read_text("utf-8"))
            valid, errors = verify_freeze(loaded)
            self.assertFalse(valid)
            self.assertTrue(any(
                error.startswith("missing:")
                and "proposal_net_v1.pt.promotion.json" in error
                for error in errors
            ))
            self.assertFalse(any(
                error.startswith("missing:") and "glyph_prior" in error
                for error in errors
            ))
            loaded["thresholds"]["renderer_model_limit"] = 99
            valid, errors = verify_freeze(loaded)
            self.assertFalse(valid)
            self.assertIn("freeze hash mismatch", errors)


if __name__ == "__main__":
    unittest.main()

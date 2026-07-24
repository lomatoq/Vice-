from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from vice_compiler.audit_plan_traceability import (
    _current_phase4_ablation_reports,
    _phase4_runtime_ablation_evidence,
)
from vice_compiler.build_identity import (
    bind_report,
    compiler_source_sha256,
    evaluation_source_sha256,
)
from vice_compiler.pre_v14_readiness import _load_artifact


class EvaluationSourceIdentityTests(unittest.TestCase):
    def test_report_binds_deterministic_evaluator_closure(self) -> None:
        source = "vice_compiler/experiment4_textline.py"
        expected = evaluation_source_sha256(source)
        self.assertEqual(len(expected), 64)
        self.assertEqual(evaluation_source_sha256(source), expected)
        self.assertEqual(
            bind_report({}, evaluator_source=source)[
                "evaluation_source_sha256"
            ],
            expected,
        )

    def test_pretraining_readiness_rejects_stale_evaluator(self) -> None:
        with TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact.json"
            artifact.write_text(json.dumps({
                "schema": "unit-artifact/v1",
                "gate_pass": True,
                "compiler_source_sha256": compiler_source_sha256(),
                "evaluation_source_sha256": "stale",
            }), "utf-8")
            passed, evidence = _load_artifact(
                artifact, schemas={"unit-artifact/v1"},
                passed=lambda row: row.get("gate_pass") is True,
                expected_evaluator_sha256="current",
            )
        self.assertFalse(passed)
        self.assertIn("evaluation-source", evidence["reasons"])


class Phase4WordmarkAblationDiscoveryTests(unittest.TestCase):
    @staticmethod
    def _report(*, candidate: bool) -> dict:
        rows = [
            {
                "id": f"line-{index:03d}",
                "candidate_mask_digest": (
                    "wordmark" if candidate and index == 7 else "baseline"
                ),
                "candidate_svg_digest": (
                    "wordmark-svg" if candidate and index == 7
                    else "baseline-svg"
                ),
            }
            for index in range(100)
        ]
        return {
            "schema": "pcdc-experiment4-textline/v2",
            "compiler_source_sha256": "current-compiler",
            "evaluation_source_sha256": "current-evaluator",
            "created_at": "2026-07-23T10:00:01Z" if candidate else
                          "2026-07-23T10:00:00Z",
            "wordmark_prior_checkpoint": (
                {"sha256": "candidate-sha"} if candidate else None
            ),
            "machine": {
                "all_reviewed_lines_not_worse": True,
                "candidate_mean_iou": 0.81 if candidate else 0.80,
                "candidate_gcr_rate": 0.10,
                "warm_p95_ms_per_line": 75.0,
                "full_p95_ms_per_line": 120.0,
            },
            "rows": rows,
        }

    def test_wordmark_identity_is_discovered_as_model_on_and_changes_delivery(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            reports = project / "benchmarks" / "pcdc_experiment4"
            reports.mkdir(parents=True)
            (reports / "baseline.json").write_text(
                json.dumps(self._report(candidate=False)), "utf-8",
            )
            (reports / "wordmark.json").write_text(
                json.dumps(self._report(candidate=True)), "utf-8",
            )
            with patch(
                "vice_compiler.audit_plan_traceability.PROJECT", project,
            ), patch(
                "vice_compiler.audit_plan_traceability."
                "compiler_source_sha256",
                return_value="current-compiler",
            ), patch(
                "vice_compiler.audit_plan_traceability."
                "evaluation_source_sha256",
                return_value="current-evaluator",
            ):
                baseline, candidate = _current_phase4_ablation_reports()
                evidence = _phase4_runtime_ablation_evidence(
                    expected_wordmark_sha256="candidate-sha",
                )
            self.assertEqual(
                baseline, "benchmarks/pcdc_experiment4/baseline.json",
            )
            self.assertEqual(
                candidate, "benchmarks/pcdc_experiment4/wordmark.json",
            )
            self.assertEqual(evidence["delivered_rows_changed"], 1)
            self.assertTrue(evidence["complete"])

    def test_another_neural_checkpoint_cannot_satisfy_wordmark_ablation(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            reports = project / "benchmarks" / "pcdc_experiment4"
            reports.mkdir(parents=True)
            (reports / "baseline.json").write_text(
                json.dumps(self._report(candidate=False)), "utf-8",
            )
            (reports / "wordmark.json").write_text(
                json.dumps(self._report(candidate=True)), "utf-8",
            )
            with patch(
                "vice_compiler.audit_plan_traceability.PROJECT", project,
            ), patch(
                "vice_compiler.audit_plan_traceability."
                "compiler_source_sha256",
                return_value="current-compiler",
            ), patch(
                "vice_compiler.audit_plan_traceability."
                "evaluation_source_sha256",
                return_value="current-evaluator",
            ):
                evidence = _phase4_runtime_ablation_evidence(
                    expected_wordmark_sha256="different-checkpoint",
                )
        self.assertFalse(evidence["complete"])
        self.assertFalse(evidence["checks"][
            "candidate_bound_to_trained_wordmark"
        ])

    def test_stale_evaluator_cannot_satisfy_wordmark_ablation(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            reports = project / "benchmarks" / "pcdc_experiment4"
            reports.mkdir(parents=True)
            baseline = self._report(candidate=False)
            candidate = self._report(candidate=True)
            candidate["evaluation_source_sha256"] = "stale-evaluator"
            (reports / "baseline.json").write_text(
                json.dumps(baseline), "utf-8",
            )
            (reports / "wordmark.json").write_text(
                json.dumps(candidate), "utf-8",
            )
            with patch(
                "vice_compiler.audit_plan_traceability.PROJECT", project,
            ), patch(
                "vice_compiler.audit_plan_traceability."
                "compiler_source_sha256",
                return_value="current-compiler",
            ), patch(
                "vice_compiler.audit_plan_traceability."
                "evaluation_source_sha256",
                return_value="current-evaluator",
            ):
                evidence = _phase4_runtime_ablation_evidence(
                    expected_wordmark_sha256="candidate-sha",
                )
        self.assertFalse(evidence["complete"])
        self.assertFalse(evidence["checks"]["candidate_report_current"])


if __name__ == "__main__":
    unittest.main()

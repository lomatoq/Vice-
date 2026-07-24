from __future__ import annotations

import unittest

from vice_compiler.audit_proposal_training_dynamics import (
    LEGACY_ANCHOR_FAMILIES, _anti_forgetting, _maximum_metric_delta,
)


def _metrics(recall: float, iou: float) -> dict:
    rows = {
        family: {
            "instances": 16,
            "neural_only_recall_at_5_iou50": recall,
            "mean_best_soft_iou_at_5": iou,
        }
        for family in LEGACY_ANCHOR_FAMILIES
    }
    rows["overall"] = {
        "instances": 64,
        "neural_only_recall_at_5_iou50": recall,
        "mean_best_soft_iou_at_5": iou,
    }
    return rows


class ProposalTrainingDynamicsTests(unittest.TestCase):
    def test_anti_forgetting_allows_only_bounded_anchor_drift(self) -> None:
        passed, audit = _anti_forgetting(
            _metrics(0.90, 0.80), _metrics(0.87, 0.77), 1.0, 1.05,
        )
        self.assertTrue(passed)
        self.assertAlmostEqual(audit["overall_recall_drop"], 0.03)
        failed, _audit = _anti_forgetting(
            _metrics(0.90, 0.80), _metrics(0.82, 0.77), 1.0, 1.05,
        )
        self.assertFalse(failed)

    def test_reproducibility_metric_delta_checks_every_stage(self) -> None:
        first = {
            "anchor_before": {"text_line": {"recall_at_5": 0.8}},
            "anchor_after": {"text_line": {"recall_at_5": 0.7}},
            "adaptation_after": {"stroke_network": {"recall_at_5": 0.9}},
        }
        second = {
            "anchor_before": {"text_line": {"recall_at_5": 0.8}},
            "anchor_after": {"text_line": {"recall_at_5": 0.69}},
            "adaptation_after": {"stroke_network": {"recall_at_5": 0.9}},
        }
        self.assertAlmostEqual(_maximum_metric_delta(first, second), 0.01)


if __name__ == "__main__":
    unittest.main()

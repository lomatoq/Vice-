from __future__ import annotations

import json
from pathlib import Path
import unittest

from vice_compiler.locus_corpus import TARGETS, validate_manifest
from vice_compiler.proposal_real_labels import PROPOSAL_FAMILIES
from vice_compiler.runtime_budget import StageBudget, StageProfiler
from web_preview.server import _clean_locus_review


ROOT = Path(__file__).resolve().parent


class RealLocusCorpusTests(unittest.TestCase):
    def test_manifest_is_exact_and_source_unique(self) -> None:
        path = ROOT / "datasets" / "pcdc_real_loci_v1" / "manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(validate_manifest(payload), [])
        self.assertEqual(payload["total"], 300)
        self.assertEqual(payload["counts"], dict(TARGETS))
        self.assertEqual(
            len({row["source"]["sha256"] for row in payload["loci"]}), 300
        )
        self.assertTrue(
            all(not row["source"]["vai_output"] for row in payload["loci"])
        )
        self.assertTrue(
            all(row["annotation_status"] == "pending_review" for row in payload["loci"])
        )

    def test_review_file_does_not_claim_unreviewed_truth(self) -> None:
        path = ROOT / "datasets" / "pcdc_real_loci_v1" / "review.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        reviews = payload.get("reviews", {})
        self.assertEqual(
            payload.get("complete_count", 0),
            sum(row.get("status") == "complete" for row in reviews.values()),
        )
        self.assertEqual(
            payload.get("ground_truth_derived_count", 0),
            sum(
                row.get("status") == "ground_truth_derived"
                for row in reviews.values()
            ),
        )
        self.assertEqual(
            payload.get("evidence_reviewed_count", 0),
            sum(
                row.get("status")
                in {"ground_truth_derived", "evidence_reviewed", "complete"}
                for row in reviews.values()
            ),
        )


class CompletenessLedgerTests(unittest.TestCase):
    def test_every_frozen_item_has_an_explicit_complete_row(self) -> None:
        path = ROOT / "benchmarks" / "pcdc_phase0" / "completeness_report.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(payload["complete"])
        vai50 = payload["campaigns"]["vai50"]
        challenge = payload["campaigns"]["challenge115"]
        self.assertEqual((vai50["complete_rows"], vai50["failed_rows"]), (50, 0))
        self.assertEqual(
            (challenge["complete_rows"], challenge["failed_rows"]), (115, 0)
        )
        self.assertEqual(len(vai50["rows"]), 50)
        self.assertEqual(len(challenge["rows"]), 115)


class StageProfilerTests(unittest.TestCase):
    def test_records_success_and_budget(self) -> None:
        profiler = StageProfiler({"tiny": StageBudget(wall_ms=1000)})
        with profiler.stage("tiny", item="fixture"):
            sum(range(100))
        summary = profiler.summary()
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["record_count"], 1)
        self.assertEqual(summary["records"][0]["metadata"], {"item": "fixture"})

    def test_records_failure_instead_of_dropping_stage(self) -> None:
        profiler = StageProfiler()
        with self.assertRaisesRegex(RuntimeError, "boom"):
            with profiler.stage("failure"):
                raise RuntimeError("boom")
        summary = profiler.summary()
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["by_stage"]["failure"]["failures"], 1)


class ReviewContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.locus = {"image": {"width": 20, "height": 10}}
        self.base = {
            "status": "evidence_reviewed",
            "roi_xyxy": [0, 0, 20, 10],
            "acceptable_support": "whole glyph support",
            "support_rle": [[0, 200]],
            "components": 1,
            "holes": 1,
            "macro_family": "text",
            "proposal_family": "text_line",
            "text_line_membership": "yes",
            "layer_relation": "none",
            "preferred_candidate": "",
            "reviewer": "fixture",
        }

    def test_evidence_review_accepts_complete_topology_fields(self) -> None:
        clean = _clean_locus_review(self.locus, self.base)
        self.assertEqual(clean["status"], "evidence_reviewed")
        self.assertEqual(clean["proposal_family"], "text_line")

    def test_unknown_proposal_family_is_rejected(self) -> None:
        raw = dict(self.base, proposal_family="stroke_diagram")
        self.assertNotIn(raw["proposal_family"], PROPOSAL_FAMILIES)
        with self.assertRaisesRegex(ValueError, "ProposalNet family"):
            _clean_locus_review(self.locus, raw)

    def test_one_logo_can_save_multiple_proposal_instances(self) -> None:
        raw = dict(self.base)
        raw["proposal_instances"] = [
            {
                "id": "mark", "proposal_family": "whole_shape",
            },
            {
                "id": "repeat",
                "proposal_family": "symmetry_repeat_group",
                "relation_contract": {
                    "schema": "query-relations/v1",
                    "family": "symmetry_repeat_group",
                    "positive": ["same_group", "repeat"],
                    "observable": ["same_group", "repeat", "mirror"],
                },
            },
        ]
        clean = _clean_locus_review(self.locus, raw)
        self.assertEqual(len(clean["proposal_instances"]), 2)
        self.assertEqual(
            clean["proposal_instances"][1]["relation_contract"]["positive"],
            ["same_group", "repeat"],
        )

    def test_relation_contract_cannot_claim_unobservable_positive(self) -> None:
        raw = dict(self.base)
        raw["proposal_instances"] = [{
            "id": "repeat", "proposal_family": "symmetry_repeat_group",
            "relation_contract": {
                "schema": "query-relations/v1",
                "family": "symmetry_repeat_group",
                "positive": ["repeat"],
                "observable": ["mirror"],
            },
        }]
        with self.assertRaisesRegex(ValueError, "relation tokens"):
            _clean_locus_review(self.locus, raw)

    def test_complete_requires_human_candidate_preference(self) -> None:
        raw = dict(self.base, status="complete")
        with self.assertRaisesRegex(ValueError, "preference"):
            _clean_locus_review(self.locus, raw)


if __name__ == "__main__":
    unittest.main()

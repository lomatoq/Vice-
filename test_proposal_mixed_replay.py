from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from vice_compiler.proposal_mixed_corpus import (
    build_mixed_corpus,
    validate_mixed_corpus,
)
from vice_compiler.proposal_replay import (
    expected_source_share,
    rebalance_source_share,
    rebalance_source_shares,
)
from vice_compiler.proposal_source_attestation import (
    create_source_attestation,
)


class ProposalMixedReplayTests(unittest.TestCase):
    @staticmethod
    def _root(parent: Path, name: str, source: str) -> Path:
        root = parent / name
        root.mkdir()
        Image.new("RGBA", (8, 8), "white").save(root / "sample.png")
        (root / "sample.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8">'
            '<rect x="2" y="2" width="4" height="4"/></svg>', "utf-8",
        )
        row = {
            "id": f"{source}:pair", "source_id": f"{source}:asset",
            "source": source, "input_png": "sample.png",
            "target_svg": "sample.svg", "size": 8,
        }
        (root / "pairs.jsonl").write_text(json.dumps(row) + "\n", "utf-8")
        (root / "report.json").write_text(
            json.dumps({"schema": f"unit-{source}"}), "utf-8",
        )
        return root

    def test_mixed_manifest_binds_origins_without_copying_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            base = self._root(parent, "base", "legacy")
            supplement = self._root(parent, "supplement", "synthetic-extra")
            out = parent / "mixed"
            report = build_mixed_corpus((base, supplement), out)
            self.assertEqual(report["pair_count"], 2)
            self.assertTrue(all(
                len(row["attestation_sha256"]) == 64
                for row in report["inputs"]
            ))
            self.assertTrue(all(
                row["payload_file_count"] == 2
                and len(row["payload_content_sha256"]) == 64
                for row in report["inputs"]
            ))
            self.assertFalse(report["split_audit"]["group_overlap"])
            self.assertEqual(
                sum(report["split_audit"]["group_counts"].values()), 2,
            )
            rows = [
                json.loads(line) for line in
                (out / "pairs.jsonl").read_text("utf-8").splitlines()
            ]
            self.assertTrue(all(Path(row["input_png"]).is_absolute() for row in rows))
            self.assertTrue(all(Path(row["target_svg"]).is_file() for row in rows))
            self.assertFalse((out / "sample.png").exists())
            self.assertEqual(validate_mixed_corpus(out)["pair_count"], 2)

    def test_recognized_factory_attestation_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            base = self._root(parent, "base", "legacy")
            supplement = self._root(parent, "supplement", "synthetic-extra")
            (supplement / "report.json").write_text(json.dumps({
                "schema": "pcdc-proposal-text-data-factory/v2",
                "pair_rows_sha256": "0" * 64,
                "factory_source_sha256": "0" * 64,
            }), "utf-8")
            with self.assertRaisesRegex(ValueError, "pair digest"):
                build_mixed_corpus((base, supplement), parent / "mixed")

    def test_external_corpus_override_is_versioned_and_payload_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            base = self._root(parent, "base", "legacy")
            supplement = self._root(parent, "supplement", "synthetic-extra")
            override = parent / "base-attestation.json"
            generator = parent / "origin-generator.py"
            generator.write_text("# deterministic unit generator\n", "utf-8")
            create_source_attestation(
                base, override, origin_generator_source=generator,
                renderer_prefix="unit-cairo-pillow",
            )
            out = parent / "mixed"
            report = build_mixed_corpus(
                (base, supplement), out,
                attestation_overrides=(override,),
            )
            record = next(
                row for row in report["inputs"]
                if row["root"] == str(base.resolve())
            )
            self.assertEqual(
                record["schema"],
                "pcdc-external-raster-vector-corpus-attestation/v2",
            )
            self.assertEqual(record["attestation_path"], str(override.resolve()))
            mixed_rows = [
                json.loads(line) for line in
                (out / "pairs.jsonl").read_text("utf-8").splitlines()
            ]
            base_row = next(row for row in mixed_rows if row["source"] == "legacy")
            self.assertEqual(
                base_row["augmentation"]["renderer"],
                "unit-cairo-pillow-png/v1",
            )
            self.assertEqual(validate_mixed_corpus(out)["pair_count"], 2)
            payload = json.loads(override.read_text("utf-8"))
            payload["payload_content_sha256"] = "0" * 64
            override.write_text(json.dumps(payload), "utf-8")
            with self.assertRaisesRegex(ValueError, "attestation digest"):
                validate_mixed_corpus(out)

    def test_replay_share_is_exact_and_preserves_within_stratum_ratios(self) -> None:
        rows = [
            {"source": "legacy"}, {"source": "legacy"},
            {"source": "synthetic-open-text"},
            {"source": "synthetic-open-text"},
        ]
        weights = np.asarray((1.0, 3.0, 2.0, 6.0))
        balanced = rebalance_source_share(
            rows, weights, source="synthetic-open-text", share=0.35,
        )
        self.assertAlmostEqual(expected_source_share(
            rows, balanced, source="synthetic-open-text",
        ), 0.35)
        self.assertAlmostEqual(balanced[3] / balanced[2], 3.0)
        self.assertAlmostEqual(balanced[1] / balanced[0], 3.0)

    def test_multiple_supplements_get_simultaneous_fixed_mass(self) -> None:
        rows = [
            {"source": "legacy"}, {"source": "legacy"},
            {"source": "synthetic-open-text"},
            {"source": "synthetic-structure-v2"},
            {"source": "synthetic-structure-v2"},
        ]
        balanced = rebalance_source_shares(
            rows, np.asarray((1.0, 2.0, 7.0, 3.0, 9.0)),
            shares={
                "synthetic-open-text": 0.30,
                "synthetic-structure-v2": 0.30,
            },
        )
        self.assertAlmostEqual(expected_source_share(
            rows, balanced, source="synthetic-open-text",
        ), 0.30)
        self.assertAlmostEqual(expected_source_share(
            rows, balanced, source="synthetic-structure-v2",
        ), 0.30)
        self.assertAlmostEqual(balanced[4] / balanced[3], 3.0)


if __name__ == "__main__":
    unittest.main()

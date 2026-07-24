from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vice_compiler.experiment_inputs import (
    artifact_set_identity, real_locus_input_identity,
)


class ExperimentInputIdentityTests(unittest.TestCase):
    def test_real_locus_identity_verifies_actual_source_bytes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            source.write_bytes(b"abc")
            source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            (root / "manifest.json").write_text(json.dumps({
                "loci": [{
                    "id": "one",
                    "source": {"path": str(source), "sha256": source_sha},
                }],
            }), "utf-8")
            (root / "review.json").write_text(
                json.dumps({"reviews": {"one": {"status": "complete"}}}),
                "utf-8",
            )
            identity = real_locus_input_identity(root)
            self.assertEqual(identity["source_file_count"], 1)
            self.assertEqual(len(identity["sha256"]), 64)

            # Same length, different bytes: a timestamp/size cache must not
            # let a replaced evidence image inherit the prior experiment.
            source.write_bytes(b"xyz")
            with self.assertRaisesRegex(ValueError, "declared hash"):
                real_locus_input_identity(root)

    def test_artifact_identity_changes_with_answer_ledger(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "human_manifest.json"
            review = root / "review.json"
            manifest.write_text("{}", "utf-8")
            review.write_text('{"answers":{}}', "utf-8")
            first = artifact_set_identity({
                "manifest": manifest, "review": review,
            })
            review.write_text('{"answers":{"one":"A"}}', "utf-8")
            second = artifact_set_identity({
                "manifest": manifest, "review": review,
            })
            self.assertNotEqual(first["sha256"], second["sha256"])


if __name__ == "__main__":
    unittest.main()

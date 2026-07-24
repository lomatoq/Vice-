from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from vice_compiler.archive_proposal_contract import archive


class ProposalContractArchiveTests(unittest.TestCase):
    def test_archive_preserves_every_bound_source_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = archive(Path(directory))
            self.assertEqual(len(report["sources"]), 8)
            self.assertEqual(len(report["label_contract_sha256"]), 64)
            self.assertTrue(all(
                (Path(directory) / row["archive"]).is_file()
                and len(row["sha256"]) == 64
                for row in report["sources"]
            ))


if __name__ == "__main__":
    unittest.main()

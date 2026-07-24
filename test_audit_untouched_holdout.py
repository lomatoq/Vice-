from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vice_compiler.audit_untouched_holdout import audit_rows
from vice_compiler.proposal_data_contract import RELATION_TYPES
from vice_compiler.train_proposal_net_large import _split_group, _stable_bucket


class UntouchedHoldoutAuditTests(unittest.TestCase):
    @staticmethod
    def _row(root: Path, split: str, suffix: str, *, webp: bool) -> dict:
        for index in range(10_000):
            source_id = f"structure-v2:appearance_model:{suffix}:{index}"
            row = {
                "id": f"{suffix}:{index}",
                "source": "synthetic-structure-v2",
                "source_id": source_id,
                "macro_family_contract": {
                    "schema": "typed-generator/v2",
                    "families": ["appearance_model"],
                },
                "relation_contract": {
                    "schema": "query-relations/v1",
                    "family": "appearance_model",
                    "positive": ["same_appearance"],
                    "observable": list(RELATION_TYPES),
                },
            }
            if _stable_bucket(_split_group(row)) == split:
                break
        else:
            raise AssertionError(f"cannot synthesize a {split} split row")
        image = root / f"{suffix}.png"
        vector = root / f"{suffix}.svg"
        image.write_bytes(f"png:{suffix}".encode())
        vector.write_bytes(f"svg:{suffix}".encode())
        row.update({
            "input_png": image.name,
            "target_svg": vector.name,
            "augmentation": {
                "renderer": (
                    "resvg-pillow-webp/v1"
                    if webp else "resvg-pillow-png/v1"
                ),
                "webp_quality": 74 if webp else None,
            },
        })
        return row

    def test_webp_test_rows_are_sealed_and_payload_disjoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [
                self._row(root, "train", "train", webp=False),
                self._row(root, "calibration", "cal", webp=False),
                self._row(root, "test", "test", webp=True),
            ]
            report = audit_rows(
                rows, root, root / "future-v14.pt",
                minimum_holdout_rows=1, minimum_family_rows=0,
            )
            self.assertTrue(report["passed"])
            self.assertEqual(
                report["held_out_renderers"], ["resvg-pillow-webp/v1"],
            )
            self.assertEqual(report["held_out_degradations"], ["webp"])

    def test_duplicate_target_payload_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train = self._row(root, "train", "train", webp=False)
            test = self._row(root, "test", "test", webp=True)
            (root / test["target_svg"]).write_bytes(
                (root / train["target_svg"]).read_bytes(),
            )
            report = audit_rows(
                [train, test], root, root / "future-v14.pt",
                minimum_holdout_rows=1, minimum_family_rows=0,
            )
            self.assertTrue(report["contamination_detected"])
            self.assertFalse(report["passed"])


if __name__ == "__main__":
    unittest.main()

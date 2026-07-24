from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

from vice_compiler.proposal_filter_cache import (
    build_filter_cache, build_filter_cache_from_scan,
    corpus_data_contract_sha256, validate_filter_cache,
)


class ProposalFilterCacheTests(unittest.TestCase):
    def test_report_derived_cache_replays_only_bound_accepted_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [
                {"id": "accepted", "source_id": "a"},
                {"id": "rejected", "source_id": "b"},
            ]
            (root / "pairs.jsonl").write_text("".join(
                json.dumps(row) + "\n" for row in rows
            ), "utf-8")
            report = {
                "schema": "pcdc-proposal-large-training/v2-honest-top5",
                "raw_pair_count": 2, "pair_count": 1,
                "corpus_data_contract_sha256": corpus_data_contract_sha256(root),
                "rejected_pairs": [{
                    "id": "rejected", "reason": "unobservable-raster",
                }],
            }
            report_path = root / "report.json"
            report_path.write_text(json.dumps(report), "utf-8")
            cache_path = root / "cache.json"
            build_filter_cache(root, report_path, cache_path)
            accepted, rejected = validate_filter_cache(
                cache_path, rows,
                training_data_contract_sha256=corpus_data_contract_sha256(root),
            )
            self.assertEqual([row["id"] for row in accepted], ["accepted"])
            self.assertEqual(rejected[0]["id"], "rejected")

    def test_cache_rejects_another_data_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [{"id": "accepted", "source_id": "a"}]
            (root / "pairs.jsonl").write_text(
                json.dumps(rows[0]) + "\n", "utf-8",
            )
            report_path = root / "report.json"
            report_path.write_text(json.dumps({
                "schema": "pcdc-proposal-large-training/v2-honest-top5",
                "raw_pair_count": 1, "pair_count": 1,
                "corpus_data_contract_sha256": corpus_data_contract_sha256(root),
                "rejected_pairs": [],
            }), "utf-8")
            cache_path = root / "cache.json"
            build_filter_cache(root, report_path, cache_path)
            with self.assertRaisesRegex(ValueError, "another data contract"):
                validate_filter_cache(
                    cache_path, rows, training_data_contract_sha256="b" * 64,
                )

    def test_scan_builds_filter_before_any_training_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "images").mkdir()
            (root / "vectors").mkdir()
            visible = np.full((32, 32, 4), 255, np.uint8)
            visible[8:24, 10:22, :3] = 0
            Image.fromarray(visible, "RGBA").save(root / "images" / "visible.png")
            (root / "vectors" / "rect.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
                '<rect x="10" y="8" width="12" height="16"/></svg>',
                "utf-8",
            )
            row = {
                "id": "visible", "source": "unit", "source_id": "unit:visible",
                "input_png": "images/visible.png", "target_svg": "vectors/rect.svg",
                "size": 32, "augmentation": {
                    "scale": 1.0, "shift_x": 0, "shift_y": 0,
                    "rotate_degrees": 0.0,
                },
            }
            (root / "pairs.jsonl").write_text(json.dumps(row) + "\n", "utf-8")
            cache_path = root / "cache.json"
            payload = build_filter_cache_from_scan(root, cache_path)
            self.assertEqual(payload["schema"], "pcdc-proposal-filter-cache/v2")
            accepted, rejected = validate_filter_cache(
                cache_path, [row],
                training_data_contract_sha256=corpus_data_contract_sha256(root),
            )
            self.assertEqual([value["id"] for value in accepted], ["visible"])
            self.assertFalse(rejected)

    def test_module_cli_writes_scan_cache_after_all_helpers_are_defined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "images").mkdir()
            (root / "vectors").mkdir()
            visible = np.full((32, 32, 4), 255, np.uint8)
            visible[8:24, 10:22, :3] = 0
            Image.fromarray(visible, "RGBA").save(root / "images" / "visible.png")
            (root / "vectors" / "rect.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
                '<rect x="10" y="8" width="12" height="16"/></svg>',
                "utf-8",
            )
            row = {
                "id": "visible", "source": "unit", "source_id": "unit:visible",
                "input_png": "images/visible.png", "target_svg": "vectors/rect.svg",
                "size": 32, "augmentation": {
                    "scale": 1.0, "shift_x": 0, "shift_y": 0,
                    "rotate_degrees": 0.0,
                },
            }
            (root / "pairs.jsonl").write_text(json.dumps(row) + "\n", "utf-8")
            cache_path = root / "cache.json"
            completed = subprocess.run(
                [
                    sys.executable, "-m", "vice_compiler.proposal_filter_cache",
                    "--pair-root", str(root), "--out", str(cache_path),
                ],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(cache_path.is_file())
            self.assertEqual(
                json.loads(cache_path.read_text("utf-8"))["accepted_ids"],
                ["visible"],
            )

    def test_scan_rejects_target_that_vanishes_after_recorded_transform(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "images").mkdir()
            (root / "vectors").mkdir()
            visible = np.full((96, 96, 4), 255, np.uint8)
            visible[72, 41:46, :3] = (242, 249, 245)
            Image.fromarray(visible, "RGBA").save(root / "images" / "visible.png")
            (root / "vectors" / "rect.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" '
                'viewBox="0 0 256 256"><path fill="#16a34a" '
                'd="M 95.18 207.13 L 80.09 208.72 L 129.91 202.84 Z"/></svg>',
                "utf-8",
            )
            row = {
                "id": "vanished-target", "source": "unit",
                "source_id": "unit:vanished-target",
                "input_png": "images/visible.png",
                "target_svg": "vectors/rect.svg", "size": 96,
                "augmentation": {
                    "scale": 0.7314, "shift_x": 3, "shift_y": 3,
                    "rotate_degrees": 0.0,
                },
            }
            (root / "pairs.jsonl").write_text(
                json.dumps(row) + "\n", "utf-8",
            )
            payload = build_filter_cache_from_scan(root, root / "cache.json")
            self.assertEqual(payload["accepted_ids"], [])
            self.assertEqual(
                payload["rejected_pairs"],
                [{
                    "id": "vanished-target",
                    "reason": "unobservable-clean-target",
                    "alignment_iou": 0.0,
                }],
            )

    def test_scan_rejects_nonempty_but_misaligned_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "images").mkdir()
            (root / "vectors").mkdir()
            visible = np.full((32, 32, 4), 255, np.uint8)
            visible[2:10, 2:10, :3] = 0
            Image.fromarray(visible, "RGBA").save(root / "images" / "visible.png")
            (root / "vectors" / "rect.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
                '<rect x="20" y="20" width="8" height="8"/></svg>',
                "utf-8",
            )
            row = {
                "id": "misaligned-target", "source": "unit",
                "source_id": "unit:misaligned-target",
                "input_png": "images/visible.png",
                "target_svg": "vectors/rect.svg", "size": 32,
                "augmentation": {
                    "scale": 1.0, "shift_x": 0, "shift_y": 0,
                    "rotate_degrees": 0.0,
                },
            }
            (root / "pairs.jsonl").write_text(
                json.dumps(row) + "\n", "utf-8",
            )
            payload = build_filter_cache_from_scan(root, root / "cache.json")
            self.assertEqual(payload["accepted_ids"], [])
            self.assertEqual(
                payload["rejected_pairs"][0]["reason"],
                "target-alignment-below-proof-floor",
            )
            self.assertLess(
                payload["rejected_pairs"][0]["alignment_iou"], 0.35,
            )

    def test_threaded_scan_preserves_order_across_bounded_batches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "images").mkdir()
            (root / "vectors").mkdir()
            visible = np.full((16, 16, 4), 255, np.uint8)
            visible[4:12, 5:11, :3] = 0
            Image.fromarray(visible, "RGBA").save(root / "images" / "visible.png")
            (root / "vectors" / "rect.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
                '<rect x="5" y="4" width="6" height="8"/></svg>',
                "utf-8",
            )
            rows = [{
                "id": f"visible-{index:04d}", "source": "unit",
                "source_id": f"unit:visible:{index:04d}",
                "input_png": "images/visible.png",
                "target_svg": "vectors/rect.svg", "size": 16,
                "augmentation": {
                    "scale": 1.0, "shift_x": 0, "shift_y": 0,
                    "rotate_degrees": 0.0,
                },
            } for index in range(1030)]
            (root / "pairs.jsonl").write_text("".join(
                json.dumps(row) + "\n" for row in rows
            ), "utf-8")
            payload = build_filter_cache_from_scan(root, root / "cache.json")
            self.assertEqual(
                payload["accepted_ids"], [row["id"] for row in rows],
            )


if __name__ == "__main__":
    unittest.main()

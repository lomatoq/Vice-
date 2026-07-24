from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from vice_compiler.proposal_structure_data_factory import (
    FAMILIES, _source_split, build_pair, build_sources, generate,
)
from vice_compiler.proposal_data_contract import RELATION_TYPES, relation_supervision
from vice_compiler.proposal_net import HARD_NEGATIVE_TYPES
from vice_compiler.train_proposal_net_large import PairDataset, _svg_families


class ProposalStructureDataFactoryTests(unittest.TestCase):
    def test_each_typed_source_has_the_claimed_render_inference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source in build_sources(count=8, seed=41):
                path = root / f"{source['family']}-{source['prototype']}.svg"
                path.write_text(source["svg"], "utf-8")
                row = {
                    **source, "target_svg": path.name,
                    "source_id": source["id"],
                }
                self.assertEqual(_svg_families(row, root), (source["family"],))

    def test_smoke_factory_is_balanced_and_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "factory"
            report = generate(
                out, source_count=8, variants=2, workers=2, seed=43,
            )
            self.assertEqual(report["pair_count"], 16)
            self.assertEqual(set(report["family_source_counts"]), set(FAMILIES))
            self.assertEqual(set(report["family_source_counts"].values()), {2})
            rows = [
                json.loads(line) for line in
                (out / "pairs.jsonl").read_text("utf-8").splitlines()
            ]
            self.assertTrue(all(
                row["macro_family_contract"]["schema"] == "typed-generator/v2"
                and row["relation_contract"]["schema"] == "query-relations/v1"
                and (out / row["input_png"]).is_file()
                and (out / row["target_svg"]).is_file()
                for row in rows
            ))
            self.assertEqual(report["schema"], "pcdc-proposal-structure-data-factory/v2")
            families = {
                row["id"]: _svg_families(row, out) for row in rows
            }
            for index in range(len(rows)):
                sample = PairDataset(rows, out, families)[index]
                self.assertGreater(len(sample["family"]), 0)
                semantic_negative = {
                    "appearance_model": "gradient_band_explosion",
                    "stroke_network": "stroke_fill_confusion",
                    "layer_relation": "wrong_layer",
                }.get(families[rows[index]["id"]][0])
                if semantic_negative is not None:
                    self.assertIn(
                        HARD_NEGATIVE_TYPES.index(semantic_negative),
                        sample["hard_negative"].tolist(),
                    )

    def test_test_split_gets_an_unseen_webp_renderer_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            source = next(
                row for row in build_sources(count=128, seed=53)
                if _source_split(row["id"]) == "test"
            )
            png_or_jpeg = build_pair(source, 0, out, seed=53)
            webp = build_pair(source, 1, out, seed=53)
            self.assertNotEqual(
                png_or_jpeg["augmentation"]["renderer"],
                "resvg-pillow-webp/v1",
            )
            self.assertEqual(
                webp["augmentation"]["renderer"],
                "resvg-pillow-webp/v1",
            )
            self.assertIsNotNone(webp["augmentation"]["webp_quality"])
            self.assertIsNone(webp["augmentation"]["jpeg_quality"])
            self.assertTrue((out / webp["input_png"]).is_file())

    def test_relation_factory_has_positive_and_negative_examples_for_every_token(self) -> None:
        positives = {name: 0 for name in RELATION_TYPES}
        negatives = {name: 0 for name in RELATION_TYPES}
        sources = build_sources(count=256, seed=47)
        repeats = [
            row for row in sources
            if row["family"] == "symmetry_repeat_group"
        ]
        mirrors = [row for row in repeats if row["prototype"] == "mirror"]
        self.assertGreaterEqual(len(mirrors), len(repeats) // 2)
        self.assertTrue(all(
            {"repeat", "mirror"}.issubset(
                row["relation_contract"]["positive"],
            )
            for row in mirrors
        ))
        for row in sources:
            positive, observable = relation_supervision(row, row["family"])
            for name in observable:
                (positives if name in positive else negatives)[name] += 1
        text_row = {
            "source": "synthetic-open-text",
            "owner_contract": {
                "schema": "explicit-svg-groups/v1", "owner_ids": ["line-0"],
            },
        }
        positive, observable = relation_supervision(text_row, "text_line")
        for name in observable:
            (positives if name in positive else negatives)[name] += 1
        self.assertTrue(all(positives.values()), positives)
        self.assertTrue(all(negatives.values()), negatives)


if __name__ == "__main__":
    unittest.main()

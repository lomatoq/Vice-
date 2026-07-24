from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from vice_compiler.proposal_text_data_factory import (
    build_source_svg, generate, load_licensed_fonts,
)


class ProposalTextDataFactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = Path("fonts/google-fonts-manifest.json")

    def test_compound_svg_has_explicit_separate_owner_groups(self) -> None:
        _manifest, fonts = load_licensed_fonts(self.manifest)
        svg, owners, dimensions = build_source_svg(
            fonts[0], ("VECTOR", "digital studio"), seed=17,
        )
        root = ET.fromstring(svg)
        groups = [
            row for row in root.iter()
            if row.attrib.get("data-pcdc-owner") == "text-line"
        ]
        self.assertEqual(len(groups), 2)
        self.assertEqual(len(owners), 2)
        self.assertTrue(all(value > 0 for value in dimensions))
        self.assertNotEqual(groups[0].attrib["data-pcdc-owner-id"],
                            groups[1].attrib["data-pcdc-owner-id"])

    def test_smoke_factory_binds_fonts_sources_pairs_and_variants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "factory"
            report = generate(
                self.manifest, out, source_count=3,
                variants=2, workers=2, seed=23,
            )
            self.assertEqual(report["source_count"], 3)
            self.assertEqual(report["pair_count"], 6)
            self.assertEqual(report["owner_contract"], "explicit-svg-groups/v1")
            pairs = [
                json.loads(line) for line in
                (out / "pairs.jsonl").read_text("utf-8").splitlines()
            ]
            self.assertEqual(len(pairs), 6)
            self.assertTrue(all(
                (out / row["input_png"]).is_file()
                and (out / row["target_svg"]).is_file()
                for row in pairs
            ))
            self.assertEqual(
                {row["owner_contract"]["schema"] for row in pairs},
                {"explicit-svg-groups/v1"},
            )


if __name__ == "__main__":
    unittest.main()

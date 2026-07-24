from __future__ import annotations

from pathlib import Path
import unittest

import numpy as np

from vice_compiler.explicit_svg_owners import (
    explicit_svg_owners, has_explicit_owner_contract,
)
from vice_compiler.proposal_text_data_factory import (
    build_source_svg, load_licensed_fonts,
)
from vice_compiler.proposal_instance_labels import (
    _project_mask, augmented_svg_owner_targets, svg_owner_templates,
)


class ExplicitSvgOwnerTests(unittest.TestCase):
    def test_factory_rows_render_as_exact_separate_owners(self) -> None:
        _manifest, fonts = load_licensed_fonts(
            Path("fonts/google-fonts-manifest.json"),
        )
        svg, owner_ids, _dimensions = build_source_svg(
            fonts[0], ("VECTOR", "digital studio", "EST. 2026"), seed=31,
        )
        self.assertTrue(has_explicit_owner_contract(svg))
        result = explicit_svg_owners(svg, render_width=384)
        self.assertEqual([row.owner_id for row in result.owners], list(owner_ids))
        self.assertEqual([row.family for row in result.owners], ["text_line"] * 3)
        self.assertTrue(all(not row.mask.flags.writeable for row in result.owners))
        for left, right in zip(result.owners, result.owners[1:]):
            self.assertFalse(np.any(left.mask & right.mask))
        self.assertTrue(np.array_equal(
            np.logical_or.reduce([row.mask for row in result.owners]),
            result.full_mask,
        ))

    def test_duplicate_owner_identity_fails_closed(self) -> None:
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10"
          data-pcdc-owner-contract="explicit-groups/v1">
          <g data-pcdc-owner="text-line" data-pcdc-owner-id="same">
            <rect width="5" height="5"/></g>
          <g data-pcdc-owner="text-line" data-pcdc-owner-id="same">
            <rect x="10" width="5" height="5"/></g>
        </svg>"""
        with self.assertRaisesRegex(ValueError, "unique"):
            explicit_svg_owners(svg)

    def test_three_rows_use_three_line_slots_and_one_compound_glyph_slot(self) -> None:
        _manifest, fonts = load_licensed_fonts(
            Path("fonts/google-fonts-manifest.json"),
        )
        svg, _owner_ids, _dimensions = build_source_svg(
            fonts[0], ("VECTOR", "digital studio", "EST. 2026"), seed=37,
        )
        templates = svg_owner_templates(svg, render_width=384)
        row = {
            "size": 128,
            "augmentation": {
                "scale": 0.75, "shift_x": 1, "shift_y": -1,
                "rotate_degrees": 0.0,
            },
        }
        observed = _project_mask(
            templates.full_mask, size=128, scale=0.75,
            shift_x=1, shift_y=-1, rotate_degrees=0.0,
        )
        targets, alignment_iou = augmented_svg_owner_targets(
            templates, row, observed,
        )
        self.assertAlmostEqual(alignment_iou, 1.0)
        self.assertEqual(
            [family for family, _mask in targets],
            ["text_line", "text_line", "text_line", "glyph_group"],
        )
        line_union = np.logical_or.reduce([
            mask for family, mask in targets if family == "text_line"
        ])
        glyph = next(mask for family, mask in targets if family == "glyph_group")
        self.assertTrue(np.array_equal(line_union, glyph))
        self.assertLessEqual(len(targets) + 1, 5)  # optional degradation risk


if __name__ == "__main__":
    unittest.main()

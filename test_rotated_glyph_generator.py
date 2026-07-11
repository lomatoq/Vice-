import json
import tempfile
import unittest
from pathlib import Path

from svgpathtools import svg2paths2

import build_corner_dataset as builder
import generate_rotated_glyph_pilot as generator
from svg_corner_gt import frame_loop_examples, unsupported_reason, visible_svg_regions


FONT = Path(r"C:/Windows/Fonts/arial.ttf")


def _painted_bounds_without_anchors(svg: Path) -> tuple[float, float, float, float]:
    paths, _attributes, _svg_attributes = svg2paths2(str(svg))
    boxes = []
    for subpath in paths[0].continuous_subpaths():
        box = subpath.bbox()
        if box[1] - box[0] > 1e-8 or box[3] - box[2] > 1e-8:
            boxes.append(box)
    return (
        min(box[0] for box in boxes), max(box[1] for box in boxes),
        min(box[2] for box in boxes), max(box[3] for box in boxes),
    )


@unittest.skipUnless(FONT.exists(), "Arial is required for the Windows glyph pilot")
class RotatedGlyphGeneratorTests(unittest.TestCase):
    def test_parser_accepts_configurable_angles_and_phase_pairs(self):
        self.assertEqual(generator.parse_angles("-30, 0,15,0"), [-30.0, 0.0, 15.0])
        self.assertEqual(
            generator.parse_phases("0:0, .25:.5,0:0"),
            [(0.0, 0.0), (0.25, 0.5)],
        )

    def test_generation_is_byte_deterministic_and_metadata_is_complete(self):
        with tempfile.TemporaryDirectory(dir="tmp") as first_dir, tempfile.TemporaryDirectory(
            dir="tmp"
        ) as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            kwargs = dict(
                font_path=FONT,
                chars="AL",
                angles=[0.0, 27.5],
                phases=[(0.0, 0.0), (0.25, 0.5)],
                reference_resolution=32,
            )
            first_manifest = generator.generate(out=first, **kwargs)
            second_manifest = generator.generate(out=second, **kwargs)
            self.assertEqual(first_manifest, second_manifest)
            self.assertEqual(first_manifest["count"], 8)
            self.assertEqual(
                (first / "manifest.json").read_bytes(),
                (second / "manifest.json").read_bytes(),
            )
            for record in first_manifest["records"]:
                first_svg = first / record["file"]
                second_svg = second / record["file"]
                self.assertEqual(first_svg.read_bytes(), second_svg.read_bytes())
                text = first_svg.read_text(encoding="utf-8")
                self.assertNotIn(" transform=", text)
                self.assertIn("exact-rotated-subpixel-glyph-v1", text)
                self.assertIsNone(unsupported_reason(first_svg))

            # Reusing an owned output root cannot leave variants from an older
            # configuration for build_corner_dataset to discover via rglob.
            reduced = generator.generate(
                FONT, first, chars="A", angles=[0.0], phases=[(0.0, 0.0)],
                reference_resolution=32,
            )
            self.assertEqual(reduced["count"], 1)
            self.assertEqual(len(list(first.rglob("*.svg"))), 1)

    def test_rotation_is_baked_into_outline_and_phase_survives_bbox_normalisation(self):
        with tempfile.TemporaryDirectory(dir="tmp") as directory:
            root = Path(directory)
            manifest = generator.generate(
                FONT, root, chars="L", angles=[0.0, 90.0],
                phases=[(0.0, 0.0), (0.5, 0.25)], reference_resolution=32,
            )
            records = manifest["records"]

            def source(angle, phase_x):
                record = next(
                    item for item in records
                    if item["angle_deg_clockwise_svg"] == angle and item["phase_x_px"] == phase_x
                )
                return root / record["file"], record

            zero, zero_record = source(0.0, 0.0)
            shifted, shifted_record = source(0.0, 0.5)
            rotated, _ = source(90.0, 0.0)
            zero_box = _painted_bounds_without_anchors(zero)
            shifted_box = _painted_bounds_without_anchors(shifted)
            rotated_box = _painted_bounds_without_anchors(rotated)
            scale = 32.0 / zero_record["canvas_units"]
            self.assertAlmostEqual((shifted_box[0] - zero_box[0]) * scale, 0.5, places=5)
            self.assertAlmostEqual((shifted_box[2] - zero_box[2]) * scale, 0.25, places=5)
            zero_frame = visible_svg_regions(zero, 32)
            shifted_frame = visible_svg_regions(shifted, 32)
            zero_candidates = zero_frame.regions[0].candidates
            shifted_candidates = shifted_frame.regions[0].candidates
            self.assertEqual(len(zero_candidates), len(shifted_candidates))
            for first, second in zip(zero_candidates, shifted_candidates):
                # This assertion exercises the real dataset loader.  Without
                # the zero-area frame anchors its bbox normalisation would
                # recenter both variants and both differences would be zero.
                self.assertAlmostEqual(second.x - first.x, 0.5, places=5)
                self.assertAlmostEqual(second.y - first.y, 0.25, places=5)
            self.assertAlmostEqual(zero_box[1] - zero_box[0], rotated_box[3] - rotated_box[2], places=4)
            self.assertAlmostEqual(zero_box[3] - zero_box[2], rotated_box[1] - rotated_box[0], places=4)
            self.assertNotEqual(
                zero.read_text(encoding="utf-8"), rotated.read_text(encoding="utf-8")
            )
            self.assertNotEqual(
                zero_record["affine_font_to_svg"], shifted_record["affine_font_to_svg"]
            )

    def test_builder_consumes_transform_free_samples_without_anchor_regions(self):
        with tempfile.TemporaryDirectory(dir="tmp") as directory:
            root = Path(directory)
            sources, dataset, preview = root / "sources", root / "dataset", root / "preview"
            manifest = generator.generate(
                FONT, sources, chars="A", angles=[-15.0, 15.0],
                phases=[(0.0, 0.0), (0.25, 0.5)], reference_resolution=32,
            )
            for record in manifest["records"]:
                frame = visible_svg_regions(sources / record["file"], 32)
                self.assertEqual(frame.path_count, 1)
                self.assertEqual(len(frame.regions), 1)
                self.assertTrue(frame_loop_examples(frame))

            summary = builder.build(
                [sources], dataset, preview, file_limit=4, resolutions=[32],
                preview_files=0, scan_limit=20, seed=7,
                allow_empty_resolutions=False,
            )
            self.assertEqual(summary["files"], 4)
            built = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual({item["split"] for item in built["files"]},
                             {manifest["records"][0]["split"]})


if __name__ == "__main__":
    unittest.main()

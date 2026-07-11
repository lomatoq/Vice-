import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import font_match


ARIAL = Path(r"C:/Windows/Fonts/arial.ttf")
TIMES = Path(r"C:/Windows/Fonts/times.ttf")


def _synthetic_word_mask(
    font: Path, text: str, *, tracking: float = 0.06, ink_height: int = 14
) -> np.ndarray:
    rendered = font_match.render_tracked_text(font, text, tracking)
    width = int(round(rendered.shape[1] * ink_height / rendered.shape[0]))
    resized = cv2.resize(rendered, (width, ink_height), interpolation=cv2.INTER_AREA) >= 96
    canvas = np.zeros((ink_height + 4, width + 8), dtype=bool)
    canvas[2 : 2 + ink_height, 4 : 4 + width] = resized
    return canvas


class FontCatalogTests(unittest.TestCase):
    def test_catalog_streams_small_fields_and_cache_works_without_source(self):
        with tempfile.TemporaryDirectory(dir="tmp") as directory:
            root = Path(directory)
            jsonl = root / "text_shapes.jsonl"
            cache = root / "font_catalog.json"
            rows = [
                {
                    "font": "Arial",
                    "font_file": str(ARIAL),
                    "svg": "<svg>" + "x" * 20_000 + "</svg>",
                },
                {"font": "Arial duplicate", "font_file": str(ARIAL), "svg": "<svg/>"},
                {"font": "Times", "font_file": str(TIMES), "svg": "<svg/>"},
            ]
            jsonl.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
            )
            records, metadata = font_match.load_or_build_catalog(
                jsonl, cache, stop_after_stale=0
            )
            self.assertEqual([record.name for record in records], ["Arial", "Times"])
            self.assertEqual(metadata["unique_fonts"], 2)
            self.assertTrue(cache.is_file())

            jsonl.unlink()
            cached, cached_metadata = font_match.load_or_build_catalog(jsonl, cache)
            self.assertEqual(cached, records)
            self.assertEqual(cached_metadata["source"], "cache")


@unittest.skipUnless(ARIAL.exists() and TIMES.exists(), "Windows Arial and Times are required")
class FontMatchingTests(unittest.TestCase):
    def test_tracking_changes_width_and_topology_preserves_hole(self):
        tight = font_match.render_tracked_text(ARIAL, "AA", -0.08)
        loose = font_match.render_tracked_text(ARIAL, "AA", 0.16)
        self.assertGreater(loose.shape[1], tight.shape[1])
        components, holes = font_match.mask_topology(
            font_match.render_tracked_text(ARIAL, "A", 0.0) >= 96
        )
        self.assertEqual(components, 1)
        self.assertEqual(holes, 1)

    def test_known_font_ranks_first_and_recovers_tracking(self):
        target = _synthetic_word_mask(ARIAL, "IKEA", tracking=0.06)
        results = font_match.match_fonts(
            target,
            "IKEA",
            [
                font_match.FontRecord("Times", str(TIMES)),
                font_match.FontRecord("Arial", str(ARIAL)),
            ],
            refine_rounds=2,
            top_k=2,
        )
        self.assertEqual(results[0][0].font, "Arial")
        self.assertGreater(results[0][0].score, results[1][0].score)
        self.assertAlmostEqual(results[0][0].tracking_em, 0.06, delta=0.03)

    def test_cli_run_writes_json_and_visual_preview(self):
        with tempfile.TemporaryDirectory(dir="tmp") as directory:
            root = Path(directory)
            target = _synthetic_word_mask(ARIAL, "LOGO", tracking=0.0, ink_height=18)
            image_array = np.where(target, 0, 255).astype(np.uint8)
            image = root / "logo.png"
            Image.fromarray(image_array, mode="L").save(image)
            output = root / "result"
            args = font_match.build_parser().parse_args(
                [
                    "--image",
                    str(image),
                    "--text",
                    "LOGO",
                    "--bbox",
                    f"0,0,{target.shape[1]},{target.shape[0]}",
                    "--font",
                    str(ARIAL),
                    "--tracking=-0.06,0,0.06",
                    "--x-scales",
                    "0.95,1,1.05",
                    "--y-scales",
                    "0.95,1,1.05",
                    "--refine-rounds",
                    "1",
                    "--top-k",
                    "1",
                    "--output",
                    str(output),
                ]
            )
            payload = font_match.run(args)
            self.assertTrue(payload["preview_only"])
            self.assertEqual(payload["text"], "LOGO")
            self.assertEqual(len(payload["matches"]), 1)
            self.assertIn("passed", payload["confidence_gate"])
            self.assertTrue((output / "font_match.json").is_file())
            self.assertTrue((output / "font_match_preview.png").is_file())
            with Image.open(output / "font_match_preview.png") as preview:
                self.assertGreater(preview.width, target.shape[1])
                self.assertGreater(preview.height, target.shape[0])


class FontMaskTests(unittest.TestCase):
    def test_bbox_parser_and_auto_dark_text_mask(self):
        image = Image.new("RGB", (30, 20), "white")
        draw = np.asarray(image).copy()
        draw[6:15, 9:20] = (0, 0, 0)
        mask, crop, selected = font_match.extract_target_mask(
            Image.fromarray(draw), "5,3,20,15", polarity="auto"
        )
        self.assertEqual(crop.size, (20, 15))
        self.assertIn(selected, {"dark", "colour"})
        self.assertGreater(float(mask.mean()), 0.05)
        self.assertLess(float(mask.mean()), 0.8)

    def test_bbox_outside_image_is_rejected(self):
        with self.assertRaises(ValueError):
            font_match.extract_target_mask(Image.new("RGB", (10, 10)), "8,8,5,5")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from vice_compiler.evidence_ir import build_reir
from vice_compiler.exact_font_provider import OcrLineHint, ReirExactFontProvider
from vice_compiler.neural_ocr import (
    NeuralOcrLine, _leading_mark_crop, propose_ocr_crops, recognize_local_text,
    resolve_local_trocr_snapshot,
)


class LocalNeuralOcrTests(unittest.TestCase):
    def test_missing_model_is_strictly_local_and_fails_open(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(resolve_local_trocr_snapshot(root))
            result = recognize_local_text(
                Image.new("RGB", (80, 24), "white"), model_root=root,
            )
            self.assertEqual(result, ())

    def test_crop_ensemble_is_deterministic_and_bounded(self) -> None:
        image = Image.new("RGB", (160, 48), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 7, 34, 39), fill="navy")
        draw.text((48, 8), "WORD", fill="black")
        first = propose_ocr_crops(
            image, seed_boxes=((44, 5, 105, 35),), max_crops=5,
        )
        second = propose_ocr_crops(
            image, seed_boxes=((44, 5, 105, 35),), max_crops=5,
        )
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 5)
        self.assertTrue(any(row.provenance == "whole-frame" for row in first))
        self.assertTrue(all(
            0 <= row.bbox_xyxy[0] < row.bbox_xyxy[2] <= image.width
            and 0 <= row.bbox_xyxy[1] < row.bbox_xyxy[3] <= image.height
            for row in first
        ))
        self.assertIsNotNone(_leading_mark_crop(image))

        connected = Image.new("RGB", (160, 48), "white")
        ImageDraw.Draw(connected).rectangle((2, 14, 150, 32), fill="black")
        self.assertIsNone(_leading_mark_crop(connected))

    def test_optional_provider_merges_neural_hypothesis_fail_open(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "word.png"
            Image.new("RGB", (80, 24), "white").save(source)
            reir = build_reir(source)
            neural = NeuralOcrLine(
                "STORMCRAFT", (9, 2, 79, 17), 0.91,
                "trocr-small-printed:unit",
            )
            with patch(
                "vice_compiler.neural_ocr.recognize_local_text",
                return_value=(neural,),
            ):
                provider = ReirExactFontProvider(
                    reir, font_catalog=(), allow_upscale_ocr=True,
                )
                provider.refine_line_hints((SimpleNamespace(
                    id="physical-line", roi_xyxy=(4, 2, 79, 20),
                    score=0.96, glyphs=(1, 2, 3, 4),
                ),))
            self.assertTrue(any(
                row.text == "STORMCRAFT" for row in provider.line_hints()
            ))

    def test_matching_hint_prefers_the_line_transcription(self) -> None:
        provider = object.__new__(ReirExactFontProvider)
        provider._hints = (
            OcrLineHint("garbage", (0, 0, 100, 30), 0.80),
            OcrLineHint("STORMCRAFT", (12, 2, 92, 26), 0.85),
        )
        line = SimpleNamespace(
            roi_xyxy=(0, 0, 100, 30),
            sources=("OCR", "ocr-text:STORMCRAFT"),
        )
        self.assertEqual(provider._matching_hint(line).text, "STORMCRAFT")


if __name__ == "__main__":
    unittest.main()

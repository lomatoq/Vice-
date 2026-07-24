from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from vice_compiler.evidence_ir import build_reir
from vice_compiler.text_macros import (
    _WORDMARK_PRIOR_CHARACTERS, JointLineAppearance, TextLineProposal,
    _late_neural_glyph_refinements, _wordmark_prior_text_contract,
    propose_text_lines,
)
from vice_compiler.wordmark_prior import WORDMARK_CHARACTERS, topology_signature
from vice_compiler.wordmark_runtime import WordmarkPriorProposal


class WordmarkTextLineIntegrationTests(unittest.TestCase):
    def test_whole_line_and_glyph_lanes_choose_independent_source_masks(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "blank.png"
            Image.new("RGB", (120, 40), "white").save(source)
            reir = build_reir(source)
            connected = np.zeros((40, 120), bool)
            connected[12:27, 12:105] = True
            separated = np.zeros_like(connected)
            for x in (15, 48, 81):
                separated[12:27, x:x + 18] = True
            connected.setflags(write=False)
            separated.setflags(write=False)
            appearance = JointLineAppearance(
                foreground_linear_rgba=(0.0, 0.0, 0.0, 1.0),
                background_linear_rgba=(1.0, 1.0, 1.0, 1.0),
                foreground_oklab=(0.0, 0.0, 0.0),
                soft_coverage_mean=1.0, robust_scale=0.0,
                multi_color_groups=(),
            )
            common = {
                "roi_xyxy": (8, 8, 110, 31),
                "polarity": "dark-on-light",
                "sources": (
                    "OCR", "ocr-text:CCC",
                    "persistent-physical-midline-topology",
                ),
                "baseline": 27.0, "x_height": 15.0,
                "cap_height": 15.0, "overshoot": 0.0,
                "slant": 0.0, "tracking": 10.0,
                "stem_classes": (), "glyphs": (),
                "appearance": appearance,
            }
            high_score_joined = TextLineProposal(
                id="joined", support_mask=connected, score=0.95, **common,
            )
            lower_score_cell_exact = TextLineProposal(
                id="separate", support_mask=separated, score=0.55, **common,
            )
            wordmark_sources: list[np.ndarray] = []
            glyph_sources: list[np.ndarray] = []

            def record_wordmark(requests, **_kwargs):
                rows = tuple(requests)
                wordmark_sources.extend(row.certified_support for row in rows)
                return tuple(None for _ in rows)

            def record_glyph(mask, *_args, **_kwargs):
                glyph_sources.append(mask)
                return None

            with (
                patch.dict(os.environ, {
                    "VICE_WORDMARK_PRIOR_CHECKPOINT": "explicit-test-model.pt",
                    "VICE_WORDMARK_PRIOR_EVALUATION": "1",
                }),
                patch(
                    "vice_compiler.wordmark_runtime.propose_wordmark_masks",
                    side_effect=record_wordmark,
                ),
                patch(
                    "vice_compiler.text_macros._ocr_adaptive_glyph_preimage",
                    return_value=None,
                ),
                patch(
                    "vice_compiler.text_macros._ocr_neural_glyph_preimage",
                    side_effect=record_glyph,
                ),
            ):
                _late_neural_glyph_refinements(
                    reir, (lower_score_cell_exact, high_score_joined),
                    np.ones((40, 120, 3), np.float32),
                )
        self.assertEqual(len(wordmark_sources), 1)
        self.assertEqual(len(glyph_sources), 1)
        np.testing.assert_array_equal(wordmark_sources[0], connected)
        np.testing.assert_array_equal(glyph_sources[0], separated)

    def test_whole_line_vocabulary_is_not_restricted_by_glyph_cell_contract(
        self,
    ) -> None:
        self.assertEqual(_WORDMARK_PRIOR_CHARACTERS, frozenset(WORDMARK_CHARACTERS))
        self.assertEqual(
            _wordmark_prior_text_contract("A+B"), ("A", "+", "B"),
        )
        self.assertEqual(
            _wordmark_prior_text_contract("co-op"),
            ("c", "o", "-", "o", "p"),
        )
        self.assertEqual(
            _wordmark_prior_text_contract("ACME\t LAB"),
            tuple("ACME LAB"),
        )
        self.assertEqual(_wordmark_prior_text_contract("Q"), ("Q",))
        self.assertEqual(_wordmark_prior_text_contract("HP"), ("H", "P"))
        self.assertIsNotNone(_wordmark_prior_text_contract("A" * 32))
        self.assertIsNone(_wordmark_prior_text_contract("A" * 33))
        self.assertIsNone(_wordmark_prior_text_contract("тэкст"))

    def test_certified_ocr_lines_enter_one_batched_whole_line_lane(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "wordmark.jpg"
            image = Image.new("RGB", (220, 64), "white")
            font_path = Path(r"C:\Windows\Fonts\arialbd.ttf")
            font = (
                ImageFont.truetype(str(font_path), 32)
                if font_path.is_file() else ImageFont.load_default()
            )
            ImageDraw.Draw(image).text(
                (10, 10), "Mastercard", font=font, fill=(18, 20, 24),
            )
            image.save(source, quality=35)
            reir = build_reir(source)
            batch_sizes: list[int] = []

            def fake_wordmark_batch(requests, **_kwargs):
                rows = tuple(requests)
                batch_sizes.append(len(rows))
                results = []
                for row in rows:
                    support = row.certified_support
                    components, holes = topology_signature(support)
                    results.append(WordmarkPriorProposal(
                        support_mask=support,
                        predicted_topology=(components, holes),
                        topology_confidence=0.99,
                        support_threshold=0.85,
                        repair_confidence_threshold=0.70,
                        source_iou=1.0, source_edit_fraction=0.0,
                        checkpoint_epoch=4,
                    ))
                return tuple(results)

            with (
                patch.dict(os.environ, {
                    "VICE_WORDMARK_PRIOR_CHECKPOINT": "explicit-test-model.pt",
                    "VICE_WORDMARK_PRIOR_EVALUATION": "1",
                }),
                patch(
                    "vice_compiler.wordmark_runtime.propose_wordmark_masks",
                    side_effect=fake_wordmark_batch,
                ),
                patch(
                    "vice_compiler.text_macros._ocr_neural_glyph_preimage",
                    return_value=None,
                ),
            ):
                proposals = propose_text_lines(
                    reir, max_proposals=16,
                    ocr_hints=(("Mastercard", (7, 6, 205, 55), 1.0),),
                )

        self.assertEqual(len(batch_sizes), 1)
        self.assertGreater(batch_sizes[0], 0)
        whole_lines = [
            proposal for proposal in proposals
            if "font-free-whole-line-wordmark-prior" in proposal.sources
        ]
        self.assertEqual(len(whole_lines), 1)
        self.assertIn("no-character-cell-seams", whole_lines[0].sources)
        self.assertIn("batched-whole-line-inference", whole_lines[0].sources)
        self.assertIn(
            "native-resolution-topology-recertified", whole_lines[0].sources,
        )

    def test_punctuation_wordmark_reaches_runtime_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "punctuation.png"
            image = Image.new("RGB", (150, 64), "white")
            font_path = Path(r"C:\Windows\Fonts\arialbd.ttf")
            font = (
                ImageFont.truetype(str(font_path), 38)
                if font_path.is_file() else ImageFont.load_default()
            )
            ImageDraw.Draw(image).text(
                (12, 8), "A+B", font=font, fill=(10, 10, 10),
            )
            image.save(source)
            reir = build_reir(source)
            recognized_rows: list[tuple[str, ...]] = []

            def reject_after_recording(requests, **_kwargs):
                rows = tuple(requests)
                recognized_rows.append(tuple(
                    row.recognized_text for row in rows
                ))
                return tuple(None for _ in rows)

            with (
                patch.dict(os.environ, {
                    "VICE_WORDMARK_PRIOR_CHECKPOINT": "explicit-test-model.pt",
                    "VICE_WORDMARK_PRIOR_EVALUATION": "1",
                }),
                patch(
                    "vice_compiler.wordmark_runtime.propose_wordmark_masks",
                    side_effect=reject_after_recording,
                ),
                patch(
                    "vice_compiler.text_macros._ocr_neural_glyph_preimage",
                    return_value=None,
                ),
            ):
                propose_text_lines(
                    reir, max_proposals=16,
                    ocr_hints=(("A+B", (8, 5, 142, 58), 1.0),),
                )
        self.assertEqual(len(recognized_rows), 1)
        self.assertIn("A+B", recognized_rows[0])

    def test_single_and_two_glyph_logos_reach_runtime_batch(self) -> None:
        font_path = Path(r"C:\Windows\Fonts\arialbd.ttf")
        font = (
            ImageFont.truetype(str(font_path), 42)
            if font_path.is_file() else ImageFont.load_default()
        )
        for recognized in ("Q", "HP"):
            with self.subTest(recognized=recognized), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / f"{recognized}.png"
                image = Image.new("RGB", (96, 64), "white")
                ImageDraw.Draw(image).text(
                    (12, 5), recognized, font=font, fill=(10, 10, 10),
                )
                image.save(source)
                reir = build_reir(source)
                recognized_rows: list[tuple[str, ...]] = []

                def reject_after_recording(requests, **_kwargs):
                    rows = tuple(requests)
                    recognized_rows.append(tuple(
                        row.recognized_text for row in rows
                    ))
                    return tuple(None for _ in rows)

                with (
                    patch.dict(os.environ, {
                        "VICE_WORDMARK_PRIOR_CHECKPOINT": "explicit-test-model.pt",
                        "VICE_WORDMARK_PRIOR_EVALUATION": "1",
                    }),
                    patch(
                        "vice_compiler.wordmark_runtime.propose_wordmark_masks",
                        side_effect=reject_after_recording,
                    ),
                    patch(
                        "vice_compiler.text_macros._ocr_neural_glyph_preimage",
                        return_value=None,
                    ),
                ):
                    propose_text_lines(
                        reir, max_proposals=16,
                        ocr_hints=((recognized, (8, 3, 88, 60), 1.0),),
                    )
                self.assertEqual(len(recognized_rows), 1)
                self.assertIn(recognized, recognized_rows[0])


if __name__ == "__main__":
    unittest.main()

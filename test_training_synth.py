import random
import unittest
from pathlib import Path

import numpy as np

import corner_classifier as cc
import corner_cnn


class FocusedTrainingSynthesisTests(unittest.TestCase):
    def test_variable_length_batch_matches_individual_circular_forward(self):
        import torch
        torch.manual_seed(4)
        model = corner_cnn._make_model().eval()
        lengths = torch.tensor([73, 109], dtype=torch.long)
        padded = torch.zeros(2, len(corner_cnn.TURN_WINDOWS), 109)
        padded[0, :, :73] = torch.randn(len(corner_cnn.TURN_WINDOWS), 73)
        padded[1] = torch.randn(len(corner_cnn.TURN_WINDOWS), 109)
        with torch.no_grad():
            batched = model(padded, lengths=lengths)
            first = model(padded[0:1, :, :73])
            second = model(padded[1:2])
        self.assertTrue(torch.allclose(batched[0, :73], first[0], atol=2e-6, rtol=2e-5))
        self.assertTrue(torch.allclose(batched[1, :109], second[0], atol=2e-6, rtol=2e-5))

    def test_balanced_epoch_source_policy(self):
        tags = ["svg-gt:primitive_corner_v1:a_smooth_ring",
                "svg-gt:primitive_corner_v1:b_zigzag",
                "svg-gt:corner_gt_v4:x", "text-corpus", "neg", "synth", "paper:x"]
        data = []
        for index in range(600):
            tag = tags[index % len(tags)]
            data.append((np.zeros((len(corner_cnn.TURN_WINDOWS), 72), np.float32),
                         np.zeros(72, np.float32), tag))
        order = corner_cnn._epoch_order(data, random.Random(9), balanced=True)
        from collections import Counter
        mix = Counter(corner_cnn._training_source(data[index][2]) for index in order)
        self.assertEqual(len(order), len(data))
        self.assertEqual(mix, {"primitive": 180, "reviewed": 180, "text": 90,
                               "smooth-neg": 90, "synth": 30, "aux": 30})

    def test_new_primitive_families_have_exact_corners(self):
        kinds = ("thin_rect", "diamond", "trapezoid", "chevron", "notch", "zigzag")
        for index, kind in enumerate(kinds):
            with self.subTest(kind=kind):
                mask, corners = cc._synth_shape(random.Random(index), 64, forced_kind=kind)
                self.assertGreater(int(mask.sum()), 4)
                self.assertGreaterEqual(len(corners), 4)
                points = np.asarray(corners, float)
                self.assertTrue(np.isfinite(points).all())
                self.assertTrue((points >= -1).all())
                self.assertTrue((points <= 65).all())

    def test_curved_stroke_negatives_are_nonempty_at_tiny_sizes(self):
        for kind in ("linebar", "curvebar", "sbar"):
            for resolution in (12, 16, 24, 48):
                with self.subTest(kind=kind, resolution=resolution):
                    mask = cc._synth_smooth_mask(random.Random(resolution), resolution,
                                                 forced_kind=kind)
                    self.assertGreater(int(mask.sum()), 2)
                    self.assertTrue(cc.mask_loops(mask))

    def test_explicit_single_letters_render_with_structural_labels(self):
        font = Path(r"C:/Windows/Fonts/arial.ttf")
        if not font.exists():
            self.skipTest("Arial is unavailable")
        for char in ("A", "K", "S", "a", "e"):
            with self.subTest(char=char):
                out = cc._synth_text(random.Random(0), 24, text=char,
                                     font_path=str(font))
                self.assertIsNotNone(out)
                mask, corners = out
                self.assertGreater(int(mask.sum()), 3)
                self.assertEqual(np.asarray(corners).ndim, 2)


if __name__ == "__main__":
    unittest.main()

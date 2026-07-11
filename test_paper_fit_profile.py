import unittest
from unittest import mock

import numpy as np

import geometry_vectorizer as gv
from vectorize_papers import Curve


class PaperFitProfileTests(unittest.TestCase):
    def setUp(self):
        self.loop = np.asarray([[0, 0], [20, 0], [20, 20], [0, 20]], dtype=float)
        self.curves = [Curve(1, np.asarray([[0, 0], [20, 0]], dtype=float))]
        self.fallback = [Curve(1, np.asarray([[1, 1], [2, 2]], dtype=float))]

    def test_production_preserves_fixed_iou_fallback(self):
        with mock.patch.object(gv, "_loop_fit_deviation", return_value=0.8), \
                mock.patch.object(gv, "_loop_fill_iou", return_value=0.82), \
                mock.patch.object(gv, "_chain_self_intersects", return_value=False), \
                mock.patch.object(gv, "_pixel_faithful_curves", return_value=self.fallback):
            result = gv._finish_loop(
                self.loop, self.curves, 1.0, "paper", fit_profile="production"
            )
        self.assertEqual(result.template, "paper-fallback")
        self.assertIs(result.curves, self.fallback)

    def test_text_safe_keeps_low_deviation_fit_despite_low_iou(self):
        with mock.patch.object(gv, "_loop_fit_deviation", return_value=0.8), \
                mock.patch.object(gv, "_loop_fill_iou", return_value=0.82), \
                mock.patch.object(gv, "_chain_self_intersects", return_value=False):
            result = gv._finish_loop(
                self.loop, self.curves, 1.0, "paper", fit_profile="text-safe"
            )
        self.assertEqual(result.template, "paper")
        self.assertIs(result.curves, self.curves)

    def test_text_safe_still_falls_back_when_iou_and_deviation_are_bad(self):
        with mock.patch.object(gv, "_loop_fit_deviation", return_value=1.5), \
                mock.patch.object(gv, "_loop_fill_iou", return_value=0.82), \
                mock.patch.object(gv, "_chain_self_intersects", return_value=False), \
                mock.patch.object(gv, "_pixel_faithful_curves", return_value=self.fallback):
            result = gv._finish_loop(
                self.loop, self.curves, 1.0, "paper", fit_profile="text-safe"
            )
        self.assertEqual(result.template, "paper-fallback")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown paper fit profile"):
            gv._finish_loop(self.loop, self.curves, 1.0, "paper", fit_profile="mystery")


if __name__ == "__main__":
    unittest.main()

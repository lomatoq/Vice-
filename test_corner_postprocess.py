import unittest
from unittest import mock

import numpy as np

import geometry_vectorizer as gv


def _loop(size: int = 40) -> np.ndarray:
    # A deterministic native-density ring; the helper tests routing, while the
    # dataset evaluator measures geometric quality.
    x = np.arange(size, dtype=float)
    return np.column_stack((x, np.sin(x / 4.0)))


class CornerPostprocessPolicyTests(unittest.TestCase):
    def test_production_keeps_original_stage_order_and_parameters(self):
        loop = _loop()
        with mock.patch.object(gv, "_recenter_corners", return_value=[2, 9]) as recenter, \
                mock.patch.object(gv, "_collapse_short_corners", return_value=[2]) as collapse, \
                mock.patch.object(gv, "_iterated_removal", return_value=[2]) as removal:
            got = gv._postprocess_corner_candidates(
                loop, [9, 2, 2], work_res=25.0, spacing=1.25,
                policy="production", use_cnn=True,
            )
        self.assertEqual(got, [2])
        recenter.assert_called_once_with(loop, [2, 9])
        collapse.assert_called_once_with(loop, [2, 9], 20.0)
        removal.assert_called_once_with(loop, [2], 32.0 / 25.0, 2.0, close_px=2.5)

    def test_tiny_safe_uses_raw_candidates_without_recenter_or_collapse(self):
        loop = _loop()
        with mock.patch.object(gv, "_recenter_corners") as recenter, \
                mock.patch.object(gv, "_collapse_short_corners") as collapse, \
                mock.patch.object(gv, "_iterated_removal", return_value=[2, 9]) as removal:
            small = gv._postprocess_corner_candidates(
                loop, [9, 2], work_res=18.0, spacing=1.0,
                policy="tiny-safe", use_cnn=True,
            )
            medium = gv._postprocess_corner_candidates(
                loop, [9, 2], work_res=25.0, spacing=1.0,
                policy="tiny-safe", use_cnn=True,
            )
        self.assertEqual(small, [2, 9])
        self.assertEqual(medium, [2, 9])
        recenter.assert_not_called()
        collapse.assert_not_called()
        removal.assert_called_once_with(loop, [2, 9], 32.0 / 18.0, acc=0.55, close_px=1.8)

    def test_conservative_has_one_vertex_snap_no_collapse_and_paper_accuracy(self):
        loop = _loop()
        with mock.patch.object(gv, "_recenter_corners", return_value=[3, 9]) as recenter, \
                mock.patch.object(gv, "_collapse_short_corners") as collapse, \
                mock.patch.object(gv, "_iterated_removal", return_value=[3, 9]) as removal:
            got = gv._postprocess_corner_candidates(
                loop, [2, 9], work_res=30.0, spacing=1.0,
                policy="cnn-conservative", use_cnn=True,
            )
        self.assertEqual(got, [3, 9])
        recenter.assert_called_once_with(loop, [2, 9], radius=1, w=2)
        collapse.assert_not_called()
        removal.assert_called_once_with(
            loop, [3, 9], 32.0 / 30.0, acc=gv._PAPER_ACC, close_px=3.0,
        )

    def test_non_cnn_route_keeps_production_policy(self):
        loop = _loop()
        with mock.patch.object(gv, "_recenter_corners", return_value=[2]) as recenter, \
                mock.patch.object(gv, "_collapse_short_corners", return_value=[2]) as collapse:
            with mock.patch.object(gv, "_iterated_removal", return_value=[2]):
                gv._postprocess_corner_candidates(
                    loop, [2], work_res=18.0, spacing=1.0,
                    policy="tiny-safe", use_cnn=False,
                )
        recenter.assert_called_once()
        collapse.assert_called_once()

    def test_unknown_policy_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown corner postprocess policy"):
            gv._postprocess_corner_candidates(
                _loop(), [2], work_res=20.0, spacing=1.0,
                policy="mystery", use_cnn=True,
            )


if __name__ == "__main__":
    unittest.main()

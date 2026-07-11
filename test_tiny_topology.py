import unittest

import numpy as np

import geometry_vectorizer as gv
from region_graph import vectorize_region_graph


class TinyTopologyTests(unittest.TestCase):
    def test_overlapping_circle_graph_reuses_circular_supports(self):
        yy, xx = np.mgrid[0:180, 0:280]
        left = (xx - 105) ** 2 + (yy - 85) ** 2 <= 70 ** 2
        right = (xx - 175) ** 2 + (yy - 85) ** 2 <= 70 ** 2
        labels = np.full((180, 280), -1, np.int32)
        labels[left] = 0
        labels[right] = 1
        labels[left & right] = 2
        regions, _ = vectorize_region_graph(labels, analysis_scale=1.0)
        curves = [curve for loops in regions.values() for loop in loops for curve in loop.curves]
        chords = [float(np.linalg.norm(curve.control[-1] - curve.control[0])) for curve in curves]
        self.assertEqual(len(regions), 3)
        self.assertLessEqual(len(curves), 20)
        self.assertLessEqual(sum(curve.degree == 1 for curve in curves), 2)
        self.assertLessEqual(sum(length < 0.75 for length in chords), 2)

    def test_region_graph_is_reserved_for_material_shared_interfaces(self):
        left = np.zeros((80, 120), bool)
        right = np.zeros_like(left)
        left[15:65, 10:60] = True
        right[15:65, 60:110] = True
        self.assertTrue(gv._needs_shared_region_graph([left, right], 1))
        right[:, :] = False
        right[15:65, 70:110] = True
        self.assertFalse(gv._needs_shared_region_graph([left, right], 1))

    def test_three_pixel_counter_stays_pixel_faithful(self):
        mask = np.zeros((8, 8), np.uint8)
        mask[3, 4] = 1
        mask[4, 3:5] = 1
        raw = gv.mask_loops(mask)[0]
        loop = raw[:-1] if np.allclose(raw[0], raw[-1]) else raw
        fitted = gv.fit_loop_paper(loop.astype(float), px=1.0)
        self.assertEqual(fitted.template, "paper-tiny")
        self.assertGreaterEqual(gv._loop_fill_iou(loop, fitted.curves), 0.95)
        self.assertLessEqual(len(fitted.curves), 10)

    def test_dense_subpixel_tiny_loop_is_compacted(self):
        # 4x crack chain around a 4x4 native-pixel square: source evidence is
        # one native pixel, not every quarter-pixel sample.
        side = []
        for x in np.arange(0, 4, 0.25): side.append((x, 0))
        for y in np.arange(0, 4, 0.25): side.append((4, y))
        for x in np.arange(4, 0, -0.25): side.append((x, 4))
        for y in np.arange(4, 0, -0.25): side.append((0, y))
        curves = gv._tiny_pixel_curves(np.asarray(side, float))
        self.assertLessEqual(len(curves), 22)


if __name__ == "__main__":
    unittest.main()

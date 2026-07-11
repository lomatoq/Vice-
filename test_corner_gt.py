from pathlib import Path
import unittest

import numpy as np

from svg_corner_gt import EVENT_SHORT_SPAN, frame_loop_examples, visible_svg_regions


FIXTURES = Path(__file__).resolve().parent / "test_runs" / "corner_gt_fixtures"


def counts(name: str, resolution: int) -> tuple[int, int]:
    frame = visible_svg_regions(FIXTURES / name, resolution)
    examples = frame_loop_examples(frame)
    structural = sum(int(np.count_nonzero(example.labels == 1)) for example in examples)
    occlusion = sum(int(np.count_nonzero(example.labels == 2)) for example in examples)
    return structural, occlusion


def event_counts(name: str, resolution: int) -> tuple[int, int]:
    examples = frame_loop_examples(visible_svg_regions(FIXTURES / name, resolution))
    total = sum(len(set(example.event_ids[example.event_ids >= 0].tolist())) for example in examples)
    spans = sum(len(set(example.event_ids[example.event_kinds == EVENT_SHORT_SPAN].tolist()))
                for example in examples)
    return total, spans


class CornerGroundTruthTests(unittest.TestCase):
    def test_smooth_shapes_have_no_corners_at_any_scale(self):
        for resolution in (16, 24, 32, 64, 128, 256):
            self.assertEqual(counts("smooth.svg", resolution), (0, 0))

    def test_polygon_has_exact_structural_vertices(self):
        # triangle (3) + star (10)
        for resolution in (32, 64, 128, 256):
            self.assertEqual(event_counts("polygon.svg", resolution)[0], 13)
            self.assertEqual(counts("polygon.svg", resolution)[1], 0)

    def test_rotated_square_uses_two_endpoints_for_each_latent_corner(self):
        for resolution in (32, 64, 128, 256):
            self.assertEqual(counts("diamond.svg", resolution), (8, 0))
            self.assertEqual(event_counts("diamond.svg", resolution), (4, 4))

    def test_rounded_joins_are_not_corners(self):
        # Rounded rectangle contributes zero. The second deliberately C0
        # cubic outline contributes three perceptual joins.  A join landing on
        # a short raster plateau may use two endpoint vertex labels.
        for resolution in (32, 64, 128, 256):
            self.assertEqual(event_counts("rounded.svg", resolution)[0], 3)
            self.assertEqual(counts("rounded.svg", resolution)[1], 0)

    def test_occlusion_has_separate_label_type(self):
        for resolution in (32, 64, 128, 256):
            structural, occlusion = counts("occlusion.svg", resolution)
            self.assertGreaterEqual(structural, 3)
            self.assertGreaterEqual(occlusion, 2)


if __name__ == "__main__":
    unittest.main()

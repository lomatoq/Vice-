"""Focused guards for evidence-gated perceptual repair routes."""

from pathlib import Path
import re
import unittest

import cv2
import numpy as np
from PIL import Image, ImageDraw

import geometry_vectorizer as gv


ROOT = Path(__file__).parent
MASTERCARD = ROOT / "web_preview" / "uploads" / "52_icon_group_4_24_src.png"


class KnownTemplateRouterTests(unittest.TestCase):
    def test_topology_reconciliation_stops_on_first_exact_pixel(self) -> None:
        source = np.zeros((10, 10), bool)
        source[2:6, 1:4] = True
        source[2:6, 5:8] = True
        source[3, 4] = True
        candidate = source.copy()
        candidate[2, 2] = False  # harmless coverage mismatch, row-major first
        candidate[3, 4] = False  # the topology-changing bridge
        operations, exact = gv._known_template_topology_ops(
            candidate, source, limit=4)
        self.assertTrue(exact)
        self.assertEqual(operations, [(4, 3, True)])

    def test_visual_match_is_source_only(self) -> None:
        image = Image.open(MASTERCARD).convert("RGB")
        match = gv._known_template_quick_match(gv._KNOWN_TEMPLATE_CATALOG[0], image)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(match["ssim"], 0.93)
        self.assertGreaterEqual(match["ink_iou"], 0.94)
        self.assertEqual((match["x"], match["y"]), (5, 6))

    def test_two_disc_impostor_abstains(self) -> None:
        image = Image.new("RGB", (98, 65), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((6, 7, 58, 59), fill=(213, 54, 44))
        draw.ellipse((40, 7, 92, 59), fill=(225, 126, 47))
        match = gv._known_template_quick_match(gv._KNOWN_TEMPLATE_CATALOG[0], image)
        self.assertIsNone(match)

    def test_exact_topology_recovery_has_a_bounded_perceptual_budget(self) -> None:
        incumbent = {"topology": (4, 4), "ssim": 0.94301, "mae": 4.697,
                     "ink_iou": 0.95340, "boundary_f": 0.99119}
        candidate = {"topology": (5, 7), "ssim": 0.92590, "mae": 5.785,
                     "ink_iou": 0.94238, "boundary_f": 0.99184,
                     "primitives": 436, "micro_segments": 52}
        reasons, recovery = gv._known_template_court_reasons(
            candidate, incumbent, (5, 7), 905)
        self.assertTrue(recovery)
        self.assertEqual(reasons, [])

    def test_topology_recovery_budget_rejects_large_visual_loss(self) -> None:
        incumbent = {"topology": (4, 4), "ssim": 0.95, "mae": 4.0,
                     "ink_iou": 0.96, "boundary_f": 0.99}
        candidate = {"topology": (5, 7), "ssim": 0.80, "mae": 8.0,
                     "ink_iou": 0.80, "boundary_f": 0.90,
                     "primitives": 100, "micro_segments": 0}
        reasons, recovery = gv._known_template_court_reasons(
            candidate, incumbent, (5, 7), 900)
        self.assertTrue(recovery)
        self.assertTrue({"ssim", "mae", "ink-iou", "boundary"} <= set(reasons))


class CoverageCalibrationTests(unittest.TestCase):
    def test_compound_ring_contours_get_independent_ellipse_courts(self) -> None:
        mask = np.zeros((256, 256), np.uint8)
        cv2.circle(mask, (128, 128), 92, 1, thickness=-1,
                   lineType=cv2.LINE_8)
        cv2.circle(mask, (128, 128), 70, 0, thickness=-1,
                   lineType=cv2.LINE_8)
        raw_loops = gv.mask_loops(mask > 0)
        self.assertEqual(len(raw_loops), 2)
        fitted = gv._try_clean_compound_circle_loops(mask > 0, raw_loops, 4)
        self.assertIsNotNone(fitted)
        self.assertEqual([len(loop.curves) for loop in fitted], [4, 4])
        self.assertEqual(
            [loop.template for loop in fitted],
            ["paper-clean-compound-circle", "paper-clean-compound-circle"])

    def test_non_circular_compound_does_not_enter_circle_court(self) -> None:
        mask = np.zeros((256, 256), np.uint8)
        cv2.rectangle(mask, (24, 40), (230, 212), 1, thickness=-1)
        cv2.rectangle(mask, (64, 76), (188, 174), 0, thickness=-1)
        raw_loops = gv.mask_loops(mask > 0)
        self.assertEqual(len(raw_loops), 2)
        self.assertIsNone(
            gv._try_clean_compound_circle_loops(mask > 0, raw_loops, 4))

    def test_source_retrace_skips_after_exact_topology_repair(self) -> None:
        saved = list(gv._TOPOLOGY_REPAIR_AUDIT)
        regions = [object()]
        try:
            gv._TOPOLOGY_REPAIR_AUDIT[:] = [{
                "accepted": True,
                "source_topology": [7, 1],
                "candidate_topology": [7, 1],
            }]
            result = gv._repair_perceptual_trace(
                regions, Image.new("RGB", (80, 80), "white"))
            self.assertIs(result, regions)
            self.assertEqual(
                gv._PERCEPTUAL_TRACE_AUDIT[-1]["reason"],
                "skipped-after-exact-topology-repair")
            self.assertEqual(gv._PERCEPTUAL_TRACE_AUDIT[-1]["trials"], [])
        finally:
            gv._TOPOLOGY_REPAIR_AUDIT[:] = saved

    def test_calibration_replaces_existing_apron_without_duplicates(self) -> None:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg">'
               '<path data-region="0" d="M0 0L2 0L2 2Z" fill="#123456" '
               'stroke="#123456" stroke-width="0.60" stroke-linejoin="round"/>'
               '</svg>')
        calibrated = gv._coverage_calibrated_svg(svg, 0.30, 0.0, 0.10)
        self.assertEqual(calibrated.count(' stroke="#123456"'), 1)
        self.assertEqual(calibrated.count(' stroke-width="0.30"'), 1)
        self.assertIn('transform="translate(0.00 0.10)"', calibrated)

    def test_clustered_coverage_is_deterministic_and_preserves_paths(self) -> None:
        colors = [f"#{index:02x}{(index * 7) % 256:02x}{255 - index:02x}"
                  for index in range(24)]
        forward = gv._cluster_fill_colors(colors, maximum=8)
        reverse = gv._cluster_fill_colors(list(reversed(colors)), maximum=8)
        self.assertEqual(forward, reverse)
        self.assertLessEqual(len(set(forward.values())), 8)
        svg = ('<svg xmlns="http://www.w3.org/2000/svg">'
               '<path d="M0 0L4 0L4 4Z" fill="%s"/>'
               '<path d="M8 0L12 0L12 4Z" fill="%s"/>'
               '</svg>') % (colors[0], colors[-1])
        before = re.findall(r'\sd="([^"]+)"', svg)
        tuned = gv._clustered_coverage_svg(
            svg, forward,
            {forward[colors[0]]: (0.16, 0.12, -0.12)})
        self.assertEqual(re.findall(r'\sd="([^"]+)"', tuned), before)
        self.assertNotIn('<image', tuned)

    def test_path_affine_preserves_every_d_command(self) -> None:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg">'
               '<path d="M0 0L4 0L4 4Z" fill="#123456"/>'
               '<path d="M8 0L12 0L12 4Z" fill="#abcdef"/>'
               '</svg>')
        before = re.findall(r'\sd="([^"]+)"', svg)
        centers = gv._path_affine_centers(svg)
        tuned = gv._path_affine_svg(
            svg,
            [(0.12, 0.10, -0.10, 1.01, 0.99),
             (-0.05, 0.0, 0.0, 1.0, 1.0)],
            centers)
        self.assertEqual(re.findall(r'\sd="([^"]+)"', tuned), before)
        self.assertNotIn('<image', tuned)

    def test_residual_seam_meter_detects_enclosed_crack(self) -> None:
        source = Image.new("RGB", (64, 64), "white")
        ImageDraw.Draw(source).rectangle((8, 8, 55, 55), fill="black")
        good = ('<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 64 64">'
                '<path d="M8 8H56V56H8Z" fill="#000000"/>'
                '</svg>')
        cracked = good.replace(
            '</svg>',
            '<path d="M31.6 12H32.4V52H31.6Z" fill="#ffffff"/>'
            '</svg>')
        self.assertEqual(gv._residual_seam_meter(good, source), 0.0)
        self.assertGreater(gv._residual_seam_meter(cracked, source), 0.0)

    def test_compact_color_court_detects_lost_material(self) -> None:
        rgb = np.full((24, 24, 3), 255, np.uint8)
        mask = np.zeros((24, 24), bool)
        mask[10:13, 10:13] = True
        target = np.asarray((240.0, 190.0, 0.0))
        context = (rgb, [(mask, target)])
        preserved = Image.new("RGB", (24, 24), "white")
        ImageDraw.Draw(preserved).rectangle(
            (10, 10, 12, 12), fill=tuple(target.astype(int)))
        lost = Image.new("RGB", (24, 24), "white")
        good = gv._compact_color_detail_score(preserved, context)
        bad = gv._compact_color_detail_score(lost, context)
        self.assertIsNotNone(good)
        self.assertIsNotNone(bad)
        self.assertGreater(good, bad + 0.5)


if __name__ == "__main__":
    unittest.main()

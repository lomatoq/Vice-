"""Materialization v2 — commit M2-07 gate: appearance completeness.

Plan S8 "Appearance" list: three stripes survive, a small red cross is
salient, a red eye detail survives, a linear gradient's direction is
preserved, an antialiasing ribbon is not promoted to a colour layer, a
monochrome wordmark gains no false colours.
"""

from __future__ import annotations

import unittest

import numpy as np

from vice_compiler.appearance_transport import (
    appearance_completeness,
    boundary_normal_transport,
    extract_salient_clusters,
    linear_gradient_evidence,
    linear_srgb_to_oklab,
)

CANVAS = 64


def _stripes() -> tuple[np.ndarray, np.ndarray]:
    rgb = np.zeros((CANVAS, CANVAS, 3), np.float64)
    support = np.zeros((CANVAS, CANVAS), bool)
    support[16:48, 8:56] = True
    rgb[16:27, 8:56] = (0.75, 0.05, 0.05)
    rgb[27:38, 8:56] = (0.05, 0.55, 0.10)
    rgb[38:48, 8:56] = (0.05, 0.10, 0.70)
    return rgb, support


def _red_cross_on_white_mark() -> tuple[np.ndarray, np.ndarray]:
    rgb = np.zeros((CANVAS, CANVAS, 3), np.float64)
    support = np.zeros((CANVAS, CANVAS), bool)
    support[10:54, 10:54] = True
    rgb[10:54, 10:54] = (0.02, 0.02, 0.02)
    rgb[28:36, 20:44] = (0.70, 0.03, 0.03)
    rgb[20:44, 28:36] = (0.70, 0.03, 0.03)
    return rgb, support


def _monochrome() -> tuple[np.ndarray, np.ndarray]:
    rgb = np.zeros((CANVAS, CANVAS, 3), np.float64)
    support = np.zeros((CANVAS, CANVAS), bool)
    support[12:52, 12:52] = True
    rgb[12:52, 12:52] = (0.03, 0.03, 0.03)
    return rgb, support


def _gradient() -> tuple[np.ndarray, np.ndarray]:
    rgb = np.zeros((CANVAS, CANVAS, 3), np.float64)
    support = np.zeros((CANVAS, CANVAS), bool)
    support[16:48, 8:56] = True
    ramp = np.linspace(0.05, 0.95, 48)
    for index, x in enumerate(range(8, 56)):
        rgb[16:48, x] = (ramp[index], ramp[index] * 0.4, 0.08)
    return rgb, support


class SalientClusterTests(unittest.TestCase):
    def test_three_stripes_are_found(self) -> None:
        rgb, support = _stripes()
        clusters = extract_salient_clusters(rgb, support)
        self.assertGreaterEqual(len(clusters), 3)

    def test_small_red_cross_is_salient(self) -> None:
        rgb, support = _red_cross_on_white_mark()
        clusters = extract_salient_clusters(rgb, support)
        self.assertGreaterEqual(len(clusters), 2)
        chromas = sorted(cluster.chroma for cluster in clusters)
        self.assertGreater(
            chromas[-1], 0.05, "the chromatic detail was dropped",
        )
        areas = [cluster.area_px for cluster in clusters]
        self.assertLess(
            min(areas) / max(areas), 0.5,
            "the small detail should stay a separate small cluster",
        )

    def test_monochrome_gains_no_false_colours(self) -> None:
        rgb, support = _monochrome()
        clusters = extract_salient_clusters(rgb, support)
        self.assertLessEqual(len(clusters), 1)

    def test_antialiasing_ribbon_is_not_a_layer(self) -> None:
        rgb, support = _monochrome()
        # Paint a one-pixel transition ring - the classic AA ribbon.
        rgb[11, 12:52] = (0.5, 0.5, 0.5)
        rgb[52, 12:52] = (0.5, 0.5, 0.5)
        support[11, 12:52] = True
        support[52, 12:52] = True
        clusters = extract_salient_clusters(rgb, support)
        self.assertLessEqual(len(clusters), 1)


class GradientTests(unittest.TestCase):
    def test_linear_gradient_direction_is_recovered(self) -> None:
        rgb, support = _gradient()
        ok, p0, p1, ramp = linear_gradient_evidence(rgb, support)
        self.assertTrue(ok)
        self.assertGreater(ramp, 0.08)
        direction = np.array(p1) - np.array(p0)
        self.assertGreater(abs(direction[0]), 4.0 * abs(direction[1]) + 1.0)

    def test_flat_colour_has_no_gradient_evidence(self) -> None:
        rgb, support = _monochrome()
        ok, _p0, _p1, _ramp = linear_gradient_evidence(rgb, support)
        self.assertFalse(ok)


class TransportTests(unittest.TestCase):
    def test_transport_covers_the_target_without_overlap(self) -> None:
        _rgb, support = _stripes()
        layers = [
            np.zeros((CANVAS, CANVAS), bool) for _ in range(3)
        ]
        layers[0][16:27, 8:56] = True
        layers[1][27:38, 8:56] = True
        layers[2][38:48, 8:56] = True
        target = np.zeros((CANVAS, CANVAS), bool)
        target[15:49, 7:57] = True          # slightly idealized geometry
        transported = boundary_normal_transport(layers, target)
        union = np.zeros_like(target)
        for mask in transported:
            self.assertFalse(np.any(mask & ~target))
            self.assertFalse(np.any(mask & union), "layers overlap")
            union |= mask
        self.assertTrue(np.array_equal(union, target))


class CompletenessTests(unittest.TestCase):
    def _delivered(self, clusters, drop: int | None = None):
        rows = []
        for index, cluster in enumerate(clusters):
            if drop is not None and index == drop:
                continue
            rows.append((f"layer-{index}", cluster.linear_rgba, cluster.mask))
        return rows

    def test_complete_delivery_passes(self) -> None:
        rgb, support = _stripes()
        clusters = extract_salient_clusters(rgb, support)
        certificate = appearance_completeness(
            clusters, self._delivered(clusters),
        )
        self.assertTrue(certificate.valid, certificate.violations)
        self.assertEqual(certificate.missing_salient_clusters, ())
        self.assertAlmostEqual(certificate.salient_recall, 1.0)

    def test_dropped_stripe_is_a_violation(self) -> None:
        rgb, support = _stripes()
        clusters = extract_salient_clusters(rgb, support)
        certificate = appearance_completeness(
            clusters, self._delivered(clusters, drop=1),
        )
        self.assertFalse(certificate.valid)
        self.assertTrue(certificate.missing_salient_clusters)
        self.assertLess(certificate.salient_recall, 0.95)

    def test_dropped_small_detail_is_a_violation(self) -> None:
        rgb, support = _red_cross_on_white_mark()
        clusters = extract_salient_clusters(rgb, support)
        smallest = min(
            range(len(clusters)), key=lambda i: clusters[i].area_px,
        )
        certificate = appearance_completeness(
            clusters, self._delivered(clusters, drop=smallest),
        )
        self.assertFalse(certificate.valid)
        self.assertIn(
            clusters[smallest].id, certificate.missing_salient_clusters,
        )

    def test_colour_completeness_cannot_be_bought_by_mean_iou(self) -> None:
        # A delivery that paints everything with the dominant colour has a
        # perfect support IoU and still fails appearance completeness.
        rgb, support = _stripes()
        clusters = extract_salient_clusters(rgb, support)
        dominant = max(clusters, key=lambda cluster: cluster.area_px)
        certificate = appearance_completeness(
            clusters, [("layer-flat", dominant.linear_rgba, support)],
        )
        self.assertFalse(certificate.valid)
        self.assertGreaterEqual(len(certificate.missing_salient_clusters), 1)


class OklabTests(unittest.TestCase):
    def test_oklab_is_monotone_in_lightness(self) -> None:
        dark = linear_srgb_to_oklab(np.array([0.02, 0.02, 0.02]))
        light = linear_srgb_to_oklab(np.array([0.85, 0.85, 0.85]))
        self.assertLess(dark[0], light[0])

    def test_saturated_colour_has_chroma(self) -> None:
        red = linear_srgb_to_oklab(np.array([0.7, 0.02, 0.02]))
        grey = linear_srgb_to_oklab(np.array([0.3, 0.3, 0.3]))
        self.assertGreater(abs(red[1]) + abs(red[2]), 0.10)
        self.assertLess(abs(grey[1]) + abs(grey[2]), 0.01)


if __name__ == "__main__":
    unittest.main()

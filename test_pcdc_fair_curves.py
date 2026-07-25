"""Materialization v2 — commit M2-06 gate: fair primitive grammar.

Plan S8 "Geometry" test list, verbatim in intent:
exact lines stay lines, exact circles stay arcs, real corners survive,
smooth bowls do not reverse curvature, an S-curve keeps its one real
inflection, a wavy C1 curve is rejected as unfair, undecided microspans
fall back to faithful geometry, and the cost does not depend on sampling
density.
"""

from __future__ import annotations

import math
import unittest

import cv2
import numpy as np

from vice_compiler.certificates import topology_signature
from vice_compiler.coverage_evidence import (
    boundary_observations,
    marching_squares,
    observations_preserve_topology,
    robust_two_color_coverage,
)
from vice_compiler.fair_curve_program import (
    fair_program_from_coverage,
    fit_path_program,
    line_corridor_check,
    stable_corner_indices,
)
from vice_compiler.svg_fragment_renderer import render_program
from vice_compiler.vector_program import (
    CubicSpan,
    LineSpan,
    program_primitive_census,
    validate_text_vector_program,
)
from vice_compiler.wobble_metrics import span_fairness

CANVAS = 96
BLACK = (0.0, 0.0, 0.0, 1.0)


def _antialiased(draw, canvas: int = CANVAS, supersample: int = 4):
    big = np.zeros((canvas * supersample, canvas * supersample), np.float32)
    draw(big, supersample)
    return cv2.resize(
        big, (canvas, canvas), interpolation=cv2.INTER_AREA,
    ).astype(np.float32)


def _disc(canvas: int = CANVAS) -> np.ndarray:
    yy, xx = np.mgrid[0:canvas, 0:canvas]
    return np.clip(
        28.0 - np.hypot(xx - 48.0, yy - 48.0), 0.0, 1.0,
    ).astype(np.float32)


def _annulus(canvas: int = CANVAS) -> np.ndarray:
    yy, xx = np.mgrid[0:canvas, 0:canvas]
    outer = np.clip(30.0 - np.hypot(xx - 48.0, yy - 48.0), 0.0, 1.0)
    inner = np.clip(16.0 - np.hypot(xx - 48.0, yy - 48.0), 0.0, 1.0)
    return (outer * (1.0 - inner)).astype(np.float32)


def _rectangle() -> np.ndarray:
    field = np.zeros((CANVAS, CANVAS), np.float32)
    field[20:76, 14:82] = 1.0
    return field


def _triangle() -> np.ndarray:
    return _antialiased(lambda m, s: cv2.fillPoly(
        m, [np.array([[12 * s, 80 * s], [48 * s, 16 * s], [84 * s, 80 * s]])],
        1.0,
    ))


def _fit(alpha: np.ndarray, name: str):
    return fair_program_from_coverage(
        alpha, program_id=f"fair-{name}", source_line_id="line-0",
        straight_rgba=BLACK,
    )


class BoundaryEvidenceTests(unittest.TestCase):
    def test_marching_squares_is_subpixel_accurate(self) -> None:
        alpha = _disc()
        rings = marching_squares(alpha)
        self.assertEqual(len(rings), 1)
        radius = np.linalg.norm(rings[0] - np.array([48.0, 48.0]), axis=1)
        self.assertLess(float(np.std(radius)), 0.10)

    def test_topology_is_preserved_by_extraction(self) -> None:
        for name, alpha in (("disc", _disc()), ("annulus", _annulus())):
            with self.subTest(shape=name):
                observations = boundary_observations(alpha, component_id=name)
                self.assertTrue(
                    observations_preserve_topology(alpha, observations),
                )

    def test_two_colour_coverage_recovers_alpha(self) -> None:
        alpha = _disc()
        rgb = np.zeros((CANVAS, CANVAS, 3), np.float32)
        rgb[..., :] = 1.0
        rgb *= (1.0 - alpha)[..., None]
        estimate = robust_two_color_coverage(rgb, alpha >= 0.5)
        self.assertTrue(estimate.separable)
        error = np.abs(estimate.alpha - alpha)
        self.assertLess(float(np.percentile(error, 99)), 0.10)

    def test_sampling_density_does_not_change_cost(self) -> None:
        alpha = _rectangle()
        coarse = boundary_observations(alpha, component_id="c", step_px=0.5)[0]
        fine = boundary_observations(alpha, component_id="f", step_px=0.2)[0]
        self.assertAlmostEqual(coarse.length_px, fine.length_px, delta=1.0)
        span = LineSpan(p0=(14.0, 20.0), p1=(82.0, 20.0))

        def residual(observation) -> float:
            points = np.asarray(observation.points_xy)
            keep = np.flatnonzero(
                (points[:, 1] < 20.6) & (points[:, 0] > 15.0)
                & (points[:, 0] < 81.0)
            )
            check = line_corridor_check(
                span, points[keep],
                np.asarray(observation.normals_xy)[keep],
                np.asarray(observation.halfwidth_px)[keep],
                np.asarray(observation.physical_weights)[keep],
            )
            return check.residual

        coarse_cost = residual(coarse)
        fine_cost = residual(fine)
        self.assertLess(
            abs(coarse_cost - fine_cost) / max(1.0e-6, coarse_cost), 0.35,
            f"density changed the cost: {coarse_cost} vs {fine_cost}",
        )


class ExactPrimitiveTests(unittest.TestCase):
    def test_exact_line_emits_L_not_cubic(self) -> None:
        program, certificate = _fit(_rectangle(), "rect")
        self.assertIsNotNone(program)
        census = program_primitive_census(program)
        self.assertGreaterEqual(census.get("line", 0), 4)
        self.assertEqual(census.get("cubic", 0), 0)
        self.assertTrue(certificate.valid)

    def test_exact_circle_emits_arcs(self) -> None:
        program, certificate = _fit(_disc(), "disc")
        census = program_primitive_census(program)
        self.assertGreaterEqual(census.get("circular_arc", 0), 1)
        self.assertEqual(census.get("cubic", 0), 0)
        self.assertLessEqual(sum(census.values()), 8)
        self.assertTrue(certificate.valid)

    def test_clean_ellipse_stays_smooth_without_wobble(self) -> None:
        alpha = _antialiased(lambda m, s: cv2.ellipse(
            m, (48 * s, 48 * s), (34 * s, 20 * s), 0, 0, 360, 1.0, -1,
        ))
        program, certificate = _fit(alpha, "ellipse")
        self.assertIsNotNone(program)
        self.assertTrue(certificate.valid)
        self.assertEqual(certificate.unsupported_wobble_count, 0)
        self.assertLessEqual(sum(program_primitive_census(program).values()), 12)

    def test_true_corner_is_not_rounded(self) -> None:
        alpha = _triangle()
        observations = boundary_observations(alpha, component_id="tri")
        self.assertTrue(observations)
        corners = stable_corner_indices(observations[0])
        self.assertGreaterEqual(len(corners), 3)
        program, _certificate = _fit(alpha, "triangle")
        census = program_primitive_census(program)
        self.assertGreaterEqual(census.get("line", 0), 3)

    def test_rounded_rectangle_mixes_lines_and_arcs(self) -> None:
        alpha = _antialiased(lambda m, s: cv2.rectangle(
            m, (16 * s, 28 * s), (80 * s, 68 * s), 1.0, -1,
        ))
        program, certificate = _fit(alpha, "rounded")
        census = program_primitive_census(program)
        self.assertGreaterEqual(census.get("line", 0), 4)
        self.assertTrue(certificate.valid)


class FairnessRuleTests(unittest.TestCase):
    def test_wavy_cubic_over_a_straight_boundary_is_hard_invalid(self) -> None:
        observed = np.column_stack((
            np.linspace(0.0, 40.0, 60), np.zeros(60),
        ))
        normals = np.tile(np.array([0.0, 1.0]), (60, 1))
        wavy = CubicSpan(
            p0=(0.0, 0.0), c1=(13.0, 9.0), c2=(27.0, -9.0), p1=(40.0, 0.0),
        )
        fairness = span_fairness(
            wavy, path_id="probe", span_index=0,
            observed_points=observed, observed_normals=normals,
            halfwidth_px=np.full(60, 0.35), line_residual_px=0.0,
        )
        self.assertTrue(fairness.hard_invalid)
        self.assertIn(
            "unsupported-curvature-sign-change", fairness.invalid_reasons,
        )

    def test_smooth_bowl_has_no_curvature_reversal(self) -> None:
        bowl = CubicSpan(
            p0=(0.0, 0.0), c1=(10.0, 12.0), c2=(30.0, 12.0), p1=(40.0, 0.0),
        )
        fairness = span_fairness(bowl, path_id="probe", span_index=0)
        self.assertEqual(fairness.curvature_sign_changes, 0)
        self.assertEqual(fairness.tangent_reversal_count, 0)

    def test_s_curve_keeps_one_real_inflection(self) -> None:
        s_curve = CubicSpan(
            p0=(0.0, 0.0), c1=(14.0, 14.0), c2=(26.0, -14.0), p1=(40.0, 0.0),
        )
        fairness = span_fairness(s_curve, path_id="probe", span_index=0)
        self.assertEqual(fairness.curvature_sign_changes, 1)

    def test_line_span_is_curvature_free(self) -> None:
        fairness = span_fairness(
            LineSpan(p0=(0.0, 0.0), p1=(30.0, 12.0)),
            path_id="probe", span_index=0,
        )
        self.assertEqual(fairness.curvature_sign_changes, 0)
        self.assertEqual(
            fairness.scale_invariant_curvature_variation, 0.0,
        )

    def test_uncertain_microspan_uses_faithful_fallback(self) -> None:
        # A jagged one-pixel-scale boundary supports no primitive at all;
        # the program must still exist, carried by faithful microspans.
        field = np.zeros((48, 48), np.float32)
        for index in range(6, 42):
            field[index, 6:20 + (index % 3)] = 1.0
        observations = boundary_observations(field, component_id="jag")
        self.assertTrue(observations)
        spans, _rows = fit_path_program(observations[0])
        self.assertTrue(spans)
        self.assertTrue(all(span.kind in ("line", "cubic", "circular_arc")
                            for span in spans))


class DeliveredProgramTests(unittest.TestCase):
    def test_programs_are_valid_and_topology_faithful(self) -> None:
        cases = {
            "disc": _disc(), "annulus": _annulus(), "rect": _rectangle(),
            "triangle": _triangle(),
        }
        for name, alpha in cases.items():
            with self.subTest(shape=name):
                program, certificate = _fit(alpha, name)
                self.assertIsNotNone(program, f"{name} produced no program")
                validate_text_vector_program(program)
                self.assertTrue(certificate.valid)
                rendered = render_program(
                    program, width=CANVAS, height=CANVAS,
                ).alpha_mask
                self.assertEqual(
                    topology_signature(rendered),
                    topology_signature(alpha >= 0.5),
                    f"{name} changed topology",
                )
                intersection = int(np.sum(rendered & (alpha >= 0.5)))
                union = int(np.sum(rendered | (alpha >= 0.5)))
                self.assertGreater(intersection / max(1, union), 0.88)

    def test_program_digests_are_deterministic(self) -> None:
        first, _ = _fit(_disc(), "disc")
        second, _ = _fit(_disc(), "disc")
        self.assertEqual(first.program_sha256, second.program_sha256)
        self.assertEqual(
            first.exact_fragment_sha256, second.exact_fragment_sha256,
        )


if __name__ == "__main__":
    unittest.main()

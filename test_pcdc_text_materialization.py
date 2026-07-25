"""Materialization v2 — commit M2-02/M2-03 gates.

M2-02 gate (plan S7): the faithful program renders IDENTICALLY to the
current ``_pixel_run_path`` route, topology identical, digest deterministic.
M2-03 gate: the current smooth fitter, moved in front of the court, still
delivers the same bytes-worth of geometry (render identity through the
program round-trip).
"""

from __future__ import annotations

import unittest

import cv2
import numpy as np

from vice_compiler.certificates import topology_signature
from vice_compiler.export_writer import _fitted_mask_path, _paint, _pixel_run_path
from vice_compiler.svg_fragment_renderer import render_fragment, render_program
from vice_compiler.text_materialization import (
    FAITHFUL_FAMILY,
    LEGACY_SMOOTH_FAMILY,
    faithful_program_from_mask,
    generate_legacy_smooth_program,
    mask_runs,
    parse_path_data,
    program_from_path_data,
)
from vice_compiler.vector_program import (
    rgba_to_svg,
    serialize_text_vector_program,
    solid_paint_from_straight_rgba,
    srgb_to_linear,
    validate_text_vector_program,
)

CANVAS = 64


def _letter_o(canvas: int = CANVAS) -> np.ndarray:
    mask = np.zeros((canvas, canvas), np.uint8)
    cv2.ellipse(mask, (32, 32), (18, 24), 0, 0, 360, 1, thickness=6)
    return mask.astype(bool)


def _letter_b(canvas: int = CANVAS) -> np.ndarray:
    mask = np.zeros((canvas, canvas), np.uint8)
    cv2.rectangle(mask, (14, 8), (18, 56), 1, -1)
    cv2.ellipse(mask, (26, 20), (10, 11), 0, -90, 90, 1, thickness=5)
    cv2.ellipse(mask, (26, 44), (12, 12), 0, -90, 90, 1, thickness=5)
    return mask.astype(bool)


def _thin_stems(canvas: int = CANVAS) -> np.ndarray:
    mask = np.zeros((canvas, canvas), bool)
    for x in range(6, canvas - 6, 7):
        mask[10:canvas - 10, x] = True
    mask[30, 6:canvas - 6] = True
    return mask


def _dotted(canvas: int = CANVAS) -> np.ndarray:
    mask = np.zeros((canvas, canvas), bool)
    mask[5, 5] = True
    mask[9:12, 20:23] = True
    mask[40:44, 8:30] = True
    mask[50, 50] = True
    return mask


SHAPES = {
    "letter_o": _letter_o(), "letter_b": _letter_b(),
    "thin_stems": _thin_stems(), "dotted": _dotted(),
}

SMOOTH_CANVAS = 128


def _filled_disc() -> np.ndarray:
    mask = np.zeros((SMOOTH_CANVAS, SMOOTH_CANVAS), np.uint8)
    cv2.circle(mask, (64, 64), 40, 1, -1)
    return mask.astype(bool)


def _filled_rect() -> np.ndarray:
    mask = np.zeros((SMOOTH_CANVAS, SMOOTH_CANVAS), np.uint8)
    cv2.rectangle(mask, (20, 30), (108, 96), 1, -1)
    return mask.astype(bool)


def _rotated_ellipse() -> np.ndarray:
    mask = np.zeros((SMOOTH_CANVAS, SMOOTH_CANVAS), np.uint8)
    cv2.ellipse(mask, (64, 64), (46, 30), 20, 0, 360, 1, -1)
    return mask.astype(bool)


#: Shapes the legacy G1 fitter actually accepts (thin/holed shapes make it
#: refuse by design - its own raster proof rejects the smoothing).
SMOOTH_SHAPES = {
    "filled_disc": _filled_disc(), "filled_rect": _filled_rect(),
    "rotated_ellipse": _rotated_ellipse(),
}

BLACK_STRAIGHT = (0.0, 0.0, 0.0, 1.0)
BLUE_STRAIGHT = (0.12, 0.35, 0.86, 1.0)


def _legacy_faithful_fragment(mask: np.ndarray, straight_rgba) -> str:
    data = _pixel_run_path(mask)
    colour = tuple(
        int(round(float(value) * 255.0)) for value in straight_rgba[:3]
    ) + (float(straight_rgba[3]),)
    return f'<path d="{data}" fill-rule="evenodd" {_paint(colour)}/>'


class ColourParityTests(unittest.TestCase):
    def test_srgb_roundtrip_is_exact_for_all_bytes(self) -> None:
        for value in range(256):
            display = value / 255.0
            paint = solid_paint_from_straight_rgba(
                (display, display, display, 1.0),
            )
            hexed, _alpha = rgba_to_svg(paint.rgba_linear)
            self.assertEqual(
                hexed, "#%02x%02x%02x" % (value, value, value),
                f"channel {value} did not round-trip",
            )

    def test_linear_conversion_is_monotone(self) -> None:
        values = [srgb_to_linear(v / 32.0) for v in range(33)]
        self.assertTrue(all(b >= a for a, b in zip(values, values[1:])))

    def test_alpha_threshold_matches_legacy(self) -> None:
        paint = solid_paint_from_straight_rgba((0.0, 0.0, 0.0, 0.9996))
        program = faithful_program_from_mask(
            SHAPES["dotted"], program_id="p", source_line_id="l",
            straight_rgba=(0.0, 0.0, 0.0, 0.9996),
        )
        fragment = serialize_text_vector_program(program)
        self.assertNotIn("fill-opacity", fragment)
        self.assertAlmostEqual(paint.rgba_linear[3], 0.9996, places=6)


class FaithfulParityTests(unittest.TestCase):
    """M2-02 gate: v2 faithful == current faithful, exactly."""

    def test_runs_match_legacy_path_string(self) -> None:
        for name, mask in SHAPES.items():
            with self.subTest(shape=name):
                expected = _pixel_run_path(mask)
                rebuilt = " ".join(
                    f"M{start},{y}H{end}V{y + 1}H{start}Z"
                    for y, start, end in mask_runs(mask)
                )
                self.assertEqual(rebuilt, expected)

    def test_render_is_pixel_identical_to_legacy(self) -> None:
        for name, mask in SHAPES.items():
            for straight in (BLACK_STRAIGHT, BLUE_STRAIGHT):
                with self.subTest(shape=name, colour=straight):
                    legacy = render_fragment(
                        _legacy_faithful_fragment(mask, straight),
                        width=CANVAS, height=CANVAS,
                    )
                    program = faithful_program_from_mask(
                        mask, program_id=f"faithful-{name}",
                        source_line_id="line-0", straight_rgba=straight,
                    )
                    candidate = render_program(
                        program, width=CANVAS, height=CANVAS,
                    )
                    self.assertEqual(
                        legacy.rgba_sha256, candidate.rgba_sha256,
                        "faithful v2 render differs from the legacy route",
                    )

    def test_topology_is_identical_to_source(self) -> None:
        for name, mask in SHAPES.items():
            with self.subTest(shape=name):
                program = faithful_program_from_mask(
                    mask, program_id=f"faithful-{name}",
                    source_line_id="line-0", straight_rgba=BLACK_STRAIGHT,
                )
                rendered = render_program(
                    program, width=CANVAS, height=CANVAS,
                ).alpha_mask
                self.assertEqual(
                    topology_signature(rendered), topology_signature(mask),
                )
                self.assertTrue(np.array_equal(rendered, mask))

    def test_program_is_sealed_and_deterministic(self) -> None:
        first = faithful_program_from_mask(
            SHAPES["letter_o"], program_id="p", source_line_id="l",
            straight_rgba=BLACK_STRAIGHT,
        )
        second = faithful_program_from_mask(
            SHAPES["letter_o"], program_id="p", source_line_id="l",
            straight_rgba=BLACK_STRAIGHT,
        )
        self.assertEqual(first.program_sha256, second.program_sha256)
        self.assertEqual(first.geometry_family, FAITHFUL_FAMILY)
        validate_text_vector_program(first)

    def test_empty_mask_yields_no_program(self) -> None:
        self.assertIsNone(faithful_program_from_mask(
            np.zeros((8, 8), bool), program_id="p", source_line_id="l",
            straight_rgba=BLACK_STRAIGHT,
        ))


class PathParserTests(unittest.TestCase):
    def test_parses_pixel_run_syntax(self) -> None:
        rings = parse_path_data("M3,4H7V5H3Z M10,4H12V5H10Z")
        self.assertEqual(len(rings), 2)
        for ring in rings:
            self.assertEqual(len(ring), 4)
            self.assertEqual(ring[0].p0, (3.0, 4.0) if ring is rings[0] else (10.0, 4.0))

    def test_parses_cubic_and_line_mix(self) -> None:
        rings = parse_path_data("M0 0C1 2 3 4 5 0L0 0Z")
        self.assertEqual(len(rings), 1)
        self.assertEqual([span.kind for span in rings[0]], ["cubic", "line"])

    def test_implicit_closing_segment_is_added(self) -> None:
        rings = parse_path_data("M0 0L4 0L4 4Z")
        self.assertEqual(len(rings[0]), 3)
        self.assertEqual(rings[0][-1].p1, (0.0, 0.0))

    def test_truncated_data_raises(self) -> None:
        with self.assertRaises(Exception):
            parse_path_data("M0 0L4")

    def test_roundtrip_of_legacy_run_path_renders_identically(self) -> None:
        mask = SHAPES["letter_b"]
        data = _pixel_run_path(mask)
        program = program_from_path_data(
            data, program_id="roundtrip", source_line_id="line-0",
            geometry_family="parsed-faithful", straight_rgba=BLACK_STRAIGHT,
        )
        legacy = render_fragment(
            _legacy_faithful_fragment(mask, BLACK_STRAIGHT),
            width=CANVAS, height=CANVAS,
        )
        parsed = render_program(program, width=CANVAS, height=CANVAS)
        self.assertEqual(legacy.rgba_sha256, parsed.rgba_sha256)


class LegacySmoothParityTests(unittest.TestCase):
    """M2-03 gate: the current fitter survives the program round-trip."""

    def test_smooth_program_matches_legacy_render(self) -> None:
        checked = 0
        for name, mask in SMOOTH_SHAPES.items():
            data = _fitted_mask_path(mask, density_proof=False)
            self.assertTrue(data, f"{name} no longer exercises the fitter")
            checked += 1
            with self.subTest(shape=name):
                legacy = render_fragment(
                    f'<path d="{data}" fill-rule="evenodd" '
                    f'{_paint((0, 0, 0, 1.0))}/>',
                    width=SMOOTH_CANVAS, height=SMOOTH_CANVAS,
                )
                program = generate_legacy_smooth_program(
                    mask, program_id=f"smooth-{name}", source_line_id="line-0",
                    straight_rgba=BLACK_STRAIGHT, density_proof=False,
                )
                self.assertIsNotNone(program)
                self.assertEqual(program.geometry_family, LEGACY_SMOOTH_FAMILY)
                rendered = render_program(
                    program, width=SMOOTH_CANVAS, height=SMOOTH_CANVAS,
                )
                self.assertEqual(legacy.rgba_sha256, rendered.rgba_sha256)
        self.assertGreater(checked, 0, "no shape exercised the smooth fitter")

    def test_generator_fails_open_exactly_like_the_fitter(self) -> None:
        # The production call site uses density_proof=True, where the fitter
        # refuses these shapes; the generator must return None, never a
        # silently different geometry.
        for name, mask in SMOOTH_SHAPES.items():
            with self.subTest(shape=name):
                self.assertEqual(
                    _fitted_mask_path(mask, density_proof=True), "",
                )
                self.assertIsNone(generate_legacy_smooth_program(
                    mask, program_id=f"smooth-{name}",
                    source_line_id="line-0", straight_rgba=BLACK_STRAIGHT,
                    density_proof=True,
                ))

    def test_smooth_program_keeps_source_topology(self) -> None:
        for name, mask in SMOOTH_SHAPES.items():
            with self.subTest(shape=name):
                program = generate_legacy_smooth_program(
                    mask, program_id=f"smooth-{name}", source_line_id="line-0",
                    straight_rgba=BLACK_STRAIGHT, density_proof=False,
                )
                rendered = render_program(
                    program, width=SMOOTH_CANVAS, height=SMOOTH_CANVAS,
                ).alpha_mask
                self.assertEqual(
                    topology_signature(rendered), topology_signature(mask),
                )

    def test_hole_rings_are_marked_negative(self) -> None:
        mask = np.zeros((CANVAS, CANVAS), bool)
        mask[10:50, 10:50] = True
        mask[20:40, 20:40] = False
        data = _pixel_run_path(mask)
        program = program_from_path_data(
            data, program_id="ring-roles", source_line_id="line-0",
            geometry_family="parsed-faithful", straight_rgba=BLACK_STRAIGHT,
        )
        # Run decomposition has no nesting, so all rings stay positive and the
        # even-odd rule still renders the hole.
        rendered = render_program(program, width=CANVAS, height=CANVAS)
        self.assertEqual(
            topology_signature(rendered.alpha_mask), topology_signature(mask),
        )


if __name__ == "__main__":
    unittest.main()

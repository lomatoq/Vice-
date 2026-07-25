"""Materialization v2 — commit M2-05 gate: correspondence and separation.

Plan S8 "Text topology" list: counters keep their identity, adjacent
letters keep a background corridor, a real ligature needs an explicit
operator, a frame does not fuse with the text inside it, and the delivered
topology is stable at 1x/2x/4x and across pixel phases.
"""

from __future__ import annotations

import unittest

import cv2
import numpy as np

from vice_compiler.materialization_certificates import (
    component_correspondence,
    delivery_identity_certificate,
    gap_corridor_points,
    separation_certificate,
)
from vice_compiler.svg_fragment_renderer import render_program
from vice_compiler.text_materialization import faithful_program_from_mask

CANVAS = 96
BLACK = (0.0, 0.0, 0.0, 1.0)


def _two_letters(gap: int = 4) -> np.ndarray:
    mask = np.zeros((CANVAS, CANVAS), bool)
    mask[30:70, 20:36] = True
    mask[30:70, 36 + gap:52 + gap] = True
    return mask


def _letter_o() -> np.ndarray:
    mask = np.zeros((CANVAS, CANVAS), np.uint8)
    cv2.ellipse(mask, (48, 48), (18, 26), 0, 0, 360, 1, thickness=7)
    return mask.astype(bool)


def _letter_b() -> np.ndarray:
    """One body with two enclosed counters (the topology that matters)."""
    mask = np.zeros((CANVAS, CANVAS), np.uint8)
    cv2.rectangle(mask, (24, 16), (58, 80), 1, -1)
    cv2.rectangle(mask, (34, 24), (50, 42), 0, -1)
    cv2.rectangle(mask, (34, 54), (50, 72), 0, -1)
    return mask.astype(bool)


def _frame_with_text() -> np.ndarray:
    mask = np.zeros((CANVAS, CANVAS), np.uint8)
    cv2.rectangle(mask, (8, 24), (88, 72), 1, thickness=4)
    cv2.rectangle(mask, (24, 40), (34, 58), 1, -1)
    cv2.rectangle(mask, (44, 40), (54, 58), 1, -1)
    return mask.astype(bool)


def _render_scales(mask: np.ndarray) -> dict[str, np.ndarray]:
    program = faithful_program_from_mask(
        mask, program_id="p", source_line_id="l", straight_rgba=BLACK,
    )
    out: dict[str, np.ndarray] = {}
    for label, factor in (("native", 1), ("scale2", 2), ("scale4", 4)):
        rendered = render_program(
            program, width=CANVAS, height=CANVAS, supersample=factor,
        )
        out[label] = rendered.rgba[..., 3].astype(np.float32) / 255.0
    return out


class CorrespondenceTests(unittest.TestCase):
    def test_identical_masks_match_one_to_one(self) -> None:
        mask = _two_letters()
        certificate = component_correspondence(mask, mask)
        self.assertTrue(certificate.valid)
        self.assertEqual(len(certificate.matches), 2)
        self.assertEqual(certificate.unmatched_source_ids, ())
        self.assertEqual(certificate.fused_source_groups, ())

    def test_fusion_is_detected_and_rejected(self) -> None:
        source = _two_letters(gap=4)
        fused = source.copy()
        fused[30:70, 36:40] = True          # bridge the gap
        certificate = component_correspondence(source, fused)
        self.assertFalse(certificate.valid)
        self.assertTrue(certificate.fused_source_groups)
        self.assertIn(
            "source-bodies-fused-without-operator", certificate.violations,
        )

    def test_explicit_operator_admits_a_true_ligature(self) -> None:
        source = _two_letters(gap=4)
        fused = source.copy()
        fused[30:70, 36:40] = True
        certificate = component_correspondence(
            source, fused, allow_fusion=True,
        )
        self.assertEqual(certificate.violations, ())

    def test_counter_loss_is_detected(self) -> None:
        source = _letter_o()
        filled = source.copy()
        cv2.floodFill(
            filled.astype(np.uint8), None, (48, 48), 1,
        )
        solid = np.zeros_like(source)
        cv2.ellipse(
            solid.view(np.uint8), (48, 48), (18, 26), 0, 0, 360, 1, -1,
        )
        certificate = component_correspondence(source, solid.astype(bool))
        self.assertFalse(certificate.valid)
        self.assertIn("counter-lost", certificate.violations)

    def test_two_counters_of_b_are_preserved(self) -> None:
        mask = _letter_b()
        certificate = component_correspondence(mask, mask)
        self.assertTrue(certificate.valid)
        self.assertEqual(certificate.counter_mismatches, ())
        self.assertEqual(certificate.matches[0].source_holes, 2)
        self.assertEqual(certificate.matches[0].delivered_holes, 2)

    def test_split_body_is_rejected(self) -> None:
        source = np.zeros((CANVAS, CANVAS), bool)
        source[30:70, 20:60] = True
        split = source.copy()
        split[30:70, 38:42] = False
        certificate = component_correspondence(source, split)
        self.assertFalse(certificate.valid)
        self.assertIn("source-body-split", certificate.violations)

    def test_invented_body_is_rejected(self) -> None:
        source = _two_letters()
        invented = source.copy()
        invented[10:20, 70:80] = True
        certificate = component_correspondence(source, invented)
        self.assertFalse(certificate.valid)
        self.assertIn("unsupported-delivered-body", certificate.violations)


class SeparationTests(unittest.TestCase):
    def test_gap_corridor_is_found_between_neighbours(self) -> None:
        mask = _two_letters(gap=4)
        left = np.zeros_like(mask)
        left[30:70, 20:36] = True
        right = np.zeros_like(mask)
        right[30:70, 40:56] = True
        points = gap_corridor_points(left, right)
        self.assertTrue(points)
        for x, _y in points:
            self.assertGreater(x, 35.0)
            self.assertLess(x, 41.0)

    def test_faithful_delivery_keeps_the_corridor_at_all_scales(self) -> None:
        mask = _two_letters(gap=4)
        certificate = separation_certificate(mask, _render_scales(mask))
        self.assertTrue(certificate.valid, certificate.violations)
        self.assertTrue(certificate.corridors)
        for corridor in certificate.corridors:
            self.assertTrue(corridor.native_pass)
            self.assertTrue(corridor.scale2_pass)
            self.assertTrue(corridor.scale4_pass)

    def test_bridged_delivery_fails_separation(self) -> None:
        mask = _two_letters(gap=4)
        bridged = mask.copy()
        bridged[46:52, 36:40] = True
        certificate = separation_certificate(mask, _render_scales(bridged))
        self.assertFalse(certificate.valid)
        self.assertTrue(certificate.violations)

    def test_explicit_operator_admits_the_bridge(self) -> None:
        mask = _two_letters(gap=4)
        bridged = mask.copy()
        bridged[46:52, 36:40] = True
        certificate = separation_certificate(
            mask, _render_scales(bridged),
            explicit_fusion_operator="ligature",
        )
        self.assertTrue(certificate.valid)

    def test_frame_does_not_fuse_with_inner_text(self) -> None:
        mask = _frame_with_text()
        certificate = separation_certificate(mask, _render_scales(mask))
        self.assertTrue(certificate.valid, certificate.violations)
        correspondence = component_correspondence(mask, mask)
        self.assertTrue(correspondence.valid)
        self.assertEqual(len(correspondence.matches), 3)


class DeliveryIdentityTests(unittest.TestCase):
    def test_identity_certificate_matches_the_program(self) -> None:
        mask = _letter_o()
        program = faithful_program_from_mask(
            mask, program_id="p", source_line_id="l", straight_rgba=BLACK,
        )
        rendered = render_program(program, width=CANVAS, height=CANVAS)
        certificate = delivery_identity_certificate(
            program, rendered_rgba_sha256=rendered.rgba_sha256,
        )
        self.assertTrue(certificate.valid)
        self.assertEqual(
            certificate.svg_fragment_sha256, program.exact_fragment_sha256,
        )
        self.assertEqual(certificate.rendered_rgba_sha256, rendered.rgba_sha256)

    def test_tampered_program_fails_identity(self) -> None:
        from dataclasses import replace

        mask = _letter_o()
        program = faithful_program_from_mask(
            mask, program_id="p", source_line_id="l", straight_rgba=BLACK,
        )
        tampered = replace(program, exact_fragment_sha256="0" * 64)
        certificate = delivery_identity_certificate(
            tampered, rendered_rgba_sha256="",
        )
        self.assertFalse(certificate.valid)
        self.assertIn("fragment-digest-mismatch", certificate.violations)


if __name__ == "__main__":
    unittest.main()

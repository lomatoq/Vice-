"""Materialization v2 — commit M2-08/M2-09 gates.

Plan S8 "Delivery identity": the courted fragment IS the exported
fragment, its digest matches the exact render, the exporter cannot refit
the selected program, and a serializer change invalidates the digest.
Plus the M9 transaction: refinement moves real span parameters, never the
structure, and rolls back anything that is not an improvement.
"""

from __future__ import annotations

import hashlib
import os
import unittest
from dataclasses import replace

import cv2
import numpy as np

from vice_compiler.fair_curve_program import fair_program_from_coverage
from vice_compiler.program_refinement import refine_program
from vice_compiler.svg_fragment_renderer import render_program
from vice_compiler.text_materialization import faithful_program_from_mask
from vice_compiler.text_vector_court import (
    evaluation_domain,
    race_materializations,
)
from vice_compiler.vector_program import (
    CircularArcSpan,
    SERIALIZER_VERSION,
    program_digest,
    serialize_text_vector_program,
    validate_text_vector_program,
)

CANVAS = 96
BLACK = (0.0, 0.0, 0.0, 1.0)


def _disc_coverage(radius: int = 29, supersample: int = 4) -> np.ndarray:
    big = np.zeros((CANVAS * supersample, CANVAS * supersample), np.float32)
    cv2.circle(
        big, (48 * supersample, 48 * supersample), radius * supersample,
        1.0, -1,
    )
    return cv2.resize(
        big, (CANVAS, CANVAS), interpolation=cv2.INTER_AREA,
    ).astype(np.float32)


class DeliveryIdentityTests(unittest.TestCase):
    def test_courted_fragment_equals_exported_fragment(self) -> None:
        coverage = _disc_coverage()
        race = race_materializations(
            coverage >= 0.5, record_id="rec", line_id="line",
            straight_rgba=BLACK, coverage=coverage,
        )
        self.assertIsNotNone(race)
        winner = race.winner
        exported = serialize_text_vector_program(winner.program)
        self.assertEqual(exported, winner.exact_svg_fragment)
        self.assertEqual(
            hashlib.sha256(exported.encode("utf-8")).hexdigest(),
            winner.program.exact_fragment_sha256,
        )

    def test_fragment_digest_matches_exact_render(self) -> None:
        coverage = _disc_coverage()
        race = race_materializations(
            coverage >= 0.5, record_id="rec", line_id="line",
            straight_rgba=BLACK, coverage=coverage,
        )
        winner = race.winner
        rendered = render_program(
            winner.program, width=CANVAS, height=CANVAS,
        )
        self.assertEqual(rendered.rgba_sha256, winner.exact_render_sha256)

    def test_render_program_refuses_a_tampered_digest(self) -> None:
        program = faithful_program_from_mask(
            _disc_coverage() >= 0.5, program_id="p", source_line_id="l",
            straight_rgba=BLACK,
        )
        tampered = replace(program, exact_fragment_sha256="0" * 64)
        with self.assertRaises(ValueError):
            render_program(tampered, width=CANVAS, height=CANVAS)

    def test_program_digest_binds_the_serializer_version(self) -> None:
        program = faithful_program_from_mask(
            _disc_coverage() >= 0.5, program_id="p", source_line_id="l",
            straight_rgba=BLACK,
        )
        from vice_compiler.vector_program import canonical_json

        self.assertIn(SERIALIZER_VERSION, canonical_json(program))
        self.assertEqual(program_digest(program), program.program_sha256)

    def test_exporter_route_is_off_by_default(self) -> None:
        self.assertNotEqual(
            os.environ.get("VICE_TEXT_MATERIALIZATION_V2"), "1",
            "the migration flag must be opt-in",
        )


class ProgramRefinementTests(unittest.TestCase):
    def _fair_disc(self):
        coverage = _disc_coverage()
        program, _certificate = fair_program_from_coverage(
            coverage, program_id="p", source_line_id="l",
            straight_rgba=BLACK,
        )
        return program, coverage

    def test_refinement_recovers_a_perturbed_radius(self) -> None:
        program, coverage = self._fair_disc()
        self.assertTrue(any(
            isinstance(span, CircularArcSpan)
            for path in program.paths for span in path.spans
        ))
        domain = evaluation_domain(coverage >= 0.5, apron=3)
        clean_error = refine_program(
            program, observed_alpha=coverage, evaluation_domain=domain,
        ).error_before
        # Shrink every arc: a worse program the transaction should improve.
        from vice_compiler.vector_program import seal_program

        from vice_compiler.program_refinement import rescale_arc

        perturbed_paths = []
        for path in program.paths:
            spans = []
            for span in path.spans:
                rescaled = (
                    rescale_arc(span, 1.06)
                    if isinstance(span, CircularArcSpan) else None
                )
                spans.append(rescaled if rescaled is not None else span)
            perturbed_paths.append(replace(path, spans=tuple(spans)))
        perturbed = seal_program(replace(program, paths=tuple(perturbed_paths)))
        result = refine_program(
            perturbed, observed_alpha=coverage, evaluation_domain=domain,
        )
        self.assertTrue(result.committed)
        # The transaction is a bounded local search, not a full solver: it
        # must recover a large part of the damage and may never regress.
        self.assertLess(result.error_after, 0.5 * result.error_before)
        self.assertGreater(clean_error, 0.0)
        validate_text_vector_program(result.program)

    def test_refinement_never_changes_structure(self) -> None:
        program, coverage = self._fair_disc()
        domain = evaluation_domain(coverage >= 0.5, apron=3)
        result = refine_program(
            program, observed_alpha=coverage, evaluation_domain=domain,
        )
        self.assertEqual(len(result.program.paths), len(program.paths))
        self.assertEqual(
            [[span.kind for span in path.spans] for path in result.program.paths],
            [[span.kind for span in path.spans] for path in program.paths],
        )
        self.assertEqual(
            [path.role for path in result.program.paths],
            [path.role for path in program.paths],
        )

    def test_refinement_rolls_back_when_certifier_refuses(self) -> None:
        program, coverage = self._fair_disc()
        domain = evaluation_domain(coverage >= 0.5, apron=3)
        result = refine_program(
            program, observed_alpha=coverage, evaluation_domain=domain,
            recertify=lambda _candidate: False,
        )
        self.assertFalse(result.committed)
        self.assertEqual(result.program.program_sha256, program.program_sha256)
        self.assertEqual(result.rollback_reason, "no-admissible-improvement")


if __name__ == "__main__":
    unittest.main()

"""Materialization v2 — commit M2-04 gate: ownership vs evaluation domain.

Plan S1.6 / M8.1.  A candidate that silently drops a small red detail
today pays nothing, because the score is computed on the candidate's own
claim and the omission lies outside it.  With an evaluation domain
(candidate | fallback | required evidence, plus an apron) the omission is
inside the scored region and costs its real price.

Plan S8 "Court" list: the omitted detail is inside the evaluation support,
a candidate claim cannot move the score domain, and a tie returns fallback.
"""

from __future__ import annotations

import unittest

import cv2
import numpy as np

from vice_compiler.atlas_renderer import ExactRoiAtlas, RoiRenderRequest
from vice_compiler.local_court import (
    CourtCandidate,
    CourtWeights,
    compare_in_local_court,
)
from vice_compiler.renderer_posterior import synthetic_renderer_posterior

CANVAS = 48
ROI = (4, 4, 44, 44)


def _observed() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Black bar plus a small red detail on white (premultiplied linear)."""
    rgba = np.zeros((CANVAS, CANVAS, 4), np.float32)
    rgba[..., :3] = 1.0
    rgba[..., 3] = 1.0
    bar = np.zeros((CANVAS, CANVAS), bool)
    bar[14:34, 8:30] = True
    detail = np.zeros((CANVAS, CANVAS), bool)
    detail[18:24, 33:39] = True
    rgba[bar] = np.array([0.0, 0.0, 0.0, 1.0], np.float32)
    rgba[detail] = np.array([0.55, 0.02, 0.02, 1.0], np.float32)
    return rgba, bar, detail


def _raster_request(
    id_: str, painted: dict[tuple[int, int, int, int], tuple[float, ...]],
) -> RoiRenderRequest:
    x1, y1, x2, y2 = ROI
    patch = np.zeros((y2 - y1, x2 - x1, 4), np.float32)
    patch[..., :3] = 1.0
    patch[..., 3] = 1.0
    for (bx1, by1, bx2, by2), colour in painted.items():
        patch[by1 - y1:by2 - y1, bx1 - x1:bx2 - x1] = np.array(
            colour, np.float32,
        )
    return RoiRenderRequest(
        id=id_, roi_xyxy=ROI, kind="raster",
        raster_premultiplied_linear_rgba=patch,
        supersample=1,
    )


def _mask_from(boxes) -> np.ndarray:
    mask = np.zeros((CANVAS, CANVAS), bool)
    for (x1, y1, x2, y2) in boxes:
        mask[y1:y2, x1:x2] = True
    return mask


BAR_BOX = (8, 14, 30, 34)
DETAIL_BOX = (33, 18, 39, 24)
BLACK = (0.0, 0.0, 0.0, 1.0)
RED = (0.55, 0.02, 0.02, 1.0)
WHITE = (1.0, 1.0, 1.0, 1.0)


class EvaluationDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.observed, self.bar, self.detail = _observed()
        self.posterior = synthetic_renderer_posterior(
            source_id="materialization-court-unit",
        )
        self.atlas = ExactRoiAtlas()
        self.evidence = self.bar | self.detail

    def _run(self, *, evaluation: np.ndarray | None):
        """Candidate draws only the bar; fallback draws bar AND detail."""
        candidate = CourtCandidate(
            id="omits-detail",
            request=_raster_request("omits-detail", {BAR_BOX: BLACK}),
            claimed_support=_mask_from([BAR_BOX]),
            certificate_alpha_mask=_mask_from([BAR_BOX]).astype(np.float32),
            evaluation_support=evaluation,
        )
        fallback = CourtCandidate(
            id="keeps-detail",
            request=_raster_request(
                "keeps-detail", {BAR_BOX: BLACK, DETAIL_BOX: RED},
            ),
            claimed_support=_mask_from([BAR_BOX, DETAIL_BOX]),
            certificate_alpha_mask=_mask_from(
                [BAR_BOX, DETAIL_BOX],
            ).astype(np.float32),
        )
        return compare_in_local_court(
            self.observed, self.evidence, candidate, fallback,
            self.posterior, atlas=self.atlas,
        )

    def test_evaluation_domain_never_helps_an_omitting_candidate(self) -> None:
        # Widening the scored region to include what the candidate dropped
        # can only make its score worse; it must never rescue it.
        claim_scoped = self._run(evaluation=None)
        evaluation = cv2.dilate(
            (self.evidence | _mask_from([BAR_BOX, DETAIL_BOX])).astype(
                np.uint8,
            ),
            np.ones((3, 3), np.uint8),
        ).astype(bool)
        domain_scoped = self._run(evaluation=evaluation)
        self.assertLessEqual(
            domain_scoped.candidate_score, claim_scoped.candidate_score + 1e-9,
        )
        self.assertFalse(domain_scoped.candidate_selected)

    def test_omitted_detail_loses_on_the_evaluation_domain(self) -> None:
        evaluation = cv2.dilate(
            (self.evidence | _mask_from([BAR_BOX, DETAIL_BOX])).astype(
                np.uint8,
            ),
            np.ones((3, 3), np.uint8),
        ).astype(bool)
        decision = self._run(evaluation=evaluation)
        self.assertLess(decision.candidate_score, 0.0)
        self.assertFalse(decision.candidate_selected)

    def test_candidate_claim_cannot_move_the_score_domain(self) -> None:
        evaluation = cv2.dilate(
            (self.evidence | _mask_from([BAR_BOX, DETAIL_BOX])).astype(
                np.uint8,
            ),
            np.ones((3, 3), np.uint8),
        ).astype(bool)
        wide = self._run(evaluation=evaluation)
        # Shrinking the claim must not rescue the candidate: the evaluation
        # domain is supplied by the court, not by the candidate.
        candidate = CourtCandidate(
            id="tiny-claim",
            request=_raster_request("tiny-claim", {BAR_BOX: BLACK}),
            claimed_support=_mask_from([(10, 16, 20, 30)]),
            certificate_alpha_mask=_mask_from([BAR_BOX]).astype(np.float32),
            evaluation_support=evaluation,
        )
        fallback = CourtCandidate(
            id="keeps-detail",
            request=_raster_request(
                "keeps-detail", {BAR_BOX: BLACK, DETAIL_BOX: RED},
            ),
            claimed_support=_mask_from([BAR_BOX, DETAIL_BOX]),
            certificate_alpha_mask=_mask_from(
                [BAR_BOX, DETAIL_BOX],
            ).astype(np.float32),
        )
        narrow = compare_in_local_court(
            self.observed, self.evidence, candidate, fallback,
            self.posterior, atlas=self.atlas,
        )
        self.assertFalse(narrow.candidate_selected)
        self.assertLess(narrow.candidate_score, 0.0)
        self.assertAlmostEqual(
            narrow.candidate_score, wide.candidate_score, delta=0.35,
        )

    def test_ownership_must_lie_inside_the_evaluation_domain(self) -> None:
        with self.assertRaises(ValueError):
            CourtCandidate(
                id="rogue",
                request=_raster_request("rogue", {BAR_BOX: BLACK}),
                claimed_support=_mask_from([BAR_BOX]),
                evaluation_support=_mask_from([(0, 0, 4, 4)]),
            ).validate((CANVAS, CANVAS))

    def test_tie_returns_fallback(self) -> None:
        identical = _raster_request("same", {BAR_BOX: BLACK})
        mask = _mask_from([BAR_BOX])
        candidate = CourtCandidate(
            id="candidate", request=identical, claimed_support=mask,
            certificate_alpha_mask=mask.astype(np.float32),
        )
        fallback = CourtCandidate(
            id="fallback",
            request=_raster_request("same-fallback", {BAR_BOX: BLACK}),
            claimed_support=mask,
            certificate_alpha_mask=mask.astype(np.float32),
        )
        decision = compare_in_local_court(
            self.observed, self.evidence, candidate, fallback,
            self.posterior, atlas=self.atlas,
            weights=CourtWeights(),
        )
        self.assertFalse(decision.candidate_selected)
        self.assertNotIn("positive-conservative-utility", decision.reason)


if __name__ == "__main__":
    unittest.main()


class MaterializationRaceTests(unittest.TestCase):
    """Plan M8: pixel-faithful vs fair program, decided before delivery."""

    @staticmethod
    def _coverage(draw, size: int = 96, supersample: int = 4) -> np.ndarray:
        big = np.zeros((size * supersample, size * supersample), np.float32)
        draw(big, supersample)
        return cv2.resize(
            big, (size, size), interpolation=cv2.INTER_AREA,
        ).astype(np.float32)

    def _race(self, coverage: np.ndarray, name: str):
        from vice_compiler.text_vector_court import race_materializations

        return race_materializations(
            coverage >= 0.5, record_id=f"record-{name}", line_id="line-0",
            straight_rgba=(0.0, 0.0, 0.0, 1.0), coverage=coverage,
        )

    def test_fair_arc_beats_pixel_faithful_on_a_smooth_shape(self) -> None:
        coverage = self._coverage(
            lambda m, s: cv2.circle(m, (48 * s, 48 * s), 30 * s, 1.0, -1),
        )
        race = self._race(coverage, "disc")
        self.assertIsNotNone(race)
        self.assertEqual(
            race.winner.program.geometry_family, "fair-primitive-hybrid",
        )
        self.assertLess(race.winner.resource_estimate.span_count, 12)

    def test_fair_program_wins_a_physical_tie_on_fairness(self) -> None:
        coverage = self._coverage(
            lambda m, s: cv2.rectangle(
                m, (16 * s, 28 * s), (80 * s, 68 * s), 1.0, -1,
            ),
        )
        race = self._race(coverage, "rounded")
        decision = race.decisions[-1]
        self.assertTrue(decision.candidate_selected)
        self.assertEqual(decision.reason, "fair-program-wins-physical-tie")
        self.assertGreater(decision.fairness_delta, 0.0)
        self.assertLess(abs(decision.render_delta), 0.010)

    def test_pixel_faithful_wins_when_evidence_is_undecided(self) -> None:
        size = 96
        coverage = np.array([
            [
                1.0 if (abs(x - 48) < 20 and abs(y - 48) < 20
                        and (x + y) % 7 != 0) else 0.0
                for x in range(size)
            ]
            for y in range(size)
        ], np.float32)
        race = self._race(coverage, "jagged")
        self.assertEqual(
            race.winner.program.geometry_family, "faithful-cell-edge",
        )
        self.assertEqual(
            race.decisions[-1].reason, "negative-render-evidence-fallback",
        )

    def test_fairness_cannot_buy_a_topology_loss(self) -> None:
        from vice_compiler.materialization_certificates import (
            component_correspondence,
        )
        from vice_compiler.text_vector_court import compare_materializations
        from vice_compiler.text_materialization import (
            MaterializationCertificateBundle,
        )

        coverage = self._coverage(
            lambda m, s: cv2.ellipse(
                m, (48 * s, 48 * s), (24 * s, 32 * s), 0, 0, 360, 1.0, 7 * s,
            ),
        )
        race = self._race(coverage, "letter-o")
        winner = race.winner
        # Forge a candidate whose topology certificate failed: no render
        # advantage may rescue it.
        source = coverage >= 0.5
        filled = np.zeros_like(source)
        cv2.ellipse(
            filled.view(np.uint8), (48, 48), (24, 32), 0, 0, 360, 1, -1,
        )
        from dataclasses import replace as dc_replace

        from vice_compiler.materialization_certificates import (
            MaterializationCertificates,
        )

        broken = dc_replace(
            winner,
            certificates=MaterializationCertificates(
                topology=component_correspondence(source, filled.astype(bool)),
            ),
        )
        decision = compare_materializations(
            broken, race.candidates[0], observed_alpha=coverage,
            candidate_fairness_cost=0.0, fallback_fairness_cost=99.0,
        )
        self.assertFalse(decision.candidate_selected)
        self.assertEqual(decision.reason, "candidate-certificate-rejected")
        self.assertTrue(decision.violations)

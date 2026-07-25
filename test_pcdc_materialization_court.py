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

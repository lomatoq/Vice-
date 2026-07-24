from __future__ import annotations

from dataclasses import replace
import math
import unittest

import cv2
import numpy as np

from vice_compiler.atlas_renderer import ExactRoiAtlas, RoiRenderRequest
from vice_compiler.certificates import (
    build_geometry_certificate, build_topology_certificate,
    build_validity_certificate,
)
from vice_compiler.experiment3_certificate_discrimination import _make_pair
from vice_compiler.local_court import (
    CourtCandidate, bind_selected_proof, compare_in_local_court,
)
from vice_compiler.macro_ir import (
    MacroCandidate, MacroCertificates, MacroKind, ResourceEstimate,
    SceneProgram, ScoreBounds,
)
from vice_compiler.macro_extractor import _proof_admissible
from vice_compiler.production_court import _paint_canvas_background
from vice_compiler.renderer_posterior import (
    ModelLikelihood, summarize_pairwise_render_evidence,
    synthetic_renderer_posterior,
)


class CourtPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.posterior = synthetic_renderer_posterior(source_id="court-unit")
        self.atlas = ExactRoiAtlas()

    def test_fixed_posterior_is_sealed_and_bounded(self) -> None:
        self.posterior.validate()
        self.assertEqual(len(self.posterior.models), 2)
        self.assertEqual(len(self.posterior.digest), 64)
        self.assertAlmostEqual(
            sum(model.weight for model in self.posterior.models), 1.0
        )
        damaged = replace(self.posterior, digest="0" * 64)
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            damaged.validate()

    def test_render_lcb_conditions_only_on_fixed_fallback_evidence(self) -> None:
        first, second = self.posterior.models
        candidate_likes = (
            ModelLikelihood(first.id, -100.0, 1.0, 64),
            ModelLikelihood(second.id, -600.0, 3.0, 64),
        )
        fallback_likes = (
            ModelLikelihood(first.id, -220.0, 2.0, 64),
            ModelLikelihood(second.id, -250.0, 2.5, 64),
        )
        summary = summarize_pairwise_render_evidence(
            self.posterior, candidate_likes, fallback_likes,
            confidence_z=1.96,
        )
        # The second renderer makes the common fallback about exp(-30) less
        # likely.  It cannot dominate the pairwise LCB merely because its
        # candidate delta is poor: q_F is frozen from F before H is inspected.
        self.assertGreater(dict(summary.reference_model_weights)[first.id], 0.999999)
        self.assertGreater(summary.conservative_lower_bound, 100.0)
        self.assertLessEqual(
            summary.conservative_lower_bound,
            summary.marginal_log_bayes_factor + 1e-9,
        )

    def test_render_lcb_fails_closed_when_reference_renderer_is_ambiguous(self) -> None:
        first, second = self.posterior.models
        fallback_likes = (
            ModelLikelihood(first.id, -100.0, 2.0, 64),
            ModelLikelihood(second.id, -100.0, 2.0, 64),
        )
        candidate_likes = (
            ModelLikelihood(first.id, 0.0, 1.0, 64),
            ModelLikelihood(second.id, -200.0, 4.0, 64),
        )
        summary = summarize_pairwise_render_evidence(
            self.posterior, candidate_likes, fallback_likes,
            confidence_z=1.96,
        )
        self.assertLess(summary.conservative_lower_bound, 0.0)
        self.assertAlmostEqual(
            dict(summary.reference_model_weights)[first.id], first.weight,
        )

    def test_roi_atlas_reports_exact_physical_budget(self) -> None:
        first = RoiRenderRequest(
            id="first", roi_xyxy=(2, 3, 10, 11), kind="rect",
            parameters=(("cx", 6.0), ("cy", 7.0),
                        ("width", 6.0), ("height", 6.0)),
            supersample=4,
        )
        second = replace(first, id="second", supersample=2)
        result = self.atlas.render((first, second), canvas_size=(16, 16))
        self.assertEqual(result.exact_render_pixels, 2 * 8 * 8)
        self.assertEqual(result.supersampled_pixels, 8 * 8 * (16 + 4))
        self.assertEqual(set(result.by_id()), {"first", "second"})
        self.assertFalse(result.atlas_premultiplied_linear_rgba.flags.writeable)

    def test_roi_atlas_accepts_exact_delivered_raster_patch(self) -> None:
        patch = np.zeros((5, 7, 4), np.float32)
        patch[..., 0] = 0.25
        patch[..., 3] = 0.5
        patch.setflags(write=False)
        request = RoiRenderRequest(
            id="delivered", roi_xyxy=(3, 4, 10, 9), kind="raster",
            raster_premultiplied_linear_rgba=patch, supersample=4,
        )
        result = self.atlas.render((request,), canvas_size=(16, 16))
        np.testing.assert_array_equal(result.by_id()["delivered"], patch)
        self.assertEqual(result.exact_render_pixels, 35)
        with self.assertRaisesRegex(ValueError, "raster.*patch"):
            replace(
                request, roi_xyxy=(3, 4, 11, 9),
            ).validate((16, 16))

    def test_replacement_cut_paints_canvas_background_not_transparency(self) -> None:
        incumbent = np.zeros((3, 4, 4), np.float32)
        incumbent[..., 0] = 0.20
        incumbent[..., 3] = 1.0
        owned = np.zeros((3, 4), bool)
        owned[1, 1:3] = True
        opaque_white = np.ones(4, np.float32)
        cleared = _paint_canvas_background(incumbent, owned, opaque_white)
        np.testing.assert_array_equal(cleared[1, 1:3], np.ones((2, 4)))
        np.testing.assert_array_equal(cleared[~owned], incumbent[~owned])

        translucent = np.asarray((0.0, 0.0, 0.0, 0.5), np.float32)
        blended = _paint_canvas_background(incumbent, owned, translucent)
        np.testing.assert_allclose(blended[1, 1:3, 0], 0.10)
        np.testing.assert_allclose(blended[1, 1:3, 3], 1.0)

    def test_topology_and_canvas_eraser_are_hard_certificates(self) -> None:
        ring = np.zeros((32, 32), np.uint8)
        cv2.circle(ring, (16, 16), 10, 1, -1)
        cv2.circle(ring, (16, 16), 4, 0, -1)
        good = build_topology_certificate(
            ring, expected_components=1, expected_holes=1,
            hard_requirement=True,
        )
        bad = build_topology_certificate(
            ring, expected_components=1, expected_holes=0,
            hard_requirement=True,
        )
        self.assertTrue(good.valid)
        self.assertFalse(bad.valid)
        eraser = build_validity_certificate(
            kind="eraser", parameters=(), roi_xyxy=(0, 0, 32, 32),
            canvas_size=(32, 32),
        )
        self.assertFalse(eraser.valid)
        self.assertIn("no-canvas-residual-eraser", eraser.violations)

    def test_geometry_certificate_uses_finite_sdf_bound(self) -> None:
        evidence = np.zeros((32, 32), np.uint8)
        rendered = np.zeros((32, 32), np.float32)
        cv2.circle(evidence, (16, 16), 8, 1, -1)
        cv2.circle(rendered, (17, 16), 8, 1.0, -1)
        claimed = cv2.dilate(
            (evidence | (rendered >= 0.5)).astype(np.uint8),
            np.ones((5, 5), np.uint8),
        ).astype(bool)
        certificate = build_geometry_certificate(
            evidence, rendered, claimed, tolerance_px=2.0
        )
        self.assertTrue(certificate.valid)
        self.assertTrue(math.isfinite(certificate.sdf_lower_bound))
        self.assertGreater(certificate.sdf_lower_bound, 0.0)

    def test_court_selects_ideal_circle_and_binds_sealed_proof(self) -> None:
        case = _make_pair(
            "ideal_circle_vs_jagged_overfit", 2,
            self.posterior, self.atlas,
        )
        correct = replace(case.correct, core_bits=1)
        competitor = replace(case.competitor, core_bits=1)
        decision = compare_in_local_court(
            case.observed, case.evidence_support, correct, competitor,
            self.posterior, atlas=self.atlas,
        )
        self.assertTrue(decision.candidate_selected)
        self.assertEqual(decision.selected_id, correct.id)
        self.assertEqual(decision.posterior_digest, self.posterior.digest)
        self.assertEqual(
            decision.candidate_bundle.render_evidence.posterior_digest,
            decision.fallback_bundle.render_evidence.posterior_digest,
        )
        decision.candidate_bundle.validate()
        macro = MacroCandidate(
            id=correct.id, registry_index=0, kind=MacroKind.SHAPE,
            family="shape", roi_xyxy=(0, 0, 64, 64), core_bits=1,
            alpha_bounds=(1.0, 1.0),
            boundary_interfaces=(), soft_evidence=(), hidden_geometry=None,
            program=SceneProgram("Circle"), continuous_params=(),
            covariance=(), certificates=MacroCertificates(
                valid=True, support_source="unit", support_size=(64, 64)
            ), conflict_bits=0, prerequisite_claims=(),
            score_bounds=ScoreBounds(0.0, 1.0, 2.0),
            resource_estimate=ResourceEstimate(0.0, 4096, 128, 1),
            provenance=("unit",),
        )
        certified = bind_selected_proof(macro, decision)
        self.assertTrue(certified.is_proof_carrying)
        certified.validate(leaf_count=1, interface_count=0, candidate_count=1)
        self.assertTrue(_proof_admissible(certified, True))
        self.assertFalse(_proof_admissible(replace(
            certified, prerequisite_claims=("unknown-factor-claim",),
        ), True))

    def test_exact_tie_returns_fallback(self) -> None:
        request_a = RoiRenderRequest(
            id="candidate-render", roi_xyxy=(0, 0, 32, 32),
            kind="circle", parameters=(("cx", 16.0), ("cy", 16.0),
                                       ("radius", 8.0)),
        )
        request_b = replace(request_a, id="fallback-render")
        crops = self.atlas.render(
            (request_a, request_b), canvas_size=(32, 32)
        ).by_id()
        observed = crops[request_a.id]
        evidence = observed[..., 3] >= 0.5
        claim = cv2.dilate(
            (observed[..., 3] > 1e-5).astype(np.uint8),
            np.ones((3, 3), np.uint8),
        ).astype(bool)
        candidate = CourtCandidate("candidate", request_a, claim)
        fallback = CourtCandidate("fallback", request_b, claim)
        decision = compare_in_local_court(
            observed, evidence, candidate, fallback, self.posterior,
            atlas=self.atlas,
        )
        self.assertFalse(decision.candidate_selected)
        self.assertEqual(decision.selected_id, "fallback")
        self.assertEqual(decision.reason, "tie-without-preference-model-fallback")
        self.assertEqual(
            [stage for stage, _value in decision.cascade],
            [
                "color-mass-lower-bound", "sdf-interval-bound", "topology",
                "approximate-analytic-render", "exact-batched-roi-render",
                "expensive-perceptual-tiebreak",
            ],
        )
        self.assertGreater(decision.approximate_render_pixels, 0)
        preferred = compare_in_local_court(
            observed, evidence, candidate, fallback, self.posterior,
            atlas=self.atlas,
            preference_tiebreaker=lambda *_args: 0.75,
        )
        self.assertTrue(preferred.candidate_selected)
        self.assertEqual(
            preferred.reason, "learned-preference-tiebreak-candidate"
        )
        self.assertEqual(preferred.preference_tiebreak_score, 0.75)

    def test_color_mass_proof_prunes_robust_outlier_overfit(self) -> None:
        observed = np.zeros((32, 32, 4), np.float32)
        observed[..., 3] = 1.0
        # H fits 93.75% of pixels exactly but spends impossible red mass on a
        # small block.  A robust Student-t likelihood can prefer those many
        # exact pixels; the triangle-inequality mass bound nevertheless proves
        # H has more L1 error than the measured fallback.
        overfit = observed.copy()
        overfit[:2, :, 0] = 0.8
        fallback_render = observed.copy()
        fallback_render[..., 0] = 0.02
        overfit.setflags(write=False)
        fallback_render.setflags(write=False)
        candidate_request = RoiRenderRequest(
            id="outlier-overfit-render", roi_xyxy=(0, 0, 32, 32),
            kind="raster", raster_premultiplied_linear_rgba=overfit,
        )
        fallback_request = RoiRenderRequest(
            id="bounded-fallback-render", roi_xyxy=(0, 0, 32, 32),
            kind="raster", raster_premultiplied_linear_rgba=fallback_render,
        )
        support = np.ones((32, 32), bool)
        candidate = CourtCandidate(
            "outlier-overfit", candidate_request, support,
            boundary_tolerance_px=2.0,
        )
        fallback = CourtCandidate(
            "bounded-fallback", fallback_request, support,
            boundary_tolerance_px=2.0,
        )
        decision = compare_in_local_court(
            observed, support, candidate, fallback, self.posterior,
            atlas=self.atlas,
        )
        self.assertFalse(decision.candidate_selected)
        self.assertEqual(
            decision.reason, "candidate-color-mass-bound-dominated"
        )
        self.assertTrue(decision.cascade_pruned_before_exact)
        self.assertEqual(decision.exact_render_pixels, 0)
        self.assertEqual(
            dict(decision.cascade)["exact-batched-roi-render"],
            "pruned-color-mass-dominance",
        )
        components = dict(
            decision.candidate_bundle.render_evidence.score_components
        )
        self.assertGreater(
            components["candidate_posterior_color_mass_lower_bound"],
            components["fallback_posterior_pixel_l1"],
        )

    def test_invalid_candidate_is_pruned_before_exact_atlas(self) -> None:
        fallback_request = RoiRenderRequest(
            id="valid-fallback-render", roi_xyxy=(0, 0, 32, 32),
            kind="circle", parameters=(("cx", 16.0), ("cy", 16.0),
                                       ("radius", 8.0)),
        )
        eraser_request = RoiRenderRequest(
            id="invalid-eraser-render", roi_xyxy=(0, 0, 32, 32),
            kind="eraser", support_mask=np.ones((32, 32), bool),
        )
        observed = self.atlas.render(
            (fallback_request,), canvas_size=(32, 32)
        ).by_id()[fallback_request.id]
        evidence = observed[..., 3] >= 0.5
        claim = np.ones((32, 32), bool)
        candidate = CourtCandidate("invalid-eraser", eraser_request, claim)
        fallback = CourtCandidate(
            "valid-fallback", fallback_request, claim,
            boundary_tolerance_px=16.0,
        )
        decision = compare_in_local_court(
            observed, evidence, candidate, fallback, self.posterior,
            atlas=self.atlas,
        )
        self.assertFalse(decision.candidate_selected)
        self.assertTrue(decision.cascade_pruned_before_exact)
        self.assertEqual(decision.exact_render_pixels, 0)
        self.assertGreater(decision.approximate_render_pixels, 0)
        self.assertEqual(
            dict(decision.cascade)["exact-batched-roi-render"],
            "pruned-certificate-reject",
        )


if __name__ == "__main__":
    unittest.main()

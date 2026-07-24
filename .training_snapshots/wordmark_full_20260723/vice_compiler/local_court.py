"""Fixed-posterior proof-carrying local court for phase 3."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Callable

import numpy as np

from .atlas_renderer import ExactRoiAtlas, RoiRenderRequest
from .certificates import (
    CertificateBundle, RenderEvidenceCertificate, SCHEMA as CERT_SCHEMA,
    build_complexity_certificate, build_geometry_certificate,
    build_resource_certificate, build_structural_certificate,
    build_support_certificate, build_topology_certificate,
    build_validity_certificate, seal_bundle,
)
from .renderer_posterior import (
    FixedRendererPosterior, ModelLikelihood, apply_formation,
    score_log_likelihood,
    summarize_pairwise_render_evidence,
)
from .macro_ir import MacroCandidate


@dataclass(frozen=True)
class CourtWeights:
    lambda_mdl: float = 0.16
    lambda_struct: float = 0.28
    lambda_risk: float = 0.24
    confidence_z: float = 1.96
    probability_temperature: float = 0.08
    preference_tie_epsilon: float = 1e-9

    def validate(self) -> None:
        values = (
            self.lambda_mdl, self.lambda_struct, self.lambda_risk,
            self.confidence_z, self.probability_temperature,
            self.preference_tie_epsilon,
        )
        if not all(math.isfinite(value) and value >= 0.0 for value in values):
            raise ValueError("invalid court weights")
        if self.probability_temperature <= 0.0:
            raise ValueError("court temperature must be positive")


@dataclass(frozen=True)
class CourtCandidate:
    id: str
    request: RoiRenderRequest
    claimed_support: np.ndarray
    # The paired render may contain the surrounding incumbent scene.  Proofs
    # must nevertheless describe the delivered macro geometry itself, not the
    # alpha topology of that complete scene crop.
    certificate_alpha_mask: np.ndarray | None = None
    expected_components: int | None = None
    expected_holes: int | None = None
    hard_topology: bool = False
    persistent_topology_evidence: bool = True
    boundary_tolerance_px: float = 2.0
    structural_claims: tuple[tuple[str, float], ...] = ()
    risk: float = 0.0
    exception_count: int = 0
    group_savings_bits: float = 0.0
    editability_cost_bits: float = 0.0
    parameter_condition_number: float = 1.0
    legal_paths: bool = True
    no_self_intersections: bool = True
    legal_loops: bool = True
    holes_contained: bool = True
    layer_order_acyclic: bool = True
    hidden_geometry_bounded: bool = True
    core_bits: int = 0
    interface_ids: tuple[int, ...] = ()
    provenance: tuple[str, ...] = ()

    def validate(self, canvas_size: tuple[int, int]) -> None:
        if not self.id:
            raise ValueError("court candidate id is empty")
        self.request.validate(canvas_size)
        width, height = canvas_size
        if np.asarray(self.claimed_support).shape != (height, width):
            raise ValueError("court claimed support must be canvas-sized")
        if not np.any(self.claimed_support):
            raise ValueError("court candidate has empty claimed support")
        if self.certificate_alpha_mask is not None:
            proof_mask = np.asarray(self.certificate_alpha_mask)
            if proof_mask.shape != (height, width):
                raise ValueError("court certificate alpha mask must be canvas-sized")
            if not np.any(proof_mask):
                raise ValueError("court certificate alpha mask is empty")
        if not math.isfinite(self.risk) or self.risk < 0.0:
            raise ValueError("court candidate risk must be finite/nonnegative")


@dataclass(frozen=True)
class CourtDecision:
    selected_id: str
    fallback_id: str
    candidate_id: str
    candidate_selected: bool
    candidate_score: float
    fallback_score: float
    calibrated_candidate_probability: float
    reason: str
    stages: tuple[tuple[str, str], ...]
    candidate_bundle: CertificateBundle
    fallback_bundle: CertificateBundle
    posterior_digest: str
    exact_render_pixels: int
    approximate_render_pixels: int = 0
    cascade_pruned_before_exact: bool = False
    cascade: tuple[tuple[str, str], ...] = ()
    preference_tiebreak_score: float | None = None


PreferenceTiebreaker = Callable[[
    np.ndarray, np.ndarray, np.ndarray, CertificateBundle, CertificateBundle,
], float]


def bind_selected_proof(
    candidate: MacroCandidate, decision: CourtDecision
) -> MacroCandidate:
    """Admit only the winning candidate's sealed court proof into CMIR."""
    if not decision.candidate_selected or decision.selected_id != candidate.id:
        raise ValueError("court did not select this CMIR candidate")
    if decision.candidate_bundle.candidate_id != candidate.id:
        raise ValueError("court proof/candidate identity mismatch")
    return candidate.with_proof_bundle(decision.candidate_bundle)


def _structural_map(candidate: CourtCandidate) -> dict[str, float]:
    return {name: float(value) for name, value in candidate.structural_claims}


def _render_certificate(
    posterior: FixedRendererPosterior,
    candidate_likelihoods: tuple[ModelLikelihood, ...],
    fallback_likelihoods: tuple[ModelLikelihood, ...],
    *, exact_pixels: int, confidence_z: float,
    components: tuple[tuple[str, float], ...],
) -> RenderEvidenceCertificate:
    summary = summarize_pairwise_render_evidence(
        posterior, candidate_likelihoods, fallback_likelihoods,
        confidence_z=confidence_z,
    )
    effective_models = 1.0 / max(
        1e-12,
        sum(weight * weight for _model_id, weight in summary.reference_model_weights),
    )
    audit_components = (
        *components,
        ("marginal_log_bayes_factor", summary.marginal_log_bayes_factor),
        ("reference_posterior_effective_models", effective_models),
        *tuple(
            (f"reference_weight:{model_id}", weight)
            for model_id, weight in summary.reference_model_weights
        ),
    )
    certificate = RenderEvidenceCertificate(
        valid=True, posterior_digest=posterior.digest,
        posterior_mean_delta_logp=summary.posterior_mean_delta_logp,
        posterior_variance=summary.posterior_variance,
        conservative_lower_bound=summary.conservative_lower_bound,
        model_deltas=summary.model_deltas,
        score_components=audit_components,
        exact_rendered_pixel_budget=int(exact_pixels),
    )
    certificate.validate()
    return certificate


def _likelihood_deltas(
    observed_crop: np.ndarray, candidate_crop: np.ndarray,
    fallback_crop: np.ndarray, score_support: np.ndarray,
    posterior: FixedRendererPosterior,
) -> tuple[tuple[ModelLikelihood, ...], tuple[ModelLikelihood, ...]]:
    candidate_likelihoods: list[ModelLikelihood] = []
    fallback_likelihoods: list[ModelLikelihood] = []
    for model in posterior.models:
        candidate_like = score_log_likelihood(
            observed_crop, candidate_crop, model, support=score_support
        )
        fallback_like = score_log_likelihood(
            observed_crop, fallback_crop, model, support=score_support
        )
        candidate_likelihoods.append(candidate_like)
        fallback_likelihoods.append(fallback_like)
    return tuple(candidate_likelihoods), tuple(fallback_likelihoods)


def _color_mass_l1_lower_bound(
    observed: np.ndarray, rendered: np.ndarray, support: np.ndarray
) -> float:
    """Triangle-inequality lower bound on per-pixel RGBA L1 residual."""
    values = np.asarray(observed, np.float64)[support]
    prediction = np.asarray(rendered, np.float64)[support]
    if not len(values):
        return 0.0
    channel_mass_residual = np.abs(np.sum(values - prediction, axis=0))
    return float(np.sum(channel_mass_residual) / len(values))


@dataclass(frozen=True)
class _PhysicalRenderResiduals:
    """Renderer-conditioned physical checks that cannot be won by a score.

    The color-mass quantity is a triangle-inequality lower bound on the true
    RGBA L1 residual.  Consequently, when a candidate's lower bound is above
    the fallback's measured residual, the candidate is *provably* worse in
    physical color mass under the same fallback-conditioned renderer state.
    This is a hard cheap-cascade result, not a tunable preference threshold.
    """

    candidate_pixel_l1: float
    fallback_pixel_l1: float
    candidate_color_mass_lower_bound: float
    fallback_color_mass_lower_bound: float

    @property
    def candidate_definitely_dominated(self) -> bool:
        tolerance = 1e-8 * max(
            1.0, self.candidate_color_mass_lower_bound,
            self.fallback_pixel_l1,
        )
        return (
            self.candidate_color_mass_lower_bound
            > self.fallback_pixel_l1 + tolerance
        )


def _posterior_physical_residuals(
    observed: np.ndarray,
    candidate: np.ndarray,
    fallback: np.ndarray,
    support: np.ndarray,
    posterior: FixedRendererPosterior,
    candidate_likelihoods: tuple[ModelLikelihood, ...],
    fallback_likelihoods: tuple[ModelLikelihood, ...],
) -> _PhysicalRenderResiduals:
    """Measure L1 and its color-mass bound under one fixed renderer state.

    Weights are the candidate-independent ``q_F`` reference weights used by
    the render Bayes factor.  Measuring the unformed vector patch here would
    make the cheap bound disagree merely because the source contains blur,
    JPEG or a subpixel phase; conditioning both checks on the same renderer
    removes that calibration error.
    """
    pairwise = summarize_pairwise_render_evidence(
        posterior, candidate_likelihoods, fallback_likelihoods,
        confidence_z=0.0,
    )
    reference_weights = dict(pairwise.reference_model_weights)
    count = int(np.count_nonzero(support))
    if count <= 0:
        return _PhysicalRenderResiduals(0.0, 0.0, 0.0, 0.0)
    candidate_l1 = 0.0
    fallback_l1 = 0.0
    candidate_mass = 0.0
    fallback_mass = 0.0
    for model in posterior.models:
        weight = float(reference_weights[model.id])
        formed_candidate = apply_formation(candidate, model)
        formed_fallback = apply_formation(fallback, model)
        candidate_values = np.asarray(observed - formed_candidate, np.float64)[support]
        fallback_values = np.asarray(observed - formed_fallback, np.float64)[support]
        candidate_l1 += weight * float(np.sum(np.abs(candidate_values)) / count)
        fallback_l1 += weight * float(np.sum(np.abs(fallback_values)) / count)
        candidate_mass += weight * float(
            np.sum(np.abs(np.sum(candidate_values, axis=0))) / count
        )
        fallback_mass += weight * float(
            np.sum(np.abs(np.sum(fallback_values, axis=0))) / count
        )
    return _PhysicalRenderResiduals(
        candidate_pixel_l1=float(candidate_l1),
        fallback_pixel_l1=float(fallback_l1),
        candidate_color_mass_lower_bound=float(candidate_mass),
        fallback_color_mass_lower_bound=float(fallback_mass),
    )


def _candidate_bundle(
    candidate: CourtCandidate, *, rendered_crop: np.ndarray,
    evidence_support: np.ndarray, posterior: FixedRendererPosterior,
    render_certificate: RenderEvidenceCertificate,
    canvas_size: tuple[int, int], exact_pixels: int,
) -> CertificateBundle:
    width, height = canvas_size
    x1, y1, x2, y2 = candidate.request.roi_xyxy
    if candidate.certificate_alpha_mask is None:
        full_alpha = np.zeros((height, width), np.float32)
        full_alpha[y1:y2, x1:x2] = rendered_crop[..., 3]
    else:
        full_alpha = np.asarray(
            candidate.certificate_alpha_mask, np.float32,
        )
    claimed = np.asarray(candidate.claimed_support, bool)
    validity = build_validity_certificate(
        kind=candidate.request.kind,
        parameters=candidate.request.parameters,
        roi_xyxy=candidate.request.roi_xyxy, canvas_size=canvas_size,
        legal_paths=candidate.legal_paths,
        no_self_intersections=candidate.no_self_intersections,
        legal_loops=candidate.legal_loops,
        holes_contained=candidate.holes_contained,
        layer_order_acyclic=candidate.layer_order_acyclic,
        hidden_geometry_bounded=candidate.hidden_geometry_bounded,
    )
    support = build_support_certificate(
        claimed, roi_xyxy=candidate.request.roi_xyxy,
        scored_mask=claimed, core_bits=candidate.core_bits,
        interface_ids=candidate.interface_ids,
        provenance=(*candidate.provenance, "court-claimed-support"),
    )
    topology = build_topology_certificate(
        full_alpha >= 0.5,
        expected_components=candidate.expected_components,
        expected_holes=candidate.expected_holes,
        hard_requirement=candidate.hard_topology,
        persistent_evidence_matched=candidate.persistent_topology_evidence,
    )
    geometry = build_geometry_certificate(
        evidence_support, full_alpha, claimed,
        tolerance_px=candidate.boundary_tolerance_px,
        parameter_condition_number=candidate.parameter_condition_number,
    )
    structural_values = _structural_map(candidate)
    structural = build_structural_certificate(
        text_line=structural_values.get("text_line", 0.0),
        repeated_glyph=structural_values.get("repeated_glyph", 0.0),
        symmetry=structural_values.get("symmetry", 0.0),
        equal_radius=structural_values.get("equal_radius", 0.0),
        stroke_width=structural_values.get("stroke_width", 0.0),
        layer_order=structural_values.get("layer_order", 0.0),
        semantic_confidence=structural_values.get("semantic_confidence", 0.0),
    )
    complexity = build_complexity_certificate(
        parameter_count=sum(
            isinstance(value, (float, int))
            for _name, value in candidate.request.parameters
        ),
        exception_count=candidate.exception_count,
        components=topology.components, holes=topology.holes,
        layers=1, group_savings_bits=candidate.group_savings_bits,
        editability_cost_bits=candidate.editability_cost_bits,
    )
    resource = build_resource_certificate(
        fitting_ms=0.0, render_pixels=exact_pixels,
        memory_bytes=int(rendered_crop.nbytes), solver_variables=1,
    )
    bundle = CertificateBundle(
        schema=CERT_SCHEMA, candidate_id=candidate.id,
        validity=validity, support=support, topology=topology,
        geometry=geometry, render_evidence=render_certificate,
        structural=structural, complexity=complexity, resource=resource,
        digest="",
        provenance=(*candidate.provenance, "fixed-posterior-local-court/v1"),
    )
    return seal_bundle(bundle)


def compare_in_local_court(
    observed_premultiplied_linear_rgba: np.ndarray,
    evidence_support: np.ndarray,
    candidate: CourtCandidate,
    fallback: CourtCandidate,
    posterior: FixedRendererPosterior,
    *, weights: CourtWeights | None = None,
    atlas: ExactRoiAtlas | None = None,
    preference_tiebreaker: PreferenceTiebreaker | None = None,
) -> CourtDecision:
    """Court a candidate through the bounded cheap-to-expensive cascade."""
    weights = weights or CourtWeights()
    weights.validate(); posterior.validate()
    observed = np.asarray(observed_premultiplied_linear_rgba, np.float32)
    if observed.ndim != 3 or observed.shape[2] != 4:
        raise ValueError("court observation must be HxWx4")
    canvas_size = (observed.shape[1], observed.shape[0])
    candidate.validate(canvas_size); fallback.validate(canvas_size)
    evidence = np.asarray(evidence_support, bool)
    if evidence.shape != observed.shape[:2]:
        raise ValueError("court evidence support shape mismatch")
    if candidate.request.roi_xyxy != fallback.request.roi_xyxy:
        raise ValueError("phase-3 pair court requires a shared exact ROI")
    x1, y1, x2, y2 = candidate.request.roi_xyxy
    observed_crop = observed[y1:y2, x1:x2]
    score_support = np.asarray(candidate.claimed_support, bool)[y1:y2, x1:x2]
    if not np.any(score_support):
        raise ValueError("court candidate has no claimed pixels inside ROI")

    atlas_renderer = atlas or ExactRoiAtlas()
    approximate_result = atlas_renderer.render((
        replace(candidate.request, supersample=1),
        replace(fallback.request, supersample=1),
    ), canvas_size=canvas_size)
    approximate_crops = approximate_result.by_id()
    approximate_candidate = approximate_crops[candidate.request.id]
    approximate_fallback = approximate_crops[fallback.request.id]
    approximate_candidate_likes, approximate_fallback_likes = (
        _likelihood_deltas(
            observed_crop, approximate_candidate, approximate_fallback,
            score_support, posterior,
        )
    )
    approximate_physical = _posterior_physical_residuals(
        observed_crop, approximate_candidate, approximate_fallback,
        score_support, posterior,
        approximate_candidate_likes, approximate_fallback_likes,
    )
    approximate_pixels_each = approximate_result.exact_render_pixels // 2
    approximate_render_certificate = _render_certificate(
        posterior, approximate_candidate_likes, approximate_fallback_likes,
        exact_pixels=approximate_pixels_each,
        confidence_z=weights.confidence_z,
        components=(
            ("candidate_mean_robust_nll",
             float(np.mean(tuple(
                 row.mean_robust_nll for row in approximate_candidate_likes
             )))),
            ("fallback_mean_robust_nll",
             float(np.mean(tuple(
                 row.mean_robust_nll for row in approximate_fallback_likes
             )))),
            ("candidate_posterior_pixel_l1",
             approximate_physical.candidate_pixel_l1),
            ("fallback_posterior_pixel_l1",
             approximate_physical.fallback_pixel_l1),
            ("candidate_posterior_color_mass_lower_bound",
             approximate_physical.candidate_color_mass_lower_bound),
            ("fallback_posterior_color_mass_lower_bound",
             approximate_physical.fallback_color_mass_lower_bound),
            ("analytic_supersample", 1.0),
        ),
    )
    approximate_fallback_certificate = _render_certificate(
        posterior, approximate_fallback_likes, approximate_fallback_likes,
        exact_pixels=approximate_pixels_each,
        confidence_z=weights.confidence_z,
        components=(("fallback_self_delta", 0.0),
                    ("analytic_supersample", 1.0)),
    )
    approximate_candidate_bundle = _candidate_bundle(
        candidate, rendered_crop=approximate_candidate,
        evidence_support=evidence, posterior=posterior,
        render_certificate=approximate_render_certificate,
        canvas_size=canvas_size, exact_pixels=approximate_pixels_each,
    )
    approximate_fallback_bundle = _candidate_bundle(
        fallback, rendered_crop=approximate_fallback,
        evidence_support=evidence, posterior=posterior,
        render_certificate=approximate_fallback_certificate,
        canvas_size=canvas_size, exact_pixels=approximate_pixels_each,
    )
    approximate_render_gain = (
        approximate_candidate_bundle.render_evidence.conservative_lower_bound
        / max(1, approximate_candidate_bundle.support.scored_pixels)
    )
    cascade: list[tuple[str, str]] = [
        ("color-mass-lower-bound",
         f"candidate_lb={approximate_physical.candidate_color_mass_lower_bound:.9g};"
         f"candidate_l1={approximate_physical.candidate_pixel_l1:.9g};"
         f"fallback_lb={approximate_physical.fallback_color_mass_lower_bound:.9g};"
         f"fallback_l1={approximate_physical.fallback_pixel_l1:.9g}"),
        ("sdf-interval-bound",
         "pass" if approximate_candidate_bundle.geometry.valid else "reject"),
        ("topology",
         "pass" if approximate_candidate_bundle.topology.valid else "reject"),
        ("approximate-analytic-render",
         f"lcb/pixel={approximate_render_gain:.9g}"),
    ]
    if not approximate_candidate_bundle.valid:
        cascade.extend((
            ("exact-batched-roi-render", "pruned-certificate-reject"),
            ("expensive-perceptual-tiebreak", "skipped"),
        ))
        stages = (
            ("validity", "pass" if approximate_candidate_bundle.validity.valid else "reject"),
            ("hard-topology", "pass" if approximate_candidate_bundle.topology.valid else "reject"),
            ("support+geometry", "pass" if (
                approximate_candidate_bundle.support.valid
                and approximate_candidate_bundle.geometry.valid
            ) else "reject"),
            ("render-bayes-factor", "skipped-certificate-reject"),
            ("structural-group-prior", "skipped-certificate-reject"),
            ("mdl-editability", "skipped-certificate-reject"),
            ("learned-preference-tiebreak", "skipped-certificate-reject"),
            ("tie-policy", "fallback"),
        )
        return CourtDecision(
            selected_id=fallback.id, fallback_id=fallback.id,
            candidate_id=candidate.id, candidate_selected=False,
            candidate_score=-1.0e12, fallback_score=0.0,
            calibrated_candidate_probability=0.0,
            reason="candidate-certificate-rejected-before-exact-render",
            stages=stages, candidate_bundle=approximate_candidate_bundle,
            fallback_bundle=approximate_fallback_bundle,
            posterior_digest=posterior.digest, exact_render_pixels=0,
            approximate_render_pixels=approximate_result.exact_render_pixels,
            cascade_pruned_before_exact=True, cascade=tuple(cascade),
            preference_tiebreak_score=None,
        )

    if approximate_physical.candidate_definitely_dominated:
        cascade.extend((
            ("exact-batched-roi-render", "pruned-color-mass-dominance"),
            ("expensive-perceptual-tiebreak", "skipped"),
        ))
        stages = (
            ("validity", "pass"),
            ("hard-topology", "pass"),
            ("support+geometry", "pass"),
            ("render-bayes-factor", "reject-physical-color-mass-bound"),
            ("structural-group-prior", "skipped-physical-dominance"),
            ("mdl-editability", "skipped-physical-dominance"),
            ("learned-preference-tiebreak", "skipped-physical-dominance"),
            ("tie-policy", "fallback"),
        )
        return CourtDecision(
            selected_id=fallback.id, fallback_id=fallback.id,
            candidate_id=candidate.id, candidate_selected=False,
            candidate_score=-1.0e12, fallback_score=0.0,
            calibrated_candidate_probability=0.0,
            reason="candidate-color-mass-bound-dominated",
            stages=stages, candidate_bundle=approximate_candidate_bundle,
            fallback_bundle=approximate_fallback_bundle,
            posterior_digest=posterior.digest, exact_render_pixels=0,
            approximate_render_pixels=approximate_result.exact_render_pixels,
            cascade_pruned_before_exact=True, cascade=tuple(cascade),
            preference_tiebreak_score=None,
        )

    raster_exact_reuse = (
        candidate.request.kind == "raster"
        and fallback.request.kind == "raster"
    )
    if raster_exact_reuse:
        # Raster requests already carry the exact deterministic delivery
        # patch.  Supersampling cannot change those bytes, so a second atlas
        # render and a second posterior likelihood pass would be pure work
        # duplication rather than a stronger certificate.
        atlas_result = approximate_result
        candidate_crop = approximate_candidate
        fallback_crop = approximate_fallback
        candidate_likes = approximate_candidate_likes
        fallback_likes = approximate_fallback_likes
        exact_physical = approximate_physical
    else:
        atlas_result = atlas_renderer.render(
            (candidate.request, fallback.request), canvas_size=canvas_size
        )
        crops = atlas_result.by_id()
        candidate_crop = crops[candidate.request.id]
        fallback_crop = crops[fallback.request.id]
        candidate_likes, fallback_likes = _likelihood_deltas(
            observed_crop, candidate_crop, fallback_crop,
            score_support, posterior,
        )
        exact_physical = _posterior_physical_residuals(
            observed_crop, candidate_crop, fallback_crop,
            score_support, posterior, candidate_likes, fallback_likes,
        )
    exact_pixels_each = atlas_result.exact_render_pixels // 2
    if raster_exact_reuse:
        render_certificate = approximate_render_certificate
        fallback_render_certificate = approximate_fallback_certificate
        candidate_bundle = approximate_candidate_bundle
        fallback_bundle = approximate_fallback_bundle
        cascade.append((
            "exact-batched-roi-render", "pass:raster-exact-reuse",
        ))
    else:
        render_certificate = _render_certificate(
            posterior, candidate_likes, fallback_likes,
            exact_pixels=exact_pixels_each,
            confidence_z=weights.confidence_z,
            components=(
                ("candidate_mean_robust_nll", float(np.mean(tuple(
                    row.mean_robust_nll for row in candidate_likes
                )))),
                ("fallback_mean_robust_nll", float(np.mean(tuple(
                    row.mean_robust_nll for row in fallback_likes
                )))),
                ("candidate_posterior_pixel_l1",
                 exact_physical.candidate_pixel_l1),
                ("fallback_posterior_pixel_l1",
                 exact_physical.fallback_pixel_l1),
                ("candidate_posterior_color_mass_lower_bound",
                 exact_physical.candidate_color_mass_lower_bound),
                ("fallback_posterior_color_mass_lower_bound",
                 exact_physical.fallback_color_mass_lower_bound),
            ),
        )
        fallback_render_certificate = _render_certificate(
            posterior, fallback_likes, fallback_likes,
            exact_pixels=exact_pixels_each, confidence_z=weights.confidence_z,
            components=(("fallback_self_delta", 0.0),),
        )
        candidate_bundle = _candidate_bundle(
            candidate, rendered_crop=candidate_crop,
            evidence_support=evidence, posterior=posterior,
            render_certificate=render_certificate, canvas_size=canvas_size,
            exact_pixels=exact_pixels_each,
        )
        fallback_bundle = _candidate_bundle(
            fallback, rendered_crop=fallback_crop,
            evidence_support=evidence, posterior=posterior,
            render_certificate=fallback_render_certificate,
            canvas_size=canvas_size, exact_pixels=exact_pixels_each,
        )
        cascade.append((
            "exact-batched-roi-render",
            "reject-color-mass-dominance"
            if exact_physical.candidate_definitely_dominated else "pass",
        ))
    stages: list[tuple[str, str]] = []
    stages.append(("validity", "pass" if candidate_bundle.validity.valid else "reject"))
    stages.append((
        "hard-topology",
        "pass" if candidate_bundle.topology.valid else "reject",
    ))
    stages.append((
        "support+geometry",
        "pass" if candidate_bundle.support.valid and candidate_bundle.geometry.valid
        else "reject",
    ))
    scored_pixels = max(1, candidate_bundle.support.scored_pixels)
    render_gain = (
        candidate_bundle.render_evidence.conservative_lower_bound
        / scored_pixels
    )
    complexity_delta = (
        candidate_bundle.complexity.total_code_bits
        - fallback_bundle.complexity.total_code_bits
    ) / max(64.0, float(scored_pixels))
    structure_delta = (
        candidate_bundle.structural.score - fallback_bundle.structural.score
    )
    risk_delta = float(candidate.risk - fallback.risk)
    score = (
        render_gain - weights.lambda_mdl * complexity_delta
        + weights.lambda_struct * structure_delta
        - weights.lambda_risk * risk_delta
    )
    stages.extend((
        ("render-bayes-factor", f"lcb/pixel={render_gain:.9g}"),
        ("structural-group-prior", f"delta={structure_delta:.9g}"),
        ("mdl-editability", f"delta/pixel={complexity_delta:.9g}"),
    ))
    preference_score: float | None = None
    if exact_physical.candidate_definitely_dominated:
        score = -1.0e12
        selected = False
        reason = "candidate-exact-color-mass-bound-dominated"
        preference_status = "skipped-physical-dominance"
    elif not candidate_bundle.valid:
        selected = False
        reason = "candidate-certificate-rejected"
        preference_status = "skipped-certificate-reject"
    elif not fallback_bundle.valid:
        selected = True
        reason = "fallback-certificate-rejected"
        preference_status = "skipped-fallback-reject"
    elif score > weights.preference_tie_epsilon:
        selected = True
        reason = "positive-conservative-utility"
        preference_status = "not-needed"
    elif score < -weights.preference_tie_epsilon:
        selected = False
        reason = "negative-conservative-utility-fallback"
        preference_status = "not-needed"
    elif preference_tiebreaker is not None:
        preference_score = float(preference_tiebreaker(
            observed_crop, candidate_crop, fallback_crop,
            candidate_bundle, fallback_bundle,
        ))
        if not math.isfinite(preference_score):
            raise ValueError("preference tiebreaker returned a non-finite score")
        selected = preference_score > 0.0
        reason = (
            "learned-preference-tiebreak-candidate"
            if selected else "learned-preference-tie-or-fallback"
        )
        preference_status = f"score={preference_score:.9g}"
    else:
        selected = False
        reason = "tie-without-preference-model-fallback"
        preference_status = "unavailable"
    stages.append(("learned-preference-tiebreak", preference_status))
    cascade.append((
        "expensive-perceptual-tiebreak",
        preference_status if abs(score) <= weights.preference_tie_epsilon
        else "not-needed",
    ))
    scaled = float(np.clip(
        score / weights.probability_temperature, -60.0, 60.0
    ))
    probability = 1.0 / (1.0 + math.exp(-scaled))
    if exact_physical.candidate_definitely_dominated:
        probability = 0.0
    elif not candidate_bundle.valid:
        probability = 0.0
    elif not fallback_bundle.valid:
        probability = 1.0
    stages.append(("tie-policy", "fallback" if not selected else "not-needed"))
    return CourtDecision(
        selected_id=candidate.id if selected else fallback.id,
        fallback_id=fallback.id, candidate_id=candidate.id,
        candidate_selected=selected, candidate_score=float(score),
        fallback_score=0.0,
        calibrated_candidate_probability=float(probability), reason=reason,
        stages=tuple(stages), candidate_bundle=candidate_bundle,
        fallback_bundle=fallback_bundle,
        posterior_digest=posterior.digest,
        exact_render_pixels=atlas_result.exact_render_pixels,
        approximate_render_pixels=approximate_result.exact_render_pixels,
        cascade_pruned_before_exact=False, cascade=tuple(cascade),
        preference_tiebreak_score=preference_score,
    )

"""M8: the materialization court - a race between final programs.

Plan M8.  Until now the court chose a support mask and the exporter chose
the geometry afterwards, so "pixel-faithful vs wobbly cubic vs fair arc"
was never a decision anyone made.  Here the alternatives are built first,
certified, rendered exactly, and compared in a lexicographic order that
cannot be gamed by a prettier curve:

    hard certificates first  (validity, correspondence, separation,
                              appearance completeness, corridor)
    then physical evidence   (render residual under one posterior)
    then fairness and MDL    (only inside a physical near-tie)

Tie goes to the incumbent (plan S4.4 of the project contract).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from .appearance_transport import (
    appearance_completeness,
    extract_salient_clusters,
)
from .fair_curve_program import fair_program_from_coverage
from .materialization_certificates import (
    MaterializationCertificates,
    component_correspondence,
    delivery_identity_certificate,
    separation_certificate,
)
from .svg_fragment_renderer import render_program
from .text_materialization import (
    ResourceEstimate,
    TextVectorCandidate,
    faithful_program_from_mask,
    generate_legacy_smooth_program,
    resource_estimate_for,
)
from .vector_program import TextVectorProgram, serialize_text_vector_program
from .wobble_metrics import turning_density

#: A candidate must beat the incumbent by more than this to win outright.
STRONG_RENDER_MARGIN = 0.010
#: Below this it is a physical loss and no amount of fairness buys it back.
NEGATIVE_RENDER_MARGIN = -0.002
#: Inside the tie band, fairness decides - but only by a real margin.
FAIRNESS_MARGIN = 1.0e-6
#: The fair program may cost more spans than the faithful one only up to
#: this factor; beyond it the "simpler program" argument is gone.
ALLOWED_COMPLEXITY_RATIO = 1.6


@dataclass(frozen=True)
class MaterializationDecision:
    selected_id: str
    candidate_id: str
    fallback_id: str
    candidate_selected: bool
    reason: str
    render_delta: float
    fairness_delta: float
    complexity_ratio: float
    stages: tuple[tuple[str, str], ...] = ()
    violations: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaterializationRace:
    winner: TextVectorCandidate
    decisions: tuple[MaterializationDecision, ...] = ()
    candidates: tuple[TextVectorCandidate, ...] = ()
    elapsed_ms: float = 0.0


def _alpha_of(candidate: TextVectorCandidate) -> np.ndarray:
    render = candidate.exact_render_linear_rgba
    if render is None:
        raise ValueError("candidate has no exact render")
    return np.asarray(render[..., 3], np.float32)


def render_residual(
    candidate: TextVectorCandidate, observed_alpha: np.ndarray,
) -> float:
    """Mean absolute alpha residual on the evaluation domain (density-free)."""
    domain = np.asarray(candidate.evaluation_support, bool)
    if not domain.any():
        return 0.0
    delivered = _alpha_of(candidate)
    observed = np.asarray(observed_alpha, np.float32)
    return float(np.mean(np.abs(delivered[domain] - observed[domain])))


def compare_materializations(
    candidate: TextVectorCandidate, fallback: TextVectorCandidate, *,
    observed_alpha: np.ndarray,
    candidate_fairness_cost: float = 0.0,
    fallback_fairness_cost: float = 0.0,
) -> MaterializationDecision:
    """Plan M8.3 lexicographic decision order."""
    stages: list[tuple[str, str]] = []
    violations = candidate.certificates.violations()
    if violations:
        stages.append(("hard-certificates", "rejected"))
        return MaterializationDecision(
            selected_id=fallback.id, candidate_id=candidate.id,
            fallback_id=fallback.id, candidate_selected=False,
            reason="candidate-certificate-rejected",
            render_delta=0.0, fairness_delta=0.0, complexity_ratio=1.0,
            stages=tuple(stages), violations=violations,
        )
    stages.append(("hard-certificates", "passed"))

    candidate_error = render_residual(candidate, observed_alpha)
    fallback_error = render_residual(fallback, observed_alpha)
    render_delta = fallback_error - candidate_error
    fairness_delta = fallback_fairness_cost - candidate_fairness_cost
    candidate_spans = max(1, candidate.resource_estimate.span_count)
    fallback_spans = max(1, fallback.resource_estimate.span_count)
    complexity_ratio = candidate_spans / fallback_spans

    if render_delta < NEGATIVE_RENDER_MARGIN:
        stages.append(("physical-evidence", "candidate-worse"))
        reason = "negative-render-evidence-fallback"
        selected = False
    elif render_delta > STRONG_RENDER_MARGIN:
        stages.append(("physical-evidence", "candidate-strongly-better"))
        reason = "strong-render-evidence-candidate"
        selected = True
    elif (
        fairness_delta > FAIRNESS_MARGIN
        and complexity_ratio <= ALLOWED_COMPLEXITY_RATIO
    ):
        stages.append(("physical-evidence", "near-tie"))
        stages.append(("fairness", "candidate-fairer-and-simple-enough"))
        reason = "fair-program-wins-physical-tie"
        selected = True
    else:
        stages.append(("physical-evidence", "near-tie"))
        stages.append(("fairness", "no-decisive-advantage"))
        reason = "tie-returns-fallback"
        selected = False
    stages.append(("tie-policy", "fallback" if not selected else "not-needed"))
    return MaterializationDecision(
        selected_id=candidate.id if selected else fallback.id,
        candidate_id=candidate.id, fallback_id=fallback.id,
        candidate_selected=selected, reason=reason,
        render_delta=render_delta, fairness_delta=fairness_delta,
        complexity_ratio=complexity_ratio, stages=tuple(stages),
    )


def _certify(
    program: TextVectorProgram, *, source_mask: np.ndarray,
    rendered_alpha: np.ndarray, rendered_sha: str,
    canvas: tuple[int, int], allow_fusion: bool,
    source_clusters, delivered_layers, scales: dict[str, np.ndarray],
    fairness=None,
) -> MaterializationCertificates:
    delivered_mask = rendered_alpha >= 0.5
    return MaterializationCertificates(
        topology=component_correspondence(
            source_mask, delivered_mask, allow_fusion=allow_fusion,
        ),
        separation=separation_certificate(
            source_mask, scales, explicit_fusion_operator=(
                "declared-ligature" if allow_fusion else None
            ),
        ),
        fairness=fairness,
        appearance=(
            appearance_completeness(source_clusters, delivered_layers)
            if source_clusters else None
        ),
        identity=delivery_identity_certificate(
            program, rendered_rgba_sha256=rendered_sha,
        ),
    )


def _build_candidate(
    program: TextVectorProgram, *, record_id: str, source_mask: np.ndarray,
    evaluation_support: np.ndarray, canvas: tuple[int, int],
    allow_fusion: bool, source_clusters, fairness=None,
    fit_milliseconds: float = 0.0,
) -> TextVectorCandidate | None:
    width, height = canvas
    try:
        rendered = render_program(program, width=width, height=height)
    except Exception:
        return None
    alpha = rendered.rgba[..., 3].astype(np.float32) / 255.0
    if alpha.shape != (height, width):
        return None
    scales = {"native": alpha}
    for label, factor in (("scale2", 2), ("scale4", 4)):
        try:
            scaled = render_program(
                program, width=width, height=height, supersample=factor,
            )
            scales[label] = scaled.rgba[..., 3].astype(np.float32) / 255.0
        except Exception:
            continue
    delivered_layers = [
        (
            layer.id,
            getattr(layer.paint, "rgba_linear", (0.0, 0.0, 0.0, 1.0)),
            alpha >= 0.5,
        )
        for layer in program.layers
    ]
    certificates = _certify(
        program, source_mask=source_mask, rendered_alpha=alpha,
        rendered_sha=rendered.rgba_sha256, canvas=canvas,
        allow_fusion=allow_fusion, source_clusters=source_clusters,
        delivered_layers=delivered_layers, scales=scales, fairness=fairness,
    )
    linear = rendered.rgba.astype(np.float32) / 255.0
    return TextVectorCandidate(
        id=f"{record_id}:{program.geometry_family}",
        source_record_id=record_id, program=program,
        ownership_support=np.asarray(alpha >= 0.5, bool),
        evaluation_support=np.asarray(evaluation_support, bool),
        exact_svg_fragment=serialize_text_vector_program(program),
        exact_render_linear_rgba=linear,
        exact_render_sha256=rendered.rgba_sha256,
        certificates=certificates,
        resource_estimate=resource_estimate_for(
            program, exact_render_pixels=int(alpha.size),
            fit_milliseconds=fit_milliseconds,
        ),
        provenance=program.provenance,
    )


def evaluation_domain(
    *masks: np.ndarray, apron: int = 2,
) -> np.ndarray:
    """candidate | fallback | required evidence + apron (plan S1.6)."""
    union = np.zeros_like(np.asarray(masks[0], bool))
    for mask in masks:
        if mask is None:
            continue
        union |= np.asarray(mask, bool)
    if apron > 0:
        union = cv2.dilate(
            union.astype(np.uint8), np.ones((3, 3), np.uint8),
            iterations=int(apron),
        ).astype(bool)
    return union


def race_materializations(
    source_mask: np.ndarray, *, record_id: str, line_id: str,
    straight_rgba: tuple[float, float, float, float],
    coverage: np.ndarray | None = None,
    linear_rgb: np.ndarray | None = None,
    allow_fusion: bool = False, enable_fair: bool = True,
    enable_legacy_smooth: bool = True,
) -> MaterializationRace | None:
    """Build the candidate set for one line and race it (plan M8).

    The faithful program is the incumbent by construction: it is exact by
    definition, so any other family must earn its place.
    """
    started = time.perf_counter()
    mask = np.asarray(source_mask, bool)
    if not mask.any():
        return None
    height, width = mask.shape
    canvas = (width, height)
    observed_alpha = (
        np.asarray(coverage, np.float32) if coverage is not None
        else mask.astype(np.float32)
    )
    source_clusters = (
        extract_salient_clusters(linear_rgb, mask)
        if linear_rgb is not None else []
    )

    faithful_program = faithful_program_from_mask(
        mask, program_id=f"{record_id}-faithful", source_line_id=line_id,
        straight_rgba=straight_rgba,
    )
    if faithful_program is None:
        return None
    programs: list[tuple[TextVectorProgram, object]] = [
        (faithful_program, None),
    ]
    if enable_legacy_smooth:
        legacy = generate_legacy_smooth_program(
            mask, program_id=f"{record_id}-legacy", source_line_id=line_id,
            straight_rgba=straight_rgba, density_proof=True,
        )
        if legacy is not None:
            programs.append((legacy, None))
    if enable_fair:
        fair_program, fair_certificate = fair_program_from_coverage(
            observed_alpha, program_id=f"{record_id}-fair",
            source_line_id=line_id, straight_rgba=straight_rgba,
        )
        if fair_program is not None:
            programs.append((fair_program, fair_certificate))

    supports = [mask]
    built: list[TextVectorCandidate] = []
    fairness_costs: dict[str, float] = {}
    for program, fairness in programs:
        preview = render_program(program, width=width, height=height)
        supports.append(preview.rgba[..., 3] >= 128)
    domain = evaluation_domain(*supports)

    for program, fairness in programs:
        candidate = _build_candidate(
            program, record_id=record_id, source_mask=mask,
            evaluation_support=domain, canvas=canvas,
            allow_fusion=allow_fusion, source_clusters=source_clusters,
            fairness=fairness,
        )
        if candidate is None:
            continue
        built.append(candidate)
        # Every candidate pays an honest fairness cost, including the
        # faithful one: excess turning is what a staircase actually costs
        # the eye, and pretending it is zero made the tie band unusable.
        fairness_costs[candidate.id] = (
            turning_density(program)
            + (float(getattr(fairness, "soft_cost", 0.0)) if fairness else 0.0)
        )
    if not built:
        return None

    incumbent = built[0]
    decisions: list[MaterializationDecision] = []
    for challenger in built[1:]:
        decision = compare_materializations(
            challenger, incumbent, observed_alpha=observed_alpha,
            candidate_fairness_cost=fairness_costs.get(challenger.id, 0.0),
            fallback_fairness_cost=fairness_costs.get(incumbent.id, 0.0),
        )
        decisions.append(decision)
        if decision.candidate_selected:
            incumbent = challenger
    return MaterializationRace(
        winner=incumbent, decisions=tuple(decisions),
        candidates=tuple(built),
        elapsed_ms=(time.perf_counter() - started) * 1000.0,
    )

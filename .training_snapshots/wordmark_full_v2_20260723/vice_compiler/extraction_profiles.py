"""Faithful, balanced and idealized Pareto extraction finalists."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Callable

from .hierarchy import RegionHierarchy
from .macro_extractor import SelectionConstraint, extract_visible_scene
from .macro_ir import CandidateMacroIR, MacroCandidate, ScoreBounds, registry_digest
from .master_problem import MasterSolution
from .production_court import CourtMarginalDelta


class ExtractionProfile(str, Enum):
    FAITHFUL = "faithful"
    BALANCED = "balanced"
    IDEALIZED = "idealized"

    @classmethod
    def parse(cls, value: str | "ExtractionProfile") -> "ExtractionProfile":
        if isinstance(value, cls):
            return value
        return cls(str(value).strip().lower())


@dataclass(frozen=True)
class ExtractionFinalist:
    profile: ExtractionProfile
    solution: MasterSolution
    predicted_pixel_delta: float
    support_loss: float
    structural_score: float
    complexity_bits: float
    typed_macros: int
    pareto: bool
    provenance: tuple[str, ...]


FinalistPreferenceSelector = Callable[
    [tuple[ExtractionFinalist, ...]], str | ExtractionProfile | None
]


def _profile_bonus(
    profile: ExtractionProfile, candidate: MacroCandidate,
    marginal: CourtMarginalDelta | None,
) -> float:
    if candidate.is_base:
        return 0.0
    pixel_delta = marginal.pixel_error_delta if marginal is not None else 0.0
    support_loss = 1.0 - marginal.evidence_iou if marginal is not None else 0.0
    proof = candidate.proof_bundle
    structural = proof.structural.score if proof is not None else 0.0
    complexity = proof.complexity.total_code_bits if proof is not None else 0.0
    if profile is ExtractionProfile.FAITHFUL:
        return float(
            -24.0 * max(0.0, pixel_delta)
            -8.0 * max(0.0, support_loss - 0.005)
            -0.002 * complexity
        )
    if profile is ExtractionProfile.IDEALIZED:
        # Idealization remains bounded by the same hard certificates/court;
        # only the global objective shifts toward structure and concise native
        # programs after validity, topology and support are already fixed.
        return float(
            0.90 * structural
            +0.14 * math.log2(max(1, candidate.cell_count))
            -0.010 * complexity
            -2.0 * max(0.0, support_loss - 0.20)
        )
    return 0.0


def _profiled_cmir(
    cmir: CandidateMacroIR, profile: ExtractionProfile,
    marginals: dict[str, CourtMarginalDelta],
) -> CandidateMacroIR:
    candidates = []
    for candidate in cmir.candidates:
        shift = _profile_bonus(profile, candidate, marginals.get(candidate.id))
        bounds = candidate.score_bounds
        candidates.append(replace(
            candidate,
            score_bounds=ScoreBounds(
                bounds.lower + shift,
                bounds.expected + shift,
                bounds.upper + shift,
            ),
        ))
    frozen = tuple(candidates)
    result = replace(
        cmir, candidates=frozen,
        registry_hash=registry_digest(frozen, cmir.interface_endpoints),
        provenance=(*cmir.provenance, f"objective-profile:{profile.value}"),
    )
    result.validate()
    return result


def _summarize(
    profile: ExtractionProfile, solution: MasterSolution,
    cmir: CandidateMacroIR, marginals: dict[str, CourtMarginalDelta],
) -> ExtractionFinalist:
    lookup = cmir.by_id()
    typed = [
        lookup[candidate_id] for candidate_id in solution.selected_ids
        if not lookup[candidate_id].is_base
    ]
    pixel = support = structural = complexity = 0.0
    for candidate in typed:
        marginal = marginals.get(candidate.id)
        if marginal is not None:
            pixel += marginal.pixel_error_delta
            support += max(0.0, 1.0 - marginal.evidence_iou)
        if candidate.proof_bundle is not None:
            structural += candidate.proof_bundle.structural.score
            complexity += candidate.proof_bundle.complexity.total_code_bits
    return ExtractionFinalist(
        profile=profile, solution=solution,
        predicted_pixel_delta=float(pixel), support_loss=float(support),
        structural_score=float(structural), complexity_bits=float(complexity),
        typed_macros=len(typed), pareto=False,
        provenance=(
            "same-certified-CMIR", "profiled-global-objective",
            "hard-constraints-identical-across-profiles",
        ),
    )


def _dominates(first: ExtractionFinalist, second: ExtractionFinalist) -> bool:
    no_worse = (
        first.predicted_pixel_delta <= second.predicted_pixel_delta + 1e-12
        and first.support_loss <= second.support_loss + 1e-12
        and first.structural_score >= second.structural_score - 1e-12
        and first.complexity_bits <= second.complexity_bits + 1e-12
    )
    strict = (
        first.predicted_pixel_delta < second.predicted_pixel_delta - 1e-12
        or first.support_loss < second.support_loss - 1e-12
        or first.structural_score > second.structural_score + 1e-12
        or first.complexity_bits < second.complexity_bits - 1e-12
    )
    return bool(no_worse and strict)


def build_profile_finalists(
    cmir: CandidateMacroIR, hierarchy: RegionHierarchy,
    *, marginals: tuple[CourtMarginalDelta, ...],
    exact_component_limit: int, time_budget_ms: float,
    selection_constraint: SelectionConstraint | None,
    balanced_solution: MasterSolution | None = None,
) -> tuple[ExtractionFinalist, ...]:
    marginal_map = {row.candidate_id: row for row in marginals}
    rows = []
    for profile in ExtractionProfile:
        if profile is ExtractionProfile.BALANCED and balanced_solution is not None:
            solution = balanced_solution
        else:
            profiled = _profiled_cmir(cmir, profile, marginal_map)
            solution = extract_visible_scene(
                profiled, hierarchy,
                exact_component_limit=exact_component_limit,
                time_budget_ms=max(1.0, float(time_budget_ms) / 3.0),
                require_proofs=True,
                selection_constraint=selection_constraint,
            )
        rows.append(_summarize(
            profile, solution, cmir, marginal_map,
        ))
    return tuple(
        replace(row, pareto=not any(
            other is not row and _dominates(other, row)
            for other in rows
        ))
        for row in rows
    )


def choose_profile_finalist(
    finalists: tuple[ExtractionFinalist, ...],
    requested: ExtractionProfile,
    selector: FinalistPreferenceSelector | None = None,
) -> ExtractionFinalist:
    pareto = tuple(row for row in finalists if row.pareto and row.solution.feasible)
    if not pareto:
        raise ValueError("no feasible Pareto extraction finalist")
    if selector is not None:
        choice = selector(pareto)
        if choice is not None:
            parsed = ExtractionProfile.parse(choice)
            selected = next((row for row in pareto if row.profile is parsed), None)
            if selected is not None:
                return selected
    requested_row = next(
        (row for row in pareto if row.profile is requested), None,
    )
    if requested_row is not None:
        return requested_row
    if requested is ExtractionProfile.FAITHFUL:
        return min(pareto, key=lambda row: (
            row.predicted_pixel_delta, row.support_loss,
            row.complexity_bits, row.profile.value,
        ))
    if requested is ExtractionProfile.IDEALIZED:
        return max(pareto, key=lambda row: (
            row.structural_score, -row.complexity_bits,
            -row.support_loss, row.profile.value,
        ))
    return min(pareto, key=lambda row: (
        row.support_loss + max(0.0, row.predicted_pixel_delta),
        -row.structural_score, row.complexity_bits, row.profile.value,
    ))

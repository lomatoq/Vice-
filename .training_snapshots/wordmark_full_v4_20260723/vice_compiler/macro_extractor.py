"""Bounded visible exact-cover extraction over hierarchy + typed macros."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .conflict_components import typed_conflict_components
from .hierarchy import RegionHierarchy
from .hierarchy_dp import solve_hierarchy_dp
from .macro_ir import CandidateMacroIR, MacroCandidate, MacroKind
from .master_problem import MasterSolution


SelectionConstraint = Callable[
    [tuple[MacroCandidate, ...], MacroCandidate], bool
]


@dataclass(frozen=True)
class ConflictRollbackResult:
    solution: MasterSolution
    blamed_ids: tuple[str, ...]
    affected_candidate_ids: tuple[str, ...]
    retained_typed_ids: tuple[str, ...]
    affected_components: int


def _prerequisite_satisfied(candidate: MacroCandidate, claim: str) -> bool:
    bundle = candidate.proof_bundle
    if bundle is None:
        return False
    notes = candidate.certificates.notes
    if claim.startswith("components="):
        try:
            return bundle.topology.components == int(claim.split("=", 1)[1])
        except ValueError:
            return False
    if claim.startswith("persistent-counters="):
        try:
            return bundle.topology.holes >= int(claim.split("=", 1)[1])
        except ValueError:
            return False
    if claim in {
        "no-unproven-fusion", "no-unproven-hole-fill",
        "native-topology-preserved",
    }:
        return bool(bundle.topology.valid and bundle.geometry.valid)
    if claim == "digital-preimage-feasible":
        return bool(
            bundle.geometry.valid
            and bundle.geometry.digital_preimage_feasible
        )
    if claim == "type-specific-identifiability-wall":
        return bool(
            bundle.geometry.valid
            and bundle.geometry.directional_interval_feasible
            and bundle.geometry.parameter_condition_number < 1e8
        )
    if claim == "bounded-render-residual":
        return bool(bundle.render_evidence.valid)
    if claim == "visible-ownership-before-hidden-completion":
        return bool(
            candidate.hidden_geometry is not None
            and bundle.validity.hidden_geometry_bounded
        )
    if claim == "no-glyph-outside-line-support":
        return bool(
            candidate.kind is MacroKind.TEXT_LINE
            and bundle.support.no_score_outside_support
        )
    if claim == "minimum-centerline-support":
        return bool(
            candidate.kind is MacroKind.STROKE_NETWORK
            and bundle.support.support_pixels >= 3
        )
    if claim == "distance-ridge-width-profile":
        return bool(any(row.startswith("width_cv=") for row in notes))
    if claim == "competes-with-filled-region-hierarchy":
        return candidate.kind is MacroKind.STROKE_NETWORK
    if claim in {
        "members-compete-with-independent-shapes",
        "shared-parameter-evidence", "bounded-member-residuals",
    }:
        return bool(
            candidate.program.operator.startswith("RepeatGroup/")
            and bundle.structural.valid
        )
    if claim == "single-image-level-degradation-posterior":
        return bool(bundle.render_evidence.posterior_digest)
    if claim in {
        "counterfactual-competes-in-global-extractor",
        "semantic-microdetail-rights-only", "residual-never-mutates-vsir",
    }:
        return candidate.kind is MacroKind.CODEC_DETAIL
    if claim == "region-support-evidence":
        return bool(bundle.support.valid and bundle.support.support_pixels > 0)
    if claim == "edge-mixture-excluded":
        return "edge-mixture-excluded" in notes
    if claim == "continuity-evidence":
        return any(row.startswith("residual_p95=") for row in notes)
    if claim == "model-complexity-penalized":
        return bool(bundle.complexity.valid)
    if claim == "palette-late-constraint-not-early-quantized":
        return candidate.program.operator.startswith("Appearance/")
    if claim == "layer-interaction-explicit-alpha":
        return bool(
            candidate.program.operator.startswith("Appearance/")
            and 0.0 <= candidate.alpha_bounds[0]
            <= candidate.alpha_bounds[1] <= 1.0
        )
    if claim == "local-cell-refinement-certified":
        return "selected-boundary-materialized-as-child-cells" in candidate.provenance
    # Claim ids are a closed factor vocabulary.  A typo or an unimplemented
    # prerequisite can never silently degrade into descriptive metadata.
    return False


def _proof_admissible(candidate: MacroCandidate, require_proofs: bool) -> bool:
    if candidate.is_base or not require_proofs:
        return True
    bundle = candidate.proof_bundle
    if bundle is None or not bundle.valid:
        return False
    # These are the hard global gates represented by the current CMIR claim
    # vocabulary.  Descriptive prerequisite strings can add evidence, but can
    # never weaken a failed machine-checkable certificate.
    if not (
        bundle.validity.valid and bundle.support.valid
        and bundle.topology.valid and bundle.geometry.valid
        and bundle.render_evidence.valid and bundle.resource.valid
    ):
        return False
    return all(
        _prerequisite_satisfied(candidate, claim)
        for claim in candidate.prerequisite_claims
    )


def _solution_for_typed(
    cmir: CandidateMacroIR, hierarchy: RegionHierarchy,
    typed: tuple[MacroCandidate, ...],
    *, require_proofs: bool = False,
    selection_constraint: SelectionConstraint | None = None,
) -> tuple[float, tuple[str, ...], int] | None:
    blocked = 0
    typed_utility = 0.0
    accepted: tuple[MacroCandidate, ...] = ()
    for candidate in typed:
        if not _proof_admissible(candidate, require_proofs):
            return None
        if selection_constraint is not None and not selection_constraint(
            accepted, candidate,
        ):
            return None
        if blocked & candidate.core_bits:
            return None
        blocked |= candidate.core_bits
        typed_utility += candidate.score_bounds.lower
        accepted = (*accepted, candidate)
    base = solve_hierarchy_dp(cmir, hierarchy, blocked_bits=blocked)
    if not base.feasible:
        return None
    selected = tuple(sorted((*base.selected_ids, *(candidate.id for candidate in typed))))
    return typed_utility + base.utility, selected, blocked | base.covered_bits


def extract_visible_scene(
    cmir: CandidateMacroIR, hierarchy: RegionHierarchy,
    *, exact_component_limit: int = 18,
    time_budget_ms: float = 100.0,
    require_proofs: bool = False,
    selection_constraint: SelectionConstraint | None = None,
) -> MasterSolution:
    """Solve sparse typed conflict components with a guaranteed base cover."""
    started = time.perf_counter()
    # A wall-clock cutoff made the chosen scene depend on scheduler load: the
    # same component could commit an arbitrary partially explored subset on
    # one run and a different subset on the next.  Convert the public time
    # allowance into a deterministic search-work certificate.  Exact search
    # is entered only when its complete binary tree fits the remaining budget;
    # otherwise the whole component uses the stable greedy fallback.
    work_remaining = max(64, int(max(0.0, time_budget_ms) * 40.0))
    base = solve_hierarchy_dp(cmir, hierarchy)
    if not base.feasible:
        return MasterSolution(
            selected_ids=(), utility=float("-inf"), covered_bits=0,
            feasible=False, exact_cover=False, used_atomic_fallback=False,
            fallback_always_feasible=False,
            solve_ms=(time.perf_counter() - started) * 1000.0,
            exact_components=0, bounded_components=0,
            fallback_reason="mandatory-base-cover-infeasible",
        )
    lookup = cmir.by_id()
    selected_typed: tuple[MacroCandidate, ...] = ()
    current = _solution_for_typed(
        cmir, hierarchy, selected_typed,
        require_proofs=require_proofs,
        selection_constraint=selection_constraint,
    )
    assert current is not None
    exact_components = 0
    bounded_components = 0
    work_bounded = False

    for component in typed_conflict_components(cmir):
        candidates = tuple(
            candidate for candidate_id in component.candidate_ids
            if _proof_admissible(
                (candidate := lookup[candidate_id]), require_proofs,
            )
        )
        if not candidates:
            continue
        required_exact_nodes = (1 << (len(candidates) + 1)) - 1
        can_finish_exact = bool(
            len(candidates) <= exact_component_limit
            and required_exact_nodes <= work_remaining
        )
        if can_finish_exact:
            exact_components += 1
            best = current
            best_subset: tuple[MacroCandidate, ...] = ()
            visited_nodes = 0

            def search(
                index: int, chosen: tuple[MacroCandidate, ...], occupied: int
            ) -> None:
                nonlocal best, best_subset, visited_nodes
                visited_nodes += 1
                if index >= len(candidates):
                    proposal = _solution_for_typed(
                        cmir, hierarchy, (*selected_typed, *chosen),
                        require_proofs=require_proofs,
                        selection_constraint=selection_constraint,
                    )
                    if proposal is not None and (
                        proposal[0] > best[0] + 1e-12
                        or (abs(proposal[0] - best[0]) <= 1e-12
                            and len(proposal[1]) < len(best[1]))
                    ):
                        best = proposal
                        best_subset = chosen
                    return
                search(index + 1, chosen, occupied)
                candidate = candidates[index]
                if not (occupied & candidate.core_bits):
                    search(
                        index + 1, (*chosen, candidate),
                        occupied | candidate.core_bits,
                    )

            occupied_before = 0
            for candidate in selected_typed:
                occupied_before |= candidate.core_bits
            search(0, (), occupied_before)
            work_remaining -= visited_nodes
            if best[0] > current[0] + 1e-12:
                selected_typed = (*selected_typed, *best_subset)
                current = best
        else:
            work_bounded = True
            bounded_components += 1
            occupied = 0
            for candidate in selected_typed:
                occupied |= candidate.core_bits
            for candidate in sorted(
                candidates,
                key=lambda item: (-item.score_bounds.lower, item.id),
            ):
                if work_remaining <= 0:
                    break
                work_remaining -= 1
                if occupied & candidate.core_bits:
                    continue
                proposal = _solution_for_typed(
                    cmir, hierarchy, (*selected_typed, candidate),
                    require_proofs=require_proofs,
                    selection_constraint=selection_constraint,
                )
                if proposal is not None and proposal[0] > current[0] + 1e-12:
                    selected_typed = (*selected_typed, candidate)
                    occupied |= candidate.core_bits
                    current = proposal

    selected_ids = current[1]
    covered_bits = current[2]
    all_bits = (1 << cmir.leaf_count) - 1
    exact_cover = covered_bits == all_bits
    used_atomic = any(
        lookup[candidate_id].kind is MacroKind.ATOMIC_FALLBACK
        for candidate_id in selected_ids
    )
    return MasterSolution(
        selected_ids=selected_ids, utility=current[0],
        covered_bits=covered_bits, feasible=exact_cover,
        exact_cover=exact_cover, used_atomic_fallback=used_atomic,
        fallback_always_feasible=base.feasible,
        solve_ms=(time.perf_counter() - started) * 1000.0,
        exact_components=exact_components,
        bounded_components=bounded_components,
        fallback_reason=(
            "deterministic-work-budget-returned-valid-best"
            if work_bounded else None
        ),
    )


def rollback_conflict_components(
    cmir: CandidateMacroIR, hierarchy: RegionHierarchy,
    incumbent: MasterSolution, blamed_ids: tuple[str, ...],
    *, require_proofs: bool = False,
    selection_constraint: SelectionConstraint | None = None,
) -> ConflictRollbackResult:
    """Rollback only conflict components touched by marginal blame.

    Affected components deliberately re-extract to the hierarchy/base cover.
    Unaffected typed winners stay frozen, which preserves good rewrites while
    making the recovery render derivable from the cached exact transaction.
    """
    lookup = cmir.by_id()
    blamed = tuple(sorted({
        candidate_id for candidate_id in blamed_ids
        if candidate_id in lookup and not lookup[candidate_id].is_base
    }))
    components = typed_conflict_components(cmir)
    affected_components = tuple(
        component for component in components
        if set(component.candidate_ids).intersection(blamed)
    )
    affected_ids = {
        candidate_id for component in affected_components
        for candidate_id in component.candidate_ids
    }
    # A delivery-overlap closure can join coarse-core components.  Include a
    # blamed singleton even if the registry graph was constructed before that
    # delivery mask existed.
    affected_ids.update(blamed)
    retained = tuple(
        lookup[candidate_id]
        for candidate_id in incumbent.selected_ids
        if candidate_id in lookup
        and not lookup[candidate_id].is_base
        and candidate_id not in affected_ids
    )
    proposal = _solution_for_typed(
        cmir, hierarchy, retained,
        require_proofs=require_proofs,
        selection_constraint=selection_constraint,
    )
    if proposal is None:
        retained = ()
        proposal = _solution_for_typed(
            cmir, hierarchy, retained,
            require_proofs=require_proofs,
            selection_constraint=selection_constraint,
        )
    if proposal is None:
        raise RuntimeError("mandatory base cover failed during component rollback")
    selected_ids = proposal[1]
    all_bits = (1 << cmir.leaf_count) - 1
    solution = MasterSolution(
        selected_ids=selected_ids, utility=proposal[0],
        covered_bits=proposal[2], feasible=proposal[2] == all_bits,
        exact_cover=proposal[2] == all_bits,
        used_atomic_fallback=any(
            lookup[candidate_id].kind is MacroKind.ATOMIC_FALLBACK
            for candidate_id in selected_ids
        ),
        fallback_always_feasible=True, solve_ms=0.0,
        exact_components=len(affected_components), bounded_components=0,
        fallback_reason="marginal-blame-conflict-component-rollback",
    )
    return ConflictRollbackResult(
        solution=solution, blamed_ids=blamed,
        affected_candidate_ids=tuple(sorted(affected_ids)),
        retained_typed_ids=tuple(row.id for row in retained),
        affected_components=len(affected_components),
    )

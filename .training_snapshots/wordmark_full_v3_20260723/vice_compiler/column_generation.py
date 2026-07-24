"""Bounded production approximation to dual-guided column generation."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable

from .evidence_ir import RasterEvidenceIR
from .hierarchy_dp import solve_hierarchy_dp
from .macro_extractor import SelectionConstraint, extract_visible_scene
from .macro_ir import CandidateMacroIR, MacroCandidate
from .macro_registry import build_base_registry, candidate_from_token, extend_registry
from .master_problem import MasterSolution, derive_dual_prices, initial_master_solution
from .pricing_oracles import (
    PricingBatch, TokenPricingOracle, default_pricing_oracles,
    PricingContext,
)


@dataclass(frozen=True)
class PricingRound:
    index: int
    batches: tuple[PricingBatch, ...]
    added_ids: tuple[str, ...]
    generated_columns: int
    elapsed_ms: float
    dual_concentration: float
    master_utility: float
    master_feasible: bool


@dataclass(frozen=True)
class ColumnGenerationResult:
    cmir: CandidateMacroIR
    solution: MasterSolution
    rounds: tuple[PricingRound, ...]
    initial_columns: int
    final_columns: int
    total_pricing_ms: float
    used_manual_risk_threshold: bool


def _cell_uncertainty(reir: RasterEvidenceIR) -> tuple[float, ...]:
    values = [0.0] * reir.hierarchy.leaf_count
    for cell in reir.cells.cells:
        values[cell.leaf_id] = float(cell.uncertainty)
    return tuple(values)


def _dual_concentration(prices: tuple[float, ...]) -> float:
    values = sorted((max(0.0, value) for value in prices), reverse=True)
    total = sum(values)
    if total <= 0.0:
        return 0.0
    head = max(1, int((len(values) + 4) // 5))
    return float(sum(values[:head]) / total)


def _structural_residuals(reir: RasterEvidenceIR) -> tuple[float, float]:
    """Immutable REIR evidence that prices topology/layer factor claims."""
    topology = max((
        float(token.score) for token in reir.proposal_tokens
        if token.family in {"topology", "text", "stroke", "shape"}
    ), default=0.0)
    layer = max((
        float(token.score) for token in reir.proposal_tokens
        if token.family == "layer"
    ), default=0.0)
    return topology, layer


def _provisional_pricing_master(
    cmir: CandidateMacroIR, reir: RasterEvidenceIR,
) -> MasterSolution:
    """Cheap deterministic Lagrangian-like master used between pricing rounds.

    It never materialises a visible scene and never replaces the single final
    exact extraction.  Its only job is to update residual prices after newly
    certified columns arrive.
    """
    occupied = 0
    selected: list[MacroCandidate] = []
    typed = sorted(
        (candidate for candidate in cmir.candidates if not candidate.is_base),
        key=lambda candidate: (
            -(candidate.score_bounds.lower / max(1, candidate.cell_count)),
            -candidate.score_bounds.lower,
            candidate.id,
        ),
    )
    for candidate in typed:
        if candidate.score_bounds.lower <= 0.0:
            continue
        if occupied & candidate.core_bits:
            continue
        selected.append(candidate)
        occupied |= candidate.core_bits
    base = solve_hierarchy_dp(cmir, reir.hierarchy, blocked_bits=occupied)
    if not base.feasible:
        return initial_master_solution(cmir, reir.hierarchy)
    selected_ids = tuple(sorted((
        *base.selected_ids, *(candidate.id for candidate in selected)
    )))
    all_bits = (1 << cmir.leaf_count) - 1
    return MasterSolution(
        selected_ids=selected_ids,
        utility=base.utility + sum(
            candidate.score_bounds.lower for candidate in selected
        ),
        covered_bits=base.covered_bits | occupied,
        feasible=(base.covered_bits | occupied) == all_bits,
        exact_cover=(base.covered_bits | occupied) == all_bits,
        used_atomic_fallback=any(
            cmir.by_id()[candidate_id].kind.value == "atomic_fallback"
            for candidate_id in base.selected_ids
        ),
        fallback_always_feasible=True, solve_ms=0.0,
        exact_components=0, bounded_components=0,
        fallback_reason="provisional-pricing-master",
    )


def run_column_generation(
    reir: RasterEvidenceIR, *, rounds: int = 3,
    max_columns_per_oracle: int = 12,
    oracles: tuple[TokenPricingOracle, ...] | None = None,
    extraction_budget_ms: float = 60.0,
    exact_component_limit: int = 7,
    base_cmir: CandidateMacroIR | None = None,
    candidate_pool: tuple[MacroCandidate, ...] | None = None,
    admit_candidate: Callable[[MacroCandidate], MacroCandidate | None] | None = None,
    allow_support_qualification: bool = True,
    require_proofs: bool = False,
    selection_constraint: SelectionConstraint | None = None,
) -> ColumnGenerationResult:
    cmir = base_cmir or build_base_registry(reir)
    cmir.validate()
    initial_columns = len(cmir.candidates)
    solution = initial_master_solution(cmir, reir.hierarchy)
    uncertainty = _cell_uncertainty(reir)
    topology_residual, layer_residual = _structural_residuals(reir)
    oracle_set = oracles or default_pricing_oracles()
    if candidate_pool is None:
        candidate_pool = tuple(
            candidate for token in reir.proposal_tokens
            if (candidate := candidate_from_token(reir, token)) is not None
        )
    else:
        candidate_pool = tuple(candidate_pool)
    records: list[PricingRound] = []
    total_pricing_ms = 0.0
    used_manual = False
    any_additions = False
    for round_index in range(1, max(0, int(rounds)) + 1):
        started = time.perf_counter()
        prices = derive_dual_prices(
            cmir, solution, cell_uncertainty=uncertainty,
            topology_residual=topology_residual,
            layer_residual=layer_residual,
        )
        context = PricingContext(
            reir=reir, cmir=cmir, prices=prices,
            round_index=round_index,
            candidate_pool=candidate_pool,
            max_columns=max_columns_per_oracle,
            allow_support_qualification=allow_support_qualification,
        )
        batches = tuple(oracle.price(context) for oracle in oracle_set)
        additions = []
        seen: set[str] = set()
        for batch in batches:
            used_manual |= batch.used_manual_risk_threshold
            for priced in batch.columns:
                draft = priced.candidate
                if draft.id in seen:
                    continue
                seen.add(draft.id)
                admitted = admit_candidate(draft) if admit_candidate is not None else draft
                if admitted is not None:
                    additions.append(admitted)
        pricing_ms = sum(batch.elapsed_ms for batch in batches)
        total_pricing_ms += pricing_ms
        if additions:
            any_additions = True
            cmir = extend_registry(reir, cmir, additions, validate=False)
            solution = _provisional_pricing_master(cmir, reir)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        records.append(PricingRound(
            index=round_index, batches=batches,
            added_ids=tuple(candidate.id for candidate in additions),
            generated_columns=len(additions), elapsed_ms=elapsed_ms,
            dual_concentration=_dual_concentration(prices.cell_prices),
            master_utility=solution.utility,
            master_feasible=solution.feasible,
        ))
        if not additions:
            break
    # The bounded production contract permits one visible exact extraction.
    # Pricing rounds above only update a cheap provisional master/dual state.
    if any_additions:
        solution = extract_visible_scene(
            cmir, reir.hierarchy,
            exact_component_limit=exact_component_limit,
            time_budget_ms=extraction_budget_ms,
            require_proofs=require_proofs,
            selection_constraint=selection_constraint,
        )
    cmir.validate()
    return ColumnGenerationResult(
        cmir=cmir, solution=solution, rounds=tuple(records),
        initial_columns=initial_columns, final_columns=len(cmir.candidates),
        total_pricing_ms=total_pricing_ms,
        used_manual_risk_threshold=used_manual,
    )

"""Initial feasible master and dual-like residual prices for lazy pricing."""

from __future__ import annotations

from dataclasses import dataclass

from .hierarchy import RegionHierarchy
from .hierarchy_dp import solve_hierarchy_dp
from .macro_ir import CandidateMacroIR


@dataclass(frozen=True)
class MasterSolution:
    selected_ids: tuple[str, ...]
    utility: float
    covered_bits: int
    feasible: bool
    exact_cover: bool
    used_atomic_fallback: bool
    fallback_always_feasible: bool
    solve_ms: float
    exact_components: int
    bounded_components: int
    fallback_reason: str | None = None


@dataclass(frozen=True)
class DualPrices:
    cell_prices: tuple[float, ...]
    interface_prices: tuple[float, ...]
    topology_price: float
    layer_price: float
    provenance: str


def initial_master_solution(
    cmir: CandidateMacroIR, hierarchy: RegionHierarchy
) -> MasterSolution:
    base = solve_hierarchy_dp(cmir, hierarchy)
    lookup = cmir.by_id()
    return MasterSolution(
        selected_ids=base.selected_ids, utility=base.utility,
        covered_bits=base.covered_bits, feasible=base.feasible,
        exact_cover=base.feasible,
        used_atomic_fallback=any(
            lookup[candidate_id].kind.value == "atomic_fallback"
            for candidate_id in base.selected_ids
        ),
        fallback_always_feasible=base.feasible, solve_ms=0.0,
        exact_components=0, bounded_components=0,
        fallback_reason=None if base.feasible else "hierarchy-base-infeasible",
    )


def derive_dual_prices(
    cmir: CandidateMacroIR, solution: MasterSolution,
    *, cell_uncertainty: tuple[float, ...] | None = None,
    topology_residual: float = 0.0,
    layer_residual: float = 0.0,
) -> DualPrices:
    """Create deterministic dual-like prices from the current exact cover.

    These are residual prices, not fabricated LP duals: selected macro cost is
    distributed across its owned cells and uncertainty adds pressure where the
    current explanation is weak.  Pricing oracles only see this vector and
    REIR evidence; they never receive a hand-authored risk label.
    """
    prices = [0.0] * cmir.leaf_count
    lookup = cmir.by_id()
    for candidate_id in solution.selected_ids:
        candidate = lookup[candidate_id]
        share = max(0.0, candidate.score_bounds.lower) / max(1, candidate.cell_count)
        bits = candidate.core_bits
        while bits:
            low = bits & -bits
            leaf = low.bit_length() - 1
            prices[leaf] += share
            bits ^= low
    if cell_uncertainty is not None:
        if len(cell_uncertainty) != cmir.leaf_count:
            raise ValueError("cell uncertainty size mismatch")
        for index, uncertainty in enumerate(cell_uncertainty):
            prices[index] += 0.025 * max(0.0, min(1.0, float(uncertainty)))
    # One evidence interface is one factor variable.  The two selected macros
    # on opposite sides may both reference it, but summing both claims would
    # count the same boundary geometry twice (§7.4).  Aggregate the symmetric
    # claims into one canonical price instead.
    interface_claims: list[list[float]] = [
        [] for _ in range(cmir.interface_count)
    ]
    for candidate_id in solution.selected_ids:
        candidate = lookup[candidate_id]
        for interface_id in candidate.boundary_interfaces:
            interface_claims[interface_id].append(
                candidate.score_bounds.lower
                / max(1, len(candidate.boundary_interfaces))
            )
    interface_prices = [
        float(sum(claims) / len(claims)) if claims else 0.0
        for claims in interface_claims
    ]
    return DualPrices(
        cell_prices=tuple(prices),
        interface_prices=tuple(interface_prices),
        topology_price=0.05 * max(0.0, min(1.0, float(topology_residual))),
        layer_price=0.05 * max(0.0, min(1.0, float(layer_residual))),
        provenance=(
            "hierarchy-master-residual-prices+single-interface-factor"
            "+evidence-backed-topology-layer-v3"
        ),
    )


def reduced_gain(
    core_bits: int, lower_utility: float, prices: DualPrices,
    interface_ids: tuple[int, ...] = (),
    *, topology_claim: bool = False, layer_claim: bool = False,
) -> float:
    # In the maximization form used by the pricing oracles, a high residual
    # dual price is a reward for explaining an expensive cell (equivalent to
    # the negative reduced cost C(H)-sum(pi) in the minimization notation from
    # the plan).  Subtracting it would perversely suppress whole-scene
    # TextLine/gradient columns exactly where fallback is most expensive.
    dual_reward = 0.0
    bits = core_bits
    while bits:
        low = bits & -bits
        dual_reward += prices.cell_prices[low.bit_length() - 1]
        bits ^= low
    for interface_id in set(interface_ids):
        if interface_id < 0 or interface_id >= len(prices.interface_prices):
            raise ValueError("pricing candidate references an invalid interface")
        dual_reward += prices.interface_prices[interface_id]
    if topology_claim:
        dual_reward += prices.topology_price
    if layer_claim:
        dual_reward += prices.layer_price
    return float(lower_utility + dual_reward)

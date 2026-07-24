"""Linear laminar hierarchy dynamic program for the CMIR base master."""

from __future__ import annotations

from dataclasses import dataclass

from .hierarchy import RegionHierarchy
from .macro_ir import CandidateMacroIR, MacroCandidate


@dataclass(frozen=True)
class HierarchySolution:
    selected_ids: tuple[str, ...]
    utility: float
    covered_bits: int
    blocked_bits: int
    feasible: bool


def hierarchy_leaf_bits(hierarchy: RegionHierarchy) -> tuple[int, ...]:
    bits_by_node: list[int] = []
    for node in hierarchy.nodes:
        if node.left is None:
            bits = 1 << node.id
        else:
            bits = bits_by_node[node.left] | bits_by_node[node.right]
        bits_by_node.append(bits)
    return tuple(bits_by_node)


def _better(
    first: tuple[float, tuple[str, ...]],
    second: tuple[float, tuple[str, ...]],
) -> tuple[float, tuple[str, ...]]:
    if first[0] > second[0] + 1e-12:
        return first
    if second[0] > first[0] + 1e-12:
        return second
    if len(first[1]) < len(second[1]):
        return first
    if len(second[1]) < len(first[1]):
        return second
    return min(first, second, key=lambda value: value[1])


def solve_hierarchy_dp(
    cmir: CandidateMacroIR, hierarchy: RegionHierarchy,
    *, blocked_bits: int = 0,
) -> HierarchySolution:
    """Select an exact laminar cover for all cells not owned by typed macros."""
    if cmir.leaf_count != hierarchy.leaf_count:
        # A transactional local-refinement lattice is a derived partition of
        # the immutable hierarchy leaves.  It deliberately has no fabricated
        # global tree: cover every unblocked child with its mandatory atomic
        # fallback.  Typed conflict components are still solved exactly.
        all_bits = (1 << cmir.leaf_count) - 1
        if blocked_bits & ~all_bits:
            raise ValueError("blocked cells exceed refined lattice")
        by_bit: dict[int, list[MacroCandidate]] = {}
        for candidate in cmir.candidates:
            if candidate.is_base and candidate.core_bits.bit_count() == 1:
                by_bit.setdefault(candidate.core_bits, []).append(candidate)
        selected = []; utility = 0.0; covered = 0
        for cell_id in range(cmir.leaf_count):
            bit = 1 << cell_id
            if blocked_bits & bit:
                continue
            options = by_bit.get(bit, ())
            if not options:
                return HierarchySolution(
                    selected_ids=(), utility=float("-inf"), covered_bits=0,
                    blocked_bits=blocked_bits, feasible=False,
                )
            winner = max(
                options, key=lambda row: (row.score_bounds.lower, -len(row.id), row.id),
            )
            selected.append(winner.id); utility += winner.score_bounds.lower
            covered |= bit
        expected = all_bits & ~blocked_bits
        return HierarchySolution(
            selected_ids=tuple(sorted(selected)), utility=float(utility),
            covered_bits=covered, blocked_bits=blocked_bits,
            feasible=covered == expected,
        )
    all_bits = (1 << cmir.leaf_count) - 1
    if blocked_bits & ~all_bits:
        raise ValueError("blocked cells exceed hierarchy")
    node_bits = hierarchy_leaf_bits(hierarchy)
    candidates_by_support: dict[int, list[MacroCandidate]] = {}
    for candidate in cmir.candidates:
        if not candidate.is_base:
            continue
        candidates_by_support.setdefault(candidate.core_bits, []).append(candidate)
    cache: dict[int, tuple[float, tuple[str, ...]]] = {}

    def solve(node_id: int) -> tuple[float, tuple[str, ...]]:
        if node_id in cache:
            return cache[node_id]
        node = hierarchy.nodes[node_id]
        support = node_bits[node_id]
        remaining = support & ~blocked_bits
        if remaining == 0:
            result = (0.0, ())
        elif node.left is None:
            options = [
                (candidate.score_bounds.lower, (candidate.id,))
                for candidate in candidates_by_support.get(support, ())
            ]
            if not options:
                result = (float("-inf"), ())
            else:
                result = options[0]
                for option in options[1:]:
                    result = _better(result, option)
        else:
            left = solve(node.left)
            right = solve(node.right)
            split = (
                left[0] + right[0],
                tuple(sorted((*left[1], *right[1]))),
            )
            result = split
            if not (support & blocked_bits):
                for candidate in candidates_by_support.get(support, ()):
                    result = _better(
                        result,
                        (candidate.score_bounds.lower, (candidate.id,)),
                    )
        cache[node_id] = result
        return result

    utility, selected = solve(hierarchy.root_id)
    lookup = cmir.by_id()
    covered = 0
    for candidate_id in selected:
        covered |= lookup[candidate_id].core_bits
    expected = all_bits & ~blocked_bits
    feasible = utility != float("-inf") and covered == expected
    return HierarchySolution(
        selected_ids=selected, utility=float(utility),
        covered_bits=covered, blocked_bits=blocked_bits,
        feasible=feasible,
    )

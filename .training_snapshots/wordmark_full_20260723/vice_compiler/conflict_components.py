"""Sparse typed-macro conflict graph decomposition."""

from __future__ import annotations

from dataclasses import dataclass

from .macro_ir import CandidateMacroIR, iter_set_bits


@dataclass(frozen=True)
class ConflictComponent:
    candidate_ids: tuple[str, ...]
    registry_bits: int
    core_bits: int


def typed_conflict_components(cmir: CandidateMacroIR) -> tuple[ConflictComponent, ...]:
    typed = [candidate for candidate in cmir.candidates if not candidate.is_base]
    typed_indices = {candidate.registry_index for candidate in typed}
    unseen = set(typed_indices)
    components: list[ConflictComponent] = []
    by_index = cmir.candidates
    while unseen:
        seed = min(unseen)
        stack = [seed]
        unseen.remove(seed)
        members: set[int] = set()
        while stack:
            index = stack.pop()
            members.add(index)
            neighbours = {
                other for other in iter_set_bits(by_index[index].conflict_bits)
                if other in typed_indices
            }
            fresh = neighbours & unseen
            unseen.difference_update(fresh)
            stack.extend(sorted(fresh, reverse=True))
        ordered = tuple(sorted(members))
        registry_bits = sum(1 << index for index in ordered)
        core_bits = 0
        for index in ordered:
            core_bits |= by_index[index].core_bits
        components.append(ConflictComponent(
            candidate_ids=tuple(by_index[index].id for index in ordered),
            registry_bits=registry_bits, core_bits=core_bits,
        ))
    return tuple(sorted(components, key=lambda component: component.candidate_ids))

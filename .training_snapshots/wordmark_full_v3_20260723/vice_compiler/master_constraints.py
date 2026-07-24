"""Hard production constraints for sparse typed-master selection."""

from __future__ import annotations

from dataclasses import dataclass

from .macro_ir import MacroCandidate
from .phase5_macros import Phase5MacroBundle


@dataclass(frozen=True)
class MasterResourceLimits:
    fitting_ms: float
    render_pixels: int
    memory_bytes: int
    solver_variables: int


@dataclass(frozen=True)
class ProductionMasterConstraints:
    """Stateless branch-and-bound predicate over a proposed typed subset.

    Exact cover remains in ``macro_extractor``.  This predicate supplies the
    missing hard certificate, prerequisite/group, interface, layer-validity
    and aggregate resource walls without making search order part of truth.
    """

    limits: MasterResourceLimits
    group_members: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @classmethod
    def from_phase5(
        cls, phase5: Phase5MacroBundle, *, limits: MasterResourceLimits,
    ) -> "ProductionMasterConstraints":
        return cls(
            limits=limits,
            group_members=tuple(sorted(
                (row.candidate.id, tuple(row.member_ids))
                for row in phase5.shapes.groups
            )),
        )

    def __call__(
        self, selected: tuple[MacroCandidate, ...], candidate: MacroCandidate,
    ) -> bool:
        rows = (*selected, candidate)
        if any(
            row.hidden_geometry is not None
            and "visible-ownership-before-hidden-completion"
            not in row.prerequisite_claims
            for row in rows
        ):
            # A hidden carrier may enter only as a certified visible-support
            # column.  Expansion remains downstream of exact VSIR selection.
            return False
        if any(not row.is_proof_carrying for row in rows):
            return False
        if any(
            not (
                row.proof_bundle.validity.layer_order_acyclic
                and row.proof_bundle.topology.valid
                and row.proof_bundle.geometry.valid
                and row.proof_bundle.resource.within_job_budget
            )
            for row in rows
            if row.proof_bundle is not None
        ):
            return False

        group_map = dict(self.group_members)
        selected_ids = {row.id for row in rows}
        for group_id, members in group_map.items():
            if group_id in selected_ids and selected_ids.intersection(members):
                # RepeatGroup is one bundled owning macro in the current CMIR;
                # its independent member alternatives may not double-own or
                # double-score the same authored shapes.
                return False

        # Both sides of a selected shared interface must carry geometry proofs
        # against the same immutable REIR interface.  Candidate validation has
        # already bound the proof interface ids to CMIR ownership.
        for index, first in enumerate(rows):
            first_interfaces = set(first.boundary_interfaces)
            for second in rows[index + 1:]:
                if not first_interfaces.intersection(second.boundary_interfaces):
                    continue
                if (
                    first.proof_bundle is None or second.proof_bundle is None
                    or not first.proof_bundle.geometry.directional_interval_feasible
                    or not second.proof_bundle.geometry.directional_interval_feasible
                ):
                    return False

        estimate = [row.resource_estimate for row in rows]
        proof_resources = [
            row.proof_bundle.resource for row in rows
            if row.proof_bundle is not None
        ]
        return bool(
            sum(row.fitting_ms for row in estimate) <= self.limits.fitting_ms
            and sum(row.render_pixels for row in proof_resources)
            <= self.limits.render_pixels
            and sum(row.memory_bytes for row in estimate)
            <= self.limits.memory_bytes
            and sum(row.solver_variables for row in estimate)
            <= self.limits.solver_variables
        )

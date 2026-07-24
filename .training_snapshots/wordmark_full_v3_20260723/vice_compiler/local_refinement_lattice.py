"""Transactional materialisation of typed boundaries into a bounded CMIR lattice.

The initial hierarchy is intentionally coarse.  A court-certified typed macro
may split a crossed cell, but rejected candidates must leave REIR untouched.
This module materialises only accepted refinement transactions into a derived
CMIR: every child gets an atomic fallback and typed ownership is remapped onto
the child cells.  The immutable REIR remains unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib

import cv2
import numpy as np

from .certificates import seal_bundle, topology_signature
from .evidence_ir import RasterEvidenceIR
from .macro_ir import (
    SCHEMA, CandidateMacroIR, MacroCandidate, MacroCertificates, MacroKind,
    ResourceEstimate, SceneProgram, ScoreBounds, registry_digest,
    stable_macro_id,
)
from .macro_registry import encode_mask_rle
from .native_core import conflict_masks as native_conflict_masks
from .production_court import RuntimeMacroCourt


@dataclass(frozen=True)
class LocalRefinementAudit:
    initial_cells: int
    final_cells: int
    planned_candidates: int
    materialized_candidate_ids: tuple[str, ...]
    skipped_candidate_ids: tuple[str, ...]
    maximum_cells: int
    labels_sha256: str
    provenance: tuple[str, ...]


@dataclass(frozen=True)
class LocalRefinementResult:
    cmir: CandidateMacroIR
    audit: LocalRefinementAudit


def _bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    return (
        int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1,
    )


def _split_labels(
    labels: np.ndarray, parents: tuple[int, ...], boundary_owner: np.ndarray,
) -> tuple[np.ndarray, tuple[int, ...], bool]:
    """Split every current cell by one candidate's inside/outside partition."""
    output = np.full(labels.shape, -1, np.int32)
    next_parents: list[int] = []
    changed = False
    for cell_id, parent in enumerate(parents):
        cell = labels == cell_id
        parts = (cell & boundary_owner, cell & ~boundary_owner)
        emitted = 0
        for part in parts:
            if not np.any(part):
                continue
            count, component_labels, stats, _ = cv2.connectedComponentsWithStats(
                part.astype(np.uint8), connectivity=4,
            )
            for component in range(1, count):
                if int(stats[component, cv2.CC_STAT_AREA]) <= 0:
                    continue
                output[component_labels == component] = len(next_parents)
                next_parents.append(parent); emitted += 1
        changed |= emitted >= 2
    if np.any(output < 0):
        raise RuntimeError("local refinement failed to preserve the cell partition")
    return output, tuple(next_parents), changed


def _atomic_child(
    reir: RasterEvidenceIR, cell_id: int, parent_leaf: int, mask: np.ndarray,
) -> MacroCandidate:
    area = int(mask.sum())
    payload = {
        "source": reir.source_sha256, "cell": cell_id,
        "parent": parent_leaf,
        "support": hashlib.sha256(
            np.packbits(mask, bitorder="little").tobytes()
        ).hexdigest(),
    }
    return MacroCandidate(
        id=stable_macro_id("atomic-refined", payload), registry_index=-1,
        kind=MacroKind.ATOMIC_FALLBACK, family="fallback",
        roi_xyxy=_bbox(mask), core_bits=1 << cell_id,
        alpha_bounds=(
            float(np.min(reir.raster.straight_rgba[..., 3][mask])),
            float(np.max(reir.raster.straight_rgba[..., 3][mask])),
        ),
        boundary_interfaces=(), soft_evidence=(), hidden_geometry=None,
        program=SceneProgram("AtomicRefinedFallback", (
            ("cell_id", cell_id), ("parent_leaf_id", parent_leaf),
        )),
        continuous_params=(), covariance=(),
        certificates=MacroCertificates(
            valid=True, support_source="transactional-refined-core-cell",
            support_size=(reir.width, reir.height),
            support_rle=encode_mask_rle(mask),
            components=topology_signature(mask)[0],
            holes=topology_signature(mask)[1],
            notes=("always-feasible", "derived-REIR-not-source-mutation"),
        ),
        conflict_bits=0, prerequisite_claims=(),
        score_bounds=ScoreBounds(0.0, 0.0, 0.0),
        resource_estimate=ResourceEstimate(0.0, area, 96, 1),
        provenance=(
            "mandatory-refined-atomic-fallback",
            f"parent-hierarchy-leaf={parent_leaf}",
        ),
    )


def _remap_proof(
    candidate: MacroCandidate, core_bits: int, *, refined: bool,
) -> MacroCandidate:
    extra_variables = max(0, core_bits.bit_count() - candidate.core_bits.bit_count())
    estimate = replace(
        candidate.resource_estimate,
        solver_variables=candidate.resource_estimate.solver_variables + extra_variables,
    )
    proof = candidate.proof_bundle
    if proof is not None:
        support = replace(
            proof.support, core_bits=int(core_bits),
            provenance=(*proof.support.provenance, "local-cell-lattice-remap"),
        )
        resource = replace(
            proof.resource,
            solver_variables=proof.resource.solver_variables + extra_variables,
        )
        proof = seal_bundle(replace(
            proof, support=support, resource=resource, digest="",
            provenance=(*proof.provenance, "transactional-local-cell-refinement"),
        ))
    claims = candidate.prerequisite_claims
    provenance = candidate.provenance
    if refined:
        claims = (*claims, "local-cell-refinement-certified")
        provenance = (*provenance, "selected-boundary-materialized-as-child-cells")
    return replace(
        candidate, registry_index=-1, conflict_bits=0,
        core_bits=int(core_bits), resource_estimate=estimate,
        prerequisite_claims=claims, provenance=provenance,
        proof_bundle=proof,
    )


def _derived_interface_endpoints(
    labels: np.ndarray,
) -> tuple[tuple[int, int], ...]:
    """Return every 4-neighbour child-cell interface exactly once."""
    pairs: set[tuple[int, int]] = set()
    for first, second in (
        (labels[:, :-1], labels[:, 1:]),
        (labels[:-1, :], labels[1:, :]),
    ):
        changed = first != second
        for left, right in zip(first[changed].tolist(), second[changed].tolist()):
            a, b = sorted((int(left), int(right)))
            if a != b:
                pairs.add((a, b))
    return tuple(sorted(pairs))


def _crossing_interface_ids(
    core_bits: int, endpoints: tuple[tuple[int, int], ...],
) -> tuple[int, ...]:
    return tuple(
        interface_id
        for interface_id, (first, second) in enumerate(endpoints)
        if bool(core_bits & (1 << first)) != bool(core_bits & (1 << second))
    )


def _remap_interfaces(
    candidate: MacroCandidate, endpoints: tuple[tuple[int, int], ...],
) -> MacroCandidate:
    """Bind a remapped candidate and its proof to the derived half-edge IR."""
    interface_ids = _crossing_interface_ids(candidate.core_bits, endpoints)
    proof = candidate.proof_bundle
    if proof is not None:
        support = replace(
            proof.support,
            interface_ids=interface_ids,
            provenance=(
                *proof.support.provenance,
                "derived-interface-factor-remap",
            ),
        )
        proof = seal_bundle(replace(
            proof,
            support=support,
            digest="",
            provenance=(
                *proof.provenance,
                "derived-interface-factor-remap",
            ),
        ))
    return replace(
        candidate,
        boundary_interfaces=interface_ids,
        provenance=(*candidate.provenance, "derived-half-edge-interface-ir"),
        proof_bundle=proof,
    )


def remap_candidate_core_ownership(
    candidate: MacroCandidate, core_bits: int, *, refined: bool = True,
) -> MacroCandidate:
    """Public proof-preserving ownership remap for a fixed child lattice."""
    return _remap_proof(candidate, core_bits, refined=refined)


def materialize_local_refinements(
    reir: RasterEvidenceIR, certified_cmir: CandidateMacroIR,
    court: RuntimeMacroCourt, *, maximum_cells: int = 512,
) -> LocalRefinementResult:
    """Build a bounded derived lattice from accepted court transactions."""
    initial = reir.hierarchy.leaf_count
    maximum = max(initial, int(maximum_cells))
    ownership_lookup = getattr(court, "ownership_mask", court.delivery_mask)
    typed = tuple(
        candidate for candidate in certified_cmir.candidates
        if not candidate.is_base and candidate.is_proof_carrying
    )
    # Every certified visible delivery is an ownership proposal, even when
    # the older boundary-only planner reported that it did not cut one of the
    # boundary-stripped core cells.  Such a proposal may still span many
    # hierarchy leaves.  Keeping its original ``core_bits`` would let export
    # paint outside the master exact cover.
    planned = tuple(
        candidate for candidate in typed
        if ownership_lookup(candidate.id) is not None
    )
    labels = np.asarray(reir.hierarchy.leaf_labels, np.int32).copy()
    parents = tuple(range(initial))
    inserted: set[str] = set()
    budget_rejected: set[str] = set()
    # Stronger columns get first claim on the bounded arrangement.  Ties are
    # stable, making the derived registry deterministic.
    for candidate in sorted(
        planned, key=lambda row: (-row.score_bounds.lower, row.id),
    ):
        delivery = np.asarray(ownership_lookup(candidate.id), bool)
        proposed, proposed_parents, changed = _split_labels(
            labels, parents, delivery,
        )
        if not changed:
            # The ownership boundary is already a union of current cells.
            # It still needs an exact core remap below.
            continue
        if len(proposed_parents) > maximum:
            budget_rejected.add(candidate.id); continue
        labels = proposed; parents = proposed_parents
        inserted.add(candidate.id)

    unit_masks = tuple(labels == cell_id for cell_id in range(len(parents)))
    drafts: list[MacroCandidate] = [
        _atomic_child(reir, cell_id, parents[cell_id], mask)
        for cell_id, mask in enumerate(unit_masks)
    ]
    # Keep a frozen whole-scene Best column as immutable underlay metadata.
    # The refined-lattice base solver ignores non-atomic multi-cell columns,
    # while the SVG writer can still reproduce the exact incumbent outside
    # typed replacement ownership instead of silently falling back to T1.
    legacy = tuple(
        candidate for candidate in certified_cmir.candidates
        if candidate.program.operator == "LegacyBestScene"
    )
    full_bits = (1 << len(parents)) - 1
    drafts.extend(
        _remap_proof(candidate, full_bits, refined=False)
        for candidate in legacy
    )
    materialized: set[str] = set()
    skipped: set[str] = set()
    for candidate in typed:
        raw_ownership = ownership_lookup(candidate.id)
        if raw_ownership is None:
            skipped.add(candidate.id)
            continue
        ownership = np.asarray(raw_ownership, bool)
        if ownership.shape != labels.shape or not np.any(ownership):
            skipped.add(candidate.id)
            continue
        bits = 0
        reconstructed = np.zeros_like(ownership)
        representable = True
        for cell_id, mask in enumerate(unit_masks):
            intersection = int(np.sum(mask & ownership))
            if intersection == 0:
                continue
            if intersection != int(mask.sum()):
                representable = False
                break
            bits |= 1 << cell_id
            reconstructed |= mask
        # Never retain a typed column whose production ownership is only
        # approximately represented.  A majority remap is not proof of exact
        # cover and was the source of whole-scene paint leakage.
        if (
            not representable
            or not bits
            or not np.array_equal(reconstructed, ownership)
        ):
            skipped.add(candidate.id)
            continue
        materialized.add(candidate.id)
        drafts.append(_remap_proof(candidate, bits, refined=True))

    skipped.update(budget_rejected - materialized)

    # If every ownership already matched the source hierarchy and no column
    # changed its core, preserve the original registry verbatim.
    if not inserted and not skipped and all(
        next(row for row in drafts if row.id == candidate.id).core_bits
        == candidate.core_bits
        for candidate in typed
    ):
        digest = hashlib.sha256(labels.tobytes()).hexdigest()
        return LocalRefinementResult(
            cmir=certified_cmir,
            audit=LocalRefinementAudit(
                initial_cells=initial, final_cells=initial,
                planned_candidates=len(planned), materialized_candidate_ids=(),
                skipped_candidate_ids=(), maximum_cells=maximum,
                labels_sha256=digest,
                provenance=("all-certified-ownership-already-exact",),
            ),
        )

    interface_endpoints = _derived_interface_endpoints(labels)
    drafts = [
        _remap_interfaces(candidate, interface_endpoints)
        for candidate in drafts
    ]
    unique = {candidate.id: candidate for candidate in drafts}
    ordered = tuple(unique.values())
    indexed = tuple(
        replace(candidate, registry_index=index, conflict_bits=0)
        for index, candidate in enumerate(ordered)
    )
    conflicts = native_conflict_masks(row.core_bits for row in indexed)
    candidates = tuple(
        replace(row, conflict_bits=int(conflicts[index]))
        for index, row in enumerate(indexed)
    )
    cmir = CandidateMacroIR(
        schema=SCHEMA, source_sha256=reir.source_sha256,
        leaf_count=len(parents),
        interface_count=len(interface_endpoints),
        interface_endpoints=interface_endpoints,
        candidates=candidates,
        atomic_ids=tuple(
            row.id for row in candidates
            if row.kind is MacroKind.ATOMIC_FALLBACK
        ),
        legacy_ids=tuple(
            row.id for row in candidates
            if row.program.operator == "LegacyBestScene"
        ), registry_hash=registry_digest(candidates, interface_endpoints),
        provenance=(
            *certified_cmir.provenance,
            "transactional-local-cell-refinement-lattice",
            "derived-half-edge-interface-ir",
            f"initial-cells={initial}", f"final-cells={len(parents)}",
        ),
    )
    cmir.validate()
    frozen_labels = np.ascontiguousarray(labels, np.int32)
    digest = hashlib.sha256(frozen_labels.tobytes()).hexdigest()
    return LocalRefinementResult(
        cmir=cmir,
        audit=LocalRefinementAudit(
            initial_cells=initial, final_cells=len(parents),
                planned_candidates=len(planned),
                materialized_candidate_ids=tuple(sorted(materialized)),
                skipped_candidate_ids=tuple(sorted(skipped)),
            maximum_cells=maximum, labels_sha256=digest,
            provenance=(
                "candidate-boundary-inserted-only-after-local-court",
                "every-visible-delivery-remapped-to-exact-owner-cells",
                "unrepresentable-delivery-dropped-fail-closed",
                "atomic-child-fallback-for-every-derived-cell",
                "one-derived-interface-factor-per-adjacent-cell-pair",
                "immutable-REIR-preserved",
            ),
        ),
    )

"""Bounded CMIR registry construction and REIR-to-macro adapters."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import math
from typing import Iterable

import cv2
import numpy as np

from .evidence_ir import ProposalToken, RasterEvidenceIR
from .legacy_best import LegacyBestArtifact
from .macro_ir import (
    SCHEMA, CandidateMacroIR, MacroCandidate, MacroCertificates, MacroKind,
    ResourceEstimate, SceneProgram, ScoreBounds, registry_digest,
    stable_macro_id,
)
from .native_core import conflict_masks as native_conflict_masks


def encode_mask_rle(mask: np.ndarray) -> tuple[tuple[int, int], ...]:
    flat = np.asarray(mask, dtype=np.int8).ravel()
    if flat.size == 0 or not np.any(flat):
        return ()
    transitions = np.diff(np.pad(flat, (1, 1), constant_values=0))
    starts = np.flatnonzero(transitions == 1)
    ends = np.flatnonzero(transitions == -1)
    return tuple(
        (int(start), int(end - start))
        for start, end in zip(starts.tolist(), ends.tolist())
    )


def _certificate_support_identity(certificates: MacroCertificates) -> str:
    """Bind a candidate id to exact support, not only coarse REIR cells."""
    digest = hashlib.sha256()
    digest.update(certificates.support_source.encode("utf-8"))
    digest.update(repr(certificates.support_size).encode("ascii"))
    digest.update(repr(certificates.support_rle).encode("ascii"))
    digest.update(certificates.support_bits)
    digest.update(repr((
        certificates.components, certificates.holes,
    )).encode("ascii"))
    return digest.hexdigest()


def decode_token_mask(
    token: ProposalToken, shape: tuple[int, int]
) -> np.ndarray | None:
    width, height = token.support_size
    count = width * height
    if token.support_bits:
        mask = np.unpackbits(
            np.frombuffer(token.support_bits, dtype=np.uint8),
            count=count, bitorder="little",
        ).astype(bool, copy=False).reshape((height, width))
    elif token.support_rle:
        flat = np.zeros(count, dtype=bool)
        for start, length in token.support_rle:
            flat[start:start + length] = True
        mask = flat.reshape((height, width))
    else:
        return None
    if mask.shape != shape:
        mask = cv2.resize(
            mask.astype(np.uint8), (shape[1], shape[0]),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    return mask


def descendant_leaf_bits(reir: RasterEvidenceIR) -> tuple[int, ...]:
    result: list[int] = []
    for node in reir.hierarchy.nodes:
        if node.left is None:
            bits = 1 << node.id
        else:
            bits = result[node.left] | result[node.right]
        result.append(bits)
    return tuple(result)


def mask_to_leaf_bits(
    reir: RasterEvidenceIR, mask: np.ndarray, *, minimum_fraction: float = 0.50,
) -> int:
    labels = reir.hierarchy.leaf_labels
    if mask.shape != labels.shape:
        mask = cv2.resize(
            mask.astype(np.uint8), (labels.shape[1], labels.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    leaf_count = reir.hierarchy.leaf_count
    areas = np.bincount(labels.ravel(), minlength=leaf_count)
    intersections = np.bincount(labels[mask], minlength=leaf_count)
    bits = 0
    for leaf_id in range(leaf_count):
        # Exact visible ownership cannot be inferred from a small incidental
        # overlap.  The old 15% rule made a large foreground carrier claim
        # boundary/background cells and conflict with unrelated tiny details.
        # Majority support is the conservative proof wall; the single best
        # cell fallback below keeps very thin proposals representable without
        # weakening every ordinary ownership claim.
        if intersections[leaf_id] > 0 and (
            intersections[leaf_id] / max(1, areas[leaf_id]) >= minimum_fraction
        ):
            bits |= 1 << leaf_id
    if bits == 0 and np.any(mask):
        best = int(np.argmax(intersections))
        if intersections[best] > 0:
            bits = 1 << best
    return bits


def leaf_bits_mask(reir: RasterEvidenceIR, bits: int) -> np.ndarray:
    leaf_ids = [index for index in range(reir.hierarchy.leaf_count)
                if bits & (1 << index)]
    return np.isin(reir.hierarchy.leaf_labels, leaf_ids)


def crossing_interfaces(reir: RasterEvidenceIR, core_bits: int) -> tuple[int, ...]:
    result = []
    for interface in reir.interfaces.interfaces:
        first = bool(core_bits & (1 << interface.cell_a))
        second = bool(core_bits & (1 << interface.cell_b))
        if first != second:
            result.append(interface.id)
    return tuple(result)


def kind_for_family(family: str) -> MacroKind:
    if family == "text":
        return MacroKind.TEXT_LINE
    if family in {"shape", "component", "symmetry"}:
        return MacroKind.SHAPE
    if family == "stroke":
        return MacroKind.STROKE_NETWORK
    if family == "layer":
        return MacroKind.LAYER
    if family == "gradient":
        return MacroKind.GRADIENT
    if family == "codec_detail":
        return MacroKind.CODEC_DETAIL
    return MacroKind.GENERIC_REGION


def _draft_candidate(
    *, prefix: str, kind: MacroKind, family: str,
    roi_xyxy: tuple[int, int, int, int], core_bits: int,
    alpha_bounds: tuple[float, float],
    interfaces: tuple[int, ...], soft_evidence: tuple[int, ...],
    program: SceneProgram, certificates: MacroCertificates,
    score: ScoreBounds, resource: ResourceEstimate,
    provenance: tuple[str, ...],
) -> MacroCandidate:
    payload = {
        "kind": kind.value, "family": family, "roi": roi_xyxy,
        "core_bits": str(core_bits), "evidence": soft_evidence,
        "program": program.operator, "provenance": provenance,
        "support": _certificate_support_identity(certificates),
    }
    return MacroCandidate(
        id=stable_macro_id(prefix, payload), registry_index=-1,
        kind=kind, family=family, roi_xyxy=roi_xyxy,
        core_bits=int(core_bits), alpha_bounds=alpha_bounds,
        boundary_interfaces=interfaces,
        soft_evidence=soft_evidence, hidden_geometry=None,
        program=program, continuous_params=(), covariance=(),
        certificates=certificates, conflict_bits=0,
        prerequisite_claims=(), score_bounds=score,
        resource_estimate=resource, provenance=provenance,
    )


def rekey_draft_candidate(
    candidate: MacroCandidate, *, prefix: str = "typed",
) -> MacroCandidate:
    """Bind a draft identity to its final immutable program parameters.

    ``candidate_from_support`` cannot know the analytic program that a typed
    generator will attach later.  Rekeying after that attachment prevents two
    different programs over the same coarse REIR cells from aliasing in CMIR.
    Registered/proof-bound candidates may never be rekeyed.
    """
    if candidate.registry_index != -1 or candidate.conflict_bits != 0:
        raise ValueError("only an unregistered draft candidate may be rekeyed")
    if candidate.proof_bundle is not None:
        raise ValueError("proof-bound candidate identity is immutable")
    payload = {
        "kind": candidate.kind.value,
        "family": candidate.family,
        "roi": candidate.roi_xyxy,
        "core_bits": str(candidate.core_bits),
        "evidence": candidate.soft_evidence,
        "program": {
            "operator": candidate.program.operator,
            "parameters": candidate.program.parameters,
        },
        "continuous": candidate.continuous_params,
        "topology": (
            candidate.certificates.components, candidate.certificates.holes,
        ),
        "support": _certificate_support_identity(candidate.certificates),
        "provenance": candidate.provenance,
    }
    return replace(candidate, id=stable_macro_id(prefix, payload))


def atomic_fallback_candidates(reir: RasterEvidenceIR) -> list[MacroCandidate]:
    result: list[MacroCandidate] = []
    for leaf_id in range(reir.hierarchy.leaf_count):
        node = reir.hierarchy.nodes[leaf_id]
        bits = 1 << leaf_id
        alpha = reir.raster.straight_rgba[..., 3][
            reir.hierarchy.leaf_labels == leaf_id
        ]
        result.append(_draft_candidate(
            prefix="atomic", kind=MacroKind.ATOMIC_FALLBACK,
            family="fallback", roi_xyxy=node.bbox_xyxy, core_bits=bits,
            alpha_bounds=(float(np.min(alpha)), float(np.max(alpha))),
            interfaces=crossing_interfaces(reir, bits), soft_evidence=(),
            program=SceneProgram("AtomicRasterFallback", (("leaf_id", leaf_id),)),
            certificates=MacroCertificates(
                valid=True, support_source="reir-core-cell",
                support_size=(reir.width, reir.height),
                notes=("always-feasible",),
            ),
            score=ScoreBounds(0.0, 0.0, 0.0),
            resource=ResourceEstimate(0.0, node.area, 64, 1),
            provenance=("mandatory-atomic-fallback",),
        ))
    return result


def legacy_scene_adapter(
    reir: RasterEvidenceIR, artifact: LegacyBestArtifact | None,
) -> list[MacroCandidate]:
    """Import the real frozen V-ICE Best scene as a transactional fallback.

    The previous implementation relabelled REIR leaves as ``LegacyBest`` even
    though it never read a V-ICE artifact.  That made rollback destructive.
    The real baseline is intentionally one whole-scene column: typed macros
    are still generated independently and atomic fallbacks remain available
    for partial extraction, while a rejected transaction can restore the
    exact production SVG byte-for-byte in semantic content.
    """
    if artifact is None:
        return []
    bits = (1 << reir.hierarchy.leaf_count) - 1
    alpha = reir.raster.straight_rgba[..., 3]
    return [_draft_candidate(
        prefix="legacy-scene", kind=MacroKind.LEGACY_REGION,
        family="legacy", roi_xyxy=(0, 0, reir.width, reir.height),
        core_bits=bits,
        alpha_bounds=(float(np.min(alpha)), float(np.max(alpha))),
        interfaces=(), soft_evidence=(),
        program=SceneProgram("LegacyBestScene", (
            ("svg_path", str(artifact.path)),
            ("svg_sha256", artifact.sha256),
        )),
        certificates=MacroCertificates(
            valid=True, support_source="frozen-v-ice-best-svg",
            support_size=(reir.width, reir.height),
            notes=("whole-scene-transactional-fallback", "vector-only"),
        ),
        score=ScoreBounds(0.001, 0.002, 0.003),
        resource=ResourceEstimate(
            0.0, reir.width * reir.height, artifact.path.stat().st_size, 1,
        ),
        provenance=("V-ICE-Best-frozen-artifact", artifact.sha256),
    )]


def hierarchy_candidates(reir: RasterEvidenceIR) -> list[MacroCandidate]:
    leaf_bits = descendant_leaf_bits(reir)
    result: list[MacroCandidate] = []
    for node in reir.hierarchy.nodes:
        if node.left is None:
            continue
        bits = leaf_bits[node.id]
        alpha = reir.raster.straight_rgba[..., 3][leaf_bits_mask(reir, bits)]
        merge_confidence = float(np.clip(1.0 - node.merge_level, 0.0, 1.0))
        saving = max(0.0, math.log2(max(2, node.leaf_count)))
        expected = 0.004 * saving + 0.012 * merge_confidence
        lower = expected * (0.55 + 0.35 * merge_confidence)
        result.append(_draft_candidate(
            prefix="hierarchy", kind=MacroKind.HIERARCHY_REGION,
            family="generic_region", roi_xyxy=node.bbox_xyxy,
            core_bits=bits, interfaces=crossing_interfaces(reir, bits),
            alpha_bounds=(float(np.min(alpha)), float(np.max(alpha))),
            soft_evidence=(),
            program=SceneProgram("HierarchyRegion", (
                ("node_id", node.id), ("merge_level", node.merge_level),
            )),
            certificates=MacroCertificates(
                valid=True, support_source="ucm-hierarchy-node",
                support_size=(reir.width, reir.height),
                notes=("laminar",),
            ),
            score=ScoreBounds(lower, expected, expected * 1.25 + 1e-6),
            resource=ResourceEstimate(0.01, node.area, 128, 1),
            provenance=("ucm-laminar-hierarchy",),
        ))
    return result


def candidate_from_support(
    reir: RasterEvidenceIR, *, family: str, mask: np.ndarray,
    roi_xyxy: tuple[int, int, int, int], evidence_token_ids: tuple[int, ...],
    score: float, provenance: tuple[str, ...], kind: MacroKind | None = None,
    components: int | None = None, holes: int | None = None,
    prefix: str = "typed",
    core_fraction: float = 0.50,
) -> MacroCandidate | None:
    mask = np.asarray(mask, dtype=bool)
    if mask.shape != (reir.height, reir.width):
        mask = cv2.resize(
            mask.astype(np.uint8), (reir.width, reir.height),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    if not 0.0 < float(core_fraction) <= 1.0:
        raise ValueError("core ownership fraction must lie in (0,1]")
    bits = mask_to_leaf_bits(
        reir, mask, minimum_fraction=float(core_fraction),
    )
    if bits <= 0:
        return None
    bounded_score = float(np.clip(score, 0.0, 4.0))
    macro_kind = kind or kind_for_family(family)
    return _draft_candidate(
        prefix=prefix, kind=macro_kind, family=family,
        roi_xyxy=tuple(int(value) for value in roi_xyxy), core_bits=bits,
        alpha_bounds=(
            float(np.min(reir.raster.straight_rgba[..., 3][mask])),
            float(np.max(reir.raster.straight_rgba[..., 3][mask])),
        ),
        interfaces=crossing_interfaces(reir, bits),
        soft_evidence=evidence_token_ids,
        program=SceneProgram(macro_kind.value, (("family", family),)),
        certificates=MacroCertificates(
            valid=True, support_source="typed-reir-support",
            support_size=(reir.width, reir.height),
            support_rle=encode_mask_rle(mask), components=components,
            holes=holes, evidence_token_ids=evidence_token_ids,
        ),
        score=ScoreBounds(
            bounded_score * 0.72,
            bounded_score,
            bounded_score * 1.18 + 1e-6,
        ),
        resource=ResourceEstimate(
            fitting_ms=0.04 + 0.005 * len(evidence_token_ids),
            render_pixels=max(1, int(mask.sum())), memory_bytes=256,
            solver_variables=1,
        ),
        provenance=provenance,
    )


def candidate_from_token(
    reir: RasterEvidenceIR, token: ProposalToken,
    *, family: str | None = None,
) -> MacroCandidate | None:
    mask = decode_token_mask(token, (reir.height, reir.width))
    if mask is None and token.support_leaf_ids:
        bits = sum(1 << int(value) for value in token.support_leaf_ids)
        mask = leaf_bits_mask(reir, bits)
    if mask is None:
        return None
    output_family = family or token.family
    bits = mask_to_leaf_bits(reir, mask)
    if bits <= 0:
        return None
    # A typed column replacing several atomic/legacy owners earns a bounded
    # structural/MDL saving.  Without it a whole gradient or TextLine can have
    # positive local evidence yet a falsely non-improving reduced cost simply
    # because its support spans many current fallback cells.
    structural_saving = 0.012 * math.log2(max(1, bits.bit_count()))
    score = float(np.clip(token.score + structural_saving, 0.0, 4.0))
    kind = kind_for_family(output_family)
    support_size = (reir.width, reir.height)
    support_rle: tuple[tuple[int, int], ...] = ()
    support_bits = b""
    if token.support_size == support_size:
        support_rle = token.support_rle
        support_bits = token.support_bits
    else:
        support_rle = encode_mask_rle(mask)
    return _draft_candidate(
        prefix="typed", kind=kind, family=output_family,
        roi_xyxy=tuple(int(value) for value in token.bbox_xyxy),
        core_bits=bits, interfaces=crossing_interfaces(reir, bits),
        alpha_bounds=(
            float(np.min(reir.raster.straight_rgba[..., 3][mask])),
            float(np.max(reir.raster.straight_rgba[..., 3][mask])),
        ),
        soft_evidence=(token.id,),
        program=SceneProgram(kind.value, (("family", output_family),)),
        certificates=MacroCertificates(
            valid=True, support_source="typed-reir-support",
            support_size=support_size, support_rle=support_rle,
            support_bits=support_bits, evidence_token_ids=(token.id,),
        ),
        score=ScoreBounds(score * 0.72, score, score * 1.18 + 1e-6),
        resource=ResourceEstimate(
            fitting_ms=0.045, render_pixels=max(1, int(mask.sum())),
            memory_bytes=256, solver_variables=1,
        ),
        provenance=(token.provenance, "typed-token-column"),
    )


def _finalize_registry(
    reir: RasterEvidenceIR, drafts: Iterable[MacroCandidate],
    *, validate: bool = True, leaf_count: int | None = None,
    interface_endpoints: tuple[tuple[int, int], ...] | None = None,
    provenance: tuple[str, ...] | None = None,
) -> CandidateMacroIR:
    unique: dict[str, MacroCandidate] = {}
    for candidate in drafts:
        previous = unique.get(candidate.id)
        if previous is None or candidate.score_bounds.lower > previous.score_bounds.lower:
            unique[candidate.id] = candidate
    ordered_drafts = list(unique.values())
    indexed = [replace(candidate, registry_index=index, conflict_bits=0)
               for index, candidate in enumerate(ordered_drafts)]
    # Packed support intersections are the dominant registry hot loop.  The
    # Rust kernel writes complete symmetric bitsets and has an exact fallback
    # in ``native_core`` for source-only environments.
    conflicts = list(native_conflict_masks(
        candidate.core_bits for candidate in indexed
    ))
    candidates = tuple(
        replace(candidate, conflict_bits=conflicts[index])
        for index, candidate in enumerate(indexed)
    )
    atomic_ids = tuple(candidate.id for candidate in candidates
                       if candidate.kind is MacroKind.ATOMIC_FALLBACK)
    legacy_ids = tuple(candidate.id for candidate in candidates
                       if candidate.kind is MacroKind.LEGACY_REGION)
    endpoints = (
        tuple((row.cell_a, row.cell_b) for row in reir.interfaces.interfaces)
        if interface_endpoints is None else tuple(interface_endpoints)
    )
    cmir = CandidateMacroIR(
        schema=SCHEMA, source_sha256=reir.source_sha256,
        leaf_count=(
            reir.hierarchy.leaf_count if leaf_count is None else int(leaf_count)
        ),
        interface_count=len(endpoints), interface_endpoints=endpoints,
        candidates=candidates, atomic_ids=atomic_ids,
        legacy_ids=legacy_ids,
        registry_hash=registry_digest(candidates, endpoints),
        provenance=(
            ("REIR-v24", "phase2-bounded-registry")
            if provenance is None else tuple(provenance)
        ),
    )
    if validate:
        cmir.validate()
    return cmir


def build_base_registry(
    reir: RasterEvidenceIR, *, legacy_artifact: LegacyBestArtifact | None = None,
) -> CandidateMacroIR:
    drafts = [
        *atomic_fallback_candidates(reir),
        *legacy_scene_adapter(reir, legacy_artifact),
        *hierarchy_candidates(reir),
    ]
    return _finalize_registry(reir, drafts)


def extend_registry(
    reir: RasterEvidenceIR, cmir: CandidateMacroIR,
    additions: Iterable[MacroCandidate], *, validate: bool = True,
) -> CandidateMacroIR:
    return _finalize_registry(
        reir, (*cmir.candidates, *tuple(additions)), validate=validate,
        leaf_count=cmir.leaf_count,
        interface_endpoints=cmir.interface_endpoints,
        provenance=cmir.provenance,
    )

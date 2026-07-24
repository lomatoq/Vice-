"""Phase-5 codec-residue and lost-detail counterfactual macros.

Residuals only create evidence and competing CMIR columns.  They never mutate
the raster, selected program, or future VSIR directly.  Every counterfactual
is scored under one image-level renderer posterior frozen before any locus is
examined.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Iterable, TYPE_CHECKING

import cv2
import numpy as np

from .certificates import mask_sha256, topology_signature
from .evidence_ir import RasterEvidenceIR
from .macro_ir import MacroCandidate, MacroKind, ResourceEstimate, SceneProgram
from .macro_registry import (
    candidate_from_support, decode_token_mask, rekey_draft_candidate,
)
from .renderer_posterior import (
    FixedRendererPosterior, freeze_renderer_posterior, score_log_likelihood,
)

if TYPE_CHECKING:
    from .proposal_net import ProposalQuery


@dataclass(frozen=True)
class CodecLocus:
    id: str
    mask: np.ndarray
    roi_xyxy: tuple[int, int, int, int]
    residual_strength: float
    uncertainty: float
    semantic_relations: tuple[str, ...]
    evidence_token_ids: tuple[int, ...]
    proposal_query_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CodecCounterfactualRecord:
    candidate: MacroCandidate
    locus_id: str
    counterfactual: str
    support_mask: np.ndarray
    render_roi_xyxy: tuple[int, int, int, int]
    rendered_premultiplied_patch: np.ndarray
    posterior_digest: str
    model_mean_nll: tuple[tuple[str, float], ...]
    expected_mean_nll: float
    semantic_relations: tuple[str, ...]

    def validate(self, reir: RasterEvidenceIR, posterior: FixedRendererPosterior) -> None:
        if self.support_mask.shape != (reir.height, reir.width):
            raise ValueError("codec counterfactual support is off lattice")
        if self.support_mask.flags.writeable or self.rendered_premultiplied_patch.flags.writeable:
            raise ValueError("codec counterfactual evidence must be immutable")
        x1, y1, x2, y2 = self.render_roi_xyxy
        if self.rendered_premultiplied_patch.shape != (y2 - y1, x2 - x1, 4):
            raise ValueError("codec counterfactual patch/ROI mismatch")
        if self.posterior_digest != posterior.digest:
            raise ValueError("counterfactual was scored under a different posterior")
        if tuple(row.id for row in posterior.models) != tuple(row[0] for row in self.model_mean_nll):
            raise ValueError("counterfactual did not use every frozen renderer model")
        replace(self.candidate, registry_index=0, conflict_bits=0).validate(
            leaf_count=reir.hierarchy.leaf_count,
            interface_count=len(reir.interfaces.interfaces), candidate_count=1,
        )


@dataclass(frozen=True)
class CodecMacroSet:
    loci: tuple[CodecLocus, ...]
    records: tuple[CodecCounterfactualRecord, ...]
    renderer_posterior: FixedRendererPosterior
    loci_pruned: int
    provenance: tuple[str, ...]

    @property
    def candidates(self) -> tuple[MacroCandidate, ...]:
        return tuple(row.candidate for row in self.records)


def _freeze(array: np.ndarray, dtype: np.dtype | type | None = None) -> np.ndarray:
    result = np.ascontiguousarray(array, dtype=dtype)
    result.setflags(write=False)
    return result


def _bbox(mask: np.ndarray, pad: int = 0) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("cannot bound empty codec locus")
    return (
        max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
        min(mask.shape[1], int(xs.max()) + 1 + pad),
        min(mask.shape[0], int(ys.max()) + 1 + pad),
    )


def _token_masks(reir: RasterEvidenceIR) -> dict[int, np.ndarray]:
    result = {}
    for token in reir.proposal_tokens:
        mask = decode_token_mask(token, (reir.height, reir.width))
        if mask is not None and np.any(mask):
            result[token.id] = mask
    return result


def _semantic_relations(
    reir: RasterEvidenceIR, locus: np.ndarray, token_masks: dict[int, np.ndarray],
    token_areas: dict[int, int], token_families: dict[int, str],
    peer_areas: tuple[int, ...],
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    expanded = cv2.dilate(locus.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    x1, y1, x2, y2 = _bbox(expanded)
    relations = []
    evidence_ids = []
    locus_area = int(locus.sum())
    for token in reir.proposal_tokens:
        mask = token_masks.get(token.id)
        if mask is None:
            continue
        local = mask[y1:y2, x1:x2]
        intersection = int(np.sum(locus[y1:y2, x1:x2] & local))
        containment = intersection / max(1, locus_area)
        token_area = token_areas[token.id]
        area_ratio = token_area / max(1, locus_area)
        if containment < 0.50:
            continue
        tx1, ty1, tx2, ty2 = token.bbox_xyxy
        token_width = max(1, tx2 - tx1); token_height = max(1, ty2 - ty1)
        token_aspect = token_width / token_height
        token_occupancy = token_area / max(1, token_width * token_height)
        accepted = False
        if (
            token.family == "text" and token.score >= 0.65
            and token_aspect >= 1.25 and token_area <= 0.35 * locus.size
            and area_ratio <= 300.0
        ):
            relations.append("text-line-membership")
            accepted = True
        elif (
            token.family == "stroke" and token.score >= 0.62
            and token_occupancy <= 0.50 and area_ratio <= 180.0
        ):
            relations.append("stroke-group-membership")
            accepted = True
        elif (
            token.family == "topology" and token.score >= 0.62
            and area_ratio <= 80.0
        ):
            relations.append("topology-relation")
            accepted = True
        elif (
            token.family == "component" and token.score >= 0.68
            and 1.0 <= area_ratio <= 80.0
        ):
            relations.append("stable-inclusion-tree-node")
            accepted = True
        elif (
            token.family == "shape" and token.score >= 0.66
            and area_ratio <= 150.0
        ):
            relations.append("ideal-shape-relation")
            accepted = True
        elif (
            token.family == "symmetry" and token.score >= 0.68
            and area_ratio <= 160.0
        ):
            relations.append("repeated-family")
            accepted = True
        if accepted:
            evidence_ids.append(token.id)
    # An interior micro-mark with coherent contrast is an engraving relation,
    # not a generic "small pixel" exemption.
    containing = [
        mask for token_id, mask in token_masks.items()
        if token_families[token_id] == "component"
        and 6 * locus_area <= token_areas[token_id] <= 80 * locus_area
        and np.all(mask[locus])
        and np.all(cv2.erode(
            mask.astype(np.uint8), np.ones((3, 3), np.uint8)
        ).astype(bool)[locus])
    ]
    if containing:
        relations.append("engraving-relation")
    return tuple(sorted(set(relations))), tuple(sorted(set(evidence_ids)))


def detect_codec_loci(
    reir: RasterEvidenceIR, *, max_loci: int = 32,
    proposal_queries: Iterable["ProposalQuery"] = (),
) -> tuple[tuple[CodecLocus, ...], int]:
    """Detect ambiguous residual evidence without making a cleanup decision."""
    signal = reir.raster.oklab
    smooth = cv2.GaussianBlur(signal, (0, 0), 1.15, borderType=cv2.BORDER_REPLICATE)
    residual = np.linalg.norm(signal - smooth, axis=2)
    alpha = reir.raster.straight_rgba[..., 3]
    valid = alpha > 0.01
    values = residual[valid]
    if not len(values):
        return (), 0
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    robust_sigma = max(1e-6, 1.4826 * mad)
    threshold = max(median + 3.25 * robust_sigma, float(np.quantile(values, 0.965)))
    boundary = reir.boundary_pyramid[0]
    unstable = (
        (boundary.cross_scale_persistence < 0.58)
        | (boundary.uncertainty > 0.52)
    )
    ambiguous = valid & (residual >= threshold) & unstable
    ambiguous = cv2.morphologyEx(
        ambiguous.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8),
    ) > 0
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        ambiguous.astype(np.uint8), 8,
    )
    components = []
    maximum_area = max(9, int(0.012 * ambiguous.size))
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if 1 <= area <= maximum_area:
            mask = labels == label
            components.append((mask, area, float(np.mean(residual[mask]))))
    total_components = len(components)
    areas = tuple(row[1] for row in components)
    token_masks = _token_masks(reir)
    token_areas = {
        token_id: int(mask.sum()) for token_id, mask in token_masks.items()
    }
    token_families = {
        token.id: token.family for token in reir.proposal_tokens
        if token.id in token_masks
    }
    # The runtime contract permits at most 64 typed ROIs.  Do the cheap,
    # renderer-independent residual ranking first and run semantic joins only
    # on that bounded pool; otherwise JPEG confetti creates O(loci*tokens*N)
    # work before the advertised max_loci limit is applied.
    prelimit = max(1, min(64, max(int(max_loci), 2 * int(max_loci))))
    components.sort(key=lambda row: (-row[2], row[1]))
    components = components[:prelimit]
    rows = []
    for mask, _area, strength in components:
        relations, token_ids = _semantic_relations(
            reir, mask, token_masks, token_areas, token_families, areas,
        )
        uncertainty = float(np.mean(boundary.uncertainty[mask]))
        digest = mask_sha256(mask)[:12]
        frozen = _freeze(mask, bool)
        rows.append(CodecLocus(
            id=f"codec-locus-{digest}", mask=frozen, roi_xyxy=_bbox(mask, 4),
            residual_strength=strength, uncertainty=uncertainty,
            semantic_relations=relations, evidence_token_ids=token_ids,
        ))
    # ProposalNet is a recall oracle, never a cleanup route switch.  Risk
    # queries may add bounded micro-loci before counterfactual fitting, but do
    # not grant semantic keep-detail rights and still face the same fixed
    # renderer posterior and production court as classical residual loci.
    from .proposal_net import query_support_mask
    query_rows = []
    for query in proposal_queries:
        if query.family != "risk_hard_negative":
            continue
        mask = query_support_mask(reir, query, minimum_pixels=1)
        if mask is None:
            continue
        component_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            np.asarray(mask, np.uint8), 8,
        )
        for label in range(1, component_count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if not 1 <= area <= maximum_area:
                continue
            component = labels == label
            digest = mask_sha256(component)[:12]
            strength = float(np.mean(residual[component]))
            uncertainty = float(np.mean(boundary.uncertainty[component]))
            query_rows.append(CodecLocus(
                id=f"codec-locus-{digest}", mask=_freeze(component, bool),
                roi_xyxy=_bbox(component, 4), residual_strength=strength,
                uncertainty=uncertainty, semantic_relations=(),
                evidence_token_ids=(),
                proposal_query_ids=(
                    query.id + (
                        f":{query.hard_negative_class}"
                        if query.hard_negative_class else ""
                    ),
                ),
            ))
    by_digest = {mask_sha256(row.mask): row for row in rows}
    classical_digests = set(by_digest)
    for row in query_rows:
        digest = mask_sha256(row.mask)
        previous = by_digest.get(digest)
        if previous is None:
            by_digest[digest] = row
        else:
            by_digest[digest] = replace(
                previous,
                proposal_query_ids=tuple(sorted(set(
                    previous.proposal_query_ids + row.proposal_query_ids
                ))),
            )
    rows = list(by_digest.values())
    rows.sort(key=lambda row: (
        -bool(row.proposal_query_ids), -row.residual_strength,
        -len(row.semantic_relations), row.id,
    ))
    limit = max(1, min(64, int(max_loci)))
    guided_additions = len({
        mask_sha256(row.mask) for row in query_rows
        if mask_sha256(row.mask) not in classical_digests
    })
    return (
        tuple(rows[:limit]),
        max(0, total_components + guided_additions - limit),
    )


def _weighted_likelihood(
    observed: np.ndarray, rendered: np.ndarray, eval_mask: np.ndarray,
    posterior: FixedRendererPosterior,
) -> tuple[tuple[tuple[str, float], ...], float]:
    rows = []
    expected = 0.0
    for model in posterior.models:
        likelihood = score_log_likelihood(
            observed, rendered, model, support=eval_mask,
        )
        rows.append((model.id, likelihood.mean_robust_nll))
        expected += model.weight * likelihood.mean_robust_nll
    return tuple(rows), float(expected)


def _proposal_patches(
    reir: RasterEvidenceIR, locus: CodecLocus,
) -> list[tuple[str, np.ndarray, tuple[str, ...]]]:
    x1, y1, x2, y2 = locus.roi_xyxy
    observed = reir.raster.linear_premultiplied_rgba[y1:y2, x1:x2]
    local_mask = locus.mask[y1:y2, x1:x2]
    base = cv2.GaussianBlur(observed, (0, 0), 1.0, borderType=cv2.BORDER_REPLICATE)
    removed = observed.copy(); removed[local_mask] = base[local_mask]
    rows = [("remove_halo_confetti", removed, ("residual-cleanup",))]

    # Baseline/atomic columns already preserve raw pixels.  A typed keep macro
    # is earned only by a structural relation listed in section 15.3.
    if locus.semantic_relations:
        rows.append(("keep_detail", observed.copy(), locus.semantic_relations))
    if any(row in locus.semantic_relations for row in (
        "text-line-membership", "stroke-group-membership",
    )):
        rows.append((
            "attach_detail_to_text_stroke", observed.copy(),
            tuple(row for row in locus.semantic_relations if row.endswith("membership")),
        ))
    if any(row in locus.semantic_relations for row in (
        "engraving-relation", "stable-inclusion-tree-node", "topology-relation",
    )):
        rows.append((
            "preserve_engraving", observed.copy(), locus.semantic_relations,
        ))
    if "ideal-shape-relation" in locus.semantic_relations:
        ideal = observed.copy()
        # Symmetric local reconstruction supplies the shape alternative; it is
        # still only a candidate and must win under the fixed posterior/court.
        mirrored = np.flip(np.flip(observed, axis=0), axis=1)
        ideal[local_mask] = 0.5 * (base[local_mask] + mirrored[local_mask])
        rows.append(("restore_ideal_shape", ideal, ("ideal-shape-relation",)))
    return rows


def generate_cleanup_macros(
    reir: RasterEvidenceIR, *, max_loci: int = 32,
    validate_reir: bool = True,
    proposal_queries: Iterable["ProposalQuery"] = (),
) -> CodecMacroSet:
    if validate_reir:
        reir.validate()
    posterior = freeze_renderer_posterior(reir)
    loci, pruned = detect_codec_loci(
        reir, max_loci=max_loci, proposal_queries=proposal_queries,
    )
    records = []
    for locus in loci:
        x1, y1, x2, y2 = locus.roi_xyxy
        observed = reir.raster.linear_premultiplied_rgba[y1:y2, x1:x2]
        local = locus.mask[y1:y2, x1:x2]
        eval_mask = cv2.dilate(local.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        proposals = []
        for name, rendered, relations in _proposal_patches(reir, locus):
            likelihoods, expected_nll = _weighted_likelihood(
                observed, rendered, eval_mask, posterior,
            )
            proposals.append((name, rendered, relations, likelihoods, expected_nll))
        if not proposals:
            continue
        best_nll = min(row[4] for row in proposals)
        for name, rendered, relations, likelihoods, expected_nll in proposals:
            likelihood_quality = math.exp(-min(12.0, max(0.0, expected_nll - best_nll)))
            semantic_strength = min(1.0, 0.22 * len(relations))
            score = float(np.clip(
                0.52 * likelihood_quality + 0.18 * semantic_strength
                + 0.16 * math.exp(-locus.residual_strength / 0.18)
                + 0.14 * (1.0 - locus.uncertainty), 0.0, 1.5,
            ))
            candidate = candidate_from_support(
                reir, family="codec_detail", mask=locus.mask,
                roi_xyxy=locus.roi_xyxy,
                evidence_token_ids=locus.evidence_token_ids,
                score=score, kind=MacroKind.CODEC_DETAIL,
                components=topology_signature(locus.mask)[0],
                holes=topology_signature(locus.mask)[1],
                prefix=f"codec-{name}",
                provenance=(
                    "phase5-codec-counterfactual", f"type:{name}",
                    *(f"proposal-query:{query_id}"
                      for query_id in locus.proposal_query_ids),
                ),
            )
            if candidate is None:
                continue
            parameters: tuple[tuple[str, float | int | str], ...] = (
                ("locus", locus.id), ("posterior", posterior.digest),
                ("relations", ",".join(relations)),
            )
            candidate = replace(
                candidate, program=SceneProgram(f"CodecDetail/{name}", parameters),
                certificates=replace(candidate.certificates, notes=(
                    *candidate.certificates.notes,
                    f"fixed_posterior={posterior.digest}",
                    f"expected_mean_nll={expected_nll:.8f}",
                    "residual-created-candidate-not-route-switch",
                    "no-direct-vsir-mutation",
                )),
                prerequisite_claims=(
                    "single-image-level-degradation-posterior",
                    "counterfactual-competes-in-global-extractor",
                    "semantic-microdetail-rights-only",
                    "residual-never-mutates-vsir",
                ),
                resource_estimate=ResourceEstimate(
                    fitting_ms=0.12 * len(posterior.models),
                    render_pixels=int(eval_mask.sum()), memory_bytes=1024,
                    solver_variables=1,
                ),
            )
            candidate = rekey_draft_candidate(
                candidate, prefix=f"codec-{name}",
            )
            records.append(CodecCounterfactualRecord(
                candidate=candidate, locus_id=locus.id, counterfactual=name,
                support_mask=locus.mask, render_roi_xyxy=locus.roi_xyxy,
                rendered_premultiplied_patch=_freeze(rendered, np.float32),
                posterior_digest=posterior.digest,
                model_mean_nll=likelihoods, expected_mean_nll=expected_nll,
                semantic_relations=relations,
            ))
    final = tuple(sorted(
        records, key=lambda row: (row.locus_id, row.counterfactual, row.candidate.id),
    ))
    for row in final:
        row.validate(reir, posterior)
    return CodecMacroSet(
        loci=loci, records=final, renderer_posterior=posterior,
        loci_pruned=pruned,
        provenance=(
            "residual-evidence-only", "fixed-degradation-posterior",
            "phase5-codec-detail-counterfactuals/v1",
        ),
    )

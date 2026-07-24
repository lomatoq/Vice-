"""Top-K split/merge, hole, containment, and explicit-region hypotheses."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import cv2
import numpy as np

from .appearance import AppearanceHypotheses
from .evidence_model import EvidenceBundle


OUTSIDE = -1


@dataclass(frozen=True)
class RegionProposal:
    id: str
    appearance_index: int
    mask: np.ndarray
    area_px: float
    bbox: tuple[int, int, int, int]
    positive_contour: np.ndarray
    negative_contours: tuple[np.ndarray, ...]
    parent: str | None
    confidence: float
    soft_membership: np.ndarray | None = None


@dataclass(frozen=True)
class AdjacencyEdge:
    region_a: str
    region_b: str
    boundary_length_px: float


@dataclass(frozen=True)
class OcclusionCandidate:
    covered_shape: str
    covering_shape: str
    completion_family: str
    confidence: float


@dataclass(frozen=True)
class TopologyHypothesis:
    id: str
    regions: tuple[RegionProposal, ...]
    label_map: np.ndarray
    background_appearance: int
    score: float
    operations: tuple[str, ...]
    adjacency: tuple[AdjacencyEdge, ...] = ()
    occlusion_candidates: tuple[OcclusionCandidate, ...] = ()

    def validate(self) -> None:
        if self.label_map.ndim != 2 or self.label_map.dtype != np.int32:
            raise ValueError("topology label map must be int32 HxW")
        ids = [region.id for region in self.regions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate topology region ids")
        valid = set(range(len(self.regions))) | {OUTSIDE}
        if not set(int(v) for v in np.unique(self.label_map)).issubset(valid):
            raise ValueError("label map references unknown regions")
        for index, region in enumerate(self.regions):
            if not np.array_equal(self.label_map == index, region.mask):
                raise ValueError(f"region {region.id} mask disagrees with label map")
            expected_soft = (region.bbox[3] - region.bbox[1],
                             region.bbox[2] - region.bbox[0])
            if (region.soft_membership is not None
                    and region.soft_membership.shape != expected_soft):
                raise ValueError(f"region {region.id} soft membership has wrong shape")
        id_set = set(ids)
        for edge in self.adjacency:
            if edge.region_a not in id_set or edge.region_b not in id_set:
                raise ValueError("adjacency references an unknown region")
        for item in self.occlusion_candidates:
            if item.covered_shape not in id_set or item.covering_shape not in id_set:
                raise ValueError("occlusion candidate references an unknown region")


def build_topology_hypotheses(appearances: AppearanceHypotheses,
                              evidence: EvidenceBundle, *, top_k: int = 4,
                              min_area_px: float = 2.0,
                              max_regions: int = 128) -> tuple[TopologyHypothesis, ...]:
    probabilities = appearances.probabilities
    uncertainty = evidence.levels[0].heads["uncertainty"]
    proposals: list[tuple[np.ndarray, tuple[str, ...]]] = []
    raw = np.argmax(probabilities, axis=2).astype(np.int32)
    proposals.append((raw, ("soft-argmax-proposal",)))
    for sigma in (0.65, 1.15):
        blurred = np.stack([cv2.GaussianBlur(probabilities[..., index], (0, 0), sigma)
                            for index in range(probabilities.shape[2])], axis=2)
        proposals.append((np.argmax(blurred, axis=2).astype(np.int32),
                          (f"soft-spatial-proposal-sigma-{sigma:g}",)))
    # A conservative morphology hypothesis acts only inside uncertain bands.
    morph = raw.copy()
    uncertain = uncertainty > 0.55
    kernel = np.ones((3, 3), np.uint8)
    for index in range(probabilities.shape[2]):
        closed = cv2.morphologyEx((raw == index).astype(np.uint8), cv2.MORPH_CLOSE, kernel) > 0
        morph[uncertain & closed] = index
    proposals.append((morph, ("uncertainty-band-close-proposal",)))

    unique: dict[str, TopologyHypothesis] = {}
    for cluster_map, operations in proposals:
        hypothesis = _materialize(
            cluster_map, appearances, evidence.levels[0].heads,
            min_area_px, max_regions, operations)
        key = hashlib.sha1(hypothesis.label_map.tobytes()).hexdigest()
        unique.setdefault(key, hypothesis)
    ranked = sorted(unique.values(), key=lambda item: item.score)
    result = _shortlist_topologies(ranked, top_k)
    for item in result:
        item.validate()
    return result


def _shortlist_topologies(ranked: list[TopologyHypothesis],
                          top_k: int) -> tuple[TopologyHypothesis, ...]:
    """Keep a cheap-score winner plus the canonical detail-preserving scale.

    Topology score is intentionally a cheap pre-court.  Letting it fill the
    entire shortlist with coarse/morphological proposals can prune the only
    hypothesis that preserves separate glyphs before physical rendering sees
    it.  Sigma 0.65 is the bounded middle-scale proposal, not a content route.
    """
    limit = max(1, int(top_k))
    chosen = list(ranked[:limit])
    if limit >= 2:
        balanced = next((item for item in ranked
                         if any(operation == "soft-spatial-proposal-sigma-0.65"
                                for operation in item.operations)), None)
        if (balanced is not None
                and all(item.id != balanced.id for item in chosen)):
            chosen[-1] = balanced
            chosen.sort(key=lambda item: item.score)
    return tuple(chosen)


def _materialize(cluster_map: np.ndarray, appearances: AppearanceHypotheses,
                 evidence_heads: dict[str, np.ndarray], min_area_px: float,
                 max_regions: int, operations: tuple[str, ...]) -> TopologyHypothesis:
    probabilities = appearances.probabilities
    label_map = np.full(cluster_map.shape, OUTSIDE, np.int32)
    raw_regions: list[dict] = []
    for appearance_index in range(probabilities.shape[2]):
        is_background = appearance_index == appearances.background_index
        background_appearance = appearances.appearances[appearance_index]
        # Transparent outside pixels are compositing space, never paint.
        # Opaque border-colour islands, however, can be real white glyphs or
        # knockouts enclosed by artwork and must be allowed into the painter.
        if is_background and background_appearance.rgba_linear[3] < .5:
            continue
        binary = (cluster_map == appearance_index).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
        for component in range(1, count):
            area = float(stats[component, cv2.CC_STAT_AREA])
            mask = labels == component
            if is_background:
                x, y, w, h = (int(v) for v in stats[component, :4])
                if x == 0 or y == 0 or x + w == cluster_map.shape[1] \
                        or y + h == cluster_map.shape[0]:
                    continue
            text_support = float(np.mean(np.maximum(
                evidence_heads["text_line_prob"][mask],
                evidence_heads["glyph_occupancy"][mask],
            ))) if np.any(mask) else 0.0
            corner_support = float(np.mean(evidence_heads["corner_prob"][mask])) if np.any(mask) else 0.0
            protected = max(text_support, .75 * corner_support)
            # One-pixel components survive only with explicit glyph/corner
            # evidence.  This removes codec barnacles without erasing tiny text.
            if area + 1e-9 < min_area_px and protected < .38:
                continue
            contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP,
                                                    cv2.CHAIN_APPROX_NONE)
            if not contours:
                continue
            hierarchy_row = hierarchy[0] if hierarchy is not None else np.empty((0, 4), int)
            outer_indices = [i for i, row in enumerate(hierarchy_row) if row[3] < 0]
            outer_index = max(outer_indices or range(len(contours)), key=lambda i: abs(cv2.contourArea(contours[i])))
            positive = contours[outer_index][:, 0, :].astype(np.float32) + 0.5
            holes = tuple(contours[i][:, 0, :].astype(np.float32) + 0.5
                          for i, row in enumerate(hierarchy_row) if row[3] == outer_index)
            x, y, w, h = (int(v) for v in stats[component, :4])
            confidence = float(np.mean(probabilities[..., appearance_index][mask]))
            raw_regions.append({
                "appearance_index": appearance_index, "mask": mask,
                "area": area, "bbox": (x, y, x + w, y + h),
                "positive": positive, "holes": holes, "confidence": confidence,
                "protected": protected,
                "soft": (probabilities[y:y + h, x:x + w, appearance_index]
                         * cv2.dilate(mask[y:y + h, x:x + w].astype(np.uint8),
                                      np.ones((3, 3), np.uint8))),
            })
    if len(raw_regions) > max_regions:
        raw_regions = sorted(
            raw_regions,
            key=lambda row: (-row["protected"], -row["confidence"], -row["area"],
                             row["bbox"], row["appearance_index"]),
        )[:max_regions]
    # Stable visual order: large underpainting first, smaller nested/top layers later.
    raw_regions.sort(key=lambda row: (-row["area"], row["bbox"], row["appearance_index"]))
    parents: list[str | None] = [None] * len(raw_regions)
    ids = [f"topology-region-{index}" for index in range(len(raw_regions))]
    for child_index, child in enumerate(raw_regions):
        candidates = []
        child_samples = child["positive"][::max(1, len(child["positive"]) // 24)]
        for parent_index, parent in enumerate(raw_regions):
            if parent["area"] <= child["area"] or parent_index == child_index:
                continue
            px0, py0, px1, py1 = parent["bbox"]
            cx = float(np.mean(child_samples[:, 0]))
            cy = float(np.mean(child_samples[:, 1]))
            inside = (px0 <= cx <= px1 and py0 <= cy <= py1
                      and cv2.pointPolygonTest(parent["positive"].astype(np.float32),
                                               (cx, cy), False) >= 0)
            if inside:
                candidates.append((parent["area"], parent_index))
        if candidates:
            parents[child_index] = ids[min(candidates)[1]]
    regions: list[RegionProposal] = []
    for index, row in enumerate(raw_regions):
        label_map[row["mask"]] = index
        regions.append(RegionProposal(
            id=ids[index], appearance_index=row["appearance_index"], mask=row["mask"],
            area_px=row["area"], bbox=row["bbox"], positive_contour=row["positive"],
            negative_contours=row["holes"], parent=parents[index],
            confidence=row["confidence"], soft_membership=row["soft"].astype(np.float32),
        ))
    assigned = label_map >= 0
    # Confidence of the appearance evidence itself.  Proposal-specific
    # departures (including blur-driven merges) are judged by the full
    # physical forward court; charging them here as well strongly biases the
    # shortlist toward raw noisy argmax fragments.
    chosen_prob = np.max(probabilities, axis=2)
    data_cost = float(np.mean(-np.log(np.clip(chosen_prob, 1e-7, 1.0))))
    complexity = 0.0015 * len(regions)
    unsupported = float(np.mean((cluster_map != appearances.background_index) & ~assigned))
    score = data_cost + complexity + 0.2 * unsupported
    adjacency_counts: dict[tuple[int, int], int] = {}
    for left, right in ((label_map[:, :-1], label_map[:, 1:]),
                        (label_map[:-1, :], label_map[1:, :])):
        changed = (left != right) & (left >= 0) & (right >= 0)
        for a, b in zip(left[changed], right[changed]):
            pair = (min(int(a), int(b)), max(int(a), int(b)))
            adjacency_counts[pair] = adjacency_counts.get(pair, 0) + 1
    adjacency = tuple(AdjacencyEdge(ids[a], ids[b], float(length))
                      for (a, b), length in sorted(adjacency_counts.items()))
    occlusion = []
    for child_index, parent_id in enumerate(parents):
        if parent_id is not None:
            parent_index = ids.index(parent_id)
            confidence = float(min(raw_regions[child_index]["confidence"],
                                   raw_regions[parent_index]["confidence"]))
            occlusion.append(OcclusionCandidate(
                covered_shape=parent_id, covering_shape=ids[child_index],
                completion_family="unknown-or-parameterized", confidence=confidence,
            ))
    # Every real shared interface is also a bounded two-way occlusion proposal;
    # the global court, not the component builder, chooses draw order.
    for edge in adjacency:
        first = ids.index(edge.region_a)
        second = ids.index(edge.region_b)
        confidence = float(min(raw_regions[first]["confidence"],
                               raw_regions[second]["confidence"]))
        for covered, covering in ((edge.region_a, edge.region_b),
                                  (edge.region_b, edge.region_a)):
            row = OcclusionCandidate(covered, covering,
                                     "adjacent-hidden-shape-completion",
                                     .5 * confidence)
            if row not in occlusion:
                occlusion.append(row)
    return TopologyHypothesis(
        id="topology-" + hashlib.sha1(label_map.tobytes()).hexdigest()[:12],
        regions=tuple(regions), label_map=label_map,
        background_appearance=appearances.background_index,
        score=score, operations=operations, adjacency=adjacency,
        occlusion_candidates=tuple(occlusion),
    )

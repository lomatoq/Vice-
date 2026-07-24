"""Core-cell, uncertain boundary-band, and microfeature construction."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .hierarchy import RegionHierarchy


@dataclass(frozen=True)
class CoreCell:
    id: int
    leaf_id: int
    area: int
    core_area: int
    bbox_xyxy: tuple[int, int, int, int]
    mean_linear_premul_rgba: tuple[float, float, float, float]
    membership_confidence: float
    uncertainty: float
    provenance: str


@dataclass(frozen=True)
class BoundaryBand:
    id: int
    bbox_xyxy: tuple[int, int, int, int]
    area: int
    mean_probability: float
    max_probability: float
    uncertainty: float
    provenance: str


@dataclass(frozen=True)
class MicrofeatureToken:
    id: int
    bbox_xyxy: tuple[int, int, int, int]
    area: int
    strength: float
    persistence: float
    kind: str
    uncertainty: float
    provenance: str


@dataclass(frozen=True)
class CellComplex:
    core_labels: np.ndarray
    boundary_mask: np.ndarray
    cells: tuple[CoreCell, ...]
    boundary_bands: tuple[BoundaryBand, ...]
    microfeatures: tuple[MicrofeatureToken, ...]

    def validate(self) -> None:
        if self.core_labels.shape != self.boundary_mask.shape:
            raise ValueError("cell/boundary shape mismatch")
        if np.any((self.core_labels >= 0) & self.boundary_mask):
            raise ValueError("boundary pixels cannot have committed core ownership")


@dataclass(frozen=True)
class RefinementChild:
    local_id: int
    parent_leaf_id: int
    area: int
    bbox_xyxy: tuple[int, int, int, int]


@dataclass(frozen=True)
class CellRefinementTransaction:
    """Non-materialized local split proposed by a typed macro boundary."""

    roi_xyxy: tuple[int, int, int, int]
    candidate_boundary: np.ndarray
    child_labels: np.ndarray
    children: tuple[RefinementChild, ...]
    accepted: bool
    reason: str
    minimum_support: int
    provenance: str

    def validate(self) -> None:
        if self.candidate_boundary.shape != self.child_labels.shape:
            raise ValueError("refinement boundary/label shape mismatch")
        if self.accepted and len(self.children) < 2:
            raise ValueError("accepted refinement did not create child cells")
        if self.accepted and any(
            child.area < self.minimum_support for child in self.children
        ):
            raise ValueError("refinement child violates minimum support")
        if self.candidate_boundary.flags.writeable or self.child_labels.flags.writeable:
            raise ValueError("refinement transaction arrays must be immutable")


def plan_local_refinement(
    complex_: CellComplex,
    candidate_boundary: np.ndarray,
    roi_xyxy: tuple[int, int, int, int],
    *,
    minimum_support: int = 2,
    provenance: str = "typed-macro-candidate-boundary",
) -> CellRefinementTransaction:
    """Intersect one candidate boundary with the cell complex inside its ROI.

    The source ``CellComplex`` is never mutated.  CMIR extraction may
    materialize this transaction only if the owning macro is selected.
    """

    height, width = complex_.core_labels.shape
    x1, y1, x2, y2 = (int(value) for value in roi_xyxy)
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("refinement ROI is outside the processing lattice")
    boundary = np.asarray(candidate_boundary, dtype=bool)
    roi_shape = (y2 - y1, x2 - x1)
    if boundary.shape == (height, width):
        boundary = boundary[y1:y2, x1:x2]
    elif boundary.shape != roi_shape:
        raise ValueError("candidate boundary must match the ROI or full lattice")
    boundary = np.ascontiguousarray(boundary)
    parent_labels = complex_.core_labels[y1:y2, x1:x2]
    split_labels = np.full(roi_shape, -1, dtype=np.int32)
    children: list[RefinementChild] = []
    split_parent_count = 0
    for parent in np.unique(parent_labels[parent_labels >= 0]):
        parent_mask = (parent_labels == parent) & ~boundary
        count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            parent_mask.astype(np.uint8), connectivity=4
        )
        components: list[tuple[int, int]] = []
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area > 0:
                components.append((label, area))
        if len(components) >= 2:
            split_parent_count += 1
        for label, area in components:
            local_id = len(children)
            component = labels == label
            split_labels[component] = local_id
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            w = int(stats[label, cv2.CC_STAT_WIDTH])
            h = int(stats[label, cv2.CC_STAT_HEIGHT])
            children.append(
                RefinementChild(
                    local_id=local_id,
                    parent_leaf_id=int(parent),
                    area=area,
                    bbox_xyxy=(x1 + x, y1 + y, x1 + x + w, y1 + y + h),
                )
            )
    parent_child_counts = {
        parent: sum(child.parent_leaf_id == parent for child in children)
        for parent in {child.parent_leaf_id for child in children}
    }
    too_small = any(
        parent_child_counts[child.parent_leaf_id] >= 2
        and child.area < minimum_support
        for child in children
    )
    accepted = split_parent_count > 0 and not too_small
    reason = (
        "accepted" if accepted
        else "minimum_support" if too_small
        else "candidate_does_not_split_a_core_cell"
    )
    boundary.setflags(write=False); split_labels.setflags(write=False)
    transaction = CellRefinementTransaction(
        roi_xyxy=(x1, y1, x2, y2),
        candidate_boundary=boundary,
        child_labels=split_labels,
        children=tuple(children),
        accepted=accepted,
        reason=reason,
        minimum_support=int(minimum_support),
        provenance=provenance,
    )
    transaction.validate()
    return transaction


def _bbox_from_stats(stats: np.ndarray, label: int) -> tuple[int, int, int, int]:
    x, y, width, height, _area = (int(value) for value in stats[label])
    return x, y, x + width, y + height


def build_cell_complex(
    hierarchy: RegionHierarchy,
    boundary_probability: np.ndarray,
    linear_premul_rgba: np.ndarray,
    *,
    boundary_threshold: float = 0.24,
) -> CellComplex:
    labels = hierarchy.leaf_labels
    if labels.shape != boundary_probability.shape:
        raise ValueError("hierarchy/boundary shape mismatch")
    threshold = max(
        float(boundary_threshold),
        float(np.quantile(boundary_probability, 0.82)) * 0.72,
    )
    raw_boundary = boundary_probability >= min(threshold, 0.8)
    kernel = np.ones((3, 3), np.uint8)
    boundary_mask = cv2.dilate(raw_boundary.astype(np.uint8), kernel) > 0
    core_labels = labels.copy()
    core_labels[boundary_mask] = -1
    cell_count = hierarchy.leaf_count
    flat_labels = labels.ravel()
    area_by_leaf = np.bincount(flat_labels, minlength=cell_count)
    valid_core = core_labels.ravel() >= 0
    core_area_by_leaf = np.bincount(
        core_labels.ravel()[valid_core], minlength=cell_count
    )
    color_sums = np.stack(
        [
            np.bincount(
                flat_labels,
                weights=linear_premul_rgba[..., channel].ravel(),
                minlength=cell_count,
            )
            for channel in range(4)
        ],
        axis=1,
    )
    cells: list[CoreCell] = []
    for leaf_id in range(cell_count):
        area = int(area_by_leaf[leaf_id])
        if area <= 0:
            continue
        core_area = int(core_area_by_leaf[leaf_id])
        mean = color_sums[leaf_id] / area
        leaf = hierarchy.nodes[leaf_id]
        cells.append(
            CoreCell(
                id=len(cells),
                leaf_id=leaf_id,
                area=area,
                core_area=core_area,
                bbox_xyxy=leaf.bbox_xyxy,
                mean_linear_premul_rgba=tuple(float(v) for v in mean),
                membership_confidence=float(core_area / max(1, area)),
                uncertainty=float(1.0 - core_area / max(1, area)),
                provenance="watershed-leaf-minus-oriented-boundary-band",
            )
        )
    band_count, band_labels, band_stats, _ = cv2.connectedComponentsWithStats(
        boundary_mask.astype(np.uint8), connectivity=8
    )
    bands: list[BoundaryBand] = []
    for label in range(1, band_count):
        area = int(band_stats[label, cv2.CC_STAT_AREA])
        if area <= 0:
            continue
        values = boundary_probability[band_labels == label]
        bands.append(
            BoundaryBand(
                id=len(bands),
                bbox_xyxy=_bbox_from_stats(band_stats, label),
                area=area,
                mean_probability=float(values.mean()),
                max_probability=float(values.max()),
                uncertainty=float(np.clip(1.0 - values.mean(), 0.0, 1.0)),
                provenance="oriented-boundary-pyramid+ucm",
            )
        )
    strong = (boundary_probability >= max(0.32, float(np.quantile(boundary_probability, 0.9)))).astype(np.uint8)
    micro_count, micro_labels, micro_stats, _ = cv2.connectedComponentsWithStats(
        strong, connectivity=8
    )
    microfeatures: list[MicrofeatureToken] = []
    for label in range(1, micro_count):
        area = int(micro_stats[label, cv2.CC_STAT_AREA])
        x, y, width, height, _ = (int(v) for v in micro_stats[label])
        if area > 32 or max(width, height) > 14:
            continue
        values = boundary_probability[micro_labels == label]
        aspect = max(width, height) / max(1, min(width, height))
        kind = "connector" if aspect >= 3.0 else "dot_or_accent"
        microfeatures.append(
            MicrofeatureToken(
                id=len(microfeatures),
                bbox_xyxy=(x, y, x + width, y + height),
                area=area,
                strength=float(values.mean()),
                persistence=float(np.clip(values.max() - values.min() + values.mean(), 0, 1)),
                kind=kind,
                uncertainty=float(np.clip(1.0 - values.mean(), 0, 1)),
                provenance="cross-scale-persistent-small-boundary-component",
            )
        )
    core_labels = core_labels.astype(np.int32, copy=False)
    boundary_mask = boundary_mask.astype(bool, copy=False)
    core_labels.setflags(write=False); boundary_mask.setflags(write=False)
    result = CellComplex(
        core_labels=core_labels,
        boundary_mask=boundary_mask,
        cells=tuple(cells),
        boundary_bands=tuple(bands),
        microfeatures=tuple(microfeatures),
    )
    result.validate()
    return result

"""Compressed min/max/alpha inclusion-tree candidates for REIR."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class InclusionNode:
    id: int
    kind: str
    level: float
    area: int
    bbox_xyxy: tuple[int, int, int, int]
    centroid_xy: tuple[float, float]
    parent: int | None = None
    persistence: float = 0.0
    provenance: str = ""
    uncertainty: float = 1.0
    support_rle: tuple[tuple[int, int], ...] = ()
    support_size: tuple[int, int] = (0, 0)


@dataclass(frozen=True)
class InclusionTree:
    kind: str
    nodes: tuple[InclusionNode, ...]
    levels: tuple[float, ...]


@dataclass(frozen=True)
class InclusionForest:
    min_tree: InclusionTree
    max_tree: InclusionTree
    alpha_tree: InclusionTree
    tree_of_shapes_candidates: tuple[int, ...]
    stable_components: tuple[InclusionNode, ...]


def _quantile_levels(field: np.ndarray, count: int = 5) -> np.ndarray:
    finite = field[np.isfinite(field)]
    if finite.size == 0:
        return np.array([0.5], dtype=np.float32)
    levels = np.quantile(finite, np.linspace(0.08, 0.92, count))
    return np.unique(levels.astype(np.float32))


def _runs_by_label(
    labels: np.ndarray,
) -> dict[int, tuple[tuple[int, int], ...]]:
    """Encode every connected-component label in one vectorized flat pass."""

    flat = labels.ravel()
    if not flat.size:
        return {}
    changes = np.flatnonzero(flat[1:] != flat[:-1]) + 1
    starts = np.concatenate((np.zeros(1, dtype=np.intp), changes))
    ends = np.concatenate((changes, np.asarray([flat.size], dtype=np.intp)))
    runs: dict[int, list[tuple[int, int]]] = {}
    for label, start, end in zip(flat[starts], starts, ends):
        label_value = int(label)
        if label_value > 0:
            runs.setdefault(label_value, []).append(
                (int(start), int(end - start))
            )
    return {label: tuple(values) for label, values in runs.items()}


def _component_tree(
    field: np.ndarray,
    *,
    kind: str,
    bright: bool,
    min_area: int,
) -> InclusionTree:
    levels = _quantile_levels(field)
    growth_levels = levels[::-1] if bright else levels
    nodes: list[InclusionNode] = []
    previous: list[tuple[int, tuple[int, int]]] = []
    for level in growth_levels:
        mask = (field >= level) if bright else (field <= level)
        component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), connectivity=8
        )
        label_runs = _runs_by_label(labels)
        current_by_label: dict[int, int] = {}
        for label in range(1, component_count):
            x, y, width, height, area = (int(value) for value in stats[label])
            if area < min_area or area >= field.size * 0.995:
                continue
            node_id = len(nodes)
            current_by_label[label] = node_id
            nodes.append(
                InclusionNode(
                    id=node_id,
                    kind=kind,
                    level=float(level),
                    area=area,
                    bbox_xyxy=(x, y, x + width, y + height),
                    centroid_xy=(
                        float(centroids[label][0]), float(centroids[label][1])
                    ),
                    provenance=f"quantile-{kind}-component-tree",
                    support_rle=label_runs.get(label, ()),
                    support_size=(int(field.shape[1]), int(field.shape[0])),
                )
            )
        for previous_id, sample in previous:
            px, py = sample
            label = int(labels[py, px])
            parent_id = current_by_label.get(label)
            if parent_id is not None and parent_id != previous_id:
                nodes[previous_id].parent = parent_id
                nodes[previous_id].persistence = abs(
                    float(level) - nodes[previous_id].level
                )
                nodes[previous_id].uncertainty = float(np.clip(
                    1.0 - nodes[previous_id].persistence * 4.0,
                    0.0,
                    1.0,
                ))
        previous = []
        for label, node_id in current_by_label.items():
            x, y, width, height, _area = (int(value) for value in stats[label])
            component = labels[y:y + height, x:x + width] == label
            coordinates = np.argwhere(component)
            if coordinates.size:
                sy, sx = coordinates[len(coordinates) // 2]
                previous.append((node_id, (x + int(sx), y + int(sy))))
    return InclusionTree(
        kind=kind, nodes=tuple(nodes),
        levels=tuple(float(value) for value in growth_levels),
    )


def build_inclusion_forest(
    lightness: np.ndarray,
    alpha: np.ndarray,
    *,
    min_area: int = 2,
) -> InclusionForest:
    min_tree = _component_tree(
        lightness, kind="min", bright=False, min_area=min_area
    )
    max_tree = _component_tree(
        lightness, kind="max", bright=True, min_area=min_area
    )
    if float(np.ptp(alpha)) > 1e-4:
        alpha_tree = _component_tree(
            alpha, kind="alpha", bright=True, min_area=min_area
        )
    else:
        alpha_tree = InclusionTree(kind="alpha", nodes=(), levels=())
    all_nodes = list(min_tree.nodes) + list(max_tree.nodes) + list(alpha_tree.nodes)
    stable = tuple(
        node for node in all_nodes
        if node.persistence >= 0.03 or node.area <= 16
    )
    shape_candidates = tuple(
        node.id for node in stable
        if node.area >= min_area and node.area < lightness.size * 0.9
    )
    return InclusionForest(
        min_tree=min_tree,
        max_tree=max_tree,
        alpha_tree=alpha_tree,
        tree_of_shapes_candidates=shape_candidates,
        stable_components=stable,
    )

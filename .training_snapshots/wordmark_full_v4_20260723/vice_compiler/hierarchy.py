"""Ultrametric contour map and nested region hierarchy for REIR."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class RegionNode:
    id: int
    left: int | None
    right: int | None
    parent: int | None
    merge_level: float
    leaf_count: int
    area: int
    bbox_xyxy: tuple[int, int, int, int]


@dataclass(frozen=True)
class RegionHierarchy:
    leaf_labels: np.ndarray
    nodes: tuple[RegionNode, ...]
    root_id: int
    ucm: np.ndarray
    adjacency: tuple[tuple[int, int, float, int], ...]
    region_size: int

    @property
    def leaf_count(self) -> int:
        return int(self.leaf_labels.max()) + 1

    def validate(self) -> None:
        n = self.leaf_count
        active = np.unique(self.leaf_labels)
        if not np.array_equal(active, np.arange(n, dtype=active.dtype)):
            raise ValueError("hierarchy leaf labels must be contiguous")
        if len(self.nodes) > max(1, 2 * n):
            raise ValueError("hierarchy exceeds the 2N node contract")
        if not (0 <= self.root_id < len(self.nodes)):
            raise ValueError("invalid hierarchy root")
        if self.leaf_labels.dtype != np.int32:
            raise ValueError("leaf labels must be int32")
        for node in self.nodes:
            x1, y1, x2, y2 = node.bbox_xyxy
            if node.area <= 0 or not (x1 < x2 and y1 < y2):
                raise ValueError("hierarchy contains an empty/invalid node")
            if node.left is not None and node.left >= node.id:
                raise ValueError("child must precede parent")
            if node.right is not None and node.right >= node.id:
                raise ValueError("child must precede parent")


def _leaf_geometry(labels: np.ndarray, count: int) -> tuple[np.ndarray, ...]:
    height, width = labels.shape
    flat = labels.ravel()
    area = np.bincount(flat, minlength=count).astype(np.int64)
    yy, xx = np.indices((height, width), dtype=np.int32)
    min_x = np.full(count, width, np.int32)
    min_y = np.full(count, height, np.int32)
    max_x = np.zeros(count, np.int32)
    max_y = np.zeros(count, np.int32)
    np.minimum.at(min_x, flat, xx.ravel())
    np.minimum.at(min_y, flat, yy.ravel())
    np.maximum.at(max_x, flat, xx.ravel())
    np.maximum.at(max_y, flat, yy.ravel())
    return area, min_x, min_y, max_x + 1, max_y + 1


def _adjacency(
    labels: np.ndarray, boundary: np.ndarray, count: int
) -> tuple[list[tuple[int, int, float, int]], np.ndarray]:
    pairs: list[np.ndarray] = []
    strengths: list[np.ndarray] = []
    coords: list[tuple[str, np.ndarray, np.ndarray]] = []
    left, right = labels[:, :-1], labels[:, 1:]
    mask = left != right
    if np.any(mask):
        a, b = left[mask], right[mask]
        pairs.append(np.stack([np.minimum(a, b), np.maximum(a, b)], axis=1))
        strengths.append(
            ((boundary[:, :-1] + boundary[:, 1:]) * 0.5)[mask]
        )
        ys, xs = np.nonzero(mask)
        coords.append(("h", ys, xs))
    top, bottom = labels[:-1, :], labels[1:, :]
    mask_v = top != bottom
    if np.any(mask_v):
        a, b = top[mask_v], bottom[mask_v]
        pairs.append(np.stack([np.minimum(a, b), np.maximum(a, b)], axis=1))
        strengths.append(
            ((boundary[:-1, :] + boundary[1:, :]) * 0.5)[mask_v]
        )
        ys, xs = np.nonzero(mask_v)
        coords.append(("v", ys, xs))
    if not pairs:
        return [], np.zeros_like(boundary, dtype=np.float32)
    all_pairs = np.concatenate(pairs, axis=0).astype(np.int64, copy=False)
    values = np.concatenate(strengths).astype(np.float64, copy=False)
    keys = all_pairs[:, 0] * count + all_pairs[:, 1]
    unique, inverse = np.unique(keys, return_inverse=True)
    totals = np.bincount(inverse, weights=values)
    lengths = np.bincount(inverse)
    means = totals / np.maximum(lengths, 1)
    result = [
        (int(key // count), int(key % count), float(mean), int(length))
        for key, mean, length in zip(unique, means, lengths)
    ]
    ucm = np.zeros_like(boundary, dtype=np.float32)
    offset = 0
    for (direction, ys, xs), part in zip(coords, pairs):
        part_length = len(part)
        part_inverse = inverse[offset:offset + part_length]
        values_at_edges = means[part_inverse].astype(np.float32, copy=False)
        ucm[ys, xs] = np.maximum(ucm[ys, xs], values_at_edges)
        if direction == "h":
            ucm[ys, xs + 1] = np.maximum(
                ucm[ys, xs + 1], values_at_edges
            )
        else:
            ucm[ys + 1, xs] = np.maximum(
                ucm[ys + 1, xs], values_at_edges
            )
        offset += part_length
    return result, ucm


def build_ucm_hierarchy(
    oklab: np.ndarray,
    boundary_probability: np.ndarray,
    *,
    region_size: int = 28,
    iterations: int = 1,
) -> RegionHierarchy:
    """Build an oriented watershed, UCM adjacency, and ultrametric merge tree.

    SLIC supplies bounded interior seeds.  High-probability oriented boundary
    pixels are released to OpenCV watershed, so the final leaf lattice follows
    measured contours without allowing an unbounded marker count.
    """
    if oklab.ndim != 3 or oklab.shape[2] != 3:
        raise ValueError("oklab must have shape HxWx3")
    if boundary_probability.shape != oklab.shape[:2]:
        raise ValueError("boundary shape mismatch")
    height, width = boundary_probability.shape
    region_size = max(
        4,
        min(
            int(region_size),
            max(4, min(height, width) // 6),
        ),
    )
    display = np.empty_like(oklab, dtype=np.float32)
    display[..., 0] = np.clip(oklab[..., 0], 0.0, 1.0) * 255.0
    display[..., 1:] = np.clip(oklab[..., 1:] + 0.5, 0.0, 1.0) * 255.0
    slic_input = np.clip(display, 0, 255).astype(np.uint8)
    if min(height, width) < 8:
        labels = np.zeros((height, width), dtype=np.int32)
    else:
        slic = cv2.ximgproc.createSuperpixelSLIC(
            slic_input,
            algorithm=cv2.ximgproc.SLIC,
            region_size=region_size,
            ruler=10.0,
        )
        slic.iterate(max(1, int(iterations)))
        slic.enforceLabelConnectivity(max(4, region_size // 2))
        labels = slic.getLabels().astype(np.int32, copy=False)
        markers = labels.copy() + 1
        release_threshold = max(
            0.18, float(np.quantile(boundary_probability, 0.72))
        )
        released = boundary_probability >= release_threshold
        markers[released] = 0
        watershed_image = np.ascontiguousarray(slic_input[..., ::-1])
        cv2.watershed(watershed_image, markers)
        refined = markers - 1
        refined[markers <= 0] = labels[markers <= 0]
        labels = refined.astype(np.int32, copy=False)
        labels = labels.reshape((height, width)).astype(np.int32, copy=False)
        # Watershed can eliminate every pixel of a small SLIC seed.  The
        # surviving ids then contain gaps even though no new ids are created.
        # Remap only in that case; otherwise phantom zero-area leaves leak into
        # the hierarchy and make exact ownership mathematically ill-defined.
        active = np.unique(labels)
        if (
            int(active[0]) != 0
            or int(active[-1]) + 1 != len(active)
        ):
            labels = np.searchsorted(active, labels).reshape(
                (height, width)
            ).astype(np.int32, copy=False)
    count = int(labels.max()) + 1
    area, min_x, min_y, max_x, max_y = _leaf_geometry(labels, count)
    adjacency, ucm = _adjacency(labels, boundary_probability, count)
    nodes: list[RegionNode] = [
        RegionNode(
            id=index,
            left=None,
            right=None,
            parent=None,
            merge_level=0.0,
            leaf_count=1,
            area=int(area[index]),
            bbox_xyxy=(
                int(min_x[index]), int(min_y[index]),
                int(max_x[index]), int(max_y[index]),
            ),
        )
        for index in range(count)
    ]
    dsu = np.arange(count, dtype=np.int32)
    rank = np.zeros(count, dtype=np.int8)
    component_node = np.arange(count, dtype=np.int32)

    def find(value: int) -> int:
        root = value
        while int(dsu[root]) != root:
            root = int(dsu[root])
        while int(dsu[value]) != value:
            parent = int(dsu[value]); dsu[value] = root; value = parent
        return root

    def merge_roots(first: int, second: int) -> int:
        if rank[first] < rank[second]:
            first, second = second, first
        dsu[second] = first
        if rank[first] == rank[second]:
            rank[first] += 1
        return first

    for first, second, strength, _length in sorted(
        adjacency, key=lambda edge: (edge[2], edge[0], edge[1])
    ):
        root_a, root_b = find(first), find(second)
        if root_a == root_b:
            continue
        left_id, right_id = int(component_node[root_a]), int(component_node[root_b])
        left, right = nodes[left_id], nodes[right_id]
        node_id = len(nodes)
        bbox = (
            min(left.bbox_xyxy[0], right.bbox_xyxy[0]),
            min(left.bbox_xyxy[1], right.bbox_xyxy[1]),
            max(left.bbox_xyxy[2], right.bbox_xyxy[2]),
            max(left.bbox_xyxy[3], right.bbox_xyxy[3]),
        )
        nodes.append(
            RegionNode(
                id=node_id,
                left=left_id,
                right=right_id,
                parent=None,
                merge_level=float(np.clip(strength, 0.0, 1.0)),
                leaf_count=left.leaf_count + right.leaf_count,
                area=left.area + right.area,
                bbox_xyxy=bbox,
            )
        )
        left.parent = node_id; right.parent = node_id
        root = merge_roots(root_a, root_b)
        component_node[root] = node_id
    roots = sorted({find(index) for index in range(count)})
    while len(roots) > 1:
        root_a, root_b = roots.pop(0), roots.pop(0)
        left_id, right_id = int(component_node[root_a]), int(component_node[root_b])
        left, right = nodes[left_id], nodes[right_id]
        node_id = len(nodes)
        nodes.append(
            RegionNode(
                id=node_id, left=left_id, right=right_id, parent=None,
                merge_level=1.0,
                leaf_count=left.leaf_count + right.leaf_count,
                area=left.area + right.area,
                bbox_xyxy=(
                    min(left.bbox_xyxy[0], right.bbox_xyxy[0]),
                    min(left.bbox_xyxy[1], right.bbox_xyxy[1]),
                    max(left.bbox_xyxy[2], right.bbox_xyxy[2]),
                    max(left.bbox_xyxy[3], right.bbox_xyxy[3]),
                ),
            )
        )
        left.parent = node_id; right.parent = node_id
        root = merge_roots(root_a, root_b)
        component_node[root] = node_id
        roots.append(root)
    labels.setflags(write=False); ucm.setflags(write=False)
    hierarchy = RegionHierarchy(
        leaf_labels=labels,
        nodes=tuple(nodes),
        root_id=int(component_node[find(0)]),
        ucm=ucm,
        adjacency=tuple(adjacency),
        region_size=region_size,
    )
    hierarchy.validate()
    return hierarchy

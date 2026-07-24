"""Half-edge interface graph derived once from the REIR leaf complex."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .hierarchy import RegionHierarchy


@dataclass(frozen=True)
class InterfaceObservation:
    id: int
    cell_a: int
    cell_b: int
    length_px: int
    mean_boundary_probability: float
    max_boundary_probability: float
    orientation_histogram: tuple[float, ...]
    side_a_mean_oklab: tuple[float, float, float]
    side_b_mean_oklab: tuple[float, float, float]
    side_a_variance_oklab: tuple[float, float, float]
    side_b_variance_oklab: tuple[float, float, float]
    color_separation: float
    bbox_xyxy: tuple[int, int, int, int]
    uncertainty: float
    provenance: str


@dataclass(frozen=True)
class HalfEdge:
    id: int
    origin: int
    target: int
    twin: int
    interface_id: int


@dataclass(frozen=True)
class InterfaceGraph:
    interfaces: tuple[InterfaceObservation, ...]
    half_edges: tuple[HalfEdge, ...]
    outgoing: tuple[tuple[int, ...], ...]

    def validate(self) -> None:
        for edge in self.half_edges:
            twin = self.half_edges[edge.twin]
            if twin.twin != edge.id:
                raise ValueError("half-edge twin relation is not involutive")
            if twin.origin != edge.target or twin.target != edge.origin:
                raise ValueError("half-edge twin endpoints mismatch")


def build_interface_graph(
    hierarchy: RegionHierarchy,
    boundary_probability: np.ndarray,
    orientation_distribution: np.ndarray,
    oklab: np.ndarray,
) -> InterfaceGraph:
    labels = hierarchy.leaf_labels
    if orientation_distribution.shape[:2] != labels.shape:
        raise ValueError("orientation distribution shape mismatch")
    if oklab.shape != (*labels.shape, 3):
        raise ValueError("interface Oklab shape mismatch")
    cell_count = hierarchy.leaf_count
    keys_parts: list[np.ndarray] = []
    probability_parts: list[np.ndarray] = []
    orientation_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []
    x_parts: list[np.ndarray] = []
    side_a_parts: list[np.ndarray] = []
    side_b_parts: list[np.ndarray] = []
    horizontal = labels[:, :-1] != labels[:, 1:]
    ys, xs = np.nonzero(horizontal)
    if len(ys):
        first, second = labels[ys, xs], labels[ys, xs + 1]
        low, high = np.minimum(first, second), np.maximum(first, second)
        keys_parts.append(low.astype(np.int64) * cell_count + high)
        probability_parts.append(
            (boundary_probability[ys, xs] + boundary_probability[ys, xs + 1]) * 0.5
        )
        orientation_parts.append(
            (orientation_distribution[ys, xs] + orientation_distribution[ys, xs + 1]) * 0.5
        )
        y_parts.append(ys); x_parts.append(xs)
        first_color = oklab[ys, xs]
        second_color = oklab[ys, xs + 1]
        first_is_low = first <= second
        side_a_parts.append(np.where(first_is_low[:, None], first_color, second_color))
        side_b_parts.append(np.where(first_is_low[:, None], second_color, first_color))
    vertical = labels[:-1, :] != labels[1:, :]
    ys, xs = np.nonzero(vertical)
    if len(ys):
        first, second = labels[ys, xs], labels[ys + 1, xs]
        low, high = np.minimum(first, second), np.maximum(first, second)
        keys_parts.append(low.astype(np.int64) * cell_count + high)
        probability_parts.append(
            (boundary_probability[ys, xs] + boundary_probability[ys + 1, xs]) * 0.5
        )
        orientation_parts.append(
            (orientation_distribution[ys, xs] + orientation_distribution[ys + 1, xs]) * 0.5
        )
        y_parts.append(ys); x_parts.append(xs)
        first_color = oklab[ys, xs]
        second_color = oklab[ys + 1, xs]
        first_is_low = first <= second
        side_a_parts.append(np.where(first_is_low[:, None], first_color, second_color))
        side_b_parts.append(np.where(first_is_low[:, None], second_color, first_color))
    if not keys_parts:
        return InterfaceGraph(interfaces=(), half_edges=(), outgoing=tuple(() for _ in range(cell_count)))
    keys = np.concatenate(keys_parts)
    probabilities = np.concatenate(probability_parts).astype(np.float64, copy=False)
    orientations = np.concatenate(orientation_parts).astype(np.float64, copy=False)
    all_y = np.concatenate(y_parts).astype(np.int32, copy=False)
    all_x = np.concatenate(x_parts).astype(np.int32, copy=False)
    side_a = np.concatenate(side_a_parts).astype(np.float64, copy=False)
    side_b = np.concatenate(side_b_parts).astype(np.float64, copy=False)
    unique, inverse = np.unique(keys, return_inverse=True)
    group_count = len(unique)
    lengths = np.bincount(inverse, minlength=group_count)
    probability_sum = np.bincount(
        inverse, weights=probabilities, minlength=group_count
    )
    probability_max = np.zeros(group_count, dtype=np.float64)
    np.maximum.at(probability_max, inverse, probabilities)
    orientation_sum = np.stack(
        [np.bincount(inverse, weights=orientations[:, index], minlength=group_count)
         for index in range(orientations.shape[1])], axis=1
    )
    side_a_sum = np.stack(
        [np.bincount(inverse, weights=side_a[:, index], minlength=group_count)
         for index in range(3)], axis=1
    )
    side_b_sum = np.stack(
        [np.bincount(inverse, weights=side_b[:, index], minlength=group_count)
         for index in range(3)], axis=1
    )
    side_a_square_sum = np.stack(
        [np.bincount(inverse, weights=side_a[:, index] ** 2, minlength=group_count)
         for index in range(3)], axis=1
    )
    side_b_square_sum = np.stack(
        [np.bincount(inverse, weights=side_b[:, index] ** 2, minlength=group_count)
         for index in range(3)], axis=1
    )
    min_x = np.full(group_count, labels.shape[1], np.int32)
    min_y = np.full(group_count, labels.shape[0], np.int32)
    max_x = np.zeros(group_count, np.int32)
    max_y = np.zeros(group_count, np.int32)
    np.minimum.at(min_x, inverse, all_x); np.minimum.at(min_y, inverse, all_y)
    np.maximum.at(max_x, inverse, all_x); np.maximum.at(max_y, inverse, all_y)
    interfaces: list[InterfaceObservation] = []
    half_edges: list[HalfEdge] = []
    outgoing_lists: list[list[int]] = [
        [] for _ in range(cell_count)
    ]
    for group, key in enumerate(unique.tolist()):
        pair = (int(key // cell_count), int(key % cell_count))
        mean_probability = probability_sum[group] / max(1, lengths[group])
        histogram = orientation_sum[group] / max(1, lengths[group])
        total = float(histogram.sum())
        if total > 0:
            histogram = histogram / total
        side_a_mean = side_a_sum[group] / max(1, lengths[group])
        side_b_mean = side_b_sum[group] / max(1, lengths[group])
        side_a_variance = np.maximum(
            side_a_square_sum[group] / max(1, lengths[group]) - side_a_mean ** 2,
            0.0,
        )
        side_b_variance = np.maximum(
            side_b_square_sum[group] / max(1, lengths[group]) - side_b_mean ** 2,
            0.0,
        )
        color_separation = float(np.linalg.norm(side_a_mean - side_b_mean))
        interface_id = len(interfaces)
        interfaces.append(
            InterfaceObservation(
                id=interface_id,
                cell_a=pair[0], cell_b=pair[1],
                length_px=int(lengths[group]),
                mean_boundary_probability=float(mean_probability),
                max_boundary_probability=float(probability_max[group]),
                orientation_histogram=tuple(float(v) for v in histogram),
                side_a_mean_oklab=tuple(float(v) for v in side_a_mean),
                side_b_mean_oklab=tuple(float(v) for v in side_b_mean),
                side_a_variance_oklab=tuple(float(v) for v in side_a_variance),
                side_b_variance_oklab=tuple(float(v) for v in side_b_variance),
                color_separation=color_separation,
                bbox_xyxy=(
                    int(min_x[group]), int(min_y[group]),
                    min(labels.shape[1], int(max_x[group]) + 2),
                    min(labels.shape[0], int(max_y[group]) + 2),
                ),
                uncertainty=float(np.clip(
                    1.0 - 0.7 * mean_probability
                    - 0.3 * min(1.0, color_separation * 2.0),
                    0.0,
                    1.0,
                )),
                provenance="leaf-adjacency+oriented-boundary+local-oklab-v2",
            )
        )
        first_id = len(half_edges); second_id = first_id + 1
        half_edges.extend((
            HalfEdge(first_id, pair[0], pair[1], second_id, interface_id),
            HalfEdge(second_id, pair[1], pair[0], first_id, interface_id),
        ))
        outgoing_lists[pair[0]].append(first_id)
        outgoing_lists[pair[1]].append(second_id)
    graph = InterfaceGraph(
        interfaces=tuple(interfaces),
        half_edges=tuple(half_edges),
        outgoing=tuple(tuple(values) for values in outgoing_lists),
    )
    graph.validate()
    return graph

"""Phase-5 proof-carrying stroke and diagram macro generator.

Filled ribbons and centerline programs are generated as competing CMIR
columns.  The source evidence is never rewritten: every stroke program is
rendered on the native REIR lattice and admitted only through support,
topology, width and boundary-residual walls.
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
from .proposal_net import query_support_mask

if TYPE_CHECKING:
    from .proposal_net import ProposalQuery


@dataclass(frozen=True)
class StrokeNode:
    id: int
    xy: tuple[float, float]
    kind: str
    degree: int


@dataclass(frozen=True)
class StrokeEdge:
    id: int
    start_node: int | None
    end_node: int | None
    centerline: tuple[tuple[float, float], ...]
    width_profile: tuple[float, ...]
    orientation_deg: float


@dataclass(frozen=True)
class StrokeGraph:
    nodes: tuple[StrokeNode, ...]
    edges: tuple[StrokeEdge, ...]
    cap: str
    join: str
    dash_pattern: tuple[float, ...]
    markers: tuple[str, ...]
    z_order: int


@dataclass(frozen=True)
class StrokeFitRecord:
    candidate: MacroCandidate
    macro_type: str
    source_mask: np.ndarray
    rendered_mask: np.ndarray
    skeleton_mask: np.ndarray
    graph: StrokeGraph
    iou: float
    boundary_p95_px: float
    width_median_px: float
    width_cv: float
    orthogonality: float
    phase_support: float
    source_token_ids: tuple[int, ...]

    def validate(self, reir: RasterEvidenceIR) -> None:
        expected = (reir.height, reir.width)
        for mask in (self.source_mask, self.rendered_mask, self.skeleton_mask):
            if mask.shape != expected or mask.flags.writeable:
                raise ValueError("stroke evidence must be an immutable REIR lattice")
        if not self.graph.edges:
            raise ValueError("stroke graph has no centerline edge")
        if self.width_median_px <= 0 or not math.isfinite(self.width_cv):
            raise ValueError("invalid stroke width evidence")
        if not (0.0 <= self.iou <= 1.0 and 0.0 <= self.orthogonality <= 1.0):
            raise ValueError("stroke score lies outside [0,1]")
        replace(self.candidate, registry_index=0, conflict_bits=0).validate(
            leaf_count=reir.hierarchy.leaf_count,
            interface_count=len(reir.interfaces.interfaces), candidate_count=1,
        )


@dataclass(frozen=True)
class StrokeMacroSet:
    records: tuple[StrokeFitRecord, ...]
    rois_considered: int
    candidates_pruned: int
    provenance: tuple[str, ...]

    @property
    def candidates(self) -> tuple[MacroCandidate, ...]:
        return tuple(row.candidate for row in self.records)


def _freeze(mask: np.ndarray) -> np.ndarray:
    result = np.ascontiguousarray(mask, dtype=bool)
    result.setflags(write=False)
    return result


def _bbox(mask: np.ndarray, pad: int = 1) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("cannot bound empty stroke support")
    return (
        max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
        min(mask.shape[1], int(xs.max()) + 1 + pad),
        min(mask.shape[0], int(ys.max()) + 1 + pad),
    )


def _skeletonize(mask: np.ndarray) -> np.ndarray:
    binary = np.asarray(mask, np.uint8) * 255
    if hasattr(cv2, "ximgproc") and hasattr(cv2.ximgproc, "thinning"):
        return cv2.ximgproc.thinning(binary) > 0
    work = binary // 255
    skeleton = np.zeros_like(work)
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    for _ in range(max(work.shape)):
        opened = cv2.morphologyEx(work, cv2.MORPH_OPEN, kernel)
        skeleton |= work & (1 - opened)
        work = cv2.erode(work, kernel)
        if not np.any(work):
            break
    return skeleton > 0


def _neighbor_degree(skeleton: np.ndarray) -> np.ndarray:
    return cv2.filter2D(
        skeleton.astype(np.uint8), cv2.CV_16S,
        np.ones((3, 3), np.int16), borderType=cv2.BORDER_CONSTANT,
    ) - skeleton.astype(np.int16)


def _principal_polyline(points_yx: np.ndarray) -> np.ndarray:
    """Order a skeleton arc monotonically along its principal direction."""
    xy = points_yx[:, ::-1].astype(np.float64)
    if len(xy) <= 2:
        return xy
    centered = xy - np.mean(xy, axis=0)
    covariance = centered.T @ centered
    _values, vectors = np.linalg.eigh(covariance)
    direction = vectors[:, -1]
    order = np.argsort(centered @ direction, kind="stable")
    ordered = xy[order]
    epsilon = max(0.35, 0.006 * cv2.arcLength(
        ordered.astype(np.float32).reshape((-1, 1, 2)), False,
    ))
    return cv2.approxPolyDP(
        ordered.astype(np.float32).reshape((-1, 1, 2)), epsilon, False,
    ).reshape((-1, 2)).astype(np.float64)


def _closed_polyline(component: np.ndarray) -> np.ndarray:
    contours, _hierarchy = cv2.findContours(
        component.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE,
    )
    if not contours:
        return _principal_polyline(np.column_stack(np.nonzero(component)))
    contour = max(contours, key=lambda row: cv2.arcLength(row, True))
    perimeter = max(1.0, float(cv2.arcLength(contour, True)))
    points = cv2.approxPolyDP(contour, max(0.35, 0.006 * perimeter), True)
    polyline = points.reshape((-1, 2)).astype(np.float64)
    if len(polyline):
        polyline = np.vstack((polyline, polyline[0]))
    return polyline


def _stroke_graph(mask: np.ndarray) -> tuple[StrokeGraph, np.ndarray, np.ndarray]:
    skeleton = _skeletonize(mask)
    distance = cv2.distanceTransform(np.asarray(mask, np.uint8), cv2.DIST_L2, 5)
    degree = _neighbor_degree(skeleton)
    special = skeleton & (degree != 2)
    count, labels, _stats, centroids = cv2.connectedComponentsWithStats(
        special.astype(np.uint8), 8,
    )
    nodes: list[StrokeNode] = []
    for label in range(1, count):
        pixels = labels == label
        local_degree = degree[pixels]
        maximum = int(local_degree.max(initial=0))
        kind = "junction" if maximum >= 3 else "endpoint"
        nodes.append(StrokeNode(
            id=len(nodes), xy=(float(centroids[label, 0]), float(centroids[label, 1])),
            kind=kind, degree=maximum,
        ))

    # Removing clustered junction/end pixels yields stable centerline arcs.
    arc_mask = skeleton & ~special
    arc_count, arc_labels = cv2.connectedComponents(
        arc_mask.astype(np.uint8), 8,
    )
    edges: list[StrokeEdge] = []

    for label in range(1, arc_count):
        component = arc_labels == label
        points = np.column_stack(np.nonzero(component))
        if not len(points):
            continue
        touches_node = np.any(
            (cv2.dilate(component.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)
            & special
        )
        polyline = (
            _principal_polyline(points) if touches_node
            else _closed_polyline(component)
        )
        if len(polyline) == 1:
            polyline = np.vstack((polyline, polyline))
        sample_x = np.clip(np.rint(polyline[:, 0]).astype(int), 0, mask.shape[1] - 1)
        sample_y = np.clip(np.rint(polyline[:, 1]).astype(int), 0, mask.shape[0] - 1)
        widths = np.maximum(1.0, 2.0 * distance[sample_y, sample_x] - 1.0)
        vector = polyline[-1] - polyline[0]
        if np.linalg.norm(vector) < 1e-6 and len(polyline) > 2:
            vector = polyline[1] - polyline[0]
        angle = math.degrees(math.atan2(float(vector[1]), float(vector[0]))) % 180.0
        touched = cv2.dilate(
            component.astype(np.uint8), np.ones((3, 3), np.uint8),
        ) > 0
        adjacent_labels = np.unique(labels[touched & special])
        adjacent_ids = [int(value) - 1 for value in adjacent_labels if int(value) > 0]

        def nearest_node(point: np.ndarray) -> int | None:
            if not adjacent_ids:
                return None
            return min(
                adjacent_ids,
                key=lambda node_id: (
                    (nodes[node_id].xy[0] - float(point[0])) ** 2
                    + (nodes[node_id].xy[1] - float(point[1])) ** 2,
                    node_id,
                ),
            )

        edges.append(StrokeEdge(
            id=len(edges), start_node=nearest_node(polyline[0]),
            end_node=nearest_node(polyline[-1]),
            centerline=tuple((float(x), float(y)) for x, y in polyline),
            width_profile=tuple(float(value) for value in widths),
            orientation_deg=float(angle),
        ))

    # A very short line can be all endpoints after thinning.  It is still a
    # valid centerline edge and must not disappear from the candidate set.
    if not edges and np.any(skeleton):
        points = np.column_stack(np.nonzero(skeleton))
        polyline = _principal_polyline(points)
        if len(polyline) == 1:
            polyline = np.vstack((polyline, polyline))
        sx = np.clip(np.rint(polyline[:, 0]).astype(int), 0, mask.shape[1] - 1)
        sy = np.clip(np.rint(polyline[:, 1]).astype(int), 0, mask.shape[0] - 1)
        vector = polyline[-1] - polyline[0]
        edges.append(StrokeEdge(
            id=0, start_node=nodes[0].id if nodes else None,
            end_node=nodes[-1].id if len(nodes) > 1 else None,
            centerline=tuple((float(x), float(y)) for x, y in polyline),
            width_profile=tuple(float(value) for value in np.maximum(
                1.0, 2.0 * distance[sy, sx] - 1.0,
            )),
            orientation_deg=float(math.degrees(math.atan2(
                float(vector[1]), float(vector[0]),
            )) % 180.0),
        ))
    return StrokeGraph(
        nodes=tuple(nodes), edges=tuple(edges), cap="round", join="round",
        dash_pattern=(), markers=(), z_order=0,
    ), skeleton, distance


def _translate_graph(graph: StrokeGraph, dx: int, dy: int) -> StrokeGraph:
    if dx == 0 and dy == 0:
        return graph
    return replace(
        graph,
        nodes=tuple(replace(
            node, xy=(node.xy[0] + dx, node.xy[1] + dy),
        ) for node in graph.nodes),
        edges=tuple(replace(
            edge,
            centerline=tuple((x + dx, y + dy) for x, y in edge.centerline),
        ) for edge in graph.edges),
    )


def _render_graph(
    shape: tuple[int, int], graph: StrokeGraph, *, variable_width: bool,
    cap: str,
) -> np.ndarray:
    result = np.zeros(shape, np.uint8)
    all_widths = [value for edge in graph.edges for value in edge.width_profile]
    common = max(1, int(round(float(np.median(all_widths))))) if all_widths else 1
    for edge in graph.edges:
        points = np.rint(np.asarray(edge.centerline)).astype(np.int32)
        if not len(points):
            continue
        if graph.dash_pattern and len(points) == 2:
            on, off = graph.dash_pattern[:2]
            start = points[0].astype(np.float64)
            vector = points[1].astype(np.float64) - start
            length = float(np.linalg.norm(vector))
            direction = vector / max(length, 1e-9)
            position = 0.0
            while position < length - 1e-9:
                stop = min(length, position + on)
                first = tuple(np.rint(start + direction * position).astype(int))
                second = tuple(np.rint(start + direction * stop).astype(int))
                cv2.line(result, first, second, 1, common, cv2.LINE_AA)
                if cap == "round":
                    radius = max(1, int(round(common / 2)))
                    cv2.circle(result, first, radius, 1, -1, cv2.LINE_AA)
                    cv2.circle(result, second, radius, 1, -1, cv2.LINE_AA)
                position += max(1e-6, on + off)
            continue
        if variable_width and len(points) > 1:
            widths = np.interp(
                np.linspace(0, max(0, len(edge.width_profile) - 1), len(points)),
                np.arange(len(edge.width_profile)), np.asarray(edge.width_profile),
            )
            for index in range(len(points) - 1):
                thickness = max(1, int(round(0.5 * (widths[index] + widths[index + 1]))))
                cv2.line(result, tuple(points[index]), tuple(points[index + 1]),
                         1, thickness, cv2.LINE_AA)
        else:
            cv2.polylines(result, [points.reshape((-1, 1, 2))], False, 1,
                          common, cv2.LINE_AA)
        if cap == "round":
            endpoint_width = (
                float(edge.width_profile[0]) if edge.width_profile else float(common)
            )
            cv2.circle(result, tuple(points[0]), max(1, int(round(endpoint_width / 2))),
                       1, -1, cv2.LINE_AA)
            endpoint_width = (
                float(edge.width_profile[-1]) if edge.width_profile else float(common)
            )
            cv2.circle(result, tuple(points[-1]), max(1, int(round(endpoint_width / 2))),
                       1, -1, cv2.LINE_AA)
    for node in graph.nodes:
        if node.kind == "junction":
            cv2.circle(result, tuple(np.rint(node.xy).astype(int)),
                       max(1, common // 2), 1, -1, cv2.LINE_AA)
    if graph.markers and graph.edges:
        edge = graph.edges[0]
        points = np.asarray(edge.centerline, np.float64)
        if len(points) >= 2:
            direction = points[-1] - points[0]
            direction /= max(1e-9, float(np.linalg.norm(direction)))
            normal = np.asarray((-direction[1], direction[0]))
            head_length = 4.0 * common
            half_width = 2.0 * common
            if "arrow-start" in graph.markers:
                tip = points[0]; base = tip + direction * head_length
                polygon = np.rint(np.asarray((
                    tip, base + normal * half_width,
                    base - normal * half_width,
                ))).astype(np.int32)
                cv2.fillPoly(result, [polygon], 1, cv2.LINE_AA)
            if "arrow-end" in graph.markers:
                tip = points[-1]; base = tip - direction * head_length
                polygon = np.rint(np.asarray((
                    tip, base + normal * half_width,
                    base - normal * half_width,
                ))).astype(np.int32)
                cv2.fillPoly(result, [polygon], 1, cv2.LINE_AA)
    return result > 0


def _fit_collinear_dash_graph(
    graph: StrokeGraph, width_median: float, source: np.ndarray,
) -> StrokeGraph | None:
    """Collapse a measured collinear dash train to one bounded SVG pattern."""
    component_count, component_labels = cv2.connectedComponents(
        np.asarray(source, np.uint8), 8,
    )
    if not 4 <= component_count <= 65:
        return None
    angles = np.radians(np.asarray([
        edge.orientation_deg for edge in graph.edges
    ], np.float64) * 2.0)
    mean_angle = 0.5 * math.atan2(
        float(np.mean(np.sin(angles))), float(np.mean(np.cos(angles))),
    )
    direction = np.asarray((math.cos(mean_angle), math.sin(mean_angle)))
    normal = np.asarray((-direction[1], direction[0]))
    intervals = []
    normal_centers = []
    widths = [
        value for edge in graph.edges for value in edge.width_profile
    ]
    for component_id in range(1, component_count):
        ys, xs = np.nonzero(component_labels == component_id)
        points = np.column_stack((xs, ys)).astype(np.float64)
        if len(points) < 2:
            return None
        projected = points @ direction
        lo, hi = float(np.min(projected)), float(np.max(projected))
        if hi - lo < max(1.0, 0.55 * width_median):
            return None
        intervals.append((lo, hi))
        normal_centers.append(float(np.mean(points @ normal)))
    if float(np.std(normal_centers)) > max(1.25, 0.65 * width_median):
        return None
    intervals.sort()
    on_lengths = np.asarray([hi - lo for lo, hi in intervals], np.float64)
    gaps = np.asarray([
        right[0] - left[1] for left, right in zip(intervals, intervals[1:])
    ], np.float64)
    if np.any(gaps <= max(0.5, 0.12 * width_median)):
        return None
    on = float(np.median(on_lengths)); off = float(np.median(gaps))
    if (
        float(np.std(on_lengths) / max(1e-6, on)) > 0.35
        or float(np.std(gaps) / max(1e-6, off)) > 0.40
    ):
        return None
    normal_center = float(np.median(normal_centers))
    start = direction * intervals[0][0] + normal * normal_center
    stop = direction * intervals[-1][1] + normal * normal_center
    common_width = float(np.median(widths)) if widths else width_median
    edge = StrokeEdge(
        id=0, start_node=0, end_node=1,
        centerline=(tuple(start.tolist()), tuple(stop.tolist())),
        width_profile=(common_width, common_width),
        orientation_deg=float(math.degrees(mean_angle) % 180.0),
    )
    nodes = (
        StrokeNode(0, tuple(start.tolist()), "endpoint", 1),
        StrokeNode(1, tuple(stop.tolist()), "endpoint", 1),
    )
    return replace(
        graph, nodes=nodes, edges=(edge,), dash_pattern=(on, off),
    )


def _fit_arrow_marker_graph(source: np.ndarray) -> StrokeGraph | None:
    """Fit an elongated tubular component with measured terminal arrowheads."""
    mask = np.asarray(source, bool)
    components, holes = topology_signature(mask)
    if components != 1 or holes != 0 or int(mask.sum()) < 24:
        return None
    ys, xs = np.nonzero(mask)
    points = np.column_stack((xs, ys)).astype(np.float64)
    centered = points - np.mean(points, axis=0)
    eigenvalues, vectors = np.linalg.eigh(centered.T @ centered)
    if eigenvalues[-1] <= max(1e-6, 6.25 * eigenvalues[0]):
        return None
    direction = vectors[:, -1]
    normal = vectors[:, 0]
    along = points @ direction
    across = points @ normal
    low, high = float(np.min(along)), float(np.max(along))
    length = high - low
    if length < 12.0:
        return None
    bin_count = int(np.clip(round(length), 16, 96))
    indices = np.clip(
        np.floor((along - low) / max(1e-9, length) * bin_count).astype(int),
        0, bin_count - 1,
    )
    spans = np.full(bin_count, np.nan, np.float64)
    centers = np.full(bin_count, np.nan, np.float64)
    for index in range(bin_count):
        cross_section = across[indices == index]
        if len(cross_section):
            spans[index] = float(
                np.max(cross_section) - np.min(cross_section) + 1.0
            )
            centers[index] = float(np.median(cross_section))
    middle = spans[int(0.30 * bin_count):max(int(0.70 * bin_count), 1)]
    middle = middle[np.isfinite(middle)]
    if len(middle) < 4:
        return None
    body_width = float(np.median(middle))
    end_count = max(4, int(round(0.28 * bin_count)))

    def terminal_marker(rows: np.ndarray) -> bool:
        finite = rows[np.isfinite(rows)]
        if len(finite) < 3:
            return False
        peak = float(np.max(finite))
        terminal = float(finite[-1])
        return bool(
            peak >= max(body_width + 3.0, 1.85 * body_width)
            and terminal <= 0.72 * peak
        )

    start_marker = terminal_marker(spans[:end_count][::-1])
    end_marker = terminal_marker(spans[-end_count:])
    if not (start_marker or end_marker):
        return None
    normal_center = float(np.median(centers[np.isfinite(centers)]))
    start = direction * low + normal * normal_center
    stop = direction * high + normal * normal_center
    # PCA has no sign.  A single observed tip defines semantic direction, so
    # canonicalize it as marker-end regardless of the eigenvector orientation.
    if start_marker and not end_marker:
        start, stop = stop, start
        direction = -direction
        start_marker = False
        end_marker = True
    edge = StrokeEdge(
        id=0, start_node=0, end_node=1,
        centerline=(tuple(start.tolist()), tuple(stop.tolist())),
        width_profile=(body_width, body_width),
        orientation_deg=float(math.degrees(math.atan2(
            float(direction[1]), float(direction[0]),
        )) % 180.0),
    )
    markers = tuple(
        name for enabled, name in (
            (start_marker, "arrow-start"), (end_marker, "arrow-end"),
        ) if enabled
    )
    return StrokeGraph(
        nodes=(
            StrokeNode(0, tuple(start.tolist()), "endpoint", 1),
            StrokeNode(1, tuple(stop.tolist()), "endpoint", 1),
        ),
        edges=(edge,), cap="square", join="miter", dash_pattern=(),
        markers=markers, z_order=0,
    )


def _boundary_p95(first: np.ndarray, second: np.ndarray) -> float:
    # The metric is translation invariant.  Cropping to the affected support
    # avoids two full-canvas distance transforms for every small stroke while
    # preserving exactly the same boundary distances (with a safety halo).
    union = np.asarray(first, dtype=bool) | np.asarray(second, dtype=bool)
    if not np.any(union):
        return 0.0
    x1, y1, x2, y2 = _bbox(union, pad=4)
    first = np.asarray(first, dtype=bool)[y1:y2, x1:x2]
    second = np.asarray(second, dtype=bool)[y1:y2, x1:x2]
    kernel = np.ones((3, 3), np.uint8)
    a = cv2.morphologyEx(first.astype(np.uint8), cv2.MORPH_GRADIENT, kernel) > 0
    b = cv2.morphologyEx(second.astype(np.uint8), cv2.MORPH_GRADIENT, kernel) > 0
    if not np.any(a) or not np.any(b):
        return float(math.hypot(*first.shape))
    to_a = cv2.distanceTransform((~a).astype(np.uint8), cv2.DIST_L2, 5)
    to_b = cv2.distanceTransform((~b).astype(np.uint8), cv2.DIST_L2, 5)
    values = np.concatenate((to_a[b], to_b[a])).astype(np.float64)
    return float(np.quantile(values, 0.95))


def _iou(first: np.ndarray, second: np.ndarray) -> float:
    return float(np.sum(first & second) / max(1, np.sum(first | second)))


def _orthogonality(graph: StrokeGraph) -> float:
    if not graph.edges:
        return 0.0
    residuals = []
    for edge in graph.edges:
        angle = edge.orientation_deg % 90.0
        residuals.append(min(angle, 90.0 - angle))
    return float(np.mean(np.exp(-np.square(np.asarray(residuals) / 12.0))))


def _collinear_dash_evidence(mask: np.ndarray) -> bool:
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        np.asarray(mask, np.uint8), 8,
    )
    if not 4 <= count <= 65:
        return False
    areas = stats[1:, cv2.CC_STAT_AREA].astype(np.float64)
    if np.any(areas < 4) or float(np.std(areas) / max(1.0, np.mean(areas))) > 0.45:
        return False
    centers = np.asarray(centroids[1:], np.float64)
    centered = centers - np.mean(centers, axis=0)
    _values, vectors = np.linalg.eigh(centered.T @ centered)
    direction = vectors[:, -1]
    normal = vectors[:, 0]
    thickness = float(np.median(np.minimum(
        stats[1:, cv2.CC_STAT_WIDTH], stats[1:, cv2.CC_STAT_HEIGHT],
    )))
    if float(np.std(centered @ normal)) > max(1.25, 0.75 * thickness):
        return False
    intervals = []
    for component_id in range(1, count):
        ys, xs = np.nonzero(labels == component_id)
        projected = np.column_stack((xs, ys)) @ direction
        intervals.append((float(np.min(projected)), float(np.max(projected))))
    intervals.sort()
    lengths = np.asarray([hi - lo for lo, hi in intervals], np.float64)
    gaps = np.asarray([
        right[0] - left[1] for left, right in zip(intervals, intervals[1:])
    ], np.float64)
    return bool(
        np.all(gaps > max(0.5, 0.12 * thickness))
        and float(np.std(lengths) / max(1.0, np.mean(lengths))) <= 0.35
        and float(np.std(gaps) / max(1.0, np.mean(gaps))) <= 0.40
    )


def _source_rois(
    reir: RasterEvidenceIR, max_rois: int,
    proposal_queries: Iterable["ProposalQuery"] = (),
) -> list[tuple[np.ndarray, tuple[int, ...], float, tuple[str, ...]]]:
    sources: list[tuple[np.ndarray, tuple[int, ...], float, tuple[str, ...]]] = []
    families = {"stroke", "component", "topology", "shape"}
    stroke_tokens = [row for row in reir.proposal_tokens if row.family == "stroke"]
    for token in reir.proposal_tokens:
        if token.family not in families:
            continue
        mask = decode_token_mask(token, (reir.height, reir.width))
        if mask is None or int(mask.sum()) < 4:
            continue
        # A photometric bank token may contain a full page.  Diagram strokes
        # enter as connected support units, never as an accidental scene union.
        count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), 8,
        )
        if _collinear_dash_evidence(mask):
            sources.append((
                _freeze(mask), (token.id,), float(token.score),
                (token.provenance, "collinear-rhythmic-dash-evidence"),
            ))
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < 4 or area > int(0.65 * mask.size):
                continue
            component = labels == label
            x, y, width, height = (int(value) for value in stats[label, :4])
            aspect = max(width, height) / max(1.0, min(width, height))
            fill = area / max(1.0, float(width * height))
            # Dense, large 2-D regions are fills/photometric threshold banks,
            # not centerline programs.  Rejecting them before thinning is a
            # type check, not a score heuristic: genuine frames, paths and
            # connector networks occupy a sparse tubular support.  This also
            # prevents JPEG threshold masks from creating minute-long tails.
            if (
                area > 4096 and min(width, height) >= 32
                and fill > 0.30
            ):
                continue
            holes = topology_signature(component)[1]
            if token.family != "stroke" and aspect < 1.3 and holes == 0 and area > 24:
                continue
            sources.append((
                _freeze(component), (token.id,), float(token.score),
                (token.provenance, f"component:{label}"),
            ))
    if len(stroke_tokens) >= 2:
        union = np.zeros((reir.height, reir.width), bool)
        token_ids = []
        scores = []
        for token in sorted(stroke_tokens, key=lambda row: -row.score)[:32]:
            mask = decode_token_mask(token, union.shape)
            if mask is not None:
                union |= mask
                token_ids.append(token.id); scores.append(token.score)
        if np.any(union):
            sources.append((
                _freeze(union), tuple(token_ids), float(np.mean(scores)),
                ("phase-gradient-hough-network", "diagram-query-envelope"),
            ))
    for query in proposal_queries:
        if query.family != "stroke_network":
            continue
        mask = query_support_mask(reir, query, minimum_pixels=4)
        if mask is None or int(mask.sum()) > int(0.70 * mask.size):
            continue
        from .proposal_net import query_head_prior_score
        query_score, head_provenance = query_head_prior_score(
            query, mask, expected_relation_groups=(
                ("same_group",), ("stroke_membership",),
            ),
        )
        count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), 8,
        )
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < 4:
                continue
            sources.append((
                _freeze(labels == label), (), query_score,
                ("ProposalNet-guided-before-stroke-fitting", query.id,
                 *head_provenance, *query.provenance),
            ))
    unique: dict[str, tuple[np.ndarray, tuple[int, ...], float, tuple[str, ...]]] = {}
    for row in sources:
        digest = mask_sha256(row[0])
        old = unique.get(digest)
        if old is None or row[2] > old[2]:
            unique[digest] = row
    return sorted(
        unique.values(), key=lambda row: (-row[2], -int(row[0].sum()), mask_sha256(row[0])),
    )[:max(1, min(64, int(max_rois)))]


def _classify(graph: StrokeGraph, source: np.ndarray, width_cv: float) -> str:
    components, holes = topology_signature(source)
    junctions = sum(node.kind == "junction" for node in graph.nodes)
    endpoints = sum(node.kind == "endpoint" for node in graph.nodes)
    orthogonal = _orthogonality(graph)
    if graph.markers:
        return "connector_network"
    if graph.dash_pattern:
        return "dashed_stroke"
    if components >= 4 and holes == 0:
        return "dashed_frame"
    if holes >= 2 and junctions >= 4 and orthogonal >= 0.72:
        return "swimlane_structure"
    if holes >= 1 and orthogonal >= 0.62:
        return "frame"
    if junctions and orthogonal >= 0.72 and len(graph.edges) >= 3:
        return "axes_grid"
    if junctions and width_cv >= 0.14:
        return "variable_width_branch"
    if junctions:
        return "connector_network"
    if endpoints <= 2 and len(graph.edges) <= 1:
        return "single_stroke"
    return "polyline"


def _make_record(
    reir: RasterEvidenceIR, source: np.ndarray, token_ids: tuple[int, ...],
    source_score: float, provenance: tuple[str, ...],
) -> StrokeFitRecord | None:
    crop = _bbox(source, pad=2)
    x1, y1, x2, y2 = crop
    graph, local_skeleton, local_distance = _stroke_graph(source[y1:y2, x1:x2])
    graph = _translate_graph(graph, x1, y1)
    skeleton = np.zeros(source.shape, bool)
    skeleton[y1:y2, x1:x2] = local_skeleton
    distance = np.zeros(source.shape, np.float32)
    distance[y1:y2, x1:x2] = local_distance
    if not graph.edges or int(skeleton.sum()) < 3:
        return None
    sampled = distance[skeleton]
    widths = np.maximum(1.0, 2.0 * sampled - 1.0)
    width_median = float(np.median(widths))
    width_cv = float(np.std(widths) / max(1.0, np.mean(widths)))
    marker_graph = _fit_arrow_marker_graph(source)
    if marker_graph is not None:
        graph = marker_graph
        graph_widths = np.asarray([
            value for edge in graph.edges for value in edge.width_profile
        ], np.float64)
        width_median = float(np.median(graph_widths))
        width_cv = float(
            np.std(graph_widths) / max(1.0, np.mean(graph_widths))
        )
    else:
        dash_graph = _fit_collinear_dash_graph(graph, width_median, source)
        if dash_graph is not None:
            graph = dash_graph
    variable = width_cv >= 0.14
    alternatives = []
    for cap in ("round", "square"):
        rendered = _render_graph(source.shape, graph, variable_width=variable, cap=cap)
        alternatives.append((_iou(source, rendered), cap, rendered))
    # IoU is the primary ordering key, so the expensive exact boundary metric
    # is needed only for the IoU winner(s), not unconditionally for both caps.
    best_iou = max(row[0] for row in alternatives)
    finalists = [row for row in alternatives if row[0] == best_iou]
    scored = [
        (iou, -_boundary_p95(source, rendered), cap, rendered)
        for iou, cap, rendered in finalists
    ]
    iou, negative_p95, cap, rendered = max(scored, key=lambda row: (row[0], row[1]))
    p95 = -negative_p95
    topology_ok = topology_signature(source) == topology_signature(rendered)
    tolerance = max(1.5, min(3.0, 0.55 * width_median + 0.8))
    phase = reir.boundary_pyramid[0].phase_congruency
    phase_support = float(np.mean(phase[skeleton])) if np.any(skeleton) else 0.0
    edge_lengths = [
        sum(math.dist(a, b) for a, b in zip(edge.centerline, edge.centerline[1:]))
        for edge in graph.edges
    ]
    support_ok = sum(edge_lengths) >= 3.0 and width_median <= 0.55 * max(source.shape)
    if not (support_ok and topology_ok and iou >= 0.58 and p95 <= tolerance):
        return None
    macro_type = _classify(graph, source, width_cv)
    graph = replace(graph, cap=cap)
    orthogonality = _orthogonality(graph)
    score = float(np.clip(
        0.52 * iou + 0.16 * math.exp(-p95 / max(0.5, tolerance))
        + 0.10 * (1.0 - min(1.0, width_cv)) + 0.08 * orthogonality
        + 0.08 * source_score + 0.06 * phase_support, 0.0, 1.5,
    ))
    candidate = candidate_from_support(
        reir, family="stroke", mask=rendered, roi_xyxy=_bbox(rendered),
        evidence_token_ids=token_ids, score=score,
        kind=MacroKind.STROKE_NETWORK,
        components=topology_signature(rendered)[0],
        holes=topology_signature(rendered)[1], prefix=f"stroke-{macro_type}",
        provenance=("phase5-stroke-network", f"macro:{macro_type}", *provenance),
    )
    if candidate is None:
        return None
    parameters: tuple[tuple[str, float | int | str], ...] = (
        ("nodes", len(graph.nodes)), ("edges", len(graph.edges)),
        ("width", width_median), ("width_cv", width_cv),
        ("cap", graph.cap), ("join", graph.join),
        ("dash", ",".join(f"{value:.3f}" for value in graph.dash_pattern)),
        ("markers", ",".join(graph.markers)), ("z_order", graph.z_order),
    )
    candidate = replace(
        candidate,
        program=SceneProgram(f"Stroke/{macro_type}", parameters),
        continuous_params=(("width", width_median),),
        covariance=(max(0.02, width_cv * width_median),),
        certificates=replace(candidate.certificates, notes=(
            *candidate.certificates.notes, f"iou={iou:.6f}",
            f"boundary_p95={p95:.6f}", f"width_cv={width_cv:.6f}",
            f"orthogonality={orthogonality:.6f}",
            "centerline-rerendered-native-lattice", "topology-preserved",
        )),
        prerequisite_claims=(
            "minimum-centerline-support", "distance-ridge-width-profile",
            "native-topology-preserved", "bounded-render-residual",
            "competes-with-filled-region-hierarchy",
        ),
        resource_estimate=ResourceEstimate(
            fitting_ms=0.18, render_pixels=int(rendered.sum()),
            memory_bytes=768, solver_variables=max(1, len(graph.edges) + 1),
        ),
    )
    candidate = rekey_draft_candidate(
        candidate, prefix=f"stroke-{macro_type}",
    )
    return StrokeFitRecord(
        candidate=candidate, macro_type=macro_type,
        source_mask=_freeze(source), rendered_mask=_freeze(rendered),
        skeleton_mask=_freeze(skeleton), graph=graph, iou=iou,
        boundary_p95_px=p95, width_median_px=width_median,
        width_cv=width_cv, orthogonality=orthogonality,
        phase_support=phase_support, source_token_ids=token_ids,
    )


def generate_stroke_macros(
    reir: RasterEvidenceIR, *, max_rois: int = 64,
    validate_reir: bool = True,
    proposal_queries: Iterable["ProposalQuery"] = (),
) -> StrokeMacroSet:
    if validate_reir:
        reir.validate()
    sources = _source_rois(reir, max_rois, proposal_queries)
    records = []
    pruned = 0
    for source, token_ids, score, provenance in sources:
        row = _make_record(reir, source, token_ids, score, provenance)
        if row is None:
            pruned += 1
        else:
            records.append(row)
    unique: dict[tuple[str, str], StrokeFitRecord] = {}
    for row in records:
        key = (row.macro_type, mask_sha256(row.rendered_mask))
        old = unique.get(key)
        if old is None or row.candidate.score_bounds.lower > old.candidate.score_bounds.lower:
            unique[key] = row
    final = tuple(sorted(
        unique.values(), key=lambda row: (row.candidate.roi_xyxy, row.macro_type, row.candidate.id),
    ))
    for row in final:
        row.validate(reir)
    return StrokeMacroSet(
        records=final, rois_considered=len(sources), candidates_pruned=pruned,
        provenance=(
            "phase-gradient+Hough+path-opening+distance-ridge",
            "phase5-stroke-diagram-generator/v1", "bounded-64-rois",
        ),
    )

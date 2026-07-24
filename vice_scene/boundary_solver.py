"""Fit every raster interface once with physical arclength-invariant costs."""

from __future__ import annotations

import collections
import math
from dataclasses import dataclass

import cv2
import numpy as np

from .contracts import GeometryPrimitive, InterfaceEdge
from .topology import OUTSIDE, TopologyHypothesis


@dataclass(frozen=True)
class InterfaceRun:
    left_region: int
    right_region: int
    points: np.ndarray
    confidence: np.ndarray


def physical_residual_cost(residuals: np.ndarray, sample_points: np.ndarray,
                           sigma: np.ndarray | float = 1.0, huber_delta: float = 1.5) -> float:
    """Huber residual integrated over physical arclength, independent of density."""
    residuals = np.asarray(residuals, np.float64).reshape(-1)
    points = np.asarray(sample_points, np.float64).reshape(-1, 2)
    if len(residuals) != len(points) or not len(points):
        raise ValueError("residual/sample length mismatch")
    if len(points) == 1:
        weights = np.ones(1)
    else:
        spans = np.linalg.norm(np.diff(points, axis=0), axis=1)
        weights = np.empty(len(points), np.float64)
        weights[0], weights[-1] = spans[0] * .5, spans[-1] * .5
        if len(points) > 2:
            weights[1:-1] = .5 * (spans[:-1] + spans[1:])
    scaled = np.abs(residuals / np.maximum(np.asarray(sigma, np.float64), 1e-6))
    rho = np.where(scaled <= huber_delta, .5 * scaled * scaled,
                   huber_delta * (scaled - .5 * huber_delta))
    return float(np.sum(weights * rho) / max(np.sum(weights), 1e-9))


def solve_shared_interfaces(topology: TopologyHypothesis,
                            shape_ids: tuple[str, ...],
                            boundary_confidence: np.ndarray | None = None,
                            subpixel_offset: np.ndarray | None = None) -> tuple[InterfaceEdge, ...]:
    if len(shape_ids) != len(topology.regions):
        raise ValueError("shape/region mapping mismatch")
    runs = extract_interface_runs(topology.label_map, boundary_confidence)
    result: list[InterfaceEdge] = []
    for index, run in enumerate(runs):
        if subpixel_offset is not None:
            run = InterfaceRun(run.left_region, run.right_region,
                               _offset_interface_points(run.points, subpixel_offset,
                                                        boundary_confidence),
                               run.confidence)
        geometry = fit_interface_run(run)
        left = shape_ids[run.left_region] if run.left_region != OUTSIDE else None
        right = shape_ids[run.right_region] if run.right_region != OUTSIDE else None
        if left is not None and right is not None and left > right:
            left, right = right, left
        result.append(InterfaceEdge(
            id=f"interface-{index}", left_shape=left, right_shape=right,
            geometry=geometry, confidence_profile=tuple(float(v) for v in run.confidence),
            evidence_refs=("boundary_prob", "boundary_normal", "subpixel_offset",
                           "uncertainty"),
        ))
    return tuple(result)


def _offset_interface_points(points: np.ndarray, offsets: np.ndarray,
                             confidence: np.ndarray | None) -> np.ndarray:
    """Move lattice interfaces by the bounded evidence-predicted edge phase."""
    field = np.asarray(offsets, np.float32)
    if field.ndim != 3 or field.shape[2] != 2:
        return np.asarray(points, np.float64)
    height, width = field.shape[:2]
    result = np.asarray(points, np.float64).copy()
    columns = np.clip(np.floor(result[:, 0]).astype(int), 0, width - 1)
    rows = np.clip(np.floor(result[:, 1]).astype(int), 0, height - 1)
    delta = field[rows, columns].astype(np.float64)
    norms = np.linalg.norm(delta, axis=1, keepdims=True)
    delta *= np.minimum(1.0, .5 / np.maximum(norms, 1e-9))
    if confidence is not None and np.asarray(confidence).shape[:2] == (height, width):
        strength = np.clip(np.asarray(confidence)[rows, columns], 0.0, 1.0)[:, None]
        delta *= strength
    return result + delta


def extract_interface_runs(label_map: np.ndarray,
                           confidence: np.ndarray | None = None) -> tuple[InterfaceRun, ...]:
    labels = np.asarray(label_map, np.int32)
    height, width = labels.shape
    segments: dict[tuple[int, int], list[tuple[tuple[int, int], tuple[int, int], float]]] = collections.defaultdict(list)

    def add(a: int, b: int, p0: tuple[int, int], p1: tuple[int, int], cy: int, cx: int) -> None:
        if a == b:
            return
        pair = (min(a, b), max(a, b))
        conf = float(confidence[cy, cx]) if confidence is not None else 1.0
        segments[pair].append((p0, p1, conf))

    for y in range(height):
        for x in range(width - 1):
            add(int(labels[y, x]), int(labels[y, x + 1]), (x + 1, y), (x + 1, y + 1), y, x)
    for y in range(height - 1):
        for x in range(width):
            add(int(labels[y, x]), int(labels[y + 1, x]), (x, y + 1), (x + 1, y + 1), y, x)
    for x in range(width):
        add(OUTSIDE, int(labels[0, x]), (x, 0), (x + 1, 0), 0, x)
        add(OUTSIDE, int(labels[-1, x]), (x + 1, height), (x, height), height - 1, x)
    for y in range(height):
        add(OUTSIDE, int(labels[y, 0]), (0, y + 1), (0, y), y, 0)
        add(OUTSIDE, int(labels[y, -1]), (width, y), (width, y + 1), y, width - 1)

    runs: list[InterfaceRun] = []
    for pair, rows in sorted(segments.items()):
        for component in _connected_segment_components(rows):
            points, conf = _order_segment_chain(component)
            if len(points) >= 2:
                runs.append(InterfaceRun(pair[0], pair[1], points, conf))
    return tuple(runs)


def fit_interface_run(run: InterfaceRun) -> tuple[GeometryPrimitive, ...]:
    points = np.asarray(run.points, np.float64)
    if len(points) == 2:
        return (GeometryPrimitive("line", points=tuple(map(tuple, points)), provenance=("shared-interface",)),)
    centered = points - points.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    normal = vh[-1]
    residuals = centered @ normal
    sigma = np.maximum(0.15, 1.0 - np.asarray(run.confidence) * 0.75)
    line_cost = physical_residual_cost(residuals, points, sigma)
    direction = vh[0]
    projection = centered @ direction
    endpoints = np.vstack((points.mean(axis=0) + direction * projection.min(),
                           points.mean(axis=0) + direction * projection.max()))
    rms = float(np.sqrt(np.mean(residuals * residuals)))
    analytic: list[tuple[float, GeometryPrimitive]] = [(
        line_cost + .001,
        GeometryPrimitive("line", points=tuple(map(tuple, endpoints)),
                          confidence=float(math.exp(-line_cost)), evidence_rms_px=rms,
                          provenance=("shared-interface-pca-line",)),
    )]
    analytic.extend(_analytic_curve_candidates(points, sigma))
    best_cost, best_primitive = min(analytic, key=lambda row: row[0])
    if best_cost <= 0.24:
        return (best_primitive,)
    contour = points.astype(np.float32).reshape(-1, 1, 2)
    length = cv2.arcLength(contour, False)
    uncertainty = 1.0 - float(np.mean(run.confidence))
    epsilon = max(0.18, (0.004 + 0.012 * uncertainty) * length)
    approx = cv2.approxPolyDP(contour, epsilon, False)[:, 0, :].astype(np.float64)
    primitives = []
    for p0, p1 in zip(approx[:-1], approx[1:]):
        primitives.append(GeometryPrimitive("line", points=(tuple(p0), tuple(p1)),
                                            provenance=("shared-interface-polyline",)))
    return tuple(primitives) or (GeometryPrimitive("line", points=(tuple(points[0]), tuple(points[-1]))),)


def _analytic_curve_candidates(points: np.ndarray,
                               sigma: np.ndarray) -> list[tuple[float, GeometryPrimitive]]:
    result: list[tuple[float, GeometryPrimitive]] = []
    spans = np.linalg.norm(np.diff(points, axis=0), axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(spans)))
    if cumulative[-1] <= 1e-8:
        return result
    t = cumulative / cumulative[-1]
    p0, p3 = points[0], points[-1]
    x, y = points[:, 0], points[:, 1]
    try:
        center_solution, *_ = np.linalg.lstsq(
            np.column_stack((2 * x, 2 * y, np.ones(len(x)))),
            x * x + y * y, rcond=None)
        cx, cy, constant = center_solution
        radius2 = constant + cx * cx + cy * cy
        if radius2 > .25:
            radius = math.sqrt(radius2)
            angles = np.unwrap(np.arctan2(y - cy, x - cx))
            predicted = np.column_stack((cx + radius * np.cos(angles),
                                         cy + radius * np.sin(angles)))
            residual = np.linalg.norm(points - predicted, axis=1)
            cost = physical_residual_cost(residual, points, sigma) + .003
            span = float(angles[-1] - angles[0])
            if .08 <= abs(span) <= 2 * math.pi + .1:
                result.append((cost, GeometryPrimitive(
                    "circular-arc", (float(cx), float(cy), float(radius),
                                     float(angles[0]), float(angles[-1])),
                    confidence=float(math.exp(-cost)),
                    evidence_rms_px=float(np.sqrt(np.mean(residual ** 2))),
                    provenance=("shared-interface-circular-arc",),
                )))
    except np.linalg.LinAlgError:
        pass
    if len(points) >= 8:
        try:
            (cx, cy), (da, db), angle = cv2.fitEllipseDirect(
                points.astype(np.float32).reshape(-1, 1, 2))
            rx, ry = da * .5, db * .5
            if min(rx, ry) >= .5 and max(rx, ry) / min(rx, ry) <= 12:
                theta = math.radians(angle)
                rotation = np.array([[math.cos(theta), math.sin(theta)],
                                     [-math.sin(theta), math.cos(theta)]])
                local = (points - (cx, cy)) @ rotation.T
                angles = np.unwrap(np.arctan2(local[:, 1] / ry,
                                              local[:, 0] / rx))
                predicted_local = np.column_stack((rx * np.cos(angles),
                                                   ry * np.sin(angles)))
                predicted = predicted_local @ rotation + (cx, cy)
                residual = np.linalg.norm(points - predicted, axis=1)
                cost = physical_residual_cost(residual, points, sigma) + .005
                if .08 <= abs(angles[-1] - angles[0]) <= 2 * math.pi + .1:
                    result.append((cost, GeometryPrimitive(
                        "elliptical-arc", (float(cx), float(cy), float(rx), float(ry),
                                           float(angle), float(angles[0]), float(angles[-1])),
                        confidence=float(math.exp(-cost)),
                        evidence_rms_px=float(np.sqrt(np.mean(residual ** 2))),
                        provenance=("shared-interface-elliptical-arc",),
                    )))
        except cv2.error:
            pass
    basis = 2 * (1 - t) * t
    known = (1 - t)[:, None] ** 2 * p0 + t[:, None] ** 2 * p3
    if float(np.dot(basis, basis)) > 1e-9:
        control = np.sum(basis[:, None] * (points - known), axis=0) / np.dot(basis, basis)
        predicted = known + basis[:, None] * control
        residual = np.linalg.norm(points - predicted, axis=1)
        cost = physical_residual_cost(residual, points, sigma) + .004
        result.append((cost, GeometryPrimitive(
            "quadratic", points=(tuple(p0), tuple(control), tuple(p3)),
            confidence=float(math.exp(-cost)),
            evidence_rms_px=float(np.sqrt(np.mean(residual ** 2))),
            provenance=("shared-interface-quadratic-lsq",),
        )))
    b1 = 3 * (1 - t) ** 2 * t
    b2 = 3 * (1 - t) * t ** 2
    known = (1 - t)[:, None] ** 3 * p0 + t[:, None] ** 3 * p3
    design = np.column_stack((b1, b2))
    if np.linalg.matrix_rank(design) == 2:
        controls, *_ = np.linalg.lstsq(design, points - known, rcond=None)
        predicted = known + design @ controls
        residual = np.linalg.norm(points - predicted, axis=1)
        cost = physical_residual_cost(residual, points, sigma) + .006
        result.append((cost, GeometryPrimitive(
            "cubic", points=(tuple(p0), tuple(controls[0]), tuple(controls[1]), tuple(p3)),
            confidence=float(math.exp(-cost)),
            evidence_rms_px=float(np.sqrt(np.mean(residual ** 2))),
            provenance=("shared-interface-cubic-lsq",),
        )))
    return result


def fit_with_legacy_dp(points: np.ndarray, *, px: float = 1.0) -> tuple[GeometryPrimitive, ...]:
    """Lazy adapter to the current V-ICE directional interval-law fitter.

    It is intentionally not the default scene solver: it exists as a candidate
    and fallback, and importing the 650KB legacy monolith is avoided unless the
    caller explicitly requests this route.
    """
    from geometry_vectorizer import fit_loop_paper

    loop = np.asarray(points, np.float64).reshape(-1, 2)
    if len(loop) < 3:
        return ()
    if np.linalg.norm(loop[0] - loop[-1]) > 1e-8:
        loop = np.vstack((loop, loop[0]))
    fitted = fit_loop_paper(loop, px=px)
    result = []
    for curve in fitted.curves:
        control = np.asarray(curve.control, np.float64)
        kind = {1: "line", 2: "quadratic", 3: "cubic"}.get(int(curve.degree), "polyline")
        provenance = ("legacy-directional-interval-dp", fitted.template)
        result.append(GeometryPrimitive(kind, points=tuple(map(tuple, control)),
                                        provenance=provenance))
    return tuple(result)


def _connected_segment_components(rows: list[tuple[tuple[int, int], tuple[int, int], float]]) -> list[list[tuple]]:
    endpoint_map: dict[tuple[int, int], list[int]] = collections.defaultdict(list)
    for index, (p0, p1, _) in enumerate(rows):
        endpoint_map[p0].append(index)
        endpoint_map[p1].append(index)
    unseen = set(range(len(rows)))
    result = []
    while unseen:
        seed = unseen.pop()
        component = [seed]
        stack = [seed]
        while stack:
            index = stack.pop()
            for endpoint in rows[index][:2]:
                for neighbor in endpoint_map[endpoint]:
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        component.append(neighbor)
                        stack.append(neighbor)
        result.append([rows[index] for index in component])
    return result


def _order_segment_chain(rows: list[tuple[tuple[int, int], tuple[int, int], float]]) -> tuple[np.ndarray, np.ndarray]:
    adjacency: dict[tuple[int, int], list[tuple[tuple[int, int], float, int]]] = collections.defaultdict(list)
    for index, (p0, p1, conf) in enumerate(rows):
        adjacency[p0].append((p1, conf, index))
        adjacency[p1].append((p0, conf, index))
    starts = [point for point, edges in adjacency.items() if len(edges) == 1]
    current = min(starts or adjacency.keys())
    points = [current]
    confidences = [float(np.mean([edge[1] for edge in adjacency[current]]))]
    used: set[int] = set()
    while len(used) < len(rows):
        choices = [edge for edge in adjacency[current] if edge[2] not in used]
        if not choices:
            break
        nxt, conf, index = min(choices, key=lambda row: row[0])
        used.add(index)
        current = nxt
        points.append(current)
        confidences.append(conf)
    return np.asarray(points, np.float64), np.asarray(confidences, np.float32)

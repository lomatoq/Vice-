"""Dependency-neutral primitive fitting shared by both V-ICE lanes.

Plan S5 ("reusable legacy math to extract"): the geometry lane already owns
proven span fitting, but ``vice_compiler`` must not import the whole
``geometry_vectorizer`` module.  The pure math lives here - numpy only, no
compiler, no renderer, no cv2 - so the fair materializer and the legacy
vectorizer share one implementation instead of growing a third fitter.

Adapted from ``geometry_vectorizer`` (`_unit`, `_arc_center`,
`_cubic_control`, `_multiscale_corners`, `_fit_biarc`) with the same
mathematics and explicit units.
"""

from __future__ import annotations

import math

import numpy as np

EPSILON = 1.0e-9


def unit(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    return vector / length if length > EPSILON else np.array([1.0, 0.0])


def polyline_length(points: np.ndarray) -> float:
    if len(points) < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(points, axis=0), axis=1)))


def point_line_distance(
    points: np.ndarray, start: np.ndarray, end: np.ndarray,
) -> np.ndarray:
    """Perpendicular distance of each point to the infinite line start->end."""
    direction = end - start
    length = float(np.linalg.norm(direction))
    if length <= EPSILON:
        return np.linalg.norm(points - start, axis=1)
    normal = np.array([-direction[1], direction[0]]) / length
    return np.abs((points - start) @ normal)


def fit_line(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Endpoint line through the first/last sample plus its worst deviation."""
    start, end = points[0], points[-1]
    return start, end, float(np.max(point_line_distance(points, start, end)))


def fit_circle(
    points: np.ndarray,
) -> tuple[np.ndarray, float, float] | None:
    """Algebraic (Kasa) circle fit; returns (center, radius, max residual)."""
    if len(points) < 3:
        return None
    x = points[:, 0].astype(np.float64)
    y = points[:, 1].astype(np.float64)
    a = np.column_stack((2.0 * x, 2.0 * y, np.ones_like(x)))
    rhs = x * x + y * y
    try:
        solution, *_ = np.linalg.lstsq(a, rhs, rcond=None)
    except np.linalg.LinAlgError:
        return None
    cx, cy, c = (float(value) for value in solution[:3])
    squared = c + cx * cx + cy * cy
    if not math.isfinite(squared) or squared <= EPSILON:
        return None
    radius = math.sqrt(squared)
    center = np.array([cx, cy])
    residual = float(np.max(np.abs(
        np.linalg.norm(points - center, axis=1) - radius,
    )))
    if not math.isfinite(radius) or not math.isfinite(residual):
        return None
    return center, radius, residual


def arc_center(
    p0: np.ndarray, t0: np.ndarray, p1: np.ndarray,
) -> tuple[np.ndarray, float] | None:
    """Centre/radius of the circle through p0 with tangent t0 and through p1."""
    normal = np.array([-t0[1], t0[0]])
    delta = p1 - p0
    denominator = 2.0 * float(delta @ normal)
    if abs(denominator) < EPSILON:
        return None
    scale = float(delta @ delta) / denominator
    return p0 + scale * normal, abs(scale)


def cubic_control(
    points: np.ndarray, tangent_start: np.ndarray, tangent_end: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Least-squares cubic with fixed endpoints/tangents (2x2 normal equations).

    Returns (control points 4x2, predicted samples).
    """
    segment = np.linalg.norm(np.diff(points, axis=0), axis=1)
    parameter = np.concatenate(([0.0], np.cumsum(segment)))
    parameter = parameter / max(float(parameter[-1]), EPSILON)
    t = parameter[:, None]
    b0 = (1 - t) ** 3
    b1 = 3 * (1 - t) ** 2 * t
    b2 = 3 * (1 - t) * t ** 2
    b3 = t ** 3
    p0, p3 = points[0], points[-1]
    fixed = (b0 + b1) * p0 + (b2 + b3) * p3
    a = np.column_stack((
        (b1 * tangent_start).reshape(-1), (-b2 * tangent_end).reshape(-1),
    ))
    rhs = (points - fixed).reshape(-1)
    chord = max(float(np.linalg.norm(p3 - p0)), 1.0e-6)
    travel = max(float(np.sum(segment)), chord)
    maximum_handle = max(chord / 3.0, 0.65 * travel)
    try:
        alpha, beta = np.linalg.solve(a.T @ a, a.T @ rhs)
    except np.linalg.LinAlgError:
        alpha = beta = chord / 3.0
    if not (math.isfinite(alpha) and math.isfinite(beta)):
        alpha = beta = chord / 3.0
    alpha = float(np.clip(alpha, 0.0, maximum_handle))
    beta = float(np.clip(beta, 0.0, maximum_handle))
    control = np.vstack((
        p0, p0 + alpha * tangent_start, p3 - beta * tangent_end, p3,
    ))
    prediction = (
        b0 * control[0] + b1 * control[1] + b2 * control[2] + b3 * control[3]
    )
    return control, prediction


def fit_biarc(
    p0: np.ndarray, t0: np.ndarray, p1: np.ndarray, t1: np.ndarray,
):
    """Two G1 circular arcs from (p0,t0) to (p1,t1); monotone curvature each."""
    t0, t1 = unit(t0), unit(t1)
    delta = p1 - p0
    dot_tangents = float(t0 @ t1)
    b = float(delta @ (t0 + t1))
    vv = float(delta @ delta)
    denominator = 2.0 * (1.0 - dot_tangents)
    if denominator > 1.0e-6:
        d = (-b + math.sqrt(max(0.0, b * b + denominator * vv))) / denominator
    else:
        along = float(delta @ t0)
        if abs(along) < EPSILON:
            return None
        d = vv / (4.0 * along)
    if d <= 1.0e-6:
        return None
    joint = 0.5 * ((p0 + d * t0) + (p1 - d * t1))
    first = arc_center(p0, t0, joint)
    second = arc_center(joint, unit(joint - (p0 + d * t0)) if np.linalg.norm(
        joint - (p0 + d * t0),
    ) > EPSILON else t0, p1)
    if first is None or second is None:
        return None
    return joint, first, second


def resample_by_arclength(
    points: np.ndarray, *, step: float, closed: bool = True,
) -> np.ndarray:
    """Uniform arclength resampling; the invariant behind density-free costs."""
    samples = np.asarray(points, np.float64)
    if closed and len(samples) > 1 and not np.allclose(samples[0], samples[-1]):
        samples = np.vstack((samples, samples[:1]))
    segment = np.linalg.norm(np.diff(samples, axis=0), axis=1)
    total = float(np.sum(segment))
    if total <= EPSILON:
        return samples[:1]
    count = max(4, int(round(total / max(step, 1.0e-3))))
    cumulative = np.concatenate(([0.0], np.cumsum(segment)))
    targets = np.linspace(0.0, total, count, endpoint=not closed)
    x = np.interp(targets, cumulative, samples[:, 0])
    y = np.interp(targets, cumulative, samples[:, 1])
    return np.column_stack((x, y))


def polyline_tangents(points: np.ndarray, *, closed: bool = True) -> np.ndarray:
    """Central-difference unit tangents."""
    count = len(points)
    if count < 2:
        return np.tile(np.array([1.0, 0.0]), (count, 1))
    if closed:
        following = np.roll(points, -1, axis=0)
        previous = np.roll(points, 1, axis=0)
    else:
        following = np.vstack((points[1:], points[-1:]))
        previous = np.vstack((points[:1], points[:-1]))
    delta = following - previous
    lengths = np.linalg.norm(delta, axis=1)
    lengths[lengths < EPSILON] = 1.0
    return delta / lengths[:, None]


def multiscale_corner_indices(
    ring: np.ndarray, *, feature_scale: float, spacing: float,
    minimum_turn_deg: float = 32.0, persistence_ratio: float = 1.35,
) -> list[int]:
    """Corners whose turn persists across two physical neighbourhoods.

    Adapted from ``geometry_vectorizer._multiscale_corners``: a corner must
    be sharp at the fine scale AND survive the coarse scale, so antialiasing
    ripple cannot mint corners and a real corner is not smoothed away.
    Vectorized - the per-sample Python loop dominated the fair-curve profile.
    """
    count = len(ring)
    if count < 12:
        return []
    small = max(2, int(round(max(1.1, 1.25 * feature_scale) / max(spacing, 1e-6))))
    large = max(small + 2, int(round(2.5 * max(1.1, feature_scale) / max(spacing, 1e-6))))
    large = min(large, max(3, count // 7))

    def turns(step: int) -> np.ndarray:
        incoming = ring - np.roll(ring, step, axis=0)
        outgoing = np.roll(ring, -step, axis=0) - ring
        incoming_norm = np.maximum(np.linalg.norm(incoming, axis=1), EPSILON)
        outgoing_norm = np.maximum(np.linalg.norm(outgoing, axis=1), EPSILON)
        incoming = incoming / incoming_norm[:, None]
        outgoing = outgoing / outgoing_norm[:, None]
        cross = incoming[:, 0] * outgoing[:, 1] - incoming[:, 1] * outgoing[:, 0]
        dot = np.einsum("ij,ij->i", incoming, outgoing)
        return np.arctan2(cross, dot)

    fine = turns(small)
    coarse = turns(large)
    ratio = np.abs(fine) / np.maximum(np.abs(coarse), math.radians(2.0))
    persistent = (
        (np.abs(coarse) >= math.radians(minimum_turn_deg) * 0.5)
        & (ratio <= persistence_ratio * 2.0)
    )
    score = np.where(persistent, np.abs(fine), 0.0)

    threshold = math.radians(minimum_turn_deg)
    window = max(2, small)
    candidates = np.flatnonzero(score >= threshold)
    corners: list[int] = []
    for index in candidates.tolist():
        offsets = (np.arange(-window, window + 1) + index) % count
        if score[index] >= float(np.max(score[offsets])) - 1.0e-12:
            if not corners or min(
                (index - corners[-1]) % count, (corners[-1] - index) % count,
            ) >= window:
                corners.append(int(index))
    return corners

"""Geometry-first raster vectorizer with no vocabulary quotas.

Colour components become SVG regions with shared holes.  Complete rectangles
and ellipses are recognized globally; other boundaries are fitted adaptively.
"""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from vectorize_papers import (
    Curve,
    cad_regularize_ring,
    circular_beziers,
    eval_curve,
    extract_shape_masks,
    fit_circle,
    interpolate_ring,
    mask_loops,
    point_line_distance,
    resample_ring,
    signed_area,
    taubin_smooth_ring,
)


TYPE_COLORS = {"line": (38, 99, 235), "ellipse": (245, 145, 30), "curve": (196, 57, 173)}


@dataclass
class FittedLoop:
    source: np.ndarray
    curves: list[Curve]
    template: str


@dataclass
class Region:
    color: tuple[int, int, int]
    area: int
    loops: list[FittedLoop]
    # optional gradient fill (audit P2: banded shading merges into ONE region):
    #   ("linear", (x0, y0), (x1, y1), [(t, (r, g, b)), ...])
    #   ("radial", (cx, cy), r0, r1, [(t, (r, g, b)), ...])
    fill: tuple | None = None
    # optional stroke representation (audit P2: a constant-width ribbon is a
    # stroked CENTERLINE, not a filled outline): (width_px, [Curve, ...])
    stroke: tuple | None = None
    # METHOD_ICE 3.1 apron: abutting SVG paths leave an AA hairline where the
    # background bleeds between fills.  A region that has a LATER-painted
    # neighbour gets stroke=fill so its edge extends ~0.3px under that
    # neighbour (the neighbour paints over the excess).  Topmost/isolated
    # regions never bleed, so the outer silhouette stays crisp.
    bleed: bool = False


def perimeter(loop: np.ndarray) -> float:
    return float(np.sum(np.linalg.norm(np.diff(loop, axis=0), axis=1)))


def _ellipse_curves(center: np.ndarray, axes: np.ndarray, angle: float) -> list[Curve]:
    k = 0.5522847498307936
    rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])

    def p(x: float, y: float) -> np.ndarray:
        return center + rotation @ (np.array([x, y]) * axes)

    return [
        Curve(3, np.vstack((p(1, 0), p(1, k), p(k, 1), p(0, 1)))),
        Curve(3, np.vstack((p(0, 1), p(-k, 1), p(-1, k), p(-1, 0)))),
        Curve(3, np.vstack((p(-1, 0), p(-1, -k), p(-k, -1), p(0, -1)))),
        Curve(3, np.vstack((p(0, -1), p(k, -1), p(1, -k), p(1, 0)))),
    ]


def _ellipse_candidate(loop: np.ndarray) -> tuple[float, float, list[Curve]] | None:
    points = loop[:-1].astype(np.float32)
    if len(points) < 12:
        return None
    try:
        (cx, cy), (width, height), degrees = cv2.fitEllipseDirect(points.reshape(-1, 1, 2))
    except cv2.error:
        return None
    if width < 2 or height < 2:
        return None
    angle = math.radians(degrees)
    rotation = np.array([[math.cos(angle), math.sin(angle)], [-math.sin(angle), math.cos(angle)]])
    local = (points - np.array([cx, cy])) @ rotation.T
    axes = np.array([width / 2, height / 2])
    radial = np.sqrt(np.sum((local / axes) ** 2, axis=1))
    error = float(np.sqrt(np.mean(((radial - 1) * min(axes)) ** 2)))
    # Relative circle court (blind roundness target: our small discs shipped
    # 0.02-0.03R eccentric while VAI snaps perfect circles; the failed
    # absolute-budget rescue taught us the judgement must be RELATIVE).  When
    # the fitted ellipse is nearly isotropic, refit an ideal circle and let
    # the residuals compete: the circle wins unless it is measurably worse
    # (+0.15px, well inside the 0.5px evidence tube).  A genuine oval
    # (digital-ocean drop) keeps a big residual gap and survives untouched.
    if float(min(axes)) / float(max(axes)) >= 0.75:
        circ = fit_circle(points.astype(float))
        if circ is not None:
            c_center, c_radius, c_rms = circ
            if (c_radius >= 1.0 and c_radius <= 1.3 * float(max(axes))
                    and float(c_rms) <= error + 0.15):
                return (float(c_rms), float(c_radius),
                        _ellipse_curves(np.asarray(c_center, float),
                                        np.array([c_radius, c_radius]), 0.0))
    return error, float(min(axes)), _ellipse_curves(np.array([cx, cy]), axes, angle)


def _rectangle_candidate(loop: np.ndarray) -> tuple[float, list[Curve]] | None:
    points = loop[:-1].astype(np.float32)
    if len(points) < 8:
        return None
    rect = cv2.minAreaRect(points.reshape(-1, 1, 2))
    box = cv2.boxPoints(rect).astype(float)
    errors = []
    for p in points:
        errors.append(min(float(point_line_distance(p[None, :], box[i], box[(i + 1) % 4])[0]) for i in range(4)))
    error = float(np.sqrt(np.mean(np.square(errors))))
    curves = [Curve(1, np.vstack((box[i], box[(i + 1) % 4]))) for i in range(4)]
    return error, curves


def _unit(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    return vector / length if length > 1e-9 else np.array([1.0, 0.0])


def _ring_slice(ring: np.ndarray, start: int, end: int) -> np.ndarray:
    if end >= start:
        return ring[start : end + 1]
    return np.vstack((ring[start:], ring[: end + 1]))


def _multiscale_corners(ring: np.ndarray, feature_scale: float, spacing: float) -> list[int]:
    """Find corners whose turn persists across two physical neighbourhoods."""
    n = len(ring)
    if n < 12:
        return []
    small = max(2, int(round(max(1.1, 1.25 * feature_scale) / spacing)))
    large = max(small + 2, int(round(2.5 * max(1.1, feature_scale) / spacing)))
    large = min(large, max(3, n // 7))
    score = np.zeros(n, dtype=float)
    signed = np.zeros(n, dtype=float)
    for i in range(n):
        turns = []
        for step in (small, large):
            incoming = _unit(ring[i] - ring[(i - step) % n])
            outgoing = _unit(ring[(i + step) % n] - ring[i])
            turns.append(math.atan2(float(np.cross(incoming, outgoing)), float(np.dot(incoming, outgoing))))
        fine, coarse = turns
        ratio = abs(fine) / max(abs(coarse), math.radians(2.0))
        if abs(fine) >= math.radians(17.0) and abs(coarse) >= math.radians(23.0) and ratio >= 0.70:
            score[i] = abs(fine) * min(ratio, 1.25)
            signed[i] = fine

    candidates = list(np.flatnonzero(score > 0))
    candidates.sort(key=lambda i: score[i], reverse=True)
    separation = max(small * 2, int(round(1.5 * feature_scale / spacing)))
    chosen: list[int] = []
    for index in candidates:
        if all(min((index - old) % n, (old - index) % n) > separation for old in chosen):
            chosen.append(int(index))
    return sorted(chosen)


def _cubic_control(points: np.ndarray, tangent_start: np.ndarray, tangent_end: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    segment = np.linalg.norm(np.diff(points, axis=0), axis=1)
    parameter = np.concatenate(([0.0], np.cumsum(segment)))
    parameter /= max(float(parameter[-1]), 1e-9)
    t = parameter[:, None]
    b0 = (1 - t) ** 3
    b1 = 3 * (1 - t) ** 2 * t
    b2 = 3 * (1 - t) * t**2
    b3 = t**3
    p0, p3 = points[0], points[-1]
    fixed = (b0 + b1) * p0 + (b2 + b3) * p3
    a = np.column_stack(((b1 * tangent_start).reshape(-1), (-b2 * tangent_end).reshape(-1)))
    rhs = (points - fixed).reshape(-1)
    # 2x2 normal equations instead of lstsq(SVD): same result for 2 unknowns, far cheaper
    # (this is the DP's hottest call).
    ata = a.T @ a
    try:
        alpha, beta = np.linalg.solve(ata, a.T @ rhs)
    except np.linalg.LinAlgError:
        alpha = beta = float(np.linalg.norm(p3 - p0)) / 3.0
    chord = max(float(np.linalg.norm(p3 - p0)), 1e-6)
    travel = max(float(np.sum(segment)), chord)
    maximum_handle = max(chord / 3.0, 0.65 * travel)
    replacement = min(maximum_handle, travel / 3.0)
    if alpha <= 0 or alpha > maximum_handle:
        alpha = replacement
    if beta <= 0 or beta > maximum_handle:
        beta = replacement
    control = np.vstack((p0, p0 + alpha * tangent_start, p3 - beta * tangent_end, p3))
    prediction = (
        b0 * control[0]
        + b1 * control[1]
        + b2 * control[2]
        + b3 * control[3]
    )
    return control, prediction


def _arc_center(p0: np.ndarray, t0: np.ndarray, p1: np.ndarray):
    """Centre+radius of the circle through p0 (tangent t0) and p1; None if straight."""
    n0 = np.array([-t0[1], t0[0]])
    w = p1 - p0
    denom = 2.0 * float(w @ n0)
    if abs(denom) < 1e-9:
        return None
    s = float(w @ w) / denom
    return p0 + s * n0, abs(s)


def _fit_biarc(p0: np.ndarray, t0: np.ndarray, p1: np.ndarray, t1: np.ndarray):
    """Paper Sec 5.1 clothoid stand-in: two circular arcs meeting G1, from (p0,t0) to
    (p1,t1).  Each arc has constant (so MONOTONE) curvature, so a biarc physically cannot
    overshoot or loop the way a cubic Bezier does — it removes the S-hook artefacts.
    Returns (joint, (c1,r1), (c2,r2)) or None when degenerate (caller falls back)."""
    t0, t1 = _unit(t0), _unit(t1)
    v = p1 - p0
    dott = float(t0 @ t1)
    b = float(v @ (t0 + t1))
    vv = float(v @ v)
    denom = 2.0 * (1.0 - dott)
    if denom > 1e-6:
        d = (-b + math.sqrt(max(0.0, b * b + denom * vv))) / denom
    else:
        db = float(v @ t0)
        if abs(db) < 1e-9:
            return None
        d = vv / (4.0 * db)
    if d <= 1e-6:
        return None
    joint = 0.5 * ((p0 + d * t0) + (p1 - d * t1))
    c1 = _arc_center(p0, t0, joint)
    c2 = _arc_center(p1, -t1, joint)
    if c1 is None or c2 is None or c1[1] < 0.5 or c2[1] < 0.5:
        return None
    return joint, c1, c2


def _biarc_curves(p0: np.ndarray, t0: np.ndarray, p1: np.ndarray, t1: np.ndarray, arc_pts: np.ndarray) -> list[Curve] | None:
    """Draw a biarc as two arc-approximating cubic-Bezier runs; None if degenerate."""
    fit = _fit_biarc(p0, t0, p1, t1)
    if fit is None:
        return None
    joint, (c1, r1), (c2, r2) = fit
    half = len(arc_pts) // 2
    curves = circular_beziers(p0, joint, c1, r1, arc_pts[: half + 1] if half >= 1 else arc_pts)
    curves += circular_beziers(joint, p1, c2, r2, arc_pts[half:] if half >= 1 else arc_pts)
    return curves or None


def _fit_g1_span(
    points: np.ndarray,
    tangent_start: np.ndarray,
    tangent_end: np.ndarray,
    tolerance: float,
    depth: int = 0,
) -> list[Curve]:
    if len(points) <= 3:
        chord = float(np.linalg.norm(points[-1] - points[0]))
        return [Curve(3, np.vstack((points[0], points[0] + tangent_start * chord / 3, points[-1] - tangent_end * chord / 3, points[-1])))]
    control, prediction = _cubic_control(points, tangent_start, tangent_end)
    errors = np.linalg.norm(prediction - points, axis=1)
    split = int(np.argmax(errors))
    if float(errors[split]) <= tolerance or depth >= 12 or len(points) < 8:
        return [Curve(3, control)]
    split = max(3, min(len(points) - 4, split))
    tangent = _unit(points[split + 1] - points[split - 1])
    return _fit_g1_span(points[: split + 1], tangent_start, tangent, tolerance, depth + 1) + _fit_g1_span(
        points[split:], tangent, tangent_end, tolerance, depth + 1
    )


def _fit_supported_span(
    points: np.ndarray,
    tangent_start: np.ndarray,
    tangent_end: np.ndarray,
    feature_scale: float,
) -> tuple[str, list[Curve]]:
    travel = float(np.sum(np.linalg.norm(np.diff(points, axis=0), axis=1)))
    chord = float(np.linalg.norm(points[-1] - points[0]))
    line_error = float(np.max(point_line_distance(points, points[0], points[-1])))
    line_support = max(4.5, 5.5 * feature_scale)
    line_tolerance = 0.16 + 0.035 * feature_scale
    if travel >= line_support and line_error <= line_tolerance and travel <= chord * 1.018 + 1e-6:
        return "line", [Curve(1, np.vstack((points[0], points[-1])))]

    circle = fit_circle(points)
    if circle is not None:
        center, radius, residual = circle
        sweep = travel / max(radius, 1e-6)
        if travel >= max(4.0, 4.5 * feature_scale) and residual <= 0.17 + 0.04 * feature_scale and 0.32 <= sweep <= math.pi * 1.15:
            return "arc", circular_beziers(points[0], points[-1], center, radius, points)

    tolerance = 0.16 + 0.045 * feature_scale
    return "curve", _fit_g1_span(points, tangent_start, tangent_end, tolerance)


def _global_dp_span(
    points: np.ndarray,
    tangent_start: np.ndarray,
    tangent_end: np.ndarray,
    feature_scale: float,
) -> list[Curve]:
    """Globally choose Line/Arc/Cubic hypotheses inside an uncertainty band.

    Unlike the recursive fitter, this keeps several explanations alive and
    applies a description-length penalty.  A primitive must explain a complete
    interval; fitting a tiny staircase fragment is therefore not rewarded.
    """
    if len(points) < 7:
        return _fit_g1_span(points, tangent_start, tangent_end, 0.24 + 0.05 * feature_scale)
    spacing = float(np.median(np.linalg.norm(np.diff(points, axis=0), axis=1)))
    stride = max(3, int(round(max(1.8, 2.2 * feature_scale) / max(spacing, 0.2))))
    nodes = list(range(0, len(points) - 1, stride))
    if nodes[-1] != len(points) - 1:
        nodes.append(len(points) - 1)
    # This is a localization uncertainty, not a smoothing radius.  Keeping it
    # below roughly half an original pixel prevents a compact solution from
    # cutting across narrow notches and counters.
    band = 0.28 + 0.08 * feature_scale
    count = len(nodes)
    inf = float("inf")
    dp = [inf] * count
    previous: list[tuple[int, list[Curve], str] | None] = [None] * count
    dp[0] = 0.0

    def tangent(index: int) -> np.ndarray:
        if index <= 0:
            return tangent_start
        if index >= len(points) - 1:
            return tangent_end
        return _unit(points[index + 1] - points[index - 1])

    for j in range(1, count):
        # Long support remains possible, but quadratic work is bounded on very
        # large outlines by considering the preceding 22 candidate nodes.
        for i in range(max(0, j - 22), j):
            a, b = nodes[i], nodes[j]
            sample = points[a : b + 1]
            if len(sample) < 3:
                continue
            travel = float(np.sum(np.linalg.norm(np.diff(sample, axis=0), axis=1)))
            options: list[tuple[float, str, list[Curve]]] = []

            line_errors = point_line_distance(sample, sample[0], sample[-1])
            line_limit = min(band, 0.24 + 0.045 * feature_scale)
            if travel >= max(2.2, 2.8 * feature_scale) and float(line_errors.max()) <= line_limit:
                fidelity = 0.065 * float(np.sum((line_errors / band) ** 2))
                options.append((0.34 + fidelity, "line", [Curve(1, np.vstack((sample[0], sample[-1])))]))

            circle = fit_circle(sample)
            if circle is not None:
                center, radius, _ = circle
                radial = np.abs(np.linalg.norm(sample - center, axis=1) - radius)
                sweep = travel / max(radius, 1e-6)
                arc_limit = min(band, 0.32 + 0.055 * feature_scale)
                if travel >= max(3.0, 3.5 * feature_scale) and float(radial.max()) <= arc_limit and 0.28 <= sweep <= math.pi * 1.2:
                    arc_curves = circular_beziers(sample[0], sample[-1], center, radius, sample)
                    if arc_curves:
                        rendered_arc = np.vstack(
                            [chunk if index == 0 else chunk[1:] for index, chunk in enumerate(eval_curve(curve, 28) for curve in arc_curves)]
                        )
                        # A circle has two branches between its endpoints.  A
                        # radial residual alone cannot detect choosing the wrong
                        # branch, so verify the actual generated path too.
                        branch_error = np.sqrt(
                            np.min(np.sum((rendered_arc[:, None, :] - sample[None, :, :]) ** 2, axis=2), axis=1)
                        )
                        if float(branch_error.max()) <= band:
                            fidelity = 0.06 * float(np.sum((radial / band) ** 2))
                            options.append((0.56 + fidelity, "arc", arc_curves))

            control, prediction = _cubic_control(sample, tangent(a), tangent(b))
            cubic_errors = np.linalg.norm(prediction - sample, axis=1)
            if float(cubic_errors.max()) <= band:
                fidelity = 0.052 * float(np.sum((cubic_errors / band) ** 2))
                options.append((0.92 + fidelity, "cubic", [Curve(3, control)]))

            for local_cost, kind, curves in options:
                cost = dp[i] + local_cost
                if cost < dp[j]:
                    dp[j] = cost
                    previous[j] = (i, curves, kind)

    if previous[-1] is None:
        # If the strict uncertainty tube has no complete DP path, preserve the
        # proven high-fidelity local solution instead of relaxing the tube.
        _, fallback = _fit_supported_span(points, tangent_start, tangent_end, feature_scale)
        return fallback
    chunks: list[list[Curve]] = []
    cursor = count - 1
    while cursor > 0 and previous[cursor] is not None:
        old, curves, _ = previous[cursor]
        chunks.append(curves)
        cursor = old
    chunks.reverse()
    return [curve for chunk in chunks for curve in chunk]


def _smooth_closed_chain(ring: np.ndarray, feature_scale: float, global_fit: bool = False) -> list[Curve]:
    """Fit a corner-free closed curve as four G1-compatible cubic spans."""
    n = len(ring)
    cuts = sorted(set(int(round(i * n / 4)) % n for i in range(4)))
    curves: list[Curve] = []
    for i, start in enumerate(cuts):
        end = cuts[(i + 1) % len(cuts)]
        points = _ring_slice(ring, start, end)
        tangent_start = _unit(ring[(start + 1) % n] - ring[(start - 1) % n])
        tangent_end = _unit(ring[(end + 1) % n] - ring[(end - 1) % n])
        if global_fit:
            fitted = _global_dp_span(points, tangent_start, tangent_end, feature_scale)
        else:
            _, fitted = _fit_supported_span(points, tangent_start, tangent_end, feature_scale)
        curves.extend(fitted)
    return curves


def _rounded_corner_chain(
    ring: np.ndarray,
    corners: list[int],
    feature_scale: float,
    spacing: float,
    global_fit: bool = False,
) -> list[Curve]:
    n = len(ring)
    cuts = max(1, int(round(max(0.28, 0.55 * feature_scale) / spacing)))
    records = []
    for position, corner in enumerate(corners):
        previous_corner = corners[position - 1]
        next_corner = corners[(position + 1) % len(corners)]
        distance_before = (corner - previous_corner) % n
        distance_after = (next_corner - corner) % n
        previous = ring[(corner - cuts) % n]
        point = ring[corner]
        following = ring[(corner + cuts) % n]
        incoming = _unit(point - previous)
        outgoing = _unit(following - point)
        turn = abs(math.atan2(float(np.cross(incoming, outgoing)), float(np.dot(incoming, outgoing))))
        # More acute corners receive a slightly larger fillet, but never enough
        # to consume the neighbouring feature.
        desired = max(1, int(round(cuts * (0.75 + 0.45 * min(turn / (math.pi / 2), 1.4)))))
        # Adjacent tiny features must not have overlapping fillets: that would
        # make the closed traversal wrap around the complete ring and produce a
        # long diagonal across letters such as B or C.
        adaptive = min(desired, max(1, min(distance_before, distance_after) // 3))
        records.append(
            {
                "corner": corner,
                "pre_i": (corner - adaptive) % n,
                "post_i": (corner + adaptive) % n,
                "pre": ring[(corner - adaptive) % n],
                "point": point,
                "post": ring[(corner + adaptive) % n],
            }
        )

    curves: list[Curve] = []
    for i, record in enumerate(records):
        # A quadratic with its control at the detected vertex is tangent to both
        # incident directions.  At icon scale it is an excellent circular
        # fillet approximation and mirrors VAI's common Q/L corner structure.
        curves.append(Curve(2, np.vstack((record["pre"], record["point"], record["post"]))))
        following = records[(i + 1) % len(records)]
        span = _ring_slice(ring, record["post_i"], following["pre_i"])
        if len(span) < 2:
            continue
        tangent_start = _unit(record["post"] - record["point"])
        tangent_end = _unit(following["point"] - following["pre"])
        span_travel = float(np.sum(np.linalg.norm(np.diff(span, axis=0), axis=1)))
        if global_fit and span_travel >= max(8.0, 8.0 * feature_scale):
            fitted = _global_dp_span(span, tangent_start, tangent_end, feature_scale)
        else:
            _, fitted = _fit_supported_span(span, tangent_start, tangent_end, feature_scale)
        curves.extend(fitted)
    return curves


# ------- Paper Sec 5: corner set = learned classifier (Sec 4) + iterated removal -------

_CORNER_MODEL: tuple | None = None
_PAPER_ACC = 0.7  # fitting accuracy bound to edge midpoints (native px)
_OBTUSE_TURN = 60.0  # Sec 5.2.1: a corner with turn < 60 deg (interior > 120) is a gentle bend
_AXIS_TOL = 1.0      # Sec 6: max px an axis/parallel snap may move the boundary (accuracy budget)


def _corner_model():
    global _CORNER_MODEL
    if _CORNER_MODEL is None:
        from corner_classifier import load

        _CORNER_MODEL = load()
    return _CORNER_MODEL


_CORNER_THRESHOLDS: dict | None = None


def _corner_threshold(resolution: float) -> float:
    """Paper Fig 7 per-resolution operating point: the lax cutoff calibrated to ~95%
    recall at the nearest trained resolution; falls back to the fixed lax default."""
    global _CORNER_THRESHOLDS
    if _CORNER_THRESHOLDS is None:
        from corner_classifier import load_thresholds

        _CORNER_THRESHOLDS = load_thresholds() or {}
    if not _CORNER_THRESHOLDS:
        return _CORNER_LAX_THRESHOLD
    nearest = min(_CORNER_THRESHOLDS, key=lambda r: abs(float(r) - resolution))
    return float(_CORNER_THRESHOLDS[nearest])


def _arc_slice(loop: np.ndarray, a: int, b: int) -> np.ndarray:
    return loop[a : b + 1] if b >= a else np.vstack((loop[a:], loop[: b + 1]))


def _clothoid_fit(sub: np.ndarray):
    """LSQ Euler-spiral (clothoid) fit — the paper's true Sec 5.1 r=4 primitive.

    The tangent angle of a clothoid is QUADRATIC in arclength (curvature linear),
    so the family is fitted EXACTLY by least squares on the step tangent angles:
    theta(s) = a + b*s + c*s^2.  Positions are recovered by trapezoid integration
    at the data arclengths (sub-0.01px at midpoint density) and translated to the
    optimal overlay.  Returns (poly, t_start, t_end, (a, b, c, L)) or None."""
    steps = np.diff(sub, axis=0)
    ds = np.linalg.norm(steps, axis=1)
    if len(ds) < 4 or float(ds.min()) <= 1e-9:
        return None
    s = np.concatenate(([0.0], np.cumsum(ds)))
    length = float(s[-1])
    if length < 1e-6:
        return None
    ang = np.unwrap(np.arctan2(steps[:, 1], steps[:, 0]))
    sm = 0.5 * (s[:-1] + s[1:])                       # step tangent lives mid-step
    basis = np.stack([np.ones_like(sm), sm, sm * sm], axis=1)
    try:
        coef, *_ = np.linalg.lstsq(basis, ang, rcond=None)
    except np.linalg.LinAlgError:
        return None
    a0, b0, c0 = (float(v) for v in coef)
    theta = a0 + b0 * s + c0 * s * s
    dirs = np.stack([np.cos(theta), np.sin(theta)], axis=1)
    poly = np.zeros_like(sub)
    poly[1:] = np.cumsum(0.5 * (dirs[:-1] + dirs[1:]) * ds[:, None], axis=0)
    # Similarity (Procrustes) alignment instead of pure translation: on raster
    # cracks the polyline arclength is Manhattan-inflated (~1.3x for diagonals),
    # so the integrated spiral overshoots.  A scaled/rotated clothoid is still a
    # clothoid (k' = k/gamma), so aligning within the family fixes this exactly.
    x = poly - poly.mean(axis=0)
    y = sub - sub.mean(axis=0)
    dot = float(np.sum(x * y))
    crs = float(np.sum(x[:, 0] * y[:, 1] - x[:, 1] * y[:, 0]))
    norm_x = float(np.sum(x * x))
    if norm_x < 1e-9:
        return None
    phi = math.atan2(crs, dot)
    gamma = (dot * math.cos(phi) + crs * math.sin(phi)) / norm_x
    if not (0.5 <= gamma <= 2.0):
        return None
    rot = np.array([[math.cos(phi), -math.sin(phi)], [math.sin(phi), math.cos(phi)]])
    poly = gamma * (x @ rot.T) + sub.mean(axis=0)
    theta = theta + phi
    a0, b0, c0, length = a0 + phi, b0 / gamma, c0 / (gamma * gamma), gamma * length
    ts = np.array([math.cos(theta[0]), math.sin(theta[0])])
    te = np.array([math.cos(theta[-1]), math.sin(theta[-1])])
    return poly, ts, te, (a0, b0, c0, length)


def _clothoid_curves(sub: np.ndarray, params: tuple, start: np.ndarray, end: np.ndarray) -> list[Curve]:
    """Draw a fitted clothoid as 1-4 tangent-matched cubics (SVG has no spiral
    primitive), each covering <=90 deg of turn; endpoints snap to the segment's
    corner vertices with the sub-px closure drift distributed along the curve."""
    a0, b0, c0, length = params
    n = max(24, min(160, int(length * 2)))
    s = np.linspace(0.0, length, n)
    theta = a0 + b0 * s + c0 * s * s
    dirs = np.stack([np.cos(theta), np.sin(theta)], axis=1)
    ds = np.diff(s)[:, None]
    poly = np.zeros((n, 2))
    poly[1:] = np.cumsum(0.5 * (dirs[:-1] + dirs[1:]) * ds, axis=0)
    poly += start - poly[0]
    # Close the sub-px endpoint drift with a SIMILARITY about the start point:
    # a rotated+scaled clothoid is still a clothoid (b/=gamma, c/=gamma^2 in
    # arclength), whereas the old linear shear (+= linspace*(drift)) left the
    # family and slightly bent the spiral (audited Stage-2.4 fix).
    chord_have = poly[-1] - poly[0]
    chord_want = np.asarray(end, float) - poly[0]
    nh, nw = float(np.linalg.norm(chord_have)), float(np.linalg.norm(chord_want))
    ang = 0.0
    gamma = 1.0
    if nh > 1e-9 and nw > 1e-9:
        ang = math.atan2(chord_have[0] * chord_want[1] - chord_have[1] * chord_want[0],
                         float(chord_have @ chord_want))
        gamma = nw / nh
    if abs(ang) <= math.radians(2.0) and 0.97 <= gamma <= 1.03:
        # small drift: close it in-family (the rotation also turns the start
        # tangent, so only a tiny one is legal — bigger drifts keep the shear)
        ca, sa = math.cos(ang), math.sin(ang)
        rot = np.array([[ca, -sa], [sa, ca]]) * gamma
        poly = (poly - poly[0]) @ rot.T + poly[0]
    else:
        poly += np.linspace(0.0, 1.0, n)[:, None] * (end - poly[-1])
    total_turn = abs(b0 * length + c0 * length * length)
    pieces = max(1, min(4, int(math.ceil(total_turn / (0.5 * math.pi)))))
    bounds = np.linspace(0, n - 1, pieces + 1).astype(int)
    _ARC_RUN_ID[0] += 1
    meta = ("clothoid", _ARC_RUN_ID[0], float(b0), float(b0 + 2.0 * c0 * length), float(length))
    out: list[Curve] = []
    for i in range(pieces):
        piece = poly[bounds[i]: bounds[i + 1] + 1]
        if len(piece) < 2:
            continue
        t0 = _unit(piece[min(1, len(piece) - 1)] - piece[0])
        t1 = _unit(piece[-1] - piece[max(-2, -len(piece))])
        control, _ = _cubic_control(piece, t0, t1)
        curve = Curve(3, control)
        curve.meta = meta
        out.append(curve)
    return out


def _single_primitive_fit(points: np.ndarray, acc: float):
    """Cheapest SINGLE primitive (line r=1 / arc r=2 / clothoid or cubic r=4) within
    `acc`.  Returns (D, R, t_start, t_end) with unit end tangents of the FITTED
    primitive (noise-free, unlike raw-polyline windows), or (inf, inf, None, None)."""
    if len(points) < 3:
        return 0.0, 1.0, None, None
    mid = 0.5 * (points[:-1] + points[1:])
    if len(mid) < 2:
        return 0.0, 1.0, None, None
    if len(mid) > 160:                                   # big spans (removal ring refits on
        mid = mid[np.linspace(0, len(mid) - 1, 160).astype(int)]   # 1500-vert loops) dominated
                                                         # runtime; a 160-pt subsample keeps
                                                         # the cost estimate faithful
    # LSQ line, not the endpoint chord — quantized endpoints tilt a long chord and
    # its mid-span leaves `acc`, capping how much a removal merge can straighten.
    centre_l = mid.mean(axis=0)
    _, _, vt_l = np.linalg.svd(mid - centre_l, full_matrices=False)
    du_l = vt_l[0]
    if float(du_l @ (mid[-1] - mid[0])) < 0:
        du_l = -du_l
    line_dev = np.abs((mid - centre_l) @ np.array([-du_l[1], du_l[0]]))
    if float(line_dev.max()) <= acc:                     # gate on max; D = L1 SUM (paper Eq 2)
        return float(line_dev.sum()), 1.0, du_l, du_l
    circle = fit_circle(mid)
    if circle is not None:
        center, radius, _ = circle
        radial_dev = np.abs(np.linalg.norm(mid - center, axis=1) - radius)
        radial = float(radial_dev.max())
        if radial <= acc and radius >= 1.0:
            def arc_tan(p: np.ndarray, travel: np.ndarray) -> np.ndarray:
                rad = p - center
                tang = np.array([-rad[1], rad[0]])
                if float(tang @ travel) < 0:
                    tang = -tang
                return _unit(tang)
            ts = arc_tan(mid[0], mid[1] - mid[0])
            te = arc_tan(mid[-1], mid[-1] - mid[-2])
            return float(radial_dev.sum()), 2.0, ts, te
    clothoid = _clothoid_fit(mid)
    if clothoid is not None:
        poly, ts, te, _ = clothoid
        clothoid_dev = np.linalg.norm(poly - mid, axis=1)
        if float(clothoid_dev.max()) <= acc:
            # variable-curvature spans (bar sides, letter bowls) fit ONE clothoid
            # where neither line, arc nor a hooked cubic passes — this is what
            # makes spurious lax corners on such spans removable (Sec 5.2)
            return float(clothoid_dev.sum()), 4.0, ts, te
    _, prediction = _cubic_control(mid, _unit(mid[1] - mid[0]), _unit(mid[-1] - mid[-2]))
    cubic_dev = np.linalg.norm(prediction - mid, axis=1)
    if float(cubic_dev.max()) <= acc:
        return float(cubic_dev.sum()), 4.0, _unit(prediction[1] - prediction[0]), _unit(prediction[-1] - prediction[-2])
    return float("inf"), float("inf"), None, None


def _single_primitive_cost(points: np.ndarray, acc: float) -> tuple[float, float]:
    d, r, _, _ = _single_primitive_fit(points, acc)
    return d, r


def _split_candidates(points: np.ndarray) -> list[int]:
    """Candidate split vertices for a multi-primitive fit: quartiles + up to four local
    TURNING PEAKS (line->arc tangencies live at local turning maxima — quartiles alone
    never isolate a small cap on a long ring)."""
    n = len(points)
    cands = {n // 4, n // 2, (3 * n) // 4}
    if n >= 16:
        w = 6                                            # +-6: above staircase noise scale
        a = points[w:-w] - points[:-2 * w]
        b = points[2 * w:] - points[w:-w]
        na = np.linalg.norm(a, axis=1)
        nb = np.linalg.norm(b, axis=1)
        ok = (na > 1e-9) & (nb > 1e-9)
        if ok.any():
            cosv = np.full(len(a), 1.0)
            cosv[ok] = np.clip(np.einsum("ij,ij->i", a[ok], b[ok]) / (na[ok] * nb[ok]), -1.0, 1.0)
            order = np.argsort(cosv)                     # sharpest first
            picked: list[int] = []
            for idx in order:
                if cosv[idx] > math.cos(math.radians(12.0)):
                    break                                # remaining are near-straight
                k = int(idx) + w
                if all(abs(k - q) >= 10 for q in picked):
                    picked.append(k)
                    if len(picked) >= 6:
                        break
            cands.update(picked)
    return sorted(k for k in cands if 4 <= k <= n - 5)


def _segment_cost(points: np.ndarray, acc: float = _PAPER_ACC, max_prims: int = 3) -> tuple[float, float]:
    """Cheapest multi-primitive fit (D=summed max-deviations, R=summed type costs) of the
    segment's edge midpoints within `acc` per piece; (inf, inf) if even `max_prims` pieces
    cannot fit (a real corner is inside).

    Paper Sec 5.2 RE-VECTORIZES the merged segment when scoring a corner removal — a single
    primitive is the wrong surrogate: a bar CAP (side line + tangent arc) merges into
    line+arc, and removing BOTH cap corners needs line+arc+line.  With the single-primitive
    test those merges cost inf and cap corners were mathematically unremovable (audit probe).
    Splits are searched recursively over quartile + sharpest-vertex candidates.

    `acc` must exceed the raster staircase amplitude (~1px on the detection loop) so a
    smooth arc split by a spurious corner CAN re-merge, yet stay below a real corner's
    >=2px jut so true corners never merge away."""
    n_total = len(points)
    memo: dict[tuple[int, int], tuple] = {}
    g1_cos = math.cos(math.radians(20.0))

    def best(off: int, prims: int):
        """(D, R, t_start, t_end) of the cheapest G1-legal decomposition of points[off:]."""
        key = (off, prims)
        if key in memo:
            return memo[key]
        sub = points[off:]
        d, r, ts, te = _single_primitive_fit(sub, acc)
        if math.isfinite(r):
            memo[key] = (d, r, ts, te)
            return memo[key]
        if prims <= 1 or len(sub) < 10:
            memo[key] = (float("inf"), float("inf"), None, None)
            return memo[key]
        found = (float("inf"), float("inf"), None, None)
        for k in _split_candidates(sub):
            d1, r1, ts1, te1 = _single_primitive_fit(sub[: k + 1], acc)
            if not math.isfinite(r1):
                continue
            d2, r2, ts2, te2 = best(off + k, prims - 1)
            if not math.isfinite(r2):
                continue
            # Paper Sec 5.1: primitives INSIDE a segment join G1 — gate on the FITTED
            # primitives' end tangents (noise-free), so a decomposition can never hide the
            # scored corner as a C0 kink (line|line at 45deg rejected; a cap tangency,
            # where line and arc tangents agree exactly, passes).
            if ts2 is not None and te1 is not None and float(te1 @ ts2) < g1_cos:
                continue
            if (r1 + r2, d1 + d2) < (found[1], found[0]):
                found = (d1 + d2, r1 + r2, ts1, te2)
        memo[key] = found
        return memo[key]

    d, r, _, _ = best(0, max_prims)
    return d, r


def _recenter_corners(loop: np.ndarray, indices: list[int], radius: int = 3, w: int = 4) -> list[int]:
    """Snap each detected corner to the local windowed-turning maximum within
    +-radius vertices — the same re-centring the human-label cleaner applies
    (validated there: +0.11 F1).  The lax detector's NMS lands within ~1 vertex of
    the true apex; a 1-off segment endpoint makes the first midpoints of BOTH
    adjacent segments miss their Eq4-5 intervals, forcing spurious end-cubics on
    otherwise straight sides."""
    n = len(loop)
    out: set[int] = set()
    for i in indices:
        best, best_turn = i % n, -1.0
        for k in range(i - radius, i + radius + 1):
            j = k % n
            p, c, q = loop[(j - w) % n], loop[j], loop[(j + w) % n]
            din, dout = c - p, q - c
            ni, no = float(np.linalg.norm(din)), float(np.linalg.norm(dout))
            if ni < 1e-9 or no < 1e-9:
                continue
            turn = math.acos(max(-1.0, min(1.0, float((din / ni) @ (dout / no)))))
            if turn > best_turn:
                best_turn, best = turn, j
        out.add(best)
    return sorted(out)


def _collapse_short_corners(loop: np.ndarray, corners: list[int], threshold: float) -> list[int]:
    """Sec 5.2.1: merge a close corner PAIR into one — but ONLY a genuine double
    detection (both ends gentle bends, or within ~2.5px), never two distinct SHARP
    corners that merely sit close (the two ends of a narrow bar like the I of IKEA);
    collapsing those loses a real corner."""
    corners = sorted(corners)
    changed = True
    while changed and len(corners) > 2:
        changed = False
        m = len(corners)
        turns = _corner_turn_angles(loop, corners)
        for i in range(m):
            a, b = corners[i], corners[(i + 1) % m]
            dist = float(np.linalg.norm(loop[a] - loop[b]))
            if dist > threshold:
                continue
            both_gentle = turns[i] < 45.0 and turns[(i + 1) % m] < 45.0
            if not (dist <= 2.5 or both_gentle):     # keep two distinct sharp corners
                continue
            span = list(range(a, b + 1)) if b >= a else list(range(a, len(loop))) + list(range(0, b + 1))
            middle = (loop[a] + loop[b]) / 2
            keep = min(span, key=lambda k: float(np.linalg.norm(loop[k] - middle)))
            corners = sorted(set(corners) - {a, b} | {keep})
            changed = True
            break
    return corners


def _corner_turn_angles(loop: np.ndarray, corners: list[int]) -> np.ndarray:
    """Turn angle (deg, 0=straight .. 180=hairpin) at each corner, from the directions
    to its neighbouring corners; interior angle = 180 - turn (Sec 5.2.1 phi angles)."""
    m = len(corners)
    turns = np.zeros(m)
    for i in range(m):
        p, c, n = loop[corners[(i - 1) % m]], loop[corners[i]], loop[corners[(i + 1) % m]]
        din, dout = c - p, n - c
        ni, no = float(np.linalg.norm(din)), float(np.linalg.norm(dout))
        if ni < 1e-9 or no < 1e-9:
            continue
        turns[i] = math.degrees(math.acos(max(-1.0, min(1.0, float((din / ni) @ (dout / no))))))
    return turns


def _local_corner_geometry(loop: np.ndarray, corners: list[int], w: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """(turn_deg, convex) per corner from the LOCAL boundary over a ±w-vertex window.

    Sec 5.2.1's phi are angles of the fitted primitives at the corner — a chord to the
    NEIGHBOURING CORNERS misreads them: at a bar-cap tangency the chords span the whole
    cap and read 90 deg although the boundary is locally smooth (~15 deg), which blocked
    the obtuse relaxation and locked cap corners in (audit).  A short local window is the
    honest proxy: smooth tangency -> small turn, true corner -> its actual angle.
    Convexity sign = cross(din,dout) normalized by the loop's shoelace winding, so outer
    loops and holes read consistently (Sec 5.2.1 convex preference / Sec 5.3)."""
    x, y = loop[:, 0], loop[:, 1]
    winding = 1.0 if float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)) >= 0 else -1.0
    n = len(loop)
    m = len(corners)
    turns = np.zeros(m)
    convex = np.zeros(m, bool)
    for i in range(m):
        c = corners[i]
        din = loop[c] - loop[(c - w) % n]
        dout = loop[(c + w) % n] - loop[c]
        ni, no = float(np.linalg.norm(din)), float(np.linalg.norm(dout))
        if ni < 1e-9 or no < 1e-9:
            continue
        cosv = max(-1.0, min(1.0, float((din / ni) @ (dout / no))))
        turns[i] = math.degrees(math.acos(cosv))
        cross = float(din[0] * dout[1] - din[1] * dout[0])
        convex[i] = (cross * winding) >= 0
    return turns, convex


def _closure_partners(loop: np.ndarray, corners: list[int], convex: np.ndarray,
                      turns: np.ndarray, inside_fn) -> dict[int, int]:
    """Sec 5.3 (compact): pair CONCAVE corners whose straight closure is an IMAGINED
    contour — the chord between them lies inside the shape (inscribed-circle test at the
    midpoint, x0.90) and the boundary direction continues across the gap (chord within
    ~8 deg of the outgoing tangents).  Such corners are perceptually one occlusion event;
    removal treats them as a GROUP (Algorithm 2 'corner + closure-paired corners')."""
    res = max(1.0, float(np.ptp(loop[:, 0]) + np.ptp(loop[:, 1])) / 2)
    conc = [i for i in range(len(corners)) if (not convex[i]) and turns[i] >= 25.0]
    partners: dict[int, int] = {}
    for a_pos in range(len(conc)):
        i = conc[a_pos]
        if i in partners:
            continue
        pi = loop[corners[i]]
        for j in conc[a_pos + 1:]:
            if j in partners:
                continue
            pj = loop[corners[j]]
            gap = pj - pi
            dist = float(np.hypot(gap[0], gap[1]))
            if dist < 4.0 or dist > 0.5 * res:
                continue
            mid = 0.5 * (pi + pj)
            radius = 0.45 * dist
            angles = np.linspace(0.0, 2.0 * math.pi, 10, endpoint=False)
            ring = mid[None, :] + radius * np.stack([np.cos(angles), np.sin(angles)], axis=1)
            if not all(inside_fn(p) for p in ring):
                continue
            u = gap / dist
            ti = _unit(loop[(corners[i] + 3) % len(loop)] - pi)     # outgoing side of the gap
            tj = _unit(pj - loop[(corners[j] - 3) % len(loop)])     # incoming side of the gap
            if abs(float(ti @ u)) < math.cos(math.radians(8.0)):
                continue
            if abs(float(tj @ u)) < math.cos(math.radians(8.0)):
                continue
            partners[i] = j
            partners[j] = i
            break
    return partners


def _iterated_removal(loop: np.ndarray, corners: list[int], alpha: float, acc: float = _PAPER_ACC,
                      close_px: float | None = None) -> list[int]:
    """Sec 5.2 + 5.2.1 + 5.3: greedily drop the corner GROUP whose removal most lowers
    E=αD+R (Algorithm 2, lexicographic: argmin ΔR s.t. ΔR<0, else argmin ΔE s.t. ΔR=0,
    ΔE<0, else the obtuse Sec-5.2.1 relaxation).  Candidate groups are:
      * every single corner;
      * every ADJACENT PAIR closer than `close_px` (paper: 10% of the resolution) whose
        convexity signs agree (a mixed pair prefers removing the convex single);
      * Sec-5.3 CLOSURE pairs (concave corners bridging an imagined contour) — those are
        only ever removed together.
    The merged-segment cost is a true multi-primitive re-fit (_segment_cost, up to 3
    primitives), so a cap pair (line|arc|line) gets a finite honest cost."""
    corners = sorted(corners)
    res = max(1.0, float(np.ptp(loop[:, 0]) + np.ptp(loop[:, 1])) / 2)
    if close_px is None:
        close_px = 0.10 * res

    # rasterize the loop once for the Sec-5.3 inside test (local frame, 1px grid)
    lo = loop.min(axis=0) - 2.0
    size = np.maximum(4, np.ceil(loop.max(axis=0) - lo + 4.0).astype(int))
    mask_img = Image.new("1", (int(size[0]), int(size[1])), 0)
    ImageDraw.Draw(mask_img).polygon([tuple(p - lo) for p in loop], fill=1)
    mask_arr = np.asarray(mask_img, bool)

    def inside(p) -> bool:
        xi, yi = int(round(p[0] - lo[0])), int(round(p[1] - lo[1]))
        return 0 <= yi < mask_arr.shape[0] and 0 <= xi < mask_arr.shape[1] and bool(mask_arr[yi, xi])

    cost_cache: dict[tuple[int, int], tuple[float, float]] = {}

    def seg_cost(a: int, b: int) -> tuple[float, float]:
        key = (a, b)
        if key not in cost_cache:
            if a == b:                                   # full closed ring anchored at a
                ring = np.roll(loop, -a, axis=0)
                cost_cache[key] = _segment_cost(np.vstack([ring, ring[:1]]), acc, max_prims=6)
            else:
                cost_cache[key] = _segment_cost(_arc_slice(loop, a, b), acc)
        return cost_cache[key]

    while len(corners) > 1:
        m = len(corners)
        turns, convex = _local_corner_geometry(loop, corners)
        closure = _closure_partners(loop, corners, convex, turns, inside)
        costs = [seg_cost(corners[i], corners[(i + 1) % m]) for i in range(m)]
        drop_r, drop_e, promote = None, None, None  # Algorithm 2 lexicographic phases

        def consider(group: tuple[int, ...], dR: float, dD: float, obtuse_ok: bool) -> None:
            nonlocal drop_r, drop_e, promote
            dE = alpha * dD + dR
            if dR < 0:
                if drop_r is None or (dR, dE) < (drop_r[0], drop_r[1]):
                    drop_r = (dR, dE, group)
            elif dR == 0 and dD < 0:
                if drop_e is None or dE < drop_e[0]:
                    drop_e = (dE, dE, group)
            elif dR <= 1.0 and obtuse_ok:
                if promote is None or dE < promote[0]:
                    promote = (dE, dE, group)

        for i in range(m):
            if closure.get(i) is not None:          # closure corners only leave with their partner
                continue
            a, b = corners[(i - 1) % m], corners[(i + 1) % m]
            merged_d, merged_r = seg_cost(a, b)
            if not np.isfinite(merged_r):
                continue
            old_d = costs[(i - 1) % m][0] + costs[i][0]
            old_r = costs[(i - 1) % m][1] + costs[i][1]
            # merged multi-primitive fits are G1-legal by construction (fitted-tangent gate
            # inside _segment_cost), so a real corner can never be hidden as a C0 split —
            # the obtuse relaxation only needs the paper's angle condition.
            consider((i,), merged_r - old_r, merged_d - old_d, turns[i] < _OBTUSE_TURN)

        if m > 3:
            for i in range(m):
                j = (i + 1) % m
                pair_dist = float(np.linalg.norm(loop[corners[i]] - loop[corners[j]]))
                is_closure = closure.get(i) == j
                if not (is_closure or pair_dist <= close_px):
                    continue
                if not is_closure and convex[i] != convex[j]:
                    continue                        # Sec 5.2.1: mixed pair -> convex single wins
                a, b = corners[(i - 1) % m], corners[(j + 1) % m]
                merged_d, merged_r = seg_cost(a, b)
                if not np.isfinite(merged_r):
                    continue
                old_d = costs[(i - 1) % m][0] + costs[i][0] + costs[j][0]
                old_r = costs[(i - 1) % m][1] + costs[i][1] + costs[j][1]
                both_obtuse = turns[i] < _OBTUSE_TURN and turns[j] < _OBTUSE_TURN
                consider((i, j), merged_r - old_r, merged_d - old_d, both_obtuse)

        best = drop_r or drop_e or promote
        if best is None:
            break
        for idx in sorted(best[2], reverse=True):
            del corners[idx]
    if len(corners) == 1:
        # The LAST corner: geometry is the same closed ring with or without the C0 break, so
        # dR=dD=0 and only the Sec-5.2.1 obtuse relaxation applies — a lone gentle bend on an
        # otherwise-fittable smooth loop is spurious (the smooth branch then draws it G1-closed);
        # a genuine lone tip (teardrop, >=_OBTUSE_TURN) stays.
        turns, _ = _local_corner_geometry(loop, corners)
        if turns[0] < _OBTUSE_TURN and math.isfinite(seg_cost(corners[0], corners[0])[1]):
            corners = []
    return corners


_CORNER_LAX_THRESHOLD = 0.125  # paper Sec 4.1: lax, high-recall initial set; Sec 5 removal prunes
_CORNER_NMS = 2.0              # greedy NMS radius; a pair EXACTLY 2px apart is suppressed to one
                               # (Sec 4.2.1 both-endpoint pairs re-emerge via _collapse to the mid vertex)
_CORNER_DETECT_RES = 200.0     # detector was trained on <=128px shapes: normalize large loops to this
# The 1D CNN (corner_cnn) is the primary detector: on the human-annotated hold-in it beats the
# RF on perceptual agreement and is far more precise (fewer spurious corners for Sec-5 removal
# to prune).  The TILED model (short loops tiled into view; cleaned labels) reaches the paper's
# Sec-4 LAX spec: detector recall 0.952 at thr 0.14 on the 60-logo casino held-out.
# RECALIBRATED 2026-07-11 (after pair removal #19, clothoid removal #22, and the P0 fitting
# fixes): the paper's 'lax >=95% + removal cleans up' lever is EXHAUSTED here — final
# post-removal recall is FLAT across thresholds (0.28/0.20/0.14 -> R 0.728/0.731/0.732)
# because removal prunes the extra lax candidates right back, while precision falls
# (P 0.840/0.824/0.815, F1 0.780/0.774/0.771; synthetic score identical 0.913).  The
# remaining misses are microtext at annotation scale, not threshold-gated.  0.28 is the
# calibrated operating point; do NOT lower it without new evidence (e.g. event-level GT).
_USE_CNN_DETECTOR = True
_CNN_LAX_THRESHOLD = 0.28
# Validated 2026-07-11 on untouched V4 + primitive tests.  The original model
# is materially safer on raster-sized detail (Lacoste scales, tiny counters),
# while the balanced primitive/text candidate is more precise on normal loops.
# Use exactly one model per loop; this is not an expensive ensemble.
_CNN_HYBRID_CUTOFF = 4.0
_CNN_HYBRID_MAX_DENSITY = 8.0
_CNN_HYBRID_THRESHOLD = 0.36
_CNN_HYBRID_MODEL_PATH = Path(__file__).resolve().parent / "models" / "corner_cnn_hybrid_large_v1.pt"
_DEBUG_CORNER_ROUTING = False
# Elliptical-arc DP candidate (Stage 1.5).  Flag kept for A/B and fast revert.
_EARC_ENABLED = True
# Stage 2.3: corners as latent DP decisions (CNN log-odds priced against the
# G1 bend penalty inside the shortest path) instead of threshold->NMS->
# collapse->removal.  Flag for A/B and fast revert.
_JOINT_CORNER_DP = True
# 2026-07-13 hunt #2 CLOSED BY MACHINE SEARCH (optimize_corner_prices.py,
# 81 configs, objective = V4-val event-F1, constraints = star/lshape/spotify
# probes; log benchmarks/price_search.jsonl).  F1 0.7361 -> 0.7434.  The
# search says floor/slope barely matter (F1 flat across floor 1.6-2.8); the
# drivers are FEWER noise candidates (superset 0.15 -> 0.20) and CHEAPER
# geometric testimony (cap 1.2 -> 0.8).  Not hand-tuned.
_JOINT_SUPERSET_THRESHOLD = 0.20
_JOINT_CAP_PRICE = 0.8
# Stage 2.6b: gated font substitution (OCR -> font_match -> double iron gate
# -> true vector glyphs as the TOP layer).  Faithful fit always kept when any
# gate fails; flag for A/B and fast revert.
_FONT_SNAP_ENABLED = True


def _corner_probabilities(loop: np.ndarray) -> np.ndarray | None:
    """Raw per-vertex corner probabilities at native density (hybrid routing),
    or None when the CNN path is unavailable (caller falls back to classic)."""
    if not _USE_CNN_DETECTOR:
        return None
    try:
        import corner_cnn
        if len(loop) < corner_cnn.MIN_LOOP:
            return None
        res = max(1.0, float(np.ptp(loop[:, 0]) + np.ptp(loop[:, 1])) / 2)
        density = len(loop) / res
        use_large = (res > _CNN_HYBRID_CUTOFF and density <= _CNN_HYBRID_MAX_DENSITY
                     and _CNN_HYBRID_MODEL_PATH.is_file())
        return np.asarray(corner_cnn.predict_prob(
            loop, model_path=_CNN_HYBRID_MODEL_PATH if use_large else None), float)
    except Exception:
        return None


def _corner_price(p: float) -> float:
    """Price of declaring a C0 corner, competed against the G1 bend penalty
    (6.0/rad above 4deg).  p=0.9 -> 1.5 (cheap), p=0.5 -> 3.5 (a ~37deg bend),
    p=0.15 -> 5.25 (only a sharp turn justifies it)."""
    return 1.0 + 5.0 * (1.0 - float(np.clip(p, 0.0, 1.0)))
_CORNER_POSTPROCESS_POLICIES = ("production", "tiny-safe", "cnn-conservative")
# 2026-07-12 night A/B (benchmarks/vai_textsafe_probe.json + stages --fast):
# tiny-safe + text-safe promoted to DEFAULT.  On wordmark stems fallbacks went
# 1->0, wobble 62.5->0.25 (Hyundai) and 5.5->0.8, ink-IoU +0.024/-0.014; all
# non-text stems byte-identical; stages showed only the two pre-existing
# failures.  The old defaults remain available for A/B via CLI overrides.
_CORNER_POSTPROCESS_POLICY = "tiny-safe"
_PAPER_FIT_PROFILES = ("production", "text-safe")
_PAPER_FIT_PROFILE = "text-safe"


def _detect_lax_corners(work: np.ndarray, work_res: float, model, s: int,
                        detector: str = "cnn") -> list[int]:
    """Lax (high-recall) corner vertex indices for `work`.

    detector="cnn" (default): the 1D CNN over the boundary turning sequence (corner_cnn),
    RF fallback if unavailable.  detector="perres-paper": the paper's ORIGINAL setup — one RF
    per resolution trained ONLY on the Hoshyari training set, auto-selected by loop extent
    (corner_perres) — kept as a comparable alternative."""
    if detector == "perres-paper":
        try:
            import corner_perres
            mask = corner_perres.predict_corners_perres(work, threshold=None, nms_px=_CORNER_NMS)
            return list(np.flatnonzero(mask))
        except Exception:
            pass                                   # bundle missing -> fall through to CNN/RF
    if _USE_CNN_DETECTOR:
        try:
            import corner_cnn
            if len(work) >= corner_cnn.MIN_LOOP:   # short loops are tiled inside predict_prob
                density = len(work) / max(1.0, work_res)
                use_large = (work_res > _CNN_HYBRID_CUTOFF
                             and density <= _CNN_HYBRID_MAX_DENSITY
                             and _CNN_HYBRID_MODEL_PATH.is_file())
                if _DEBUG_CORNER_ROUTING:
                    print(f"corner-route extent={work_res:.3f} vertices={len(work)} "
                          f"density={density:.3f} model={'large' if use_large else 'small'}")
                threshold = _CNN_HYBRID_THRESHOLD if use_large else _CNN_LAX_THRESHOLD
                model_path = _CNN_HYBRID_MODEL_PATH if use_large else None
                mask = corner_cnn.predict_corners(
                    work, threshold=threshold, nms_px=_CORNER_NMS, model_path=model_path)
                return list(np.flatnonzero(mask))
        except Exception:
            pass  # torch/model missing or a runtime error -> RF fallback below
    from corner_classifier import predict_corners
    threshold = _corner_threshold(work_res)         # Fig 7 per-resolution operating point
    return list(np.flatnonzero(predict_corners(work, model, s, threshold=threshold, nms_radius=_CORNER_NMS)))


def _postprocess_corner_candidates(
    work: np.ndarray,
    candidates: list[int],
    work_res: float,
    spacing: float,
    policy: str = "production",
    use_cnn: bool = True,
) -> list[int]:
    """Turn lax detector candidates into the final corner set.

    ``production`` preserves the pre-existing Sec-5-inspired pipeline exactly.
    The other policies are isolated ablations for the native-density CNN route;
    RF/per-resolution detections intentionally keep their calibrated production
    post-processing even when an experimental policy is requested.

    ``tiny-safe`` tests the main failure found on reviewed glyphs: recentering and
    short-pair collapse erased true nearby letter corners before removal could
    score them.  At <=20 px it only performs a tight refit removal, at <=32 px it
    leaves the detector result alone, and above that it falls back to production.

    ``cnn-conservative`` is a less resolution-specific alternative: snap by just
    one boundary vertex, never collapse a close pair, and use the paper's 0.7 px
    accuracy rather than the current 1.6 px native-staircase tolerance.
    """
    if policy not in _CORNER_POSTPROCESS_POLICIES:
        valid = ", ".join(_CORNER_POSTPROCESS_POLICIES)
        raise ValueError(f"unknown corner postprocess policy {policy!r}; expected one of: {valid}")
    n = len(work)
    raw = sorted({int(index) % n for index in candidates}) if n else []
    if not raw:
        return []

    # Alternative policies are CNN ablations, not silent changes to the paper RF.
    if use_cnn and policy == "tiny-safe":
        if work_res <= 20.0:
            return _iterated_removal(
                work, raw, 32.0 / work_res, acc=0.55,
                close_px=0.10 * work_res,
            )
        if work_res <= 32.0:
            return raw
    elif use_cnn and policy == "cnn-conservative":
        recentered = _recenter_corners(work, raw, radius=1, w=2)
        return _iterated_removal(
            work, recentered, 32.0 / work_res, acc=_PAPER_ACC,
            close_px=0.10 * work_res,
        )

    # Original production path.  Keep this block mechanically identical to the
    # implementation used before the opt-in A/B policies were added.
    recentered = _recenter_corners(work, raw)
    collapsed = _collapse_short_corners(work, recentered, max(4.0, 16.0 * spacing))
    acc = max(1.3, 1.6 * spacing)
    return _iterated_removal(
        work, collapsed, 32.0 / work_res, acc,
        close_px=0.10 * work_res,
    )


def paper_corner_positions(
    loop: np.ndarray,
    detector: str = "cnn",
    postprocess_policy: str | None = None,
) -> np.ndarray:
    """xy positions of the perceptual corners of a native-resolution boundary loop.

    The CNN detector's turning windows are in PIXELS and it is trained at ~1px vertex
    spacing, so it must see the loop at NATIVE density: resampling a large loop to a
    coarser spacing collapses its probabilities (audited: max prob 0.013 vs threshold
    0.28 on a 720px icon -> zero corners -> the corner-rich shape fell into the smooth
    branch and was fit with shape-crossing chords).  Only the RF FALLBACK (fixed s=14
    VERTEX window, hence resolution-sensitive) still needs large loops resampled down to
    ~_CORNER_DETECT_RES density.  Collapse/accuracy knobs scale with the loop's vertex
    SPACING (the staircase amplitude), not its extents — at native density a 720px and a
    64px loop have the same ~1px staircase."""
    policy = _CORNER_POSTPROCESS_POLICY if postprocess_policy is None else postprocess_policy
    if policy not in _CORNER_POSTPROCESS_POLICIES:
        valid = ", ".join(_CORNER_POSTPROCESS_POLICIES)
        raise ValueError(f"unknown corner postprocess policy {policy!r}; expected one of: {valid}")
    model, s = _corner_model()
    resolution = max(1.0, float(np.ptp(loop[:, 0]) + np.ptp(loop[:, 1])) / 2)
    use_cnn = False
    if detector == "cnn" and _USE_CNN_DETECTOR:
        try:
            import corner_cnn
            use_cnn = len(loop) >= corner_cnn.MIN_LOOP
        except Exception:
            use_cnn = False
    work = loop
    if not use_cnn and resolution > _CORNER_DETECT_RES * 1.3 and len(loop) > 24:
        work = resample_ring(np.vstack((loop, loop[0])), resolution / _CORNER_DETECT_RES)[:-1]
    if detector == "perres-paper":
        min_len = 24                                 # the res-8 model handles ~24-vertex loops
    else:
        min_len = 10 if use_cnn else 4 * s + 4
    if len(work) < min_len:
        return np.empty((0, 2))
    work_res = max(1.0, float(np.ptp(work[:, 0]) + np.ptp(work[:, 1])) / 2)
    lax = _detect_lax_corners(work, work_res, model, s, detector=detector)
    if not lax:
        return np.empty((0, 2))
    # NO <3 early exit: removal now handles 1-2 corner loops via full-ring refits, so a
    # lone spurious gentle bend on a smooth closed loop gets pruned like any other.
    # Vertex spacing ~= staircase amplitude: 1-1.4px on a native marching-squares loop,
    # resolution/_CORNER_DETECT_RES on a resampled one (16*sp / 1.6*sp reproduce the old
    # 0.08*res / 0.008*res exactly on that path).
    spacing = max(1.0, float(np.mean(np.linalg.norm(np.roll(work, -1, axis=0) - work, axis=1))))
    kept = _postprocess_corner_candidates(
        work, lax, work_res, spacing, policy=policy, use_cnn=use_cnn,
    )
    return work[sorted(kept)]


def _positions_to_ring(ring: np.ndarray, positions: np.ndarray) -> list[int]:
    if positions is None or len(positions) == 0:
        return []
    return sorted({int(np.argmin(np.sum((ring - p) ** 2, axis=1))) for p in positions})


def fit_loop(
    loop: np.ndarray,
    feature_scale: float = 1.0,
    prefer_ellipse: bool = False,
    global_fit: bool = False,
    corner_positions: np.ndarray | None = None,
) -> FittedLoop:
    spacing = max(0.42, min(0.68, 0.52 * feature_scale))
    smooth = taubin_smooth_ring(resample_ring(loop, spacing), passes=4)
    ring = smooth[:-1]
    if corner_positions is not None:
        corners = _positions_to_ring(ring, corner_positions)
    else:
        corners = _multiscale_corners(ring, feature_scale, spacing)

    # Closed conics are decided globally.  Local staircase fragments are never
    # allowed to vote a circle/ellipse into existence.  Three or more stable
    # corners veto a conic, which prevents thin rounded rectangles and letters
    # such as I/l from being mistaken for extremely eccentric ellipses.
    ellipse = _ellipse_candidate(smooth)
    if ellipse is not None and (prefer_ellipse or len(corners) < 3 or ellipse[0] <= 0.12):
        error, minor_axis, curves = ellipse
        tolerance = max(0.24, min(0.58, 0.06 * minor_axis + 0.16))
        if prefer_ellipse:
            tolerance = max(tolerance, min(0.82, 0.12 + 0.11 * minor_axis))
        if error <= tolerance:
            return FittedLoop(smooth, curves, "ellipse")

    if len(corners) >= 2:
        curves = _rounded_corner_chain(ring, corners, feature_scale, spacing, global_fit=global_fit)
        return FittedLoop(smooth, curves, "uncertainty-dp" if global_fit else "rounded-g1")
    return FittedLoop(
        smooth,
        _smooth_closed_chain(ring, feature_scale, global_fit=global_fit),
        "uncertainty-dp" if global_fit else "g1-curve",
    )


_FIT_DEBUG = [False]       # print per-chunk Alg-1 violation devs (diagnostics only)
_PAPER_FIT_ALPHA_K = 32.0  # paper's alpha = 32 / resolution (Sec 5.1)
_DP_SPAN_PX = 110.0        # physical arc length one primitive's look-back can span (native px)
_DP_MAX_NODES = 220        # cap DP break points per segment for speed on huge loops
_DP_DEBUG: dict | None = None   # {"target_mid": i[, "win", "ban_near"]}: print span
                                # economics around mid i; ban_near drops priced corner
                                # candidates within 5 mids (counterfactual run). Probe-only.
_PAPER_FIT_EPS = 0.1       # paper's interval relaxation epsilon (Sec 5.1, Eq 5), in raster px
_PAPER_G1_W = 6.0          # weight of the G1-continuity term in the fit energy (Sec 5.1): a
                           # corner-bounded segment is smooth INSIDE, so any tangent break
                           # between two internal primitives is spurious and is penalised,
                           # making one clean arc beat a wavy line/arc patchwork.
_PAPER_G1_DEAD = 4.0       # deadzone (deg): sub-this tangent breaks read as smooth, no penalty


def _tangent_out(curve: Curve) -> np.ndarray:
    p = curve.control
    v = p[-1] - p[-2]
    n = float(np.linalg.norm(v))
    if n < 1e-9:
        v = p[-1] - p[0]; n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else np.array([1.0, 0.0])


def _tangent_in(curve: Curve) -> np.ndarray:
    p = curve.control
    v = p[1] - p[0]
    n = float(np.linalg.norm(v))
    if n < 1e-9:
        v = p[-1] - p[0]; n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else np.array([1.0, 0.0])


def _enforce_g1_chain(curves: list[Curve], max_angle_deg: float = 35.0, closed: bool = False,
                      keep_c0: set | None = None) -> list[Curve]:
    """Paper Sec 5.1 G1 continuity between consecutive primitives WITHIN a segment.

    A corner-bounded segment is smooth everywhere except its (corner) endpoints, so
    internal joins where the DP split it should share a unit tangent.  We rotate the
    flexible (cubic) handle(s) at each internal join to a common tangent — but ONLY
    when the two incident tangents already nearly agree (angle < max_angle).  A large
    tangent jump means a sharp feature the corner detector missed (e.g. a crocodile
    tooth tip inside the back-ridge segment); we leave those C0 so G1 never rounds a
    genuine sharp point."""
    if len(curves) < 2:
        return curves

    def rigid(c: Curve) -> bool:
        # Lines AND analytic runs (arc/clothoid beziers) are RIGID: their geometry
        # IS the primitive.  Rotating an arc's bezier handle to a neighbour's
        # tangent BOWS the drawn arc off its circle by 1-2px — Alg-1 then bans a
        # perfectly good arc (and the ban misses when the re-run shifts the span).
        meta = getattr(c, "meta", None)
        return c.degree == 1 or (isinstance(meta, tuple) and len(meta) and meta[0] in ("arc", "clothoid", "earc"))

    limit = math.cos(math.radians(max_angle_deg))
    out = list(curves)
    # closed chains also unify the wrap-around join (last -> first), which the open-range
    # loop used to skip — the one kink §6 could never clear on a closed smooth loop.
    joins = range(len(out)) if closed else range(len(out) - 1)
    for i in joins:
        if keep_c0 and i in keep_c0:
            continue                       # DP-paid corner: stays C0 at ANY angle
        a, b = out[i], out[(i + 1) % len(out)]
        ta, tb = _tangent_out(a), _tangent_in(b)
        if float(ta @ tb) < limit:
            continue                       # sharp join = unmarked corner, keep C0
        rigid_a, rigid_b = rigid(a), rigid(b)
        if rigid_a and rigid_b:
            continue                       # two rigid primitives: Sec 6 decides
        # The RIGID side dictates the shared tangent; two free cubics average.
        shared = tb if rigid_b else (ta if rigid_a else ta + tb)
        norm = float(np.linalg.norm(shared))
        if norm < 1e-9:
            continue
        shared = shared / norm
        if a.degree == 3 and not rigid_a:
            pa = a.control.copy()
            length = max(1e-3, float(np.linalg.norm(pa[-1] - pa[-2])))
            pa[-2] = pa[-1] - length * shared
            meta_a = getattr(a, "meta", None)
            out[i] = Curve(3, pa)
            out[i].meta = meta_a
        if b.degree == 3 and not rigid_b:
            pb = b.control.copy()
            length = max(1e-3, float(np.linalg.norm(pb[1] - pb[0])))
            pb[1] = pb[0] + length * shared
            meta_b = getattr(b, "meta", None)
            out[(i + 1) % len(out)] = Curve(3, pb)
            out[(i + 1) % len(out)].meta = meta_b
    return out


def _halfspace_ok(tangent: np.ndarray, poly: np.ndarray) -> bool:
    """Paper Sec 5.1 half-space tangent constraint.

    At a corner (poly[0]) the fitted curve's tangent must lie in the same half-space
    as the polyline itself, w.r.t. the edge immediately emanating from the corner.
    The half-space side is found from the first subsequent polyline edge orthogonal
    to that emanating edge.  This is what rejects a curve that curves the WRONG way
    at a corner (the arc that bulges out of a B counter) — a purely-accuracy fit can
    still point its tangent backward / to the wrong side and look counter-intuitive."""
    if len(poly) < 3:
        return True
    t = np.asarray(tangent, float)
    nt = float(np.linalg.norm(t))
    if nt < 1e-9:
        return True
    t = t / nt
    e0 = poly[1] - poly[0]
    ne0 = float(np.linalg.norm(e0))
    if ne0 < 1e-9:
        return True
    e0 = e0 / ne0
    if float(t @ e0) < -0.02:                       # tangent points backward -> wrong half-space
        return False
    perp = np.array([-e0[1], e0[0]])
    hi = min(len(poly) - 1, 25)
    seg = poly[2:hi + 1] - poly[1:hi]               # candidate edges after the emanating one
    if len(seg) == 0:
        return True
    norms = np.linalg.norm(seg, axis=1)
    good = norms > 1e-9
    cos_e0 = np.where(good, np.abs(seg @ e0) / np.where(good, norms, 1.0), 1.0)
    ortho = np.flatnonzero(cos_e0 < 0.5)            # first edge ~orthogonal to the emanating one
    if len(ortho) == 0:
        return True                                 # straight run: pointing forward suffices
    j = ortho[0]
    side = float((seg[j] @ perp) / norms[j])
    if abs(side) < 1e-6:
        return True
    return float(t @ perp) * side >= -0.02          # tangent must be on the polyline's side


# --- METHOD_ICE 3.2: deterministic sub-pixel evidence field ------------------
# Anti-aliased coverage is a physical measurement of the edge position.  For a
# crack midpoint whose two straddling pixels have coverages aM, aP of the
# +normal-side colour, an ideal edge satisfies the conservation rule
# offset = aM + aP - 1 (in native px along the normal).  Where the measurement
# is trustworthy the DP interval is re-centered on it and narrowed; everywhere
# else the classic +-0.5px midpoint corridor stays.  No ML, no training.
# Per-mask fitting context: ink of ALL OTHER masks at analysis resolution.
# A fit whose drawn curve lands on foreign ink is stealing a neighbour's
# territory (letters 1-2px apart bleed into one blob) — _finish_loop rejects
# it and the ladder finds a closer chain.  Only set on the ISOLATED per-mask
# path; the region graph shares boundaries legitimately.
_FOREIGN_INK: list = [None]          # (dt_own, dt_others, analysis_scale) | None
# 2026-07-13: Voronoi property-line ENFORCEMENT is experimental-OFF.  Two
# rounds of gate breakage (contact boundaries, palette-noise slivers around
# occlusion contacts) while the target case (114_bank component merges) never
# moved — the mergers are curved-part bulges legally at the midline.  The
# context DTs stay computed: the evenodd-hole own-bound gate for tiny
# counters uses them and never broke anything.
_VORONOI_LAWS = False
_EVIDENCE_FIELD: list = [None]
_IMAGE_NOISE: list = [0.0]           # native-px tube slack from measured JPEG ringing


def measure_image_noise(source: Image.Image) -> float:
    """Tube slack (native px) from the raster's own noise level.

    METHOD_ICE law 1: the interval is the observation's uncertainty — and a
    q30 JPEG observation is measurably noisier than a clean render, so its
    tube must be wider or the DP is FORBIDDEN the smooth truth and legally
    ships jagged chains (the blind kink tail).  Signal: p90 of |gray - box3|
    in the ringing zone 2-5px off Canny edges.  Measured 2026-07-14 on
    challenge crops: q30 JPEG 4.4-8.0, clean PNG 0.0-0.33 — the classes do
    not touch.  Mapping (signed by that measurement): slack = 0.08*(p90-1),
    capped at 0.45px so a genuine 1px feature still breaks any primitive."""
    gray = cv2.cvtColor(np.asarray(source.convert("RGB"), dtype=np.uint8),
                        cv2.COLOR_RGB2GRAY).astype(np.float32)
    if gray.size < 400:
        return 0.0
    resid = np.abs(gray - cv2.blur(gray, (3, 3)))
    edges = cv2.Canny(gray.astype(np.uint8), 40, 120)
    dt = cv2.distanceTransform((edges == 0).astype(np.uint8), cv2.DIST_L2, 3)
    ring_zone = (dt >= 2.0) & (dt <= 5.0)
    if int(ring_zone.sum()) < 50:
        return 0.0
    p90 = float(np.percentile(resid[ring_zone], 90))
    # Heavy-JPEG class ONLY (p90 >= 4.2, the measured lower edge of the q30
    # cluster).  bars_jpeg (p90 3.89, mild synthetic JPEG) lost a real 23px
    # step to a 0.23px slack — moderate ringing must not widen the tube; the
    # LSQ line / chunk-merge already absorb it (that is the signed reason
    # fit_px stayed 1.0 for JPEG all along).
    if p90 < 4.2:
        return 0.0
    return float(min(0.45, 0.08 * (p90 - 1.0)))
# 2026-07-12: EXPERIMENTAL, default OFF.  Night A/B: on the deblur path the 4x
# loops are already subpixel (tug-of-war fragmented fits); scoped to the native
# path it then broke 7 of the calibrated 900px synthetic decompositions
# (rrect/bars/ellipse/stadium/star type gates).  The probe math itself is unit-
# verified exact (+-0.3px edges recovered to 0.001) — the missing piece is
# making the DP treat re-centered corridors consistently with type domination.
# Kept as the measurement foundation for Stage-3 SEF work; enable via
# gv._EVIDENCE_ENABLED = True for experiments.
_EVIDENCE_ENABLED = False
_EVIDENCE_HALF = 0.30          # narrowed interval half-width (native px)
_EVIDENCE_MAX_OFF = 0.45       # clamp: never trust an offset beyond the crack cell


class _EvidenceField:
    """Bilinear probe of the NATIVE raster (the true physical measurement even
    when fitting runs on 4x-deblurred coordinates — loops are in native px)."""

    def __init__(self, pixels: np.ndarray, strict: bool = False):
        self.img = np.asarray(pixels, np.float32) / 255.0
        # JPEG ringing fakes coverage: demand twice the contrast before trusting.
        self.min_contrast = 0.24 if strict else 0.12

    def _sample(self, pts: np.ndarray) -> np.ndarray:
        h, w = self.img.shape[:2]
        x = np.clip(pts[:, 0] - 0.5, 0.0, w - 1.001)
        y = np.clip(pts[:, 1] - 0.5, 0.0, h - 1.001)
        x0 = np.floor(x).astype(int)
        y0 = np.floor(y).astype(int)
        x1 = np.minimum(x0 + 1, w - 1)
        y1 = np.minimum(y0 + 1, h - 1)
        fx = (x - x0)[:, None]
        fy = (y - y0)[:, None]
        return (self.img[y0, x0] * (1 - fx) * (1 - fy) + self.img[y0, x1] * fx * (1 - fy)
                + self.img[y1, x0] * (1 - fx) * fy + self.img[y1, x1] * fx * fy)

    def query(self, mid: np.ndarray, um: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(offsets, trusted) per midpoint; offset in native px along +um."""
        plus = self._sample(mid + 2.0 * um)      # pure colour on the +normal side
        minus = self._sample(mid - 2.0 * um)     # pure colour on the -normal side
        near_p = self._sample(mid + 0.5 * um)
        near_m = self._sample(mid - 0.5 * um)
        axis = plus - minus
        contrast = np.linalg.norm(axis, axis=1)
        denom = np.maximum(contrast * contrast, 1e-9)
        # fraction of the +side colour in each straddling pixel
        a_p = np.sum((near_p - minus) * axis, axis=1) / denom
        a_m = np.sum((near_m - minus) * axis, axis=1) / denom
        # off-axis residual: blend with a THIRD colour (junction, texture) = lie
        res_p = np.linalg.norm(near_p - (minus + a_p[:, None] * axis), axis=1)
        res_m = np.linalg.norm(near_m - (minus + a_m[:, None] * axis), axis=1)
        res_budget = 0.25 * contrast + 0.02
        # a_p/a_m are +side-colour coverages; the +side colour occupies x > edge,
        # so its total coverage in the straddling pair is 1 - e  =>  e = 1 - sum.
        offsets = 1.0 - (a_p + a_m)
        trusted = ((contrast >= self.min_contrast)
                   & (a_p > -0.1) & (a_p < 1.1) & (a_m > -0.1) & (a_m < 1.1)
                   & (res_p <= res_budget) & (res_m <= res_budget)
                   & (np.abs(offsets) <= _EVIDENCE_MAX_OFF))
        return np.clip(offsets, -_EVIDENCE_MAX_OFF, _EVIDENCE_MAX_OFF), trusted


def fit_segment_midpoints(vertices: np.ndarray, alpha: float = 0.13, px: float = 1.0,
                          snap_ends: bool = True,
                          corner_prices: dict[int, float] | None = None) -> list[Curve]:
    """Paper Sec 5.1: fit a corner-bounded raster segment to its pixel-edge MIDPOINTS
    with a Cornucopia-style shortest-path DP over line (r=1) / arc (r=2) / clothoid
    (r=4; biarc and cubic remain as degenerate-case fallbacks); energy E = alpha*D + R.

    Accuracy is the paper's DIRECTIONAL interval constraint (Eq 4-5), NOT a symmetric
    band: each pixel-edge midpoint m carries an interval Im = m + (t-0.5)*um, where um
    is the edge NORMAL ((1,0) for a vertical edge, (0,1) for a horizontal one), of
    half-width 0.5 raster-px.  A primitive is accurate iff it crosses that interval
    (or passes within eps of it) at every spanned midpoint.  This is what lets a
    diagonal staircase collapse to ONE line — the tolerance runs along the step
    direction — while a real >=1px feature (crocodile tooth) leaves the interval and
    forces a break.  No pre-smoothing needed.

    `px` is the size of one raster pixel in the fit's coordinates (1/analysis_scale):
    a deblurred 4x boundary has px=0.25 native, so the interval is a tight 0.125 native,
    which absorbs the 4x staircase yet keeps 1px-native detail (4 raster px)."""
    if len(vertices) < 3:
        return [Curve(1, np.vstack((vertices[0], vertices[-1])))]
    mid = 0.5 * (vertices[:-1] + vertices[1:])
    m = len(mid)
    edges = np.diff(vertices, axis=0)
    horizontal = np.abs(edges[:, 0]) >= np.abs(edges[:, 1])   # edge runs along x -> normal is y
    um = np.where(horizontal[:, None], np.array([0.0, 1.0]), np.array([1.0, 0.0]))
    half = 0.5 * px
    eps = _PAPER_FIT_EPS * px
    half_arr = np.full(m, half)
    # Noise-calibrated tube: measure_image_noise() (once per image, from the
    # raster's own JPEG ringing — clean images measure 0.0) widens every
    # interval by the observation's excess uncertainty.  Geometry-side
    # estimators failed twice here: a moving average carries curvature bias
    # (clean small loops read 'noisy'), a second-difference median reads 0 on
    # staircase mids.  The raster measurement separates the classes cleanly
    # (q30: 4.4-8.0, clean: <=0.33 — see measure_image_noise).
    if _IMAGE_NOISE[0] > 0.0:
        half_arr = half_arr + _IMAGE_NOISE[0]
    field = _EVIDENCE_FIELD[0]
    if field is not None and px >= 0.99 and m >= 5:
        # Sub-pixel evidence: re-center each interval on the coverage-derived
        # edge position.  RAW per-pixel offsets are noisy (real AA/JPEG) — using
        # them directly fragments the DP (first ship: Hyundai wobble 0.25 ->
        # 28297, betsoft grew 2 fallbacks).  The offsets are a 1D signal along
        # the boundary: low-pass over a ~3px window keeps the true subpixel
        # trend and kills the per-pixel noise; the interval NARROWS only where
        # the point agrees with its smoothed neighbourhood (coherence), and the
        # narrowed width still exceeds the residual budget.
        offsets, trusted = field.query(mid, um)
        if int(trusted.sum()) >= max(5, int(0.4 * m)):
            step = float(np.median(np.linalg.norm(np.diff(mid, axis=0), axis=1))) if m > 1 else 1.0
            win = max(3, int(round(3.0 / max(step, 0.2))))
            win = min(win, m - 1 if m % 2 == 0 else m)  # np.convolve('same') returns
            win += 1 - win % 2                          # max(M,N): kernel must not
            win = max(win, 3)                           # outgrow the signal
            kernel = np.ones(win, float)
            weights = trusted.astype(float)
            num = np.convolve(offsets * weights, kernel, mode="same")
            den = np.convolve(weights, kernel, mode="same")
            smoothed = np.where(den > 0, num / np.maximum(den, 1e-9), 0.0)
            support = den >= 0.6 * win                # enough trusted neighbours
            coherent = trusted & support & (np.abs(offsets - smoothed) <= 0.10)
            shift = np.where(trusted & support, smoothed, 0.0)
            shift = np.clip(shift, -_EVIDENCE_MAX_OFF, _EVIDENCE_MAX_OFF)
            mid = mid + shift[:, None] * um
            half_arr = np.where(coherent, _EVIDENCE_HALF * px, half)
    foreign_ctx = _FOREIGN_INK[0] if _VORONOI_LAWS else None
    if foreign_ctx is not None and m and foreign_ctx[2] >= 2:
        # native evidence is itself +-0.5px — the property line is only
        # enforceable on the subpixel (4x deblur) path
        # Voronoi property line inside the DP itself: at mids whose gap to a
        # NEIGHBOUR's ink is under a pixel, the interval may not reach past
        # half the gap — two exact letters 1px apart then stay 1px apart, and
        # the AA render keeps the white column (114_bank 6->3 merge class).
        dt_own_f, dt_others_f, fscale = foreign_ctx
        gx = np.clip((mid[:, 0] * fscale).astype(int), 0, dt_others_f.shape[1] - 1)
        gy = np.clip((mid[:, 1] * fscale).astype(int), 0, dt_others_f.shape[0] - 1)
        gap_native = dt_others_f[gy, gx] / max(1.0, float(fscale))
        # The property line exists only across a real BACKGROUND gap.  At
        # CONTACT boundaries (ikea letters on the badge, occlusion bases)
        # gap~0 and the cap crushed intervals to 0.12px — fits impossible,
        # three gates went red.  gap in [0.75, 2)px: genuine thin white gap.
        cap = np.where((gap_native >= 0.75) & (gap_native < 2.0),
                       np.maximum(0.12, 0.5 * gap_native - 0.02), half)
        half_arr = np.minimum(half_arr, cap)
    lo = mid - half_arr[:, None] * um   # interval end Im(0)
    hi = mid + half_arr[:, None] * um   # interval end Im(1)

    # DP break points ('nodes') and the look-back window are sized in PHYSICAL px, not
    # in point counts — otherwise a long smooth arc on a high-res native boundary (a
    # Pepsi wave) cannot be spanned by one primitive and collapses to a polyline of
    # short lines.  ~1.5px node spacing keeps fine detail; the look-back covers a
    # ~_DP_SPAN_PX arc regardless of resolution; total nodes are capped for speed.
    spacing = float(np.median(np.linalg.norm(np.diff(mid, axis=0), axis=1))) if m > 1 else 1.0
    spacing = max(spacing, 0.05)
    seg_len = spacing * m
    node_target = 1.5 if seg_len < 150.0 else 2.5      # long smooth segments: coarser breaks,
    stride = max(1, int(round(node_target / spacing)))  # quadratically fewer candidate spans
    if m // stride > _DP_MAX_NODES:
        stride = max(stride, m // _DP_MAX_NODES)
    nodes = list(range(0, m, stride))
    if nodes[-1] != m - 1:
        nodes.append(m - 1)
    if corner_prices:
        # A paid corner must be able to break the chain EXACTLY at its apex —
        # snapping the price to a ~1.5-2.5px node grid parks the C0 one or two
        # mids off the true corner, and the flanking line candidates then fail
        # their intervals AT the apex (polygon sides fragmented into cubics).
        # Grid nodes hugging an inserted apex are DROPPED: a 1-2 mid stub that
        # straddles the apex fits nothing but a forced cubic (star-tip C=4 bug).
        wanted = {int(i) for i in corner_prices if 0 < int(i) < m - 1}
        guard = max(2, stride)
        nodes = [v for v in nodes
                 if v in (0, m - 1) or v in wanted
                 or all(abs(v - w) >= guard for w in wanted)]
        nodes = sorted(set(nodes) | wanted)
    k = len(nodes)
    node_px = stride * spacing
    look_back = max(14, int(round(_DP_SPAN_PX / max(node_px, 0.3))))

    span_cache: dict[tuple[int, int, bool], list] = {}

    def fit_sub_all(a: int, b: int, force: bool, banned: set) -> list:
        """ALL competing primitive candidates for span [a,b] (paper Sec 5.1: fit EVERY type
        for every pair, then the shortest path chooses GLOBALLY — the lazy first-fit-wins
        shortcut systematically over-picked lines on shallow curves, making wavy line
        chains).  Domination pruning keeps it fast: on a genuinely straight span the line
        dominates every pricier type (same tangents, smaller r), and when an ARC passes,
        biarc/cubic (r=4 vs 2, same end tangents) are dominated too."""
        span_banned = any(key[1] == a and key[2] == b for key in banned)
        cache_key = (a, b, force)
        if not span_banned and cache_key in span_cache:
            return span_cache[cache_key]               # repair iterations reuse span fits
        def _store(res):
            if not span_banned:
                span_cache[cache_key] = res
            return res

        out = []
        # A PAID corner's midpoints belong to the raster's ROUNDED CAP, not to
        # either side: marching squares rounds an acute tip over 2-3px, so the
        # last/first few mids bend away from the straight sides (star tips came
        # out as cubic caps).  Chunks touching a priced corner drop up to 3 cap
        # mids on that end — the support intersection weld reconstructs the
        # EXACT sharp apex the raster could not render (same slack the classic
        # corner-vertex split has always had).
        start, end = chunk_slice(a, b)
        sub = mid[start : end]
        lo_s, hi_s, um_s = lo[start : end], hi[start : end], um[start : end]
        half_s = half_arr[start : end]   # per-midpoint interval half-width (evidence)
        rev = sub[::-1]  # polyline seen from the END corner, for the half-space test there

        # --- line: interval crosses the segment normal, or is within eps of it ---
        p0, p1 = sub[0], sub[-1]
        d = p1 - p0
        length = float(np.linalg.norm(d))
        turn_total = 0.0
        if len(sub) >= 7:
            va = _unit(sub[min(3, len(sub) - 1)] - sub[0])
            vb = _unit(sub[-1] - sub[max(-4, -len(sub))])
            turn_total = math.degrees(math.acos(max(-1.0, min(1.0, float(va @ vb)))))
        if length > 1e-9 and ("line", a, b) not in banned:
            # LSQ line, not the endpoint chord (Cornucopia fits primitives by least
            # squares): the chord's two endpoints carry +-0.5px raster quantization,
            # tilting it so mid-span midpoints leave their intervals on long spans —
            # which capped mergeable line length and let near-straight arcs win.
            centre = sub.mean(axis=0)
            sample_l = sub if len(sub) <= 200 else sub[np.linspace(0, len(sub) - 1, 200).astype(int)]
            _, _, vt = np.linalg.svd(sample_l - sample_l.mean(axis=0), full_matrices=False)
            du = vt[0]
            if float(du @ d) < 0:
                du = -du
            normal = np.array([-du[1], du[0]])
            da = (lo_s - centre) @ normal
            db = (hi_s - centre) @ normal
            ok = (da * db <= 0.0) | (np.minimum(np.abs(da), np.abs(db)) <= eps)
            if bool(ok.all()) and _halfspace_ok(du, sub) and _halfspace_ok(-du, rev):
                perp = np.abs((sub - centre) @ normal)
                ep0 = centre + float((sub[0] - centre) @ du) * du
                ep1 = centre + float((sub[-1] - centre) @ du) * du
                out.append((alpha * float(perp.sum()) + 1.0, "line", (ep0, ep1), du, du))
                if turn_total < 3.0 and float(perp.max()) < 0.3 * half:
                    return _store(out)               # dead straight: line strictly dominates
                if b - a < 14:
                    return _store(out)               # short span: the arc-vs-line competition
                                                     # is decided on LONG spans; skip the
                                                     # expensive arc fit here for speed

        # --- arc: interval straddles the circle AND its tangents obey the half-space ---
        sample = sub if len(sub) <= 120 else sub[np.linspace(0, len(sub) - 1, 120).astype(int)]
        circle = fit_circle(sample) if ("arc", a, b) not in banned else None
        if circle is not None:
            center, radius, _ = circle
            ra = np.linalg.norm(lo_s - center, axis=1) - radius
            rb = np.linalg.norm(hi_s - center, axis=1) - radius
            ok = (ra * rb <= 0.0) | (np.minimum(np.abs(ra), np.abs(rb)) <= eps)
            arc_feasible = bool(ok.all())
            if not arc_feasible and radius >= 1.0:
                # Outlier budget (kink hunt, spotify-711): binarization double-
                # step jags leave 1-4 stray mids that block an otherwise perfect
                # R~300 arc, and the DP then zigzags 26 lines with 44.5-deg
                # joins THROUGH them.  Allow <=1 stray per 40 mids IFF its
                # euclidean miss is bounded by the same slack the Alg-1 re-check
                # already grants (half + 0.35) — the interval law still binds
                # every other midpoint.
                stray = ~ok
                span_px = (b - a) * spacing          # PHYSICAL px, not mids —
                # Short spans get a MINIMUM budget of one stray (spotify-380
                # closure: a stroke cap is a 5-15px semicircle whose single
                # staircase step blocked the arc under the old span>=40 gate,
                # so the DP bought the corner at probs-price ~3.9 instead —
                # machine-search-proof, both cap-veto attempts dead-aimed).
                # The bounded-miss law (half + 0.35) and the strong-claim veto
                # below still bind; a real 2-4 mid tooth is never one stray.
                if int(stray.sum()) <= max(1, int(span_px // 40)):  # 4x loops have 0.25px steps
                    stray_mids = a + np.flatnonzero(stray)
                    # a stray near a STRONG corner claim (p>=0.6 <=> price<=3)
                    # is the apex, not noise — bridging it blunts the tip
                    # (star L=10 -> 7).  Weak noise-level candidates must not
                    # veto absorption (spotify's wavy runs are littered with
                    # p~0.2 claims the DP already declined).
                    near_strong = any(
                        abs(int(s) - node) <= 6
                        for s in stray_mids
                        for node, pr in node_price.items() if pr <= 3.0)
                    if not near_strong:
                        miss = np.abs(np.linalg.norm(sub[stray] - center, axis=1) - radius)
                        arc_feasible = bool((miss <= half + 0.35).all())
            if arc_feasible and radius >= 1.0:
                angle = np.unwrap(np.arctan2(sub[:, 1] - center[1], sub[:, 0] - center[0]))
                if abs(float(angle[-1] - angle[0])) <= math.radians(178):
                    r0 = sub[0] - center
                    t0 = np.array([-r0[1], r0[0]])
                    if float(t0 @ (sub[1] - sub[0])) < 0:
                        t0 = -t0
                    r1 = sub[-1] - center
                    t1 = np.array([-r1[1], r1[0]])
                    if float(t1 @ (sub[-1] - sub[-2])) < 0:
                        t1 = -t1
                    if _halfspace_ok(t0, sub) and _halfspace_ok(-t1, rev):
                        # NOTE: the DRAWN-arc bulge check (circular_beziers + sampling) used
                        # to run here for EVERY candidate span — the DP's dominant cost.  It
                        # moved to the Algorithm-1 repair phase: a bulging drawn arc fails
                        # the post-selection accuracy re-check, gets banned, and the path
                        # re-runs without it.
                        radial = np.abs(np.linalg.norm(sub - center, axis=1) - radius)
                        nt0 = float(np.linalg.norm(t0)); nt1 = float(np.linalg.norm(t1))
                        ts = t0 / nt0 if nt0 > 1e-9 else _unit(sub[1] - sub[0])
                        teA = t1 / nt1 if nt1 > 1e-9 else _unit(sub[-1] - sub[-2])
                        out.append((alpha * float(radial.sum()) + 2.0, "arc", (center, radius), ts, teA))
                        return _store(out)           # arc dominates biarc/cubic (r 2 vs 4)

        # --- elliptical arc (r=3, METHOD_ICE 3.3): reached only when the CIRCLE
        # failed (the arc branch above early-returns on success), so this is the
        # 'partial oval' slot that previously decomposed into clothoid/cubic
        # patchwork.  Same hard feasibility as every other type. ---
        if _EARC_ENABLED and len(sub) >= 10 and ("earc", a, b) not in banned:
            earc = _earc_fit(sub, um_s, half_s, eps)
            if earc is not None:
                edev, eparams, ets, ete = earc
                if _halfspace_ok(ets, sub) and _halfspace_ok(-ete, rev):
                    out.append((alpha * edev + 3.0, "earc", eparams, ets, ete))
                    return _store(out)   # exact conic beats the r=4 family on cost

        # --- clothoid (the paper's TRUE Sec 5.1 r=4 primitive): curvature linear in
        # arclength.  biarc/cubic below stay as fallbacks for spans where the LSQ
        # spiral is degenerate (heavy staircase noise, ~180deg hooks). ---
        if len(sub) >= 6 and ("clothoid", a, b) not in banned:
            clothoid = _clothoid_fit(sub)
            if clothoid is not None:
                poly, cts, cte, cparams = clothoid
                dev = np.abs(np.sum((poly - sub) * um_s, axis=1))
                if bool((dev <= half_s + eps).all()) and _halfspace_ok(cts, sub) and _halfspace_ok(-cte, rev):
                    out.append((alpha * float(np.linalg.norm(poly - sub, axis=1).sum()) + 4.0,
                                "clothoid", cparams, cts, cte))
                    return _store(out)   # r=4 family: the clothoid IS the paper primitive

        # --- cubic: deviation ALONG um inside the interval, and half-space tangents ---
        control, prediction = _cubic_control(sub, _unit(sub[1] - sub[0]), _unit(sub[-1] - sub[-2]))
        dev_um = np.abs(np.sum((prediction - sub) * um_s, axis=1))
        te0, te1 = _unit(sub[1] - sub[0]), _unit(sub[-1] - sub[-2])

        # --- biarc (paper clothoid stand-in): two G1 arcs, monotone curvature so it
        # physically CANNOT overshoot/hook the way a cubic does.  Preferred r=4 curve. ---
        if len(sub) >= 5 and ("biarc", a, b) not in banned and _halfspace_ok(te0, sub) and _halfspace_ok(-te1, rev):
            biarc = _biarc_curves(sub[0], te0, sub[-1], te1, sub)
            if biarc is not None:
                poly = np.vstack([eval_curve(c, 10) for c in biarc])
                dmat = np.linalg.norm(poly[:, None, :] - sub[None, :, :], axis=2)  # drawn x sub
                sub_to = np.min(dmat, axis=0)                # each midpoint -> nearest drawn pt
                drawn_to = np.min(dmat, axis=1)              # each drawn pt -> nearest midpoint
                near = np.argmin(dmat, axis=0)
                dev = np.abs(np.sum((poly[near] - sub) * um_s, axis=1))
                # accurate at every midpoint AND the drawn biarc never bulges off the boundary
                if bool((dev <= half_s + eps).all()) and float(drawn_to.max()) <= half + eps + 0.35:
                    out.append((alpha * float(sub_to.sum()) + 4.0, "biarc", (te0, te1), te0, te1))
                    return _store(out)               # biarc and cubic share r=4: keep one

        # --- cubic fallback (degenerate biarc, e.g. ~180° turn): with overshoot/cusp gate ---
        if ("cubic", a, b) in banned and not force:
            return _store(out)
        accurate = bool((dev_um <= half_s + eps).all())
        if accurate and len(sub) >= 4:
            dense = eval_curve(Curve(3, control), max(16, 2 * len(sub)))
            over = np.min(np.linalg.norm(dense[:, None, :] - sub[None, :, :], axis=2), axis=1)
            steps = np.diff(dense, axis=0)
            slen = np.linalg.norm(steps, axis=1, keepdims=True)
            stepu = steps / np.maximum(slen, 1e-9)
            cusp = len(stepu) > 1 and float(np.min(np.sum(stepu[:-1] * stepu[1:], axis=1))) < -0.55
            if float(over.max()) > half + eps + 0.35 or cusp:
                accurate = False
        if (accurate and _halfspace_ok(control[1] - control[0], sub) and _halfspace_ok(control[2] - control[3], rev)) or force:
            out.append((alpha * float(np.linalg.norm(prediction - sub, axis=1).sum()) + 4.0, "cubic", None, te0, te1))
        return _store(out)

    # Shortest-path (Cornucopia Sec 5.1) over PRIMITIVE states: a DP state is (node,
    # tangent-bin of the incoming primitive), so two paths reaching the same break with
    # different tangents both survive and the G1 term is charged EXACTLY per candidate
    # pair (the old single-tangent memo was greedy/order-dependent).  All passing types
    # compete; the paper's Algorithm-1 repair loop re-runs the path with violating
    # candidates banned after continuity enforcement (<=4 iterations).
    dead = math.radians(_PAPER_G1_DEAD)
    BINS = 12

    # Stage 2.3 (METHOD_ICE 3.3): corner-as-DP-decision.  corner_prices maps a
    # MID index to the price of declaring a C0 corner there (from calibrated
    # CNN log-odds).  At a priced node the DP pays min(G1 penalty, price): a
    # confident corner is cheaper than bending a primitive chain around it,
    # a weak candidate loses to a smooth continuation — no threshold, no NMS,
    # no collapse window ever pre-decides.
    node_price: dict[int, float] = {}
    if corner_prices:
        node_set = set()
        ban = _DP_DEBUG.get("ban_near") if _DP_DEBUG else None
        if ban is not None:
            corner_prices = {i: p for i, p in corner_prices.items()
                             if abs(int(i) - int(ban)) > 5}
        for mid_index, price in corner_prices.items():
            # nearest DP node to the candidate's mid index
            node_val = nodes[min(range(len(nodes)), key=lambda q: abs(nodes[q] - mid_index))]
            if node_val in (0, m - 1):
                continue                     # chain ends are C0 by construction
            if node_val in node_set:
                node_price[node_val] = min(node_price[node_val], float(price))
            else:
                node_set.add(node_val)
                node_price[node_val] = float(price)

    def chunk_slice(a: int, b: int) -> tuple[int, int]:
        """Midpoint range of chunk [a,b]: at a priced corner the LAST midpoint
        belongs to the outgoing edge (a 90-deg apex makes its interval parallel
        to the incoming carrier), so ending chunks drop exactly one.  Wider cap
        trims open multi-mid gaps between adjacent chunks that the 1.5px welds
        cannot bridge (423-line heal cascade in the star probe)."""
        end = b + 1
        if node_price and b in node_price and b - a >= 3:
            end = b
        return a, end

    def tangent_bin(t) -> int:
        if t is None:
            return -1
        return int(((math.atan2(float(t[1]), float(t[0])) + math.pi) / (2.0 * math.pi)) * BINS) % BINS

    def run_dp(banned: set):
        # dp[j]: bin -> (cost, exact_tangent, back=(ii, bin_in, kind, parameter, corner_in))
        dp: list[dict] = [dict() for _ in range(k)]
        dp[0][-1] = (0.0, None, None)
        for jj in range(1, k):
            for ii in range(max(0, jj - look_back), jj):
                if nodes[jj] - nodes[ii] < 1 or not dp[ii]:
                    continue
                cands = fit_sub_all(nodes[ii], nodes[jj], force=(ii == jj - 1), banned=banned)
                for cost, kind, parameter, t_start, t_end in cands:
                    for bin_in, (cost_in, tan_in, _) in dp[ii].items():
                        penalty = 0.0
                        corner_in = False
                        if tan_in is not None and t_start is not None:
                            cosang = max(-1.0, min(1.0, float(tan_in[0] * t_start[0] + tan_in[1] * t_start[1])))
                            penalty = _PAPER_G1_W * max(0.0, math.acos(cosang) - dead)
                            price = node_price.get(nodes[ii])
                            if price is not None and price < penalty:
                                penalty = price
                                corner_in = True
                        total = cost_in + cost + penalty
                        nb = tangent_bin(t_end)
                        cur = dp[jj].get(nb)
                        if cur is None or total < cur[0]:
                            dp[jj][nb] = (total, t_end, (ii, bin_in, kind, parameter, corner_in))
        if not dp[k - 1]:
            return None
        end_bin = min(dp[k - 1], key=lambda bkey: dp[k - 1][bkey][0])
        chunks: list[tuple[int, int, str, object]] = []
        corner_mids: set[int] = set()
        jj, bkey = k - 1, end_bin
        while jj > 0:
            _, _, back = dp[jj][bkey]
            if back is None:
                break
            ii, bin_in, kind, parameter, corner_in = back
            chunks.append((nodes[ii], nodes[jj], kind, parameter))
            if corner_in:
                corner_mids.add(nodes[ii])
            jj, bkey = ii, bin_in
        chunks.reverse()
        run_dp.last_corner_mids = corner_mids
        if _DP_DEBUG:
            t = int(_DP_DEBUG.get("target_mid", -1))
            win = int(_DP_DEBUG.get("win", 25))
            if 0 <= t < m:
                total = dp[k - 1][end_bin][0]
                near = [v for v in nodes if abs(v - t) <= win]
                print(f"[DPDBG] m={m} k={k} stride={stride} node_px={node_px:.2f} "
                      f"total={total:.3f} corner_mids={sorted(corner_mids)}")
                print(f"[DPDBG] nodes near {t}: {near}")
                print(f"[DPDBG] prices near: "
                      f"{ {v: round(node_price[v], 3) for v in near if v in node_price} }")
                for ci, (a, b, kind, parameter) in enumerate(chunks):
                    if a - win <= t <= b + win:
                        cands = sorted(fit_sub_all(a, b, force=False, banned=banned))[:4]
                        print(f"[DPDBG] chunk {a}->{b} won={kind} cands="
                              f"{[(kk, round(cc, 3)) for cc, kk, *_ in cands]}")
                for ci in range(len(chunks) - 1):
                    a0, b0 = chunks[ci][0], chunks[ci][1]
                    a1, b1 = chunks[ci + 1][0], chunks[ci + 1][1]
                    if b0 == a1 and abs(b0 - t) <= win:
                        merged = sorted(fit_sub_all(a0, b1, force=False, banned=banned))[:5]
                        print(f"[DPDBG] MERGED span {a0}->{b1} across join {b0}: "
                              f"{[(kk, round(cc, 3)) for cc, kk, *_ in merged]}")
                        cA = sorted(fit_sub_all(a0, b0, force=False, banned=banned))
                        cB = sorted(fit_sub_all(a1, b1, force=False, banned=banned))
                        if cA and cB and cA[0][4] is not None and cB[0][3] is not None:
                            cosang = max(-1.0, min(1.0, float(cA[0][4] @ cB[0][3])))
                            ang_d = math.degrees(math.acos(cosang))
                            pen = _PAPER_G1_W * max(0.0, math.acos(cosang) - dead)
                            print(f"[DPDBG] join {b0}: tangent gap {ang_d:.1f}deg pen={pen:.3f} "
                                  f"pair total={cA[0][0] + cB[0][0] + pen:.3f}")
                        # forced clothoid on each side + merged (arc early-return hides it)
                        for (aa, bb) in ((a0, b0), (a1, b1), (a0, b1)):
                            st, en = chunk_slice(aa, bb)
                            subd = mid[st:en]
                            cl = _clothoid_fit(subd)
                            if cl is None:
                                print(f"[DPDBG] clothoid {aa}->{bb}: degenerate")
                                continue
                            poly, cts, cte, _cp = cl
                            devc = np.abs(np.sum((poly - subd) * um[st:en], axis=1))
                            okc = bool((devc <= half_arr[st:en] + eps).all())
                            costc = alpha * float(np.linalg.norm(poly - subd, axis=1).sum()) + 4.0
                            print(f"[DPDBG] clothoid {aa}->{bb}: feasible={okc} cost={costc:.3f} "
                                  f"dev_max={float(devc.max()):.2f} ts={np.round(cts, 3)} te={np.round(cte, 3)}")
                        # best alternative two-piece splits of the SAME window
                        rows = []
                        for X in nodes:
                            if not (a0 + 4 <= X <= b1 - 4) or X == b0:
                                continue
                            sA = sorted(fit_sub_all(a0, X, force=False, banned=banned))
                            sB = sorted(fit_sub_all(X, b1, force=False, banned=banned))
                            if not sA or not sB:
                                continue
                            pen2 = 0.0
                            if sA[0][4] is not None and sB[0][3] is not None:
                                c2 = max(-1.0, min(1.0, float(sA[0][4] @ sB[0][3])))
                                pen2 = _PAPER_G1_W * max(0.0, math.acos(c2) - dead)
                            rows.append((sA[0][0] + sB[0][0] + pen2, X, sA[0][1],
                                         round(sA[0][0], 2), sB[0][1], round(sB[0][0], 2),
                                         round(pen2, 2)))
                        for r in sorted(rows)[:4]:
                            print(f"[DPDBG] split@{r[1]}: {r[2]}({r[3]}) + {r[4]}({r[5]}) "
                                  f"pen={r[6]} total={r[0]:.3f}")
        return chunks

    def build_curves(chunks):
        curves: list[Curve] = []
        spans: list[tuple[int, int, int, str]] = []   # (curve_lo, curve_hi, chunk_idx, kind)
        for index, (a, b, kind, parameter) in enumerate(chunks):
            s_a, end_b = chunk_slice(a, b)
            sub = mid[s_a : end_b]
            # snap_ends=True glues the chain ends to the segment's raster corner
            # VERTICES.  The vertex carries +-0.5-1px quantization, which TILTS a
            # long LSQ line beyond its interval budget (Alg-1 then bans it and a
            # near-straight arc wins — the 'line became arc' defect).  Paper loops
            # pass snap_ends=False and close corners at the INTERSECTION of the two
            # adjacent primitives instead (see fit_loop_paper).
            start = vertices[0] if (index == 0 and snap_ends) else sub[0]
            end = vertices[-1] if (index == len(chunks) - 1 and snap_ends) else sub[-1]
            c_lo = len(curves)
            if kind == "line":
                # endpoints ride the LSQ line (chord/vertex endpoints carry raster
                # quantization); only snap_ends chains pin the outermost ones
                ep0, ep1 = parameter if parameter is not None else (start, end)
                p0 = start if (index == 0 and snap_ends) else ep0
                p1 = end if (index == len(chunks) - 1 and snap_ends) else ep1
                curves.append(Curve(1, np.vstack((p0, p1))))
            elif kind == "arc":
                center, radius = parameter
                # draw ON the fitted circle: chunk-boundary midpoints sit +-0.5px off
                # it, and a bezier arc forced through off-circle endpoints sags ~0.9px
                s0 = start if (index == 0 and snap_ends) else center + radius * _unit(start - center)
                s1 = end if (index == len(chunks) - 1 and snap_ends) else center + radius * _unit(end - center)
                curves.extend(_tag_arcs(circular_beziers(s0, s1, center, radius, sub), center, radius))
            elif kind == "earc":
                drawn = _earc_curves(parameter, sub)
                if drawn:
                    curves.extend(drawn)
                else:
                    control, _ = _cubic_control(sub, _unit(sub[1] - sub[0]), _unit(sub[-1] - sub[-2]))
                    control = control.copy(); control[0] = start; control[-1] = end
                    curves.append(Curve(3, control))
            elif kind == "clothoid":
                drawn = _clothoid_curves(sub, parameter, start, end)
                if drawn:
                    curves.extend(drawn)
                else:
                    control, _ = _cubic_control(sub, _unit(sub[1] - sub[0]), _unit(sub[-1] - sub[-2]))
                    control = control.copy(); control[0] = start; control[-1] = end
                    curves.append(Curve(3, control))
            elif kind == "biarc":
                te0, te1 = parameter
                drawn = _biarc_curves(start, te0, end, te1, sub)
                if drawn:
                    curves.extend(drawn)
                else:
                    control, _ = _cubic_control(sub, _unit(sub[1] - sub[0]), _unit(sub[-1] - sub[-2]))
                    control = control.copy(); control[0] = start; control[-1] = end
                    curves.append(Curve(3, control))
            else:
                control, _ = _cubic_control(sub, _unit(sub[1] - sub[0]), _unit(sub[-1] - sub[-2]))
                control = control.copy()
                control[0] = start
                control[-1] = end
                curves.append(Curve(3, control))
            spans.append((c_lo, len(curves), index, kind))
        return curves, spans

    def chunk_violations(chunks, curves, spans) -> set:
        """Paper Algorithm 1 repair test: after continuity enforcement, every primitive must
        still satisfy the (slightly slackened) interval accuracy over its own span.

        The drawn curve is sampled at <=~0.5px: with sparse samples the nearest drawn
        point to a STEP midpoint (whose um runs ALONG the primitive) sits many px away
        tangentially and its um-projection reads as a huge fake violation — the audit's
        'accuracy not hard' hole traced back here."""
        bad: set = set()
        slack = 0.25
        for c_lo, c_hi, index, kind in spans:
            a, b, _, _ = chunks[index]
            s_a, end_b = chunk_slice(a, b)
            sub = mid[s_a : end_b]
            um_s = um[s_a : end_b]
            pieces = []
            for c in curves[c_lo:c_hi]:
                chord = float(np.linalg.norm(c.control[-1] - c.control[0]))
                pieces.append(eval_curve(c, max(12, min(600, int(2.0 * chord) + 4))))
            pts = np.vstack(pieces)
            from scipy.spatial import cKDTree
            near = cKDTree(pts).query(sub)[1]
            dev = np.abs(np.sum((pts[near] - sub) * um_s, axis=1))
            if kind in ("arc", "earc", "clothoid") and (b - a) * spacing >= 40.0:
                # Same stray-outlier budget the candidate test grants (kink
                # hunt): without it Alg-1 bans a perfect R~300 arc over 1-2
                # binarization jags, and the re-run zigzags 26 lines through
                # them.  Selection and re-check must judge by the SAME law —
                # and neither may spend the budget near a corner CANDIDATE
                # (a stray at a priced node is the apex, not noise).
                order = np.argsort(dev)
                budget_n = int((b - a) * spacing // 40)
                strays = order[-budget_n:]
                stray_mids = s_a + strays
                near_strong = any(
                    abs(int(s) - node) <= 6
                    for s in stray_mids
                    for node, pr in node_price.items() if pr <= 3.0)
                keep = order[:-budget_n] if budget_n < len(dev) else order[:0]
                if not near_strong and bool((dev[strays] <= half + eps + 0.45).all()):
                    dev = dev[keep]
            if _FIT_DEBUG[0]:
                print(f"    chunk {kind:8s} [{a:4d},{b:4d}] dev={float(dev.max()):.2f} "
                      f"(budget {half + eps + slack:.2f}) at mid {np.round(sub[int(np.argmax(dev))],1)}")
            if float(dev.max()) > half + eps + slack:
                bad.add((kind, a, b))
        return bad

    def merge_chunks(chunks, banned: set, protected: set | None = None):
        """Greedy union-refits beyond the DP horizon.  The look-back caps a single
        primitive at ~_DP_SPAN_PX of arclength (a perf bound the paper does not
        have), so a large smooth run comes out as many pieces with slightly
        different parameters — a visibly jagged ring.  Re-fitting the union of two
        adjacent chunks and accepting whenever the Sec 5.1 energy does not increase
        is the same shortest-path objective applied at the scale the windowed DP
        could not see.  Also demotes arc->line when the union passes as a line
        (r 2 vs 1): 'almost straight arcs' cannot survive this pass."""
        def piece_cost(a, b, kind):
            for cost, k2, _p, _ts, _te in fit_sub_all(a, b, force=True, banned=banned):
                if k2 == kind:
                    return cost
            return None
        chunks = list(chunks)
        changed = True
        while changed and len(chunks) > 1:
            changed = False
            for i in range(len(chunks) - 1):
                a1, b1, k1c, _p1 = chunks[i]
                a2, b2, k2c, _p2 = chunks[i + 1]
                if b1 != a2:
                    continue
                if protected and a2 in protected:
                    continue                 # never merge across a PAID corner
                cands = fit_sub_all(a1, b2, force=False, banned=banned)
                if not cands:
                    continue
                best = min(cands, key=lambda c: c[0])
                c1, c2 = piece_cost(a1, b1, k1c), piece_cost(a2, b2, k2c)
                if c1 is None or c2 is None:
                    continue
                # Conservative: the union must win even without crediting the G1
                # seam penalty the two pieces currently pay between them.
                if best[0] <= c1 + c2 + 1e-9:
                    chunks[i] = (a1, b2, best[1], best[2])
                    del chunks[i + 1]
                    changed = True
                    break
        return chunks

    banned: set = set()
    curves: list[Curve] = []
    fit_segment_midpoints.last_corner_joins = []
    for _ in range(3):                                  # Alg-1: repeat until constraints hold
        chunks = run_dp(banned)
        if chunks is None:
            control, _ = _cubic_control(mid, _unit(mid[1] - mid[0]), _unit(mid[-1] - mid[-2]))
            return [Curve(3, control)]
        corner_mids: set = getattr(run_dp, "last_corner_mids", set())
        chunks = merge_chunks(chunks, banned, protected=corner_mids)
        fit_segment_midpoints.last_kinds = [c[2] for c in chunks]  # debug: true primitive kinds
        raw_curves, spans = build_curves(chunks)
        # Paid corner joins stay C0 through the intra-segment G1 pass and are
        # exported so the caller can weld them at analytic support intersections.
        corner_joins: list[tuple[int, np.ndarray]] = []
        for c_lo, _c_hi, index, _kind in spans:
            a_chunk = chunks[index][0]
            if a_chunk in corner_mids and c_lo > 0:
                corner_joins.append((c_lo, mid[a_chunk].copy()))
        keep = {c_lo - 1 for c_lo, _ in corner_joins}
        curves = _weld_chain(_enforce_g1_chain(raw_curves, keep_c0=keep))
        bad = chunk_violations(chunks, curves, spans)
        if not bad:
            fit_segment_midpoints.last_corner_joins = corner_joins
            return curves
        banned |= bad
    # Alg-1 exhausted with violations left: an inaccurate primitive must never ship
    # (audit P0).  Replace each still-violating chunk with the pixel-faithful ~2px
    # polyline of ITS OWN span; accurate neighbours are kept as fitted.
    healed: list[Curve] = []
    for c_lo, c_hi, index, kind in spans:
        a, b, _, _ = chunks[index]
        if (kind, a, b) in bad:
            seg = vertices[a:b + 2]
            dist = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(seg, axis=0), axis=1))))
            count = max(2, int(round(float(dist[-1]) / 2.0)) + 1)
            target = np.linspace(0.0, float(dist[-1]), count)
            chain = np.column_stack([np.interp(target, dist, seg[:, k]) for k in range(2)])
            healed.extend(Curve(1, np.vstack((chain[i], chain[i + 1]))) for i in range(len(chain) - 1))
        else:
            healed.extend(curves[c_lo:c_hi])
    return healed


def _regularize_loop(curves: list[Curve], tol: float = 0.7, angle_deg: float = 15.0) -> list[Curve]:
    """Paper §6 (collinear line regularization): merge consecutive near-collinear line
    primitives into one, but only when the merged line still passes within `tol` of
    both.  A curve's short pieces bow away from the merged chord, so they are left
    alone — this cannot facet a genuine curve."""
    curves = list(curves)
    angle_limit = math.radians(angle_deg)
    changed = True
    while changed and len(curves) > 2:
        changed = False
        for i in range(len(curves)):
            a, b = curves[i], curves[(i + 1) % len(curves)]
            if a.degree != 1 or b.degree != 1:
                continue
            da, db = a.control[-1] - a.control[0], b.control[-1] - b.control[0]
            if float(np.linalg.norm(da)) < 1e-6 or float(np.linalg.norm(db)) < 1e-6:
                continue
            turn = abs(math.atan2(float(np.cross(da, db)), float(np.dot(da, db))))
            start, end = a.control[0], b.control[-1]
            deviation = float(point_line_distance(np.vstack((a.control[0], a.control[-1], b.control[0])), start, end).max())
            if turn <= angle_limit and deviation <= tol:
                curves[i] = Curve(1, np.vstack((start, end)))
                del curves[(i + 1) % len(curves)]
                changed = True
                break
    return curves


_ARC_RUN_ID = [0]


def _tag_arcs(curves: list[Curve], center: np.ndarray, radius: float) -> list[Curve]:
    """Mark a circular_beziers run as ONE arc so §6 can regularize it as a circular unit."""
    _ARC_RUN_ID[0] += 1
    meta = ("arc", _ARC_RUN_ID[0], np.asarray(center, float).copy(), float(radius))
    for c in curves:
        c.meta = meta
    return curves


def _earc_fit(sub: np.ndarray, um_s: np.ndarray, half: float, eps: float):
    """Elliptical-arc candidate (METHOD_ICE 3.3, VAI parity: partial ovals as ONE
    primitive).  Direct LSQ ellipse (cv2.fitEllipseDirect — the stabilized
    Fitzgibbon family), then the SAME hard feasibility the other curve types
    use: um-projected deviation of the drawn arc at every midpoint plus the
    biarc-style bulge test.  Returns (deviation_sum, params, t_start, t_end)
    with params = (center, axes, theta, phi0, phi1), or None."""
    if len(sub) < 8:
        return None
    try:
        (cx, cy), (d0, d1), ang = cv2.fitEllipseDirect(sub.astype(np.float32))
    except cv2.error:
        return None
    if not np.all(np.isfinite([cx, cy, d0, d1, ang])):
        return None
    a_ax, b_ax = 0.5 * float(d0), 0.5 * float(d1)
    if min(a_ax, b_ax) < 0.8 or max(a_ax, b_ax) / max(min(a_ax, b_ax), 1e-9) > 12.0:
        return None
    chord = float(np.linalg.norm(sub[-1] - sub[0]))
    if max(a_ax, b_ax) > 50.0 * max(2.0, chord):
        return None                      # wild extrapolated fit: no evidence for it
    theta = math.radians(float(ang))
    ct, st = math.cos(theta), math.sin(theta)
    rot = np.array([[ct, st], [-st, ct]])          # world -> ellipse frame
    q = (sub - np.array([cx, cy])) @ rot.T
    q[:, 0] /= a_ax
    q[:, 1] /= b_ax
    phi = np.unwrap(np.arctan2(q[:, 1], q[:, 0]))
    dphi = np.diff(phi)
    if not (np.all(dphi >= -1e-6) or np.all(dphi <= 1e-6)):
        return None                      # midpoints wander back and forth in angle
    sweep = float(phi[-1] - phi[0])
    if abs(sweep) < 0.05 or abs(sweep) > math.radians(178):
        return None
    inv_rot = rot.T                                  # ellipse frame -> world
    dense_phi = np.linspace(phi[0], phi[-1], max(24, 3 * len(sub)))
    poly = (np.column_stack((a_ax * np.cos(dense_phi), b_ax * np.sin(dense_phi)))
            @ inv_rot.T) + np.array([cx, cy])
    dmat = np.linalg.norm(poly[:, None, :] - sub[None, :, :], axis=2)
    sub_to = np.min(dmat, axis=0)
    drawn_to = np.min(dmat, axis=1)
    near = np.argmin(dmat, axis=0)
    dev = np.abs(np.sum((poly[near] - sub) * um_s, axis=1))
    half_hi = float(np.max(half))            # half may be a per-midpoint array
    if not bool((dev <= half + eps).all()) or float(drawn_to.max()) > half_hi + eps + 0.35:
        return None
    def tangent_at(p: float, forward: np.ndarray) -> np.ndarray:
        t = np.array([-a_ax * math.sin(p), b_ax * math.cos(p)]) @ inv_rot.T
        t = _unit(t)
        return t if float(t @ forward) >= 0 else -t
    ts = tangent_at(float(phi[0]), sub[1] - sub[0])
    te = tangent_at(float(phi[-1]), sub[-1] - sub[-2])
    params = (np.array([cx, cy]), np.array([a_ax, b_ax]), theta,
              float(phi[0]), float(phi[-1]))
    return float(sub_to.sum()), params, ts, te


def _earc_curves(params: tuple, sub: np.ndarray) -> list[Curve]:
    """Draw an elliptical arc as <=90-degree tangent-matched cubics ON the fitted
    ellipse (handle k = 4/3*tan(dphi/4) in PARAMETER space — exact construction),
    tagged as ONE 'earc' unit so G1 enforcement treats it as rigid."""
    center, axes, theta, phi0, phi1 = params
    a_ax, b_ax = float(axes[0]), float(axes[1])
    ct, st = math.cos(theta), math.sin(theta)
    inv_rot = np.array([[ct, -st], [st, ct]])        # ellipse frame -> world

    def point(p: float) -> np.ndarray:
        return center + inv_rot @ np.array([a_ax * math.cos(p), b_ax * math.sin(p)])

    def deriv(p: float) -> np.ndarray:
        return inv_rot @ np.array([-a_ax * math.sin(p), b_ax * math.cos(p)])

    sweep = phi1 - phi0
    pieces = max(1, int(math.ceil(abs(sweep) / (0.5 * math.pi))))
    _ARC_RUN_ID[0] += 1
    meta = ("earc", _ARC_RUN_ID[0], np.asarray(center, float).copy(),
            np.asarray(axes, float).copy(), float(theta))
    curves: list[Curve] = []
    for i in range(pieces):
        f0 = phi0 + sweep * (i / pieces)
        f1 = phi0 + sweep * ((i + 1) / pieces)
        k = 4.0 / 3.0 * math.tan((f1 - f0) / 4.0)
        p0, p1 = point(f0), point(f1)
        control = np.vstack((p0, p0 + k * deriv(f0), p1 - k * deriv(f1), p1))
        curve = Curve(3, control)
        curve.meta = meta
        curves.append(curve)
    return curves


def _map_curve(control: np.ndarray, new_start: np.ndarray, new_end: np.ndarray) -> np.ndarray:
    """Rigidly map a curve's control points so its endpoints move to new_start/new_end
    (similarity: rotate+scale about the old start).  Lets arcs/cubics ride along when
    §6 regularization moves their bounding vertices."""
    old_start, old_end = control[0], control[-1]
    old_vec, new_vec = old_end - old_start, new_end - new_start
    lo = float(np.linalg.norm(old_vec))
    if lo < 1e-9:
        return control + (new_start - old_start)
    scale = float(np.linalg.norm(new_vec)) / lo
    ang = math.atan2(new_vec[1], new_vec[0]) - math.atan2(old_vec[1], old_vec[0])
    c, s = math.cos(ang) * scale, math.sin(ang) * scale
    rot = np.array([[c, -s], [s, c]])
    return np.array([new_start + rot @ (p - old_start) for p in control])


def _regularize_axis_parallel(curves: list[Curve], axis_deg: float = 8.0, par_deg: float = 6.0, w_dir: float = 60.0,
                              global_dirs: list | None = None,
                              offset_targets: dict | None = None) -> list[Curve]:
    """Paper §6: snap near-axis lines to exact horizontal/vertical and make near-parallel
    lines parallel, via a constrained vertex least-squares that keeps the loop connected;
    arcs/cubics ride along (an arc's whole bezier RUN is mapped as one circular unit).

    `global_dirs` (unit vectors) are IMAGE-WIDE parallel-cluster directions: lines snap to
    the nearest one within tolerance so strokes of DIFFERENT letters co-align (the paper's
    global scope).  `offset_targets` maps a line curve index -> (normal, c*): the line is
    additionally pulled onto a shared offset (same-line groups, e.g. a common baseline),
    softly, in the same least-squares."""
    n = len(curves)
    if n < 3:
        return curves
    verts = np.array([c.control[0] for c in curves], dtype=float)
    target: list[np.ndarray | None] = [None] * n
    line_angles: list[tuple[int, float, float]] = []  # (i, angle, length)
    for i in range(n):
        if curves[i].degree == 1:
            d = verts[(i + 1) % n] - verts[i]
            length = float(np.linalg.norm(d))
            if length > 1e-9:
                line_angles.append((i, math.atan2(d[1], d[0]), length))

    def _within_accuracy(length: float, dev_deg: float) -> bool:
        # rotating a line of this length by dev degrees moves its far end this far off
        # the raster boundary; only regularize if that stays within the accuracy budget.
        return length * math.sin(math.radians(abs(dev_deg))) <= _AXIS_TOL

    for i, a, length in line_angles:              # 1) axis snap — only if it stays accurate
        deg = math.degrees(a) % 180
        for axis in (0.0, 90.0, 180.0):
            dev = abs(deg - axis)
            if dev <= axis_deg and _within_accuracy(length, dev):
                r = math.radians(axis)
                target[i] = np.array([math.cos(r), math.sin(r)])
                break
    if global_dirs:
        for i, a, length in line_angles:              # 1b) image-wide parallel clusters first
            if target[i] is not None:
                continue
            for u in global_dirs:
                ga = math.atan2(float(u[1]), float(u[0]))
                dev = abs((math.degrees(a - ga) + 90) % 180 - 90)
                if dev <= par_deg and _within_accuracy(length, dev):
                    target[i] = np.asarray(u, float)
                    break
    rest = [(i, a, length) for i, a, length in line_angles if target[i] is None]
    used = [False] * len(rest)
    for j, (i, a, length) in enumerate(rest):     # 2) parallel clusters for the rest
        if used[j]:
            continue
        group = [j]
        used[j] = True
        for k, (i2, a2, l2) in enumerate(rest):
            if used[k]:
                continue
            if abs((math.degrees(a) - math.degrees(a2) + 90) % 180 - 90) <= par_deg:
                group.append(k)
                used[k] = True
        if len(group) >= 2:
            mean = math.atan2(sum(math.sin(2 * rest[g][1]) for g in group),
                              sum(math.cos(2 * rest[g][1]) for g in group)) / 2
            u = np.array([math.cos(mean), math.sin(mean)])
            for g in group:                       # only members that stay accurate
                dev = abs((math.degrees(rest[g][1]) - math.degrees(mean) + 90) % 180 - 90)
                if _within_accuracy(rest[g][2], dev):
                    target[rest[g][0]] = u
    if not any(t is not None for t in target) and not offset_targets:
        return curves
    rows, rhs = [], []                            # 3) constrained least squares
    for i in range(n):
        r = np.zeros(2 * n); r[i] = 1.0; rows.append(r); rhs.append(verts[i, 0])
        r = np.zeros(2 * n); r[n + i] = 1.0; rows.append(r); rhs.append(verts[i, 1])
    for i in range(n):
        if target[i] is None:
            continue
        ux, uy = target[i]; nx, ny = -uy, ux      # line dir constrained -> normal component 0
        j = (i + 1) % n
        r = np.zeros(2 * n)
        r[j] += w_dir * nx; r[i] -= w_dir * nx
        r[n + j] += w_dir * ny; r[n + i] -= w_dir * ny
        rows.append(r); rhs.append(0.0)
    if offset_targets:
        w_off = 20.0                                  # softer than direction constraints
        for i, (normal, c_star) in offset_targets.items():
            if i >= n or curves[i].degree != 1:
                continue
            nx, ny = float(normal[0]), float(normal[1])
            for v in (i, (i + 1) % n):                # both endpoints onto the shared line
                r = np.zeros(2 * n)
                r[v] = w_off * nx
                r[n + v] = w_off * ny
                rows.append(r); rhs.append(w_off * float(c_star))
    sol = np.linalg.lstsq(np.array(rows), np.array(rhs), rcond=None)[0]
    nv = np.column_stack([sol[:n], sol[n:]])
    # Safety: if the joint solve dragged any vertex well beyond the accuracy budget
    # (e.g. conflicting constraints on a curvy loop), abandon the regularization.
    if float(np.linalg.norm(nv - verts, axis=1).max()) > 2.0 * _AXIS_TOL + 0.5:
        return curves
    out: list[Curve] = []
    i = 0
    while i < n:
        meta = curves[i].meta
        if meta is not None and isinstance(meta, tuple) and meta[0] == "arc":
            j = i                                     # the arc's whole bezier RUN
            while j + 1 < n and curves[j + 1].meta is meta:
                j += 1
            a, b = nv[i], nv[(j + 1) % n]
            old_start, old_end = curves[i].control[0], curves[j].control[-1]
            # ONE similarity for the entire run keeps it co-circular (mapping each bezier
            # separately bent arcs mid-way — the audited _map_curve defect)
            ov, nvec = old_end - old_start, b - a
            lo_n = float(np.linalg.norm(ov))
            if lo_n < 1e-9:
                shift = a - old_start
                for c in curves[i:j + 1]:
                    out.append(Curve(3, c.control + shift, meta=meta))
            else:
                scale = float(np.linalg.norm(nvec)) / lo_n
                ang = math.atan2(nvec[1], nvec[0]) - math.atan2(ov[1], ov[0])
                co, si = math.cos(ang) * scale, math.sin(ang) * scale
                rot = np.array([[co, -si], [si, co]])
                new_meta = ("arc", meta[1], a + rot @ (meta[2] - old_start), meta[3] * scale)
                for c in curves[i:j + 1]:
                    mapped = np.array([a + rot @ (p - old_start) for p in c.control])
                    out.append(Curve(3, mapped, meta=new_meta))
            i = j + 1
            continue
        a, b = nv[i], nv[(i + 1) % n]
        if curves[i].degree == 1:
            out.append(Curve(1, np.vstack((a, b))))
        else:
            out.append(Curve(curves[i].degree, _map_curve(curves[i].control, a, b)))
        i += 1
    return out


def _grid_snap_axis_lines(regions: list) -> None:
    """Idealize-to-evidence: axis-aligned line carriers within 0.18px of an
    integer CRACK line snap onto it (small loops only, extent <= 40px).

    Stems of small text legally land at e.g. x=88.03 after LSQ/welds; at 1px
    inter-letter gaps that off-grid hair makes the AA render bridge letters
    (114_bank).  The crack grid IS the evidence — snapping to it is the purest
    idealization there is.  Neighbour curve endpoints ride along to keep C0."""
    for region in regions:
        for fl in region.loops:
            curves = fl.curves
            if not curves:
                continue
            pts = np.vstack([c.control for c in curves])
            extent = float(max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])))
            if extent > 40.0 or len(curves) < 3:
                continue
            for axis in (0, 1):
                for i, c in enumerate(curves):
                    if c.degree != 1:
                        continue
                    a, b = c.control[0], c.control[-1]
                    if abs(a[axis] - b[axis]) > 1e-6:
                        continue           # not axis-constant along this axis
                    coord = a[axis]
                    snapped = round(coord)
                    if abs(coord - snapped) < 1e-9 or abs(coord - snapped) > 0.18:
                        continue
                    prev_c = curves[(i - 1) % len(curves)]
                    next_c = curves[(i + 1) % len(curves)]

                    def _rigid(cv: Curve) -> bool:
                        meta = getattr(cv, "meta", None)
                        return isinstance(meta, tuple) and len(meta) and \
                            meta[0] in ("arc", "clothoid", "earc")
                    if _rigid(prev_c) or _rigid(next_c):
                        continue           # never bend an analytic run off its carrier
                    c.control[0][axis] = snapped
                    c.control[-1][axis] = snapped
                    prev_c.control[-1][axis] = snapped
                    next_c.control[0][axis] = snapped


def _regularize_regions_global(regions: list) -> None:
    """Paper Sec-6 GLOBAL scope: regularities are located across the WHOLE vectorization,
    not per loop.  (1) image-wide PARALLEL clusters: line directions shared by >=2 loops
    become common targets, so strokes of different letters co-align; (2) SAME-LINE groups:
    lines of one direction whose carrier offsets agree within ~1.2px are pulled onto the
    shared line (common baselines/stems); (3) CO-CIRCULAR reuse: arc runs whose circles
    nearly coincide across loops are re-emitted from ONE shared circle (badge rings, split
    O letters).  Mutates the FittedLoop.curves lists in place."""
    line_info = []          # (loop_obj, curve_idx, angle, length, midpoint)
    # paper-tiny loops are EXACT evidence chains on the crack grid: any Sec-6
    # nudge (axis snap, shared carrier) moves them off-grid by ~0.3px, and at
    # 1px inter-letter gaps the AA render then bridges neighbours (114_bank
    # 6 -> 3 components).  Idealization has nothing to add to an exact chain.
    loops = [fl for region in regions for fl in region.loops
             if not fl.template.startswith("paper-tiny")]
    for fl in loops:
        for idx, c in enumerate(fl.curves):
            if c.degree == 1:
                d = c.control[-1] - c.control[0]
                length = float(np.linalg.norm(d))
                if length > 2.0:
                    line_info.append((fl, idx, math.atan2(float(d[1]), float(d[0])), length,
                                      0.5 * (c.control[0] + c.control[-1])))

    # ---- (1) global parallel clusters (>=2 loops), excluding near-axis lines ----
    global_dirs: list[np.ndarray] = []
    dir_weights: list[float] = []
    cand = [(fl, a, ln) for fl, _, a, ln, _ in line_info
            if min(abs(math.degrees(a) % 90), 90 - abs(math.degrees(a) % 90)) > 8.0]
    used = [False] * len(cand)
    for i in range(len(cand)):
        if used[i]:
            continue
        group = [i]
        used[i] = True
        for j in range(i + 1, len(cand)):
            if used[j]:
                continue
            if abs((math.degrees(cand[i][1] - cand[j][1]) + 90) % 180 - 90) <= 6.0:
                group.append(j)
                used[j] = True
        if len({id(cand[g][0]) for g in group}) >= 2:   # spans at least two loops
            sin2 = sum(cand[g][2] * math.sin(2 * cand[g][1]) for g in group)
            cos2 = sum(cand[g][2] * math.cos(2 * cand[g][1]) for g in group)
            mean = 0.5 * math.atan2(sin2, cos2)
            global_dirs.append(np.array([math.cos(mean), math.sin(mean)]))
            dir_weights.append(sum(cand[g][2] for g in group))

    # ---- (1b) ORTHOGONAL relations between direction families (paper Sec 6): two
    # global families within 4 deg of perpendicular snap to an exactly-orthogonal
    # weighted pair — the same relation axis-alignment gives 0/90 lines, extended
    # to rotated designs.  4 deg of rotation moves a 60px line's ends ~2px at most;
    # the per-line 1px offset budget and the loop-level re-check still gate it.
    for i in range(len(global_dirs)):
        for j in range(i + 1, len(global_dirs)):
            ai = math.atan2(float(global_dirs[i][1]), float(global_dirs[i][0]))
            aj = math.atan2(float(global_dirs[j][1]), float(global_dirs[j][0]))
            diff = (aj - ai) % math.pi                  # undirected lines: mod 180 deg
            err = diff - math.pi / 2.0                  # signed deviation from orthogonal
            if abs(math.degrees(err)) > 4.0:
                continue
            wi, wj = dir_weights[i], dir_weights[j]
            total = max(1e-9, wi + wj)
            ai_new = ai + err * (wj / total)            # heavier family moves less
            aj_new = aj - err * (wi / total)
            global_dirs[i] = np.array([math.cos(ai_new), math.sin(ai_new)])
            global_dirs[j] = np.array([math.cos(aj_new), math.sin(aj_new)])

    # ---- (2) same-line offset groups per direction family ----
    per_loop_offsets: dict[int, dict] = {}
    families: list[np.ndarray] = [np.array([1.0, 0.0]), np.array([0.0, 1.0])] + global_dirs
    for u in families:
        normal = np.array([-u[1], u[0]])
        members = []
        for fl, idx, a, ln, mp in line_info:
            dev = abs((math.degrees(a - math.atan2(float(u[1]), float(u[0]))) + 90) % 180 - 90)
            if dev <= 6.0:
                members.append((fl, idx, ln, float(normal @ mp)))
        members.sort(key=lambda t: t[3])
        i = 0
        while i < len(members):
            j = i
            while j + 1 < len(members) and members[j + 1][3] - members[i][3] <= 1.2:
                j += 1
            group = members[i:j + 1]
            if len(group) >= 2 and len({id(g[0]) for g in group}) >= 2:
                c_star = sum(g[2] * g[3] for g in group) / max(1e-9, sum(g[2] for g in group))
                for fl, idx, ln, off in group:
                    if abs(off - c_star) <= 1.0:        # accuracy budget
                        per_loop_offsets.setdefault(id(fl), {})[idx] = (normal.copy(), c_star)
            i = j + 1

    # ---- apply per loop: re-run the constrained solve with the GLOBAL targets ----
    for fl in loops:
        if len(fl.curves) >= 3:
            fl.curves = _regularize_axis_parallel(
                fl.curves, global_dirs=global_dirs or None,
                offset_targets=per_loop_offsets.get(id(fl)))

    # ---- (3) co-circular arc clusters across loops (after the solve settled) ----
    arc_info = []
    for fl in loops:
        seen: dict[int, tuple[int, int]] = {}
        for idx, c in enumerate(fl.curves):
            meta = c.meta
            if isinstance(meta, tuple) and meta and meta[0] == "arc":
                if meta[1] in seen:
                    seen[meta[1]] = (seen[meta[1]][0], idx)
                else:
                    seen[meta[1]] = (idx, idx)
        for meta_id, (i0, i1) in seen.items():
            arc_info.append((fl, fl.curves[i0].meta, i0, i1))
    used_a = [False] * len(arc_info)
    for i in range(len(arc_info)):
        if used_a[i]:
            continue
        _, meta_i, _, _ = arc_info[i]
        cluster = [i]
        used_a[i] = True
        for j in range(i + 1, len(arc_info)):
            if used_a[j]:
                continue
            _, meta_j, _, _ = arc_info[j]
            r_ref = max(meta_i[3], meta_j[3])
            if (np.linalg.norm(meta_i[2] - meta_j[2]) <= max(2.0, 0.02 * r_ref)
                    and abs(meta_i[3] - meta_j[3]) <= max(1.5, 0.04 * r_ref)):
                cluster.append(j)
                used_a[j] = True
        if len(cluster) < 2:
            continue
        c_star = np.mean([arc_info[g][1][2] for g in cluster], axis=0)
        r_star = float(np.mean([arc_info[g][1][3] for g in cluster]))
        for g in cluster:
            fl, meta, i0, i1 = arc_info[g]
            if float(np.linalg.norm(meta[2] - c_star)) + abs(meta[3] - r_star) > 2.0:
                continue                                # would move the boundary too far
            start = fl.curves[i0].control[0]
            end = fl.curves[i1].control[-1]
            old_pts = np.vstack([eval_curve(c, 8) for c in fl.curves[i0:i1 + 1]])
            drawn = circular_beziers(start, end, c_star, r_star, old_pts)
            # arc_info stores indexes for every run before this loop.  Changing
            # a run's curve count here invalidates later indexes in the same
            # FittedLoop (graph mode commonly has several shared circle runs).
            # Keep this regularization pass length-preserving; graph-level
            # co-circular recovery already chooses the economical run count.
            if drawn and len(drawn) == i1 - i0 + 1:
                fl.curves[i0:i1 + 1] = _tag_arcs(drawn, c_star, r_star)

    # ---- (4) CIRCLE REUSE for lines (paper Sec 6): a short line that lies ON an
    # existing arc circle (both endpoints and midpoint within the co-circular
    # tolerance) becomes an arc OF that circle — typically the flat piece the DP
    # placed between two arcs of one ring.  Per-STEP accuracy guard: the swap is
    # accepted only when the replacement stays within 0.8px of the old line.
    circles: list[tuple[np.ndarray, float]] = []
    for fl in loops:
        for c in fl.curves:
            meta = c.meta
            if isinstance(meta, tuple) and len(meta) >= 4 and meta[0] == "arc":
                if all(float(np.linalg.norm(meta[2] - cc)) > 1.0 or abs(meta[3] - rr) > 1.0
                       for cc, rr in circles):
                    circles.append((np.asarray(meta[2], float), float(meta[3])))
    if circles:
        for fl in loops:
            for idx, c in enumerate(fl.curves):
                if c.degree != 1:
                    continue
                p0, p1 = c.control[0], c.control[-1]
                mid = 0.5 * (p0 + p1)
                length = float(np.linalg.norm(p1 - p0))
                if length < 2.0:
                    continue
                for cc, rr in circles:
                    if length > 1.2 * rr:
                        continue
                    tol = max(1.0, 0.01 * rr)
                    if (abs(float(np.linalg.norm(p0 - cc)) - rr) > tol
                            or abs(float(np.linalg.norm(p1 - cc)) - rr) > tol
                            or abs(float(np.linalg.norm(mid - cc)) - rr) > tol):
                        continue
                    chord = np.vstack((p0, mid, p1))
                    drawn = circular_beziers(cc + rr * _unit(p0 - cc), cc + rr * _unit(p1 - cc),
                                             cc, rr, chord)
                    if not drawn:
                        continue
                    pts = np.vstack([eval_curve(dc, 10) for dc in drawn])
                    dev = point_line_distance(pts, p0, p1)
                    if float(dev.max()) <= 0.8:          # per-step interval guard
                        fl.curves[idx:idx + 1] = _tag_arcs(drawn, cc, rr)
                    break

    # ---- (4.9) crack-grid snapping of axis lines (small text stems) ----
    _grid_snap_axis_lines(regions)

    # ---- (5) MIRROR SYMMETRY (audit P2): exact reflective regularity ----
    _regularize_mirror(regions)

    # ---- (6) N-fold ROTATIONAL symmetry + REPEATED shapes + glyph BASELINES ----
    _regularize_rotation(regions)
    _unify_repeated_shapes(regions)      # Stage 2.6a: decomposition-independent
    _regularize_repeats(regions)
    _regularize_baselines(regions)


def _regularize_mirror(regions: list) -> None:
    """Paper Sec 6 SYMMETRY: when the whole vectorization is mirror-symmetric
    about a vertical or horizontal axis (dense curve cloud within 0.8px of its
    own reflection), snap mirror curve PAIRS and self-symmetric curves to EXACT
    symmetry.  Every move is bounded (<=2px per control point) and the Sec-6
    accuracy re-check that wraps regularization reverts any loop that the snap
    pushes past the loop tolerance."""
    from scipy.spatial import cKDTree
    loops = [fl for region in regions for fl in region.loops]
    curves = [c for fl in loops for c in fl.curves]
    if len(curves) < 4:
        return
    cloud = np.vstack([eval_curve(c, 10) for c in curves])
    if len(cloud) < 40:
        return
    tree = cKDTree(cloud)
    candidates: list[tuple[np.ndarray, float]] = []
    for k in (0, 1):                       # classic V/H offset grid (cheap, exact)
        n_hat = np.array([1.0, 0.0]) if k == 0 else np.array([0.0, 1.0])
        c0 = float(cloud[:, k].mean())
        for dc in np.arange(-3.0, 3.01, 0.5):
            candidates.append((n_hat, c0 + float(dc)))
    # Stage 2.5 (METHOD_ICE 3.6, Mitra-style): ARBITRARY axes by transformation-
    # space voting — every point pair votes for the axis that would swap it
    # (normal = pair direction, offset = midpoint projection); dense vote
    # clusters become hypotheses, verified by the same 0.8px reflected-cloud
    # residual as V/H.  Diagonal shields/arrows stop being invisible to §6.
    sub = cloud if len(cloud) <= 150 else cloud[np.linspace(0, len(cloud) - 1, 150).astype(int)]
    iu = np.triu_indices(len(sub), 1)
    vecs = (sub[:, None, :] - sub[None, :, :])[iu]
    norms = np.linalg.norm(vecs, axis=1)
    keep = norms > 2.0
    if bool(keep.any()):
        vecs = vecs[keep] / norms[keep][:, None]
        mids = (0.5 * (sub[:, None, :] + sub[None, :, :]))[iu][keep]
        theta = np.mod(np.arctan2(vecs[:, 1], vecs[:, 0]), np.pi)
        rho = np.sum(mids * vecs, axis=1)
        keys = (np.floor(theta / math.radians(2.0)).astype(np.int64) * 100003
                + np.floor(rho / 2.0).astype(np.int64))
        uniq, counts = np.unique(keys, return_counts=True)
        for key in uniq[np.argsort(counts)[-4:]]:
            sel = keys == key
            n_mean = vecs[sel].mean(axis=0)
            nn = float(np.linalg.norm(n_mean))
            if nn < 1e-6:
                continue
            candidates.append((n_mean / nn, float(rho[sel].mean())))
    best = None
    for n_hat, c in candidates:
        proj = cloud @ n_hat
        refl = cloud - 2.0 * (proj - c)[:, None] * n_hat[None, :]
        score = float(np.mean(tree.query(refl)[0]))
        if best is None or score < best[0]:
            best = (score, n_hat, c)
    if best is None or best[0] > 0.8:
        return
    _, n_best, c_best = best

    def reflect(pts: np.ndarray) -> np.ndarray:
        out = np.array(pts, float, copy=True)
        proj = out @ n_best
        return out - 2.0 * (proj - c_best)[:, None] * n_best[None, :]

    eps = 1.5
    starts = np.array([cv.control[0] for cv in curves], float)
    tree_s = cKDTree(starts)
    done: set[int] = set()
    for i, a in enumerate(curves):
        if i in done:
            continue
        r_start = reflect(a.control[:1])[0]
        r_end = reflect(a.control[-1:])[0]
        # a mirror partner runs the OPPOSITE orientation on a consistently
        # oriented loop: partner.start ~ reflect(a.end), partner.end ~ reflect(a.start)
        d_j, j = tree_s.query(r_end)
        if j != i and j not in done and float(d_j) <= eps:
            b = curves[int(j)]
            if len(b.control) == len(a.control) and                     float(np.linalg.norm(b.control[-1] - r_start)) <= eps:
                refl_b = reflect(b.control[::-1])
                if float(np.max(np.linalg.norm(a.control - refl_b, axis=1))) <= 2.0:
                    avg = 0.5 * (a.control + refl_b)
                    a.control = avg
                    b.control = reflect(avg[::-1])
                    done.add(i)
                    done.add(int(j))
                    continue
        # self-symmetric curve (crosses the axis)
        if float(np.linalg.norm(r_start - a.control[-1])) <= eps and                 float(np.linalg.norm(r_end - a.control[0])) <= eps:
            refl_a = reflect(a.control[::-1])
            if float(np.max(np.linalg.norm(a.control - refl_a, axis=1))) <= 2.0:
                a.control = 0.5 * (a.control + refl_a)
                done.add(i)


def _regularize_rotation(regions: list) -> None:
    """Paper Sec 6 N-FOLD ROTATIONAL symmetry (stars, petals, gears): when the
    drawn-curve cloud coincides with itself rotated by 2pi/N about its centroid
    (mean residual <= 0.8px, N in 3..12), curve ORBITS under the rotation are
    averaged in a canonical frame and written back exactly N-fold symmetric.
    Moves bounded <= 2px; the Sec-6 re-check wrapper reverts damaged loops."""
    from scipy.spatial import cKDTree
    curves = [c for region in regions for fl in region.loops for c in fl.curves]
    if len(curves) < 6:
        return
    cloud = np.vstack([eval_curve(c, 10) for c in curves])
    if len(cloud) < 60:
        return
    centre = cloud.mean(axis=0)
    tree = cKDTree(cloud)
    best = None
    for n in (12, 10, 8, 6, 5, 4, 3):
        ang = 2.0 * math.pi / n
        rot = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
        rc = (cloud - centre) @ rot.T + centre
        score = float(np.mean(tree.query(rc)[0]))
        if score <= 0.8:
            best = (score, n)
            break                                    # prefer the HIGHEST fold that fits
    if best is None:
        return
    n_fold = best[1]
    ang = 2.0 * math.pi / n_fold
    rot = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])

    def rotate(pts: np.ndarray, k: int = 1) -> np.ndarray:
        out = np.array(pts, float, copy=True) - centre
        for _ in range(k % n_fold):
            out = out @ rot.T
        return out + centre

    starts = np.array([c.control[0] for c in curves], float)
    tree_s = cKDTree(starts)
    used: set[int] = set()
    for i, a in enumerate(curves):
        if i in used:
            continue
        orbit = [i]
        ok = True
        while len(orbit) < n_fold:
            cur = curves[orbit[-1]]
            target = rotate(cur.control[:1])[0]
            d_j, j = tree_s.query(target)
            j = int(j)
            if float(d_j) > 1.5 or j in used or (j in orbit and j != i):
                ok = False
                break
            if j == i:
                ok = len(orbit) == n_fold - 1 or False
                break
            b = curves[j]
            if len(b.control) != len(cur.control) or                     float(np.max(np.linalg.norm(rotate(cur.control) - b.control, axis=1))) > 2.0:
                ok = False
                break
            orbit.append(j)
        if not ok or len(orbit) != n_fold:
            continue
        canonical = np.mean([rotate(curves[orbit[k]].control, n_fold - k) for k in range(n_fold)], axis=0)
        if float(np.max(np.linalg.norm(canonical - curves[i].control, axis=1))) > 2.0:
            continue
        for k, idx in enumerate(orbit):
            curves[idx].control = rotate(canonical, k)
            used.add(idx)


def _unify_repeated_shapes(regions: list) -> None:
    """Stage 2.6a (METHOD_ICE 3.7): repeated GLYPHS unify by canonical-side
    INSTANCING, decomposition-independent.

    _regularize_repeats demands identical curve counts and degree sequences —
    two instances of the same letter fit with different primitive splits never
    unify (the common case: the DP is threshold-sensitive).  Here sameness is
    judged on the DRAWN OUTLINE (64 arclength samples, centroid-aligned, best
    cyclic shift, RMS <= 0.8px); the member with the FEWEST curves becomes the
    canonical instance and every other member is REPLACED by its translated
    copy — but only when the translated canonical still passes that member's
    own source-polyline accuracy (per-member gate, never a blind average)."""
    loops = [fl for region in regions for fl in region.loops
             if 2 <= len(fl.curves) <= 60 and len(fl.source) >= 12]
    if len(loops) < 2:
        return

    def outline(fl) -> np.ndarray:
        pts = np.vstack([eval_curve(c, 8)[:-1] for c in fl.curves])
        closed = np.vstack((pts, pts[:1]))
        dist = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(closed, axis=0), axis=1))))
        if dist[-1] < 1e-6:
            return None
        target = np.linspace(0.0, dist[-1], 64, endpoint=False)
        return np.column_stack([np.interp(target, dist, closed[:, k]) for k in range(2)])

    infos = []
    for fl in loops:
        o = outline(fl)
        if o is None:
            continue
        c = o.mean(axis=0)
        infos.append((fl, o - c, c, float(np.ptp(o[:, 0])), float(np.ptp(o[:, 1]))))

    used: set[int] = set()
    for i in range(len(infos)):
        if i in used:
            continue
        fl_i, rel_i, c_i, w_i, h_i = infos[i]
        group = [i]
        for j in range(i + 1, len(infos)):
            if j in used:
                continue
            fl_j, rel_j, c_j, w_j, h_j = infos[j]
            if abs(w_i - w_j) > max(1.0, 0.06 * w_i) or abs(h_i - h_j) > max(1.0, 0.06 * h_i):
                continue
            best = None
            for shift in range(0, 64, 2):
                delta = np.linalg.norm(np.roll(rel_j, -shift, axis=0) - rel_i, axis=1)
                rms = float(np.sqrt(np.mean(delta ** 2)))
                if best is None or rms < best:
                    best = rms
            if best is not None and best <= 0.8:
                group.append(j)
        if len(group) < 2:
            continue
        canonical = min(group, key=lambda g: len(infos[g][0].curves))
        can_fl, _, can_c, _, _ = infos[canonical]
        for g in group:
            used.add(g)
            if g == canonical:
                continue
            fl_g, _, c_g, _, _ = infos[g]
            offset = c_g - can_c
            new_curves = []
            for c in can_fl.curves:
                nc = Curve(c.degree, c.control + offset)
                nc.meta = getattr(c, "meta", None)
                new_curves.append(nc)
            # per-member accuracy gate: the instanced glyph must still explain
            # THIS member's own raster boundary
            if _loop_fit_deviation(fl_g.source, new_curves) <= 2.5:
                fl_g.curves = new_curves


def _regularize_repeats(regions: list) -> None:
    """Audit P2 REPETITION + text/glyph structure: loops with the SAME SHAPE
    (repeated elements, repeated letters of a wordmark) are unified to their
    average shape, translation-aligned by centroid.  Matching is strict — same
    curve count, same degree sequence up to a cyclic shift, per-control RMS
    <= 1.2px and max <= 2px after centroid alignment."""
    loops = [fl for region in regions for fl in region.loops
             if 2 <= len(fl.curves) <= 40 and all(getattr(c, "meta", None) is None for c in fl.curves)]
    if len(loops) < 2:
        return

    def stack(fl) -> np.ndarray:
        return np.vstack([c.control for c in fl.curves])

    def centroid(fl) -> np.ndarray:
        return stack(fl).mean(axis=0)

    def shifted(fl, shift: int) -> list:
        return fl.curves[shift:] + fl.curves[:shift]

    used: set[int] = set()
    for i in range(len(loops)):
        if i in used:
            continue
        base = loops[i]
        base_rel = stack(base) - centroid(base)
        degs_i = [c.degree for c in base.curves]
        members = [(i, 0)]
        for j in range(i + 1, len(loops)):
            if j in used:
                continue
            other = loops[j]
            if len(other.curves) != len(base.curves):
                continue
            degs_j = [c.degree for c in other.curves]
            best_shift = None
            for shift in range(len(other.curves)):
                if degs_j[shift:] + degs_j[:shift] != degs_i:
                    continue
                rel = np.vstack([c.control for c in shifted(other, shift)]) - centroid(other)
                if rel.shape != base_rel.shape:
                    continue
                delta = np.linalg.norm(rel - base_rel, axis=1)
                if float(delta.max()) <= 2.0 and float(np.sqrt(np.mean(delta ** 2))) <= 1.2:
                    best_shift = shift
                    break
            if best_shift is not None:
                members.append((j, best_shift))
        if len(members) < 2:
            continue
        rels = []
        for j, shift in members:
            fl = loops[j]
            rels.append(np.vstack([c.control for c in shifted(fl, shift)]) - centroid(fl))
        mean_rel = np.mean(rels, axis=0)
        for j, shift in members:
            fl = loops[j]
            target = mean_rel + centroid(fl)
            pos = 0
            reordered = shifted(fl, shift)
            for c in reordered:
                m = len(c.control)
                c.control = target[pos:pos + m].copy()
                pos += m
            used.add(j)


def _regularize_baselines(regions: list) -> None:
    """Text/glyph structure (audit P2): glyph-sized loops of a wordmark share
    BASELINE and CAP-HEIGHT lines.  Cluster loop bottom/top extremes (1.2px
    window, >=3 members) and translate each member loop VERTICALLY onto the
    weighted line (shape-preserving whole-loop shift, bounded <= 1.0px)."""
    loops = [fl for region in regions for fl in region.loops if len(fl.curves) >= 2]
    if len(loops) < 3:
        return
    heights = []
    for fl in loops:
        pts = np.vstack([c.control for c in fl.curves])
        heights.append((float(pts[:, 1].min()), float(pts[:, 1].max()), fl))

    moved: set[int] = set()
    for key in (1, 0):                                # BASELINE (bottoms) rules; tops
        entries = sorted(((h[key], h[2]) for h in heights), key=lambda t: t[0])
        i = 0
        while i < len(entries):
            j = i
            while j + 1 < len(entries) and entries[j + 1][0] - entries[i][0] <= 1.2:
                j += 1
            group = entries[i:j + 1]
            if len(group) >= 3:
                target = float(np.mean([g[0] for g in group]))
                for value, fl in group:
                    if key == 0 and id(fl) in moved:
                        continue                      # baseline already placed this glyph
                    shift = target - value
                    if 1e-4 < abs(shift) <= 1.0:
                        for c in fl.curves:
                            c.control = c.control + np.array([0.0, shift])
                        moved.add(id(fl))
            i = j + 1


def _whole_loop_circle(loop: np.ndarray, px: float, slack: float = 0.35,
                       residual_gate: bool = True):
    """(center, radius) if the WHOLE closed loop is one genuine circle, else None.

    The radial residual alone is degenerate (audit P0 'circle catastrophe'): a thin
    43x6 wordmark fit against an R~2000 circle lies entirely inside the tolerance
    annulus with near-zero residual.  A genuine full circle must ALSO satisfy:
      - square-ish bbox (aspect >= 0.6),
      - radius commensurate with the bbox (0.7 <= 2R/extent <= 1.4),
      - centre inside the bbox,
      - full angular coverage around the centre (unwrapped span >= 330 deg).
    Only then is the scale-relative residual tolerance (cf. Sec 6 co-circular %R)
    safe: with 2R ~ extent it is ~0.5% of the shape, never a 20px annulus."""
    mid = 0.5 * (loop[:-1] + loop[1:])
    if len(mid) < 12:
        return None
    circle = fit_circle(mid)
    if circle is None or circle[1] < 1.5:
        return None
    center, radius, _ = circle
    w, h = float(np.ptp(loop[:, 0])), float(np.ptp(loop[:, 1]))
    extent = max(w, h)
    if extent < 1e-9 or min(w, h) / extent < 0.6:
        return None
    if not (0.7 <= (2.0 * radius) / extent <= 1.4):
        return None
    if not (loop[:, 0].min() <= center[0] <= loop[:, 0].max()
            and loop[:, 1].min() <= center[1] <= loop[:, 1].max()):
        return None
    angles = np.unwrap(np.arctan2(mid[:, 1] - center[1], mid[:, 0] - center[0]))
    if abs(float(angles[-1] - angles[0])) < math.radians(330.0):
        return None
    radial = np.abs(np.linalg.norm(mid - center, axis=1) - radius)
    if residual_gate and float(radial.max()) > max(0.5 * px + slack, 0.01 * radius):
        return None
    return center, radius


def _loop_is_circle(loop: np.ndarray, px: float) -> bool:
    """Whole closed loop is a single circle within accuracy — so any corners the lax
    detector left on its staircase are spurious and it should be fit as one co-circular
    disc, not split.  (Corner removal floors at 2 corners because a full circle cannot
    be one arc, so this catch is needed to reach the smooth branch.)"""
    return _whole_loop_circle(loop, px) is not None


def _flattest_index(loop: np.ndarray) -> int:
    """Vertex where the boundary turns least over a window — the safest place to cut
    a corner-free closed loop for the open-segment DP: the seam lands inside a long
    straight or gently-curved run, where the closed G1 chain and Sec 6 heal it."""
    n = len(loop)
    w = max(4, n // 36)
    prev = loop - np.roll(loop, w, axis=0)
    nxt = np.roll(loop, -w, axis=0) - loop
    cross = prev[:, 0] * nxt[:, 1] - prev[:, 1] * nxt[:, 0]
    dot = np.sum(prev * nxt, axis=1)
    return int(np.argmin(np.abs(np.arctan2(cross, dot))))


def _relative_circle_court(loop: np.ndarray, curves: list[Curve], px: float) -> list[Curve] | None:
    """RELATIVE small-shape court (research: unified tournament).  Ideal
    candidates COMPETE with the chain just fitted, on the same evidence: p90
    of each candidate's distance to the loop mids, strict +0.1px margin (an
    MDL head start was probed 2026-07-13 and REVERTED — it bought non-circles
    on text dots; description cost returns only with topology terms).

    Candidates: the ideal CIRCLE (any size, roundness strike) and, for small
    loops (extent <= 24px — alarm-bell 'hammers', q40 UI paddles), the
    min-area ROTATED RECT: a 15x8px rotated rectangle mangled by codec noise
    is otherwise fitted as a ragged 6-piece chain (isolated map item057,
    kinks 7.39 with VAI at 0.74)."""
    if not curves or len(curves) < 2:
        return None
    mid = 0.5 * (loop[:-1] + loop[1:])
    drawn = np.vstack([eval_curve(c, 12) for c in curves])
    dmat = np.linalg.norm(mid[:, None, :] - drawn[None, :, :], axis=2)
    p90_chain = float(np.percentile(np.min(dmat, axis=1), 90))

    shape = _whole_loop_circle(loop, px, slack=0.3, residual_gate=False)
    if shape is not None:
        center, radius = shape
        p90_circle = float(np.percentile(
            np.abs(np.linalg.norm(mid - center, axis=1) - radius), 90))
        if p90_circle <= p90_chain + 0.1:
            n = len(loop)
            cuts4 = [0, n // 4, n // 2, 3 * n // 4]
            ideal: list[Curve] = []
            for k in range(4):
                seg = _arc_slice(loop, cuts4[k], cuts4[(k + 1) % 4])
                ideal.extend(_tag_arcs(circular_beziers(seg[0], seg[-1], center, radius, seg), center, radius))
            return _enforce_g1_chain(ideal, closed=True)

    extent = float(max(np.ptp(loop[:, 0]), np.ptp(loop[:, 1])))
    if extent <= 24.0 and len(loop) >= 10:
        rect = cv2.minAreaRect(loop[:-1].astype(np.float32).reshape(-1, 1, 2))
        (rcx, rcy), (rw, rh), _ang = rect
        if min(rw, rh) >= 2.0:
            box = cv2.boxPoints(rect).astype(float)
            d_side = np.stack([
                point_line_distance(mid, box[k], box[(k + 1) % 4]) for k in range(4)
            ], axis=1)
            p90_rect = float(np.percentile(np.min(d_side, axis=1), 90))
            # Absurd-chain head start, rect branch only (measured on item057
            # hammers: a 14px rotated rect fitted as a 15-piece chain at p90
            # 0.39 while the ideal rect sits at 0.90 — the 0.5px gap IS the
            # q40 jag amplitude).  Applies only against chains of >=10
            # primitives on a <=24px shape (one curve per boundary pixel is
            # description absurdity); stars/drops keep p90_rect 1.5-3px and
            # still lose, clean rounded cards never produce such chains.
            margin = 0.1
            if len(curves) >= 10:
                margin = min(0.6, 0.06 * (len(curves) - 4))
            if p90_rect <= p90_chain + margin:
                # emit the rect with true C0 corners (they ARE corners)
                return [Curve(1, np.vstack((box[k], box[(k + 1) % 4]))) for k in range(4)]
    return None


def _fit_smooth_closed(loop: np.ndarray, alpha: float, px: float) -> list[Curve]:
    """A corner-free closed loop.  Paper Sec 6 co-circular: if ONE circle fits the
    whole boundary emit four arcs sharing that centre/radius (truly round disc).
    Otherwise the loop is ONE cyclic Sec 5.1 segment: unroll it at its flattest
    vertex and run the same line/arc/clothoid shortest path as everywhere else.

    (The old cubic-spline branch bypassed both the interval accuracy and the type
    competition: it reproduced raster/JPEG noise on large rings as wiggles — the
    'jagged ring' — and drew long straight sides as strings of near-straight
    cubics.  No other paper-mode path could emit those artefacts.)"""
    circle = _whole_loop_circle(loop, px, slack=0.3)
    if circle is not None:
        center, radius = circle
        n = len(loop)
        cuts4 = [0, n // 4, n // 2, 3 * n // 4]
        curves: list[Curve] = []
        for k in range(4):
            seg = _arc_slice(loop, cuts4[k], cuts4[(k + 1) % 4])
            curves.extend(_tag_arcs(circular_beziers(seg[0], seg[-1], center, radius, seg), center, radius))
        return _enforce_g1_chain(curves, closed=True)
    start = _flattest_index(loop)
    ring = np.vstack((loop[start:], loop[:start], loop[start:start + 1]))
    curves = fit_segment_midpoints(ring, alpha, px, snap_ends=False)
    court = _relative_circle_court(loop, curves, px)
    if court is not None:
        return court
    if curves:
        seam = _corner_intersection(curves[-1], curves[0], loop[start])
        _shift_curve_end(curves[-1], seam)
        _shift_curve_start(curves[0], seam)
    return _enforce_g1_chain(_regularize_loop(curves), max_angle_deg=20.0, closed=True)


def _support_of(curve: Curve):
    """The analytic support of a rigid primitive: ('line', p, d) or ('circle', c, R)."""
    meta = getattr(curve, "meta", None)
    if curve.degree == 1:
        d = curve.control[-1] - curve.control[0]
        n = float(np.linalg.norm(d))
        if n < 1e-9:
            return None
        return ("line", curve.control[0].astype(float), d / n)
    if isinstance(meta, tuple) and len(meta) >= 4 and meta[0] == "arc":
        return ("circle", np.asarray(meta[2], float), float(meta[3]))
    return None


def _intersect_supports(sa, sb, near: np.ndarray):
    """Intersection of two analytic supports nearest to `near`, or None."""
    kinds = (sa[0], sb[0])
    if kinds == ("line", "line"):
        _, p0, d0 = sa
        _, p1, d1 = sb
        cross = float(d0[0] * d1[1] - d0[1] * d1[0])
        if abs(cross) < 0.17:
            return None
        d = p1 - p0
        s = (d[0] * d1[1] - d[1] * d1[0]) / cross
        return p0 + s * d0
    if "line" in kinds and "circle" in kinds:
        (_, p0, d0), (_, c, r) = (sa, sb) if sa[0] == "line" else (sb, sa)
        f = p0 - c
        b_half = float(f @ d0)
        disc = b_half * b_half - (float(f @ f) - r * r)
        if disc < 0:
            return None
        root = math.sqrt(disc)
        cands = [p0 + (-b_half + root) * d0, p0 + (-b_half - root) * d0]
        return min(cands, key=lambda q: float(np.linalg.norm(q - near)))
    if kinds == ("circle", "circle"):
        _, c0, r0 = sa
        _, c1, r1 = sb
        d = float(np.linalg.norm(c1 - c0))
        if d < 1e-9 or d > r0 + r1 or d < abs(r0 - r1):
            return None
        a = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
        h2 = r0 * r0 - a * a
        if h2 < 0:
            return None
        h = math.sqrt(h2)
        u = (c1 - c0) / d
        base = c0 + a * u
        n = np.array([-u[1], u[0]])
        cands = [base + h * n, base - h * n]
        return min(cands, key=lambda q: float(np.linalg.norm(q - near)))
    return None


def _corner_intersection(a: Curve, b: Curve, vertex: np.ndarray, cap: float = 1.5) -> np.ndarray:
    """Quantization-free corner position: the intersection of the two adjacent
    primitives' SUPPORTS (line/circle — the point then lies exactly ON both, zero
    tilt for either side), falling back to end-tangent-line intersection for free
    cubics/clothoids.  Snapping to the raster vertex instead tilted long lines by
    its +-0.5-1px quantization and made Alg-1 ban perfectly good primitives.
    Falls back to the endpoint midpoint (then the vertex) when near-parallel or
    the intersection strays more than `cap` px from the raster vertex."""
    p = None
    sa, sb = _support_of(a), _support_of(b)
    if sa is not None and sb is not None:
        p = _intersect_supports(sa, sb, np.asarray(vertex, float))
    if p is None:
        pa, ta = a.control[-1], _tangent_out(a)
        pb, tb = b.control[0], _tangent_in(b)
        cross = float(ta[0] * tb[1] - ta[1] * tb[0])
        if abs(cross) >= 0.17:                 # tangents differ by >=~10 deg
            d = pb - pa
            s = (d[0] * tb[1] - d[1] * tb[0]) / cross
            p = pa + s * ta
        else:
            p = 0.5 * (pa + pb)
    if float(np.linalg.norm(p - vertex)) > cap:
        p = 0.5 * (a.control[-1] + b.control[0])
        if float(np.linalg.norm(p - vertex)) > cap:
            p = np.asarray(vertex, float)
    return p


def _shift_curve_start(curve: Curve, p: np.ndarray) -> None:
    delta = p - curve.control[0]
    curve.control[0] = p
    if curve.degree == 3:
        curve.control[1] = curve.control[1] + delta


def _shift_curve_end(curve: Curve, p: np.ndarray) -> None:
    delta = p - curve.control[-1]
    curve.control[-1] = p
    if curve.degree == 3:
        curve.control[-2] = curve.control[-2] + delta


def _weld_chain(curves: list[Curve]) -> list[Curve]:
    """Unify INTERIOR joins of an open chain at the intersection of the two sides'
    supports (midpoint fallback): adjacent chunks project their shared boundary
    midpoint onto DIFFERENT supports, so their drawn endpoints disagree by ~0.5px,
    which reads as a gap/step at every type transition."""
    for i in range(len(curves) - 1):
        a, b = curves[i], curves[i + 1]
        near = 0.5 * (a.control[-1] + b.control[0])
        p = _corner_intersection(a, b, near, cap=1.2)
        _shift_curve_end(a, p)
        _shift_curve_start(b, p)
    return curves


def _close_chain_corners(seg_curves: list[list[Curve]], loop: np.ndarray, corner_indices: list[int]) -> list[Curve]:
    """C0 closure of per-segment chains at their shared corners via primitive
    intersection (see _corner_intersection)."""
    m = len(seg_curves)
    for k in range(m):
        a_list, b_list = seg_curves[k], seg_curves[(k + 1) % m]
        if not a_list or not b_list:
            continue
        vertex = loop[corner_indices[(k + 1) % m]]
        p = _corner_intersection(a_list[-1], b_list[0], vertex)
        _shift_curve_end(a_list[-1], p)
        _shift_curve_start(b_list[0], p)
    return [c for chain in seg_curves for c in chain]


def _cubic_end_curvature(control: np.ndarray, at_start: bool) -> float:
    """Signed curvature of a cubic Bezier at t=0 or t=1 (analytic)."""
    if at_start:
        h = control[1] - control[0]
        v = control[2] - control[1]
    else:
        h = control[2] - control[3]
        v = control[1] - control[2]
    nh = float(np.linalg.norm(h))
    if nh < 1e-9:
        return 0.0
    return (2.0 / 3.0) * float(h[0] * v[1] - h[1] * v[0]) / (nh ** 3)


def _g2_fair_chain(curves: list[Curve]) -> list[Curve]:
    """Stage 2.4 (METHOD_ICE 3.4): curvature agreement at G1-smooth joins.

    At every join whose tangents already agree (<=8 deg), the FREE cubic side
    rescales its tangent-handle length so its endpoint curvature meets the
    neighbour's (rigid primitives — lines/arcs/clothoids/earcs — dictate
    theirs; two free cubics meet at the geometric mean).  Handle DIRECTION is
    untouched, so G1 survives by construction; the caller re-runs the FULL
    accuracy gates on the faired chain and keeps the unfaired one if fairing
    drifted.  This is what removes the visible curvature steps a G1-only chain
    shows on large smooth silhouettes."""
    if len(curves) < 2:
        return curves

    def is_rigid(c: Curve) -> bool:
        meta = getattr(c, "meta", None)
        return c.degree != 3 or (isinstance(meta, tuple) and len(meta)
                                 and meta[0] in ("arc", "clothoid", "earc"))

    def end_curvature(c: Curve, at_start: bool) -> float:
        if c.degree == 1:
            return 0.0
        ctrl = c.control if c.degree == 3 else np.vstack(
            (c.control[0], c.control[0] + (2.0 / 3.0) * (c.control[1] - c.control[0]),
             c.control[2] + (2.0 / 3.0) * (c.control[1] - c.control[2]), c.control[2]))
        return _cubic_end_curvature(ctrl, at_start)

    def rescale_handle(c: Curve, at_start: bool, target_kappa: float) -> None:
        ctrl = c.control
        if at_start:
            h = ctrl[1] - ctrl[0]
            v = ctrl[2] - ctrl[1]
        else:
            h = ctrl[2] - ctrl[3]
            v = ctrl[1] - ctrl[2]
        nh = float(np.linalg.norm(h))
        if nh < 1e-9:
            return
        # kappa(s) for handle length s*nh: (2/3)*cross(h_hat, P2-P1(s))/ (s*nh)^2
        # solved numerically on a tight bracket — the cubic stays inside its
        # own chunk so the caller's gates bound any drift.
        best_s, best_err = 1.0, abs(end_curvature(c, at_start) - target_kappa)
        for s in (0.7, 0.8, 0.9, 1.1, 1.25, 1.4):
            trial = ctrl.copy()
            if at_start:
                trial[1] = trial[0] + s * (ctrl[1] - ctrl[0])
            else:
                trial[2] = trial[3] + s * (ctrl[2] - ctrl[3])
            err = abs(_cubic_end_curvature(trial, at_start) - target_kappa)
            if err < best_err:
                best_err, best_s = err, s
        if best_s != 1.0:
            if at_start:
                ctrl[1] = ctrl[0] + best_s * (ctrl[1] - ctrl[0])
            else:
                ctrl[2] = ctrl[3] + best_s * (ctrl[2] - ctrl[3])

    out = [Curve(c.degree, c.control.copy()) for c in curves]
    for src_c, dst in zip(curves, out):
        dst.meta = getattr(src_c, "meta", None)
    limit = math.cos(math.radians(8.0))
    for i in range(len(out)):
        a, b = out[i], out[(i + 1) % len(out)]
        if i == len(out) - 1 and len(out) == 2:
            break
        ta, tb = _tangent_out(a), _tangent_in(b)
        if float(ta @ tb) < limit:
            continue                        # not a smooth join
        rig_a, rig_b = is_rigid(a), is_rigid(b)
        if rig_a and rig_b:
            continue
        ka, kb = end_curvature(a, False), end_curvature(b, True)
        if abs(ka - kb) < 1e-4:
            continue
        if rig_a:
            rescale_handle(b, True, ka)
        elif rig_b:
            rescale_handle(a, False, kb)
        else:
            sign = math.copysign(1.0, ka if abs(ka) > abs(kb) else kb)
            target = sign * math.sqrt(abs(ka) * abs(kb)) if ka * kb > 0 else 0.5 * (ka + kb)
            rescale_handle(a, False, target)
            rescale_handle(b, True, target)
    return out


def _loop_fit_deviation(loop: np.ndarray, curves: list[Curve]) -> float:
    """Bidirectional hard-accuracy of a DRAWN loop (audit P0):
      fit->boundary — every drawn sample near the polyline (catches oval blobs and
      bulges the per-chunk interval test cannot see once a whole loop mis-routes);
      boundary->fit — every polyline vertex near the drawn curve (catches dropped
      detail; the audit measured 9.75px here on a wordmark turned circle)."""
    if not curves:
        return float("inf")
    from scipy.spatial import cKDTree
    # sample every drawn curve at <=~0.7px so point-to-point distance approximates
    # point-to-curve (a sparse 24-sample discretization reads tangential offset as
    # 5px of 'error' on a large circle and would fail every good fit)
    pieces = []
    for c in curves:
        chord = float(np.linalg.norm(c.control[-1] - c.control[0]))
        pieces.append(eval_curve(c, max(8, min(400, int(2.0 * chord) + 4))))
    drawn = np.vstack(pieces)
    boundary_to_fit = float(cKDTree(drawn).query(loop)[0].max())
    fit_to_boundary = float(cKDTree(loop).query(drawn)[0].max())
    return max(boundary_to_fit, fit_to_boundary)


def _pixel_faithful_curves(loop: np.ndarray) -> list[Curve]:
    """Last-resort fallback: the boundary itself as a ~2px line chain.  Not pretty,
    but pixel-faithful — the audit's rule is that an inaccurate primitive must never
    ship, and the final fallback must be MORE detailed, not a forced loose cubic."""
    ring = resample_ring(np.vstack((loop, loop[:1])), 2.0)[:-1]
    if len(ring) < 3:
        ring = loop
    return [Curve(1, np.vstack((ring[i], ring[(i + 1) % len(ring)])))
            for i in range(len(ring))]


def _smooth_fallback_curves(loop: np.ndarray, px: float) -> list[Curve]:
    """Degradation-ladder rung 1 (METHOD_ICE 3.5): corner-aware G1 cubic chain.

    When the primary paper fit fails the backstop, the old behaviour shipped the
    raw ~2px staircase polyline — perceptually the worst possible SVG.  This rung
    keeps the accuracy discipline (the caller re-checks deviation/IoU/self-
    intersection) but stays SMOOTH: gentle non-shrinking Taubin, two-scale corner
    detection, recursive tangent-constrained cubics between corners (C0 only at
    detected corners, G1 everywhere else)."""
    closed = np.vstack((loop, loop[:1]))
    spacing = 0.8
    ring = taubin_smooth_ring(resample_ring(closed, spacing), passes=1)[:-1]
    n = len(ring)
    if n < 8:
        return []
    corner_idx = sorted(set(_multiscale_corners(ring, 1.2, spacing)))
    corner_set = set(corner_idx)
    if len(corner_idx) < 2:
        # No reliable corners: quarter the ring so every join stays G1.
        base = corner_idx[0] if corner_idx else 0
        corner_idx = sorted({base % n, (base + n // 4) % n,
                             (base + n // 2) % n, (base + 3 * n // 4) % n})
        corner_set = set(corner_idx) & corner_set

    def central_tangent(k: int) -> np.ndarray:
        t = ring[(k + 1) % n] - ring[(k - 1) % n]
        norm = float(np.linalg.norm(t))
        return t / norm if norm > 1e-9 else np.array([1.0, 0.0])

    curves: list[Curve] = []
    bounds = list(zip(corner_idx, corner_idx[1:] + [corner_idx[0] + n]))
    for a, b in bounds:
        pts = ring[[k % n for k in range(a, b + 1)]]
        if len(pts) < 2:
            continue
        ta = pts[1] - pts[0] if (a % n) in corner_set else central_tangent(a % n)
        tb = pts[-1] - pts[-2] if (b % n) in corner_set else central_tangent(b % n)
        for tangent in (ta, tb):
            norm = float(np.linalg.norm(tangent))
            if norm > 1e-9:
                tangent /= norm
        curves.extend(_fit_g1_span(pts, ta, tb, max(0.35, 0.5 * px)))
    return curves


def _dense_fallback_curves(loop: np.ndarray) -> list[Curve]:
    """Degradation-ladder rung 2: dense-but-smooth interpolating cubic chain.

    Near-interpolates the gently smoothed boundary (one cubic per ~1px edge,
    central-difference tangents) — heavy on segments but free of staircase
    jaggies; strictly better to look at than the raw polyline at equal
    fidelity."""
    ring = taubin_smooth_ring(resample_ring(np.vstack((loop, loop[:1])), 1.0),
                              passes=2)[:-1]
    n = len(ring)
    if n < 4:
        return []
    tangents = np.roll(ring, -1, axis=0) - np.roll(ring, 1, axis=0)
    norms = np.maximum(np.linalg.norm(tangents, axis=1, keepdims=True), 1e-9)
    tangents = tangents / norms
    curves: list[Curve] = []
    for i in range(n):
        j = (i + 1) % n
        p0, p1 = ring[i], ring[j]
        chord = float(np.linalg.norm(p1 - p0))
        curves.append(Curve(3, np.vstack((p0, p0 + tangents[i] * chord / 3.0,
                                          p1 - tangents[j] * chord / 3.0, p1))))
    return curves


def _foreign_trespass(curves: list[Curve], own_bound: float | None = None) -> bool:
    """Voronoi property-line test against the per-mask foreign-ink context.

    The tiny paths return WITHOUT passing _finish_loop, so an inflated
    fitEllipseDirect counter (2px hole -> ellipse overshooting 0.5px) walked
    into a 1px inter-letter gap unchecked — and a HOLE past its own outer
    contour turns to INK under evenodd (3 crossings), darkening the gap
    (114_bank merge class).  own_bound therefore adds a second law for
    evidence-exact tiny loops: every drawn point must stay within own_bound
    native px of the loop's OWN ink, neighbours or not."""
    ctx = _FOREIGN_INK[0]
    if ctx is None or not curves or ctx[2] < 2:
        return False
    dt_own, dt_others, fscale = ctx
    drawn = np.vstack([eval_curve(c, 12) for c in curves])
    ix = np.clip((drawn[:, 0] * fscale).astype(int), 0, dt_own.shape[1] - 1)
    iy = np.clip((drawn[:, 1] * fscale).astype(int), 0, dt_own.shape[0] - 1)
    if _VORONOI_LAWS:
        depth = dt_own[iy, ix] - dt_others[iy, ix]
        in_gap = (dt_own[iy, ix] + dt_others[iy, ix]) >= 0.75 * fscale
        if bool(in_gap.any()) and float(depth[in_gap].max()) > 0.35 * fscale:
            return True
    if own_bound is not None and float(dt_own[iy, ix].max()) > own_bound * fscale:
        return True
    return False


def _tiny_template_curves(name: str, th: np.ndarray) -> list[Curve] | None:
    """Exact analytic curves for a fitted tiny template (world native px)."""
    if name == "circle":
        center = np.array([th[0], th[1]])
        return _earc_curves((center, np.array([th[2], th[2]]), 0.0, 0.0, 2.0 * math.pi), None)
    if name == "ellipse":
        return _earc_curves((np.array([th[0], th[1]]), np.array([th[2], th[3]]),
                             float(th[4]), 0.0, 2.0 * math.pi), None)
    if name in ("rect", "diamond"):
        cx, cy, hw, hh, ang = float(th[0]), float(th[1]), float(th[2]), float(th[3]), float(th[4])
        c, s = math.cos(ang), math.sin(ang)
        rot = np.array([[c, -s], [s, c]])
        if name == "rect":
            base = np.array([[hw, hh], [-hw, hh], [-hw, -hh], [hw, -hh]])
        else:
            base = np.array([[hw, 0.0], [0.0, hh], [-hw, 0.0], [0.0, -hh]])
        pts = base @ rot.T + np.array([cx, cy])
        return [Curve(1, np.vstack((pts[k], pts[(k + 1) % 4]))) for k in range(4)]
    if name == "rrect":
        cx, cy, hw, hh, r, ang = (float(th[0]), float(th[1]), float(th[2]),
                                  float(th[3]), float(th[4]), float(th[5]))
        r = float(np.clip(r, 0.0, max(0.0, min(hw, hh) - 1e-3)))
        if r < 0.35:                       # visually sharp at tiny scale
            return _tiny_template_curves("rect", np.array([cx, cy, hw, hh, ang]))
        c, s = math.cos(ang), math.sin(ang)
        rot = np.array([[c, -s], [s, c]])
        origin = np.array([cx, cy])
        cw, ch = hw - r, hh - r
        corners = [(np.array([cw, ch]), 0.0), (np.array([-cw, ch]), 0.5 * math.pi),
                   (np.array([-cw, -ch]), math.pi), (np.array([cw, -ch]), 1.5 * math.pi)]
        curves: list[Curve] = []
        for i, (cc, a0) in enumerate(corners):
            arc_start = cc + r * np.array([math.cos(a0), math.sin(a0)])
            arc_end = cc + r * np.array([math.cos(a0 + 0.5 * math.pi), math.sin(a0 + 0.5 * math.pi)])
            world_c = origin + rot @ cc
            ws, we = origin + rot @ arc_start, origin + rot @ arc_end
            sample = np.vstack((ws, origin + rot @ (cc + r * np.array(
                [math.cos(a0 + 0.25 * math.pi), math.sin(a0 + 0.25 * math.pi)])), we))
            curves.extend(circular_beziers(ws, we, world_c, r, sample))
            nxt_cc, nxt_a0 = corners[(i + 1) % 4]
            nxt_start = origin + rot @ (nxt_cc + r * np.array([math.cos(nxt_a0), math.sin(nxt_a0)]))
            curves.append(Curve(1, np.vstack((we, nxt_start))))
        return curves
    return None


def _try_tiny_template(mask: np.ndarray, analysis_pixels: np.ndarray,
                       quantized: np.ndarray, scale: int,
                       bg: tuple[int, int, int]) -> FittedLoop | None:
    """Stage 2.2: fit the coverage template league to a tiny isolated region.

    Two independent acceptance gates (either failing keeps today's behaviour):
    coverage-MAE against the observed alpha map, and bidirectional Hausdorff
    between the analytic outline and the crack chain."""
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    ex = (float(xs.max() - xs.min()) + 1.0) / scale
    ey = (float(ys.max() - ys.min()) + 1.0) / scale
    extent = max(ex, ey)
    if not (3.0 <= extent <= 24.0):
        return None                       # <3px: the pixel chain IS the evidence
    loops = [lp for lp in mask_loops(mask) if len(lp) >= 4]
    if len(loops) != 1:
        return None                       # holes/multi-part: not league material
    try:
        from tiny_templates import fit_tiny_template, observed_alpha, template_outline
    except Exception:
        return None
    if analysis_pixels.shape[:2] != mask.shape:
        return None
    nx0 = int(xs.min()) // scale
    ny0 = int(ys.min()) // scale
    nx1 = min(int(xs.max()) // scale + 2, analysis_pixels.shape[1] // scale - 1)
    ny1 = min(int(ys.max()) // scale + 2, analysis_pixels.shape[0] // scale - 1)
    nx0 = max(0, nx0 - 2)
    ny0 = max(0, ny0 - 2)
    ink = np.array(_region_color(analysis_pixels, quantized, mask, scale), float)
    ring = cv2.dilate(mask.astype(np.uint8),
                      np.ones((2 * scale + 1, 2 * scale + 1), np.uint8)).astype(bool) & ~mask.astype(bool)
    bg_local = (np.median(analysis_pixels[ring], axis=0).astype(float)
                if ring.any() else np.array(bg, float))
    alpha = observed_alpha(analysis_pixels, mask, (nx0, ny0, nx1, ny1), scale, ink, bg_local)
    if alpha is None or alpha.size < 9:
        return None
    fit = fit_tiny_template(alpha, (float(nx0), float(ny0)))
    if fit is None:
        return None
    name, th, mae = fit
    if mae > 0.045:
        return None
    outline = template_outline(name, th)
    if outline is None or len(outline) < 8:
        return None
    loop_native = loops[0] / float(scale)
    from scipy.spatial import cKDTree
    d1 = float(cKDTree(outline).query(loop_native)[0].max())
    d2 = float(cKDTree(loop_native).query(outline)[0].max())
    if max(d1, d2) > max(0.9, 0.06 * extent):
        return None
    curves = _tiny_template_curves(name, th)
    if not curves:
        return None
    return FittedLoop(loop_native, curves, f"tiny-{name}")


def _tiny_pixel_curves(loop: np.ndarray) -> list[Curve]:
    """Exact crack-boundary chain for a tiny counter/detail.

    At 2--4px scale there is not enough evidence to infer a prettier circle or
    spline.  Resampling or smooth fitting can shrink a three-pixel A counter to a
    subpixel speck and erase Lacoste scales.  Preserve the observed topology; a
    later text/template stage may replace it when stronger evidence exists.
    """
    # Deblurred masks arrive at 4x density (0.25 native-px crack steps).  Keeping
    # every such step preserves no extra source evidence and explodes one scale to
    # hundreds of SVG lines, so collapse to roughly one native-pixel spacing first.
    original = np.asarray(loop, float)
    steps = np.linalg.norm(np.roll(original, -1, axis=0) - original, axis=1)
    if len(steps) and float(np.median(steps)) < 0.75:
        pts = resample_ring(np.vstack((original, original[:1])), 0.9)[:-1]
    else:
        # Native 1px loops (e.g. the three-pixel IKEA counter) are already the
        # irreducible evidence.  Resampling them moves their fill off the source
        # pixels and can erase the counter again.
        pts = original
    pts = np.asarray(pts, float)
    keep = np.r_[True, np.linalg.norm(np.diff(pts, axis=0), axis=1) > 1e-9]
    pts = pts[keep]
    if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    return [Curve(1, np.vstack((pts[i], pts[(i + 1) % len(pts)])))
            for i in range(len(pts))]


def _loop_fill_iou(loop: np.ndarray, curves: list[Curve]) -> float:
    """Fill IoU between the source polyline and the drawn loop.  The bidirectional
    DISTANCE misses fill-visible failures (a bowtie self-intersection or a mis-routed
    chain can stay Hausdorff-close yet paint the wrong region)."""
    if not curves:
        return 0.0
    drawn = np.vstack([eval_curve(c, 16) for c in curves])
    both = np.vstack((loop, drawn))
    lo = np.floor(both.min(axis=0)) - 2.0
    hi = np.ceil(both.max(axis=0)) + 2.0
    size = (int(hi[0] - lo[0]), int(hi[1] - lo[1]))
    if size[0] <= 2 or size[1] <= 2 or size[0] * size[1] > 4_000_000:
        return 1.0
    def rasterize(pts: np.ndarray) -> np.ndarray:
        img = Image.new("1", size, 0)
        ImageDraw.Draw(img).polygon([tuple(p) for p in (pts - lo)], fill=1)
        return np.asarray(img, bool)
    a, b = rasterize(loop), rasterize(drawn)
    union = int(np.sum(a | b))
    if union == 0:
        return 1.0
    return float(np.sum(a & b)) / union


def _chain_self_intersects(curves: list[Curve]) -> bool:
    """Explicit segment-intersection test on the drawn closed chain (audit P0):
    the fill IoU catches most self-intersection damage, but a small bowtie can
    survive both the IoU and the bidirectional distance.  Strict interior
    crossings only — shared endpoints of adjacent segments do not count."""
    if not curves:
        return False
    pts = np.vstack([eval_curve(c, 8)[:-1] for c in curves])
    if len(pts) > 400:
        pts = pts[np.linspace(0, len(pts) - 1, 400).astype(int)]
    n = len(pts)
    if n < 4:
        return False
    a = pts
    d = np.roll(pts, -1, axis=0) - pts
    eps = 1e-6
    for i in range(n - 2):
        j0 = i + 2
        j1 = n - 1 if i == 0 else n          # closed chain: seg 0 is adjacent to seg n-1
        if j0 >= j1:
            continue
        r = d[i]
        qp = a[j0:j1] - a[i]
        s = d[j0:j1]
        denom = r[0] * s[:, 1] - r[1] * s[:, 0]
        ok = np.abs(denom) > 1e-12
        if not ok.any():
            continue
        t = (qp[:, 0] * s[:, 1] - qp[:, 1] * s[:, 0])
        u = (qp[:, 0] * r[1] - qp[:, 1] * r[0])
        with np.errstate(divide="ignore", invalid="ignore"):
            tt = np.where(ok, t / denom, -1.0)
            uu = np.where(ok, u / denom, -1.0)
        if bool(np.any((tt > eps) & (tt < 1 - eps) & (uu > eps) & (uu < 1 - eps))):
            return True
    return False


def _finish_loop(
    loop: np.ndarray,
    curves: list[Curve],
    px: float,
    template: str,
    fit_profile: str | None = None,
) -> FittedLoop:
    """Loop-level accuracy backstop for every paper-mode exit path: bidirectional
    hard distance PLUS fill IoU (skipped for tiny loops where IoU is noise) PLUS
    an explicit self-intersection test.

    ``text-safe`` is an opt-in A/B profile for compact glyph contours.  Reviewed
    letters exposed valid 5--8 primitive fits with sub-1.1px boundary deviation
    that the fixed IoU threshold replaced by 29--86 raster-staircase lines.  In
    this profile low IoU triggers fallback only when the geometric deviation is
    also above 1.25px.  The production profile remains byte-for-byte unchanged.
    """
    profile = _PAPER_FIT_PROFILE if fit_profile is None else fit_profile
    if profile not in _PAPER_FIT_PROFILES:
        valid = ", ".join(_PAPER_FIT_PROFILES)
        raise ValueError(f"unknown paper fit profile {profile!r}; expected one of: {valid}")
    # Scale-aware: 2.5px of licence on an 8px letter is a whole stem width —
    # neighbouring glyphs 2px apart BLEED into one blob (114_bank: components
    # 1/6).  Small loops get a proportional budget; large shapes keep the
    # classic native-staircase tolerance.
    loop_extent = float(max(np.ptp(loop[:, 0]), np.ptp(loop[:, 1]))) if len(loop) else 0.0
    tolerance = min(max(2.5, 2.0 * px + 1.0), max(0.8, 0.12 * loop_extent))
    area = abs(float(np.sum(loop[:, 0] * np.roll(loop[:, 1], -1) - np.roll(loop[:, 0], -1) * loop[:, 1]))) / 2.0
    perimeter_len = float(np.sum(np.linalg.norm(np.roll(loop, -1, axis=0) - loop, axis=1)))
    thickness = 2.0 * area / max(perimeter_len, 1e-9)

    def accepted(candidate: list[Curve]) -> bool:
        """The unchanged accuracy discipline, applied to any candidate chain."""
        if not candidate:
            return False
        deviation = _loop_fit_deviation(loop, candidate)
        if deviation > tolerance:
            return False
        foreign = _FOREIGN_INK[0] if _VORONOI_LAWS else None
        if foreign is not None and foreign[2] >= 2:
            # Voronoi rule: neighbours 1-2px apart both fatten into the gap and
            # MEET (114_bank letters), though neither touches the other's ink.
            # A drawn point may never be closer to a neighbour's ink than to
            # its own — the gap midline is the property line.
            dt_own, dt_others, fscale = foreign
            drawn = np.vstack([eval_curve(c, 12) for c in candidate])
            ix = np.clip((drawn[:, 0] * fscale).astype(int), 0, dt_own.shape[1] - 1)
            iy = np.clip((drawn[:, 1] * fscale).astype(int), 0, dt_own.shape[0] - 1)
            depth = dt_own[iy, ix] - dt_others[iy, ix]   # >0: closer to neighbour
            in_gap = (dt_own[iy, ix] + dt_others[iy, ix]) >= 0.75 * fscale
            if bool(in_gap.any()) and float(depth[in_gap].max()) > 0.35 * fscale:
                return False                 # trespassing across a REAL gap only
        # IoU is only informative for THICK shapes: a 4px-wide letter stem at a
        # good 0.5px fit already reads ~0.75 IoU (the boundary band dominates its
        # area), so gating thin loops on IoU sent every small letter into the
        # polyline fallback.  Thin shapes are guarded by the distance above.
        if area >= 60.0 and thickness >= 6.0:
            poor_iou = _loop_fill_iou(loop, candidate) < 0.90
            if poor_iou and (profile == "production" or deviation > 1.25):
                return False
        return not _chain_self_intersects(candidate)

    # Stage 2.4: G2 fairing first — the faired chain ships ONLY if it passes
    # the very same gates; otherwise the untouched fit competes as before.
    if curves and template != "paper-tiny":
        faired = _g2_fair_chain(curves)
        if faired is not curves and accepted(faired):
            return FittedLoop(loop, faired, template)
    if accepted(curves):
        return FittedLoop(loop, curves, template)

    # Degradation ladder (METHOD_ICE 3.5): never ship a raster staircase while a
    # smooth chain passes the very same accuracy gates.  Tiny loops keep the
    # exact pixel chain — at 2-8px the crack polyline IS the evidence and
    # smoothing it erased real counters before (the reverted subpixel-RDP).
    extent = float(max(np.ptp(loop[:, 0]), np.ptp(loop[:, 1])))
    if area > 18.0 or extent > 8.0:
        for candidate, suffix in ((_smooth_fallback_curves(loop, px), "-g1-fallback"),
                                  (_dense_fallback_curves(loop), "-dense-fallback")):
            if accepted(candidate):
                return FittedLoop(loop, candidate, template + suffix)
    return FittedLoop(loop, _pixel_faithful_curves(loop), template + "-fallback")


def _fit_loop_joint(loop: np.ndarray, alpha: float, px: float) -> FittedLoop | None:
    """Stage 2.3: the WHOLE loop as one open DP chain with corners as PRICED
    latent decisions (METHOD_ICE 3.3).  Returns None whenever any prerequisite
    is missing — the caller then runs the classic threshold->removal path.

    Mechanism: raw CNN probabilities at native density -> local-max superset at
    a LAX 0.15 threshold (no NMS radius, no collapse window) -> recentered to
    the turning apex -> the loop is unrolled at the STRONGEST candidate (that
    seam is C0 by construction, welded at the support intersection like the
    classic 1-corner path) -> every other candidate becomes a corner PRICE at
    its DP node: the shortest path pays min(G1 bend penalty, price), so two
    adjacent true letter corners survive (two cheap corners beat one strained
    clothoid) and a staircase artefact loses (smooth continuation is cheaper)."""
    n = len(loop)
    if n < 24:
        return None
    # Native-density ring for the CNN (its turning windows are in px).
    spacing = float(np.median(np.linalg.norm(np.roll(loop, -1, axis=0) - loop, axis=1)))
    stride = max(1, int(round(1.0 / max(spacing, 1e-6)))) if spacing < 0.6 else 1
    coarse = loop[::stride]
    if len(coarse) < 10:
        return None
    probs = _corner_probabilities(coarse)
    if probs is None or len(probs) != len(coarse):
        return None
    above = probs >= _JOINT_SUPERSET_THRESHOLD
    if not bool(above.any()):
        return None                        # smooth loop: classic path handles it
    if float(probs.max()) < 0.30:
        return None                        # noise-only claims: not corner territory
    if _loop_is_circle(loop, px):
        return None                        # a genuine circle outranks any corner
                                           # claim (decision order: full ellipse
                                           # first — G1 doc rule; the outlier
                                           # budget must never chord a disc)
    # Local maxima of the probability signal (superset, deliberately lax).
    prev_p = np.roll(probs, 1)
    next_p = np.roll(probs, -1)
    cand_coarse = np.flatnonzero(above & (probs >= prev_p) & (probs >= next_p))
    if not len(cand_coarse):
        return None
    recentered = _recenter_corners(coarse, [int(c) for c in cand_coarse])
    nc = len(coarse)
    cand_pairs = []
    for idx in recentered:
        ring_dist = np.minimum((cand_coarse - idx) % nc, (idx - cand_coarse) % nc)
        near = cand_coarse[ring_dist <= 4]
        p_max = float(probs[near].max()) if len(near) else float(probs[idx])
        cand_pairs.append(((int(idx) * stride) % n, p_max))
    cand_pairs = sorted(dict(cand_pairs).items())
    if stride > 1:
        # coarse*stride is up to stride-1 vertices off the true apex on the
        # full-density ring — re-snap there before pricing DP nodes.
        refined: dict[int, float] = {}
        for full_idx, p in cand_pairs:
            snapped = _recenter_corners(loop, [full_idx], radius=stride + 2)
            key = snapped[0] if snapped else full_idx
            refined[key] = max(p, refined.get(key, 0.0))
        cand_pairs = sorted(refined.items())
    strongest = max(cand_pairs, key=lambda kv: kv[1])[0]
    ring = np.vstack((loop[strongest:], loop[:strongest], loop[strongest:strongest + 1]))
    prices: dict[int, float] = {}
    w_turn = max(3, min(6, n // 8))
    for full_idx, p in cand_pairs:
        u = (full_idx - strongest) % n     # vertex index in the unrolled chain
        if u == 0 or u >= n - 2:
            continue                       # the seam corner is C0 already
        price = _corner_price(p)
        # The raster testifies too: at a hard local turn (star tip, box corner)
        # a low CNN score must not price the corner out of reach — otherwise a
        # single r=4 cubic threads the tip cheaper than corner + two lines.
        va = loop[full_idx] - loop[(full_idx - w_turn) % n]
        vb = loop[(full_idx + w_turn) % n] - loop[full_idx]
        na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
        if na > 1e-9 and nb > 1e-9:
            turn = math.degrees(math.acos(max(-1.0, min(1.0, float((va / na) @ (vb / nb))))))
            if turn >= 45.0:
                # (Two cap-veto variants were probed here 2026-07-14 and
                # removed as DEAD AIM: the spotify-380 caps measure turn(w)
                # of only 18-23 deg — they never even ENTER this branch.
                # 2026-07-15 instrumentation closed the case: the residual
                # cap corner was never PAID at all — it was the free C0 of
                # the unroll SEAM (strongest candidate p=0.42).  The seam
                # court below now judges that cut under the DP's own
                # price-vs-penalty law.)
                price = min(price, _JOINT_CAP_PRICE)
        prices[u] = min(prices.get(u, float("inf")), price)
    chain = fit_segment_midpoints(ring, alpha, px, snap_ends=False,
                                  corner_prices=prices or None)
    if not chain:
        return None
    corner_joins = list(getattr(fit_segment_midpoints, "last_corner_joins", []))
    # Acute apexes: marching squares rounds a sharp tip over 2-4px, and the DP
    # legitimately covers that cap with a short cubic between the two flanking
    # lines.  The IDEAL shape has no cap — absorb it and extend the lines to
    # their exact intersection (bounded: only <=4.5px caps at PAID corners).
    if corner_joins and len(chain) >= 3:
        # Single pass over the PAID join positions with consistent indexing —
        # the first version scanned curves while mixing pre-/post-absorption
        # neighbours and could drop a cap without welding its true flanks
        # (latent in 7c7c4c9; surfaced as a spurious -g1-fallback on rects).
        # Cap bound 8px: the sharper the tip, the longer the raster cap.
        drop: set[int] = set()
        for c_lo, _vertex in corner_joins:
            for cap_idx in (c_lo, c_lo - 1):
                if not (0 < cap_idx < len(chain)) or cap_idx in drop:
                    continue
                if (cap_idx - 1) in drop:
                    continue
                cap = chain[cap_idx]
                prv = chain[cap_idx - 1]
                nxt = chain[(cap_idx + 1) % len(chain)]
                if (cap.degree == 3 and getattr(cap, "meta", None) is None
                        and prv.degree == 1 and nxt.degree == 1
                        and float(np.linalg.norm(cap.control[-1] - cap.control[0])) <= 8.0):
                    p_tip = _corner_intersection(prv, nxt, cap.control[0])
                    _shift_curve_end(prv, p_tip)
                    _shift_curve_start(nxt, p_tip)
                    drop.add(cap_idx)
                    break
        if drop:
            chain = [c for i, c in enumerate(chain) if i not in drop]
            corner_joins = []          # indices are stale after absorption
    # SEAM COURT.  The unroll cut received its C0 for FREE — an open chain never
    # unifies its two ends, so the strongest candidate is the ONE corner the DP
    # can never price against a smooth continuation.  Judge it under the DP's
    # own law: corner price (same turn>=45 testimony cap) vs the G1 penalty the
    # actual end-tangent gap would cost.  When the seam loses on a chain with
    # no other PAID corner, the joint verdict is literally "zero corners" —
    # fit the loop cyclically, where no seam exists at all.  Instrumented on
    # the residual spotify-380 kink (2026-07-15): cap claim p=0.42 -> price
    # 3.9, measured seam gap 15.6deg -> penalty 1.215; the corner survived
    # ONLY because the cut made it free.  Chains that did pay corners keep
    # the classic weld: their strongest claim is a corner among corners.
    if not corner_joins:
        ta_seam = _tangent_out(chain[-1])
        tb_seam = _tangent_in(chain[0])
        if ta_seam is not None and tb_seam is not None:
            gap = math.acos(max(-1.0, min(1.0, float(ta_seam @ tb_seam))))
            pen = _PAPER_G1_W * max(0.0, gap - math.radians(_PAPER_G1_DEAD))
            seam_price = _corner_price(dict(cand_pairs).get(strongest, 1.0))
            va = loop[strongest] - loop[(strongest - w_turn) % n]
            vb = loop[(strongest + w_turn) % n] - loop[strongest]
            na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
            if na > 1e-9 and nb > 1e-9:
                turn = math.degrees(math.acos(max(-1.0, min(1.0, float((va / na) @ (vb / nb))))))
                if turn >= 45.0:
                    seam_price = min(seam_price, _JOINT_CAP_PRICE)
            if pen <= seam_price:
                return _finish_loop(loop, _fit_smooth_closed(loop, alpha, px),
                                    px, "paper-smooth")
    # Weld the wrap seam C0 at the strongest candidate (classic 1-corner move).
    p_seam = _corner_intersection(chain[-1], chain[0], loop[strongest])
    _shift_curve_end(chain[-1], p_seam)
    _shift_curve_start(chain[0], p_seam)
    # Weld every DP-paid corner at the analytic support intersection.
    for c_lo, vertex in corner_joins:
        if 0 < c_lo < len(chain):
            p_c = _corner_intersection(chain[c_lo - 1], chain[c_lo], vertex)
            _shift_curve_end(chain[c_lo - 1], p_c)
            _shift_curve_start(chain[c_lo], p_c)
    keep = {c_lo - 1 for c_lo, _ in corner_joins if 0 < c_lo < len(chain)}
    curves = _regularize_axis_parallel(_regularize_loop(chain))
    curves = _enforce_g1_chain(curves, max_angle_deg=20.0, closed=False,
                               keep_c0=keep if len(curves) == len(chain) else None)
    return _finish_loop(loop, curves, px, "paper-joint")


def fit_loop_paper(loop: np.ndarray, alpha: float = 0.13, corner_positions: np.ndarray | None = None, px: float = 1.0) -> FittedLoop:
    """Full paper boundary fit for one loop: Sec4/Sec5 corners split the loop into
    segments, each fit to edge midpoints by Sec 5.1 with the directional interval
    accuracy constraint.  A corner-free loop is a smooth curve split into four arcs.

    The staircase is absorbed by the per-midpoint interval (`px` wide), not by any
    pre-smoothing — so a genuine corner stays exactly sharp and a straight edge fits
    as one clean line.  Corners may be supplied externally (detected on the raw loop);
    only those lying on this loop are used."""
    # Topology-first floor for tiny counters/details.  Both conditions are needed:
    # do not turn a long one-pixel stroke into a staircase, but never let a compact
    # 2x2--8x8 region disappear merely because its corner probabilities are weak.
    signed = float(np.sum(loop[:, 0] * np.roll(loop[:, 1], -1)
                          - np.roll(loop[:, 0], -1) * loop[:, 1]))
    area = abs(signed) / 2.0
    extent = float(max(np.ptp(loop[:, 0]), np.ptp(loop[:, 1])))
    if area <= 18.0 and extent <= 8.0:
        # Tiny round scales/dots still have strong ellipse evidence at 4x.  Keep
        # them compact (four cubics) when the fit is genuinely close; angular or
        # under-sampled counters such as IKEA's A remain exact pixel chains.
        closed = np.vstack((loop, loop[:1]))
        ellipse = _ellipse_candidate(closed)
        if ellipse is not None and ellipse[0] <= 0.22 and not _foreign_trespass(ellipse[2], own_bound=0.45):
            return FittedLoop(loop, ellipse[2], "paper-tiny-ellipse")
        return FittedLoop(loop, _tiny_pixel_curves(loop), "paper-tiny")
    if _JOINT_CORNER_DP:
        joint = _fit_loop_joint(loop, alpha, px)
        if joint is not None:
            # A q30 disc often reaches the joint path via pseudo-corner claims;
            # give the ideal circle the same relative day in court it gets on
            # the smooth-closed path (it only wins when it explains the loop
            # as well as the joint chain does).
            closed = np.vstack((loop, loop[:1]))
            court = _relative_circle_court(closed, joint.curves, px)
            if court is not None:
                return FittedLoop(loop, court, "paper-circle-court")
            return joint
    if corner_positions is None:
        positions = paper_corner_positions(loop)
    else:
        candidates = np.asarray(corner_positions, dtype=float).reshape(-1, 2)
        if len(candidates):
            nearest = np.min(np.sum((loop[:, None, :] - candidates[None, :, :]) ** 2, axis=2), axis=0)
            positions = candidates[nearest <= 4.0]
        else:
            positions = np.empty((0, 2))
    n = len(loop)
    if len(positions) == 0 or _loop_is_circle(loop, px):
        # No corners, or a genuine full circle (spurious staircase corners on a disc
        # are overridden) -> the cyclic Sec 5.1 segment / co-circular disc path.
        return _finish_loop(loop, _fit_smooth_closed(loop, alpha, px), px, "paper-smooth")
    indices = sorted({int(np.argmin(np.sum((loop - p) ** 2, axis=1))) for p in positions})
    if len(indices) == 1:
        # ONE corner: unroll the loop AT that corner and fit the whole ring as a
        # single open Sec 5.1 segment — the corner stays C0 (an open chain never
        # unifies its two ends), everything else joins G1.
        i = indices[0]
        ring = np.vstack((loop[i:], loop[:i], loop[i:i + 1]))
        chain = fit_segment_midpoints(ring, alpha, px, snap_ends=False)
        if chain:
            p = _corner_intersection(chain[-1], chain[0], loop[i])
            _shift_curve_end(chain[-1], p)
            _shift_curve_start(chain[0], p)
        curves = _regularize_axis_parallel(_regularize_loop(chain))
        curves = _enforce_g1_chain(curves, max_angle_deg=20.0, closed=False)
        return _finish_loop(loop, curves, px, "paper")
    seg_curves = []
    for k in range(len(indices)):
        segment = _arc_slice(loop, indices[k], indices[(k + 1) % len(indices)])
        seg_curves.append(fit_segment_midpoints(segment, alpha, px, snap_ends=False))
    curves = _close_chain_corners(seg_curves, loop, indices)
    curves = _regularize_axis_parallel(_regularize_loop(curves))
    # Paper §6 continuity: a join whose two tangents differ by < 20 deg reads as smooth,
    # so unify it to G1 — clears the visible kink of any spurious corner the detector /
    # removal left on a curve, while genuine sharp corners (> 20 deg) stay C0.
    curves = _enforce_g1_chain(curves, max_angle_deg=20.0, closed=True)
    return _finish_loop(loop, curves, px, "paper")


def fit_perceptual_loop(loop: np.ndarray, feature_scale: float = 1.0) -> FittedLoop:
    """Interpolate a high-resolution boundary without simplifying its features.

    Smooth locations only very lightly.  Perceptual corners are C0 anchors;
    all other joins share a tangent and are therefore G1.  Every curve remains
    local, so a thin notch cannot be traded for a globally cheaper primitive.
    """
    spacing = max(0.42, min(0.62, 0.48 * feature_scale))
    smooth = taubin_smooth_ring(resample_ring(loop, spacing), passes=2)
    ring = smooth[:-1]
    n = len(ring)
    if n < 3:
        return FittedLoop(smooth, [Curve(1, np.vstack((ring[0], ring[-1])))], "perceptual-contour")
    corners = set(_multiscale_corners(ring, feature_scale, spacing))
    curves: list[Curve] = []
    for i in range(n):
        j = (i + 1) % n
        chord_vector = ring[j] - ring[i]
        chord = float(np.linalg.norm(chord_vector))
        if chord < 1e-8:
            continue
        direction = chord_vector / chord
        tangent_start = direction if i in corners else _unit(ring[j] - ring[(i - 1) % n])
        tangent_end = direction if j in corners else _unit(ring[(j + 1) % n] - ring[i])
        handle = chord / 3.0
        curves.append(
            Curve(
                3,
                np.vstack((ring[i], ring[i] + handle * tangent_start, ring[j] - handle * tangent_end, ring[j])),
            )
        )
    return FittedLoop(smooth, curves, "perceptual-contour")


def curve_command(curve: Curve, move: bool = False) -> str:
    p = curve.control
    prefix = f"M{p[0,0]:.2f} {p[0,1]:.2f}" if move else ""
    if curve.degree == 1:
        return f"{prefix}L{p[1,0]:.2f} {p[1,1]:.2f}"
    if curve.degree == 2:
        return f"{prefix}Q{p[1,0]:.2f} {p[1,1]:.2f} {p[2,0]:.2f} {p[2,1]:.2f}"
    return f"{prefix}C{p[1,0]:.2f} {p[1,1]:.2f} {p[2,0]:.2f} {p[2,1]:.2f} {p[3,0]:.2f} {p[3,1]:.2f}"


def loop_path(loop: FittedLoop) -> str:
    return "".join(curve_command(curve, move=(i == 0)) for i, curve in enumerate(loop.curves)) + "Z"


def chain_path(curves: list[Curve]) -> str:
    """Open path (no Z) for a stroked centerline chain."""
    return "".join(curve_command(curve, move=(i == 0)) for i, curve in enumerate(curves))


def _gradient_svg_def(region_id: int, fill: tuple) -> tuple[str, str]:
    """(defs_row, fill_attr) for a Region.fill gradient."""
    gid = f"grad{region_id}"
    stops = "".join(
        f'<stop offset="{t:.4f}" stop-color="#{r:02x}{g:02x}{b:02x}"/>'
        for t, (r, g, b) in fill[-1])
    if fill[0] == "linear":
        (x0, y0), (x1, y1) = fill[1], fill[2]
        row = (f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" '
               f'x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}">{stops}</linearGradient>')
    else:
        (cx, cy), r0, r1 = fill[1], fill[2], fill[3]
        # SVG radial gradients start at 0: renormalize stops onto [0, r1]
        if r1 > 1e-9 and r0 > 1e-9:
            stops = "".join(
                f'<stop offset="{(r0 + t * (r1 - r0)) / r1:.4f}" stop-color="#{r:02x}{g:02x}{b:02x}"/>'
                for t, (r, g, b) in fill[-1])
        row = (f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" '
               f'cx="{cx:.2f}" cy="{cy:.2f}" r="{r1:.2f}">{stops}</radialGradient>')
    return row, f"url(#{gid})"


def write_svgs(output: Path, regions: list[Region], size: tuple[int, int]) -> None:
    w, h = size
    head = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
    fill_rows = [head, '<rect width="100%" height="100%" fill="#ffffff"/>']
    map_rows = [head, '<rect width="100%" height="100%" fill="#ffffff"/>']
    defs: list[str] = []
    for region_id, region in enumerate(regions):
        data = "".join(loop_path(loop) for loop in region.loops)
        fill = "#%02x%02x%02x" % region.color
        if getattr(region, "fill", None):
            def_row, fill = _gradient_svg_def(region_id, region.fill)
            defs.append(def_row)
        if getattr(region, "stroke", None):
            width, stroke_curves, closed_s = region.stroke
            sdata = chain_path(stroke_curves) + ("Z" if closed_s else "")
            fill_rows.append(f'<path data-region="{region_id}" d="{sdata}" fill="none" stroke="{fill}" '
                             f'stroke-width="{width:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')
            for curve in stroke_curves:
                kind = "line" if curve.degree == 1 else "curve"
                color = TYPE_COLORS[kind]
                map_rows.append(f'<path data-type="{kind}" d="{curve_command(curve, True)}" fill="none" '
                                f'stroke="rgb{color}" stroke-width="0.65"/>')
        if data:
            apron = (f' stroke="{fill}" stroke-width="0.6" stroke-linejoin="round"'
                     if getattr(region, "bleed", False) and not str(fill).startswith("url(") else "")
            fill_rows.append(f'<path data-region="{region_id}" d="{data}" fill="{fill}"'
                             f' fill-rule="evenodd"{apron}/>')
        for loop in region.loops:
            for curve in loop.curves:
                kind = "line" if curve.degree == 1 else ("ellipse" if loop.template == "ellipse" else "curve")
                color = TYPE_COLORS[kind]
                map_rows.append(f'<path data-type="{kind}" d="{curve_command(curve, True)}" fill="none" stroke="rgb{color}" stroke-width="0.65"/>')
    if defs:
        fill_rows.insert(1, "<defs>" + "".join(defs) + "</defs>")
    fill_rows.append("</svg>")
    map_rows.append("</svg>")
    (output / "03_rebuilt_filled.svg").write_text("\n".join(fill_rows), encoding="utf-8")
    (output / "02_primitive_map.svg").write_text("\n".join(map_rows), encoding="utf-8")


def _sample_loop(loop: FittedLoop, scale: int) -> list[tuple[float, float]]:
    chunks = [eval_curve(curve, 28) for curve in loop.curves]
    points = np.vstack([chunk if i == 0 else chunk[1:] for i, chunk in enumerate(chunks)])
    return [tuple(point * scale) for point in points]


def render_regions(regions: list[Region], size: tuple[int, int], outline: bool = False, scale: int = 4) -> Image.Image:
    canvas = Image.new("RGB", (size[0] * scale, size[1] * scale), "white")
    for region in regions:
        if outline:
            draw = ImageDraw.Draw(canvas)
            for loop in region.loops:
                draw.line(_sample_loop(loop, scale), fill=(0, 0, 0), width=scale, joint="curve")
            if getattr(region, "stroke", None):
                _, stroke_curves, closed_s = region.stroke
                pts = [tuple(q * scale) for q in np.vstack([eval_curve(c, 24) for c in stroke_curves])]
                if closed_s:
                    pts.append(pts[0])
                draw.line(pts, fill=(0, 0, 0), width=scale, joint="curve")
            continue
        if getattr(region, "stroke", None):
            width, stroke_curves, closed_s = region.stroke
            draw = ImageDraw.Draw(canvas)
            pts = [tuple(q * scale) for q in np.vstack([eval_curve(c, 24) for c in stroke_curves])]
            w_px = max(1, int(round(width * scale)))
            if closed_s:
                pts.append(pts[0])
                draw.line(pts, fill=region.color, width=w_px, joint="curve")
            else:
                draw.line(pts, fill=region.color, width=w_px, joint="curve")
                r = w_px / 2.0
                for cap in (pts[0], pts[-1]):
                    draw.ellipse([cap[0] - r, cap[1] - r, cap[0] + r, cap[1] + r], fill=region.color)
            continue
        mask = Image.new("1", canvas.size, 0)
        mask_array = np.zeros((canvas.height, canvas.width), dtype=np.uint8)
        for loop in region.loops:
            part = Image.new("1", canvas.size, 0)
            ImageDraw.Draw(part).polygon(_sample_loop(loop, scale), fill=1)
            mask_array ^= np.asarray(part, dtype=np.uint8)
        mask = Image.fromarray(mask_array * 255, "L")
        if getattr(region, "fill", None):
            canvas.paste(_render_gradient_fill(region.fill, canvas.size, scale), (0, 0), mask)
        else:
            canvas.paste(Image.new("RGB", canvas.size, region.color), (0, 0), mask)
    return canvas.resize(size, Image.Resampling.LANCZOS)


def _render_gradient_fill(fill: tuple, size: tuple[int, int], scale: int) -> Image.Image:
    """Rasterize a Region.fill gradient (coordinates are native px; canvas is scaled)."""
    w, h = size
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32) / scale,
                         np.arange(h, dtype=np.float32) / scale)
    if fill[0] == "linear":
        (x0, y0), (x1, y1) = fill[1], fill[2]
        vx, vy = x1 - x0, y1 - y0
        denom = max(1e-9, vx * vx + vy * vy)
        t = ((xs - x0) * vx + (ys - y0) * vy) / denom
    else:
        (cx, cy), r0, r1 = fill[1], fill[2], fill[3]
        t = (np.hypot(xs - cx, ys - cy) - r0) / max(1e-9, r1 - r0)
    t = np.clip(t, 0.0, 1.0)
    stops = fill[-1]
    offs = np.array([s[0] for s in stops], np.float32)
    cols = np.array([s[1] for s in stops], np.float32)
    out = np.empty((h, w, 3), np.uint8)
    for ch in range(3):
        out[..., ch] = np.clip(np.interp(t, offs, cols[:, ch]), 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGB")


def _detect_diagram_signature(masks: list[np.ndarray], analysis_scale: int) -> bool:
    """Router lane 1 (design D1): the width-split lane is FOR DIAGRAMS —
    globally it tore up the 512px logo corpus (vai50 kinks 4.61 -> 5.80).
    A diagram announces itself: a large share of ink sits in RECTANGULAR
    panels (minAreaRect coverage >= 0.85 on big masks) and several small
    ELONGATED connectors/arrows exist alongside.  Logos/text almost never
    combine both."""
    if len(masks) < 4:
        return False
    total_ink = float(sum(int(m.sum()) for m in masks)) or 1.0
    panel_ink = 0.0
    connectors = 0
    for m in masks:
        area = int(m.sum())
        if area < 40 * analysis_scale:
            continue
        ys, xs = np.nonzero(m)
        w_b = float(xs.max() - xs.min() + 1)
        h_b = float(ys.max() - ys.min() + 1)
        if area >= 900 * analysis_scale * analysis_scale:
            pts = np.column_stack((xs, ys)).astype(np.float32)
            rect = cv2.minAreaRect(pts.reshape(-1, 1, 2))
            rect_area = max(1.0, rect[1][0] * rect[1][1])
            if area / rect_area >= 0.85:
                panel_ink += area
        else:
            aspect = max(w_b, h_b) / max(1.0, min(w_b, h_b))
            if aspect >= 3.0:
                connectors += 1
    return panel_ink / total_ink >= 0.40 and connectors >= 3


def _split_masks_by_width(masks: list[np.ndarray], analysis_scale: int) -> list[np.ndarray]:
    """Line-width v3 groundwork (the two whole-region stroke attempts failed
    because axes+polyline FUSE into one multi-width region): split a BIG
    bimodal-width mask into its thin (<=4.5 native px) and thick parts as
    SEPARATE same-colour regions BEFORE the graph is built — the polyline
    between node markers becomes stroke-eligible pieces, the markers stay
    fillable blobs.  Small regions (extent <= 40px) are exempt: glyph stems
    must never be torn off their letters."""
    out: list[np.ndarray] = []
    thr = 2.25 * analysis_scale          # dt half-width for 4.5 native px
    for m in masks:
        mm = m.astype(np.uint8)
        ys, xs = np.nonzero(mm)
        if not len(ys):
            continue
        extent_native = max(float(xs.max() - xs.min()), float(ys.max() - ys.min())) / analysis_scale
        if extent_native <= 40.0:
            out.append(m)
            continue
        dt = cv2.distanceTransform(mm, cv2.DIST_L2, 3)
        thin_zone = (dt > 0) & (dt <= thr)
        thick_seed = dt > thr
        if not thick_seed.any() or not thin_zone.any():
            out.append(m)
            continue
        # thick part = pixels closer to a thick seed than the thin ridge:
        # reconstruct by dilating seeds within the mask
        thick = cv2.dilate(thick_seed.astype(np.uint8), np.ones((3, 3), np.uint8),
                           iterations=int(np.ceil(thr))) .astype(bool) & mm.astype(bool)
        thin = mm.astype(bool) & ~thick
        n_thin = int(thin.sum())
        n_thick = int(thick.sum())
        if n_thin < 60 * analysis_scale or n_thick < 60 * analysis_scale:
            out.append(m)
            continue
        # both parts must be substantial AND the thin part elongated
        dt_thin = cv2.distanceTransform(thin.astype(np.uint8), cv2.DIST_L2, 3)
        med_w = float(np.median(dt_thin[dt_thin > 0.6])) if (dt_thin > 0.6).any() else 0.0
        if med_w <= 0.0 or n_thin / max(1.0, 2.0 * med_w) < 30 * analysis_scale:
            out.append(m)
            continue
        # clean specks: components under 12px fall back to the thick side
        cnt, lbl = cv2.connectedComponents(thin.astype(np.uint8), connectivity=8)
        keep_thin = np.zeros_like(thin)
        for c in range(1, cnt):
            comp = lbl == c
            if int(comp.sum()) >= 12 * analysis_scale:
                keep_thin |= comp
            else:
                thick |= comp
        if not keep_thin.any():
            out.append(m)
            continue
        out.append(thick)
        out.append(keep_thin)
    return out


def _merge_gradient_field(masks: list[np.ndarray], reference_rgb: np.ndarray,
                          analysis_scale: int) -> tuple[list[np.ndarray], dict[int, tuple]]:
    """Form-aware gradient (H95 lost-detail strike): a ramp THROUGH a logo
    shape never satisfies the band-chain topology of _merge_gradient_stacks
    (isolated map: items 068/059 ride 99-135 bands into the graph path with
    kinks 8.8-8.9).  Instead of chains, fit a LINEAR Lab FIELD over the union
    of a connected same-hue family and accept by residual:

      union     = connected (after 1-dilate) group of >=4 masks whose
                  neighbouring Lab colours sit within dE 20 (one ink family);
                  pastel diagram panels are separate islands and never form
                  one connected union (nested-106 stays safe);
      model     = L(x,y) = a + b*x + c*y per Lab channel (lstsq over union
                  pixels of the ORIGINAL reference);
      accept    = p90 |Lab - model| <= 7.0 AND at least 25% better than the
                  flat per-band error (the stacks' acceptance philosophy).
    Emits ONE mask with a linear gradient fill (stops at the projected
    extremes)."""
    n = len(masks)
    if n < 4:
        return masks, {}
    lab_img = cv2.cvtColor(reference_rgb.astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    colors_lab = []
    for m in masks:
        ys, xs = np.nonzero(m)
        colors_lab.append(np.median(lab_img[ys, xs], axis=0) if len(ys) else np.zeros(3, np.float32))
    kernel = np.ones((3, 3), np.uint8)
    # adjacency graph limited to close-colour pairs (one ink family)
    dil = [cv2.dilate(m.astype(np.uint8), kernel) for m in masks]
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if float(np.linalg.norm(colors_lab[i] - colors_lab[j])) > 20.0:
                continue
            if int(np.sum(dil[i] & masks[j].astype(np.uint8))) >= 8:
                parent[find(j)] = find(i)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    fills: dict[int, tuple] = {}
    out_masks = list(masks)
    consumed: set[int] = set()
    for root, members in groups.items():
        if len(members) < 4:
            continue
        union = np.zeros_like(masks[0], bool)
        for k in members:
            union |= masks[k].astype(bool)
        ys, xs = np.nonzero(union)
        if len(ys) < 200:
            continue
        pix = lab_img[ys, xs]
        A = np.column_stack((np.ones_like(xs, np.float32), xs.astype(np.float32), ys.astype(np.float32)))
        coef, *_ = np.linalg.lstsq(A, pix, rcond=None)
        rec = A @ coef
        resid = np.linalg.norm(pix - rec, axis=1)
        p90 = float(np.percentile(resid, 90))
        flat_err = 0.0
        for k in members:
            mys, mxs = np.nonzero(masks[k])
            flat_err += float(np.sum(np.linalg.norm(lab_img[mys, mxs] - colors_lab[k], axis=1)))
        flat_err /= max(1, len(ys))
        mean_err = float(np.mean(resid))
        if p90 > 7.0 or mean_err > 0.75 * flat_err:
            continue
        # gradient direction = colour-change gradient of the fitted field
        g = coef[1:, :]                       # (2,3): d/dx, d/dy per channel
        direction = np.array([float(np.linalg.norm(g[0])), float(np.linalg.norm(g[1]))])
        u = np.array([coef[1] @ coef[1], 0.0])
        # project pixels on the dominant direction in xy
        dvec = np.array([np.linalg.norm(coef[1]), np.linalg.norm(coef[2])], np.float32)
        if float(np.linalg.norm(dvec)) < 1e-6:
            continue
        dvec = dvec / float(np.linalg.norm(dvec))
        t = xs * dvec[0] + ys * dvec[1]
        lo, hi = float(t.min()), float(t.max())
        if hi - lo < 4.0:
            continue
        # stops: sample the FIELD at the extremes (convert Lab->RGB via the
        # original pixels nearest to each extreme)
        i_lo, i_hi = int(np.argmin(t)), int(np.argmax(t))
        rgb_lo = tuple(int(v) for v in reference_rgb[ys[i_lo], xs[i_lo]])
        rgb_hi = tuple(int(v) for v in reference_rgb[ys[i_hi], xs[i_hi]])
        inv = 1.0 / analysis_scale
        p0 = (float(xs[i_lo]) * inv, float(ys[i_lo]) * inv)
        p1 = (float(xs[i_hi]) * inv, float(ys[i_hi]) * inv)
        rep = members[0]
        out_masks[rep] = union
        fills[rep] = ("linear", p0, p1, [(0.0, rgb_lo), (1.0, rgb_hi)])
        consumed.update(members[1:])
    if consumed:
        out_masks = [m for i, m in enumerate(out_masks) if i not in consumed]
        # reindex fills after removal
        remap = {}
        j = 0
        for i in range(len(masks)):
            if i in consumed:
                continue
            remap[i] = j
            j += 1
        fills = {remap[i]: f for i, f in fills.items() if i in remap}
    return out_masks, fills


def _merge_gradient_stacks(masks: list[np.ndarray], reference_rgb: np.ndarray,
                           analysis_scale: int) -> tuple[list[np.ndarray], dict[int, tuple]]:
    """Audit P2 'gradients замест сотняў flat fragments': detect QUANTIZED
    GRADIENT stacks — chains of >=3 adjacent bands whose Lab colours form a
    monotone, direction-consistent ramp — and merge each into ONE mask with a
    linear or radial gradient fill.

    `reference_rgb` must be the ORIGINAL image resampled to the mask grid — the
    acceptance test compares against real pixels; against the anchor-quantized
    render the flat bands are exact by construction and nothing ever merges.

    Guards (each stack): chain topology (every interior band's two strongest
    same-chain neighbours are its chain neighbours), colour-step consistency
    (consecutive Lab steps within 45 deg of each other, magnitudes in [4, 60]
    OpenCV-Lab and within x2.5 of each other), and an ACCEPTANCE render test:
    the gradient must reproduce the ORIGINAL pixels at least as well as the
    flat bands did (mean Lab error <= flat * 1.2 + 2).  A flag's blue/white/red
    fails the direction test; two-tone designs fail the k>=3 requirement."""
    n = len(masks)
    if n < 3:
        return masks, {}
    lab_img = cv2.cvtColor(reference_rgb.astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    colors_lab = []
    colors_rgb = []
    centroids = []
    for m in masks:
        ys, xs = np.nonzero(m)
        colors_lab.append(np.median(lab_img[ys, xs], axis=0))
        colors_rgb.append(np.median(reference_rgb[ys, xs], axis=0))
        centroids.append(np.array([xs.mean(), ys.mean()]))
    kernel = np.ones((3, 3), np.uint8)
    contact = np.zeros((n, n), np.int64)
    dil = [cv2.dilate(m.astype(np.uint8), kernel) for m in masks]
    for i in range(n):
        for j in range(i + 1, n):
            c = int(np.sum(dil[i] & masks[j].astype(np.uint8)))
            contact[i, j] = contact[j, i] = c

    def step_ok(a: int, b: int) -> bool:
        d = colors_lab[b] - colors_lab[a]
        # cap 90 OpenCV-Lab: palette compaction can collapse a long ramp into a
        # few FAT bands with big steps; genuinely different inks (flag stripes)
        # sit far beyond (blue->white ~170)
        return 4.0 <= float(np.linalg.norm(d)) <= 90.0

    def steps_aligned(a: int, b: int, c: int) -> bool:
        d1 = colors_lab[b] - colors_lab[a]
        d2 = colors_lab[c] - colors_lab[b]
        n1, n2 = float(np.linalg.norm(d1)), float(np.linalg.norm(d2))
        if n1 < 1e-6 or n2 < 1e-6 or not (0.4 <= n1 / n2 <= 2.5):
            return False
        return float(d1 @ d2) / (n1 * n2) >= math.cos(math.radians(45.0))

    # graph of (adjacent AND gradient-step-sized) band pairs -> connected
    # components -> each ordered along the principal axis of its Lab colours
    min_contact = 8
    adjacency: dict[int, set[int]] = {}
    for i in range(n):
        for j in range(i + 1, n):
            if contact[i, j] >= min_contact and step_ok(i, j):
                adjacency.setdefault(i, set()).add(j)
                adjacency.setdefault(j, set()).add(i)
    chains: list[list[int]] = []
    seen: set[int] = set()
    for s in range(n):
        if s in seen or s not in adjacency:
            continue
        comp: list[int] = []
        stack = [s]
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            comp.append(v)
            stack.extend(adjacency.get(v, set()) - seen)
        if len(comp) < 3:
            continue
        cl = np.array([colors_lab[k] for k in comp], np.float32)
        _, _, vt = np.linalg.svd(cl - cl.mean(axis=0), full_matrices=False)
        order = np.argsort(cl @ vt[0])
        chain = [comp[o] for o in order]
        # The all()-gate stays deliberately strict.  A subchain-split variant
        # (maximal valid runs instead of whole-component pass/fail) was probed
        # 2026-07-14 and REVERTED: it bought only -16% kinks on ONE real ramp
        # (item068) while gluing three pastel diagram panels into a fake
        # gradient (nested_containers iou 0.797 -> 0.761) — exactly the class
        # this gate protects.  Real ramps drawn THROUGH logo shapes need a
        # form-aware gradient detector (field fit over the union, not band
        # chains) — queued in NEXT_STRIKES.
        if all(step_ok(chain[i], chain[i + 1]) for i in range(len(chain) - 1)) and \
           all(steps_aligned(chain[i], chain[i + 1], chain[i + 2]) for i in range(len(chain) - 2)):
            chains.append(chain)

    used: set[int] = set()
    fills: dict[int, tuple] = {}
    out_masks = list(masks)
    replaced: dict[int, int] = {}
    for chain in chains:
        if any(k in used for k in chain):
            continue
        # ---- fit linear AND radial models on band centroids, keep the better ----
        idxs = np.arange(len(chain), dtype=np.float32)
        cents = np.array([centroids[k] for k in chain], np.float32)
        v = cents[-1] - cents[0]
        vn = float(np.linalg.norm(v))
        union = np.zeros_like(masks[0], bool)
        for k in chain:
            union |= masks[k].astype(bool)
        ys, xs = np.nonzero(union)
        pix_lab = lab_img[ys, xs]
        flat_err = 0.0
        for k in chain:
            mys, mxs = np.nonzero(masks[k])
            flat_err += float(np.sum(np.linalg.norm(lab_img[mys, mxs] - colors_lab[k], axis=1)))
        flat_err /= max(1, len(ys))

        def model_error(t_pix: np.ndarray, t_bands: np.ndarray) -> float:
            order = np.argsort(t_bands)
            tb = t_bands[order]
            cl = np.array([colors_lab[chain[o]] for o in order], np.float32)
            rec = np.stack([np.interp(t_pix, tb, cl[:, ch]) for ch in range(3)], axis=1)
            return float(np.mean(np.linalg.norm(pix_lab - rec, axis=1)))

        best = None
        if vn > 2.0:
            u = v / vn
            t_pix = (np.stack([xs, ys], 1).astype(np.float32) - cents[0]) @ u
            t_bands = (cents - cents[0]) @ u
            err = model_error(t_pix, t_bands)
            lo, hi = float(t_pix.min()), float(t_pix.max())
            span = max(1e-6, hi - lo)
            stops = sorted((max(0.0, min(1.0, (float(tb) - lo) / span)),
                            tuple(int(c) for c in colors_rgb[chain[i]]))
                           for i, tb in enumerate(t_bands))
            p0 = (cents[0] + lo * u) / analysis_scale
            p1 = (cents[0] + hi * u) / analysis_scale
            best = (err, ("linear", tuple(np.round(p0, 2)), tuple(np.round(p1, 2)), stops))
        # radial: centre from the innermost band (smallest mean radius spread)
        centre = cents[0] if float(np.linalg.norm(cents[0] - cents.mean(0))) > float(np.linalg.norm(cents[-1] - cents.mean(0))) else cents[-1]
        r_bands = np.array([float(np.mean(np.hypot(*(np.nonzero(masks[k])[::-1] - centre[:, None])))) for k in chain], np.float32)
        if np.all(np.diff(np.sort(r_bands)) > 0.5):
            t_pix = np.hypot(xs - centre[0], ys - centre[1]).astype(np.float32)
            err = model_error(t_pix, r_bands)
            if best is None or err < best[0]:
                r0, r1 = float(r_bands.min()), float(r_bands.max())
                span = max(1e-6, r1 - r0)
                stops = sorted((max(0.0, min(1.0, (float(rb) - r0) / span)),
                                tuple(int(c) for c in colors_rgb[chain[i]]))
                               for i, rb in enumerate(r_bands))
                best = (err, ("radial", tuple(np.round(centre / analysis_scale, 2)),
                              r0 / analysis_scale, r1 / analysis_scale, stops))
        if _FIT_DEBUG[0]:
            print(f"    gradient chain {chain}: model={'none' if best is None else best[1][0]} "
                  f"err={None if best is None else round(best[0], 2)} flat={round(flat_err, 2)}")
        if best is None or best[0] > flat_err * 1.2 + 2.0:
            continue                                    # gradient does NOT explain the pixels
        keep = chain[0]
        out_masks[keep] = union
        fills[keep] = best[1]
        used.update(chain)
        for k in chain[1:]:
            replaced[k] = keep
    if not fills:
        return masks, {}
    final_masks: list[np.ndarray] = []
    final_fills: dict[int, tuple] = {}
    for i, m in enumerate(out_masks):
        if i in replaced:
            continue
        if i in fills:
            final_fills[len(final_masks)] = fills[i]
        final_masks.append(m)
    return final_masks, final_fills


def _detect_stroke(mask, analysis_scale):
    """Audit P2 'strokes замест вузкіх filled polygons': if the mask is a
    near-constant-width, non-branching ribbon, return (width_native, curves) of
    its stroked CENTERLINE (fit by the same Sec 5.1 machinery), else None.

    Guards: skeleton must have exactly 2 endpoints and no branch points; core
    width spread <= 20% of the median; length >= 2.5 widths.  ACCEPTANCE by
    rendering: the drawn round-cap stroke must reproduce the mask (IoU >= 0.88
    and boundary deviation <= max(1.5px, 18% of width)) — a fat square-butt
    rectangle or a tapering wedge fails and stays a filled region."""
    m8 = mask.astype(np.uint8)
    area = int(m8.sum())
    if area < 24:
        return None
    dist = cv2.distanceTransform(m8, cv2.DIST_L2, 5)
    # skimage.skeletonize, NOT cv2.ximgproc.thinning: cv2 5.0 thinning DOUBLES
    # the centerline of wide ribbons (two parallel lines joined at the ends — a
    # long flat cycle), which breaks both the open-path walk and the ring test.
    from skimage.morphology import skeletonize as _skeletonize
    skel = _skeletonize(mask.astype(bool))
    ys, xs = np.nonzero(skel)
    if len(ys) < 8:
        return None
    # The thinned skeleton carries short SPURS at caps/AA bumps, so naїve
    # endpoint/branch counting rejects every real stroke.  Take the LONGEST PATH
    # through the skeleton graph instead (double BFS from the farthest ends) and
    # require the off-path twig mass to be small.
    skel_set = {(int(y), int(x)) for y, x in zip(ys, xs)}

    # ---- CLOSED RING (annulus -> closed stroked path).  AA bumps leave short
    # spurs with endpoint pixels on an otherwise clean ring, so PRUNE endpoints
    # iteratively to ~w/2 depth first (cycle pixels always keep 2 neighbours and
    # survive; a spur base recovers once its twig is consumed).  If the pruned
    # skeleton has no endpoints left, walk the cycle and fit it closed.
    w_guess = 2.0 * float(np.median(dist[skel])) if int(skel.sum()) else 0.0
    pruned = skel.copy()
    for _ in range(int(w_guess / 2.0) + 2):
        nb_p = cv2.filter2D(pruned.astype(np.uint8), -1, np.ones((3, 3), np.uint8),
                            borderType=cv2.BORDER_CONSTANT) - pruned.astype(np.uint8)
        tips = pruned & (nb_p <= 1)
        if not bool(tips.any()):
            break
        pruned &= ~tips
    nb_p = cv2.filter2D(pruned.astype(np.uint8), -1, np.ones((3, 3), np.uint8),
                        borderType=cv2.BORDER_CONSTANT) - pruned.astype(np.uint8)
    pys, pxs = np.nonzero(pruned)
    if len(pys) >= 12 and not bool(np.any(pruned & (nb_p == 1))):
        skel_set = {(int(y), int(x)) for y, x in zip(pys, pxs)}
        ys, xs = pys, pxs
        start = (int(ys[0]), int(xs[0]))
        cycle = [start]
        seen_c = {start}
        while True:
            y, x = cycle[-1]
            nxt = [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                   if (dy or dx) and (y + dy, x + dx) in skel_set and (y + dy, x + dx) not in seen_c]
            if not nxt:
                break
            nxt.sort(key=lambda q: abs(q[0] - y) + abs(q[1] - x))
            cycle.append(nxt[0])
            seen_c.add(nxt[0])
        if len(cycle) >= max(12, 0.9 * len(skel_set)):
            radii_c = np.array([dist[y, x] for y, x in cycle], float)
            w_c = 2.0 * float(np.median(radii_c))
            if w_c >= 1.5 and float(np.std(2.0 * radii_c)) <= 0.20 * w_c:
                pts_c = np.array([(x + 0.5, y + 0.5) for y, x in cycle], float)
                ring_len = float(np.sum(np.linalg.norm(np.diff(pts_c, axis=0), axis=1)))
                if ring_len >= 3.0 * w_c:
                    dist_along = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(pts_c, axis=0), axis=1))))
                    count = max(12, int(round(float(dist_along[-1]) / 2.0)))
                    target = np.linspace(0.0, float(dist_along[-1]), count, endpoint=False)
                    pts_c = np.column_stack([np.interp(target, dist_along, pts_c[:, k]) for k in range(2)])
                    win = int(np.clip(int(w_c / 4.0) * 2 + 1, 5, 41))
                    if len(pts_c) > 2 * win:
                        kernel = np.ones(win) / win
                        pad = np.vstack((pts_c[-win:], pts_c, pts_c[:win]))
                        sm = np.column_stack([np.convolve(pad[:, k], kernel, mode="same") for k in range(2)])
                        pts_c = sm[win:-win]
                    fl = fit_loop_paper(pts_c, 32.0 / max(16.0, (float(np.ptp(pts_c[:, 0])) + float(np.ptp(pts_c[:, 1]))) / 2),
                                        corner_positions=np.empty((0, 2)), px=1.0)
                    curves_c = list(fl.curves)
                    if curves_c:
                        canvas = Image.new("1", (mask.shape[1], mask.shape[0]), 0)
                        draw = ImageDraw.Draw(canvas)
                        chain = np.vstack([eval_curve(c, 24) for c in curves_c])
                        draw.line([tuple(q) for q in np.vstack((chain, chain[:1]))],
                                  fill=1, width=max(1, int(round(w_c))), joint="curve")
                        rendered = np.asarray(canvas, bool)
                        m_bool = mask.astype(bool)
                        union = int(np.sum(rendered | m_bool))
                        if union and float(np.sum(rendered & m_bool)) / union >= 0.88:
                            tol_c = max(1.5, 0.18 * w_c)
                            over = rendered & ~m_bool
                            under = m_bool & ~rendered
                            ok = True
                            if over.any() and float(cv2.distanceTransform((~m_bool).astype(np.uint8), cv2.DIST_L2, 5)[over].max()) > tol_c:
                                ok = False
                            if ok and under.any() and float(cv2.distanceTransform((~rendered).astype(np.uint8), cv2.DIST_L2, 5)[under].max()) > tol_c:
                                ok = False
                            if ok:
                                inv = 1.0 / float(analysis_scale)
                                for c in curves_c:
                                    c.control = c.control * inv
                                return w_c * inv, curves_c, True
    skel_set = {(int(y), int(x)) for y, x in zip(*np.nonzero(skel))}
    ys, xs = np.nonzero(skel)

    def bfs_farthest(start):
        from collections import deque
        parent = {start: None}
        queue = deque([start])
        last = start
        while queue:
            y, x = queue.popleft()
            last = (y, x)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if not (dy or dx):
                        continue
                    q = (y + dy, x + dx)
                    if q in skel_set and q not in parent:
                        parent[q] = (y, x)
                        queue.append(q)
        return last, parent

    seed = (int(ys[0]), int(xs[0]))
    end_a, _ = bfs_farthest(seed)
    end_b, parent = bfs_farthest(end_a)
    path = [end_b]
    while parent[path[-1]] is not None:
        path.append(parent[path[-1]])
    if len(path) < 8:
        return None
    # Branch test by DISTANCE, not by twig pixel count: cap fans and AA-bump
    # spurs always stay within ~w/2 of the main path, while a genuine side
    # branch (Y/T shape) runs beyond the ribbon's own width.
    off_path = np.array([q for q in skel_set if q not in set(path)], float)
    if len(off_path):
        from scipy.spatial import cKDTree
        path_arr = np.array(path, float)
        w_est = 2.0 * float(np.median([dist[y, x] for y, x in path]))
        if float(cKDTree(path_arr).query(off_path)[0].max()) > 0.7 * max(2.0, w_est):
            return None                               # genuinely branched shape
    radii = np.array([dist[y, x] for y, x in path], float)
    w = 2.0 * float(np.median(radii))
    if w < 1.5:
        return None
    # TRIM the path ends to the true centerline: the double-BFS endpoints are
    # the farthest skeleton pixels, i.e. CAP-FAN TIPS whose clearance is far
    # below w/2 — a cap circle drawn there pokes outside the mask.  The real
    # centerline end is where clearance reaches ~w/2.
    lo = 0
    while lo < len(path) - 1 and radii[lo] < 0.45 * w:
        lo += 1
    hi = len(path) - 1
    while hi > lo and radii[hi] < 0.45 * w:
        hi -= 1
    if hi - lo < 6:
        return None
    path = path[lo:hi + 1]
    widths = 2.0 * radii[lo:hi + 1]
    if float(np.std(widths)) > 0.20 * w or float(widths.max() - widths.min()) > max(2.0, 0.45 * w):
        return None                                   # tapering wedge / variable width
    pts = np.array([(x + 0.5, y + 0.5) for y, x in path], float)
    length = float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
    if length < 2.5 * w:
        return None
    # The skeleton is NOT a raster boundary: thinning zigzags +-1.5px with no
    # crack statistics, so resample at ~2px and lightly smooth before the fit —
    # the end-to-end acceptance below still guards fidelity against the mask.
    dist_along = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))))
    count = max(8, int(round(float(dist_along[-1]) / 2.0)) + 1)
    target = np.linspace(0.0, float(dist_along[-1]), count)
    pts = np.column_stack([np.interp(target, dist_along, pts[:, k]) for k in range(2)])
    # Smoothing window scales with the WIDTH: thinning wanders ~+-1.5px and its
    # low-frequency bow survives a short window, bowing the fitted centerline.
    # A constant-width ribbon's centerline is smooth by nature, and stroke
    # joins render rounded anyway (stroke-linejoin=round).
    win = int(np.clip(int(w / 4.0) * 2 + 1, 5, 41))
    if len(pts) > win + 2:
        kernel = np.ones(win) / win
        smooth = pts.copy()
        half_w = win // 2
        for k in range(2):
            smooth[half_w:-half_w, k] = np.convolve(pts[:, k], kernel, mode="valid")
        pts = smooth
    curves = fit_segment_midpoints(
        pts, 32.0 / max(16.0, (float(np.ptp(pts[:, 0])) + float(np.ptp(pts[:, 1]))) / 2),
        px=1.0, snap_ends=False)
    if not curves:
        return None
    canvas = Image.new("1", (mask.shape[1], mask.shape[0]), 0)
    draw = ImageDraw.Draw(canvas)
    chain = np.vstack([eval_curve(c, 24) for c in curves])
    w_i = max(1, int(round(w)))
    draw.line([tuple(q) for q in chain], fill=1, width=w_i, joint="curve")
    r = w / 2.0
    for cap in (chain[0], chain[-1]):
        draw.ellipse([cap[0] - r, cap[1] - r, cap[0] + r, cap[1] + r], fill=1)
    rendered = np.asarray(canvas, bool)
    m_bool = mask.astype(bool)
    union = int(np.sum(rendered | m_bool))
    if union == 0 or float(np.sum(rendered & m_bool)) / union < 0.88:
        return None
    tol = max(1.5, 0.18 * w)
    overshoot = rendered & ~m_bool
    undershoot = m_bool & ~rendered
    if overshoot.any():
        if float(cv2.distanceTransform((~m_bool).astype(np.uint8), cv2.DIST_L2, 5)[overshoot].max()) > tol:
            return None
    if undershoot.any():
        if float(cv2.distanceTransform((~rendered).astype(np.uint8), cv2.DIST_L2, 5)[undershoot].max()) > tol:
            return None
    inv = 1.0 / float(analysis_scale)
    # Sub-pixel de-bias (105 XOR-diff lesson: the skeleton lives on the
    # integer 4x grid, so the stroked centerline sits ~half a grid-cell off
    # the AA mass centre and the whole line pays iou in shifted slivers).
    # One rigid shift of the chain onto the mask's dt-weighted centroid.
    mys, mxs = np.nonzero(mask)
    wts = dist[mys, mxs]
    mask_c = np.array([float(np.average(mxs, weights=wts)),
                       float(np.average(mys, weights=wts))])
    drawn_pts = np.vstack([eval_curve(c, 12) for c in curves])
    shift = mask_c - drawn_pts.mean(axis=0)
    if float(np.hypot(*shift)) <= 1.5:
        for c in curves:
            c.control = c.control + shift
    for c in curves:
        c.control = c.control * inv
    return w * inv, curves, False


def _complete_occlusions(masks: list[np.ndarray], analysis_scale: int,
                         rgb: np.ndarray) -> dict[int, tuple]:
    """Audit P2 'occlusion/layer completion' for the paper modes: a region whose
    completion to a SIMPLE TEMPLATE (axis-aligned rectangle or ellipse) hides
    entirely behind the other masks is recovered as the full template, drawn
    UNDER its occluders (the classic base-behind-overlay logo layering).

    Acceptance per mask: (1) the hidden part is non-trivial (>=2% of the
    template) yet fully covered by other masks (uncovered <= max(8px, 0.5%));
    (2) every VISIBLE boundary pixel (not adjacent to another mask) lies within
    1.5px of the template outline — an L-shape next to a square does not
    'complete' to its bbox.  Returns {mask_index: ("rect", x0, y0, x1, y1) |
    ("ellipse", cx, cy, ax, ay, angle_deg)} in ANALYSIS coordinates.

    A base is often SPLIT by its overlay into several visible pieces (the IKEA
    ellipse cuts the blue field into strips), so SAME-COLOUR mask groups are
    tried as one union candidate too; every returned spec carries the member
    index tuple — all members collapse into the one completed region."""
    n = len(masks)
    if n < 2:
        return {}
    total = np.zeros_like(masks[0], bool)
    for m in masks:
        total |= m.astype(bool)
    kernel = np.ones((3, 3), np.uint8)
    lab_full = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    colors = [np.median(lab_full[np.nonzero(m)], axis=0) for m in masks]

    # candidates: singles + same-colour groups (pairwise dLab <= 12, area >= 40).
    # A group member must expose FREE boundary of its own (not be enclosed by
    # other masks): the letters of a logo share the base's colour but are fully
    # surrounded by the overlay — grouping them in would collapse them into the
    # completed base and they would vanish under the occluder.
    def _free_boundary_px(idx: int) -> int:
        mb0 = masks[idx].astype(bool)
        others0 = total & ~mb0
        bnd0 = mb0 & ~(cv2.erode(mb0.astype(np.uint8), kernel) > 0)
        near0 = cv2.dilate(others0.astype(np.uint8), kernel, iterations=2) > 0
        return int(np.sum(bnd0 & ~near0))

    candidates: list[tuple[int, ...]] = [(i,) for i in range(n)]
    big = [i for i in range(n) if int(masks[i].sum()) >= 40 and _free_boundary_px(i) >= 4]
    grouped: list[list[int]] = []
    used_g: set[int] = set()
    for i in big:
        if i in used_g:
            continue
        group = [i]
        used_g.add(i)
        for j in big:
            if j in used_g:
                continue
            if float(np.linalg.norm(colors[i] - colors[j])) <= 12.0:
                group.append(j)
                used_g.add(j)
        if len(group) >= 2:
            grouped.append(group)
    candidates += [tuple(sorted(g)) for g in grouped]

    out: dict[int, tuple] = {}
    claimed: set[int] = set()
    # groups FIRST (a whole base beats per-strip bboxes), then singles
    for members in sorted(candidates, key=lambda t: -len(t)):
        if any(k in claimed for k in members):
            continue
        mb = np.zeros_like(masks[0], bool)
        for k in members:
            mb |= masks[k].astype(bool)
        others = total & ~mb
        if not others.any():
            continue
        area_m = int(mb.sum())
        if area_m < 40:
            continue
        boundary = mb & ~(cv2.erode(mb.astype(np.uint8), kernel) > 0)
        near_others = cv2.dilate(others.astype(np.uint8), kernel, iterations=2) > 0
        free_boundary = boundary & ~near_others

        def accept(template: np.ndarray) -> bool:
            tb = template.astype(bool)
            if int(np.sum(mb & ~tb)) > max(4, 0.003 * area_m):
                return False                     # template must contain the piece
            hidden = tb & ~mb
            h = int(hidden.sum())
            if h < 0.02 * int(tb.sum()):
                return False                     # nothing meaningful to complete
            if int(np.sum(hidden & ~others)) > max(8, 0.005 * int(tb.sum())):
                return False                     # completion would be VISIBLE
            t_boundary = tb & ~(cv2.erode(tb.astype(np.uint8), kernel) > 0)
            if not free_boundary.any():
                return False                     # template outline never actually OBSERVED
            gap = cv2.distanceTransform((~t_boundary).astype(np.uint8), cv2.DIST_L2, 5)
            if float(gap[free_boundary].max()) > 1.5 * analysis_scale:
                return False                     # visible outline is NOT the template's
            # we must SEE a substantial part of the template outline, else the
            # completion is speculation (a letter enclosed in another colour
            # 'completes' to its bbox and silently becomes a layered rectangle)
            matched = int(np.sum(gap[free_boundary] <= 1.5 * analysis_scale))
            if matched < 0.4 * int(t_boundary.sum()):
                return False
            return True

        ys, xs = np.nonzero(mb)
        y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
        rect = np.zeros_like(mb)
        rect[y0:y1 + 1, x0:x1 + 1] = True
        if accept(rect):
            out[members[0]] = ("rect", x0, y0, x1, y1, members)
            claimed.update(members)
            continue
        contours, _ = cv2.findContours(mb.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if contours and len(max(contours, key=len)) >= 24:
            outer = max(contours, key=len).reshape(-1, 2).astype(np.float32)
            try:
                (ecx, ecy), (dw, dh), angle = cv2.fitEllipseDirect(outer)
            except cv2.error:
                continue
            if dw < 4 or dh < 4 or dw > 2.5 * mb.shape[1] or dh > 2.5 * mb.shape[0]:
                continue
            ell = np.zeros(mb.shape, np.uint8)
            cv2.ellipse(ell, (int(round(ecx)), int(round(ecy))),
                        (int(round(dw / 2)), int(round(dh / 2))), angle, 0, 360, 1, -1)
            if accept(ell):
                out[members[0]] = ("ellipse", float(ecx), float(ecy), float(dw / 2), float(dh / 2), float(angle), members)
                claimed.update(members)
    return out


def complete_occluded_rectangles(
    masks: list[np.ndarray], rgb: np.ndarray, analysis_scale: int, size: tuple[int, int]
) -> tuple[list[Region], set[int]]:
    """Recover a base rectangle split into visible pieces by an overlay.

    This is the layer configuration used by many logos: a background rectangle
    exists behind an ellipse even when the visible colour has two components.
    """
    entries = []
    for index, mask in enumerate(masks):
        color = tuple(int(value) for value in np.median(rgb[mask], axis=0))
        entries.append((index, mask, color))
    groups: list[list[tuple[int, np.ndarray, tuple[int, int, int]]]] = []
    for entry in entries:
        for group in groups:
            if np.linalg.norm(np.asarray(entry[2], float) - np.asarray(group[0][2], float)) < 12:
                group.append(entry)
                break
        else:
            groups.append([entry])

    layers: list[Region] = []
    consumed: set[int] = set()
    h, w = masks[0].shape if masks else (0, 0)
    for group in groups:
        if len(group) < 2:
            continue
        union = np.zeros((h, w), dtype=bool)
        for _, mask, _ in group:
            union |= mask
        yy, xx = np.nonzero(union)
        if not len(xx):
            continue
        x0, x1, y0, y1 = int(xx.min()), int(xx.max()), int(yy.min()), int(yy.max())
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bw < size[0] * analysis_scale * 0.35 or bh < size[1] * analysis_scale * 0.35:
            continue
        border_support = (
            union[y0, x0 : x1 + 1].mean()
            + union[y1, x0 : x1 + 1].mean()
            + union[y0 : y1 + 1, x0].mean()
            + union[y0 : y1 + 1, x1].mean()
        ) / 4
        if border_support < 0.58:
            continue
        corners = np.array([[x0, y0], [x1 + 1, y0], [x1 + 1, y1 + 1], [x0, y1 + 1]], dtype=float) / analysis_scale
        curves = [Curve(1, np.vstack((corners[i], corners[(i + 1) % 4]))) for i in range(4)]
        loop = np.vstack((corners, corners[0]))
        layers.append(Region(group[0][2], bw * bh, [FittedLoop(loop, curves, "completed-rectangle")]))
        for index, mask, _ in group:
            my, mx = np.nonzero(mask)
            touches = np.any(mx == x0) or np.any(mx == x1) or np.any(my == y0) or np.any(my == y1)
            if touches and mask.sum() >= bw * bh * 0.03:
                consumed.add(index)
    return layers, consumed


# Contrast-sensitive Potts parameters, tuned in OpenCV-Lab units (L,a,b in 0..255).
# Verified safe on close-colour logos (Mastercard keeps all 5 inks): the data
# term + sharp inter-region edges prevent bleeding, while gentle gradient edges
# and AA speckle are absorbed.  Raising lambda cleans more but never merges
# genuinely distinct anchors here.
_ICM_LAMBDA = 45.0  # smoothness weight: ΔE a flip must beat across a same-colour edge
_ICM_SIGMA = 36.0   # edge scale: neighbour ΔE >> sigma is treated as a real boundary
_ICM_ITERS = 14


def _shift2(array: np.ndarray, dy: int, dx: int) -> np.ndarray:
    return np.roll(np.roll(array, dy, axis=0), dx, axis=1)


def _icm_labels(
    lab: np.ndarray,
    anchor_lab: np.ndarray,
    init_labels: np.ndarray,
    lam: float = _ICM_LAMBDA,
    sigma: float = _ICM_SIGMA,
    iters: int = _ICM_ITERS,
) -> np.ndarray:
    """Contrast-sensitive Potts labelling via checkerboard ICM.

    Minimises  E(L) = Σ_p ΔE(p, anchor_{L_p}) + λ Σ_{p~q} w_pq · [L_p ≠ L_q],
    with w_pq = exp(−‖lab_p − lab_q‖² / 2σ²).  The data term anchors genuinely
    dark/saturated marks; the pairwise term collapses weak-edge speckle and
    gradient fragments while leaving strong-edge thin features intact.  Updates
    run on a two-colour checkerboard, so each half is exact block coordinate
    descent and the energy does not increase.
    """
    height, width = init_labels.shape
    n = anchor_lab.shape[0]
    data = np.sqrt(np.sum((lab[..., None, :] - anchor_lab[None, None, :, :]) ** 2, axis=3)).astype(np.float32)
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    affinity = []
    for dy, dx in offsets:
        diff = lab - _shift2(lab, dy, dx)
        weight = np.exp(-np.sum(diff * diff, axis=2) / (2.0 * sigma * sigma)).astype(np.float32)
        if dy and dx:
            weight = weight * 0.7071  # keep the 8-neighbourhood roughly isotropic
        affinity.append(weight)
    labels = init_labels.astype(np.int16).copy()
    yy, xx = np.mgrid[0:height, 0:width]
    parity = ((yy + xx) & 1).astype(bool)
    for _ in range(iters):
        for turn in (False, True):
            agree = np.zeros((height, width, n), np.float32)
            for (dy, dx), weight in zip(offsets, affinity):
                shifted = _shift2(labels, dy, dx)
                for a in range(n):
                    agree[..., a] += weight * (shifted == a)
            choice = np.argmin(data - lam * agree, axis=2).astype(np.int16)
            active = parity if turn else ~parity
            labels = np.where(active, choice, labels)
    return labels


_MERGE_WEAK_DELTAE = 80.0  # OpenCV-Lab ΔE below which a shared edge is 'weak' (same ink family)
_MERGE_KEEP_FRAC = 0.006   # a region above this fraction of the analysis area is never absorbed
_MERGE_THIN = 1.5          # analysis-scale half-width below which a region is an AA / edge ribbon


def _merge_regions(
    labels: np.ndarray,
    anchor_lab: np.ndarray,
    minimum: int,
    scale: int,
    weak_de: float = _MERGE_WEAK_DELTAE,
) -> np.ndarray:
    """Contrast-aware region-adjacency merge (perceptual region simplification).

    Absorbs the long tail of small fragments into their strongest-contact
    neighbour when the fragment is a thin AA/edge ribbon or the shared edge is
    weak (similar colour).  The discriminator is thickness, not area: a compact,
    high-contrast small mark — a dot, an eye, a letter stroke — is neither thin
    nor weak-edged, so it is preserved.  Runs after ICM and only ever recolours
    small fragments, never the large shapes.
    """
    from collections import defaultdict

    height, width = labels.shape
    anchors = anchor_lab.shape[0]
    min_keep = max(minimum * 8, int(height * width * _MERGE_KEEP_FRAC))
    # _MERGE_THIN is calibrated for 4x analysis; scale it so a native thin stroke
    # (thickness ~scale/2) is never treated as a sub-pixel AA ribbon.
    thin_thresh = _MERGE_THIN * scale / 4.0
    # A component only one pixel wide (thickness ~1) and of tiny area is aliasing —
    # a warm/cool tint the palette snapped to a saturated anchor along a hard edge
    # (e.g. red slivers riding the top of black text).  Genuine thin marks are
    # >=~2px thick (thickness >1.2) or long (larger area), so they are exempt.
    sliver_thick = 1.2 * max(1.0, scale / 4.0)
    sliver_area = max(minimum * 4, int(round(30 * scale * scale)))

    # 1) Give every connected component a unique id, plus its area and thickness
    #    (max distance-to-boundary — how far from an AA ribbon it is).
    rid = np.full((height, width), -1, np.int32)
    areas: list[int] = []
    region_anchor: list[int] = []
    thickness: list[float] = []
    touches_border: list[bool] = []
    count = 0
    for anchor_index in range(anchors):
        mask = (labels == anchor_index).astype(np.uint8)
        num, comp, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        distance = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
        for component in range(1, num):
            selection = comp == component
            rid[selection] = count
            areas.append(int(stats[component, cv2.CC_STAT_AREA]))
            region_anchor.append(anchor_index)
            thickness.append(float(distance[selection].max()))
            x0, y0 = int(stats[component, cv2.CC_STAT_LEFT]), int(stats[component, cv2.CC_STAT_TOP])
            w0, h0 = int(stats[component, cv2.CC_STAT_WIDTH]), int(stats[component, cv2.CC_STAT_HEIGHT])
            touches_border.append(x0 == 0 or y0 == 0 or x0 + w0 == width or y0 + h0 == height)
            count += 1
    if count <= 1:
        return labels
    area = np.asarray(areas, np.int64)
    region_anchor_arr = np.asarray(region_anchor)
    thin = np.asarray(thickness, np.float32)

    # 2) Shared-boundary counts between adjacent regions (4-neighbour).
    adjacency: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for dy, dx in ((0, 1), (1, 0)):
        shifted = np.roll(np.roll(rid, -dy, 0), -dx, 1)
        valid = np.ones((height, width), bool)
        if dy:
            valid[-1, :] = False
        else:
            valid[:, -1] = False
        edge = (rid != shifted) & (rid >= 0) & (shifted >= 0) & valid
        lo = np.minimum(rid[edge], shifted[edge])
        hi = np.maximum(rid[edge], shifted[edge])
        key = lo.astype(np.int64) * count + hi
        uniq, freq = np.unique(key, return_counts=True)
        for k, f in zip(uniq, freq):
            i, j = int(k // count), int(k % count)
            adjacency[i][j] += int(f)
            adjacency[j][i] += int(f)

    # 3) Absorb small fragments into their best neighbour, smallest first.
    parent = list(range(count))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for region in np.argsort(area):
        region = int(region)
        if find(region) != region or area[region] >= min_keep:
            continue
        contacts: dict[int, int] = defaultdict(int)
        for neighbour, shared in adjacency[region].items():
            other = find(neighbour)
            if other != region:
                contacts[other] += shared
        if not contacts:
            continue
        best = max(contacts, key=contacts.get)
        delta = float(np.linalg.norm(anchor_lab[region_anchor_arr[region]] - anchor_lab[region_anchor_arr[best]]))
        # A fully ENCLOSED strong-contrast island is a perceptual counter (the
        # hole of an 'A', a pupil): signal, never aliasing.  Slivers ride an
        # edge BETWEEN >=2 regions (or hug the image border); a counter has
        # exactly one neighbour.  At native scale a 2x2 counter is otherwise
        # indistinguishable from a sliver by thickness alone.
        if len(contacts) == 1 and not touches_border[region] and delta >= weak_de and area[region] >= 2:
            continue
        is_sliver = thin[region] <= sliver_thick and area[region] <= sliver_area
        # Absorb a 1px aliasing sliver (any contrast), a thin AA/edge ribbon, or a
        # weak-colour-edge fragment; a compact high-contrast mark (eye, dot, letter
        # stroke) satisfies none of these and is kept.
        if is_sliver or thin[region] < thin_thresh or delta < weak_de:
            parent[region] = best
            area[best] += area[region]
            for neighbour, shared in adjacency[region].items():
                adjacency[best][neighbour] += shared
                adjacency[neighbour][best] += shared

    root_of = np.fromiter((find(i) for i in range(count)), dtype=np.int64, count=count)
    return region_anchor_arr[root_of][rid]


def _enclosed_counter(labels: np.ndarray, component_mask: np.ndarray, own: int,
                      anchor_lab: np.ndarray, min_delta: float = _MERGE_WEAK_DELTAE) -> bool:
    """True for a small island fully surrounded by ONE strong-contrast label.

    Such an island is a perceptual counter (letter hole, pupil) and must be kept
    regardless of area.  AA/JPEG slivers touch >=2 labels or the image border.
    """
    ys, xs = np.nonzero(component_mask)
    if not len(ys):
        return False
    h, w = labels.shape
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    if x0 == 0 or y0 == 0 or x1 == w - 1 or y1 == h - 1:
        return False
    window = (slice(y0 - 1, y1 + 2), slice(x0 - 1, x1 + 2))
    sub = component_mask[window].astype(np.uint8)
    ring = (cv2.dilate(sub, np.ones((3, 3), np.uint8)) > 0) & (sub == 0)
    neighbours = np.unique(labels[window][ring])
    neighbours = neighbours[neighbours != own]
    if len(neighbours) != 1:
        return False
    return float(np.linalg.norm(anchor_lab[own] - anchor_lab[int(neighbours[0])])) >= min_delta


def _flatten_white(image: Image.Image) -> Image.Image:
    """Composite transparency onto white BEFORE any colour analysis.

    ``convert("RGB")`` drops alpha without compositing, so a transparent PNG
    contributes whatever RGB lies under alpha=0 (often black) — poisoning the
    palette anchors and the background estimate.  White matches deblur_4x's own
    convention, keeping the deblur and native paths consistent."""
    has_alpha = image.mode in ("RGBA", "LA", "PA") or (
        image.mode == "P" and "transparency" in image.info)
    if not has_alpha:
        return image.convert("RGB")
    rgba = image.convert("RGBA")
    canvas = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    canvas.alpha_composite(rgba)
    return canvas.convert("RGB")


def _region_color(analysis_pixels: np.ndarray, quantized: np.ndarray,
                  mask: np.ndarray, scale: int) -> tuple[int, int, int]:
    """Final region colour re-estimated from the ANALYSIS raster (METHOD_ICE 3.8).

    Shipping the palette anchor as the fill inherits any palette-compaction hue
    drift.  Median over the eroded interior avoids AA-contaminated boundary
    pixels; when erosion empties (1-2px strokes and letter stems) fall back to
    the top-30% distance-transform ridge — never the full mask, whose median is
    boundary-dominated exactly on those thin regions."""
    m = mask.astype(np.uint8)
    radius = max(1, int(scale))
    interior = cv2.erode(m, np.ones((2 * radius + 1, 2 * radius + 1), np.uint8)) > 0
    if not interior.any():
        distance = cv2.distanceTransform(m, cv2.DIST_L2, 3)
        peak = float(distance.max())
        interior = (distance >= 0.7 * peak) if peak > 0 else (m > 0)
    # A tiny blob's ridge is a handful of blended pixels (JPEG ringing, AA soup):
    # the analysis-raster median there is WORSE than the palette anchor that was
    # chosen robustly over the whole family (ikea_jpeg counter: 0.9728 -> 0.437
    # tiny-detail when re-estimated).  Re-estimate only with real interior
    # support; long thin strokes clear the bar via their many ridge pixels.
    if analysis_pixels.shape[:2] != mask.shape or int(interior.sum()) < 12:
        return tuple(int(v) for v in np.median(quantized[mask], axis=0))
    return tuple(int(v) for v in np.median(analysis_pixels[interior], axis=0))


def extract_perceptual_masks(source: Image.Image, use_icm: bool = False, merge: bool = False, deblur: bool = True,
                             palette_thick_veto: bool = True) -> tuple[np.ndarray, list[np.ndarray], np.ndarray, tuple[int, int, int], float, int, np.ndarray]:
    """Segment continuous MiniNet output directly in perceptual Lab space.

    The geometry is never generated from a palette-snapped RGB image.  Palette
    colours are only region hypotheses, and connected components are retained
    at a much lower threshold so thin, high-contrast marks survive.

    Returns (rendered, masks, boundary, background_color, threshold, scale,
    analysis_pixels) — the last element is the continuous analysis raster the
    masks were cut from, for downstream colour re-estimation.
    """
    from subpixel_mininet import compact_palette, deblur_4x

    flat = _flatten_white(source)
    if deblur and max(source.size) <= 512:
        analysis = deblur_4x(source, snap_palette=False)
        scale = 4
    else:
        # Paper mode: fit on the HARD native raster (correct line/arc geometry).
        # Colour speckle is cleaned downstream by the sliver merge, not by blurring
        # the raster here (which would round the very edges we want hard).
        analysis = flat
        scale = 1
    pixels = np.asarray(analysis.convert("RGB"), dtype=np.uint8)
    anchors = compact_palette(flat, thick_core_veto=palette_thick_veto).clip(0, 255).astype(np.uint8)
    if not len(anchors):
        anchors = np.array([[255, 255, 255], [0, 0, 0]], dtype=np.uint8)

    lab = cv2.cvtColor(pixels, cv2.COLOR_RGB2LAB).astype(np.float32)
    anchor_lab = cv2.cvtColor(anchors.reshape(1, -1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    distance = np.sum((lab[..., None, :] - anchor_lab[None, None, :, :]) ** 2, axis=3)
    labels = np.argmin(distance, axis=2).astype(np.int16)
    border = np.concatenate((pixels[0], pixels[-1], pixels[:, 0], pixels[:, -1]), axis=0)
    border_color = np.median(border, axis=0).astype(np.uint8)
    border_lab = cv2.cvtColor(border_color.reshape(1, 1, 3), cv2.COLOR_RGB2LAB).reshape(3).astype(float)
    background_index = int(np.argmin(np.sum((anchor_lab - border_lab) ** 2, axis=1)))
    # Blind-pack lesson (hipercard: red badge cropped edge-to-edge -> red
    # declared 'background', DROPPED, white letters painted on white = EMPTY
    # output while VAI was near-perfect).  Dropping the border anchor is only
    # legal when the frame really is a uniform canvas; a mixed frame means the
    # artwork reaches the edges, and every anchor must be emitted (the frame
    # anchor becomes an ordinary bottom-layer region).
    border_lab_px = cv2.cvtColor(border.reshape(1, -1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(float)
    uniform_frac = float(np.mean(np.linalg.norm(border_lab_px - border_lab, axis=1) <= 18.0))
    if uniform_frac < 0.85:
        background_index = -1              # nothing is background: emit all anchors

    source_area = source.width * source.height
    minimum = max(4, int(source_area * scale * scale * 0.00006))

    if use_icm:
        # One global energy replaces the hand-tuned thin/tiny reassignment: the
        # contrast-sensitive Potts prior absorbs speckle and gradient fragments
        # while the data term keeps genuine high-contrast marks.
        labels = _icm_labels(lab, anchor_lab, labels)
    else:
        # Do not simply discard tiny colour components: their pixels then become
        # unowned holes in the vector output.  Reassign only thin/tiny components
        # to a touching, perceptually similar region.  High-contrast small marks
        # remain intact, including dots, narrow letters and genuine counters.
        anchor_cie = cv2.cvtColor(
            (anchors.reshape(1, -1, 3).astype(np.float32) / 255.0),
            cv2.COLOR_RGB2LAB,
        ).reshape(-1, 3)
        artifact_limit = max(8, minimum * 6, int(labels.size * 0.00018))
        clean_labels = labels.copy()
        neighbourhood = np.ones((3, 3), np.uint8)
        for anchor_index in range(len(anchors)):
            original_region = (labels == anchor_index).astype(np.uint8)
            count, component_labels, stats, _ = cv2.connectedComponentsWithStats(original_region, connectivity=8)
            for component in range(1, count):
                area = int(stats[component, cv2.CC_STAT_AREA])
                width = int(stats[component, cv2.CC_STAT_WIDTH])
                height = int(stats[component, cv2.CC_STAT_HEIGHT])
                component_mask = component_labels == component
                thickness = float(
                    cv2.distanceTransform(component_mask.astype(np.uint8), cv2.DIST_L2, 3).max()
                )
                has_extent = max(width, height) >= max(6, int(2.0 * scale))
                definitely_tiny = area < minimum and not has_extent

                ring = cv2.dilate(component_mask.astype(np.uint8), neighbourhood, iterations=1).astype(bool)
                ring &= ~component_mask
                adjacent = clean_labels[ring]
                adjacent = adjacent[adjacent != anchor_index]
                if not len(adjacent):
                    continue
                neighbours, contacts = np.unique(adjacent, return_counts=True)
                perceptual = np.linalg.norm(anchor_cie[neighbours] - anchor_cie[anchor_index], axis=1)
                # Require useful boundary contact, then prefer a close colour over
                # a coincidental one-pixel touch at a three-way junction.
                useful = contacts >= max(1, int(contacts.max() * 0.20))
                candidates = np.flatnonzero(useful)
                contact_ratio = contacts.astype(np.float32) / float(contacts.max())
                score = perceptual + 8.0 * (1.0 - contact_ratio)
                best = int(candidates[np.argmin(score[candidates])])
                nearest_label = int(neighbours[best])
                nearest_delta = float(perceptual[best])
                thin_similar_artifact = (
                    area < artifact_limit
                    and thickness < 1.5
                    and nearest_delta < 24.0
                )
                if definitely_tiny or thin_similar_artifact:
                    clean_labels[component_mask] = nearest_label

        labels = clean_labels
    if merge:
        labels = _merge_regions(labels, anchor_lab, minimum, scale)
    rendered = anchors[labels]
    masks: list[np.ndarray] = []
    for anchor_index in range(len(anchors)):
        if anchor_index == background_index:
            continue
        region = (labels == anchor_index).astype(np.uint8)
        count, component_labels, stats, _ = cv2.connectedComponentsWithStats(region, connectivity=8)
        for component in range(1, count):
            area = int(stats[component, cv2.CC_STAT_AREA])
            width = int(stats[component, cv2.CC_STAT_WIDTH])
            height = int(stats[component, cv2.CC_STAT_HEIGHT])
            # Preserve a long one-pixel mark even when its area is tiny; reject
            # only compact speckles that have neither area nor visual extent.
            # An enclosed strong-contrast island (letter counter, pupil) is kept
            # at ANY size: at native scale a real 2x2 counter fails every area
            # gate a JPEG speckle fails, but a speckle is never cleanly enclosed.
            has_extent = max(width, height) >= max(6, int(2.0 * scale))
            if area < minimum and not (area >= max(2, scale) and has_extent):
                component_mask = component_labels == component
                if not (area >= 2 and _enclosed_counter(labels, component_mask, anchor_index, anchor_lab)):
                    continue
                masks.append(component_mask)
                continue
            masks.append(component_labels == component)

    boundary = np.zeros(labels.shape, dtype=bool)
    kernel = np.ones((3, 3), np.uint8)
    for mask in masks:
        eroded = cv2.erode(mask.astype(np.uint8), kernel, iterations=1).astype(bool)
        boundary |= mask & ~eroded
    bg_color = anchors[background_index] if background_index >= 0 else border_color
    return rendered, masks, boundary, tuple(int(v) for v in bg_color), 0.0, scale, pixels


def _bleed_flags(masks: list[np.ndarray], analysis_scale: int = 1) -> list[bool]:
    """Which regions need the paint-order apron (METHOD_ICE 3.1).

    masks arrive in paint order (area-descending); region i bleeds iff some
    LATER-painted mask j>i touches it by 4-neighbour contact — the neighbour
    then paints over the 0.3px excess, and the AA hairline between abutting
    fills becomes unrepresentable.  Topmost and isolated regions stay crisp."""
    if len(masks) < 2:
        return [False] * len(masks)
    labels = np.full(masks[0].shape, -1, np.int32)
    for index, mask in enumerate(masks):
        labels[mask.astype(bool)] = index
    pairs: set[tuple[int, int]] = set()
    for a, b in ((labels[:, :-1], labels[:, 1:]), (labels[:-1, :], labels[1:, :])):
        touching = (a != b) & (a >= 0) & (b >= 0)
        if not touching.any():
            continue
        lo = np.minimum(a[touching], b[touching])
        hi = np.maximum(a[touching], b[touching])
        for key in np.unique(lo.astype(np.int64) * len(masks) + hi):
            pairs.add((int(key // len(masks)), int(key % len(masks))))
    flags = [False] * len(masks)
    for i, j in pairs:
        flags[min(i, j)] = True
    # Thin regions must not bleed: 0.3px of apron on a 2px letter stem is +15%
    # stroke weight (the Hyundai wordmark visibly fattened).  The hairline-seam
    # class the apron kills lives between THICK abutting fills anyway.
    for index, mask in enumerate(masks):
        if not flags[index]:
            continue
        m = mask.astype(np.uint8)
        if not m.any():
            flags[index] = False
            continue
        dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
        width_native = 2.0 * float(np.median(dist[m > 0])) / max(1.0, float(analysis_scale))
        if width_native < 2.5:
            flags[index] = False
    return flags


def _needs_shared_region_graph(masks: list[np.ndarray], analysis_scale: int) -> bool:
    """Whether §7 shared-interface fitting is materially useful for this image.

    A region graph is essential for IKEA's touching letters/badge and Mastercard's
    overlapping discs.  It is needless overhead for isolated wordmarks and stroke
    illustrations: there are no non-background seams to share, while graph fitting
    bypasses the stronger stroke and loop-level validators.  Require both an absolute
    and relative amount of direct 4-neighbour contact between different masks.
    """
    if len(masks) < 2:
        return False
    labels = np.full(masks[0].shape, -1, np.int32)
    for index, mask in enumerate(masks):
        labels[mask.astype(bool)] = index
    shared = 0
    boundary = 0
    for a, b in ((labels[:, :-1], labels[:, 1:]), (labels[:-1, :], labels[1:, :])):
        different = a != b
        shared += int(np.sum(different & (a >= 0) & (b >= 0)))
        boundary += int(np.sum(different & ((a >= 0) | (b >= 0))))
    native_shared = shared / max(1.0, float(analysis_scale))
    ratio = shared / max(1, boundary)
    # 2026-07-12 night A/B: lowering this gate to >=4 cracks flipped small noisy
    # wordmarks (icon_group_4_78/-22) into graph fitting and cost them 0.10-0.14
    # ink-IoU, while every measured seam win came from the paint-order APRON
    # (Region.bleed), not from wider graph routing.  The AA-hairline class is
    # solved at emission; the gate stays at the calibrated 16/0.08.
    return native_shared >= 16.0 and ratio >= 0.08


def _kink_energy(regions: list) -> float:
    """Tangent-break count per 100px of contour, one formula for both routes."""
    breaks, length = 0, 0.0
    for region in regions:
        for loop in region.loops:
            curves = loop.curves
            for c in curves:
                pts = eval_curve(c, 8)
                length += float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
            if len(curves) < 2:
                continue
            for i in range(len(curves)):
                a, b = curves[i], curves[(i + 1) % len(curves)]
                ta, tb = _tangent_out(a), _tangent_in(b)
                ang = float(np.degrees(np.arccos(np.clip(float(ta @ tb), -1.0, 1.0))))
                if 20.0 < ang < 150.0:
                    breaks += 1
    return 100.0 * breaks / max(1.0, length)


def _route_mae(output: Path, image: Image.Image) -> float:
    rendered = Image.open(output / "03_rebuilt_filled.png").convert("RGB")
    rendered = rendered.resize(image.size, Image.Resampling.LANCZOS)
    a = np.asarray(rendered, dtype=np.float32)
    b = np.asarray(_flatten_white(image).convert("RGB"), dtype=np.float32)
    return float(np.mean(np.abs(a - b)))


def _route_boundary_f(output: Path, image: Image.Image, tolerance_px: float = 1.5) -> float:
    """Boundary-F between the run's render and the source (same construction
    as benchmark_vai.boundary_meters, local copy — bv imports gv, not vice
    versa).  The GEOMETRIC judge for the route arbiter: mae punishes a
    different shade split even when every boundary is right (exactly what
    froze the honest native wins on 075/079)."""
    rendered = Image.open(output / "03_rebuilt_filled.png").convert("RGB")
    rendered = rendered.resize(image.size, Image.Resampling.LANCZOS)
    def edge_mask(img: np.ndarray) -> np.ndarray:
        gray = np.mean(img, axis=2).astype(np.float32)
        gx = cv2.Scharr(gray, cv2.CV_32F, 1, 0)
        gy = cv2.Scharr(gray, cv2.CV_32F, 0, 1)
        mag = np.hypot(gx, gy)
        peak = float(mag.max())
        if peak < 1e-6:
            return np.zeros(gray.shape, bool)
        return mag >= 0.12 * peak
    e_ren = edge_mask(np.asarray(rendered, np.float32))
    e_src = edge_mask(np.asarray(_flatten_white(image).convert("RGB"), np.float32))
    if not e_src.any() or not e_ren.any():
        return 0.0
    dt_src = cv2.distanceTransform((~e_src).astype(np.uint8), cv2.DIST_L2, 3)
    dt_ren = cv2.distanceTransform((~e_ren).astype(np.uint8), cv2.DIST_L2, 3)
    precision = float(np.mean(dt_src[e_ren] <= tolerance_px))
    recall = float(np.mean(dt_ren[e_src] <= tolerance_px))
    return 2 * precision * recall / max(1e-9, precision + recall)


def process(image_path: Path, output_root: Path, extractor: str = "mininet", smoothing: str = "cad",
            route: str = "auto") -> dict:
    image = Image.open(image_path)
    analysis_scale = 1
    extractor_used = extractor
    _EVIDENCE_FIELD[0] = None      # never inherit a stale field from a prior call
    _FOREIGN_INK[0] = None
    _IMAGE_NOISE[0] = 0.0          # set only on the perceptual paper paths below
    perceptual = smoothing in {"perceptual", "perceptual-icm", "perceptual-merge", "paper", "paper-native", "paper-perc", "paper-perres", "paper-regions"}
    if perceptual:
        # paper-native = the CANONICAL Hoshyari reproduction: hard nearest-anchor
        # labels at native resolution, NO MiniNet deblur, NO ICM, NO merge — so
        # paper-reproduction regressions are attributable separately from the
        # production input hybrid (audit P1).
        use_icm = smoothing in {"perceptual-icm", "perceptual-merge", "paper", "paper-perc", "paper-perres", "paper-regions"}
        do_merge = smoothing in {"perceptual-merge", "paper", "paper-perc", "paper-perres", "paper-regions"}
        # Input routing for the paper modes (Sec 4-7), by NOISE CLASS of the raster:
        #  - JPEG: ringing/blocking survives palette snapping as 1-2px boundary
        #    ripple; MiniNet deblur (trained on clean rasterized art) AMPLIFIES it
        #    into wobbly boundaries.  Fit the hard NATIVE raster with a noise-matched
        #    interval (px=1.3) instead.
        #  - Lossless small art (<=512): clean AA gradients carry true subpixel edge
        #    positions and the 4x deblur RECOVERS them (crocodile scales, halftone
        #    stripes, 2px counters) — at native res a 1px real detail is geometrically
        #    indistinguishable from an aliasing sliver, so native LOSES detail there.
        #  - Lossless >512: native as always (deblur is gated to <=512 anyway).
        # paper-perc keeps the deblurred subpixel contour by design.
        native_raster = smoothing in {"paper", "paper-perres", "paper-regions"}
        # The route stays FORMAT-decided.  A content-measured switch to native
        # was probed 2026-07-14 and REVERTED: lacoste (re-encoded PNG, ringing
        # p90 6.44 — deep in the q30 class) needs the 4x deblur to keep its
        # 1-2px scales (native iou 0.9241 -> 0.8972, arcs collapsed to lines),
        # i.e. heavy noise does NOT imply native is safe — fine repeated detail
        # overrides.  What the measurement DOES drive is the tube slack below:
        # q30-class ringing (p90 >= 4.2) widens intervals so the DP may prefer
        # the smooth truth over chasing block ripple (blind kink tail).
        measured_noise = measure_image_noise(image)
        jpeg_input = ((getattr(image, "format", None) or "").upper() in {"JPEG", "MPO"}
                      or route == "native")
        force_native = smoothing == "paper-native"
        rgb, masks, boundary, bg, threshold, analysis_scale, analysis_pixels = extract_perceptual_masks(
            image, use_icm=use_icm, merge=do_merge,
            deblur=not (force_native or (native_raster and jpeg_input)),
            palette_thick_veto=measured_noise < 0.27)
        # Tube slack from measured q30-class ringing — DEBLUR PATH ONLY.  The
        # native path already absorbs ringing by design (fit_px stayed 1.0 for
        # JPEG precisely because LSQ + chunk-merge + the relative circle
        # tolerance handle the ripple — vai50 probe: full slack there cost
        # roundness 0.0156->0.0170 and wobble for zero kink gain).  The 4x
        # deblur path is where MiniNet AMPLIFIES ringing into geometry the
        # fitter chases (blind kink tail); 0.2px slack there fixed item043
        # kink 8.71->1.76 WITH the best iou, lacoste 0.9241->0.9341.
        if (native_raster or force_native) and analysis_scale == 4:
            _IMAGE_NOISE[0] = min(0.2, measured_noise)
        elif route == "native" and analysis_scale == 1:
            # explicit second-hypothesis run: the native route takes the full
            # measured slack (the whole point is out-smoothing q30 ripple)
            _IMAGE_NOISE[0] = measured_noise
        # METHOD_ICE 3.2: sub-pixel evidence for the DP intervals is probed from
        # the NATIVE raster (loops live in native px).  Reset-then-set per call —
        # legacy modes and exceptions can never inherit a stale field.
        #
        # SCOPE (night A/B, vai_ev_probe1-3): the field applies ONLY to the
        # NATIVE path (analysis_scale == 1: JPEG and >512px inputs).  Deblurred
        # 4x loops are ALREADY subpixel-positioned by MiniNet; re-centering them
        # on coverage probes is a systematic tug-of-war between two subpixel
        # estimates (betsoft wobble 0.013 -> 0.88, Hyundai 0.25 -> 7011) — and
        # +-2px pure-colour probes cross 2px stems entirely on small text.
        _EVIDENCE_FIELD[0] = None
        if _EVIDENCE_ENABLED and smoothing != "paper-native" and analysis_scale == 1:
            _EVIDENCE_FIELD[0] = _EvidenceField(
                np.asarray(_flatten_white(image), np.float32), strict=jpeg_input)
        if smoothing == "paper":
            extractor_used = "paper-hoshyari"
        elif smoothing == "paper-perc":
            extractor_used = "paper-hoshyari-perc"
        elif smoothing == "paper-native":
            extractor_used = "paper-hoshyari-native"
        elif smoothing == "paper-perres":
            extractor_used = "paper-hoshyari-perres"
        elif smoothing == "paper-regions":
            extractor_used = "paper-hoshyari-regions"
        else:
            extractor_used = "perceptual-lab-merge" if do_merge else ("perceptual-lab-icm" if use_icm else "perceptual-lab-soft")
    else:
        if extractor == "mininet" and max(image.size) <= 256:
            from subpixel_mininet import deblur_4x

            analysis = deblur_4x(image)
            analysis_scale = 4
        else:
            analysis = image
            if extractor == "mininet":
                extractor_used = "palette-large-fallback"
        rgb, masks, boundary, bg, threshold = extract_shape_masks(analysis)
    if perceptual:
        # extract_perceptual_masks already applied this exact area policy plus the
        # enclosed-counter rescue; re-filtering here would re-kill tiny counters.
        minimum_region = 2
    else:
        minimum_region = max(6 * analysis_scale * analysis_scale, int(image.width * image.height * analysis_scale**2 * 0.0005))
    masks = [mask for mask in masks if int(mask.sum()) >= minimum_region]
    masks = sorted(masks, key=lambda mask: int(mask.sum()), reverse=True)
    gradient_fills: dict[int, tuple] = {}
    if smoothing in {"paper", "paper-native", "paper-perc", "paper-perres", "paper-regions"} and masks:
        # audit P2: quantized-gradient stacks (banded shading) merge into ONE
        # region with a linear/radial gradient fill BEFORE any boundary is fit —
        # this collapses the mask explosion at its source.  The acceptance test
        # needs the ORIGINAL pixels (the quantized render is flat by construction).
        # Moved BEFORE the region-graph decision (isolated-map lesson, items
        # 068/059: gradient renders arrive as 99-135 tightly-touching bands,
        # _needs_shared_region_graph then fires and this merge never ran — the
        # whole ramp was fitted band-by-band, kinks 8.8-8.9/100px).  After the
        # merge the graph usually is not needed at all; if it still is, the
        # graph branch now carries the fills too.
        reference = np.asarray(image.convert("RGB").resize(
            (masks[0].shape[1], masks[0].shape[0]), Image.Resampling.BILINEAR), np.uint8)
        masks, gradient_fills = _merge_gradient_stacks(masks, reference, analysis_scale)
        if not gradient_fills:
            masks, gradient_fills = _merge_gradient_field(masks, reference, analysis_scale)
        # Router lane 1: the width-split mechanism fires ONLY on a diagram
        # signature (globally it tore the logo corpus: vai50 kinks 4.61 ->
        # 5.80, while the diagram crops it was built for improved — 105
        # polyline 0.84 -> 0.27 with node markers intact, 043 pad ring
        # restored, 111 +0.021 iou).
        diagram_lane = (not gradient_fills and smoothing == "paper-regions"
                        and _detect_diagram_signature(masks, analysis_scale))
        if diagram_lane:
            masks = _split_masks_by_width(masks, analysis_scale)
    region_graph_active = smoothing == "paper-regions" and _needs_shared_region_graph(masks, analysis_scale)
    paper_loop_mode = smoothing in {"paper", "paper-native", "paper-perc", "paper-perres"} or (
        smoothing == "paper-regions" and not region_graph_active)
    if smoothing == "paper-regions" and not region_graph_active:
        extractor_used = "paper-hoshyari-regions-isolated"
    # Perceptual masks already preserve shared boundaries and holes.  Replacing
    # them with a guessed hidden rectangle destroys white-on-colour artwork
    # (Peugeot/Pepsi/Colgate) and can merge separate letters (Mobil).
    if perceptual:
        base_layers, consumed = [], set()
    else:
        base_layers, consumed = complete_occluded_rectangles(masks, rgb, analysis_scale, image.size)
    regions: list[Region] = list(base_layers)
    completed_regions: list[Region] = []             # occlusion-completed bases, drawn UNDER all
    occlusion_completions: dict[int, tuple] = {}
    if paper_loop_mode and len(masks) >= 2:
        occlusion_completions = _complete_occlusions(masks, analysis_scale, rgb)
    occlusion_members: dict[int, int] = {}
    for rep, spec in occlusion_completions.items():
        for k in spec[-1]:
            occlusion_members[k] = rep
    corner_dots: list[np.ndarray] = []               # Sec-4 detected corners (paper mode), native px
    if region_graph_active:
        # Paper Sec 7: ONE region-boundary graph; every interface fitted once and SHARED by
        # its two regions (fit-once + junction rules + corner consensus) -> no seams.
        from region_graph import vectorize_region_graph, OUTSIDE
        label_map = np.full(masks[0].shape if masks else (1, 1), OUTSIDE, np.int32)
        for mask_index, mask in enumerate(masks):
            label_map[mask.astype(bool)] = mask_index
        # alpha is computed PER POLYLINE inside (paper's rs = the shape's raster
        # resolution, not the canvas size).  px stays 1.0 for JPEG too: the LSQ
        # line, chunk-merge and relative circle tolerance absorb ringing ripple; a
        # wider interval lets independently-fit neighbouring regions drift apart.
        lab_ref = cv2.cvtColor(np.asarray(analysis_pixels, np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
        label_lab = {}
        for mask_index, mask in enumerate(masks):
            mys, mxs = np.nonzero(mask)
            if len(mys):
                label_lab[mask_index] = np.median(lab_ref[mys, mxs], axis=0)
        loops_by_label, dots = vectorize_region_graph(label_map, analysis_scale, px=1.0,
                                                      label_lab=label_lab)
        corner_dots.extend(dots)
        bleed = _bleed_flags(masks, analysis_scale)
        for mask_index, mask in enumerate(masks):
            loops = loops_by_label.get(mask_index, [])
            if not loops:
                continue
            color = _region_color(analysis_pixels, rgb, mask, analysis_scale)
            # Graph-path stroke emission ships only inside the diagram lane
            # (without the split it re-creates the v1/v2 regressions).
            if diagram_lane:
                interior = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
                w_vals = interior[interior > 0.6]
                if len(w_vals) > 30:
                    med_w = float(np.median(w_vals))
                    p90_w = float(np.percentile(w_vals, 90))
                    if p90_w / max(med_w, 1e-6) <= 1.35 and (2.0 * med_w / analysis_scale) <= 4.5:
                        stroke_spec = _detect_stroke(mask, analysis_scale)
                        if stroke_spec is not None:
                            regions.append(Region(color, int(mask.sum()), [], stroke=stroke_spec))
                            continue
            regions.append(Region(color, int(mask.sum()), loops,
                                  fill=gradient_fills.get(mask_index), bleed=bleed[mask_index]))
        masks = []                                   # handled; skip the per-mask loop below

    mask_bleed = dict(enumerate(_bleed_flags(masks, analysis_scale))) if masks else {}
    for mask_index, mask in enumerate(masks):
        if mask_index in consumed:
            continue
        if paper_loop_mode and mask_index not in gradient_fills:
            if mask_index in occlusion_members:
                rep = occlusion_members[mask_index]
                if mask_index != rep:
                    continue                     # collapsed into the representative
                # audit P2: the region completes to a simple template hidden
                # behind its occluders — emit the EXACT template geometry and
                # draw it UNDER everything (front of the region list).
                spec = occlusion_completions[rep]
                group_mask = np.zeros_like(mask, bool)
                for k in spec[-1]:
                    group_mask |= masks[k].astype(bool)
                color = _region_color(analysis_pixels, rgb, group_mask, analysis_scale)
                inv_s = 1.0 / analysis_scale
                if spec[0] == "rect":
                    _, rx0, ry0, rx1, ry1, _members = spec
                    corners_t = np.array([[rx0, ry0], [rx1 + 1, ry0], [rx1 + 1, ry1 + 1], [rx0, ry1 + 1]], float) * inv_s
                    curves_t = [Curve(1, np.vstack((corners_t[k], corners_t[(k + 1) % 4]))) for k in range(4)]
                    template_name = "occlusion-rect"
                else:
                    _, ecx, ecy, ax_, ay_, ang, _members = spec
                    curves_t = _ellipse_curves(np.array([ecx, ecy]) * inv_s,
                                               np.array([ax_, ay_]) * inv_s, math.radians(ang))
                    template_name = "occlusion-ellipse"
                source_pts = np.vstack([eval_curve(c, 16) for c in curves_t])
                completed_regions.append(Region(color, int(group_mask.sum()),
                                                [FittedLoop(source_pts, curves_t, template_name)]))
                continue
            # audit P2: a constant-width ribbon becomes a stroked centerline —
            # 1-2 primitives instead of a filled outline with caps and sides
            stroke_spec = _detect_stroke(mask, analysis_scale)
            if stroke_spec is not None:
                color = _region_color(analysis_pixels, rgb, mask, analysis_scale)
                regions.append(Region(color, int(mask.sum()), [], stroke=stroke_spec))
                continue
            # Stage 2.2 (METHOD_ICE 3.5): coverage template league — at <=24px
            # the AA alpha map distinguishes circle/rrect/diamond far better
            # than the crack chain; a fitted analytic template replaces the
            # 'ellipse or pixel-chain' dichotomy.  Two hard gates inside.
            tiny_loop = _try_tiny_template(mask, analysis_pixels, rgb, analysis_scale, bg)
            if tiny_loop is not None:
                color = _region_color(analysis_pixels, rgb, mask, analysis_scale)
                regions.append(Region(color, int(mask.sum()), [tiny_loop],
                                      bleed=mask_bleed.get(mask_index, False)))
                continue
        distance = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
        interior = distance[distance > 0]
        stroke = 2.0 * float(np.percentile(interior, 72)) / analysis_scale if len(interior) else 1.0
        feature_scale = max(0.48, min(2.2, 0.18 * stroke))
        loops = []
        if paper_loop_mode:
            # Per loop: detect Sec4/Sec5 corners on a native-density SUBSAMPLE of the
            # loop itself (the classifier's training scale) but FIT the full-resolution
            # loop.  Subsampling the loop — never the mask — keeps every fine feature
            # (teeth, leg tips, the opening of a C) instead of filling it.
            if len(masks) > 1:
                foreign = np.zeros_like(mask, bool)
                for other_index, other in enumerate(masks):
                    if other_index != mask_index:
                        foreign |= other.astype(bool)
                if foreign.any():
                    dt_own = cv2.distanceTransform((~mask.astype(bool)).astype(np.uint8), cv2.DIST_L2, 3)
                    dt_others = cv2.distanceTransform((~foreign).astype(np.uint8), cv2.DIST_L2, 3)
                    _FOREIGN_INK[0] = (dt_own, dt_others, analysis_scale)
                else:
                    _FOREIGN_INK[0] = None
            raw_loops = [raw for raw in mask_loops(mask) if perimeter(raw) >= 4 * analysis_scale]
            # Paper Sec 5.1: alpha = 32/rs where rs is the SHAPE's raster resolution
            # (in the paper the image IS the shape).  Per-loop extent — not the canvas
            # size — keeps the D/R balance scale-invariant: with alpha tied to a big
            # canvas, a small logo's D-term vanishes and primitive types are chosen
            # by gate luck (lines<->arcs flips).  Removal already used per-loop alpha.
            # px: the interval is a NATIVE pixel (the 4x deblur is interpolation, so
            # its boundary is only accurate to ~0.5 native px).  It stays 1.0 for
            # JPEG-native input too — the LSQ line, the chunk-merge pass and the
            # relative circle tolerance absorb ringing ripple, while a wider interval
            # lets independently-fit neighbouring regions drift visibly apart.
            fit_px = 1.0
            det = "perres-paper" if smoothing == "paper-perres" else "cnn"
            for raw in raw_loops:
                full = raw / analysis_scale
                coarse = full[:: max(1, analysis_scale)]
                corners = paper_corner_positions(coarse, detector=det)   # corners on the RAW staircase
                if len(corners):
                    corner_dots.append(np.asarray(corners, float))
                fit_alpha = _PAPER_FIT_ALPHA_K / max(16.0, float(np.ptp(full[:, 0]) + np.ptp(full[:, 1])) / 2)
                fit_input, px_in = full, fit_px
                if smoothing == "paper-perc" and len(full) >= 12:
                    # EXPERIMENT "paper on the perceptual contour": fit the same lightly
                    # Taubin-smoothed subpixel curve the perceptual mode draws (detail kept,
                    # staircase noise gone), with a tighter interval since the smoothing
                    # already absorbed the raster quantization.  Corner DETECTION stays on
                    # the raw staircase above — the CNN is staircase-trained.
                    spacing = max(0.42, min(0.62, 0.48 * feature_scale))
                    fit_input = taubin_smooth_ring(resample_ring(full, spacing), passes=2)[:-1]
                    px_in = 0.6
                loops.append(fit_loop_paper(fit_input, fit_alpha, corner_positions=corners, px=px_in))
            _FOREIGN_INK[0] = None
        else:
            raw_loops = [raw for raw in mask_loops(mask) if perimeter(raw) >= 4 * analysis_scale]
            prefer_ellipse = len(raw_loops) == 2
            for raw in raw_loops:
                source = raw / analysis_scale
                # The old CAD pre-pass projected locally straight staircase pieces
                # before it knew the global shape.  On tiny o/B/C glyphs this could
                # move half a contour by several pixels.  The new fitter performs
                # scale-aware line decisions downstream, so CAD mode starts from
                # the unmodified subpixel boundary.
                if perceptual:
                    loops.append(fit_perceptual_loop(source, feature_scale))
                else:
                    regularized = source if smoothing in {"cad", "uncertainty"} else interpolate_ring(source, smoothing)
                    loops.append(
                        fit_loop(
                            regularized,
                            feature_scale,
                            prefer_ellipse=prefer_ellipse,
                            global_fit=smoothing == "uncertainty",
                        )
                    )
        if not loops:
            continue
        color = _region_color(analysis_pixels, rgb, mask, analysis_scale)
        regions.append(Region(color, int(mask.sum()), loops, fill=gradient_fills.get(mask_index),
                              bleed=mask_bleed.get(mask_index, False)))

    if completed_regions:
        regions = completed_regions + regions        # completed bases render first (bottom layer)
    if smoothing in {"paper", "paper-native", "paper-perc", "paper-perres", "paper-regions"}:
        # paper Sec 6 GLOBAL-scope regularities — and the audit's rule: regularization
        # must RE-PASS hard accuracy.  Snapshot每 loop, regularize, and revert any loop
        # the moved primitives pushed past the loop tolerance.
        snapshot = [[[Curve(c.degree, c.control.copy(), meta=getattr(c, "meta", None))
                      for c in lp.curves] for lp in region.loops] for region in regions]
        _regularize_regions_global(regions)
        for region, region_snap in zip(regions, snapshot):
            for lp, saved in zip(region.loops, region_snap):
                source = np.asarray(lp.source, float)
                if len(source) >= 3 and _loop_fit_deviation(source, lp.curves) > max(2.5, 3.0):
                    lp.curves = saved            # Sec 6 must never trade accuracy away
                # Graph welding may collapse a tiny connector to an exact point.
                # It carries no geometry but survives as a 0px SVG primitive and
                # pollutes editability/micro-fragment metrics.
                lp.curves = [curve for curve in lp.curves
                             if float(np.ptp(curve.control[:, 0]) + np.ptp(curve.control[:, 1])) > 1e-5]
    if _FONT_SNAP_ENABLED and smoothing in {"paper", "paper-perc", "paper-perres", "paper-regions"}:
        # Stage 2.6b: OCR -> font retrieval -> DOUBLE iron gate -> the winning
        # font's TRUE vector outlines replace the fitted letter regions as the
        # TOP painter's-stack layer (VAI forensics: letters redrawn on top).
        # Any exception or failed gate leaves the faithful fit untouched.
        subs_done: list[tuple] = []
        try:
            from text_substitution import try_substitute_lines
            for sub in try_substitute_lines(image, regions):
                bx0, by0, bx1, by1 = sub["bbox"]
                subs_done.append(sub["bbox"])
                ink = np.array(sub["ink"], float)
                kept: list[Region] = []
                for region in regions:
                    if region.fill is not None:
                        kept.append(region)
                        continue
                    if region.stroke is not None:
                        # letter bars often ship as stroked centerlines — they
                        # must vanish under the glyphs too, or they double-draw
                        _w, s_curves, _cl = region.stroke
                        pts = np.vstack([eval_curve(c, 8) for c in s_curves]) if s_curves else None
                    elif region.loops:
                        pts = np.vstack([lp.source for lp in region.loops if len(lp.source)])
                    else:
                        kept.append(region)
                        continue
                    if pts is None or not len(pts):
                        kept.append(region)
                        continue
                    inside = (pts[:, 0].min() >= bx0 - 1.5 and pts[:, 0].max() <= bx1 + 1.5
                              and pts[:, 1].min() >= by0 - 1.5 and pts[:, 1].max() <= by1 + 1.5)
                    same_ink = float(np.linalg.norm(np.asarray(region.color, float) - ink)) <= 60.0
                    if not (inside and same_ink):
                        kept.append(region)
                glyph_loops = []
                for curves in sub["loops"]:
                    drawn = np.vstack([eval_curve(c, 8) for c in curves])
                    glyph_loops.append(FittedLoop(drawn, curves, "font-snap"))
                area_est = max(1, int(0.35 * (bx1 - bx0) * (by1 - by0)))
                kept.append(Region(tuple(int(v) for v in sub["ink"]), area_est, glyph_loops))
                regions = kept
        except Exception:
            pass
        # Glyph consensus v1 was probed twice on 2026-07-14 and its CALL was
        # reverted: post-fit vertical snapping moved iou (-0.009..-0.012 on
        # 021/018) without touching kinks — they live in the letter CONTOURS,
        # not in inter-glyph jitter.  v2 must constrain the grid DURING the
        # fit (or add stem consensus); the function stays for that.  The
        # probe's lasting win is the 3x OCR fallback now feeding font-snap.
    output = output_root / image_path.stem
    output.mkdir(parents=True, exist_ok=True)
    write_svgs(output, regions, image.size)
    render_regions(regions, image.size, outline=True, scale=8).save(output / "01_contour.png")
    render_regions(regions, image.size, outline=True, scale=8).save(output / "02_primitive_map.png")
    render_regions(regions, image.size, outline=False, scale=8).save(output / "03_rebuilt_filled.png")
    if smoothing in {"paper", "paper-native", "paper-perc", "paper-perres", "paper-regions"}:
        # Where the Sec-4 detector (+ Sec-5 removal) placed corners.  Underlay: the
        # SOURCE raster upscaled NEAREST (pixel-crisp at any UI zoom — the honest
        # bitmap the fit consumed), lightened; overlay: the fitted contour drawn
        # directly in display coordinates (thin, no resampling blur) + blue dots.
        up = max(2, 1200 // max(image.size))
        base = image.convert("RGB").resize((image.size[0] * up, image.size[1] * up), Image.Resampling.NEAREST)
        corners_img = Image.blend(base, Image.new("RGB", base.size, (255, 255, 255)), 0.45)
        draw = ImageDraw.Draw(corners_img)
        for region in regions:
            for loop in region.loops:
                for curve in loop.curves:
                    pts = eval_curve(curve, 24) * up
                    draw.line([tuple(map(float, p)) for p in pts], fill=(40, 40, 40), width=1)
        radius = max(3, int(0.8 * up))
        for p in (np.vstack(corner_dots) if corner_dots else np.zeros((0, 2))):
            x, y = float(p[0]) * up, float(p[1]) * up
            draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                         fill=(0, 110, 230), outline=(255, 255, 255), width=1)
        corners_img.save(output / "04_corners.png")
    templates = {}
    degrees = {"L": 0, "Q": 0, "C": 0}
    for region in regions:
        if getattr(region, "stroke", None):
            templates["stroke"] = templates.get("stroke", 0) + 1
            for curve in region.stroke[1]:
                degrees[{1: "L", 2: "Q", 3: "C"}[curve.degree]] += 1
        for loop in region.loops:
            templates[loop.template] = templates.get(loop.template, 0) + 1
            for curve in loop.curves:
                degrees[{1: "L", 2: "Q", 3: "C"}[curve.degree]] += 1
    report = {
        "input": image_path.name,
        "pipeline": "geometry-first",
        "extractor_used": extractor_used,
        "analysis_scale": analysis_scale,
        "smoothing": smoothing,
        "regions": len(regions),
        "closed_contours": sum(len(region.loops) for region in regions),
        "rendered_primitive_count": sum(degrees.values()),
        "actual": degrees,
        "templates": templates,
        "threshold": threshold,
    }
    if smoothing in {"paper", "paper-native", "paper-perc", "paper-perres", "paper-regions"}:
        report["corner_detector"] = {
            "type": "resolution-density-hybrid-cnn",
            "small_model": "corner_cnn.pt",
            "small_threshold": _CNN_LAX_THRESHOLD,
            "large_model": _CNN_HYBRID_MODEL_PATH.name,
            "large_threshold": _CNN_HYBRID_THRESHOLD,
            "small_extent_max": _CNN_HYBRID_CUTOFF,
            "small_density_min": _CNN_HYBRID_MAX_DENSITY,
        }
    # Two-hypothesis route arbiter (research: multi-hypothesis + one judge,
    # image-level).  A priori 'large-form' features failed three times
    # (lacoste scales vs KA text are inseparable by thickness stats), so at
    # q30-class noise BOTH routes run and the EVIDENCE picks: the native
    # route must not pay accuracy (mae within +1.0 of the deblur run) and
    # must clearly win smoothness (kink energy down by >=1.5/100px).
    # Probes 2026-07-14: 075/079 flip native (kinks 6.7->2.9, 8.3->3.0),
    # lacoste/043 stay deblur (native mae there loses on vanished detail).
    if (route == "auto" and smoothing in {"paper", "paper-perres", "paper-regions"}
            and analysis_scale == 4 and measured_noise >= 0.27):
        shadow_dir = output_root / f"_route_native_{image_path.stem}"
        saved_noise = _IMAGE_NOISE[0]
        try:
            process(image_path, shadow_dir, extractor, smoothing, route="native")
            shadow_out = shadow_dir / image_path.stem
            mae_d = _route_mae(output, image)
            mae_n = _route_mae(shadow_out, image)
            bf_d = _route_boundary_f(output, image)
            bf_n = _route_boundary_f(shadow_out, image)
            kink_d = _kink_energy(regions)
            # shadow kinks: recomputed from its own report-independent render is
            # not possible here — reuse the same metric via its saved curves is
            # unavailable, so the shadow run stores it in its report.
            shadow_report = json.loads((shadow_out / "report.json").read_text(encoding="utf-8"))
            kink_n = float(shadow_report.get("kink_energy", 1e9))
            report["route_arbiter"] = {
                "mae_deblur": round(mae_d, 2), "mae_native": round(mae_n, 2),
                "bf_deblur": round(bf_d, 4), "bf_native": round(bf_n, 4),
                "kink_deblur": round(kink_d, 2), "kink_native": round(kink_n, 2),
            }
            # Judge switch (design D1, calibrated on the wave-B meter): the
            # GEOMETRIC boundary-F replaces mae — a different shade split no
            # longer vetoes an honest geometric win.  075-class calibration:
            # deblur F 0.982 vs native 0.950 stays deblur (the veto was
            # right); the mae guard is kept only as a coarse 3x-blowup fuse.
            if (bf_n >= bf_d - 0.005 and kink_n <= kink_d - 1.5
                    and mae_n <= mae_d * 3.0):
                for name in ("02_primitive_map.png", "02_primitive_map.svg",
                             "03_rebuilt_filled.png", "03_rebuilt_filled.svg",
                             "01_contour.png", "04_corners.png"):
                    src_f = shadow_out / name
                    if src_f.exists():
                        shutil.copy2(src_f, output / name)
                report["route_arbiter"]["winner"] = "native"
                report["extractor_used"] = shadow_report.get("extractor_used", report["extractor_used"])
                report["analysis_scale"] = 1
                report["rendered_primitive_count"] = shadow_report.get("rendered_primitive_count")
                report["actual"] = shadow_report.get("actual")
            else:
                report["route_arbiter"]["winner"] = "deblur"
        except Exception as exc:
            report["route_arbiter"] = {"error": f"{type(exc).__name__}: {exc}"[:120]}
        finally:
            _IMAGE_NOISE[0] = saved_noise   # the shadow run must not leak state
            shutil.rmtree(shadow_dir, ignore_errors=True)
    report["kink_energy"] = round(_kink_energy(regions), 3)
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report

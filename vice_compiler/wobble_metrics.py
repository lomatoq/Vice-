"""M5: fairness math - why a G1 curve can still look crooked (plan S4.1, M5).

Continuity is not fairness.  The current fitter guarantees C1/G1-like joins
and a bounded raster error, and the human court still preferred honest
pixels 13 times out of 23 on the single-custom-glyph route.  What the eye
punishes is curvature behaviour: ripple, unsupported inflections, bulges and
tangent reversals inside one span.

Everything here is measured on the ANALYTIC span, not on a re-rasterization,
and every deviation is expressed against the evidence corridor, so a span is
only "unfair" when the source does not support what it does.

Scale-invariant variation (plan M5.1):

    E = L^3 * integral (dk/ds)^2 ds
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .vector_program import (
    BiarcSpan,
    CircularArcSpan,
    CubicSpan,
    EllipticArcSpan,
    LineSpan,
    VectorSpan,
    arc_sweep,
)

#: Curvature noise floor: below this a sign flip is sampling noise, not an
#: inflection.  Expressed in 1/px and scaled by the span length in use.
CURVATURE_DEADZONE = 1.0e-3


@dataclass(frozen=True)
class SpanFairness:
    """Plan S4.1 span-level fairness features."""

    path_id: str
    span_index: int
    primitive_kind: str

    line_residual_px: float | None
    circle_residual_px: float | None

    max_normal_deviation_px: float
    p95_normal_deviation_px: float

    tangent_total_variation: float
    tangent_reversal_count: int

    curvature_sign_changes: int
    curvature_extrema_count: int
    inflection_count: int

    scale_invariant_curvature_variation: float
    corner_angle_drift_deg: float
    bulge_px: float

    supported_inflections: int = 0
    corridor_halfwidth_p50_px: float = 0.0
    hard_invalid: bool = False
    invalid_reasons: tuple[str, ...] = ()

    @property
    def soft_cost(self) -> float:
        """Lower is fairer; only compared among hard-valid candidates."""
        return float(
            self.scale_invariant_curvature_variation
            + 4.0 * max(0, self.curvature_sign_changes - self.supported_inflections)
            + 2.0 * self.tangent_reversal_count
            + 0.5 * self.bulge_px
        )


@dataclass(frozen=True)
class FairnessCertificate:
    """Plan S4.1 program-level fairness certificate."""

    valid: bool
    spans: tuple[SpanFairness, ...]
    exact_line_span_count: int
    exact_arc_span_count: int
    faithful_fallback_span_count: int
    unsupported_wobble_count: int

    @property
    def soft_cost(self) -> float:
        return float(sum(span.soft_cost for span in self.spans))


# --------------------------------------------------------------------------
# analytic span sampling
# --------------------------------------------------------------------------


def sample_span(
    span: VectorSpan, *, count: int = 64,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (points, first derivative, second derivative) samples."""
    t = np.linspace(0.0, 1.0, max(8, int(count)))
    if isinstance(span, LineSpan):
        p0 = np.asarray(span.p0, float)
        p1 = np.asarray(span.p1, float)
        points = p0[None, :] + t[:, None] * (p1 - p0)[None, :]
        d1 = np.tile(p1 - p0, (len(t), 1))
        d2 = np.zeros_like(d1)
        return points, d1, d2
    if isinstance(span, CircularArcSpan):
        start, delta = arc_sweep(span)
        angles = start + delta * t
        center = np.asarray(span.center, float)
        radius = float(span.radius)
        points = center[None, :] + radius * np.column_stack(
            (np.cos(angles), np.sin(angles)),
        )
        d1 = radius * delta * np.column_stack((-np.sin(angles), np.cos(angles)))
        d2 = radius * delta * delta * np.column_stack(
            (-np.cos(angles), -np.sin(angles)),
        )
        return points, d1, d2
    if isinstance(span, EllipticArcSpan):
        rotation = math.radians(span.angle_deg)
        cos_r, sin_r = math.cos(rotation), math.sin(rotation)
        center = np.asarray(span.center, float)

        def unit_angle(point) -> float:
            dx = point[0] - center[0]
            dy = point[1] - center[1]
            return math.atan2(
                (-dx * sin_r + dy * cos_r) / max(span.ry, 1e-12),
                (dx * cos_r + dy * sin_r) / max(span.rx, 1e-12),
            )

        start = unit_angle(span.p0)
        end = unit_angle(span.p1)
        delta = end - start
        if span.clockwise:
            while delta <= 0.0:
                delta += 2.0 * math.pi
        else:
            while delta >= 0.0:
                delta -= 2.0 * math.pi
        angles = start + delta * t
        ux = span.rx * np.cos(angles)
        uy = span.ry * np.sin(angles)
        points = np.column_stack((
            center[0] + ux * cos_r - uy * sin_r,
            center[1] + ux * sin_r + uy * cos_r,
        ))
        dux = -span.rx * np.sin(angles) * delta
        duy = span.ry * np.cos(angles) * delta
        d1 = np.column_stack((
            dux * cos_r - duy * sin_r, dux * sin_r + duy * cos_r,
        ))
        ddux = -span.rx * np.cos(angles) * delta * delta
        dduy = -span.ry * np.sin(angles) * delta * delta
        d2 = np.column_stack((
            ddux * cos_r - dduy * sin_r, ddux * sin_r + dduy * cos_r,
        ))
        return points, d1, d2
    if isinstance(span, CubicSpan):
        p0 = np.asarray(span.p0, float)
        c1 = np.asarray(span.c1, float)
        c2 = np.asarray(span.c2, float)
        p1 = np.asarray(span.p1, float)
        u = (1.0 - t)[:, None]
        tt = t[:, None]
        points = (
            u ** 3 * p0 + 3 * u ** 2 * tt * c1
            + 3 * u * tt ** 2 * c2 + tt ** 3 * p1
        )
        d1 = (
            3 * u ** 2 * (c1 - p0) + 6 * u * tt * (c2 - c1)
            + 3 * tt ** 2 * (p1 - c2)
        )
        d2 = 6 * u * (c2 - 2 * c1 + p0) + 6 * tt * (p1 - 2 * c2 + c1)
        return points, d1, d2
    if isinstance(span, BiarcSpan):
        first = sample_span(span.first, count=count // 2 + 1)
        second = sample_span(span.second, count=count // 2 + 1)
        return (
            np.vstack((first[0], second[0])),
            np.vstack((first[1], second[1])),
            np.vstack((first[2], second[2])),
        )
    raise ValueError(f"unknown span kind: {span!r}")


def curvature_profile(
    span: VectorSpan, *, count: int = 64,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (arclength weights, curvature, tangent angle) samples."""
    points, d1, d2 = sample_span(span, count=count)
    speed = np.maximum(np.linalg.norm(d1, axis=1), 1.0e-9)
    curvature = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / speed ** 3
    steps = np.linalg.norm(np.diff(points, axis=0), axis=1)
    weights = np.concatenate(([0.0], steps))
    angles = np.unwrap(np.arctan2(d1[:, 1], d1[:, 0]))
    return weights, curvature, angles


def robust_sign_changes(values: np.ndarray, *, deadzone: float) -> int:
    """Sign changes ignoring a noise deadzone around zero."""
    signs = np.zeros(len(values), dtype=int)
    signs[values > deadzone] = 1
    signs[values < -deadzone] = -1
    nonzero = signs[signs != 0]
    if len(nonzero) < 2:
        return 0
    return int(np.sum(nonzero[1:] != nonzero[:-1]))


def _observed_inflections(
    points: np.ndarray, *, deadzone_scale: float,
) -> int:
    """Curvature sign changes the SOURCE boundary itself exhibits."""
    if len(points) < 5:
        return 0
    d1 = np.gradient(points, axis=0)
    d2 = np.gradient(d1, axis=0)
    speed = np.maximum(np.linalg.norm(d1, axis=1), 1.0e-9)
    curvature = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / speed ** 3
    window = max(3, len(curvature) // 12)
    kernel = np.ones(window) / window
    smoothed = np.convolve(curvature, kernel, mode="same")
    return robust_sign_changes(
        smoothed, deadzone=max(CURVATURE_DEADZONE, deadzone_scale),
    )


def span_fairness(
    span: VectorSpan, *, path_id: str, span_index: int,
    observed_points: np.ndarray | None = None,
    observed_normals: np.ndarray | None = None,
    halfwidth_px: np.ndarray | None = None,
    line_residual_px: float | None = None,
    circle_residual_px: float | None = None,
    corner_angle_drift_deg: float = 0.0,
    samples: int = 64,
    precomputed_deviation: tuple[float, float, float, float] | None = None,
    supported_inflections: int | None = None,
) -> SpanFairness:
    """Measure one span against its evidence (plan S4.1, M5.2)."""
    weights, curvature, angles = curvature_profile(span, count=samples)
    length = float(np.sum(weights))
    ds = np.maximum(weights[1:], 1.0e-9)
    dcurvature = np.diff(curvature) / ds
    si_variation = float(
        max(length, 1.0e-9) ** 3 * np.sum(dcurvature ** 2 * ds),
    )
    deadzone = max(CURVATURE_DEADZONE, 0.02 / max(length, 1.0))
    sign_changes = robust_sign_changes(curvature, deadzone=deadzone)
    slope_signs = np.sign(np.diff(curvature))
    extrema = int(np.sum(
        (slope_signs[1:] != slope_signs[:-1]) & (slope_signs[1:] != 0),
    ))
    tangent_delta = np.diff(angles)
    tangent_variation = float(np.sum(np.abs(tangent_delta)))
    direction = np.sign(tangent_delta)
    nonzero = direction[np.abs(tangent_delta) > 1.0e-6]
    reversals = (
        int(np.sum(nonzero[1:] != nonzero[:-1])) if len(nonzero) > 1 else 0
    )

    max_deviation = 0.0
    p95_deviation = 0.0
    bulge = 0.0
    supported = 0
    halfwidth_p50 = 0.0
    if precomputed_deviation is not None:
        # The corridor check already measured the deviation against the
        # observation; recomputing it here was the DP's dominant cost.
        max_deviation, p95_deviation, bulge, halfwidth_p50 = (
            float(value) for value in precomputed_deviation
        )
    elif observed_points is not None and len(observed_points) >= 2:
        points, _d1, _d2 = sample_span(span, count=samples)
        # Normal-direction deviation of the curve from the observed boundary.
        deltas = points[:, None, :] - observed_points[None, :, :]
        distances = np.linalg.norm(deltas, axis=2)
        nearest = np.argmin(distances, axis=1)
        offsets = points - observed_points[nearest]
        if observed_normals is not None:
            deviation = np.abs(np.sum(
                offsets * observed_normals[nearest], axis=1,
            ))
        else:
            deviation = np.linalg.norm(offsets, axis=1)
        max_deviation = float(np.max(deviation))
        p95_deviation = float(np.percentile(deviation, 95))
        if halfwidth_px is not None:
            corridor = np.asarray(halfwidth_px, float)[nearest]
            halfwidth_p50 = float(np.median(corridor))
            bulge = float(np.max(np.maximum(deviation - corridor, 0.0)))
        supported = _observed_inflections(
            np.asarray(observed_points, float), deadzone_scale=deadzone,
        )
    if supported_inflections is not None:
        supported = int(supported_inflections)

    reasons: list[str] = []
    if reversals > 0:
        reasons.append("tangent-reversal-inside-span")
    if sign_changes > supported:
        reasons.append("unsupported-curvature-sign-change")
    if bulge > 1.0e-9:
        reasons.append("bulge-outside-evidence-corridor")
    if (
        isinstance(span, CubicSpan) and line_residual_px is not None
        and line_residual_px <= 0.12 and sign_changes > 0
    ):
        reasons.append("line-like-span-shipped-as-wavy-cubic")

    return SpanFairness(
        path_id=path_id, span_index=span_index, primitive_kind=span.kind,
        line_residual_px=line_residual_px,
        circle_residual_px=circle_residual_px,
        max_normal_deviation_px=max_deviation,
        p95_normal_deviation_px=p95_deviation,
        tangent_total_variation=tangent_variation,
        tangent_reversal_count=reversals,
        curvature_sign_changes=sign_changes,
        curvature_extrema_count=extrema,
        inflection_count=sign_changes,
        scale_invariant_curvature_variation=si_variation,
        corner_angle_drift_deg=float(corner_angle_drift_deg),
        bulge_px=bulge,
        supported_inflections=supported,
        corridor_halfwidth_p50_px=halfwidth_p50,
        hard_invalid=bool(reasons),
        invalid_reasons=tuple(reasons),
    )


def fairness_certificate(
    spans: list[SpanFairness], *, faithful_kinds: tuple[str, ...] = (),
) -> FairnessCertificate:
    exact_lines = sum(1 for span in spans if span.primitive_kind == "line")
    exact_arcs = sum(
        1 for span in spans
        if span.primitive_kind in ("circular_arc", "elliptic_arc", "biarc")
    )
    faithful = sum(
        1 for span in spans if span.path_id.endswith("faithful")
        or span.primitive_kind in faithful_kinds
    )
    unsupported = sum(1 for span in spans if span.hard_invalid)
    return FairnessCertificate(
        valid=unsupported == 0, spans=tuple(spans),
        exact_line_span_count=exact_lines, exact_arc_span_count=exact_arcs,
        faithful_fallback_span_count=faithful,
        unsupported_wobble_count=unsupported,
    )

def turning_density(program) -> float:
    """Absolute turning per unit arclength of the whole program (rad/px).

    Scale invariant and representation revealing.  A smooth ring spends
    2*pi over its full perimeter, so its density is low; a cell-edge
    staircase spends 2*pi on every few pixels of run, so its density is
    high - even though each individual run rectangle is convex and would
    look perfectly "fair" when measured per path.  This is the honest
    fairness cost of a FAITHFUL program: it is exact, but it is not fair,
    and the tie band must be able to say so (plan M5.3 preference order).
    """
    from .vector_program import flatten_path

    turning_total = 0.0
    length_total = 0.0
    for path in program.paths:
        points = flatten_path(path, samples=8)
        if len(points) < 4:
            continue
        array = np.asarray(points, float)
        deltas = np.diff(array, axis=0)
        lengths = np.linalg.norm(deltas, axis=1)
        keep = lengths > 1.0e-9
        deltas = deltas[keep]
        length_total += float(np.sum(lengths[keep]))
        if len(deltas) < 3:
            continue
        angles = np.arctan2(deltas[:, 1], deltas[:, 0])
        turning = np.diff(np.concatenate((angles, angles[:1])))
        turning = (turning + math.pi) % (2.0 * math.pi) - math.pi
        turning_total += float(np.sum(np.abs(turning)))
    if length_total <= 1.0e-9:
        return 0.0
    return turning_total / length_total

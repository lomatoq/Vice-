"""M4: the missing third candidate - exact primitives + fair curves.

Plan M4.  Today a TextLine is delivered either as honest pixel cells or as
one smoothed attempt whose only guarantee is "not too far from the mask".
The human court rejected both.  This module builds the candidate that was
missing:

    exact lines where the evidence proves straightness,
    exact arcs where it proves circularity,
    fair curves on genuinely smooth spans,
    faithful microspans exactly where the evidence is undecided.

The selection is a lexicographic dynamic program (plan M4.4), not a fragile
weighted sum: a candidate span must first pass the hard uncertainty
corridor, then it is ranked by unsupported inflections, then by how much
faithful fallback it needs, then by primitive code length, then by fairness,
and only last by render residual.  That ordering is what makes a straight
edge come out as ``L`` instead of an almost-straight cubic (plan M4.5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from shared_primitive_fitting import (
    cubic_control,
    multiscale_corner_indices,
    point_line_distance,
    polyline_tangents,
    unit,
)

from .coverage_evidence import BoundaryObservation
from .vector_program import (
    CircularArcSpan,
    ClosedPathProgram,
    CubicSpan,
    LineSpan,
    Point,
    TextVectorProgram,
    VectorPaintLayer,
    VectorSpan,
    point_in_polygon,
    seal_program,
    solid_paint_from_straight_rgba,
)
from .wobble_metrics import SpanFairness, fairness_certificate, span_fairness

FAIR_FAMILY = "fair-primitive-hybrid"

#: DP budget per ring (plan S10 materialization budget).
MAX_NODES_PER_RING = 36
MAX_SPAN_NODES = 14
#: A line/arc must cover at least this much arclength before it may claim
#: an exact primitive; below it the evidence cannot distinguish families.
MINIMUM_PRIMITIVE_LENGTH_PX = 2.5
MINIMUM_ARC_SWEEP_RAD = 0.25
#: The faithful fallback exists for SHORT undecided spans (plan M4.7); it is
#: never the way to cover a long boundary, and computing it everywhere was
#: the dominant DP cost.
MAX_FAITHFUL_NODES = 4


@dataclass(frozen=True)
class LexiScore:
    """Plan M4.4 candidate ordering, compared lexicographically."""

    topology_events: int = 0
    unsupported_inflections: int = 0
    faithful_fallbacks: int = 0
    primitive_code_bits: float = 0.0
    fairness: float = 0.0
    render_nll: float = 0.0

    def __add__(self, other: "LexiScore") -> "LexiScore":
        return LexiScore(
            self.topology_events + other.topology_events,
            self.unsupported_inflections + other.unsupported_inflections,
            self.faithful_fallbacks + other.faithful_fallbacks,
            self.primitive_code_bits + other.primitive_code_bits,
            self.fairness + other.fairness,
            self.render_nll + other.render_nll,
        )

    def key(self) -> tuple:
        return (
            self.topology_events, self.unsupported_inflections,
            self.faithful_fallbacks, round(self.primitive_code_bits, 6),
            round(self.fairness, 9), round(self.render_nll, 9),
        )

    @staticmethod
    def zero() -> "LexiScore":
        return LexiScore()


@dataclass(frozen=True)
class SpanProposal:
    spans: tuple[VectorSpan, ...]
    family: str
    score: LexiScore
    fairness: SpanFairness | None


# --------------------------------------------------------------------------
# M4.1 stable corners
# --------------------------------------------------------------------------


def stable_corner_indices(
    observation: BoundaryObservation, *, feature_scale: float | None = None,
) -> list[int]:
    """Corners that persist across two physical scales (plan M4.1).

    The input is the SUBPIXEL boundary, not the pixel-centre contour, so
    lattice ripple cannot mint a corner in the first place.
    """
    points = np.asarray(observation.points_xy, float)
    if len(points) < 12:
        return []
    spacing = max(
        float(np.median(np.linalg.norm(np.diff(points, axis=0), axis=1))),
        1.0e-6,
    )
    if feature_scale is None:
        # The corridor is the physical uncertainty of this boundary; a
        # corner must be sharper than the noise that produced it.
        feature_scale = max(1.0, 2.0 * float(np.median(observation.halfwidth_px)))
    return multiscale_corner_indices(
        points, feature_scale=feature_scale, spacing=spacing,
    )


def build_dp_nodes(
    observation: BoundaryObservation, corners: list[int],
) -> list[int]:
    """Corner nodes plus a bounded regular subdivision (plan M4.4)."""
    count = len(observation.points_xy)
    nodes = set(int(index) % count for index in corners)
    stride = max(1, int(math.ceil(count / max(1, MAX_NODES_PER_RING))))
    nodes.update(range(0, count, stride))
    ordered = sorted(nodes)
    return ordered or [0]


# --------------------------------------------------------------------------
# M4.3 hard uncertainty corridor
# --------------------------------------------------------------------------


def _span_samples(span: VectorSpan, count: int) -> np.ndarray:
    from .wobble_metrics import sample_span

    points, _d1, _d2 = sample_span(span, count=max(8, count))
    return points


@dataclass(frozen=True)
class CorridorCheck:
    feasible: bool
    residual: float
    max_deviation_px: float
    p95_deviation_px: float
    bulge_px: float
    halfwidth_p50_px: float


def _monotone_nearest(
    observed: np.ndarray, samples: np.ndarray, *, window: int = 6,
) -> np.ndarray:
    """Correspondence by monotone parameter with a small local search.

    Both sequences run along the same span in the same direction, so the
    O(N*M) distance matrix is unnecessary; a bounded window keeps the cost
    linear, which is what makes the DP affordable (plan S10).
    """
    count = len(observed)
    total = len(samples)
    if total == 0 or count == 0:
        return np.zeros(count, dtype=int)
    guess = np.clip(
        np.round(np.linspace(0, total - 1, count)).astype(int), 0, total - 1,
    )
    offsets = np.arange(-window, window + 1)
    candidates = np.clip(guess[:, None] + offsets[None, :], 0, total - 1)
    deltas = samples[candidates] - observed[:, None, :]
    distances = np.einsum("ijk,ijk->ij", deltas, deltas)
    return candidates[np.arange(count), np.argmin(distances, axis=1)]


def _order_statistic(values: np.ndarray, fraction: float) -> float:
    """Nearest-rank order statistic via partition.

    ``np.percentile``/``np.median`` dominated the DP profile (8k calls per
    ring); nearest rank is O(n), deterministic and sufficient here - every
    threshold in this module is defined against this convention.
    """
    count = len(values)
    if count == 0:
        return 0.0
    index = min(count - 1, max(0, int(round(fraction * (count - 1)))))
    return float(np.partition(values, index)[index])


def _check_from_errors(
    normal_error: np.ndarray, tangential: np.ndarray,
    halfwidth: np.ndarray, weights: np.ndarray,
    halfwidth_median: float | None = None,
) -> "CorridorCheck":
    median = (
        float(halfwidth_median) if halfwidth_median is not None
        else _order_statistic(halfwidth, 0.5)
    )
    feasible = bool(
        np.all(normal_error <= halfwidth + 1.0e-9)
        and _order_statistic(tangential, 0.95) <= 1.5 * median + 0.5
    )
    return CorridorCheck(
        feasible=feasible,
        residual=float(np.sum(normal_error ** 2 * weights)),
        max_deviation_px=float(np.max(normal_error)),
        p95_deviation_px=_order_statistic(normal_error, 0.95),
        bulge_px=float(np.max(np.maximum(normal_error - halfwidth, 0.0))),
        halfwidth_p50_px=median,
    )


def line_corridor_check(
    span: LineSpan, observed: np.ndarray, normals: np.ndarray,
    halfwidth: np.ndarray, weights: np.ndarray,
    halfwidth_median: float | None = None,
) -> "CorridorCheck":
    """Exact corridor test for a segment - projection, no sampling."""
    p0 = np.asarray(span.p0, float)
    p1 = np.asarray(span.p1, float)
    direction = p1 - p0
    denominator = float(direction @ direction)
    if denominator <= 1.0e-12:
        return CorridorCheck(False, 0.0, 0.0, 0.0, 0.0, 0.0)
    t = np.clip(((observed - p0) @ direction) / denominator, 0.0, 1.0)
    projected = p0[None, :] + t[:, None] * direction[None, :]
    offsets = projected - observed
    normal_error = np.abs(np.sum(offsets * normals, axis=1))
    tangential = np.sqrt(np.maximum(
        np.einsum("ij,ij->i", offsets, offsets) - normal_error ** 2, 0.0,
    ))
    return _check_from_errors(
        normal_error, tangential, halfwidth, weights, halfwidth_median,
    )


def arc_corridor_check(
    span: CircularArcSpan, observed: np.ndarray, normals: np.ndarray,
    halfwidth: np.ndarray, weights: np.ndarray,
    halfwidth_median: float | None = None,
) -> "CorridorCheck":
    """Exact corridor test for a circular arc - radial residual, no sampling."""
    center = np.asarray(span.center, float)
    radial = np.linalg.norm(observed - center, axis=1)
    signed = radial - float(span.radius)
    offsets = (
        (observed - center) / np.maximum(radial, 1.0e-9)[:, None]
    ) * (-signed)[:, None]
    normal_error = np.abs(np.sum(offsets * normals, axis=1))
    tangential = np.sqrt(np.maximum(
        np.einsum("ij,ij->i", offsets, offsets) - normal_error ** 2, 0.0,
    ))
    return _check_from_errors(
        normal_error, tangential, halfwidth, weights, halfwidth_median,
    )


def corridor_check(
    span: VectorSpan, observation: BoundaryObservation,
    indices: np.ndarray,
) -> CorridorCheck:
    """Every observed sample must lie within its own corridor (plan M4.3).

    The residual integrates squared normal error against physical ds
    weights, so sampling density cannot change the cost (plan S13.2).
    """
    observed = np.asarray(observation.points_xy, float)[indices]
    normals = np.asarray(observation.normals_xy, float)[indices]
    halfwidth = np.asarray(observation.halfwidth_px, float)[indices]
    weights = np.asarray(observation.physical_weights, float)[indices]
    samples = _span_samples(span, max(16, 2 * len(indices)))
    nearest = _monotone_nearest(observed, samples)
    offsets = samples[nearest] - observed
    normal_error = np.abs(np.sum(offsets * normals, axis=1))
    tangential = np.sqrt(np.maximum(
        np.einsum("ij,ij->i", offsets, offsets) - normal_error ** 2, 0.0,
    ))
    return _check_from_errors(normal_error, tangential, halfwidth, weights)


def corridor_feasible(
    span: VectorSpan, observation: BoundaryObservation,
    indices: np.ndarray,
) -> tuple[bool, float]:
    check = corridor_check(span, observation, indices)
    return check.feasible, check.residual


# --------------------------------------------------------------------------
# M4.2 span family fits
# --------------------------------------------------------------------------


def ring_curvature_signs(
    observation: BoundaryObservation, *, deadzone: float = 2.0e-3,
) -> np.ndarray:
    """Smoothed curvature sign of the OBSERVED boundary, computed once.

    A candidate span may only change curvature sign where the source
    already does; computing that per (i, j) pair was the dominant cost.
    """
    points = np.asarray(observation.points_xy, float)
    if len(points) < 5:
        return np.zeros(len(points), dtype=int)
    d1 = np.gradient(points, axis=0)
    d2 = np.gradient(d1, axis=0)
    speed = np.maximum(np.linalg.norm(d1, axis=1), 1.0e-9)
    curvature = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / speed ** 3
    window = max(3, len(curvature) // 12)
    kernel = np.ones(window) / window
    smoothed = np.convolve(
        np.concatenate((curvature[-window:], curvature, curvature[:window])),
        kernel, mode="same",
    )[window:-window]
    signs = np.zeros(len(smoothed), dtype=int)
    signs[smoothed > deadzone] = 1
    signs[smoothed < -deadzone] = -1
    return signs


def _supported_inflections(signs: np.ndarray, indices: np.ndarray) -> int:
    local = signs[indices]
    nonzero = local[local != 0]
    if len(nonzero) < 2:
        return 0
    return int(np.sum(nonzero[1:] != nonzero[:-1]))


def _fairness_for(
    span: VectorSpan, *, check: "CorridorCheck", supported: int,
    line_residual: float, samples: int = 24,
) -> SpanFairness:
    """Fairness features; analytic (exact, free) for line and circular arc."""
    if isinstance(span, (LineSpan, CircularArcSpan)):
        # A line has zero curvature everywhere; a circular arc has constant
        # curvature.  Both therefore have zero curvature variation, zero
        # sign changes and zero tangent reversals BY CONSTRUCTION - there is
        # nothing to sample, and no wobble is representable.
        reasons: list[str] = []
        if check.bulge_px > 1.0e-9:
            reasons.append("bulge-outside-evidence-corridor")
        return SpanFairness(
            path_id="probe", span_index=0, primitive_kind=span.kind,
            line_residual_px=line_residual,
            circle_residual_px=(
                None if isinstance(span, LineSpan) else check.p95_deviation_px
            ),
            max_normal_deviation_px=check.max_deviation_px,
            p95_normal_deviation_px=check.p95_deviation_px,
            tangent_total_variation=0.0, tangent_reversal_count=0,
            curvature_sign_changes=0, curvature_extrema_count=0,
            inflection_count=0, scale_invariant_curvature_variation=0.0,
            corner_angle_drift_deg=0.0, bulge_px=check.bulge_px,
            supported_inflections=supported,
            corridor_halfwidth_p50_px=check.halfwidth_p50_px,
            hard_invalid=bool(reasons), invalid_reasons=tuple(reasons),
        )
    return span_fairness(
        span, path_id="probe", span_index=0,
        precomputed_deviation=(
            check.max_deviation_px, check.p95_deviation_px, check.bulge_px,
            check.halfwidth_p50_px,
        ),
        supported_inflections=supported,
        line_residual_px=line_residual, samples=samples,
    )


def _circumcircle(
    p0: np.ndarray, pm: np.ndarray, p1: np.ndarray,
) -> tuple[np.ndarray, float] | None:
    ax, ay = float(p0[0]), float(p0[1])
    bx, by = float(pm[0]), float(pm[1])
    cx, cy = float(p1[0]), float(p1[1])
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1.0e-9:
        return None
    ux = (
        (ax * ax + ay * ay) * (by - cy)
        + (bx * bx + by * by) * (cy - ay)
        + (cx * cx + cy * cy) * (ay - by)
    ) / d
    uy = (
        (ax * ax + ay * ay) * (cx - bx)
        + (bx * bx + by * by) * (ax - cx)
        + (cx * cx + cy * cy) * (bx - ax)
    ) / d
    center = np.array([ux, uy])
    radius = float(np.linalg.norm(p0 - center))
    if not math.isfinite(radius) or radius <= 1.0e-6 or radius > 1.0e6:
        return None
    return center, radius


def _code_bits(span: VectorSpan) -> float:
    numbers = {
        "line": 4, "circular_arc": 7, "elliptic_arc": 9, "cubic": 8,
        "biarc": 14,
    }[span.kind]
    return 12.0 * numbers


def _proposals_for_span(
    observation: BoundaryObservation, start: int, end: int,
    tangents: np.ndarray, *, enable_arcs: bool = True,
    curvature_signs: np.ndarray | None = None, node_distance: int = 1,
) -> list[SpanProposal]:
    """The dominant family fit between two nodes (plan M4.2/M4.5/M4.6).

    Families are tried in strict dominance order.  Within one (i, j) pair
    every family contributes the same prefix and suffix to the DP path, so a
    feasible line dominates a feasible arc, which dominates a feasible
    cubic, which dominates the faithful fallback: same topology events, no
    more unsupported inflections, no faithful fallback and fewer code bits.
    The early exit is therefore exact rather than a heuristic prune - and it
    is exactly the mechanism behind the exact-straightness (M4.5) and
    exact-arcness (M4.6) rules.
    """
    points = np.asarray(observation.points_xy, float)
    count = len(points)
    indices = np.array(
        [i % count for i in range(start, end + 1)], dtype=int,
    )
    if len(indices) < 2:
        return []
    span_points = points[indices]
    normals = np.asarray(observation.normals_xy, float)[indices]
    halfwidth = np.asarray(observation.halfwidth_px, float)[indices]
    weights = np.asarray(observation.physical_weights, float)[indices]
    arclength = float(np.sum(weights))
    p0: Point = (float(span_points[0][0]), float(span_points[0][1]))
    p1: Point = (float(span_points[-1][0]), float(span_points[-1][1]))
    line_residual = float(np.max(point_line_distance(
        span_points, span_points[0], span_points[-1],
    )))
    supported = (
        _supported_inflections(curvature_signs, indices)
        if curvature_signs is not None else 0
    )
    halfwidth_median = _order_statistic(halfwidth, 0.5)

    def build(span: VectorSpan, family: str) -> SpanProposal | None:
        if isinstance(span, LineSpan):
            check = line_corridor_check(
                span, span_points, normals, halfwidth, weights,
                halfwidth_median,
            )
        elif isinstance(span, CircularArcSpan):
            check = arc_corridor_check(
                span, span_points, normals, halfwidth, weights,
                halfwidth_median,
            )
        else:
            check = corridor_check(span, observation, indices)
        if not check.feasible:
            return None
        fairness = _fairness_for(
            span, check=check, supported=supported,
            line_residual=line_residual,
        )
        if fairness.hard_invalid:
            return None
        return SpanProposal(
            spans=(span,), family=family,
            score=LexiScore(
                topology_events=0,
                unsupported_inflections=max(
                    0,
                    fairness.curvature_sign_changes
                    - fairness.supported_inflections,
                ),
                faithful_fallbacks=0,
                primitive_code_bits=_code_bits(span),
                fairness=fairness.soft_cost,
                render_nll=check.residual,
            ),
            fairness=fairness,
        )

    # --- exact straightness first (plan M4.5) -----------------------------
    if arclength >= MINIMUM_PRIMITIVE_LENGTH_PX:
        proposal = build(LineSpan(p0=p0, p1=p1), "line")
        if proposal is not None:
            return [proposal]

    # --- exact arcness (plan M4.6) ----------------------------------------
    if (
        enable_arcs and arclength >= MINIMUM_PRIMITIVE_LENGTH_PX
        and len(indices) >= 5
    ):
        middle = span_points[len(span_points) // 2]
        circle = _circumcircle(span_points[0], middle, span_points[-1])
        if circle is not None:
            center, radius = circle
            radial = np.abs(
                np.linalg.norm(span_points - center, axis=1) - radius,
            )
            angular_support = arclength / max(radius, 1.0e-6)
            if (
                angular_support >= MINIMUM_ARC_SWEEP_RAD
                and _order_statistic(radial, 0.95) <= halfwidth_median
            ):
                first_leg = middle - span_points[0]
                second_leg = span_points[-1] - middle
                cross = float(
                    first_leg[0] * second_leg[1] - first_leg[1] * second_leg[0]
                )
                proposal = build(
                    CircularArcSpan(
                        p0=p0, p1=p1,
                        center=(float(center[0]), float(center[1])),
                        radius=float(radius), clockwise=cross > 0.0,
                    ),
                    "circular_arc",
                )
                if proposal is not None:
                    return [proposal]

    # --- fair cubic -------------------------------------------------------
    if len(indices) >= 4:
        control, _prediction = cubic_control(
            span_points, unit(tangents[indices[0]]),
            unit(tangents[indices[-1]]),
        )
        proposal = build(
            CubicSpan(
                p0=p0,
                c1=(float(control[1][0]), float(control[1][1])),
                c2=(float(control[2][0]), float(control[2][1])),
                p1=p1,
            ),
            "cubic",
        )
        if proposal is not None:
            return [proposal]

    # --- faithful microspan (plan M4.7) -----------------------------------
    if node_distance > MAX_FAITHFUL_NODES:
        return []
    faithful_spans = _faithful_spans(span_points, halfwidth)
    if not faithful_spans:
        return []
    return [SpanProposal(
        spans=faithful_spans, family="faithful",
        score=LexiScore(
            topology_events=0, unsupported_inflections=0,
            faithful_fallbacks=1,
            primitive_code_bits=sum(
                _code_bits(span) for span in faithful_spans
            ),
            fairness=0.0, render_nll=0.0,
        ),
        fairness=None,
    )]


def _simplify(points: np.ndarray, tolerance: float) -> list[int]:
    """Douglas-Peucker keeping every vertex inside ``tolerance``."""
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue
        segment = points[start:end + 1]
        distances = point_line_distance(segment, points[start], points[end])
        offset = int(np.argmax(distances))
        if float(distances[offset]) > tolerance:
            index = start + offset
            keep.add(index)
            stack.append((start, index))
            stack.append((index, end))
    return sorted(keep)


def _faithful_spans(
    span_points: np.ndarray, halfwidth: np.ndarray,
) -> tuple[VectorSpan, ...]:
    """Corridor-safe polyline: the honest answer for undecided evidence."""
    tolerance = max(0.05, 0.5 * float(np.min(halfwidth)))
    kept = _simplify(span_points, tolerance)
    if len(kept) < 2:
        return ()
    spans: list[VectorSpan] = []
    for a, b in zip(kept, kept[1:]):
        spans.append(LineSpan(
            p0=(float(span_points[a][0]), float(span_points[a][1])),
            p1=(float(span_points[b][0]), float(span_points[b][1])),
        ))
    return tuple(spans)


# --------------------------------------------------------------------------
# M4.4 lexicographic DP
# --------------------------------------------------------------------------


def fit_path_program(
    observation: BoundaryObservation, *, enable_arcs: bool = True,
) -> tuple[tuple[VectorSpan, ...], list[SpanFairness]]:
    """Fit one closed boundary into a hybrid span program (plan M4.4)."""
    points = np.asarray(observation.points_xy, float)
    count = len(points)
    if count < 8:
        return (), []
    corners = stable_corner_indices(observation)
    nodes = build_dp_nodes(observation, corners)
    if len(nodes) < 3:
        nodes = list(range(0, count, max(1, count // 8)))
    # Cut the ring at the first corner so a real corner is never smoothed
    # across; without corners any cut is equivalent.
    cut = corners[0] if corners else nodes[0]
    ordered = sorted(nodes, key=lambda index: (index - cut) % count)
    chain = [((index - cut) % count) + cut for index in ordered]
    chain.append(chain[0] + count)
    tangents = polyline_tangents(points, closed=True)
    curvature_signs = ring_curvature_signs(observation)

    best: dict[int, LexiScore] = {0: LexiScore.zero()}
    back: dict[int, tuple[int, SpanProposal]] = {}
    for target in range(1, len(chain)):
        for source in range(max(0, target - MAX_SPAN_NODES), target):
            if source not in best:
                continue
            proposals = _proposals_for_span(
                observation, chain[source], chain[target], tangents,
                enable_arcs=enable_arcs, curvature_signs=curvature_signs,
                node_distance=target - source,
            )
            if not proposals:
                continue
            base = best[source]
            for proposal in proposals:
                total = base + proposal.score
                current = best.get(target)
                if current is None or total.key() < current.key():
                    best[target] = total
                    back[target] = (source, proposal)
    if len(chain) - 1 not in back:
        return (), []
    spans: list[VectorSpan] = []
    fairness_rows: list[SpanFairness] = []
    node = len(chain) - 1
    while node > 0:
        source, proposal = back[node]
        spans = list(proposal.spans) + spans
        if proposal.fairness is not None:
            fairness_rows.insert(0, proposal.fairness)
        node = source
    return tuple(spans), fairness_rows


# --------------------------------------------------------------------------
# program assembly
# --------------------------------------------------------------------------


def _ring_polygon(spans: tuple[VectorSpan, ...]) -> list[Point]:
    from .vector_program import flatten_path

    return flatten_path(
        ClosedPathProgram(
            id="probe", role="positive", spans=spans, fill_rule="evenodd",
        ),
        samples=10,
    )


def fair_program_from_observations(
    observations: list[BoundaryObservation], *, program_id: str,
    source_line_id: str,
    straight_rgba: tuple[float, float, float, float],
    enable_arcs: bool = True, provenance: tuple[str, ...] = (),
) -> tuple[TextVectorProgram | None, list[SpanFairness]]:
    """Assemble one hybrid program from all rings of a line (plan M4)."""
    rings: list[tuple[tuple[VectorSpan, ...], list[Point]]] = []
    fairness_rows: list[SpanFairness] = []
    for observation in observations:
        spans, rows = fit_path_program(observation, enable_arcs=enable_arcs)
        if not spans:
            return None, []
        rings.append((spans, _ring_polygon(spans)))
        fairness_rows.extend(rows)
    if not rings:
        return None, []
    paths: list[ClosedPathProgram] = []
    for index, (spans, polygon) in enumerate(rings):
        # Nesting is decided by a point ON this ring: rings never cross, so
        # a boundary point is unambiguous, while an INTERIOR point of an
        # outer ring can legitimately fall inside a hole and invert the role.
        probe = polygon[0] if polygon else None
        depth = 0
        if probe is not None:
            depth = sum(
                1 for other_index, (_other_spans, other) in enumerate(rings)
                if other_index != index and point_in_polygon(probe, other)
            )
        paths.append(ClosedPathProgram(
            id=f"ring-{index:04d}",
            role="positive" if depth % 2 == 0 else "negative",
            spans=spans, fill_rule="evenodd",
        ))
    layer = VectorPaintLayer(
        id="fill-0", path_ids=tuple(path.id for path in paths),
        paint=solid_paint_from_straight_rgba(straight_rgba), z_index=0,
        semantic_role="fill",
    )
    program = seal_program(TextVectorProgram(
        id=program_id, source_line_id=source_line_id,
        geometry_family=FAIR_FAMILY, paths=tuple(paths), layers=(layer,),
        provenance=(
            "materialization-v2", "fair-primitive-hybrid", *provenance,
        ),
    ))
    return program, fairness_rows


def fair_program_from_coverage(
    alpha: np.ndarray, *, program_id: str, source_line_id: str,
    straight_rgba: tuple[float, float, float, float],
    uncertainty: np.ndarray | None = None, enable_arcs: bool = True,
    provenance: tuple[str, ...] = (),
):
    """Coverage field -> boundary observations -> hybrid program."""
    from .coverage_evidence import boundary_observations

    observations = boundary_observations(
        alpha, uncertainty=uncertainty, component_id=source_line_id,
    )
    if not observations:
        return None, None
    program, rows = fair_program_from_observations(
        observations, program_id=program_id, source_line_id=source_line_id,
        straight_rgba=straight_rgba, enable_arcs=enable_arcs,
        provenance=provenance,
    )
    if program is None:
        return None, None
    return program, fairness_certificate(rows)

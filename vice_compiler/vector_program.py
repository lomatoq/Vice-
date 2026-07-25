"""Materialization v2: the final vector program contract (plan S3.1-S3.2).

The delivered SVG fragment of a TextLine must BE the serialization of the
program the court selected.  Today the court selects a support mask and the
exporter afterwards invents geometry and paint on its own, which is why the
delivered result can be "pixelated or crooked" no matter what the court
decided.  This module introduces the missing artefact:

    serialize(selected TextVectorProgram) == final SVG fragment shipped

Nothing here renders, fits or decides.  It is a pure, dependency-neutral
contract module: dataclasses, validation, canonical serialization and the
SVG writer.  Every consumer (materializers, certificates, court, exporter)
shares exactly these bytes, so a digest computed at court time is checkable
at export time.

Float policy (plan S3.2):
    internal            float64
    canonical program   decimal round-trip, 12 significant digits
    SVG writer          the same values, no second quantization

``seal_program`` performs the single quantization, then both the canonical
JSON and the SVG fragment are produced from those identical numbers.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from typing import Iterable, Literal, Sequence

Point = tuple[float, float]
RGBA = tuple[float, float, float, float]

SERIALIZER_VERSION = "vice-text-vector-program/1"
#: Programs are sealed at 12 significant digits; a closed path must return to
#: its start well inside that, but not so tight that legal rounding fails.
CLOSURE_EPSILON_PX = 1.0e-6
#: Span chaining uses the same budget: span i+1 starts where span i ended.
CHAIN_EPSILON_PX = 1.0e-6


# --------------------------------------------------------------------------
# spans
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LineSpan:
    p0: Point
    p1: Point
    kind: Literal["line"] = "line"


@dataclass(frozen=True)
class CircularArcSpan:
    """Circular arc.

    ``clockwise`` is SVG sweep-flag semantics: True serializes sweep-flag 1,
    i.e. the angle increases in SVG's y-down frame (visually clockwise).
    """

    p0: Point
    p1: Point
    center: Point
    radius: float
    clockwise: bool
    kind: Literal["circular_arc"] = "circular_arc"


@dataclass(frozen=True)
class EllipticArcSpan:
    p0: Point
    p1: Point
    center: Point
    rx: float
    ry: float
    angle_deg: float
    clockwise: bool
    kind: Literal["elliptic_arc"] = "elliptic_arc"


@dataclass(frozen=True)
class CubicSpan:
    p0: Point
    c1: Point
    c2: Point
    p1: Point
    kind: Literal["cubic"] = "cubic"


@dataclass(frozen=True)
class BiarcSpan:
    first: CircularArcSpan
    second: CircularArcSpan
    kind: Literal["biarc"] = "biarc"


VectorSpan = (
    LineSpan | CircularArcSpan | EllipticArcSpan | CubicSpan | BiarcSpan
)

SpanRole = Literal[
    "positive", "negative", "frame_outer", "frame_inner", "stroke_outline",
]
NEGATIVE_ROLES = frozenset({"negative", "frame_inner"})


@dataclass(frozen=True)
class ClosedPathProgram:
    id: str
    role: SpanRole
    spans: tuple[VectorSpan, ...]
    fill_rule: Literal["nonzero", "evenodd"]
    source_component_ids: tuple[str, ...] = ()
    source_hole_ids: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# paint
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SolidPaint:
    rgba_linear: RGBA
    kind: Literal["solid"] = "solid"


@dataclass(frozen=True)
class LinearGradientPaint:
    p0: Point
    p1: Point
    stops: tuple[tuple[float, RGBA], ...]
    kind: Literal["linear_gradient"] = "linear_gradient"


@dataclass(frozen=True)
class RadialGradientPaint:
    center: Point
    radius: float
    stops: tuple[tuple[float, RGBA], ...]
    kind: Literal["radial_gradient"] = "radial_gradient"


PaintProgram = SolidPaint | LinearGradientPaint | RadialGradientPaint

SemanticRole = Literal[
    "fill", "outline", "shadow", "knockout", "stripe", "detail", "mark",
]


@dataclass(frozen=True)
class VectorPaintLayer:
    id: str
    path_ids: tuple[str, ...]
    paint: PaintProgram
    z_index: int
    source_cluster_ids: tuple[str, ...] = ()
    semantic_role: SemanticRole = "fill"


@dataclass(frozen=True)
class TextVectorProgram:
    id: str
    source_line_id: str
    geometry_family: str
    paths: tuple[ClosedPathProgram, ...]
    layers: tuple[VectorPaintLayer, ...]
    glyph_path_groups: tuple[tuple[str, tuple[str, ...]], ...] = ()
    exact_fragment_sha256: str = ""
    program_sha256: str = ""
    provenance: tuple[str, ...] = ()


class ProgramValidationError(ValueError):
    """Raised when a program violates the plan S3.2 contract."""


# --------------------------------------------------------------------------
# float policy
# --------------------------------------------------------------------------


def quantize(value: float) -> float:
    """12 significant digits, decimal round-trip (plan S3.2 float policy)."""
    number = float(value)
    if not math.isfinite(number):
        raise ProgramValidationError(f"non-finite coordinate: {value!r}")
    if number == 0.0:
        return 0.0
    return float(f"{number:.12g}")


def format_number(value: float) -> str:
    """Serialize an already-quantized value; never quantizes a second time."""
    text = f"{float(value):.12g}"
    return "0" if text in ("-0", "-0.0") else text


def _q_point(point: Sequence[float]) -> Point:
    return (quantize(point[0]), quantize(point[1]))


def _q_rgba(rgba: Sequence[float]) -> RGBA:
    if len(rgba) != 4:
        raise ProgramValidationError("rgba must have four channels")
    return (
        quantize(rgba[0]), quantize(rgba[1]),
        quantize(rgba[2]), quantize(rgba[3]),
    )


def quantize_span(span: VectorSpan) -> VectorSpan:
    if isinstance(span, LineSpan):
        return LineSpan(p0=_q_point(span.p0), p1=_q_point(span.p1))
    if isinstance(span, CircularArcSpan):
        return CircularArcSpan(
            p0=_q_point(span.p0), p1=_q_point(span.p1),
            center=_q_point(span.center), radius=quantize(span.radius),
            clockwise=bool(span.clockwise),
        )
    if isinstance(span, EllipticArcSpan):
        return EllipticArcSpan(
            p0=_q_point(span.p0), p1=_q_point(span.p1),
            center=_q_point(span.center), rx=quantize(span.rx),
            ry=quantize(span.ry), angle_deg=quantize(span.angle_deg),
            clockwise=bool(span.clockwise),
        )
    if isinstance(span, CubicSpan):
        return CubicSpan(
            p0=_q_point(span.p0), c1=_q_point(span.c1),
            c2=_q_point(span.c2), p1=_q_point(span.p1),
        )
    if isinstance(span, BiarcSpan):
        return BiarcSpan(
            first=quantize_span(span.first), second=quantize_span(span.second),
        )
    raise ProgramValidationError(f"unknown span kind: {span!r}")


def quantize_paint(paint: PaintProgram) -> PaintProgram:
    if isinstance(paint, SolidPaint):
        return SolidPaint(rgba_linear=_q_rgba(paint.rgba_linear))
    if isinstance(paint, LinearGradientPaint):
        return LinearGradientPaint(
            p0=_q_point(paint.p0), p1=_q_point(paint.p1),
            stops=tuple(
                (quantize(offset), _q_rgba(colour))
                for offset, colour in paint.stops
            ),
        )
    if isinstance(paint, RadialGradientPaint):
        return RadialGradientPaint(
            center=_q_point(paint.center), radius=quantize(paint.radius),
            stops=tuple(
                (quantize(offset), _q_rgba(colour))
                for offset, colour in paint.stops
            ),
        )
    raise ProgramValidationError(f"unknown paint kind: {paint!r}")


def quantize_program(program: TextVectorProgram) -> TextVectorProgram:
    return replace(
        program,
        paths=tuple(
            replace(path, spans=tuple(quantize_span(s) for s in path.spans))
            for path in program.paths
        ),
        layers=tuple(
            replace(layer, paint=quantize_paint(layer.paint))
            for layer in program.layers
        ),
    )


# --------------------------------------------------------------------------
# geometry helpers (shared by validation, certificates and metrics)
# --------------------------------------------------------------------------


def span_endpoints(span: VectorSpan) -> tuple[Point, Point]:
    if isinstance(span, BiarcSpan):
        return span.first.p0, span.second.p1
    return span.p0, span.p1


def _angle_of(center: Point, point: Point) -> float:
    return math.atan2(point[1] - center[1], point[0] - center[0])


def arc_sweep(span: CircularArcSpan) -> tuple[float, float]:
    """Return (start_angle, signed sweep) in SVG's y-down frame."""
    start = _angle_of(span.center, span.p0)
    end = _angle_of(span.center, span.p1)
    delta = end - start
    if span.clockwise:
        while delta <= 0.0:
            delta += 2.0 * math.pi
        while delta > 2.0 * math.pi:
            delta -= 2.0 * math.pi
    else:
        while delta >= 0.0:
            delta -= 2.0 * math.pi
        while delta < -2.0 * math.pi:
            delta += 2.0 * math.pi
    return start, delta


def flatten_span(span: VectorSpan, *, samples: int = 24) -> list[Point]:
    """Polyline approximation EXCLUDING the start point (append-friendly)."""
    steps = max(2, int(samples))
    if isinstance(span, LineSpan):
        return [span.p1]
    if isinstance(span, CircularArcSpan):
        start, delta = arc_sweep(span)
        points: list[Point] = []
        for index in range(1, steps + 1):
            angle = start + delta * (index / steps)
            points.append((
                span.center[0] + span.radius * math.cos(angle),
                span.center[1] + span.radius * math.sin(angle),
            ))
        points[-1] = span.p1
        return points
    if isinstance(span, EllipticArcSpan):
        rotation = math.radians(span.angle_deg)
        cos_r, sin_r = math.cos(rotation), math.sin(rotation)

        def to_unit(point: Point) -> float:
            dx = point[0] - span.center[0]
            dy = point[1] - span.center[1]
            ux = (dx * cos_r + dy * sin_r) / max(span.rx, 1.0e-12)
            uy = (-dx * sin_r + dy * cos_r) / max(span.ry, 1.0e-12)
            return math.atan2(uy, ux)

        start = to_unit(span.p0)
        end = to_unit(span.p1)
        delta = end - start
        if span.clockwise:
            while delta <= 0.0:
                delta += 2.0 * math.pi
        else:
            while delta >= 0.0:
                delta -= 2.0 * math.pi
        points = []
        for index in range(1, steps + 1):
            angle = start + delta * (index / steps)
            ux = span.rx * math.cos(angle)
            uy = span.ry * math.sin(angle)
            points.append((
                span.center[0] + ux * cos_r - uy * sin_r,
                span.center[1] + ux * sin_r + uy * cos_r,
            ))
        points[-1] = span.p1
        return points
    if isinstance(span, CubicSpan):
        points = []
        for index in range(1, steps + 1):
            t = index / steps
            u = 1.0 - t
            x = (
                u * u * u * span.p0[0] + 3 * u * u * t * span.c1[0]
                + 3 * u * t * t * span.c2[0] + t * t * t * span.p1[0]
            )
            y = (
                u * u * u * span.p0[1] + 3 * u * u * t * span.c1[1]
                + 3 * u * t * t * span.c2[1] + t * t * t * span.p1[1]
            )
            points.append((x, y))
        points[-1] = span.p1
        return points
    if isinstance(span, BiarcSpan):
        return (
            flatten_span(span.first, samples=steps)
            + flatten_span(span.second, samples=steps)
        )
    raise ProgramValidationError(f"unknown span kind: {span!r}")


def flatten_path(
    path: ClosedPathProgram, *, samples: int = 24,
) -> list[Point]:
    if not path.spans:
        return []
    points = [span_endpoints(path.spans[0])[0]]
    for span in path.spans:
        points.extend(flatten_span(span, samples=samples))
    return points


def polygon_area(points: Sequence[Point]) -> float:
    """Signed area; positive means counter-clockwise in a y-up frame."""
    total = 0.0
    count = len(points)
    for index in range(count):
        x0, y0 = points[index]
        x1, y1 = points[(index + 1) % count]
        total += x0 * y1 - x1 * y0
    return 0.5 * total


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    x, y = point
    inside = False
    count = len(polygon)
    for index in range(count):
        x0, y0 = polygon[index]
        x1, y1 = polygon[(index + 1) % count]
        if (y0 > y) != (y1 > y):
            slope = (x1 - x0) / (y1 - y0) if y1 != y0 else 0.0
            if x < x0 + (y - y0) * slope:
                inside = not inside
    return inside


def path_bbox(path: ClosedPathProgram) -> tuple[float, float, float, float]:
    points = flatten_path(path)
    if not points:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


# --------------------------------------------------------------------------
# validation (plan S3.2)
# --------------------------------------------------------------------------


def _validate_span(span: VectorSpan, where: str) -> None:
    for name, point in (
        ("p0", span_endpoints(span)[0]), ("p1", span_endpoints(span)[1]),
    ):
        for value in point:
            if not math.isfinite(value):
                raise ProgramValidationError(
                    f"{where}: non-finite {name} coordinate",
                )
    if isinstance(span, CircularArcSpan):
        if not (span.radius > 0.0):
            raise ProgramValidationError(f"{where}: arc radius must be > 0")
        for point, name in ((span.p0, "p0"), (span.p1, "p1")):
            distance = math.hypot(
                point[0] - span.center[0], point[1] - span.center[1],
            )
            if abs(distance - span.radius) > max(1.0e-6, 1.0e-6 * span.radius):
                raise ProgramValidationError(
                    f"{where}: arc {name} is not on the circle "
                    f"({distance:.9g} vs r={span.radius:.9g})",
                )
    elif isinstance(span, EllipticArcSpan):
        if not (span.rx > 0.0 and span.ry > 0.0):
            raise ProgramValidationError(f"{where}: ellipse radii must be > 0")
    elif isinstance(span, CubicSpan):
        for name, point in (("c1", span.c1), ("c2", span.c2)):
            for value in point:
                if not math.isfinite(value):
                    raise ProgramValidationError(
                        f"{where}: non-finite {name} coordinate",
                    )
    elif isinstance(span, BiarcSpan):
        _validate_span(span.first, f"{where}.first")
        _validate_span(span.second, f"{where}.second")
        join_a = span.first.p1
        join_b = span.second.p0
        if math.dist(join_a, join_b) > CHAIN_EPSILON_PX:
            raise ProgramValidationError(f"{where}: biarc halves do not meet")


def _validate_path(path: ClosedPathProgram) -> None:
    if not path.spans:
        raise ProgramValidationError(f"path {path.id}: no spans")
    if path.fill_rule not in ("nonzero", "evenodd"):
        raise ProgramValidationError(f"path {path.id}: bad fill rule")
    previous_end: Point | None = None
    for index, span in enumerate(path.spans):
        where = f"path {path.id} span {index}"
        _validate_span(span, where)
        start, end = span_endpoints(span)
        if previous_end is not None:
            if math.dist(previous_end, start) > CHAIN_EPSILON_PX:
                raise ProgramValidationError(
                    f"{where}: does not start where the previous span ended",
                )
        previous_end = end
    first_start = span_endpoints(path.spans[0])[0]
    if math.dist(first_start, previous_end or first_start) > CLOSURE_EPSILON_PX:
        raise ProgramValidationError(f"path {path.id}: path is not closed")


def _validate_paint(layer: VectorPaintLayer) -> None:
    paint = layer.paint
    if isinstance(paint, SolidPaint):
        channels = paint.rgba_linear
    else:
        if not paint.stops:
            raise ProgramValidationError(f"layer {layer.id}: gradient has no stops")
        offsets = [offset for offset, _ in paint.stops]
        if any(not (0.0 <= offset <= 1.0) for offset in offsets):
            raise ProgramValidationError(
                f"layer {layer.id}: gradient stop offset outside [0, 1]",
            )
        if any(b < a for a, b in zip(offsets, offsets[1:])):
            raise ProgramValidationError(
                f"layer {layer.id}: gradient stops are not sorted",
            )
        if isinstance(paint, RadialGradientPaint) and not (paint.radius > 0.0):
            raise ProgramValidationError(
                f"layer {layer.id}: radial gradient radius must be > 0",
            )
        channels = paint.stops[0][1]
    for value in channels:
        if not math.isfinite(value):
            raise ProgramValidationError(f"layer {layer.id}: non-finite colour")


def validate_text_vector_program(
    program: TextVectorProgram, *, check_digests: bool = True,
) -> None:
    """Enforce the plan S3.2 contract; raises ProgramValidationError."""
    if not program.paths:
        raise ProgramValidationError("program has no paths")
    path_ids = [path.id for path in program.paths]
    if len(set(path_ids)) != len(path_ids):
        raise ProgramValidationError("duplicate path ids")
    layer_ids = [layer.id for layer in program.layers]
    if len(set(layer_ids)) != len(layer_ids):
        raise ProgramValidationError("duplicate layer ids")
    for path in program.paths:
        _validate_path(path)
    known = set(path_ids)
    for layer in program.layers:
        if not layer.path_ids:
            raise ProgramValidationError(f"layer {layer.id}: no paths")
        missing = [pid for pid in layer.path_ids if pid not in known]
        if missing:
            raise ProgramValidationError(
                f"layer {layer.id}: unknown path ids {missing}",
            )
        rules = {
            path.fill_rule for path in program.paths
            if path.id in set(layer.path_ids)
        }
        if len(rules) > 1:
            raise ProgramValidationError(
                f"layer {layer.id}: mixed fill rules in one element",
            )
        _validate_paint(layer)
    z_indices = [layer.z_index for layer in program.layers]
    if len(set(z_indices)) != len(z_indices):
        raise ProgramValidationError("z-indices must be a deterministic order")
    for glyph_id, members in program.glyph_path_groups:
        missing = [pid for pid in members if pid not in known]
        if missing:
            raise ProgramValidationError(
                f"glyph group {glyph_id}: unknown path ids {missing}",
            )
    _validate_negative_containment(program)
    if check_digests:
        expected_program = program_digest(program)
        if program.program_sha256 != expected_program:
            raise ProgramValidationError("program_sha256 does not match")
        fragment = serialize_text_vector_program(program)
        expected_fragment = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
        if program.exact_fragment_sha256 != expected_fragment:
            raise ProgramValidationError("exact_fragment_sha256 does not match")


def _validate_negative_containment(program: TextVectorProgram) -> None:
    """Every negative loop must sit inside a positive loop of the same layer."""
    positives = {
        path.id: flatten_path(path, samples=12)
        for path in program.paths if path.role not in NEGATIVE_ROLES
    }
    if not positives:
        raise ProgramValidationError("program has no positive path")
    by_id = {path.id: path for path in program.paths}
    for layer in program.layers:
        layer_positive = [
            points for pid, points in positives.items() if pid in layer.path_ids
        ]
        for pid in layer.path_ids:
            path = by_id[pid]
            if path.role not in NEGATIVE_ROLES:
                continue
            probe = flatten_path(path, samples=12)
            if not probe:
                continue
            sample = probe[len(probe) // 2]
            if not any(
                point_in_polygon(sample, outer) for outer in layer_positive
            ):
                raise ProgramValidationError(
                    f"path {pid}: negative loop is not contained",
                )


# --------------------------------------------------------------------------
# canonical serialization
# --------------------------------------------------------------------------


def _span_dict(span: VectorSpan) -> dict:
    if isinstance(span, LineSpan):
        return {"kind": "line", "p0": list(span.p0), "p1": list(span.p1)}
    if isinstance(span, CircularArcSpan):
        return {
            "kind": "circular_arc", "p0": list(span.p0), "p1": list(span.p1),
            "center": list(span.center), "radius": span.radius,
            "clockwise": bool(span.clockwise),
        }
    if isinstance(span, EllipticArcSpan):
        return {
            "kind": "elliptic_arc", "p0": list(span.p0), "p1": list(span.p1),
            "center": list(span.center), "rx": span.rx, "ry": span.ry,
            "angle_deg": span.angle_deg, "clockwise": bool(span.clockwise),
        }
    if isinstance(span, CubicSpan):
        return {
            "kind": "cubic", "p0": list(span.p0), "c1": list(span.c1),
            "c2": list(span.c2), "p1": list(span.p1),
        }
    if isinstance(span, BiarcSpan):
        return {
            "kind": "biarc",
            "first": _span_dict(span.first), "second": _span_dict(span.second),
        }
    raise ProgramValidationError(f"unknown span kind: {span!r}")


def _paint_dict(paint: PaintProgram) -> dict:
    if isinstance(paint, SolidPaint):
        return {"kind": "solid", "rgba_linear": list(paint.rgba_linear)}
    if isinstance(paint, LinearGradientPaint):
        return {
            "kind": "linear_gradient", "p0": list(paint.p0),
            "p1": list(paint.p1),
            "stops": [[offset, list(colour)] for offset, colour in paint.stops],
        }
    if isinstance(paint, RadialGradientPaint):
        return {
            "kind": "radial_gradient", "center": list(paint.center),
            "radius": paint.radius,
            "stops": [[offset, list(colour)] for offset, colour in paint.stops],
        }
    raise ProgramValidationError(f"unknown paint kind: {paint!r}")


def to_canonical_dict(program: TextVectorProgram) -> dict:
    """Digest domain: everything except the digests themselves."""
    return {
        "serializer_version": SERIALIZER_VERSION,
        "id": program.id,
        "source_line_id": program.source_line_id,
        "geometry_family": program.geometry_family,
        "paths": [
            {
                "id": path.id, "role": path.role, "fill_rule": path.fill_rule,
                "spans": [_span_dict(span) for span in path.spans],
                "source_component_ids": list(path.source_component_ids),
                "source_hole_ids": list(path.source_hole_ids),
            }
            for path in program.paths
        ],
        "layers": [
            {
                "id": layer.id, "path_ids": list(layer.path_ids),
                "paint": _paint_dict(layer.paint), "z_index": layer.z_index,
                "source_cluster_ids": list(layer.source_cluster_ids),
                "semantic_role": layer.semantic_role,
            }
            for layer in program.layers
        ],
        "glyph_path_groups": [
            [glyph_id, list(members)]
            for glyph_id, members in program.glyph_path_groups
        ],
        "provenance": list(program.provenance),
    }


def canonical_json(program: TextVectorProgram) -> str:
    return json.dumps(
        to_canonical_dict(program),
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    )


def program_digest(program: TextVectorProgram) -> str:
    return hashlib.sha256(canonical_json(program).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# SVG writer (the delivered bytes)
# --------------------------------------------------------------------------


def _svg_span(span: VectorSpan) -> str:
    if isinstance(span, LineSpan):
        return f"L{format_number(span.p1[0])} {format_number(span.p1[1])}"
    if isinstance(span, CircularArcSpan):
        _start, delta = arc_sweep(span)
        large = 1 if abs(delta) > math.pi else 0
        sweep = 1 if span.clockwise else 0
        radius = format_number(span.radius)
        return (
            f"A{radius} {radius} 0 {large} {sweep} "
            f"{format_number(span.p1[0])} {format_number(span.p1[1])}"
        )
    if isinstance(span, EllipticArcSpan):
        points = flatten_span(span, samples=48)
        midpoint = points[len(points) // 2]
        chord = (
            math.atan2(span.p1[1] - span.p0[1], span.p1[0] - span.p0[0])
        )
        to_mid = math.atan2(
            midpoint[1] - span.p0[1], midpoint[0] - span.p0[0],
        )
        turn = (to_mid - chord + math.pi) % (2 * math.pi) - math.pi
        large = 1 if abs(turn) > math.pi / 2 else 0
        sweep = 1 if span.clockwise else 0
        return (
            f"A{format_number(span.rx)} {format_number(span.ry)} "
            f"{format_number(span.angle_deg)} {large} {sweep} "
            f"{format_number(span.p1[0])} {format_number(span.p1[1])}"
        )
    if isinstance(span, CubicSpan):
        return (
            f"C{format_number(span.c1[0])} {format_number(span.c1[1])} "
            f"{format_number(span.c2[0])} {format_number(span.c2[1])} "
            f"{format_number(span.p1[0])} {format_number(span.p1[1])}"
        )
    if isinstance(span, BiarcSpan):
        return f"{_svg_span(span.first)}{_svg_span(span.second)}"
    raise ProgramValidationError(f"unknown span kind: {span!r}")


def path_data(path: ClosedPathProgram) -> str:
    start = span_endpoints(path.spans[0])[0]
    parts = [f"M{format_number(start[0])} {format_number(start[1])}"]
    parts.extend(_svg_span(span) for span in path.spans)
    parts.append("Z")
    return "".join(parts)


def _srgb_channel(value: float) -> float:
    linear = min(1.0, max(0.0, float(value)))
    if linear <= 0.0031308:
        return 12.92 * linear
    return 1.055 * (linear ** (1.0 / 2.4)) - 0.055


def rgba_to_svg(rgba: RGBA) -> tuple[str, float]:
    """Linear RGBA -> (#rrggbb, alpha) exactly like the legacy writer."""
    red, green, blue, alpha = rgba
    channels = tuple(
        int(round(min(255.0, max(0.0, _srgb_channel(value) * 255.0))))
        for value in (red, green, blue)
    )
    return "#%02x%02x%02x" % channels, float(min(1.0, max(0.0, alpha)))


def _paint_attributes(
    paint: PaintProgram, gradient_id: str,
) -> tuple[str, str]:
    """Return (defs fragment, fill attributes)."""
    if isinstance(paint, SolidPaint):
        colour, alpha = rgba_to_svg(paint.rgba_linear)
        attributes = f'fill="{colour}"'
        if alpha < 1.0:
            attributes += f' fill-opacity="{format_number(alpha)}"'
        return "", attributes
    stops = "".join(
        f'<stop offset="{format_number(offset)}" '
        f'stop-color="{rgba_to_svg(colour)[0]}" '
        f'stop-opacity="{format_number(rgba_to_svg(colour)[1])}"/>'
        for offset, colour in paint.stops
    )
    if isinstance(paint, LinearGradientPaint):
        defs = (
            f'<linearGradient id="{gradient_id}" '
            f'gradientUnits="userSpaceOnUse" '
            f'x1="{format_number(paint.p0[0])}" '
            f'y1="{format_number(paint.p0[1])}" '
            f'x2="{format_number(paint.p1[0])}" '
            f'y2="{format_number(paint.p1[1])}">{stops}</linearGradient>'
        )
    else:
        defs = (
            f'<radialGradient id="{gradient_id}" '
            f'gradientUnits="userSpaceOnUse" '
            f'cx="{format_number(paint.center[0])}" '
            f'cy="{format_number(paint.center[1])}" '
            f'r="{format_number(paint.radius)}">{stops}</radialGradient>'
        )
    return defs, f'fill="url(#{gradient_id})"'


def serialize_text_vector_program(program: TextVectorProgram) -> str:
    """The delivered SVG fragment.  This is the single source of truth."""
    by_id = {path.id: path for path in program.paths}
    defs: list[str] = []
    elements: list[str] = []
    for layer in sorted(program.layers, key=lambda row: (row.z_index, row.id)):
        data = "".join(path_data(by_id[pid]) for pid in layer.path_ids)
        gradient_id = f"{program.id}-{layer.id}-paint"
        defs_fragment, fill_attributes = _paint_attributes(
            layer.paint, gradient_id,
        )
        if defs_fragment:
            defs.append(defs_fragment)
        fill_rule = by_id[layer.path_ids[0]].fill_rule
        elements.append(
            f'<path d="{data}" fill-rule="{fill_rule}" {fill_attributes} '
            f'data-pcdc-text-geometry="{program.geometry_family}" '
            f'data-pcdc-layer-role="{layer.semantic_role}"/>'
        )
    body = "".join(elements)
    if defs:
        body = f"<defs>{''.join(defs)}</defs>{body}"
    return body


def seal_program(program: TextVectorProgram) -> TextVectorProgram:
    """Quantize once, validate, then bind both digests (plan S3.2)."""
    quantized = quantize_program(program)
    validate_text_vector_program(quantized, check_digests=False)
    digest = program_digest(quantized)
    sealed = replace(quantized, program_sha256=digest)
    fragment = serialize_text_vector_program(sealed)
    return replace(
        sealed,
        exact_fragment_sha256=hashlib.sha256(
            fragment.encode("utf-8"),
        ).hexdigest(),
    )


def fragment_to_document(
    fragment: str, *, width: int, height: int,
) -> str:
    """Wrap a fragment for exact rendering/proofs (no geometry decisions)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(width)}" '
        f'height="{int(height)}" viewBox="0 0 {int(width)} {int(height)}">'
        f"{fragment}</svg>"
    )


def program_span_count(program: TextVectorProgram) -> int:
    return sum(len(path.spans) for path in program.paths)


def program_primitive_census(program: TextVectorProgram) -> dict[str, int]:
    census: dict[str, int] = {}
    for path in program.paths:
        for span in path.spans:
            census[span.kind] = census.get(span.kind, 0) + 1
    return census


def iter_spans(
    program: TextVectorProgram,
) -> Iterable[tuple[str, int, VectorSpan]]:
    for path in program.paths:
        for index, span in enumerate(path.spans):
            yield path.id, index, span

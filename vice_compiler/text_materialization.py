"""Materialization v2: candidate generators that run BEFORE the court.

Plan S2/S3.4/M1/M2.  Today the exporter invents the delivered geometry after
selection, so the court never compares "pixel-faithful" against "smooth" -
it only ever sees a support mask.  This module produces competing final
programs for one support, each of which can be rendered, certified and
judged, and the winner is what the exporter serializes verbatim.

Generators implemented here:

    faithful_program_from_mask       exact pixel cell union   (M1 parity)
    generate_legacy_smooth_program   the current G1 fitter    (M2 parity)

Both are byte/raster equivalent to the routes they replace, which is the
gate for the migration commits; new geometry families arrive in M4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from .vector_program import (
    ClosedPathProgram,
    CubicSpan,
    LineSpan,
    Point,
    ProgramValidationError,
    SolidPaint,
    TextVectorProgram,
    VectorPaintLayer,
    VectorSpan,
    flatten_path,
    interior_point,
    point_in_polygon,
    seal_program,
    solid_paint_from_straight_rgba,
)

FAITHFUL_FAMILY = "faithful-cell-edge"
LEGACY_SMOOTH_FAMILY = "legacy-current-smooth"


@dataclass(frozen=True)
class ResourceEstimate:
    """Bounded-cost accounting for one materialization candidate (S10)."""

    span_count: int = 0
    path_count: int = 0
    layer_count: int = 0
    exact_render_pixels: int = 0
    fit_milliseconds: float = 0.0


@dataclass(frozen=True)
class MaterializationCertificateBundle:
    """Placeholder bundle; populated by materialization_certificates (M5-M7)."""

    entries: tuple[tuple[str, object], ...] = ()

    def get(self, name: str, default: object = None) -> object:
        for key, value in self.entries:
            if key == name:
                return value
        return default

    @property
    def valid(self) -> bool:
        return all(
            getattr(value, "valid", True) for _key, value in self.entries
        )


@dataclass(frozen=True)
class TextVectorCandidate:
    """Plan S3.4: a final program plus everything needed to judge it."""

    id: str
    source_record_id: str
    program: TextVectorProgram
    ownership_support: np.ndarray
    evaluation_support: np.ndarray
    exact_svg_fragment: str
    exact_render_linear_rgba: np.ndarray | None = None
    exact_render_sha256: str = ""
    certificates: MaterializationCertificateBundle = field(
        default_factory=MaterializationCertificateBundle,
    )
    resource_estimate: ResourceEstimate = field(
        default_factory=ResourceEstimate,
    )
    provenance: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# M1: faithful cell-edge program (exact parity with _pixel_run_path)
# --------------------------------------------------------------------------


def mask_runs(mask: np.ndarray) -> list[tuple[int, int, int]]:
    """Horizontal runs as (y, x_start, x_end_exclusive), scanline order.

    Mirrors ``export_writer._pixel_run_path`` exactly, including the row
    order and the half-open run convention.
    """
    binary = np.asarray(mask, bool)
    runs: list[tuple[int, int, int]] = []
    for y in range(binary.shape[0]):
        values = binary[y].astype(np.int8)
        transitions = np.diff(np.pad(values, (1, 1)))
        starts = np.flatnonzero(transitions == 1)
        ends = np.flatnonzero(transitions == -1)
        for start, end in zip(starts.tolist(), ends.tolist()):
            runs.append((int(y), int(start), int(end)))
    return runs


def _rectangle_path(
    path_id: str, x0: float, y0: float, x1: float, y1: float,
) -> ClosedPathProgram:
    corners: list[Point] = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    spans = tuple(
        LineSpan(p0=corners[index], p1=corners[(index + 1) % 4])
        for index in range(4)
    )
    return ClosedPathProgram(
        id=path_id, role="positive", spans=spans, fill_rule="evenodd",
    )


def faithful_program_from_mask(
    mask: np.ndarray, *, program_id: str, source_line_id: str,
    straight_rgba: tuple[float, float, float, float],
    semantic_role: str = "fill",
    provenance: tuple[str, ...] = (),
) -> TextVectorProgram | None:
    """Exact union of pixel cells as a sealed program (plan M1).

    ``straight_rgba`` is the legacy display-space colour (channels in [0,1]);
    the serialized fill is byte-identical to ``export_writer._paint``.
    """
    runs = mask_runs(mask)
    if not runs:
        return None
    paths = tuple(
        _rectangle_path(
            f"run-{index:06d}", float(start), float(y), float(end),
            float(y + 1),
        )
        for index, (y, start, end) in enumerate(runs)
    )
    layer = VectorPaintLayer(
        id="fill-0", path_ids=tuple(path.id for path in paths),
        paint=solid_paint_from_straight_rgba(straight_rgba), z_index=0,
        semantic_role=semantic_role,
    )
    return seal_program(TextVectorProgram(
        id=program_id, source_line_id=source_line_id,
        geometry_family=FAITHFUL_FAMILY, paths=paths, layers=(layer,),
        provenance=("materialization-v2", "exact-pixel-cell-union", *provenance),
    ))


# --------------------------------------------------------------------------
# M2: the current smooth fitter, moved in front of the court
# --------------------------------------------------------------------------

_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_COMMAND = re.compile(r"[MmLlHhVvCcZz]")


def parse_path_data(data: str) -> list[list[VectorSpan]]:
    """Parse an absolute M/L/H/V/C/Z path string into closed span rings.

    Only the command set the legacy writers emit is supported; anything
    else raises, because silently dropping a command would change the
    delivered geometry.
    """
    subpaths: list[list[VectorSpan]] = []
    spans: list[VectorSpan] = []
    start: Point | None = None
    current: Point | None = None
    index = 0
    text = data.strip()

    def numbers(count: int) -> list[float]:
        nonlocal index
        values: list[float] = []
        while len(values) < count:
            match = _NUMBER.search(text, index)
            if match is None:
                raise ProgramValidationError("truncated path data")
            values.append(float(match.group(0)))
            index = match.end()
        return values

    def close_ring() -> None:
        nonlocal spans, current
        if spans and start is not None and current is not None:
            if current != start:
                spans.append(LineSpan(p0=current, p1=start))
            subpaths.append(spans)
        spans = []
        current = start

    while True:
        match = _COMMAND.search(text, index)
        if match is None:
            break
        command = match.group(0)
        index = match.end()
        if command in "Mm":
            if spans:
                close_ring()
            x, y = numbers(2)
            if command == "m" and current is not None:
                x, y = current[0] + x, current[1] + y
            start = current = (x, y)
        elif command in "Ll":
            x, y = numbers(2)
            if command == "l":
                x, y = current[0] + x, current[1] + y
            spans.append(LineSpan(p0=current, p1=(x, y)))
            current = (x, y)
        elif command in "Hh":
            (x,) = numbers(1)
            if command == "h":
                x = current[0] + x
            spans.append(LineSpan(p0=current, p1=(x, current[1])))
            current = (x, current[1])
        elif command in "Vv":
            (y,) = numbers(1)
            if command == "v":
                y = current[1] + y
            spans.append(LineSpan(p0=current, p1=(current[0], y)))
            current = (current[0], y)
        elif command in "Cc":
            x1, y1, x2, y2, x, y = numbers(6)
            if command == "c":
                x1, y1 = current[0] + x1, current[1] + y1
                x2, y2 = current[0] + x2, current[1] + y2
                x, y = current[0] + x, current[1] + y
            spans.append(CubicSpan(
                p0=current, c1=(x1, y1), c2=(x2, y2), p1=(x, y),
            ))
            current = (x, y)
        elif command in "Zz":
            close_ring()
    if spans:
        close_ring()
    return [ring for ring in subpaths if ring]


def _ring_roles(rings: list[list[VectorSpan]]) -> list[str]:
    """Even-odd nesting depth decides positive vs negative rings."""
    polygons = [
        flatten_path(
            ClosedPathProgram(
                id="probe", role="positive", spans=tuple(ring),
                fill_rule="evenodd",
            ),
            samples=8,
        )
        for ring in rings
    ]
    roles: list[str] = []
    for index, polygon in enumerate(polygons):
        probe = interior_point(polygon) if polygon else None
        if probe is None:
            roles.append("positive")
            continue
        depth = sum(
            1 for other_index, other in enumerate(polygons)
            if other_index != index and other
            and point_in_polygon(probe, other)
        )
        role = "positive" if depth % 2 == 0 else "negative"
        if role == "negative" and not any(
            point_in_polygon(probe, other)
            for other_index, other in enumerate(polygons)
            if other_index != index and other
        ):
            role = "positive"
        roles.append(role)
    return roles


def program_from_path_data(
    data: str, *, program_id: str, source_line_id: str,
    geometry_family: str,
    straight_rgba: tuple[float, float, float, float],
    fill_rule: str = "evenodd", semantic_role: str = "fill",
    provenance: tuple[str, ...] = (),
) -> TextVectorProgram | None:
    """Wrap an existing legacy path string as a sealed program."""
    rings = parse_path_data(data)
    if not rings:
        return None
    roles = _ring_roles(rings)
    paths = tuple(
        ClosedPathProgram(
            id=f"ring-{index:04d}", role=role, spans=tuple(ring),
            fill_rule=fill_rule,
        )
        for index, (ring, role) in enumerate(zip(rings, roles))
    )
    layer = VectorPaintLayer(
        id="fill-0", path_ids=tuple(path.id for path in paths),
        paint=solid_paint_from_straight_rgba(straight_rgba), z_index=0,
        semantic_role=semantic_role,
    )
    return seal_program(TextVectorProgram(
        id=program_id, source_line_id=source_line_id,
        geometry_family=geometry_family, paths=paths, layers=(layer,),
        provenance=("materialization-v2", *provenance),
    ))


def generate_legacy_smooth_program(
    mask: np.ndarray, *, program_id: str, source_line_id: str,
    straight_rgba: tuple[float, float, float, float],
    density_proof: bool = True,
    provenance: tuple[str, ...] = (),
) -> TextVectorProgram | None:
    """The current ``_fitted_mask_path`` route as a pre-court candidate.

    The math is untouched (plan M2: architecture change, not math change);
    only its position moves - from "exporter decides" to "one candidate
    among several, judged before delivery".
    """
    from .export_writer import _fitted_mask_path

    data = _fitted_mask_path(np.asarray(mask, bool), density_proof=density_proof)
    if not data:
        return None
    return program_from_path_data(
        data, program_id=program_id, source_line_id=source_line_id,
        geometry_family=LEGACY_SMOOTH_FAMILY, straight_rgba=straight_rgba,
        provenance=("legacy-g1-fitter", "court-proven-g1", *provenance),
    )


def resource_estimate_for(
    program: TextVectorProgram, *, exact_render_pixels: int = 0,
    fit_milliseconds: float = 0.0,
) -> ResourceEstimate:
    return ResourceEstimate(
        span_count=sum(len(path.spans) for path in program.paths),
        path_count=len(program.paths),
        layer_count=len(program.layers),
        exact_render_pixels=int(exact_render_pixels),
        fit_milliseconds=float(fit_milliseconds),
    )

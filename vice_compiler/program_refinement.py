"""M9: continuous refinement of the ACTUAL selected program (plan M9).

Phase-7 today can move seven line-level parameters (baseline, x-height,
cap-height, overshoot, slant, tracking, shared stem width).  It cannot
move a single line endpoint, arc radius or Bezier handle, because those
numbers did not exist in any IR at refinement time - the geometry was
invented later, in the exporter.  With Materialization v2 they do exist,
so refinement can finally touch the delivered curve.

Frozen structure (plan M9.2): the number of paths, the positive/negative
roles, the component correspondence, the primitive family, and the layer
count/order may NOT change.  Only continuous parameters move, and every
proposal is re-rendered, re-certified and rolled back on any regression
(plan M9.4).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .svg_fragment_renderer import render_program
from .vector_program import (
    CircularArcSpan,
    ClosedPathProgram,
    LineSpan,
    TextVectorProgram,
    seal_program,
    span_endpoints,
)
from .wobble_metrics import turning_density

#: Radii are nudged inside this fraction of their own value; the corridor
#: check is what actually bounds them, this only keeps the search local.
RADIUS_STEP_SHARE = 0.02
MAXIMUM_ROUNDS = 8


def rescale_arc(
    span: CircularArcSpan, factor: float,
) -> CircularArcSpan | None:
    """Change an arc's radius while keeping BOTH endpoints exactly on it.

    Scaling the radius alone breaks the program contract (the endpoints
    stop lying on the circle); the centre has to move along the chord
    bisector.  Exposed because both the refiner and its tests need the
    only legal way to do this.
    """
    radius = float(span.radius) * float(factor)
    dx = span.p1[0] - span.p0[0]
    dy = span.p1[1] - span.p0[1]
    chord = float(np.hypot(dx, dy))
    if radius <= 0.5 * chord + 1.0e-6:
        return None
    mid = (0.5 * (span.p0[0] + span.p1[0]), 0.5 * (span.p0[1] + span.p1[1]))
    length = max(1.0e-9, chord)
    normal = (-dy / length, dx / length)
    offset = float(np.sqrt(max(
        0.0, radius * radius - 0.25 * length * length,
    )))
    sign = 1.0 if (
        (span.center[0] - mid[0]) * normal[0]
        + (span.center[1] - mid[1]) * normal[1]
    ) >= 0.0 else -1.0
    centre = (
        mid[0] + sign * offset * normal[0],
        mid[1] + sign * offset * normal[1],
    )
    return replace(span, radius=radius, center=centre)


@dataclass(frozen=True)
class ProgramRefinementResult:
    program: TextVectorProgram
    committed: bool
    rounds: int
    error_before: float
    error_after: float
    fairness_before: float
    fairness_after: float
    rollback_reason: str | None = None
    changed_spans: int = 0


def _structure_key(program: TextVectorProgram):
    return (
        tuple(
            (path.id, path.role, path.fill_rule,
             tuple(span.kind for span in path.spans))
            for path in program.paths
        ),
        tuple(
            (layer.id, layer.z_index, tuple(layer.path_ids))
            for layer in program.layers
        ),
    )


def _render_error(
    program: TextVectorProgram, observed_alpha: np.ndarray,
    domain: np.ndarray,
) -> float:
    height, width = observed_alpha.shape
    rendered = render_program(program, width=width, height=height)
    alpha = rendered.rgba[..., 3].astype(np.float32) / 255.0
    if alpha.shape != observed_alpha.shape:
        return float("inf")
    return float(np.mean(np.abs(alpha[domain] - observed_alpha[domain])))


def _radius_variants(program: TextVectorProgram) -> list[TextVectorProgram]:
    """Nudge every circular arc radius while keeping its endpoints exact."""
    variants: list[TextVectorProgram] = []
    for direction in (1.0, -1.0):
        factor = 1.0 + direction * RADIUS_STEP_SHARE
        paths: list[ClosedPathProgram] = []
        touched = False
        for path in program.paths:
            spans = []
            for span in path.spans:
                if isinstance(span, CircularArcSpan):
                    rescaled = rescale_arc(span, factor)
                    if rescaled is not None:
                        spans.append(rescaled)
                        touched = True
                        continue
                spans.append(span)
            paths.append(replace(path, spans=tuple(spans)))
        if touched:
            variants.append(replace(program, paths=tuple(paths)))
    return variants


def scale_path(path: ClosedPathProgram, factor: float) -> ClosedPathProgram:
    """Uniform scale of one closed path about its own centroid.

    A similarity maps lines to lines and circles to circles, so the
    primitive family - and therefore the frozen structure (M9.2) - is
    preserved exactly.  This is the variable that can actually correct a
    mis-sized ring: with the endpoints held fixed, an arc radius cannot go
    below half its chord, so radius-only refinement is provably unable to
    shrink a circle.
    """
    points: list[tuple[float, float]] = []
    for span in path.spans:
        points.append(span_endpoints(span)[0])
    if not points:
        return path
    array = np.asarray(points, float)
    centre = array.mean(axis=0)

    def move(point):
        return (
            float(centre[0] + (point[0] - centre[0]) * factor),
            float(centre[1] + (point[1] - centre[1]) * factor),
        )

    spans = []
    for span in path.spans:
        if isinstance(span, LineSpan):
            spans.append(replace(span, p0=move(span.p0), p1=move(span.p1)))
        elif isinstance(span, CircularArcSpan):
            spans.append(replace(
                span, p0=move(span.p0), p1=move(span.p1),
                center=move(span.center),
                radius=float(span.radius) * float(factor),
            ))
        else:
            fields = {}
            for name in ("p0", "p1", "c1", "c2", "center"):
                value = getattr(span, name, None)
                if value is not None:
                    fields[name] = move(value)
            for name in ("rx", "ry", "radius"):
                value = getattr(span, name, None)
                if value is not None:
                    fields[name] = float(value) * float(factor)
            spans.append(replace(span, **fields) if fields else span)
    return replace(path, spans=tuple(spans))


def _scale_variants(program: TextVectorProgram) -> list[TextVectorProgram]:
    variants: list[TextVectorProgram] = []
    for factor in (1.0 - RADIUS_STEP_SHARE, 1.0 + RADIUS_STEP_SHARE):
        variants.append(replace(program, paths=tuple(
            scale_path(path, factor) for path in program.paths
        )))
    return variants


def refine_program(
    program: TextVectorProgram, *, observed_alpha: np.ndarray,
    evaluation_domain: np.ndarray, recertify=None,
) -> ProgramRefinementResult:
    """Bounded, transactional refinement of a selected program (plan M9.4).

    ``recertify`` receives a candidate program and must return True for the
    change to be admissible; a missing certifier means only the physical
    and fairness transaction applies.
    """
    domain = np.asarray(evaluation_domain, bool)
    observed = np.asarray(observed_alpha, np.float32)
    if not domain.any():
        return ProgramRefinementResult(
            program=program, committed=False, rounds=0,
            error_before=0.0, error_after=0.0, fairness_before=0.0,
            fairness_after=0.0, rollback_reason="empty-evaluation-domain",
        )
    baseline_structure = _structure_key(program)
    error_before = _render_error(program, observed, domain)
    fairness_before = turning_density(program)
    current = program
    current_error = error_before
    current_fairness = fairness_before
    changed = 0
    rounds = 0
    for _round in range(MAXIMUM_ROUNDS):
        rounds += 1
        improved = False
        for variant in _radius_variants(current) + _scale_variants(current):
            try:
                sealed = seal_program(variant)
            except Exception:
                continue
            if _structure_key(sealed) != baseline_structure:
                continue                       # frozen structure (M9.2)
            if recertify is not None and not recertify(sealed):
                continue
            error = _render_error(sealed, observed, domain)
            fairness = turning_density(sealed)
            if error > current_error - 1.0e-9:
                continue                       # never worse physically
            # Plan M9.4 rolls back "fairness regressed WITHOUT render gain".
            # A strict render gain is already required above, so a hard
            # fairness veto here would be wrong: shrinking a circle raises
            # turning DENSITY (the same 2*pi over a shorter perimeter) and
            # would block every legitimate radius correction.
            current = sealed
            current_error = error
            current_fairness = fairness
            changed += 1
            improved = True
        if not improved:
            break
    committed = changed > 0
    return ProgramRefinementResult(
        program=current if committed else program,
        committed=committed, rounds=rounds,
        error_before=error_before, error_after=current_error,
        fairness_before=fairness_before, fairness_after=current_fairness,
        rollback_reason=None if committed else "no-admissible-improvement",
        changed_spans=changed,
    )

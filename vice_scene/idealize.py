"""Evidence-budgeted symmetry, repetition, equal-radius, and fairing passes."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

import cv2
import numpy as np

from .contracts import ConstraintEdge, GeometryPrimitive, SceneGraph


@dataclass(frozen=True)
class IdealizationAudit:
    action: str
    accepted: bool
    score_before: float
    score_after: float
    affected: tuple[str, ...]


ScoreFunction = Callable[[SceneGraph], float]


def idealize_scene(graph: SceneGraph, score: ScoreFunction,
                   *, accuracy_budget: float = 0.0015,
                   symmetry_evidence: np.ndarray | None = None
                   ) -> tuple[SceneGraph, tuple[IdealizationAudit, ...]]:
    incumbent = graph
    incumbent_score = score(graph)
    audits: list[IdealizationAudit] = []
    # A nearly-square, maximally-rounded box is a common digital preimage of a
    # circle. Court explicit circle radii instead of exporting four fake flats.
    for shape in tuple(incumbent.shapes):
        trials = _circle_intent_trials(incumbent, shape.id)
        if not trials:
            continue
        scored = [(score(trial), trial) for trial in trials]
        trial_score, trial = min(scored, key=lambda row: row[0])
        accepted = trial_score <= incumbent_score + accuracy_budget
        audits.append(IdealizationAudit("rounded-square-to-circle", accepted,
                                        incumbent_score, trial_score, (shape.id,)))
        if accepted:
            incumbent, incumbent_score = trial, trial_score
    # Equal-radius constraints become geometry, not metadata only.
    for constraint in graph.constraints:
        if constraint.kind != "equal-radius":
            continue
        trial = _snap_equal_radii(incumbent, constraint.members)
        if trial == incumbent:
            continue
        trial_score = score(trial)
        accepted = trial_score <= incumbent_score + accuracy_budget
        audits.append(IdealizationAudit("equal-radius", accepted, incumbent_score,
                                        trial_score, constraint.members))
        if accepted:
            incumbent, incumbent_score = trial, trial_score
    # Free polygonal loops get one uncertainty-style fairing/simplification
    # proposal; the render budget owns accept/reject.
    for shape in incumbent.shapes:
        if shape.model_family not in {"generic", "glyph", "ribbon"}:
            continue
        trial = _fair_shape(incumbent, shape.id)
        if trial == incumbent:
            continue
        trial_score = score(trial)
        accepted = trial_score <= incumbent_score + accuracy_budget
        audits.append(IdealizationAudit("fair-polyline", accepted, incumbent_score,
                                        trial_score, (shape.id,)))
        if accepted:
            incumbent, incumbent_score = trial, trial_score
    symmetry = _detect_pair_symmetry(incumbent)
    symmetry_support = (float(np.mean(symmetry_evidence))
                        if symmetry_evidence is not None else 0.0)
    if symmetry_support >= .55:
        for constraint in symmetry:
            trial = _snap_mirror_pair(incumbent, constraint.members)
            if trial == incumbent:
                continue
            trial_score = score(trial)
            accepted = trial_score <= incumbent_score + accuracy_budget
            audits.append(IdealizationAudit("mirror-symmetry", accepted,
                                            incumbent_score, trial_score,
                                            constraint.members))
            if accepted:
                incumbent = replace(
                    trial,
                    constraints=trial.constraints + (replace(
                        constraint,
                        evidence=constraint.evidence + ("symmetry_evidence",)),),
                )
                incumbent_score = trial_score
    incumbent.validate()
    return incumbent, tuple(audits)


def _circle_intent_trials(graph: SceneGraph, shape_id: str) -> tuple[SceneGraph, ...]:
    shape_index = next(index for index, item in enumerate(graph.shapes)
                       if item.id == shape_id)
    shape = graph.shapes[shape_index]
    if shape.negative_loops:
        return ()
    loop_index = next(index for index, item in enumerate(graph.loops)
                      if item.id == shape.positive_loop)
    loop = graph.loops[loop_index]
    if len(loop.primitives) != 1:
        return ()
    primitive = loop.primitives[0]
    if primitive.kind != "rounded-rect":
        return ()
    cx, cy, width, height, _angle, radius = primitive.parameters
    if max(width, height) / max(min(width, height), 1e-6) > 1.08:
        return ()
    if radius < .72 * (.5 * min(width, height)):
        return ()
    base_radius = .25 * (width + height)
    results = []
    for correction in (0.0, .2, .4, .6):
        trial_radius = base_radius + correction
        circle = GeometryPrimitive(
            "circle", (cx, cy, trial_radius), confidence=primitive.confidence,
            evidence_rms_px=primitive.evidence_rms_px,
            provenance=primitive.provenance + ("rounded-square-circle-intent",),
        )
        loops = list(graph.loops)
        loops[loop_index] = replace(loop, primitives=(circle,))
        shapes = list(graph.shapes)
        shapes[shape_index] = replace(
            shape, model_family="circle", model_params=circle.parameters,
            provenance=shape.provenance + ("circle-intent-court",),
        )
        results.append(replace(graph, loops=tuple(loops), shapes=tuple(shapes)))
    return tuple(results)


def _snap_equal_radii(graph: SceneGraph, members: tuple[str, ...]) -> SceneGraph:
    shape_by_id = {shape.id: shape for shape in graph.shapes}
    loop_index = {loop.id: index for index, loop in enumerate(graph.loops)}
    rows = []
    for shape_id in members:
        shape = shape_by_id.get(shape_id)
        if shape is None:
            continue
        loop = graph.loops[loop_index[shape.positive_loop]]
        if len(loop.primitives) == 1 and loop.primitives[0].kind == "circle":
            rows.append((loop_index[shape.positive_loop], loop.primitives[0]))
    if len(rows) < 2:
        return graph
    radius = float(np.median([primitive.parameters[2] for _, primitive in rows]))
    loops = list(graph.loops)
    for index, primitive in rows:
        params = primitive.parameters[:2] + (radius,)
        loops[index] = replace(loops[index], primitives=(replace(
            primitive, parameters=params,
            provenance=primitive.provenance + ("equal-radius-snap",)),))
    return replace(graph, loops=tuple(loops))


def _fair_shape(graph: SceneGraph, shape_id: str) -> SceneGraph:
    shape = next(item for item in graph.shapes if item.id == shape_id)
    loop_index = next(index for index, loop in enumerate(graph.loops) if loop.id == shape.positive_loop)
    loop = graph.loops[loop_index]
    if len(loop.primitives) != 1 or loop.primitives[0].kind != "polyline":
        return graph
    primitive = loop.primitives[0]
    points = np.asarray(primitive.points, np.float32)
    if len(points) < 7:
        return graph
    closed = np.linalg.norm(points[0] - points[-1]) < 1e-5
    perimeter = cv2.arcLength(points.reshape(-1, 1, 2), closed)
    simplified = cv2.approxPolyDP(points.reshape(-1, 1, 2), max(.15, .0025 * perimeter),
                                  closed)[:, 0, :]
    if closed and np.linalg.norm(simplified[0] - simplified[-1]) > 1e-5:
        simplified = np.vstack((simplified, simplified[0]))
    if len(simplified) >= len(points):
        return graph
    new_primitive = replace(primitive,
                            points=tuple((float(x), float(y)) for x, y in simplified),
                            provenance=primitive.provenance + ("evidence-budgeted-fairing",))
    loops = list(graph.loops)
    loops[loop_index] = replace(loop, primitives=(new_primitive,))
    return replace(graph, loops=tuple(loops))


def _detect_pair_symmetry(graph: SceneGraph) -> tuple[ConstraintEdge, ...]:
    boxes = {}
    loop_by_id = {loop.id: loop for loop in graph.loops}
    for shape in graph.shapes:
        points = []
        for primitive in loop_by_id[shape.positive_loop].primitives:
            if primitive.points:
                points.extend(primitive.points)
            elif primitive.kind in {"circle", "ellipse", "rect", "rounded-rect"}:
                cx, cy = primitive.parameters[:2]
                extent_x = primitive.parameters[2]
                extent_y = primitive.parameters[2] if primitive.kind == "circle" else primitive.parameters[3]
                points.extend(((cx - extent_x, cy - extent_y), (cx + extent_x, cy + extent_y)))
        if points:
            value = np.asarray(points)
            boxes[shape.id] = (value[:, 0].min(), value[:, 1].min(), value[:, 0].max(), value[:, 1].max())
    constraints = []
    axis = graph.width * .5
    used = set()
    for left_id, left in boxes.items():
        if left_id in used:
            continue
        mirrored_center = 2 * axis - .5 * (left[0] + left[2])
        for right_id, right in boxes.items():
            if right_id == left_id or right_id in used:
                continue
            if abs(mirrored_center - .5 * (right[0] + right[2])) <= .5:
                if abs((left[2] - left[0]) - (right[2] - right[0])) <= .5 and abs((left[3] - left[1]) - (right[3] - right[1])) <= .5:
                    constraints.append(ConstraintEdge(
                        f"constraint-mirror-{len(constraints)}", "mirror-symmetry",
                        (left_id, right_id), .7, ("group-bbox-symmetry",),
                    ))
                    used.update((left_id, right_id))
                    break
    return tuple(constraints)


def _snap_mirror_pair(graph: SceneGraph,
                      members: tuple[str, ...]) -> SceneGraph:
    if len(members) != 2:
        return graph
    shape_by_id = {shape.id: shape for shape in graph.shapes}
    loop_index = {loop.id: index for index, loop in enumerate(graph.loops)}
    rows = []
    for shape_id in members:
        shape = shape_by_id.get(shape_id)
        if shape is None:
            return graph
        index = loop_index[shape.positive_loop]
        loop = graph.loops[index]
        if len(loop.primitives) != 1:
            return graph
        primitive = loop.primitives[0]
        if primitive.kind not in {"circle", "ellipse", "rect", "rounded-rect"}:
            return graph
        rows.append((shape, index, primitive))
    if rows[0][2].kind != rows[1][2].kind:
        return graph
    rows.sort(key=lambda row: row[2].parameters[0])
    left, right = rows
    axis = graph.width * .5
    left_params = np.asarray(left[2].parameters, np.float64)
    right_params = np.asarray(right[2].parameters, np.float64)
    distance = .5 * ((axis - left_params[0]) + (right_params[0] - axis))
    center_y = .5 * (left_params[1] + right_params[1])
    left_params[0], right_params[0] = axis - distance, axis + distance
    left_params[1] = right_params[1] = center_y
    if left[2].kind == "circle":
        radius = .5 * (left_params[2] + right_params[2])
        left_params[2] = right_params[2] = radius
    else:
        left_params[2:4] = right_params[2:4] = .5 * (
            left_params[2:4] + right_params[2:4])
        mirrored_angle = .5 * (left_params[4] - right_params[4])
        left_params[4], right_params[4] = mirrored_angle, -mirrored_angle
        if left[2].kind == "rounded-rect":
            radius = .5 * (left_params[5] + right_params[5])
            left_params[5] = right_params[5] = radius
    loops = list(graph.loops)
    shapes = list(graph.shapes)
    for shape, index, primitive, params in (
            (*left, left_params), (*right, right_params)):
        updated = replace(
            primitive, parameters=tuple(float(value) for value in params),
            points=(), provenance=primitive.provenance + ("mirror-symmetry-snap",),
        )
        loops[index] = replace(loops[index], primitives=(updated,))
        shape_index = next(i for i, item in enumerate(shapes) if item.id == shape.id)
        shapes[shape_index] = replace(
            shapes[shape_index], model_params=updated.parameters,
            provenance=shapes[shape_index].provenance + ("mirror-symmetry-snap",),
        )
    result = replace(graph, loops=tuple(loops), shapes=tuple(shapes))
    result.validate()
    return result

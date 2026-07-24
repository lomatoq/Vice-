"""Assemble immutable shapes, loops, interfaces, layers, and constraints."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace

import cv2
import numpy as np

from .appearance import AppearanceHypotheses, fit_region_appearance
from .boundary_solver import solve_shared_interfaces
from .contracts import (Appearance, ConstraintEdge, LayerEdge, LoopNode,
                        SceneGraph, ShapeNode)
from .corner_graph import build_corner_graph
from .evidence_model import EvidenceBundle
from .ingest import CanonicalRaster
from .shape_models import (ShapeCandidate, generic_region_candidate,
                           primitive_points, tournament_region)
from .topology import TopologyHypothesis


@dataclass(frozen=True)
class SceneBuildResult:
    graph: SceneGraph
    alternatives: dict[str, tuple[ShapeCandidate, ...]]
    selected: dict[str, ShapeCandidate]
    topology_id: str
    # Keep the topology proposal's evidence/complexity cost in the global
    # court.  Previously it was recorded in the trace but silently discarded
    # when scene hypotheses were compared.
    topology_score: float = 0.0


@dataclass
class SceneBuildCache:
    """Per-image fits reused by topologies that contain identical regions."""
    appearances: dict[tuple, Appearance] = field(default_factory=dict)
    tournaments: dict[tuple, tuple[ShapeCandidate, tuple[ShapeCandidate, ...]]] = field(
        default_factory=dict)


def build_scene_graph(raster: CanonicalRaster, topology: TopologyHypothesis,
                      appearance_hypotheses: AppearanceHypotheses,
                      evidence: EvidenceBundle, *, allow_gradients: bool = True,
                      whole_shapes: bool = True,
                      shared_boundaries: bool = True,
                      cache: SceneBuildCache | None = None) -> SceneBuildResult:
    uncertainty = evidence.levels[0].heads["uncertainty"]
    boundary = evidence.levels[0].heads["boundary_prob"]
    subpixel = evidence.levels[0].heads["subpixel_offset"]
    shape_logits = evidence.levels[0].heads["shape_class_logits"]
    fit_cache = cache or SceneBuildCache()
    appearances: list[Appearance] = []
    loops: list[LoopNode] = []
    shapes: list[ShapeNode] = []
    selected: dict[str, ShapeCandidate] = {}
    alternatives: dict[str, tuple[ShapeCandidate, ...]] = {}
    topology_to_shape: dict[str, str] = {}

    for index, region in enumerate(topology.regions):
        shape_id = f"shape-{index}"
        topology_to_shape[region.id] = shape_id
        base_appearance = appearance_hypotheses.appearances[region.appearance_index]
        appearance_id = f"appearance-shape-{index}"
        mask_key = _region_cache_key(region)
        appearance_key = (mask_key, region.appearance_index, bool(allow_gradients))
        appearance = fit_cache.appearances.get(appearance_key)
        if appearance is None:
            appearance = fit_region_appearance(
                raster, region.mask, replace(base_appearance, id=appearance_id),
                allow_gradient=allow_gradients,
            )
            fit_cache.appearances[appearance_key] = appearance
        else:
            appearance = replace(appearance, id=appearance_id)
        appearances.append(appearance)

        prior = (np.mean(shape_logits[region.mask], axis=0)
                 if np.any(region.mask) else np.zeros(4, np.float32))
        tournament_key = (mask_key, bool(whole_shapes))
        tournament = fit_cache.tournaments.get(tournament_key)
        if tournament is None:
            if whole_shapes:
                tournament = tournament_region(
                    region, uncertainty=uncertainty, shape_prior=prior)
            else:
                generic = generic_region_candidate(
                    region, uncertainty=uncertainty, shape_prior=prior)
                tournament = (generic, (generic,))
            fit_cache.tournaments[tournament_key] = tournament
        best, ranked = tournament
        selected[shape_id] = best
        alternatives[shape_id] = ranked
        positive_id = f"loop-{index}-positive"
        loops.append(LoopNode(
            id=positive_id, primitives=best.positive, orientation=1,
            signed_area=abs(_geometry_area(best.positive)),
        ))
        negative_ids = []
        for hole_index, geometry in enumerate(best.negatives):
            loop_id = f"loop-{index}-negative-{hole_index}"
            negative_ids.append(loop_id)
            loops.append(LoopNode(id=loop_id, primitives=geometry, orientation=-1,
                                  signed_area=-abs(_geometry_area(geometry))))
        shapes.append(ShapeNode(
            id=shape_id, topology_id=region.id, appearance_id=appearance_id,
            positive_loop=positive_id, negative_loops=tuple(negative_ids),
            parent=None, layer=index, model_family=best.family,
            model_params=best.parameters, confidence=min(region.confidence, best.confidence),
            provenance=(topology.id, *topology.operations, "whole-shape-tournament"),
        ))

    shapes = [replace(shape, parent=topology_to_shape.get(topology.regions[index].parent))
              for index, shape in enumerate(shapes)]
    shape_ids = tuple(shape.id for shape in shapes)
    interfaces = solve_shared_interfaces(
        topology, shape_ids, boundary, subpixel) if shared_boundaries else ()
    interfaces, corners = build_corner_graph(interfaces)
    constraints = list(_initial_constraints(shapes, selected))
    layer_edges = tuple(LayerEdge(shape_ids[index], shape_ids[index + 1])
                        for index in range(max(0, len(shape_ids) - 1)))
    graph = SceneGraph(
        width=raster.width, height=raster.height,
        appearances=tuple(appearances), loops=tuple(loops), shapes=tuple(shapes),
        interfaces=interfaces, corners=corners, constraints=tuple(constraints),
        layer_edges=layer_edges,
    )
    graph.validate()
    return SceneBuildResult(graph, alternatives, selected, topology.id,
                            topology.score)


def _region_cache_key(region) -> str:
    digest = hashlib.sha1()
    digest.update(np.asarray(region.mask, np.uint8).tobytes())
    digest.update(int(region.appearance_index).to_bytes(4, "little", signed=False))
    if region.soft_membership is not None:
        digest.update(np.asarray(region.soft_membership, np.float32).tobytes())
    return digest.hexdigest()


def replace_shape_candidate(graph: SceneGraph, shape_id: str,
                            candidate: ShapeCandidate) -> SceneGraph:
    shapes = list(graph.shapes)
    loops = list(graph.loops)
    shape_index = next(index for index, shape in enumerate(shapes) if shape.id == shape_id)
    shape = shapes[shape_index]
    positive_index = next(index for index, loop in enumerate(loops) if loop.id == shape.positive_loop)
    loops[positive_index] = replace(loops[positive_index], primitives=candidate.positive,
                                    signed_area=abs(_geometry_area(candidate.positive)))
    negative_ids = list(shape.negative_loops)
    if len(candidate.negatives) == len(negative_ids):
        for loop_id, geometry in zip(negative_ids, candidate.negatives):
            loop_index = next(index for index, loop in enumerate(loops) if loop.id == loop_id)
            loops[loop_index] = replace(loops[loop_index], primitives=geometry,
                                        signed_area=-abs(_geometry_area(geometry)))
    shapes[shape_index] = replace(shape, model_family=candidate.family,
                                  model_params=candidate.parameters,
                                  confidence=candidate.confidence,
                                  provenance=shape.provenance + ("candidate-replacement",))
    result = replace(graph, loops=tuple(loops), shapes=tuple(shapes))
    result.validate()
    return result


def _geometry_area(geometry: tuple) -> float:
    points = []
    for primitive in geometry:
        sampled = primitive_points(primitive, 96)
        if len(sampled):
            if points and np.linalg.norm(np.asarray(points[-1]) - sampled[0]) < 1e-5:
                sampled = sampled[1:]
            points.extend(sampled.tolist())
    if len(points) < 3:
        return 0.0
    contour = np.asarray(points, np.float32)
    return float(cv2.contourArea(contour, oriented=True))


def _initial_constraints(shapes: list[ShapeNode],
                         selected: dict[str, ShapeCandidate]) -> tuple[ConstraintEdge, ...]:
    constraints: list[ConstraintEdge] = []
    radius_rows: list[tuple[str, float]] = []
    for shape in shapes:
        candidate = selected[shape.id]
        if candidate.family in {"circle", "ring"} and len(candidate.parameters) >= 3:
            radius_rows.append((shape.id, candidate.parameters[2]))
    used: set[str] = set()
    for index, (shape_id, radius) in enumerate(radius_rows):
        if shape_id in used:
            continue
        family = [(other_id, other_radius) for other_id, other_radius in radius_rows
                  if abs(other_radius - radius) <= max(.25, .04 * max(radius, other_radius))]
        if len(family) >= 2:
            members = tuple(item[0] for item in family)
            used.update(members)
            constraints.append(ConstraintEdge(
                id=f"constraint-equal-radius-{index}", kind="equal-radius",
                members=members, weight_or_hardness=0.8,
                evidence=("whole-shape-family", "repeated-dimension",),
            ))
    return tuple(constraints)

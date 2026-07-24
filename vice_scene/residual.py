"""Residual-driven missing-shape proposals followed by unsupported-shape pruning."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

import cv2
import numpy as np

from .contracts import Appearance, LayerEdge, LoopNode, SceneGraph, ShapeNode
from .ingest import CanonicalRaster, srgb_to_linear
from .render_models import render_scene
from .shape_models import tournament_region
from .topology import RegionProposal


@dataclass(frozen=True)
class ResidualAudit:
    action: str
    accepted: bool
    score_before: float
    score_after: float
    area_px: int
    reason: str


ScoreFunction = Callable[[SceneGraph], float]


def residual_add_prune(graph: SceneGraph, raster: CanonicalRaster, score: ScoreFunction,
                       *, threshold: float = .12, min_area_px: int = 2,
                       max_additions: int = 4,
                       max_attempts: int = 8) -> tuple[SceneGraph, tuple[ResidualAudit, ...]]:
    incumbent = graph
    incumbent_score = score(graph)
    audits: list[ResidualAudit] = []
    rendered = render_scene(graph)
    render_rgb = srgb_to_linear(rendered[..., :3].astype(np.float32) / 255.0)
    render_alpha = rendered[..., 3].astype(np.float32) / 255.0
    target_rgb = raster.rgba_linear_premul[..., :3]
    target_alpha = raster.rgba_linear_premul[..., 3]
    border = np.concatenate((target_rgb[0], target_rgb[-1], target_rgb[:, 0], target_rgb[:, -1]), axis=0)
    background = np.median(border, axis=0)
    transparency_present = bool(np.mean(target_alpha < .999) > 1e-4)
    if transparency_present:
        residual = np.linalg.norm(target_rgb - render_rgb * render_alpha[..., None], axis=2)
        residual += .5 * np.abs(target_alpha - render_alpha)
    else:
        composite = (render_rgb * render_alpha[..., None]
                     + background * (1.0 - render_alpha[..., None]))
        residual = np.linalg.norm(target_rgb - composite, axis=2)
    proposals = residual > threshold
    proposals &= cv2.morphologyEx(proposals.astype(np.uint8), cv2.MORPH_OPEN,
                                  np.ones((2, 2), np.uint8)) > 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats(proposals.astype(np.uint8), 8)
    order = sorted(range(1, count), key=lambda index: int(stats[index, cv2.CC_STAT_AREA]), reverse=True)
    additions = 0
    attempts = 0
    for component in order:
        area = int(stats[component, cv2.CC_STAT_AREA])
        if area < min_area_px:
            continue
        if additions >= max_additions or attempts >= max_attempts:
            break
        attempts += 1
        mask = labels == component
        # Residual repair is a local missing-detail stage, never a second
        # whole-image topology pass.  When the incumbent is already poor, a
        # giant background-coloured top layer can lower pixel loss by erasing
        # the scene; that created the observed full-canvas artifact shapes.
        if area > .35 * raster.width * raster.height:
            audits.append(ResidualAudit(
                "add", False, incumbent_score, incumbent_score, area,
                "broad residual belongs to topology/background, not local repair"))
            continue
        # Exclude broad codec/AA bands: a supported new object should have a
        # compact interior, not merely hug every existing edge.
        x, y, w, h = (int(v) for v in stats[component, :4])
        compactness = area / max(1, w * h)
        if compactness < .16 and min(w, h) <= 2:
            audits.append(ResidualAudit("add", False, incumbent_score, incumbent_score,
                                        area, "thin AA/JPEG-like residual"))
            continue
        region = _region_from_mask(mask, component)
        best, _ = tournament_region(region, uncertainty=None)
        trial = _add_shape(incumbent, raster, region, best)
        trial_score = score(trial)
        # A new object must pay its full description length.  Without this term
        # three 5--16px patches could improve pixel NLL by fractions and recreate
        # exactly the coloured barnacles the residual pass is meant to reject.
        effective_trial = trial_score + float(best.mdl) + .001
        accepted = effective_trial + 1e-9 < incumbent_score
        audits.append(ResidualAudit("add", accepted, incumbent_score, effective_trial,
                                    area, "forward loss + topology/MDL court"))
        if accepted:
            incumbent, incumbent_score = trial, trial_score
            additions += 1
    # Prune only weak residual-added or extremely unsupported shapes.  Original
    # topology is not silently erased just because another layer can cover it.
    for shape in tuple(incumbent.shapes):
        if "residual-add" not in shape.provenance and shape.confidence >= .08:
            continue
        trial = _remove_shape(incumbent, shape.id)
        trial_score = score(trial)
        accepted = trial_score <= incumbent_score + 1e-6
        audits.append(ResidualAudit("prune", accepted, incumbent_score, trial_score,
                                    0, f"unsupported shape {shape.id}"))
        if accepted:
            incumbent, incumbent_score = trial, trial_score
    incumbent.validate()
    return incumbent, tuple(audits)


def _region_from_mask(mask: np.ndarray, component: int) -> RegionProposal:
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP,
                                            cv2.CHAIN_APPROX_NONE)
    hierarchy_row = hierarchy[0] if hierarchy is not None else np.empty((0, 4), int)
    outer = max((i for i, row in enumerate(hierarchy_row) if row[3] < 0),
                key=lambda i: abs(cv2.contourArea(contours[i])), default=0)
    positive = contours[outer][:, 0, :].astype(np.float32) + .5
    negatives = tuple(contours[i][:, 0, :].astype(np.float32) + .5
                      for i, row in enumerate(hierarchy_row) if row[3] == outer)
    y, x = np.nonzero(mask)
    return RegionProposal(
        id=f"residual-region-{component}", appearance_index=0, mask=mask,
        area_px=float(mask.sum()), bbox=(int(x.min()), int(y.min()), int(x.max() + 1), int(y.max() + 1)),
        positive_contour=positive, negative_contours=negatives,
        parent=None, confidence=.5,
    )


def _add_shape(graph: SceneGraph, raster: CanonicalRaster, region: RegionProposal, candidate) -> SceneGraph:
    index = len(graph.shapes)
    appearance_id = f"appearance-residual-{index}"
    pixels = raster.rgba_linear_premul[region.mask]
    rgba = tuple(float(v) for v in np.median(pixels, axis=0))
    if rgba[3] > 1e-6:
        rgba = tuple(float(v) for v in (np.asarray(rgba[:3]) / rgba[3])) + (rgba[3],)
    appearance = Appearance(appearance_id, "solid", rgba,
                            confidence=.5, provenance=("residual-color",))
    positive_id = f"loop-residual-{index}-positive"
    loops = list(graph.loops) + [LoopNode(positive_id, candidate.positive, 1,
                                             float(region.area_px))]
    negative_ids = []
    for hole_index, geometry in enumerate(candidate.negatives):
        loop_id = f"loop-residual-{index}-negative-{hole_index}"
        negative_ids.append(loop_id)
        loops.append(LoopNode(loop_id, geometry, -1, -1.0))
    shape_id = f"shape-residual-{index}"
    shape = ShapeNode(
        id=shape_id, topology_id=region.id, appearance_id=appearance_id,
        positive_loop=positive_id, negative_loops=tuple(negative_ids),
        layer=max((item.layer for item in graph.shapes), default=-1) + 1,
        model_family=candidate.family, model_params=candidate.parameters,
        confidence=candidate.confidence,
        provenance=("residual-add", "forward-loss-court",),
    )
    layer_edges = graph.layer_edges
    if graph.shapes:
        top = max(graph.shapes, key=lambda item: item.layer)
        layer_edges += (LayerEdge(top.id, shape_id),)
    result = replace(graph, appearances=graph.appearances + (appearance,),
                     loops=tuple(loops), shapes=graph.shapes + (shape,),
                     layer_edges=layer_edges)
    result.validate()
    return result


def _remove_shape(graph: SceneGraph, shape_id: str) -> SceneGraph:
    shape = next(item for item in graph.shapes if item.id == shape_id)
    loop_ids = {shape.positive_loop, *shape.negative_loops}
    appearances_in_use = {item.appearance_id for item in graph.shapes if item.id != shape_id}
    interfaces = tuple(item for item in graph.interfaces
                       if item.left_shape != shape_id and item.right_shape != shape_id)
    interface_ids = {item.id for item in interfaces}
    corners = tuple(replace(item, incident_interfaces=tuple(
        edge for edge in item.incident_interfaces if edge in interface_ids))
        for item in graph.corners
        if any(edge in interface_ids for edge in item.incident_interfaces))
    corner_ids = {item.id for item in corners}
    interfaces = tuple(replace(item, corner_nodes=tuple(
        corner for corner in item.corner_nodes if corner in corner_ids))
        for item in interfaces)
    return replace(
        graph,
        appearances=tuple(item for item in graph.appearances if item.id in appearances_in_use),
        loops=tuple(item for item in graph.loops if item.id not in loop_ids),
        shapes=tuple(replace(item, parent=None if item.parent == shape_id else item.parent)
                     for item in graph.shapes if item.id != shape_id),
        interfaces=interfaces,
        corners=corners,
        constraints=tuple(item for item in graph.constraints if shape_id not in item.members),
        layer_edges=tuple(item for item in graph.layer_edges
                          if item.below != shape_id and item.above != shape_id),
    )

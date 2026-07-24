"""Line-level text grouping, font-free glyph topology, and optional font Path A."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

import cv2
import numpy as np

from .contracts import (ConstraintEdge, GeometryPrimitive, LayerEdge, LoopNode,
                        SceneGraph, ShapeNode)
from .shape_models import primitive_points
from .ingest import CanonicalRaster
from .topology import TopologyHypothesis


@dataclass(frozen=True)
class GlyphInstance:
    shape_id: str
    bbox: tuple[int, int, int, int]
    baseline: float
    height: float
    stroke_width: float
    components: int
    counters: int
    descriptor: tuple[float, ...]
    prototype_id: str | None = None


@dataclass(frozen=True)
class TextLine:
    id: str
    glyphs: tuple[GlyphInstance, ...]
    baseline: float
    x_height: float
    cap_height: float
    ink_appearance: str
    confidence: float
    recognized_text: str | None = None


@dataclass(frozen=True)
class ExactFontProposal:
    line_id: str
    font_file: str
    text: str
    score: float
    topology_match: bool
    replacement_shapes: tuple[ShapeNode, ...] = ()


FontPathA = Callable[[CanonicalRaster, TextLine], ExactFontProposal | None]


def integrate_text_scene(graph: SceneGraph, topology: TopologyHypothesis,
                         raster: CanonicalRaster, text_probability: np.ndarray,
                         *, glyph_occupancy: np.ndarray | None = None,
                         stroke_centerline_prob: np.ndarray | None = None,
                         stroke_half_width: np.ndarray | None = None,
                         exact_font_path: FontPathA | None = None
                         ) -> tuple[SceneGraph, tuple[TextLine, ...], tuple[ExactFontProposal, ...]]:
    candidates: list[tuple[int, tuple[int, int, int, int], float]] = []
    for index, region in enumerate(topology.regions):
        x0, y0, x1, y1 = region.bbox
        width, height = x1 - x0, y1 - y0
        if not (2 <= height <= max(4, int(.35 * raster.height)) and 1 <= width <= 3.0 * height):
            continue
        local_text = float(np.mean(text_probability[y0:y1, x0:x1])) if y1 > y0 and x1 > x0 else 0.0
        local_glyph = (float(np.mean(glyph_occupancy[y0:y1, x0:x1]))
                       if glyph_occupancy is not None and y1 > y0 and x1 > x0 else 0.0)
        support = max(local_text, local_glyph)
        if support >= 0.15 or raster.height <= 64:
            candidates.append((index, region.bbox, support))
    groups = _group_lines(candidates)
    lines: list[TextLine] = []
    shape_updates: dict[str, tuple[str, str]] = {}
    constraints = list(graph.constraints)
    prototypes: dict[tuple[int, ...], list[str]] = {}
    loop_replacements = {loop.id: loop for loop in graph.loops}
    for line_index, group in enumerate(groups):
        if len(group) < 2:
            continue
        glyphs: list[GlyphInstance] = []
        ordered_group = sorted(group, key=lambda row: row[1][0])
        stem_class = float(np.median([
            _evidence_stroke_width(
                topology.regions[region_index].mask,
                stroke_centerline_prob, stroke_half_width,
            )
            for region_index, _, _ in ordered_group
        ]))
        for region_index, bbox, confidence in ordered_group:
            region = topology.regions[region_index]
            shape = graph.shapes[region_index]
            rebuilt_mask = font_free_sdf_reconstruct(region.mask, stem_class)
            descriptor = _glyph_descriptor(rebuilt_mask)
            key = tuple(int(round(value * 16)) for value in descriptor[:7])
            prototype_id = f"glyph-prototype-{len(prototypes)}" if key not in prototypes else f"glyph-prototype-{list(prototypes).index(key)}"
            prototypes.setdefault(key, []).append(shape.id)
            stroke = _evidence_stroke_width(
                region.mask, stroke_centerline_prob, stroke_half_width)
            counters = len(region.negative_contours)
            replacement = _mask_geometry(rebuilt_mask)
            if replacement is not None and len(replacement[1]) == len(shape.negative_loops):
                positive, negatives = replacement
                loop_replacements[shape.positive_loop] = replace(
                    loop_replacements[shape.positive_loop], primitives=positive)
                for loop_id, geometry in zip(shape.negative_loops, negatives):
                    loop_replacements[loop_id] = replace(
                        loop_replacements[loop_id], primitives=geometry)
            glyphs.append(GlyphInstance(
                shape_id=shape.id, bbox=bbox, baseline=float(bbox[3]),
                height=float(bbox[3] - bbox[1]), stroke_width=stroke,
                components=1, counters=counters, descriptor=descriptor,
                prototype_id=prototype_id,
            ))
            shape_updates[shape.id] = (f"text-line-{line_index}", prototype_id)
        baselines = np.array([glyph.baseline for glyph in glyphs])
        heights = np.array([glyph.height for glyph in glyphs])
        appearance_ids = [graph.shapes[next(i for i, s in enumerate(graph.shapes) if s.id == glyph.shape_id)].appearance_id
                          for glyph in glyphs]
        line = TextLine(
            id=f"text-line-{line_index}", glyphs=tuple(glyphs),
            baseline=float(np.median(baselines)), x_height=float(np.median(heights)),
            cap_height=float(np.percentile(heights, 80)), ink_appearance=max(set(appearance_ids), key=appearance_ids.count),
            confidence=float(np.clip(np.mean([row[2] for row in group]) + .35, 0.0, 1.0)),
        )
        lines.append(line)
        constraints.extend((
            ConstraintEdge(f"constraint-{line.id}-baseline", "baseline",
                           tuple(g.shape_id for g in glyphs), .85, ("text-line-group",)),
            ConstraintEdge(f"constraint-{line.id}-stem", "stroke-width-class",
                           tuple(g.shape_id for g in glyphs), .65, ("glyph-sdf",)),
        ))
    for key_index, members in enumerate(prototypes.values()):
        if len(members) >= 2:
            constraints.append(ConstraintEdge(
                f"constraint-glyph-repeat-{key_index}", "repeated-glyph",
                tuple(members), .75, ("hu-moment-prototype",),
            ))
    shapes = tuple(replace(
        shape, model_family="glyph", semantic_group=shape_updates[shape.id][0],
        provenance=shape.provenance + (shape_updates[shape.id][1], "font-free-path-B",
                                       "persistent-counters" if shape.negative_loops else "no-counter"),
    ) if shape.id in shape_updates else shape for shape in graph.shapes)
    loops = tuple(loop_replacements[loop.id] for loop in graph.loops)
    updated = replace(graph, shapes=shapes, loops=loops,
                      constraints=tuple(constraints))
    updated.validate()
    exact: list[ExactFontProposal] = []
    if exact_font_path is not None:
        for line in lines:
            proposal = exact_font_path(raster, line)
            if proposal is not None and proposal.topology_match and proposal.score >= 0.92:
                exact.append(proposal)
                # Deliberately do not mutate here: an accepted Path A replacement
                # still has to enter the global forward-model court.
    return updated, tuple(lines), tuple(exact)


def glyph_catastrophe_count(before: tuple[GlyphInstance, ...],
                            after: tuple[GlyphInstance, ...]) -> int:
    by_id = {glyph.shape_id: glyph for glyph in after}
    catastrophes = 0
    for glyph in before:
        candidate = by_id.get(glyph.shape_id)
        if candidate is None or candidate.components < glyph.components or candidate.counters < glyph.counters:
            catastrophes += 1
    return catastrophes


def font_free_sdf_reconstruct(mask: np.ndarray, target_stem_width: float) -> np.ndarray:
    """Regularize glyph stems as a signed-distance level set without topology loss."""
    original = np.asarray(mask, bool)
    if not original.any():
        return original.copy()
    inside = cv2.distanceTransform(original.astype(np.uint8), cv2.DIST_L2, 5)
    outside = cv2.distanceTransform((~original).astype(np.uint8), cv2.DIST_L2, 5)
    signed = inside - outside
    current = _sdf_stroke_width(original)
    offset = .5 * (current - float(target_stem_width))
    offset = float(np.clip(offset, -0.45, 0.45))
    candidate = signed >= offset
    if _component_count(candidate) != _component_count(original):
        return original.copy()
    if _hole_count(candidate) != _hole_count(original):
        return original.copy()
    intersection = np.logical_and(candidate, original).sum()
    union = np.logical_or(candidate, original).sum()
    if intersection / max(1, union) < .78:
        return original.copy()
    return candidate


def apply_exact_font_substitution(graph: SceneGraph, substitution: dict) -> SceneGraph | None:
    """Convert a gated legacy font match into an immutable scene hypothesis."""
    raw_loops = substitution.get("loops") or []
    bbox = substitution.get("bbox")
    if not raw_loops or bbox is None:
        return None
    bx0, by0, bx1, by1 = (float(v) for v in bbox)
    if bx1 <= bx0 or by1 <= by0:
        return None
    loop_by_id = {loop.id: loop for loop in graph.loops}
    replaced_ids = []
    for shape in graph.shapes:
        if shape.model_family != "glyph":
            continue
        points = []
        for primitive in loop_by_id[shape.positive_loop].primitives:
            points.extend(primitive_points(primitive, 48).tolist())
        if not points:
            continue
        center = np.mean(points, axis=0)
        if bx0 <= center[0] <= bx1 and by0 <= center[1] <= by1:
            replaced_ids.append(shape.id)
    if not replaced_ids:
        return None
    old_shapes = [shape for shape in graph.shapes if shape.id in replaced_ids]
    appearance_id = max({shape.appearance_id for shape in old_shapes},
                        key=lambda item: sum(shape.appearance_id == item for shape in old_shapes))
    converted: list[tuple[GeometryPrimitive, ...]] = []
    polygons: list[np.ndarray] = []
    for raw_loop in raw_loops:
        geometry = []
        for curve in raw_loop:
            control = np.asarray(curve.control, np.float64)
            kind = {1: "line", 2: "quadratic", 3: "cubic"}.get(int(curve.degree), "polyline")
            geometry.append(GeometryPrimitive(
                kind, points=tuple((float(x), float(y)) for x, y in control),
                provenance=("exact-font-path-A", str(substitution.get("font", "unknown"))),
            ))
        if not geometry:
            continue
        converted.append(tuple(geometry))
        sampled = [primitive_points(item, 24) for item in geometry]
        polygons.append(np.vstack([item for item in sampled if len(item)]).astype(np.float32))
    if not converted:
        return None
    parent_index: list[int | None] = [None] * len(polygons)
    depth = [0] * len(polygons)
    areas = [abs(float(cv2.contourArea(poly))) for poly in polygons]
    for child, polygon in enumerate(polygons):
        center = tuple(float(v) for v in np.mean(polygon, axis=0))
        containers = [(areas[parent], parent) for parent, candidate in enumerate(polygons)
                      if parent != child and areas[parent] > areas[child]
                      and cv2.pointPolygonTest(candidate.reshape(-1, 1, 2), center, False) >= 0]
        if containers:
            parent_index[child] = min(containers)[1]
    for index in range(len(polygons)):
        cursor = parent_index[index]
        seen = set()
        while cursor is not None and cursor not in seen:
            seen.add(cursor)
            depth[index] += 1
            cursor = parent_index[cursor]
    kept_shape_ids = {shape.id for shape in graph.shapes} - set(replaced_ids)
    kept_shapes = [replace(shape, parent=None if shape.parent in replaced_ids else shape.parent)
                   for shape in graph.shapes if shape.id in kept_shape_ids]
    old_loop_ids = {loop_id for shape in old_shapes
                    for loop_id in (shape.positive_loop, *shape.negative_loops)}
    kept_loops = [loop for loop in graph.loops if loop.id not in old_loop_ids]
    new_shapes = []
    new_loops = []
    roots = [index for index, value in enumerate(depth) if value % 2 == 0]
    base_index = len(graph.shapes)
    for root_position, root in enumerate(roots):
        positive_id = f"loop-font-{base_index}-{root_position}-positive"
        new_loops.append(LoopNode(positive_id, converted[root], 1, areas[root]))
        holes = [index for index, parent in enumerate(parent_index)
                 if parent == root and depth[index] % 2 == 1]
        negative_ids = []
        for hole_position, hole in enumerate(holes):
            loop_id = f"loop-font-{base_index}-{root_position}-negative-{hole_position}"
            negative_ids.append(loop_id)
            new_loops.append(LoopNode(loop_id, converted[hole], -1, -areas[hole]))
        shape_id = f"shape-font-{base_index}-{root_position}"
        new_shapes.append(ShapeNode(
            id=shape_id, topology_id=f"font:{substitution.get('text', '')}:{root_position}",
            appearance_id=appearance_id, positive_loop=positive_id,
            negative_loops=tuple(negative_ids),
            layer=max((shape.layer for shape in graph.shapes), default=-1) + 1 + root_position,
            model_family="glyph-font", confidence=float(substitution.get("iou", .9)),
            provenance=("exact-font-path-A", str(substitution.get("font", "unknown")),
                        str(substitution.get("text", "")), "strict-silhouette-wall"),
            semantic_group=f"font-line:{substitution.get('text', '')}",
        ))
    if not new_shapes:
        return None
    interfaces = tuple(edge for edge in graph.interfaces
                       if edge.left_shape not in replaced_ids and edge.right_shape not in replaced_ids)
    surviving_interface_ids = {edge.id for edge in interfaces}
    corners = tuple(replace(corner, incident_interfaces=tuple(
        edge for edge in corner.incident_interfaces if edge in surviving_interface_ids))
        for corner in graph.corners
        if any(edge in surviving_interface_ids for edge in corner.incident_interfaces))
    surviving_corner_ids = {corner.id for corner in corners}
    interfaces = tuple(replace(edge, corner_nodes=tuple(
        corner for corner in edge.corner_nodes if corner in surviving_corner_ids))
        for edge in interfaces)
    constraints = tuple(item for item in graph.constraints
                        if not set(item.members).intersection(replaced_ids))
    constraints += (ConstraintEdge(
        f"constraint-exact-font-{base_index}", "exact-font-outline",
        tuple(shape.id for shape in new_shapes), 1.0,
        (str(substitution.get("font", "unknown")), str(substitution.get("text", ""))),
    ),)
    layer_edges = tuple(item for item in graph.layer_edges
                        if item.below not in replaced_ids and item.above not in replaced_ids)
    if kept_shapes:
        top = max(kept_shapes, key=lambda item: item.layer).id
        layer_edges += (LayerEdge(top, new_shapes[0].id),)
    layer_edges += tuple(LayerEdge(new_shapes[index].id, new_shapes[index + 1].id)
                         for index in range(len(new_shapes) - 1))
    result = replace(graph, loops=tuple(kept_loops + new_loops),
                     shapes=tuple(kept_shapes + new_shapes), interfaces=interfaces,
                     corners=corners, constraints=constraints, layer_edges=layer_edges)
    result.validate()
    return result


def _sdf_stroke_width(mask: np.ndarray) -> float:
    interior = cv2.distanceTransform(np.asarray(mask, np.uint8), cv2.DIST_L2, 5)
    ridge = interior >= cv2.dilate(interior, np.ones((3, 3), np.float32)) - 1e-5
    values = interior[ridge & (interior > .35)]
    return float(2.0 * np.median(values)) if len(values) else 1.0


def _evidence_stroke_width(mask: np.ndarray,
                           centerline: np.ndarray | None,
                           half_width: np.ndarray | None) -> float:
    if (centerline is not None and half_width is not None
            and centerline.shape == mask.shape and half_width.shape == mask.shape):
        support = np.asarray(mask, bool) & (np.asarray(centerline) >= .2)
        values = np.asarray(half_width, np.float32)[support]
        values = values[np.isfinite(values) & (values > .15)]
        if len(values):
            return float(2.0 * np.median(values))
    return _sdf_stroke_width(mask)


def _component_count(mask: np.ndarray) -> int:
    count, _ = cv2.connectedComponents(np.asarray(mask, np.uint8), 8)
    return int(count - 1)


def _mask_geometry(mask: np.ndarray) -> tuple[tuple[GeometryPrimitive, ...],
                                                tuple[tuple[GeometryPrimitive, ...], ...]] | None:
    contours, hierarchy = cv2.findContours(np.asarray(mask, np.uint8), cv2.RETR_CCOMP,
                                            cv2.CHAIN_APPROX_NONE)
    if not contours or hierarchy is None:
        return None
    hierarchy_rows = hierarchy[0]
    outers = [index for index, row in enumerate(hierarchy_rows) if row[3] < 0]
    if len(outers) != 1:
        return None
    outer = outers[0]

    def geometry(contour: np.ndarray, role: str) -> tuple[GeometryPrimitive, ...]:
        perimeter = cv2.arcLength(contour, True)
        points = cv2.approxPolyDP(contour, max(.18, .004 * perimeter), True).reshape(-1, 2)
        if len(points) and np.linalg.norm(points[0] - points[-1]) > 1e-6:
            points = np.vstack((points, points[0]))
        return (GeometryPrimitive(
            "polyline", points=tuple((float(x) + .5, float(y) + .5) for x, y in points),
            provenance=("font-free-sdf-path-B", role),
        ),)

    positive = geometry(contours[outer], "positive")
    negatives = tuple(geometry(contours[index], "counter")
                      for index, row in enumerate(hierarchy_rows) if row[3] == outer)
    return positive, negatives


def _group_lines(candidates: list[tuple[int, tuple[int, int, int, int], float]]) -> list[list[tuple]]:
    groups: list[list[tuple]] = []
    for row in sorted(candidates, key=lambda item: (item[1][1] + item[1][3], item[1][0])):
        _, bbox, _ = row
        center = .5 * (bbox[1] + bbox[3])
        height = bbox[3] - bbox[1]
        target = None
        for group in groups:
            centers = [.5 * (item[1][1] + item[1][3]) for item in group]
            heights = [item[1][3] - item[1][1] for item in group]
            if abs(center - float(np.median(centers))) <= .6 * max(height, float(np.median(heights))):
                if .45 <= height / max(float(np.median(heights)), 1.0) <= 2.1:
                    target = group
                    break
        if target is None:
            groups.append([row])
        else:
            target.append(row)
    return groups


def _glyph_descriptor(mask: np.ndarray) -> tuple[float, ...]:
    moments = cv2.moments(mask.astype(np.uint8))
    hu = cv2.HuMoments(moments).ravel()
    hu = -np.sign(hu) * np.log10(np.maximum(np.abs(hu), 1e-30))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    holes = _hole_count(mask)
    area = float(mask.sum())
    return tuple(float(v) for v in hu) + (float(count - 1), float(holes), area / max(1, mask.size))


def _hole_count(mask: np.ndarray) -> int:
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return 0
    return sum(int(row[3] >= 0) for row in hierarchy[0])

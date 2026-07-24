"""Exact source-scene generation from user-licensed OpenType fonts."""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

from .contracts import (Appearance, ConstraintEdge, GeometryPrimitive,
                        LayerEdge, LoopNode, SceneGraph, ShapeNode)
from .shape_models import primitive_points


def font_text_scene(font_path: Path, text: str, *, width: int = 256,
                    height: int = 96, font_size: float = 58.0,
                    tracking_em: float = 0.02) -> SceneGraph:
    """Convert text to an exact SceneGraph without embedding the font file.

    The caller is responsible for using a font licensed for the generated
    dataset. Only the font hash and basename enter provenance.
    """
    from fontTools.misc.transform import Transform
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    from svgpathtools import parse_path

    if not font_path.is_file() or not text:
        raise ValueError("a readable font and non-empty text are required")
    font_bytes = font_path.read_bytes()
    font_hash = hashlib.sha256(font_bytes).hexdigest()
    font = TTFont(font_path, fontNumber=0, lazy=False)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap() or {}
    units_per_em = float(font["head"].unitsPerEm)
    hmtx = font["hmtx"].metrics
    scale = font_size / units_per_em
    baseline = min(height - 5.0, 5.0 + .8 * font_size)
    cursor = 6.0
    loops: list[LoopNode] = []
    shapes: list[ShapeNode] = []
    appearance = Appearance(
        "font-ink", "solid", (.018, .018, .022, 1.0),
        provenance=(f"font-sha256:{font_hash}", font_path.name,
                    "caller-asserts-training-license"),
    )
    for character_index, character in enumerate(text):
        glyph_name = cmap.get(ord(character))
        if glyph_name is None:
            cursor += .5 * font_size
            continue
        advance = hmtx.get(glyph_name, (units_per_em * .5, 0))[0] * scale
        pen = SVGPathPen(glyph_set)
        glyph_set[glyph_name].draw(TransformPen(
            pen, Transform(scale, 0, 0, -scale, cursor, baseline)))
        commands = pen.getCommands()
        if commands:
            path = parse_path(commands)
            rows = []
            for subpath in path.continuous_subpaths():
                primitives: list[GeometryPrimitive] = []
                sampled: list[tuple[float, float]] = []
                for segment in subpath:
                    kind = type(segment).__name__
                    point = lambda value: (float(value.real), float(value.imag))
                    if kind == "Line":
                        primitive = GeometryPrimitive("line", points=(point(segment.start),
                                                                       point(segment.end)))
                    elif kind == "QuadraticBezier":
                        primitive = GeometryPrimitive("quadratic", points=(
                            point(segment.start), point(segment.control), point(segment.end)))
                    elif kind == "CubicBezier":
                        primitive = GeometryPrimitive("cubic", points=(
                            point(segment.start), point(segment.control1),
                            point(segment.control2), point(segment.end)))
                    else:
                        points = tuple(point(segment.point(t)) for t in np.linspace(0, 1, 17))
                        primitive = GeometryPrimitive("polyline", points=points)
                    primitives.append(primitive)
                    sampled.extend(tuple(value) for value in primitive_points(primitive, 32))
                if len(sampled) >= 3:
                    contour = np.asarray(sampled, np.float32)
                    rows.append({"primitives": tuple(primitives), "contour": contour,
                                 "area": abs(float(cv2.contourArea(contour)))})
            parents = _containment_parents(rows)
            loop_ids = []
            for row_index, row in enumerate(rows):
                loop_id = f"font-loop-{character_index}-{row_index}"
                loop_ids.append(loop_id)
                depth = _depth(parents, row_index)
                loops.append(LoopNode(loop_id, row["primitives"],
                                      1 if depth % 2 == 0 else -1,
                                      row["area"] * (1 if depth % 2 == 0 else -1)))
            outer_shape_by_row = {
                row_index: f"font-glyph-{character_index}-{row_index}"
                for row_index in range(len(rows))
                if _depth(parents, row_index) % 2 == 0
            }
            for row_index, row in enumerate(rows):
                depth = _depth(parents, row_index)
                if depth % 2:
                    continue
                shape_id = outer_shape_by_row[row_index]
                holes = tuple(loop_ids[index] for index, parent in enumerate(parents)
                              if parent == row_index and _depth(parents, index) % 2 == 1)
                ancestor = parents[row_index]
                while ancestor is not None and ancestor not in outer_shape_by_row:
                    ancestor = parents[ancestor]
                shapes.append(ShapeNode(
                    shape_id, f"font-character-{character_index}", "font-ink",
                    loop_ids[row_index], holes,
                    parent=outer_shape_by_row.get(ancestor), layer=len(shapes),
                    model_family="glyph-font-synthetic", semantic_group="font-line-0",
                    provenance=(f"font-sha256:{font_hash}", f"unicode:{ord(character):04X}",
                                "exact-font-source"),
                ))
        cursor += advance + tracking_em * font_size
        if cursor > width - 4:
            break
    font.close()
    if not shapes:
        raise ValueError("font produced no supported glyph outlines")
    edges = tuple(LayerEdge(shapes[index - 1].id, shapes[index].id)
                  for index in range(1, len(shapes)))
    members = tuple(shape.id for shape in shapes)
    constraints = (
        ConstraintEdge("font-baseline", "baseline", members, 1.0,
                       ("exact-font-source",)),
        ConstraintEdge("font-stroke-family", "stroke-width-class", members, .8,
                       ("exact-font-source",)),
    )
    scene = SceneGraph(width, height, (appearance,), tuple(loops), tuple(shapes),
                       constraints=constraints, layer_edges=edges)
    scene.validate()
    return scene


def _containment_parents(rows: list[dict]) -> list[int | None]:
    parents: list[int | None] = [None] * len(rows)
    for index, row in enumerate(rows):
        point = tuple(float(value) for value in row["contour"].mean(axis=0))
        candidates = []
        for other_index, other in enumerate(rows):
            if other_index == index or other["area"] <= row["area"]:
                continue
            if cv2.pointPolygonTest(other["contour"], point, False) >= 0:
                candidates.append((other["area"], other_index))
        if candidates:
            parents[index] = min(candidates)[1]
    return parents


def _depth(parents: list[int | None], index: int) -> int:
    depth = 0
    current = parents[index]
    while current is not None:
        depth += 1
        current = parents[current]
    return depth

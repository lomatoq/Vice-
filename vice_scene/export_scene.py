"""Canonical scene export: SVG/cutout/stacked, PNG, PDF/EPS, and DXF adapters."""

from __future__ import annotations

import html
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .contracts import (Appearance, GeometryPrimitive, LayerEdge, LoopNode,
                        SceneGraph, ShapeNode)
from .gap_filler import gap_filler_rows
from .ingest import linear_to_srgb
from .render_models import render_scene
from .shape_models import primitive_points, render_geometry_mask


def scene_to_svg(scene: SceneGraph, *, mode: str = "stacked", gap_filler: bool = True,
                 primitive_map: bool = False, group_by: str = "parent",
                 preserve_parametric: bool = True) -> str:
    if mode not in {"stacked", "cutout"}:
        raise ValueError("SVG mode must be stacked or cutout")
    if group_by not in {"parent", "layer", "color", "none"}:
        raise ValueError("group_by must be parent, layer, color, or none")
    scene.validate()
    appearance_by_id = {item.id: item for item in scene.appearances}
    loop_by_id = {item.id: item for item in scene.loops}
    defs, paint = _appearance_defs(scene.appearances)
    ordered_shapes = sorted(scene.shapes, key=lambda item: (item.layer, item.id))
    cutout_masks: dict[str, str] = {}
    if mode == "cutout":
        mask_rows, cutout_masks = _svg_cutout_masks(
            scene, ordered_shapes, loop_by_id, appearance_by_id)
        defs.extend(mask_rows)
    rows = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene.width}" height="{scene.height}" '
        f'viewBox="0 0 {scene.width} {scene.height}" data-v-ice-schema="{html.escape(scene.schema_version)}" '
        f'data-export-mode="{mode}">',
    ]
    if defs:
        rows.extend(("<defs>", *defs, "</defs>"))
    if gap_filler and not primitive_map and mode == "stacked":
        rows.extend(gap_filler_rows(scene, geometry_to_path))
    groups: dict[str, list] = {}
    for shape in ordered_shapes:
        if group_by == "parent":
            key = shape.parent or "scene-root"
        elif group_by == "layer":
            key = f"layer-{shape.layer}"
        elif group_by == "color":
            key = shape.appearance_id
        else:
            key = "scene-root"
        groups.setdefault(key, []).append(shape)
    for group_key, shapes in groups.items():
        rows.append(f'<g data-group-by="{group_by}" data-group="{html.escape(group_key)}">')
        for shape in shapes:
            appearance = appearance_by_id[shape.appearance_id]
            positive = loop_by_id[shape.positive_loop]
            negatives = tuple(loop_by_id[item] for item in shape.negative_loops)
            if primitive_map:
                rows.extend(_primitive_map_rows(shape.id, positive, negatives))
            else:
                shape_row = _shape_svg(shape.id, shape.model_family, positive, negatives,
                                       paint[appearance.id], appearance,
                                       preserve_parametric=preserve_parametric)
                if shape.id in cutout_masks:
                    rows.extend((f'<g mask="url(#{cutout_masks[shape.id]})">',
                                 shape_row, "</g>"))
                else:
                    rows.append(shape_row)
        rows.append("</g>")
    rows.append("</svg>")
    return "\n".join(rows) + "\n"


def export_svg(path: Path, scene: SceneGraph, *, mode: str = "stacked",
               gap_filler: bool = True, primitive_map: bool = False,
               group_by: str = "parent", preserve_parametric: bool = True) -> None:
    path.write_text(scene_to_svg(scene, mode=mode, gap_filler=gap_filler,
                                 primitive_map=primitive_map, group_by=group_by,
                                 preserve_parametric=preserve_parametric), encoding="utf-8")


def export_png(path: Path, scene: SceneGraph, *, scale: int = 4,
               antialias: bool = True,
               size: tuple[int, int] | None = None) -> None:
    from .contracts import RenderModel
    if scale <= 0 or (size is not None and min(size) <= 0):
        raise ValueError("PNG scale/size must be positive")
    model = RenderModel("clean-aa" if antialias else "hard", supersample=4 if antialias else 1)
    render_scale = scale
    if size is not None:
        render_scale = max(1, int(math.ceil(max(size[0] / scene.width,
                                                size[1] / scene.height))))
    image = Image.fromarray(render_scene(scene, output_scale=render_scale, model=model), "RGBA")
    if size is not None and image.size != size:
        image = image.resize(size, Image.Resampling.LANCZOS if antialias
                             else Image.Resampling.NEAREST)
    image.save(path)


def export_pdf_or_eps(path: Path, scene: SceneGraph, *, mode: str = "stacked") -> None:
    if mode not in {"stacked", "cutout"}:
        raise ValueError("mode must be stacked or cutout")
    exported_scene = _flatten_cutout_scene(scene) if mode == "cutout" else scene
    if path.suffix.lower() == ".pdf":
        _export_pdf(path, exported_scene)
    elif path.suffix.lower() == ".eps":
        _export_eps(path, exported_scene)
    else:
        raise ValueError("path must end in .pdf or .eps")


def export_dxf(path: Path, scene: SceneGraph, *, mode: str = "stacked") -> None:
    if mode not in {"stacked", "cutout"}:
        raise ValueError("mode must be stacked or cutout")
    scene = _flatten_cutout_scene(scene) if mode == "cutout" else scene
    loop_by_id = {item.id: item for item in scene.loops}
    rows = ["0", "SECTION", "2", "ENTITIES"]
    for shape in scene.shapes:
        for loop_id in (shape.positive_loop, *shape.negative_loops):
            loop = loop_by_id[loop_id]
            points = _loop_points(loop)
            if len(points) < 2:
                continue
            rows.extend(("0", "LWPOLYLINE", "8", "0", "90", str(len(points)), "70", "1"))
            for x, y in points:
                rows.extend(("10", f"{x:.6f}", "20", f"{y:.6f}"))
    rows.extend(("0", "ENDSEC", "0", "EOF"))
    path.write_text("\n".join(rows) + "\n", encoding="ascii")


def geometry_to_path(geometry: tuple[GeometryPrimitive, ...], *, close: bool = True) -> str:
    commands: list[str] = []
    current = None
    for primitive in geometry:
        kind = primitive.kind
        if kind == "line" and len(primitive.points) >= 2:
            points = np.asarray(primitive.points, float)
            if current is None or np.linalg.norm(current - points[0]) > 1e-6:
                commands.append(f"M {_fmt(points[0, 0])} {_fmt(points[0, 1])}")
            commands.append(f"L {_fmt(points[-1, 0])} {_fmt(points[-1, 1])}")
            current = points[-1]
        elif kind in {"circular-arc", "elliptical-arc"}:
            points = primitive_points(primitive, 2)
            if len(points) < 2:
                continue
            if current is None or np.linalg.norm(current - points[0]) > 1e-6:
                commands.append(f"M {_fmt(points[0, 0])} {_fmt(points[0, 1])}")
            p = primitive.parameters
            if kind == "circular-arc":
                rx, ry, rotation, start, end = p[2], p[2], 0.0, p[3], p[4]
            else:
                rx, ry, rotation, start, end = p[2], p[3], p[4], p[5], p[6]
            span = end - start
            commands.append(
                f"A {_fmt(rx)} {_fmt(ry)} {_fmt(rotation)} {int(abs(span) > math.pi)} "
                f"{int(span >= 0)} {_fmt(points[-1, 0])} {_fmt(points[-1, 1])}"
            )
            current = points[-1]
        elif kind in {"quadratic", "cubic"} and primitive.points:
            points = np.asarray(primitive.points, float)
            if current is None or np.linalg.norm(current - points[0]) > 1e-6:
                commands.append(f"M {_fmt(points[0, 0])} {_fmt(points[0, 1])}")
            letter = "Q" if kind == "quadratic" else "C"
            commands.append(letter + " " + " ".join(f"{_fmt(x)} {_fmt(y)}" for x, y in points[1:]))
            current = points[-1]
        else:
            points = primitive_points(primitive, 64)
            if not len(points):
                continue
            if current is None or np.linalg.norm(current - points[0]) > 1e-6:
                commands.append(f"M {_fmt(points[0, 0])} {_fmt(points[0, 1])}")
            commands.extend(f"L {_fmt(x)} {_fmt(y)}" for x, y in points[1:])
            current = points[-1]
    if close and commands:
        commands.append("Z")
    return " ".join(commands)


def _shape_svg(shape_id: str, family: str, positive: LoopNode,
               negatives: tuple[LoopNode, ...], paint: str,
               appearance: Appearance, *, preserve_parametric: bool = True) -> str:
    opacity = appearance.rgba_linear[3]
    style = f'{paint} fill-opacity="{opacity:.6g}"'
    primitive = positive.primitives[0] if len(positive.primitives) == 1 else None
    attrs = f'id="{html.escape(shape_id)}" data-model="{html.escape(family)}"'
    if preserve_parametric and not negatives and primitive is not None:
        p = primitive.parameters
        if primitive.kind == "circle":
            return f'<circle {attrs} cx="{_fmt(p[0])}" cy="{_fmt(p[1])}" r="{_fmt(p[2])}" {style}/>'
        if primitive.kind == "ellipse":
            transform = f' transform="rotate({_fmt(p[4])} {_fmt(p[0])} {_fmt(p[1])})"' if abs(p[4]) > 1e-8 else ""
            return f'<ellipse {attrs} cx="{_fmt(p[0])}" cy="{_fmt(p[1])}" rx="{_fmt(p[2])}" ry="{_fmt(p[3])}"{transform} {style}/>'
        if primitive.kind in {"rect", "rounded-rect"}:
            cx, cy, width, height, angle = p[:5]
            radius = p[5] if primitive.kind == "rounded-rect" else 0.0
            transform = f' transform="rotate({_fmt(angle)} {_fmt(cx)} {_fmt(cy)})"' if abs(angle) > 1e-8 else ""
            return f'<rect {attrs} x="{_fmt(cx-width/2)}" y="{_fmt(cy-height/2)}" width="{_fmt(width)}" height="{_fmt(height)}" rx="{_fmt(radius)}"{transform} {style}/>'
    paths = [geometry_to_path(positive.primitives)]
    paths.extend(geometry_to_path(loop.primitives) for loop in negatives)
    return f'<path {attrs} d="{" ".join(paths)}" fill-rule="evenodd" {style}/>'


def _svg_cutout_masks(scene: SceneGraph, ordered_shapes: list[ShapeNode],
                      loops: dict[str, LoopNode],
                      appearances: dict[str, Appearance]) -> tuple[list[str], dict[str, str]]:
    rows: list[str] = []
    mapping: dict[str, str] = {}
    for index, shape in enumerate(ordered_shapes[:-1]):
        above = ordered_shapes[index + 1:]
        if not above:
            continue
        mask_id = f"cutout-{shape.id}"
        mapping[shape.id] = mask_id
        rows.append(f'<mask id="{html.escape(mask_id)}" maskUnits="userSpaceOnUse" '
                    f'x="0" y="0" width="{scene.width}" height="{scene.height}">')
        rows.append(f'<rect x="0" y="0" width="{scene.width}" height="{scene.height}" fill="white"/>')
        for covering in above:
            appearance = appearances[covering.appearance_id]
            opacity = max((stop.rgba_linear[3] for stop in appearance.stops),
                          default=appearance.rgba_linear[3])
            if opacity <= 1e-6:
                continue
            path = geometry_to_path(loops[covering.positive_loop].primitives)
            path += " " + " ".join(geometry_to_path(loops[item].primitives)
                                     for item in covering.negative_loops)
            rows.append(f'<path d="{path.strip()}" fill="black" fill-rule="evenodd" '
                        f'fill-opacity="{float(opacity):.6g}"/>')
        rows.append("</mask>")
    return rows, mapping


def _flatten_cutout_scene(scene: SceneGraph) -> SceneGraph:
    """Opaque visible-region boolean fallback for non-SVG vector adapters."""
    ordered = sorted(scene.shapes, key=lambda item: (item.layer, item.id))
    loops = {item.id: item for item in scene.loops}
    appearances = {item.id: item for item in scene.appearances}
    masks = []
    for shape in ordered:
        positive = loops[shape.positive_loop].primitives
        negatives = tuple(loops[item].primitives for item in shape.negative_loops)
        masks.append(render_geometry_mask((scene.height, scene.width), positive,
                                          negatives, supersample=4) >= 128)
    output_loops: list[LoopNode] = []
    output_shapes: list[ShapeNode] = []
    for index, shape in enumerate(ordered):
        hidden = np.zeros((scene.height, scene.width), bool)
        for covering_index in range(index + 1, len(ordered)):
            covering = ordered[covering_index]
            opacity = appearances[covering.appearance_id].rgba_linear[3]
            if opacity >= .999:
                hidden |= masks[covering_index]
        visible = masks[index] & ~hidden
        contours, hierarchy = cv2.findContours(visible.astype(np.uint8), cv2.RETR_CCOMP,
                                                cv2.CHAIN_APPROX_SIMPLE)
        if not contours or hierarchy is None:
            continue
        hierarchy_rows = hierarchy[0]
        for component, row in enumerate(hierarchy_rows):
            if row[3] >= 0:
                continue
            positive_id = f"cutout-loop-{index}-{component}-positive"
            positive_points = tuple((float(x) + .5, float(y) + .5)
                                    for x, y in contours[component][:, 0, :])
            if len(positive_points) < 3:
                continue
            positive_geometry = GeometryPrimitive(
                "polyline", points=positive_points + (positive_points[0],),
                provenance=("cutout-boolean-fallback",))
            output_loops.append(LoopNode(positive_id, (positive_geometry,), 1,
                                         abs(float(cv2.contourArea(contours[component])))))
            negative_ids = []
            for hole, hole_row in enumerate(hierarchy_rows):
                if hole_row[3] != component:
                    continue
                points = tuple((float(x) + .5, float(y) + .5)
                               for x, y in contours[hole][:, 0, :])
                if len(points) < 3:
                    continue
                loop_id = f"cutout-loop-{index}-{component}-negative-{hole}"
                geometry = GeometryPrimitive(
                    "polyline", points=points + (points[0],),
                    provenance=("cutout-boolean-fallback",))
                output_loops.append(LoopNode(loop_id, (geometry,), -1,
                                             -abs(float(cv2.contourArea(contours[hole])))))
                negative_ids.append(loop_id)
            output_shapes.append(ShapeNode(
                f"cutout-{shape.id}-{component}", shape.topology_id,
                shape.appearance_id, positive_id, tuple(negative_ids),
                layer=len(output_shapes), model_family="cutout-flattened",
                confidence=shape.confidence,
                provenance=shape.provenance + ("visible-region-cutout",),
                semantic_group=shape.semantic_group,
            ))
    used_appearances = {shape.appearance_id for shape in output_shapes}
    edges = tuple(LayerEdge(output_shapes[index - 1].id, output_shapes[index].id)
                  for index in range(1, len(output_shapes)))
    result = SceneGraph(scene.width, scene.height,
                        tuple(item for item in scene.appearances if item.id in used_appearances),
                        tuple(output_loops), tuple(output_shapes), layer_edges=edges)
    result.validate()
    return result


def _appearance_defs(appearances: tuple[Appearance, ...]) -> tuple[list[str], dict[str, str]]:
    defs, paint = [], {}
    for appearance in appearances:
        if appearance.kind == "solid" or not appearance.stops:
            rgb = linear_to_srgb(np.asarray([appearance.rgba_linear[:3]], np.float32))[0]
            paint[appearance.id] = 'fill="#' + "".join(f"{int(round(v * 255)):02x}" for v in rgb) + '"'
            continue
        gradient_id = f"gradient-{appearance.id}"
        if appearance.kind == "linear-gradient":
            x0, y0, x1, y1 = appearance.parameters[:4]
            defs.append(f'<linearGradient id="{gradient_id}" gradientUnits="userSpaceOnUse" x1="{_fmt(x0)}" y1="{_fmt(y0)}" x2="{_fmt(x1)}" y2="{_fmt(y1)}">')
            closing = "linearGradient"
        else:
            cx, cy, radius = appearance.parameters[:3]
            defs.append(f'<radialGradient id="{gradient_id}" gradientUnits="userSpaceOnUse" cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="{_fmt(radius)}">')
            closing = "radialGradient"
        for stop in appearance.stops:
            rgb = linear_to_srgb(np.asarray([stop.rgba_linear[:3]], np.float32))[0]
            color = "#" + "".join(f"{int(round(v * 255)):02x}" for v in rgb)
            defs.append(f'<stop offset="{stop.offset:.6g}" stop-color="{color}" stop-opacity="{stop.rgba_linear[3]:.6g}"/>')
        defs.append(f'</{closing}>')
        paint[appearance.id] = f'fill="url(#{gradient_id})"'
    return defs, paint


def _primitive_map_rows(shape_id: str, positive: LoopNode,
                        negatives: tuple[LoopNode, ...]) -> list[str]:
    colors = {"line": "#2663eb", "circle": "#f5911e", "ellipse": "#f5911e",
              "rect": "#16a34a", "rounded-rect": "#16a34a"}
    rows = []
    for loop in (positive, *negatives):
        for primitive in loop.primitives:
            d = geometry_to_path((primitive,), close=primitive.kind not in {"line", "quadratic", "cubic"})
            color = colors.get(primitive.kind, "#c439ad")
            rows.append(f'<path data-shape="{html.escape(shape_id)}" data-type="{html.escape(primitive.kind)}" d="{d}" fill="none" stroke="{color}" stroke-width="0.65" vector-effect="non-scaling-stroke"/>')
    return rows


def _loop_points(loop: LoopNode) -> np.ndarray:
    points = []
    for primitive in loop.primitives:
        value = primitive_points(primitive, 64)
        if len(value):
            points.extend(value.tolist())
    return np.asarray(points, float)


def _export_pdf(path: Path, scene: SceneGraph) -> None:
    from reportlab.pdfgen import canvas

    output = canvas.Canvas(str(path), pagesize=(scene.width, scene.height), pageCompression=1)
    appearance = {item.id: item for item in scene.appearances}
    loops = {item.id: item for item in scene.loops}
    for shape in sorted(scene.shapes, key=lambda item: (item.layer, item.id)):
        fill = appearance[shape.appearance_id]
        rgb = linear_to_srgb(np.asarray([fill.rgba_linear[:3]], np.float32))[0]
        output.setFillColorRGB(*(float(v) for v in rgb))
        if hasattr(output, "setFillAlpha"):
            output.setFillAlpha(float(fill.rgba_linear[3]))
        pdf_path = output.beginPath()
        for loop_id in (shape.positive_loop, *shape.negative_loops):
            points = _loop_points(loops[loop_id])
            if len(points) < 3:
                continue
            pdf_path.moveTo(float(points[0, 0]), scene.height - float(points[0, 1]))
            for x, y in points[1:]:
                pdf_path.lineTo(float(x), scene.height - float(y))
            pdf_path.close()
        output.drawPath(pdf_path, fill=1, stroke=0, fillMode=0)
    output.showPage()
    output.save()


def _export_eps(path: Path, scene: SceneGraph) -> None:
    appearance = {item.id: item for item in scene.appearances}
    loops = {item.id: item for item in scene.loops}
    rows = ["%!PS-Adobe-3.0 EPSF-3.0", f"%%BoundingBox: 0 0 {scene.width} {scene.height}",
            "1 setlinejoin 1 setlinecap"]
    for shape in sorted(scene.shapes, key=lambda item: (item.layer, item.id)):
        fill = appearance[shape.appearance_id]
        rgb = linear_to_srgb(np.asarray([fill.rgba_linear[:3]], np.float32))[0]
        rows.append(f"{rgb[0]:.6f} {rgb[1]:.6f} {rgb[2]:.6f} setrgbcolor")
        rows.append("newpath")
        for loop_id in (shape.positive_loop, *shape.negative_loops):
            points = _loop_points(loops[loop_id])
            if len(points) < 3:
                continue
            rows.append(f"{points[0,0]:.6f} {scene.height-points[0,1]:.6f} moveto")
            rows.extend(f"{x:.6f} {scene.height-y:.6f} lineto" for x, y in points[1:])
            rows.append("closepath")
        rows.append("eofill")
    rows.extend(("showpage", "%%EOF"))
    path.write_text("\n".join(rows) + "\n", encoding="ascii")


def _fmt(value: float) -> str:
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return text if text not in {"", "-0"} else "0"

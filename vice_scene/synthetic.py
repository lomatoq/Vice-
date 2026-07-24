"""Deterministic scene/data factory with exact labels and degradation manifests."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .contracts import (Appearance, ConstraintEdge, CornerNode,
                        GeometryPrimitive, GradientStop, InterfaceEdge,
                        LayerEdge, LoopNode, RenderModel, SceneGraph, ShapeNode)
from .render_models import render_scene
from .shape_models import primitive_points


@dataclass(frozen=True)
class DegradationStep:
    kind: str
    parameters: tuple[float, ...]


@dataclass(frozen=True)
class SyntheticManifest:
    schema: str
    seed: int
    scene_sha256: str
    renderer: str
    render_model: dict
    degradations: tuple[DegradationStep, ...]
    output_sha256: str


def canonical_smoke_scene(size: int = 32) -> SceneGraph:
    appearances = (
        Appearance("appearance-red", "solid", (0.95, 0.025, 0.02, 1.0), provenance=("synthetic",)),
        Appearance("appearance-blue", "solid", (0.02, 0.16, 0.82, 1.0), provenance=("synthetic",)),
    )
    circle = GeometryPrimitive("circle", (10.0, 10.0, 6.0), provenance=("synthetic",))
    rounded = GeometryPrimitive("rounded-rect", (20.0, 19.0, 16.0, 12.0, 0.0, 3.0), provenance=("synthetic",))
    hole = GeometryPrimitive("circle", (20.0, 19.0, 2.5), provenance=("synthetic-counter",))
    loops = (
        LoopNode("loop-circle", (circle,), 1, 3.141592653589793 * 36.0),
        LoopNode("loop-rounded", (rounded,), 1, 160.0),
        LoopNode("loop-counter", (hole,), -1, -3.141592653589793 * 6.25),
    )
    shapes = (
        ShapeNode("shape-circle", "synthetic-circle", "appearance-red", "loop-circle",
                  layer=0, model_family="circle", model_params=circle.parameters,
                  provenance=("synthetic-ground-truth",)),
        ShapeNode("shape-rounded", "synthetic-rounded", "appearance-blue", "loop-rounded",
                  ("loop-counter",), layer=1, model_family="rounded-rectangle",
                  model_params=rounded.parameters, provenance=("synthetic-ground-truth",)),
    )
    scene = SceneGraph(size, size, appearances, loops, shapes,
                       layer_edges=(LayerEdge("shape-circle", "shape-rounded"),))
    scene.validate()
    return scene


def random_scene(seed: int, width: int = 128, height: int = 96,
                 shape_count: int = 8) -> SceneGraph:
    rng = np.random.default_rng(seed)
    appearances, loops, shapes, layer_edges = [], [], [], []
    for index in range(shape_count):
        color = tuple(float(v) for v in rng.uniform(.02, .95, 3)) + (float(rng.uniform(.65, 1.0)),)
        appearances.append(Appearance(f"appearance-{index}", "solid", color,
                                      provenance=(f"synthetic-seed-{seed}",)))
        family = ("circle", "ellipse", "rect", "rounded-rect", "star")[index % 5]
        cx, cy = float(rng.uniform(8, width - 8)), float(rng.uniform(8, height - 8))
        radius = float(rng.uniform(3, min(width, height) * .13))
        if family == "circle":
            primitive = GeometryPrimitive("circle", (cx, cy, radius))
        elif family == "ellipse":
            primitive = GeometryPrimitive("ellipse", (cx, cy, radius, radius * rng.uniform(.45, .9), rng.uniform(-60, 60)))
        elif family == "rect":
            primitive = GeometryPrimitive("rect", (cx, cy, radius * 2, radius * rng.uniform(.8, 1.8), rng.uniform(-40, 40)))
        elif family == "rounded-rect":
            primitive = GeometryPrimitive("rounded-rect", (cx, cy, radius * 2, radius * rng.uniform(.8, 1.8), rng.uniform(-30, 30), radius * .25))
        else:
            primitive = GeometryPrimitive("star", (cx, cy, radius, radius * .45, float(3 + index % 4), rng.uniform(-3.14, 3.14)))
        loop_id, shape_id = f"loop-{index}", f"shape-{index}"
        loops.append(LoopNode(loop_id, (primitive,), 1, 1.0))
        shapes.append(ShapeNode(shape_id, f"topology-{index}", f"appearance-{index}", loop_id,
                                layer=index, model_family=family, model_params=primitive.parameters,
                                provenance=("synthetic-ground-truth",)))
        if index:
            layer_edges.append(LayerEdge(f"shape-{index - 1}", shape_id))
    scene = SceneGraph(width, height, tuple(appearances), tuple(loops), tuple(shapes),
                       layer_edges=tuple(layer_edges))
    scene.validate()
    return scene


def coverage_scene(seed: int, width: int = 160, height: int = 120) -> SceneGraph:
    """Feature-dense source scene for corpus coverage, not a benchmark target.

    The scene deliberately contains holes, nested/occluding layers, cubic artwork,
    a ribbon, a font-free glyph group, gradients, alpha, repeated geometry,
    symmetry, deliberate asymmetry, diagram dashes, and subpixel microdetail.
    """
    if width < 160 or height < 120:
        raise ValueError("coverage_scene requires at least 160x120 native pixels")
    rng = np.random.default_rng(seed)
    appearances = [
        Appearance("a-ring", "radial-gradient", (.9, .08, .03, .92),
                   (35.0, 34.0, 22.0),
                   (GradientStop(0.0, (1.0, .35, .05, .95)),
                    GradientStop(1.0, (.55, .015, .01, .8)))),
        Appearance("a-blob", "solid", (.04, .24, .85, .88)),
        Appearance("a-ribbon", "solid", (.05, .72, .2, .78)),
        Appearance("a-glyph", "solid", (.025, .025, .03, 1.0)),
        Appearance("a-linear", "linear-gradient", (.7, .1, .8, 1.0),
                   (92.0, 18.0, 144.0, 50.0),
                   (GradientStop(0.0, (.2, .04, .75, 1.0)),
                    GradientStop(1.0, (.95, .2, .35, .65)))),
        Appearance("a-diagram", "solid", (.1, .12, .16, 1.0)),
        Appearance("a-micro", "solid", (.95, .8, .05, .9)),
    ]
    loops: list[LoopNode] = []
    shapes: list[ShapeNode] = []

    def add(shape_id: str, family: str, primitive: GeometryPrimitive,
            appearance_id: str, *, hole: GeometryPrimitive | None = None,
            parent: str | None = None, group: str | None = None) -> None:
        loop_id = f"loop-{shape_id}"
        loops.append(LoopNode(loop_id, (primitive,), 1, 1.0))
        negative = ()
        if hole is not None:
            hole_id = f"loop-{shape_id}-counter"
            loops.append(LoopNode(hole_id, (hole,), -1, -1.0))
            negative = (hole_id,)
        shapes.append(ShapeNode(
            shape_id, f"synthetic-{shape_id}", appearance_id, loop_id, negative,
            parent=parent, layer=len(shapes), model_family=family,
            model_params=primitive.parameters, semantic_group=group,
            provenance=(f"synthetic-seed-{seed}", "exact-source-scene"),
        ))

    add("ring", "ring", GeometryPrimitive("circle", (34, 33, 23)), "a-ring",
        hole=GeometryPrimitive("circle", (34, 33, 11)))
    blob = GeometryPrimitive("cubic", points=((58, 17), (76, 3), (88, 30), (78, 42)))
    blob2 = GeometryPrimitive("cubic", points=((78, 42), (66, 57), (48, 44), (58, 17)))
    loops.append(LoopNode("loop-blob", (blob, blob2), 1, 1.0))
    shapes.append(ShapeNode("blob", "synthetic-blob", "a-blob", "loop-blob",
                            parent="ring", layer=1, model_family="generic-bezier",
                            semantic_group="artwork", provenance=("arbitrary-bezier",)))
    ribbon_points = ((12, 72), (28, 64), (50, 70), (72, 61), (94, 69),
                     (92, 77), (72, 70), (51, 79), (28, 73), (14, 81), (12, 72))
    add("ribbon", "ribbon", GeometryPrimitive("polyline", points=ribbon_points),
        "a-ribbon", group="variable-width-stroke")
    glyph_points = ((104, 91), (115, 58), (128, 91), (123, 91), (120, 82),
                    (110, 82), (107, 91), (104, 91))
    glyph_counter = GeometryPrimitive("polyline", points=((113, 77), (118, 77),
                                                            (115.5, 68), (113, 77)))
    add("glyph-A", "glyph-custom", GeometryPrimitive("polyline", points=glyph_points),
        "a-glyph", hole=glyph_counter, group="text-line-0")
    add("gradient-panel", "rectangle", GeometryPrimitive("rounded-rect",
        (130, 32, 46, 29, -8, 5)), "a-linear")

    # Repeated symmetric circles with one deliberate asymmetry.
    for index, x in enumerate((32.0, 52.0, 72.0)):
        radius = 5.0 if index < 2 else 4.2
        add(f"repeat-{index}", "circle", GeometryPrimitive("circle", (x, 101, radius)),
            "a-diagram", group="repeat-row")
    # Dashed diagram frame represented as editable individual rectangles.
    dash_index = 0
    for x in range(89, 151, 12):
        for y in (98, 112):
            add(f"dash-{dash_index}", "rectangle",
                GeometryPrimitive("rect", (x, y, 7, 1.5, 0)), "a-diagram",
                group="dashed-frame")
            dash_index += 1
    for y in (103, 109):
        for x in (88, 152):
            add(f"dash-{dash_index}", "rectangle",
                GeometryPrimitive("rect", (x, y, 1.5, 4, 0)), "a-diagram",
                group="dashed-frame")
            dash_index += 1
    # Engraved/tiny evidence goes below one pixel by construction.
    for index in range(4):
        add(f"micro-{index}", "circle", GeometryPrimitive(
            "circle", (82 + index * 3.2, 53 + float(rng.uniform(-.25, .25)),
                       .48 + .08 * (index % 2))), "a-micro", group="microdetail")

    layer_edges = tuple(LayerEdge(shapes[index - 1].id, shapes[index].id)
                        for index in range(1, len(shapes)))
    constraints = (
        ConstraintEdge("c-repeat-radius", "equal-radius",
                       ("repeat-0", "repeat-1"), 1.0, ("synthetic-oracle",)),
        ConstraintEdge("c-repeat-gap", "equal-gap",
                       ("repeat-0", "repeat-1", "repeat-2"), .7,
                       ("deliberate-asymmetry-last-radius",)),
        ConstraintEdge("c-glyph-line", "baseline", ("glyph-A",), 1.0,
                       ("font-free-custom-glyph",)),
    )
    interface_geometry = (GeometryPrimitive("line", points=((88, 96), (154, 96))),)
    interfaces = (InterfaceEdge("i-frame-top", "gradient-panel", "dash-0",
                                interface_geometry, evidence_refs=("synthetic-oracle",)),)
    corners = ()
    scene = SceneGraph(width, height, tuple(appearances), tuple(loops), tuple(shapes),
                       interfaces=interfaces, corners=corners,
                       constraints=constraints, layer_edges=layer_edges)
    scene.validate()
    return scene


def render_synthetic(scene: SceneGraph, model: RenderModel,
                     degradations: tuple[DegradationStep, ...] = (), *,
                     renderer: str = "vice-analytic") -> np.ndarray:
    rgba = render_with_family(scene, renderer, model)
    image = Image.fromarray(rgba, "RGBA")
    for step in degradations:
        if step.kind in {"gaussian-blur", "defocus-blur"}:
            image = image.filter(ImageFilter.GaussianBlur(step.parameters[0]))
        elif step.kind in {"sharpen", "ringing"}:
            amount = float(step.parameters[0])
            value = np.asarray(image, np.float32)
            blur = cv2.GaussianBlur(value, (0, 0), max(.2, float(step.parameters[1])
                                                      if len(step.parameters) > 1 else .7))
            value = np.clip(value + amount * (value - blur), 0, 255)
            image = Image.fromarray((value + .5).astype(np.uint8), "RGBA")
        elif step.kind == "resize":
            factor = step.parameters[0]
            small = image.resize((max(1, round(image.width * factor)),
                                  max(1, round(image.height * factor))), Image.Resampling.LANCZOS)
            image = small.resize((scene.width, scene.height), Image.Resampling.LANCZOS)
        elif step.kind == "gamma":
            value = np.asarray(image, np.float32) / 255.0
            value[..., :3] = np.power(value[..., :3], step.parameters[0])
            image = Image.fromarray((np.clip(value, 0.0, 1.0) * 255 + .5).astype(np.uint8), "RGBA")
        elif step.kind in {"jpeg", "recompress"}:
            quality = int(step.parameters[0])
            rgb = Image.new("RGB", image.size, "white")
            rgb.paste(image, mask=image.getchannel("A"))
            generations = (int(step.parameters[1]) if step.kind == "recompress"
                           and len(step.parameters) > 1 else 1)
            for _ in range(max(1, generations)):
                stream = io.BytesIO()
                rgb.save(stream, "JPEG", quality=quality, subsampling=2)
                rgb = Image.open(io.BytesIO(stream.getvalue())).convert("RGB")
            image = rgb.convert("RGBA")
        elif step.kind == "translate":
            matrix = np.float32([[1, 0, step.parameters[0]], [0, 1, step.parameters[1]]])
            value = cv2.warpAffine(np.asarray(image), matrix, image.size,
                                   flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT,
                                   borderValue=(0, 0, 0, 0))
            image = Image.fromarray(value, "RGBA")
        elif step.kind == "rotate":
            angle = float(step.parameters[0])
            value = cv2.warpAffine(
                np.asarray(image), cv2.getRotationMatrix2D(
                    ((image.width - 1) * .5, (image.height - 1) * .5), angle, 1.0),
                image.size, flags=cv2.INTER_LANCZOS4,
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
            )
            image = Image.fromarray(value, "RGBA")
        elif step.kind == "palette":
            colors = max(2, int(step.parameters[0]))
            alpha = image.getchannel("A")
            rgb = image.convert("RGB").quantize(colors=colors,
                                                  method=Image.Quantize.MEDIANCUT).convert("RGB")
            image = rgb.convert("RGBA")
            image.putalpha(alpha)
        elif step.kind == "scan-noise":
            sigma = float(step.parameters[0])
            seed = int(step.parameters[1]) if len(step.parameters) > 1 else 0
            rng = np.random.default_rng(seed)
            value = np.asarray(image, np.float32)
            value[..., :3] += rng.normal(0.0, sigma, value[..., :3].shape)
            image = Image.fromarray(np.clip(value, 0, 255).astype(np.uint8), "RGBA")
        elif step.kind == "alpha-roundtrip-error":
            strength = float(step.parameters[0]) if step.parameters else 1.0
            value = np.asarray(image, np.float32) / 255.0
            premultiplied = value[..., :3] * value[..., 3:4]
            value[..., :3] = ((1.0 - strength) * value[..., :3]
                              + strength * premultiplied)
            image = Image.fromarray((np.clip(value, 0, 1) * 255 + .5).astype(np.uint8),
                                    "RGBA")
        else:
            raise ValueError(f"unknown degradation {step.kind!r}")
    return np.asarray(image, np.uint8)


def render_with_family(scene: SceneGraph, family: str,
                       model: RenderModel | None = None) -> np.ndarray:
    """Independent renderer adapter used for renderer-holdout datasets."""
    model = model or RenderModel()
    if family == "vice-analytic":
        return render_scene(scene, model=model)
    if family == "opencv-polygon":
        return _render_opencv_polygon(scene, model)
    if family in {"chromium-svg", "resvg-svg"}:
        return _render_external_svg(scene, family)
    if family != "pillow-polygon":
        raise ValueError(f"unknown renderer family {family!r}")
    scale = max(4, model.supersample)
    canvas = Image.new("RGBA", (scene.width * scale, scene.height * scale), (0, 0, 0, 0))
    appearance = {item.id: item for item in scene.appearances}
    loops = {item.id: item for item in scene.loops}
    from .ingest import linear_to_srgb
    for shape in sorted(scene.shapes, key=lambda item: (item.layer, item.id)):
        fill = appearance[shape.appearance_id]
        if fill.kind != "solid":
            return render_scene(scene, model=model)
        rgb = linear_to_srgb(np.asarray([fill.rgba_linear[:3]], np.float32))[0]
        rgba = tuple(int(round(v * 255)) for v in rgb) + (int(round(fill.rgba_linear[3] * 255)),)
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        mask = Image.new("L", canvas.size, 0)
        draw = ImageDraw.Draw(mask)
        for loop_id, color in ((shape.positive_loop, 255),
                               *((item, 0) for item in shape.negative_loops)):
            points = []
            for primitive in loops[loop_id].primitives:
                points.extend(primitive_points(primitive, 96).tolist())
            if len(points) >= 3:
                draw.polygon([(x * scale, y * scale) for x, y in points], fill=color)
        layer.paste(Image.new("RGBA", canvas.size, rgba), mask=mask)
        canvas = Image.alpha_composite(canvas, layer)
    return np.asarray(canvas.resize((scene.width, scene.height), Image.Resampling.LANCZOS), np.uint8)


def available_renderer_families() -> tuple[str, ...]:
    families = ["vice-analytic", "pillow-polygon", "opencv-polygon"]
    chrome = _find_chromium()
    if chrome is not None:
        families.append("chromium-svg")
    if shutil.which("resvg") or shutil.which("rsvg-convert"):
        families.append("resvg-svg")
    return tuple(families)


def _render_opencv_polygon(scene: SceneGraph, model: RenderModel) -> np.ndarray:
    # Independent fixed-point polygon rasterizer. Gradients fall back because
    # OpenCV fillPoly has no gradient paint model.
    if any(item.kind != "solid" for item in scene.appearances):
        return render_scene(scene, model=model)
    scale = max(4, model.supersample)
    canvas = np.zeros((scene.height * scale, scene.width * scale, 4), np.uint8)
    appearances = {item.id: item for item in scene.appearances}
    loops = {item.id: item for item in scene.loops}
    from .ingest import linear_to_srgb
    for shape in sorted(scene.shapes, key=lambda item: (item.layer, item.id)):
        mask = np.zeros(canvas.shape[:2], np.uint8)
        for loop_id, fill_value in ((shape.positive_loop, 255),
                                    *((item, 0) for item in shape.negative_loops)):
            points = []
            for primitive in loops[loop_id].primitives:
                points.extend(primitive_points(primitive, 128).tolist())
            if len(points) >= 3:
                scaled = np.round(np.asarray(points) * scale).astype(np.int32)
                cv2.fillPoly(mask, [scaled], fill_value, lineType=cv2.LINE_8)
        appearance = appearances[shape.appearance_id]
        rgb = linear_to_srgb(np.asarray([appearance.rgba_linear[:3]], np.float32))[0]
        source = np.zeros_like(canvas)
        source[..., :3] = np.round(rgb * 255).astype(np.uint8)
        source[..., 3] = int(round(appearance.rgba_linear[3] * 255))
        coverage = (mask.astype(np.float32) / 255.0)[..., None]
        source_alpha = source[..., 3:4].astype(np.float32) / 255.0 * coverage
        destination_alpha = canvas[..., 3:4].astype(np.float32) / 255.0
        out_alpha = source_alpha + destination_alpha * (1.0 - source_alpha)
        source_rgb = source[..., :3].astype(np.float32) / 255.0
        destination_rgb = canvas[..., :3].astype(np.float32) / 255.0
        premul = (source_rgb * source_alpha
                  + destination_rgb * destination_alpha * (1.0 - source_alpha))
        straight = np.zeros_like(premul)
        np.divide(premul, out_alpha, out=straight, where=out_alpha > 1e-7)
        canvas[..., :3] = np.round(straight * 255).astype(np.uint8)
        canvas[..., 3:4] = np.round(out_alpha * 255).astype(np.uint8)
    return cv2.resize(canvas, (scene.width, scene.height), interpolation=cv2.INTER_AREA)


def _find_chromium() -> Path | None:
    candidates = [shutil.which("chrome"), shutil.which("chromium"),
                  shutil.which("msedge"),
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    return next((Path(item) for item in candidates if item and Path(item).is_file()), None)


def _render_external_svg(scene: SceneGraph, family: str) -> np.ndarray:
    from .export_scene import scene_to_svg
    with tempfile.TemporaryDirectory(prefix="vice-render-") as raw:
        root = Path(raw)
        source = root / "scene.svg"
        target = root / "scene.png"
        source.write_text(scene_to_svg(scene, mode="stacked"), encoding="utf-8")
        if family == "chromium-svg":
            executable = _find_chromium()
            if executable is None:
                raise RuntimeError("Chromium/Chrome renderer is unavailable")
            command = [str(executable), "--headless=new", "--disable-gpu",
                       "--hide-scrollbars", "--force-device-scale-factor=1",
                       f"--window-size={scene.width},{scene.height}",
                       f"--screenshot={target}", source.resolve().as_uri()]
        else:
            executable = shutil.which("resvg") or shutil.which("rsvg-convert")
            if executable is None:
                raise RuntimeError("resvg/Cairo renderer is unavailable")
            command = ([executable, str(source), str(target)] if Path(executable).stem == "resvg"
                       else [executable, "-o", str(target), str(source)])
        completed = subprocess.run(command, capture_output=True, timeout=30,
                                   check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if completed.returncode != 0 or not target.is_file():
            raise RuntimeError(f"external renderer failed: {completed.stderr[-300:]!r}")
        return np.asarray(Image.open(target).convert("RGBA").resize(
            (scene.width, scene.height), Image.Resampling.LANCZOS), np.uint8)


def write_fixture(root: Path, scene: SceneGraph, *, seed: int,
                  model: RenderModel | None = None,
                  degradations: tuple[DegradationStep, ...] = (),
                  renderer: str = "vice-analytic") -> SyntheticManifest:
    root.mkdir(parents=True, exist_ok=True)
    model = model or RenderModel()
    scene_json = scene.to_json() + "\n"
    image = render_synthetic(scene, model, degradations, renderer=renderer)
    output_hash = hashlib.sha256(image.tobytes()).hexdigest()
    manifest = SyntheticManifest(
        "vice-synthetic/1", seed, hashlib.sha256(scene_json.encode("utf-8")).hexdigest(),
        renderer, asdict(model), degradations, output_hash,
    )
    (root / "scene.json").write_text(scene_json, encoding="utf-8")
    Image.fromarray(image, "RGBA").save(root / "input.png")
    (root / "manifest.json").write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return manifest


def reproduce_fixture(root: Path) -> bool:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    scene = SceneGraph.from_json((root / "scene.json").read_text(encoding="utf-8"))
    model = RenderModel(**manifest["render_model"])
    degradations = tuple(DegradationStep(row["kind"], tuple(row["parameters"]))
                         for row in manifest["degradations"])
    image = render_synthetic(scene, model, degradations,
                             renderer=manifest.get("renderer", "vice-analytic"))
    return hashlib.sha256(image.tobytes()).hexdigest() == manifest["output_sha256"]

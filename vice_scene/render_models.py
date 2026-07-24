"""Physical vector renderer and AA/gamma/PSF/JPEG forward-model court."""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from .contracts import Appearance, LoopNode, RenderModel, SceneGraph
from .ingest import CanonicalRaster, linear_to_srgb, srgb_to_linear
from .shape_models import primitive_points


@dataclass(frozen=True)
class ForwardScore:
    model: RenderModel
    nll: float
    color_mae: float
    alpha_mae: float
    edge_mae: float
    worst_window: float = 0.0


@dataclass(frozen=True)
class ScoreCalibration:
    temperature: float = .015
    color_weight: float = 1.0
    alpha_weight: float = .35
    edge_weight: float = .18
    local_weight: float = .12


def render_scene(scene: SceneGraph, *, output_scale: int = 1,
                 model: RenderModel | None = None) -> np.ndarray:
    model = model or RenderModel()
    ss = max(1, int(model.supersample))
    scale = max(1, int(output_scale))
    height, width = scene.height * scale, scene.width * scale
    canvas = np.zeros((height, width, 4), np.float32)  # premultiplied linear
    appearance_by_id = {item.id: item for item in scene.appearances}
    loop_by_id = {item.id: item for item in scene.loops}
    for shape in sorted(scene.shapes, key=lambda item: (item.layer, item.id)):
        positive = loop_by_id[shape.positive_loop]
        negatives = tuple(loop_by_id[item] for item in shape.negative_loops)
        bounds = _loop_bounds(positive)
        if bounds is None:
            continue
        x0 = max(0, int(math.floor(bounds[0] * scale)) - 1)
        y0 = max(0, int(math.floor(bounds[1] * scale)) - 1)
        x1 = min(width, int(math.ceil(bounds[2] * scale)) + 1)
        y1 = min(height, int(math.ceil(bounds[3] * scale)) + 1)
        if x1 <= x0 or y1 <= y0:
            continue
        patch_height, patch_width = y1 - y0, x1 - x0
        origin = (x0 / scale, y0 / scale)
        mask = _shape_mask((patch_height, patch_width), ss * scale, positive,
                           negatives, origin=origin, supersample=ss)
        appearance = appearance_by_id[shape.appearance_id]
        source = _appearance_field(appearance, (patch_height, patch_width), scale,
                                   origin=origin)
        coverage = (mask[..., None] / 255.0) * source[..., 3:4]
        premul = source[..., :3] * coverage
        destination = canvas[y0:y1, x0:x1]
        destination[..., :3] = premul + destination[..., :3] * (1.0 - coverage)
        destination[..., 3:4] = coverage + destination[..., 3:4] * (1.0 - coverage)
    if model.blur_sigma > 0:
        sigma = model.blur_sigma * scale
        for channel in range(4):
            canvas[..., channel] = cv2.GaussianBlur(canvas[..., channel], (0, 0), sigma)
    alpha = np.clip(canvas[..., 3:4], 0.0, 1.0)
    linear = np.where(alpha > 1e-7, canvas[..., :3] / np.maximum(alpha, 1e-7), 0.0)
    if model.gamma > 0 and abs(model.gamma - 2.2) > 1e-6:
        srgb = np.power(np.clip(linear, 0.0, 1.0), 1.0 / model.gamma)
    else:
        srgb = linear_to_srgb(linear)
    rgba = np.concatenate((np.clip(srgb, 0.0, 1.0), alpha), axis=2)
    result = (rgba * 255.0 + .5).astype(np.uint8)
    if model.jpeg_quality is not None:
        # JPEG formation is evaluated on a white composite; alpha is restored
        # only for API consistency and is never interpreted as JPEG evidence.
        composite = result[..., :3].astype(np.float32) * (result[..., 3:4] / 255.0)
        composite += 255.0 * (1.0 - result[..., 3:4] / 255.0)
        buffer = io.BytesIO()
        Image.fromarray(composite.astype(np.uint8), "RGB").save(
            buffer, format="JPEG", quality=int(model.jpeg_quality), subsampling=2)
        decoded = np.asarray(Image.open(io.BytesIO(buffer.getvalue())).convert("RGB"), np.uint8)
        result = np.concatenate((decoded, np.full((*decoded.shape[:2], 1), 255, np.uint8)), axis=2)
    return result


def forward_model_catalog(names: tuple[str, ...] | list[str]) -> tuple[RenderModel, ...]:
    result = []
    for name in names:
        if name == "clean-aa":
            result.append(RenderModel(name, supersample=4))
        elif name == "hard":
            result.append(RenderModel(name, supersample=1))
        elif name.startswith("blur-"):
            result.append(RenderModel(name, supersample=4, blur_sigma=float(name.split("-", 1)[1])))
        elif name.startswith("gamma-"):
            result.append(RenderModel(name, supersample=4, gamma=float(name.split("-", 1)[1])))
        elif name.startswith("jpeg-"):
            result.append(RenderModel(name, supersample=4, jpeg_quality=int(name.split("-", 1)[1])))
        else:
            raise ValueError(f"unknown forward model {name!r}")
    return tuple(result)


def score_forward(scene: SceneGraph, raster: CanonicalRaster,
                  model: RenderModel,
                  calibration: ScoreCalibration | None = None) -> ForwardScore:
    calibration = calibration or ScoreCalibration()
    rendered = render_scene(scene, model=model)
    srgb = rendered[..., :3].astype(np.float32) / 255.0
    alpha = rendered[..., 3].astype(np.float32) / 255.0
    linear = srgb_to_linear(srgb)
    target = raster.rgba_linear_premul
    target_alpha = target[..., 3]
    # Opaque border-connected background is an observation/compositing field,
    # not automatically an exported shape.  Court the vector scene on that
    # field so a white JPEG background does not force a giant white rectangle.
    border = np.concatenate((target[0, :, :3], target[-1, :, :3],
                             target[:, 0, :3], target[:, -1, :3]), axis=0)
    background = np.median(border, axis=0)
    transparency_present = bool(np.mean(target_alpha < .999) > 1e-4)
    if transparency_present:
        # Compare premultiplied colours. Comparing a semi-transparent straight
        # colour to a background-composited render penalizes an exact match.
        color_residual = np.abs(linear * alpha[..., None] - target[..., :3])
        alpha_residual = np.abs(alpha - target_alpha)
    else:
        composite = linear * alpha[..., None] + background * (1.0 - alpha[..., None])
        color_residual = np.abs(composite - target[..., :3])
        alpha_residual = np.zeros_like(alpha)
    color_mae = float(np.mean(color_residual))
    alpha_mae = float(np.mean(alpha_residual))
    gray_render = cv2.cvtColor(rendered[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    gray_target = cv2.cvtColor((raster.rgba_srgb_straight[..., :3] * 255 + .5).astype(np.uint8),
                               cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    edge_render = cv2.Laplacian(gray_render, cv2.CV_32F)
    edge_target = cv2.Laplacian(gray_target, cv2.CV_32F)
    edge_mae = float(np.mean(np.abs(edge_render - edge_target)))
    # Pseudo-NLL uses a robust Charbonnier likelihood; it stays calibrated in
    # native pixels and cannot be improved by merely rendering at 4x.
    charb = float(np.mean(np.sqrt(color_residual * color_residual + 1e-5)))
    pixel_residual = np.mean(color_residual, axis=2) + .35 * alpha_residual
    window = max(3, min(16, max(3, min(pixel_residual.shape) // 4)))
    local = cv2.boxFilter(pixel_residual.astype(np.float32), cv2.CV_32F,
                          (window, window), normalize=True,
                          borderType=cv2.BORDER_REPLICATE)
    worst_window = float(np.max(local))
    nll = (calibration.color_weight * charb
           + calibration.alpha_weight * alpha_mae
           + calibration.edge_weight * edge_mae
           + calibration.local_weight * worst_window)
    return ForwardScore(model, nll, color_mae, alpha_mae, edge_mae, worst_window)


def select_forward_model(scene: SceneGraph, raster: CanonicalRaster,
                         models: tuple[RenderModel, ...]) -> tuple[ForwardScore, tuple[ForwardScore, ...]]:
    scores = tuple(score_forward(scene, raster, model) for model in models)
    return min(scores, key=lambda item: item.nll), scores


def marginalized_forward_nll(scores: tuple[ForwardScore, ...],
                             calibration: ScoreCalibration | None = None) -> float:
    """Log-mean-exp marginalization over plausible raster formation models."""
    if not scores:
        raise ValueError("cannot marginalize an empty forward-model set")
    calibration = calibration or ScoreCalibration()
    temperature = max(float(calibration.temperature), 1e-6)
    values = np.asarray([item.nll for item in scores], np.float64)
    minimum = float(values.min())
    return float(minimum - temperature * math.log(
        float(np.mean(np.exp(-(values - minimum) / temperature)))))


def _shape_mask(shape: tuple[int, int], sample_scale: int, positive: LoopNode,
                negatives: tuple[LoopNode, ...], *, origin: tuple[float, float],
                supersample: int) -> np.ndarray:
    high_shape = (shape[0] * supersample, shape[1] * supersample)
    mask = np.zeros(high_shape, np.uint8)
    _draw_loop(mask, positive, 255, sample_scale, origin)
    for loop in negatives:
        _draw_loop(mask, loop, 0, sample_scale, origin)
    if supersample > 1:
        mask = cv2.resize(mask, (shape[1], shape[0]), interpolation=cv2.INTER_AREA)
    return mask


def _draw_loop(canvas: np.ndarray, loop: LoopNode, color: int, scale: int,
               origin: tuple[float, float]) -> None:
    if len(loop.primitives) == 1 and loop.primitives[0].kind in {
            "circle", "ellipse", "rect", "rounded-rect"}:
        analytic = _analytic_primitive_mask(canvas.shape, loop.primitives[0], scale,
                                            origin)
        canvas[analytic] = int(color)
        return
    chain: list[np.ndarray] = []
    for primitive in loop.primitives:
        points = primitive_points(primitive, max(48, 16 * scale))
        if len(points):
            if chain and np.linalg.norm(chain[-1][-1] - points[0]) < 1e-5:
                points = points[1:]
            if len(points):
                chain.append(points)
    if not chain:
        return
    points = np.vstack(chain)
    if len(points) >= 3:
        local = (points - np.asarray(origin, np.float64)) * scale - .5
        fixed = np.round(local * 256).astype(np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(canvas, [fixed], int(color), lineType=cv2.LINE_8, shift=8)


def _appearance_field(appearance: Appearance, shape: tuple[int, int], scale: int,
                      *, origin: tuple[float, float] = (0.0, 0.0)) -> np.ndarray:
    height, width = shape
    if appearance.kind == "solid" or not appearance.stops:
        field = np.empty((height, width, 4), np.float32)
        field[:] = appearance.rgba_linear
        return field
    yy, xx = np.mgrid[:height, :width].astype(np.float32)
    xx = (xx + .5) / scale + origin[0]
    yy = (yy + .5) / scale + origin[1]
    if appearance.kind == "linear-gradient":
        x0, y0, x1, y1 = appearance.parameters[:4]
        dx, dy = x1 - x0, y1 - y0
        t = ((xx - x0) * dx + (yy - y0) * dy) / max(dx * dx + dy * dy, 1e-8)
    elif appearance.kind == "radial-gradient":
        cx, cy, radius = appearance.parameters[:3]
        t = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / max(radius, 1e-8)
    else:
        raise ValueError(f"unknown appearance kind {appearance.kind!r}")
    t = np.clip(t, 0.0, 1.0)
    stops = sorted(appearance.stops, key=lambda item: item.offset)
    result = np.empty((height, width, 4), np.float32)
    result[:] = stops[-1].rgba_linear
    previous = stops[0]
    result[t <= previous.offset] = previous.rgba_linear
    for stop in stops[1:]:
        band = (t > previous.offset) & (t <= stop.offset)
        local = np.clip((t - previous.offset) / max(stop.offset - previous.offset, 1e-8), 0.0, 1.0)
        a = np.asarray(previous.rgba_linear, np.float32)
        b = np.asarray(stop.rgba_linear, np.float32)
        result[band] = (a + (b - a) * local[band, None])
        previous = stop
    return result


def _loop_bounds(loop: LoopNode) -> tuple[float, float, float, float] | None:
    rows = [primitive_points(primitive, 96) for primitive in loop.primitives]
    rows = [row for row in rows if len(row)]
    if not rows:
        return None
    points = np.vstack(rows)
    return (float(points[:, 0].min()), float(points[:, 1].min()),
            float(points[:, 0].max()), float(points[:, 1].max()))


def _analytic_primitive_mask(shape: tuple[int, int], primitive,
                             scale: int, origin: tuple[float, float]) -> np.ndarray:
    yy, xx = np.mgrid[:shape[0], :shape[1]].astype(np.float64)
    xx = (xx + .5) / scale + origin[0]
    yy = (yy + .5) / scale + origin[1]
    kind = primitive.kind
    parameters = primitive.parameters
    if kind == "circle":
        cx, cy, radius = parameters
        return (xx - cx) ** 2 + (yy - cy) ** 2 <= radius * radius
    cx, cy, width, height, angle = parameters[:5]
    theta = math.radians(angle)
    dx, dy = xx - cx, yy - cy
    local_x = math.cos(theta) * dx + math.sin(theta) * dy
    local_y = -math.sin(theta) * dx + math.cos(theta) * dy
    if kind == "ellipse":
        rx, ry = max(width, 1e-9), max(height, 1e-9)
        return (local_x / rx) ** 2 + (local_y / ry) ** 2 <= 1.0
    half_width, half_height = max(width * .5, 0.0), max(height * .5, 0.0)
    if kind == "rect":
        return (np.abs(local_x) <= half_width) & (np.abs(local_y) <= half_height)
    radius = min(max(float(parameters[5]), 0.0), half_width, half_height)
    qx = np.abs(local_x) - (half_width - radius)
    qy = np.abs(local_y) - (half_height - radius)
    outside = np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2)
    signed = outside + np.minimum(np.maximum(qx, qy), 0.0) - radius
    return signed <= 0.0

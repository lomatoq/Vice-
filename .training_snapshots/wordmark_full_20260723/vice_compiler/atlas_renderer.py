"""Deterministic batched ROI renderer for the phase-3 exact court pass."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import cv2
import numpy as np

from .native_core import pack_atlas


SUPPORTED_KINDS = frozenset({
    "mask", "circle", "jagged_circle", "ring", "rect",
    "rounded_rect", "stroke", "gradient", "band_stack", "eraser", "raster",
})


@dataclass(frozen=True)
class RoiRenderRequest:
    id: str
    roi_xyxy: tuple[int, int, int, int]
    kind: str
    parameters: tuple[tuple[str, float | int | str], ...] = ()
    color0_linear: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    color1_linear: tuple[float, float, float, float] | None = None
    support_mask: np.ndarray | None = None
    raster_premultiplied_linear_rgba: np.ndarray | None = None
    supersample: int = 4

    def parameter_map(self) -> dict[str, float | int | str]:
        return dict(self.parameters)

    def validate(self, canvas_size: tuple[int, int]) -> None:
        if not self.id or self.kind not in SUPPORTED_KINDS:
            raise ValueError("invalid ROI render request id/kind")
        width, height = canvas_size
        x1, y1, x2, y2 = self.roi_xyxy
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("ROI render request lies outside canvas")
        if not 1 <= int(self.supersample) <= 8:
            raise ValueError("ROI supersample must be within [1,8]")
        colors = (*self.color0_linear,
                  *(self.color1_linear or self.color0_linear))
        if not all(math.isfinite(float(value)) for value in colors):
            raise ValueError("ROI request contains a non-finite color")
        for _name, value in self.parameters:
            if isinstance(value, (float, int)) and not math.isfinite(float(value)):
                raise ValueError("ROI request contains a non-finite parameter")
        if self.support_mask is not None:
            mask = np.asarray(self.support_mask)
            if mask.ndim != 2:
                raise ValueError("ROI support mask must be two-dimensional")
            if mask.shape not in {
                (height, width), (y2 - y1, x2 - x1)
            }:
                raise ValueError("ROI support mask shape is not canvas/ROI sized")
        if self.kind == "raster":
            if self.raster_premultiplied_linear_rgba is None:
                raise ValueError("raster ROI request lacks a render patch")
            patch = np.asarray(self.raster_premultiplied_linear_rgba)
            if patch.shape != (y2 - y1, x2 - x1, 4):
                raise ValueError("raster ROI patch shape differs from its ROI")
            if not np.all(np.isfinite(patch)):
                raise ValueError("raster ROI patch contains non-finite values")
        elif self.raster_premultiplied_linear_rgba is not None:
            raise ValueError("non-raster ROI request carries a raster patch")


@dataclass(frozen=True)
class AtlasPlacement:
    request_id: str
    atlas_xyxy: tuple[int, int, int, int]
    source_roi_xyxy: tuple[int, int, int, int]


@dataclass(frozen=True)
class AtlasRenderResult:
    atlas_premultiplied_linear_rgba: np.ndarray
    placements: tuple[AtlasPlacement, ...]
    crops: tuple[tuple[str, np.ndarray], ...]
    exact_render_pixels: int
    supersampled_pixels: int
    renderer: str

    def by_id(self) -> dict[str, np.ndarray]:
        return dict(self.crops)


class ExactRoiAtlas:
    def __init__(
        self, *, max_requests: int = 256, padding: int = 1,
        max_atlas_width: int = 2048,
    ) -> None:
        self.max_requests = int(max_requests)
        self.padding = max(0, int(padding))
        self.max_atlas_width = max(32, int(max_atlas_width))

    def render(
        self, requests: Iterable[RoiRenderRequest],
        *, canvas_size: tuple[int, int],
    ) -> AtlasRenderResult:
        rows = tuple(requests)
        if not rows or len(rows) > self.max_requests:
            raise ValueError("ROI atlas request count is outside the bounded contract")
        if len({row.id for row in rows}) != len(rows):
            raise ValueError("ROI atlas request ids are not unique")
        for row in rows:
            row.validate(canvas_size)
        rendered = [(row, _render_request(row, canvas_size)) for row in rows]
        placements, atlas_shape = self._pack(rendered)
        atlas = np.zeros((*atlas_shape, 4), dtype=np.float32)
        crop_rows: list[tuple[str, np.ndarray]] = []
        exact_pixels = 0
        supersampled_pixels = 0
        placement_rows: list[AtlasPlacement] = []
        for (row, crop), (ax1, ay1, ax2, ay2) in zip(rendered, placements):
            atlas[ay1:ay2, ax1:ax2] = crop
            crop.setflags(write=False)
            crop_rows.append((row.id, crop))
            exact_pixels += int(crop.shape[0] * crop.shape[1])
            supersampled_pixels += int(
                crop.shape[0] * crop.shape[1] * row.supersample ** 2
            )
            placement_rows.append(AtlasPlacement(
                request_id=row.id, atlas_xyxy=(ax1, ay1, ax2, ay2),
                source_roi_xyxy=row.roi_xyxy,
            ))
        atlas.setflags(write=False)
        return AtlasRenderResult(
            atlas_premultiplied_linear_rgba=atlas,
            placements=tuple(placement_rows), crops=tuple(crop_rows),
            exact_render_pixels=exact_pixels,
            supersampled_pixels=supersampled_pixels,
            renderer="pcdc-deterministic-roi-atlas/v1",
        )

    def _pack(
        self, rendered: list[tuple[RoiRenderRequest, np.ndarray]]
    ) -> tuple[list[tuple[int, int, int, int]], tuple[int, int]]:
        total = sum(int(crop.shape[0] * crop.shape[1]) for _row, crop in rendered)
        widest = max(int(crop.shape[1]) for _row, crop in rendered)
        target_width = min(
            self.max_atlas_width,
            max(widest, int(math.ceil(math.sqrt(max(1, total)))))
        )
        placements, atlas_wh = pack_atlas(
            ((crop.shape[1], crop.shape[0]) for _request, crop in rendered),
            target_width=target_width, padding=self.padding,
        )
        return list(placements), (atlas_wh[1], atlas_wh[0])


def _mask_for_roi(
    request: RoiRenderRequest, canvas_size: tuple[int, int]
) -> np.ndarray | None:
    if request.support_mask is None:
        return None
    mask = np.asarray(request.support_mask, dtype=bool)
    x1, y1, x2, y2 = request.roi_xyxy
    width, height = canvas_size
    if mask.shape == (height, width):
        return mask[y1:y2, x1:x2]
    return mask


def _render_request(
    request: RoiRenderRequest, canvas_size: tuple[int, int]
) -> np.ndarray:
    x1, y1, x2, y2 = request.roi_xyxy
    width, height = x2 - x1, y2 - y1
    if request.kind == "raster":
        return np.ascontiguousarray(np.clip(
            np.asarray(request.raster_premultiplied_linear_rgba, np.float32),
            0.0, 1.0,
        ), dtype=np.float32)
    ss = int(request.supersample)
    high_height, high_width = height * ss, width * ss
    yy, xx = np.mgrid[:high_height, :high_width].astype(np.float32)
    gx = x1 + (xx + 0.5) / ss
    gy = y1 + (yy + 0.5) / ss
    parameters = request.parameter_map()
    support = _mask_for_roi(request, canvas_size)
    if support is not None:
        support_high = cv2.resize(
            support.astype(np.uint8), (high_width, high_height),
            interpolation=cv2.INTER_NEAREST,
        ).astype(bool)
    else:
        support_high = np.ones((high_height, high_width), dtype=bool)

    kind = request.kind
    if kind in {"mask", "gradient", "band_stack", "eraser"}:
        coverage = support_high
    elif kind in {"circle", "jagged_circle"}:
        cx = float(parameters["cx"]); cy = float(parameters["cy"])
        radius = max(0.0, float(parameters["radius"]))
        dx, dy = gx - cx, gy - cy
        if kind == "jagged_circle":
            angle = np.arctan2(dy, dx)
            lobes = max(3, int(parameters.get("lobes", 12)))
            amplitude = float(parameters.get("amplitude", 0.8))
            phase = float(parameters.get("phase", 0.0))
            local_radius = radius + amplitude * np.sin(lobes * angle + phase)
        else:
            local_radius = radius
        coverage = (dx * dx + dy * dy <= local_radius * local_radius) & support_high
    elif kind == "ring":
        cx = float(parameters["cx"]); cy = float(parameters["cy"])
        radius = max(0.0, float(parameters["radius"]))
        stroke_width = max(0.0, float(parameters["width"]))
        distance = np.sqrt(np.square(gx - cx) + np.square(gy - cy))
        coverage = (np.abs(distance - radius) <= stroke_width * 0.5) & support_high
    elif kind in {"rect", "rounded_rect"}:
        cx = float(parameters["cx"]); cy = float(parameters["cy"])
        rect_width = max(0.0, float(parameters["width"]))
        rect_height = max(0.0, float(parameters["height"]))
        dx = np.abs(gx - cx); dy = np.abs(gy - cy)
        if kind == "rect":
            coverage = (dx <= rect_width * 0.5) & (dy <= rect_height * 0.5)
        else:
            radius = min(
                max(0.0, float(parameters.get("radius", 0.0))),
                rect_width * 0.5, rect_height * 0.5,
            )
            qx = dx - (rect_width * 0.5 - radius)
            qy = dy - (rect_height * 0.5 - radius)
            outside = np.sqrt(np.square(np.maximum(qx, 0.0))
                              + np.square(np.maximum(qy, 0.0)))
            signed = outside + np.minimum(np.maximum(qx, qy), 0.0) - radius
            coverage = signed <= 0.0
        coverage &= support_high
    elif kind == "stroke":
        start = np.asarray([float(parameters["x1"]), float(parameters["y1"])])
        end = np.asarray([float(parameters["x2"]), float(parameters["y2"])])
        stroke_width = max(0.0, float(parameters["width"]))
        vx, vy = end - start
        denominator = max(1e-12, float(vx * vx + vy * vy))
        t = np.clip(((gx - start[0]) * vx + (gy - start[1]) * vy)
                    / denominator, 0.0, 1.0)
        px = start[0] + t * vx; py = start[1] + t * vy
        coverage = (
            np.square(gx - px) + np.square(gy - py)
            <= (stroke_width * 0.5) ** 2
        ) & support_high
    else:  # pragma: no cover - guarded by validate
        raise ValueError(f"unsupported ROI kind {kind!r}")

    color0 = np.asarray(request.color0_linear, np.float32)
    color1 = np.asarray(request.color1_linear or request.color0_linear, np.float32)
    if kind in {"gradient", "band_stack"}:
        gx0 = float(parameters.get("x0", x1)); gy0 = float(parameters.get("y0", y1))
        gx1 = float(parameters.get("x1", x2)); gy1 = float(parameters.get("y1", y1))
        dx, dy = gx1 - gx0, gy1 - gy0
        t = np.clip(
            ((gx - gx0) * dx + (gy - gy0) * dy)
            / max(1e-12, dx * dx + dy * dy), 0.0, 1.0,
        )
        if kind == "band_stack":
            bands = max(2, int(parameters.get("bands", 5)))
            t = np.round(t * (bands - 1)) / (bands - 1)
        straight = color0[None, None, :] * (1.0 - t[..., None])
        straight += color1[None, None, :] * t[..., None]
    else:
        straight = np.empty((high_height, high_width, 4), np.float32)
        straight[:] = color0
    alpha = np.clip(straight[..., 3] * coverage, 0.0, 1.0)
    high = np.empty_like(straight)
    high[..., :3] = np.clip(straight[..., :3], 0.0, 1.0) * alpha[..., None]
    high[..., 3] = alpha
    if kind == "eraser":
        high[:] = 0.0
    if ss > 1:
        native = cv2.resize(
            high, (width, height), interpolation=cv2.INTER_AREA
        )
    else:
        native = high
    return np.ascontiguousarray(np.clip(native, 0.0, 1.0), dtype=np.float32)

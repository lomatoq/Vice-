"""Soft solid/gradient/alpha appearance hypotheses with late palette projection."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .contracts import Appearance, GradientStop, RasterProfile
from .ingest import CanonicalRaster, oklab_to_linear_rgb


@dataclass(frozen=True)
class AppearanceHypotheses:
    appearances: tuple[Appearance, ...]
    probabilities: np.ndarray  # H x W x K, never a committed label map
    background_index: int
    cluster_covariance: tuple[tuple[float, ...], ...]

    def validate(self) -> None:
        if self.probabilities.ndim != 3 or self.probabilities.shape[2] != len(self.appearances):
            raise ValueError("appearance probabilities/appearance count mismatch")
        sums = self.probabilities.sum(axis=2)
        if not np.allclose(sums, 1.0, atol=2e-4):
            raise ValueError("appearance probabilities are not normalized")
        if not 0 <= self.background_index < len(self.appearances):
            raise ValueError("invalid background index")


def infer_appearances(raster: CanonicalRaster, profile: RasterProfile,
                      *, max_colors: int = 24, seed: int = 20260719) -> AppearanceHypotheses:
    lab = raster.oklab
    alpha = raster.alpha_native
    visible = alpha > 0.03
    samples = lab[visible]
    if not len(samples):
        samples = np.zeros((1, 3), np.float32)
    expected = sum(v * p for v, p in zip(profile.palette_complexity.values,
                                         profile.palette_complexity.probabilities))
    k = int(np.clip(round(expected), 2 if len(samples) >= 2 else 1,
                    min(max_colors, max(1, len(samples)))))
    if len(samples) > 80_000:
        rng = np.random.default_rng(seed)
        samples_fit = samples[rng.choice(len(samples), 80_000, replace=False)]
    else:
        samples_fit = samples
    cv2.setRNGSeed(int(seed & 0x7FFFFFFF))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 1e-4)
    if k == 1:
        centers = np.mean(samples_fit, axis=0, keepdims=True)
    else:
        _, _, centers = cv2.kmeans(samples_fit.astype(np.float32), k, None, criteria,
                                   2, cv2.KMEANS_PP_CENTERS)
    centers = _consolidate_centers(centers.astype(np.float32), samples)
    k = len(centers)
    dist2 = np.sum((lab[..., None, :] - centers[None, None, :, :]) ** 2, axis=3)
    nearest = np.sqrt(np.partition(dist2.reshape(-1, k), min(1, k - 1), axis=1)[:, min(1, k - 1)])
    temperature = float(np.clip(np.median(nearest) ** 2, 2e-4, 0.025))
    logits = -dist2 / temperature
    logits -= logits.max(axis=2, keepdims=True)
    probabilities = np.exp(logits).astype(np.float32)
    probabilities /= np.maximum(probabilities.sum(axis=2, keepdims=True), 1e-12)
    transparent_background = float(np.mean(alpha < .999)) > 1e-4
    if transparent_background:
        probabilities *= alpha[..., None]
        probabilities = np.concatenate((probabilities, (1.0 - alpha)[..., None]), axis=2)
        probabilities /= np.maximum(probabilities.sum(axis=2, keepdims=True), 1e-12)
        background = k
    else:
        border = np.concatenate((probabilities[0], probabilities[-1],
                                 probabilities[:, 0], probabilities[:, -1]), axis=0)
        background = int(np.argmax(border.mean(axis=0)))
    hard = np.argmax(probabilities, axis=2)
    appearances: list[Appearance] = []
    covariances: list[tuple[float, ...]] = []
    for index, center in enumerate(centers):
        weights = probabilities[..., index] * alpha
        total = max(float(weights.sum()), 1e-8)
        core_alpha = alpha[(hard == index) & visible]
        opacity = float(np.percentile(core_alpha, 90)) if len(core_alpha) else 1.0
        rgba = tuple(float(v) for v in oklab_to_linear_rgb(center[None, :])[0]) + (
            float(np.clip(opacity, 0.0, 1.0)),)
        delta = lab - center
        covariance = tuple(float(np.sum(weights * delta[..., channel] ** 2) / total)
                           for channel in range(3))
        appearances.append(Appearance(
            id=f"appearance-{index}", kind="solid", rgba_linear=rgba,
            confidence=float(np.clip(probabilities[..., index][hard == index].mean()
                                     if np.any(hard == index) else 0.0, 0.0, 1.0)),
            covariance=covariance, provenance=("soft-oklab-mixture",),
        ))
        covariances.append(covariance)
    if transparent_background:
        appearances.append(Appearance(
            id=f"appearance-{k}", kind="solid", rgba_linear=(0.0, 0.0, 0.0, 0.0),
            confidence=1.0, covariance=(0.0, 0.0, 0.0),
            provenance=("explicit-transparent-background",),
        ))
        covariances.append((0.0, 0.0, 0.0))
    result = AppearanceHypotheses(tuple(appearances), probabilities,
                                  background, tuple(covariances))
    result.validate()
    return result


def _consolidate_centers(centers: np.ndarray, samples: np.ndarray) -> np.ndarray:
    """Remove tiny codec/AA modes and merge perceptually indistinguishable modes."""
    if len(centers) <= 1:
        return centers
    dist2 = np.sum((samples[:, None, :] - centers[None, :, :]) ** 2, axis=2)
    labels = np.argmin(dist2, axis=1)
    counts = np.bincount(labels, minlength=len(centers))
    linear_centers = oklab_to_linear_rgb(centers)
    minimum = max(2, int(np.ceil(.004 * len(samples))))
    order = sorted(range(len(centers)), key=lambda index: (-int(counts[index]), index))
    kept: list[np.ndarray] = []
    weights: list[int] = []
    for index in order:
        if counts[index] < minimum and kept:
            continue
        if _is_low_support_composite(index, linear_centers, counts):
            continue
        center = centers[index]
        target = next((j for j, other in enumerate(kept)
                       if float(np.linalg.norm(center - other)) < .06), None)
        if target is None:
            kept.append(center.copy())
            weights.append(max(1, int(counts[index])))
        else:
            total = weights[target] + int(counts[index])
            kept[target] = (kept[target] * weights[target] + center * counts[index]) / max(1, total)
            weights[target] = total
    return np.asarray(kept or [centers[int(np.argmax(counts))]], np.float32)


def _is_low_support_composite(index: int, centers: np.ndarray,
                              counts: np.ndarray) -> bool:
    """Reject AA/compositing modes explained by two stronger source paints."""
    support = max(1, int(counts[index]))
    stronger = [row for row in range(len(centers))
                if row != index and counts[row] >= 4 * support]
    value = centers[index]
    for position, first in enumerate(stronger):
        for second in stronger[position + 1:]:
            direction = centers[second] - centers[first]
            denominator = float(np.dot(direction, direction))
            if denominator < 1e-8:
                continue
            fraction = float(np.dot(value - centers[first], direction) / denominator)
            if .03 < fraction < .97:
                projected = centers[first] + fraction * direction
                if float(np.linalg.norm(value - projected)) < .018:
                    return True
    return False


def fit_region_appearance(raster: CanonicalRaster, mask: np.ndarray,
                          solid: Appearance, *, allow_gradient: bool = True) -> Appearance:
    """Compete a solid against linear/radial models using an MDL-style penalty."""
    ys, xs = np.nonzero(mask & (raster.alpha_native > 1e-3))
    if len(xs) < 12 or not allow_gradient:
        return solid
    alpha = raster.alpha_native[ys, xs]
    rgb = raster.rgba_linear_premul[ys, xs, :3] / np.maximum(alpha[:, None], 1e-5)
    xn = xs / max(1, raster.width - 1)
    yn = ys / max(1, raster.height - 1)
    design = np.column_stack((np.ones(len(xs)), xn, yn)).astype(np.float64)
    params, *_ = np.linalg.lstsq(design, rgb.astype(np.float64), rcond=None)
    prediction = np.clip(design @ params, 0.0, 1.0)
    linear_mse = float(np.mean((prediction - rgb) ** 2))
    solid_rgb = np.asarray(solid.rgba_linear[:3], np.float32)
    solid_mse = float(np.mean((rgb - solid_rgb) ** 2))
    # Radial hypotheses compete independently; the center is a model parameter,
    # not assumed to be the bounding-box center.
    radial_rows = []
    for cx, cy in ((float(np.mean(xs)), float(np.mean(ys))),
                   ((float(xs.min()) + float(xs.max())) * .5,
                    (float(ys.min()) + float(ys.max())) * .5)):
        radius = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
        radius_max = max(float(radius.max()), 1e-6)
        radial_design = np.column_stack((np.ones(len(xs)), radius / radius_max))
        radial_params, *_ = np.linalg.lstsq(radial_design, rgb.astype(np.float64), rcond=None)
        radial_prediction = np.clip(radial_design @ radial_params, 0.0, 1.0)
        radial_rows.append((float(np.mean((radial_prediction - rgb) ** 2)),
                            cx, cy, radius_max, radial_params))
    radial_mse, radial_cx, radial_cy, radial_radius, radial_params = min(
        radial_rows, key=lambda row: row[0])
    # Description length of two/three colour slopes plus geometric parameters.
    linear_penalty = 6.0 / max(1.0, len(xs)) * 3e-4
    radial_penalty = 5.0 / max(1.0, len(xs)) * 3e-4
    best_kind, best_mse, best_penalty = min(
        ("linear-gradient", linear_mse, linear_penalty),
        ("radial-gradient", radial_mse, radial_penalty),
        key=lambda row: row[1] + row[2],
    )
    if best_mse + best_penalty >= solid_mse * 0.82:
        return solid
    opacity = float(np.percentile(alpha, 90))
    if best_kind == "radial-gradient":
        geometry = (radial_cx, radial_cy, radial_radius)
        color0 = np.clip(radial_params[0], 0.0, 1.0)
        color1 = np.clip(radial_params[0] + radial_params[1], 0.0, 1.0)
    else:
        slopes = params[1:, :]
        tensor = slopes @ slopes.T
        _, vectors = np.linalg.eigh(tensor)
        direction = vectors[:, -1]
        projection = np.column_stack((xn, yn)) @ direction
        t0, t1 = float(projection.min()), float(projection.max())
        center = np.array([float(np.mean(xn)), float(np.mean(yn))])
        center_projection = float(np.dot(center, direction))
        start = center + direction * (t0 - center_projection)
        end = center + direction * (t1 - center_projection)
        geometry = (float(start[0] * max(1, raster.width - 1)),
                    float(start[1] * max(1, raster.height - 1)),
                    float(end[0] * max(1, raster.width - 1)),
                    float(end[1] * max(1, raster.height - 1)))
        color0 = np.clip(np.array([1.0, start[0], start[1]]) @ params, 0.0, 1.0)
        color1 = np.clip(np.array([1.0, end[0], end[1]]) @ params, 0.0, 1.0)
    return Appearance(
        id=solid.id, kind=best_kind, rgba_linear=solid.rgba_linear,
        parameters=geometry,
        stops=(GradientStop(0.0, tuple(float(v) for v in color0) + (opacity,)),
               GradientStop(1.0, tuple(float(v) for v in color1) + (opacity,))),
        confidence=float(np.clip(1.0 - best_mse / max(solid_mse, 1e-8), 0.0, 1.0)),
        covariance=solid.covariance, provenance=solid.provenance + (best_kind + "-mdl",),
    )

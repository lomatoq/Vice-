"""Spatial raster diagnosis: AA/blur/JPEG/artwork/text/diagram evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from .contracts import Distribution, RasterProfile
from .ingest import CanonicalRaster


@dataclass(frozen=True)
class ProfileFields:
    confidence: np.ndarray
    edge_strength: np.ndarray
    text_probability: np.ndarray
    diagram_probability: np.ndarray
    local_blur: np.ndarray


def diagnose_raster(raster: CanonicalRaster) -> tuple[RasterProfile, ProfileFields]:
    rgb = raster.rgba_srgb_straight[..., :3]
    alpha = raster.alpha_native
    gray = cv2.cvtColor((rgb * 255.0 + 0.5).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    gx = cv2.Scharr(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Scharr(gray, cv2.CV_32F, 0, 1)
    edge = np.sqrt(gx * gx + gy * gy)
    edge /= max(float(np.percentile(edge, 99.0)), 1e-6)
    edge = np.clip(edge, 0.0, 1.0).astype(np.float32)

    lap = np.abs(cv2.Laplacian(gray, cv2.CV_32F, ksize=3))
    local_lap = cv2.GaussianBlur(lap, (0, 0), 1.2)
    local_blur = np.exp(-4.0 * local_lap).astype(np.float32)
    edge_pixels = edge > 0.12
    soft_edge_fraction = float(np.mean((edge > 0.04) & (edge < 0.45)))
    hard_edge_fraction = float(np.mean(edge > 0.65))

    quant = np.round(rgb * 31.0).astype(np.uint8)
    packed = quant[..., 0].astype(np.int32) * 1024 + quant[..., 1].astype(np.int32) * 32 + quant[..., 2]
    visible = alpha > 1e-3
    unique = int(np.unique(packed[visible]).size) if visible.any() else 1
    palette_ratio = unique / max(1, int(visible.sum()))
    smooth_residual = np.mean(np.abs(gray - cv2.GaussianBlur(gray, (0, 0), 1.0)))
    artwork_prob = float(np.clip(1.12 - 2.6 * palette_ratio - 1.8 * smooth_residual, 0.02, 0.98))
    photo_prob = 1.0 - artwork_prob

    blockiness = _jpeg_blockiness(gray)
    jpeg_dist = None
    if raster.source.format in {"JPEG", "JPG", "MPO"} or blockiness > 0.012:
        quality = float(np.clip(96.0 - 950.0 * blockiness, 20.0, 95.0))
        jpeg_dist = _tri_distribution((max(20.0, quality - 15), quality, min(98.0, quality + 15)), 1)

    blur_sigma = float(np.clip(1.4 - 5.0 * float(np.median(local_lap[edge_pixels]))
                               if edge_pixels.any() else 0.6, 0.0, 2.5))
    blur_dist = _tri_distribution((max(0.0, blur_sigma - .4), blur_sigma, blur_sigma + .4), 1)
    gamma_dist = Distribution((1.8, 2.2, 2.4), (0.2, 0.6, 0.2))
    complexity_values = (2.0, 4.0, 8.0, 16.0, 32.0, 64.0)
    complexity_center = float(np.clip(math.log2(max(unique, 2)), 1.0, 6.0))
    weights = np.exp(-0.5 * ((np.arange(1, 7) - complexity_center) / 1.0) ** 2)
    weights /= weights.sum()
    palette_dist = Distribution(complexity_values, tuple(float(v) for v in weights))

    text_map, text_prob = _text_field(gray, edge)
    diagram_map, diagram_prob = _diagram_field(gray, edge)
    gradient_prob = float(np.clip(3.0 * soft_edge_fraction - 1.2 * hard_edge_fraction, 0.0, 1.0))
    confidence = np.clip((0.35 + 0.65 * edge) * (1.0 - 0.55 * local_blur)
                         + 0.35 * text_map + 0.25 * diagram_map, 0.03, 1.0).astype(np.float32)

    aa_probs = np.array([
        max(0.01, soft_edge_fraction),
        max(0.01, hard_edge_fraction),
        max(0.01, 1.0 - soft_edge_fraction - hard_edge_fraction),
    ], np.float64)
    aa_probs /= aa_probs.sum()
    profile = RasterProfile(
        artwork_prob=artwork_prob, photo_prob=photo_prob,
        aa_mode_probs=tuple(float(v) for v in aa_probs),
        blur_sigma_distribution=blur_dist, gamma_distribution=gamma_dist,
        jpeg_quality_distribution=jpeg_dist, palette_complexity=palette_dist,
        text_probability=text_prob, diagram_probability=diagram_prob,
        gradient_probability=gradient_prob,
        transparency_probability=float(np.mean(alpha < 0.999)),
    )
    profile.validate()
    return profile, ProfileFields(confidence, edge, text_map, diagram_map, local_blur)


def _tri_distribution(values: tuple[float, float, float], peak: int) -> Distribution:
    probabilities = [0.2, 0.2, 0.2]
    probabilities[peak] = 0.6
    return Distribution(tuple(float(v) for v in values), tuple(probabilities))


def _jpeg_blockiness(gray: np.ndarray) -> float:
    if min(gray.shape) < 16:
        return 0.0
    vertical = np.abs(np.diff(gray, axis=1))
    horizontal = np.abs(np.diff(gray, axis=0))
    vb = float(np.mean(vertical[:, 7::8])) if vertical.shape[1] > 7 else 0.0
    hb = float(np.mean(horizontal[7::8, :])) if horizontal.shape[0] > 7 else 0.0
    vi = float(np.mean(np.delete(vertical, np.s_[7::8], axis=1)))
    hi = float(np.mean(np.delete(horizontal, np.s_[7::8], axis=0)))
    return max(0.0, 0.5 * ((vb - vi) + (hb - hi)))


def _text_field(gray: np.ndarray, edge: np.ndarray) -> tuple[np.ndarray, float]:
    candidates: list[tuple[int, int, int, int]] = []
    height_limit = max(3, int(0.48 * gray.shape[0]))
    gray_u8 = (gray * 255).astype(np.uint8)
    # Text can be darker OR lighter than its local field (white wordmarks on
    # coloured badges are common).  The previous inverse-only detector marked
    # City Breach/Mastercard as text_probability=0 and disabled the entire text
    # scene before it could compete.
    for threshold_type in (cv2.THRESH_BINARY_INV, cv2.THRESH_BINARY):
        binary = cv2.adaptiveThreshold(
            gray_u8, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            threshold_type, 15, 4)
        count, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
        for index in range(1, count):
            x, y, w, h, area = (int(v) for v in stats[index])
            touches = int(x == 0) + int(y == 0) + int(x + w == gray.shape[1]) \
                + int(y + h == gray.shape[0])
            if touches >= 2 or area > .20 * gray.size:
                continue
            if (2 <= h <= height_limit and 1 <= w <= 3.0 * h
                    and 2 <= area <= 0.85 * w * h):
                candidates.append((x, y, w, h))
    field = np.zeros_like(gray, np.float32)
    if not candidates:
        return field, 0.0
    heights = np.array([row[3] for row in candidates], np.float32)
    for x, y, w, h in candidates:
        peers = sum(abs((yy + hh * .5) - (y + h * .5)) <= max(h, hh) * .55
                    and 0.45 <= hh / max(h, 1) <= 2.2
                    for _, yy, _, hh in candidates)
        if peers >= 3:
            pad = max(1, int(round(np.median(heights) * .2)))
            field[max(0, y - pad):min(gray.shape[0], y + h + pad),
                  max(0, x - pad):min(gray.shape[1], x + w + pad)] = 1.0
    field = cv2.GaussianBlur(field, (0, 0), 1.0)
    probability = float(np.clip(8.0 * np.mean(field) + 0.2 * (len(candidates) >= 3), 0.0, 1.0))
    return field.astype(np.float32), probability


def _diagram_field(gray: np.ndarray, edge: np.ndarray) -> tuple[np.ndarray, float]:
    lines = cv2.HoughLinesP((edge > 0.35).astype(np.uint8) * 255, 1, np.pi / 180,
                            threshold=max(8, min(gray.shape) // 10),
                            minLineLength=max(5, min(gray.shape) // 12), maxLineGap=2)
    field = np.zeros_like(gray, np.float32)
    lengths: list[float] = []
    if lines is not None:
        for row in np.asarray(lines).reshape(-1, 4):
            x0, y0, x1, y1 = (int(v) for v in row)
            length = math.hypot(x1 - x0, y1 - y0)
            lengths.append(length)
            cv2.line(field, (x0, y0), (x1, y1), 1.0, 3, cv2.LINE_AA)
    density = sum(lengths) / max(1.0, float(gray.shape[0] * gray.shape[1]))
    probability = float(np.clip(2.2 * density + 0.08 * len(lengths), 0.0, 1.0))
    return np.clip(field, 0.0, 1.0), probability

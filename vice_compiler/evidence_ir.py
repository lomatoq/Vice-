"""Raster Evidence IR (REIR) for the Proof-Carrying Design Compiler.

REIR is a non-semantic, immutable evidence substrate.  It decodes and measures
the raster exactly once; downstream passes consume this object and are not
allowed to reopen the source or recompute color, morphology, distance, or
boundary pyramids.
"""

from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
import io
import json
import math
import os
from pathlib import Path
import pickle
import sys
import tempfile
import threading
import time
from typing import Any, Callable

import cv2
import numpy as np
import PIL
from PIL import Image, ImageCms, ImageOps

from .cell_complex import CellComplex, build_cell_complex
from .hierarchy import RegionHierarchy, build_ucm_hierarchy
from .inclusion_trees import InclusionForest, build_inclusion_forest
from .interface_ir import InterfaceGraph, build_interface_graph
from .runtime_budget import StageBudget, StageProfiler


SCHEMA = "pcdc-reir/v29"
PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = PROJECT / ".vice_pcdc_cache" / "evidence"
_MAX_PROPOSAL_TOKENS = 384
_SRGB_AXIS = np.arange(256, dtype=np.float32) / 255.0
_SRGB_LINEAR_LUT = np.where(
    _SRGB_AXIS <= 0.04045,
    _SRGB_AXIS / 12.92,
    np.power((_SRGB_AXIS + 0.055) / 1.055, 2.4),
).astype(np.float32)
_OKLAB_M1 = np.asarray(
    [
        [0.4122214708, 0.5363325363, 0.0514459929],
        [0.2119034982, 0.6806995451, 0.1073969566],
        [0.0883024619, 0.2817188376, 0.6299787005],
    ], dtype=np.float32,
)
_OKLAB_M2 = np.asarray(
    [
        [0.2104542553, 0.7936177850, -0.0040720468],
        [1.9779984951, -2.4285922050, 0.4505937099],
        [0.0259040371, 0.7827717662, -0.8086757660],
    ], dtype=np.float32,
)


@dataclass(frozen=True)
class CoordinateTransform:
    encoded_size: tuple[int, int]
    oriented_size: tuple[int, int]
    processing_size: tuple[int, int]
    processing_to_oriented_scale: tuple[float, float]
    exif_orientation_applied: bool
    crop_xyxy: tuple[int, int, int, int]


@dataclass(frozen=True)
class CanonicalRaster:
    straight_rgba: np.ndarray
    linear_premultiplied_rgba: np.ndarray
    oklab: np.ndarray
    transform: CoordinateTransform
    icc_policy: str
    source_mode: str


@dataclass(frozen=True)
class FormationHypothesis:
    family: str
    weight: float
    pixel_phase_xy: tuple[float, float]
    blur_sigma_range: tuple[float, float]
    gamma_range: tuple[float, float]
    jpeg_quality_range: tuple[int, int] | None
    chroma_subsampling: str
    resize_chain: str
    alpha_mode: str


@dataclass(frozen=True)
class ImageFormationPosterior:
    hypotheses: tuple[FormationHypothesis, ...]
    estimator: str
    uncertainty: float
    observations: tuple[tuple[str, float | str], ...]


@dataclass(frozen=True)
class BoundaryScale:
    sigma: float
    scale_to_processing: tuple[float, float]
    probability: np.ndarray
    orientation: np.ndarray
    orientation_distribution: np.ndarray
    phase_congruency: np.ndarray
    classical_edge: np.ndarray
    cross_scale_persistence: np.ndarray
    subpixel_offset: np.ndarray
    uncertainty: np.ndarray


@dataclass(frozen=True)
class ProposalToken:
    id: int
    family: str
    bbox_xyxy: tuple[int, int, int, int]
    score: float
    parameters: tuple[tuple[str, float | str], ...]
    provenance: str
    uncertainty: float
    support_leaf_ids: tuple[int, ...] = ()
    support_rle: tuple[tuple[int, int], ...] = ()
    support_bits: bytes = b""
    support_size: tuple[int, int] = (0, 0)


@dataclass(frozen=True)
class RasterEvidenceIR:
    schema: str
    source_path: str
    source_sha256: str
    config_fingerprint: str
    raster: CanonicalRaster
    formation_posterior: ImageFormationPosterior
    boundary_pyramid: tuple[BoundaryScale, ...]
    coverage_alpha: np.ndarray
    color_mixture_mean: np.ndarray
    color_mixture_variance: np.ndarray
    hierarchy: RegionHierarchy
    inclusion: InclusionForest
    cells: CellComplex
    interfaces: InterfaceGraph
    proposal_tokens: tuple[ProposalToken, ...]
    provenance: tuple[tuple[str, str], ...]
    stage_profile: dict[str, Any]

    @property
    def width(self) -> int:
        return int(self.raster.straight_rgba.shape[1])

    @property
    def height(self) -> int:
        return int(self.raster.straight_rgba.shape[0])

    def validate(self) -> None:
        shape = self.raster.straight_rgba.shape[:2]
        if self.schema != SCHEMA:
            raise ValueError("unsupported REIR schema")
        if self.raster.straight_rgba.shape != (*shape, 4):
            raise ValueError("straight RGBA shape mismatch")
        if self.raster.linear_premultiplied_rgba.shape != (*shape, 4):
            raise ValueError("linear RGBA shape mismatch")
        if self.raster.oklab.shape != (*shape, 3):
            raise ValueError("Oklab shape mismatch")
        if self.coverage_alpha.shape != shape:
            raise ValueError("coverage shape mismatch")
        for field in self.boundary_pyramid:
            field_shape = field.probability.shape
            if field.orientation.shape != field_shape:
                raise ValueError("boundary orientation shape mismatch")
            if field.orientation_distribution.shape != (*field_shape, 8):
                raise ValueError("orientation distribution must use 8 bins")
            if field.phase_congruency.shape != field_shape:
                raise ValueError("phase-congruency shape mismatch")
            if field.classical_edge.shape != field_shape:
                raise ValueError("classical-edge shape mismatch")
            if field.cross_scale_persistence.shape != field_shape:
                raise ValueError("cross-scale persistence shape mismatch")
        if self.boundary_pyramid[0].probability.shape != shape:
            raise ValueError("base boundary scale must match processing lattice")
        transparent = self.raster.straight_rgba[..., 3] <= 0.0
        if np.any(self.raster.straight_rgba[..., :3][transparent] != 0.0):
            raise ValueError("RGB under alpha=0 leaked into evidence")
        for token in self.proposal_tokens:
            if any(
                leaf_id < 0 or leaf_id >= self.hierarchy.leaf_count
                for leaf_id in token.support_leaf_ids
            ):
                raise ValueError("proposal token references an invalid leaf")
            previous_end = 0
            for start, length in token.support_rle:
                end = start + length
                if (
                    start < previous_end or length <= 0
                    or end > token.support_size[0] * token.support_size[1]
                ):
                    raise ValueError("proposal token has invalid support RLE")
                previous_end = end
            if token.support_bits:
                expected = (
                    token.support_size[0] * token.support_size[1] + 7
                ) // 8
                if len(token.support_bits) != expected:
                    raise ValueError("proposal token has invalid bit-packed support")
        arrays = [
            self.raster.straight_rgba,
            self.raster.linear_premultiplied_rgba,
            self.raster.oklab,
            self.coverage_alpha,
            self.color_mixture_mean,
            self.color_mixture_variance,
            self.hierarchy.leaf_labels,
            self.hierarchy.ucm,
            self.cells.core_labels,
            self.cells.boundary_mask,
        ]
        arrays.extend(
            array
            for field in self.boundary_pyramid
            for array in (
                field.probability, field.orientation,
                field.orientation_distribution, field.phase_congruency,
                field.classical_edge, field.cross_scale_persistence,
                field.subpixel_offset, field.uncertainty,
            )
        )
        if any(array.flags.writeable for array in arrays):
            raise ValueError("REIR arrays must be immutable")
        self.hierarchy.validate()
        self.cells.validate()
        self.interfaces.validate()


def _freeze(array: np.ndarray, dtype: np.dtype | type | None = None) -> np.ndarray:
    result = np.asarray(array, dtype=dtype)
    if not result.flags.c_contiguous:
        result = np.ascontiguousarray(result)
    result.setflags(write=False)
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    return np.where(
        rgb <= 0.04045,
        rgb / 12.92,
        np.power((rgb + 0.055) / 1.055, 2.4),
    ).astype(np.float32)


def _linear_rgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    lms = cv2.transform(rgb, _OKLAB_M1)
    np.cbrt(lms, out=lms)
    return cv2.transform(lms, _OKLAB_M2).astype(np.float32, copy=False)


def _apply_icc(image: Image.Image) -> tuple[Image.Image, str]:
    profile = image.info.get("icc_profile")
    if not profile:
        return image, "assume-sRGB-no-embedded-ICC"
    try:
        alpha = image.getchannel("A") if "A" in image.getbands() else None
        rgb = image.convert("RGB")
        converted = ImageCms.profileToProfile(
            rgb,
            ImageCms.ImageCmsProfile(io.BytesIO(profile)),
            ImageCms.createProfile("sRGB"),
            outputMode="RGB",
        )
        if alpha is not None:
            converted.putalpha(alpha)
        return converted, "embedded-ICC-to-sRGB"
    except Exception:
        return image, "embedded-ICC-invalid-assume-sRGB"


def canonical_decode(path: str | Path, max_dim: int = 512) -> CanonicalRaster:
    source = Path(path)
    with Image.open(source) as encoded:
        encoded_size = encoded.size
        source_mode = encoded.mode
        exif = encoded.getexif()
        orientation = int(exif.get(274, 1)) if exif else 1
        if orientation == 1:
            # ImageOps.exif_transpose copies even when there is no transform.
            # Keep the decoded owner alive inside this context instead.
            oriented = encoded
            oriented.load()
        else:
            oriented = ImageOps.exif_transpose(encoded)
            oriented.load()
        oriented, icc_policy = _apply_icc(oriented)
        oriented_size = oriented.size
        width, height = oriented.size
        scale = min(1.0, float(max_dim) / max(width, height))
        processing_size = (
            max(1, int(round(width * scale))),
            max(1, int(round(height * scale))),
        )
        rgba_image = (
            oriented if oriented.mode == "RGBA" else oriented.convert("RGBA")
        )
        if scale < 1.0:
            # Pillow's RGBA resampler handles alpha-associated filtering and
            # avoids materializing a full-resolution NumPy lattice merely to
            # discard it.  This is decisive for large source PNGs at 512 px.
            rgba_image = rgba_image.resize(
                processing_size, resample=Image.Resampling.BOX
            )
        rgba_u8 = np.asarray(rgba_image, dtype=np.uint8).copy()
    rgba = rgba_u8.astype(np.float32) / 255.0
    alpha = rgba[..., 3:4]
    rgba[..., :3][alpha[..., 0] <= 0.0] = 0.0
    linear_straight = _SRGB_LINEAR_LUT[rgba_u8[..., :3]]
    linear_straight[alpha[..., 0] <= 0.0] = 0.0
    linear_premul = np.empty((*alpha.shape[:2], 4), dtype=np.float32)
    linear_premul[..., :3] = linear_straight * alpha
    linear_premul[..., 3] = alpha[..., 0]
    oklab = _linear_rgb_to_oklab(linear_straight)
    oklab[alpha[..., 0] <= 0.0] = 0.0
    transform = CoordinateTransform(
        encoded_size=tuple(int(v) for v in encoded_size),
        oriented_size=tuple(int(v) for v in oriented_size),
        processing_size=processing_size,
        processing_to_oriented_scale=(
            width / processing_size[0], height / processing_size[1]
        ),
        exif_orientation_applied=orientation != 1,
        crop_xyxy=(0, 0, width, height),
    )
    return CanonicalRaster(
        straight_rgba=_freeze(rgba, np.float32),
        linear_premultiplied_rgba=_freeze(linear_premul, np.float32),
        oklab=_freeze(oklab, np.float32),
        transform=transform,
        icc_policy=icc_policy,
        source_mode=source_mode,
    )


def estimate_formation_posterior(
    raster: CanonicalRaster, source_suffix: str
) -> ImageFormationPosterior:
    lightness = raster.oklab[..., 0]
    laplacian_variance = float(cv2.Laplacian(lightness, cv2.CV_32F).var())
    blur_center = float(np.clip(0.25 / math.sqrt(laplacian_variance + 1e-5), 0.2, 2.4))
    alpha_varies = float(np.ptp(raster.straight_rgba[..., 3])) > 1e-4
    jpeg = source_suffix.lower() in {".jpg", ".jpeg"}
    dx = np.abs(np.diff(lightness, axis=1))
    dy = np.abs(np.diff(lightness, axis=0))
    dx_mean = float(dx.mean()) if dx.size else 0.0
    dy_mean = float(dy.mean()) if dy.size else 0.0
    block_x = float(dx[:, 7::8].mean()) if dx.shape[1] >= 8 else dx_mean
    block_y = float(dy[7::8, :].mean()) if dy.shape[0] >= 8 else dy_mean
    jpeg_grid_score = float(np.clip(
        max(block_x - dx_mean, block_y - dy_mean)
        / max(1e-6, 0.5 * (dx_mean + dy_mean)),
        0.0,
        4.0,
    ))
    anisotropy = float(
        abs(dx_mean - dy_mean) / max(1e-6, dx_mean + dy_mean)
    )
    raw_weights = np.asarray(
        [0.44, 0.18 + 0.08 * anisotropy, 0.18 + 0.08 * anisotropy, 0.20],
        dtype=np.float64,
    )
    raw_weights /= raw_weights.sum()
    alpha_mode = "straight-or-premul" if alpha_varies else "opaque"
    hypotheses = tuple(
        FormationHypothesis(
            family=(
                "jpeg-aa" if jpeg and index == 0
                else "resampled-coverage"
            ),
            weight=float(raw_weights[index]),
            pixel_phase_xy=phase,
            blur_sigma_range=(
                max(0.0, blur_center * (0.45 if index == 0 else 0.25)),
                max(0.8, blur_center * (1.6 if index == 0 else 2.0)),
            ),
            gamma_range=(1.9, 2.4) if index == 0 else (1.0, 2.4),
            jpeg_quality_range=(25, 95) if jpeg and index == 0 else (
                (20, 100) if jpeg else None
            ),
            chroma_subsampling=(
                "4:2:0-or-4:4:4" if jpeg and index == 0
                else ("unknown" if jpeg else "none")
            ),
            resize_chain="single-or-two-stage" if index == 0 else "unknown",
            alpha_mode=alpha_mode,
        )
        for index, phase in enumerate(
            ((0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5))
        )
    )
    return ImageFormationPosterior(
        hypotheses=hypotheses,
        estimator="deterministic-codec+grid+laplacian+phase-v2",
        uncertainty=float(np.clip(0.22 + 0.25 * blur_center / 2.4, 0.0, 1.0)),
        observations=(
            ("laplacian_variance", laplacian_variance),
            ("blur_center", blur_center),
            ("jpeg_grid_score", jpeg_grid_score),
            ("gradient_anisotropy", anisotropy),
            ("source_codec", "jpeg" if jpeg else "non-jpeg"),
            ("alpha_mode", alpha_mode),
        ),
    )


def build_boundary_pyramid(raster: CanonicalRaster) -> tuple[BoundaryScale, ...]:
    channels = np.concatenate(
        [raster.oklab, raster.straight_rgba[..., 3:4]], axis=2
    ).astype(np.float32, copy=False)
    raw: list[
        tuple[
            float, int, np.ndarray, np.ndarray, np.ndarray, np.ndarray,
            np.ndarray, np.ndarray,
        ]
    ] = []
    # Two genuinely different lattice scales satisfy the oriented multi-scale
    # contract; a third full field did not add independent evidence in the
    # coverage probes and consumed ~20 ms at 512 px.
    levels = ((0.65, 1), (1.0, 4))
    for sigma, divisor in levels:
        level_channels = channels
        if divisor > 1:
            level_channels = cv2.resize(
                channels,
                (
                    max(1, channels.shape[1] // divisor),
                    max(1, channels.shape[0] // divisor),
                ),
                interpolation=cv2.INTER_AREA,
            )
        blurred = cv2.GaussianBlur(
            level_channels, (0, 0), sigmaX=sigma, sigmaY=sigma,
            borderType=cv2.BORDER_REFLECT101,
        )
        gx_channels = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
        gy_channels = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
        weights = np.asarray([1.0, 1.5, 1.5, 1.25], dtype=np.float32)
        energy = np.sum((gx_channels ** 2 + gy_channels ** 2) * weights, axis=2)
        magnitude = np.sqrt(np.maximum(energy, 0.0))
        channel_energy = gx_channels ** 2 + gy_channels ** 2
        strongest = np.argmax(channel_energy * weights, axis=2)
        gx = np.take_along_axis(gx_channels, strongest[..., None], axis=2)[..., 0]
        gy = np.take_along_axis(gy_channels, strongest[..., None], axis=2)[..., 0]
        orientation = np.mod(np.arctan2(gy, gx), np.pi).astype(np.float32)
        light_u8 = np.clip(level_channels[..., 0] * 255.0, 0, 255).astype(np.uint8)
        canny = cv2.Canny(light_u8, 40, 120, L2gradient=True).astype(np.float32) / 255.0

        # Parabolic peak interpolation along the dominant gradient axis gives
        # a bounded subpixel normal offset without an expensive remap.
        center = magnitude
        left = np.roll(center, 1, axis=1)
        right = np.roll(center, -1, axis=1)
        up = np.roll(center, 1, axis=0)
        down = np.roll(center, -1, axis=0)
        horizontal = np.abs(gx) >= np.abs(gy)
        before = np.where(horizontal, left, up)
        after = np.where(horizontal, right, down)
        denominator = before - 2.0 * center + after
        offset = np.zeros_like(center, dtype=np.float32)
        valid = np.abs(denominator) > 1e-6
        offset[valid] = 0.5 * (before[valid] - after[valid]) / denominator[valid]
        np.clip(offset, -0.5, 0.5, out=offset)
        offset[[0, -1], :] = 0.0
        offset[:, [0, -1]] = 0.0
        raw.append((
            sigma, divisor, magnitude, orientation,
            gx.astype(np.float32), gy.astype(np.float32), canny, offset,
        ))
    normalizer = max(float(np.quantile(raw[0][2], 0.985)), 1e-6)
    fields: list[BoundaryScale] = []
    for raw_index, (
        sigma, divisor, magnitude, orientation, gx, gy, canny, subpixel,
    ) in enumerate(raw):
        other = raw[1 - raw_index]
        other_gx = cv2.resize(
            other[4], (magnitude.shape[1], magnitude.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )
        other_gy = cv2.resize(
            other[5], (magnitude.shape[1], magnitude.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )
        local_magnitude = np.hypot(gx, gy)
        other_magnitude = np.hypot(other_gx, other_gy)
        phase_dot = np.maximum(gx * other_gx + gy * other_gy, 0.0)
        phase_congruency = phase_dot / np.maximum(
            local_magnitude * other_magnitude, 1e-6
        )
        cross_scale = phase_congruency * (
            np.minimum(local_magnitude, other_magnitude)
            / np.maximum(np.maximum(local_magnitude, other_magnitude), 1e-6)
        )
        phase_congruency = phase_congruency.astype(np.float32, copy=False)
        cross_scale = cross_scale.astype(np.float32, copy=False)
        gradient_probability = np.clip(
            magnitude / normalizer, 0.0, 1.0
        ).astype(np.float32)
        probability = np.clip(
            0.62 * gradient_probability
            + 0.16 * phase_congruency * gradient_probability
            + 0.12 * cross_scale
            + 0.10 * canny,
            0.0,
            1.0,
        ).astype(np.float32)
        bin_position = orientation * (8.0 / np.pi)
        lower = np.floor(bin_position).astype(np.intp) % 8
        fraction = (bin_position - np.floor(bin_position)).astype(np.float32)
        upper = (lower + 1) % 8
        distribution = np.zeros((*probability.shape, 8), dtype=np.float32)
        np.put_along_axis(
            distribution, lower[..., None],
            (probability * (1.0 - fraction))[..., None], axis=2,
        )
        np.put_along_axis(
            distribution, upper[..., None],
            (probability * fraction)[..., None], axis=2,
        )
        uncertainty = np.clip(
            1.0 - (0.65 * probability + 0.35 * cross_scale), 0.0, 1.0
        ).astype(np.float32)
        fields.append(
            BoundaryScale(
                sigma=sigma,
                scale_to_processing=(float(divisor), float(divisor)),
                probability=_freeze(probability),
                orientation=_freeze(orientation),
                orientation_distribution=_freeze(distribution),
                phase_congruency=_freeze(phase_congruency),
                classical_edge=_freeze(canny),
                cross_scale_persistence=_freeze(cross_scale),
                subpixel_offset=_freeze(subpixel),
                uncertainty=_freeze(uncertainty),
            )
        )
    return tuple(fields)


def _color_mixture(raster: CanonicalRaster) -> tuple[np.ndarray, np.ndarray]:
    rgb = raster.linear_premultiplied_rgba[..., :3]
    mean = cv2.GaussianBlur(rgb, (0, 0), 1.0)
    square = cv2.GaussianBlur(rgb * rgb, (0, 0), 1.0)
    variance = np.maximum(square - mean * mean, 0.0)
    return _freeze(mean, np.float32), _freeze(variance, np.float32)


def _background_hypotheses(
    rgb: np.ndarray, *, dominant_limit: int
) -> list[tuple[str, np.ndarray]]:
    """Return deterministic background colours without assuming empty edges."""

    rgb_i16 = rgb.astype(np.int16)
    border = np.concatenate(
        (rgb_i16[0], rgb_i16[-1], rgb_i16[:, 0], rgb_i16[:, -1]), axis=0
    )
    corners = np.asarray(
        (rgb_i16[0, 0], rgb_i16[0, -1], rgb_i16[-1, 0], rgb_i16[-1, -1])
    )
    backgrounds: list[tuple[str, np.ndarray]] = [
        ("border", np.median(border, axis=0)),
        ("corners", np.median(corners, axis=0)),
    ]
    quantised = (rgb // 16).astype(np.int32)
    keys = quantised[..., 0] * 256 + quantised[..., 1] * 16 + quantised[..., 2]
    histogram = np.bincount(keys.ravel(), minlength=4096)
    occupied = np.flatnonzero(histogram)
    dominant_keys = occupied[
        np.argsort(histogram[occupied])[
            -min(dominant_limit, len(occupied)):
        ][::-1]
    ]
    for rank, key in enumerate(dominant_keys):
        backgrounds.append(
            (f"dominant{rank}", np.median(rgb_i16[keys == key], axis=0))
        )
    unique: list[tuple[str, np.ndarray]] = []
    seen_colours: set[tuple[int, int, int]] = set()
    for name, colour in backgrounds:
        signature = tuple(int(round(value)) for value in colour)
        if signature not in seen_colours:
            unique.append((name, colour))
            seen_colours.add(signature)
    return unique


def _foreground_mask_bank(
    raster: CanonicalRaster,
    *,
    limit: int = 32,
    backgrounds: list[tuple[str, np.ndarray]] | None = None,
) -> list[tuple[np.ndarray, bytes, float, str]]:
    """Build codec-tolerant foreground hypotheses from independent backgrounds."""

    rgb = np.clip(
        raster.straight_rgba[..., :3] * 255.0, 0, 255
    ).astype(np.uint8)
    rgb_i16 = rgb.astype(np.int16)
    unique_backgrounds = (
        backgrounds
        if backgrounds is not None
        else _background_hypotheses(rgb, dominant_limit=1)
    )

    alpha = raster.straight_rgba[..., 3]
    masks: list[tuple[np.ndarray, bytes, float, str]] = []
    mask_indices: dict[bytes, int] = {}

    def retain_strongest(
        mask: np.ndarray, signature: bytes, score: float, method: str,
    ) -> None:
        previous = mask_indices.get(signature)
        if previous is None:
            mask_indices[signature] = len(masks)
            masks.append((mask, signature, score, method))
        elif score > masks[previous][2]:
            masks[previous] = (mask, signature, score, method)

    if float(np.ptp(alpha)) > 1e-4:
        for alpha_threshold in (4, 64, 128, 192):
            alpha_mask = alpha > (alpha_threshold / 255.0)
            signature = np.packbits(
                alpha_mask, axis=None, bitorder="little"
            ).tobytes()
            retain_strongest(
                alpha_mask, signature,
                float(0.82 + 0.18 * alpha_threshold / 192.0),
                f"source-alpha>{alpha_threshold}",
            )
    for background_name, background in unique_backgrounds:
        background_u8 = np.clip(np.round(background), 0, 255).astype(np.uint8)
        distance = np.abs(rgb_i16[..., 0] - int(background_u8[0]))
        np.maximum(
            distance,
            np.abs(rgb_i16[..., 1] - int(background_u8[1])),
            out=distance,
        )
        np.maximum(
            distance,
            np.abs(rgb_i16[..., 2] - int(background_u8[2])),
            out=distance,
        )
        for threshold in (4, 8, 16, 24, 40, 64, 96, 128, 192):
            mask = distance > threshold
            fraction = float(cv2.countNonZero(mask.astype(np.uint8)) / mask.size)
            if fraction < 0.001 or fraction > 0.98:
                continue
            signature = np.packbits(
                mask, axis=None, bitorder="little"
            ).tobytes()
            score = float(np.clip(
                0.42 + 0.30 * min(1.0, threshold / 72.0)
                + 0.18 * (1.0 - fraction),
                0.0,
                1.0,
            ))
            # A hard two-colour mark can produce the exact same support at
            # every threshold.  Keep the strongest observation rather than
            # freezing the first and weakest threshold score.
            retain_strongest(
                mask, signature, score,
                f"{background_name}:linf>{threshold}",
            )
    return masks[:limit]


def _topology_mask_bank(
    raster: CanonicalRaster,
    *,
    limit: int = 160,
    backgrounds: list[tuple[str, np.ndarray]] | None = None,
) -> list[tuple[np.ndarray, bytes, float, str]]:
    """Enumerate bounded fine-threshold supports for topology preservation.

    Coarse photometric thresholds cover pixels well but can merge a counter,
    split a glyph, or erase a tiny knockout.  This bank deliberately samples
    the integer source evidence more finely.  It is still bounded: transparent
    inputs contribute at most 63 alpha masks; opaque inputs contribute at most
    48 border-background and 25 masks for each of four dominant colours.
    """

    rgb = np.clip(
        raster.straight_rgba[..., :3] * 255.0, 0, 255
    ).astype(np.uint8)
    alpha_u8 = np.clip(
        np.round(raster.straight_rgba[..., 3] * 255.0), 0, 255
    ).astype(np.uint8)
    large_raster = alpha_u8.size > 100_000
    threshold_step = 16 if large_raster else 4
    streams: list[tuple[str, np.ndarray, range]] = []
    if int(alpha_u8.max()) - int(alpha_u8.min()) > 8:
        streams.append((
            "source-alpha", alpha_u8, range(4, 253, threshold_step)
        ))
    else:
        rgb_i16 = rgb.astype(np.int16)
        background_hypotheses = (
            backgrounds
            if backgrounds is not None
            else _background_hypotheses(rgb, dominant_limit=4)
        )
        for background_name, background in background_hypotheses:
            if background_name == "corners":
                continue
            background_u8 = np.clip(
                np.round(background), 0, 255
            ).astype(np.uint8)
            distance = np.abs(rgb_i16[..., 0] - int(background_u8[0]))
            np.maximum(
                distance,
                np.abs(rgb_i16[..., 1] - int(background_u8[1])),
                out=distance,
            )
            np.maximum(
                distance,
                np.abs(rgb_i16[..., 2] - int(background_u8[2])),
                out=distance,
            )
            thresholds = (
                range(4, 193, threshold_step)
                if background_name == "border"
                else range(32, 129, threshold_step)
            )
            streams.append((f"{background_name}:linf", distance, thresholds))

    masks: list[tuple[np.ndarray, bytes, float, str]] = []
    seen_masks: set[bytes] = set()
    for method, evidence, thresholds in streams:
        for threshold in thresholds:
            mask = evidence > threshold
            area = int(cv2.countNonZero(mask.astype(np.uint8)))
            fraction = area / mask.size
            if fraction < 0.001 or fraction > 0.98:
                continue
            packed = np.packbits(mask, axis=None, bitorder="little").tobytes()
            if packed in seen_masks:
                continue
            seen_masks.add(packed)
            score = float(np.clip(
                0.58 + 0.20 * (1.0 - fraction)
                + 0.12 * min(1.0, threshold / 128.0),
                0.0,
                0.94,
            ))
            masks.append((mask, packed, score, f"{method}>{threshold}"))
            if len(masks) >= limit:
                return masks
    return masks


def _photometric_mask_banks(
    raster: CanonicalRaster,
) -> tuple[
    list[tuple[np.ndarray, bytes, float, str]],
    list[tuple[np.ndarray, bytes, float, str]],
]:
    rgb = np.clip(
        raster.straight_rgba[..., :3] * 255.0, 0, 255
    ).astype(np.uint8)
    alpha = raster.straight_rgba[..., 3]
    dominant_limit = 1 if float(np.ptp(alpha)) > 1e-4 else 4
    backgrounds = _background_hypotheses(
        rgb, dominant_limit=dominant_limit
    )
    foreground = _foreground_mask_bank(
        raster,
        limit=16 if alpha.size > 100_000 else 32,
        backgrounds=backgrounds,
    )
    foreground_support = {packed for _mask, packed, _score, _method in foreground}
    topology = [
        row for row in _topology_mask_bank(raster, backgrounds=backgrounds)
        if row[1] not in foreground_support
    ]
    return foreground, topology


def _proposal_tokens(
    raster: CanonicalRaster,
    boundary: BoundaryScale,
    inclusion: InclusionForest,
    formation: ImageFormationPosterior,
    foreground_bank: list[tuple[np.ndarray, bytes, float, str]] | None = None,
    topology_bank: list[tuple[np.ndarray, bytes, float, str]] | None = None,
) -> tuple[ProposalToken, ...]:
    height, width = boundary.probability.shape
    tokens: list[ProposalToken] = []

    def add(
        family: str,
        bbox: tuple[int, int, int, int],
        score: float,
        provenance: str,
        uncertainty: float,
        *,
        support: np.ndarray | None = None,
        packed_support: bytes = b"",
        support_runs: tuple[tuple[int, int], ...] = (),
        support_dimensions: tuple[int, int] = (0, 0),
        **parameters: float | str,
    ) -> None:
        if len(tokens) >= _MAX_PROPOSAL_TOKENS:
            return
        tokens.append(
            ProposalToken(
                id=len(tokens), family=family, bbox_xyxy=bbox,
                score=float(np.clip(score, 0, 1)),
                parameters=tuple(sorted(parameters.items())),
                provenance=provenance,
                uncertainty=float(np.clip(uncertainty, 0, 1)),
                support_rle=support_runs,
                support_bits=(
                    packed_support or np.packbits(
                        support.astype(bool, copy=False), axis=None,
                        bitorder="little",
                    ).tobytes()
                    if support is not None else b""
                ),
                support_size=(
                    (width, height) if support is not None
                    else support_dimensions if support_runs else (0, 0)
                ),
            )
        )

    stable = sorted(
        inclusion.stable_components,
        key=lambda node: (-node.persistence, node.area, node.bbox_xyxy),
    )[:128]
    for node in stable:
        add(
            "component", node.bbox_xyxy,
            min(1.0, 0.35 + node.persistence),
            f"{node.kind}-tree", 1.0 - min(1.0, node.persistence + 0.2),
            support_runs=node.support_rle,
            support_dimensions=node.support_size,
            area=float(node.area), level=float(node.level),
        )
    if foreground_bank is None or topology_bank is None:
        foreground_bank, topology_bank = _photometric_mask_banks(raster)
    text_hypotheses: list[
        tuple[float, np.ndarray, bytes, tuple[int, int, int, int], str]
    ] = []
    for mask, packed, score, method in foreground_bank:
        x, y, box_width, box_height = cv2.boundingRect(mask.astype(np.uint8))
        if box_width <= 0 or box_height <= 0:
            continue
        bbox = (x, y, x + box_width, y + box_height)
        add(
            "component", bbox, score,
            "adaptive-background-foreground-bank", 1.0 - score,
            support=mask, packed_support=packed,
            method=method, area=float(mask.sum()),
        )
    # The foreground bank is ordered by deterministic generator provenance,
    # not by quality.  Its first masks are deliberately lax background-
    # distance envelopes and can cover 95%+ of a canvas.  Treating only those
    # first four as TextLine evidence promoted the white page around outlined
    # logos and hid the actual ink masks later in the bank.  Rank all bounded
    # masks by measured score, reject majority/background supports, then spend
    # connected-component work on at most eight plausible ink hypotheses.
    text_layouts_considered = 0
    for mask, packed, score, method in sorted(
        foreground_bank, key=lambda row: (-row[2], row[3])
    ):
        x, y, box_width, box_height = cv2.boundingRect(mask.astype(np.uint8))
        if box_width <= 0 or box_height <= 0:
            continue
        local_occupancy = float(mask.sum()) / max(1, box_width * box_height)
        count, _labels_bank, stats_bank, _centroids_bank = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), connectivity=8
        )
        aspect = box_width / max(1, box_height)
        component_areas = (
            stats_bank[1:, cv2.CC_STAT_AREA]
            if count > 1 else np.empty(0)
        )
        material = int(np.sum(component_areas >= 2))
        canvas_fraction = (
            box_width * box_height / max(1.0, float(width * height))
        )
        interior = bool(
            x > 0 and y > 0
            and x + box_width < width and y + box_height < height
        )
        isolated_glyph = bool(
            material == 1 and interior
            and 0.03 <= canvas_fraction <= 0.82
            # A one-symbol logo may legitimately be a fully solid dot/block.
            # The older 0.90 ceiling discarded every stable threshold of a
            # compact punctuation mark and left only its inverse canvas as a
            # false TextLine.  Interior/scale/aspect/topology consensus still
            # keep full-canvas backgrounds out of this lane.
            and 0.15 <= local_occupancy <= 1.00
            and 0.45 <= aspect <= 1.80
            and min(box_width, box_height) >= 3
        )
        ordinary_line = bool(
            0.01 <= local_occupancy <= 0.65
            and (material >= 2 or (material == 1 and aspect >= 1.25))
        )
        if not (ordinary_line or isolated_glyph):
            continue
        text_layouts_considered += 1
        text_score = float(np.clip(
            score * (
                0.95 if isolated_glyph else (
                    0.55
                    + 0.16 * min(3, material)
                    + 0.12 * min(2.0, max(0.0, aspect - 1.0))
                )
            ),
            0.0,
            0.98,
        ))
        text_hypotheses.append((
            text_score, mask, packed,
            (x, y, x + box_width, y + box_height), method,
        ))
        if text_layouts_considered >= 8:
            break
    topology_by_support: dict[bytes, tuple[int, int]] = {}
    topology_votes: dict[tuple[int, int], int] = {}
    for _score, mask, packed, _bbox_row, _method in text_hypotheses:
        contours, hierarchy = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE,
        )
        components = holes = 0
        if hierarchy is not None:
            for index in range(len(contours)):
                depth = 0
                parent = int(hierarchy[0, index, 3])
                while parent >= 0:
                    depth += 1
                    parent = int(hierarchy[0, parent, 3])
                if depth == 0:
                    components += 1
                elif depth % 2 == 1:
                    holes += 1
        signature = (components, holes)
        topology_by_support[packed] = signature
        topology_votes[signature] = topology_votes.get(signature, 0) + 1
    maximum_votes = max(topology_votes.values(), default=1)

    def topology_consensus_score(
        row: tuple[float, np.ndarray, bytes, tuple[int, int, int, int], str]
    ) -> float:
        votes = topology_votes.get(topology_by_support.get(row[2], (0, 0)), 1)
        # Persistent topology across independent thresholds is stronger text
        # evidence than the raw score of one aggressive threshold.  Rare
        # high-threshold fragmentation is penalized instead of winning merely
        # because it produces more connected pieces.
        return float(row[0] * (0.65 + 0.35 * votes / maximum_votes))

    for raw_score, mask, packed, bbox, method in sorted(
        text_hypotheses,
        key=lambda row: (-topology_consensus_score(row), row[4]),
    )[:3]:
        score = topology_consensus_score((raw_score, mask, packed, bbox, method))
        signature = topology_by_support.get(packed, (0, 0))
        consensus = topology_votes.get(signature, 0) == maximum_votes
        add(
            "text", bbox, score,
            (
                "adaptive-foreground-topology-consensus"
                if consensus and maximum_votes > 1
                else "adaptive-foreground-component-layout"
            ),
            1.0 - score,
            support=mask, packed_support=packed, method=method,
            topology_votes=float(topology_votes.get(signature, 1)),
            topology_components=float(signature[0]),
            topology_holes=float(signature[1]),
            local_occupancy=float(
                np.mean(mask[bbox[1]:bbox[3], bbox[0]:bbox[2]])
            ),
            isolated_glyph=float(
                signature[0] == 1
                and 0.45 <= (bbox[2] - bbox[0]) / max(
                    1.0, bbox[3] - bbox[1],
                ) <= 1.80
                and bbox[0] > 0 and bbox[1] > 0
                and bbox[2] < width and bbox[3] < height
            ),
        )
    if foreground_bank and not text_hypotheses:
        mask, packed, score, method = foreground_bank[0]
        x, y, box_width, box_height = cv2.boundingRect(mask.astype(np.uint8))
        add(
            "text", (x, y, x + box_width, y + box_height), score * 0.45,
            "low-confidence-text-query-from-foreground", 0.78,
            support=mask, packed_support=packed, method=method,
        )
    light = raster.oklab[..., 0]
    threshold = float(np.median(light))
    dark = ((light < threshold - 0.04) & (raster.straight_rgba[..., 3] > 0.05)).astype(np.uint8)
    count, dark_labels, stats, centroids = cv2.connectedComponentsWithStats(dark, 8)
    components = []
    for label in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[label])
        if 2 <= area <= max(6, int(width * height * 0.08)):
            components.append((
                x, y, w, h, area,
                float(centroids[label][0]), float(centroids[label][1]),
                label,
            ))
        fill = area / max(1, w * h)
        aspect = w / max(1, h)
        circular_score = min(aspect, 1 / max(aspect, 1e-6)) * (1.0 - abs(fill - math.pi / 4))
        if w >= 5 and h >= 5 and circular_score > 0.52:
            add("shape", (x, y, x + w, y + h), circular_score,
                "stable-component-circularity", 1.0 - circular_score,
                support=dark_labels == label,
                primitive="circle_or_ellipse", area=float(area))
    contours, topology = cv2.findContours(
        dark, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )
    if topology is not None and len(contours):
        relations = topology[0]
        component_total = int(np.sum(relations[:, 3] < 0))
        hole_total = int(np.sum(relations[:, 3] >= 0))
        add(
            "topology", (0, 0, width, height), 0.72,
            "threshold-component-contour", 0.28,
            support=dark > 0,
            components=float(component_total), holes=float(hole_total),
            polarity="dark",
        )
    if len(components) >= 2:
        xs = [c[0] for c in components]
        ys = [c[1] for c in components]
        x2 = [c[0] + c[2] for c in components]
        y2 = [c[1] + c[3] for c in components]
        heights = np.asarray([c[3] for c in components], dtype=np.float32)
        centers_y = np.asarray([c[6] for c in components], dtype=np.float32)
        alignment = float(np.exp(-np.std(centers_y) / max(1.0, np.median(heights))))
        score = float(np.clip(0.35 + 0.08 * len(components), 0, 0.9) * alignment)
        # The token's bbox and score are derived from the bounded small
        # components above, so its dense support must be the same components.
        # Using the entire dark field leaked unrelated emblems/illustrations
        # into an otherwise valid word line and made the downstream text
        # geometry wall reject every proposal.
        line_support = np.isin(
            dark_labels, np.asarray([c[7] for c in components], np.int32),
        )
        add("text", (min(xs), min(ys), max(x2), max(y2)), score,
            "stable-small-component-line", 1.0 - score,
            support=line_support,
            components=float(len(components)), alignment=alignment)
    edge_u8 = (boundary.probability >= 0.38).astype(np.uint8) * 255
    min_line = max(6, min(height, width) // 16)
    lines = cv2.HoughLinesP(
        edge_u8, 1, np.pi / 180, threshold=max(8, min_line // 2),
        minLineLength=min_line, maxLineGap=3,
    )
    if lines is not None:
        for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4)[:32]:
            length = math.hypot(float(x2 - x1), float(y2 - y1))
            score = min(0.96, length / max(height, width) + 0.35)
            line_support = np.zeros((height, width), dtype=np.uint8)
            cv2.line(
                line_support, (int(x1), int(y1)), (int(x2), int(y2)),
                1, thickness=2, lineType=cv2.LINE_8,
            )
            add("stroke", (min(x1, x2), min(y1, y2), max(x1, x2) + 1, max(y1, y2) + 1),
                score, "persistent-boundary-hough", 1.0 - score,
                support=line_support > 0,
                x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2))
    visible = raster.straight_rgba[..., 3] > 0.05
    edge_density = float(np.mean(boundary.probability[visible])) if np.any(visible) else 0.0
    color_range = float(np.mean(np.ptp(raster.oklab, axis=(0, 1))))
    if color_range > 0.03 and edge_density < 0.35:
        score = float(np.clip(color_range * 3.0 - edge_density, 0.1, 0.95))
        add("gradient", (0, 0, width, height), score,
            "smooth-color-mixture", 1.0 - score,
            support=visible,
            color_range=color_range, edge_density=edge_density)
    alpha_range = float(np.ptp(raster.straight_rgba[..., 3]))
    if alpha_range > 0.05 or len(inclusion.alpha_tree.nodes) > 0:
        score = float(np.clip(0.55 + alpha_range * 0.4, 0, 0.95))
        add("layer", (0, 0, width, height), score,
            "alpha-inclusion-tree", 1.0 - score,
            support=visible,
            alpha_range=alpha_range,
            alpha_nodes=float(len(inclusion.alpha_tree.nodes)))
    if any(
        hypothesis.jpeg_quality_range is not None
        for hypothesis in formation.hypotheses
    ):
        # This is an evidence token, not a cleanup decision.  The true source
        # suffix is attached later through the shared formation posterior.
        add("codec_detail", (0, 0, width, height), 0.45,
            "microfeature+formation-evidence", 0.55,
            edge_density=edge_density)
    lightness = light.copy()
    alpha = raster.straight_rgba[..., 3]
    valid = alpha > 0.05
    if np.any(valid):
        horizontal = float(
            1.0 - np.mean(np.abs(lightness - np.fliplr(lightness)))
        )
        vertical = float(
            1.0 - np.mean(np.abs(lightness - np.flipud(lightness)))
        )
        best = max(horizontal, vertical)
        if best > 0.78:
            add("symmetry", (0, 0, width, height), best,
                "oklab-reflection-consistency", 1.0 - best,
                axis="horizontal" if horizontal >= vertical else "vertical")
    for mask, packed, score, method in topology_bank:
        x, y, box_width, box_height = cv2.boundingRect(mask.astype(np.uint8))
        if box_width <= 0 or box_height <= 0:
            continue
        add(
            "topology", (x, y, x + box_width, y + box_height), score,
            "fine-topology-threshold-bank", 1.0 - score,
            support=mask, packed_support=packed, method=method,
        )
    return tuple(tokens)


def _attach_token_support(
    tokens: tuple[ProposalToken, ...], hierarchy: RegionHierarchy
) -> tuple[ProposalToken, ...]:
    """Attach sparse hierarchy-leaf support to typed REIR proposals.

    These are evidence proposals, not selected CMIR macros.  A downstream
    coverage probe can therefore test whether a typed proposal plus hierarchy
    nodes can express support without storing one dense mask per token.
    """

    labels = hierarchy.leaf_labels
    leaf_count = hierarchy.leaf_count
    leaf_area = np.bincount(labels.ravel(), minlength=leaf_count)
    support_families = {"component", "shape", "text", "stroke", "gradient", "layer"}
    thresholds = {
        "component": 0.30,
        "shape": 0.30,
        "text": 0.12,
        "stroke": 0.08,
        "gradient": 0.0,
        "layer": 0.0,
    }
    height, width = labels.shape
    attached: list[ProposalToken] = []
    for token in tokens:
        if token.family not in support_families:
            attached.append(token)
            continue
        x1, y1, x2, y2 = token.bbox_xyxy
        x1 = max(0, min(width, int(x1)))
        x2 = max(x1, min(width, int(x2)))
        y1 = max(0, min(height, int(y1)))
        y2 = max(y1, min(height, int(y2)))
        if x1 == 0 and y1 == 0 and x2 == width and y2 == height:
            leaf_ids = tuple(range(leaf_count))
        elif x2 <= x1 or y2 <= y1:
            leaf_ids = ()
        else:
            overlap = np.bincount(
                labels[y1:y2, x1:x2].ravel(), minlength=leaf_count
            )
            fraction = overlap / np.maximum(leaf_area, 1)
            leaf_ids = tuple(
                int(value) for value in np.flatnonzero(
                    fraction >= thresholds[token.family]
                )
            )
        attached.append(replace(token, support_leaf_ids=leaf_ids))
    return tuple(attached)


def _config_fingerprint(max_dim: int, region_size: int) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "schema": SCHEMA,
                "max_dim": max_dim,
                "region_size": region_size,
                "implementation_sha256": reir_implementation_sha256(),
                "runtime": {
                    "python": ".".join(map(str, sys.version_info[:3])),
                    "numpy": np.__version__,
                    "opencv": cv2.__version__,
                    "pillow": PIL.__version__,
                },
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


@lru_cache(maxsize=1)
def reir_implementation_sha256() -> str:
    """Bind cached evidence to every local module that constructs REIR.

    ``SCHEMA`` describes the serialized contract, not every mathematical
    change inside proposal or hierarchy construction.  Keying only by schema
    let old proposal tokens survive source fixes and made fresh experiments
    silently measure stale algorithms.  The implementation closure and native
    numeric-library versions are therefore part of the cache identity.
    """
    digest = hashlib.sha256(b"pcdc-reir-implementation/v1\0")
    package = Path(__file__).parent
    pending = [Path(__file__).name]
    visited: set[str] = set()
    paths: list[Path] = []
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        path = package / name
        visited.add(name)
        paths.append(path)
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level <= 0:
                continue
            names = (
                (node.module.split(".", 1)[0],) if node.module
                else tuple(alias.name.split(".", 1)[0] for alias in node.names)
            )
            for module in names:
                child = f"{module}.py"
                if (package / child).is_file() and child not in visited:
                    pending.append(child)
    for path in sorted(paths):
        name = path.name
        digest.update(name.encode("ascii"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_reir(
    path: str | Path,
    *,
    max_dim: int = 512,
    region_size: int = 28,
) -> RasterEvidenceIR:
    source = Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    # Four independent Python evidence tasks already provide outer
    # parallelism.  Letting every OpenCV kernel fan out to all 16 host threads
    # oversubscribes the machine and creates >300 ms tails.
    if cv2.getNumThreads() != 2:
        cv2.setNumThreads(2)
    profiler = StageProfiler(
        {"reir_total": StageBudget(wall_ms=300.0)}
    )

    def measured(name: str, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with profiler.stage(name):
            return function(*args, **kwargs)

    with profiler.stage("reir_total", source=str(source)):
        with profiler.stage("decode"):
            raster = canonical_decode(source, max_dim=max_dim)
        # All inputs below are immutable.  The independent evidence passes run
        # in the bounded CPU pool described by the PCDC runtime architecture.
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="pcdc-reir") as pool:
            boundary_future = pool.submit(
                measured, "boundary_pyramid", build_boundary_pyramid, raster
            )
            formation_future = pool.submit(
                measured, "formation_posterior",
                estimate_formation_posterior, raster, source.suffix,
            )
            mixture_future = pool.submit(
                measured, "color_mixture", _color_mixture, raster
            )
            inclusion_future = pool.submit(
                measured, "inclusion_trees", build_inclusion_forest,
                raster.oklab[..., 0], raster.straight_rgba[..., 3],
            )
            mask_banks_future = pool.submit(
                measured, "photometric_mask_banks",
                _photometric_mask_banks, raster,
            )
            boundary_pyramid = boundary_future.result()
            hierarchy_future = pool.submit(
                measured, "ucm_hierarchy", build_ucm_hierarchy,
                raster.oklab, boundary_pyramid[0].probability,
                region_size=region_size,
            )
            formation = formation_future.result()
            mixture_mean, mixture_variance = mixture_future.result()
            inclusion = inclusion_future.result()
            foreground_bank, topology_bank = mask_banks_future.result()
            # Tokens depend on boundary/inclusion/formation, not on the UCM.
            # Start them now so their photometric proposal bank overlaps the
            # hierarchy and subsequent cell/interface construction.
            tokens_future = pool.submit(
                measured, "proposal_tokens", _proposal_tokens,
                raster, boundary_pyramid[0], inclusion, formation,
                foreground_bank, topology_bank,
            )
            hierarchy = hierarchy_future.result()
            cells_future = pool.submit(
                measured, "cell_complex", build_cell_complex,
                hierarchy, boundary_pyramid[0].probability,
                raster.linear_premultiplied_rgba,
            )
            interfaces_future = pool.submit(
                measured, "interfaces", build_interface_graph,
                hierarchy, boundary_pyramid[0].probability,
                boundary_pyramid[0].orientation_distribution,
                raster.oklab,
            )
            cells = cells_future.result()
            interfaces = interfaces_future.result()
            proposal_tokens = tokens_future.result()
            proposal_tokens = measured(
                "proposal_support", _attach_token_support,
                proposal_tokens, hierarchy,
            )
    coverage = _freeze(raster.straight_rgba[..., 3].copy(), np.float32)
    profile = profiler.summary()
    reir = RasterEvidenceIR(
        schema=SCHEMA,
        source_path=str(source),
        source_sha256=_sha256(source),
        config_fingerprint=_config_fingerprint(max_dim, region_size),
        raster=raster,
        formation_posterior=formation,
        boundary_pyramid=boundary_pyramid,
        coverage_alpha=coverage,
        color_mixture_mean=mixture_mean,
        color_mixture_variance=mixture_variance,
        hierarchy=hierarchy,
        inclusion=inclusion,
        cells=cells,
        interfaces=interfaces,
        proposal_tokens=proposal_tokens,
        provenance=(
            ("canonical_raster", "Pillow EXIF+ICC+sRGB-linear-premul"),
            (
                "boundaries",
                "Oklab+alpha Sobel+Canny+phase-congruency+subpixel-v2",
            ),
            ("hierarchy", "SLIC-seeded-oriented-watershed+UCM+Kruskal-v1"),
            ("inclusion", "quantile min/max/alpha component trees-v1"),
            ("interfaces", "leaf half-edge adjacency-v1"),
            ("tokens", "deterministic typed proposals+fine-topology-support-v3"),
        ),
        stage_profile=profile,
    )
    reir.validate()
    return reir


class EvidenceCache:
    """Content-addressed REIR cache with atomic publication."""

    def __init__(self, root: str | Path = DEFAULT_CACHE) -> None:
        self.root = Path(root)
        self._publication_lock = threading.Lock()

    @staticmethod
    def _read_valid(target: Path) -> RasterEvidenceIR | None:
        if not target.is_file():
            return None
        try:
            with target.open("rb") as stream:
                payload = pickle.load(stream)
            if isinstance(payload, RasterEvidenceIR) and payload.schema == SCHEMA:
                payload.validate()
                return payload
        except Exception:
            pass
        return None

    @classmethod
    def _publish(cls, temporary: Path, target: Path) -> None:
        """Publish once, tolerating another process winning the same key."""
        delay = 0.002
        for attempt in range(9):
            if cls._read_valid(target) is not None:
                return
            try:
                os.replace(temporary, target)
                return
            except PermissionError:
                # Windows can reject a replace while another publisher has the
                # destination open.  A valid winner is sufficient because the
                # key binds source bytes and the entire REIR implementation.
                if attempt == 8:
                    raise
                time.sleep(delay)
                delay = min(delay * 2.0, 0.05)

    def key(self, source: Path, max_dim: int, region_size: int) -> str:
        return hashlib.sha256(
            (_sha256(source) + _config_fingerprint(max_dim, region_size)).encode()
        ).hexdigest()

    def get_or_build(
        self,
        path: str | Path,
        *,
        max_dim: int = 512,
        region_size: int = 28,
    ) -> tuple[RasterEvidenceIR, bool]:
        source = Path(path).resolve()
        key = self.key(source, max_dim, region_size)
        target = self.root / f"{key}.pkl"
        cached = self._read_valid(target)
        if cached is not None:
            return cached, True
        payload = build_reir(
            source, max_dim=max_dim, region_size=region_size
        )
        self.root.mkdir(parents=True, exist_ok=True)
        # Concurrent requests for the same cold key must never share a temp
        # filename: their pickle streams would interleave and one publisher
        # could remove another's file before atomic replace on Windows.
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f"{key}.", suffix=".pkl.tmp",
            dir=self.root, delete=False,
        ) as stream:
            temporary = Path(stream.name)
            pickle.dump(payload, stream, protocol=pickle.HIGHEST_PROTOCOL)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            with self._publication_lock:
                self._publish(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return payload, False


def summary(reir: RasterEvidenceIR) -> dict[str, Any]:
    return {
        "schema": reir.schema,
        "source": reir.source_path,
        "size": [reir.width, reir.height],
        "hierarchy_nodes": len(reir.hierarchy.nodes),
        "hierarchy_leaves": reir.hierarchy.leaf_count,
        "inclusion_nodes": {
            "min": len(reir.inclusion.min_tree.nodes),
            "max": len(reir.inclusion.max_tree.nodes),
            "alpha": len(reir.inclusion.alpha_tree.nodes),
        },
        "core_cells": len(reir.cells.cells),
        "boundary_bands": len(reir.cells.boundary_bands),
        "microfeatures": len(reir.cells.microfeatures),
        "interfaces": len(reir.interfaces.interfaces),
        "proposal_tokens": len(reir.proposal_tokens),
        "formation_hypotheses": len(reir.formation_posterior.hypotheses),
        "profile": reir.stage_profile,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--max-dim", type=int, default=512)
    parser.add_argument("--region-size", type=int, default=28)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    if args.no_cache:
        reir = build_reir(
            args.image, max_dim=args.max_dim, region_size=args.region_size
        )
        hit = False
    else:
        reir, hit = EvidenceCache().get_or_build(
            args.image, max_dim=args.max_dim, region_size=args.region_size
        )
    payload = summary(reir)
    payload["cache_hit"] = hit
    payload["command_wall_ms"] = round(
        (time.perf_counter() - started) * 1000.0, 3
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return int(not reir.stage_profile["complete"] and not hit)


if __name__ == "__main__":
    raise SystemExit(main())

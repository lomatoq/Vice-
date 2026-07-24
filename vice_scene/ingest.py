"""Canonical source decode with one crop/resize transform and explicit colour views."""

from __future__ import annotations

import hashlib
import io
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps, __version__ as PIL_VERSION

from .contracts import AlphaConvention, RasterSource, Rect


@dataclass(frozen=True)
class CanonicalRaster:
    source: RasterSource
    rgba_srgb_straight: np.ndarray
    rgba_linear_premul: np.ndarray
    oklab: np.ndarray
    alpha_native: np.ndarray

    @property
    def width(self) -> int:
        return self.source.native_width

    @property
    def height(self) -> int:
        return self.source.native_height

    def validate(self) -> None:
        self.source.validate()
        expected = (self.height, self.width)
        if self.rgba_srgb_straight.shape != (*expected, 4):
            raise ValueError("straight RGBA view has the wrong shape")
        if self.rgba_linear_premul.shape != (*expected, 4):
            raise ValueError("linear premultiplied RGBA view has the wrong shape")
        if self.oklab.shape != (*expected, 3) or self.alpha_native.shape != expected:
            raise ValueError("perceptual/alpha views have the wrong shape")
        for array in (self.rgba_srgb_straight, self.rgba_linear_premul,
                      self.oklab, self.alpha_native):
            if array.dtype != np.float32 or not np.isfinite(array).all():
                raise ValueError("canonical views must be finite float32 arrays")


def decode_raster(path: Path, *, max_pixels: int = 3_145_728,
                  crop: tuple[float, float, float, float] | None = None,
                  icc_policy: str = "preserve", frame_index: int = 0) -> CanonicalRaster:
    """Decode once and produce coordinate-consistent straight/linear/Oklab views.

    GIF policy is deliberately explicit: the requested frame is seeked and
    composited by Pillow.  The default is frame zero.
    """
    encoded = path.read_bytes()
    with Image.open(io.BytesIO(encoded)) as decoded:
        fmt = (decoded.format or path.suffix.lstrip(".") or "unknown").upper()
        source_width, source_height = decoded.size
        dpi_raw = decoded.info.get("dpi")
        dpi = None
        if isinstance(dpi_raw, tuple) and len(dpi_raw) >= 2:
            dpi = (float(dpi_raw[0]), float(dpi_raw[1]))
        frames = int(getattr(decoded, "n_frames", 1))
        if not 0 <= frame_index < frames:
            raise ValueError(f"frame_index {frame_index} outside 0..{frames - 1}")
        if frames > 1:
            decoded.seek(frame_index)
        orientation = int(decoded.getexif().get(274, 1)) if hasattr(decoded, "getexif") else 1
        image = ImageOps.exif_transpose(decoded)
        oriented_width, oriented_height = image.size
        exif_transform = _orientation_matrix(orientation, source_width, source_height)

        if icc_policy not in {"preserve", "ignore"}:
            raise ValueError("icc_policy must be 'preserve' or 'ignore'")
        if icc_policy == "preserve" and decoded.info.get("icc_profile"):
            try:
                source_profile = ImageCms.ImageCmsProfile(io.BytesIO(decoded.info["icc_profile"]))
                target_profile = ImageCms.createProfile("sRGB")
                alpha = image.getchannel("A") if "A" in image.getbands() else None
                rgb = ImageCms.profileToProfile(image.convert("RGB"), source_profile,
                                                target_profile, outputMode="RGB")
                if alpha is not None:
                    rgb.putalpha(alpha)
                image = rgb
            except (OSError, ValueError, ImageCms.PyCMSError):
                # Provenance still records the requested policy; malformed ICC
                # must not make a valid bitmap undecodable.
                image = image.convert("RGBA")

        if crop is None:
            requested_crop = Rect(0.0, 0.0, float(oriented_width), float(oriented_height))
        else:
            x0, y0, x1, y1 = (float(v) for v in crop)
            requested_crop = Rect(max(0.0, x0), max(0.0, y0),
                                  min(float(oriented_width), x1), min(float(oriented_height), y1))
            requested_crop.validate()
            if requested_crop.width <= 0 or requested_crop.height <= 0:
                raise ValueError("crop is empty")
        # Pillow crops on integer pixel-edge coordinates. The coordinate map
        # must describe that effective operation, not the fractional request.
        effective_crop = Rect(float(math.floor(requested_crop.x0)),
                              float(math.floor(requested_crop.y0)),
                              float(math.ceil(requested_crop.x1)),
                              float(math.ceil(requested_crop.y1)))
        if (effective_crop.x0, effective_crop.y0, effective_crop.x1, effective_crop.y1) != (
                0.0, 0.0, float(oriented_width), float(oriented_height)):
            image = image.crop((int(effective_crop.x0), int(effective_crop.y0),
                                int(effective_crop.x1), int(effective_crop.y1)))

        crop_w, crop_h = image.size
        scale = min(1.0, math.sqrt(max_pixels / max(1, crop_w * crop_h)))
        native_width = max(1, int(round(crop_w * scale)))
        native_height = max(1, int(round(crop_h * scale)))
        if (native_width, native_height) != image.size:
            image = image.resize((native_width, native_height), Image.Resampling.LANCZOS)
        image = image.convert("RGBA")

    srgb = np.asarray(image, dtype=np.float32) / 255.0
    alpha = srgb[..., 3:4]
    # RGB below alpha=0 is undefined storage, never evidence.
    srgb[..., :3] = np.where(alpha > 0.0, srgb[..., :3], 0.0)
    linear_rgb = srgb_to_linear(srgb[..., :3])
    premul = np.concatenate((linear_rgb * alpha, alpha), axis=2).astype(np.float32)
    oklab = linear_rgb_to_oklab(linear_rgb).astype(np.float32)

    sx = native_width / max(1.0, effective_crop.width)
    sy = native_height / max(1.0, effective_crop.height)
    canonical_from_oriented = (
        sx, 0.0, -effective_crop.x0 * sx,
        0.0, sy, -effective_crop.y0 * sy,
        0.0, 0.0, 1.0,
    )
    canonical_from_source = _matmul3(canonical_from_oriented, exif_transform)
    crop_rect_source = _inverse_rect(effective_crop, exif_transform)
    source = RasterSource(
        source_hash=hashlib.sha256(encoded).hexdigest(), format=fmt,
        encoded_size=len(encoded), source_width=source_width,
        source_height=source_height, native_width=native_width,
        native_height=native_height, frame_index=frame_index,
        exif_transform=exif_transform, crop_rect_source=crop_rect_source,
        canonical_from_source=canonical_from_source, icc_policy=icc_policy,
        alpha_mode=AlphaConvention.STRAIGHT.value,
        decoder="Pillow", decoder_version=PIL_VERSION, dpi=dpi,
    )
    result = CanonicalRaster(
        source=source, rgba_srgb_straight=srgb.astype(np.float32),
        rgba_linear_premul=premul, oklab=oklab,
        alpha_native=alpha[..., 0].astype(np.float32),
    )
    result.validate()
    return result


def srgb_to_linear(value: np.ndarray) -> np.ndarray:
    value = np.asarray(value, np.float32)
    return np.where(value <= 0.04045, value / 12.92,
                    ((value + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(value: np.ndarray) -> np.ndarray:
    value = np.clip(np.asarray(value, np.float32), 0.0, 1.0)
    return np.where(value <= 0.0031308, value * 12.92,
                    1.055 * np.power(value, 1.0 / 2.4) - 0.055).astype(np.float32)


def linear_rgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, np.float32)
    l = 0.4122214708 * rgb[..., 0] + 0.5363325363 * rgb[..., 1] + 0.0514459929 * rgb[..., 2]
    m = 0.2119034982 * rgb[..., 0] + 0.6806995451 * rgb[..., 1] + 0.1073969566 * rgb[..., 2]
    s = 0.0883024619 * rgb[..., 0] + 0.2817188376 * rgb[..., 1] + 0.6299787005 * rgb[..., 2]
    l_, m_, s_ = np.cbrt(np.clip(l, 0.0, None)), np.cbrt(np.clip(m, 0.0, None)), np.cbrt(np.clip(s, 0.0, None))
    return np.stack((
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    ), axis=-1)


def oklab_to_linear_rgb(lab: np.ndarray) -> np.ndarray:
    lab = np.asarray(lab, np.float32)
    l_ = lab[..., 0] + 0.3963377774 * lab[..., 1] + 0.2158037573 * lab[..., 2]
    m_ = lab[..., 0] - 0.1055613458 * lab[..., 1] - 0.0638541728 * lab[..., 2]
    s_ = lab[..., 0] - 0.0894841775 * lab[..., 1] - 1.2914855480 * lab[..., 2]
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return np.clip(np.stack((
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    ), axis=-1), 0.0, 1.0)


def _orientation_matrix(orientation: int, width: int, height: int) -> tuple[float, ...]:
    # Maps source edge coordinates to ImageOps.exif_transpose coordinates.
    matrices = {
        1: (1, 0, 0, 0, 1, 0, 0, 0, 1),
        2: (-1, 0, width, 0, 1, 0, 0, 0, 1),
        3: (-1, 0, width, 0, -1, height, 0, 0, 1),
        4: (1, 0, 0, 0, -1, height, 0, 0, 1),
        5: (0, 1, 0, 1, 0, 0, 0, 0, 1),
        6: (0, -1, height, 1, 0, 0, 0, 0, 1),
        7: (0, -1, height, -1, 0, width, 0, 0, 1),
        8: (0, 1, 0, -1, 0, width, 0, 0, 1),
    }
    return tuple(float(v) for v in matrices.get(orientation, matrices[1]))


def _matmul3(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    aa = np.asarray(a, dtype=np.float64).reshape(3, 3)
    bb = np.asarray(b, dtype=np.float64).reshape(3, 3)
    return tuple(float(v) for v in (aa @ bb).ravel())


def _inverse_rect(rect: Rect, transform: tuple[float, ...]) -> Rect:
    inverse = np.linalg.inv(np.asarray(transform, np.float64).reshape(3, 3))
    corners = np.asarray(((rect.x0, rect.y0, 1.0), (rect.x1, rect.y0, 1.0),
                          (rect.x1, rect.y1, 1.0), (rect.x0, rect.y1, 1.0)))
    mapped = corners @ inverse.T
    mapped = mapped[:, :2] / mapped[:, 2:3]
    return Rect(float(mapped[:, 0].min()), float(mapped[:, 1].min()),
                float(mapped[:, 0].max()), float(mapped[:, 1].max()))

"""Frozen multi-head evidence API with a deterministic classical backbone.

The production contract is model-agnostic: a future trained network must emit
the same heads and uncertainty maps.  The deterministic implementation keeps
the scene solver runnable and supplies a reproducible lower bound.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import sys
from typing import Protocol

import cv2
import numpy as np
import PIL

from .contracts import EvidenceLevel, EvidencePyramid, EvidenceRef
from .ingest import CanonicalRaster
from .raster_profile import ProfileFields


REQUIRED_HEADS = (
    "region_embedding", "color_logits", "boundary_prob", "boundary_normal",
    "subpixel_offset", "coverage_alpha", "corner_prob", "corner_type",
    "junction_prob", "shape_class_logits", "text_line_prob", "glyph_occupancy",
    "stroke_centerline_prob", "stroke_half_width", "symmetry_evidence", "uncertainty",
)


@dataclass(frozen=True)
class EvidenceTensorLevel:
    scale: float
    heads: dict[str, np.ndarray]

    def validate(self) -> None:
        missing = set(REQUIRED_HEADS) - set(self.heads)
        if missing:
            raise ValueError(f"evidence level misses heads: {sorted(missing)}")
        height, width = self.heads["boundary_prob"].shape[:2]
        for name, value in self.heads.items():
            if value.shape[:2] != (height, width):
                raise ValueError(f"head {name!r} has inconsistent lattice")
            if value.dtype != np.float32 or not np.isfinite(value).all():
                raise ValueError(f"head {name!r} must be finite float32")
        for name in ("boundary_prob", "corner_prob", "corner_type", "junction_prob",
                     "shape_class_logits", "text_line_prob",
                     "glyph_occupancy", "stroke_centerline_prob", "symmetry_evidence",
                     "uncertainty", "coverage_alpha"):
            value = self.heads[name]
            if float(value.min()) < -1e-5 or float(value.max()) > 1.00001:
                raise ValueError(f"probability head {name!r} is outside [0, 1]")


@dataclass(frozen=True)
class EvidenceBundle:
    source_hash: str
    model_version: str
    levels: tuple[EvidenceTensorLevel, ...]

    def validate(self) -> None:
        if not self.levels:
            raise ValueError("evidence pyramid is empty")
        for level in self.levels:
            level.validate()

    def contract(self, cache_key: str) -> EvidencePyramid:
        contract_levels: list[EvidenceLevel] = []
        for level in self.levels:
            refs = tuple(EvidenceRef(
                name=name, version=self.model_version,
                cache_key=f"{cache_key}:{level.scale:g}:{name}", shape=value.shape,
                dtype=str(value.dtype), pixel_size_native=1.0 / level.scale,
            ) for name, value in sorted(level.heads.items()))
            contract_levels.append(EvidenceLevel(level.scale, refs))
        return EvidencePyramid(self.model_version, tuple(contract_levels), self.source_hash)


class FrozenEvidenceModel(Protocol):
    version: str

    def infer(self, raster: CanonicalRaster, profile_fields: ProfileFields,
              scales: tuple[float, ...]) -> EvidenceBundle: ...


class DeterministicEvidenceModel:
    version = "deterministic-evidence/3"

    def infer(self, raster: CanonicalRaster, profile_fields: ProfileFields,
              scales: tuple[float, ...] = (1.0, 0.5, 0.25)) -> EvidenceBundle:
        levels = tuple(self._level(raster, profile_fields, scale) for scale in scales)
        bundle = EvidenceBundle(raster.source.source_hash, self.version, levels)
        bundle.validate()
        return bundle

    def _level(self, raster: CanonicalRaster, fields: ProfileFields,
               scale: float) -> EvidenceTensorLevel:
        if not 0.0 < scale <= 1.0:
            raise ValueError("evidence scale must be in (0, 1]")
        width = max(1, int(round(raster.width * scale)))
        height = max(1, int(round(raster.height * scale)))
        size = (width, height)
        lab = _resize(raster.oklab, size)
        alpha = _resize(raster.alpha_native, size)
        native_alpha = raster.alpha_native
        native_linear = raster.rgba_linear_premul[..., :3] / np.maximum(
            native_alpha[..., None], 1e-6)
        linear_rgb = _resize(native_linear, size)
        confidence = _resize(fields.confidence, size)
        text = _resize(fields.text_probability, size)
        diagram = _resize(fields.diagram_probability, size)

        gx = cv2.Scharr(lab[..., 0], cv2.CV_32F, 1, 0)
        gy = cv2.Scharr(lab[..., 0], cv2.CV_32F, 0, 1)
        chroma_gx = cv2.Scharr(lab[..., 1:], cv2.CV_32F, 1, 0)
        chroma_gy = cv2.Scharr(lab[..., 1:], cv2.CV_32F, 0, 1)
        mag = np.sqrt(gx * gx + gy * gy + 0.35 * np.sum(chroma_gx * chroma_gx + chroma_gy * chroma_gy, axis=2))
        scale99 = max(float(np.percentile(mag, 99)), 1e-6)
        boundary = np.clip(mag / scale99, 0.0, 1.0).astype(np.float32)
        normal = np.stack((gx, gy), axis=2)
        norm = np.linalg.norm(normal, axis=2, keepdims=True)
        normal = (normal / np.maximum(norm, 1e-6)).astype(np.float32)

        harris = cv2.cornerHarris(lab[..., 0].astype(np.float32), 2, 3, 0.04)
        harris = np.maximum(harris, 0.0)
        corner = np.clip(harris / max(float(np.percentile(harris, 99.5)), 1e-8), 0.0, 1.0)
        eig = cv2.cornerEigenValsAndVecs(lab[..., 0].astype(np.float32), 3, 3)
        lambda1, lambda2 = eig[..., 0], eig[..., 1]
        junction = np.clip(2.0 * np.minimum(lambda1, lambda2)
                           / np.maximum(lambda1 + lambda2, 1e-6), 0.0, 1.0) * boundary

        # Edge phase comes from the *linear-RGB* transition, never from file
        # alpha on an opaque PNG/JPEG.  The parabolic gradient-peak estimate is
        # bounded to half a native pixel and is zero away from supported edges.
        rgb_gx = cv2.Scharr(linear_rgb, cv2.CV_32F, 1, 0)
        rgb_gy = cv2.Scharr(linear_rgb, cv2.CV_32F, 0, 1)
        phase_magnitude = np.sqrt(np.sum(rgb_gx * rgb_gx + rgb_gy * rgb_gy, axis=2))
        phase = _edge_phase(phase_magnitude, normal)
        supported = np.clip((boundary - .08) / .42, 0.0, 1.0)
        subpixel = (phase[..., None] * normal * supported[..., None]).astype(np.float32)
        has_real_transparency = bool(np.mean(native_alpha < .999) > 1e-4)
        if has_real_transparency:
            coverage = np.clip(alpha, 0.0, 1.0)
        else:
            # On opaque inputs this head means local edge coverage/phase.  Flat
            # interiors remain one; it no longer repeats a useless all-one file
            # alpha plane.
            edge_coverage = np.clip(.5 - phase, 0.0, 1.0)
            coverage = 1.0 - supported * (1.0 - edge_coverage)
        ink = (lab[..., 0] < np.median(lab[..., 0])).astype(np.uint8)
        distance = cv2.distanceTransform(ink, cv2.DIST_L2, 5)
        local_max = distance >= cv2.dilate(distance, np.ones((3, 3), np.float32)) - 1e-5
        centerline = (local_max.astype(np.float32) * (distance > 0.7))
        stroke_width = distance.astype(np.float32)
        glyph = np.clip(text * (0.35 + 0.65 * ink), 0.0, 1.0).astype(np.float32)

        # Shape logits are proposals, not decisions: round / rectilinear /
        # elongated / generic support from local tensors.
        coherence = np.clip((lambda1 - lambda2) / np.maximum(lambda1 + lambda2, 1e-6), 0.0, 1.0)
        shape_logits = np.stack((1.0 - coherence, corner, coherence * diagram,
                                 np.ones_like(boundary) * 0.5), axis=2).astype(np.float32)
        corner_type = np.stack((corner * (1.0 - coherence), corner * coherence,
                                corner * junction), axis=2).astype(np.float32)
        color_logits = np.concatenate((lab, alpha[..., None]), axis=2).astype(np.float32)
        uncertainty = np.clip(1.0 - confidence * (0.35 + 0.65 * boundary), 0.0, 1.0)
        symmetry = np.clip(0.5 * (_mirror_score(lab[..., 0], 1)
                                  + _mirror_score(lab[..., 0], 0)), 0.0, 1.0)

        heads = {
            "region_embedding": lab.astype(np.float32),
            "color_logits": color_logits,
            "boundary_prob": boundary,
            "boundary_normal": normal,
            "subpixel_offset": subpixel,
            "coverage_alpha": coverage.astype(np.float32),
            "corner_prob": corner.astype(np.float32),
            "corner_type": corner_type,
            "junction_prob": junction.astype(np.float32),
            "shape_class_logits": shape_logits,
            "text_line_prob": np.clip(text, 0.0, 1.0).astype(np.float32),
            "glyph_occupancy": glyph,
            "stroke_centerline_prob": centerline.astype(np.float32),
            "stroke_half_width": stroke_width,
            "symmetry_evidence": symmetry.astype(np.float32),
            "uncertainty": uncertainty.astype(np.float32),
        }
        return EvidenceTensorLevel(scale, heads)


def _edge_phase(magnitude: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Subpixel location of a gradient maximum along its dominant axis."""
    values = np.asarray(magnitude, np.float32)
    padded = np.pad(values, 1, mode="edge")
    left, right = padded[1:-1, :-2], padded[1:-1, 2:]
    up, down = padded[:-2, 1:-1], padded[2:, 1:-1]
    horizontal = np.abs(normal[..., 0]) >= np.abs(normal[..., 1])
    previous = np.where(horizontal, left, up)
    following = np.where(horizontal, right, down)
    denominator = previous - 2.0 * values + following
    phase = np.zeros_like(values, np.float32)
    valid = np.abs(denominator) > 1e-6
    phase[valid] = .5 * (previous[valid] - following[valid]) / denominator[valid]
    return np.clip(phase, -.5, .5).astype(np.float32)


class NeutralEvidenceModel:
    """Shape-correct no-evidence ablation for causal campaign runs."""
    version = "neutral-evidence-ablation/1"

    def infer(self, raster: CanonicalRaster, profile_fields: ProfileFields,
              scales: tuple[float, ...] = (1.0, .5, .25)) -> EvidenceBundle:
        levels = []
        channels = {"region_embedding": 3, "color_logits": 4,
                    "boundary_normal": 2, "subpixel_offset": 2,
                    "corner_type": 3, "shape_class_logits": 4}
        for scale in scales:
            width = max(1, int(round(raster.width * scale)))
            height = max(1, int(round(raster.height * scale)))
            heads = {}
            for name in REQUIRED_HEADS:
                count = channels.get(name)
                heads[name] = np.zeros((height, width, count), np.float32) if count else np.zeros(
                    (height, width), np.float32)
            heads["uncertainty"][:] = 1.0
            levels.append(EvidenceTensorLevel(float(scale), heads))
        bundle = EvidenceBundle(raster.source.source_hash, self.version, tuple(levels))
        bundle.validate()
        return bundle


def _resize(value: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    if value.shape[1::-1] == size:
        return np.asarray(value, np.float32).copy()
    return cv2.resize(np.asarray(value, np.float32), size, interpolation=cv2.INTER_AREA).astype(np.float32)


def _mirror_score(value: np.ndarray, axis: int) -> np.ndarray:
    mirrored = np.flip(value, axis=axis)
    delta = np.abs(value - mirrored)
    sigma = max(float(np.percentile(delta, 90)), 1e-4)
    return np.exp(-delta / sigma).astype(np.float32)


@lru_cache(maxsize=1)
def scene_evidence_implementation_sha256() -> str:
    """Hash the local implementation closure used to construct evidence.

    A checkpoint digest or a handwritten model version identifies weights and
    a serialized contract, but neither changes automatically when inference,
    preprocessing, hybrid routing, or deterministic evidence math changes.
    Persisted tensors must therefore be invalidated by the executable source
    closure too.  Both evidence entry points are roots so the identity covers
    classical, neural, hybrid, and neutral routes.
    """
    digest = hashlib.sha256(b"vice-scene-evidence-implementation/v1\0")
    package = Path(__file__).parent
    pending = [Path(__file__).name, "neural_evidence.py"]
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
        digest.update(path.name.encode("ascii")); digest.update(b"\0")
        digest.update(path.read_bytes()); digest.update(b"\0")
    return digest.hexdigest()


def evidence_cache_key(source_hash: str, model_version: str,
                       scales: tuple[float, ...]) -> str:
    payload = {
        "schema": "vice-scene-evidence-cache-key/2",
        "source_hash": source_hash,
        "model_version": model_version,
        "scales": [float(value) for value in scales],
        "implementation_sha256": scene_evidence_implementation_sha256(),
        "runtime": {
            "python": ".".join(map(str, sys.version_info[:3])),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "pillow": PIL.__version__,
        },
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

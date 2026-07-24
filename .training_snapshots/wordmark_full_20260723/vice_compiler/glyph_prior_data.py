"""Deterministic, family-disjoint open-font data for the glyph prior."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch
from torch.utils.data import Dataset

from .font_license_manifest import validate_manifest
from .glyph_prior import GLYPH_CHARACTERS, character_id


# These characters dominate multi-counter and detached-component failures.
# Enrichment applies only to training; calibration/test stay natural.
TOPOLOGY_ENRICHED_CHARACTERS = "B8ij&@"


@dataclass(frozen=True)
class GlyphFontRecord:
    family: str
    path: Path
    sha256: str
    license: str


@dataclass(frozen=True)
class GlyphFamilySplit:
    train: tuple[GlyphFontRecord, ...]
    calibration: tuple[GlyphFontRecord, ...]
    test: tuple[GlyphFontRecord, ...]
    family_assignment: tuple[tuple[str, str], ...]
    digest: str

    def validate(self) -> None:
        family_sets = {
            name: {row.family for row in getattr(self, name)}
            for name in ("train", "calibration", "test")
        }
        if any(not values for values in family_sets.values()):
            raise ValueError("glyph font-family split contains an empty partition")
        if any(
            family_sets[a] & family_sets[b]
            for a, b in (
                ("train", "calibration"), ("train", "test"),
                ("calibration", "test"),
            )
        ):
            raise ValueError("glyph font-family split leaks across partitions")


def load_font_records(
    manifest_path: Path, *, font_root: Path | None = None,
    verify_bytes: bool = True,
) -> tuple[tuple[GlyphFontRecord, ...], dict]:
    manifest = json.loads(Path(manifest_path).read_text("utf-8"))
    root = (font_root or Path(str(manifest["root"]))).resolve()
    if verify_bytes:
        validate_manifest(manifest, root=root)
    records = tuple(
        GlyphFontRecord(
            family=str(row["family"]), path=(root / row["font_path"]).resolve(),
            sha256=str(row["font_sha256"]), license=str(row["license"]),
        )
        for row in manifest["fonts"]
    )
    if not records:
        raise ValueError("glyph font manifest contains no fonts")
    return records, manifest


def split_font_families(
    records: Iterable[GlyphFontRecord], *, seed: int = 20260722,
) -> GlyphFamilySplit:
    rows = tuple(records)
    by_family: dict[str, list[GlyphFontRecord]] = {}
    for row in rows:
        by_family.setdefault(row.family, []).append(row)
    if len(by_family) < 10:
        raise ValueError("at least ten font families are required for held-out splits")
    ranked = sorted(
        by_family,
        key=lambda family: hashlib.sha256(
            f"{seed}\0{family}".encode("utf-8")
        ).hexdigest(),
    )
    held_out = max(1, round(0.10 * len(ranked)))
    test_families = set(ranked[:held_out])
    calibration_families = set(ranked[held_out:2 * held_out])
    assignment = []
    partitions = {name: [] for name in ("train", "calibration", "test")}
    for family in sorted(by_family):
        split = (
            "test" if family in test_families else
            "calibration" if family in calibration_families else "train"
        )
        assignment.append((family, split))
        partitions[split].extend(sorted(
            by_family[family], key=lambda row: (row.sha256, str(row.path)),
        ))
    payload = json.dumps(assignment, separators=(",", ":"), ensure_ascii=True)
    result = GlyphFamilySplit(
        train=tuple(partitions["train"]),
        calibration=tuple(partitions["calibration"]),
        test=tuple(partitions["test"]),
        family_assignment=tuple(assignment),
        digest=hashlib.sha256(payload.encode("ascii")).hexdigest(),
    )
    result.validate()
    return result


def _border_median(image: np.ndarray) -> np.ndarray:
    rgb = np.asarray(image, np.float32)
    if rgb.ndim == 2:
        rgb = np.repeat(rgb[..., None], 3, axis=2)
    if rgb.shape[2] > 3:
        rgb = rgb[..., :3]
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
    return np.median(border, axis=0)


def glyph_observation_features(image: np.ndarray, image_size: int) -> np.ndarray:
    """Build source-only contrast/distance/edge features in [0,1]."""
    rgb = np.asarray(image)
    if rgb.ndim == 2:
        rgb = np.repeat(rgb[..., None], 3, axis=2)
    if rgb.shape[2] > 3:
        rgb = rgb[..., :3]
    rgb = cv2.resize(
        rgb.astype(np.float32), (image_size, image_size),
        interpolation=cv2.INTER_AREA if max(rgb.shape[:2]) > image_size else cv2.INTER_CUBIC,
    )
    if float(np.max(rgb)) > 1.5:
        rgb /= 255.0
    background = _border_median(rgb)
    difference = rgb - background[None, None, :]
    distance = np.linalg.norm(difference, axis=2)
    scale = max(0.05, float(np.quantile(distance, 0.99)))
    distance = np.clip(distance / scale, 0.0, 1.0)
    luma = rgb @ np.asarray((0.2126, 0.7152, 0.0722), np.float32)
    background_luma = float(background @ np.asarray((0.2126, 0.7152, 0.0722)))
    contrast = np.clip(np.abs(luma - background_luma) / max(0.05, scale), 0.0, 1.0)
    edge = cv2.magnitude(
        cv2.Sobel(contrast, cv2.CV_32F, 1, 0, ksize=3),
        cv2.Sobel(contrast, cv2.CV_32F, 0, 1, ksize=3),
    )
    edge /= max(1e-6, float(np.quantile(edge, 0.99)))
    features = np.clip(
        np.stack((distance, contrast, np.clip(edge, 0, 1))), 0.0, 1.0,
    )
    # OpenCV SIMD reductions may differ by one float32 ULP between repeated
    # calls.  A fixed 12-bit physical feature lattice is far finer than source
    # raster evidence and makes the training stream byte reproducible.
    features = np.round(features * 4095.0) / 4095.0
    return np.ascontiguousarray(features.astype(np.float32, copy=False))


def _topology(mask: np.ndarray) -> tuple[int, int]:
    binary = np.asarray(mask, np.uint8)
    count, _labels = cv2.connectedComponents(binary, connectivity=8)
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    holes = 0 if hierarchy is None else sum(int(row[3]) >= 0 for row in hierarchy[0])
    return max(0, int(count) - 1), int(holes)


def _signed_distance(mask: np.ndarray) -> np.ndarray:
    support = np.asarray(mask, np.uint8)
    inside = cv2.distanceTransform(support, cv2.DIST_L2, 5)
    outside = cv2.distanceTransform(1 - support, cv2.DIST_L2, 5)
    sdf = inside - outside
    return np.clip(sdf / max(1.0, 0.25 * max(mask.shape)), -1.0, 1.0).astype(np.float32)


def _skeleton(mask: np.ndarray) -> np.ndarray:
    remaining = np.asarray(mask, np.uint8).copy()
    skeleton = np.zeros_like(remaining)
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    for _ in range(max(mask.shape)):
        opened = cv2.morphologyEx(remaining, cv2.MORPH_OPEN, kernel)
        skeleton |= remaining & (1 - opened)
        remaining = cv2.erode(remaining, kernel)
        if not np.any(remaining):
            break
    return skeleton.astype(np.float32)


def _render_clean_glyph(
    font: GlyphFontRecord, character: str, image_size: int, rng: np.random.Generator,
) -> np.ndarray:
    base = _cached_normalized_glyph(str(font.path), character, image_size)
    scale = float(rng.uniform(0.82, 1.0))
    shift_x = int(rng.integers(-2, 3)); shift_y = int(rng.integers(-2, 3))
    center = 0.5 * (image_size - 1)
    matrix = np.asarray((
        (scale, 0.0, (1.0 - scale) * center + shift_x),
        (0.0, scale, (1.0 - scale) * center + shift_y),
    ), np.float32)
    transformed = cv2.warpAffine(
        base, matrix, (image_size, image_size),
        flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return transformed.astype(np.float32) / 255.0


@lru_cache(maxsize=32_768)
def _cached_normalized_glyph(
    path: str, character: str, image_size: int,
) -> np.ndarray:
    canvas_size = image_size * 4
    # Crop normalization removes nearly all apparent size variation, while
    # reopening a 0.1--2 MB font for every one of millions of variants makes
    # the data loader the dominant cost.  One high-resolution face per font
    # and worker preserves outline/hinting diversity; target scale and phase
    # still vary below.
    font_size = 3 * image_size
    face = _cached_font_face(path, font_size)
    bbox = face.getbbox(character, stroke_width=0)
    if bbox is None or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        raise ValueError("font has no renderable glyph")
    source = Image.new("L", (canvas_size, canvas_size), 0)
    draw = ImageDraw.Draw(source)
    width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((canvas_size - width) / 2 - bbox[0], (canvas_size - height) / 2 - bbox[1]),
        character, font=face, fill=255,
    )
    array = np.asarray(source, np.uint8)
    ys, xs = np.nonzero(array > 2)
    if not len(xs):
        raise ValueError("font produced an empty glyph")
    pad = max(2, int(0.06 * max(xs.max() - xs.min(), ys.max() - ys.min())))
    crop = source.crop((
        max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
        min(canvas_size, int(xs.max()) + pad + 1),
        min(canvas_size, int(ys.max()) + pad + 1),
    ))
    margin = max(3, image_size // 12)
    scale = min(
        (image_size - 2 * margin) / crop.width,
        (image_size - 2 * margin) / crop.height,
    )
    resized = crop.resize(
        (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
        Image.Resampling.LANCZOS,
    )
    target = Image.new("L", (image_size, image_size), 0)
    x = max(0, (image_size - resized.width) // 2)
    y = max(0, (image_size - resized.height) // 2)
    target.paste(resized, (x, y))
    result = np.asarray(target, np.uint8).copy()
    result.setflags(write=False)
    return result


@lru_cache(maxsize=512)
def _cached_font_face(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, int(size))


def _topology_corruption(
    coverage: np.ndarray, rng: np.random.Generator,
) -> tuple[np.ndarray, str]:
    """Apply one explicit source-like topology corruption when possible.

    Blur/downsampling alone left almost every training glyph topologically
    intact, so the U-Net learned a high-scoring identity shortcut.  Real OCR
    cells contain broken strokes, JPEG islands and counters that disappear or
    appear at the native lattice.  These deterministic operators make those
    cases the majority of the training and held-out distributions.
    """
    original = np.asarray(coverage, np.float32)
    support = original >= 0.5
    original_topology = _topology(support)
    height, width = support.shape
    ys, xs = np.nonzero(support)
    if not len(xs):
        return original.copy(), "photometric-only"
    x1 = int(xs.min())
    x2 = int(xs.max()) + 1
    y1 = int(ys.min())
    y2 = int(ys.max()) + 1

    def accept(trial: np.ndarray, profile: str) -> tuple[np.ndarray, str] | None:
        clipped = np.clip(trial, 0.0, 1.0).astype(np.float32, copy=False)
        if _topology(clipped >= 0.5) == original_topology:
            return None
        return np.ascontiguousarray(clipped), profile

    def stroke_break() -> tuple[np.ndarray, str] | None:
        candidates: list[tuple[str, int, int]] = []
        for band in range(1, max(2, min(4, (x2 - x1) // 8 + 1))):
            for x in range(x1 + 1, max(x1 + 1, x2 - band)):
                candidates.append(("vertical", x, band))
        for band in range(1, max(2, min(4, (y2 - y1) // 8 + 1))):
            for y in range(y1 + 1, max(y1 + 1, y2 - band)):
                candidates.append(("horizontal", y, band))
        if candidates:
            order = rng.permutation(len(candidates))
            for position in order[:min(48, len(order))]:
                orientation, coordinate, band = candidates[int(position)]
                trial = original.copy()
                if orientation == "vertical":
                    trial[y1:y2, coordinate:coordinate + band] = 0.0
                else:
                    trial[coordinate:coordinate + band, x1:x2] = 0.0
                result = accept(trial, "stroke-break")
                if result is not None:
                    return result
        return None

    def spurious_island() -> tuple[np.ndarray, str] | None:
        distance = cv2.distanceTransform(
            (~support).astype(np.uint8), cv2.DIST_L2, 5,
        )
        vicinity = np.zeros_like(support)
        vicinity[
            max(1, y1 - 6):min(height - 1, y2 + 6),
            max(1, x1 - 6):min(width - 1, x2 + 6),
        ] = True
        points = np.argwhere(vicinity & (distance >= 2.2))
        if len(points):
            for position in rng.permutation(len(points))[:min(32, len(points))]:
                y, x = (int(value) for value in points[int(position)])
                trial = original.copy()
                radius = int(rng.integers(1, 3))
                cv2.circle(trial, (x, y), radius, 1.0, thickness=-1)
                result = accept(trial, "spurious-island")
                if result is not None:
                    return result
        return None

    def counter_fill() -> tuple[np.ndarray, str] | None:
        inverse = (~support).astype(np.uint8)
        count, labels = cv2.connectedComponents(inverse, connectivity=8)
        holes = []
        for label in range(1, count):
            region = labels == label
            if (
                np.any(region[0]) or np.any(region[-1])
                or np.any(region[:, 0]) or np.any(region[:, -1])
            ):
                continue
            holes.append(region)
        if holes:
            region = holes[int(rng.integers(len(holes)))]
            trial = original.copy()
            trial[region] = 1.0
            return accept(trial, "counter-fill")
        return None

    def counter_punch() -> tuple[np.ndarray, str] | None:
        distance = cv2.distanceTransform(
            support.astype(np.uint8), cv2.DIST_L2, 5,
        )
        points = np.argwhere(distance >= 2.0)
        if len(points):
            ranked = sorted(
                ((-float(distance[y, x]), int(y), int(x)) for y, x in points),
                key=lambda row: row,
            )
            offset = int(rng.integers(min(8, len(ranked))))
            for _distance, y, x in ranked[offset:offset + 24]:
                trial = original.copy()
                trial[y, x] = 0.0
                result = accept(trial, "counter-punch")
                if result is not None:
                    return result
        return None

    requested = int(rng.choice(4, p=np.asarray((0.34, 0.28, 0.20, 0.18))))
    operators = (
        (stroke_break, spurious_island, counter_fill, counter_punch),
        (spurious_island, stroke_break, counter_fill, counter_punch),
        (counter_fill, stroke_break, spurious_island, counter_punch),
        (counter_punch, stroke_break, spurious_island, counter_fill),
    )[requested]
    for operator in operators:
        result = operator()
        if result is not None:
            return result
    return original.copy(), "photometric-only"


def _degrade(
    clean_coverage: np.ndarray, rng: np.random.Generator,
) -> tuple[np.ndarray, str, bool, int]:
    size = clean_coverage.shape[0]
    alpha = np.uint8(np.clip(clean_coverage * 255.0, 0, 255))
    low = int(rng.integers(max(7, size // 7), max(9, round(0.72 * size))))
    low_width = max(5, int(round(low * float(rng.uniform(0.72, 1.25)))))
    alpha = cv2.resize(alpha, (low_width, low), interpolation=cv2.INTER_AREA)
    if rng.random() < 0.85:
        alpha = cv2.GaussianBlur(
            alpha, (0, 0), sigmaX=float(rng.uniform(0.2, 1.3)),
            borderType=cv2.BORDER_REPLICATE,
        )
    coverage = cv2.resize(
        alpha, (size, size), interpolation=cv2.INTER_LINEAR,
    ).astype(np.float32) / 255.0
    target_topology = _topology(np.asarray(clean_coverage) >= 0.5)
    sampled_topology = _topology(coverage >= 0.5)
    if sampled_topology != target_topology:
        corruption_profile = "sampling-topology"
    elif rng.random() < 0.80:
        coverage, corruption_profile = _topology_corruption(coverage, rng)
        # Real OCR cells often contain several simultaneous failures (two
        # broken stems plus a JPEG pinhole), not the single easy edit used by
        # the first training corpus.  Compose a second independently valid
        # corruption when it preserves or increases topology distance from
        # the clean target; never let the composition accidentally undo the
        # hard example.
        if corruption_profile != "photometric-only" and rng.random() < 0.60:
            first_topology = _topology(coverage >= 0.5)
            first_distance = sum(abs(a - b) for a, b in zip(
                first_topology, target_topology,
            ))
            compound, second_profile = _topology_corruption(coverage, rng)
            compound_topology = _topology(compound >= 0.5)
            compound_distance = sum(abs(a - b) for a, b in zip(
                compound_topology, target_topology,
            ))
            if (
                second_profile != "photometric-only"
                and compound_topology != target_topology
                and compound_distance >= first_distance
            ):
                coverage = compound
                corruption_profile = (
                    f"compound:{corruption_profile}+{second_profile}"
                )
    else:
        corruption_profile = "photometric-only"
    topology_corrupted = _topology(coverage >= 0.5) != target_topology
    degraded_topology = _topology(coverage >= 0.5)
    topology_distance = sum(abs(a - b) for a, b in zip(
        degraded_topology, target_topology,
    ))
    background = rng.uniform(0.70, 1.0, size=3)
    foreground = rng.uniform(0.0, 0.35, size=3)
    if rng.random() < 0.25:
        background, foreground = foreground, background
    rgb = coverage[..., None] * foreground + (1.0 - coverage[..., None]) * background
    rgb += rng.normal(0.0, float(rng.uniform(0.0, 0.025)), rgb.shape)
    image = np.uint8(np.clip(rgb * 255.0, 0, 255))
    if rng.random() < 0.85:
        ok, encoded = cv2.imencode(
            ".jpg", cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
            (cv2.IMWRITE_JPEG_QUALITY, int(rng.integers(22, 92))),
        )
        if not ok:
            raise RuntimeError("OpenCV JPEG degradation failed")
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if decoded is None:
            raise RuntimeError("OpenCV JPEG degradation decode failed")
        image = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
    return (
        np.ascontiguousarray(image, dtype=np.uint8),
        corruption_profile,
        bool(topology_corrupted),
        int(topology_distance),
    )


class OpenFontGlyphDataset(Dataset):
    """Virtual deterministic stream; length controls variants, not source count."""

    def __init__(
        self, records: Iterable[GlyphFontRecord], *, samples: int,
        image_size: int = 64, seed: int = 20260722,
        topology_enrichment_probability: float = 0.0,
    ) -> None:
        self.records = tuple(records)
        self.samples = int(samples)
        self.image_size = int(image_size)
        self.seed = int(seed)
        self.topology_enrichment_probability = float(
            topology_enrichment_probability
        )
        self.epoch = 0
        if not self.records or self.samples <= 0:
            raise ValueError("glyph dataset needs fonts and positive sample count")
        if not 0.0 <= self.topology_enrichment_probability <= 1.0:
            raise ValueError("glyph topology enrichment probability is invalid")
        grouped: dict[str, list[GlyphFontRecord]] = {}
        for row in self.records:
            grouped.setdefault(row.family, []).append(row)
        self.family_records = tuple(
            (family, tuple(sorted(rows, key=lambda row: (row.sha256, str(row.path)))))
            for family, rows in sorted(grouped.items())
        )

    def __len__(self) -> int:
        return self.samples

    def set_epoch(self, epoch: int) -> None:
        if int(epoch) < 0:
            raise ValueError("glyph dataset epoch cannot be negative")
        self.epoch = int(epoch)

    def _seed(self, index: int) -> int:
        digest = hashlib.sha256(
            f"{self.seed}\0{self.epoch}\0{int(index)}".encode("ascii")
        ).digest()
        return int.from_bytes(digest[:8], "little")

    def __getitem__(self, index: int) -> dict:
        if not 0 <= int(index) < self.samples:
            raise IndexError(index)
        rng = np.random.default_rng(self._seed(int(index)))
        if rng.random() < self.topology_enrichment_probability:
            character = TOPOLOGY_ENRICHED_CHARACTERS[
                int(rng.integers(len(TOPOLOGY_ENRICHED_CHARACTERS)))
            ]
        else:
            character = GLYPH_CHARACTERS[
                int(rng.integers(len(GLYPH_CHARACTERS)))
            ]
        clean = None
        font = None
        for attempt in range(min(12, len(self.family_records))):
            family_index = (
                int(rng.integers(len(self.family_records)))
                if attempt == 0 else (int(index) + attempt) % len(self.family_records)
            )
            _family, family_fonts = self.family_records[family_index]
            candidate = family_fonts[int(rng.integers(len(family_fonts)))]
            try:
                rendered = _render_clean_glyph(
                    candidate, character, self.image_size, rng,
                )
            except (OSError, ValueError):
                continue
            binary = rendered >= 0.5
            components, holes = _topology(binary)
            if components <= 0 or components >= 6 or holes >= 5:
                continue
            clean, font = rendered, candidate
            break
        if clean is None or font is None:
            raise RuntimeError("could not render a valid glyph sample")
        support = clean >= 0.5
        (
            degraded, corruption_profile, topology_corrupted,
            topology_corruption_distance,
        ) = _degrade(clean, rng)
        return {
            "observed": torch.from_numpy(
                glyph_observation_features(degraded, self.image_size)
            ),
            "support": torch.from_numpy(support[None].astype(np.float32)),
            "sdf": torch.from_numpy(_signed_distance(support)[None]),
            "skeleton": torch.from_numpy(_skeleton(support)[None]),
            "character_id": torch.tensor(character_id(character), dtype=torch.long),
            "components": torch.tensor(_topology(support)[0], dtype=torch.long),
            "holes": torch.tensor(_topology(support)[1], dtype=torch.long),
            "family": font.family,
            "font_sha256": font.sha256,
            "character": character,
            "corruption_profile": corruption_profile,
            "topology_corrupted": torch.tensor(
                topology_corrupted, dtype=torch.bool,
            ),
            "topology_corruption_distance": torch.tensor(
                topology_corruption_distance, dtype=torch.long,
            ),
        }


def sample_digest(sample: dict) -> str:
    digest = hashlib.sha256()
    for key in ("observed", "support", "sdf", "skeleton"):
        value = sample[key]
        array = value.detach().cpu().numpy() if torch.is_tensor(value) else np.asarray(value)
        digest.update(key.encode("ascii")); digest.update(array.tobytes())
    for key in (
        "character_id", "components", "holes", "family", "font_sha256",
        "corruption_profile", "topology_corrupted",
        "topology_corruption_distance",
    ):
        value = sample[key]
        if torch.is_tensor(value):
            value = value.item()
        digest.update(str(value).encode("utf-8")); digest.update(b"\0")
    return digest.hexdigest()

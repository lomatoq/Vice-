"""Family-disjoint procedural data for the whole-line wordmark prior."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch
from torch.utils.data import Dataset

from .glyph_prior_data import GlyphFontRecord
from .wordmark_prior import (
    WORDMARK_CHARACTERS, WordmarkPriorConfig, topology_signature,
    wordmark_token_ids,
)


TEXT_MAXIMUM_LENGTH = 32
OCR_HINT_EXACT_FRACTION = 0.75
JPEG_CORRUPTION_FRACTION = 0.35
CONNECTED_WORDMARK_FRACTION = 0.18
OUTLINE_WORDMARK_FRACTION = 0.12


def wordmark_data_recipe() -> dict[str, object]:
    return {
        "schema": "pcdc-wordmark-procedural-data/v3",
        "source": "family-disjoint locally owned open-font manifest",
        "text_length": [3, TEXT_MAXIMUM_LENGTH],
        "text_modes": [
            "uppercase", "lowercase", "uppercase-digits",
            "lowercase-digits", "mixed-latin-digits-punctuation",
            "two-word-with-ordered-space",
        ],
        "tracking_em": [-0.15, 0.22],
        "ocr_hint_exact_fraction": OCR_HINT_EXACT_FRACTION,
        "ocr_hint_corruptions": ["substitute", "delete", "insert", "transpose"],
        "jpeg_corruption_fraction": JPEG_CORRUPTION_FRACTION,
        "jpeg_quality": [25, 90],
        "connected_wordmark_fraction": CONNECTED_WORDMARK_FRACTION,
        "outline_wordmark_fraction": OUTLINE_WORDMARK_FRACTION,
        "observation_corruptions": [
            "native-resolution", "blur", "gamma", "noise",
            "topology-hole-or-island", "codec",
        ],
        "sample_rng": "sha256(seed:index)",
    }


def _rng(seed: int, index: int) -> np.random.Generator:
    digest = hashlib.sha256(f"{seed}:{index}".encode("ascii")).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


def _sample_text(generator: np.random.Generator, maximum: int) -> str:
    length = int(generator.integers(3, min(TEXT_MAXIMUM_LENGTH, maximum) + 1))
    mode = int(generator.integers(0, 6))
    if mode == 0:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    elif mode == 1:
        alphabet = "abcdefghijklmnopqrstuvwxyz"
    elif mode == 2:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    elif mode == 3:
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    elif mode == 4:
        # Every non-space serving token must be an actual training target;
        # slicing the first 62 entries silently excluded &@.-_+ before v2.
        alphabet = WORDMARK_CHARACTERS.rstrip(" ")
    else:
        # The internal space is itself an ordered serving token and must fit
        # inside the same max_characters contract as visible glyphs.
        length = max(4, min(length, maximum - 1))
        alphabet = (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            if generator.random() < 0.5
            else "abcdefghijklmnopqrstuvwxyz0123456789"
        )
        characters = "".join(
            generator.choice(tuple(alphabet), size=length).tolist()
        )
        split = int(generator.integers(2, length - 1))
        return f"{characters[:split]} {characters[split:]}"
    return "".join(generator.choice(tuple(alphabet), size=length).tolist())


def _corrupt_text_hint(
    text: str, generator: np.random.Generator, maximum: int,
) -> str:
    """Model realistic OCR uncertainty while retaining a usable line hint."""
    hint = list(text)
    event = float(generator.random())
    alphabet = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if text.isupper()
        else "abcdefghijklmnopqrstuvwxyz0123456789"
    )
    if event < OCR_HINT_EXACT_FRACTION:
        return text
    index = int(generator.integers(0, len(hint)))
    if event < 0.86:
        hint[index] = str(generator.choice(tuple(alphabet)))
    elif event < 0.91 and len(hint) > 3:
        del hint[index]
    elif event < 0.96 and len(hint) < maximum:
        inserted = (
            " " if generator.random() < 0.15
            else str(generator.choice(tuple(alphabet)))
        )
        hint.insert(index, inserted)
    elif len(hint) > 1:
        second = min(len(hint) - 1, index + 1)
        first = max(0, second - 1)
        hint[first], hint[second] = hint[second], hint[first]
    return "".join(hint)


@lru_cache(maxsize=256)
def _cached_font(font_path: str, font_size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path, font_size)


def _draw_tracked_text(
    font_path: str, text: str, generator: np.random.Generator,
    *, scale: int,
) -> np.ndarray:
    # Absolute font size disappears when the result is fitted to the model
    # canvas.  One canonical high-resolution size preserves the same geometry
    # and lets each worker cache every owned face instead of reopening a TTF for
    # every synthetic sample.
    font_size = 64 * scale
    font = _cached_font(font_path, font_size)
    tracking = float(generator.uniform(-0.15, 0.22)) * font_size
    stroke = int(generator.integers(0, max(2, font_size // 18) + 1))
    advances = [max(1.0, float(font.getlength(character)) + tracking) for character in text]
    bounds = font.getbbox(text, stroke_width=stroke)
    canvas_width = max(
        64 * scale,
        int(math.ceil(64 * scale + sum(advances) + 2 * stroke)),
    )
    canvas_height = max(
        64 * scale,
        int(math.ceil(bounds[3] - bounds[1] + 48 * scale + 2 * stroke)),
    )
    canvas = Image.new("L", (canvas_width, canvas_height), 0)
    draw = ImageDraw.Draw(canvas)
    cursor = 32 * scale
    y = 24 * scale - bounds[1]
    for character, advance in zip(text, advances):
        draw.text(
            (cursor, y), character, font=font, fill=255,
            stroke_width=stroke, stroke_fill=255,
        )
        cursor += advance
    alpha = np.asarray(canvas, np.uint8)
    ys, xs = np.nonzero(alpha)
    if not len(xs):
        return np.zeros((1, 1), np.uint8)
    return alpha[
        max(0, int(ys.min()) - 2):min(alpha.shape[0], int(ys.max()) + 3),
        max(0, int(xs.min()) - 2):min(alpha.shape[1], int(xs.max()) + 3),
    ]


def render_clean_wordmark(
    font_path: str, text: str, config: WordmarkPriorConfig, *,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Render one clean line coverage/support pair on the model canvas."""
    generator = _rng(seed, 0)
    high = _draw_tracked_text(font_path, text, generator, scale=2)
    height, width = config.image_height, config.image_width
    margin_y = max(2, height // 14)
    margin_x = max(3, width // 40)
    available_height = height - 2 * margin_y
    available_width = width - 2 * margin_x
    factor = min(
        available_width / max(1, high.shape[1]),
        available_height / max(1, high.shape[0]),
    )
    target_width = max(1, int(round(high.shape[1] * factor)))
    target_height = max(1, int(round(high.shape[0] * factor)))
    resized = cv2.resize(
        high, (target_width, target_height), interpolation=cv2.INTER_AREA,
    )
    coverage = np.zeros((height, width), np.float32)
    x = (width - target_width) // 2
    y = (height - target_height) // 2
    coverage[y:y + target_height, x:x + target_width] = resized / 255.0
    support = coverage >= 0.50

    # Wordmarks frequently use negative tracking, joined scripts, outlines or
    # one carrier-like silhouette.  These are line-level targets by design and
    # are exactly what a per-cell glyph model cannot represent.
    effect = float(generator.random())
    if effect < CONNECTED_WORDMARK_FRACTION:
        radius = int(generator.integers(1, 4))
        support = cv2.morphologyEx(
            support.astype(np.uint8), cv2.MORPH_CLOSE,
            np.ones((3, 2 * radius + 1), np.uint8),
        ) > 0
    elif effect < CONNECTED_WORDMARK_FRACTION + OUTLINE_WORDMARK_FRACTION:
        outer = cv2.dilate(
            support.astype(np.uint8), np.ones((3, 3), np.uint8),
        ) > 0
        inner = cv2.erode(
            support.astype(np.uint8), np.ones((3, 3), np.uint8),
        ) > 0
        outlined = outer & ~inner
        if np.any(outlined):
            support = outlined
            coverage = cv2.GaussianBlur(
                support.astype(np.float32), (0, 0), 0.55,
            )
    coverage = np.maximum(coverage, support.astype(np.float32))
    # The 0.5 coverage level is the target support by construction.  Keeping
    # this invariant prevents contradictory observations/labels after outline
    # and morphology effects.
    coverage = np.where(
        support, np.maximum(coverage, 0.5), np.minimum(coverage, 0.499),
    )
    return np.asarray(coverage, np.float32), np.asarray(support, bool)


def degrade_wordmark(
    clean_coverage: np.ndarray, clean_support: np.ndarray, *, seed: int,
) -> np.ndarray:
    generator = _rng(seed, 1)
    height, width = clean_support.shape
    native_height = int(generator.integers(max(6, height // 8), height + 1))
    native_width = max(12, int(round(width * native_height / height)))
    native = cv2.resize(
        clean_coverage, (native_width, native_height), interpolation=cv2.INTER_AREA,
    )
    observed = cv2.resize(native, (width, height), interpolation=cv2.INTER_CUBIC)
    if generator.random() < 0.55:
        sigma = float(generator.uniform(0.25, 1.2))
        observed = cv2.GaussianBlur(observed, (0, 0), sigma)
    gamma = float(generator.uniform(0.65, 1.55))
    observed = np.power(np.clip(observed, 0.0, 1.0), gamma)
    noise = generator.normal(0.0, generator.uniform(0.0, 0.07), observed.shape)
    observed = np.clip(observed + noise, 0.0, 1.0)

    # Explicit topology corruptions teach restoration rather than mere denoise.
    if generator.random() < JPEG_CORRUPTION_FRACTION:
        y = int(generator.integers(1, height - 1))
        x = int(generator.integers(1, width - 1))
        radius = int(generator.integers(1, 4))
        value = 0.0 if clean_support[y, x] else 1.0
        cv2.circle(observed, (x, y), radius, float(value), -1)
    if generator.random() < 0.25:
        count = int(generator.integers(1, 5))
        for _ in range(count):
            y = int(generator.integers(0, height))
            x = int(generator.integers(0, width))
            observed[y, x] = 1.0
    if generator.random() < 0.35:
        quality = int(generator.integers(25, 91))
        encoded_ok, encoded = cv2.imencode(
            ".jpg", np.rint(observed * 255.0).astype(np.uint8),
            (cv2.IMWRITE_JPEG_QUALITY, quality),
        )
        if encoded_ok:
            decoded = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
            if decoded is not None:
                observed = decoded.astype(np.float32) / 255.0
    return np.asarray(observed, np.float32)


def wordmark_observation_features(observed_ink: np.ndarray) -> np.ndarray:
    values = np.asarray(observed_ink, np.float32)
    threshold = (values >= 0.50).astype(np.float32)
    gradient_x = cv2.Sobel(values, cv2.CV_32F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(values, cv2.CV_32F, 0, 1, ksize=3)
    edge = np.clip(np.hypot(gradient_x, gradient_y), 0.0, 1.0)
    return np.stack((values, threshold, edge), axis=0).astype(np.float32)


def signed_distance_target(support: np.ndarray) -> np.ndarray:
    mask = np.asarray(support, np.uint8)
    inside = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    outside = cv2.distanceTransform(1 - mask, cv2.DIST_L2, 5)
    scale = max(2.0, 0.12 * support.shape[0])
    return np.clip((inside - outside) / scale, -1.0, 1.0).astype(np.float32)


class OpenFontWordmarkDataset(Dataset):
    def __init__(
        self, fonts: tuple[GlyphFontRecord, ...], *, sample_count: int,
        seed: int, config: WordmarkPriorConfig | None = None,
    ) -> None:
        if not fonts:
            raise ValueError("wordmark dataset needs at least one font")
        self.fonts = fonts
        self.sample_count = int(sample_count)
        self.seed = int(seed)
        self.config = config or WordmarkPriorConfig()
        self.config.validate()

    def __len__(self) -> int:
        return self.sample_count

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        # Bounded deterministic retry avoids recursive self-calls when a very
        # complex line exceeds the finite topology head vocabulary.
        for retry in range(32):
            sample_index = int(index) + retry * max(1, self.sample_count)
            generator = _rng(self.seed, sample_index)
            font = self.fonts[int(generator.integers(0, len(self.fonts)))]
            text = _sample_text(generator, self.config.max_characters)
            text_hint = _corrupt_text_hint(
                text, generator, self.config.max_characters,
            )
            tokens = wordmark_token_ids(
                text_hint, max_characters=self.config.max_characters,
            )
            if tokens is None:
                raise RuntimeError("procedural wordmark emitted invalid text")
            token_ids, text_length = tokens
            coverage, support = render_clean_wordmark(
                font.path, text, self.config,
                seed=self.seed + 104729 * sample_index,
            )
            components, holes = topology_signature(support)
            maximum = self.config.topology_classes - 1
            if not np.any(support) or components > maximum or holes > maximum:
                continue
            observed = degrade_wordmark(
                coverage, support, seed=self.seed + 130363 * sample_index,
            )
            return {
                "features": torch.from_numpy(
                    wordmark_observation_features(observed),
                ),
                "support": torch.from_numpy(support.astype(np.float32))[None],
                "sdf": torch.from_numpy(signed_distance_target(support))[None],
                "text_tokens": torch.from_numpy(token_ids),
                "text_length": torch.tensor(text_length, dtype=torch.long),
                "components": torch.tensor(components, dtype=torch.long),
                "holes": torch.tensor(holes, dtype=torch.long),
            }
        raise RuntimeError("wordmark topology resampling exhausted 32 attempts")


def family_split_sha256(rows: tuple[tuple[str, str], ...]) -> str:
    payload = "\n".join(f"{family}\t{split}" for family, split in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

"""Local-only bounded neural OCR for the optional exact text lane.

The warm text path must never import or load a neural OCR model.  This module
is therefore imported lazily by :mod:`exact_font_provider` only for Max/exact
refinement.  Model resolution is deliberately local-only: a missing model,
dependency, CUDA runtime or malformed checkpoint returns no hypotheses and the
already-valid font-free result remains untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import os
from pathlib import Path
import re
from threading import Lock
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps


_PROJECT = Path(__file__).resolve().parents[1]
_DEFAULT_CACHE = _PROJECT / "models" / "trocr-small-printed"
_HF_CACHE_NAME = "models--microsoft--trocr-small-printed"
_MODEL_ENV = "VICE_TROCR_MODEL"
_REQUIRED_FILES = (
    "config.json", "model.safetensors", "preprocessor_config.json",
    "sentencepiece.bpe.model", "tokenizer_config.json",
)
_MODEL_LOCK = Lock()


@dataclass(frozen=True)
class NeuralOcrLine:
    """One source-pixel OCR hypothesis; never an output admission by itself."""

    text: str
    bbox_xyxy: tuple[int, int, int, int]
    confidence: float
    provenance: str


@dataclass(frozen=True)
class OcrCrop:
    bbox_xyxy: tuple[int, int, int, int]
    preparation: str
    provenance: str


def _valid_snapshot(path: Path) -> bool:
    return path.is_dir() and all((path / name).is_file() for name in _REQUIRED_FILES)


def resolve_local_trocr_snapshot(cache_root: str | Path | None = None) -> Path | None:
    """Resolve the pinned local snapshot without contacting Hugging Face."""
    explicit = os.environ.get(_MODEL_ENV, "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        return path.resolve() if _valid_snapshot(path) else None
    root = Path(cache_root) if cache_root is not None else _DEFAULT_CACHE
    if _valid_snapshot(root):
        return root.resolve()
    repository = root / _HF_CACHE_NAME
    revision_file = repository / "refs" / "main"
    try:
        revision = revision_file.read_text("utf-8").strip()
    except (OSError, UnicodeError):
        return None
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", revision):
        return None
    snapshot = repository / "snapshots" / revision
    return snapshot.resolve() if _valid_snapshot(snapshot) else None


def _clip_box(
    raw: Iterable[float], width: int, height: int,
) -> tuple[int, int, int, int] | None:
    values = tuple(raw)
    if len(values) != 4:
        return None
    x1, y1, x2, y2 = (int(round(float(value))) for value in values)
    x1 = max(0, min(width, x1)); x2 = max(0, min(width, x2))
    y1 = max(0, min(height, y1)); y2 = max(0, min(height, y2))
    return (x1, y1, x2, y2) if x2 - x1 >= 3 and y2 - y1 >= 3 else None


def _box_iou(
    first: tuple[int, int, int, int], second: tuple[int, int, int, int],
) -> float:
    x1 = max(first[0], second[0]); y1 = max(first[1], second[1])
    x2 = min(first[2], second[2]); y2 = min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    area2 = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    return intersection / max(1, area1 + area2 - intersection)


def _border_relative_foreground(image: Image.Image) -> np.ndarray:
    """Return immutable-looking foreground evidence relative to modal border."""
    rgba = np.asarray(image.convert("RGBA"), np.float32) / 255.0
    alpha = rgba[..., 3]
    rgb = rgba[..., :3] * alpha[..., None] + (1.0 - alpha[..., None])
    height, width = rgb.shape[:2]
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
    # A quantized modal border is stable on JPEG noise and does not assume a
    # white canvas.  It is an observation of immutable source pixels only.
    quantized = np.clip(np.floor(border * 31.0 + 0.5), 0, 31).astype(np.uint8)
    keys = (quantized[:, 0].astype(np.int32) << 10) | (
        quantized[:, 1].astype(np.int32) << 5
    ) | quantized[:, 2].astype(np.int32)
    modal_key = int(np.bincount(keys, minlength=32768).argmax())
    modal = np.array((
        (modal_key >> 10) & 31, (modal_key >> 5) & 31, modal_key & 31,
    ), np.float32) / 31.0
    distance = np.linalg.norm(rgb - modal[None, None, :], axis=2)
    distance_u8 = np.clip(distance / math.sqrt(3.0) * 255.0, 0, 255).astype(np.uint8)
    threshold, _ = cv2.threshold(
        distance_u8, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU,
    )
    return distance_u8 > max(5, int(threshold))


def _leading_mark_crop(image: Image.Image) -> int | None:
    """Prove a separate leading mark by an observed blank column run."""
    foreground = _border_relative_foreground(image)
    height, width = foreground.shape
    active = np.sum(foreground, axis=0) >= max(
        1, int(math.ceil(0.03 * height)),
    )
    padded = np.pad((~active).astype(np.int8), (1, 1))
    starts = np.flatnonzero(np.diff(padded) == 1)
    stops = np.flatnonzero(np.diff(padded) == -1)
    candidates: list[tuple[int, int]] = []
    for start, stop in zip(starts, stops):
        if stop - start < max(2, int(math.ceil(0.02 * width))):
            continue
        center = 0.5 * (start + stop)
        if not 0.06 * width <= center <= 0.38 * width:
            continue
        if not np.any(active[:start]) or not np.any(active[stop:]):
            continue
        candidates.append((stop - start, int(stop)))
    if not candidates:
        return None
    # The widest early whitespace is the strongest separation witness.
    _gap, crop_x = max(candidates, key=lambda row: (row[0], -row[1]))
    return max(1, min(width - 3, crop_x))


def _foreground_bands(image: Image.Image) -> tuple[tuple[int, int, int, int], ...]:
    """Infer at most three horizontal ink bands from border-relative colour."""
    foreground = _border_relative_foreground(image)
    height, width = foreground.shape
    row_count = np.sum(foreground, axis=1)
    active = row_count >= max(2, int(math.ceil(0.015 * width)))
    if not np.any(active):
        return ()
    # Bridge tiny antialias/JPEG gaps, then collect physical horizontal runs.
    gap = max(1, int(round(0.035 * height)))
    active = cv2.morphologyEx(
        active.astype(np.uint8)[None, :], cv2.MORPH_CLOSE,
        np.ones((1, 2 * gap + 1), np.uint8),
    )[0] > 0
    padded = np.pad(active.astype(np.int8), (1, 1))
    starts = np.flatnonzero(np.diff(padded) == 1)
    stops = np.flatnonzero(np.diff(padded) == -1)
    rows: list[tuple[int, int, int, int]] = []
    for y1, y2 in zip(starts, stops):
        if y2 - y1 < 2:
            continue
        ys, xs = np.nonzero(foreground[y1:y2])
        if not len(xs):
            continue
        x1 = int(xs.min()); x2 = int(xs.max()) + 1
        pad_x = max(1, int(round(0.025 * max(1, x2 - x1))))
        pad_y = max(1, int(round(0.10 * max(1, y2 - y1))))
        box = _clip_box(
            (x1 - pad_x, y1 - pad_y, x2 + pad_x, y2 + pad_y),
            width, height,
        )
        if box is not None:
            rows.append(box)
    rows.sort(key=lambda box: (-(box[2] - box[0]) * (box[3] - box[1]), box))
    return tuple(rows[:3])


def propose_ocr_crops(
    image: Image.Image, *,
    seed_boxes: Iterable[Iterable[float]] = (), max_crops: int = 6,
) -> tuple[OcrCrop, ...]:
    """Build a small deterministic crop ensemble from source pixels alone."""
    width, height = image.size
    rows: list[OcrCrop] = []

    def add(raw: Iterable[float], preparation: str, provenance: str) -> None:
        box = _clip_box(raw, width, height)
        if box is None:
            return
        if any(
            row.preparation == preparation and _box_iou(row.bbox_xyxy, box) >= 0.96
            for row in rows
        ):
            return
        rows.append(OcrCrop(box, preparation, provenance))

    for raw in seed_boxes:
        box = _clip_box(raw, width, height)
        if box is None:
            continue
        x1, y1, x2, y2 = box
        px = max(1, int(round(0.04 * (x2 - x1))))
        py = max(1, int(round(0.12 * (y2 - y1))))
        add((x1 - px, y1 - py, x2 + px, y2 + py), "contrast", "windows-box")
    # Whole-frame grayscale is strong for clean wordmarks and JPEG script.
    add((0, 0, width, height), "gray", "whole-frame")
    crop_x = _leading_mark_crop(image) if width >= 2.0 * height else None
    if crop_x is not None:
        # A left mark can consume the recognizer's sequence budget.  This is
        # allowed only after a source-observed blank separator proves that the
        # crop boundary cannot amputate a leading glyph.
        add((crop_x, 0, width, height), "gray", "separated-right")
        add((crop_x, 0, width, 0.68 * height), "contrast", "separated-upper")
    for band in _foreground_bands(image):
        add(band, "contrast", "foreground-band")
    return tuple(rows[:max(1, min(8, int(max_crops)))])


def _prepare_crop(image: Image.Image, crop: OcrCrop) -> Image.Image:
    result = image.crop(crop.bbox_xyxy).convert("RGB")
    if crop.preparation == "gray":
        return ImageOps.autocontrast(ImageOps.grayscale(result)).convert("RGB")
    if crop.preparation == "contrast":
        return ImageEnhance.Contrast(result).enhance(2.0)
    return result


def _normalize_text(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value)).strip()
    value = re.sub(r"^[^\w]+|[^\w]+$", "", value, flags=re.UNICODE)
    return value.strip()


@lru_cache(maxsize=1)
def _load_local_model(snapshot_text: str):
    # Heavy imports and all model allocation remain outside warm T2/module
    # import.  Passing a resolved snapshot path also prevents hub lookups.
    import torch
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    snapshot = Path(snapshot_text)
    processor = TrOCRProcessor.from_pretrained(
        snapshot, local_files_only=True,
    )
    model = VisionEncoderDecoderModel.from_pretrained(
        snapshot, local_files_only=True,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()
    return processor, model, device


def recognize_local_text(
    image: Image.Image, *, seed_boxes: Iterable[Iterable[float]] = (),
    max_hints: int = 6, model_root: str | Path | None = None,
) -> tuple[NeuralOcrLine, ...]:
    """Recognize a bounded crop ensemble; fail open on every dependency error."""
    snapshot = resolve_local_trocr_snapshot(model_root)
    if snapshot is None:
        return ()
    crops = propose_ocr_crops(
        image, seed_boxes=seed_boxes, max_crops=max_hints,
    )
    if not crops:
        return ()
    try:
        with _MODEL_LOCK:
            processor, model, device = _load_local_model(str(snapshot))
        import torch
        prepared = [_prepare_crop(image, crop) for crop in crops]
        pixel_values = processor(
            images=prepared, return_tensors="pt",
        ).pixel_values.to(device)
        with torch.inference_mode():
            generated = model.generate(
                # This is a bounded fallback behind physical TextLine seeds,
                # not a free-running document recognizer.  Four-beam CPU
                # decoding produced a 9.9 s cold outlier without fixing one
                # canonical catastrophic line; greedy decoding preserves the
                # same local hypothesis contract and keeps Max anytime-safe.
                pixel_values, max_new_tokens=32, num_beams=1,
                return_dict_in_generate=True,
                output_scores=True,
            )
        texts = processor.batch_decode(
            generated.sequences, skip_special_tokens=True,
        )
        scores = getattr(generated, "sequences_scores", None)
        score_rows = (
            scores.detach().float().cpu().tolist()
            if scores is not None else [None] * len(texts)
        )
    except Exception:
        return ()

    candidates: list[NeuralOcrLine] = []
    for crop, raw_text, raw_score in zip(crops, texts, score_rows):
        text = _normalize_text(raw_text)
        alphanumeric = sum(character.isalnum() for character in text)
        nonspace = sum(not character.isspace() for character in text)
        if alphanumeric < 2 or nonspace == 0:
            continue
        lexical = alphanumeric / nonspace
        sequence = (
            float(math.exp(max(-6.0, min(0.0, float(raw_score)))))
            if raw_score is not None and math.isfinite(float(raw_score)) else 0.5
        )
        confidence = float(np.clip(
            0.45 + 0.30 * lexical + 0.20 * sequence
            + 0.05 * min(1.0, alphanumeric / 8.0),
            0.0, 1.0,
        ))
        candidates.append(NeuralOcrLine(
            text, crop.bbox_xyxy, confidence,
            f"trocr-small-printed:{crop.provenance}:{crop.preparation}",
        ))

    # Keep one strongest transcription per effectively identical physical
    # box, while retaining distinct line crops.  No language dictionary or
    # filename is consulted, so this remains clean-room/source-only evidence.
    selected: list[NeuralOcrLine] = []
    for candidate in sorted(
        candidates,
        key=lambda row: (
            -row.confidence,
            -sum(character.isalnum() for character in row.text),
            row.text.casefold(), row.bbox_xyxy,
        ),
    ):
        if any(
            _box_iou(candidate.bbox_xyxy, previous.bbox_xyxy) >= 0.94
            for previous in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= max(1, min(8, int(max_hints))):
            break
    selected.sort(key=lambda row: (
        row.bbox_xyxy[1], row.bbox_xyxy[0], -row.confidence,
        row.text.casefold(),
    ))
    return tuple(selected)

"""Preview-only font retrieval for known text inside a raster ROI.

This module is deliberately separate from the production vectorizer.  It is a
small experiment for the question "is this word close to one of our local
fonts?" rather than an OCR system: the caller must provide both the text and a
bounding box.

The matcher renders every candidate font at high resolution, searches letter
tracking plus a small affine neighbourhood, and ranks the binary silhouettes
with IoU, a symmetric distance-transform (chamfer) term, and topology.  The CLI
writes machine-readable JSON and a contact sheet so that a human can reject a
plausible-looking but incorrect match before it affects vectorization.
"""

from __future__ import annotations

import argparse
from functools import lru_cache
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


SCHEMA = "font-match-preview-v1"
CATALOG_SCHEMA = "font-match-catalog-v1"
DEFAULT_JSONL = (
    Path(__file__).resolve().parent.parent
    / "v-ize train"
    / "dataset"
    / "text_shapes"
    / "text_shapes.jsonl"
)

_JSON_STRING = r'"(?:\\.|[^"\\])*"'
_FONT_FILE_RE = re.compile(r'"font_file"\s*:\s*(' + _JSON_STRING + r")")
_FONT_NAME_RE = re.compile(r'"font"\s*:\s*(' + _JSON_STRING + r")")


@dataclass(frozen=True)
class FontRecord:
    name: str
    path: str


@dataclass(frozen=True)
class MaskMetrics:
    score: float
    iou: float
    chamfer: float
    shape_similarity: float
    topology_similarity: float
    components: int
    holes: int


@dataclass(frozen=True)
class FontMatch:
    rank: int
    font: str
    font_file: str
    score: float
    iou: float
    chamfer: float
    shape_similarity: float
    topology_similarity: float
    components: int
    holes: int
    tracking_em: float
    x_scale: float
    y_scale: float
    dx_px: float
    dy_px: float


def parse_bbox(value: str | Sequence[int]) -> tuple[int, int, int, int]:
    """Parse ``x,y,w,h`` and reject empty or negative-size boxes."""

    if isinstance(value, str):
        pieces = [part.strip() for part in value.split(",")]
        if len(pieces) != 4:
            raise argparse.ArgumentTypeError("bbox must be x,y,w,h")
        try:
            values = tuple(int(round(float(part))) for part in pieces)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("bbox values must be numeric") from exc
    else:
        if len(value) != 4:
            raise ValueError("bbox must contain four values")
        values = tuple(int(item) for item in value)
    x, y, width, height = values
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("bbox must have x,y >= 0 and w,h > 0")
    return x, y, width, height


def parse_float_grid(value: str) -> tuple[float, ...]:
    values = sorted({round(float(part.strip()), 8) for part in value.split(",") if part.strip()})
    if not values:
        raise argparse.ArgumentTypeError("grid must contain at least one number")
    return tuple(values)


def _decode_json_string(match: re.Match[str] | None) -> str | None:
    if match is None:
        return None
    try:
        return str(json.loads(match.group(1)))
    except (json.JSONDecodeError, TypeError):
        return None


def discover_font_catalog(
    jsonl_path: str | Path,
    *,
    stop_after_stale: int = 25_000,
    min_fonts_before_stopping: int = 8,
    expected_fonts: int = 0,
) -> tuple[list[FontRecord], dict[str, int | bool]]:
    """Stream the large text-shapes JSONL without parsing its embedded SVG.

    Only the two small string fields at the front of each line are extracted.
    The scan stops after ``stop_after_stale`` consecutive rows add no new font,
    or immediately after ``expected_fonts`` unique files have been seen.  Pass
    ``stop_after_stale=0`` to force a complete scan.
    """

    source = Path(jsonl_path)
    if not source.is_file():
        raise FileNotFoundError(f"font JSONL not found: {source}")

    found: dict[str, FontRecord] = {}
    rows = 0
    stale = 0
    stopped_early = False
    with source.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            rows += 1
            font_file = _decode_json_string(_FONT_FILE_RE.search(line))
            if not font_file:
                stale += 1
                continue
            key = str(Path(font_file)).casefold()
            if key in found:
                stale += 1
            else:
                name = _decode_json_string(_FONT_NAME_RE.search(line))
                found[key] = FontRecord(name=name or Path(font_file).stem, path=font_file)
                stale = 0

            if expected_fonts > 0 and len(found) >= expected_fonts:
                stopped_early = True
                break
            if (
                stop_after_stale > 0
                and len(found) >= min_fonts_before_stopping
                and stale >= stop_after_stale
            ):
                stopped_early = True
                break

    records = sorted(found.values(), key=lambda item: (item.name.casefold(), item.path.casefold()))
    stats: dict[str, int | bool] = {
        "rows_scanned": rows,
        "unique_fonts": len(records),
        "stopped_early": stopped_early,
    }
    return records, stats


def _read_catalog(path: Path) -> list[FontRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != CATALOG_SCHEMA or not isinstance(payload.get("fonts"), list):
        raise ValueError(f"unsupported font catalog: {path}")
    return [FontRecord(str(item["name"]), str(item["path"])) for item in payload["fonts"]]


def load_or_build_catalog(
    jsonl_path: str | Path,
    catalog_path: str | Path | None = None,
    *,
    refresh: bool = False,
    stop_after_stale: int = 25_000,
    expected_fonts: int = 0,
) -> tuple[list[FontRecord], dict[str, object]]:
    """Load an optional cache, otherwise discover fonts and optionally cache them."""

    cache = Path(catalog_path) if catalog_path else None
    if cache and cache.is_file() and not refresh:
        records = _read_catalog(cache)
        return records, {"source": "cache", "catalog": str(cache), "unique_fonts": len(records)}

    records, scan = discover_font_catalog(
        jsonl_path,
        stop_after_stale=stop_after_stale,
        expected_fonts=expected_fonts,
    )
    metadata: dict[str, object] = {"source": "jsonl", "jsonl": str(jsonl_path), **scan}
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps(
                {
                    "schema": CATALOG_SCHEMA,
                    "source_jsonl": str(Path(jsonl_path)),
                    "scan": scan,
                    "fonts": [asdict(item) for item in records],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        metadata["catalog"] = str(cache)
    return records, metadata


def _remove_tiny_components(mask: np.ndarray) -> np.ndarray:
    binary = mask.astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 1:
        return mask.astype(bool)
    minimum = max(1, int(round(mask.size * 0.0005)))
    cleaned = np.zeros_like(binary)
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) >= minimum:
            cleaned[labels == label] = 1
    return cleaned.astype(bool)


def _threshold_candidates(rgb: np.ndarray, alpha: np.ndarray | None) -> dict[str, np.ndarray]:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    _threshold, dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    _threshold, light = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
    background = np.median(border.astype(np.float32), axis=0)
    distance = np.linalg.norm(rgb.astype(np.float32) - background[None, None, :], axis=2)
    distance_u8 = np.clip(distance * (255.0 / max(1.0, float(distance.max()))), 0, 255).astype(np.uint8)
    _threshold, colour = cv2.threshold(
        distance_u8, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
    )
    candidates = {
        "dark": _remove_tiny_components(dark > 0),
        "light": _remove_tiny_components(light > 0),
        "colour": _remove_tiny_components(colour > 0),
    }
    if alpha is not None and int(alpha.max()) > int(alpha.min()):
        _threshold, opaque = cv2.threshold(
            alpha, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
        )
        candidates["alpha"] = _remove_tiny_components(opaque > 0)
    return candidates


def _automatic_mask_quality(mask: np.ndarray, expected_glyphs: int | None = None) -> float:
    occupancy = float(mask.mean())
    if occupancy <= 0.005 or occupancy >= 0.985:
        return -100.0
    border = np.concatenate((mask[0], mask[-1], mask[:, 0], mask[:, -1]))
    border_occupancy = float(border.mean())
    components, _holes = mask_topology(mask)
    # A deliberately tight bbox around a bold word can legitimately be 70%
    # foreground (IKEA is a useful example), so occupancy and border contact
    # are weak priors.  When the caller supplies known text, component count is
    # a much better way to distinguish the ink from its fragmented complement.
    occupancy_penalty = 0.25 * abs(occupancy - 0.35)
    component_penalty = max(0, components - 40) * 0.01
    if expected_glyphs:
        # Do not demand one connected component per glyph: low-resolution K,
        # i/j and anti-aliased diagonals routinely split.  This guard only
        # rejects obvious texture/noise masks.
        component_penalty += max(0.0, components - expected_glyphs * 2.5) * 0.03
    return 1.0 - occupancy_penalty - 0.25 * border_occupancy - component_penalty


def extract_target_mask(
    image: Image.Image | str | Path,
    bbox: str | Sequence[int],
    *,
    polarity: str = "auto",
    expected_text: str | None = None,
) -> tuple[np.ndarray, Image.Image, str]:
    """Crop a target ROI and estimate its foreground binary silhouette."""

    source = Image.open(image) if isinstance(image, (str, Path)) else image
    source.load()
    x, y, width, height = parse_bbox(bbox)
    if x + width > source.width or y + height > source.height:
        raise ValueError(
            f"bbox {(x, y, width, height)} exceeds image size {(source.width, source.height)}"
        )
    crop = source.crop((x, y, x + width, y + height)).convert("RGBA")
    rgba = np.asarray(crop)
    candidates = _threshold_candidates(rgba[:, :, :3], rgba[:, :, 3])
    if polarity == "auto":
        glyphs = sum(not char.isspace() for char in expected_text) if expected_text else None
        selected = max(
            candidates,
            key=lambda key: (_automatic_mask_quality(candidates[key], glyphs), key),
        )
    elif polarity in candidates:
        selected = polarity
    else:
        valid = ", ".join(["auto", *sorted(candidates)])
        raise ValueError(f"unknown polarity {polarity!r}; choose {valid}")
    mask = candidates[selected]
    if not np.any(mask):
        raise ValueError("target mask is empty; check bbox or --polarity")
    return mask, crop, selected


@lru_cache(maxsize=256)
def _font_codepoints(font_path: str) -> frozenset[int] | None:
    """Load each catalog cmap once per persistent worker, not per OCR line."""
    try:
        from fontTools.ttLib import TTCollection, TTFont

        path = str(font_path)
        if path.lower().endswith(".ttc"):
            collection = TTCollection(path, lazy=True)
            font = collection.fonts[0]
        else:
            font = TTFont(path, lazy=True)
        cmap = frozenset((font.getBestCmap() or {}).keys())
        font.close()
        return cmap
    except Exception:
        # Pillow remains the final authority for formats fontTools cannot open.
        return None


def _font_has_text(font_path: str | Path, text: str) -> bool:
    codepoints = {ord(char) for char in text if not char.isspace()}
    if not codepoints:
        return False
    available = _font_codepoints(str(font_path))
    return True if available is None else codepoints.issubset(available)


def render_tracked_text(
    font_path: str | Path,
    text: str,
    tracking_em: float,
    *,
    font_size: int = 192,
) -> np.ndarray:
    """Render a tightly cropped grayscale word with explicit tracking."""

    if not text:
        raise ValueError("text cannot be empty")
    # Let Pillow select RAQM when available and its basic layout engine
    # otherwise.  Requesting RAQM explicitly emits one warning per candidate
    # on minimal Pillow builds, which makes a 45-font catalog unnecessarily
    # noisy without improving Latin wordmark matching.
    font = ImageFont.truetype(str(font_path), font_size)

    tracking_px = float(tracking_em) * font_size
    positions: list[float] = []
    boxes: list[tuple[int, int, int, int] | None] = []
    for index, char in enumerate(text):
        prefix_advance = float(font.getlength(text[:index]))
        x = prefix_advance + index * tracking_px
        positions.append(x)
        try:
            box = font.getbbox(char, anchor="ls")
        except ValueError:
            box = font.getbbox(char)
        boxes.append(box)

    painted = [
        (positions[index] + box[0], box[1], positions[index] + box[2], box[3])
        for index, box in enumerate(boxes)
        if box is not None and box[2] > box[0] and box[3] > box[1]
    ]
    if not painted:
        raise ValueError(f"font produced no visible glyphs for {text!r}")
    min_x = math.floor(min(box[0] for box in painted)) - 2
    min_y = math.floor(min(box[1] for box in painted)) - 2
    max_x = math.ceil(max(box[2] for box in painted)) + 2
    max_y = math.ceil(max(box[3] for box in painted)) + 2
    width, height = max_x - min_x, max_y - min_y
    canvas = Image.new("L", (max(1, width), max(1, height)), 0)
    draw = ImageDraw.Draw(canvas)
    for index, char in enumerate(text):
        try:
            draw.text(
                (positions[index] - min_x, -min_y), char, font=font, fill=255, anchor="ls"
            )
        except ValueError:
            draw.text((positions[index] - min_x, -min_y), char, font=font, fill=255)
    array = np.asarray(canvas)
    ys, xs = np.nonzero(array > 0)
    if not len(xs):
        raise ValueError(f"font produced an empty raster for {text!r}")
    return array[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def ink_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("mask has no foreground")
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def compose_candidate(
    source_alpha: np.ndarray,
    target_mask: np.ndarray,
    *,
    x_scale: float = 1.0,
    y_scale: float = 1.0,
    dx_px: float = 0.0,
    dy_px: float = 0.0,
    supersample: int = 4,
    threshold: int = 96,
) -> np.ndarray:
    """Place a rendered word on the target canvas using a small affine fit."""

    if x_scale <= 0 or y_scale <= 0 or supersample < 1:
        raise ValueError("scales and supersample must be positive")
    height, width = target_mask.shape
    x0, y0, x1, y1 = ink_bbox(target_mask)
    target_ink_height = max(1, y1 - y0)
    source_height, source_width = source_alpha.shape
    base_scale = target_ink_height / max(1, source_height)
    destination_width = max(1, int(round(source_width * base_scale * x_scale * supersample)))
    destination_height = max(1, int(round(source_height * base_scale * y_scale * supersample)))
    resized = cv2.resize(
        source_alpha,
        (destination_width, destination_height),
        interpolation=cv2.INTER_AREA if destination_height < source_height else cv2.INTER_CUBIC,
    )

    canvas = np.zeros((height * supersample, width * supersample), dtype=np.uint8)
    center_x = ((x0 + x1) * 0.5 + dx_px) * supersample
    center_y = ((y0 + y1) * 0.5 + dy_px) * supersample
    left = int(round(center_x - destination_width * 0.5))
    top = int(round(center_y - destination_height * 0.5))
    src_x0, src_y0 = max(0, -left), max(0, -top)
    dst_x0, dst_y0 = max(0, left), max(0, top)
    copy_width = min(destination_width - src_x0, canvas.shape[1] - dst_x0)
    copy_height = min(destination_height - src_y0, canvas.shape[0] - dst_y0)
    if copy_width > 0 and copy_height > 0:
        canvas[
            dst_y0 : dst_y0 + copy_height,
            dst_x0 : dst_x0 + copy_width,
        ] = resized[
            src_y0 : src_y0 + copy_height,
            src_x0 : src_x0 + copy_width,
        ]
    if supersample > 1:
        canvas = cv2.resize(canvas, (width, height), interpolation=cv2.INTER_AREA)
    return canvas >= threshold


def mask_topology(mask: np.ndarray) -> tuple[int, int]:
    binary = mask.astype(np.uint8)
    component_labels, _ = cv2.connectedComponents(binary, connectivity=8)
    components = max(0, int(component_labels) - 1)
    padded = np.pad(mask.astype(bool), 1, constant_values=False)
    inverse = (~padded).astype(np.uint8)
    background_labels, _ = cv2.connectedComponents(inverse, connectivity=4)
    holes = max(0, int(background_labels) - 2)
    return components, holes


class MaskScorer:
    def __init__(self, target: np.ndarray):
        self.target = target.astype(bool)
        if not np.any(self.target):
            raise ValueError("target mask cannot be empty")
        self.distance_to_target = cv2.distanceTransform(
            (~self.target).astype(np.uint8), cv2.DIST_L2, 3
        )
        self.target_components, self.target_holes = mask_topology(self.target)
        self.normalizer = float(max(self.target.shape))

    def score(self, candidate: np.ndarray) -> MaskMetrics:
        candidate = candidate.astype(bool)
        if candidate.shape != self.target.shape or not np.any(candidate):
            return MaskMetrics(0.0, 0.0, 1.0, 0.0, 0.0, 0, 0)
        intersection = int(np.logical_and(self.target, candidate).sum())
        union = int(np.logical_or(self.target, candidate).sum())
        iou = intersection / max(1, union)
        distance_to_candidate = cv2.distanceTransform(
            (~candidate).astype(np.uint8), cv2.DIST_L2, 3
        )
        forward = float(self.distance_to_target[candidate].mean())
        backward = float(distance_to_candidate[self.target].mean())
        chamfer = 0.5 * (forward + backward) / self.normalizer
        shape_similarity = math.exp(-12.0 * chamfer)
        components, holes = mask_topology(candidate)
        component_error = abs(components - self.target_components) / max(
            1, self.target_components
        )
        hole_error = abs(holes - self.target_holes) / max(1, self.target_holes)
        topology_similarity = math.exp(-0.65 * component_error - 0.9 * hole_error)
        score = 0.55 * iou + 0.35 * shape_similarity + 0.10 * topology_similarity
        return MaskMetrics(
            score=score,
            iou=iou,
            chamfer=chamfer,
            shape_similarity=shape_similarity,
            topology_similarity=topology_similarity,
            components=components,
            holes=holes,
        )


def _search_one_font(
    record: FontRecord,
    text: str,
    target: np.ndarray,
    scorer: MaskScorer,
    *,
    tracking_grid: Sequence[float],
    x_scale_grid: Sequence[float],
    y_scale_grid: Sequence[float],
    supersample: int,
    refine_rounds: int,
    render_font_size: int,
) -> tuple[dict[str, float | MaskMetrics], np.ndarray] | None:
    path = Path(record.path)
    if not path.is_file() or not _font_has_text(path, text):
        return None
    rendered: dict[float, np.ndarray] = {}

    def evaluate(params: dict[str, float]) -> tuple[MaskMetrics, np.ndarray]:
        tracking = round(params["tracking_em"], 6)
        if tracking not in rendered:
            rendered[tracking] = render_tracked_text(
                path, text, tracking, font_size=render_font_size,
            )
        mask = compose_candidate(
            rendered[tracking],
            target,
            x_scale=params["x_scale"],
            y_scale=params["y_scale"],
            dx_px=params["dx_px"],
            dy_px=params["dy_px"],
            supersample=supersample,
        )
        return scorer.score(mask), mask

    best_params: dict[str, float] | None = None
    best_metrics: MaskMetrics | None = None
    best_mask: np.ndarray | None = None
    for tracking in tracking_grid:
        try:
            rendered[round(float(tracking), 6)] = render_tracked_text(
                path, text, tracking, font_size=render_font_size,
            )
        except (OSError, ValueError):
            continue
        for x_scale in x_scale_grid:
            for y_scale in y_scale_grid:
                params = {
                    "tracking_em": float(tracking),
                    "x_scale": float(x_scale),
                    "y_scale": float(y_scale),
                    "dx_px": 0.0,
                    "dy_px": 0.0,
                }
                metrics, mask = evaluate(params)
                if best_metrics is None or metrics.score > best_metrics.score:
                    best_params, best_metrics, best_mask = params, metrics, mask
    if best_params is None or best_metrics is None or best_mask is None:
        return None

    steps = {
        "tracking_em": 0.025,
        "x_scale": 0.035,
        "y_scale": 0.025,
        "dx_px": 1.0,
        "dy_px": 1.0,
    }
    limits = {
        "tracking_em": (-0.30, 0.50),
        "x_scale": (0.72, 1.30),
        "y_scale": (0.78, 1.25),
        "dx_px": (-max(3.0, target.shape[1] * 0.06), max(3.0, target.shape[1] * 0.06)),
        "dy_px": (-max(2.0, target.shape[0] * 0.10), max(2.0, target.shape[0] * 0.10)),
    }
    for _round in range(max(0, refine_rounds)):
        for name in ("tracking_em", "x_scale", "y_scale", "dx_px", "dy_px"):
            for direction in (-1.0, 1.0):
                trial = dict(best_params)
                trial[name] = min(
                    limits[name][1], max(limits[name][0], trial[name] + direction * steps[name])
                )
                try:
                    metrics, mask = evaluate(trial)
                except (OSError, ValueError):
                    continue
                if metrics.score > best_metrics.score:
                    best_params, best_metrics, best_mask = trial, metrics, mask
        steps = {name: value * 0.5 for name, value in steps.items()}

    return {**best_params, "metrics": best_metrics}, best_mask


def match_fonts(
    target: np.ndarray,
    text: str,
    fonts: Iterable[FontRecord],
    *,
    tracking_grid: Sequence[float] = (-0.16, -0.08, 0.0, 0.08, 0.16, 0.24, 0.32, 0.40),
    x_scale_grid: Sequence[float] = (0.80, 0.95, 1.10, 1.25),
    y_scale_grid: Sequence[float] = (0.90, 1.0, 1.10),
    supersample: int = 4,
    refine_rounds: int = 3,
    top_k: int = 8,
    render_font_size: int = 192,
) -> list[tuple[FontMatch, np.ndarray]]:
    """Return the best fit for each font, sorted deterministically by score."""

    if not text:
        raise ValueError("known text is required")
    if render_font_size < 16:
        raise ValueError("render_font_size must be at least 16")
    scorer = MaskScorer(target)
    raw: list[tuple[FontRecord, dict[str, float | MaskMetrics], np.ndarray]] = []
    for record in fonts:
        result = _search_one_font(
            record,
            text,
            target,
            scorer,
            tracking_grid=tracking_grid,
            x_scale_grid=x_scale_grid,
            y_scale_grid=y_scale_grid,
            supersample=supersample,
            refine_rounds=refine_rounds,
            render_font_size=render_font_size,
        )
        if result is not None:
            parameters, mask = result
            raw.append((record, parameters, mask))
    raw.sort(
        key=lambda item: (
            -float(getattr(item[1]["metrics"], "score")),
            item[0].name.casefold(),
            item[0].path.casefold(),
        )
    )
    matches: list[tuple[FontMatch, np.ndarray]] = []
    for rank, (record, parameters, mask) in enumerate(raw[: max(1, top_k)], start=1):
        metrics = parameters["metrics"]
        assert isinstance(metrics, MaskMetrics)
        match = FontMatch(
            rank=rank,
            font=record.name,
            font_file=record.path,
            score=metrics.score,
            iou=metrics.iou,
            chamfer=metrics.chamfer,
            shape_similarity=metrics.shape_similarity,
            topology_similarity=metrics.topology_similarity,
            components=metrics.components,
            holes=metrics.holes,
            tracking_em=float(parameters["tracking_em"]),
            x_scale=float(parameters["x_scale"]),
            y_scale=float(parameters["y_scale"]),
            dx_px=float(parameters["dx_px"]),
            dy_px=float(parameters["dy_px"]),
        )
        matches.append((match, mask))
    return matches


def _mask_image(mask: np.ndarray) -> Image.Image:
    return Image.fromarray(np.where(mask, 0, 255).astype(np.uint8), mode="L").convert("RGB")


def _overlay_image(target: np.ndarray, candidate: np.ndarray) -> Image.Image:
    canvas = np.full((*target.shape, 3), 255, dtype=np.uint8)
    target_only = np.logical_and(target, ~candidate)
    candidate_only = np.logical_and(candidate, ~target)
    overlap = np.logical_and(target, candidate)
    canvas[target_only] = (235, 65, 65)
    canvas[candidate_only] = (45, 105, 235)
    canvas[overlap] = (20, 20, 20)
    return Image.fromarray(canvas, mode="RGB")


def write_preview(
    path: str | Path,
    crop: Image.Image,
    target: np.ndarray,
    matches: Sequence[tuple[FontMatch, np.ndarray]],
) -> None:
    """Write a labelled target/candidate/overlay contact sheet."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    height, width = target.shape
    scale = max(1, min(6, 360 // max(1, width)))
    panel_w, panel_h = width * scale, height * scale
    label_h, gap = 24, 12
    sheet_w = panel_w * 2 + gap * 3
    rows = 1 + len(matches)
    sheet_h = gap + rows * (label_h + panel_h + gap)
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)
    resample = Image.Resampling.NEAREST

    crop_panel = crop.convert("RGB").resize((panel_w, panel_h), Image.Resampling.BICUBIC)
    target_panel = _mask_image(target).resize((panel_w, panel_h), resample)
    y = gap
    draw.text((gap, y), "TARGET ROI", fill="black")
    draw.text((gap * 2 + panel_w, y), "EXTRACTED MASK", fill="black")
    y += label_h
    sheet.paste(crop_panel, (gap, y))
    sheet.paste(target_panel, (gap * 2 + panel_w, y))
    y += panel_h + gap

    for match, mask in matches:
        label = f"#{match.rank} {match.font}  score={match.score:.4f}  IoU={match.iou:.4f}"
        draw.text((gap, y), label[:120], fill="black")
        draw.text((gap * 2 + panel_w, y), "red=target blue=candidate black=overlap", fill="black")
        y += label_h
        sheet.paste(_mask_image(mask).resize((panel_w, panel_h), resample), (gap, y))
        sheet.paste(
            _overlay_image(target, mask).resize((panel_w, panel_h), resample),
            (gap * 2 + panel_w, y),
        )
        y += panel_h + gap
    sheet.save(destination)


def run(args: argparse.Namespace) -> dict[str, object]:
    bbox = parse_bbox(args.bbox)
    target, crop, polarity = extract_target_mask(
        args.image, bbox, polarity=args.polarity, expected_text=args.text
    )
    if args.font:
        fonts = [FontRecord(Path(path).stem, str(Path(path))) for path in args.font]
        catalog_metadata: dict[str, object] = {"source": "explicit", "unique_fonts": len(fonts)}
    else:
        fonts, catalog_metadata = load_or_build_catalog(
            args.jsonl,
            args.catalog,
            refresh=args.refresh_catalog,
            stop_after_stale=args.catalog_stale_rows,
            expected_fonts=args.expected_fonts,
        )
    existing = [record for record in fonts if Path(record.path).is_file()]
    if not existing:
        raise RuntimeError("catalog has no readable local font files")
    matches = match_fonts(
        target,
        args.text,
        existing,
        tracking_grid=args.tracking,
        x_scale_grid=args.x_scales,
        y_scale_grid=args.y_scales,
        supersample=args.supersample,
        refine_rounds=args.refine_rounds,
        top_k=args.top_k,
    )
    if not matches:
        raise RuntimeError("none of the candidate fonts could render the requested text")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    target_path = output / "target_mask.png"
    crop_path = output / "target_crop.png"
    preview_path = output / "font_match_preview.png"
    _mask_image(target).save(target_path)
    crop.save(crop_path)
    write_preview(preview_path, crop, target, matches)
    best = matches[0][0]
    # With only one candidate there is no evidence that the winner is unique;
    # keep the ambiguity gate closed rather than treating absence of a runner
    # up as a perfect margin.
    margin = best.score - matches[1][0].score if len(matches) > 1 else 0.0
    gate_thresholds = {
        "score": 0.75,
        "iou": 0.55,
        "topology_similarity": 0.75,
        "runner_up_margin": 0.012,
    }
    gate_passed = (
        best.score >= gate_thresholds["score"]
        and best.iou >= gate_thresholds["iou"]
        and best.topology_similarity >= gate_thresholds["topology_similarity"]
        and margin >= gate_thresholds["runner_up_margin"]
    )
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "preview_only": True,
        "input": str(Path(args.image)),
        "text": args.text,
        "bbox": list(bbox),
        "mask_polarity": polarity,
        "target_topology": dict(zip(("components", "holes"), mask_topology(target))),
        "catalog": catalog_metadata,
        "search": {
            "fonts_considered": len(existing),
            "tracking_grid": list(args.tracking),
            "x_scale_grid": list(args.x_scales),
            "y_scale_grid": list(args.y_scales),
            "supersample": args.supersample,
            "refine_rounds": args.refine_rounds,
        },
        # This is intentionally conservative: passing means "worth presenting
        # as a likely font family", never "silently replace production output".
        "confidence_gate": {
            "passed": gate_passed,
            "thresholds": gate_thresholds,
            "best_score": best.score,
            "best_iou": best.iou,
            "best_topology_similarity": best.topology_similarity,
            "runner_up_margin": margin,
        },
        "artifacts": {
            "target_crop": str(crop_path),
            "target_mask": str(target_path),
            "preview": str(preview_path),
        },
        "matches": [asdict(match) for match, _mask in matches],
    }
    report_path = output / "font_match.json"
    payload["artifacts"]["report"] = str(report_path)  # type: ignore[index]
    report_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True, help="raster logo/image")
    parser.add_argument("--text", required=True, help="known text; this tool does not run OCR")
    parser.add_argument("--bbox", required=True, help="text ROI as x,y,w,h")
    parser.add_argument(
        "--jsonl", type=Path, default=DEFAULT_JSONL, help="text_shapes.jsonl used as font index"
    )
    parser.add_argument(
        "--catalog", type=Path, help="optional JSON font-catalog cache (loaded or created)"
    )
    parser.add_argument("--refresh-catalog", action="store_true")
    parser.add_argument(
        "--catalog-stale-rows",
        type=int,
        default=25_000,
        help="stop catalog scan after this many rows without a new font; 0 scans all",
    )
    parser.add_argument(
        "--expected-fonts", type=int, default=0, help="stop catalog scan at this exact count"
    )
    parser.add_argument(
        "--font", action="append", help="explicit font file; repeat to bypass the catalog"
    )
    parser.add_argument(
        "--polarity", choices=("auto", "dark", "light", "colour", "alpha"), default="auto"
    )
    parser.add_argument(
        "--tracking",
        type=parse_float_grid,
        default=parse_float_grid("-0.16,-0.08,0,0.08,0.16,0.24,0.32,0.40"),
        help="coarse tracking grid in em (use --tracking=-0.1,0,... for a negative first value)",
    )
    parser.add_argument(
        "--x-scales", type=parse_float_grid, default=parse_float_grid("0.80,0.95,1.10,1.25")
    )
    parser.add_argument(
        "--y-scales", type=parse_float_grid, default=parse_float_grid("0.90,1,1.10")
    )
    parser.add_argument("--supersample", type=int, default=4)
    parser.add_argument("--refine-rounds", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--output", type=Path, default=Path("test_runs/font_match_preview"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

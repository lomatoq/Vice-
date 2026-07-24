"""Bounded exact-font Path A that consumes REIR pixels, never the source file."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import time
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFont

from .evidence_ir import RasterEvidenceIR
from .font_license_manifest import validate_manifest
from .text_macros import ExactFontEvidence, TextLineProposal


_FONT_SUFFIXES = frozenset({".ttf", ".otf", ".ttc"})
_PROJECT_FONT_BANK = Path(__file__).resolve().parents[1] / "fonts"
_PROJECT_FONT_ROOT = _PROJECT_FONT_BANK / "google-fonts"
_PROJECT_FONT_MANIFEST = _PROJECT_FONT_BANK / "google-fonts-manifest.json"
_EXTRA_FONT_DIRS_ENV = "VICE_FONT_DIRS"


def _default_font_roots() -> tuple[Path, ...]:
    """Return deterministic owned font roots, including the drop-in bank.

    ``fonts/`` is deliberately part of the project rather than an implicit
    scan of Downloads or system fonts: every default outline that can change
    vector output must be an intentional, freezeable, licensed input.
    Additional caller-attested banks can be mounted with ``VICE_FONT_DIRS``
    (``os.pathsep`` separated), but they are never silently inferred.
    """
    roots = []
    roots.extend(
        Path(value.strip())
        for value in os.environ.get(_EXTRA_FONT_DIRS_ENV, "").split(os.pathsep)
        if value.strip()
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.absolute()).casefold()
        if key not in seen:
            seen.add(key); unique.append(root)
    return tuple(unique)


@lru_cache(maxsize=1)
def _licensed_project_catalog() -> tuple[tuple[str, str], ...]:
    manifest = json.loads(_PROJECT_FONT_MANIFEST.read_text("utf-8"))
    validate_manifest(manifest, root=_PROJECT_FONT_ROOT)
    return tuple(
        (
            str(row["family"]),
            str((_PROJECT_FONT_ROOT / str(row["font_path"])).resolve()),
        )
        for row in manifest["fonts"]
    )


def discover_owned_font_catalog(
    extra_roots: Iterable[str | Path] = (),
) -> tuple[tuple[str, str], ...]:
    """Discover every intentional local outline without duplicate files.

    Project and explicitly mounted banks are recursive so an OFL corpus can
    retain its family directories.  The catalog contains paths only; a font
    still has to pass the query-specific retrieval, topology and physical
    silhouette walls before it can affect output.
    """
    rows: list[tuple[str, str]] = list(_licensed_project_catalog())
    seen = {str(Path(path)).casefold() for _name, path in rows}
    roots = _default_font_roots() + tuple(Path(root) for root in extra_roots)
    for root in roots:
        if not root.is_dir():
            continue
        paths = sorted(
            (path for path in root.rglob("*") if path.is_file()),
            key=lambda row: str(row).casefold(),
        )
        for path in paths:
            if path.suffix.casefold() not in _FONT_SUFFIXES:
                continue
            key = str(path).casefold()
            if key in seen:
                continue
            seen.add(key)
            rows.append((path.stem, str(path)))
    return tuple(rows)


SYSTEM_FONT_CATALOG = discover_owned_font_catalog()


@lru_cache(maxsize=32768)
def _cheap_font_signature(
    path: str, text: str,
) -> tuple[float, float, int, int] | None:
    """Tiny query-specific signature used before the expensive fitter."""
    try:
        font = ImageFont.truetype(path, 40)
        mask = font.getmask(text, mode="L")
        width, height = mask.size
        if width <= 0 or height <= 0:
            return None
        alpha = np.frombuffer(bytes(mask), dtype=np.uint8).reshape(
            (height, width),
        )
        support = alpha >= 128
        if not np.any(support):
            return None
        ys, xs = np.nonzero(support)
        local = support[
            int(ys.min()):int(ys.max()) + 1,
            int(xs.min()):int(xs.max()) + 1,
        ]
        aspect = local.shape[1] / max(1.0, local.shape[0])
        density = float(np.mean(local))
        components = int(
            cv2.connectedComponents(local.astype(np.uint8), 8)[0] - 1
        )
        contours, hierarchy = cv2.findContours(
            local.astype(np.uint8), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE,
        )
        holes = 0
        if hierarchy is not None:
            for index in range(len(contours)):
                depth = 0; parent = int(hierarchy[0, index, 3])
                while parent >= 0:
                    depth += 1; parent = int(hierarchy[0, parent, 3])
                holes += int(depth % 2 == 1)
        return float(aspect), density, components, holes
    except Exception:
        return None


def _prefilter_font_catalog(
    target: np.ndarray, text: str, fonts: tuple, *, limit: int,
) -> tuple:
    """Shortlist a large installed bank without doing affine raster fits."""
    target = np.asarray(target, bool)
    ys, xs = np.nonzero(target)
    if not len(xs):
        return ()
    local = target[int(ys.min()):int(ys.max()) + 1,
                   int(xs.min()):int(xs.max()) + 1]
    target_aspect = local.shape[1] / max(1.0, local.shape[0])
    target_density = float(np.mean(local))
    target_components = int(
        cv2.connectedComponents(local.astype(np.uint8), 8)[0] - 1
    )
    contours, hierarchy = cv2.findContours(
        local.astype(np.uint8), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE,
    )
    target_holes = 0
    if hierarchy is not None:
        for index in range(len(contours)):
            depth = 0; parent = int(hierarchy[0, index, 3])
            while parent >= 0:
                depth += 1; parent = int(hierarchy[0, parent, 3])
            target_holes += int(depth % 2 == 1)
    try:
        # The installed bank contains symbol, CJK and script faces.  Pillow
        # can render a replacement/tofu box for a missing Latin glyph, which
        # both wastes a trial and can look deceptively close at h24.  The cmap
        # cache is font-specific (not word-specific), so after one lazy read it
        # also makes a large drop-in bank substantially cheaper across jobs.
        from font_match import _font_has_text as font_has_text
    except Exception:
        font_has_text = None
    ranked = []
    for record in fonts:
        if font_has_text is not None and not font_has_text(record.path, text):
            continue
        signature = _cheap_font_signature(record.path, text)
        if signature is None:
            continue
        aspect, density, components, holes = signature
        # Tracking/x-scale in the exact fitter can absorb moderate width
        # differences, so topology and ink density remain meaningful but
        # deliberately weak screen terms.  The shortlist is broad (24--64).
        score = (
            abs(math.log(max(1e-6, aspect / target_aspect)))
            + 0.55 * abs(density - target_density)
            + 0.025 * abs(components - target_components)
                / max(1, target_components)
            + 0.020 * abs(holes - target_holes) / max(1, target_holes)
        )
        ranked.append((float(score), record.path.casefold(), record))
    ranked.sort(key=lambda row: (row[0], row[1]))
    return tuple(row[2] for row in ranked[:max(1, int(limit))])


@dataclass(frozen=True)
class OcrLineHint:
    text: str
    bbox_xyxy: tuple[int, int, int, int]
    confidence: float = 1.0


@dataclass(frozen=True)
class ExactFontAudit:
    line_id: str
    recognized_text: str | None
    fonts_considered: int
    candidates_returned: int
    elapsed_ms: float
    fail_open_reason: str | None
    best_retrieval_score: float | None = None
    best_silhouette_iou: float | None = None
    best_boundary_deviation_px: float | None = None
    coarse_best_score: float | None = None


def _pil_from_reir(reir: RasterEvidenceIR) -> Image.Image:
    rgba = np.clip(reir.raster.straight_rgba * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def _bbox_iou(
    first: tuple[int, int, int, int], second: tuple[int, int, int, int]
) -> float:
    x1 = max(first[0], second[0]); y1 = max(first[1], second[1])
    x2 = min(first[2], second[2]); y2 = min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    return intersection / max(1, first_area + second_area - intersection)


def _boundary_max(first: np.ndarray, second: np.ndarray) -> float:
    kernel = np.ones((3, 3), np.uint8)
    first_boundary = cv2.morphologyEx(first.astype(np.uint8), cv2.MORPH_GRADIENT, kernel) > 0
    second_boundary = cv2.morphologyEx(second.astype(np.uint8), cv2.MORPH_GRADIENT, kernel) > 0
    if not np.any(first_boundary) or not np.any(second_boundary):
        return float(math.hypot(*first.shape))
    to_first = cv2.distanceTransform((~first_boundary).astype(np.uint8), cv2.DIST_L2, 5)
    to_second = cv2.distanceTransform((~second_boundary).astype(np.uint8), cv2.DIST_L2, 5)
    return max(float(np.max(to_first[second_boundary])),
               float(np.max(to_second[first_boundary])))


class ReirExactFontProvider:
    """OCR + bounded local font retrieval with strict silhouette output.

    OCR is evaluated once at construction from canonical REIR pixels.  Any
    missing dependency, empty OCR result or font failure returns no candidates;
    font-free/conservative TextLine paths therefore remain available.
    """

    def __init__(
        self, reir: RasterEvidenceIR, *,
        ocr_hints: Iterable[OcrLineHint] | None = None,
        font_catalog: Iterable[tuple[str, str]] | None = None,
        font_directories: Iterable[str | Path] = (),
        max_fonts: int = 12, top_k: int = 4, refine_rounds: int = 1,
        min_native_height: int = 8,
        allow_upscale_ocr: bool = False,
        enable_font_search: bool = True,
    ) -> None:
        reir.validate()
        self.source_sha256 = reir.source_sha256
        self.image = _pil_from_reir(reir)
        self.max_fonts = max(1, min(32, int(max_fonts)))
        self.top_k = max(1, min(8, int(top_k)))
        self.refine_rounds = max(0, min(3, int(refine_rounds)))
        self.min_native_height = max(3, int(min_native_height))
        self.allow_upscale_ocr = bool(allow_upscale_ocr)
        self.font_search_enabled = bool(enable_font_search)
        self._explicit_catalog = font_catalog is not None
        self._audits: list[ExactFontAudit] = []
        if ocr_hints is None:
            self._hints = self._run_ocr()
        else:
            self._hints = tuple(ocr_hints)
        directory_rows = tuple(font_directories)
        catalog = tuple(
            font_catalog
            if font_catalog is not None else
            discover_owned_font_catalog(directory_rows)
            if directory_rows else SYSTEM_FONT_CATALOG
        )
        available = tuple(
            (str(name), str(path)) for name, path in catalog
            if Path(path).is_file()
        )
        # ``max_fonts`` bounds expensive refined fits.  Truncating the cheap
        # system-font retrieval bank to the first N entries meant the normal
        # fast-catalog-2 mode only ever considered Arial/Arial Bold and could
        # never retrieve Segoe, Tahoma, Verdana, serif or display faces.  The
        # non-explicit catalog is already a fixed owned-font bank; screen it
        # all once, then refine only the top match.  Explicit/owned catalogs
        # retain the caller's exact bound.
        self._catalog = (
            available[:self.max_fonts] if self._explicit_catalog
            else available
        )

    @property
    def audits(self) -> tuple[ExactFontAudit, ...]:
        return tuple(self._audits)

    def line_hints(self) -> tuple[OcrLineHint, ...]:
        return self._hints

    def _run_ocr(self) -> tuple[OcrLineHint, ...]:
        try:
            from text_substitution import ocr_lines
            rows = ocr_lines(self.image)
            if not rows and self.allow_upscale_ocr:
                # Tiny coloured/condensed words have different OCR optima:
                # 3x raw recovered many ordinary labels, but missed the pale
                # Spadegaming line that 2x contrast reads cleanly.  Run this
                # bounded ensemble only after native OCR is empty, then merge
                # duplicate boxes deterministically in native coordinates.
                scaled_rows: list[tuple[int, dict]] = []
                for factor, contrast, priority in (
                    (2, 1.0, 1), (2, 2.0, 3), (3, 1.0, 2),
                ):
                    enlarged = self.image.resize(
                        (self.image.width * factor,
                         self.image.height * factor),
                        Image.Resampling.LANCZOS,
                    )
                    if contrast != 1.0:
                        enlarged = ImageEnhance.Contrast(enlarged).enhance(
                            contrast,
                        )
                    for row in ocr_lines(enlarged):
                        scaled_rows.append((priority, {
                            "text": row["text"],
                            "bbox": tuple(
                                value / factor for value in row["bbox"]
                            ),
                        }))
                # A condensed h24 display line can remain below WinOCR's
                # stroke-width floor at 3x; cursive JPEG text may need an even
                # larger contrast-normalized view.  Spend those calls only if
                # the cheaper ensemble produced no line at all.
                if not scaled_rows:
                    for factor, contrast, priority in (
                        (4, 1.0, 2), (4, 2.0, 3), (8, 2.0, 3),
                    ):
                        enlarged = self.image.resize(
                            (self.image.width * factor,
                             self.image.height * factor),
                            Image.Resampling.LANCZOS,
                        )
                        if contrast != 1.0:
                            enlarged = ImageEnhance.Contrast(enlarged).enhance(
                                contrast,
                            )
                        for row in ocr_lines(enlarged):
                            scaled_rows.append((priority, {
                                "text": row["text"],
                                "bbox": tuple(
                                    value / factor for value in row["bbox"]
                                ),
                            }))
                        if scaled_rows:
                            break
                # Very small horizontal lockups often place a non-text mark
                # to the left of a condensed word.  Whole-image OCR then
                # spends its layout budget on the mark and returns nothing,
                # even though the same immutable pixels are readable after a
                # bounded right-side crop.  Try exactly one such crop only
                # after the full-frame ensemble is empty.  A returned box
                # touching the crop boundary is rejected because it could be
                # a word whose first glyph was cut off.
                if (
                    not scaled_rows
                    and self.image.width >= 2.2 * self.image.height
                ):
                    crop_x = int(round(0.14 * self.image.width))
                    cropped = self.image.crop((
                        crop_x, 0, self.image.width, self.image.height,
                    ))
                    factor = 4
                    enlarged = cropped.resize(
                        (cropped.width * factor, cropped.height * factor),
                        Image.Resampling.LANCZOS,
                    )
                    for row in ocr_lines(enlarged):
                        raw_bbox = tuple(float(value) for value in row["bbox"])
                        if (
                            len(raw_bbox) != 4
                            or raw_bbox[0] <= 0.03 * enlarged.width
                        ):
                            continue
                        scaled_rows.append((2, {
                            "text": row["text"],
                            "bbox": (
                                raw_bbox[0] / factor + crop_x,
                                raw_bbox[1] / factor,
                                raw_bbox[2] / factor + crop_x,
                                raw_bbox[3] / factor,
                            ),
                        }))
                clusters: list[list[tuple[int, dict]]] = []
                for priority, row in sorted(
                    scaled_rows,
                    key=lambda item: (
                        item[1]["bbox"][1], item[1]["bbox"][0],
                        -item[0], str(item[1]["text"]),
                    ),
                ):
                    bbox = tuple(float(value) for value in row["bbox"])
                    target = None
                    for cluster in clusters:
                        other = tuple(float(value) for value in cluster[0][1]["bbox"])
                        ix = max(0.0, min(bbox[2], other[2])
                                 - max(bbox[0], other[0]))
                        iy = max(0.0, min(bbox[3], other[3])
                                 - max(bbox[1], other[1]))
                        x_overlap = ix / max(
                            1.0, min(bbox[2] - bbox[0], other[2] - other[0]),
                        )
                        y_overlap = iy / max(
                            1.0, min(bbox[3] - bbox[1], other[3] - other[1]),
                        )
                        if x_overlap >= 0.50 and y_overlap >= 0.60:
                            target = cluster
                            break
                    if target is None:
                        clusters.append([(priority, row)])
                    else:
                        target.append((priority, row))
                rows = [
                    max(
                        cluster,
                        key=lambda item: (
                            sum(
                                ch.isalnum()
                                for ch in str(item[1]["text"])
                            ) / max(1, sum(
                                not ch.isspace()
                                for ch in str(item[1]["text"])
                            )),
                            -sum(
                                not (ch.isalnum() or ch.isspace())
                                for ch in str(item[1]["text"])
                            ),
                            item[0],
                            sum(ch.isalnum() for ch in str(item[1]["text"])),
                            str(item[1]["text"]),
                        ),
                    )[1]
                    for cluster in clusters
                ]
        except Exception:
            rows = []
        result: list[OcrLineHint] = []
        for row in rows:
            text = str(row.get("text", "")).strip()
            bbox = tuple(int(round(value)) for value in row.get("bbox", ()))
            if text and len(bbox) == 4 and bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                result.append(OcrLineHint(
                    # ``text_substitution.ocr_lines`` exposes no calibrated
                    # recognition probability.  Treating absence as 1.0 made
                    # any non-empty WinOCR hallucination outrank a scored
                    # neural alternative forever.  0.80 is a provider prior,
                    # not an admission score; downstream physical walls still
                    # decide whether either transcription can affect output.
                    text, bbox, float(np.clip(row.get("confidence", 0.80), 0.0, 1.0)),
                ))
        # A pathological OCR backend cannot make proposal count unbounded.
        result.sort(key=lambda row: (
            row.bbox_xyxy[1], row.bbox_xyxy[0], -row.confidence,
            row.text.casefold(),
        ))
        return tuple(result[:10])

    @staticmethod
    def _usable_ocr_hint(row: OcrLineHint) -> bool:
        alphanumeric = sum(character.isalnum() for character in row.text)
        nonspace = sum(not character.isspace() for character in row.text)
        return bool(
            alphanumeric >= 4
            and alphanumeric / max(1, nonspace) >= 0.85
        )

    def refine_line_hints(
        self, proposals: Iterable[TextLineProposal],
    ) -> tuple[OcrLineHint, ...]:
        """Buy TrOCR only after cheap physical TextLines supply seed boxes."""
        if (
            not self.allow_upscale_ocr
            or any(self._usable_ocr_hint(row) for row in self._hints)
        ):
            return self._hints
        ranked = []
        for line in proposals:
            x1, y1, x2, y2 = line.roi_xyxy
            width = x2 - x1; height = y2 - y1
            if (
                line.score < 0.90 or len(line.glyphs) < 4
                or height < 4 or width / max(1, height) < 1.8
            ):
                continue
            ranked.append((-line.score, -len(line.glyphs), line.id, line))
        ranked.sort(key=lambda row: row[:3])
        seed_boxes = tuple(row[3].roi_xyxy for row in ranked[:2])
        if not seed_boxes:
            return self._hints
        try:
            from .neural_ocr import recognize_local_text

            neural_rows = recognize_local_text(
                self.image, seed_boxes=seed_boxes, max_hints=2,
            )
        except Exception:
            neural_rows = ()
        result = list(self._hints)
        for row in neural_rows:
            candidate = OcrLineHint(
                str(row.text), tuple(row.bbox_xyxy), float(row.confidence),
            )
            duplicate = next((
                index for index, previous in enumerate(result)
                if previous.text.casefold() == candidate.text.casefold()
                and _bbox_iou(previous.bbox_xyxy, candidate.bbox_xyxy) >= 0.80
            ), None)
            if duplicate is None:
                result.append(candidate)
            elif candidate.confidence > result[duplicate].confidence:
                result[duplicate] = candidate
        result.sort(key=lambda row: (
            row.bbox_xyxy[1], row.bbox_xyxy[0], -row.confidence,
            row.text.casefold(),
        ))
        self._hints = tuple(result[:10])
        return self._hints

    def _matching_hint(self, line: TextLineProposal) -> OcrLineHint | None:
        source_texts = {
            source.split(":", 1)[1].strip().casefold()
            for source in line.sources
            if source.startswith("ocr-text:") and source.split(":", 1)[1].strip()
        }
        ranked = sorted(
            ((
                hint.text.strip().casefold() in source_texts,
                _bbox_iou(line.roi_xyxy, hint.bbox_xyxy),
                abs(
                    0.5 * (line.roi_xyxy[1] + line.roi_xyxy[3])
                    - 0.5 * (hint.bbox_xyxy[1] + hint.bbox_xyxy[3])
                ) / max(1.0, line.roi_xyxy[3] - line.roi_xyxy[1]),
                hint,
            ) for hint in self._hints),
            key=lambda row: (
                -int(row[0]), -row[3].confidence, -row[1], row[2],
                row[3].text.casefold(),
            ),
        )
        if not ranked:
            return None
        text_match, score, vertical, hint = ranked[0]
        return hint if text_match or score >= 0.08 or vertical <= 0.65 else None

    def __call__(
        self, reir: RasterEvidenceIR, line: TextLineProposal
    ) -> tuple[ExactFontEvidence, ...]:
        started = time.perf_counter()
        if reir.source_sha256 != self.source_sha256:
            raise ValueError("exact-font provider is bound to another REIR")
        hint = self._matching_hint(line)
        if not self.font_search_enabled:
            self._audits.append(ExactFontAudit(
                line.id, hint.text if hint else None, 0, 0,
                (time.perf_counter() - started) * 1000.0,
                "font-search-not-priced-by-cheap-cascade",
            ))
            return ()
        height = line.roi_xyxy[3] - line.roi_xyxy[1]
        if hint is None or height < self.min_native_height or not self._catalog:
            reason = (
                "no-ocr-line" if hint is None else
                "below-physical-height" if height < self.min_native_height else
                "empty-font-catalog"
            )
            self._audits.append(ExactFontAudit(
                line.id, hint.text if hint else None, len(self._catalog), 0,
                (time.perf_counter() - started) * 1000.0, reason,
            ))
            return ()
        try:
            import font_match as matcher
            fonts = tuple(
                matcher.FontRecord(name, path) for name, path in self._catalog
            )
            x1, y1, x2, y2 = line.roi_xyxy
            target = np.asarray(line.support_mask[y1:y2, x1:x2], bool)
            coarse_best_score: float | None = None
            if self._explicit_catalog and len(fonts) <= 2:
                # Small explicitly supplied catalogs are already a retrieval
                # result (and are used for owned-font exact substitution).
                matches = matcher.match_fonts(
                    target, hint.text, fonts, top_k=self.top_k,
                    refine_rounds=self.refine_rounds,
                    tracking_grid=(-0.16, 0.0, 0.16, 0.32),
                    x_scale_grid=(0.85, 1.0, 1.15),
                    y_scale_grid=(0.90, 1.0, 1.10), supersample=4,
                )
            else:
                # Large catalogs first get one cheap canonical silhouette per
                # font.  Only a strong coarse retrieval may buy the physical
                # affine search.  This fail-open wall removes seconds of work
                # on custom logos that cannot be any catalog font.
                fonts = _prefilter_font_catalog(
                    target, hint.text, fonts,
                    # Cheap signatures are deliberately approximate.  A
                    # 24-face shortlist dropped the real best serif/script
                    # match before the canonical silhouette court.  Keep a
                    # fixed 64-face coarse bank; ``max_fonts`` still bounds
                    # only expensive refined fits.
                    limit=64,
                )
                coarse = matcher.match_fonts(
                    target, hint.text, fonts,
                    top_k=min(4, self.max_fonts), refine_rounds=0,
                    tracking_grid=(0.0,), x_scale_grid=(1.0,),
                    y_scale_grid=(1.0,), supersample=1,
                    render_font_size=64,
                )
                coarse_best_score = (
                    float(coarse[0][0].score) if coarse else None
                )
                matches = []
                # 0.58 is a cheap pricing wall, not a correctness wall.  A
                # high-confidence neural transcription may buy one bounded
                # physical fit from 0.42 upward; it still cannot enter CMIR
                # unless the unchanged silhouette/topology admission walls
                # and the exact production court accept the rendered font.
                can_buy_refinement = bool(
                    coarse and (
                        coarse[0][0].score >= 0.58
                        or hint.confidence >= 0.90
                        and coarse[0][0].score >= 0.42
                    )
                )
                if can_buy_refinement:
                    by_path = {record.path: record for record in fonts}
                    seed_records = tuple(
                        record for seed, _mask in coarse[:min(4, self.max_fonts)]
                        if (record := by_path.get(seed.font_file)) is not None
                    )
                    if seed_records:
                        matches = matcher.match_fonts(
                            target, hint.text, seed_records,
                            top_k=min(self.top_k, len(seed_records)),
                            refine_rounds=self.refine_rounds,
                            tracking_grid=(-0.16, 0.0, 0.16, 0.32),
                            x_scale_grid=(0.85, 1.0, 1.15),
                            y_scale_grid=(0.90, 1.10), supersample=2,
                        )
            result = []
            for match, local_mask in matches:
                full = np.zeros((reir.height, reir.width), bool)
                full[y1:y2, x1:x2] = np.asarray(local_mask, bool)
                full.setflags(write=False)
                result.append(ExactFontEvidence(
                    id=f"exact-font-{line.id}-{match.rank}",
                    font_file=match.font_file, recognized_text=hint.text,
                    support_mask=full, retrieval_score=float(match.score),
                    silhouette_iou=float(match.iou),
                    max_boundary_deviation_px=_boundary_max(target, local_mask),
                    tracking_em=float(match.tracking_em),
                    x_scale=float(match.x_scale), y_scale=float(match.y_scale),
                    offset_xy=(float(match.dx_px), float(match.dy_px)),
                    provenance=(
                        "OCR-from-canonical-REIR", f"font-name:{match.font}",
                        f"rank:{match.rank}", "bounded-catalog",
                    ),
                ))
            fail_reason = None
        except Exception as error:
            result = []
            fail_reason = f"fail-open:{type(error).__name__}"
        best = max(
            result, key=lambda row: row.retrieval_score,
            default=None,
        )
        self._audits.append(ExactFontAudit(
            line.id, hint.text, len(self._catalog), len(result),
            (time.perf_counter() - started) * 1000.0, fail_reason,
            best_retrieval_score=(
                float(best.retrieval_score) if best is not None else None
            ),
            best_silhouette_iou=(
                float(best.silhouette_iou) if best is not None else None
            ),
            best_boundary_deviation_px=(
                float(best.max_boundary_deviation_px)
                if best is not None else None
            ),
            coarse_best_score=coarse_best_score,
        ))
        return tuple(result)

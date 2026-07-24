"""Approximate-template TextLine lane: the v9.5 bridge (audit S9).

The exact-font lane prices catalog fitting behind a silhouette wall that a
custom or unbanked font can never pass, so on real loci it admits nothing.
This lane replaces that seeding step with STYLE retrieval: the line's own
support mask queries the face descriptor bank (stroke width/contrast, slant,
density) and the top-K nearest faces each buy one bounded affine fit through
the same production fitter the exact lane uses.

The lane does not claim font identity - its provenance says so explicitly -
and its rows can only enter CMIR through the existing admission walls of
``generate_text_macros`` (the strict wall when a fit is genuinely exact,
otherwise the semantic-font-idealization wall) and may still be rejected by
the court. Everything is fail-open, exactly like the exact lane.

Route identity (S4.8): provenance ("approximate-template-retrieval",
"style-top{K}", "no-font-identity-claim", "font-name:...", "rank:...").
Flag / rollback: the lane exists only when a caller constructs this provider
(experiment4 ``--approximate-template``); not constructing it removes the
route completely.
Budget: OCR is delegated to one inner exact-font provider (no font search);
per admitted OCR line at most ``top_k`` refined fits with ``refine_rounds``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

from .exact_font_provider import (
    ExactFontAudit,
    ReirExactFontProvider,
    _boundary_max,
)
from .text_macros import ExactFontEvidence, TextLineProposal

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR_BANK = (
    PROJECT / "benchmarks" / "pcdc_pre_v14" / "font_style_descriptors.json"
)
QUERY_FEATURES = ("stroke_width_norm", "stroke_contrast", "slant", "density")
# The ink box spans cap+descender; cap height is roughly 85% of it. The bias
# is shared by every query, so the ranking it feeds stays consistent.
CAP_FROM_INK_HEIGHT = 0.85


def _style_query(mask: np.ndarray) -> dict[str, float] | None:
    """Cheap style features of one line support mask (query side)."""
    ink = np.asarray(mask, bool)
    if not ink.any():
        return None
    ys, xs = np.nonzero(ink)
    ink_height = float(ys.max() - ys.min() + 1)
    cap_proxy = max(4.0, CAP_FROM_INK_HEIGHT * ink_height)
    binary = ink.astype(np.uint8)
    distance = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    ink_distance = distance[binary > 0]
    moments = cv2.moments(binary, binaryImage=True)
    slant = (
        moments["mu11"] / moments["mu02"] if moments["mu02"] > 1e-6 else 0.0
    )
    box_area = float(
        (xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)
    )
    return {
        "stroke_width_norm": float(2.0 * np.median(ink_distance) / cap_proxy),
        "stroke_contrast": float(
            np.percentile(ink_distance, 90)
            / max(0.5, np.percentile(ink_distance, 10))
        ),
        "slant": float(slant),
        "density": float(binary.sum() / max(1.0, box_area)),
    }


class ApproximateTemplateProvider:
    """ExactFontProvider-protocol lane: style retrieval + bounded fits."""

    def __init__(
        self, reir, *,
        inner: ReirExactFontProvider | None = None,
        descriptor_bank: Path = DEFAULT_DESCRIPTOR_BANK,
        top_k: int = 8, refine_rounds: int = 1,
        min_native_height: int = 8,
    ) -> None:
        self.source_sha256 = reir.source_sha256
        self.inner = inner if inner is not None else ReirExactFontProvider(
            reir, max_fonts=2, top_k=1, refine_rounds=0,
            allow_upscale_ocr=True, enable_font_search=False,
        )
        self.top_k = int(top_k)
        self.refine_rounds = int(refine_rounds)
        self.min_native_height = int(min_native_height)
        bank = json.loads(Path(descriptor_bank).read_text(encoding="utf-8"))
        self._normalization = bank["normalization"]
        faces = bank["faces"]
        self._face_names: list[str] = []
        self._face_paths: list[Path] = []
        rows = []
        for face in faces.values():
            path = PROJECT / face["path"]
            if not path.is_file():
                continue
            self._face_names.append(str(face["family"]))
            self._face_paths.append(path)
            rows.append([
                (face["features"][name] - self._normalization[name]["mean"])
                / self._normalization[name]["std"]
                for name in QUERY_FEATURES
            ])
        self._matrix = np.asarray(rows, np.float64)
        self._audits: list[ExactFontAudit] = []

    # --- OCR surface is delegated so line gating matches the exact lane ---

    def line_hints(self):
        return self.inner.line_hints()

    def refine_line_hints(self, proposals):
        return self.inner.refine_line_hints(proposals)

    @property
    def audits(self) -> tuple[ExactFontAudit, ...]:
        return tuple(self._audits)

    # --- the lane ---

    def __call__(
        self, reir, line: TextLineProposal,
    ) -> tuple[ExactFontEvidence, ...]:
        started = time.perf_counter()
        if reir.source_sha256 != self.source_sha256:
            raise ValueError(
                "approximate-template provider is bound to another REIR"
            )
        hint = self.inner._matching_hint(line)
        height = line.roi_xyxy[3] - line.roi_xyxy[1]
        if (
            hint is None or height < self.min_native_height
            or not len(self._matrix)
        ):
            reason = (
                "no-ocr-line" if hint is None else
                "below-physical-height" if height < self.min_native_height
                else "empty-descriptor-bank"
            )
            self._audits.append(ExactFontAudit(
                line.id, hint.text if hint else None, len(self._matrix), 0,
                (time.perf_counter() - started) * 1000.0, reason,
            ))
            return ()
        try:
            import font_match as matcher

            x1, y1, x2, y2 = line.roi_xyxy
            target = np.asarray(line.support_mask[y1:y2, x1:x2], bool)
            query = _style_query(target)
            if query is None:
                raise ValueError("line support has no ink")
            vector = np.array([
                (query[name] - self._normalization[name]["mean"])
                / self._normalization[name]["std"]
                for name in QUERY_FEATURES
            ])
            order = np.argsort(
                np.linalg.norm(self._matrix - vector, axis=1)
            )[:self.top_k]
            seed_records = tuple(
                matcher.FontRecord(
                    self._face_names[int(position)],
                    # font_match sorts by path.casefold(): it expects str.
                    str(self._face_paths[int(position)]),
                )
                for position in order
            )
            matches = matcher.match_fonts(
                target, hint.text, seed_records,
                top_k=min(self.top_k, len(seed_records)),
                refine_rounds=self.refine_rounds,
                tracking_grid=(-0.16, 0.0, 0.16, 0.32),
                x_scale_grid=(0.85, 1.0, 1.15),
                y_scale_grid=(0.90, 1.0, 1.10), supersample=2,
            )
            result = []
            for match, local_mask in matches:
                full = np.zeros((reir.height, reir.width), bool)
                full[y1:y2, x1:x2] = np.asarray(local_mask, bool)
                full.setflags(write=False)
                result.append(ExactFontEvidence(
                    id=f"approx-template-{line.id}-{match.rank}",
                    font_file=match.font_file, recognized_text=hint.text,
                    support_mask=full,
                    retrieval_score=float(match.score),
                    silhouette_iou=float(match.iou),
                    max_boundary_deviation_px=_boundary_max(
                        target, local_mask,
                    ),
                    tracking_em=float(match.tracking_em),
                    x_scale=float(match.x_scale),
                    y_scale=float(match.y_scale),
                    offset_xy=(float(match.dx_px), float(match.dy_px)),
                    provenance=(
                        "approximate-template-retrieval",
                        f"style-top{self.top_k}",
                        "no-font-identity-claim",
                        f"font-name:{match.font}", f"rank:{match.rank}",
                    ),
                ))
            fail_reason = None
        except Exception as error:
            result = []
            fail_reason = f"fail-open:{type(error).__name__}"
        best = max(result, key=lambda row: row.retrieval_score, default=None)
        self._audits.append(ExactFontAudit(
            line.id, hint.text, len(self._matrix), len(result),
            (time.perf_counter() - started) * 1000.0, fail_reason,
            best.retrieval_score if best else None,
            best.silhouette_iou if best else None,
        ))
        return tuple(result)

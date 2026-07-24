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


class _StageDBooster:
    """Lazy runner for the Stage-D candidate support model (fail-open).

    The candidate checkpoint (ledger 92: unseen-family topology edit 7.56x
    better than classical thresholding) cleans the fit target: the fitter
    matches templates against the model's recovered support instead of the
    raw thresholded line mask. Admission walls still compare against
    line.support_mask - the booster only guides geometry.
    """

    def __init__(self, checkpoint: Path) -> None:
        self._checkpoint = Path(checkpoint)
        self._model = None
        self._device = None

    def _load(self) -> None:
        import torch
        from torch import nn

        class StageDNet(nn.Module):
            # Architecture mirror of train_v10_stage_d.StageDNet (the
            # trainer lives outside the package; duplication is recorded).
            def __init__(self, in_channels: int = 3) -> None:
                super().__init__()

                def down(cin, cout):
                    return nn.Sequential(
                        nn.Conv2d(cin, cout, 3, stride=2, padding=1),
                        nn.GroupNorm(8, cout), nn.ReLU(inplace=True),
                        nn.Conv2d(cout, cout, 3, padding=1),
                        nn.GroupNorm(8, cout), nn.ReLU(inplace=True),
                    )

                def up(cin, cout):
                    return nn.Sequential(
                        nn.ConvTranspose2d(cin, cout, 2, stride=2),
                        nn.GroupNorm(8, cout), nn.ReLU(inplace=True),
                    )

                self.d1 = down(in_channels, 32)
                self.d2 = down(32, 64)
                self.d3 = down(64, 128)
                self.d4 = down(128, 256)
                self.u3 = up(256, 128)
                self.u2 = up(256, 64)
                self.u1 = up(128, 32)
                self.u0 = up(64, 32)
                self.support_head = nn.Conv2d(32, 1, 3, padding=1)
                self.sdf_head = nn.Conv2d(32, 1, 3, padding=1)

            def forward(self, x):
                e1 = self.d1(x)
                e2 = self.d2(e1)
                e3 = self.d3(e2)
                e4 = self.d4(e3)
                y3 = torch.cat([self.u3(e4), e3], dim=1)
                y2 = torch.cat([self.u2(y3), e2], dim=1)
                y1 = torch.cat([self.u1(y2), e1], dim=1)
                y0 = self.u0(y1)
                return self.support_head(y0), torch.sigmoid(self.sdf_head(y0))

        payload = torch.load(
            self._checkpoint, map_location="cpu", weights_only=False,
        )
        if payload.get("schema") != "vice-stage-d-checkpoint/v0-pilot":
            raise ValueError("unsupported stage-d checkpoint schema")
        model = StageDNet(3)
        model.load_state_dict(payload["state_dict"], strict=True)
        model.eval()
        self._device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu",
        )
        self._model = model.to(self._device)

    def boost(self, gray_roi: np.ndarray) -> np.ndarray | None:
        """gray ROI in [0,1] -> recovered support mask, or None (fail-open)."""
        try:
            import torch

            from .wordmark_prior_data import wordmark_observation_features

            if self._model is None:
                self._load()
            height, width = gray_roi.shape
            pad_h = (16 - height % 16) % 16
            pad_w = (16 - width % 16) % 16
            padded = np.pad(
                gray_roi.astype(np.float32),
                ((0, pad_h), (0, pad_w)), mode="edge",
            )
            features = wordmark_observation_features(padded)
            with torch.no_grad():
                logits, _sdf = self._model(
                    torch.from_numpy(features[None]).to(self._device),
                )
                support = (
                    torch.sigmoid(logits)[0, 0].cpu().numpy() >= 0.5
                )
            return support[:height, :width]
        except Exception:
            return None

    def boost_letterboxed(
        self, gray_roi: np.ndarray,
        canvas: tuple[int, int] = (96, 96),
    ) -> np.ndarray | None:
        """gray ROI in [0,1] -> recovered support at ROI size, or None.

        The real-domain fine-tune (ledger 94) trained exclusively on
        aspect-preserving letterboxes over 0.5 gray.  Feeding raw ROI
        sizes puts the model off its training distribution, so inference
        mirrors the trainer's _letterbox_pair exactly and maps the
        prediction back.  canvas must match the checkpoint's training
        canvas: (96, 96) for the square models, (96, 384) for the line
        model (ledger 101: square letterboxing of long words is the
        fusion cause).
        """
        try:
            import torch

            from .wordmark_prior_data import wordmark_observation_features

            if self._model is None:
                self._load()
            canvas_h, canvas_w = canvas
            height, width = gray_roi.shape
            factor = min(canvas_h / height, canvas_w / width)
            new_w = max(1, int(round(width * factor)))
            new_h = max(1, int(round(height * factor)))
            resized = cv2.resize(
                gray_roi.astype(np.float32), (new_w, new_h),
                interpolation=cv2.INTER_AREA,
            )
            board = np.full((canvas_h, canvas_w), 0.5, np.float32)
            y = (canvas_h - new_h) // 2
            x = (canvas_w - new_w) // 2
            board[y:y + new_h, x:x + new_w] = resized
            features = wordmark_observation_features(board)
            with torch.no_grad():
                logits, _sdf = self._model(
                    torch.from_numpy(features[None]).to(self._device),
                )
                support = (
                    torch.sigmoid(logits)[0, 0].cpu().numpy() >= 0.5
                )
            window = support[y:y + new_h, x:x + new_w].astype(np.uint8)
            restored = cv2.resize(
                window, (width, height), interpolation=cv2.INTER_NEAREST,
            )
            return restored.astype(bool)
        except Exception:
            return None


class ApproximateTemplateProvider:
    """ExactFontProvider-protocol lane: style retrieval + bounded fits."""

    def __init__(
        self, reir, *,
        inner: ReirExactFontProvider | None = None,
        descriptor_bank: Path = DEFAULT_DESCRIPTOR_BANK,
        top_k: int = 8, refine_rounds: int = 1,
        min_native_height: int = 8,
        stage_d_checkpoint: Path | None = None,
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
        self._booster = (
            _StageDBooster(stage_d_checkpoint)
            if stage_d_checkpoint is not None else None
        )
        self._reir_gray = None
        if self._booster is not None:
            rgba = np.asarray(reir.raster.straight_rgba, np.float32)
            if rgba.max() > 1.5:
                rgba = rgba / 255.0
            alpha = rgba[..., 3:4]
            luminance = (
                0.2126 * rgba[..., 0] + 0.7152 * rgba[..., 1]
                + 0.0722 * rgba[..., 2]
            )
            self._reir_gray = (
                luminance * alpha[..., 0] + 0.5 * (1.0 - alpha[..., 0])
            ).astype(np.float32)

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
            boosted = False
            if self._booster is not None and self._reir_gray is not None:
                recovered = self._booster.boost(
                    self._reir_gray[y1:y2, x1:x2],
                )
                if recovered is not None and recovered.any():
                    target = recovered
                    boosted = True
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
                # Experiment-D lesson: cumulative per-glyph offsets absorb
                # the linear tracking residual on long lines. Flag-gated;
                # exact-font routes keep their default-off byte-identical
                # behaviour.
                per_glyph_refine=True,
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
                        *(("stage-d-support-booster",) if boosted else ()),
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

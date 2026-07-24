"""Trainable multi-head evidence backbone and frozen checkpoint inference."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .evidence_model import EvidenceBundle, EvidenceTensorLevel
from .ingest import CanonicalRaster
from .raster_profile import ProfileFields


HEAD_CHANNELS = {
    "region_embedding": 3, "color_logits": 4, "boundary_prob": 1,
    "boundary_normal": 2, "subpixel_offset": 2, "coverage_alpha": 1,
    "corner_prob": 1, "corner_type": 3, "junction_prob": 1,
    "shape_class_logits": 4, "text_line_prob": 1, "glyph_occupancy": 1,
    "stroke_centerline_prob": 1, "stroke_half_width": 1,
    "symmetry_evidence": 1, "uncertainty": 1,
}


def build_scene_evidence_net(base_channels: int = 32):
    import torch
    import torch.nn as nn
    import torch.nn.functional as functional

    class Block(nn.Module):
        def __init__(self, input_channels: int, output_channels: int) -> None:
            super().__init__()
            self.layers = nn.Sequential(
                nn.Conv2d(input_channels, output_channels, 3, padding=1),
                nn.GroupNorm(min(8, output_channels), output_channels), nn.SiLU(),
                nn.Conv2d(output_channels, output_channels, 3, padding=1),
                nn.GroupNorm(min(8, output_channels), output_channels), nn.SiLU(),
            )

        def forward(self, value):
            return self.layers(value)

    class SceneEvidenceNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.enc0 = Block(7, base_channels)
            self.enc1 = Block(base_channels, base_channels * 2)
            self.enc2 = Block(base_channels * 2, base_channels * 4)
            self.bridge = Block(base_channels * 4, base_channels * 4)
            self.dec1 = Block(base_channels * 6, base_channels * 2)
            self.dec0 = Block(base_channels * 3, base_channels)
            self.heads = nn.ModuleDict({
                name: nn.Conv2d(base_channels, channels, 1)
                for name, channels in HEAD_CHANNELS.items()
            })

        def forward(self, value):
            e0 = self.enc0(value)
            e1 = self.enc1(functional.avg_pool2d(e0, 2, ceil_mode=True))
            e2 = self.enc2(functional.avg_pool2d(e1, 2, ceil_mode=True))
            bridge = self.bridge(e2)
            d1 = functional.interpolate(bridge, size=e1.shape[-2:], mode="bilinear", align_corners=False)
            d1 = self.dec1(torch.cat((d1, e1), dim=1))
            d0 = functional.interpolate(d1, size=e0.shape[-2:], mode="bilinear", align_corners=False)
            features = self.dec0(torch.cat((d0, e0), dim=1))
            return {name: head(features) for name, head in self.heads.items()}

    return SceneEvidenceNet()


class TorchEvidenceModel:
    def __init__(self, checkpoint: Path, *, device: str = "auto") -> None:
        import torch

        self.checkpoint = checkpoint
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        self.version = f"scene-evidence/{digest[:16]}"
        self.device = torch.device("cuda" if device == "auto" and torch.cuda.is_available()
                                   else ("cpu" if device == "auto" else device))
        payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
        base_channels = int(payload.get("base_channels", 32)) if isinstance(payload, dict) else 32
        self.metadata = ({key: value for key, value in payload.items()
                          if key != "state_dict"} if isinstance(payload, dict) else {})
        self.model = build_scene_evidence_net(base_channels)
        state = payload.get("state_dict", payload) if isinstance(payload, dict) else payload
        self.model.load_state_dict(state, strict=True)
        self.model.to(self.device).eval()

    def infer(self, raster: CanonicalRaster, profile_fields: ProfileFields,
              scales: tuple[float, ...]) -> EvidenceBundle:
        import torch

        levels = []
        with torch.inference_mode():
            for scale in scales:
                width = max(1, round(raster.width * scale))
                height = max(1, round(raster.height * scale))
                lab = cv2.resize(raster.oklab, (width, height), interpolation=cv2.INTER_AREA)
                alpha = cv2.resize(raster.alpha_native, (width, height), interpolation=cv2.INTER_AREA)
                straight_linear = np.where(
                    raster.alpha_native[..., None] > 1e-6,
                    raster.rgba_linear_premul[..., :3]
                    / np.maximum(raster.alpha_native[..., None], 1e-6), 0.0)
                linear = cv2.resize(straight_linear, (width, height), interpolation=cv2.INTER_AREA)
                value = np.concatenate((lab, alpha[..., None], linear), axis=2)
                tensor = torch.from_numpy(value.transpose(2, 0, 1)[None].astype(np.float32)).to(self.device)
                raw = self.model(tensor)
                heads = {name: _activate(name, output[0].detach().cpu().numpy().transpose(1, 2, 0))
                         for name, output in raw.items()}
                for name in tuple(heads):
                    if heads[name].shape[2] == 1:
                        heads[name] = heads[name][..., 0]
                levels.append(EvidenceTensorLevel(float(scale), heads))
        bundle = EvidenceBundle(raster.source.source_hash, self.version, tuple(levels))
        bundle.validate()
        return bundle


HYBRID_NEURAL_HEADS = frozenset({
    "coverage_alpha", "shape_class_logits", "text_line_prob", "glyph_occupancy",
    "stroke_half_width", "symmetry_evidence", "uncertainty",
})


class HybridEvidenceModel:
    """Use learned semantics only where held-out evidence beats the baseline.

    High-precision differential geometry remains deterministic.  This mirrors
    the intended deep-evidence/classical-geometry architecture and prevents a
    weak neural boundary head from degrading the downstream curve solver.
    """

    routing_version = "hybrid-routing/1"

    def __init__(self, checkpoint: Path, *, device: str = "auto") -> None:
        from .evidence_model import DeterministicEvidenceModel

        self.neural = TorchEvidenceModel(checkpoint, device=device)
        self.deterministic = DeterministicEvidenceModel()
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        self.version = f"scene-evidence-hybrid/1/{digest[:16]}"
        self.metadata = self.neural.metadata

    def infer(self, raster: CanonicalRaster, profile_fields: ProfileFields,
              scales: tuple[float, ...]) -> EvidenceBundle:
        learned = self.neural.infer(raster, profile_fields, scales)
        classical = self.deterministic.infer(raster, profile_fields, scales)
        levels = []
        for learned_level, classical_level in zip(learned.levels, classical.levels,
                                                   strict=True):
            heads = {
                name: (learned_level.heads[name] if name in HYBRID_NEURAL_HEADS
                       else classical_level.heads[name])
                for name in classical_level.heads
            }
            levels.append(EvidenceTensorLevel(classical_level.scale, heads))
        bundle = EvidenceBundle(raster.source.source_hash, self.version, tuple(levels))
        bundle.validate()
        return bundle


@dataclass(frozen=True)
class EvidenceModelSelection:
    """Auditable result of resolving the optional promoted checkpoint."""

    model: object
    checkpoint: str | None
    checkpoint_loaded: bool
    fallback_reason: str | None = None


def select_best_evidence_model(checkpoint: Path | None) -> EvidenceModelSelection:
    from .evidence_model import DeterministicEvidenceModel

    if checkpoint is None:
        return EvidenceModelSelection(
            DeterministicEvidenceModel(), None, False,
            "no promoted evidence checkpoint configured",
        )
    resolved = checkpoint.resolve()
    if not resolved.is_file():
        return EvidenceModelSelection(
            DeterministicEvidenceModel(), str(resolved), False,
            "promoted evidence checkpoint is missing",
        )
    try:
        model = HybridEvidenceModel(resolved)
        if model.metadata.get("schema") != "vice-scene-evidence-checkpoint/1":
            raise ValueError("checkpoint lacks the promoted evidence schema")
        if model.metadata.get("status") != "promoted":
            raise ValueError("checkpoint status is not promoted")
        if model.metadata.get("routing_version") != HybridEvidenceModel.routing_version:
            raise ValueError("checkpoint was promoted for a different head routing")
        return EvidenceModelSelection(
            model, str(resolved), True, None)
    except (ImportError, OSError, RuntimeError, ValueError, KeyError, EOFError) as exc:
        return EvidenceModelSelection(
            DeterministicEvidenceModel(), str(resolved), False,
            f"promoted evidence checkpoint rejected: {type(exc).__name__}: {exc}"[:500],
        )


def load_best_evidence_model(checkpoint: Path | None):
    """Compatibility wrapper; new callers should retain the selection audit."""
    return select_best_evidence_model(checkpoint).model


def _activate(name: str, value: np.ndarray) -> np.ndarray:
    value = np.asarray(value, np.float32)
    if name in {"boundary_prob", "coverage_alpha", "corner_prob", "corner_type",
                "junction_prob", "shape_class_logits",
                "text_line_prob", "glyph_occupancy", "stroke_centerline_prob",
                "symmetry_evidence", "uncertainty"}:
        value = 1.0 / (1.0 + np.exp(-np.clip(value, -30, 30)))
    elif name in {"boundary_normal", "subpixel_offset"}:
        value = np.tanh(value)
        if name == "boundary_normal":
            value /= np.maximum(np.linalg.norm(value, axis=2, keepdims=True), 1e-6)
    elif name == "stroke_half_width":
        value = np.log1p(np.exp(np.clip(value, -20, 20)))
    return value.astype(np.float32)

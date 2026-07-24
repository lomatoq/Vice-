"""Versioned feature flags and immutable engine configuration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class EngineConfig:
    schema_version: str = "vice-scene-config/1"
    engine_version: str = "0.1.1"
    max_input_pixels: int = 3_145_728
    max_colors: int = 24
    topology_k: int = 2
    max_regions: int = 128
    supersample: int = 4
    evidence_scales: tuple[float, ...] = (1.0, 0.5, 0.25)
    evidence_model: str = "promoted-checkpoint-or-deterministic/1"
    # Only a checkpoint carrying the explicit promotion name is auto-loaded.
    # Candidate checkpoints remain opt-in during the validation campaign.
    evidence_checkpoint: str | None = "models/scene_evidence.promoted.pt"
    random_seed: int = 20260719
    min_shape_area_px: float = 2.0
    residual_add_threshold: float = 0.12
    residual_min_area_px: int = 2
    residual_max_additions: int = 4
    residual_max_attempts: int = 8
    forward_models: tuple[str, ...] = (
        "clean-aa", "hard", "blur-0.6", "gamma-1.8", "jpeg-70"
    )
    enable_evidence: bool = True
    enable_appearance: bool = True
    enable_topology: bool = True
    enable_whole_shapes: bool = True
    enable_shared_boundaries: bool = True
    enable_text_scene: bool = True
    enable_exact_font_path: bool = True
    enable_idealization: bool = True
    enable_forward_court: bool = True
    enable_residual_repair: bool = True
    enable_gap_filler: bool = True
    allow_legacy_fallback: bool = False
    legacy_fallback_mode: str = "paper-regions"
    ablations: tuple[str, ...] = field(default_factory=tuple)

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False)

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def enabled(self, module: str) -> bool:
        return module not in self.ablations and bool(getattr(self, f"enable_{module}", True))

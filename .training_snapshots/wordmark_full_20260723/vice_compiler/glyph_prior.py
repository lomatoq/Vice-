"""Font-free, character-conditioned glyph proposal model.

The model is deliberately a proposal source.  Its support is never production
geometry until the deterministic topology, overlap and local-render courts have
accepted it.  Checkpoints are local, manifest-bound and fail open.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .certificates import topology_signature


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_GLYPH_PRIOR_CHECKPOINT = (
    PROJECT / "models" / "glyph_prior.pt"
)
DEFAULT_GLYPH_PRIOR_PROMOTION = PROJECT / "models" / "glyph_prior_promotion.json"
GLYPH_CHARACTERS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789&@"
)
GLYPH_CHARACTER_SHA256 = hashlib.sha256(
    GLYPH_CHARACTERS.encode("ascii")
).hexdigest()
TOPOLOGY_DECODE_THRESHOLDS = tuple(
    round(0.20 + 0.025 * index, 3) for index in range(29)
)


def glyph_prior_source_sha256() -> str:
    """Identity of model, input, target and degradation semantics."""
    digest = hashlib.sha256()
    for name in ("glyph_prior.py", "glyph_prior_data.py"):
        path = Path(__file__).with_name(name)
        digest.update(name.encode("ascii")); digest.update(b"\0")
        digest.update(path.read_bytes()); digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class GlyphPriorConfig:
    image_size: int = 64
    base_channels: int = 24
    character_embedding_dim: int = 16
    topology_embedding_dim: int = 8
    input_channels: int = 3
    component_classes: int = 6
    hole_classes: int = 5

    def validate(self) -> None:
        if self.image_size < 32 or self.image_size % 8:
            raise ValueError("glyph-prior image size must be >=32 and divisible by 8")
        if (
            self.base_channels < 8 or self.character_embedding_dim < 4
            or self.topology_embedding_dim < 4
        ):
            raise ValueError("glyph-prior model is too small for its contract")
        if self.input_channels != 3:
            raise ValueError("glyph-prior input contract requires three channels")
        if self.component_classes < 2 or self.hole_classes < 2:
            raise ValueError("glyph-prior topology heads need overflow classes")


class _ConvBlock(nn.Module):
    def __init__(self, inputs: int, outputs: int) -> None:
        super().__init__()
        groups = max(1, min(8, outputs // 4))
        while outputs % groups:
            groups -= 1
        self.layers = nn.Sequential(
            nn.Conv2d(inputs, outputs, 3, padding=1),
            nn.GroupNorm(groups, outputs), nn.SiLU(),
            nn.Conv2d(outputs, outputs, 3, padding=1),
            nn.GroupNorm(groups, outputs), nn.SiLU(),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.layers(value)


class GlyphPriorNet(nn.Module):
    """Small U-Net with support, SDF, skeleton and topology heads."""

    def __init__(self, config: GlyphPriorConfig | None = None) -> None:
        super().__init__()
        self.config = config or GlyphPriorConfig()
        self.config.validate()
        c = self.config.base_channels
        e = self.config.character_embedding_dim
        t = self.config.topology_embedding_dim
        self.character_embedding = nn.Embedding(len(GLYPH_CHARACTERS), e)
        self.component_embedding = nn.Embedding(
            self.config.component_classes, t,
        )
        self.hole_embedding = nn.Embedding(self.config.hole_classes, t)
        # Constant character channels alone are translation equivariant: they
        # can say *what* glyph this is but cannot say *where* a missing counter
        # or detached mark belongs.  Explicit physical coordinates turn the
        # conditional cleaner into an actual generative shape prior.
        axis = torch.linspace(-1.0, 1.0, self.config.image_size)
        yy, xx = torch.meshgrid(axis, axis, indexing="ij")
        self.register_buffer(
            "coordinate_grid", torch.stack((xx, yy), dim=0), persistent=True,
        )
        self.enc1 = _ConvBlock(self.config.input_channels + e + 2 * t + 2, c)
        self.enc2 = _ConvBlock(c, 2 * c)
        self.enc3 = _ConvBlock(2 * c, 4 * c)
        self.bottleneck = _ConvBlock(4 * c, 4 * c)
        self.dec2 = _ConvBlock(8 * c, 2 * c)
        self.dec1 = _ConvBlock(4 * c, c)
        self.dec0 = _ConvBlock(2 * c, c)
        self.pixel_heads = nn.Conv2d(c, 3, 1)
        # A character/topology/coordinate-only branch is the actual
        # generative prior.  The observed U-Net remains a style/evidence
        # residual, but can no longer solve the training task solely by
        # copying a corrupted input through its high-resolution skip path.
        self.prior1 = _ConvBlock(e + 2 * t + 2, c)
        self.prior2 = _ConvBlock(c, c)
        self.style_projection = nn.Conv2d(4 * c, c, 1)
        self.prior_pixel_heads = nn.Conv2d(c, 3, 1)
        # Counters and detached marks can occupy only a handful of cells.
        # Mean pooling alone erased that evidence in the first canonical run.
        # Pooling both the 1/4 and 1/8-scale maps with mean and max preserves
        # global mass as well as small, high-response topology features.
        topology_features = 16 * c
        self.component_head = nn.Linear(
            topology_features, self.config.component_classes,
        )
        self.hole_head = nn.Linear(topology_features, self.config.hole_classes)

    def forward(
        self, observed: torch.Tensor, character_ids: torch.Tensor,
        component_ids: torch.Tensor, hole_ids: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        if observed.ndim != 4 or observed.shape[1] != self.config.input_channels:
            raise ValueError("glyph-prior input must be BCHW with three channels")
        if tuple(observed.shape[-2:]) != (
            self.config.image_size, self.config.image_size,
        ):
            raise ValueError("glyph-prior input resolution differs from checkpoint")
        if character_ids.ndim != 1 or character_ids.shape[0] != observed.shape[0]:
            raise ValueError("glyph-prior character IDs are not batch aligned")
        if (
            component_ids.ndim != 1 or hole_ids.ndim != 1
            or component_ids.shape[0] != observed.shape[0]
            or hole_ids.shape[0] != observed.shape[0]
            or bool(torch.any(component_ids < 0))
            or bool(torch.any(component_ids >= self.config.component_classes))
            or bool(torch.any(hole_ids < 0))
            or bool(torch.any(hole_ids >= self.config.hole_classes))
        ):
            raise ValueError("glyph-prior topology IDs are invalid or unaligned")
        embedding = self.character_embedding(character_ids)
        component_embedding = self.component_embedding(component_ids)
        hole_embedding = self.hole_embedding(hole_ids)
        conditioning = torch.cat((
            embedding, component_embedding, hole_embedding,
        ), dim=1)
        embedding_map = conditioning[:, :, None, None].expand(
            -1, -1, self.config.image_size, self.config.image_size,
        )
        coordinates = self.coordinate_grid[None].expand(
            observed.shape[0], -1, -1, -1,
        )
        first = self.enc1(torch.cat((
            observed, embedding_map, coordinates,
        ), dim=1))
        second = self.enc2(F.avg_pool2d(first, 2))
        third = self.enc3(F.avg_pool2d(second, 2))
        latent = self.bottleneck(F.avg_pool2d(third, 2))
        decoded2 = self.dec2(torch.cat((
            F.interpolate(latent, size=third.shape[-2:], mode="bilinear", align_corners=False),
            third,
        ), dim=1))
        decoded1 = self.dec1(torch.cat((
            F.interpolate(decoded2, size=second.shape[-2:], mode="bilinear", align_corners=False),
            second,
        ), dim=1))
        # A learned high-resolution fusion is required here: simple addition
        # made the support head unable to repair threshold-scale breaks and
        # pinholes even when the low-resolution latent was correct.
        decoded = self.dec0(torch.cat((
            F.interpolate(
                decoded1, size=first.shape[-2:], mode="bilinear",
                align_corners=False,
            ),
            first,
        ), dim=1))
        # The 1/8-scale latent retains font-specific width/slant/serif layout
        # while discarding the one-pixel breaks and JPEG pinholes that made the
        # high-resolution skip path unsafe as a generator.  Spatial style is
        # necessary: a single global vector learned a legible average glyph
        # but plateaued far below the held-out silhouette gate.
        style = F.interpolate(
            self.style_projection(latent),
            size=(self.config.image_size, self.config.image_size),
            mode="bilinear", align_corners=False,
        )
        prior = self.prior1(torch.cat((
            embedding_map, coordinates,
        ), dim=1)) + style
        prior = self.prior2(prior)
        prior_pixels = self.prior_pixel_heads(prior)
        # The independently gated generator owns the coarse glyph program;
        # the high-resolution path is an unconstrained *style residual* so it
        # can recover exact serif/weight boundaries.  Its former copy shortcut
        # is now blocked by separate prior/severe promotion gates rather than
        # by a hard logit cap that also destroyed silhouette fidelity.
        residual_pixels = self.pixel_heads(decoded)
        pixels = prior_pixels + residual_pixels
        pooled = torch.cat((
            third.mean(dim=(-2, -1)), third.amax(dim=(-2, -1)),
            latent.mean(dim=(-2, -1)), latent.amax(dim=(-2, -1)),
        ), dim=1)
        component_logits = self.component_head(pooled)
        hole_logits = self.hole_head(pooled)
        return {
            "support_logits": pixels[:, 0:1],
            "sdf": torch.tanh(pixels[:, 1:2]),
            "skeleton_logits": pixels[:, 2:3],
            "prior_support_logits": prior_pixels[:, 0:1],
            "prior_sdf": torch.tanh(prior_pixels[:, 1:2]),
            "prior_skeleton_logits": prior_pixels[:, 2:3],
            "component_logits": component_logits,
            "hole_logits": hole_logits,
        }


@dataclass(frozen=True)
class GlyphPriorProposal:
    support_mask: np.ndarray
    soft_support: np.ndarray
    sdf: np.ndarray
    skeleton: np.ndarray
    topology_code: tuple[int, int]
    confidence: float
    provenance: tuple[str, ...]

    def validate(self) -> None:
        fields = (self.support_mask, self.soft_support, self.sdf, self.skeleton)
        if any(field.ndim != 2 for field in fields):
            raise ValueError("glyph-prior fields must be two dimensional")
        if len({field.shape for field in fields}) != 1:
            raise ValueError("glyph-prior fields have different shapes")
        if any(field.flags.writeable for field in fields):
            raise ValueError("glyph-prior proposal fields must be immutable")
        if topology_signature(self.support_mask) != self.topology_code:
            raise ValueError("glyph-prior topology code does not describe support")
        if not 0.0 <= self.confidence <= 1.0 or not math.isfinite(self.confidence):
            raise ValueError("glyph-prior confidence is invalid")


def character_id(character: str) -> int | None:
    if len(character) != 1:
        return None
    try:
        return GLYPH_CHARACTERS.index(character)
    except ValueError:
        return None


def topology_constrained_support(
    probability: np.ndarray, expected_topology: tuple[int, int],
    preferred_threshold: float,
) -> tuple[np.ndarray, float, bool]:
    """Project soft support onto the certified topology using thresholds only."""
    soft = np.asarray(probability, np.float32)
    preferred = float(preferred_threshold)
    expected = (int(expected_topology[0]), int(expected_topology[1]))
    if (
        soft.ndim != 2 or not np.isfinite(soft).all()
        or not 0.0 < preferred < 1.0
        or expected[0] < 0 or expected[1] < 0
    ):
        raise ValueError("invalid topology-constrained support input")
    thresholds = sorted(
        {preferred, *TOPOLOGY_DECODE_THRESHOLDS},
        key=lambda threshold: (abs(threshold - preferred), threshold),
    )
    fallback = soft >= preferred
    for threshold in thresholds:
        candidate = soft >= threshold
        if topology_signature(candidate) == expected:
            return candidate, float(threshold), True
    return fallback, preferred, False


def resolve_glyph_prior_checkpoint(path: Path | None = None) -> Path | None:
    candidate = path
    if candidate is None:
        override = os.environ.get("VICE_GLYPH_PRIOR_CHECKPOINT", "").strip()
        candidate = Path(override) if override else DEFAULT_GLYPH_PRIOR_CHECKPOINT
    candidate = candidate.expanduser().resolve()
    if not candidate.is_file():
        return None
    # The default production path is fail closed.  Explicit paths (including
    # VICE_GLYPH_PRIOR_CHECKPOINT) are evaluation overrides and remain local.
    explicit = path is not None or bool(
        os.environ.get("VICE_GLYPH_PRIOR_CHECKPOINT", "").strip()
    )
    if candidate == DEFAULT_GLYPH_PRIOR_CHECKPOINT.resolve() and not explicit:
        try:
            validate_glyph_prior_promotion(
                candidate, DEFAULT_GLYPH_PRIOR_PROMOTION,
            )
        except (OSError, RuntimeError, UnicodeDecodeError, ValueError, TypeError):
            return None
    return candidate


def validate_glyph_prior_promotion(
    checkpoint: Path = DEFAULT_GLYPH_PRIOR_CHECKPOINT,
    manifest: Path = DEFAULT_GLYPH_PRIOR_PROMOTION,
) -> dict[str, Any]:
    """Validate the production pair independently of evaluation overrides."""
    checkpoint = checkpoint.resolve(); manifest = manifest.resolve()
    if not checkpoint.is_file() or not manifest.is_file():
        raise RuntimeError("production glyph prior or promotion manifest is missing")
    promotion = json.loads(manifest.read_text("utf-8"))
    from .build_identity import compiler_source_sha256
    expected = {
        "schema": "pcdc-glyph-prior-promotion/v1",
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "model_contract_sha256": glyph_prior_source_sha256(),
        "compiler_source_sha256": compiler_source_sha256(),
    }
    mismatches = {
        key: {"expected": value, "actual": promotion.get(key)}
        for key, value in expected.items() if promotion.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"glyph-prior promotion mismatch: {mismatches}")
    return promotion


def _checkpoint_identity(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return str(path), int(stat.st_mtime_ns), int(stat.st_size)


@lru_cache(maxsize=2)
def _load_checkpoint_cached(
    identity: tuple[str, int, int],
) -> tuple[GlyphPriorNet, torch.device, dict[str, Any]]:
    path = Path(identity[0])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    payload = torch.load(path, map_location=device, weights_only=False)
    if payload.get("schema") != "pcdc-glyph-prior-checkpoint/v1":
        raise ValueError("unsupported glyph-prior checkpoint schema")
    if payload.get("character_vocab_sha256") != GLYPH_CHARACTER_SHA256:
        raise ValueError("glyph-prior checkpoint character vocabulary mismatch")
    if payload.get("model_contract_sha256") != glyph_prior_source_sha256():
        raise ValueError("glyph-prior checkpoint model/data contract is stale")
    config = GlyphPriorConfig(**dict(payload.get("config", {})))
    config.validate()
    model = GlyphPriorNet(config).to(device)
    model.load_state_dict(payload["model"], strict=True)
    model.eval()
    return model, device, payload


def load_glyph_prior(
    checkpoint: Path | None = None,
) -> tuple[GlyphPriorNet, torch.device, dict[str, Any]] | None:
    """Load a local checkpoint, returning ``None`` for any unavailable model."""
    resolved = resolve_glyph_prior_checkpoint(checkpoint)
    if resolved is None:
        return None
    try:
        return _load_checkpoint_cached(_checkpoint_identity(resolved))
    except (OSError, RuntimeError, TypeError, ValueError, KeyError):
        return None


def propose_glyph_mask(
    observed_rgb: np.ndarray,
    character: str,
    certified_support: np.ndarray,
    *,
    checkpoint: Path | None = None,
    expected_topology: tuple[int, int] | None = None,
    minimum_iou: float = 0.58,
    maximum_change_fraction: float = 0.32,
) -> GlyphPriorProposal | None:
    """Return a topology-safe proposal or fail open.

    ``certified_support`` is source-derived evidence, not a label.  Requiring
    exact topology and overlap here prevents the network from filling a counter,
    fusing letters or inventing a disconnected accent.
    """
    identifier = character_id(character)
    support = np.asarray(certified_support, bool)
    image = np.asarray(observed_rgb)
    if identifier is None or support.ndim != 2 or image.ndim not in (2, 3):
        return None
    if image.shape[:2] != support.shape or not np.any(support):
        return None
    expected = (
        topology_signature(support)
        if expected_topology is None else
        (int(expected_topology[0]), int(expected_topology[1]))
    )
    loaded = load_glyph_prior(checkpoint)
    if loaded is None:
        return None
    model, device, payload = loaded
    if (
        expected[0] < 0 or expected[1] < 0
        or expected[0] >= model.config.component_classes
        or expected[1] >= model.config.hole_classes
    ):
        return None
    # Kept lazy to ensure the warm compiler path does not import the synthetic
    # training stack or Pillow unless a checkpoint is actually enabled.
    from .glyph_prior_data import glyph_observation_features

    features = glyph_observation_features(image, model.config.image_size)
    tensor = torch.from_numpy(features[None]).to(device=device, dtype=torch.float32)
    chars = torch.tensor((identifier,), device=device, dtype=torch.long)
    component_ids = torch.tensor((expected[0],), device=device, dtype=torch.long)
    hole_ids = torch.tensor((expected[1],), device=device, dtype=torch.long)
    with torch.inference_mode():
        output = model(tensor, chars, component_ids, hole_ids)
        probability = torch.sigmoid(output["support_logits"])[0, 0].cpu().numpy()
        sdf_small = output["sdf"][0, 0].cpu().numpy()
        skeleton_small = torch.sigmoid(
            output["skeleton_logits"]
        )[0, 0].cpu().numpy()
        component_probability = torch.softmax(
            output["component_logits"], dim=1,
        )[0].cpu().numpy()
        hole_probability = torch.softmax(
            output["hole_logits"], dim=1,
        )[0].cpu().numpy()
    height, width = support.shape
    soft = cv2.resize(probability, (width, height), interpolation=cv2.INTER_LINEAR)
    sdf = cv2.resize(sdf_small, (width, height), interpolation=cv2.INTER_LINEAR)
    skeleton = cv2.resize(
        skeleton_small, (width, height), interpolation=cv2.INTER_LINEAR,
    )
    support_threshold = float(payload.get("support_threshold", 0.5))
    if not 0.0 < support_threshold < 1.0:
        return None
    candidate, decoded_threshold, topology_matched = topology_constrained_support(
        soft, expected, support_threshold,
    )
    actual = topology_signature(candidate)
    predicted = (
        int(np.argmax(component_probability)), int(np.argmax(hole_probability)),
    )
    if not topology_matched or actual != expected or predicted != expected:
        return None
    intersection = int(np.sum(candidate & support))
    union = int(np.sum(candidate | support))
    iou = intersection / max(1, union)
    changed = float(np.mean(candidate != support))
    if iou < float(minimum_iou) or changed > float(maximum_change_fraction):
        return None
    certainty = float(np.mean(np.maximum(soft, 1.0 - soft)))
    topology_confidence = float(
        component_probability[expected[0]] * hole_probability[expected[1]]
    )
    confidence = float(np.clip(
        math.sqrt(max(0.0, certainty * topology_confidence)), 0.0, 1.0,
    ))
    frozen = []
    for value in (candidate, soft, sdf, skeleton):
        item = np.ascontiguousarray(value)
        item.setflags(write=False)
        frozen.append(item)
    proposal = GlyphPriorProposal(
        support_mask=frozen[0], soft_support=frozen[1], sdf=frozen[2],
        skeleton=frozen[3], topology_code=actual, confidence=confidence,
        provenance=(
            "font-free-character-conditioned-glyph-prior",
            "positive-negative-support-and-SDF",
            "optional-skeleton-head",
            "exact-source-topology-gate",
            "proposal-only;local-render-court-mandatory",
            f"topology-conditioned-threshold:{decoded_threshold:.3f}",
            f"checkpoint:{payload.get('checkpoint_id', 'unpromoted')}",
        ),
    )
    proposal.validate()
    return proposal


def checkpoint_payload(
    model: GlyphPriorNet, *, epoch: int, manifest_sha256: str,
    split_sha256: str, selection_key: tuple[float, ...],
    training_contract_sha256: str | None = None,
    optimizer: torch.optim.Optimizer | None = None,
    support_threshold: float = 0.5,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "pcdc-glyph-prior-checkpoint/v1",
        "config": asdict(model.config),
        "model": model.state_dict(),
        "epoch": int(epoch),
        "font_manifest_sha256": str(manifest_sha256),
        "family_split_sha256": str(split_sha256),
        "character_vocab_sha256": GLYPH_CHARACTER_SHA256,
        "model_contract_sha256": glyph_prior_source_sha256(),
        "selection_contract": (
            "eligible-calibration-weakest-normalized-gate-then-topology-IoU/v2"
        ),
        "calibration_selection_key": tuple(float(v) for v in selection_key),
        "support_threshold": float(support_threshold),
    }
    if training_contract_sha256 is not None:
        payload["training_contract_sha256"] = str(training_contract_sha256)
    if optimizer is not None:
        payload["optimizer"] = optimizer.state_dict()
    return payload

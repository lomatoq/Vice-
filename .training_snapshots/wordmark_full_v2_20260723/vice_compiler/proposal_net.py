"""Phase-9 query ProposalNet, matching loss and classical-query union.

The neural lane proposes typed macro hypotheses; it never replaces REIR
boundaries or emits final SVG.  Every query must still enter the same
certificate/CMIR/extractor path as deterministic proposals.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from scipy.optimize import linear_sum_assignment

from .evidence_ir import RasterEvidenceIR
from .certificates import topology_signature
from .macro_registry import decode_token_mask
from .proposal_data_contract import RELATION_TYPES


QUERY_FAMILIES = (
    "text_line", "glyph_group", "whole_shape", "stroke_network",
    "layer_relation", "symmetry_repeat_group", "appearance_model",
    "risk_hard_negative", "no_object",
)
HARD_NEGATIVE_TYPES = (
    "fill_counter", "split_glyph", "fuse_letters", "false_circle",
    "wrong_layer", "preserve_jpeg_halo", "remove_real_accent",
    "jagged_overfit", "gradient_band_explosion", "stroke_fill_confusion",
)


@dataclass(frozen=True)
class ProposalNetConfig:
    hidden_dim: int = 128
    query_count: int = 64
    decoder_layers: int = 3
    attention_heads: int = 8
    parameter_dim: int = 24
    relation_dim: int = len(RELATION_TYPES)
    mask_upsample: int = 1
    spatial_positioning: bool = False
    text_bbox_gate_padding: float = 0.0
    text_bbox_gate_vertical_only: bool = False


def _gate_text_support_probability(
    probability: torch.Tensor, boxes: torch.Tensor,
    families: torch.Tensor, *, padding: float, vertical_only: bool = False,
) -> torch.Tensor:
    """Apply each TextLine query's own ROI as a hard support prior."""
    if probability.ndim != 4 or boxes.shape[:2] != probability.shape[:2]:
        raise ValueError("support probability and boxes are not BQ-aligned")
    if families.shape != probability.shape[:2]:
        raise ValueError("support probability and families are not BQ-aligned")
    if float(padding) <= 0.0:
        return probability
    height, width = probability.shape[-2:]
    y = (torch.arange(height, device=probability.device, dtype=probability.dtype) + 0.5) / height
    x = (torch.arange(width, device=probability.device, dtype=probability.dtype) + 0.5) / width
    inside = (
        (y[None, None, :, None] >= boxes[..., 1, None, None] - padding)
        & (y[None, None, :, None] <= boxes[..., 3, None, None] + padding)
    )
    if not vertical_only:
        inside = (
            inside
            & (x[None, None, None, :] >= boxes[..., 0, None, None] - padding)
            & (x[None, None, None, :] <= boxes[..., 2, None, None] + padding)
        )
    text = families == QUERY_FAMILIES.index("text_line")
    gate = torch.where(text[..., None, None], inside, torch.ones_like(inside))
    return probability * gate.to(probability.dtype)


@dataclass(frozen=True)
class ProposalQuery:
    id: str
    family: str
    roi_xyxy: tuple[float, float, float, float]
    soft_support: np.ndarray
    parameters: tuple[float, ...]
    covariance: tuple[float, ...]
    confidence: float
    relation_tokens: tuple[tuple[str, float], ...]
    topology_code: tuple[int, int]
    hard_negative_class: str | None
    provenance: tuple[str, ...]

    def validate(self) -> None:
        if self.family not in QUERY_FAMILIES[:-1]:
            raise ValueError("unknown ProposalNet query family")
        if self.soft_support.ndim != 2 or self.soft_support.flags.writeable:
            raise ValueError("query support must be an immutable 2D field")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("query confidence lies outside [0,1]")
        x1, y1, x2, y2 = self.roi_xyxy
        if not (0.0 <= x1 <= x2 <= 1.0 and 0.0 <= y1 <= y2 <= 1.0):
            raise ValueError("query ROI is not normalized")
        if len(self.parameters) != len(self.covariance):
            raise ValueError("query parameter/covariance dimensions differ")
        if any(value <= 0 or not math.isfinite(value) for value in self.covariance):
            raise ValueError("query covariance must be positive and finite")


def query_head_prior_score(
    query: ProposalQuery, support: np.ndarray, *,
    expected_relations: Iterable[str] = (),
    expected_relation_groups: Iterable[Iterable[str]] = (),
) -> tuple[float, tuple[str, ...]]:
    """Apply bounded parameter/topology/relation priors before typed fitting.

    The neural heads can move a proposal score by at most 0.08.  They never
    change support, construct final geometry, or bypass the downstream
    physical certificates and local court.
    """
    if "ProposalNet-query" not in query.provenance:
        return float(query.confidence), (
            "classical-query-no-neural-head-prior",
        )
    mask = np.asarray(support, bool)
    if mask.ndim != 2 or not np.any(mask):
        return float(query.confidence), ("query-head-prior:empty-support",)
    height, width = mask.shape
    ys, xs = np.nonzero(mask)
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    observed = np.asarray((
        (x1 + x2) / (2.0 * width), (y1 + y2) / (2.0 * height),
        (x2 - x1) / width, (y2 - y1) / height,
        len(xs) / (width * height),
        len(xs) / max(1.0, (x2 - x1) * (y2 - y1)),
    ), np.float64)
    parameter_delta = 0.0
    parameter_agreement = 0.5
    if len(query.parameters) >= len(observed):
        predicted = np.asarray(query.parameters[:len(observed)], np.float64)
        variance = np.asarray(query.covariance[:len(observed)], np.float64)
        standardized = np.abs(predicted - observed) / np.sqrt(
            np.maximum(variance, 1e-4)
        )
        parameter_agreement = float(np.exp(-np.mean(np.minimum(4.0, standardized))))
        parameter_delta = 0.04 * (parameter_agreement - 0.5)

    observed_topology = topology_signature(mask)
    component_error = abs(int(query.topology_code[0]) - observed_topology[0])
    hole_error = abs(int(query.topology_code[1]) - observed_topology[1])
    topology_error = component_error + hole_error
    topology_delta = 0.025 if topology_error == 0 else -min(
        0.035, 0.009 * topology_error,
    )

    relation_lookup = dict(query.relation_tokens)
    expected = tuple(expected_relations)
    groups = tuple(tuple(group) for group in expected_relation_groups)
    if any(not group for group in groups):
        raise ValueError("expected relation groups must be non-empty")
    if groups:
        # Within a group tokens are alternatives (repeat OR mirror); across
        # groups every semantic fact is required (same_group AND membership).
        relation_probability = min(
            max(float(relation_lookup.get(name, 0.0)) for name in group)
            for group in groups
        )
    elif expected:
        relation_probability = max(
            (float(relation_lookup.get(name, 0.0)) for name in expected),
            default=0.5,
        )
    else:
        relation_probability = 0.5
    relation_delta = 0.03 * (relation_probability - 0.5)
    total_delta = float(np.clip(
        parameter_delta + topology_delta + relation_delta, -0.08, 0.08,
    ))
    score = float(np.clip(query.confidence + total_delta, 0.0, 1.0))
    return score, (
        f"query-parameter-prior:{parameter_agreement:.4f}",
        f"query-topology-prior:{observed_topology[0]},{observed_topology[1]}:"
        f"predicted={query.topology_code[0]},{query.topology_code[1]}",
        f"query-relation-prior:{relation_probability:.4f}",
        f"query-head-score-delta:{total_delta:+.4f}",
        "proposal-only-head-prior;court-still-mandatory",
    )


class ProposalNet(nn.Module):
    def __init__(self, config: ProposalNetConfig | None = None) -> None:
        super().__init__()
        self.config = config or ProposalNetConfig()
        if self.config.mask_upsample not in (1, 2):
            raise ValueError("ProposalNet mask_upsample must be 1 or 2")
        if not 0.0 <= float(self.config.text_bbox_gate_padding) <= 0.25:
            raise ValueError("ProposalNet text bbox gate padding is invalid")
        hidden = self.config.hidden_dim
        self.backbone = nn.Sequential(
            nn.Conv2d(4, hidden // 4, 5, stride=2, padding=2), nn.GELU(),
            nn.Conv2d(hidden // 4, hidden // 2, 3, stride=2, padding=1), nn.GELU(),
            nn.Conv2d(hidden // 2, hidden, 3, padding=1), nn.GELU(),
        )
        decoder_layer = nn.TransformerDecoderLayer(
            d_model=hidden, nhead=self.config.attention_heads,
            dim_feedforward=hidden * 4, dropout=0.0,
            batch_first=True, norm_first=True,
        )
        self.decoder = nn.TransformerDecoder(
            decoder_layer, num_layers=self.config.decoder_layers,
        )
        self.query_embedding = nn.Embedding(self.config.query_count, hidden)
        self.family_head = nn.Linear(hidden, len(QUERY_FAMILIES))
        self.bbox_head = nn.Sequential(nn.Linear(hidden, hidden), nn.GELU(), nn.Linear(hidden, 4))
        self.parameter_head = nn.Linear(hidden, self.config.parameter_dim)
        self.covariance_head = nn.Linear(hidden, self.config.parameter_dim)
        self.confidence_head = nn.Linear(hidden, 1)
        self.relation_head = nn.Linear(hidden, self.config.relation_dim)
        self.topology_components_head = nn.Linear(hidden, 9)
        self.topology_holes_head = nn.Linear(hidden, 6)
        self.hard_negative_head = nn.Linear(hidden, len(HARD_NEGATIVE_TYPES) + 1)
        self.mask_projection = nn.Conv2d(hidden, hidden, 1)
        self.mask_lateral = (
            nn.Conv2d(hidden // 4, hidden, 1)
            if self.config.mask_upsample == 2 else None
        )
        # A transformer decoder cannot distinguish two equal-looking glyph
        # rows when its spatial feature map is presented as an unordered set.
        # The convolutional padding leak used by the original model is not a
        # valid coordinate system and was especially weak for multi-row logo
        # text.  Project x/y and their quadratic terms into the same feature
        # space used by decoder memory and dynamic query masks.  Keeping this
        # behind an explicit config bit preserves old checkpoint semantics.
        self.position_projection = (
            nn.Conv2d(4, hidden, 1)
            if self.config.spatial_positioning else None
        )
        if self.position_projection is not None:
            nn.init.normal_(self.position_projection.weight, mean=0.0, std=0.02)
            nn.init.zeros_(self.position_projection.bias)

    @staticmethod
    def _position_features(reference: torch.Tensor) -> torch.Tensor:
        """Return absolute 2-D polynomial coordinates on a feature lattice."""
        height, width = reference.shape[-2:]
        y = torch.linspace(
            -1.0, 1.0, height, dtype=reference.dtype,
            device=reference.device,
        )
        x = torch.linspace(
            -1.0, 1.0, width, dtype=reference.dtype,
            device=reference.device,
        )
        yy, xx = torch.meshgrid(y, x, indexing="ij")
        return torch.stack((xx, yy, xx.square(), yy.square()), dim=0).unsqueeze(0)

    def _position_embedding(self, reference: torch.Tensor) -> torch.Tensor:
        if self.position_projection is None:
            return torch.zeros_like(reference)
        return self.position_projection(self._position_features(reference))

    def forward(self, rgba: torch.Tensor) -> dict[str, torch.Tensor]:
        if rgba.ndim != 4 or rgba.shape[1] != 4:
            raise ValueError("ProposalNet input must be BCHW straight RGBA")
        # Keep decoder memory bounded at stride four, while optionally
        # recovering stride-two spatial evidence for thin text masks.  Direct
        # indexing preserves the historical backbone state-dict keys.
        low_resolution = self.backbone[1](self.backbone[0](rgba))
        feature = self.backbone[3](self.backbone[2](low_resolution))
        feature = self.backbone[5](self.backbone[4](feature))
        batch, hidden, height, width = feature.shape
        memory_feature = feature + self._position_embedding(feature)
        memory = memory_feature.flatten(2).transpose(1, 2)
        queries = self.query_embedding.weight.unsqueeze(0).expand(batch, -1, -1)
        decoded = self.decoder(queries, memory)
        raw_bbox = torch.sigmoid(self.bbox_head(decoded))
        low = torch.minimum(raw_bbox[..., :2], raw_bbox[..., 2:])
        high = torch.maximum(raw_bbox[..., :2], raw_bbox[..., 2:])
        mask_feature = self.mask_projection(feature)
        if self.mask_lateral is not None:
            mask_feature = F.interpolate(
                mask_feature, size=low_resolution.shape[-2:],
                mode="bilinear", align_corners=False,
            ) + self.mask_lateral(low_resolution)
        mask_feature = mask_feature + self._position_embedding(mask_feature)
        support_logits = torch.einsum("bqd,bdhw->bqhw", decoded, mask_feature) / math.sqrt(hidden)
        return {
            "family_logits": self.family_head(decoded),
            "bbox": torch.cat((low, high), dim=-1),
            "support_logits": support_logits,
            "parameters": self.parameter_head(decoded),
            "log_variance": torch.clamp(self.covariance_head(decoded), -8.0, 8.0),
            "confidence_logits": self.confidence_head(decoded).squeeze(-1),
            "relation_logits": self.relation_head(decoded),
            "components_logits": self.topology_components_head(decoded),
            "holes_logits": self.topology_holes_head(decoded),
            "hard_negative_logits": self.hard_negative_head(decoded),
            "text_bbox_gate_padding": torch.as_tensor(
                self.config.text_bbox_gate_padding,
                dtype=rgba.dtype, device=rgba.device,
            ),
            "text_bbox_gate_vertical_only": torch.as_tensor(
                self.config.text_bbox_gate_vertical_only,
                dtype=torch.bool, device=rgba.device,
            ),
        }

    @torch.no_grad()
    def infer(
        self, rgba: torch.Tensor, *, confidence_floor: float = 0.05,
        max_queries: int | None = None,
    ) -> tuple[tuple[ProposalQuery, ...], ...]:
        self.eval(); output = self(rgba)
        family_prob = output["family_logits"].softmax(-1)
        confidence = torch.sigmoid(output["confidence_logits"])
        support = torch.sigmoid(output["support_logits"])
        predicted_family = family_prob[..., :-1].argmax(-1)
        support = _gate_text_support_probability(
            support, output["bbox"], predicted_family,
            padding=self.config.text_bbox_gate_padding,
            vertical_only=self.config.text_bbox_gate_vertical_only,
        )
        covariance = torch.exp(output["log_variance"])
        relations = torch.sigmoid(output["relation_logits"])
        hard_negative = output["hard_negative_logits"].softmax(-1)
        batches = []
        limit = max_queries or self.config.query_count
        for batch in range(rgba.shape[0]):
            scores, families = family_prob[batch, :, :-1].max(-1)
            combined = scores * confidence[batch]
            order = torch.argsort(combined, descending=True)[:limit]
            rows = []
            for query_index in order.tolist():
                score = float(combined[query_index])
                if score < confidence_floor:
                    continue
                family_index = int(families[query_index])
                family = QUERY_FAMILIES[family_index]
                soft = support[batch, query_index].detach().cpu().numpy().astype(np.float32)
                soft.setflags(write=False)
                hard_index = int(torch.argmax(hard_negative[batch, query_index, :-1]))
                hard_class = (
                    HARD_NEGATIVE_TYPES[hard_index]
                    if family == "risk_hard_negative" else None
                )
                relation_rows = tuple(
                    (name, float(relations[batch, query_index, index]))
                    for index, name in enumerate(RELATION_TYPES)
                    if float(relations[batch, query_index, index]) >= 0.20
                )
                row = ProposalQuery(
                    # Query identity is image-local.  Including the batch
                    # offset made calibration and single-image production
                    # choose different deterministic tie breaks.
                    id=f"proposal-net-q{query_index}", family=family,
                    roi_xyxy=tuple(float(value) for value in output["bbox"][batch, query_index]),
                    soft_support=soft,
                    parameters=tuple(float(value) for value in output["parameters"][batch, query_index]),
                    covariance=tuple(float(value) for value in covariance[batch, query_index]),
                    confidence=score, relation_tokens=relation_rows,
                    topology_code=(
                        int(torch.argmax(output["components_logits"][batch, query_index])),
                        int(torch.argmax(output["holes_logits"][batch, query_index])),
                    ),
                    hard_negative_class=hard_class,
                    provenance=("ProposalNet-query", "must-pass-CMIR-certificates"),
                )
                row.validate(); rows.append(row)
            batches.append(tuple(rows))
        return tuple(batches)


def _dice_probability_loss(
    probability: torch.Tensor, target: torch.Tensor,
) -> torch.Tensor:
    numerator = 2.0 * torch.sum(probability * target, dim=(-2, -1)) + 1.0
    denominator = torch.sum(probability + target, dim=(-2, -1)) + 1.0
    return 1.0 - numerator / denominator


def _soft_iou_probability_loss(
    probability: torch.Tensor, target: torch.Tensor,
) -> torch.Tensor:
    """Optimize the same soft-IoU geometry used by matching and gates."""
    intersection = torch.sum(probability * target, dim=(-2, -1))
    union = torch.sum(
        probability + target - probability * target,
        dim=(-2, -1),
    )
    return 1.0 - (intersection + 1.0) / (union + 1.0)


def _support_leakage_ratio(
    probability: torch.Tensor, target: torch.Tensor,
) -> torch.Tensor:
    """Return false-positive soft mass normalized by true support area."""
    false_positive = torch.sum(
        probability * (1.0 - target), dim=(-2, -1),
    )
    target_area = torch.sum(target, dim=(-2, -1))
    return false_positive / torch.clamp(target_area, min=1.0)


def _dice_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return _dice_probability_loss(torch.sigmoid(logits), target)


def _same_family_instance_exclusivity_loss(
    logits: torch.Tensor, target: torch.Tensor, families: torch.Tensor,
) -> torch.Tensor:
    """Penalize one matched instance query for covering another instance.

    The penalty is family-local and only sees pixels exclusively owned by the
    other target.  Cross-family semantic overlap (TextLine inside GlyphGroup)
    and genuinely shared same-family pixels therefore remain legal.
    """
    probability = torch.sigmoid(logits)
    penalties = []
    for first in range(int(families.numel())):
        for second in range(first + 1, int(families.numel())):
            if int(families[first]) != int(families[second]):
                continue
            first_only = target[first] * (1.0 - target[second])
            second_only = target[second] * (1.0 - target[first])
            if bool(torch.any(second_only)):
                penalties.append(
                    torch.sum(probability[first] * second_only)
                    / torch.clamp(torch.sum(second_only), min=1.0)
                )
            if bool(torch.any(first_only)):
                penalties.append(
                    torch.sum(probability[second] * first_only)
                    / torch.clamp(torch.sum(first_only), min=1.0)
                )
    if not penalties:
        return logits.sum() * 0.0
    return torch.stack(penalties).mean()


def _global_recall_at_k_competitor(
    negative_scores: torch.Tensor, *, positive_count: int, k: int = 5,
) -> torch.Tensor | None:
    """Return the negative score every positive must beat for global Recall@K.

    ``positive_count`` true queries consume that many places in the shared
    top-K.  Therefore only ``K - positive_count`` negatives may rank above a
    positive.  The old loss always compared against the K-th negative, which
    only proves Recall@K for a scene containing exactly one positive query.
    With TextLine + GlyphGroup it could explicitly permit one of the two
    positives to land at rank K+1.

    When a scene contains more than K positives, perfect global Recall@K is
    impossible.  Comparing against the strongest negative still teaches the
    model not to waste the bounded capacity on false queries; the dataset
    capacity audit is responsible for exposing the unavoidable ceiling.
    """
    if negative_scores.numel() == 0 or int(positive_count) <= 0:
        return None
    competitor_rank = max(1, int(k) - int(positive_count) + 1)
    competitor_count = min(competitor_rank, int(negative_scores.numel()))
    return torch.topk(negative_scores, k=competitor_count).values[-1]


def proposal_net_loss(
    output: dict[str, torch.Tensor], targets: list[dict[str, torch.Tensor]],
) -> dict[str, torch.Tensor]:
    """Hungarian Recall@K objective with geometry/topology/calibration terms."""
    device = output["family_logits"].device
    batch, query_count, family_count = output["family_logits"].shape
    family_target = torch.full(
        (batch, query_count), family_count - 1, dtype=torch.long, device=device,
    )
    matched: list[tuple[int, torch.Tensor, torch.Tensor]] = []
    for batch_index, target in enumerate(targets):
        count = int(target["family"].numel())
        if count == 0:
            continue
        probability = output["family_logits"][batch_index].softmax(-1)
        class_cost = -probability[:, target["family"]]
        bbox_cost = torch.cdist(output["bbox"][batch_index], target["bbox"], p=1)
        prediction = torch.sigmoid(output["support_logits"][batch_index]).flatten(1)
        truth = target["support"].flatten(1)
        intersection = prediction @ truth.T
        union = prediction.sum(1, keepdim=True) + truth.sum(1).unsqueeze(0) - intersection
        support_cost = 1.0 - intersection / torch.clamp(union, min=1e-6)
        cost = class_cost + 1.5 * bbox_cost + 2.0 * support_cost
        query_ids, target_ids = linear_sum_assignment(cost.detach().cpu().numpy())
        query_tensor = torch.as_tensor(query_ids, device=device, dtype=torch.long)
        target_tensor = torch.as_tensor(target_ids, device=device, dtype=torch.long)
        family_target[batch_index, query_tensor] = target["family"][target_tensor]
        matched.append((batch_index, query_tensor, target_tensor))

    # As in DETR, unmatched slots are useful supervision but must not swamp
    # the sparse positive queries.  With an unweighted no-object class a
    # 32-query image carrying two macros gets 30 negative labels and the
    # easiest solution is a nearly all-background ProposalNet.
    family_weights = torch.ones(family_count, device=device)
    family_weights[QUERY_FAMILIES.index("text_line")] = 1.35
    family_weights[QUERY_FAMILIES.index("glyph_group")] = 1.35
    family_weights[QUERY_FAMILIES.index("layer_relation")] = 1.30
    family_weights[QUERY_FAMILIES.index("appearance_model")] = 1.50
    # Explicit degradation replay now supplies a risk target on roughly 87%
    # of both new supplement strata.  The former 1.65 class boost came from
    # the sparse legacy corpus and, after the data-factory change, made this
    # already-abundant/pass-gate family crowd the shared global top-5.  Keep
    # ordinary weight here; the independent hard-negative class loss and the
    # fixed risk Recall@5 gate remain fully active.
    family_weights[QUERY_FAMILIES.index("risk_hard_negative")] = 1.0
    family_weights[-1] = 0.10
    losses = {
        "family": F.cross_entropy(
            output["family_logits"].reshape(-1, family_count),
            family_target.reshape(-1), weight=family_weights,
        )
    }
    zero = output["family_logits"].sum() * 0.0
    bbox_losses = []; support_losses = []; instance_exclusivity_losses = []
    parameter_losses = []
    topology_losses = []; relation_losses = []; hard_negative_losses = []
    top5_rank_losses = []
    confidence_target = torch.zeros(
        (batch, query_count), dtype=output["confidence_logits"].dtype,
        device=device,
    )
    for batch_index, query_ids, target_ids in matched:
        target = targets[batch_index]
        confidence_target[batch_index, query_ids] = 1.0
        matched_families = target["family"][target_ids]
        positive_weights = torch.ones(
            len(query_ids), dtype=output["family_logits"].dtype,
            device=device,
        )
        positive_weights = torch.where(
            (matched_families == QUERY_FAMILIES.index("text_line"))
            | (matched_families == QUERY_FAMILIES.index("glyph_group")),
            positive_weights * 1.50, positive_weights,
        )
        small_shape = target.get("small_shape")
        if small_shape is not None:
            positive_weights = torch.where(
                small_shape[target_ids], positive_weights * 3.0,
                positive_weights,
            )
        # The runtime and honest promotion gate rank all families together by
        # foreground probability * objectness and retain five queries.  Train
        # the matched query to clear that same bounded global competition;
        # the former independent CE/BCE terms did not optimize Recall@5.
        probability = output["family_logits"][batch_index].softmax(-1)
        objectness = torch.sigmoid(output["confidence_logits"][batch_index])
        global_scores = probability[:, :-1].amax(dim=-1) * objectness
        negative_mask = torch.ones(
            query_count, dtype=torch.bool, device=device,
        )
        negative_mask[query_ids] = False
        negative_scores = global_scores[negative_mask]
        if negative_scores.numel():
            recall_competitor = _global_recall_at_k_competitor(
                negative_scores, positive_count=len(query_ids), k=5,
            )
            assert recall_competitor is not None
            positive_scores = (
                probability[query_ids, target["family"][target_ids]]
                * objectness[query_ids]
            )
            top5_rank_losses.append(
                torch.sum(positive_weights * F.softplus(
                    (recall_competitor.detach() + 0.05 - positive_scores) * 12.0
                )) / torch.clamp(positive_weights.sum(), min=1.0) / 12.0
            )
        bbox_error = torch.mean(torch.abs(
            output["bbox"][batch_index, query_ids] - target["bbox"][target_ids]
        ), dim=-1)
        bbox_losses.append(
            torch.sum(positive_weights * bbox_error)
            / torch.clamp(positive_weights.sum(), min=1.0)
        )
        support_logits = output["support_logits"][batch_index, query_ids]
        truth_support = target["support"][target_ids]
        positive_fraction = truth_support.mean(dim=(-2, -1))
        sparse_text = (
            (matched_families == QUERY_FAMILIES.index("text_line"))
            & (positive_fraction < 0.015)
        )
        support_weights = torch.where(
            sparse_text, positive_weights * 3.0, positive_weights,
        )
        support_probability = torch.sigmoid(support_logits)
        padding = float(output.get(
            "text_bbox_gate_padding",
            torch.zeros((), device=device),
        ).detach().cpu())
        if padding > 0.0:
            support_probability = _gate_text_support_probability(
                support_probability.unsqueeze(0),
                output["bbox"][batch_index, query_ids].unsqueeze(0),
                matched_families.unsqueeze(0), padding=padding,
                vertical_only=bool(output.get(
                    "text_bbox_gate_vertical_only",
                    torch.zeros((), device=device),
                ).detach().cpu()),
            ).squeeze(0)
        support_error = (
            _dice_probability_loss(support_probability, truth_support)
            + _soft_iou_probability_loss(support_probability, truth_support)
        )
        support_error = support_error + torch.where(
            sparse_text,
            0.25 * torch.clamp(
                _support_leakage_ratio(support_probability, truth_support),
                max=4.0,
            ),
            torch.zeros_like(support_error),
        )
        pixel_bce = F.binary_cross_entropy(
            torch.clamp(support_probability, 1e-6, 1.0 - 1e-6),
            truth_support, reduction="none",
        )
        positive_pixel_weight = torch.clamp(
            (1.0 - positive_fraction) / torch.clamp(
                positive_fraction, min=1e-4,
            ), min=1.0, max=128.0,
        )
        pixel_weights = (
            truth_support * positive_pixel_weight[:, None, None]
            + (1.0 - truth_support)
        )
        balanced_bce = torch.sum(
            pixel_bce * pixel_weights, dim=(-2, -1),
        ) / torch.clamp(
            torch.sum(pixel_weights, dim=(-2, -1)), min=1.0,
        )
        support_error = support_error + balanced_bce
        support_losses.append(
            torch.sum(support_weights * support_error)
            / torch.clamp(support_weights.sum(), min=1.0)
        )
        instance_exclusivity_losses.append(
            _same_family_instance_exclusivity_loss(
                support_logits, truth_support, matched_families,
            )
        )
        predicted = output["parameters"][batch_index, query_ids]
        log_variance = output["log_variance"][batch_index, query_ids]
        truth = target["parameters"][target_ids]
        mask_all = target.get(
            "parameter_mask", torch.ones_like(target["parameters"]),
        )
        mask = mask_all[target_ids]
        # log_variance is clamped to [-8, 8].  Shift the valid Gaussian NLL by
        # four so the diagnostic total cannot become negative and obscure the
        # Recall@K terms; this constant does not change its gradients.
        nll = 0.5 * (
            torch.square(predicted - truth) * torch.exp(-log_variance)
            + log_variance
        ) + 4.0
        parameter_losses.append(torch.sum(nll * mask) / torch.clamp(mask.sum(), min=1.0))
        topology_losses.append(
            F.cross_entropy(output["components_logits"][batch_index, query_ids],
                            target["topology"][target_ids, 0])
            + F.cross_entropy(output["holes_logits"][batch_index, query_ids],
                              target["topology"][target_ids, 1])
        )
        relation_logits = output["relation_logits"][batch_index, query_ids]
        relation_truth = target["relations"][target_ids]
        relation_mask_all = target.get(
            "relation_mask", torch.ones_like(target["relations"]),
        )
        relation_mask = relation_mask_all[target_ids]
        relation_bce = F.binary_cross_entropy_with_logits(
            relation_logits, relation_truth, reduction="none",
        )
        relation_losses.append(
            torch.sum(relation_bce * relation_mask)
            / torch.clamp(relation_mask.sum(), min=1.0)
        )
        hard_negative_target = target.get("hard_negative")
        if hard_negative_target is not None:
            hard_negative_losses.append(F.cross_entropy(
                output["hard_negative_logits"][batch_index, query_ids],
                hard_negative_target[target_ids],
            ))
    # Confidence is an objectness/calibration head, so unmatched queries must
    # explicitly learn confidence zero.  Previously only positives were
    # pulled toward one and arbitrary high-confidence false queries were free.
    calibration_loss = F.binary_cross_entropy_with_logits(
        output["confidence_logits"], confidence_target,
    )
    losses.update({
        "bbox": torch.stack(bbox_losses).mean() if bbox_losses else zero,
        "support_dice_iou": torch.stack(support_losses).mean() if support_losses else zero,
        "instance_exclusivity": (
            torch.stack(instance_exclusivity_losses).mean()
            if instance_exclusivity_losses else zero
        ),
        "parameter_nll": torch.stack(parameter_losses).mean() if parameter_losses else zero,
        "topology": torch.stack(topology_losses).mean() if topology_losses else zero,
        "relation_affinity": torch.stack(relation_losses).mean() if relation_losses else zero,
        "hard_negative": (
            torch.stack(hard_negative_losses).mean()
            if hard_negative_losses else zero
        ),
        "calibration": calibration_loss,
        "global_top5_rank": (
            torch.stack(top5_rank_losses).mean()
            if top5_rank_losses else zero
        ),
    })
    losses["total"] = (
        losses["family"] + 3.0 * losses["support_dice_iou"]
        + 1.0 * losses["instance_exclusivity"]
        + 1.5 * losses["bbox"] + 0.10 * losses["parameter_nll"]
        + 0.5 * losses["topology"] + 0.35 * losses["relation_affinity"]
        + 0.25 * losses["hard_negative"] + 0.25 * losses["calibration"]
        + 1.25 * losses["global_top5_rank"]
    )
    return losses


def reir_queries(reir: RasterEvidenceIR, *, max_queries: int = 128) -> tuple[ProposalQuery, ...]:
    """Expose classical REIR proposals through the exact same query contract."""
    mapping = {
        "text": "text_line", "shape": "whole_shape", "stroke": "stroke_network",
        "layer": "layer_relation", "symmetry": "symmetry_repeat_group",
        "gradient": "appearance_model", "component": "whole_shape",
        "topology": "whole_shape", "codec_detail": "risk_hard_negative",
    }
    rows = []
    for token in sorted(reir.proposal_tokens, key=lambda row: (-row.score, row.id)):
        family = mapping.get(token.family)
        if family is None:
            continue
        mask = decode_token_mask(token, (reir.height, reir.width))
        if mask is None:
            mask = np.zeros((reir.height, reir.width), np.float32)
            x1, y1, x2, y2 = token.bbox_xyxy
            mask[y1:y2, x1:x2] = 0.35
        soft = cv2.resize(
            mask.astype(np.float32), (max(1, reir.width // 4), max(1, reir.height // 4)),
            interpolation=cv2.INTER_AREA,
        )
        soft = np.ascontiguousarray(np.clip(soft, 0, 1), np.float32); soft.setflags(write=False)
        x1, y1, x2, y2 = token.bbox_xyxy
        numeric = tuple(float(value) for _name, value in token.parameters
                        if isinstance(value, (float, int)))
        parameters = numeric[:24] + (0.0,) * max(0, 24 - len(numeric))
        covariance = tuple(max(1e-4, token.uncertainty ** 2 + 1e-3) for _ in parameters)
        query = ProposalQuery(
            id=f"reir-query-{token.id}", family=family,
            roi_xyxy=(x1 / reir.width, y1 / reir.height,
                      x2 / reir.width, y2 / reir.height),
            soft_support=soft, parameters=parameters, covariance=covariance,
            confidence=float(token.score), relation_tokens=(),
            topology_code=(0, 0),
            hard_negative_class=("preserve_jpeg_halo" if token.family == "codec_detail" else None),
            provenance=(token.provenance, "classical-geometry-query", "ProposalNet-union"),
        )
        query.validate(); rows.append(query)
        if len(rows) >= max_queries:
            break
    return tuple(rows)


def union_queries(
    *sets: Iterable[ProposalQuery], max_per_family: int = 64,
) -> tuple[ProposalQuery, ...]:
    grouped = {family: [] for family in QUERY_FAMILIES[:-1]}
    for rows in sets:
        for row in rows:
            row.validate(); grouped[row.family].append(row)
    result = []
    for family, rows in grouped.items():
        rows.sort(key=lambda row: (-row.confidence, row.id))
        result.extend(rows[:max_per_family])
    return tuple(result)


def query_support_mask(
    reir: RasterEvidenceIR, query: ProposalQuery, *, minimum_pixels: int = 4,
) -> np.ndarray | None:
    """Materialise a bounded ProposalNet support on the immutable REIR lattice.

    ProposalNet predicts its mask on the backbone grid and its ROI in normalised
    canvas coordinates.  Production generators must consume that evidence
    *before* fitting, rather than merely recording the query after extraction.
    The adaptive threshold is deterministic and deliberately conservative: a
    low-confidence diffuse query cannot turn its whole bounding box into ink.
    """
    query.validate()
    soft = cv2.resize(
        np.asarray(query.soft_support, np.float32),
        (reir.width, reir.height), interpolation=cv2.INTER_LINEAR,
    )
    x1n, y1n, x2n, y2n = query.roi_xyxy
    x1 = max(0, min(reir.width - 1, int(math.floor(x1n * reir.width))))
    y1 = max(0, min(reir.height - 1, int(math.floor(y1n * reir.height))))
    x2 = max(x1 + 1, min(reir.width, int(math.ceil(x2n * reir.width))))
    y2 = max(y1 + 1, min(reir.height, int(math.ceil(y2n * reir.height))))
    local = soft[y1:y2, x1:x2]
    if not local.size or not np.any(np.isfinite(local)):
        return None
    finite = local[np.isfinite(local)]
    # Confidence controls how much support is allowed, not whether the query is
    # trusted.  The later certificate court remains the admission authority.
    quantile = float(np.clip(0.82 - 0.24 * query.confidence, 0.55, 0.80))
    threshold = max(0.35, float(np.quantile(finite, quantile)))
    mask = np.zeros((reir.height, reir.width), dtype=bool)
    mask[y1:y2, x1:x2] = local >= threshold
    if int(mask.sum()) < max(1, int(minimum_pixels)):
        return None
    mask = np.ascontiguousarray(mask, dtype=bool)
    mask.setflags(write=False)
    return mask

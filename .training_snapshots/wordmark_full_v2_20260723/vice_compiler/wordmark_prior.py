"""Whole-line font-free wordmark prior.

Unlike the per-glyph prior, this model never assumes that character cells are
disconnected.  It predicts one clean rectangular line support together with
global component/counter topology, while OCR text is a conditioning hint rather
than a source of hard seams.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


PROJECT = Path(__file__).resolve().parents[1]
WORDMARK_CHARACTERS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789&@.-_+ "
)
WORDMARK_VOCAB_SHA256 = hashlib.sha256(
    WORDMARK_CHARACTERS.encode("ascii")
).hexdigest()
PAD_TOKEN = 0
TOPOLOGY_REPAIR_MINIMUM_CONFIDENCE = 0.50


@dataclass(frozen=True)
class WordmarkPriorConfig:
    image_height: int = 64
    image_width: int = 256
    base_channels: int = 24
    text_embedding_dim: int = 64
    max_characters: int = 32
    topology_classes: int = 65

    def validate(self) -> None:
        if (
            self.image_height < 32 or self.image_width < 96
            or self.image_height % 8 or self.image_width % 8
        ):
            raise ValueError("wordmark canvas must be >=32x96 and divisible by 8")
        if self.base_channels < 8 or self.text_embedding_dim < 8:
            raise ValueError("wordmark prior is too small for its contract")
        if not 3 <= self.max_characters <= 64:
            raise ValueError("invalid wordmark text length")
        if self.topology_classes < 17:
            raise ValueError("wordmark topology heads need overflow capacity")


class _ConvBlock(nn.Module):
    def __init__(self, first: int, second: int) -> None:
        super().__init__()
        groups = max(1, min(8, second // 4))
        while second % groups:
            groups -= 1
        self.net = nn.Sequential(
            nn.Conv2d(first, second, 3, padding=1, bias=False),
            nn.GroupNorm(groups, second), nn.SiLU(),
            nn.Conv2d(second, second, 3, padding=1, bias=False),
            nn.GroupNorm(groups, second), nn.SiLU(),
        )
        self.skip = nn.Conv2d(first, second, 1) if first != second else nn.Identity()

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.net(values) + self.skip(values)


class WordmarkPriorNet(nn.Module):
    """Small OCR-conditioned rectangular U-Net with global topology heads."""

    def __init__(self, config: WordmarkPriorConfig | None = None) -> None:
        super().__init__()
        self.config = config or WordmarkPriorConfig()
        self.config.validate()
        c = self.config.base_channels
        e = self.config.text_embedding_dim
        self.character_embedding = nn.Embedding(
            len(WORDMARK_CHARACTERS) + 1, e, padding_idx=PAD_TOKEN,
        )
        self.position_embedding = nn.Embedding(self.config.max_characters, e)
        self.text_encoder = nn.GRU(
            e, 4 * c, batch_first=True, bidirectional=True,
        )
        self.text_projection = nn.Sequential(
            nn.Linear(8 * c, 8 * c), nn.SiLU(), nn.Linear(8 * c, 8 * c),
        )
        self.encoder1 = _ConvBlock(3, c)
        self.encoder2 = _ConvBlock(c, 2 * c)
        self.encoder3 = _ConvBlock(2 * c, 4 * c)
        self.bottleneck = _ConvBlock(4 * c, 8 * c)
        self.decoder3 = _ConvBlock(8 * c + 4 * c, 4 * c)
        self.decoder2 = _ConvBlock(4 * c + 2 * c, 2 * c)
        self.decoder1 = _ConvBlock(2 * c + c, c)
        self.support_head = nn.Conv2d(c, 1, 1)
        self.sdf_head = nn.Conv2d(c, 1, 1)
        self.topology_pool = nn.AdaptiveAvgPool2d(1)
        self.topology_max_pool = nn.AdaptiveMaxPool2d(1)
        # Fine-scale dots/counters disappear when topology is inferred only
        # from the averaged bottleneck.  Pool mean+max statistics at every U-Net
        # scale and concatenate the ordered text encoding as an independent hint.
        self.topology_projection = nn.Sequential(
            nn.Linear(38 * c, 12 * c), nn.SiLU(),
            nn.Linear(12 * c, 12 * c), nn.SiLU(),
        )
        self.component_head = nn.Linear(12 * c, self.config.topology_classes)
        self.hole_head = nn.Linear(12 * c, self.config.topology_classes)

    def forward(
        self, features: torch.Tensor, text_tokens: torch.Tensor,
        text_lengths: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        expected = (self.config.image_height, self.config.image_width)
        if features.ndim != 4 or features.shape[1] != 3:
            raise ValueError("wordmark features must be BCHW with three channels")
        if tuple(features.shape[-2:]) != expected:
            raise ValueError("wordmark feature canvas differs from checkpoint")
        if text_tokens.ndim != 2 or text_tokens.shape[0] != features.shape[0]:
            raise ValueError("wordmark text tokens are not batch aligned")
        if text_tokens.shape[1] != self.config.max_characters:
            raise ValueError("wordmark token width differs from checkpoint")
        if (
            text_lengths.ndim != 1
            or text_lengths.shape[0] != features.shape[0]
            or torch.any(text_lengths < 1)
            or torch.any(text_lengths > self.config.max_characters)
        ):
            raise ValueError("wordmark text lengths are invalid")
        encoded_text = self.encode_text(text_tokens, text_lengths)

        first = self.encoder1(features)
        second = self.encoder2(F.avg_pool2d(first, 2))
        third = self.encoder3(F.avg_pool2d(second, 2))
        bottleneck = self.bottleneck(F.avg_pool2d(third, 2))
        conditioning = self.text_projection(encoded_text)[..., None, None]
        bottleneck = bottleneck + conditioning
        decoded3 = self.decoder3(torch.cat((
            F.interpolate(bottleneck, size=third.shape[-2:], mode="bilinear", align_corners=False),
            third,
        ), dim=1))
        decoded2 = self.decoder2(torch.cat((
            F.interpolate(decoded3, size=second.shape[-2:], mode="bilinear", align_corners=False),
            second,
        ), dim=1))
        decoded1 = self.decoder1(torch.cat((
            F.interpolate(decoded2, size=first.shape[-2:], mode="bilinear", align_corners=False),
            first,
        ), dim=1))
        pooled_visual = torch.cat(tuple(
            pooled.flatten(1)
            for values in (first, second, third, bottleneck)
            for pooled in (
                self.topology_pool(values), self.topology_max_pool(values),
            )
        ), dim=1)
        global_features = self.topology_projection(torch.cat((
            pooled_visual, encoded_text,
        ), dim=1))
        return {
            "support_logits": self.support_head(decoded1),
            "sdf": torch.tanh(self.sdf_head(decoded1)),
            "component_logits": self.component_head(global_features),
            "hole_logits": self.hole_head(global_features),
        }

    def encode_text(
        self, text_tokens: torch.Tensor, text_lengths: torch.Tensor,
    ) -> torch.Tensor:
        """Encode the ordered OCR sequence; anagrams must remain distinct."""
        positions = torch.arange(
            text_tokens.shape[1], device=text_tokens.device,
        )[None, :]
        embedded = (
            self.character_embedding(text_tokens)
            + self.position_embedding(positions)
        )
        packed = nn.utils.rnn.pack_padded_sequence(
            embedded, text_lengths.detach().cpu(), batch_first=True,
            enforce_sorted=False,
        )
        _sequence, hidden = self.text_encoder(packed)
        return torch.cat((hidden[-2], hidden[-1]), dim=1)


def wordmark_token_ids(
    text: str, *, max_characters: int,
) -> tuple[np.ndarray, int] | None:
    # OCR whitespace is semantically ordered geometry for multi-word logos.
    # Collapse arbitrary runs/tabs to one stable ASCII-space token, but never
    # alias `ACME LAB` with `ACMELAB` as the earlier whitespace-dropping code
    # did.
    visible = tuple(" ".join(str(text).split()))
    if not 3 <= len(visible) <= max_characters:
        return None
    identifiers = np.zeros(max_characters, np.int64)
    for index, character in enumerate(visible):
        try:
            identifiers[index] = WORDMARK_CHARACTERS.index(character) + 1
        except ValueError:
            return None
    return identifiers, len(visible)


def topology_signature(mask: np.ndarray) -> tuple[int, int]:
    support = np.asarray(mask, bool)
    components = int(cv2.connectedComponents(support.astype(np.uint8), 8)[0] - 1)
    contours, hierarchy = cv2.findContours(
        support.astype(np.uint8), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE,
    )
    holes = 0
    if hierarchy is not None:
        for index in range(len(contours)):
            depth = 0
            parent = int(hierarchy[0, index, 3])
            while parent >= 0:
                depth += 1
                parent = int(hierarchy[0, parent, 3])
            holes += int(depth % 2 == 1)
    return components, holes


def _topology_distance(
    first: tuple[int, int], second: tuple[int, int],
) -> int:
    return abs(first[0] - second[0]) + abs(first[1] - second[1])


def _hole_labels(mask: np.ndarray) -> list[tuple[int, float, int]]:
    inverse = (~np.asarray(mask, bool)).astype(np.uint8)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(inverse, 8)
    border = set(np.unique(np.concatenate((
        labels[0], labels[-1], labels[:, 0], labels[:, -1],
    ))).tolist())
    return [
        (int(stats[label, cv2.CC_STAT_AREA]), float(label), label)
        for label in range(1, count) if label not in border
    ]


def _repair_extra_hole(
    mask: np.ndarray, probability: np.ndarray,
) -> tuple[np.ndarray, int] | None:
    inverse = (~np.asarray(mask, bool)).astype(np.uint8)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(inverse, 8)
    border = set(np.unique(np.concatenate((
        labels[0], labels[-1], labels[:, 0], labels[:, -1],
    ))).tolist())
    rows = []
    for label in range(1, count):
        if label in border:
            continue
        region = labels == label
        area = int(stats[label, cv2.CC_STAT_AREA])
        cost = float(np.sum(1.0 - probability[region]))
        rows.append((cost, area, label, region))
    for _cost, area, _label, region in sorted(rows, key=lambda row: row[:3]):
        trial = np.asarray(mask, bool).copy()
        trial[region] = True
        before = topology_signature(mask)
        after = topology_signature(trial)
        if after[0] == before[0] and after[1] == before[1] - 1:
            return trial, area
    return None


def _repair_missing_hole(
    mask: np.ndarray, probability: np.ndarray,
) -> tuple[np.ndarray, int] | None:
    support = np.asarray(mask, bool)
    distance = cv2.distanceTransform(support.astype(np.uint8), cv2.DIST_L2, 5)
    ys, xs = np.nonzero(distance >= 1.0)
    ranked = sorted(
        zip(ys.tolist(), xs.tolist()),
        key=lambda point: (
            float(probability[point]), -float(distance[point]), point,
        ),
    )[:384]
    before = topology_signature(support)
    for y, x in ranked:
        maximum_radius = max(0, min(4, int(distance[y, x]) - 1))
        # Radius zero is a real one-pixel counter at the 64 px contract scale.
        # Without it, eight legitimate micro-counters necessarily consume at
        # least 40 edits and can exhaust the 3% support budget despite a nearly
        # perfect probability field.
        for radius in range(0, maximum_radius + 1):
            removed = np.zeros(support.shape, np.uint8)
            cv2.circle(removed, (x, y), radius, 1, -1)
            region = (removed > 0) & support
            if not np.any(region):
                continue
            trial = support.copy()
            trial[region] = False
            after = topology_signature(trial)
            if after[0] == before[0] and after[1] == before[1] + 1:
                return trial, int(np.sum(region))
    return None


def _repair_extra_component(
    mask: np.ndarray, probability: np.ndarray,
) -> tuple[np.ndarray, int] | None:
    support = np.asarray(mask, bool)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        support.astype(np.uint8), 8,
    )
    before = topology_signature(support)
    # Compare exact removals with exact bridges by probability cost.  Blindly
    # taking the first valid removal can delete a full letter and then exhaust
    # the bounded edit budget even when a one-pixel bridge is available.
    removal_rows = []
    for label in range(1, count):
        region = labels == label
        area = int(stats[label, cv2.CC_STAT_AREA])
        removal_rows.append((
            float(np.sum(probability[region])), area, label, region,
        ))
    exact_removals = []
    for cost, area, label, region in removal_rows:
        trial = support.copy()
        trial[region] = False
        after = topology_signature(trial)
        if after[0] == before[0] - 1 and after[1] == before[1]:
            exact_removals.append((cost, area, 0, label, trial))

    # Otherwise join the nearest likely pair with the minimum-probability-cost
    # one-pixel bridge.  Centroid distance is only a shortlist; endpoints are
    # chosen from actual component pixels.
    pair_rows = []
    for first in range(1, count):
        for second in range(first + 1, count):
            distance = float(np.linalg.norm(centroids[first] - centroids[second]))
            pair_rows.append((distance, first, second))
    bridge_rows = []
    for _distance, first, second in sorted(pair_rows)[:32]:
        first_points = np.argwhere(labels == first)
        second_points = np.argwhere(labels == second)
        if not len(first_points) or not len(second_points):
            continue
        # Bound the Cartesian comparison while retaining the component boundary.
        first_points = first_points[::max(1, len(first_points) // 256)]
        second_points = second_points[::max(1, len(second_points) // 256)]
        delta = first_points[:, None, :] - second_points[None, :, :]
        distances = np.sum(delta * delta, axis=2)
        first_index, second_index = np.unravel_index(
            int(np.argmin(distances)), distances.shape,
        )
        fy, fx = first_points[first_index]
        sy, sx = second_points[second_index]
        line = np.zeros(support.shape, np.uint8)
        cv2.line(line, (int(fx), int(fy)), (int(sx), int(sy)), 1, 1)
        region = (line > 0) & ~support
        trial = support | (line > 0)
        after = topology_signature(trial)
        if after[0] == before[0] - 1 and after[1] == before[1]:
            bridge_rows.append((
                float(np.sum(1.0 - probability[region])), int(np.sum(region)),
                1, first * count + second, trial,
            ))
    candidates = exact_removals + bridge_rows
    if not candidates:
        return None
    winner = min(candidates, key=lambda row: row[:4])
    return winner[4], winner[1]


def _repair_missing_component(
    mask: np.ndarray, probability: np.ndarray,
) -> tuple[np.ndarray, int] | None:
    support = np.asarray(mask, bool)
    before = topology_signature(support)
    # First recover a confident sub-threshold island (for example an i/j dot)
    # without lowering the threshold for the entire line.  Regions must remain
    # separated from the current support and fit the same bounded edit policy.
    local_budget = max(16, int(round(0.03 * max(1, np.sum(support)))))
    neighbourhood = cv2.dilate(
        support.astype(np.uint8), np.ones((3, 3), np.uint8),
    ) > 0
    for threshold in np.linspace(0.85, 0.10, 16):
        candidate = (probability >= threshold) & ~neighbourhood
        count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            candidate.astype(np.uint8), 8,
        )
        regions = []
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area > local_budget:
                continue
            region = labels == label
            regions.append((
                float(np.mean(1.0 - probability[region])),
                -float(np.max(probability[region])), area, label, region,
            ))
        for _cost, _peak, area, _label, region in sorted(
            regions, key=lambda row: row[:4],
        ):
            trial = support | region
            after = topology_signature(trial)
            if after[0] == before[0] + 1 and after[1] == before[1]:
                return trial, area

    # Otherwise the observation most likely merged two components.  Cutting a
    # low-confidence articulation pixel is the minimum exact topology change.
    ys, xs = np.nonzero(support)
    candidates = sorted(
        zip(ys.tolist(), xs.tolist()),
        key=lambda point: (float(probability[point]), point),
    )[:512]
    for y, x in candidates:
        trial = support.copy()
        trial[y, x] = False
        after = topology_signature(trial)
        if after[0] == before[0] + 1 and after[1] == before[1]:
            return trial, 1
    return None


def _repair_wordmark_topology(
    mask: np.ndarray, probability: np.ndarray,
    expected: tuple[int, int], *, maximum_edits: int,
) -> tuple[np.ndarray, bool]:
    result = np.asarray(mask, bool).copy()
    edits = 0
    for _ in range(128):
        observed = topology_signature(result)
        if observed == expected:
            return result, True
        operation = (
            _repair_extra_hole if observed[1] > expected[1] else
            _repair_missing_hole if observed[1] < expected[1] else
            _repair_extra_component if observed[0] > expected[0] else
            _repair_missing_component
        )
        repaired = operation(result, probability)
        if repaired is None:
            return result, False
        trial, changed = repaired
        if _topology_distance(topology_signature(trial), expected) >= (
            _topology_distance(observed, expected)
        ):
            return result, False
        edits += int(changed)
        if edits > maximum_edits:
            return result, False
        result = trial
    return result, topology_signature(result) == expected


def decode_wordmark_support(
    probability: np.ndarray, *, expected_topology: tuple[int, int],
    preferred_threshold: float = 0.5, allow_repair: bool = True,
    maximum_topology_repair_distance: int = 16,
) -> tuple[np.ndarray, float, bool]:
    """Decode a level set, with bounded topology repair only as a fallback."""
    field = np.asarray(probability, np.float32)
    if not allow_repair:
        support = field >= preferred_threshold
        return (
            support, float(preferred_threshold),
            topology_signature(support) == expected_topology,
        )
    thresholds = tuple(sorted({
        float(preferred_threshold),
        *(round(0.20 + 0.025 * index, 3) for index in range(29)),
    }))
    rows: list[tuple[float, float, float, np.ndarray]] = []
    candidates = []
    for threshold in thresholds:
        support = field >= threshold
        signature = topology_signature(support)
        certainty = float(np.mean(np.abs(field - support.astype(np.float32))))
        if signature == expected_topology:
            rows.append((
                abs(threshold - preferred_threshold), certainty,
                threshold, support,
            ))
        candidates.append((
            _topology_distance(signature, expected_topology),
            abs(threshold - preferred_threshold), certainty,
            threshold, support,
        ))
    if not rows:
        _distance, _offset, _certainty, threshold, support = min(
            candidates, key=lambda row: row[:3],
        )
        if _distance > maximum_topology_repair_distance:
            return np.asarray(support, bool), float(threshold), False
        budget = max(16, int(round(0.03 * max(1, np.sum(support)))))
        repaired, matched = _repair_wordmark_topology(
            support, field, expected_topology, maximum_edits=budget,
        )
        return repaired, float(threshold), matched
    _distance, _certainty, threshold, support = min(rows, key=lambda row: row[:2])
    return np.asarray(support, bool), float(threshold), True


def wordmark_prior_source_sha256() -> str:
    digest = hashlib.sha256(b"pcdc-wordmark-prior-source/v1\0")
    for name in ("wordmark_prior.py", "wordmark_prior_data.py"):
        path = Path(__file__).with_name(name)
        digest.update(name.encode("ascii"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def checkpoint_payload(
    model: WordmarkPriorNet, *, epoch: int, font_manifest_sha256: str,
    family_split_sha256: str, support_threshold: float,
    selection_key: tuple[float, ...],
) -> dict[str, Any]:
    return {
        "schema": "pcdc-wordmark-prior-checkpoint/v1",
        "config": asdict(model.config),
        # state_dict() tensors alias live parameter storage.  Clone an immutable
        # CPU snapshot so later epochs cannot silently overwrite the selected
        # early-stopping checkpoint while retaining its older epoch metadata.
        "state_dict": {
            name: value.detach().cpu().clone()
            for name, value in model.state_dict().items()
        },
        "epoch": int(epoch),
        "font_manifest_sha256": str(font_manifest_sha256),
        "family_split_sha256": str(family_split_sha256),
        "model_data_contract_sha256": wordmark_prior_source_sha256(),
        "vocabulary_sha256": WORDMARK_VOCAB_SHA256,
        "support_threshold": float(support_threshold),
        "selection_key": [float(value) for value in selection_key],
    }


def checkpoint_metadata(payload: dict[str, Any]) -> str:
    serializable = {key: value for key, value in payload.items() if key != "state_dict"}
    return json.dumps(serializable, sort_keys=True, separators=(",", ":"))

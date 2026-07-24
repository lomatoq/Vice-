"""Program-level hard-negative factory and pairwise candidate ranker."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .macro_ir import MacroCandidate, SceneProgram
from .macro_registry import encode_mask_rle
from .proposal_net import HARD_NEGATIVE_TYPES
from .certificates import topology_signature


@dataclass(frozen=True)
class HardNegativeProgram:
    id: str
    negative_type: str
    source_macro_id: str
    program: SceneProgram
    structural_delta: tuple[tuple[str, float | int | str], ...]
    expected_failure: str
    provenance: tuple[str, ...]
    support_size: tuple[int, int]
    rendered_support_rle: tuple[tuple[int, int], ...]
    render_sha256: str
    positive_features: tuple[float, ...]
    negative_features: tuple[float, ...]
    applicable: bool


def _negative_id(macro_id: str, negative_type: str) -> str:
    digest = hashlib.sha256(f"{macro_id}\0{negative_type}".encode("utf-8")).hexdigest()[:16]
    return f"hard-negative-{digest}"


def _scene_program_sha256(program: SceneProgram) -> str:
    payload = {
        "operator": program.operator,
        "parameters": list(program.parameters),
    }
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _decode_candidate_support(candidate: MacroCandidate) -> np.ndarray:
    width, height = candidate.certificates.support_size
    count = int(width) * int(height)
    if candidate.certificates.support_bits:
        return np.unpackbits(
            np.frombuffer(candidate.certificates.support_bits, np.uint8),
            count=count, bitorder="little",
        ).astype(bool).reshape((height, width))
    flat = np.zeros(count, bool)
    for start, length in candidate.certificates.support_rle:
        flat[int(start):int(start) + int(length)] = True
    return flat.reshape((height, width))


def _holes(mask: np.ndarray) -> list[np.ndarray]:
    inverse = (~np.asarray(mask, bool)).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(inverse, 8)
    rows = []
    height, width = mask.shape
    for label in range(1, count):
        x, y, w, h, area = (int(value) for value in stats[label])
        if area > 0 and x > 0 and y > 0 and x + w < width and y + h < height:
            rows.append(labels == label)
    return sorted(rows, key=lambda row: (-int(np.sum(row)), hashlib.sha256(row.tobytes()).hexdigest()))


def _largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        np.asarray(mask, np.uint8), 8,
    )
    if count <= 1:
        return np.zeros_like(mask, bool)
    label = max(
        range(1, count), key=lambda value: (
            int(stats[value, cv2.CC_STAT_AREA]), -value,
        ),
    )
    return labels == label


def _boundary_f(first: np.ndarray, second: np.ndarray) -> float:
    kernel = np.ones((3, 3), np.uint8)
    first_edge = cv2.morphologyEx(first.astype(np.uint8), cv2.MORPH_GRADIENT, kernel) > 0
    second_edge = cv2.morphologyEx(second.astype(np.uint8), cv2.MORPH_GRADIENT, kernel) > 0
    if not np.any(first_edge) or not np.any(second_edge):
        return float(not np.any(first_edge) and not np.any(second_edge))
    to_first = cv2.distanceTransform((~first_edge).astype(np.uint8), cv2.DIST_L2, 3)
    to_second = cv2.distanceTransform((~second_edge).astype(np.uint8), cv2.DIST_L2, 3)
    precision = float(np.mean(to_first[second_edge] <= 1.5))
    recall = float(np.mean(to_second[first_edge] <= 1.5))
    return 2.0 * precision * recall / max(1e-9, precision + recall)


def _canonical_render(mask: np.ndarray, negative_type: str | None = None) -> np.ndarray:
    support = np.asarray(mask, bool)
    render = np.ones(support.shape, np.float32)
    render[support] = 0.12
    if negative_type == "gradient_band_explosion" and np.any(support):
        bands = (np.indices(support.shape)[0] % 8) / 7.0
        render[support] = (0.08 + 0.72 * bands[support]).astype(np.float32)
    elif negative_type == "wrong_layer" and np.any(support):
        component = _largest_component(support)
        ys, xs = np.nonzero(component)
        if len(xs):
            x1, x2 = int(np.quantile(xs, 0.35)), int(np.quantile(xs, 0.65)) + 1
            y1, y2 = int(np.quantile(ys, 0.35)), int(np.quantile(ys, 0.65)) + 1
            render[y1:y2, x1:x2] = 0.72
    return render


def _mutated_support(mask: np.ndarray, negative_type: str) -> tuple[np.ndarray, bool]:
    source = np.asarray(mask, bool)
    output = source.copy()
    before_components, before_holes = topology_signature(source)
    if negative_type == "fill_counter":
        rows = _holes(source)
        if rows:
            output |= rows[0]
    elif negative_type == "split_glyph":
        component = _largest_component(source)
        ys, xs = np.nonzero(component)
        if len(xs):
            x = int(round(float(np.median(xs))))
            output[:, max(0, x - 1):min(output.shape[1], x + 1)] = False
    elif negative_type == "fuse_letters":
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(
            source.astype(np.uint8), 8,
        )
        if count > 2:
            pairs = []
            for first in range(1, count):
                for second in range(first + 1, count):
                    distance = float(np.linalg.norm(centroids[first] - centroids[second]))
                    pairs.append((distance, first, second))
            _distance, first, second = min(pairs)
            a = tuple(int(round(value)) for value in centroids[first])
            b = tuple(int(round(value)) for value in centroids[second])
            thickness = max(1, int(round(0.02 * max(source.shape))))
            bridge = np.zeros(source.shape, np.uint8)
            cv2.line(bridge, a, b, 1, thickness, cv2.LINE_8)
            output |= bridge > 0
    elif negative_type == "false_circle":
        component = _largest_component(source)
        ys, xs = np.nonzero(component)
        if len(xs):
            cx = 0.5 * (float(xs.min()) + float(xs.max()))
            cy = 0.5 * (float(ys.min()) + float(ys.max()))
            radius = 0.25 * ((xs.max() - xs.min() + 1) + (ys.max() - ys.min() + 1))
            yy, xx = np.indices(source.shape)
            circle = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2
            output = (source & ~component) | circle
    elif negative_type == "preserve_jpeg_halo":
        output |= cv2.dilate(source.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    elif negative_type == "remove_real_accent":
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            source.astype(np.uint8), 8,
        )
        if count > 2:
            label = min(
                range(1, count), key=lambda value: (
                    int(stats[value, cv2.CC_STAT_AREA]), value,
                ),
            )
            output[labels == label] = False
        else:
            component = _largest_component(source)
            ys, xs = np.nonzero(component)
            if len(xs):
                cutoff = int(np.quantile(ys, 0.12)) + 1
                accent = component & (np.indices(source.shape)[0] <= cutoff)
                output[accent] = False
    elif negative_type == "jagged_overfit":
        boundary = cv2.morphologyEx(
            source.astype(np.uint8), cv2.MORPH_GRADIENT,
            np.ones((3, 3), np.uint8),
        ) > 0
        checker = (np.indices(source.shape).sum(axis=0) % 2) == 0
        output ^= boundary & checker
    elif negative_type == "stroke_fill_confusion":
        rows = _holes(source)
        if rows:
            for row in rows:
                output |= row
        else:
            output = cv2.dilate(source.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0

    after_components, after_holes = topology_signature(output)
    applicable = {
        "fill_counter": after_holes < before_holes,
        "split_glyph": after_components > before_components,
        "fuse_letters": after_components < before_components,
        "false_circle": not np.array_equal(output, source),
        "wrong_layer": bool(np.any(source)),
        "preserve_jpeg_halo": int(np.sum(output)) > int(np.sum(source)),
        "remove_real_accent": int(np.sum(output)) < int(np.sum(source)),
        "jagged_overfit": not np.array_equal(output, source),
        "gradient_band_explosion": bool(np.any(source)),
        "stroke_fill_confusion": not np.array_equal(output, source),
    }[negative_type]
    output.setflags(write=False)
    return output, bool(applicable)


def _counterfactual_scene_program(
    candidate: MacroCandidate, negative_type: str, support: np.ndarray,
) -> SceneProgram:
    width, height = candidate.certificates.support_size
    if support.shape != (height, width):
        raise ValueError("candidate support shape disagrees with its certificate")
    encoded = json.dumps(
        list(encode_mask_rle(support)), separators=(",", ":"),
    )
    return SceneProgram("HardNegative/counterfactual-v1", (
        ("source_operator", candidate.program.operator),
        ("source_program_sha256", _scene_program_sha256(candidate.program)),
        ("negative_type", negative_type),
        ("support_width", int(width)),
        ("support_height", int(height)),
        ("source_support_rle", encoded),
    ))


def render_hard_negative_program(
    program: SceneProgram,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Render the canonical near-miss from the serialized scene program.

    This is deliberately the only render path used by the factory.  The
    persisted program, support attestation, features and render SHA therefore
    cannot describe different mutations.
    """
    if program.operator != "HardNegative/counterfactual-v1":
        raise ValueError("unsupported hard-negative program operator")
    parameters = dict(program.parameters)
    required = {
        "source_operator", "source_program_sha256", "negative_type",
        "support_width", "support_height", "source_support_rle",
    }
    if set(parameters) != required:
        raise ValueError("hard-negative program parameter contract mismatch")
    negative_type = str(parameters["negative_type"])
    if negative_type not in HARD_NEGATIVE_TYPES:
        raise ValueError("hard-negative program class is invalid")
    width = int(parameters["support_width"])
    height = int(parameters["support_height"])
    if width <= 0 or height <= 0:
        raise ValueError("hard-negative program support size is invalid")
    try:
        runs = json.loads(str(parameters["source_support_rle"]))
    except json.JSONDecodeError as error:
        raise ValueError("hard-negative support RLE is invalid JSON") from error
    flat = np.zeros(width * height, bool)
    previous_end = 0
    if not isinstance(runs, list):
        raise ValueError("hard-negative support RLE must be a list")
    for run in runs:
        if not isinstance(run, list) or len(run) != 2:
            raise ValueError("hard-negative support RLE run is malformed")
        start, length = (int(value) for value in run)
        end = start + length
        if start < previous_end or length <= 0 or end > flat.size:
            raise ValueError("hard-negative support RLE lies outside support")
        flat[start:end] = True
        previous_end = end
    source = flat.reshape((height, width))
    if not np.any(source):
        raise ValueError("hard-negative program has empty source support")
    mutated, applicable = _mutated_support(source, negative_type)
    render = _canonical_render(mutated, negative_type)
    mutated.setflags(write=False)
    render.setflags(write=False)
    return mutated, render, applicable


def counterfactual_feature_pairs(
    support: np.ndarray, *, allowed_types: frozenset[str] | None = None,
) -> dict[str, tuple[tuple[float, ...], tuple[float, ...], bool]]:
    """Exactly rasterize all ten near misses and return measured deltas."""
    reference = np.asarray(support, bool)
    if reference.ndim != 2 or not np.any(reference):
        raise ValueError("counterfactual support must be a non-empty 2D mask")
    reference_render = _canonical_render(reference)
    reference_topology = topology_signature(reference)
    positive = (0.0,) * 10 + (1.0,) * 6
    rows = {}
    for negative_type in HARD_NEGATIVE_TYPES:
        mutated, applicable = _mutated_support(reference, negative_type)
        negative_render = _canonical_render(mutated, negative_type)
        intersection = int(np.sum(reference & mutated))
        union = int(np.sum(reference | mutated))
        components, holes = topology_signature(mutated)
        area_delta = abs(int(np.sum(mutated)) - int(np.sum(reference))) / max(
            1, int(np.sum(reference)),
        )
        render_mae = float(np.mean(np.abs(reference_render - negative_render)))
        reference_gradient = cv2.Laplacian(reference_render, cv2.CV_32F)
        negative_gradient = cv2.Laplacian(negative_render, cv2.CV_32F)
        high_frequency_delta = abs(
            float(np.mean(np.abs(negative_gradient)))
            - float(np.mean(np.abs(reference_gradient)))
        )
        topology_changed = components != reference_topology[0] or holes != reference_topology[1]
        relation_valid = negative_type != "wrong_layer"
        appearance_valid = negative_type != "gradient_band_explosion"
        negative = (
            float(area_delta),
            float(abs(components - reference_topology[0]) / max(1, reference_topology[0])),
            float(abs(holes - reference_topology[1]) / max(1, reference_topology[1] + 1)),
            float(1.0 - intersection / max(1, union)),
            float(1.0 - _boundary_f(reference, mutated)),
            float(render_mae),
            float(high_frequency_delta),
            float(topology_changed),
            float(negative_type in {"preserve_jpeg_halo", "jagged_overfit"}),
            float(negative_type in {"false_circle", "stroke_fill_confusion"}),
            float(not topology_changed),
            float(intersection / max(1, union) >= 0.98),
            float(appearance_valid),
            float(max(0.0, 1.0 - min(1.0, area_delta))),
            float(relation_valid),
            float(not applicable),
        )
        semantically_allowed = (
            allowed_types is None or negative_type in allowed_types
        )
        rows[negative_type] = (
            positive, negative, bool(applicable and semantically_allowed),
        )
    return rows


def counterfactual_risk_regions(
    support: np.ndarray, *, allowed_types: frozenset[str] | None = None,
) -> dict[str, tuple[np.ndarray, bool]]:
    """Return the source-local region changed by each rendered near miss."""
    reference = np.asarray(support, bool)
    if reference.ndim != 2 or not np.any(reference):
        raise ValueError("counterfactual support must be a non-empty 2D mask")
    rows = {}
    for negative_type in HARD_NEGATIVE_TYPES:
        mutated, applicable = _mutated_support(reference, negative_type)
        region = reference ^ mutated
        if not np.any(region) and applicable:
            if negative_type == "wrong_layer":
                component = _largest_component(reference)
                ys, xs = np.nonzero(component)
                region = np.zeros_like(reference)
                if len(xs):
                    x1, x2 = int(np.quantile(xs, 0.35)), int(np.quantile(xs, 0.65)) + 1
                    y1, y2 = int(np.quantile(ys, 0.35)), int(np.quantile(ys, 0.65)) + 1
                    region[y1:y2, x1:x2] = reference[y1:y2, x1:x2]
            else:
                region = reference.copy()
        region = cv2.dilate(
            region.astype(np.uint8), np.ones((3, 3), np.uint8),
        ) > 0
        region.setflags(write=False)
        semantically_allowed = (
            allowed_types is None or negative_type in allowed_types
        )
        rows[negative_type] = (
            region,
            bool(applicable and semantically_allowed and np.any(region)),
        )
    return rows


def generate_hard_negatives(candidate: MacroCandidate) -> tuple[HardNegativeProgram, ...]:
    """Generate near-miss scene programs, never random isolated primitives."""
    rows = []
    support = _decode_candidate_support(candidate)
    allowed_types = applicable_hard_negative_types((candidate.family,))
    feature_pairs = counterfactual_feature_pairs(
        support, allowed_types=allowed_types,
    )
    for negative_type in HARD_NEGATIVE_TYPES:
        delta: tuple[tuple[str, float | int | str], ...]
        failure: str
        if negative_type == "fill_counter":
            delta = (("holes_delta", -1),); failure = "persistent counter removed"
        elif negative_type == "split_glyph":
            delta = (("components_delta", 1),); failure = "one glyph split"
        elif negative_type == "fuse_letters":
            delta = (("components_delta", -1),); failure = "adjacent glyphs fused"
        elif negative_type == "false_circle":
            delta = (("force_primitive", "circle"),); failure = "unsupported ideal circle"
        elif negative_type == "wrong_layer":
            delta = (("reverse_layer_order", 1),); failure = "front/back relation reversed"
        elif negative_type == "preserve_jpeg_halo":
            delta = (("keep_codec_residue", 1),); failure = "codec halo promoted to geometry"
        elif negative_type == "remove_real_accent":
            delta = (("remove_semantic_microdetail", 1),); failure = "real accent deleted"
        elif negative_type == "jagged_overfit":
            delta = (("extra_control_points", 16),); failure = "raster stair steps overfit"
        elif negative_type == "gradient_band_explosion":
            delta = (("gradient_bands", 32),); failure = "smooth appearance fragmented"
        else:
            delta = (("swap_stroke_fill", 1),); failure = "stroke/fill representation confused"
        program = _counterfactual_scene_program(
            candidate, negative_type, support,
        )
        rendered_support, render, raster_applicable = (
            render_hard_negative_program(program)
        )
        positive_features, negative_features, feature_applicable = (
            feature_pairs[negative_type]
        )
        rows.append(HardNegativeProgram(
            id=_negative_id(candidate.id, negative_type),
            negative_type=negative_type, source_macro_id=candidate.id,
            program=program,
            structural_delta=delta, expected_failure=failure,
            provenance=(
                "counterfactual-negative-factory", "program-level-near-miss",
                "exact-canonical-raster-attestation",
                "measured-structural-render-deltas",
            ),
            support_size=(support.shape[1], support.shape[0]),
            rendered_support_rle=encode_mask_rle(rendered_support),
            render_sha256=hashlib.sha256(render.tobytes()).hexdigest(),
            positive_features=positive_features,
            negative_features=negative_features,
            applicable=bool(
                raster_applicable
                and negative_type in allowed_types
                and feature_applicable
            ),
        ))
    return tuple(rows)


class CandidateRanker(nn.Module):
    """Ranks a GT/candidate program pair after hard physics features."""

    def __init__(self, feature_dim: int = 32, hidden_dim: int = 96) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim), nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim), nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features).squeeze(-1)


def pairwise_ranking_loss(
    ranker: CandidateRanker, positive_features: torch.Tensor,
    negative_features: torch.Tensor, *, margin: float = 0.35,
) -> torch.Tensor:
    positive = ranker(positive_features)
    negative = ranker(negative_features)
    return F.relu(margin - positive + negative).mean()
def applicable_hard_negative_types(
    families: tuple[str, ...] | list[str] | set[str], *,
    jpeg: bool = False, noisy: bool = False,
) -> frozenset[str]:
    """Return only counterfactual classes justified by scene semantics.

    A wrong-layer mutation on a plain icon, or gradient banding on flat text,
    is not a negative example of that class.  Keeping applicability separate
    from the raster mutation prevents the class head from learning invented
    semantics merely because a bitmap operation was possible.
    """
    normalized = {str(value).casefold().replace("-", "_") for value in families}
    text = any("text" in value or "glyph" in value for value in normalized)
    shape = any("shape" in value for value in normalized)
    layer = any("layer" in value for value in normalized)
    appearance = any(
        "appearance" in value or "gradient" in value for value in normalized
    )
    stroke = any("stroke" in value for value in normalized)
    allowed = set()
    if text:
        allowed.update((
            "fill_counter", "split_glyph", "fuse_letters",
            "remove_real_accent",
        ))
    if shape:
        allowed.update(("fill_counter", "false_circle", "remove_real_accent"))
    if layer:
        allowed.add("wrong_layer")
    if appearance:
        allowed.add("gradient_band_explosion")
    if stroke:
        allowed.add("stroke_fill_confusion")
    if normalized or noisy:
        allowed.add("jagged_overfit")
    if jpeg:
        allowed.add("preserve_jpeg_halo")
    return frozenset(allowed)

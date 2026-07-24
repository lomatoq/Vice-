"""Large, source-disjoint ProposalNet training on the existing SVG/raster corpus.

This is the production-scale replacement for the 300-locus Phase-9 pilot.  It
uses the already generated V-ize raster/vector pairs, keeps every augmentation
of one source SVG in exactly one split, and reports *neural-only* instance
Recall@K.  Classical REIR proposals are intentionally absent from the metric.

The network remains a proposal source.  A checkpoint passing this script's
gate still has no right to commit geometry without the normal local court.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import torch
from PIL import Image
from scipy.optimize import linear_sum_assignment
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from .build_identity import compiler_source_sha256, evaluation_source_sha256
from .certificates import topology_signature
from .conformal import (
    CalibrationExample,
    audit_conformal_coverage,
    calibrate_conformal_sets,
)
from .hard_negative_factory import (
    applicable_hard_negative_types,
    counterfactual_risk_regions,
)
from .proposal_data_contract import (
    RELATION_TYPES,
    TYPED_STRUCTURE_FAMILIES,
    relation_supervision,
    typed_macro_families,
    uses_explicit_owner_labels,
)
from .proposal_data_contract import (
    split_group as contract_split_group,
)
from .proposal_filter_cache import (
    corpus_data_contract_sha256 as _corpus_data_contract_sha256,
)
from .proposal_filter_cache import (
    validate_filter_cache,
)
from .proposal_instance_labels import (
    MINIMUM_SVG_ALIGNMENT_IOU, augmented_svg_full_support,
    augmented_svg_owner_targets,
    svg_full_template,
    svg_owner_templates,
)
from .proposal_mixed_corpus import validate_mixed_corpus
from .proposal_net import (
    HARD_NEGATIVE_TYPES,
    QUERY_FAMILIES,
    ProposalNet,
    ProposalNetConfig,
    _gate_text_support_probability,
    proposal_net_loss,
)
from .proposal_replay import expected_source_share, rebalance_source_shares

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_PAIR_ROOT = Path(
    r"C:\Users\nirrt\Toolset\v-ize train\dataset\raster_vector_pairs"
)
DEFAULT_CHECKPOINT = PROJECT / "models" / "proposal_net_large_candidate.pt"
DEFAULT_REPORT = PROJECT / "benchmarks" / "pcdc_proposal_large" / "report.json"
LABEL_CONTRACT_VERSION = "pcdc-explicit-owner-counterfactual-mixed-replay-labels/v4"
V14_REQUIRED_READINESS_GATES = (
    "full_regression_suite",
    "training_data_and_head_supervision",
    "experiment1_evidence_lattice",
    "experiment1b_dual_pricing",
    "experiment2_oracle_extraction",
    "experiment3_certificate_discrimination",
    "experiment4_textline",
    "glyph_prior_held_out_training",
    "experiment5_complexity_stress",
    "canonical_plan_traceability",
    "real_calibration_capacity",
    "runtime_conformal_harness_equivalence",
    "untouched_disjoint_holdout",
    "anti_forgetting_pilot",
    "cuda_reproducibility",
    "tiny_multi_instance_overfit",
    "licensed_font_bank_exactly_matches_runtime",
)
TINY_OVERFIT_REQUIRED_FAMILIES = (
    "text_line",
    "glyph_group",
    "whole_shape",
    "small_shape",
    "layer_relation",
    "stroke_network",
    "appearance_model",
    "symmetry_repeat_group",
    "risk_hard_negative",
)
_SHAPE_TAG = re.compile(r"<(path|rect|circle|ellipse|polygon|polyline|line)\b", re.I)
_GRADIENT = re.compile(r"<(linearGradient|radialGradient)\b|url\(#", re.I)
_STROKE = re.compile(r"\bstroke\s*=\s*['\"](?!none)[^'\"]+", re.I)
_PAINT_TAGS = frozenset({
    "path", "rect", "circle", "ellipse", "polygon", "polyline", "line",
})


def _label_contract_sha256() -> str:
    digest = hashlib.sha256(LABEL_CONTRACT_VERSION.encode("utf-8"))
    for path in (
        Path(__file__).resolve(),
        PROJECT / "vice_compiler" / "proposal_net.py",
        PROJECT / "vice_compiler" / "proposal_instance_labels.py",
        PROJECT / "vice_compiler" / "explicit_svg_owners.py",
        PROJECT / "vice_compiler" / "proposal_data_contract.py",
        PROJECT / "vice_compiler" / "proposal_replay.py",
        PROJECT / "vice_compiler" / "proposal_mixed_corpus.py",
        PROJECT / "vice_compiler" / "proposal_filter_cache.py",
        PROJECT / "vice_compiler" / "hard_negative_factory.py",
    ):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _validate_tiny_overfit_preflight(
    path: Path, *, config: ProposalNetConfig, checkpoint: Path | None,
    pair_root: Path, filter_cache: Path | None,
) -> dict:
    """Fail closed before a costly run if instance learning is not proved."""
    if checkpoint is None or filter_cache is None:
        raise RuntimeError(
            "large training requires checkpoint- and filter-bound tiny overfit preflight"
        )
    payload = json.loads(path.read_text("utf-8"))
    expected = {
        "schema": "pcdc-proposal-tiny-overfit-preflight/v1",
        "split": "train-only", "checkpoint_written": False,
        "passed": True,
        "evaluation_source_sha256": evaluation_source_sha256(
            "vice_compiler/preflight_proposal_overfit.py",
        ),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "filter_cache_sha256": hashlib.sha256(filter_cache.read_bytes()).hexdigest(),
        "label_contract_sha256": _label_contract_sha256(),
        "pair_root": str(pair_root.resolve()),
        "text_bbox_gate_padding": config.text_bbox_gate_padding,
        "text_bbox_gate_vertical_only": config.text_bbox_gate_vertical_only,
        "probe_model_config": asdict(config),
    }
    mismatches = {
        key: {"expected": value, "actual": payload.get(key)}
        for key, value in expected.items() if payload.get(key) != value
    }
    minimum = float(payload.get("minimum_text_line_recall_at_5", 0.0))
    best = float(payload.get("best_text_line_recall_at_5", 0.0))
    if minimum < 0.99 or best < minimum:
        mismatches["text_recall_gate"] = {
            "expected": ">=0.99 and best>=minimum",
            "actual": {"minimum": minimum, "best": best},
        }
    required_families = payload.get("required_overfit_families")
    if required_families != list(TINY_OVERFIT_REQUIRED_FAMILIES):
        mismatches["required_overfit_families"] = {
            "expected": list(TINY_OVERFIT_REQUIRED_FAMILIES),
            "actual": required_families,
        }
    minimum_instances = int(payload.get("minimum_family_instances", 0))
    family_counts = payload.get("family_instance_counts", {})
    if (
        minimum_instances < 16
        or not isinstance(family_counts, dict)
        or any(
            int(family_counts.get(family, 0)) < minimum_instances
            for family in TINY_OVERFIT_REQUIRED_FAMILIES
        )
    ):
        mismatches["family_instance_counts"] = {
            "expected": {
                family: ">= minimum_family_instances >= 16"
                for family in TINY_OVERFIT_REQUIRED_FAMILIES
            },
            "actual": {
                "minimum": minimum_instances, "counts": family_counts,
            },
        }
    minimum_family_recall = float(
        payload.get("minimum_family_recall_at_5", 0.0)
    )
    best_minimum_family_recall = float(
        payload.get("best_minimum_required_recall_at_5", 0.0)
    )
    best_joint_recalls = payload.get("best_recall_at_5_by_family", {})
    if (
        minimum_family_recall < 0.95
        or best_minimum_family_recall < minimum_family_recall
        or not isinstance(best_joint_recalls, dict)
        or any(
            float(best_joint_recalls.get(family, 0.0))
            < minimum_family_recall
            for family in TINY_OVERFIT_REQUIRED_FAMILIES
        )
        or float(best_joint_recalls.get("text_line", 0.0)) < minimum
        or float(payload.get("best_overall_recall_at_5", 0.0)) < 0.97
    ):
        mismatches["all_head_recall_gate"] = {
            "expected": {
                "minimum_family_recall_at_5": ">=0.95",
                "best_joint_family_recalls": ">=minimum",
                "best_joint_text_line": ">=minimum_text_line_recall_at_5",
                "best_overall_recall_at_5": ">=0.97",
            },
            "actual": {
                "minimum_family_recall_at_5": minimum_family_recall,
                "best_minimum_required_recall_at_5": (
                    best_minimum_family_recall
                ),
                "best_recall_at_5_by_family": best_joint_recalls,
                "best_overall_recall_at_5": payload.get(
                    "best_overall_recall_at_5",
                ),
            },
        }
    owner_counts = payload.get("owner_count_rows", {})
    if int(owner_counts.get("2", 0)) < 16 or int(owner_counts.get("3", 0)) < 16:
        mismatches["owner_count_rows"] = {
            "expected": {"2": ">=16", "3": ">=16"},
            "actual": owner_counts,
        }
    if mismatches:
        raise RuntimeError(
            "tiny-overfit preflight is missing, stale, or failed: "
            + json.dumps(mismatches, sort_keys=True)
        )
    return payload


def _validate_v14_readiness(
    path: Path, *, config: ProposalNetConfig, checkpoint: Path | None,
    pair_root: Path, filter_cache: Path | None,
    corpus_data_contract_sha256: str,
) -> dict:
    """Require one hash-bound all-gates verdict before any costly training."""
    if checkpoint is None or filter_cache is None:
        raise RuntimeError(
            "v14 readiness requires explicit initialization and filter cache"
        )
    payload = json.loads(path.read_text("utf-8"))
    expected = {
        "schema": "pcdc-v14-training-readiness/v1",
        "status": "TRAIN", "training_authorized": True,
        "compiler_source_sha256": compiler_source_sha256(),
        "evaluation_source_sha256": evaluation_source_sha256(
            "vice_compiler/pre_v14_readiness.py",
        ),
        "label_contract_version": LABEL_CONTRACT_VERSION,
        "label_contract_sha256": _label_contract_sha256(),
        "pair_root": str(pair_root.resolve()),
        "corpus_data_contract_sha256": corpus_data_contract_sha256,
        "filter_cache_sha256": hashlib.sha256(filter_cache.read_bytes()).hexdigest(),
        "initialization_checkpoint_sha256": hashlib.sha256(
            checkpoint.read_bytes()
        ).hexdigest(),
        "proposal_config": asdict(config),
    }
    mismatches = {
        key: {"expected": value, "actual": payload.get(key)}
        for key, value in expected.items() if payload.get(key) != value
    }
    required_gates = payload.get("required_gates")
    expected_gate_names = set(V14_REQUIRED_READINESS_GATES)
    if not isinstance(required_gates, dict):
        mismatches["required_gates"] = {
            "expected": {
                name: True for name in V14_REQUIRED_READINESS_GATES
            },
            "actual": required_gates,
        }
    elif (
        set(required_gates) != expected_gate_names
        or not all(required_gates.get(name) is True for name in expected_gate_names)
    ):
        mismatches["required_gates"] = {
            "expected": {
                name: True for name in V14_REQUIRED_READINESS_GATES
            },
            "actual": required_gates,
        }
    if mismatches:
        raise RuntimeError(
            "v14 readiness is missing, stale, or NO-TRAIN: "
            + json.dumps(mismatches, sort_keys=True)
        )
    return payload


def _stable_bucket(source_id: str) -> str:
    value = int(hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if value < 80 else "calibration" if value < 90 else "test"


def _split_group(row: dict) -> str:
    """Return the leakage boundary required by the canonical data contract."""
    return contract_split_group(row)


def _read_pairs(root: Path, limit: int | None) -> list[dict]:
    rows = []
    with (root / "pairs.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
                if limit is not None and len(rows) >= limit:
                    break
    return rows


@lru_cache(maxsize=4096)
def _read_svg_text(path: str) -> str:
    return Path(path).read_text("utf-8", errors="replace")


def _uses_svg_owner_labels(row: dict) -> bool:
    return (
        uses_explicit_owner_labels(row)
        or
        str(row.get("source", "")) == "local"
        or str(row.get("collection", "")) == "logos"
    )


def _svg_families(row: dict, root: Path) -> tuple[str, ...]:
    """Return only macro families with defensible scene-level support labels.

    Generic third-party vectors remain conservative because a path count is
    not a semantic owner label.  Curated local/logo assets additionally use
    the clean-SVG owner factory, which supplies separate text/glyph/mark masks
    later in ``PairDataset``.
    """
    source = str(row.get("source", ""))
    typed = typed_macro_families(row)
    if typed is not None:
        return typed
    if source == "synthetic-open-text":
        if not uses_explicit_owner_labels(row):
            raise ValueError("open-text source lost its explicit owner contract")
        return ("text_line", "glyph_group")
    if source == "synthetic-text":
        return ("text_line", "glyph_group")
    svg = _read_svg_text(str((root / row["target_svg"]).resolve()))
    families = ["whole_shape"]
    if _uses_svg_owner_labels(row):
        try:
            owner_templates = svg_owner_templates(svg)
        except (RuntimeError, ValueError, ET.ParseError):
            owner_templates = None
        if owner_templates is not None and owner_templates.text_masks:
            families.extend(("text_line", "glyph_group"))
            # A pure wordmark is not a generic whole-shape instance.  Mixed
            # mark+word assets retain one whole-shape target for the mark.
            if not owner_templates.mark_masks:
                families.remove("whole_shape")
    source_id = str(row.get("source_id", ""))
    xml_root: ET.Element | None = None
    try:
        xml_root = ET.fromstring(svg)
        painted = [
            element for element in xml_root.iter()
            if element.tag.rsplit("}", 1)[-1].lower() in _PAINT_TAGS
        ]
    except ET.ParseError:
        painted = []
    shape_count = len(painted) or len(_SHAPE_TAG.findall(svg))
    gradient_paints = [
        element for element in painted
        if "url(#" in (
            str(element.attrib.get("fill", ""))
            + str(element.attrib.get("stroke", ""))
            + str(element.attrib.get("style", ""))
        ).lower()
    ]
    stroke_only = [
        element for element in painted
        if str(element.attrib.get("stroke", "none")).lower() != "none"
        and str(element.attrib.get("fill", "black")).lower() == "none"
    ]
    opacity_layer = any(
        float(element.attrib.get("opacity", "1") or 1) < 0.999
        for element in painted
        if str(element.attrib.get("opacity", "1") or 1).replace(".", "", 1).isdigit()
    )
    explicit_layer = bool(re.search(
        r"<(?:mask|clipPath)\b|\b(?:mask|clip-path)\s*=", svg, re.I,
    ))
    if gradient_paints and len(gradient_paints) == shape_count:
        families.append("appearance_model")
    if stroke_only and len(stroke_only) == shape_count:
        families.append("stroke_network")
    # The procedural overlap family has known front/back instances.  For
    # third-party assets require an explicit composition cue, not merely two
    # path tags (letters and compound logos are not layer supervision).
    if (
        ":overlap:" in source_id
        or (shape_count >= 2 and (opacity_layer or explicit_layer))
    ):
        families.append("layer_relation")
    # Repeated <use> references are the only scene-level repeat labels whose
    # support can be trusted without an element-instance renderer.
    href_counts = Counter(
        str(element.attrib.get("href") or element.attrib.get(
            "{http://www.w3.org/1999/xlink}href", ""
        ))
        for element in (() if xml_root is None else xml_root.iter())
        if element.tag.rsplit("}", 1)[-1].lower() == "use"
    )
    if any(href and count >= 2 for href, count in href_counts.items()):
        families.append("symmetry_repeat_group")
    return tuple(dict.fromkeys(families))


def _foreground_support(rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return a conservative midline support and background residual field."""
    rgba = np.asarray(rgba, np.float32) / 255.0
    alpha = rgba[..., 3]
    if float(np.quantile(alpha, 0.10)) < 0.10:
        support = alpha >= 0.30
        residual = alpha
    else:
        rgb = rgba[..., :3]
        border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
        background = np.median(border, axis=0)
        distance = np.max(np.abs(rgb - background), axis=2)
        border_distance = np.max(np.abs(border - background), axis=1)
        median = float(np.median(border_distance))
        mad = 1.4826 * float(np.median(np.abs(border_distance - median)))
        threshold = max(0.035, median + 4.0 * mad)
        support = distance >= threshold
        residual = distance
    # Only remove isolated physical impossibilities.  Closing/filling here
    # would teach the query model to destroy counters.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        support.astype(np.uint8), 8,
    )
    cleaned = np.zeros(support.shape, bool)
    minimum = 1 if max(support.shape) <= 64 else 2
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) >= minimum:
            cleaned |= labels == label
    return cleaned, residual


def _validate_filter_row(row: dict, root: Path) -> dict | None:
    """Return a rejection record or ``None`` for one physically aligned row."""
    row_id = str(row.get("id", row.get("input_png", "unknown")))
    try:
        with Image.open(root / row["input_png"]) as input_image:
            with input_image.convert("RGBA") as converted:
                rgba = np.asarray(converted).copy()
        support, _residual = _foreground_support(rgba)
    except (OSError, ValueError):
        support = np.zeros((1, 1), bool)
    if int(np.sum(support)) < 2:
        return {"id": row_id, "reason": "unobservable-raster"}
    target_path = str((root / row["target_svg"]).resolve())
    try:
        svg = _read_svg_text(target_path)
        ET.fromstring(svg)
        svg_full_template(svg)
    except (OSError, RuntimeError, ValueError, ET.ParseError) as error:
        return {
            "id": row_id, "reason": "invalid-clean-render-target",
            "error": type(error).__name__,
        }
    try:
        aligned_target, target_alignment_iou = augmented_svg_full_support(
            svg, row, support,
        )
    except (OSError, RuntimeError, ValueError, ET.ParseError) as error:
        return {
            "id": row_id, "reason": "invalid-augmented-render-target",
            "error": type(error).__name__,
        }
    if not np.any(aligned_target):
        return {
            "id": row_id, "reason": "unobservable-clean-target",
            "alignment_iou": float(target_alignment_iou),
        }
    if target_alignment_iou < MINIMUM_SVG_ALIGNMENT_IOU:
        return {
            "id": row_id,
            "reason": "target-alignment-below-proof-floor",
            "alignment_iou": float(target_alignment_iou),
        }
    if _uses_svg_owner_labels(row):
        try:
            templates = svg_owner_templates(svg)
            owner_targets, alignment_iou = augmented_svg_owner_targets(
                templates, row, support,
            )
        except (OSError, RuntimeError, ValueError, ET.ParseError) as error:
            return {
                "id": row_id, "reason": "invalid-owner-template",
                "error": type(error).__name__,
            }
        if not owner_targets:
            return {
                "id": row_id, "reason": "owner-alignment-below-proof-floor",
                "alignment_iou": float(alignment_iou),
            }
    return None


def _validate_filter_chunk(
    payload: tuple[tuple[dict, ...], str],
) -> tuple[dict | None, ...]:
    rows, root_text = payload
    root = Path(root_text)
    return tuple(_validate_filter_row(row, root) for row in rows)


def _filter_supervisable_pairs(
    rows: Iterable[dict], root: Path,
) -> tuple[list[dict], tuple[dict, ...]]:
    """Remove pairs without measurable input or trustworthy owner labels.

    A real corpus-builder edge case composited light artwork over a transparent
    background and then JPEG-flattened it onto white.  The result is a blank
    input paired with non-empty SVG geometry.  Training on that row asks the
    network to hallucinate an unrecoverable target, so it is excluded before
    source-disjoint splitting and reported explicitly.
    """
    rows = tuple(rows)
    chunk_size = 1024
    chunks = tuple(
        rows[start:start + chunk_size]
        for start in range(0, len(rows), chunk_size)
    )
    payloads = tuple((chunk, str(root.resolve())) for chunk in chunks)
    # resvg's native Windows renderer retains process handles after thousands
    # of distinct SVG templates even when every PIL/BytesIO object is closed.
    # Contain those native resources in short-lived worker processes.  Ordered
    # chunks preserve the immutable accepted/rejected row contract.
    if len(rows) < chunk_size:
        reports = tuple(_validate_filter_chunk(payload) for payload in payloads)
    else:
        worker_count = min(4, max(1, len(chunks)))
        reports_list = []
        # ProcessPoolExecutor's max_tasks_per_child can deadlock on Windows
        # when queued work exceeds workers*limit.  Explicit finite waves give
        # the same native-resource lifetime without relying on worker respawn.
        wave_size = worker_count * 4
        for start in range(0, len(payloads), wave_size):
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                reports_list.extend(executor.map(
                    _validate_filter_chunk,
                    payloads[start:start + wave_size],
                ))
        reports = tuple(reports_list)
    accepted: list[dict] = []
    rejected: list[dict] = []
    for chunk, report in zip(chunks, reports):
        for row, rejection in zip(chunk, report):
            if rejection is None:
                accepted.append(row)
            else:
                rejected.append(rejection)
    return accepted, tuple(rejected)


def _bbox(mask: np.ndarray) -> tuple[float, float, float, float]:
    ys, xs = np.nonzero(mask)
    height, width = mask.shape
    return (
        float(xs.min()) / width, float(ys.min()) / height,
        float(xs.max() + 1) / width, float(ys.max() + 1) / height,
    )


def _components(mask: np.ndarray, *, maximum: int = 8) -> list[np.ndarray]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    rows = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area >= 2:
            rows.append((area, labels == label))
    rows.sort(key=lambda item: -item[0])
    return [mask for _area, mask in rows[:maximum]]


def _small_shape_augment(
    image: np.ndarray, support: np.ndarray, source_id: str,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Create deterministic physically aligned small-shape supervision.

    The original raster-pair builder renders objects at 66--92% of the
    canvas, so it cannot measure the canonical small-shape Recall@5 gate.  A
    source-disjoint subset of procedural geometry is recomposited at 18--34%
    of the canvas.  Image and support undergo the exact same transform.
    """
    digest = hashlib.sha256(source_id.encode("utf-8")).digest()
    if digest[0] >= 96 or not np.any(support):  # 37.5% deterministic subset
        return image, support, False
    ys, xs = np.nonzero(support)
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    crop = np.asarray(image[y1:y2, x1:x2], np.uint8)
    crop_mask = np.asarray(support[y1:y2, x1:x2], np.uint8) * 255
    height, width = support.shape
    target_fraction = 0.18 + (digest[1] / 255.0) * 0.16
    scale = target_fraction * max(height, width) / max(crop.shape[:2])
    new_width = max(3, int(round(crop.shape[1] * scale)))
    new_height = max(3, int(round(crop.shape[0] * scale)))
    resized = cv2.resize(crop, (new_width, new_height), interpolation=cv2.INTER_AREA)
    soft_mask = cv2.resize(
        crop_mask, (new_width, new_height), interpolation=cv2.INTER_AREA,
    ).astype(np.float32) / 255.0
    border = np.concatenate(
        (image[0], image[-1], image[:, 0], image[:, -1]), axis=0,
    )
    background = np.median(border, axis=0).astype(np.float32)
    canvas = np.broadcast_to(background, image.shape).copy()
    max_jitter_x = max(0, (width - new_width) // 5)
    max_jitter_y = max(0, (height - new_height) // 5)
    jitter_x = int(round((digest[2] / 255.0 * 2.0 - 1.0) * max_jitter_x))
    jitter_y = int(round((digest[3] / 255.0 * 2.0 - 1.0) * max_jitter_y))
    px = int(np.clip((width - new_width) // 2 + jitter_x, 0, width - new_width))
    py = int(np.clip((height - new_height) // 2 + jitter_y, 0, height - new_height))
    alpha = soft_mask[..., None]
    canvas[py:py + new_height, px:px + new_width] = (
        resized.astype(np.float32) * alpha
        + background[None, None, :] * (1.0 - alpha)
    )
    transformed_support = np.zeros((height, width), bool)
    transformed_support[py:py + new_height, px:px + new_width] = soft_mask >= 0.35
    # Very thin anti-aliased objects can disappear completely when reduced.
    # Such an example carries no valid box/topology supervision, so keep the
    # original aligned pair instead of manufacturing an empty target.
    if not np.any(transformed_support):
        return image, support, False
    return np.clip(np.rint(canvas), 0, 255).astype(np.uint8), transformed_support, True


def _gate_balanced_sample_weight(
    row: dict, row_families: tuple[str, ...],
) -> float:
    """Oversample fixed-gate slices without inspecting held-out outcomes."""
    weight = 1.0
    source = str(row.get("source", ""))
    # The v2 structural factory is balanced by construction: it contributes
    # the same number of source designs and rendered variants for stroke,
    # appearance, layer and repeat.  The large multipliers below compensate
    # for those families being extremely rare in the legacy harvested corpus.
    # Applying them again *inside* the balanced replay stratum changes its
    # intended 1:1:1:1 family mixture into roughly 34:3:1:8.  Keep the fixed
    # source-level replay share and equal within-source family prior here;
    # degradation weighting remains valid because it is orthogonal to type.
    balanced_structure = source == "synthetic-structure-v2"
    if source in {"synthetic-text", "synthetic-open-text"}:
        weight *= 1.65
    if source == "synthetic-geometry":
        digest = hashlib.sha256(str(row["id"]).encode("utf-8")).digest()
        if digest[0] < 96:
            weight *= 3.0
    if not balanced_structure and "layer_relation" in row_families:
        weight *= 1.50
    # The harvested corpus is extremely long-tailed (the original v8 run had
    # only 50 stroke scenes and 194 repeat scenes in ~60k pairs).  A cap of
    # six left those heads effectively unsupervised.  These source-only
    # weights give each rare, explicitly labelled family a material share of
    # an epoch without consulting calibration/test outcomes.
    if not balanced_structure and "stroke_network" in row_families:
        weight *= 48.0
    if not balanced_structure and "symmetry_repeat_group" in row_families:
        weight *= 12.0
    if not balanced_structure and "appearance_model" in row_families:
        weight *= 4.0
    augmentation = row.get("augmentation", {})
    if (
        float(augmentation.get("blur_radius") or 0) > 0
        or float(augmentation.get("noise_sigma") or 0) > 0
        or augmentation.get("jpeg_quality") is not None
    ):
        weight *= 1.20
    return float(min(64.0, weight))


def _balanced_structure_family_shares(
    rows: list[dict], weights: np.ndarray,
    families: dict[str, tuple[str, ...]],
) -> dict[str, float]:
    """Audit the conditional sampler prior of the balanced structure source."""
    if len(rows) != len(weights):
        raise ValueError("sampler rows and weights are not aligned")
    mass = {family: 0.0 for family in sorted(TYPED_STRUCTURE_FAMILIES)}
    total = 0.0
    for row, value in zip(rows, weights):
        if str(row.get("source", "")) != "synthetic-structure-v2":
            continue
        typed = tuple(
            family for family in families[str(row["id"])]
            if family in TYPED_STRUCTURE_FAMILIES
        )
        if len(typed) != 1:
            raise RuntimeError(
                "balanced structure row must supervise exactly one typed family"
            )
        amount = float(value)
        if not math.isfinite(amount) or amount <= 0.0:
            raise ValueError("balanced structure sampler mass must be positive")
        mass[typed[0]] += amount
        total += amount
    if total <= 0.0:
        return {}
    return {family: value / total for family, value in mass.items()}


def _support_parameters(mask: np.ndarray, parameter_dim: int) -> tuple[np.ndarray, np.ndarray]:
    """Measured generic geometry descriptors for the query parameter head."""
    ys, xs = np.nonzero(mask)
    height, width = mask.shape
    if not len(xs):
        return np.zeros(parameter_dim, np.float32), np.zeros(parameter_dim, np.float32)
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    normalized_x = (xs.astype(np.float64) + 0.5) / width
    normalized_y = (ys.astype(np.float64) + 0.5) / height
    centered = np.stack(
        (normalized_x - normalized_x.mean(), normalized_y - normalized_y.mean()),
        axis=1,
    )
    covariance = centered.T @ centered / max(1, len(centered))
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    major = eigenvectors[:, int(np.argmax(eigenvalues))]
    perimeter = float(cv2.arcLength(
        max(
            cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL,
                             cv2.CHAIN_APPROX_NONE)[0],
            key=cv2.contourArea,
        ), True,
    ))
    components, holes = topology_signature(mask)
    area = float(len(xs))
    bbox_area = float((x2 - x1) * (y2 - y1))
    values = np.asarray((
        (x1 + x2) / (2.0 * width), (y1 + y2) / (2.0 * height),
        (x2 - x1) / width, (y2 - y1) / height,
        area / (width * height), area / max(1.0, bbox_area),
        float(normalized_x.mean()), float(normalized_y.mean()),
        float(eigenvalues[1]), float(eigenvalues[0]),
        float(major[0]), float(major[1]),
        perimeter / max(1.0, math.sqrt(area)),
        float(4.0 * math.pi * area / max(1.0, perimeter * perimeter)),
        min(8.0, float(components)) / 8.0,
        min(5.0, float(holes)) / 5.0,
    ), np.float32)
    result = np.zeros(parameter_dim, np.float32)
    valid = np.zeros(parameter_dim, np.float32)
    count = min(parameter_dim, len(values))
    result[:count] = values[:count]
    valid[:count] = 1.0
    return result, valid


def _support_preimage_lattice(mask: np.ndarray, size: int) -> np.ndarray:
    """Project support conservatively onto the neural mask lattice.

    Nearest-neighbour downsampling can erase a real one-pixel stroke solely
    because it falls between selected sample centres.  A lattice cell belongs
    to the digital preimage whenever any source support contributes to it.
    """
    support = np.asarray(mask, bool)
    if support.ndim != 2 or int(size) <= 0:
        raise ValueError("support preimage requires a 2D mask and positive size")
    coverage = cv2.resize(
        support.astype(np.float32), (int(size), int(size)),
        interpolation=cv2.INTER_AREA,
    )
    result = np.ascontiguousarray(coverage > 0.0, dtype=np.float32)
    if np.any(support) and not np.any(result):
        raise RuntimeError("non-empty support vanished on the neural lattice")
    return result


class PairDataset(Dataset):
    def __init__(
        self, rows: Iterable[dict], root: Path, families: dict[str, tuple[str, ...]],
        *, image_size: int = 128, parameter_dim: int = 16,
        support_size: int | None = None,
    ) -> None:
        self.rows = tuple(rows)
        self.root = root
        self.families = families
        self.image_size = int(image_size)
        self.parameter_dim = int(parameter_dim)
        self.support_size = int(
            support_size if support_size is not None else self.image_size // 4
        )

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict:
        row = self.rows[index]
        with Image.open(self.root / row["input_png"]) as input_image:
            with input_image.convert("RGBA") as converted:
                image = np.asarray(converted).copy()
        observed_support, residual = _foreground_support(image)
        if not np.any(observed_support):
            raise RuntimeError(f"unobservable row reached dataset: {row['id']}")
        svg = _read_svg_text(str((self.root / row["target_svg"]).resolve()))
        support, _clean_alignment_iou = augmented_svg_full_support(
            svg, row, observed_support,
        )
        small_shape_augmented = False
        if str(row.get("source", "")) == "synthetic-geometry":
            image, support, small_shape_augmented = _small_shape_augment(
                image, support, str(row["id"]),
            )
            if small_shape_augmented:
                observed_support, residual = _foreground_support(image)
        resized = np.asarray(Image.fromarray(image).resize(
            (self.image_size, self.image_size), Image.Resampling.BILINEAR,
        ), np.float32) / 255.0
        targets: list[tuple[str, np.ndarray, str | None]] = []
        owner_targets: tuple[tuple[str, np.ndarray], ...] = ()
        owner_families = frozenset(("whole_shape", "text_line", "glyph_group"))
        if _uses_svg_owner_labels(row):
            try:
                templates = svg_owner_templates(svg)
                owner_targets, _alignment_iou = augmented_svg_owner_targets(
                    templates, row, observed_support,
                )
            except (OSError, RuntimeError, ValueError, ET.ParseError) as error:
                raise RuntimeError(
                    f"invalid SVG owner supervision for {row['id']}"
                ) from error
            if not owner_targets:
                raise RuntimeError(
                    f"unproved SVG owner alignment reached dataset: {row['id']}"
                )
        if owner_targets:
            targets.extend((family, mask, None) for family, mask in owner_targets)
        for family in self.families[row["id"]]:
            # A glyph-group query denotes the group/line, not every connected
            # letter.  Treating letters as separate group instances allowed a
            # single broad query to be counted repeatedly and made Recall@K
            # both inflated and, under one-to-one matching, impossible at K=5.
            if owner_targets and family in owner_families:
                continue
            targets.append((family, support, None))
        augmentation = row.get("augmentation", {})
        codec_roundtrip = bool(
            augmentation.get("jpeg_quality") is not None
            or augmentation.get("webp_quality") is not None
        )
        degraded = bool(
            float(augmentation.get("blur_radius") or 0) > 0
            or float(augmentation.get("noise_sigma") or 0) > 0
            or codec_roundtrip
        )
        row_families = self.families[row["id"]]
        allowed_negative_types = applicable_hard_negative_types(
            row_families,
            jpeg=codec_roundtrip,
            noisy=float(augmentation.get("noise_sigma") or 0) > 0,
        )
        if degraded:
            boundary = cv2.morphologyEx(
                observed_support.astype(np.uint8), cv2.MORPH_GRADIENT,
                np.ones((3, 3), np.uint8),
            ) > 0
            high = residual >= max(0.04, float(np.quantile(residual, 0.92)))
            risk = cv2.dilate(boundary.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
            risk |= high & cv2.dilate(
                observed_support.astype(np.uint8), np.ones((5, 5), np.uint8),
            ).astype(bool)
            negative_type = (
                "preserve_jpeg_halo"
                if codec_roundtrip else
                "jagged_overfit"
                if float(augmentation.get("noise_sigma") or 0) > 0 else
                "remove_real_accent"
            )
            if (
                int(risk.sum()) >= 2
                and negative_type in allowed_negative_types
            ):
                targets.append(("risk_hard_negative", risk, negative_type))
        # Every declared hard-negative class is supervised by an actual
        # deterministic counterfactual program render over the clean target
        # support.  The target is the region whose support/appearance changes,
        # not an inert class one-hot or a parameter name appended to an IR.
        counterfactuals = counterfactual_risk_regions(
            support, allowed_types=allowed_negative_types,
        )
        counterfactual_targets = []
        offset = int(hashlib.sha256(
            str(row["id"]).encode("utf-8")
        ).hexdigest()[:8], 16) % len(HARD_NEGATIVE_TYPES)
        rotated_negative_types = (
            HARD_NEGATIVE_TYPES[offset:] + HARD_NEGATIVE_TYPES[:offset]
        )
        # Family-specific semantic near misses are otherwise drowned out by
        # the generic jagged/codec classes: a calibration split can contain
        # hundreds of appearance/stroke/layer scenes yet expose only a few
        # dozen labels for the corresponding class head.  Prefer the one
        # canonical counterfactual justified by the declared family, then keep
        # the deterministic rotation for every remaining class.
        semantic_priority = tuple(
            negative_type for family, negative_type in (
                ("appearance_model", "gradient_band_explosion"),
                ("stroke_network", "stroke_fill_confusion"),
                ("layer_relation", "wrong_layer"),
            )
            if family in row_families
        )
        ordered_negative_types = semantic_priority + tuple(
            negative_type for negative_type in rotated_negative_types
            if negative_type not in semantic_priority
        )
        for negative_type in ordered_negative_types:
            risk, applicable = counterfactuals[negative_type]
            if applicable:
                counterfactual_targets.append((
                    "risk_hard_negative", risk, negative_type,
                ))
                break
        targets = (
            targets[:max(0, 24 - len(counterfactual_targets))]
            + counterfactual_targets
        )[:24]
        family_ids = []
        masks = []
        boxes = []
        topology = []
        relations = []
        relation_masks = []
        parameters = []
        parameter_masks = []
        hard_negatives = []
        small_shapes = []
        for family, mask, hard_negative_name in targets:
            # Fail closed on malformed/vanished supervision.  The normal
            # support target is guaranteed non-empty above, while optional
            # risk targets may legitimately disappear after transforms.
            if not np.any(mask):
                continue
            scaled = _support_preimage_lattice(mask, self.support_size)
            family_ids.append(QUERY_FAMILIES.index(family))
            masks.append(scaled)
            components, holes = topology_signature(mask)
            boxes.append(_bbox(mask))
            topology.append((min(8, components), min(5, holes)))
            positive_relations, observable_relations = relation_supervision(
                row, family,
            )
            relation = np.asarray(
                [name in positive_relations for name in RELATION_TYPES],
                np.float32,
            )
            relation_mask = np.asarray(
                [name in observable_relations for name in RELATION_TYPES],
                np.float32,
            )
            relations.append(relation)
            relation_masks.append(relation_mask)
            values, value_mask = _support_parameters(mask, self.parameter_dim)
            parameters.append(values)
            parameter_masks.append(value_mask)
            hard_negative = len(HARD_NEGATIVE_TYPES)
            if family == "risk_hard_negative":
                if hard_negative_name not in HARD_NEGATIVE_TYPES:
                    raise RuntimeError("risk target lacks a hard-negative class")
                hard_negative = HARD_NEGATIVE_TYPES.index(hard_negative_name)
            hard_negatives.append(hard_negative)
            small_shapes.append(bool(
                family == "whole_shape" and small_shape_augmented
            ))
        return {
            "id": row["id"], "source_id": _split_group(row),
            "rgba": np.transpose(resized, (2, 0, 1)).astype(np.float32),
            "family": np.asarray(family_ids, np.int64),
            "support": np.stack(masks).astype(np.float32),
            "bbox": np.asarray(boxes, np.float32),
            "topology": np.asarray(topology, np.int64),
            "relations": np.stack(relations).astype(np.float32),
            "relation_mask": np.stack(relation_masks).astype(np.float32),
            "parameters": np.stack(parameters).astype(np.float32),
            "parameter_mask": np.stack(parameter_masks).astype(np.float32),
            "hard_negative": np.asarray(hard_negatives, np.int64),
            "small_shape": np.asarray(small_shapes, bool),
        }


def _collate(rows: list[dict]) -> list[dict] | torch.Tensor:
    return rows


def _targets(rows: list[dict], config: ProposalNetConfig, device: torch.device) -> list[dict]:
    result = []
    for row in rows:
        result.append({
            "family": torch.as_tensor(row["family"], device=device),
            "bbox": torch.as_tensor(row["bbox"], device=device),
            "support": torch.as_tensor(row["support"], device=device),
            "parameters": torch.as_tensor(row["parameters"], device=device),
            "parameter_mask": torch.as_tensor(row["parameter_mask"], device=device),
            "topology": torch.as_tensor(row["topology"], device=device),
            "relations": torch.as_tensor(row["relations"], device=device),
            "relation_mask": torch.as_tensor(
                row["relation_mask"], device=device,
            ),
            "hard_negative": torch.as_tensor(row["hard_negative"], device=device),
            "small_shape": torch.as_tensor(row["small_shape"], device=device),
        })
    return result


def _soft_iou(prediction: np.ndarray, target: np.ndarray) -> float:
    intersection = float(np.sum(prediction * target))
    union = float(np.sum(prediction + target - prediction * target))
    return intersection / max(1e-7, union)


@torch.no_grad()
def _evaluate(
    model: ProposalNet, loader: DataLoader, device: torch.device, *, k: int = 32,
) -> tuple[dict, list[CalibrationExample]]:
    """Evaluate neural queries only, with global top-K and one-to-one matches.

    The previous metric selected K queries independently for every family and
    allowed one query to satisfy several target instances.  That was not
    Recall@K and could substantially inflate glyph/instance recall.
    """
    model.eval()
    totals = Counter()
    hits5 = Counter()
    hitsk = Counter()
    iou5_sums = Counter()
    iouk_sums = Counter()
    oracle_capacity5 = Counter()
    row_count = 0
    rows_over_global_top5_capacity = 0
    examples: list[CalibrationExample] = []

    def matched_targets(
        probability: np.ndarray, confidence: np.ndarray,
        supports: np.ndarray, row: dict, cutoff: int,
    ) -> dict[int, tuple[float, float, int, int]]:
        predicted_family = np.argmax(probability[:, :-1], axis=-1)
        combined = np.max(probability[:, :-1], axis=-1) * confidence
        order = np.argsort(-combined)[:min(int(cutoff), len(combined))]
        result: dict[int, tuple[float, float, int, int]] = {}
        for family_index in sorted(set(row["family"].tolist())):
            target_ids = np.flatnonzero(row["family"] == family_index)
            query_ids = np.asarray([
                query_id for query_id in order
                if int(predicted_family[query_id]) == int(family_index)
            ], np.int64)
            if not len(target_ids) or not len(query_ids):
                continue
            ious = np.asarray([
                [
                    _soft_iou(supports[query_id], row["support"][target_id])
                    for target_id in target_ids
                ]
                for query_id in query_ids
            ], np.float64)
            query_match, target_match = linear_sum_assignment(-ious)
            for query_local, target_local in zip(query_match, target_match):
                query_id = int(query_ids[query_local])
                target_id = int(target_ids[target_local])
                result[target_id] = (
                    float(probability[query_id, family_index] * confidence[query_id]),
                    float(ious[query_local, target_local]),
                    int(query_local) + 1,
                    int(len(query_ids)),
                )
        return result

    for rows in loader:
        images = torch.as_tensor(np.stack([row["rgba"] for row in rows]), device=device)
        output = model(images)
        probability = output["family_logits"].softmax(-1).cpu().numpy()
        confidence = torch.sigmoid(output["confidence_logits"]).cpu().numpy()
        support_probability = torch.sigmoid(output["support_logits"])
        predicted_family = output["family_logits"][..., :-1].argmax(-1)
        support_probability = _gate_text_support_probability(
            support_probability, output["bbox"], predicted_family,
            padding=model.config.text_bbox_gate_padding,
            vertical_only=model.config.text_bbox_gate_vertical_only,
        )
        supports = support_probability.cpu().numpy()
        for batch_index, row in enumerate(rows):
            row_count += 1
            row_target_count = int(len(row["family"]))
            rows_over_global_top5_capacity += int(row_target_count > 5)
            oracle_capacity5["overall"] += min(5, row_target_count)
            local_family_counts = Counter(
                QUERY_FAMILIES[int(family_index)]
                for family_index in row["family"].tolist()
            )
            for family, count in local_family_counts.items():
                oracle_capacity5[family] += min(5, int(count))
            small_count = int(np.sum(row["small_shape"]))
            oracle_capacity5["small_shape"] += min(5, small_count)
            matches5 = matched_targets(
                probability[batch_index], confidence[batch_index],
                supports[batch_index], row, min(5, k),
            )
            matchesk = matched_targets(
                probability[batch_index], confidence[batch_index],
                supports[batch_index], row, k,
            )
            for target_index, family_index in enumerate(row["family"].tolist()):
                family = QUERY_FAMILIES[family_index]
                family_candidate_count = int(np.sum(
                    predicted_family[batch_index] == family_index
                ))
                _confidence5, iou5, _rank5, _count5 = matches5.get(
                    target_index, (0.0, 0.0, 6, 5),
                )
                best_confidence, iouk, admission_rank, candidate_count = matchesk.get(
                    target_index,
                    (0.0, 0.0, family_candidate_count + 1, family_candidate_count),
                )
                totals[family] += 1
                hits5[family] += int(iou5 >= 0.50)
                hitsk[family] += int(iouk >= 0.50)
                iou5_sums[family] += iou5
                iouk_sums[family] += iouk
                if bool(row["small_shape"][target_index]):
                    totals["small_shape"] += 1
                    hits5["small_shape"] += int(iou5 >= 0.50)
                    hitsk["small_shape"] += int(iouk >= 0.50)
                    iou5_sums["small_shape"] += iou5
                    iouk_sums["small_shape"] += iouk
                examples.append(CalibrationExample(
                    family=family, type_confidence=best_confidence,
                    support_iou=iouk, source_group=str(row["source_id"]),
                    admission_rank=admission_rank,
                    candidate_count=max(1, candidate_count),
                ))
    measured_families = sorted(totals)
    metrics = {
        family: {
            "instances": totals[family],
            "neural_only_recall_at_5_iou50": hits5[family] / max(1, totals[family]),
            "neural_only_recall_at_k_iou50": hitsk[family] / max(1, totals[family]),
            "mean_best_soft_iou_at_5": iou5_sums[family] / max(1, totals[family]),
            "mean_best_soft_iou_at_k": iouk_sums[family] / max(1, totals[family]),
            "individual_family_oracle_recall_at_5_capacity": (
                oracle_capacity5[family] / max(1, totals[family])
            ),
        }
        for family in measured_families
    }
    family_rows = [family for family in measured_families if family != "small_shape"]
    overall_count = sum(totals[family] for family in family_rows)
    metrics["overall"] = {
        "instances": overall_count,
        "neural_only_recall_at_5_iou50": (
            sum(hits5[family] for family in family_rows) / max(1, overall_count)
        ),
        "neural_only_recall_at_k_iou50": (
            sum(hitsk[family] for family in family_rows) / max(1, overall_count)
        ),
        "mean_best_soft_iou_at_5": (
            sum(iou5_sums[family] for family in family_rows) / max(1, overall_count)
        ),
        "mean_best_soft_iou_at_k": (
            sum(iouk_sums[family] for family in family_rows) / max(1, overall_count)
        ),
        "global_oracle_recall_at_5_capacity": (
            oracle_capacity5["overall"] / max(1, overall_count)
        ),
        "rows": row_count,
        "rows_over_global_top5_capacity": rows_over_global_top5_capacity,
    }
    return metrics, examples


_SELECTION_RECALL_GATES = {
    "overall": 0.97,
    "text_line": 0.99,
    "glyph_group": 0.99,
    "small_shape": 0.98,
    "layer_relation": 0.95,
    "stroke_network": 0.98,
    "appearance_model": 0.95,
    "symmetry_repeat_group": 0.95,
    "risk_hard_negative": 0.95,
}


def _calibration_selection_key(metrics: dict) -> tuple[float, float, float]:
    """Rank checkpoints on held-out Recall@5, never training NLL.

    The minimum normalized gate margin is primary, so a large easy-family gain
    cannot hide a weaker required slice.  Overall recall and mean required-slice
    IoU are deterministic tie breakers.  The test split is not inspected here.
    """
    recalls = {
        family: float(metrics.get(family, {}).get(
            "neural_only_recall_at_5_iou50", 0.0,
        ))
        for family in _SELECTION_RECALL_GATES
    }
    margins = [
        recalls[family] / threshold
        for family, threshold in _SELECTION_RECALL_GATES.items()
    ]
    mean_iou = float(np.mean([
        float(metrics.get(family, {}).get("mean_best_soft_iou_at_5", 0.0))
        for family in _SELECTION_RECALL_GATES
    ]))
    return (
        min(margins), recalls["overall"], mean_iou,
    )


def _save_checkpoint(
    path: Path, model: ProposalNet, config: ProposalNetConfig, *, epoch: int,
    family_counts: dict, split_counts: dict, training_sources_sha256: str,
    training_rows_sha256: str, training_data_contract_sha256: str,
    label_contract_sha256: str,
    selection_key: tuple[float, float, float], training_loss: float,
    optimizer: torch.optim.Optimizer | None = None,
    scaler: torch.amp.GradScaler | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "pcdc-proposal-net-checkpoint/v2-large",
        "config": asdict(config), "model": model.state_dict(),
        "families": QUERY_FAMILIES, "epoch": int(epoch),
        "family_counts": family_counts, "split_counts": split_counts,
        "training_sources_sha256": training_sources_sha256,
        "training_rows_sha256": training_rows_sha256,
        "training_data_contract_sha256": training_data_contract_sha256,
        "label_contract_version": LABEL_CONTRACT_VERSION,
        "label_contract_sha256": label_contract_sha256,
        "selection_contract": "calibration-min-normalized-required-Recall@5/v1",
        "calibration_selection_key": tuple(float(value) for value in selection_key),
        "training_loss_diagnostic": float(training_loss),
    }
    if optimizer is not None:
        payload["optimizer"] = optimizer.state_dict()
    if scaler is not None:
        payload["scaler"] = scaler.state_dict()
    torch.save(payload, path)


def train(args: argparse.Namespace) -> dict:
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    mixed_report_path = args.pair_root / "report.json"
    mixed_report = None
    if mixed_report_path.is_file():
        candidate_report = json.loads(mixed_report_path.read_text("utf-8"))
        if candidate_report.get("schema") == "pcdc-proposal-mixed-corpus/v1":
            mixed_report = validate_mixed_corpus(args.pair_root)
    if (
        float(args.open_text_replay_share) > 0
        or float(args.structure_replay_share) > 0
    ) and mixed_report is None:
        raise ValueError("fixed supplement replay requires a validated mixed corpus")
    corpus_data_contract_sha256 = _corpus_data_contract_sha256(args.pair_root)
    if args.filter_cache is not None:
        training_contract_digest = hashlib.sha256(
            corpus_data_contract_sha256.encode("ascii")
        )
        training_contract_digest.update(args.filter_cache.read_bytes())
        training_data_contract_sha256 = training_contract_digest.hexdigest()
    else:
        training_data_contract_sha256 = corpus_data_contract_sha256
    raw_rows = _read_pairs(args.pair_root, args.limit)
    if args.filter_cache is not None:
        rows, rejected_pairs = validate_filter_cache(
            args.filter_cache, raw_rows,
            training_data_contract_sha256=corpus_data_contract_sha256,
        )
    else:
        rows, rejected_pairs = _filter_supervisable_pairs(
            raw_rows, args.pair_root,
        )
    if not rows:
        raise RuntimeError("no observable raster/vector training pairs")
    label_contract_sha256 = _label_contract_sha256()
    family_cache: dict[tuple[str, str, str], tuple[str, ...]] = {}
    families = {}
    for row in rows:
        key = (
            str(row.get("source", "")), str(row.get("source_id", "")),
            str(row.get("target_svg", "")),
        )
        if key not in family_cache:
            family_cache[key] = _svg_families(row, args.pair_root)
        families[row["id"]] = family_cache[key]
    split_rows = {name: [] for name in ("train", "calibration", "test")}
    for row in rows:
        split_rows[_stable_bucket(_split_group(row))].append(row)
    split_group_sets = {
        name: {_split_group(row) for row in part}
        for name, part in split_rows.items()
    }
    split_source_sets = {
        name: {str(row["source_id"]) for row in part}
        for name, part in split_rows.items()
    }
    if any(split_group_sets[a] & split_group_sets[b]
           for a, b in (("train", "calibration"), ("train", "test"), ("calibration", "test"))):
        raise RuntimeError("family-disjoint split contract failed")
    datasets = {
        name: PairDataset(
            part, args.pair_root, families, image_size=args.image_size,
            parameter_dim=args.parameter_dim,
            support_size=(args.image_size // 4) * args.mask_upsample,
        )
        for name, part in split_rows.items()
    }
    training_weights = np.asarray([
        _gate_balanced_sample_weight(row, families[row["id"]])
        for row in split_rows["train"]
    ], np.float64)
    requested_replay_shares = {
        source: share for source, share in {
            "synthetic-open-text": float(args.open_text_replay_share),
            "synthetic-structure-v2": float(args.structure_replay_share),
        }.items() if share > 0.0
    }
    if requested_replay_shares:
        training_weights = rebalance_source_shares(
            split_rows["train"], training_weights,
            shares=requested_replay_shares,
        )
    expected_replay_shares = {
        source: expected_source_share(
            split_rows["train"], training_weights, source=source,
        )
        for source in requested_replay_shares
    }
    expected_structure_family_shares = _balanced_structure_family_shares(
        split_rows["train"], training_weights, families,
    )
    if "synthetic-structure-v2" in requested_replay_shares:
        if set(expected_structure_family_shares) != set(TYPED_STRUCTURE_FAMILIES):
            raise RuntimeError("balanced structure sampler is missing a family")
        if any(
            not 0.20 <= share <= 0.30
            for share in expected_structure_family_shares.values()
        ):
            raise RuntimeError(
                "balanced structure replay family mass escaped the 20-30% "
                "preflight envelope"
            )
    sampling_generator = torch.Generator().manual_seed(args.seed)
    training_sampler = WeightedRandomSampler(
        torch.as_tensor(training_weights, dtype=torch.double),
        num_samples=len(datasets["train"]), replacement=True,
        generator=sampling_generator,
    )
    loaders = {}
    for name, dataset in datasets.items():
        loaders[name] = DataLoader(
            dataset, batch_size=args.batch_size, shuffle=False,
            sampler=training_sampler if name == "train" else None,
            num_workers=args.workers, persistent_workers=args.workers > 0,
            prefetch_factor=4 if args.workers > 0 else None,
            collate_fn=_collate, pin_memory=torch.cuda.is_available(),
        )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    config = ProposalNetConfig(
        hidden_dim=args.hidden_dim, query_count=args.query_count,
        decoder_layers=args.decoder_layers, attention_heads=8,
        parameter_dim=args.parameter_dim, mask_upsample=args.mask_upsample,
        spatial_positioning=args.spatial_positioning,
        text_bbox_gate_padding=args.text_bbox_gate_padding,
        text_bbox_gate_vertical_only=args.text_bbox_gate_vertical_only,
    )
    preflight_checkpoint = args.resume or args.initialize
    if args.readiness_report is None:
        raise RuntimeError(
            "refusing large training without --readiness-report"
        )
    readiness = _validate_v14_readiness(
        args.readiness_report, config=config,
        checkpoint=preflight_checkpoint, pair_root=args.pair_root,
        filter_cache=args.filter_cache,
        corpus_data_contract_sha256=corpus_data_contract_sha256,
    )
    if args.tiny_overfit_preflight is None:
        raise RuntimeError(
            "refusing large training without --tiny-overfit-preflight"
        )
    tiny_overfit_preflight = _validate_tiny_overfit_preflight(
        args.tiny_overfit_preflight, config=config,
        checkpoint=preflight_checkpoint, pair_root=args.pair_root,
        filter_cache=args.filter_cache,
    )
    model = ProposalNet(config).to(device)
    resume_epoch = 0
    resumed_from = None
    initialized_from = None
    if args.resume is not None:
        resume_payload = torch.load(
            args.resume, map_location=device, weights_only=False,
        )
        if resume_payload.get("schema") != "pcdc-proposal-net-checkpoint/v2-large":
            raise RuntimeError("resume checkpoint has an unsupported schema")
        if resume_payload.get("config") != asdict(config):
            raise RuntimeError("resume checkpoint/model configuration mismatch")
        model.load_state_dict(resume_payload["model"])
        resume_epoch = int(resume_payload.get("epoch", 0))
        resumed_from = str(args.resume.resolve())
    elif args.initialize is not None:
        initialization_payload = torch.load(
            args.initialize, map_location=device, weights_only=False,
        )
        if initialization_payload.get("schema") != "pcdc-proposal-net-checkpoint/v2-large":
            raise RuntimeError("initialization checkpoint has an unsupported schema")
        initialization_config = dict(initialization_payload.get("config", {}))
        current_config = asdict(config)
        comparable_keys = set(current_config) - {
            "mask_upsample", "spatial_positioning", "text_bbox_gate_padding",
            "text_bbox_gate_vertical_only",
        }
        if any(
            initialization_config.get(key, current_config[key])
            != current_config[key]
            for key in comparable_keys
        ):
            raise RuntimeError("initialization checkpoint/model configuration mismatch")
        incompatible = model.load_state_dict(
            initialization_payload["model"], strict=False,
        )
        allowed_missing = set()
        if (
            config.mask_upsample == 2
            and initialization_config.get("mask_upsample", 1) != 2
        ):
            allowed_missing.update({
                "mask_lateral.weight", "mask_lateral.bias",
            })
        if (
            config.spatial_positioning
            and not initialization_config.get("spatial_positioning", False)
        ):
            allowed_missing.update({
                "position_projection.weight", "position_projection.bias",
            })
        if (
            set(incompatible.missing_keys) != allowed_missing
            or incompatible.unexpected_keys
        ):
            raise RuntimeError(
                "initialization checkpoint has incompatible model weights: "
                f"missing={incompatible.missing_keys}, "
                f"unexpected={incompatible.unexpected_keys}"
            )
        initialized_from = str(args.initialize.resolve())
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    if args.resume is not None:
        if resume_payload.get("optimizer") is not None:
            optimizer.load_state_dict(resume_payload["optimizer"])
        if resume_payload.get("scaler") is not None:
            scaler.load_state_dict(resume_payload["scaler"])
    history = []
    selection_history = []
    best_loss = math.inf
    best_selection_key = (-math.inf, -math.inf, -math.inf)
    started = time.perf_counter()
    family_counts = Counter(
        family for row in rows for family in families[row["id"]]
    )
    split_counts = {name: len(part) for name, part in split_rows.items()}
    source_digest = hashlib.sha256("\n".join(sorted(split_group_sets["train"])).encode()).hexdigest()
    row_digest = hashlib.sha256("\n".join(sorted(
        str(row["id"]) for row in split_rows["train"]
    )).encode()).hexdigest()
    if args.resume is not None and (
        resume_payload.get("training_sources_sha256") != source_digest
    ):
        raise RuntimeError("resume checkpoint belongs to another training split")
    if args.resume is not None and (
        resume_payload.get("training_rows_sha256") != row_digest
    ):
        raise RuntimeError("resume checkpoint belongs to another accepted-row set")
    if args.resume is not None and (
        resume_payload.get("training_data_contract_sha256")
        != training_data_contract_sha256
    ):
        raise RuntimeError("resume checkpoint belongs to another data manifest")
    if args.resume is not None and (
        resume_payload.get("label_contract_version") != LABEL_CONTRACT_VERSION
        or resume_payload.get("label_contract_sha256") != label_contract_sha256
    ):
        raise RuntimeError(
            "resume checkpoint has another label contract; use --initialize "
            "for a new proof-bound training run"
        )
    total_epochs = resume_epoch + args.epochs
    latest_checkpoint = (
        args.latest_checkpoint
        if args.latest_checkpoint is not None else
        args.checkpoint.with_name(
            args.checkpoint.stem + "_latest" + args.checkpoint.suffix
        )
    )
    def progress(payload: dict) -> None:
        if args.progress is None:
            return
        args.progress.parent.mkdir(parents=True, exist_ok=True)
        args.progress.write_text(json.dumps({
            **payload, "updated_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2, sort_keys=True), "utf-8")

    progress({
        "status": "running", "epoch": resume_epoch, "epochs": total_epochs,
        "pairs": len(rows), "split_counts": split_counts,
        "device": str(device),
    })
    if args.resume is not None or args.initialize is not None:
        baseline_metrics, _baseline_examples = _evaluate(
            model, loaders["calibration"], device, k=args.query_count,
        )
        best_selection_key = _calibration_selection_key(baseline_metrics)
        best_loss = (
            float(resume_payload.get("training_loss_diagnostic", math.inf))
            if args.resume is not None else math.inf
        )
        selection_history.append({
            "epoch": resume_epoch, "training_loss": None,
            "minimum_normalized_gate_margin": best_selection_key[0],
            "overall_recall_at_5": best_selection_key[1],
            "mean_required_iou_at_5": best_selection_key[2],
            "source": (
                "resume-baseline" if args.resume is not None
                else "immutable-initialization-baseline"
            ),
        })
        _save_checkpoint(
            args.checkpoint, model, config, epoch=resume_epoch,
            family_counts=dict(family_counts), split_counts=split_counts,
            training_sources_sha256=source_digest,
            training_rows_sha256=row_digest,
            training_data_contract_sha256=training_data_contract_sha256,
            label_contract_sha256=label_contract_sha256,
            selection_key=best_selection_key, training_loss=best_loss,
            optimizer=optimizer, scaler=scaler,
        )
    for continuation_epoch in range(1, args.epochs + 1):
        epoch = resume_epoch + continuation_epoch
        model.train()
        losses = []
        for step, batch in enumerate(loaders["train"], 1):
            images = torch.as_tensor(np.stack([row["rgba"] for row in batch]), device=device)
            target = _targets(batch, config, device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                loss = proposal_net_loss(model(images), target)["total"]
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
            if step % 100 == 0:
                row = {
                    "epoch": epoch, "step": step, "steps": len(loaders["train"]),
                    "mean_loss": float(np.mean(losses[-100:])),
                    "status": "running", "epochs": total_epochs,
                }
                if not args.quiet:
                    print(json.dumps(row), flush=True)
                progress(row)
        epoch_loss = float(np.mean(losses))
        history.append(epoch_loss)
        calibration_epoch_metrics, _selection_examples = _evaluate(
            model, loaders["calibration"], device, k=args.query_count,
        )
        selection_key = _calibration_selection_key(calibration_epoch_metrics)
        selection_history.append({
            "epoch": epoch, "training_loss": epoch_loss,
            "minimum_normalized_gate_margin": selection_key[0],
            "overall_recall_at_5": selection_key[1],
            "mean_required_iou_at_5": selection_key[2],
        })
        if (
            selection_key > best_selection_key
            or (selection_key == best_selection_key and epoch_loss < best_loss)
        ):
            best_selection_key = selection_key
            best_loss = epoch_loss
            _save_checkpoint(
                args.checkpoint, model, config, epoch=epoch,
                family_counts=dict(family_counts), split_counts=split_counts,
                training_sources_sha256=source_digest,
                training_rows_sha256=row_digest,
                training_data_contract_sha256=training_data_contract_sha256,
                label_contract_sha256=label_contract_sha256,
                selection_key=selection_key, training_loss=epoch_loss,
                optimizer=optimizer, scaler=scaler,
            )
        _save_checkpoint(
            latest_checkpoint, model, config, epoch=epoch,
            family_counts=dict(family_counts), split_counts=split_counts,
            training_sources_sha256=source_digest,
            training_rows_sha256=row_digest,
            training_data_contract_sha256=training_data_contract_sha256,
            label_contract_sha256=label_contract_sha256,
            selection_key=selection_key, training_loss=epoch_loss,
            optimizer=optimizer, scaler=scaler,
        )
        if not args.quiet:
            print(json.dumps({
                "epoch": epoch, "loss": epoch_loss,
                "calibration_selection_key": selection_key,
                "best_calibration_selection_key": best_selection_key,
            }), flush=True)
        progress({
            "status": "running", "epoch": epoch, "epochs": total_epochs,
            "loss": epoch_loss,
            "calibration_selection_key": selection_key,
            "best_calibration_selection_key": best_selection_key,
        })

    payload = torch.load(args.checkpoint, map_location=device, weights_only=False)
    model.load_state_dict(payload["model"])
    calibration_metrics, calibration_examples = _evaluate(
        model, loaders["calibration"], device, k=args.query_count,
    )
    test_metrics, test_examples = _evaluate(
        model, loaders["test"], device, k=args.query_count,
    )
    calibration = calibrate_conformal_sets(
        calibration_examples, target_coverage=0.99, minimum_class_examples=100,
    )
    # Canonical plan section 22 specifies global top-5 gates.  Missing slices
    # fail closed; they are never silently removed from the required set.
    recall_gates = {
        "overall": max(0.97, float(args.minimum_recall)),
        "text_line": 0.99,
        "glyph_group": 0.99,
        "small_shape": 0.98,
        "layer_relation": 0.95,
        "stroke_network": 0.98,
        "appearance_model": 0.95,
        "symmetry_repeat_group": 0.95,
        "risk_hard_negative": 0.95,
    }
    recall_gate_results = {
        family: {
            "instances": int(test_metrics.get(family, {}).get("instances", 0)),
            "threshold": threshold,
            "recall": float(test_metrics.get(family, {}).get(
                "neural_only_recall_at_5_iou50", 0.0,
            )),
            "oracle_capacity": float(test_metrics.get(family, {}).get(
                "global_oracle_recall_at_5_capacity" if family == "overall"
                else "individual_family_oracle_recall_at_5_capacity",
                0.0,
            )),
            "mathematically_feasible": bool(
                test_metrics.get(family, {}).get(
                    "global_oracle_recall_at_5_capacity" if family == "overall"
                    else "individual_family_oracle_recall_at_5_capacity",
                    0.0,
                ) >= threshold
            ),
            "passed": bool(
                test_metrics.get(family, {}).get("instances", 0) >= 100
                and test_metrics.get(family, {}).get(
                    "neural_only_recall_at_5_iou50", 0.0,
                ) >= threshold
            ),
        }
        for family, threshold in recall_gates.items()
    }
    required = tuple(recall_gates)
    oracle_capacity_gate_feasible = all(
        row["mathematically_feasible"]
        for row in recall_gate_results.values()
    )
    minimum_recall = min(
        (row["recall"] for row in recall_gate_results.values()), default=0.0,
    )
    thresholds = [asdict(row) for row in calibration.thresholds]
    threshold_by_family = {row["family"]: row for row in thresholds}
    conformal_required = (
        "text_line", "glyph_group", "whole_shape", "layer_relation",
        "stroke_network", "appearance_model", "symmetry_repeat_group",
        "risk_hard_negative",
    )
    nonvacuous = all(
        family in threshold_by_family
        and threshold_by_family[family]["calibration_count"] >= 100
        and threshold_by_family[family]["threshold"] < 1.0
        for family in conformal_required
    )
    test_conformal_coverage = audit_conformal_coverage(
        test_examples, calibration,
    )
    conformal_coverage_passed = all(
        test_metrics.get(family, {}).get("instances", 0) >= 100
        and test_conformal_coverage.get(family, 0.0) >= 0.99
        for family in conformal_required
    )
    gate = bool(
        all(row["passed"] for row in recall_gate_results.values())
        and oracle_capacity_gate_feasible
        and nonvacuous and conformal_coverage_passed
    )
    report = {
        "schema": "pcdc-proposal-large-training/v2-honest-top5",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if gate else "failed", "gate_pass": gate,
        "device": str(device), "epochs": total_epochs,
        "model_config": asdict(config),
        "tiny_overfit_preflight": str(
            args.tiny_overfit_preflight.resolve()
        ),
        "tiny_overfit_preflight_sha256": hashlib.sha256(
            args.tiny_overfit_preflight.read_bytes()
        ).hexdigest(),
        "tiny_overfit_preflight_best_text_recall_at_5": (
            tiny_overfit_preflight["best_text_line_recall_at_5"]
        ),
        "v14_readiness_report": str(args.readiness_report.resolve()),
        "v14_readiness_report_sha256": hashlib.sha256(
            args.readiness_report.read_bytes()
        ).hexdigest(),
        "v14_readiness_compiler_source_sha256": readiness[
            "compiler_source_sha256"
        ],
        "continuation_epochs": args.epochs,
        "resumed_from": resumed_from,
        "initialized_from": initialized_from,
        "elapsed_seconds": time.perf_counter() - started,
        "pair_root": str(args.pair_root.resolve()), "pair_count": len(rows),
        "raw_pair_count": len(raw_rows),
        "rejected_pair_count": len(rejected_pairs),
        "rejected_pairs": list(rejected_pairs),
        "source_disjoint": True, "split_counts": split_counts,
        "training_sources_sha256": source_digest,
        "training_rows_sha256": row_digest,
        "training_data_contract_sha256": training_data_contract_sha256,
        "corpus_data_contract_sha256": corpus_data_contract_sha256,
        "filter_cache": (
            str(args.filter_cache.resolve()) if args.filter_cache is not None
            else None
        ),
        "filter_cache_sha256": (
            hashlib.sha256(args.filter_cache.read_bytes()).hexdigest()
            if args.filter_cache is not None else None
        ),
        "mixed_corpus_attestation_sha256": (
            hashlib.sha256(mixed_report_path.read_bytes()).hexdigest()
            if mixed_report is not None else None
        ),
        "requested_replay_shares": requested_replay_shares,
        "expected_replay_shares": expected_replay_shares,
        "expected_structure_family_shares": expected_structure_family_shares,
        "split_source_counts": {name: len(value) for name, value in split_source_sets.items()},
        "split_group_counts": {name: len(value) for name, value in split_group_sets.items()},
        "family_counts": dict(family_counts), "loss_history": history,
        "selection_history": selection_history,
        "checkpoint_selection_contract": (
            "calibration-min-normalized-required-Recall@5/v1"
        ),
        "checkpoint_selection_key": payload.get("calibration_selection_key"),
        "calibration_neural_only": calibration_metrics,
        "test_neural_only": test_metrics,
        "required_recall_slices": required,
        "recall_gate_results": recall_gate_results,
        "minimum_required_recall": minimum_recall,
        "minimum_recall_gate": args.minimum_recall,
        "oracle_capacity_gate_feasible": oracle_capacity_gate_feasible,
        "conformal_thresholds": thresholds, "conformal_nonvacuous": nonvacuous,
        "conformal_admission_contract": (
            "exact-family-prefix-rank/support-IoU>=0.50/v1"
        ),
        "conformal_required_families": conformal_required,
        "test_conformal_coverage_by_family": test_conformal_coverage,
        "conformal_coverage_gate_passed": conformal_coverage_passed,
        "evaluation_contract": {
            "neural_only": True,
            "query_ranking": "global-top-k-across-families",
            "instance_matching": "one-to-one-Hungarian-within-family",
            "promotion_metric": "Recall@5 IoU>=0.50",
            "oracle_capacity_audit": (
                "global min(5,target-count) and individual-family top5 ceiling"
            ),
            "glyph_group_target": "whole-group-not-per-component",
        },
        "label_contract": {
            "version": LABEL_CONTRACT_VERSION,
            "source_sha256": label_contract_sha256,
            "split_grouping": (
                "open-font-family/icon-library/local-asset-family/"
                "typed-structure-source/otherwise-source-asset"
            ),
            "semantic_scene_labels": "conservative-explicit-cues-only",
            "compound_svg_owner_factory": (
                "exact named SVG text-row owners plus one compound glyph union; "
                "heuristic local-owner fallback; both projected by recorded "
                "augmentation and registered to observed support"
            ),
            "typed_structure_factory": (
                "typed-generator/v2 exact family and masked relation supervision "
                "for stroke/appearance/layer/repeat-or-mirror"
            ),
            "unobservable_pair_policy": (
                "exclude-unobservable/invalid/unaligned-before-source-disjoint-"
                "split-and-report-reason"
            ),
            "small_shape_factory": "deterministic-source-disjoint-procedural-recomposition",
            "support_lattice": (
                f"{(args.image_size // 4) * args.mask_upsample}x"
                f"{(args.image_size // 4) * args.mask_upsample} "
                "conservative-digital-preimage"
            ),
            "generic_parameters_supervised": args.parameter_dim,
            "hard_negative_head_supervised": True,
            "hard_negative_semantic_applicability": (
                "family/degradation-bound; canonical serialized program render/v1"
            ),
            "unknown_relation_policy": (
                "mask-unobserved; never coerce missing semantic labels to false"
            ),
            "ranking_objective": (
                "target-weighted-positive-slot-adjusted-global-Recall@5-margin"
            ),
            "positive_weighting": (
                "risk=1.0 (explicit degradation replay),small-shape=x3,"
                "text/glyph=1.50,sparse-text-support(<1.5%)=x3; "
                "foreground balance cap=128; "
                "same-family instance exclusivity+mask+bbox+global-top5-rank"
            ),
            "loss_version": "recall-k-instance-exclusive-roi-soft-iou/v5",
            "text_bbox_gate_padding": config.text_bbox_gate_padding,
            "text_bbox_gate_vertical_only": (
                config.text_bbox_gate_vertical_only
            ),
            "training_sampler": (
                "deterministic-gate-balanced-replacement/v1; "
                "legacy scarcity weights: small-shape=3.0,text/glyph=1.65,"
                "layer=1.50,stroke=48,symmetry=12,appearance=4,cap=64; "
                "balanced synthetic-structure-v2 uses an equal family prior; "
                "degraded=1.20; fixed source mass after within-source balancing"
            ),
        },
        "checkpoint": str(args.checkpoint.resolve()),
        "latest_checkpoint": str(latest_checkpoint.resolve()),
        "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        "promotion_policy": (
            "candidate only; runtime promotion requires neural-only held-out gate, "
            "non-vacuous calibration and downstream full PCDC ablation"
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    progress({
        "status": "complete", "epoch": total_epochs, "epochs": total_epochs,
        "gate_pass": gate, "report": str(args.report.resolve()),
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-root", type=Path, default=DEFAULT_PAIR_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--latest-checkpoint", type=Path)
    checkpoint_mode = parser.add_mutually_exclusive_group()
    checkpoint_mode.add_argument(
        "--resume", type=Path,
        help="continue from a v2-large checkpoint with the same config/split",
    )
    checkpoint_mode.add_argument(
        "--initialize", type=Path,
        help=(
            "load v2-large model weights but reset epoch/optimizer and bind "
            "the new checkpoint to the current label contract"
        ),
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--progress", type=Path,
        default=PROJECT / "benchmarks" / "pcdc_proposal_large" / "progress.json",
    )
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--image-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--query-count", type=int, default=32)
    parser.add_argument("--decoder-layers", type=int, default=3)
    parser.add_argument("--parameter-dim", type=int, default=16)
    parser.add_argument("--mask-upsample", type=int, choices=(1, 2), default=1)
    parser.add_argument(
        "--spatial-positioning", action="store_true",
        help=(
            "add explicit 2-D coordinates to decoder memory and query masks "
            "so repeated instances can be separated by location"
        ),
    )
    parser.add_argument(
        "--text-bbox-gate-padding", type=float, default=0.0,
        help=(
            "restrict predicted TextLine soft support to its own ROI plus "
            "this normalized padding"
        ),
    )
    parser.add_argument(
        "--text-bbox-gate-vertical-only", action="store_true",
        help="gate TextLine support by its predicted vertical span only",
    )
    parser.add_argument("--lr", type=float, default=8e-4)
    parser.add_argument("--minimum-recall", type=float, default=0.97)
    parser.add_argument(
        "--filter-cache", type=Path,
        help="hash-bound accepted/rejected preflight cache for this corpus",
    )
    parser.add_argument(
        "--readiness-report", type=Path,
        help="hash-bound all-gates TRAIN/NO-TRAIN report",
    )
    parser.add_argument(
        "--tiny-overfit-preflight", type=Path,
        help="hash-bound passing train-only instance-learning preflight",
    )
    parser.add_argument(
        "--open-text-replay-share", type=float, default=0.0,
        help="expected training-sampler mass reserved for synthetic-open-text",
    )
    parser.add_argument(
        "--structure-replay-share", type=float, default=0.0,
        help="expected sampler mass reserved for synthetic-structure-v2",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--seed", type=int, default=20260721)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    report = train(args)
    if not args.quiet:
        print(json.dumps({
            "status": report["status"], "checkpoint": report["checkpoint"],
            "report": str(args.report.resolve()),
        }, indent=2), flush=True)


if __name__ == "__main__":
    main()

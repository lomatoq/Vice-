"""Preflight and train the manifest-bound font-free glyph prior."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader

from .build_identity import bind_report, compiler_source_sha256
from .glyph_prior import (
    GLYPH_CHARACTER_SHA256,
    GLYPH_CHARACTERS,
    GlyphPriorConfig,
    GlyphPriorNet,
    checkpoint_payload,
    glyph_prior_contract_compatibility,
    glyph_prior_source_sha256,
    topology_constrained_support,
    topology_signature,
)
from .glyph_prior_data import (
    TOPOLOGY_ENRICHED_CHARACTERS,
    OpenFontGlyphDataset,
    load_font_records,
    sample_digest,
    split_font_families,
)

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT / "fonts" / "google-fonts-manifest.json"
DEFAULT_FONT_ROOT = PROJECT / "fonts" / "google-fonts"
DEFAULT_CHECKPOINT = PROJECT / "models" / "glyph_prior_candidate_v1.pt"
DEFAULT_REPORT = PROJECT / "benchmarks" / "pcdc_pre_v14" / "glyph_prior_training.json"
DEFAULT_PREFLIGHT = PROJECT / "benchmarks" / "pcdc_pre_v14" / "glyph_prior_preflight.json"
CANONICAL_MINIMUM_TOPOLOGY_ACCURACY = 0.97
CANONICAL_MINIMUM_SUPPORT_IOU = 0.90
CANONICAL_MINIMUM_HARD_TOPOLOGY_ACCURACY = 0.95
CANONICAL_MINIMUM_HARD_SUPPORT_IOU = 0.88
CANONICAL_MINIMUM_PRIOR_TOPOLOGY_ACCURACY = 0.90
CANONICAL_MINIMUM_PRIOR_SUPPORT_IOU = 0.82
CANONICAL_MINIMUM_PRIOR_HARD_TOPOLOGY_ACCURACY = 0.88
CANONICAL_MINIMUM_PRIOR_HARD_SUPPORT_IOU = 0.78
CANONICAL_MINIMUM_SEVERE_TOPOLOGY_ACCURACY = 0.88
CANONICAL_MINIMUM_SEVERE_SUPPORT_IOU = 0.80
CANONICAL_MINIMUM_PRIOR_SEVERE_TOPOLOGY_ACCURACY = 0.80
CANONICAL_MINIMUM_PRIOR_SEVERE_SUPPORT_IOU = 0.70
CANONICAL_MINIMUM_TOPOLOGY_CORRUPTION_FRACTION = 0.65
CANONICAL_MINIMUM_SEVERE_TOPOLOGY_CORRUPTION_FRACTION = 0.18
CANONICAL_PREFLIGHT_SAMPLES_PER_SPLIT = 2_048
CANONICAL_MINIMUM_TRAINING_VARIANTS = 2_000_000
CANONICAL_MINIMUM_HELD_OUT_SAMPLES = 20_000
CANONICAL_MINIMUM_IMAGE_SIZE = 64
CANONICAL_MINIMUM_BASE_CHANNELS = 24
CANONICAL_MINIMUM_CHARACTER_EMBEDDING = 16
CANONICAL_MAXIMUM_EPOCH_LR_DECAY = 0.5
CANONICAL_TOPOLOGY_ENRICHMENT_PROBABILITY = 0.25
SUPPORT_THRESHOLD_GRID = tuple(
    round(0.35 + 0.025 * index, 3) for index in range(19)
)


def _balanced_cross_entropy(
    logits: torch.Tensor, targets: torch.Tensor,
) -> torch.Tensor:
    """Batch-balanced exact-label loss with bounded rare-class leverage."""
    counts = torch.bincount(targets, minlength=logits.shape[1]).to(logits.dtype)
    present = counts > 0
    maximum = counts.max().clamp_min(1.0)
    weights = torch.zeros_like(counts)
    weights[present] = torch.sqrt(maximum / counts[present]).clamp(max=4.0)
    return F.cross_entropy(logits, targets, weight=weights)


def _dense_prediction_loss(
    support_logits: torch.Tensor, sdf_prediction: torch.Tensor,
    skeleton_logits: torch.Tensor, batch: dict, device: torch.device,
) -> torch.Tensor:
    support = batch["support"].to(device)
    sdf = batch["sdf"].to(device)
    skeleton = batch["skeleton"].to(device)
    support_bce = F.binary_cross_entropy_with_logits(
        support_logits, support, reduction="none",
    )
    support_positive = support.sum(dim=(-2, -1), keepdim=True).clamp_min(1.0)
    support_negative = (1.0 - support).sum(dim=(-2, -1), keepdim=True)
    support_weight = torch.clamp(support_negative / support_positive, 1.0, 8.0)
    support_bce = support_bce * (1.0 + support * (support_weight - 1.0))
    # Topology failures happen at the threshold-scale boundary.  Give those
    # pixels extra weight without changing the average loss scale per sample.
    boundary_weight = 1.0 + 1.5 * torch.exp(-12.0 * torch.abs(sdf))
    boundary_weight = boundary_weight / boundary_weight.mean(
        dim=(-2, -1), keepdim=True,
    ).clamp_min(1e-6)
    support_bce = torch.mean(support_bce * boundary_weight)
    support_probability = torch.sigmoid(support_logits)
    dice = 1.0 - torch.mean(
        (2.0 * torch.sum(support_probability * support, dim=(-2, -1)) + 1.0)
        / (
            torch.sum(support_probability, dim=(-2, -1))
            + torch.sum(support, dim=(-2, -1)) + 1.0
        )
    )
    intersection = torch.sum(support_probability * support, dim=(-2, -1))
    union = (
        torch.sum(support_probability, dim=(-2, -1))
        + torch.sum(support, dim=(-2, -1)) - intersection
    )
    soft_iou = 1.0 - torch.mean((intersection + 1.0) / (union + 1.0))
    skeleton_bce = F.binary_cross_entropy_with_logits(
        skeleton_logits, skeleton, reduction="none",
    )
    skeleton_positive = skeleton.sum(dim=(-2, -1), keepdim=True).clamp_min(1.0)
    skeleton_negative = (1.0 - skeleton).sum(dim=(-2, -1), keepdim=True)
    skeleton_weight = torch.clamp(
        skeleton_negative / skeleton_positive, 1.0, 16.0,
    )
    skeleton_bce = torch.mean(
        skeleton_bce * (1.0 + skeleton * (skeleton_weight - 1.0))
    )
    return (
        support_bce + 0.45 * dice + 0.45 * soft_iou
        + 0.25 * F.smooth_l1_loss(sdf_prediction, sdf)
        + 0.10 * skeleton_bce
    )


def _loss(output: dict[str, torch.Tensor], batch: dict, device: torch.device) -> torch.Tensor:
    components = batch["components"].to(device)
    holes = batch["holes"].to(device)
    fused_dense = _dense_prediction_loss(
        output["support_logits"], output["sdf"],
        output["skeleton_logits"], batch, device,
    )
    # Train the low-frequency character/style generator as an independently
    # useful decoder.  Without this auxiliary objective the observation U-Net
    # can cancel an empty prior and achieve excellent synthetic metrics while
    # contributing zero real proposals at serving time.
    prior_dense = _dense_prediction_loss(
        output["prior_support_logits"], output["prior_sdf"],
        output["prior_skeleton_logits"], batch, device,
    )
    return (
        fused_dense + 0.75 * prior_dense
        + 0.65 * _balanced_cross_entropy(
            output["component_logits"], components,
        )
        + 0.65 * _balanced_cross_entropy(output["hole_logits"], holes)
    )


def _batch_to_model(
    batch: dict, device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    return (
        batch["observed"].to(device), batch["character_id"].to(device),
        batch["components"].to(device), batch["holes"].to(device),
    )


def _evaluate(
    model: GlyphPriorNet, loader: DataLoader, device: torch.device,
    *, support_threshold: float = 0.5,
) -> dict:
    intersections = unions = samples = 0
    prior_intersections = prior_unions = prior_mask_topology_correct = 0
    correct_mask_topology = correct_head_topology = correct_joint_topology = 0
    topology_samples: Counter[str] = Counter()
    topology_mask_correct: Counter[str] = Counter()
    topology_head_correct: Counter[str] = Counter()
    topology_joint_correct: Counter[str] = Counter()
    topology_decode_failures = topology_threshold_adjustments = 0
    decoded_threshold_total = 0.0
    corruption_samples: Counter[str] = Counter()
    corruption_intersections: Counter[str] = Counter()
    corruption_unions: Counter[str] = Counter()
    corruption_joint_correct: Counter[str] = Counter()
    hard_samples = hard_intersections = hard_unions = hard_joint_correct = 0
    prior_hard_intersections = prior_hard_unions = prior_hard_correct = 0
    severe_samples = severe_intersections = severe_unions = severe_correct = 0
    prior_severe_intersections = prior_severe_unions = prior_severe_correct = 0
    loss_total = 0.0
    model.eval()
    with torch.inference_mode():
        for batch in loader:
            model_inputs = _batch_to_model(batch, device)
            characters = model_inputs[1]
            output = model(*model_inputs)
            loss_total += float(_loss(output, batch, device)) * len(characters)
            probability_cpu = torch.sigmoid(
                output["support_logits"]
            )[:, 0].detach().cpu().numpy()
            prior_probability_cpu = torch.sigmoid(
                output["prior_support_logits"]
            )[:, 0].detach().cpu().numpy()
            expected_cpu = tuple(zip(
                batch["components"].tolist(), batch["holes"].tolist(),
            ))
            decoded = [
                topology_constrained_support(
                    probability, (int(components), int(holes)),
                    float(support_threshold),
                )
                for probability, (components, holes) in zip(
                    probability_cpu, expected_cpu,
                )
            ]
            prior_decoded = [
                topology_constrained_support(
                    probability, (int(components), int(holes)),
                    float(support_threshold),
                )
                for probability, (components, holes) in zip(
                    prior_probability_cpu, expected_cpu,
                )
            ]
            predicted_cpu = np.stack([row[0] for row in decoded], axis=0)
            prior_predicted_cpu = np.stack(
                [row[0] for row in prior_decoded], axis=0,
            )
            decoded_threshold_total += sum(row[1] for row in decoded)
            topology_threshold_adjustments += sum(
                abs(row[1] - float(support_threshold)) > 1e-12
                for row in decoded
            )
            topology_decode_failures += sum(not row[2] for row in decoded)
            predicted = torch.from_numpy(
                predicted_cpu[:, None]
            ).to(device=device, dtype=torch.bool)
            prior_predicted = torch.from_numpy(
                prior_predicted_cpu[:, None]
            ).to(device=device, dtype=torch.bool)
            target = batch["support"].to(device) >= 0.5
            intersections += int(torch.sum(predicted & target))
            unions += int(torch.sum(predicted | target))
            prior_intersections += int(torch.sum(prior_predicted & target))
            prior_unions += int(torch.sum(prior_predicted | target))
            predicted_components = torch.argmax(output["component_logits"], dim=1)
            predicted_holes = torch.argmax(output["hole_logits"], dim=1)
            target_components = batch["components"].to(device)
            target_holes = batch["holes"].to(device)
            head_correct = (
                (predicted_components == target_components)
                & (predicted_holes == target_holes)
            )
            mask_correct = torch.tensor([
                topology_signature(mask) == (int(components), int(holes))
                for mask, (components, holes) in zip(
                    predicted_cpu, expected_cpu,
                )
            ], device=device, dtype=torch.bool)
            prior_mask_correct = torch.tensor([
                topology_signature(mask) == (int(components), int(holes))
                for mask, (components, holes) in zip(
                    prior_predicted_cpu, expected_cpu,
                )
            ], device=device, dtype=torch.bool)
            mask_correct_cpu = mask_correct.detach().cpu().tolist()
            head_correct_cpu = head_correct.detach().cpu().tolist()
            target_cpu = target[:, 0].detach().cpu().numpy()
            profiles = batch.get("corruption_profile")
            if profiles is None:
                profiles = ["unspecified"] * len(predicted_cpu)
            hard_flags = batch.get("topology_corrupted")
            if hard_flags is None:
                hard_flags = [False] * len(predicted_cpu)
            elif torch.is_tensor(hard_flags):
                hard_flags = hard_flags.detach().cpu().tolist()
            severity = batch.get("topology_corruption_distance")
            if severity is None:
                severity = [0] * len(predicted_cpu)
            elif torch.is_tensor(severity):
                severity = severity.detach().cpu().tolist()
            for topology, mask_ok, head_ok in zip(
                expected_cpu, mask_correct_cpu, head_correct_cpu,
            ):
                key = f"{int(topology[0])}:{int(topology[1])}"
                topology_samples[key] += 1
                topology_mask_correct[key] += int(mask_ok)
                topology_head_correct[key] += int(head_ok)
                topology_joint_correct[key] += int(mask_ok and head_ok)
            prior_mask_correct_cpu = prior_mask_correct.detach().cpu().tolist()
            for prediction, prior_prediction, truth, profile, hard, distance, mask_ok, head_ok, prior_ok in zip(
                predicted_cpu, prior_predicted_cpu, target_cpu, profiles,
                hard_flags, severity, mask_correct_cpu, head_correct_cpu,
                prior_mask_correct_cpu,
            ):
                profile = str(profile)
                intersection = int(np.sum(prediction & truth))
                union = int(np.sum(prediction | truth))
                corruption_samples[profile] += 1
                corruption_intersections[profile] += intersection
                corruption_unions[profile] += union
                corruption_joint_correct[profile] += int(mask_ok and head_ok)
                if bool(hard):
                    hard_samples += 1
                    hard_intersections += intersection
                    hard_unions += union
                    hard_joint_correct += int(mask_ok and head_ok)
                    prior_hard_intersections += int(
                        np.sum(prior_prediction & truth)
                    )
                    prior_hard_unions += int(
                        np.sum(prior_prediction | truth)
                    )
                    prior_hard_correct += int(prior_ok)
                if int(distance) >= 2:
                    severe_samples += 1
                    severe_intersections += intersection
                    severe_unions += union
                    severe_correct += int(mask_ok and head_ok)
                    prior_severe_intersections += int(
                        np.sum(prior_prediction & truth)
                    )
                    prior_severe_unions += int(
                        np.sum(prior_prediction | truth)
                    )
                    prior_severe_correct += int(prior_ok)
            correct_mask_topology += int(torch.sum(mask_correct))
            prior_mask_topology_correct += int(torch.sum(prior_mask_correct))
            correct_head_topology += int(torch.sum(head_correct))
            correct_joint_topology += int(torch.sum(mask_correct & head_correct))
            samples += len(characters)
    per_topology = {
        key: {
            "samples": count,
            "mask_topology_accuracy": topology_mask_correct[key] / count,
            "topology_head_accuracy": topology_head_correct[key] / count,
            "topology_accuracy": topology_joint_correct[key] / count,
        }
        for key, count in sorted(topology_samples.items())
    }
    per_corruption_profile = {
        key: {
            "samples": count,
            "topology_accuracy": corruption_joint_correct[key] / count,
            "support_iou": (
                corruption_intersections[key]
                / max(1, corruption_unions[key])
            ),
        }
        for key, count in sorted(corruption_samples.items())
    }
    return {
        "samples": samples,
        "loss": loss_total / max(1, samples),
        "support_iou": intersections / max(1, unions),
        "prior_support_iou": prior_intersections / max(1, prior_unions),
        "prior_topology_accuracy": (
            prior_mask_topology_correct / max(1, samples)
        ),
        # This primary metric is the runtime admission contract: both the
        # decoded support and the auxiliary topology head must agree exactly
        # with the clean glyph's components/counters.  Reporting only the
        # easy classification head previously allowed visibly broken masks to
        # pass a nominal 97% gate.
        "topology_accuracy": correct_joint_topology / max(1, samples),
        "mask_topology_accuracy": correct_mask_topology / max(1, samples),
        "topology_head_accuracy": correct_head_topology / max(1, samples),
        "support_threshold": float(support_threshold),
        "mean_decoded_threshold": decoded_threshold_total / max(1, samples),
        "topology_threshold_adjustment_fraction": (
            topology_threshold_adjustments / max(1, samples)
        ),
        "topology_decode_failures": topology_decode_failures,
        "topology_corrupted_samples": hard_samples,
        "topology_corruption_fraction": hard_samples / max(1, samples),
        "hard_topology_accuracy": hard_joint_correct / max(1, hard_samples),
        "hard_support_iou": hard_intersections / max(1, hard_unions),
        "prior_hard_topology_accuracy": (
            prior_hard_correct / max(1, hard_samples)
        ),
        "prior_hard_support_iou": (
            prior_hard_intersections / max(1, prior_hard_unions)
        ),
        "severe_topology_samples": severe_samples,
        "severe_topology_fraction": severe_samples / max(1, samples),
        "severe_topology_accuracy": severe_correct / max(1, severe_samples),
        "severe_support_iou": severe_intersections / max(1, severe_unions),
        "prior_severe_topology_accuracy": (
            prior_severe_correct / max(1, severe_samples)
        ),
        "prior_severe_support_iou": (
            prior_severe_intersections / max(1, prior_severe_unions)
        ),
        "per_topology": per_topology,
        "per_corruption_profile": per_corruption_profile,
    }


def _support_iou_sweep(
    model: GlyphPriorNet, loader: DataLoader, device: torch.device,
    thresholds: tuple[float, ...] = SUPPORT_THRESHOLD_GRID,
) -> dict[float, float]:
    totals = {float(threshold): [0, 0] for threshold in thresholds}
    model.eval()
    with torch.inference_mode():
        for batch in loader:
            model_inputs = _batch_to_model(batch, device)
            probability = torch.sigmoid(
                model(*model_inputs)["support_logits"]
            )
            target = batch["support"].to(device) >= 0.5
            for threshold in thresholds:
                predicted = probability >= float(threshold)
                row = totals[float(threshold)]
                row[0] += int(torch.sum(predicted & target))
                row[1] += int(torch.sum(predicted | target))
    return {
        threshold: intersection / max(1, union)
        for threshold, (intersection, union) in totals.items()
    }


def _calibrate_support_threshold(
    model: GlyphPriorNet, loader: DataLoader, device: torch.device,
    *, minimum_topology: float, minimum_support_iou: float,
) -> dict:
    """Choose support cutoff on calibration only; test remains untouched."""
    sweep = _support_iou_sweep(model, loader, device)
    candidates = {
        threshold for threshold, _iou in sorted(
            sweep.items(), key=lambda row: (row[1], -abs(row[0] - 0.5)),
            reverse=True,
        )[:3]
    }
    candidates.add(0.5)
    rows = [
        _evaluate(model, loader, device, support_threshold=threshold)
        for threshold in sorted(candidates)
    ]
    selected = max(rows, key=lambda metrics: _checkpoint_selection_key(
        metrics, minimum_topology=minimum_topology,
        minimum_support_iou=minimum_support_iou,
    ))
    selected["threshold_iou_sweep"] = {
        f"{threshold:.3f}": iou for threshold, iou in sorted(sweep.items())
    }
    selected["evaluated_thresholds"] = sorted(candidates)
    return selected


def _checkpoint_selection_key(
    metrics: dict, *, minimum_topology: float, minimum_support_iou: float,
) -> tuple[float, ...]:
    """Prefer the checkpoint closest to satisfying its weakest hard gate."""
    topology = float(metrics["topology_accuracy"])
    support_iou = float(metrics["support_iou"])
    hard_topology = float(metrics.get("hard_topology_accuracy", topology))
    hard_support_iou = float(metrics.get("hard_support_iou", support_iou))
    prior_topology = float(metrics.get("prior_topology_accuracy", topology))
    prior_support_iou = float(metrics.get("prior_support_iou", support_iou))
    prior_hard_topology = float(metrics.get(
        "prior_hard_topology_accuracy", hard_topology,
    ))
    prior_hard_support_iou = float(metrics.get(
        "prior_hard_support_iou", hard_support_iou,
    ))
    severe_topology = float(metrics.get(
        "severe_topology_accuracy", hard_topology,
    ))
    severe_support_iou = float(metrics.get(
        "severe_support_iou", hard_support_iou,
    ))
    prior_severe_topology = float(metrics.get(
        "prior_severe_topology_accuracy", prior_hard_topology,
    ))
    prior_severe_support_iou = float(metrics.get(
        "prior_severe_support_iou", prior_hard_support_iou,
    ))
    weakest = min(
        topology / max(1e-12, float(minimum_topology)),
        support_iou / max(1e-12, float(minimum_support_iou)),
        hard_topology / CANONICAL_MINIMUM_HARD_TOPOLOGY_ACCURACY,
        hard_support_iou / CANONICAL_MINIMUM_HARD_SUPPORT_IOU,
        prior_topology / CANONICAL_MINIMUM_PRIOR_TOPOLOGY_ACCURACY,
        prior_support_iou / CANONICAL_MINIMUM_PRIOR_SUPPORT_IOU,
        prior_hard_topology
            / CANONICAL_MINIMUM_PRIOR_HARD_TOPOLOGY_ACCURACY,
        prior_hard_support_iou
            / CANONICAL_MINIMUM_PRIOR_HARD_SUPPORT_IOU,
        severe_topology / CANONICAL_MINIMUM_SEVERE_TOPOLOGY_ACCURACY,
        severe_support_iou / CANONICAL_MINIMUM_SEVERE_SUPPORT_IOU,
        prior_severe_topology
            / CANONICAL_MINIMUM_PRIOR_SEVERE_TOPOLOGY_ACCURACY,
        prior_severe_support_iou
            / CANONICAL_MINIMUM_PRIOR_SEVERE_SUPPORT_IOU,
    )
    return (
        weakest, prior_severe_topology, prior_severe_support_iou,
        severe_topology, severe_support_iou,
        prior_hard_topology, prior_hard_support_iou,
        prior_topology, prior_support_iou,
        hard_topology, hard_support_iou, topology, support_iou,
    )


def _contract(
    manifest: dict, split, config: GlyphPriorConfig,
) -> dict:
    return {
        "font_manifest_sha256": manifest["content_sha256"],
        "font_count": manifest["font_count"],
        "family_count": manifest["family_count"],
        "family_split_sha256": split.digest,
        "family_assignment": [list(row) for row in split.family_assignment],
        "config": asdict(config),
        "training_topology_enrichment": {
            "characters": TOPOLOGY_ENRICHED_CHARACTERS,
            "probability": CANONICAL_TOPOLOGY_ENRICHMENT_PROBABILITY,
            "calibration_and_test_probability": 0.0,
        },
        "topology_corruption_gate": {
            "minimum_fraction": (
                CANONICAL_MINIMUM_TOPOLOGY_CORRUPTION_FRACTION
            ),
            "minimum_severe_fraction": (
                CANONICAL_MINIMUM_SEVERE_TOPOLOGY_CORRUPTION_FRACTION
            ),
            "minimum_hard_topology_accuracy": (
                CANONICAL_MINIMUM_HARD_TOPOLOGY_ACCURACY
            ),
            "minimum_hard_support_iou": CANONICAL_MINIMUM_HARD_SUPPORT_IOU,
            "minimum_prior_topology_accuracy": (
                CANONICAL_MINIMUM_PRIOR_TOPOLOGY_ACCURACY
            ),
            "minimum_prior_support_iou": CANONICAL_MINIMUM_PRIOR_SUPPORT_IOU,
            "minimum_prior_hard_topology_accuracy": (
                CANONICAL_MINIMUM_PRIOR_HARD_TOPOLOGY_ACCURACY
            ),
            "minimum_prior_hard_support_iou": (
                CANONICAL_MINIMUM_PRIOR_HARD_SUPPORT_IOU
            ),
            "minimum_severe_topology_accuracy": (
                CANONICAL_MINIMUM_SEVERE_TOPOLOGY_ACCURACY
            ),
            "minimum_severe_support_iou": (
                CANONICAL_MINIMUM_SEVERE_SUPPORT_IOU
            ),
            "minimum_prior_severe_topology_accuracy": (
                CANONICAL_MINIMUM_PRIOR_SEVERE_TOPOLOGY_ACCURACY
            ),
            "minimum_prior_severe_support_iou": (
                CANONICAL_MINIMUM_PRIOR_SEVERE_SUPPORT_IOU
            ),
        },
        "glyph_prior_source_sha256": glyph_prior_source_sha256(),
        "compiler_source_sha256": compiler_source_sha256(),
    }


def _training_contract_sha256(args: argparse.Namespace) -> str:
    payload = {
        "schema": "pcdc-glyph-prior-training-contract/v1",
        "seed": int(args.seed),
        "samples_per_epoch": int(args.samples_per_epoch),
        "validation_samples": int(args.validation_samples),
        "batch_size": int(args.batch_size),
        "learning_rate": float(args.lr),
        "epoch_learning_rate_decay": float(args.epoch_lr_decay),
        "learning_rate_schedule": "base_lr*epoch_decay**(absolute_epoch-1)",
        "optimizer": "AdamW(weight_decay=1e-4,clip_grad_norm=5)",
        "sample_schedule": "sha256(seed,epoch,index);uniform-font-family/v1",
        "topology_enrichment_probability": (
            CANONICAL_TOPOLOGY_ENRICHMENT_PROBABILITY
        ),
    }
    digest = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
    ).encode("ascii"))
    digest.update(Path(__file__).read_bytes())
    return digest.hexdigest()


def _audit_preflight_dataset(dataset: OpenFontGlyphDataset) -> dict:
    characters: Counter[str] = Counter()
    families: Counter[str] = Counter()
    topologies: Counter[str] = Counter()
    corruption_profiles: Counter[str] = Counter()
    digests = set()
    finite_and_bounded = True
    degradation_delta = 0.0
    topology_corrupted = 0
    severe_topology_corrupted = 0
    topology_distance_total = 0
    for index in range(len(dataset)):
        sample = dataset[index]
        observed = sample["observed"].numpy()
        support = sample["support"].numpy()
        finite_and_bounded = bool(
            finite_and_bounded
            and np.isfinite(observed).all()
            and np.isfinite(support).all()
            and float(observed.min()) >= 0.0
            and float(observed.max()) <= 1.0
            and observed.shape == (3, dataset.image_size, dataset.image_size)
            and support.shape == (1, dataset.image_size, dataset.image_size)
        )
        character = str(sample["character"])
        family = str(sample["family"])
        components = int(sample["components"])
        holes = int(sample["holes"])
        characters[character] += 1
        families[family] += 1
        topologies[f"{components}:{holes}"] += 1
        corruption_profiles[str(sample["corruption_profile"])] += 1
        topology_corrupted += int(bool(sample["topology_corrupted"]))
        topology_distance = int(sample["topology_corruption_distance"])
        topology_distance_total += topology_distance
        severe_topology_corrupted += int(topology_distance >= 2)
        digests.add(sample_digest(sample))
        degradation_delta += float(np.mean(np.abs(
            support[0] - observed[0],
        )))
        if not (
            0 < components < 6 and 0 <= holes < 5
        ):
            finite_and_bounded = False
    family_min = min(families.values(), default=0)
    family_max = max(families.values(), default=0)
    return {
        "samples": len(dataset),
        "character_counts": dict(sorted(characters.items())),
        "family_counts": dict(sorted(families.items())),
        "topology_counts": dict(sorted(topologies.items())),
        "corruption_profile_counts": dict(sorted(corruption_profiles.items())),
        "topology_corruption_fraction": topology_corrupted / max(1, len(dataset)),
        "severe_topology_corruption_fraction": (
            severe_topology_corrupted / max(1, len(dataset))
        ),
        "mean_topology_corruption_distance": (
            topology_distance_total / max(1, len(dataset))
        ),
        "character_coverage": len(characters) / len(GLYPH_CHARACTERS),
        "family_coverage": len(families) / len(dataset.family_records),
        "family_max_min_ratio": family_max / max(1, family_min),
        "unique_sample_digests": len(digests),
        "all_samples_unique": len(digests) == len(dataset),
        "finite_bounded_shapes_and_labels": finite_and_bounded,
        "mean_degradation_delta": degradation_delta / max(1, len(dataset)),
    }


def run_preflight(args: argparse.Namespace) -> dict:
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    records, manifest = load_font_records(
        args.manifest, font_root=args.font_root, verify_bytes=True,
    )
    split = split_font_families(records, seed=args.seed)
    config = GlyphPriorConfig(
        image_size=args.image_size, base_channels=args.base_channels,
        character_embedding_dim=args.character_embedding_dim,
    )
    config.validate()
    audit_samples = max(
        CANONICAL_PREFLIGHT_SAMPLES_PER_SPLIT, int(args.preflight_samples),
    )
    audit_datasets = {
        "train": OpenFontGlyphDataset(
            split.train, samples=audit_samples,
            image_size=config.image_size, seed=args.seed,
            topology_enrichment_probability=(
                CANONICAL_TOPOLOGY_ENRICHMENT_PROBABILITY
            ),
        ),
        "calibration": OpenFontGlyphDataset(
            split.calibration, samples=audit_samples,
            image_size=config.image_size, seed=args.seed + 1,
        ),
        "test": OpenFontGlyphDataset(
            split.test, samples=audit_samples,
            image_size=config.image_size, seed=args.seed + 2,
        ),
    }
    audits = {
        name: _audit_preflight_dataset(dataset)
        for name, dataset in audit_datasets.items()
    }
    dataset = audit_datasets["train"]
    first = dataset[0]
    repeated = dataset[0]
    deterministic = sample_digest(first) == sample_digest(repeated)
    target = first["support"].numpy()[0]
    observed = first["observed"].numpy()[0]
    degradation_distinct = float(np.mean(np.abs(target - observed))) >= 0.01
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GlyphPriorNet(config).to(device)
    loader = DataLoader(dataset, batch_size=min(4, len(dataset)), shuffle=False)
    batch = next(iter(loader))
    model_inputs = _batch_to_model(batch, device)
    output = model(*model_inputs)
    finite_forward = all(bool(torch.isfinite(value).all()) for value in output.values())
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    before = float(_loss(output, batch, device).detach())
    optimizer.zero_grad(set_to_none=True)
    _loss(output, batch, device).backward()
    finite_gradients = all(
        parameter.grad is None or bool(torch.isfinite(parameter.grad).all())
        for parameter in model.parameters()
    )
    optimizer.step()
    after_output = model(*model_inputs)
    after = float(_loss(after_output, batch, device))
    finite_step = math.isfinite(after)
    contract = _contract(manifest, split, config)
    gate = bool(
        deterministic and degradation_distinct and finite_forward
        and finite_gradients and finite_step
        and all(
            row["samples"] >= CANONICAL_PREFLIGHT_SAMPLES_PER_SPLIT
            and row["character_coverage"] == 1.0
            and row["family_coverage"] >= 0.90
            and row["family_max_min_ratio"] <= 3.5
            and row["all_samples_unique"]
            and row["finite_bounded_shapes_and_labels"]
            and row["mean_degradation_delta"] >= 0.01
            and row["topology_corruption_fraction"]
                >= CANONICAL_MINIMUM_TOPOLOGY_CORRUPTION_FRACTION
            and row["severe_topology_corruption_fraction"]
                >= CANONICAL_MINIMUM_SEVERE_TOPOLOGY_CORRUPTION_FRACTION
            and len(row["corruption_profile_counts"]) >= 4
            for row in audits.values()
        )
    )
    report = bind_report({
        "schema": "pcdc-glyph-prior-preflight/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if gate else "failed",
        "gate_pass": gate,
        "contract": contract,
        "checks": {
            "license_manifest_valid": True,
            "family_splits_disjoint": True,
            "all_splits_nonempty": True,
            "deterministic_sample": deterministic,
            "degradation_target_distinct": degradation_distinct,
            "finite_forward": finite_forward,
            "finite_gradients": finite_gradients,
            "finite_optimizer_step": finite_step,
            "canonical_samples_per_split": (
                CANONICAL_PREFLIGHT_SAMPLES_PER_SPLIT
            ),
        },
        "data_audit": audits,
        "tiny_step": {"loss_before": before, "loss_after": after},
        "split_font_counts": {
            name: len(getattr(split, name))
            for name in ("train", "calibration", "test")
        },
        "split_family_counts": {
            name: len({row.family for row in getattr(split, name)})
            for name in ("train", "calibration", "test")
        },
        "sample_sha256": sample_digest(first),
        "training_authorized": False,
        "reason": (
            "preflight proves data/model mechanics only; full training still "
            "requires an explicitly supplied current hash-bound report"
        ),
    })
    args.preflight_out.parent.mkdir(parents=True, exist_ok=True)
    args.preflight_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8",
    )
    return report


def _validate_preflight(path: Path, contract: dict) -> dict:
    report = json.loads(path.read_text("utf-8"))
    if (
        report.get("schema") != "pcdc-glyph-prior-preflight/v1"
        or report.get("gate_pass") is not True
        or report.get("status") != "passed"
    ):
        raise RuntimeError("glyph-prior preflight is absent or failed")
    if report.get("contract") != contract:
        raise RuntimeError("glyph-prior preflight belongs to another source/data/config")
    if report.get("compiler_source_sha256") != compiler_source_sha256():
        raise RuntimeError("glyph-prior preflight is stale after compiler edits")
    audits = report.get("data_audit", {})
    if not all(
        isinstance(audits.get(name), dict)
        and int(audits[name].get("samples", 0))
        >= CANONICAL_PREFLIGHT_SAMPLES_PER_SPLIT
        for name in ("train", "calibration", "test")
    ):
        raise RuntimeError("glyph-prior preflight did not audit every family split")
    return report


def train(args: argparse.Namespace) -> dict:
    if (
        args.epochs <= 0 or args.samples_per_epoch <= 0
        or args.validation_samples < CANONICAL_MINIMUM_HELD_OUT_SAMPLES
        or args.image_size < CANONICAL_MINIMUM_IMAGE_SIZE
        or args.base_channels < CANONICAL_MINIMUM_BASE_CHANNELS
        or args.character_embedding_dim
        < CANONICAL_MINIMUM_CHARACTER_EMBEDDING
        or args.batch_size <= 0 or args.workers < 0
        or not 0.0 < args.epoch_lr_decay <= CANONICAL_MAXIMUM_EPOCH_LR_DECAY
    ):
        raise RuntimeError(
            "glyph-prior training is below the canonical data/model floor"
        )
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    records, manifest = load_font_records(
        args.manifest, font_root=args.font_root, verify_bytes=True,
    )
    split = split_font_families(records, seed=args.seed)
    config = GlyphPriorConfig(
        image_size=args.image_size, base_channels=args.base_channels,
        character_embedding_dim=args.character_embedding_dim,
    )
    contract = _contract(manifest, split, config)
    if args.preflight_report is None:
        raise RuntimeError("refusing glyph-prior training without --preflight-report")
    _validate_preflight(args.preflight_report, contract)
    datasets = {
        "train": OpenFontGlyphDataset(
            split.train, samples=args.samples_per_epoch,
            image_size=config.image_size, seed=args.seed,
            topology_enrichment_probability=(
                CANONICAL_TOPOLOGY_ENRICHMENT_PROBABILITY
            ),
        ),
        "calibration": OpenFontGlyphDataset(
            split.calibration, samples=args.validation_samples,
            image_size=config.image_size, seed=args.seed + 1,
        ),
        "test": OpenFontGlyphDataset(
            split.test, samples=args.validation_samples,
            image_size=config.image_size, seed=args.seed + 2,
        ),
    }
    loaders = {
        name: DataLoader(
            dataset, batch_size=args.batch_size,
            # Samples are already a SHA-256 permutation.  Keeping index order
            # makes resume deterministic; set_epoch supplies fresh variants.
            shuffle=False, num_workers=args.workers,
            persistent_workers=False,
            pin_memory=torch.cuda.is_available(),
        )
        for name, dataset in datasets.items()
    }
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GlyphPriorNet(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    training_contract_sha256 = _training_contract_sha256(args)
    start_epoch = 0
    if args.resume is not None:
        payload = torch.load(args.resume, map_location=device, weights_only=False)
        if payload.get("schema") != "pcdc-glyph-prior-checkpoint/v1":
            raise RuntimeError("unsupported glyph-prior resume checkpoint")
        if glyph_prior_contract_compatibility(
            payload.get("model_contract_sha256")
        ) is None:
            raise RuntimeError("glyph-prior resume model/data contract is stale")
        if payload.get("config") != asdict(config):
            raise RuntimeError("glyph-prior resume config mismatch")
        if payload.get("font_manifest_sha256") != manifest["content_sha256"]:
            raise RuntimeError("glyph-prior resume manifest mismatch")
        if payload.get("family_split_sha256") != split.digest:
            raise RuntimeError("glyph-prior resume family split mismatch")
        if payload.get("training_contract_sha256") != training_contract_sha256:
            raise RuntimeError("glyph-prior resume training contract mismatch")
        model.load_state_dict(payload["model"], strict=True)
        optimizer.load_state_dict(payload["optimizer"])
        start_epoch = int(payload["epoch"])
    final_epoch = start_epoch + int(args.epochs)
    planned_variants = final_epoch * int(args.samples_per_epoch)
    if planned_variants < CANONICAL_MINIMUM_TRAINING_VARIANTS:
        raise RuntimeError(
            "glyph-prior training must expose at least "
            f"{CANONICAL_MINIMUM_TRAINING_VARIANTS} deterministic variants"
        )
    minimum_topology = max(
        CANONICAL_MINIMUM_TOPOLOGY_ACCURACY,
        float(args.minimum_topology_accuracy),
    )
    minimum_support_iou = max(
        CANONICAL_MINIMUM_SUPPORT_IOU, float(args.minimum_support_iou),
    )
    best_key = (-1.0,) * 13
    history = []
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    working_checkpoint = args.checkpoint.with_suffix(
        args.checkpoint.suffix + ".training",
    )
    for epoch in range(start_epoch + 1, start_epoch + args.epochs + 1):
        datasets["train"].set_epoch(epoch)
        epoch_learning_rate = float(args.lr) * (
            float(args.epoch_lr_decay) ** (epoch - 1)
        )
        for parameter_group in optimizer.param_groups:
            parameter_group["lr"] = epoch_learning_rate
        model.train()
        running = samples = 0
        total_batches = len(loaders["train"])
        progress_interval = max(1, total_batches // 20)
        print(
            f"[glyph-prior] epoch {epoch}/{start_epoch + args.epochs} "
            f"started ({len(datasets['train'])} variants; "
            f"lr={epoch_learning_rate:.8f})",
            flush=True,
        )
        for batch_index, batch in enumerate(loaders["train"], start=1):
            model_inputs = _batch_to_model(batch, device)
            characters = model_inputs[1]
            optimizer.zero_grad(set_to_none=True)
            loss = _loss(model(*model_inputs), batch, device)
            if not bool(torch.isfinite(loss)):
                raise RuntimeError("glyph-prior training loss became non-finite")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            running += float(loss) * len(characters)
            samples += len(characters)
            if batch_index % progress_interval == 0 or batch_index == total_batches:
                print(
                    f"[glyph-prior] epoch {epoch} "
                    f"{batch_index}/{total_batches} "
                    f"loss={running / max(1, samples):.6f}",
                    flush=True,
                )
        calibration = _calibrate_support_threshold(
            model, loaders["calibration"], device,
            minimum_topology=minimum_topology,
            minimum_support_iou=minimum_support_iou,
        )
        key = _checkpoint_selection_key(
            calibration, minimum_topology=minimum_topology,
            minimum_support_iou=minimum_support_iou,
        )
        history.append({
            "epoch": epoch, "training_loss": running / max(1, samples),
            "learning_rate": epoch_learning_rate,
            "calibration": calibration,
        })
        print(
            "[glyph-prior] calibration "
            f"topology={calibration['topology_accuracy']:.6f} "
            f"mask-topology={calibration['mask_topology_accuracy']:.6f} "
            f"support-iou={calibration['support_iou']:.6f} "
            f"hard-topology={calibration['hard_topology_accuracy']:.6f} "
            f"hard-iou={calibration['hard_support_iou']:.6f} "
            f"prior-topology={calibration['prior_topology_accuracy']:.6f} "
            f"prior-iou={calibration['prior_support_iou']:.6f} "
            f"prior-hard-topology="
            f"{calibration['prior_hard_topology_accuracy']:.6f} "
            f"prior-hard-iou={calibration['prior_hard_support_iou']:.6f} "
            f"severe-topology={calibration['severe_topology_accuracy']:.6f} "
            f"severe-iou={calibration['severe_support_iou']:.6f} "
            f"prior-severe-topology="
            f"{calibration['prior_severe_topology_accuracy']:.6f} "
            f"prior-severe-iou="
            f"{calibration['prior_severe_support_iou']:.6f} "
            f"threshold={calibration['support_threshold']:.3f}",
            flush=True,
        )
        eligible_variants = epoch * int(args.samples_per_epoch)
        if (
            eligible_variants >= CANONICAL_MINIMUM_TRAINING_VARIANTS
            and key > best_key
        ):
            best_key = key
            torch.save(checkpoint_payload(
                model, epoch=epoch,
                manifest_sha256=manifest["content_sha256"],
                split_sha256=split.digest, selection_key=key,
                training_contract_sha256=training_contract_sha256,
                optimizer=optimizer,
                support_threshold=float(calibration["support_threshold"]),
            ), working_checkpoint)
    payload = torch.load(
        working_checkpoint, map_location=device, weights_only=False,
    )
    model.load_state_dict(payload["model"], strict=True)
    test = _evaluate(
        model, loaders["test"], device,
        support_threshold=float(payload.get("support_threshold", 0.5)),
    )
    gate = bool(
        test["topology_accuracy"] >= minimum_topology
        and test["support_iou"] >= minimum_support_iou
        and test["hard_topology_accuracy"]
            >= CANONICAL_MINIMUM_HARD_TOPOLOGY_ACCURACY
        and test["hard_support_iou"] >= CANONICAL_MINIMUM_HARD_SUPPORT_IOU
        and test["prior_topology_accuracy"]
            >= CANONICAL_MINIMUM_PRIOR_TOPOLOGY_ACCURACY
        and test["prior_support_iou"] >= CANONICAL_MINIMUM_PRIOR_SUPPORT_IOU
        and test["prior_hard_topology_accuracy"]
            >= CANONICAL_MINIMUM_PRIOR_HARD_TOPOLOGY_ACCURACY
        and test["prior_hard_support_iou"]
            >= CANONICAL_MINIMUM_PRIOR_HARD_SUPPORT_IOU
        and test["severe_topology_accuracy"]
            >= CANONICAL_MINIMUM_SEVERE_TOPOLOGY_ACCURACY
        and test["severe_support_iou"]
            >= CANONICAL_MINIMUM_SEVERE_SUPPORT_IOU
        and test["prior_severe_topology_accuracy"]
            >= CANONICAL_MINIMUM_PRIOR_SEVERE_TOPOLOGY_ACCURACY
        and test["prior_severe_support_iou"]
            >= CANONICAL_MINIMUM_PRIOR_SEVERE_SUPPORT_IOU
        and test["severe_topology_fraction"]
            >= CANONICAL_MINIMUM_SEVERE_TOPOLOGY_CORRUPTION_FRACTION
        and test["topology_corruption_fraction"]
            >= CANONICAL_MINIMUM_TOPOLOGY_CORRUPTION_FRACTION
        and int(payload["epoch"]) * int(args.samples_per_epoch)
        >= CANONICAL_MINIMUM_TRAINING_VARIANTS
    )
    final_checkpoint = (
        args.checkpoint
        if gate else args.checkpoint.with_name(
            args.checkpoint.stem + "_failed" + args.checkpoint.suffix,
        )
    )
    working_checkpoint.replace(final_checkpoint)
    report = bind_report({
        "schema": "pcdc-glyph-prior-training/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "candidate-passed" if gate else "candidate-failed",
        "gate_pass": gate,
        "contract": contract,
        "training_contract_sha256": training_contract_sha256,
        "epochs": history,
        "held_out_test": test,
        "selected_epoch": int(payload["epoch"]),
        "training_variants": int(payload["epoch"]) * int(args.samples_per_epoch),
        "total_training_variants": final_epoch * int(args.samples_per_epoch),
        "held_out_samples_per_split": int(args.validation_samples),
        "minimum_topology_accuracy": minimum_topology,
        "minimum_support_iou": minimum_support_iou,
        "minimum_prior_topology_accuracy": (
            CANONICAL_MINIMUM_PRIOR_TOPOLOGY_ACCURACY
        ),
        "minimum_prior_support_iou": CANONICAL_MINIMUM_PRIOR_SUPPORT_IOU,
        "minimum_prior_hard_topology_accuracy": (
            CANONICAL_MINIMUM_PRIOR_HARD_TOPOLOGY_ACCURACY
        ),
        "minimum_prior_hard_support_iou": (
            CANONICAL_MINIMUM_PRIOR_HARD_SUPPORT_IOU
        ),
        "minimum_severe_topology_accuracy": (
            CANONICAL_MINIMUM_SEVERE_TOPOLOGY_ACCURACY
        ),
        "minimum_severe_support_iou": CANONICAL_MINIMUM_SEVERE_SUPPORT_IOU,
        "minimum_prior_severe_topology_accuracy": (
            CANONICAL_MINIMUM_PRIOR_SEVERE_TOPOLOGY_ACCURACY
        ),
        "minimum_prior_severe_support_iou": (
            CANONICAL_MINIMUM_PRIOR_SEVERE_SUPPORT_IOU
        ),
        "requested_minimum_topology_accuracy": args.minimum_topology_accuracy,
        "requested_minimum_support_iou": args.minimum_support_iou,
        "checkpoint": str(final_checkpoint.resolve()),
        "checkpoint_sha256": hashlib.sha256(
            final_checkpoint.read_bytes(),
        ).hexdigest(),
        "promotion_policy": (
            "candidate only; promotion additionally requires Experiment 4 "
            "line-level GCR, zero reviewed-line topology regression and warm p95"
        ),
    })
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8")
    return report


def reevaluate_trained_checkpoint(args: argparse.Namespace) -> dict:
    """Re-evaluate compatible trained weights after deterministic decoding edits."""
    if args.preflight_report is None or args.source_training_report is None:
        raise RuntimeError(
            "decoder re-evaluation requires --preflight-report and "
            "--source-training-report"
        )
    source_path = args.reevaluate_checkpoint.resolve()
    source_report_path = args.source_training_report.resolve()
    source_report = json.loads(source_report_path.read_text("utf-8"))
    source_checkpoint_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if (
        source_report.get("schema") != "pcdc-glyph-prior-training/v1"
        or source_report.get("checkpoint_sha256") != source_checkpoint_sha
        or int(source_report.get("training_variants", 0))
        < CANONICAL_MINIMUM_TRAINING_VARIANTS
        or int(source_report.get("held_out_samples_per_split", 0))
        < CANONICAL_MINIMUM_HELD_OUT_SAMPLES
    ):
        raise RuntimeError("source glyph-prior training proof is invalid")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    records, manifest = load_font_records(
        args.manifest, font_root=args.font_root, verify_bytes=True,
    )
    split = split_font_families(records, seed=args.seed)
    payload = torch.load(source_path, map_location="cpu", weights_only=False)
    if (
        payload.get("schema") != "pcdc-glyph-prior-checkpoint/v1"
        or payload.get("character_vocab_sha256") != GLYPH_CHARACTER_SHA256
        or payload.get("font_manifest_sha256") != manifest["content_sha256"]
        or payload.get("family_split_sha256") != split.digest
        or int(payload.get("epoch", 0))
        != int(source_report.get("selected_epoch", -1))
    ):
        raise RuntimeError("source glyph-prior checkpoint proof is invalid")
    config = GlyphPriorConfig(**dict(payload.get("config", {})))
    contract = _contract(manifest, split, config)
    _validate_preflight(args.preflight_report, contract)
    source_contract = source_report.get("contract", {})
    for key in ("font_manifest_sha256", "family_split_sha256", "config"):
        if source_contract.get(key) != contract.get(key):
            raise RuntimeError(
                f"source glyph-prior training contract changed at {key}"
            )
    validation_samples = max(
        CANONICAL_MINIMUM_HELD_OUT_SAMPLES, int(args.validation_samples),
    )
    datasets = {
        "calibration": OpenFontGlyphDataset(
            split.calibration, samples=validation_samples,
            image_size=config.image_size, seed=args.seed + 1,
        ),
        "test": OpenFontGlyphDataset(
            split.test, samples=validation_samples,
            image_size=config.image_size, seed=args.seed + 2,
        ),
    }
    loaders = {
        name: DataLoader(
            dataset, batch_size=args.batch_size, shuffle=False,
            num_workers=args.workers, persistent_workers=False,
            pin_memory=torch.cuda.is_available(),
        )
        for name, dataset in datasets.items()
    }
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GlyphPriorNet(config).to(device)
    # Strict state loading is the migration proof: only deterministic decoding
    # changed; every learned tensor and architecture surface is identical.
    model.load_state_dict(payload["model"], strict=True)
    minimum_topology = max(
        CANONICAL_MINIMUM_TOPOLOGY_ACCURACY,
        float(args.minimum_topology_accuracy),
    )
    minimum_support_iou = max(
        CANONICAL_MINIMUM_SUPPORT_IOU, float(args.minimum_support_iou),
    )
    calibration = _calibrate_support_threshold(
        model, loaders["calibration"], device,
        minimum_topology=minimum_topology,
        minimum_support_iou=minimum_support_iou,
    )
    test = _evaluate(
        model, loaders["test"], device,
        support_threshold=float(calibration["support_threshold"]),
    )
    gate = bool(
        calibration["topology_accuracy"] >= minimum_topology
        and calibration["support_iou"] >= minimum_support_iou
        and calibration["hard_topology_accuracy"]
            >= CANONICAL_MINIMUM_HARD_TOPOLOGY_ACCURACY
        and calibration["hard_support_iou"]
            >= CANONICAL_MINIMUM_HARD_SUPPORT_IOU
        and calibration["prior_topology_accuracy"]
            >= CANONICAL_MINIMUM_PRIOR_TOPOLOGY_ACCURACY
        and calibration["prior_support_iou"]
            >= CANONICAL_MINIMUM_PRIOR_SUPPORT_IOU
        and calibration["prior_hard_topology_accuracy"]
            >= CANONICAL_MINIMUM_PRIOR_HARD_TOPOLOGY_ACCURACY
        and calibration["prior_hard_support_iou"]
            >= CANONICAL_MINIMUM_PRIOR_HARD_SUPPORT_IOU
        and calibration["severe_topology_accuracy"]
            >= CANONICAL_MINIMUM_SEVERE_TOPOLOGY_ACCURACY
        and calibration["severe_support_iou"]
            >= CANONICAL_MINIMUM_SEVERE_SUPPORT_IOU
        and calibration["prior_severe_topology_accuracy"]
            >= CANONICAL_MINIMUM_PRIOR_SEVERE_TOPOLOGY_ACCURACY
        and calibration["prior_severe_support_iou"]
            >= CANONICAL_MINIMUM_PRIOR_SEVERE_SUPPORT_IOU
        and test["topology_accuracy"] >= minimum_topology
        and test["support_iou"] >= minimum_support_iou
        and test["hard_topology_accuracy"]
            >= CANONICAL_MINIMUM_HARD_TOPOLOGY_ACCURACY
        and test["hard_support_iou"] >= CANONICAL_MINIMUM_HARD_SUPPORT_IOU
        and test["prior_topology_accuracy"]
            >= CANONICAL_MINIMUM_PRIOR_TOPOLOGY_ACCURACY
        and test["prior_support_iou"] >= CANONICAL_MINIMUM_PRIOR_SUPPORT_IOU
        and test["prior_hard_topology_accuracy"]
            >= CANONICAL_MINIMUM_PRIOR_HARD_TOPOLOGY_ACCURACY
        and test["prior_hard_support_iou"]
            >= CANONICAL_MINIMUM_PRIOR_HARD_SUPPORT_IOU
        and test["severe_topology_accuracy"]
            >= CANONICAL_MINIMUM_SEVERE_TOPOLOGY_ACCURACY
        and test["severe_support_iou"]
            >= CANONICAL_MINIMUM_SEVERE_SUPPORT_IOU
        and test["prior_severe_topology_accuracy"]
            >= CANONICAL_MINIMUM_PRIOR_SEVERE_TOPOLOGY_ACCURACY
        and test["prior_severe_support_iou"]
            >= CANONICAL_MINIMUM_PRIOR_SEVERE_SUPPORT_IOU
    )
    selection_key = _checkpoint_selection_key(
        calibration, minimum_topology=minimum_topology,
        minimum_support_iou=minimum_support_iou,
    )
    migrated = checkpoint_payload(
        model, epoch=int(payload["epoch"]),
        manifest_sha256=manifest["content_sha256"],
        split_sha256=split.digest, selection_key=selection_key,
        training_contract_sha256=payload.get("training_contract_sha256"),
        support_threshold=float(calibration["support_threshold"]),
    )
    final_checkpoint = (
        args.checkpoint if gate else args.checkpoint.with_name(
            args.checkpoint.stem + "_decoded_failed" + args.checkpoint.suffix,
        )
    )
    final_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(migrated, final_checkpoint)
    report = bind_report({
        "schema": "pcdc-glyph-prior-training/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "candidate-passed" if gate else "candidate-failed",
        "gate_pass": gate,
        "contract": contract,
        "training_contract_sha256": payload.get("training_contract_sha256"),
        "epochs": source_report.get("epochs", []),
        "decoder_reevaluation": {
            "calibration": calibration,
            "source_checkpoint": str(source_path),
            "source_checkpoint_sha256": source_checkpoint_sha,
            "source_model_contract_sha256": payload.get(
                "model_contract_sha256"
            ),
            "current_model_contract_sha256": glyph_prior_source_sha256(),
            "strict_state_dict_compatible": True,
            "source_training_report": str(source_report_path),
            "source_training_report_sha256": hashlib.sha256(
                source_report_path.read_bytes()
            ).hexdigest(),
        },
        "held_out_test": test,
        "selected_epoch": int(payload["epoch"]),
        "training_variants": int(source_report["training_variants"]),
        "total_training_variants": int(source_report.get(
            "total_training_variants", source_report["training_variants"],
        )),
        "held_out_samples_per_split": validation_samples,
        "minimum_topology_accuracy": minimum_topology,
        "minimum_support_iou": minimum_support_iou,
        "requested_minimum_topology_accuracy": (
            args.minimum_topology_accuracy
        ),
        "requested_minimum_support_iou": args.minimum_support_iou,
        "checkpoint": str(final_checkpoint.resolve()),
        "checkpoint_sha256": hashlib.sha256(
            final_checkpoint.read_bytes()
        ).hexdigest(),
        "promotion_policy": (
            "candidate only; promotion additionally requires Experiment 4 "
            "line-level GCR, zero reviewed-line topology regression and warm p95"
        ),
    })
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--font-root", type=Path, default=DEFAULT_FONT_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--reevaluate-checkpoint", type=Path)
    parser.add_argument("--source-training-report", type=Path)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--preflight-report", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--preflight-out", type=Path,
                        default=DEFAULT_PREFLIGHT)
    parser.add_argument(
        "--preflight-samples", type=int,
        default=CANONICAL_PREFLIGHT_SAMPLES_PER_SPLIT,
    )
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--samples-per-epoch", type=int, default=500_000)
    parser.add_argument("--validation-samples", type=int, default=20_000)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--image-size", type=int, default=64)
    parser.add_argument("--base-channels", type=int, default=24)
    parser.add_argument("--character-embedding-dim", type=int, default=16)
    parser.add_argument("--lr", type=float, default=8e-4)
    parser.add_argument("--epoch-lr-decay", type=float, default=0.5)
    parser.add_argument("--minimum-topology-accuracy", type=float, default=0.97)
    parser.add_argument("--minimum-support-iou", type=float, default=0.90)
    parser.add_argument("--seed", type=int, default=20260722)
    args = parser.parse_args()
    if args.preflight_only:
        report = run_preflight(args)
    elif args.reevaluate_checkpoint is not None:
        report = reevaluate_trained_checkpoint(args)
    else:
        report = train(args)
    print(json.dumps({
        "schema": report["schema"], "status": report["status"],
        "gate_pass": report["gate_pass"],
    }, indent=2, sort_keys=True))
    if not report["gate_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

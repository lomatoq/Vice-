"""Preflight and train the family-disjoint whole-line wordmark prior."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader

from .build_identity import compiler_source_sha256
from .glyph_prior_data import load_font_records, split_font_families
from .wordmark_prior import (
    TOPOLOGY_REPAIR_MINIMUM_CONFIDENCE, WORDMARK_CHARACTERS,
    WordmarkPriorConfig, WordmarkPriorNet, checkpoint_payload,
    decode_wordmark_support,
    topology_signature, wordmark_prior_source_sha256,
)
from .wordmark_prior_data import OpenFontWordmarkDataset, wordmark_data_recipe


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT / "fonts" / "google-fonts-manifest.json"
DEFAULT_FONT_ROOT = PROJECT / "fonts" / "google-fonts"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def wordmark_trainer_source_sha256() -> str:
    digest = hashlib.sha256(b"pcdc-wordmark-trainer-source/v1\0")
    digest.update(wordmark_prior_source_sha256().encode("ascii"))
    digest.update(b"\0")
    digest.update(Path(__file__).read_bytes())
    return digest.hexdigest()


def _atomic_torch_save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)


def _state_dict_sha256(model: nn.Module) -> str:
    digest = hashlib.sha256(b"pcdc-torch-state/v1\0")
    for name, value in sorted(model.state_dict().items()):
        array = value.detach().cpu().contiguous().numpy()
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(np.asarray(array.shape, np.int64).tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()


def _device(value: str) -> torch.device:
    if value == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(value)


def _configure_training_determinism(seed: int) -> None:
    # Seed alone does not freeze cuDNN/cuBLAS kernel choices.  Configure the
    # process before its first CUDA training operation so a checkpoint recipe
    # means the same computation on repeat runs of the frozen environment.
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.manual_seed(int(seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(seed))
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)


def _training_contract(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema": "pcdc-wordmark-prior-training-contract/v1",
        "seed": int(args.seed), "family_split_seed": int(args.split_seed),
        "unique_training_variants": int(args.training_variants),
        "training_sample_presentations": int(args.training_variants * args.epochs),
        "held_out_samples_per_split": int(args.held_out_samples),
        "epochs": int(args.epochs), "batch_size": int(args.batch_size),
        "evaluation_batch_size": int(args.eval_batch_size),
        "loader_workers": int(args.workers),
        "evaluation_loader_workers": int(args.eval_workers),
        "optimizer": "AdamW", "weight_decay": 1.0e-4,
        "learning_rate": float(args.learning_rate),
        "automatic_mixed_precision": "resolved-at-runtime",
        "deterministic_algorithms": True,
        "cudnn_benchmark": False,
        "cudnn_deterministic": True,
        "cublas_workspace_config": ":4096:8",
        "trainer_source_sha256": wordmark_trainer_source_sha256(),
        "per_epoch_best_snapshot": str((
            args.latest_checkpoint
            or args.checkpoint.with_name(
                f"{args.checkpoint.stem}_latest{args.checkpoint.suffix}"
            )
        ).resolve()) if args.checkpoint is not None else None,
    }


def _loader(
    dataset: OpenFontWordmarkDataset, *, batch_size: int, workers: int,
    persistent_workers: bool = False,
) -> DataLoader:
    return DataLoader(
        dataset, batch_size=batch_size, shuffle=False,
        num_workers=max(0, int(workers)), pin_memory=torch.cuda.is_available(),
        persistent_workers=bool(workers and persistent_workers), drop_last=False,
    )


def _loss(
    output: dict[str, torch.Tensor], batch: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, dict[str, float]]:
    target = batch["support"]
    logits = output["support_logits"]
    positive = torch.clamp(target.mean(), min=1.0e-4, max=1.0 - 1.0e-4)
    pos_weight = torch.clamp((1.0 - positive) / positive, 1.0, 12.0)
    bce = F.binary_cross_entropy_with_logits(
        logits, target, pos_weight=pos_weight,
    )
    probability = torch.sigmoid(logits)
    intersection = torch.sum(probability * target, dim=(1, 2, 3))
    dice = 1.0 - torch.mean(
        (2.0 * intersection + 1.0)
        / (torch.sum(probability, dim=(1, 2, 3))
           + torch.sum(target, dim=(1, 2, 3)) + 1.0)
    )
    sdf = F.smooth_l1_loss(output["sdf"], batch["sdf"], beta=0.10)
    component = _focal_count_loss(
        output["component_logits"], batch["components"],
    )
    holes = _focal_count_loss(output["hole_logits"], batch["holes"])
    component_ordinal = _ordinal_count_loss(
        output["component_logits"], batch["components"],
    )
    hole_ordinal = _ordinal_count_loss(
        output["hole_logits"], batch["holes"],
    )
    total = (
        bce + 0.65 * dice + 0.20 * sdf
        + 0.30 * (component + holes)
        + 0.40 * (component_ordinal + hole_ordinal)
    )
    return total, {
        "bce": float(bce.detach()), "dice": float(dice.detach()),
        "sdf": float(sdf.detach()),
        "component_focal": float(component.detach()),
        "hole_focal": float(holes.detach()),
        "component_ordinal": float(component_ordinal.detach()),
        "hole_ordinal": float(hole_ordinal.detach()),
    }


def _focal_count_loss(
    logits: torch.Tensor, target: torch.Tensor, *, gamma: float = 1.5,
) -> torch.Tensor:
    log_probability = F.log_softmax(logits, dim=1)
    negative_log_likelihood = F.nll_loss(
        log_probability, target, reduction="none",
    )
    target_probability = torch.exp(-negative_log_likelihood)
    return torch.mean(
        torch.pow(1.0 - target_probability, gamma) * negative_log_likelihood,
    )


def _ordinal_count_loss(
    logits: torch.Tensor, target: torch.Tensor,
) -> torch.Tensor:
    probability_cdf = torch.cumsum(torch.softmax(logits, dim=1), dim=1)
    classes = torch.arange(logits.shape[1], device=logits.device)[None, :]
    target_cdf = (classes >= target[:, None]).to(probability_cdf.dtype)
    return torch.mean(torch.abs(probability_cdf - target_cdf))


def _move(batch: dict[str, torch.Tensor], device: torch.device) -> dict[str, torch.Tensor]:
    return {
        key: value.to(device=device, non_blocking=True)
        for key, value in batch.items()
    }


def _iou(reference: np.ndarray, candidate: np.ndarray) -> float:
    intersection = int(np.sum(reference & candidate))
    union = int(np.sum(reference | candidate))
    return intersection / max(1, union)


@torch.inference_mode()
def evaluate(
    model: WordmarkPriorNet, loader: DataLoader, device: torch.device,
    *, thresholds: tuple[float, ...] = (
        0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90,
    ),
    fixed_threshold: float | None = None,
    repair_confidence_thresholds: tuple[float, ...] = (
        0.50, 0.60, 0.70, 0.80, 0.90, 1.01,
    ),
    fixed_repair_confidence_threshold: float | None = None,
) -> dict[str, Any]:
    """Evaluate without retaining the held-out raster corpus in RAM.

    The first deterministic pass calibrates the global threshold.  The second
    pass performs topology-conditioned decoding at that threshold.  A 20k
    held-out split would otherwise retain more than a gigabyte of float maps.
    """
    model.eval()
    evaluated_thresholds = tuple(sorted({
        *(float(threshold) for threshold in thresholds),
        *(() if fixed_threshold is None else (float(fixed_threshold),)),
    }))
    sweep_totals = {
        float(threshold): {
            "iou": 0.0, "topology": 0, "complex_topology": 0,
            "complex_samples": 0,
        }
        for threshold in evaluated_thresholds
    }
    component_correct = hole_correct = joint_correct = samples = 0
    component_top3_correct = hole_top3_correct = 0
    component_absolute_error = hole_absolute_error = 0
    for batch in loader:
        moved = _move(batch, device)
        output = model(
            moved["features"], moved["text_tokens"], moved["text_length"],
        )
        probability = torch.sigmoid(output["support_logits"]).cpu().numpy()[:, 0]
        target = moved["support"].cpu().numpy()[:, 0] >= 0.5
        predicted_components = torch.argmax(
            output["component_logits"], dim=1,
        ).cpu().numpy()
        predicted_holes = torch.argmax(output["hole_logits"], dim=1).cpu().numpy()
        component_top3 = torch.topk(
            output["component_logits"], k=3, dim=1,
        ).indices.cpu().numpy()
        hole_top3 = torch.topk(
            output["hole_logits"], k=3, dim=1,
        ).indices.cpu().numpy()
        true_components = moved["components"].cpu().numpy()
        true_holes = moved["holes"].cpu().numpy()
        component_correct += int(np.sum(predicted_components == true_components))
        hole_correct += int(np.sum(predicted_holes == true_holes))
        joint_correct += int(np.sum(
            (predicted_components == true_components)
            & (predicted_holes == true_holes)
        ))
        component_top3_correct += int(np.sum(
            np.any(component_top3 == true_components[:, None], axis=1)
        ))
        hole_top3_correct += int(np.sum(
            np.any(hole_top3 == true_holes[:, None], axis=1)
        ))
        component_absolute_error += int(np.sum(np.abs(
            predicted_components - true_components,
        )))
        hole_absolute_error += int(np.sum(np.abs(
            predicted_holes - true_holes,
        )))
        samples += len(target)
        for threshold in evaluated_thresholds:
            support = probability >= threshold
            intersection = np.sum(support & target, axis=(1, 2))
            union = np.sum(support | target, axis=(1, 2))
            sweep_totals[threshold]["iou"] += float(
                np.sum(intersection / np.maximum(1, union))
            )
            for index in range(len(target)):
                truth = (
                    int(true_components[index]), int(true_holes[index]),
                )
                matched = topology_signature(support[index]) == truth
                sweep_totals[threshold]["topology"] += int(matched)
                if truth[0] > 1 or truth[1] >= 4:
                    sweep_totals[threshold]["complex_samples"] += 1
                    sweep_totals[threshold]["complex_topology"] += int(matched)
    sweeps: dict[str, dict[str, float]] = {}
    for threshold in evaluated_thresholds:
        totals = sweep_totals[threshold]
        sweeps[f"{threshold:.3f}"] = {
            "support_iou": totals["iou"] / max(1, samples),
            "topology_accuracy": totals["topology"] / max(1, samples),
            "complex_topology_accuracy": (
                totals["complex_topology"]
                / max(1, totals["complex_samples"])
            ),
        }
    if fixed_threshold is None:
        best_threshold, best = max(
            sweeps.items(),
            key=lambda row: (
                row[1]["topology_accuracy"], row[1]["support_iou"], row[0],
            ),
        )
        threshold_policy = "calibrated-on-this-split"
    else:
        best_threshold = f"{float(fixed_threshold):.3f}"
        best = sweeps[best_threshold]
        threshold_policy = "fixed-from-calibration-split"
    preferred_threshold = float(best_threshold)
    evaluated_repair_thresholds = tuple(sorted({
        *(float(value) for value in repair_confidence_thresholds),
        *(
            () if fixed_repair_confidence_threshold is None
            else (float(fixed_repair_confidence_threshold),)
        ),
    }))
    repair_totals = {
        threshold: {
            "iou": 0.0, "topology": 0, "complex_topology": 0,
            "complex_samples": 0, "eligible": 0, "decode_match": 0,
        }
        for threshold in evaluated_repair_thresholds
    }
    failures_by_threshold: dict[float, list[dict[str, Any]]] = {
        threshold: [] for threshold in evaluated_repair_thresholds
    }
    topology_confidences = []
    for batch in loader:
        moved = _move(batch, device)
        output = model(
            moved["features"], moved["text_tokens"], moved["text_length"],
        )
        probability = torch.sigmoid(output["support_logits"]).cpu().numpy()[:, 0]
        target = moved["support"].cpu().numpy()[:, 0] >= 0.5
        component_probability = torch.softmax(
            output["component_logits"], dim=1,
        )
        hole_probability = torch.softmax(output["hole_logits"], dim=1)
        predicted_components = torch.argmax(
            component_probability, dim=1,
        ).cpu().numpy()
        predicted_holes = torch.argmax(hole_probability, dim=1).cpu().numpy()
        component_confidence = torch.amax(
            component_probability, dim=1,
        ).cpu().numpy()
        hole_confidence = torch.amax(hole_probability, dim=1).cpu().numpy()
        true_components = moved["components"].cpu().numpy()
        true_holes = moved["holes"].cpu().numpy()
        for index in range(len(target)):
            predicted = (
                int(predicted_components[index]), int(predicted_holes[index]),
            )
            truth = (int(true_components[index]), int(true_holes[index]))
            topology_confidence = float(min(
                component_confidence[index], hole_confidence[index],
            ))
            topology_confidences.append(topology_confidence)
            raw = probability[index] >= preferred_threshold
            raw_signature = topology_signature(raw)
            decoded = raw
            decoded_signature = raw_signature
            matched = raw_signature == predicted
            if topology_confidence >= TOPOLOGY_REPAIR_MINIMUM_CONFIDENCE:
                decoded, _threshold, matched = decode_wordmark_support(
                    probability[index], expected_topology=predicted,
                    preferred_threshold=preferred_threshold,
                    allow_repair=True,
                )
                decoded_signature = topology_signature(decoded)
            for repair_threshold in evaluated_repair_thresholds:
                use_repair = topology_confidence >= repair_threshold
                selected = decoded if use_repair else raw
                signature = decoded_signature if use_repair else raw_signature
                selected_match = matched if use_repair else raw_signature == predicted
                totals = repair_totals[repair_threshold]
                totals["iou"] += _iou(target[index], selected)
                totals["topology"] += int(signature == truth)
                totals["eligible"] += int(use_repair)
                totals["decode_match"] += int(selected_match)
                complex_sample = truth[0] > 1 or truth[1] >= 4
                totals["complex_samples"] += int(complex_sample)
                totals["complex_topology"] += int(
                    complex_sample and signature == truth
                )
                failures = failures_by_threshold[repair_threshold]
                if signature != truth and len(failures) < 32:
                    failures.append({
                        "predicted_topology": list(predicted),
                        "true_topology": list(truth),
                        "raw_topology": list(raw_signature),
                        "decoded_topology": list(signature),
                        "head_matches_truth": predicted == truth,
                        "decoder_matched_head": bool(selected_match),
                        "topology_head_confidence": topology_confidence,
                        "repair_applied": bool(use_repair),
                        "decoded_iou": _iou(target[index], selected),
                    })
    repair_sweep: dict[str, dict[str, float]] = {}
    for repair_threshold in evaluated_repair_thresholds:
        totals = repair_totals[repair_threshold]
        repair_sweep[f"{repair_threshold:.3f}"] = {
            "decoded_support_iou": totals["iou"] / max(1, samples),
            "decoded_topology_accuracy": totals["topology"] / max(1, samples),
            "decoded_complex_topology_accuracy": (
                totals["complex_topology"]
                / max(1, totals["complex_samples"])
            ),
            "topology_repair_eligible_fraction": (
                totals["eligible"] / max(1, samples)
            ),
            "topology_decode_match_fraction": (
                totals["decode_match"] / max(1, samples)
            ),
        }
    if fixed_repair_confidence_threshold is None:
        best_repair_threshold, decoded_metrics = max(
            repair_sweep.items(),
            key=lambda row: (
                row[1]["decoded_topology_accuracy"],
                row[1]["decoded_complex_topology_accuracy"],
                row[1]["decoded_support_iou"], row[0],
            ),
        )
        repair_threshold_policy = "calibrated-on-this-split"
    else:
        best_repair_threshold = f"{fixed_repair_confidence_threshold:.3f}"
        decoded_metrics = repair_sweep[best_repair_threshold]
        repair_threshold_policy = "fixed-from-calibration-split"
    selected_repair_threshold = float(best_repair_threshold)
    return {
        "samples": samples,
        "support_threshold": float(best_threshold),
        "support_threshold_policy": threshold_policy,
        **best,
        "component_head_accuracy": component_correct / max(1, samples),
        "hole_head_accuracy": hole_correct / max(1, samples),
        "joint_topology_head_accuracy": joint_correct / max(1, samples),
        "component_head_top3_accuracy": (
            component_top3_correct / max(1, samples)
        ),
        "hole_head_top3_accuracy": hole_top3_correct / max(1, samples),
        "component_head_mean_absolute_error": (
            component_absolute_error / max(1, samples)
        ),
        "hole_head_mean_absolute_error": (
            hole_absolute_error / max(1, samples)
        ),
        **decoded_metrics,
        "mean_topology_head_confidence": (
            float(np.mean(topology_confidences))
            if topology_confidences else 0.0
        ),
        "topology_repair_confidence_threshold": selected_repair_threshold,
        "topology_repair_confidence_policy": repair_threshold_policy,
        "topology_repair_minimum_confidence": (
            TOPOLOGY_REPAIR_MINIMUM_CONFIDENCE
        ),
        "decoded_failures": failures_by_threshold[selected_repair_threshold],
        "topology_repair_sweep": repair_sweep,
        "threshold_sweep": sweeps,
    }


def _tiny_overfit(
    fonts: tuple, device: torch.device, *, steps: int, seed: int,
) -> dict[str, Any]:
    _configure_training_determinism(seed)
    config = WordmarkPriorConfig(base_channels=8, text_embedding_dim=16)
    dataset = OpenFontWordmarkDataset(
        fonts[:max(1, min(4, len(fonts)))], sample_count=8,
        seed=seed, config=config,
    )
    loader = _loader(dataset, batch_size=8, workers=0)
    batch = _move(next(iter(loader)), device)
    model = WordmarkPriorNet(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3.0e-3, weight_decay=0.0)
    losses = []
    started = time.perf_counter()
    model.train()
    for _ in range(int(steps)):
        optimizer.zero_grad(set_to_none=True)
        output = model(batch["features"], batch["text_tokens"], batch["text_length"])
        loss, _parts = _loss(output, batch)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
        losses.append(float(loss.detach()))
    measured = evaluate(model, loader, device, thresholds=(0.35, 0.5, 0.65, 0.8))
    result = {
        "steps": int(steps), "initial_loss": losses[0], "final_loss": losses[-1],
        "loss_ratio": losses[-1] / max(1.0e-9, losses[0]),
        "elapsed_seconds": time.perf_counter() - started,
        "loss_trace_sha256": hashlib.sha256(
            np.asarray(losses, np.float64).tobytes()
        ).hexdigest(),
        "final_state_sha256": _state_dict_sha256(model),
        **measured,
    }
    result["passed"] = bool(
        result["loss_ratio"] <= 0.10
        and result["decoded_support_iou"] >= 0.95
        and result["decoded_topology_accuracy"] >= 0.95
        and result["decoded_complex_topology_accuracy"] >= 0.90
        and result["component_head_accuracy"] >= 0.95
        and result["hole_head_accuracy"] >= 0.95
    )
    return result


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    fonts, manifest = load_font_records(
        args.font_manifest, font_root=args.font_root,
    )
    split = split_font_families(fonts, seed=args.split_seed)
    device = _device(args.device)
    sample_dataset = OpenFontWordmarkDataset(
        split.train, sample_count=args.preflight_samples,
        seed=args.seed, config=WordmarkPriorConfig(),
    )
    topology_histogram: dict[str, int] = {}
    deterministic = True
    observed_token_ids: set[int] = set()
    observed_text_lengths: set[int] = set()
    for index in range(len(sample_dataset)):
        first = sample_dataset[index]
        second = sample_dataset[index]
        deterministic &= first.keys() == second.keys() and all(
            torch.equal(first[key], second[key]) for key in first
        )
        key = f"{int(first['components'])}:{int(first['holes'])}"
        topology_histogram[key] = topology_histogram.get(key, 0) + 1
        observed_token_ids.update(
            int(value) for value in first["text_tokens"].tolist()
            if int(value) > 0
        )
        observed_text_lengths.add(int(first["text_length"]))
    tiny = _tiny_overfit(
        split.train, device, steps=args.tiny_overfit_steps, seed=args.seed + 17,
    )
    tiny_repeat = _tiny_overfit(
        split.train, device, steps=args.tiny_overfit_steps, seed=args.seed + 17,
    )
    family_sets = tuple(
        {row.family for row in rows}
        for rows in (split.train, split.calibration, split.test)
    )
    checks = {
        "family_disjoint": all(
            not family_sets[first] & family_sets[second]
            for first, second in ((0, 1), (0, 2), (1, 2))
        ),
        "procedural_determinism": bool(deterministic),
        "serving_vocabulary_fully_covered": observed_token_ids == set(
            range(1, len(WORDMARK_CHARACTERS) + 1)
        ),
        "serving_length_range_fully_covered": observed_text_lengths == set(
            range(1, WordmarkPriorConfig().max_characters + 1)
        ),
        "topology_diversity": len(topology_histogram) >= 12,
        "connected_wordmarks_present": any(
            key.startswith("1:") for key in topology_histogram
        ),
        "high_counter_wordmarks_present": any(
            int(key.split(":", 1)[1]) >= 8 for key in topology_histogram
        ),
        "tiny_overfit": bool(tiny["passed"]),
        "cuda_training_reproducible": bool(
            tiny["loss_trace_sha256"] == tiny_repeat["loss_trace_sha256"]
            and tiny["final_state_sha256"] == tiny_repeat["final_state_sha256"]
        ),
    }
    return {
        "schema": "pcdc-wordmark-prior-preflight/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(checks.values()) else "failed",
        "gate_pass": all(checks.values()), "checks": checks,
        "model_data_contract_sha256": wordmark_prior_source_sha256(),
        "trainer_source_sha256": wordmark_trainer_source_sha256(),
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "family_split_sha256": split.digest,
        "font_families": {
            "train": len({row.family for row in split.train}),
            "calibration": len({row.family for row in split.calibration}),
            "test": len({row.family for row in split.test}),
        },
        "font_faces": {
            "train": len(split.train), "calibration": len(split.calibration),
            "test": len(split.test),
        },
        "data_recipe": wordmark_data_recipe(),
        "sample_count": len(sample_dataset),
        "serving_vocabulary": {
            "characters": WORDMARK_CHARACTERS,
            "covered_token_ids": sorted(observed_token_ids),
            "missing_characters": "".join(
                WORDMARK_CHARACTERS[index - 1]
                for index in range(1, len(WORDMARK_CHARACTERS) + 1)
                if index not in observed_token_ids
            ),
        },
        "observed_text_lengths": sorted(observed_text_lengths),
        "topology_histogram": topology_histogram,
        "tiny_overfit": tiny,
        "tiny_overfit_repeat": tiny_repeat,
        "device": str(device),
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    compiler_hash_at_start = compiler_source_sha256()
    model_data_hash_at_start = wordmark_prior_source_sha256()
    trainer_hash_at_start = wordmark_trainer_source_sha256()
    preflight_report = json.loads(args.preflight_report.read_text("utf-8"))
    if (
        preflight_report.get("schema") != "pcdc-wordmark-prior-preflight/v1"
        or not preflight_report.get("gate_pass")
        or preflight_report.get("model_data_contract_sha256")
        != wordmark_prior_source_sha256()
        or preflight_report.get("trainer_source_sha256")
        != trainer_hash_at_start
    ):
        raise RuntimeError("wordmark prior preflight is missing, failed or stale")
    fonts, manifest = load_font_records(
        args.font_manifest, font_root=args.font_root,
    )
    split = split_font_families(fonts, seed=args.split_seed)
    if preflight_report.get("family_split_sha256") != split.digest:
        raise RuntimeError("wordmark preflight belongs to another family split")
    config = WordmarkPriorConfig(
        base_channels=args.base_channels,
        text_embedding_dim=args.text_embedding_dim,
    )
    training_contract = _training_contract(args)
    device = _device(args.device)
    training_contract["resolved_device"] = str(device)
    training_contract["automatic_mixed_precision"] = device.type == "cuda"
    _configure_training_determinism(args.seed)
    train_dataset = OpenFontWordmarkDataset(
        split.train, sample_count=args.training_variants,
        seed=args.seed, config=config,
    )
    calibration = OpenFontWordmarkDataset(
        split.calibration, sample_count=args.held_out_samples,
        seed=args.seed + 1_000_003, config=config,
    )
    test = OpenFontWordmarkDataset(
        split.test, sample_count=args.held_out_samples,
        seed=args.seed + 2_000_003, config=config,
    )
    train_loader = _loader(
        train_dataset, batch_size=args.batch_size, workers=args.workers,
        persistent_workers=True,
    )
    calibration_loader = _loader(
        calibration, batch_size=args.eval_batch_size,
        workers=args.eval_workers,
    )
    model = WordmarkPriorNet(config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=1.0e-4,
    )
    scaler = torch.amp.GradScaler(
        "cuda", enabled=device.type == "cuda",
    )
    best: tuple[tuple[float, ...], dict[str, Any], dict[str, Any]] | None = None
    latest_checkpoint = (
        args.latest_checkpoint
        or args.checkpoint.with_name(
            f"{args.checkpoint.stem}_latest{args.checkpoint.suffix}"
        )
    )
    epochs = []
    started = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for batch in train_loader:
            moved = _move(batch, device)
            optimizer.zero_grad(set_to_none=True)
            context = (
                torch.autocast(device_type="cuda", dtype=torch.float16)
                if device.type == "cuda" else nullcontext()
            )
            with context:
                output = model(
                    moved["features"], moved["text_tokens"], moved["text_length"],
                )
                loss, _parts = _loss(output, moved)
            if not torch.isfinite(loss):
                raise RuntimeError("wordmark training loss became non-finite")
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach()))
        measured = evaluate(model, calibration_loader, device)
        key = (
            measured["decoded_topology_accuracy"],
            measured["decoded_complex_topology_accuracy"],
            measured["decoded_support_iou"],
        )
        payload = checkpoint_payload(
            model, epoch=epoch,
            font_manifest_sha256=str(manifest["content_sha256"]),
            family_split_sha256=split.digest,
            support_threshold=float(measured["support_threshold"]),
            selection_key=key,
        )
        payload["topology_repair_confidence_threshold"] = float(
            measured["topology_repair_confidence_threshold"]
        )
        if payload["model_data_contract_sha256"] != model_data_hash_at_start:
            raise RuntimeError("wordmark model/data source changed during training")
        payload["training_contract"] = training_contract
        payload["trainer_source_sha256"] = trainer_hash_at_start
        if best is None or key > best[0]:
            best = (key, payload, measured)
        _atomic_torch_save(best[1], latest_checkpoint)
        epochs.append({
            "epoch": epoch, "training_loss": float(np.mean(losses)),
            "calibration": measured,
        })
        print(json.dumps({
            "epoch": epoch, "training_loss": epochs[-1]["training_loss"],
            **{name: measured[name] for name in (
                "decoded_support_iou", "decoded_topology_accuracy",
                "decoded_complex_topology_accuracy",
            )},
            "best_checkpoint": str(latest_checkpoint.resolve()),
        }), flush=True)
    assert best is not None
    model.load_state_dict(best[1]["state_dict"])
    # Release the persistent training pool before the independent held-out test
    # pool is spawned.  On Windows every Torch worker owns hundreds of MB.
    del train_loader, calibration_loader
    gc.collect()
    test_loader = _loader(
        test, batch_size=args.eval_batch_size, workers=args.eval_workers,
    )
    held_out = evaluate(
        model, test_loader, device,
        fixed_threshold=float(best[1]["support_threshold"]),
        fixed_repair_confidence_threshold=float(
            best[1]["topology_repair_confidence_threshold"]
        ),
    )
    if (
        compiler_source_sha256() != compiler_hash_at_start
        or wordmark_prior_source_sha256() != model_data_hash_at_start
        or wordmark_trainer_source_sha256() != trainer_hash_at_start
    ):
        raise RuntimeError("compiler source changed during wordmark training")
    gate = {
        "support_iou": (
            held_out["decoded_support_iou"] >= args.minimum_support_iou
        ),
        "topology_accuracy": (
            held_out["decoded_topology_accuracy"] >= args.minimum_topology_accuracy
        ),
        "complex_topology_accuracy": (
            held_out["decoded_complex_topology_accuracy"]
            >= args.minimum_complex_topology_accuracy
        ),
        "component_head_accuracy": held_out["component_head_accuracy"] >= 0.90,
        "hole_head_accuracy": held_out["hole_head_accuracy"] >= 0.90,
    }
    _atomic_torch_save(best[1], args.checkpoint)
    report = {
        "schema": "pcdc-wordmark-prior-training/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "candidate-passed" if all(gate.values()) else "candidate-failed",
        "gate_pass": all(gate.values()), "gate": gate,
        "model_data_contract_sha256": wordmark_prior_source_sha256(),
        "trainer_source_sha256": trainer_hash_at_start,
        "compiler_source_sha256": compiler_hash_at_start,
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "family_split_sha256": split.digest,
        "config": asdict(config), "epochs": epochs,
        "training_contract": training_contract,
        "data_recipe": wordmark_data_recipe(),
        "font_faces": {
            "train": len(split.train), "calibration": len(split.calibration),
            "test": len(split.test),
        },
        "selected_epoch": int(best[1]["epoch"]),
        "held_out_test": held_out,
        "training_variants": len(train_dataset),
        "training_sample_presentations": len(train_dataset) * args.epochs,
        "held_out_samples_per_split": len(test),
        "elapsed_seconds": time.perf_counter() - started,
        "device": str(device),
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": _sha256(args.checkpoint),
        "promotion_policy": "requires fresh model-OFF/ON Experiment-4 output delta",
    }
    return report


def evaluate_checkpoint(args: argparse.Namespace) -> dict[str, Any]:
    """Re-evaluate an immutable checkpoint with calibration-fixed decoders."""
    if args.checkpoint is None:
        raise RuntimeError("checkpoint evaluation requires --checkpoint")
    device = _device(args.device)
    payload = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    if (
        payload.get("schema") != "pcdc-wordmark-prior-checkpoint/v1"
        or payload.get("model_data_contract_sha256")
        != wordmark_prior_source_sha256()
    ):
        raise RuntimeError("wordmark checkpoint is unsupported or stale")
    fonts, manifest = load_font_records(
        args.font_manifest, font_root=args.font_root,
    )
    split = split_font_families(fonts, seed=args.split_seed)
    if payload.get("family_split_sha256") != split.digest:
        raise RuntimeError("wordmark checkpoint belongs to another family split")
    config = WordmarkPriorConfig(**dict(payload["config"]))
    config.validate()
    model = WordmarkPriorNet(config).to(device)
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()
    calibration = OpenFontWordmarkDataset(
        split.calibration, sample_count=args.held_out_samples,
        seed=args.seed + 1_000_003, config=config,
    )
    test = OpenFontWordmarkDataset(
        split.test, sample_count=args.held_out_samples,
        seed=args.seed + 2_000_003, config=config,
    )
    started = time.perf_counter()
    calibration_metrics = evaluate(model, _loader(
        calibration, batch_size=args.eval_batch_size,
        workers=args.eval_workers,
    ), device)
    test_metrics = evaluate(
        model, _loader(
            test, batch_size=args.eval_batch_size, workers=args.eval_workers,
        ), device,
        fixed_threshold=float(calibration_metrics["support_threshold"]),
        fixed_repair_confidence_threshold=float(
            calibration_metrics["topology_repair_confidence_threshold"]
        ),
    )
    gate = {
        "support_iou": (
            test_metrics["decoded_support_iou"] >= args.minimum_support_iou
        ),
        "topology_accuracy": (
            test_metrics["decoded_topology_accuracy"]
            >= args.minimum_topology_accuracy
        ),
        "complex_topology_accuracy": (
            test_metrics["decoded_complex_topology_accuracy"]
            >= args.minimum_complex_topology_accuracy
        ),
        "component_head_accuracy": (
            test_metrics["component_head_accuracy"] >= 0.90
        ),
        "hole_head_accuracy": test_metrics["hole_head_accuracy"] >= 0.90,
    }
    return {
        "schema": "pcdc-wordmark-prior-evaluation/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "candidate-passed" if all(gate.values()) else "candidate-failed",
        "gate_pass": all(gate.values()), "gate": gate,
        "compiler_source_sha256": compiler_source_sha256(),
        "model_data_contract_sha256": wordmark_prior_source_sha256(),
        "checkpoint_trainer_source_sha256": payload.get(
            "trainer_source_sha256"
        ),
        "evaluation_trainer_source_sha256": wordmark_trainer_source_sha256(),
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "family_split_sha256": split.digest,
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": _sha256(args.checkpoint),
        "checkpoint_epoch": int(payload["epoch"]),
        "checkpoint_training_contract": payload.get("training_contract"),
        "calibration": calibration_metrics, "held_out_test": test_metrics,
        "held_out_samples_per_split": int(args.held_out_samples),
        "elapsed_seconds": time.perf_counter() - started,
        "device": str(device),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--font-root", type=Path, default=DEFAULT_FONT_ROOT)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--latest-checkpoint", type=Path)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--evaluate-only", action="store_true")
    parser.add_argument("--preflight-report", type=Path)
    parser.add_argument("--preflight-samples", type=int, default=256)
    parser.add_argument("--tiny-overfit-steps", type=int, default=1500)
    parser.add_argument("--training-variants", type=int, default=2_000_000)
    parser.add_argument("--held-out-samples", type=int, default=20_000)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=48)
    parser.add_argument("--eval-batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--eval-workers", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=2.0e-4)
    parser.add_argument("--base-channels", type=int, default=24)
    parser.add_argument("--text-embedding-dim", type=int, default=64)
    parser.add_argument("--minimum-support-iou", type=float, default=0.88)
    parser.add_argument("--minimum-topology-accuracy", type=float, default=0.95)
    parser.add_argument(
        "--minimum-complex-topology-accuracy", type=float, default=0.90,
    )
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--split-seed", type=int, default=20260722)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    if args.preflight:
        report = preflight(args)
    elif args.evaluate_only:
        report = evaluate_checkpoint(args)
    else:
        if args.checkpoint is None or args.preflight_report is None:
            parser.error("training requires --checkpoint and --preflight-report")
        report = train(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    print(json.dumps({
        "status": report["status"], "gate_pass": report["gate_pass"],
        "out": str(args.out),
    }, indent=2))
    if not report["gate_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

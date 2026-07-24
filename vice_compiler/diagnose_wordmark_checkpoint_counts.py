"""Decompose wordmark topology-count predictions on a family-disjoint split."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .glyph_prior_data import load_font_records, split_font_families
from .train_wordmark_prior import (
    DEFAULT_FONT_ROOT, DEFAULT_MANIFEST, _device, _length_slice, _loader,
    wordmark_trainer_source_sha256,
)
from .wordmark_prior import (
    WordmarkPriorConfig, WordmarkPriorNet, topology_signature,
    wordmark_prior_source_sha256,
)
from .wordmark_prior_data import OpenFontWordmarkDataset, wordmark_data_recipe


def _empty_totals() -> dict[str, float]:
    return {
        "samples": 0.0, "component": 0.0, "hole": 0.0, "joint": 0.0,
        "component_absolute_error": 0.0, "hole_absolute_error": 0.0,
        "component_signed_error": 0.0, "hole_signed_error": 0.0,
    }


def _add(
    totals: dict[str, float], predicted_components: int,
    predicted_holes: int, true_components: int, true_holes: int,
) -> None:
    totals["samples"] += 1.0
    totals["component"] += float(predicted_components == true_components)
    totals["hole"] += float(predicted_holes == true_holes)
    totals["joint"] += float(
        predicted_components == true_components
        and predicted_holes == true_holes
    )
    component_error = predicted_components - true_components
    hole_error = predicted_holes - true_holes
    totals["component_absolute_error"] += abs(component_error)
    totals["hole_absolute_error"] += abs(hole_error)
    totals["component_signed_error"] += component_error
    totals["hole_signed_error"] += hole_error


def _metrics(totals: dict[str, float]) -> dict[str, float | int]:
    samples = max(1.0, totals["samples"])
    return {
        "samples": int(totals["samples"]),
        "component_accuracy": totals["component"] / samples,
        "hole_accuracy": totals["hole"] / samples,
        "joint_accuracy": totals["joint"] / samples,
        "component_mean_absolute_error": (
            totals["component_absolute_error"] / samples
        ),
        "hole_mean_absolute_error": totals["hole_absolute_error"] / samples,
        "component_mean_signed_error": (
            totals["component_signed_error"] / samples
        ),
        "hole_mean_signed_error": totals["hole_signed_error"] / samples,
    }


@torch.no_grad()
def diagnose(args: argparse.Namespace) -> dict[str, Any]:
    device = _device(args.device)
    payload = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    if (
        payload.get("schema") != "pcdc-wordmark-prior-checkpoint/v1"
        or payload.get("model_data_contract_sha256")
        != wordmark_prior_source_sha256()
    ):
        raise RuntimeError("wordmark checkpoint is unsupported or stale")
    config = WordmarkPriorConfig(**dict(payload["config"]))
    model = WordmarkPriorNet(config).to(device)
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()
    fonts, manifest = load_font_records(
        args.font_manifest, font_root=args.font_root,
    )
    split = split_font_families(fonts, seed=args.split_seed)
    records = getattr(split, args.split)
    dataset = OpenFontWordmarkDataset(
        records, sample_count=args.samples, seed=args.seed, config=config,
    )
    methods = (
        "support_mask", "categorical", "posterior_mean", "posterior_median",
        "continuous", "additive",
    )
    oracle = _empty_totals()
    totals = {name: _empty_totals() for name in methods}
    slices: dict[str, dict[str, dict[str, float]]] = {
        name: {} for name in methods
    }
    conditions: dict[str, dict[str, dict[str, float]]] = {
        name: {} for name in methods
    }
    residuals = []
    for batch in _loader(
        dataset, batch_size=args.batch_size, workers=args.workers,
    ):
        features = batch["features"].to(device)
        tokens = batch["text_tokens"].to(device)
        lengths = batch["text_length"].to(device)
        output = model(features, tokens, lengths)
        support_probability = torch.sigmoid(
            output["support_logits"],
        ).cpu().numpy()[:, 0]
        classes = torch.arange(
            config.topology_classes, device=device, dtype=torch.float32,
        )[None, :]
        component_probability = torch.softmax(
            output["component_logits"].float(), dim=1,
        )
        hole_probability = torch.softmax(
            output["hole_logits"].float(), dim=1,
        )
        categorical = torch.stack((
            torch.argmax(output["component_logits"], dim=1),
            torch.argmax(output["hole_logits"], dim=1),
        ), dim=1)
        posterior_mean = torch.round(torch.stack((
            torch.sum(component_probability * classes, dim=1),
            torch.sum(hole_probability * classes, dim=1),
        ), dim=1)).to(torch.long)
        posterior_median = torch.stack((
            torch.argmax(
                (torch.cumsum(component_probability, dim=1) >= 0.5)
                .to(torch.int8),
                dim=1,
            ),
            torch.argmax(
                (torch.cumsum(hole_probability, dim=1) >= 0.5)
                .to(torch.int8),
                dim=1,
            ),
        ), dim=1)
        continuous_values = torch.stack((
            output["component_count_estimate"],
            output["hole_count_estimate"],
        ), dim=1)
        continuous = torch.round(continuous_values).to(torch.long)
        additive_values = torch.sum(
            output["token_topology_contributions"], dim=1,
        )
        additive = torch.round(additive_values).to(torch.long)
        predictions = {
            "support_mask": np.asarray([
                topology_signature(
                    values >= float(payload["support_threshold"]),
                )
                for values in support_probability
            ], dtype=np.int64),
            "categorical": categorical.cpu().numpy(),
            "posterior_mean": posterior_mean.cpu().numpy(),
            "posterior_median": posterior_median.cpu().numpy(),
            "continuous": continuous.cpu().numpy(),
            "additive": additive.cpu().numpy(),
        }
        residuals.append((continuous_values - additive_values).cpu().numpy())
        true_components = batch["components"].numpy()
        true_holes = batch["holes"].numpy()
        true_lengths = batch["true_text_length"].numpy()
        exact_hints = batch["ocr_hint_exact"].numpy()
        for index in range(len(true_components)):
            truth = (int(true_components[index]), int(true_holes[index]))
            slice_name = f"length:{_length_slice(int(true_lengths[index]))}"
            condition_name = (
                f"ocr_hint_exact:{str(bool(exact_hints[index])).lower()}"
            )
            for method, values in predictions.items():
                predicted = (
                    int(values[index, 0]), int(values[index, 1]),
                )
                _add(totals[method], *predicted, *truth)
                _add(
                    slices[method].setdefault(
                        slice_name, _empty_totals(),
                    ),
                    *predicted, *truth,
                )
                _add(
                    conditions[method].setdefault(
                        condition_name, _empty_totals(),
                    ),
                    *predicted, *truth,
                )
            alternatives = (
                predictions["support_mask"][index],
                predictions["categorical"][index],
            )
            oracle_prediction = min(
                alternatives,
                key=lambda values: (
                    abs(int(values[0]) - truth[0])
                    + abs(int(values[1]) - truth[1]),
                    abs(int(values[0]) - truth[0]),
                    abs(int(values[1]) - truth[1]),
                ),
            )
            _add(
                oracle, int(oracle_prediction[0]), int(oracle_prediction[1]),
                *truth,
            )
    residual = np.concatenate(residuals, axis=0)
    return {
        "schema": "pcdc-wordmark-checkpoint-count-diagnostic/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_epoch": int(payload["epoch"]),
        "model_data_contract_sha256": wordmark_prior_source_sha256(),
        "checkpoint_trainer_source_sha256": payload.get(
            "trainer_source_sha256"
        ),
        "evaluation_trainer_source_sha256": wordmark_trainer_source_sha256(),
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "family_split_sha256": split.digest,
        "data_recipe": wordmark_data_recipe(),
        "split": args.split, "samples": len(dataset), "device": str(device),
        "methods": {
            method: {
                **_metrics(totals[method]),
                "diagnostic_slices": {
                    name: _metrics(values)
                    for name, values in sorted(slices[method].items())
                },
                "conditions": {
                    name: _metrics(values)
                    for name, values in sorted(conditions[method].items())
                },
            }
            for method in methods
        },
        "support_or_categorical_oracle": _metrics(oracle),
        "visual_residual": {
            "component_mean": float(np.mean(residual[:, 0])),
            "component_mean_absolute": float(np.mean(np.abs(residual[:, 0]))),
            "hole_mean": float(np.mean(residual[:, 1])),
            "hole_mean_absolute": float(np.mean(np.abs(residual[:, 1]))),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--font-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--font-root", type=Path, default=DEFAULT_FONT_ROOT)
    parser.add_argument(
        "--split", choices=("train", "calibration", "test"), default="test",
    )
    parser.add_argument("--samples", type=int, default=2_048)
    parser.add_argument("--seed", type=int, default=20260723 + 2_000_003)
    parser.add_argument("--split-seed", type=int, default=20260722)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8",
    )
    print(json.dumps({
        "out": str(args.out),
        "methods": {
            name: {
                "joint_accuracy": values["joint_accuracy"],
                "component_mean_absolute_error": values[
                    "component_mean_absolute_error"
                ],
                "hole_mean_absolute_error": values[
                    "hole_mean_absolute_error"
                ],
            }
            for name, values in report["methods"].items()
        },
        "visual_residual": report["visual_residual"],
        "support_or_categorical_oracle": report[
            "support_or_categorical_oracle"
        ],
    }, indent=2))


if __name__ == "__main__":
    main()

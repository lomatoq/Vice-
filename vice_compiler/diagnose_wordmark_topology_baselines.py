"""Measure deterministic raster-topology baselines for the wordmark prior.

This is a diagnostic, not a promotion gate.  It answers whether the learned
count heads add information beyond topology that is already observable in the
degraded raster, including an oracle over a small global threshold sweep.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .glyph_prior_data import load_font_records, split_font_families
from .train_wordmark_prior import (
    DEFAULT_FONT_ROOT, DEFAULT_MANIFEST, _length_slice,
    wordmark_trainer_source_sha256,
)
from .wordmark_prior import (
    WordmarkPriorConfig, topology_signature, wordmark_prior_source_sha256,
)
from .wordmark_prior_data import OpenFontWordmarkDataset, wordmark_data_recipe


def _empty_totals() -> dict[str, float]:
    return {
        "samples": 0.0, "component": 0.0, "hole": 0.0, "joint": 0.0,
        "complex_samples": 0.0, "complex_joint": 0.0,
        "component_absolute_error": 0.0, "hole_absolute_error": 0.0,
    }


def _add(
    totals: dict[str, float], predicted: tuple[int, int],
    truth: tuple[int, int],
) -> None:
    complex_sample = truth[0] > 1 or truth[1] >= 4
    totals["samples"] += 1.0
    totals["component"] += float(predicted[0] == truth[0])
    totals["hole"] += float(predicted[1] == truth[1])
    totals["joint"] += float(predicted == truth)
    totals["complex_samples"] += float(complex_sample)
    totals["complex_joint"] += float(complex_sample and predicted == truth)
    totals["component_absolute_error"] += abs(predicted[0] - truth[0])
    totals["hole_absolute_error"] += abs(predicted[1] - truth[1])


def _metrics(totals: dict[str, float]) -> dict[str, float | int]:
    samples = max(1.0, totals["samples"])
    complex_samples = max(1.0, totals["complex_samples"])
    return {
        "samples": int(totals["samples"]),
        "component_accuracy": totals["component"] / samples,
        "hole_accuracy": totals["hole"] / samples,
        "joint_topology_accuracy": totals["joint"] / samples,
        "complex_topology_accuracy": (
            totals["complex_joint"] / complex_samples
        ),
        "component_mean_absolute_error": (
            totals["component_absolute_error"] / samples
        ),
        "hole_mean_absolute_error": totals["hole_absolute_error"] / samples,
    }


def diagnose(args: argparse.Namespace) -> dict[str, Any]:
    fonts, manifest = load_font_records(
        args.font_manifest, font_root=args.font_root,
    )
    split = split_font_families(fonts, seed=args.split_seed)
    records = getattr(split, args.split)
    dataset = OpenFontWordmarkDataset(
        records, sample_count=args.samples, seed=args.seed,
        config=WordmarkPriorConfig(),
    )
    thresholds = tuple(float(value) for value in args.thresholds)
    totals = {threshold: _empty_totals() for threshold in thresholds}
    slices = {
        threshold: {} for threshold in thresholds
    }
    oracle = _empty_totals()
    for index in range(len(dataset)):
        row = dataset[index]
        observed = row["features"][0].numpy()
        truth = (int(row["components"]), int(row["holes"]))
        length_slice = _length_slice(int(row["true_text_length"]))
        predictions = []
        for threshold in thresholds:
            predicted = topology_signature(observed >= threshold)
            predictions.append(predicted)
            _add(totals[threshold], predicted, truth)
            sliced = slices[threshold].setdefault(
                f"length:{length_slice}", _empty_totals(),
            )
            _add(sliced, predicted, truth)
        exact = truth if truth in predictions else min(
            predictions,
            key=lambda value: (
                abs(value[0] - truth[0]) + abs(value[1] - truth[1]),
                abs(value[0] - truth[0]), abs(value[1] - truth[1]),
            ),
        )
        _add(oracle, exact, truth)
    threshold_metrics = {
        f"{threshold:.3f}": {
            **_metrics(totals[threshold]),
            "diagnostic_slices": {
                name: _metrics(values)
                for name, values in sorted(slices[threshold].items())
            },
        }
        for threshold in thresholds
    }
    best_threshold, best = max(
        threshold_metrics.items(),
        key=lambda item: (
            item[1]["joint_topology_accuracy"],
            item[1]["complex_topology_accuracy"],
            item[1]["component_accuracy"],
            item[1]["hole_accuracy"],
        ),
    )
    return {
        "schema": "pcdc-wordmark-topology-baselines/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "split": args.split, "samples": len(dataset),
        "seed": int(args.seed), "split_seed": int(args.split_seed),
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "family_split_sha256": split.digest,
        "model_data_contract_sha256": wordmark_prior_source_sha256(),
        "trainer_source_sha256": wordmark_trainer_source_sha256(),
        "data_recipe": wordmark_data_recipe(),
        "thresholds": threshold_metrics,
        "best_global_threshold": best_threshold,
        "best_global_metrics": best,
        "per_sample_threshold_oracle": _metrics(oracle),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--font-root", type=Path, default=DEFAULT_FONT_ROOT)
    parser.add_argument(
        "--split", choices=("train", "calibration", "test"), default="test",
    )
    parser.add_argument("--samples", type=int, default=2_048)
    parser.add_argument("--seed", type=int, default=20260723 + 2_000_003)
    parser.add_argument("--split-seed", type=int, default=20260722)
    parser.add_argument(
        "--thresholds", type=float, nargs="+",
        default=(0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8",
    )
    print(json.dumps({
        "out": str(args.out),
        "best_global_threshold": report["best_global_threshold"],
        "best_global_joint_topology_accuracy": report[
            "best_global_metrics"
        ]["joint_topology_accuracy"],
        "oracle_joint_topology_accuracy": report[
            "per_sample_threshold_oracle"
        ]["joint_topology_accuracy"],
    }, indent=2))


if __name__ == "__main__":
    main()

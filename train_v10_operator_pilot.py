"""v10-op-v0: bounded representative pilot of the v10 operator predictor.

Today's measurements pinned the v10 neural component's role: predict WHICH
composition operators to propose (S8.11), not paint pixels. This pilot asks
the narrowest form of that question: are the render operators readable from
the degraded raster at all?

    observed line raster -> {stroke class, tracking bin, effect class}

Labels are replayed deterministically from the data generator itself (the
draw sequence inside the snapshot's renderer is uniform(tracking),
integers(stroke), random(effect)). Held-out font families, same split as
every other diagnostic. This is a S23-class bounded pilot: minutes of GPU,
one run, no post-val tuning, stop condition written in the live log BEFORE
the run. It authorizes nothing; a full v10 training still requires its own
readiness pipeline.

Downstream gate (the real test): on fresh no-effect samples, vector-level
Recall@8 faces using only the TOP-2 predicted (tracking, stroke) variants
must stay within 5pt of the full 9-variant sweep - candidate compression
x4.5 without losing coverage.

Usage:
  C:\\Python312\\python.exe train_v10_operator_pilot.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent

from diagnose_template_warp_oracle import (  # noqa: E402
    _render_glyph_layers,
    _sample_fixed_length_text,
)
from diagnose_vector_topology_recall import _mask_topology  # noqa: E402
from diagnose_template_warp_retrieval import (  # noqa: E402
    QUERY_FEATURES,
    query_features,
)

import cv2  # noqa: E402

TRACKING_BINS = (-0.10, 0.0, 0.10)     # bin centers == composition grid
STROKE_CLASSES = (0, 2, 4)             # render-res dilation == grid
FULL_VARIANTS = tuple(
    (tracking, stroke)
    for tracking in TRACKING_BINS for stroke in STROKE_CLASSES
)


def _tracking_bin(value: float) -> int:
    if value < -0.05:
        return 0
    if value <= 0.05:
        return 1
    return 2


def _stroke_class(value: int) -> int:
    if value <= 1:
        return 0
    if value <= 4:
        return 1
    return 2


def _composed_topology_set(
    font_path: str, text: str, variants,
) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    rendered_cache: dict[float, np.ndarray | None] = {}
    for tracking, stroke in variants:
        if tracking not in rendered_cache:
            rendered = _render_glyph_layers(font_path, text, tracking)
            rendered_cache[tracking] = (
                None if rendered is None else rendered[0] >= 128
            )
        joint = rendered_cache[tracking]
        if joint is None:
            continue
        mask = joint
        if stroke:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (2 * stroke + 1, 2 * stroke + 1),
            )
            mask = cv2.dilate(joint.astype(np.uint8), kernel) > 0
        out.add(_mask_topology(mask))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root", type=Path,
        default=ROOT / ".training_snapshots" / "wordmark_full_v4_20260723",
    )
    parser.add_argument(
        "--font-manifest", type=Path,
        default=ROOT / "fonts" / "google-fonts-manifest.json",
    )
    parser.add_argument(
        "--font-root", type=Path, default=ROOT / "fonts" / "google-fonts",
    )
    parser.add_argument(
        "--descriptors", type=Path,
        default=ROOT / "benchmarks" / "pcdc_pre_v14"
        / "font_style_descriptors.json",
    )
    parser.add_argument("--train-samples", type=int, default=16000)
    parser.add_argument("--val-samples", type=int, default=2000)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--train-bank-v2", type=Path, default=None,
        help="draw TRAINING fonts from the v2-full bank (val stays on the "
        "attested held-out families, which are excluded from training)",
    )
    parser.add_argument(
        "--train-family-limit", type=int, default=0,
        help="with --train-bank-v2: cap training families (Experiment G "
        "training-side curve); 0 = no cap",
    )
    parser.add_argument("--skip-downstream", action="store_true")
    parser.add_argument("--downstream-per-length", type=int, default=48)
    parser.add_argument("--top-variants", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260725)
    parser.add_argument("--split-seed", type=int, default=20260722)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "benchmarks" / "pcdc_pre_v14"
        / "v10_operator_pilot_report.json",
    )
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    sys.path.insert(0, str(source_root))
    import torch
    from torch import nn
    from vice_compiler.wordmark_prior import (
        WORDMARK_CHARACTERS,
        WordmarkPriorConfig,
        topology_signature,
    )
    from vice_compiler.wordmark_prior_data import (
        CONNECTED_WORDMARK_FRACTION,
        OUTLINE_WORDMARK_FRACTION,
        _rng,
        degrade_wordmark,
        render_clean_wordmark,
        wordmark_observation_features,
    )
    from vice_compiler.glyph_prior_data import (
        load_font_records,
        split_font_families,
    )

    started = time.perf_counter()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed % (2**31))
    fonts, manifest = load_font_records(
        args.font_manifest, font_root=args.font_root,
    )
    split = split_font_families(fonts, seed=args.split_seed)
    if args.train_bank_v2 is not None:
        from collections import namedtuple

        FontFace = namedtuple("FontFace", ("family", "path"))
        held_out_families = {
            record.family for record in split.test
        } | {record.family for record in split.calibration}
        v2 = json.loads(args.train_bank_v2.read_text(encoding="utf-8"))
        by_family: dict[str, list] = {}
        for face in v2["faces"]:
            if face["family"] in held_out_families:
                continue
            by_family.setdefault(face["family"], []).append(
                FontFace(face["family"], str(ROOT / face["path"])),
            )
        family_names = sorted(by_family)
        if args.train_family_limit:
            family_names = family_names[:args.train_family_limit]
        train_bank = tuple(
            face for name in family_names for face in by_family[name][:4]
        )
        print(
            f"training bank: {len(family_names)} families, "
            f"{len(train_bank)} faces (val = attested held-out)",
            flush=True,
        )
    else:
        train_bank = split.train
    config = WordmarkPriorConfig(image_height=64, image_width=384)
    config.validate()
    connected_fraction = CONNECTED_WORDMARK_FRACTION
    outline_fraction = OUTLINE_WORDMARK_FRACTION

    def build_sample(bank, index: int, base_seed: int):
        """One (observed uint8 raster, labels) pair with replayed labels."""
        for retry in range(64):
            sample_index = index + retry * 1_000_003
            generator = _rng(base_seed, sample_index)
            font = bank[int(generator.integers(0, len(bank)))]
            length = int(generator.integers(1, 33))
            text = _sample_fixed_length_text(
                generator, length, WORDMARK_CHARACTERS,
            )
            render_seed = base_seed + 104729 * sample_index
            replay = _rng(render_seed, 0)
            tracking_value = float(replay.uniform(-0.15, 0.22))
            stroke_value = int(replay.integers(0, 8))
            effect_value = float(replay.random())
            try:
                coverage, support = render_clean_wordmark(
                    font.path, text, config, seed=render_seed,
                )
            except OSError:
                # Pathological faces in the full v2 bank (PIL layout
                # failures): resample, never crash a pilot.
                continue
            if not np.any(support):
                continue
            observed = degrade_wordmark(
                coverage, support,
                seed=base_seed + 130363 * sample_index,
            )
            if effect_value < connected_fraction:
                effect_label = 1
            elif effect_value < connected_fraction + outline_fraction:
                effect_label = 2
            else:
                effect_label = 0
            labels = (
                _stroke_class(stroke_value),
                _tracking_bin(tracking_value),
                effect_label,
            )
            raster = np.rint(
                np.clip(observed, 0.0, 1.0) * 255.0
            ).astype(np.uint8)
            return raster, labels, font, text
        raise RuntimeError(f"sample {index}: resampling exhausted")

    def generate_bank(bank, count: int, base_seed: int):
        rasters = np.zeros(
            (count, config.image_height, config.image_width), np.uint8,
        )
        labels = np.zeros((count, 3), np.int64)
        for index in range(count):
            raster, row_labels, _font, _text = build_sample(
                bank, index, base_seed,
            )
            rasters[index] = raster
            labels[index] = row_labels
            if (index + 1) % 4000 == 0:
                print(f"generated {index + 1}/{count}", flush=True)
        return rasters, labels

    print("generating train/val banks...", flush=True)
    train_rasters, train_labels = generate_bank(
        train_bank, args.train_samples, args.seed,
    )
    val_rasters, val_labels = generate_bank(
        split.test, args.val_samples, args.seed + 7_777_777,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    class OperatorNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            def block(cin, cout):
                return nn.Sequential(
                    nn.Conv2d(cin, cout, 3, stride=2, padding=1),
                    nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                )
            self.backbone = nn.Sequential(
                block(3, 32), block(32, 64), block(64, 128), block(128, 128),
            )
            self.neck = nn.Sequential(
                nn.Linear(256, 128), nn.ReLU(inplace=True),
            )
            self.stroke_head = nn.Linear(128, 3)
            self.tracking_head = nn.Linear(128, 3)
            self.effect_head = nn.Linear(128, 3)

        def forward(self, x):
            features = self.backbone(x)
            pooled = torch.cat([
                features.amax(dim=(2, 3)), features.mean(dim=(2, 3)),
            ], dim=1)
            neck = self.neck(pooled)
            return (
                self.stroke_head(neck), self.tracking_head(neck),
                self.effect_head(neck),
            )

    def to_features(batch_rasters: np.ndarray) -> torch.Tensor:
        stacked = np.stack([
            wordmark_observation_features(row.astype(np.float32) / 255.0)
            for row in batch_rasters
        ])
        return torch.from_numpy(stacked)

    model = OperatorNet().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-4)
    loss_fn = nn.CrossEntropyLoss()
    order = np.arange(args.train_samples)
    rng = np.random.default_rng(args.seed)
    for epoch in range(args.epochs):
        model.train()
        rng.shuffle(order)
        total_loss = 0.0
        for start in range(0, args.train_samples, args.batch_size):
            rows = order[start:start + args.batch_size]
            features = to_features(train_rasters[rows]).to(device)
            targets = torch.from_numpy(train_labels[rows]).to(device)
            optimizer.zero_grad()
            outputs = model(features)
            loss = sum(
                loss_fn(outputs[head], targets[:, head]) for head in range(3)
            )
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach())
        print(f"epoch {epoch + 1}: loss {total_loss:.1f}", flush=True)

    model.eval()
    correct = np.zeros(3, np.int64)
    majority = val_labels.copy()
    with torch.no_grad():
        for start in range(0, args.val_samples, args.batch_size):
            rows = slice(start, min(start + args.batch_size, args.val_samples))
            features = to_features(val_rasters[rows]).to(device)
            outputs = model(features)
            for head in range(3):
                predicted = outputs[head].argmax(dim=1).cpu().numpy()
                correct[head] += int(
                    np.sum(predicted == val_labels[rows][:, head])
                )
    val_accuracy = correct / args.val_samples
    baseline = np.array([
        np.bincount(majority[:, head], minlength=3).max() / args.val_samples
        for head in range(3)
    ])
    print("val accuracy [stroke, tracking, effect]:",
          np.round(val_accuracy, 4), "| majority baseline:",
          np.round(baseline, 4), flush=True)

    if args.skip_downstream:
        downstream = {"skipped": True}
    else:
        # --- Downstream: candidate compression without coverage loss ---
        bank = json.loads(args.descriptors.read_text(encoding="utf-8"))
        normalization = bank["normalization"]
        faces = bank["faces"]
        face_keys = list(faces)
        matrix = np.array([
            [
                (faces[key]["features"][name] - normalization[name]["mean"])
                / normalization[name]["std"]
                for name in QUERY_FEATURES
            ]
            for key in face_keys
        ])
        truth_config = WordmarkPriorConfig(image_height=256, image_width=16384)
        truth_config.validate()
        lengths = (1, 2, 4, 8, 16, 24, 32)
        per_length = args.downstream_per_length
        total = len(lengths) * per_length
        recall_full = np.zeros(total, bool)
        recall_predicted = np.zeros(total, bool)
        recall_mode = np.zeros(total, bool)
        effect_fraction = connected_fraction + outline_fraction
        scored = 0
        base_seed = args.seed + 55_555_555
        for length_index, length in enumerate(lengths):
            for slot in range(per_length):
                row = length_index * per_length + slot
                sample = None
                for retry in range(256):
                    index = row + retry * total
                    generator = _rng(base_seed, index)
                    font = split.test[
                        int(generator.integers(0, len(split.test)))
                    ]
                    text = _sample_fixed_length_text(
                        generator, length, WORDMARK_CHARACTERS,
                    )
                    render_seed = base_seed + 104729 * index
                    replay = _rng(render_seed, 0)
                    replay.uniform(-0.15, 0.22)
                    replay.integers(0, 8)
                    if float(replay.random()) < effect_fraction:
                        continue
                    coverage, support = render_clean_wordmark(
                        font.path, text, config, seed=render_seed,
                    )
                    if not np.any(support):
                        continue
                    observed = degrade_wordmark(
                        coverage, support, seed=base_seed + 130363 * index,
                    )
                    sample = (font, text, observed, render_seed)
                    break
                if sample is None:
                    raise RuntimeError("downstream resampling exhausted")
                font, text, observed, render_seed = sample
                _cov, truth_support = render_clean_wordmark(
                    font.path, text, truth_config, seed=render_seed,
                )
                truth = topology_signature(truth_support)
                query = query_features(
                    np.clip(observed, 0.0, 1.0).astype(np.float32)
                )
                if query is None:
                    scored += 1
                    continue
                vector = np.array([
                    (query[name] - normalization[name]["mean"])
                    / normalization[name]["std"]
                    for name in QUERY_FEATURES
                ])
                retrieved = [
                    face_keys[int(position)]
                    for position in np.argsort(
                        np.linalg.norm(matrix - vector, axis=1)
                    )[:8]
                ]
                with torch.no_grad():
                    raster = np.rint(
                        np.clip(observed, 0.0, 1.0) * 255.0
                    ).astype(np.uint8)
                    outputs = model(to_features(raster[None]).to(device))
                    stroke_probability = torch.softmax(
                        outputs[0], dim=1,
                    )[0].cpu().numpy()
                    tracking_probability = torch.softmax(
                        outputs[1], dim=1,
                    )[0].cpu().numpy()
                joint = np.outer(tracking_probability, stroke_probability)
                flat = np.argsort(joint.ravel())[::-1]
                predicted_variants = [
                    (
                        TRACKING_BINS[int(position) // 3],
                        STROKE_CLASSES[int(position) % 3],
                    )
                    for position in flat[:args.top_variants]
                ]
                mode_variant = [(0.0, 0)]
                for key in retrieved:
                    face_path = str(ROOT / faces[key]["path"])
                    full_set = _composed_topology_set(
                        face_path, text, FULL_VARIANTS,
                    )
                    if truth in full_set:
                        recall_full[row] = True
                    predicted_set = _composed_topology_set(
                        face_path, text, predicted_variants,
                    )
                    if truth in predicted_set:
                        recall_predicted[row] = True
                    if truth in _composed_topology_set(
                        face_path, text, mode_variant,
                    ):
                        recall_mode[row] = True
                    if (
                        recall_full[row] and recall_predicted[row]
                        and recall_mode[row]
                    ):
                        break
                scored += 1
                if scored % 64 == 0:
                    print(f"downstream {scored}/{total}", flush=True)

        downstream = {
            "recall_at_8_full_9_variants": float(np.mean(recall_full)),
            f"recall_at_8_top{args.top_variants}_predicted": float(
                np.mean(recall_predicted)
            ),
            "recall_at_8_mode_variant": float(np.mean(recall_mode)),
            "samples": int(total),
        }
    gate = {
        "val_beats_majority": bool(np.all(val_accuracy > baseline + 0.03)),
    }
    if not args.skip_downstream:
        gate["compression_within_5pt"] = bool(
            downstream["recall_at_8_full_9_variants"]
            - downstream[f"recall_at_8_top{args.top_variants}_predicted"]
            <= 0.05
        )
    report = {
        "schema": "vice-v10-operator-pilot/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "bounded representative pilot: are S8.11 operators readable "
            "from the degraded raster, and does predicting them compress "
            "the candidate set without losing Recall@8"
        ),
        "train_samples": int(args.train_samples),
        "train_families": (len(family_names) if args.train_bank_v2 is not None else len({r.family for r in split.train})),
        "val_samples": int(args.val_samples),
        "epochs": int(args.epochs),
        "seed": int(args.seed),
        "split_seed": int(args.split_seed),
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "family_split_sha256": split.digest,
        "device": str(device),
        "val_accuracy": {
            "stroke": float(val_accuracy[0]),
            "tracking": float(val_accuracy[1]),
            "effect": float(val_accuracy[2]),
        },
        "majority_baseline": {
            "stroke": float(baseline[0]),
            "tracking": float(baseline[1]),
            "effect": float(baseline[2]),
        },
        "downstream": downstream,
        "gate": gate,
        "gate_pass": bool(all(gate.values())),
        "authorizes_full_training": False,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "val_accuracy": report["val_accuracy"],
        "majority_baseline": report["majority_baseline"],
        "downstream": downstream, "gate": gate,
        "gate_pass": report["gate_pass"],
    }, indent=2))
    print(f"report written to {args.out}")


if __name__ == "__main__":
    main()

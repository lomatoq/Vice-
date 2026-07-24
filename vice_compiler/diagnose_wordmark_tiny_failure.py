"""Reproduce and localize a deterministic tiny-overfit topology failure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn

from .glyph_prior_data import load_font_records, split_font_families
from .train_wordmark_prior import (
    DEFAULT_FONT_ROOT, DEFAULT_MANIFEST, _configure_training_determinism,
    _device, _loader, _loss, _move,
)
from .wordmark_prior import (
    WORDMARK_CHARACTERS, WordmarkPriorConfig, WordmarkPriorNet,
    decode_wordmark_support, topology_signature,
)
from .wordmark_prior_data import OpenFontWordmarkDataset


def _component_rows(
    target: np.ndarray, candidate: np.ndarray, probability: np.ndarray,
) -> list[dict[str, object]]:
    target_count, target_labels, target_stats, _ = (
        cv2.connectedComponentsWithStats(target.astype(np.uint8), 8)
    )
    _candidate_count, candidate_labels, _candidate_stats, _ = (
        cv2.connectedComponentsWithStats(candidate.astype(np.uint8), 8)
    )
    rows = []
    for label in range(1, target_count):
        region = target_labels == label
        candidate_values, counts = np.unique(
            candidate_labels[region], return_counts=True,
        )
        overlaps = sorted(
            (
                (int(count), int(candidate_label))
                for candidate_label, count in zip(
                    candidate_values.tolist(), counts.tolist(),
                )
                if candidate_label > 0
            ),
            reverse=True,
        )
        x = int(target_stats[label, cv2.CC_STAT_LEFT])
        y = int(target_stats[label, cv2.CC_STAT_TOP])
        width = int(target_stats[label, cv2.CC_STAT_WIDTH])
        height = int(target_stats[label, cv2.CC_STAT_HEIGHT])
        rows.append({
            "target_label": label,
            "target_area": int(target_stats[label, cv2.CC_STAT_AREA]),
            "bbox_xywh": [x, y, width, height],
            "candidate_overlaps": [
                {"candidate_label": candidate_label, "pixels": count}
                for count, candidate_label in overlaps
            ],
            "candidate_pixels": int(np.sum(candidate[region])),
            "probability_min": float(np.min(probability[region])),
            "probability_mean": float(np.mean(probability[region])),
            "probability_max": float(np.max(probability[region])),
        })
    return rows


def _decode_text(tokens: np.ndarray, length: int) -> str:
    return "".join(
        WORDMARK_CHARACTERS[int(token) - 1]
        for token in tokens[:length] if int(token) > 0
    )


def diagnose(args: argparse.Namespace) -> dict[str, object]:
    device = _device(args.device)
    _configure_training_determinism(args.seed)
    fonts, _manifest = load_font_records(
        args.font_manifest, font_root=args.font_root,
    )
    split = split_font_families(fonts, seed=args.split_seed)
    config = WordmarkPriorConfig(base_channels=8, text_embedding_dim=16)
    dataset = OpenFontWordmarkDataset(
        split.train[:max(1, min(4, len(split.train)))],
        sample_count=8, seed=args.seed, config=config,
    )
    loader = _loader(dataset, batch_size=8, workers=0)
    batch = _move(next(iter(loader)), device)
    model = WordmarkPriorNet(config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=3.0e-3, weight_decay=0.0,
    )
    model.train()
    for _ in range(args.steps):
        optimizer.zero_grad(set_to_none=True)
        output = model(
            batch["features"], batch["text_tokens"], batch["text_length"],
        )
        loss, _parts = _loss(output, batch)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
    model.eval()
    with torch.no_grad():
        output = model(
            batch["features"], batch["text_tokens"], batch["text_length"],
        )
    probability = torch.sigmoid(
        output["support_logits"],
    ).cpu().numpy()[:, 0]
    component_probability = torch.softmax(
        output["component_logits"], dim=1,
    ).cpu().numpy()
    hole_probability = torch.softmax(
        output["hole_logits"], dim=1,
    ).cpu().numpy()
    targets = batch["support"].cpu().numpy()[:, 0] >= 0.5
    failures = []
    args.image_dir.mkdir(parents=True, exist_ok=True)
    for index, target in enumerate(targets):
        expected = (
            int(np.argmax(component_probability[index])),
            int(np.argmax(hole_probability[index])),
        )
        raw = probability[index] >= 0.8
        decoded, threshold, matched = decode_wordmark_support(
            probability[index], expected_topology=expected,
            preferred_threshold=0.8,
        )
        truth = (
            int(batch["components"][index]),
            int(batch["holes"][index]),
        )
        if topology_signature(decoded) == truth:
            continue
        panels = np.concatenate((
            np.rint(probability[index] * 255.0).astype(np.uint8),
            target.astype(np.uint8) * 255,
            raw.astype(np.uint8) * 255,
            decoded.astype(np.uint8) * 255,
        ), axis=1)
        image_path = args.image_dir / f"sample-{index}.png"
        cv2.imwrite(
            str(image_path),
            cv2.resize(
                panels, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST,
            ),
        )
        failures.append({
            "index": index,
            "ocr_hint": _decode_text(
                batch["text_tokens"][index].cpu().numpy(),
                int(batch["text_length"][index]),
            ),
            "true_text_length": int(batch["true_text_length"][index]),
            "ocr_hint_exact": bool(batch["ocr_hint_exact"][index]),
            "truth": list(truth), "expected": list(expected),
            "raw": list(topology_signature(raw)),
            "decoded": list(topology_signature(decoded)),
            "decode_threshold": float(threshold),
            "decoder_matched_head": bool(matched),
            "target_components": _component_rows(
                target, raw, probability[index],
            ),
            "image": str(image_path.resolve()),
        })
    return {
        "schema": "pcdc-wordmark-tiny-failure-diagnostic/v1",
        "steps": int(args.steps), "seed": int(args.seed),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--font-root", type=Path, default=DEFAULT_FONT_ROOT)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--split-seed", type=int, default=20260722)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--image-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8",
    )
    print(json.dumps({
        "out": str(args.out), "failure_count": len(report["failures"]),
    }, indent=2))


if __name__ == "__main__":
    main()

"""Train the scene evidence heads on synthetic source-scene labels.

This script never consumes Vectorizer.AI output.  Input ``.npz`` files are
created by ``vice_scene.training_data.write_training_sample``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import numpy as np

from vice_scene.ingest import linear_rgb_to_oklab, srgb_to_linear
from vice_scene.neural_evidence import HEAD_CHANNELS, build_scene_evidence_net


PROBABILITY_HEADS = {
    "boundary_prob", "coverage_alpha", "corner_prob", "corner_type",
    "junction_prob", "shape_class_logits", "text_line_prob", "glyph_occupancy",
    "stroke_centerline_prob", "symmetry_evidence", "uncertainty",
}


def main() -> int:
    import torch
    import torch.nn.functional as functional

    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--out", type=Path,
                        default=Path("models/scene_evidence.candidate.pt"))
    parser.add_argument("--split", default="train", choices=("train",),
                        help="training is deliberately restricted to the train split")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--base-channels", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    files = _split_files(args.dataset, args.split)
    if not files:
        parser.error(f"dataset contains no {args.split}/ .npz samples")
    manifest_hash = _validate_dataset_manifest(args.dataset)
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available()
                          else ("cpu" if args.device == "auto" else args.device))
    model = build_scene_evidence_net(args.base_channels).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-4)
    epoch_losses = []
    for epoch in range(args.epochs):
        random.shuffle(files)
        losses = []
        for start in range(0, len(files), args.batch_size):
            rows = [_load(path) for path in files[start:start + args.batch_size]]
            input_tensor = torch.from_numpy(np.stack([row[0] for row in rows])).to(device)
            output = model(input_tensor)
            total = torch.zeros((), device=device)
            for name, prediction in output.items():
                target = torch.from_numpy(np.stack([row[1][name] for row in rows])).to(device)
                if name in PROBABILITY_HEADS:
                    # Sparse evidence (corners, junctions, glyphs) otherwise
                    # collapses to an all-zero predictor.  The capped balance
                    # factor keeps a single positive pixel from exploding a
                    # batch while still making recall trainable.
                    reduce_dims = tuple(range(target.ndim))
                    positive = torch.mean(target, dim=reduce_dims)
                    pos_weight = torch.clamp((1.0 - positive) / torch.clamp(
                        positive, min=1e-4), 1.0, 25.0)
                    bce = functional.binary_cross_entropy_with_logits(
                        prediction, target, pos_weight=pos_weight)
                    probability = torch.sigmoid(prediction)
                    intersection = torch.sum(probability * target)
                    dice = 1.0 - (2.0 * intersection + 1.0) / (
                        torch.sum(probability) + torch.sum(target) + 1.0)
                    total = total + bce + 0.25 * dice
                elif name == "stroke_half_width":
                    total = total + functional.smooth_l1_loss(functional.softplus(prediction), target)
                else:
                    total = total + functional.smooth_l1_loss(prediction, target)
            optimizer.zero_grad(set_to_none=True)
            total.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            optimizer.step()
            losses.append(float(total.detach().cpu()))
        print(f"epoch {epoch + 1}/{args.epochs}: loss={np.mean(losses):.6f}")
        epoch_losses.append(float(np.mean(losses)))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.cpu().state_dict(), "base_channels": args.base_channels,
                "seed": args.seed, "head_channels": HEAD_CHANNELS,
                "schema": "vice-scene-evidence-checkpoint/1",
                "status": "candidate", "training_split": args.split,
                "training_samples": len(files),
                "dataset_manifest_sha256": manifest_hash,
                "epoch_losses": epoch_losses}, args.out)
    return 0


def _load(path: Path):
    archive = np.load(path, allow_pickle=False)
    rgba = archive["input_rgba"].astype(np.float32) / 255.0
    linear = srgb_to_linear(rgba[..., :3])
    lab = linear_rgb_to_oklab(linear)
    input_value = np.concatenate((lab, rgba[..., 3:4], linear), axis=2).transpose(2, 0, 1)
    targets = {}
    for name, channels in HEAD_CHANNELS.items():
        value = archive[name].astype(np.float32)
        if value.ndim == 2:
            value = value[..., None]
        targets[name] = value.transpose(2, 0, 1)
    return input_value.astype(np.float32), targets


def _split_files(dataset: Path, split: str) -> list[Path]:
    split_root = dataset / split
    if not split_root.is_dir():
        return []
    return sorted(path for path in split_root.rglob("*.npz") if path.is_file())


def _validate_dataset_manifest(dataset: Path) -> str:
    manifest_path = dataset / "dataset_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("dataset_manifest.json is required for auditable training")
    encoded = manifest_path.read_bytes()
    payload = json.loads(encoded.decode("utf-8"))
    if payload.get("schema") != "vice-synthetic-dataset/1":
        raise ValueError("unsupported evidence dataset schema")
    policy = str(payload.get("policy", ""))
    if "no Vectorizer.AI output" not in policy:
        raise ValueError("dataset manifest lacks the clean-room training policy")
    return hashlib.sha256(encoded).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())

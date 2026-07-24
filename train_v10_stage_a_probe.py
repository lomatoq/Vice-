"""Stage-A probe: the LAST readiness gate - does family diversity bind
glyph-SHAPE generalization?

Experiment G came out flat on the operator probe (style-agnostic geometry)
and on retrieval topology. The one place D5 can still bind is the inverse
glyph-shape task itself - Stage A's job: recover per-glyph topology from a
DEGRADED single-glyph render, on unseen families.

    degraded 64x64 glyph render -> components {1,2,3+} x holes {0,1,2,3+}

Bounded S23 pilot, one run per family count {81, 600, full}, no tuning.
Labels come from the 256 px clean-render topology (the Stage-A shard
convention). Validation is ALWAYS the attested held-out families, which are
excluded from every training bank. Gate resolution: rising curve closes
family_learning_curve as confirmed; a flat curve closes the QUESTION with
a falsification at every probe - the readiness builder records which.

Usage:
  C:\\Python312\\python.exe train_v10_stage_a_probe.py --train-family-limit 81
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent

from diagnose_vector_topology_recall import _glyph_topology  # noqa: E402

CHARS = "ABCDEFGHKMOPQRSabdegokpqsx02468&"


def _component_class(components: int) -> int:
    return min(2, components - 1)  # 1, 2, 3+


def _hole_class(holes: int) -> int:
    return min(3, holes)  # 0, 1, 2, 3+


def _render_glyph_64(font_path: str, character: str) -> np.ndarray | None:
    """Clean 64x64 letterboxed glyph coverage in [0,1]."""
    try:
        font = ImageFont.truetype(font_path, 128)
        bounds = font.getbbox(character)
        if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            return None
        pad = 6
        canvas = Image.new(
            "L",
            (bounds[2] - bounds[0] + 2 * pad, bounds[3] - bounds[1] + 2 * pad),
            0,
        )
        ImageDraw.Draw(canvas).text(
            (pad - bounds[0], pad - bounds[1]), character, font=font, fill=255,
        )
    except (OSError, ValueError):
        return None
    alpha = np.asarray(canvas, np.float32) / 255.0
    if not alpha.any():
        return None
    height, width = alpha.shape
    factor = 56.0 / max(height, width)
    resized = cv2.resize(
        alpha,
        (max(1, int(round(width * factor))), max(1, int(round(height * factor)))),
        interpolation=cv2.INTER_AREA,
    )
    out = np.zeros((64, 64), np.float32)
    y = (64 - resized.shape[0]) // 2
    x = (64 - resized.shape[1]) // 2
    out[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
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
        "--bank-v2", type=Path,
        default=ROOT / "fonts" / "google-fonts-manifest-v2-full.json",
    )
    parser.add_argument("--train-family-limit", type=int, default=0)
    parser.add_argument("--train-samples", type=int, default=16000)
    parser.add_argument("--val-samples", type=int, default=2000)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=20260726)
    parser.add_argument("--split-seed", type=int, default=20260722)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.out is None:
        name = args.train_family_limit or "full"
        args.out = (
            ROOT / "benchmarks" / "pcdc_pre_v14"
            / f"stage_a_probe_fam{name}.json"
        )

    source_root = args.source_root.resolve()
    sys.path.insert(0, str(source_root))
    import torch
    from torch import nn
    from vice_compiler.wordmark_prior_data import _rng, degrade_wordmark
    from vice_compiler.glyph_prior_data import (
        load_font_records,
        split_font_families,
    )

    started = time.perf_counter()
    torch.manual_seed(args.seed)
    fonts, manifest = load_font_records(
        args.font_manifest, font_root=args.font_root,
    )
    split = split_font_families(fonts, seed=args.split_seed)
    held_out_families = {
        record.family for record in split.test
    } | {record.family for record in split.calibration}
    v2 = json.loads(args.bank_v2.read_text(encoding="utf-8"))
    by_family: dict[str, list[str]] = {}
    for face in v2["faces"]:
        if face["family"] in held_out_families:
            continue
        by_family.setdefault(face["family"], []).append(
            str(ROOT / face["path"]),
        )
    family_names = sorted(by_family)
    if args.train_family_limit:
        family_names = family_names[:args.train_family_limit]
    train_faces = [
        path for name in family_names for path in by_family[name][:4]
    ]
    val_faces = [str(record.path) for record in split.test]
    print(
        f"train: {len(family_names)} families / {len(train_faces)} faces; "
        f"val: attested held-out {len(val_faces)} faces", flush=True,
    )

    def build_bank(faces: list[str], count: int, base_seed: int):
        rasters = np.zeros((count, 64, 64), np.float32)
        labels = np.zeros((count, 2), np.int64)
        built = 0
        index = 0
        while built < count:
            generator = _rng(base_seed, index)
            index += 1
            face = faces[int(generator.integers(0, len(faces)))]
            character = CHARS[int(generator.integers(0, len(CHARS)))]
            clean = _render_glyph_64(face, character)
            if clean is None:
                continue
            topology = _glyph_topology(face, character)
            if topology is None or topology[0] < 1 or topology[0] > 6:
                continue
            support = clean >= 0.5
            if not support.any():
                continue
            observed = degrade_wordmark(
                clean, support, seed=base_seed + 130363 * index,
            )
            rasters[built] = np.clip(observed, 0.0, 1.0)
            labels[built] = (
                _component_class(topology[0]), _hole_class(topology[1]),
            )
            built += 1
            if built % 4000 == 0:
                print(f"generated {built}/{count}", flush=True)
        return rasters, labels

    train_rasters, train_labels = build_bank(
        train_faces, args.train_samples, args.seed,
    )
    val_rasters, val_labels = build_bank(
        val_faces, args.val_samples, args.seed + 9_999_991,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    class GlyphProbeNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            def block(cin, cout):
                return nn.Sequential(
                    nn.Conv2d(cin, cout, 3, stride=2, padding=1),
                    nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                )
            self.backbone = nn.Sequential(
                block(1, 32), block(32, 64), block(64, 128),
            )
            self.neck = nn.Sequential(
                nn.Linear(256, 128), nn.ReLU(inplace=True),
            )
            self.component_head = nn.Linear(128, 3)
            self.hole_head = nn.Linear(128, 4)

        def forward(self, x):
            features = self.backbone(x)
            pooled = torch.cat([
                features.amax(dim=(2, 3)), features.mean(dim=(2, 3)),
            ], dim=1)
            neck = self.neck(pooled)
            return self.component_head(neck), self.hole_head(neck)

    model = GlyphProbeNet().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-4)
    loss_fn = nn.CrossEntropyLoss()
    order = np.arange(args.train_samples)
    rng = np.random.default_rng(args.seed)
    for epoch in range(args.epochs):
        model.train()
        rng.shuffle(order)
        total = 0.0
        for start in range(0, args.train_samples, args.batch_size):
            rows = order[start:start + args.batch_size]
            features = torch.from_numpy(
                train_rasters[rows][:, None],
            ).to(device)
            targets = torch.from_numpy(train_labels[rows]).to(device)
            optimizer.zero_grad()
            components, holes = model(features)
            loss = (
                loss_fn(components, targets[:, 0])
                + loss_fn(holes, targets[:, 1])
            )
            loss.backward()
            optimizer.step()
            total += float(loss.detach())
        print(f"epoch {epoch + 1}: loss {total:.1f}", flush=True)

    model.eval()
    correct = np.zeros(2, np.int64)
    joint_correct = 0
    with torch.no_grad():
        for start in range(0, args.val_samples, args.batch_size):
            rows = slice(start, min(start + args.batch_size, args.val_samples))
            features = torch.from_numpy(
                val_rasters[rows][:, None],
            ).to(device)
            components, holes = model(features)
            predicted_components = components.argmax(dim=1).cpu().numpy()
            predicted_holes = holes.argmax(dim=1).cpu().numpy()
            truth = val_labels[rows]
            correct[0] += int(np.sum(predicted_components == truth[:, 0]))
            correct[1] += int(np.sum(predicted_holes == truth[:, 1]))
            joint_correct += int(np.sum(
                (predicted_components == truth[:, 0])
                & (predicted_holes == truth[:, 1])
            ))
    accuracy = correct / args.val_samples
    joint = joint_correct / args.val_samples
    majority = np.array([
        np.bincount(val_labels[:, 0], minlength=3).max() / args.val_samples,
        np.bincount(val_labels[:, 1], minlength=4).max() / args.val_samples,
    ])
    report = {
        "schema": "vice-v10-stage-a-probe/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "train_families": len(family_names),
        "train_faces": len(train_faces),
        "train_samples": int(args.train_samples),
        "val_samples": int(args.val_samples),
        "epochs": int(args.epochs),
        "seed": int(args.seed),
        "split_seed": int(args.split_seed),
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "bank_v2_content_sha256": v2["content_sha256"],
        "device": str(device),
        "val_accuracy": {
            "components": float(accuracy[0]),
            "holes": float(accuracy[1]),
            "joint": float(joint),
        },
        "majority_baseline": {
            "components": float(majority[0]),
            "holes": float(majority[1]),
        },
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["val_accuracy"], indent=2))
    print(f"report written to {args.out}")


if __name__ == "__main__":
    main()

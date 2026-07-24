"""v10 Stage A v0: clean per-glyph program prior (audit S10 Stage A).

The first REAL v10 training stage, run under the S4.7 per-run discipline:

  --tiny-overfit   300-step memorization check (preflight ingredient);
  default          representative bounded pilot on family-disjoint splits.

Data: clean per-glyph renders from the google-fonts v2 bank, with families
partitioned exactly as text_shapes_v2 family splits (recomputed
deterministically from the jsonl: same sha-greedy assignment). Validation
families are NEVER seen in training.

v0 heads = the audit's gate surface: per-glyph topology (components x
holes). Template-shortlist / SDF / corner heads are later increments of
the same stage - the gate that authorizes progression is:

  unseen-family per-glyph topology >= 99.9% (audit S15.1 Stage A)

The pilot never overwrites anything: checkpoint saved as
models/stage_a_v0_pilot.pt (candidate lifecycle name), report to
benchmarks/pcdc_pre_v14/stage_a_v0_pilot_report.json.

Usage:
  C:\\Python312\\python.exe train_v10_stage_a.py [--tiny-overfit]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
UBER_TS2 = Path(r"C:\Users\nirrt\Toolset\v-ize train\dataset\text_shapes_v2")

from train_v10_stage_a_probe import (  # noqa: E402
    CHARS,
    _component_class,
    _hole_class,
    _render_glyph_64,
)
from diagnose_vector_topology_recall import _glyph_topology  # noqa: E402

GATE_TOPOLOGY = 0.999


def family_assignment() -> dict[str, str]:
    """Replay the text_shapes_v2 split assignment deterministically."""
    by_family: dict[str, int] = {}
    with open(UBER_TS2 / "text_shapes_v2.jsonl", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            by_family[row["family"]] = by_family.get(row["family"], 0) + 1
    order = sorted(
        by_family,
        key=lambda name: hashlib.sha256(
            ("ts2\0" + name).encode()
        ).hexdigest(),
    )
    total = sum(by_family.values())
    quotas = {
        "train": total * 0.70, "calibration": total * 0.15,
        "test": total * 0.15,
    }
    filled = {name: 0 for name in quotas}
    assignment: dict[str, str] = {}
    for family in order:
        target = max(
            quotas,
            key=lambda n: (quotas[n] - filled[n]) / max(1.0, quotas[n]),
        )
        assignment[family] = target
        filled[target] += by_family[family]
    return assignment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bank-v2", type=Path,
        default=ROOT / "fonts" / "google-fonts-manifest-v2-full.json",
    )
    parser.add_argument("--tiny-overfit", action="store_true")
    parser.add_argument("--train-samples", type=int, default=24000)
    parser.add_argument("--val-samples", type=int, default=3000)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "benchmarks" / "pcdc_pre_v14"
        / "stage_a_v0_pilot_report.json",
    )
    parser.add_argument(
        "--checkpoint", type=Path,
        default=ROOT / "models" / "stage_a_v0_pilot.pt",
    )
    args = parser.parse_args()

    sys.path.insert(
        0, str(ROOT / ".training_snapshots" / "wordmark_full_v4_20260723"),
    )
    import torch
    from torch import nn
    from vice_compiler.wordmark_prior_data import _rng

    started = time.perf_counter()
    torch.manual_seed(args.seed)
    assignment = family_assignment()
    bank = json.loads(args.bank_v2.read_text(encoding="utf-8"))
    faces_by_split: dict[str, list[str]] = {
        "train": [], "calibration": [], "test": [],
    }
    per_family: dict[str, int] = {}
    for face in bank["faces"]:
        family = face["family"]
        split = assignment.get(family)
        if split is None:
            continue
        if per_family.get(family, 0) >= 2:
            continue
        per_family[family] = per_family.get(family, 0) + 1
        faces_by_split[split].append(str(ROOT / face["path"]))
    print(
        "faces:", {name: len(faces) for name, faces in faces_by_split.items()},
        flush=True,
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
            rasters[built] = clean
            labels[built] = (
                _component_class(topology[0]), _hole_class(topology[1]),
            )
            built += 1
        return rasters, labels

    if args.tiny_overfit:
        train_count, val_count, epochs = 256, 256, 1
    else:
        train_count, val_count, epochs = (
            args.train_samples, args.val_samples, args.epochs,
        )
    print("generating banks...", flush=True)
    train_rasters, train_labels = build_bank(
        faces_by_split["train"], train_count, args.seed,
    )
    if args.tiny_overfit:
        val_rasters, val_labels = train_rasters, train_labels
    else:
        val_rasters, val_labels = build_bank(
            faces_by_split["test"], val_count, args.seed + 7_777_777,
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    class StageANet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            def block(cin, cout):
                return nn.Sequential(
                    nn.Conv2d(cin, cout, 3, stride=2, padding=1),
                    nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                )
            self.backbone = nn.Sequential(
                block(1, 32), block(32, 64), block(64, 128), block(128, 128),
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

    model = StageANet().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-4)
    loss_fn = nn.CrossEntropyLoss()
    order = np.arange(train_count)
    rng = np.random.default_rng(args.seed)
    steps = 0
    for epoch in range(epochs if not args.tiny_overfit else 100):
        model.train()
        rng.shuffle(order)
        total = 0.0
        for start in range(0, train_count, args.batch_size):
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
            steps += 1
            if args.tiny_overfit and steps >= 300:
                break
        print(f"epoch {epoch + 1}: loss {total:.2f}", flush=True)
        if args.tiny_overfit and steps >= 300:
            break

    model.eval()
    joint = comp = holes_ok = 0
    with torch.no_grad():
        for start in range(0, val_count, args.batch_size):
            rows = slice(start, min(start + args.batch_size, val_count))
            features = torch.from_numpy(
                val_rasters[rows][:, None],
            ).to(device)
            out_components, out_holes = model(features)
            predicted_c = out_components.argmax(dim=1).cpu().numpy()
            predicted_h = out_holes.argmax(dim=1).cpu().numpy()
            truth = val_labels[rows]
            comp += int(np.sum(predicted_c == truth[:, 0]))
            holes_ok += int(np.sum(predicted_h == truth[:, 1]))
            joint += int(np.sum(
                (predicted_c == truth[:, 0]) & (predicted_h == truth[:, 1])
            ))
    metrics = {
        "components": comp / val_count,
        "holes": holes_ok / val_count,
        "joint_topology": joint / val_count,
    }
    gate_pass = metrics["joint_topology"] >= GATE_TOPOLOGY
    mode = "tiny-overfit" if args.tiny_overfit else "representative-pilot"
    report = {
        "schema": "vice-v10-stage-a-pilot/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "gate": f"unseen-family joint topology >= {GATE_TOPOLOGY}",
        "gate_pass": bool(gate_pass),
        "metrics": metrics,
        "train_samples": int(train_count),
        "val_samples": int(val_count),
        "train_faces": len(faces_by_split["train"]),
        "test_faces": len(faces_by_split["test"]),
        "seed": int(args.seed),
        "bank_v2_content_sha256": bank["content_sha256"],
        "splits_source": "text_shapes_v2 family assignment (deterministic replay)",
        "device": str(device),
        "authorizes_full_training": False,
        "elapsed_seconds": time.perf_counter() - started,
    }
    if not args.tiny_overfit:
        args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "schema": "vice-stage-a-checkpoint/v0-pilot",
            "state_dict": model.state_dict(),
            "report": report,
        }, args.checkpoint)
        report["checkpoint"] = str(args.checkpoint)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"mode": mode, "metrics": metrics,
                      "gate_pass": gate_pass}, indent=1))
    print(f"report -> {args.out}")


if __name__ == "__main__":
    main()

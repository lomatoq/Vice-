"""v10 Stage A v1: learned retrieval embedding (topology by construction).

The v0 pilot proved pixel heads cannot carry the 99.9% Stage-A gate
(0.834); the gate is carried by TEMPLATE RETRIEVAL, where topology comes
from the retrieved template analytically (audit S8.6). Stage A's neural
role is therefore the retrieval embedding itself.

v1 recipe (bounded S4.7 pilot):
- train a family classifier over clean 64x64 glyph renders of the TRAIN
  families (text_shapes_v2 family split, replayed deterministically);
  the penultimate layer is the embedding;
- retrieval database = train faces' renders of the SAME character
  (Stage A receives the character - retrieval is per-character);
- gate surface on UNSEEN families: topology of the top-1 retrieved
  template vs the query glyph's true topology (plus top-8 any-match).

Baseline to beat: handcrafted style features gave R@1 0.927 on single
glyphs. Gate remains >= 0.999; the pilot records the honest distance.

Usage:
  C:\\Python312\\python.exe train_v10_stage_a_v1.py [--tiny-overfit]
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

from train_v10_stage_a_probe import CHARS, _render_glyph_64  # noqa: E402
from train_v10_stage_a import family_assignment  # noqa: E402
from diagnose_vector_topology_recall import _glyph_topology  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bank-v2", type=Path,
        default=ROOT / "fonts" / "google-fonts-manifest-v2-full.json",
    )
    parser.add_argument("--tiny-overfit", action="store_true")
    parser.add_argument("--train-samples", type=int, default=24000)
    parser.add_argument("--val-samples", type=int, default=1500)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=20260728)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "benchmarks" / "pcdc_pre_v14"
        / "stage_a_v1_retrieval_pilot_report.json",
    )
    parser.add_argument(
        "--checkpoint", type=Path,
        default=ROOT / "models" / "stage_a_v1_retrieval_pilot.pt",
    )
    args = parser.parse_args()

    sys.path.insert(
        0, str(ROOT / ".training_snapshots" / "wordmark_full_v4_20260723"),
    )
    import torch
    from torch import nn
    from torch.nn import functional as F
    from vice_compiler.wordmark_prior_data import _rng

    started = time.perf_counter()
    torch.manual_seed(args.seed)
    assignment = family_assignment()
    bank = json.loads(args.bank_v2.read_text(encoding="utf-8"))
    train_faces: list[tuple[str, str]] = []  # (family, path)
    test_faces: list[tuple[str, str]] = []
    per_family: dict[str, int] = {}
    for face in bank["faces"]:
        family = face["family"]
        split = assignment.get(family)
        if split is None or per_family.get(family, 0) >= 2:
            continue
        per_family[family] = per_family.get(family, 0) + 1
        row = (family, str(ROOT / face["path"]))
        if split == "train":
            train_faces.append(row)
        elif split == "test":
            test_faces.append(row)
    train_families = sorted({family for family, _p in train_faces})
    family_index = {name: i for i, name in enumerate(train_families)}
    print(
        f"train faces {len(train_faces)} ({len(train_families)} families); "
        f"test faces {len(test_faces)}", flush=True,
    )

    def build_samples(faces, count, base_seed):
        rasters = np.zeros((count, 64, 64), np.float32)
        labels = np.zeros(count, np.int64)  # family index (train only)
        chars = np.zeros(count, np.int64)
        topos: list[tuple[int, int]] = []
        built = 0
        index = 0
        while built < count:
            generator = _rng(base_seed, index)
            index += 1
            family, path = faces[int(generator.integers(0, len(faces)))]
            char_index = int(generator.integers(0, len(CHARS)))
            clean = _render_glyph_64(path, CHARS[char_index])
            if clean is None:
                continue
            topology = _glyph_topology(path, CHARS[char_index])
            if topology is None:
                continue
            rasters[built] = clean
            labels[built] = family_index.get(family, -1)
            chars[built] = char_index
            topos.append(topology)
            built += 1
        return rasters, labels, chars, topos

    if args.tiny_overfit:
        train_count, epochs = 256, 100
    else:
        train_count, epochs = args.train_samples, args.epochs
    print("generating training bank...", flush=True)
    train_rasters, train_labels, _tc, _tt = build_samples(
        train_faces, train_count, args.seed,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    class EmbedNet(nn.Module):
        def __init__(self, classes: int) -> None:
            super().__init__()
            def block(cin, cout):
                return nn.Sequential(
                    nn.Conv2d(cin, cout, 3, stride=2, padding=1),
                    nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                )
            self.backbone = nn.Sequential(
                block(1, 32), block(32, 64), block(64, 128), block(128, 128),
            )
            self.neck = nn.Linear(256, 128)
            self.classifier = nn.Linear(128, classes)

        def embed(self, x):
            features = self.backbone(x)
            pooled = torch.cat([
                features.amax(dim=(2, 3)), features.mean(dim=(2, 3)),
            ], dim=1)
            return F.normalize(self.neck(pooled), dim=1)

        def forward(self, x):
            return self.classifier(self.embed(x))

    model = EmbedNet(len(train_families)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-4)
    loss_fn = nn.CrossEntropyLoss()
    order = np.arange(train_count)
    rng = np.random.default_rng(args.seed)
    steps = 0
    for epoch in range(epochs):
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
            logits = model(features)
            loss = loss_fn(logits, targets)
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

    def embed_batch(rasters: np.ndarray) -> np.ndarray:
        out = []
        with torch.no_grad():
            for start in range(0, len(rasters), args.batch_size):
                chunk = torch.from_numpy(
                    rasters[start:start + args.batch_size][:, None],
                ).to(device)
                out.append(model.embed(chunk).cpu().numpy())
        return np.concatenate(out)

    if args.tiny_overfit:
        train_acc = float(np.mean(
            np.argmax(
                model(torch.from_numpy(train_rasters[:, None]).to(device))
                .detach().cpu().numpy(), axis=1,
            ) == train_labels
        ))
        report = {
            "schema": "vice-v10-stage-a-v1/tiny-overfit",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "train_accuracy": train_acc,
            "gate_pass": train_acc >= 0.99,
            "elapsed_seconds": time.perf_counter() - started,
        }
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=1))
        return

    # Retrieval database: one render per (train face, char).
    print("building retrieval database...", flush=True)
    db_entries: list[tuple[int, tuple[int, int]]] = []
    db_rasters = []
    for family, path in train_faces[:1400]:
        for char_index, character in enumerate(CHARS):
            clean = _render_glyph_64(path, character)
            topology = _glyph_topology(path, character)
            if clean is None or topology is None:
                continue
            db_rasters.append(clean)
            db_entries.append((char_index, topology))
    db_rasters = np.stack(db_rasters)
    db_embeddings = embed_batch(db_rasters)
    db_chars = np.array([entry[0] for entry in db_entries])
    print(f"database: {len(db_entries)} entries", flush=True)

    print("generating unseen-family queries...", flush=True)
    val_rasters, _vl, val_chars, val_topos = build_samples(
        test_faces, args.val_samples, args.seed + 7_777_777,
    )
    val_embeddings = embed_batch(val_rasters)

    top1 = top8 = 0
    for i in range(len(val_rasters)):
        mask = db_chars == val_chars[i]
        candidates = np.flatnonzero(mask)
        if not len(candidates):
            continue
        similarity = db_embeddings[candidates] @ val_embeddings[i]
        ranked = candidates[np.argsort(similarity)[::-1][:8]]
        truth = val_topos[i]
        retrieved = [db_entries[j][1] for j in ranked]
        if retrieved[0] == truth:
            top1 += 1
        if truth in retrieved:
            top8 += 1
    metrics = {
        "retrieval_topology_top1": top1 / len(val_rasters),
        "retrieval_topology_top8": top8 / len(val_rasters),
        "handcrafted_baseline_top1": 0.927,
        "gate": 0.999,
    }
    report = {
        "schema": "vice-v10-stage-a-v1/retrieval-pilot",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "representative-pilot",
        "metrics": metrics,
        "gate_pass": metrics["retrieval_topology_top1"] >= 0.999,
        "train_samples": int(train_count),
        "val_samples": int(len(val_rasters)),
        "train_families": len(train_families),
        "db_entries": len(db_entries),
        "seed": int(args.seed),
        "bank_v2_content_sha256": bank["content_sha256"],
        "device": str(device),
        "authorizes_full_training": False,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "schema": "vice-stage-a-v1-checkpoint/pilot",
        "state_dict": model.state_dict(),
        "train_families": train_families,
        "report": report,
    }, args.checkpoint)
    report["checkpoint"] = str(args.checkpoint)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": metrics,
                      "gate_pass": report["gate_pass"]}, indent=1))
    print(f"report -> {args.out}")


if __name__ == "__main__":
    main()

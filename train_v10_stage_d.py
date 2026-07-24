"""v10 Stage D v0: degradation-inverse support/SDF on the uber pairs.

The big-training target that today's measurements actually point at: the
clean/degraded gap dominates every failure axis, and the neural component's
proven role under degradation is reading SUPPORT (not topology counts).
Stage-D v0 learns exactly that on the user's 557k raster<->vector pairs:

    augmented input PNG -> clean support mask + SDF of the vector target

Supervision replays the pair builder's compose math exactly (fit-contain
extent = floor(size*scale), centered paste + shift, clamp) on the target
SVG; the v0 protocol keeps replay risk at zero by using the size==96,
rotate==0 subset (three quarters of pairs by construction). Photometric
augmentations (background/blur/noise/jpeg) need no replay - they do not
move the target.

Family-disjoint discipline: pair source_ids are partitioned by the
S11.3 splits (train/test id lists); validation families are never seen.

Gates (pilot, written before the run):
- tiny-overfit memorizes (support IoU ~1 on the tiny set);
- representative pilot must beat the Otsu-threshold baseline on unseen
  families by >= 0.05 mean support IoU AND not lose on topology edit
  distance; otherwise the recipe is parked with the numbers.

Usage:
  C:\\Python312\\python.exe train_v10_stage_d.py [--tiny-overfit]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
UBER = Path(r"C:\Users\nirrt\Toolset\v-ize train\dataset")
PAIRS_DIR = UBER / "raster_vector_pairs_full_x2"
SPLITS = UBER / "splits" / "family_disjoint"
SIZE = 96

from diagnose_vector_topology_recall import _mask_topology  # noqa: E402


def replay_target_support(
    svg_text: str, augmentation: dict, resvg_module,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Replicate the pair builder's geometry for the clean target mask."""
    from PIL import Image

    scale = float(augmentation["scale"])
    shift_x = int(augmentation["shift_x"])
    shift_y = int(augmentation["shift_y"])
    extent = max(int(SIZE * scale), 8)
    # The builder computes renderW/renderH from the record aspect, then
    # fit-contains; rendering the SVG into the extent box with resvg and
    # measuring the result reproduces the same overlay dimensions for the
    # rotate==0 subset.
    try:
        rendered = resvg_module.svg_to_bytes(
            svg_string=svg_text, width=extent, height=extent,
        )
        with Image.open(io.BytesIO(bytes(rendered))) as image:
            rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    except Exception:
        return None
    alpha = rgba[..., 3]
    ys, xs = np.nonzero(alpha >= 8)
    if not len(xs):
        return None
    overlay = alpha[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    overlay_height, overlay_width = overlay.shape
    if overlay_height > SIZE or overlay_width > SIZE:
        factor = min(SIZE / overlay_height, SIZE / overlay_width)
        overlay = cv2.resize(
            overlay,
            (max(1, int(overlay_width * factor)),
             max(1, int(overlay_height * factor))),
            interpolation=cv2.INTER_AREA,
        )
        overlay_height, overlay_width = overlay.shape
    left = max(0, min(SIZE - overlay_width,
                      (SIZE - overlay_width) // 2 + shift_x))
    top = max(0, min(SIZE - overlay_height,
                     (SIZE - overlay_height) // 2 + shift_y))
    canvas = np.zeros((SIZE, SIZE), np.uint8)
    canvas[top:top + overlay_height, left:left + overlay_width] = overlay
    coverage = canvas.astype(np.float32) / 255.0
    return coverage, coverage >= 0.5


def load_split_ids() -> tuple[set[str], set[str]]:
    train_ids = set(
        (SPLITS / "train_ids.txt").read_text(encoding="utf-8").split()
    )
    test_ids = set(
        (SPLITS / "test_ids.txt").read_text(encoding="utf-8").split()
    )
    return train_ids, test_ids


def collect_rows(
    limit_per_split: dict[str, int], *, hard_subset: bool = False,
) -> dict[str, list[dict]]:
    train_ids, test_ids = load_split_ids()
    out: dict[str, list[dict]] = {"train": [], "test": []}
    with open(PAIRS_DIR / "pairs.jsonl", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if int(row.get("size", 0)) != SIZE:
                continue
            if float(row["augmentation"].get("rotate_degrees", 0.0)) != 0.0:
                continue
            if hard_subset:
                augmentation = row["augmentation"]
                if not (
                    float(augmentation.get("blur_radius", 0)) > 0
                    or float(augmentation.get("noise_sigma", 0)) > 0
                    or augmentation.get("jpeg_quality") is not None
                ):
                    continue
            source_id = row["source_id"]
            split = (
                "train" if source_id in train_ids
                else "test" if source_id in test_ids else None
            )
            if split is None or len(out[split]) >= limit_per_split[split]:
                continue
            out[split].append(row)
            if all(
                len(out[name]) >= limit_per_split[name] for name in out
            ):
                break
    return out


def build_stage_d_net(nn, torch, in_channels: int = 3):
    """Factory: the Stage-D UNet (importable for fine-tune/booster)."""
    class StageDNet(nn.Module):
        def __init__(self, in_channels: int = 1) -> None:
            super().__init__()
            def down(cin, cout):
                return nn.Sequential(
                    nn.Conv2d(cin, cout, 3, stride=2, padding=1),
                    nn.GroupNorm(8, cout), nn.ReLU(inplace=True),
                    nn.Conv2d(cout, cout, 3, padding=1),
                    nn.GroupNorm(8, cout), nn.ReLU(inplace=True),
                )
            def up(cin, cout):
                return nn.Sequential(
                    nn.ConvTranspose2d(cin, cout, 2, stride=2),
                    nn.GroupNorm(8, cout), nn.ReLU(inplace=True),
                )
            self.d1 = down(in_channels, 32)  # 48
            self.d2 = down(32, 64)    # 24
            self.d3 = down(64, 128)   # 12
            self.d4 = down(128, 256)  # 6
            self.u3 = up(256, 128)    # 12
            self.u2 = up(256, 64)     # 24
            self.u1 = up(128, 32)     # 48
            self.u0 = up(64, 32)      # 96
            self.support_head = nn.Conv2d(32, 1, 3, padding=1)
            self.sdf_head = nn.Conv2d(32, 1, 3, padding=1)

        def forward(self, x):
            e1 = self.d1(x)
            e2 = self.d2(e1)
            e3 = self.d3(e2)
            e4 = self.d4(e3)
            y3 = torch.cat([self.u3(e4), e3], dim=1)
            y2 = torch.cat([self.u2(y3), e2], dim=1)
            y1 = torch.cat([self.u1(y2), e1], dim=1)
            y0 = self.u0(y1)
            return self.support_head(y0), torch.tanh(self.sdf_head(y0))

    return StageDNet(in_channels)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tiny-overfit", action="store_true")
    parser.add_argument(
        "--input-mode", choices=("gray", "observation"), default="gray",
        help="observation = production 3-channel features "
        "(values/threshold/edge) - the Stage-D v1 hypothesis",
    )
    parser.add_argument(
        "--degradation", choices=("pairs", "wordmark"), default="pairs",
        help="wordmark = synthesize the input by the production-calibrated "
        "brutal chain (native down/up, gamma, holes/islands, jpeg 25-90) "
        "over the replayed clean target - the S11.4 data-side card",
    )
    parser.add_argument(
        "--polarity", choices=("ink", "luminance"), default="ink",
        help="'ink' trains on raw degraded coverage (ink=1). 'luminance' "
        "reconstructs a pseudo-luminance observation ink_lum*obs + "
        "0.5*(1-obs) with ink_lum measured from the pair's actual raster "
        "at support pixels - the convention the real domain (and the "
        "real fine-tune) actually uses; icons invisible on the 0.5 "
        "composite (|ink_lum-0.5|<0.08) are skipped",
    )
    parser.add_argument(
        "--hard-subset", action="store_true",
        help="only pairs with blur/noise/jpeg degradation: Otsu saturates "
        "the easy pairs and drowns the model's value in the aggregate",
    )
    parser.add_argument("--train-samples", type=int, default=16000)
    parser.add_argument("--val-samples", type=int, default=2000)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument(
        "--gate", choices=("iou", "topology"), default="iou",
        help="topology = the S16.1-aligned gate (metric hierarchy puts "
        "topology edit first, pixel IoU last): model edit <= baseline/3 "
        "AND IoU not worse than baseline - 0.01",
    )
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "benchmarks" / "pcdc_pre_v14"
        / "stage_d_v0_pilot_report.json",
    )
    parser.add_argument(
        "--checkpoint", type=Path,
        default=ROOT / "models" / "stage_d_v0_pilot.pt",
    )
    args = parser.parse_args()

    sys.path.insert(
        0, str(ROOT / ".training_snapshots" / "wordmark_full_v4_20260723"),
    )
    import resvg_py
    import torch
    from torch import nn
    from vice_compiler.wordmark_prior_data import signed_distance_target

    started = time.perf_counter()
    torch.manual_seed(args.seed)
    if args.tiny_overfit:
        limits = {"train": 96, "test": 96}
    else:
        limits = {"train": args.train_samples, "test": args.val_samples}
    print("collecting pair rows...", flush=True)
    rows = collect_rows(limits, hard_subset=args.hard_subset)
    print({name: len(items) for name, items in rows.items()}, flush=True)

    channels = 3 if args.input_mode == "observation" else 1
    from vice_compiler.wordmark_prior_data import (
        degrade_wordmark,
        wordmark_observation_features,
    )
    import hashlib as _hashlib

    def build_bank(items: list[dict]):
        count = len(items)
        inputs = np.zeros((count, channels, SIZE, SIZE), np.float32)
        supports = np.zeros((count, SIZE, SIZE), bool)
        sdfs = np.zeros((count, SIZE, SIZE), np.float32)
        kept = 0
        for row in items:
            png_path = PAIRS_DIR / row["input_png"]
            svg_path = PAIRS_DIR / row["target_svg"]
            try:
                raw = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
                svg_text = svg_path.read_text(encoding="utf-8")
            except OSError:
                continue
            if raw is None or raw.shape[:2] != (SIZE, SIZE):
                continue
            if raw.ndim == 3 and raw.shape[2] == 4:
                # "transparent" background pairs keep alpha; a grayscale
                # read collapses it to black and a dark icon vanishes.
                # Composite over neutral gray so ink stays visible
                # whatever its colour.
                alpha = raw[..., 3:4].astype(np.float32) / 255.0
                rgb = raw[..., :3].astype(np.float32)
                composited = rgb * alpha + 128.0 * (1.0 - alpha)
                raster = cv2.cvtColor(
                    composited.astype(np.uint8), cv2.COLOR_BGR2GRAY,
                )
            elif raw.ndim == 3:
                raster = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
            else:
                raster = raw
            replayed = replay_target_support(
                svg_text, row["augmentation"], resvg_py,
            )
            if replayed is None:
                continue
            coverage, support = replayed
            if not support.any():
                continue
            if args.degradation == "wordmark":
                degrade_seed = int(_hashlib.sha256(
                    row["id"].encode("utf-8")
                ).hexdigest()[:8], 16)
                observed = degrade_wordmark(
                    coverage, support, seed=degrade_seed,
                )
                if args.polarity == "luminance":
                    # raster still holds the pair's true composited gray
                    # here; the reassignment below overwrites it.
                    ink_lum = float(np.median(raster[support])) / 255.0
                    if abs(ink_lum - 0.5) < 0.08:
                        continue
                    observed = (
                        ink_lum * observed + 0.5 * (1.0 - observed)
                    )
                raster = np.rint(
                    np.clip(observed, 0.0, 1.0) * 255.0
                ).astype(np.uint8)
            values = raster.astype(np.float32) / 255.0
            if channels == 3:
                inputs[kept] = wordmark_observation_features(values)
            else:
                inputs[kept] = values[None]
            supports[kept] = support
            sdfs[kept] = signed_distance_target(support)
            kept += 1
            if kept % 2000 == 0:
                print(f"prepared {kept}", flush=True)
        return inputs[:kept], supports[:kept], sdfs[:kept]

    print("preparing train bank...", flush=True)
    train_inputs, train_supports, train_sdfs = build_bank(rows["train"])
    if args.tiny_overfit:
        val_inputs, val_supports = train_inputs, train_supports
    else:
        print("preparing val bank...", flush=True)
        val_inputs, val_supports, _val_sdfs = build_bank(rows["test"])
    print(
        f"banks: train {len(train_inputs)}, val {len(val_inputs)}",
        flush=True,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = build_stage_d_net(nn, torch, channels).to(device)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=1e-3 if args.tiny_overfit else 3e-4,
    )
    bce = nn.BCEWithLogitsLoss()
    l1 = nn.L1Loss()
    count = len(train_inputs)
    order = np.arange(count)
    rng = np.random.default_rng(args.seed)
    epochs = 1100 if args.tiny_overfit else args.epochs
    steps_per_epoch = max(1, (count + args.batch_size - 1) // args.batch_size)
    total_steps = 2000 if args.tiny_overfit else epochs * steps_per_epoch
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=total_steps,
    )
    steps = 0
    for epoch in range(epochs):
        model.train()
        rng.shuffle(order)
        total = 0.0
        for start in range(0, count, args.batch_size):
            batch = order[start:start + args.batch_size]
            x = torch.from_numpy(train_inputs[batch]).to(device)
            y_support = torch.from_numpy(
                train_supports[batch].astype(np.float32),
            )[:, None].to(device)
            y_sdf = torch.from_numpy(train_sdfs[batch])[:, None].to(device)
            optimizer.zero_grad()
            support_logits, sdf = model(x)
            loss = bce(support_logits, y_support) + 0.5 * l1(sdf, y_sdf)
            loss.backward()
            optimizer.step()
            scheduler.step()
            total += float(loss.detach())
            steps += 1
            if args.tiny_overfit and steps >= 2000:
                break
        print(f"epoch {epoch + 1}: loss {total:.2f}", flush=True)
        if args.tiny_overfit and steps >= 2000:
            break

    model.eval()
    model_iou = []
    model_edit = []
    baseline_iou = []
    baseline_edit = []
    with torch.no_grad():
        for start in range(0, len(val_inputs), args.batch_size):
            stop = min(start + args.batch_size, len(val_inputs))
            x = torch.from_numpy(val_inputs[start:stop]).to(device)
            support_logits, _sdf = model(x)
            predicted = (
                torch.sigmoid(support_logits)[:, 0].cpu().numpy() >= 0.5
            )
            for i in range(stop - start):
                truth = val_supports[start + i]
                truth_topology = _mask_topology(truth)
                mask = predicted[i]
                union = np.sum(mask | truth)
                model_iou.append(np.sum(mask & truth) / max(1, union))
                topo = _mask_topology(mask)
                model_edit.append(
                    abs(topo[0] - truth_topology[0])
                    + abs(topo[1] - truth_topology[1])
                )
                gray = np.rint(
                    val_inputs[start + i][0] * 255.0,
                ).astype(np.uint8)
                _thr, otsu = cv2.threshold(
                    gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU,
                )
                best_iou, best_edit = -1.0, None
                for candidate in (otsu >= 128, otsu < 128):
                    union = np.sum(candidate | truth)
                    iou = np.sum(candidate & truth) / max(1, union)
                    if iou > best_iou:
                        topo = _mask_topology(candidate)
                        best_iou = iou
                        best_edit = (
                            abs(topo[0] - truth_topology[0])
                            + abs(topo[1] - truth_topology[1])
                        )
                baseline_iou.append(best_iou)
                baseline_edit.append(best_edit)
    metrics = {
        "model_support_iou": float(np.mean(model_iou)),
        "model_topology_edit": float(np.mean(model_edit)),
        "otsu_baseline_iou": float(np.mean(baseline_iou)),
        "otsu_baseline_edit": float(np.mean(baseline_edit)),
    }
    if args.tiny_overfit:
        gate = {"memorizes": metrics["model_support_iou"] >= 0.97}
    elif args.gate == "topology":
        gate = {
            "topology_edit_3x_better": (
                metrics["model_topology_edit"]
                <= metrics["otsu_baseline_edit"] / 3.0
            ),
            "iou_not_worse": (
                metrics["model_support_iou"]
                >= metrics["otsu_baseline_iou"] - 0.01
            ),
        }
    else:
        gate = {
            "beats_otsu_iou_by_5pt": (
                metrics["model_support_iou"]
                >= metrics["otsu_baseline_iou"] + 0.05
            ),
            "not_worse_topology_edit": (
                metrics["model_topology_edit"]
                <= metrics["otsu_baseline_edit"]
            ),
        }
    report = {
        "schema": "vice-v10-stage-d-pilot/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "tiny-overfit" if args.tiny_overfit else
                "representative-pilot",
        "protocol": "pairs size==96 rotate==0; family-disjoint splits",
        "input_mode": args.input_mode,
        "hard_subset": bool(args.hard_subset),
        "metrics": metrics,
        "gate": gate,
        "gate_pass": bool(all(gate.values())),
        "train_samples": int(len(train_inputs)),
        "val_samples": int(len(val_inputs)),
        "seed": int(args.seed),
        "device": str(device),
        "authorizes_full_training": False,
        "elapsed_seconds": time.perf_counter() - started,
    }
    if not args.tiny_overfit:
        args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "schema": "vice-stage-d-checkpoint/v0-pilot",
            "state_dict": model.state_dict(),
            "report": report,
        }, args.checkpoint)
        report["checkpoint"] = str(args.checkpoint)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"mode": report["mode"], "metrics": metrics,
                      "gate": gate, "gate_pass": report["gate_pass"]},
                     indent=1))
    print(f"report -> {args.out}")


if __name__ == "__main__":
    main()

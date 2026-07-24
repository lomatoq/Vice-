"""Stage-D real-domain fine-tune on the user's reviewed masks.

The H5 verdict (ledger 93): the synthetic 7.56x advantage does not cross
the synthetic->real gap. The real masks ALREADY EXIST - all 300 v1 loci
carry human-reviewed support_rle. This fine-tunes the gate-passed full-run
candidate on them:

    real logo ROI (gray) -> the user's reviewed support mask

Split 80/20 deterministic by locus id (no family concept on real loci;
id-hash split, recorded). Gate: on the held-out real loci the fine-tuned
model must beat BOTH the classical Otsu baseline and the pre-finetune
candidate on mean IoU, and not lose topology edit. Checkpoint saved under
the booster-compatible schema so --stage-d-booster can pick it up via
VICE_STAGE_D_CHECKPOINT.

Usage:
  C:\\Python312\\python.exe train_v10_stage_d_realft.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "datasets" / "pcdc_real_loci_v1"
SIZE = 96
CANVAS = (SIZE, SIZE)  # set from --canvas in main()

from diagnose_vector_topology_recall import _mask_topology  # noqa: E402
from train_v10_stage_d import build_stage_d_net  # noqa: E402


def _letterbox_pair(
    gray: np.ndarray, mask: np.ndarray,
    canvas: tuple[int, int] = (SIZE, SIZE),
    *, baseline_area: bool = False,
):
    """Aspect-preserving letterbox of (gray, mask) into the canvas."""
    canvas_h, canvas_w = canvas
    height, width = gray.shape
    factor = min(canvas_h / height, canvas_w / width)
    new_w = max(1, int(round(width * factor)))
    new_h = max(1, int(round(height * factor)))
    # INTER_AREA degenerates to blocky nearest on UPSCALE - an artifact
    # the synthetic bank (cubic upsample in degrade_wordmark) never
    # contains; real line ROIs upscale ~2x into the 96x384 canvas.
    # baseline_area forces AREA regardless: the classical Otsu baseline
    # must not be judged on the model's input transform (the cubic
    # letterbox collapsed Otsu to edit 116 - a vacuous gate, ledger 102).
    if baseline_area:
        interpolation = cv2.INTER_AREA
    else:
        interpolation = (
            cv2.INTER_CUBIC if factor > 1.0 else cv2.INTER_AREA
        )
    gray_r = cv2.resize(gray, (new_w, new_h), interpolation=interpolation)
    mask_r = cv2.resize(
        mask.astype(np.uint8), (new_w, new_h),
        interpolation=cv2.INTER_NEAREST,
    ) > 0
    gray_out = np.full((canvas_h, canvas_w), 0.5, np.float32)
    mask_out = np.zeros((canvas_h, canvas_w), bool)
    y = (canvas_h - new_h) // 2
    x = (canvas_w - new_w) // 2
    gray_out[y:y + new_h, x:x + new_w] = gray_r
    mask_out[y:y + new_h, x:x + new_w] = mask_r
    return gray_out, mask_out


def load_real_samples():
    from vice_compiler.experiment1_evidence_coverage import decode_support_rle

    manifest = json.loads(
        (CORPUS / "manifest.json").read_text(encoding="utf-8"),
    )
    reviews = json.loads(
        (CORPUS / "review.json").read_text(encoding="utf-8"),
    )["reviews"]
    samples = []
    skipped = 0
    for row in manifest["loci"]:
        review = reviews.get(row["id"])
        if not review or not review.get("support_rle"):
            continue
        raw = cv2.imread(str(row["source"]["path"]), cv2.IMREAD_UNCHANGED)
        if raw is None:
            skipped += 1
            continue
        if raw.ndim == 3 and raw.shape[2] == 4:
            alpha = raw[..., 3:4].astype(np.float32) / 255.0
            rgb = raw[..., :3].astype(np.float32)
            composited = rgb * alpha + 128.0 * (1.0 - alpha)
            gray = cv2.cvtColor(
                composited.astype(np.uint8), cv2.COLOR_BGR2GRAY,
            )
        elif raw.ndim == 3:
            gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
        else:
            gray = raw
        support_w, support_h = (int(v) for v in review["support_size"])
        mask = decode_support_rle(
            review["support_rle"], support_w, support_h,
        )
        if mask.shape != gray.shape:
            mask = cv2.resize(
                mask.astype(np.uint8),
                (gray.shape[1], gray.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            ) > 0
        x1, y1, x2, y2 = (int(v) for v in review["roi_xyxy"])
        pad = 6
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2 = min(gray.shape[1], x2 + pad)
        y2 = min(gray.shape[0], y2 + pad)
        if x2 - x1 < 8 or y2 - y1 < 8 or not mask[y1:y2, x1:x2].any():
            skipped += 1
            continue
        roi_aspect = (x2 - x1) / max(1, y2 - y1)
        gray_roi = gray[y1:y2, x1:x2].astype(np.float32) / 255.0
        gray_96, mask_96 = _letterbox_pair(
            gray_roi, mask[y1:y2, x1:x2], canvas=CANVAS,
        )
        gray_area, _mask_area = _letterbox_pair(
            gray_roi, mask[y1:y2, x1:x2], canvas=CANVAS,
            baseline_area=True,
        )
        bucket = int(hashlib.sha256(
            row["id"].encode("utf-8"),
        ).hexdigest()[:8], 16) % 100
        samples.append({
            "id": row["id"],
            "gray": gray_96,
            "mask": mask_96,
            "gray_area": gray_area,
            "roi_aspect": roi_aspect,
            "split": "val" if bucket < 20 else "train",
        })
    return samples, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-checkpoint", type=Path,
        default=ROOT / "models" / "stage_d_full_candidate_v1.pt",
    )
    parser.add_argument(
        "--mix-attested", type=int, default=0,
        help="add N of the user's 8849 attested uber-verify records to the "
        "training mix (masks = render alpha, perfect by construction; "
        "inputs = wordmark-grade degradation of the clean render); real "
        "samples are replicated x10 to balance domains",
    )
    parser.add_argument(
        "--mix-polarity", choices=("ink", "luminance"), default="ink",
        help="'ink' feeds degraded coverage directly (ink=1: the OPPOSITE "
        "polarity of the real luminance rows - kept as the recorded default "
        "of the first mix experiments); 'luminance' reconstructs a pseudo-"
        "luminance observation ink_lum*obs + 0.5*(1-obs) from the icon's "
        "actual ink luminance, matching the real-row convention",
    )
    parser.add_argument(
        "--aspect-min", type=float, default=0.0,
        help="keep only real ROIs with native aspect (w/h) above this - "
        "the specialist gate for the line model (S16.2 class floor): it "
        "deploys only on aspect>2.5 ROIs, so training and gating on the "
        "full mixed-real set mis-specifies both",
    )
    parser.add_argument(
        "--canvas", default="96x96",
        help="HxW letterbox canvas; '96x384' is the line canvas matching "
        "the line pretrain - long real ROIs keep glyph height instead of "
        "shrinking 4x into the square (both dims must be /16)",
    )
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=20260732)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "benchmarks" / "pcdc_pre_v14"
        / "stage_d_realft_report.json",
    )
    parser.add_argument(
        "--checkpoint", type=Path,
        default=ROOT / "models" / "stage_d_realft_candidate_v1.pt",
    )
    args = parser.parse_args()

    global CANVAS
    canvas_h, canvas_w = (int(v) for v in args.canvas.lower().split("x"))
    if canvas_h % 16 or canvas_w % 16:
        raise SystemExit("--canvas dims must be divisible by 16")
    CANVAS = (canvas_h, canvas_w)

    sys.path.insert(
        0, str(ROOT / ".training_snapshots" / "wordmark_full_v4_20260723"),
    )
    import torch
    from torch import nn
    from vice_compiler.wordmark_prior_data import (
        signed_distance_target,
        wordmark_observation_features,
    )

    started = time.perf_counter()
    torch.manual_seed(args.seed)
    samples, skipped = load_real_samples()
    if args.aspect_min > 0:
        before = len(samples)
        samples = [
            s for s in samples if s["roi_aspect"] >= args.aspect_min
        ]
        print(f"aspect>={args.aspect_min} filter: {len(samples)}/{before}",
              flush=True)
    train = [s for s in samples if s["split"] == "train"]
    val = [s for s in samples if s["split"] == "val"]
    print(f"real samples: train {len(train)}, val {len(val)}, "
          f"skipped {skipped}", flush=True)

    def to_bank(rows):
        inputs = np.stack([
            wordmark_observation_features(r["gray"]) for r in rows
        ])
        masks = np.stack([r["mask"] for r in rows])
        sdfs = np.stack([
            signed_distance_target(r["mask"]) for r in rows
        ])
        return inputs.astype(np.float32), masks, sdfs.astype(np.float32)

    if args.mix_attested:
        import hashlib as _hashlib

        from vice_compiler.wordmark_prior_data import degrade_wordmark

        v3 = json.loads(
            (ROOT / "datasets" / "pcdc_uber_verify_v3" / "manifest.json")
            .read_text(encoding="utf-8"),
        )
        rows = sorted(
            v3["loci"],
            key=lambda row: _hashlib.sha256(
                row["id"].encode()
            ).hexdigest(),
        )[:args.mix_attested]
        added = 0
        for row in rows:
            raw = cv2.imread(str(row["source"]["path"]), cv2.IMREAD_UNCHANGED)
            if raw is None or raw.ndim != 3 or raw.shape[2] != 4:
                continue
            alpha = raw[..., 3].astype(np.float32) / 255.0
            mask = alpha >= 0.5
            if not mask.any():
                continue
            degrade_seed = int(_hashlib.sha256(
                row["id"].encode(),
            ).hexdigest()[:8], 16)
            observed = degrade_wordmark(alpha, mask, seed=degrade_seed)
            if args.mix_polarity == "luminance":
                rgb = raw[..., :3].astype(np.float32) / 255.0  # BGR
                lum = (
                    0.0722 * rgb[..., 0] + 0.7152 * rgb[..., 1]
                    + 0.2126 * rgb[..., 2]
                )
                ink_lum = float(np.median(lum[mask]))
                # An icon whose ink sits at the 0.5 composite background is
                # invisible to the real-domain convention; skip, do not teach
                # the model to hallucinate ink out of flat gray.
                if abs(ink_lum - 0.5) < 0.08:
                    continue
                observed = ink_lum * observed + 0.5 * (1.0 - observed)
            gray_96, mask_96 = _letterbox_pair(
                np.clip(observed, 0.0, 1.0).astype(np.float32), mask,
                canvas=CANVAS,
            )
            train.append({
                "id": row["id"], "gray": gray_96,
                "mask": mask_96, "split": "train",
            })
            added += 1
        # Replicate the real rows to keep the real domain from drowning.
        real_rows = [s for s in train if not s["id"].startswith(
            ("small_shape-", "text-")
        ) or "-" not in s["id"][:5]]
        real_rows = [s for s in train if s["id"] in {
            r["id"] for r in samples if r["split"] == "train"
        }]
        train.extend(real_rows * 9)
        print(f"mixed bank: +{added} attested, real x10 -> "
              f"{len(train)} train rows", flush=True)

    train_x, train_m, train_s = to_bank(train)
    val_x, val_m, _val_s = to_bank(val)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    payload = torch.load(
        args.base_checkpoint, map_location="cpu", weights_only=False,
    )
    model = build_stage_d_net(nn, torch, 3)
    model.load_state_dict(payload["state_dict"], strict=True)
    model = model.to(device)

    def evaluate(net):
        net.eval()
        model_iou, model_edit = [], []
        with torch.no_grad():
            logits, _ = net(torch.from_numpy(val_x).to(device))
            predicted = (
                torch.sigmoid(logits)[:, 0].cpu().numpy() >= 0.5
            )
        for i in range(len(val)):
            truth = val_m[i]
            truth_topo = _mask_topology(truth)
            mask = predicted[i]
            union = np.sum(mask | truth)
            model_iou.append(np.sum(mask & truth) / max(1, union))
            topo = _mask_topology(mask)
            model_edit.append(
                abs(topo[0] - truth_topo[0]) + abs(topo[1] - truth_topo[1]),
            )
        return float(np.mean(model_iou)), float(np.mean(model_edit))

    pre_iou, pre_edit = evaluate(model)

    # Otsu baseline on the same real crops.
    otsu_iou, otsu_edit = [], []
    for i in range(len(val)):
        gray = np.rint(val[i]["gray_area"] * 255.0).astype(np.uint8)
        truth = val_m[i]
        truth_topo = _mask_topology(truth)
        _t, otsu = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        best = (-1.0, None)
        for candidate in (otsu >= 128, otsu < 128):
            union = np.sum(candidate | truth)
            iou = np.sum(candidate & truth) / max(1, union)
            if iou > best[0]:
                best = (iou, candidate)
        otsu_iou.append(best[0])
        topo = _mask_topology(best[1])
        otsu_edit.append(
            abs(topo[0] - truth_topo[0]) + abs(topo[1] - truth_topo[1]),
        )
    otsu_iou_mean = float(np.mean(otsu_iou))
    otsu_edit_mean = float(np.mean(otsu_edit))

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    bce = nn.BCEWithLogitsLoss()
    l1 = nn.L1Loss()
    count = len(train)
    order = np.arange(count)
    rng = np.random.default_rng(args.seed)
    steps_per_epoch = max(1, (count + args.batch_size - 1) // args.batch_size)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs * steps_per_epoch,
    )
    for epoch in range(args.epochs):
        model.train()
        rng.shuffle(order)
        total = 0.0
        for start in range(0, count, args.batch_size):
            rows = order[start:start + args.batch_size]
            x = torch.from_numpy(train_x[rows]).to(device)
            y_mask = torch.from_numpy(
                train_m[rows].astype(np.float32),
            )[:, None].to(device)
            y_sdf = torch.from_numpy(train_s[rows])[:, None].to(device)
            optimizer.zero_grad()
            logits, sdf = model(x)
            loss = bce(logits, y_mask) + 0.5 * l1(sdf, y_sdf)
            loss.backward()
            optimizer.step()
            scheduler.step()
            total += float(loss.detach())
        if (epoch + 1) % 20 == 0:
            print(f"epoch {epoch + 1}: loss {total:.3f}", flush=True)

    post_iou, post_edit = evaluate(model)
    metrics = {
        "pre_finetune_iou": pre_iou, "pre_finetune_edit": pre_edit,
        "post_finetune_iou": post_iou, "post_finetune_edit": post_edit,
        "otsu_iou": otsu_iou_mean, "otsu_edit": otsu_edit_mean,
    }
    gate = {
        "beats_otsu_iou": post_iou > otsu_iou_mean,
        "beats_pre_finetune_iou": post_iou > pre_iou,
        "not_worse_edit_than_otsu": post_edit <= otsu_edit_mean,
    }
    report = {
        "schema": "vice-stage-d-realft/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": "300 human-reviewed v1 loci masks, id-hash 80/20 split",
        "base_checkpoint": str(args.base_checkpoint),
        "metrics": metrics,
        "gate": gate,
        "gate_pass": bool(all(gate.values())),
        "train_samples": len(train), "val_samples": len(val),
        "seed": int(args.seed),
        "device": str(device),
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "schema": "vice-stage-d-checkpoint/v0-pilot",
        "state_dict": model.state_dict(),
        "report": report,
    }, args.checkpoint)
    report["checkpoint"] = str(args.checkpoint)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": metrics, "gate": gate,
                      "gate_pass": report["gate_pass"]}, indent=1))
    print(f"report -> {args.out}")


if __name__ == "__main__":
    main()

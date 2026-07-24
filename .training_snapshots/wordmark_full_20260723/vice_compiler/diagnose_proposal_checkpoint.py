"""Read-only geometry/type/rank decomposition for a ProposalNet checkpoint."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment
import torch
from torch.utils.data import DataLoader

from .proposal_net import QUERY_FAMILIES, ProposalNet, ProposalNetConfig
from .train_proposal_net_large import (
    PairDataset, _collate, _read_pairs, _soft_iou, _split_group,
    _stable_bucket, _svg_families,
)


PROJECT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _matched(
    probability: np.ndarray, confidence: np.ndarray, supports: np.ndarray,
    row: dict, *, cutoff: int, typed: bool,
) -> dict[int, tuple[float, int]]:
    predicted = np.argmax(probability[:, :-1], axis=-1)
    score = np.max(probability[:, :-1], axis=-1) * confidence
    order = np.argsort(-score)[:min(cutoff, len(score))]
    result: dict[int, tuple[float, int]] = {}
    if typed:
        groups = [
            (
                np.flatnonzero(row["family"] == family_index),
                np.asarray([
                    query for query in order
                    if int(predicted[query]) == int(family_index)
                ], np.int64),
            )
            for family_index in sorted(set(row["family"].tolist()))
        ]
    else:
        groups = [(np.arange(len(row["family"])), np.asarray(order, np.int64))]
    for target_ids, query_ids in groups:
        if not len(target_ids) or not len(query_ids):
            continue
        ious = np.asarray([
            [
                _soft_iou(supports[query], row["support"][target])
                for target in target_ids
            ]
            for query in query_ids
        ], np.float64)
        query_match, target_match = linear_sum_assignment(-ious)
        for query_local, target_local in zip(query_match, target_match):
            target = int(target_ids[target_local])
            query = int(query_ids[query_local])
            result[target] = (float(ious[query_local, target_local]), query)
    return result


def _bbox_gate_supports(
    supports: np.ndarray, boxes: np.ndarray, *, padding: float = 0.0,
    query_mask: np.ndarray | None = None, axis: str = "xy",
    softness: float = 0.0,
) -> np.ndarray:
    """Restrict each soft support to its own normalized predicted ROI."""
    if axis not in {"xy", "y"}:
        raise ValueError("bbox support gate axis must be xy or y")
    result = np.asarray(supports, np.float32).copy()
    height, width = result.shape[-2:]
    y = (np.arange(height, dtype=np.float32) + 0.5) / height
    x = (np.arange(width, dtype=np.float32) + 0.5) / width
    for query, (x1, y1, x2, y2) in enumerate(np.asarray(boxes)):
        if query_mask is not None and not bool(query_mask[query]):
            continue
        if softness > 0.0:
            sigmoid = lambda value: 1.0 / (1.0 + np.exp(-value))
            gate = sigmoid((y[:, None] - float(y1) + padding) / softness)
            gate *= sigmoid((float(y2) + padding - y[:, None]) / softness)
            if axis == "xy":
                gate *= sigmoid((x[None, :] - float(x1) + padding) / softness)
                gate *= sigmoid((float(x2) + padding - x[None, :]) / softness)
        else:
            gate = (
                (y[:, None] >= float(y1) - padding)
                & (y[:, None] <= float(y2) + padding)
            )
            if axis == "xy":
                gate = (
                    gate
                    & (x[None, :] >= float(x1) - padding)
                    & (x[None, :] <= float(x2) + padding)
                )
        result[query] *= gate
    return result


def _empty_row() -> dict[str, int | float]:
    return {
        "instances": 0, "geometry_any_at_32": 0,
        "typed_at_32": 0, "typed_at_5": 0,
        "geometry_best_iou_sum": 0.0,
        "typed32_best_iou_sum": 0.0,
        "typed5_best_iou_sum": 0.0,
    }


def _finish(row: dict[str, int | float]) -> dict[str, float | int]:
    count = max(1, row["instances"])
    geometry = row["geometry_any_at_32"] / count
    typed32 = row["typed_at_32"] / count
    typed5 = row["typed_at_5"] / count
    return {
        **row,
        "geometry_any_recall_at_32": geometry,
        "typed_recall_at_32": typed32,
        "typed_recall_at_5": typed5,
        "geometry_loss_fraction": 1.0 - geometry,
        "type_loss_fraction": max(0.0, geometry - typed32),
        "rank_loss_fraction": max(0.0, typed32 - typed5),
        "mean_geometry_best_iou_at_32": float(
            row.get("geometry_best_iou_sum", 0.0)
        ) / count,
        "mean_typed_best_iou_at_32": float(
            row.get("typed32_best_iou_sum", 0.0)
        ) / count,
        "mean_typed_best_iou_at_5": float(
            row.get("typed5_best_iou_sum", 0.0)
        ) / count,
    }


def diagnose(
    checkpoint: Path, pair_root: Path, filter_cache: Path,
    *, device_name: str = "auto", workers: int = 4,
    bbox_gate_padding: float | None = None,
    bbox_gate_family: str | None = None, source_filter: str | None = None,
    bbox_gate_axis: str = "xy",
    bbox_gate_softness: float = 0.0,
) -> dict:
    accepted = set(json.loads(filter_cache.read_text("utf-8"))["accepted_ids"])
    rows = [
        row for row in _read_pairs(pair_root, None)
        if str(row["id"]) in accepted
    ]
    split = [
        row for row in rows
        if _stable_bucket(_split_group(row)) == "test"
        and (source_filter is None or str(row.get("source", "")) == source_filter)
    ]
    family_cache = {}
    families = {}
    for row in split:
        key = (
            str(row.get("source", "")), str(row.get("source_id", "")),
            str(row.get("target_svg", "")),
        )
        if key not in family_cache:
            family_cache[key] = _svg_families(row, pair_root)
        families[row["id"]] = family_cache[key]

    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    config = ProposalNetConfig(**payload["config"])
    dataset = PairDataset(
        split, pair_root, families, image_size=128,
        parameter_dim=config.parameter_dim,
        support_size=(128 // 4) * int(config.mask_upsample),
    )
    loader = DataLoader(
        dataset, batch_size=16, shuffle=False, num_workers=workers,
        persistent_workers=workers > 0,
        prefetch_factor=4 if workers > 0 else None,
        collate_fn=_collate, pin_memory=torch.cuda.is_available(),
    )
    if device_name == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_name)
    model = ProposalNet(config).to(device)
    model.load_state_dict(payload["model"])
    model.eval()
    metadata = {str(row["id"]): row for row in split}
    by_family = defaultdict(_empty_row)
    by_slice = defaultdict(_empty_row)
    type_confusions = Counter()
    top5_family_slots = Counter()
    row_count = 0

    with torch.no_grad():
        for batch in loader:
            images = torch.as_tensor(
                np.stack([row["rgba"] for row in batch]), device=device,
            )
            output = model(images)
            probability = output["family_logits"].softmax(-1).cpu().numpy()
            confidence = torch.sigmoid(
                output["confidence_logits"],
            ).cpu().numpy()
            supports = torch.sigmoid(output["support_logits"]).cpu().numpy()
            boxes = output["bbox"].cpu().numpy()
            for offset, row in enumerate(batch):
                row_count += 1
                predicted = np.argmax(probability[offset, :, :-1], axis=-1)
                score = (
                    np.max(probability[offset, :, :-1], axis=-1)
                    * confidence[offset]
                )
                for query in np.argsort(-score)[:5]:
                    top5_family_slots[QUERY_FAMILIES[int(predicted[query])]] += 1
                row_supports = supports[offset]
                if bbox_gate_padding is not None:
                    query_mask = None
                    if bbox_gate_family is not None:
                        query_mask = predicted == QUERY_FAMILIES.index(
                            bbox_gate_family
                        )
                    row_supports = _bbox_gate_supports(
                        row_supports, boxes[offset], padding=bbox_gate_padding,
                        query_mask=query_mask, axis=bbox_gate_axis,
                        softness=bbox_gate_softness,
                    )
                geometry32 = _matched(
                    probability[offset], confidence[offset], row_supports,
                    row, cutoff=32, typed=False,
                )
                typed32 = _matched(
                    probability[offset], confidence[offset], row_supports,
                    row, cutoff=32, typed=True,
                )
                typed5 = _matched(
                    probability[offset], confidence[offset], row_supports,
                    row, cutoff=5, typed=True,
                )
                local_counts = Counter(
                    QUERY_FAMILIES[int(index)] for index in row["family"]
                )
                raw = metadata[row["id"]]
                source = str(raw.get("source", "unknown"))
                for target, family_index in enumerate(row["family"].tolist()):
                    family = QUERY_FAMILIES[int(family_index)]
                    geometry_iou, geometry_query = geometry32.get(
                        target, (0.0, -1),
                    )
                    typed32_iou = typed32.get(target, (0.0, -1))[0]
                    typed5_iou = typed5.get(target, (0.0, -1))[0]
                    values = (
                        int(geometry_iou >= 0.50),
                        int(typed32_iou >= 0.50),
                        int(typed5_iou >= 0.50),
                    )
                    slices = [f"family:{family}", f"source:{source}:{family}"]
                    if family in {"text_line", "glyph_group"}:
                        area = float(np.mean(row["support"][target] > 0.0))
                        area_bin = "lt1pct" if area < .01 else (
                            "1to3pct" if area < .03 else "ge3pct"
                        )
                        slices.extend((
                            f"text-area:{area_bin}:{family}",
                            f"text-layout:{'multi' if local_counts[family] > 1 else 'single'}:{family}",
                        ))
                        size = int(raw.get("size") or 0)
                        size_bin = "le64" if size <= 64 else (
                            "96to128" if size <= 128 else "ge192"
                        )
                        slices.append(f"text-canvas:{size_bin}:{family}")
                        if family == "text_line":
                            slices.append(
                                f"text-owner-count:{local_counts[family]}:{family}"
                            )
                        augmentation = raw.get("augmentation", {})
                        degradation = []
                        if augmentation.get("jpeg_quality") is not None:
                            degradation.append("jpeg")
                        if float(augmentation.get("blur_radius") or 0.0) > 0.0:
                            degradation.append("blur")
                        if float(augmentation.get("noise_sigma") or 0.0) > 0.0:
                            degradation.append("noise")
                        slices.append(
                            f"text-degradation:{'+'.join(degradation) or 'clean'}:{family}"
                        )
                    for key in slices:
                        target_row = by_slice[key]
                        target_row["instances"] += 1
                        target_row["geometry_any_at_32"] += values[0]
                        target_row["typed_at_32"] += values[1]
                        target_row["typed_at_5"] += values[2]
                        target_row["geometry_best_iou_sum"] += geometry_iou
                        target_row["typed32_best_iou_sum"] += typed32_iou
                        target_row["typed5_best_iou_sum"] += typed5_iou
                    target_row = by_family[family]
                    target_row["instances"] += 1
                    target_row["geometry_any_at_32"] += values[0]
                    target_row["typed_at_32"] += values[1]
                    target_row["typed_at_5"] += values[2]
                    target_row["geometry_best_iou_sum"] += geometry_iou
                    target_row["typed32_best_iou_sum"] += typed32_iou
                    target_row["typed5_best_iou_sum"] += typed5_iou
                    if values[0] and not values[1] and geometry_query >= 0:
                        wrong = QUERY_FAMILIES[int(predicted[geometry_query])]
                        type_confusions[(family, wrong)] += 1

    return {
        "schema": "pcdc-proposal-failure-decomposition/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": _sha256(checkpoint),
        "pair_root": str(pair_root.resolve()),
        "pairs_jsonl_sha256": _sha256(pair_root / "pairs.jsonl"),
        "filter_cache_sha256": _sha256(filter_cache),
        "device": str(device), "test_rows": row_count,
        "bbox_gate_padding": bbox_gate_padding,
        "bbox_gate_family": bbox_gate_family,
        "bbox_gate_axis": bbox_gate_axis,
        "bbox_gate_softness": bbox_gate_softness,
        "source_filter": source_filter,
        "by_family": {
            key: _finish(value) for key, value in sorted(by_family.items())
        },
        "by_slice": {
            key: _finish(value) for key, value in sorted(by_slice.items())
        },
        "geometry_type_confusions": [
            {"target": target, "predicted": predicted, "instances": count}
            for (target, predicted), count in sorted(
                type_confusions.items(), key=lambda item: (-item[1], item[0]),
            )
        ],
        "global_top5_predicted_family_slots": dict(top5_family_slots),
        "interpretation": (
            "geometry loss = no any-family one-to-one IoU>=0.5 in global top32; "
            "type loss = geometry exists but no correctly typed top32 match; "
            "rank loss = typed top32 match exists but not in global top5"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--filter-cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--bbox-gate-padding", type=float,
        help="diagnostic hard ROI gate padding in normalized canvas units",
    )
    parser.add_argument("--bbox-gate-family", choices=QUERY_FAMILIES[:-1])
    parser.add_argument("--bbox-gate-axis", choices=("xy", "y"), default="xy")
    parser.add_argument("--bbox-gate-softness", type=float, default=0.0)
    parser.add_argument("--source")
    args = parser.parse_args()
    report = diagnose(
        args.checkpoint, args.pair_root, args.filter_cache,
        device_name=args.device, workers=args.workers,
        bbox_gate_padding=args.bbox_gate_padding,
        bbox_gate_family=args.bbox_gate_family, source_filter=args.source,
        bbox_gate_axis=args.bbox_gate_axis,
        bbox_gate_softness=args.bbox_gate_softness,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    print(json.dumps({
        "out": str(args.out), "checkpoint_sha256": report["checkpoint_sha256"],
        "test_rows": report["test_rows"],
    }, indent=2))


if __name__ == "__main__":
    main()

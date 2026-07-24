"""Train-only tiny-overfit probe for ProposalNet instance supervision.

This is a diagnostic, not a candidate-training path: it never writes a model
checkpoint and it never reads calibration or test outcomes.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from .build_identity import evaluation_source_sha256
from .diagnose_proposal_checkpoint import _matched
from .proposal_net import (
    QUERY_FAMILIES, ProposalNet, ProposalNetConfig,
    _gate_text_support_probability, proposal_net_loss,
)
from .train_proposal_net_large import (
    PairDataset, _collate, _evaluate, _read_pairs, _split_group,
    TINY_OVERFIT_REQUIRED_FAMILIES, _label_contract_sha256, _stable_bucket,
    _svg_families, _targets,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _owner_count(row: dict) -> int:
    contract = row.get("owner_contract", {})
    owners = contract.get("owner_ids", []) if isinstance(contract, dict) else []
    return len(owners) if isinstance(owners, list) else 0


def _materialized_family_counts(sample: dict) -> Counter[str]:
    result: Counter[str] = Counter()
    for target_index, family_index in enumerate(sample["family"].tolist()):
        result[QUERY_FAMILIES[int(family_index)]] += 1
        if bool(sample["small_shape"][target_index]):
            result["small_shape"] += 1
    return result


def _candidate_priority(row: dict) -> tuple[int, str]:
    source = str(row.get("source", ""))
    priority = {
        "synthetic-open-text": 0,
        "synthetic-structure-v2": 1,
        "synthetic-geometry": 2,
    }.get(source, 3)
    return priority, str(row["id"])


def _select_rows(
    rows: list[dict], accepted: set[str], pair_root: Path,
    config: ProposalNetConfig, *, per_count: int, per_family: int,
) -> tuple[list[dict], dict[str, tuple[str, ...]], Counter[str], dict[int, int]]:
    """Choose a deterministic train-only set that exercises every output head.

    The old probe selected only multi-line text rows, so it could pass while
    layer/relation/stroke/appearance/risk heads were disconnected from their
    labels.  Materializing each candidate here verifies the exact PairDataset
    path used by large training; rows above global top-5 capacity are excluded
    because perfect Recall@5 would be mathematically impossible.
    """
    if int(per_count) < 1 or int(per_family) < 1:
        raise ValueError("tiny-overfit quotas must be positive")
    selected: list[dict] = []
    families: dict[str, tuple[str, ...]] = {}
    coverage: Counter[str] = Counter()
    owner_rows = {2: 0, 3: 0}
    support_size = (128 // 4) * int(config.mask_upsample)
    for row in sorted(rows, key=_candidate_priority):
        row_id = str(row["id"])
        if (
            row_id not in accepted
            or _stable_bucket(_split_group(row)) != "train"
        ):
            continue
        source = str(row.get("source", ""))
        owner_count = _owner_count(row)
        owner_needed = bool(
            source == "synthetic-open-text"
            and owner_count in owner_rows
            and owner_rows[owner_count] < int(per_count)
        )
        family_needed = any(
            coverage[family] < int(per_family)
            for family in TINY_OVERFIT_REQUIRED_FAMILIES
        )
        if not owner_needed and not family_needed:
            break
        needed = {
            family for family in TINY_OVERFIT_REQUIRED_FAMILIES
            if coverage[family] < int(per_family)
        }
        relevant = {
            "synthetic-open-text": {
                "text_line", "glyph_group", "risk_hard_negative",
            },
            "synthetic-structure-v2": {
                "layer_relation", "stroke_network", "appearance_model",
                "symmetry_repeat_group", "risk_hard_negative",
            },
            "synthetic-geometry": {
                "whole_shape", "small_shape", "risk_hard_negative",
            },
        }.get(source, {"whole_shape", "small_shape", "risk_hard_negative"})
        if not owner_needed and not (needed & relevant):
            continue
        # The three explicit factories cover every required slice.  External
        # rows remain a fail-safe only if a declared factory row was filtered.
        if (
            source not in {
                "synthetic-open-text",
                "synthetic-structure-v2",
                "synthetic-geometry",
            }
            and coverage["whole_shape"] >= int(per_family)
        ):
            continue
        row_families = _svg_families(row, pair_root)
        dataset = PairDataset(
            [row], pair_root, {row_id: row_families}, image_size=128,
            parameter_dim=config.parameter_dim,
            support_size=support_size,
        )
        sample = dataset[0]
        # A perfect top-5 diagnostic must be feasible by construction.
        if len(sample["family"]) > 5:
            continue
        sample_counts = _materialized_family_counts(sample)
        contributes = any(
            sample_counts[family] > 0
            and coverage[family] < int(per_family)
            for family in TINY_OVERFIT_REQUIRED_FAMILIES
        )
        if not owner_needed and not contributes:
            continue
        selected.append(row)
        families[row_id] = row_families
        coverage.update(sample_counts)
        if owner_needed:
            owner_rows[owner_count] += 1
    missing = {
        family: {
            "required": int(per_family),
            "actual": int(coverage[family]),
        }
        for family in TINY_OVERFIT_REQUIRED_FAMILIES
        if coverage[family] < int(per_family)
    }
    missing_owners = {
        str(count): {"required": int(per_count), "actual": int(actual)}
        for count, actual in owner_rows.items()
        if actual < int(per_count)
    }
    if missing or missing_owners:
        raise RuntimeError(
            "insufficient train-only all-head supervision: "
            + json.dumps({
                "families": missing, "owner_counts": missing_owners,
            }, sort_keys=True)
        )
    return selected, families, coverage, owner_rows


@torch.no_grad()
def _detailed_text_failures(
    model: ProposalNet, loader: DataLoader, device: torch.device,
    raw_rows: dict[str, dict],
) -> list[dict]:
    """Return exact row/target evidence for every failed TextLine instance."""
    model.eval()
    failures = []
    text_index = QUERY_FAMILIES.index("text_line")
    for batch in loader:
        images = torch.as_tensor(
            np.stack([row["rgba"] for row in batch]), device=device,
        )
        output = model(images)
        probability = output["family_logits"].softmax(-1)
        confidence = torch.sigmoid(output["confidence_logits"])
        predicted = probability[..., :-1].argmax(-1)
        raw_supports = torch.sigmoid(output["support_logits"])
        supports = _gate_text_support_probability(
            raw_supports, output["bbox"], predicted,
            padding=model.config.text_bbox_gate_padding,
            vertical_only=model.config.text_bbox_gate_vertical_only,
        )
        probability_np = probability.cpu().numpy()
        confidence_np = confidence.cpu().numpy()
        supports_np = supports.cpu().numpy()
        raw_supports_np = raw_supports.cpu().numpy()
        boxes_np = output["bbox"].cpu().numpy()
        for offset, sample in enumerate(batch):
            matches = _matched(
                probability_np[offset], confidence_np[offset],
                supports_np[offset], sample, cutoff=5, typed=True,
            )
            combined = (
                np.max(probability_np[offset, :, :-1], axis=-1)
                * confidence_np[offset]
            )
            order = np.argsort(-combined)
            rank_by_query = {
                int(query): rank + 1 for rank, query in enumerate(order)
            }
            raw = raw_rows[str(sample["id"])]
            for target, family in enumerate(sample["family"].tolist()):
                if int(family) != text_index:
                    continue
                iou, query = matches.get(target, (0.0, -1))
                if iou >= 0.50:
                    continue
                target_mask = np.asarray(sample["support"][target], np.float64)
                predicted_mask = (
                    np.asarray(supports_np[offset, query], np.float64)
                    if query >= 0 else np.zeros_like(target_mask)
                )
                raw_predicted_mask = (
                    np.asarray(raw_supports_np[offset, query], np.float64)
                    if query >= 0 else np.zeros_like(target_mask)
                )
                target_bool = target_mask > 0.0
                thresholds = np.linspace(0.05, 0.95, 19)
                threshold_rows = []
                for threshold in thresholds:
                    binary = predicted_mask >= threshold
                    intersection = int(np.sum(binary & target_bool))
                    union = int(np.sum(binary | target_bool))
                    threshold_rows.append((
                        intersection / max(1, union), float(threshold),
                        int(np.sum(binary)),
                    ))
                best_binary_iou, best_threshold, best_pixels = max(
                    threshold_rows
                )
                raw_intersection = float(np.sum(raw_predicted_mask * target_mask))
                raw_union = float(np.sum(
                    raw_predicted_mask + target_mask
                    - raw_predicted_mask * target_mask
                ))
                failures.append({
                    "id": str(sample["id"]),
                    "source_id": str(sample["source_id"]),
                    "font_family": str(raw.get("font_family", "")),
                    "size": int(raw.get("size") or 0),
                    "owner_count": _owner_count(raw),
                    "target_index": int(target),
                    "target_support_pixels": int(np.sum(sample["support"][target])),
                    "target_bbox": [
                        float(value) for value in sample["bbox"][target]
                    ],
                    "support_iou": float(iou),
                    "raw_support_iou": raw_intersection / max(1e-7, raw_union),
                    "predicted_support_mass": float(np.sum(predicted_mask)),
                    "predicted_mass_on_target": float(np.sum(
                        predicted_mask * target_mask
                    )),
                    "predicted_mass_outside_target": float(np.sum(
                        predicted_mask * (1.0 - target_mask)
                    )),
                    "mean_probability_on_target": float(
                        np.mean(predicted_mask[target_bool])
                    ),
                    "mean_probability_outside_target": float(
                        np.mean(predicted_mask[~target_bool])
                    ),
                    "best_binary_iou": float(best_binary_iou),
                    "best_binary_threshold": float(best_threshold),
                    "best_binary_support_pixels": int(best_pixels),
                    "query": int(query),
                    "global_rank": (
                        int(rank_by_query[query]) if query >= 0 else None
                    ),
                    "type_confidence": (
                        float(probability_np[offset, query, text_index]
                              * confidence_np[offset, query])
                        if query >= 0 else 0.0
                    ),
                    "predicted_bbox": (
                        [float(value) for value in boxes_np[offset, query]]
                        if query >= 0 else None
                    ),
                    "augmentation": raw.get("augmentation", {}),
                })
    return failures


def run_probe(
    checkpoint: Path, pair_root: Path, filter_cache: Path, *,
    per_count: int = 16, steps: int = 120, batch_size: int = 8,
    learning_rate: float = 3e-4, workers: int = 2,
    device_name: str = "auto", text_bbox_gate_padding: float | None = None,
    text_bbox_gate_vertical_only: bool | None = None,
    minimum_text_recall: float = 0.99,
    per_family: int = 16, minimum_family_recall: float = 0.95,
) -> dict:
    torch.manual_seed(20260722)
    np.random.seed(20260722)
    accepted = set(json.loads(filter_cache.read_text("utf-8"))["accepted_ids"])
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    config = ProposalNetConfig(**payload["config"])
    if text_bbox_gate_padding is not None:
        config = replace(
            config, text_bbox_gate_padding=float(text_bbox_gate_padding),
        )
    if text_bbox_gate_vertical_only is not None:
        config = replace(
            config,
            text_bbox_gate_vertical_only=bool(text_bbox_gate_vertical_only),
        )
    rows, families, family_instance_counts, owner_count_rows = _select_rows(
        _read_pairs(pair_root, None), accepted, pair_root, config,
        per_count=per_count, per_family=per_family,
    )
    dataset = PairDataset(
        rows, pair_root, families, image_size=128,
        parameter_dim=config.parameter_dim,
        support_size=(128 // 4) * int(config.mask_upsample),
    )
    loader = DataLoader(
        dataset, batch_size=batch_size, shuffle=False,
        num_workers=workers, persistent_workers=workers > 0,
        prefetch_factor=2 if workers > 0 else None,
        collate_fn=_collate, pin_memory=torch.cuda.is_available(),
    )
    if device_name == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_name)
    model = ProposalNet(config).to(device)
    model.load_state_dict(payload["model"])
    before, _examples = _evaluate(model, loader, device)

    def evaluation_row(step: int, metrics: dict) -> dict:
        recalls = {
            family: float(metrics.get(family, {}).get(
                "neural_only_recall_at_5_iou50", 0.0,
            ))
            for family in TINY_OVERFIT_REQUIRED_FAMILIES
        }
        return {
            "step": int(step),
            "recall_at_5_by_family": recalls,
            "minimum_required_recall_at_5": min(recalls.values()),
            "overall_recall_at_5": float(metrics.get("overall", {}).get(
                "neural_only_recall_at_5_iou50", 0.0,
            )),
            "text_line_mean_iou_at_5": float(
                metrics.get("text_line", {}).get(
                    "mean_best_soft_iou_at_5", 0.0,
                )
            ),
        }

    evaluation_history = [evaluation_row(0, before)]
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=1e-4,
    )
    loss_history = []
    iterator = iter(loader)
    model.train()
    for step in range(steps):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(loader)
            batch = next(iterator)
        images = torch.as_tensor(
            np.stack([row["rgba"] for row in batch]), device=device,
        )
        losses = proposal_net_loss(model(images), _targets(batch, config, device))
        optimizer.zero_grad(set_to_none=True)
        losses["total"].backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        loss_history.append(float(losses["total"].detach().cpu()))
        if (step + 1) % max(1, steps // 8) == 0 or step + 1 == steps:
            measured, _examples = _evaluate(model, loader, device)
            evaluation_history.append(evaluation_row(step + 1, measured))
            model.train()
        if step in {0, steps // 4, steps // 2, (3 * steps) // 4, steps - 1}:
            print(json.dumps({
                "step": step + 1, "steps": steps,
                "loss": loss_history[-1],
            }), flush=True)
    after, _final_examples = _evaluate(model, loader, device)
    final_text_failures = _detailed_text_failures(
        model, loader, device, {str(row["id"]): row for row in rows},
    )
    best_joint = max(
        evaluation_history,
        key=lambda row: (
            row["minimum_required_recall_at_5"],
            row["overall_recall_at_5"],
            -row["step"],
        ),
    )
    best_text_recall = max(
        row["recall_at_5_by_family"]["text_line"]
        for row in evaluation_history
    )
    coverage_passed = all(
        int(family_instance_counts[family]) >= int(per_family)
        for family in TINY_OVERFIT_REQUIRED_FAMILIES
    )
    passed = bool(
        coverage_passed
        and float(best_joint["minimum_required_recall_at_5"])
        >= float(minimum_family_recall)
        and float(best_joint["recall_at_5_by_family"]["text_line"])
        >= float(minimum_text_recall)
    )
    return {
        "schema": "pcdc-proposal-tiny-overfit-preflight/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_source_sha256": evaluation_source_sha256(__file__),
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": _sha256(checkpoint),
        "label_contract_sha256": _label_contract_sha256(),
        "pair_root": str(pair_root.resolve()),
        "filter_cache_sha256": _sha256(filter_cache),
        "split": "train-only", "checkpoint_written": False,
        "row_count": len(rows), "owner_count_rows": {
            str(count): int(owner_count_rows[count]) for count in (2, 3)
        },
        "required_overfit_families": list(TINY_OVERFIT_REQUIRED_FAMILIES),
        "minimum_family_instances": int(per_family),
        "family_instance_counts": {
            family: int(family_instance_counts[family])
            for family in TINY_OVERFIT_REQUIRED_FAMILIES
        },
        "steps": steps, "batch_size": batch_size,
        "learning_rate": learning_rate, "device": str(device),
        "text_bbox_gate_padding": config.text_bbox_gate_padding,
        "text_bbox_gate_vertical_only": config.text_bbox_gate_vertical_only,
        "probe_model_config": asdict(config),
        "initial_loss": loss_history[0], "final_loss": loss_history[-1],
        "evaluation_history": evaluation_history,
        "best_joint_step": int(best_joint["step"]),
        "best_recall_at_5_by_family": dict(
            best_joint["recall_at_5_by_family"]
        ),
        "best_minimum_required_recall_at_5": float(
            best_joint["minimum_required_recall_at_5"]
        ),
        "best_overall_recall_at_5": float(best_joint["overall_recall_at_5"]),
        "minimum_family_recall_at_5": float(minimum_family_recall),
        "best_text_line_recall_at_5": best_text_recall,
        "minimum_text_line_recall_at_5": minimum_text_recall,
        "passed": passed,
        "before": before, "after": after,
        "final_text_failures": final_text_failures,
        "interpretation": (
            "If every production query family cannot jointly approach perfect "
            "train-only Recall@5, do not start a large run; repair the label, "
            "matching, ranking, support, relation or architecture path first."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--filter-cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-count", type=int, default=16)
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--text-bbox-gate-padding", type=float)
    parser.add_argument(
        "--text-bbox-gate-vertical-only", action="store_true", default=None,
    )
    parser.add_argument("--minimum-text-recall", type=float, default=0.99)
    parser.add_argument("--per-family", type=int, default=16)
    parser.add_argument("--minimum-family-recall", type=float, default=0.95)
    args = parser.parse_args()
    report = run_probe(
        args.checkpoint, args.pair_root, args.filter_cache,
        per_count=args.per_count, steps=args.steps,
        batch_size=args.batch_size, learning_rate=args.lr,
        workers=args.workers, device_name=args.device,
        text_bbox_gate_padding=args.text_bbox_gate_padding,
        text_bbox_gate_vertical_only=args.text_bbox_gate_vertical_only,
        minimum_text_recall=args.minimum_text_recall,
        per_family=args.per_family,
        minimum_family_recall=args.minimum_family_recall,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    print(json.dumps({
        "out": str(args.out), "checkpoint_written": False,
        "before_text": report["before"]["text_line"]["neural_only_recall_at_5_iou50"],
        "after_text": report["after"]["text_line"]["neural_only_recall_at_5_iou50"],
        "best_text": report["best_text_line_recall_at_5"],
        "best_minimum_family_recall": (
            report["best_minimum_required_recall_at_5"]
        ),
        "passed": report["passed"],
    }, indent=2))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

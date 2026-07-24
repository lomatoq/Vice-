"""Pre-training anti-forgetting and same-seed CUDA reproducibility proofs.

The pilot is train-split only and never writes a checkpoint.  Two independent
replicas start from the exact v13 initialization, consume the same bounded
all-head v14 adaptation set, and are evaluated on a disjoint legacy anchor set.
This catches catastrophic forgetting and nondeterministic training conclusions
before the expensive full v14 run is authorized.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader

from .build_identity import compiler_source_sha256, evaluation_source_sha256
from .preflight_proposal_overfit import (
    _materialized_family_counts, _select_rows,
)
from .proposal_filter_cache import (
    corpus_data_contract_sha256, validate_filter_cache,
)
from .proposal_net import ProposalNet, ProposalNetConfig, proposal_net_loss
from .train_proposal_net_large import (
    PairDataset, TINY_OVERFIT_REQUIRED_FAMILIES, _collate, _evaluate,
    _label_contract_sha256, _read_pairs, _split_group, _stable_bucket,
    _svg_families, _targets,
)


ANTI_SCHEMA = "pcdc-anti-forgetting-pilot/v1"
CUDA_SCHEMA = "pcdc-cuda-reproducibility/v1"
LEGACY_ANCHOR_FAMILIES = (
    "text_line", "glyph_group", "whole_shape", "small_shape",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_sha256(model: ProposalNet) -> str:
    digest = hashlib.sha256(b"pcdc-proposal-state/v1\0")
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(
            tensor.detach().cpu().contiguous().numpy().tobytes(),
        )
    return digest.hexdigest()


def _metric_value(metrics: dict, family: str, name: str) -> float:
    return float(metrics.get(family, {}).get(name, 0.0))


def _metric_snapshot(metrics: dict) -> dict[str, dict[str, float | int]]:
    families = (*LEGACY_ANCHOR_FAMILIES, "overall")
    return {
        family: {
            "instances": int(metrics.get(family, {}).get("instances", 0)),
            "recall_at_5": _metric_value(
                metrics, family, "neural_only_recall_at_5_iou50",
            ),
            "mean_iou_at_5": _metric_value(
                metrics, family, "mean_best_soft_iou_at_5",
            ),
        }
        for family in families
    }


def _select_anchor_rows(
    rows: list[dict], accepted_ids: set[str], pair_root: Path,
    config: ProposalNetConfig, excluded_groups: set[str], *,
    per_family: int,
) -> tuple[list[dict], dict[str, tuple[str, ...]], Counter[str]]:
    selected: list[dict] = []
    families: dict[str, tuple[str, ...]] = {}
    coverage: Counter[str] = Counter()
    support_size = (128 // 4) * int(config.mask_upsample)
    priority = {"synthetic-open-text": 0, "synthetic-geometry": 1}
    candidates = sorted(
        rows,
        key=lambda row: (
            priority.get(str(row.get("source", "")), 2),
            str(row["id"]),
        ),
    )
    for row in candidates:
        row_id = str(row["id"])
        group = _split_group(row)
        if (
            row_id not in accepted_ids
            or group in excluded_groups
            or _stable_bucket(group) != "train"
            or str(row.get("source", "")) not in priority
        ):
            continue
        needed = {
            family for family in LEGACY_ANCHOR_FAMILIES
            if coverage[family] < int(per_family)
        }
        if not needed:
            break
        source = str(row.get("source", ""))
        relevant = (
            {"text_line", "glyph_group"}
            if source == "synthetic-open-text"
            else {"whole_shape", "small_shape"}
        )
        if not (needed & relevant):
            continue
        row_families = _svg_families(row, pair_root)
        dataset = PairDataset(
            [row], pair_root, {row_id: row_families}, image_size=128,
            parameter_dim=config.parameter_dim,
            support_size=support_size,
        )
        sample = dataset[0]
        if len(sample["family"]) > 5:
            continue
        sample_counts = _materialized_family_counts(sample)
        if not any(sample_counts[family] and family in needed for family in needed):
            continue
        selected.append(row)
        families[row_id] = row_families
        coverage.update(sample_counts)
    missing = {
        family: int(coverage[family])
        for family in LEGACY_ANCHOR_FAMILIES
        if coverage[family] < int(per_family)
    }
    if missing:
        raise RuntimeError(
            "insufficient disjoint legacy anchor supervision: "
            + json.dumps(missing, sort_keys=True)
        )
    return selected, families, coverage


@torch.no_grad()
def _mean_loss(
    model: ProposalNet, loader: DataLoader, config: ProposalNetConfig,
    device: torch.device,
) -> float:
    model.eval()
    values = []
    for batch in loader:
        images = torch.as_tensor(
            np.stack([row["rgba"] for row in batch]), device=device,
        )
        values.append(float(proposal_net_loss(
            model(images), _targets(batch, config, device),
        )["total"].detach().cpu()))
    return float(np.mean(values))


def _anti_forgetting(
    before: dict, after: dict, before_loss: float, after_loss: float,
) -> tuple[bool, dict]:
    rows = {}
    for family in LEGACY_ANCHOR_FAMILIES:
        before_recall = _metric_value(
            before, family, "neural_only_recall_at_5_iou50",
        )
        after_recall = _metric_value(
            after, family, "neural_only_recall_at_5_iou50",
        )
        before_iou = _metric_value(before, family, "mean_best_soft_iou_at_5")
        after_iou = _metric_value(after, family, "mean_best_soft_iou_at_5")
        rows[family] = {
            "instances": int(before.get(family, {}).get("instances", 0)),
            "recall_drop": before_recall - after_recall,
            "mean_iou_drop": before_iou - after_iou,
            "passed": bool(
                int(before.get(family, {}).get("instances", 0)) >= 16
                and before_recall - after_recall <= 0.05 + 1e-9
                and before_iou - after_iou <= 0.05 + 1e-9
            ),
        }
    overall_drop = (
        _metric_value(before, "overall", "neural_only_recall_at_5_iou50")
        - _metric_value(after, "overall", "neural_only_recall_at_5_iou50")
    )
    loss_ratio = after_loss / max(1e-9, before_loss)
    passed = bool(
        all(row["passed"] for row in rows.values())
        and overall_drop <= 0.03 + 1e-9
        and loss_ratio <= 1.10 + 1e-9
    )
    return passed, {
        "family_retention": rows,
        "overall_recall_drop": overall_drop,
        "anchor_loss_before": before_loss,
        "anchor_loss_after": after_loss,
        "anchor_loss_ratio": loss_ratio,
        "maximum_family_recall_drop": 0.05,
        "maximum_family_mean_iou_drop": 0.05,
        "maximum_overall_recall_drop": 0.03,
        "maximum_anchor_loss_ratio": 1.10,
    }


def _replica(
    checkpoint_payload: dict, config: ProposalNetConfig,
    adaptation_loader: DataLoader, anchor_loader: DataLoader,
    device: torch.device, *, steps: int, learning_rate: float, seed: int,
) -> dict[str, Any]:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    model = ProposalNet(config).to(device)
    model.load_state_dict(checkpoint_payload["model"], strict=True)
    before_metrics, _ = _evaluate(
        model, anchor_loader, device, k=config.query_count,
    )
    before_loss = _mean_loss(
        model, anchor_loader, config, device,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=1e-4,
    )
    scaler = torch.amp.GradScaler(
        "cuda", enabled=device.type == "cuda",
    )
    iterator = iter(adaptation_loader)
    loss_trace = []
    model.train()
    for _step in range(int(steps)):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(adaptation_loader)
            batch = next(iterator)
        images = torch.as_tensor(
            np.stack([row["rgba"] for row in batch]), device=device,
        )
        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast(
            "cuda", enabled=device.type == "cuda",
        ):
            loss = proposal_net_loss(
                model(images), _targets(batch, config, device),
            )["total"]
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
        scaler.step(optimizer)
        scaler.update()
        loss_trace.append(float(loss.detach().cpu()))
    after_metrics, _ = _evaluate(
        model, anchor_loader, device, k=config.query_count,
    )
    after_loss = _mean_loss(model, anchor_loader, config, device)
    adaptation_metrics, _ = _evaluate(
        model, adaptation_loader, device, k=config.query_count,
    )
    anti_passed, anti = _anti_forgetting(
        before_metrics, after_metrics, before_loss, after_loss,
    )
    trace_bytes = np.asarray(loss_trace, np.float64).tobytes()
    window = max(1, min(8, len(loss_trace) // 4))
    initial_training_loss = float(np.mean(loss_trace[:window]))
    final_training_loss = float(np.mean(loss_trace[-window:]))
    result = {
        "seed": int(seed),
        "steps": int(steps),
        "loss_trace": loss_trace,
        "loss_trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
        "loss_summary_window": window,
        "initial_training_loss": initial_training_loss,
        "final_training_loss": final_training_loss,
        "training_loss_ratio": (
            final_training_loss / max(1e-9, initial_training_loss)
        ),
        "state_sha256": _state_sha256(model),
        "anchor_before": _metric_snapshot(before_metrics),
        "anchor_after": _metric_snapshot(after_metrics),
        "adaptation_after": {
            family: {
                "instances": int(
                    adaptation_metrics.get(family, {}).get("instances", 0)
                ),
                "recall_at_5": _metric_value(
                    adaptation_metrics, family,
                    "neural_only_recall_at_5_iou50",
                ),
            }
            for family in TINY_OVERFIT_REQUIRED_FAMILIES
        },
        "anti_forgetting_passed": anti_passed,
        "anti_forgetting": anti,
    }
    del model, optimizer, scaler
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return result


def _maximum_metric_delta(first: dict, second: dict) -> float:
    values = []
    for stage in ("anchor_before", "anchor_after", "adaptation_after"):
        for family in set(first[stage]) | set(second[stage]):
            for name in set(first[stage].get(family, {})) | set(
                second[stage].get(family, {})
            ):
                a = first[stage].get(family, {}).get(name)
                b = second[stage].get(family, {}).get(name)
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    values.append(abs(float(a) - float(b)))
    return max(values, default=0.0)


def audit(
    *, checkpoint: Path, proposal_config: Path, pair_root: Path,
    filter_cache: Path, anti_out: Path, cuda_out: Path,
    steps: int = 64, batch_size: int = 8, learning_rate: float = 3e-4,
    per_family: int = 16, seed: int = 20260723,
) -> tuple[dict, dict]:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA reproducibility proof requires CUDA")
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    device = torch.device("cuda")
    config_payload = json.loads(proposal_config.read_text("utf-8"))
    if config_payload.get("schema") != "pcdc-proposal-config/v1":
        raise ValueError("unsupported ProposalNet config artifact")
    config = ProposalNetConfig(**config_payload["config"])
    checkpoint_payload = torch.load(
        checkpoint, map_location="cpu", weights_only=False,
    )
    if checkpoint_payload.get("schema") != "pcdc-proposal-net-checkpoint/v2-large":
        raise ValueError("unsupported initialization checkpoint")
    raw_rows = _read_pairs(pair_root, None)
    corpus_contract = corpus_data_contract_sha256(pair_root)
    accepted_rows, rejected_rows = validate_filter_cache(
        filter_cache, raw_rows,
        training_data_contract_sha256=corpus_contract,
    )
    accepted_ids = {str(row["id"]) for row in accepted_rows}
    adaptation_rows, adaptation_families, adaptation_counts, _owners = (
        _select_rows(
            raw_rows, accepted_ids, pair_root, config,
            per_count=per_family, per_family=per_family,
        )
    )
    excluded_groups = {_split_group(row) for row in adaptation_rows}
    anchor_rows, anchor_families, anchor_counts = _select_anchor_rows(
        raw_rows, accepted_ids, pair_root, config, excluded_groups,
        per_family=per_family,
    )
    support_size = (128 // 4) * int(config.mask_upsample)
    adaptation_loader = DataLoader(
        PairDataset(
            adaptation_rows, pair_root, adaptation_families, image_size=128,
            parameter_dim=config.parameter_dim, support_size=support_size,
        ),
        batch_size=batch_size, shuffle=False, num_workers=0,
        collate_fn=_collate,
    )
    anchor_loader = DataLoader(
        PairDataset(
            anchor_rows, pair_root, anchor_families, image_size=128,
            parameter_dim=config.parameter_dim, support_size=support_size,
        ),
        batch_size=batch_size, shuffle=False, num_workers=0,
        collate_fn=_collate,
    )
    first = _replica(
        checkpoint_payload, config, adaptation_loader, anchor_loader,
        device, steps=steps, learning_rate=learning_rate, seed=seed,
    )
    second = _replica(
        checkpoint_payload, config, adaptation_loader, anchor_loader,
        device, steps=steps, learning_rate=learning_rate, seed=seed,
    )
    common = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compiler_source_sha256": compiler_source_sha256(),
        "evaluation_source_sha256": evaluation_source_sha256(__file__),
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": _sha256(checkpoint),
        "proposal_config": asdict(config),
        "proposal_config_sha256": _sha256(proposal_config),
        "pair_root": str(pair_root.resolve()),
        "corpus_data_contract_sha256": corpus_contract,
        "filter_cache": str(filter_cache.resolve()),
        "filter_cache_sha256": _sha256(filter_cache),
        "label_contract_sha256": _label_contract_sha256(),
        "accepted_pair_count": len(accepted_rows),
        "rejected_pair_count": len(rejected_rows),
        "adaptation_row_count": len(adaptation_rows),
        "adaptation_family_counts": {
            family: int(adaptation_counts[family])
            for family in TINY_OVERFIT_REQUIRED_FAMILIES
        },
        "anchor_row_count": len(anchor_rows),
        "anchor_family_counts": {
            family: int(anchor_counts[family])
            for family in LEGACY_ANCHOR_FAMILIES
        },
        "adaptation_anchor_group_disjoint": not bool(
            excluded_groups
            & {_split_group(row) for row in anchor_rows}
        ),
        "checkpoint_written": False,
        "device": str(device),
        "steps": int(steps),
        "batch_size": int(batch_size),
        "learning_rate": float(learning_rate),
    }
    anti_passed = bool(
        common["adaptation_anchor_group_disjoint"]
        and first["anti_forgetting_passed"]
        and first["training_loss_ratio"] <= 0.95
    )
    anti_report = {
        "schema": ANTI_SCHEMA,
        **common,
        "passed": anti_passed,
        "training_loss_reduction_required": 0.05,
        "replica": first,
    }
    loss_delta = float(np.max(np.abs(
        np.asarray(first["loss_trace"], np.float64)
        - np.asarray(second["loss_trace"], np.float64)
    )))
    metric_delta = _maximum_metric_delta(first, second)
    conclusion_stable = bool(
        first["anti_forgetting_passed"]
        == second["anti_forgetting_passed"]
    )
    cuda_passed = bool(
        conclusion_stable
        and first["state_sha256"] == second["state_sha256"]
        and first["loss_trace_sha256"] == second["loss_trace_sha256"]
        and loss_delta <= 1e-7
        and metric_delta <= 1e-7
    )
    cuda_report = {
        "schema": CUDA_SCHEMA,
        **common,
        "passed": cuda_passed,
        "same_seed_conclusion_stable": conclusion_stable,
        "state_sha256_equal": (
            first["state_sha256"] == second["state_sha256"]
        ),
        "loss_trace_sha256_equal": (
            first["loss_trace_sha256"] == second["loss_trace_sha256"]
        ),
        "maximum_loss_delta": loss_delta,
        "maximum_metric_delta": metric_delta,
        "maximum_allowed_delta": 1e-7,
        "replicas": [first, second],
    }
    anti_out.parent.mkdir(parents=True, exist_ok=True)
    cuda_out.parent.mkdir(parents=True, exist_ok=True)
    anti_out.write_text(
        json.dumps(anti_report, indent=2, sort_keys=True), "utf-8",
    )
    cuda_out.write_text(
        json.dumps(cuda_report, indent=2, sort_keys=True), "utf-8",
    )
    return anti_report, cuda_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--proposal-config", type=Path, required=True)
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--filter-cache", type=Path, required=True)
    parser.add_argument("--anti-out", type=Path, required=True)
    parser.add_argument("--cuda-out", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=64)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--per-family", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260723)
    args = parser.parse_args()
    anti, cuda = audit(
        checkpoint=args.checkpoint,
        proposal_config=args.proposal_config,
        pair_root=args.pair_root, filter_cache=args.filter_cache,
        anti_out=args.anti_out, cuda_out=args.cuda_out,
        steps=args.steps, batch_size=args.batch_size,
        learning_rate=args.lr, per_family=args.per_family,
        seed=args.seed,
    )
    print(json.dumps({
        "anti_forgetting_passed": anti["passed"],
        "cuda_reproducibility_passed": cuda["passed"],
        "anti_out": str(args.anti_out.resolve()),
        "cuda_out": str(args.cuda_out.resolve()),
    }, indent=2, sort_keys=True))
    if not anti["passed"] or not cuda["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

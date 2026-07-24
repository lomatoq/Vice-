"""Phase-9 real-locus ProposalNet training and hybrid conformal calibration."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import time

import cv2
import numpy as np
from PIL import Image
import torch

from .build_identity import bind_report
from .experiment_inputs import real_locus_input_identity
from .conformal import (
    CalibrationExample, audit_conformal_coverage, calibrate_conformal_sets,
    runtime_conformal_query_set,
)
from .evidence_ir import EvidenceCache
from .experiment1_evidence_coverage import _support_recall_at_k
from .hard_negative_factory import (
    CandidateRanker, applicable_hard_negative_types,
    counterfactual_feature_pairs, pairwise_ranking_loss,
)
from .proposal_net import (
    HARD_NEGATIVE_TYPES, QUERY_FAMILIES, ProposalNet, ProposalNetConfig,
    proposal_net_loss, reir_queries,
)
from .proposal_data_contract import RELATION_CONTRACT_SCHEMA, RELATION_TYPES
from .proposal_real_labels import (
    FAMILY_TO_EVALUATION_CLASS, reviewed_proposal_family,
)
from .runtime_service import QUALITY_BUDGETS


PROJECT = Path(__file__).resolve().parents[1]
CORPUS = PROJECT / "datasets" / "pcdc_real_loci_v1"
DEFAULT_OUT = PROJECT / "benchmarks" / "pcdc_experiment9" / "report.json"
DEFAULT_CHECKPOINT = PROJECT / "models" / "proposal_net_real_candidate_v9.pt"
DEFAULT_INITIALIZATION = PROJECT / "models" / "proposal_net_large_candidate_v9.pt"
SUPPORTED_PRETRAIN_LABEL_CONTRACTS = frozenset({
    "pcdc-source-disjoint-svg-owner-labels/v1",
    "pcdc-explicit-owner-typed-mixed-replay-labels/v2",
    "pcdc-explicit-owner-counterfactual-mixed-replay-labels/v3",
    "pcdc-explicit-owner-counterfactual-mixed-replay-labels/v4",
})
_ACCEPTED_REVIEW_STATUS = frozenset({
    "ground_truth_derived", "evidence_reviewed", "complete",
})
_REAL_CONFORMAL_FAMILIES = (
    "text_line", "glyph_group", "whole_shape", "layer_relation",
    "stroke_network", "appearance_model", "symmetry_repeat_group",
    "risk_hard_negative",
)
_REAL_TEST_MINIMUM = {
    "text_line": 20, "glyph_group": 20, "whole_shape": 20,
    "layer_relation": 20, "stroke_network": 20,
    "appearance_model": 20, "symmetry_repeat_group": 20,
    "risk_hard_negative": 20,
}


def _typed_reviewed_loci(
    loci: list[dict], reviews: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """Expand explicit query instances; never infer them from sampling buckets.

    One real locus is an image/ROI, not necessarily one ProposalNet target.  A
    logo can contain a text line, a compound one-symbol mark, a repeat group and
    an appearance field at the same time.  ``proposal_instances`` preserves
    those independent supports while keeping every instance from one source in
    the same leakage-safe split.  Legacy one-mask reviews remain valid.
    """

    typed = []
    excluded = []
    for locus in loci:
        review = reviews.get(locus["id"], {})
        if review.get("status") not in _ACCEPTED_REVIEW_STATUS:
            excluded.append({"id": locus["id"], "reason": "unreviewed"})
            continue

        raw_instances = review.get("proposal_instances")
        if raw_instances is None:
            instances: list[tuple[str | None, dict]] = [(None, review)]
        elif not isinstance(raw_instances, list) or not raw_instances:
            excluded.append({
                "id": locus["id"], "reason": "empty-or-invalid-proposal-instances",
            })
            continue
        else:
            instances = []
            used_ids: set[str] = set()
            for index, raw_instance in enumerate(raw_instances):
                if not isinstance(raw_instance, dict):
                    excluded.append({
                        "id": f"{locus['id']}::proposal:{index:03d}",
                        "reason": "invalid-proposal-instance",
                    })
                    continue
                instance_id = str(
                    raw_instance.get("id", f"{index:03d}")
                ).strip()
                if not instance_id or instance_id in used_ids:
                    excluded.append({
                        "id": f"{locus['id']}::proposal:{index:03d}",
                        "reason": "missing-or-duplicate-proposal-instance-id",
                    })
                    continue
                used_ids.add(instance_id)
                merged = {
                    key: value for key, value in review.items()
                    if key != "proposal_instances"
                }
                merged.update(raw_instance)
                if merged.get("status") not in _ACCEPTED_REVIEW_STATUS:
                    excluded.append({
                        "id": f"{locus['id']}::proposal:{instance_id}",
                        "reason": "unreviewed-proposal-instance",
                    })
                    continue
                instances.append((instance_id, merged))

        for instance_id, instance in instances:
            family = reviewed_proposal_family(instance)
            row_id = (
                locus["id"] if instance_id is None
                else f"{locus['id']}::proposal:{instance_id}"
            )
            if family is None:
                excluded.append({
                    "id": row_id,
                    "reason": "missing-explicit-proposal-family",
                    "sampling_bucket": locus.get("semantic_class"),
                })
                continue
            if not _valid_review_geometry(instance):
                excluded.append({
                    "id": row_id,
                    "reason": "invalid-proposal-instance-geometry",
                })
                continue
            row = dict(locus)
            row["id"] = row_id
            row["source_locus_id"] = locus["id"]
            row["corpus_semantic_class"] = locus.get("semantic_class")
            row["semantic_class"] = FAMILY_TO_EVALUATION_CLASS[family]
            row["proposal_family"] = family
            row["_proposal_review"] = instance
            typed.append(row)
    return typed, excluded


def _valid_review_geometry(review: dict) -> bool:
    support_size = review.get("support_size")
    support_rle = review.get("support_rle")
    roi = review.get("roi_xyxy")
    if (
        not isinstance(support_size, list)
        or len(support_size) != 2
        or any(not isinstance(value, int) or value <= 0 for value in support_size)
        or not isinstance(support_rle, list)
        or not isinstance(roi, list)
        or len(roi) != 4
    ):
        return False
    try:
        components = int(review["components"])
        holes = int(review["holes"])
        x1, y1, x2, y2 = (float(value) for value in roi)
    except (KeyError, TypeError, ValueError):
        return False
    if components < 1 or holes < 0 or not (x1 < x2 and y1 < y2):
        return False
    area = int(support_size[0]) * int(support_size[1])
    for run in support_rle:
        if (
            not isinstance(run, list)
            or len(run) != 2
            or not all(isinstance(value, int) for value in run)
            or run[0] < 0
            or run[1] <= 0
            or run[0] + run[1] > area
        ):
            return False
    return bool(support_rle)


def _review_relation_targets(
    review: dict, family: str,
) -> tuple[np.ndarray, np.ndarray]:
    relations = np.zeros(len(RELATION_TYPES), np.float32)
    relation_mask = np.zeros(len(RELATION_TYPES), np.float32)
    contract = review.get("relation_contract")
    if contract is None:
        text_membership = str(
            review.get("text_line_membership", "")
        ).lower()
        if text_membership in {"yes", "no"}:
            index = RELATION_TYPES.index("text_membership")
            relation_mask[index] = 1.0
            relations[index] = float(text_membership == "yes")
        return relations, relation_mask
    if (
        not isinstance(contract, dict)
        or contract.get("schema") != RELATION_CONTRACT_SCHEMA
        or contract.get("family") != family
    ):
        raise ValueError("real proposal instance has an invalid relation contract")
    positive = contract.get("positive")
    observable = contract.get("observable")
    if not isinstance(positive, list) or not isinstance(observable, list):
        raise ValueError("real relation tokens must be explicit lists")
    positive_tokens = tuple(str(value) for value in positive)
    observable_tokens = tuple(str(value) for value in observable)
    if (
        len(positive_tokens) != len(set(positive_tokens))
        or len(observable_tokens) != len(set(observable_tokens))
        or not set(positive_tokens).issubset(observable_tokens)
        or not set(observable_tokens).issubset(RELATION_TYPES)
    ):
        raise ValueError("real relation contract is malformed")
    for token in observable_tokens:
        relation_mask[RELATION_TYPES.index(token)] = 1.0
    for token in positive_tokens:
        relations[RELATION_TYPES.index(token)] = 1.0
    return relations, relation_mask


def _real_corpus_capacity(splits: dict[str, list[dict]]) -> dict:
    """Prove sample capacity before spending time on real fine-tuning."""

    counts = {}
    for split_name, rows in splits.items():
        family_counts = Counter(str(row["proposal_family"]) for row in rows)
        family_counts["glyph_group"] += family_counts["text_line"]
        counts[split_name] = dict(family_counts)
    calibration = counts.get("calibration", {})
    test = counts.get("test", {})
    calibration_gates = {
        family: {
            "instances": int(calibration.get(family, 0)),
            "minimum_instances": 100,
            "passed": int(calibration.get(family, 0)) >= 100,
        }
        for family in _REAL_CONFORMAL_FAMILIES
    }
    test_gates = {
        family: {
            "instances": int(test.get(family, 0)),
            "minimum_instances": minimum,
            "passed": int(test.get(family, 0)) >= minimum,
        }
        for family, minimum in _REAL_TEST_MINIMUM.items()
    }
    overall_test = len(splits.get("test", ()))
    test_gates["overall"] = {
        "instances": overall_test, "minimum_instances": 100,
        "passed": overall_test >= 100,
    }
    passed = all(
        row["passed"]
        for row in (*calibration_gates.values(), *test_gates.values())
    )
    return {
        "passed": passed, "split_family_counts": counts,
        "calibration_gates": calibration_gates, "test_gates": test_gates,
    }


def _decode_rle(runs, width: int, height: int) -> np.ndarray:
    flat = np.zeros(width * height, bool)
    for start, length in runs:
        flat[int(start):int(start) + int(length)] = True
    return flat.reshape((height, width))


def _split_rows(loci: list[dict]) -> dict[str, list[dict]]:
    """Group-disjoint deterministic split, stratified by primary class."""
    splits = {"train": [], "calibration": [], "test": []}
    by_source: dict[str, list[dict]] = {}
    for locus in loci:
        source_group = str(
            locus["source"].get("source_asset") or locus["source"]["path"]
        )
        by_source.setdefault(source_group, []).append(locus)
    by_class: dict[str, list[tuple[str, list[dict]]]] = {}
    for source_group, rows in by_source.items():
        counts = {}
        for row in rows:
            semantic_class = str(row["semantic_class"])
            counts[semantic_class] = counts.get(semantic_class, 0) + 1
        primary_class = min(counts, key=lambda key: (-counts[key], key))
        by_class.setdefault(primary_class, []).append((source_group, rows))
    for semantic_class, groups in by_class.items():
        groups.sort(key=lambda item: hashlib.sha256(
            (item[0] + "\0" + semantic_class).encode("utf-8")
        ).hexdigest())
        total = sum(len(rows) for _group, rows in groups)
        consumed = 0
        for _source_group, rows in groups:
            midpoint = (consumed + 0.5 * len(rows)) / max(1, total)
            split = (
                "train" if midpoint < 0.70
                else "calibration" if midpoint < 0.85 else "test"
            )
            splits[split].extend(rows)
            consumed += len(rows)
    return splits


def _prepare(
    locus: dict, review: dict, size: int = 128,
    support_size: int | None = None,
) -> dict:
    image = Image.open(locus["source"]["path"]).convert("RGBA")
    source_rgba = np.asarray(image, np.float32) / 255.0
    # Match WarmProposalWorker exactly: the model sees straight RGBA resized
    # with INTER_AREA, never a PIL-only calibration preprocessing path.
    rgba = cv2.resize(
        source_rgba, (size, size), interpolation=cv2.INTER_AREA,
    ).astype(np.float32)
    width, height = (int(value) for value in review["support_size"])
    support = _decode_rle(review["support_rle"], width, height)
    lattice_size = int(support_size if support_size is not None else size // 4)
    support_lattice = (
        cv2.resize(
            support.astype(np.float32), (lattice_size, lattice_size),
            interpolation=cv2.INTER_AREA,
        ) > 0.0
    ).astype(np.float32)
    if np.any(support) and not np.any(support_lattice):
        raise RuntimeError("real-locus support vanished on ProposalNet lattice")
    x1, y1, x2, y2 = (float(value) for value in review["roi_xyxy"])
    family = reviewed_proposal_family(review)
    if family is None:
        raise ValueError(
            f"{locus['id']}: explicit proposal_family is required; "
            "semantic_class is only a corpus sampling bucket"
        )
    evaluation_class = FAMILY_TO_EVALUATION_CLASS[family]
    relations, relation_mask = _review_relation_targets(review, family)
    return {
        "id": locus["id"], "semantic_class": evaluation_class,
        "corpus_semantic_class": locus.get(
            "corpus_semantic_class", locus.get("semantic_class"),
        ),
        "family": family, "path": locus["source"]["path"],
        "source_group": str(locus["source"].get("source_asset") or locus["source"]["category"]),
        "rgba": np.transpose(rgba, (2, 0, 1)),
        "support": support_lattice, "support_full": support,
        "bbox": np.asarray((x1 / width, y1 / height, x2 / width, y2 / height), np.float32),
        "components": min(8, int(review["components"])),
        "holes": min(5, int(review["holes"])),
        "relations": relations,
        "relation_mask": relation_mask,
    }


def _target(sample: dict, config: ProposalNetConfig, device: torch.device) -> dict:
    families = [sample["family"]]
    # A reviewed text-line support supervises both query contracts.  The old
    # real-locus fine-tune updated text_line only and could silently forget the
    # glyph_group head that has an independent 99% production gate.
    if sample["family"] == "text_line":
        families.append("glyph_group")
    count = len(families)
    return {
        "family": torch.tensor(
            [QUERY_FAMILIES.index(family) for family in families],
            device=device,
        ),
        "bbox": torch.as_tensor(
            np.repeat(sample["bbox"][None], count, axis=0), device=device,
        ),
        "support": torch.as_tensor(
            np.repeat(sample["support"][None], count, axis=0), device=device,
        ),
        "parameters": torch.zeros(count, config.parameter_dim, device=device),
        "parameter_mask": torch.zeros(count, config.parameter_dim, device=device),
        "topology": torch.tensor(
            [[sample["components"], sample["holes"]]] * count,
            device=device,
        ),
        "relations": torch.as_tensor(
            np.repeat(sample["relations"][None], count, axis=0), device=device,
        ),
        "relation_mask": torch.as_tensor(
            np.repeat(sample["relation_mask"][None], count, axis=0),
            device=device,
        ),
    }


def _soft_iou(first: np.ndarray, second: np.ndarray) -> float:
    intersection = float(np.sum(first * second))
    union = float(np.sum(first + second - first * second))
    return intersection / max(1e-6, union)


def _counterfactual_rows(
    samples: list[dict], *, maximum_per_class: int,
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...], dict[str, int]]:
    """Build balanced, source-split program counterfactual feature pairs."""
    buckets: dict[str, list[tuple[tuple[float, ...], tuple[float, ...]]]] = {
        name: [] for name in HARD_NEGATIVE_TYPES
    }
    for sample in sorted(samples, key=lambda row: str(row["id"])):
        pairs = counterfactual_feature_pairs(
            sample["support_full"],
            allowed_types=applicable_hard_negative_types((sample["family"],)),
        )
        for name in HARD_NEGATIVE_TYPES:
            positive, negative, applicable = pairs[name]
            if applicable and len(buckets[name]) < maximum_per_class:
                buckets[name].append((positive, negative))
    positives = []
    negatives = []
    labels = []
    for name in HARD_NEGATIVE_TYPES:
        for positive, negative in buckets[name]:
            positives.append(positive)
            negatives.append(negative)
            labels.append(name)
    if not positives:
        return (
            np.empty((0, 16), np.float32), np.empty((0, 16), np.float32),
            (), {name: 0 for name in HARD_NEGATIVE_TYPES},
        )
    return (
        np.asarray(positives, np.float32), np.asarray(negatives, np.float32),
        tuple(labels), {name: len(buckets[name]) for name in HARD_NEGATIVE_TYPES},
    )


def _neural_entries(
    model: ProposalNet, samples: list[dict], device: torch.device,
) -> dict[str, list[tuple[str, float, float, str, float, str, str]]]:
    result = {}
    model.eval()
    with torch.no_grad():
        for start in range(0, len(samples), 16):
            batch = samples[start:start + 16]
            images = torch.as_tensor(np.stack([row["rgba"] for row in batch]), device=device)
            inferred = model.infer(
                images, confidence_floor=0.05,
                max_queries=min(64, model.config.query_count),
            )
            for offset, sample in enumerate(batch):
                rows = []
                for query in inferred[offset]:
                    support = cv2.resize(
                        query.soft_support,
                        (sample["support"].shape[1], sample["support"].shape[0]),
                        interpolation=cv2.INTER_LINEAR,
                    )
                    rows.append((
                        query.family, query.confidence,
                        _soft_iou(support, sample["support"]), "ProposalNet",
                        query.confidence, query.family, query.id,
                    ))
                result[sample["id"]] = rows
    return result


def _hybrid_entries(
    samples: list[dict],
    neural: dict[str, list[tuple[str, float, float, str, float, str, str]]],
    cache: EvidenceCache,
) -> tuple[
    dict[str, list[tuple[str, float, float, str, float, str, str]]],
    dict[str, float],
]:
    result = {}
    support_recall = {}
    for sample in samples:
        rows = list(neural[sample["id"]])
        reir, _hit = cache.get_or_build(sample["path"])
        support_recall[sample["id"]] = float(
            _support_recall_at_k(reir, sample["support_full"], (32,))[0]["32"]
        )
        for query in reir_queries(reir, max_queries=64):
            if query.family != sample["family"]:
                continue
            support = cv2.resize(
                query.soft_support, (sample["support"].shape[1], sample["support"].shape[0]),
                interpolation=cv2.INTER_LINEAR,
            )
            rows.append((
                sample["family"], query.confidence,
                _soft_iou(support, sample["support"]), "REIR",
                query.confidence, query.family, query.id,
            ))
        result[sample["id"]] = rows
    return result, support_recall


def _best_example(
    sample: dict,
    entries: list[tuple[str, float, float, str, float, str, str]],
    family: str | None = None,
) -> CalibrationExample:
    target_family = family or sample["family"]
    eligible = sorted(
        (row for row in entries if row[5] == target_family),
        key=lambda row: (-row[4], row[6]),
    )
    if not eligible:
        return CalibrationExample(
            target_family, 0.0, 0.0, sample["source_group"],
            admission_rank=1, candidate_count=1,
        )
    for rank, (
        _family, confidence, iou, _source, _score, _predicted, _query_id,
    ) in enumerate(
        eligible, 1,
    ):
        if iou >= 0.50:
            return CalibrationExample(
                target_family, confidence, iou, sample["source_group"],
                admission_rank=rank, candidate_count=len(eligible),
            )
    _family, confidence, iou, _source, _score, _predicted, _query_id = max(
        eligible, key=lambda row: (row[2], row[1]),
    )
    return CalibrationExample(
        target_family, confidence, iou, sample["source_group"],
        admission_rank=len(eligible) + 1, candidate_count=len(eligible),
    )


def _family_recall_at_k(
    samples: list[dict],
    entries: dict[
        str, list[tuple[str, float, float, str, float, str, str]]
    ],
    *, semantic_class: str, family: str, k: int,
) -> float:
    cases = [
        sample for sample in samples
        if sample["semantic_class"] == semantic_class
    ]
    if not cases:
        return 0.0
    hits = []
    for sample in cases:
        ranked = sorted(
            entries[sample["id"]], key=lambda row: (-row[4], row[6]),
        )[:k]
        hits.append(any(
            row[5] == family and row[2] >= 0.50 for row in ranked
        ))
    return float(np.mean(hits))


def _recall_at_k(
    samples: list[dict],
    entries: dict[
        str, list[tuple[str, float, float, str, float, str, str]]
    ],
    k: int,
) -> dict[str, float]:
    rows = {}
    all_hits = []
    for semantic_class in sorted({row["semantic_class"] for row in samples}):
        cases = [row for row in samples if row["semantic_class"] == semantic_class]
        hits = []
        for sample in cases:
            ranked = sorted(
                entries[sample["id"]], key=lambda row: (-row[4], row[6]),
            )[:k]
            hits.append(any(
                row[5] == sample["family"] and row[2] >= 0.50
                for row in ranked
            ))
        all_hits.extend(hits)
        rows[semantic_class] = float(np.mean(hits))
    rows["overall"] = float(np.mean(all_hits)) if all_hits else 0.0
    return rows


def _coverage_by_class(
    samples: list[dict], support_recall: dict[str, float], threshold: float = 0.95,
) -> dict[str, float]:
    result = {}
    for semantic_class in sorted({row["semantic_class"] for row in samples}):
        cases = [row for row in samples if row["semantic_class"] == semantic_class]
        result[semantic_class] = float(np.mean([
            support_recall[row["id"]] for row in cases
        ]))
    return result


def _runtime_mode_conformal_coverage(
    model: ProposalNet, samples: list[dict], device: torch.device,
    calibration, cache: EvidenceCache,
) -> dict:
    """Replay the exact production admission path after every global cap."""

    mode_rows = {
        budget.mode.value: {
            family: {"instances": 0, "hits": 0, "coverage": 0.0}
            for family in _REAL_CONFORMAL_FAMILIES
        }
        for budget in QUALITY_BUDGETS.values()
    }
    model.eval()
    maximum = max(
        budget.proposal_queries for budget in QUALITY_BUDGETS.values()
    )
    with torch.no_grad():
        for sample in samples:
            reir, _hit = cache.get_or_build(sample["path"])
            classical = reir_queries(reir, max_queries=maximum)
            rgba = cv2.resize(
                reir.raster.straight_rgba, (128, 128),
                interpolation=cv2.INTER_AREA,
            ).astype(np.float32)
            tensor = torch.from_numpy(
                np.transpose(rgba, (2, 0, 1))[None]
            ).to(device)
            neural = model.infer(
                tensor, confidence_floor=0.05,
                max_queries=min(maximum, model.config.query_count),
            )[0]
            target_families = [sample["family"]]
            if sample["family"] == "text_line":
                target_families.append("glyph_group")
            for budget in QUALITY_BUDGETS.values():
                query_limit = budget.proposal_queries
                admitted = runtime_conformal_query_set(
                    classical[:query_limit],
                    neural[:min(query_limit, model.config.query_count)],
                    calibration, maximum_queries=query_limit,
                )
                for family in target_families:
                    row = mode_rows[budget.mode.value][family]
                    row["instances"] += 1
                    hit = False
                    for query in admitted:
                        if query.family != family:
                            continue
                        support = cv2.resize(
                            query.soft_support,
                            (
                                sample["support"].shape[1],
                                sample["support"].shape[0],
                            ),
                            interpolation=cv2.INTER_LINEAR,
                        )
                        if _soft_iou(support, sample["support"]) >= 0.50:
                            hit = True
                            break
                    row["hits"] += int(hit)
    for families in mode_rows.values():
        for row in families.values():
            row["coverage"] = (
                row["hits"] / row["instances"] if row["instances"] else 0.0
            )
    passed = all(
        row["instances"] >= _REAL_TEST_MINIMUM[family]
        and row["coverage"] >= 0.99
        for families in mode_rows.values()
        for family, row in families.items()
    )
    return {
        "contract": "exact-production-union+family-prefix+global-cap/v1",
        "quality_modes": mode_rows,
        "all_quality_modes_coverage_ge_99pct": passed,
        "exact_runtime_rule": True,
    }


_REAL_RECALL_GATES = {
    "overall": 0.97,
    "text": 0.99,
    "glyph_group": 0.99,
    "small_shape": 0.98,
    "layer_knockout": 0.95,
    "stroke_diagram": 0.98,
    "gradient": 0.95,
    "codec_detail": 0.95,
}


def _real_calibration_selection_key(
    recall: dict[str, float],
) -> tuple[float, ...]:
    """Lexicographically protect every observed real calibration slice.

    Missing families still fail promotion, but a deliberately incomplete
    diagnostic corpus must not force every epoch's primary selection value to
    the same artificial zero.  Sorting the observed normalized margins makes
    the weakest, then second-weakest, and so on decisive before aggregate
    tie-breakers.
    """

    normalized = sorted(
        float(recall.get(name, 0.0)) / threshold
        for name, threshold in _REAL_RECALL_GATES.items()
        if name in recall
    )
    if not normalized:
        return (-float("inf"),)
    observed_mean = float(np.mean([
        recall[name] for name in _REAL_RECALL_GATES if name in recall
    ]))
    return (*normalized,
        observed_mean,
        float(recall.get("overall", 0.0)),
    )


def build_report(
    *, epochs: int = 8, checkpoint: Path = DEFAULT_CHECKPOINT,
    initialize: Path = DEFAULT_INITIALIZATION,
    allow_incomplete_corpus: bool = False,
) -> tuple[dict, dict]:
    torch.manual_seed(20260721)
    np.random.seed(20260721)
    random.seed(20260721)
    input_identity = real_locus_input_identity(CORPUS)
    manifest = json.loads((CORPUS / "manifest.json").read_text("utf-8"))
    reviews = json.loads((CORPUS / "review.json").read_text("utf-8"))["reviews"]
    loci, excluded_untyped = _typed_reviewed_loci(manifest["loci"], reviews)
    if not loci:
        raise RuntimeError(
            "real-locus calibration has no explicit ProposalNet family labels"
        )
    splits = _split_rows(loci)
    corpus_capacity = _real_corpus_capacity(splits)
    if not corpus_capacity["passed"] and not allow_incomplete_corpus:
        failed = [
            f"calibration:{family}={row['instances']}/{row['minimum_instances']}"
            for family, row in corpus_capacity["calibration_gates"].items()
            if not row["passed"]
        ] + [
            f"test:{family}={row['instances']}/{row['minimum_instances']}"
            for family, row in corpus_capacity["test_gates"].items()
            if not row["passed"]
        ]
        raise RuntimeError(
            "real-locus corpus cannot satisfy fixed promotion/calibration "
            "sample floors; expand typed source-disjoint evidence before "
            "fine-tuning (or use --diagnostic-incomplete-corpus explicitly): "
            + ", ".join(failed)
        )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not initialize.is_file():
        raise FileNotFoundError(
            f"large ProposalNet initialization is required: {initialize}"
        )
    initialization_payload = torch.load(
        initialize, map_location=device, weights_only=False,
    )
    if initialization_payload.get("schema") != "pcdc-proposal-net-checkpoint/v2-large":
        raise RuntimeError("real-locus calibration requires a v2-large checkpoint")
    if initialization_payload.get("label_contract_version") not in (
        SUPPORTED_PRETRAIN_LABEL_CONTRACTS
    ):
        raise RuntimeError("large checkpoint lacks the proved owner-label contract")
    config = ProposalNetConfig(**initialization_payload["config"])
    real_locus_contract = hashlib.sha256()
    real_locus_contract.update(Path(__file__).read_bytes())
    real_locus_contract.update((CORPUS / "manifest.json").read_bytes())
    real_locus_contract.update((CORPUS / "review.json").read_bytes())
    real_locus_contract_sha256 = real_locus_contract.hexdigest()
    support_size = (128 // 4) * int(config.mask_upsample)
    prepared = {
        name: [
            _prepare(
                row, row["_proposal_review"], support_size=support_size,
            )
            for row in rows
        ]
        for name, rows in splits.items()
    }
    model = ProposalNet(config).to(device)
    model.load_state_dict(initialization_payload["model"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5, weight_decay=1e-4)
    history = []
    baseline_neural = _neural_entries(
        model, prepared["calibration"], device,
    )
    baseline_recall = _recall_at_k(
        prepared["calibration"], baseline_neural, 5,
    )
    baseline_recall["glyph_group"] = _family_recall_at_k(
        prepared["calibration"], baseline_neural,
        semantic_class="text", family="glyph_group", k=5,
    )
    best_selection_key = _real_calibration_selection_key(baseline_recall)
    selection_history = [{
        "epoch": 0, "training_loss": None,
        "calibration_global_recall_at_5": baseline_recall,
        "selection_key": best_selection_key,
        "source": "immutable-initialization-baseline",
    }]
    best_epoch = 0
    best_state = {
        name: value.detach().cpu().clone()
        for name, value in model.state_dict().items()
    }
    started = time.perf_counter()
    model.train()
    for epoch in range(max(1, int(epochs))):
        order = list(range(len(prepared["train"])))
        random.Random(20260721 + epoch).shuffle(order)
        losses = []
        for start in range(0, len(order), 12):
            batch = [prepared["train"][index] for index in order[start:start + 12]]
            images = torch.as_tensor(np.stack([row["rgba"] for row in batch]), device=device)
            targets = [_target(row, config, device) for row in batch]
            optimizer.zero_grad(set_to_none=True)
            output = model(images)
            loss = proposal_net_loss(output, targets)["total"]
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        history.append(float(np.mean(losses)))
        calibration_neural = _neural_entries(
            model, prepared["calibration"], device,
        )
        calibration_recall = _recall_at_k(
            prepared["calibration"], calibration_neural, 5,
        )
        calibration_recall["glyph_group"] = _family_recall_at_k(
            prepared["calibration"], calibration_neural,
            semantic_class="text", family="glyph_group", k=5,
        )
        selection_key = _real_calibration_selection_key(calibration_recall)
        selection_history.append({
            "epoch": epoch + 1, "training_loss": history[-1],
            "calibration_global_recall_at_5": calibration_recall,
            "selection_key": selection_key,
        })
        if selection_key > best_selection_key:
            best_selection_key = selection_key
            best_epoch = epoch + 1
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
        model.train()

    model.load_state_dict(best_state)

    neural = {}
    for name in ("calibration", "test"):
        neural.update(_neural_entries(model, prepared[name], device))
    cache = EvidenceCache()
    hybrid = {}
    support_recall = {}
    for name in ("calibration", "test"):
        rows, coverage = _hybrid_entries(prepared[name], neural, cache)
        hybrid.update(rows)
        support_recall.update(coverage)
    calibration_examples = []
    for row in prepared["calibration"]:
        calibration_examples.append(_best_example(row, hybrid[row["id"]]))
        if row["family"] == "text_line":
            calibration_examples.append(_best_example(
                row, hybrid[row["id"]], family="glyph_group",
            ))
    calibration = calibrate_conformal_sets(
        calibration_examples, target_coverage=0.99,
        minimum_class_examples=4,
    )
    test_examples = []
    for row in prepared["test"]:
        test_examples.append(_best_example(row, hybrid[row["id"]]))
        if row["family"] == "text_line":
            test_examples.append(_best_example(
                row, hybrid[row["id"]], family="glyph_group",
            ))
    coverage_by_family = audit_conformal_coverage(test_examples, calibration)
    runtime_conformal = _runtime_mode_conformal_coverage(
        model, prepared["test"], device, calibration, cache,
    )
    neural_recall5 = _recall_at_k(prepared["test"], neural, 5)
    neural_recall5["glyph_group"] = _family_recall_at_k(
        prepared["test"], neural, semantic_class="text",
        family="glyph_group", k=5,
    )
    individual_recall32 = _recall_at_k(prepared["test"], hybrid, 32)
    recall32 = _coverage_by_class(prepared["test"], support_recall, 0.95)

    # Train on exact deterministic program/support counterfactual renders.
    # The real-locus train and test partitions are source-disjoint, so neither
    # the ranker nor its gate can memorize a source asset.  Features are
    # measured topology, boundary, appearance and complexity deltas rather
    # than a synthetic class one-hot.
    ranker = CandidateRanker(feature_dim=16, hidden_dim=48).to(device)
    rank_optimizer = torch.optim.AdamW(ranker.parameters(), lr=4e-3)
    train_positive, train_negative, _train_labels, hard_negative_train_counts = (
        _counterfactual_rows(prepared["train"], maximum_per_class=256)
    )
    test_positive, test_negative, test_labels, hard_negative_test_counts = (
        _counterfactual_rows(prepared["test"], maximum_per_class=128)
    )
    hard_negative_class_coverage = all(
        hard_negative_train_counts[name] >= 100
        and hard_negative_test_counts[name] >= 100
        for name in HARD_NEGATIVE_TYPES
    )
    if len(train_positive):
        positive = torch.as_tensor(train_positive, device=device)
        negative = torch.as_tensor(train_negative, device=device)
        for _ in range(160):
            rank_optimizer.zero_grad(set_to_none=True)
            ranking_loss = pairwise_ranking_loss(ranker, positive, negative)
            ranking_loss.backward()
            rank_optimizer.step()
    class_accuracy = {name: 0.0 for name in HARD_NEGATIVE_TYPES}
    hard_negative_accuracy = 0.0
    if len(test_positive):
        positive = torch.as_tensor(test_positive, device=device)
        negative = torch.as_tensor(test_negative, device=device)
        with torch.no_grad():
            correct = (
                ranker(positive) > ranker(negative)
            ).float().cpu().numpy()
        hard_negative_accuracy = float(np.mean(correct))
        for name in HARD_NEGATIVE_TYPES:
            selected = np.asarray([row == name for row in test_labels], bool)
            if np.any(selected):
                class_accuracy[name] = float(np.mean(correct[selected]))

    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **initialization_payload,
        "schema": "pcdc-proposal-net-checkpoint/v2-large",
        "config": asdict(config), "model": model.state_dict(),
        "ranker": ranker.state_dict(), "families": QUERY_FAMILIES,
        "relations": 8, "hard_negative_types": HARD_NEGATIVE_TYPES,
        "calibration": asdict(calibration),
        "training_split_ids": [row["id"] for row in prepared["train"]],
        "real_locus_initialized_from": str(initialize.resolve()),
        "real_locus_initialization_sha256": hashlib.sha256(
            initialize.read_bytes(),
        ).hexdigest(),
        "real_locus_epochs": int(epochs),
        "real_locus_contract_sha256": real_locus_contract_sha256,
    }
    # The pretraining optimizer/scaler no longer correspond to the fine-tuned
    # weights.  Keeping them would make a later resume silently restore stale
    # momentum under a different real-locus objective.
    payload.pop("optimizer", None)
    payload.pop("scaler", None)
    torch.save(payload, checkpoint)
    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    text_shape_coverage = min(
        coverage_by_family.get("text_line", 0.0),
        coverage_by_family.get("glyph_group", 0.0),
        coverage_by_family.get("whole_shape", 0.0),
    )
    real_neural_recall_gate = {
        "overall": neural_recall5.get("overall", 0.0) >= 0.97,
        "text": neural_recall5.get("text", 0.0) >= 0.99,
        "glyph_group": neural_recall5.get("glyph_group", 0.0) >= 0.99,
        "small_shape": neural_recall5.get("small_shape", 0.0) >= 0.98,
        "layer_knockout": neural_recall5.get("layer_knockout", 0.0) >= 0.95,
        "stroke_diagram": neural_recall5.get("stroke_diagram", 0.0) >= 0.98,
        "gradient": neural_recall5.get("gradient", 0.0) >= 0.95,
        "symmetry_repeat_group": neural_recall5.get(
            "symmetry_repeat_group", 0.0,
        ) >= 0.95,
        "codec_detail": neural_recall5.get("codec_detail", 0.0) >= 0.95,
    }
    threshold_by_family = {
        row.family: row for row in calibration.thresholds
    }
    conformal_required = (
        "text_line", "glyph_group", "whole_shape", "layer_relation",
        "stroke_network", "appearance_model", "symmetry_repeat_group",
        "risk_hard_negative",
    )
    conformal_nonvacuous = all(
        family in threshold_by_family
        and threshold_by_family[family].calibration_count >= 100
        and threshold_by_family[family].threshold < 1.0
        for family in conformal_required
    )
    required_conformal_coverage = min(
        (coverage_by_family.get(family, 0.0) for family in conformal_required),
        default=0.0,
    )
    gate = (
        required_conformal_coverage >= 0.99
        and min(recall32.get("text", 0.0), recall32.get("small_shape", 0.0)) >= 0.99
        and hard_negative_accuracy >= 0.95
        and hard_negative_class_coverage
        and all(real_neural_recall_gate.values())
        and conformal_nonvacuous
        and runtime_conformal["all_quality_modes_coverage_ge_99pct"]
    )
    report = {
        "schema": "pcdc-experiment9/v1",
        "input_identity": input_identity,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if gate else "failed", "gate_pass": gate,
        "device": str(device), "epochs": epochs,
        "training_seconds": time.perf_counter() - started,
        "split_counts": {name: len(rows) for name, rows in prepared.items()},
        "excluded_untyped_loci": excluded_untyped,
        "excluded_untyped_count": len(excluded_untyped),
        "real_corpus_capacity_preflight": corpus_capacity,
        "diagnostic_incomplete_corpus": bool(allow_incomplete_corpus),
        "split_policy": (
            "source-asset-family-disjoint; deterministic primary-semantic-class "
            "stratification at 70/15/15"
        ),
        "initialized_from": str(initialize.resolve()),
        "initialization_sha256": hashlib.sha256(initialize.read_bytes()).hexdigest(),
        "label_contract_version": initialization_payload.get(
            "label_contract_version"
        ),
        "label_contract_sha256": initialization_payload.get(
            "label_contract_sha256"
        ),
        "real_locus_contract_sha256": real_locus_contract_sha256,
        "loss_history": history,
        "real_locus_checkpoint_selection": {
            "contract": "calibration-weakest-normalized-global-Recall@5/v1",
            "best_epoch": best_epoch,
            "best_selection_key": best_selection_key,
            "history": selection_history,
        },
        "real_neural_only_global_recall_at_5": neural_recall5,
        "hybrid_support_recall_at_32": recall32,
        "individual_query_iou50_recall_at_32_diagnostic": individual_recall32,
        "conformal_target_coverage": 0.99,
        "calibration": asdict(calibration),
        "conformal_admission_contract": (
            "exact-family-prefix-rank/support-IoU>=0.50/v1"
        ),
        "conformal_thresholds": [asdict(row) for row in calibration.thresholds],
        "conformal_vacuous_classes": [
            row.family for row in calibration.thresholds if row.threshold >= 1.0
        ],
        "conformal_required_families": conformal_required,
        "conformal_nonvacuous": conformal_nonvacuous,
        "test_conformal_coverage_by_family": coverage_by_family,
        "runtime_conformal_admission": runtime_conformal,
        "hard_negative_types": list(HARD_NEGATIVE_TYPES),
        "hard_negative_pairwise_accuracy": hard_negative_accuracy,
        "hard_negative_pairwise_accuracy_by_class": class_accuracy,
        "hard_negative_train_counts": hard_negative_train_counts,
        "hard_negative_test_counts": hard_negative_test_counts,
        "hard_negative_class_coverage": hard_negative_class_coverage,
        "hard_negative_feature_contract": (
            "exact-canonical-counterfactual-render/topology-boundary-appearance-"
            "complexity-deltas/v1"
        ),
        "checkpoint": str(checkpoint), "checkpoint_sha256": checkpoint_sha,
        "classical_geometry_role": "precise-boundary source; neural queries are unioned, never replacement",
        "gate": {
            "text_shape_conformal_coverage_ge_99pct": text_shape_coverage >= 0.99,
            "all_required_conformal_coverage_ge_99pct": (
                required_conformal_coverage >= 0.99
            ),
            "text_shape_recall_at_32_ge_99pct": min(
                recall32.get("text", 0.0), recall32.get("small_shape", 0.0)
            ) >= 0.99,
            "hard_negative_ranking_ge_95pct": hard_negative_accuracy >= 0.95,
            "all_hard_negative_classes_source_disjoint": (
                hard_negative_class_coverage
            ),
            "real_neural_only_global_recall_at_5": real_neural_recall_gate,
            "required_conformal_nonvacuous": conformal_nonvacuous,
            "runtime_fast_balanced_max_conformal_coverage_ge_99pct": (
                runtime_conformal["all_quality_modes_coverage_ge_99pct"]
            ),
        },
    }
    return report, payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument(
        "--initialize", type=Path, default=DEFAULT_INITIALIZATION,
        help="proved v2-large candidate to fine-tune; toy-from-scratch is forbidden",
    )
    parser.add_argument(
        "--diagnostic-incomplete-corpus", action="store_true",
        help=(
            "run a non-promotable diagnostic despite failed real sample floors; "
            "never implied by default"
        ),
    )
    args = parser.parse_args()
    report, _payload = build_report(
        epochs=args.epochs, checkpoint=args.checkpoint,
        initialize=args.initialize,
        allow_incomplete_corpus=args.diagnostic_incomplete_corpus,
    )
    report = bind_report(report, evaluator_source=__file__)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), "utf-8")
    print(json.dumps({
        "status": report["status"], "gate": report["gate"],
        "out": str(args.out), "checkpoint": str(args.checkpoint),
    }, indent=2))


if __name__ == "__main__":
    main()

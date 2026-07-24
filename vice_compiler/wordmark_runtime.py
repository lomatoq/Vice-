"""Fail-closed runtime adapter for the whole-line wordmark prior.

The neural model is only a proposal generator.  Inputs are normalized with the
same rectangular geometry and observation features as training, decoded at the
native ROI resolution, and rejected unless topology and source-edit bounds are
certified.  Production defaults require a hash-bound promotion manifest;
explicit checkpoint paths remain local evaluation overrides.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
import torch

from .wordmark_prior import (
    WORDMARK_VOCAB_SHA256,
    WordmarkPriorConfig,
    WordmarkPriorNet,
    decode_wordmark_support,
    topology_signature,
    wordmark_prior_source_sha256,
    wordmark_token_ids,
)

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_WORDMARK_PRIOR_CHECKPOINT = PROJECT / "models" / "wordmark_prior.pt"
DEFAULT_WORDMARK_PRIOR_PROMOTION = (
    PROJECT / "models" / "wordmark_prior_promotion.json"
)


@dataclass(frozen=True)
class WordmarkPriorInput:
    observed_ink: np.ndarray
    recognized_text: str
    certified_support: np.ndarray


@dataclass(frozen=True)
class WordmarkPriorProposal:
    support_mask: np.ndarray
    predicted_topology: tuple[int, int]
    topology_confidence: float
    support_threshold: float
    repair_confidence_threshold: float
    source_iou: float
    source_edit_fraction: float
    checkpoint_epoch: int


@dataclass(frozen=True)
class _PreparedWordmark:
    features: np.ndarray
    tokens: np.ndarray
    text_length: int
    source: np.ndarray
    bbox_xyxy: tuple[int, int, int, int]
    normalized_xyxy: tuple[int, int, int, int]
    projection_xyxy: tuple[int, int, int, int]
    projection_normalized_xyxy: tuple[int, int, int, int]


def _path_stat_identity(path: Path) -> tuple[str, int, int]:
    resolved = path.expanduser().resolve()
    try:
        stat = resolved.stat()
    except OSError:
        return str(resolved), -1, -1
    return str(resolved), int(stat.st_mtime_ns), int(stat.st_size)


@lru_cache(maxsize=4)
def _promotion_evidence_paths_cached(
    manifest_identity: tuple[str, int, int],
) -> tuple[Path, ...]:
    try:
        payload = json.loads(Path(manifest_identity[0]).read_text("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ()
    return tuple(
        Path(str(payload[key])).expanduser().resolve()
        for key in (
            "training_report", "preflight_report", "short_logo_audit_report",
            "experiment4_report",
            "experiment4_baseline_report", "full_tests_report",
        )
        if payload.get(key)
    )


def _promotion_validation_identity(
    checkpoint: Path, manifest: Path,
) -> tuple[tuple[str, int, int], ...]:
    manifest_identity = _path_stat_identity(manifest)
    evidence = _promotion_evidence_paths_cached(manifest_identity)
    return (
        _path_stat_identity(checkpoint), manifest_identity,
        *(_path_stat_identity(path) for path in evidence),
    )


@lru_cache(maxsize=4)
def _validate_wordmark_prior_promotion_cached(
    identity: tuple[tuple[str, int, int], ...],
) -> None:
    validate_wordmark_prior_promotion(
        Path(identity[0][0]), Path(identity[1][0]),
    )


def resolve_wordmark_prior_checkpoint(path: Path | None = None) -> Path | None:
    candidate = path
    override = os.environ.get("VICE_WORDMARK_PRIOR_CHECKPOINT", "").strip()
    if candidate is None:
        if override:
            # An environment variable is process-global and would otherwise
            # bypass BUILD_FREEZE accidentally in a production service.  Keep
            # the unpromoted route explicit and evaluation-only; direct Path
            # arguments remain available to isolated probes.
            if os.environ.get("VICE_WORDMARK_PRIOR_EVALUATION") != "1":
                return None
            candidate = Path(override)
        else:
            candidate = DEFAULT_WORDMARK_PRIOR_CHECKPOINT
    candidate = candidate.expanduser().resolve()
    if not candidate.is_file():
        return None
    explicit = path is not None or bool(override)
    if candidate == DEFAULT_WORDMARK_PRIOR_CHECKPOINT.resolve() and not explicit:
        try:
            _validate_wordmark_prior_promotion_cached(
                _promotion_validation_identity(
                    candidate, DEFAULT_WORDMARK_PRIOR_PROMOTION,
                ),
            )
        except (OSError, RuntimeError, UnicodeDecodeError, ValueError, TypeError):
            return None
    return candidate


def validate_wordmark_prior_promotion(
    checkpoint: Path = DEFAULT_WORDMARK_PRIOR_CHECKPOINT,
    manifest: Path = DEFAULT_WORDMARK_PRIOR_PROMOTION,
) -> dict[str, Any]:
    checkpoint = checkpoint.resolve()
    manifest = manifest.resolve()
    if not checkpoint.is_file() or not manifest.is_file():
        raise RuntimeError("production wordmark prior or promotion is missing")
    promotion = json.loads(manifest.read_text("utf-8"))
    from .build_identity import compiler_source_sha256
    expected = {
        "schema": "pcdc-wordmark-prior-promotion/v1",
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "model_data_contract_sha256": wordmark_prior_source_sha256(),
        "compiler_source_sha256": compiler_source_sha256(),
    }
    mismatches = {
        key: {"expected": value, "actual": promotion.get(key)}
        for key, value in expected.items() if promotion.get(key) != value
    }
    if promotion.get("candidate_sha256") != expected["checkpoint_sha256"]:
        mismatches["candidate_sha256"] = {
            "expected": expected["checkpoint_sha256"],
            "actual": promotion.get("candidate_sha256"),
        }
    evidence_payloads: dict[str, dict[str, Any]] = {}
    for key in (
        "training_report", "preflight_report", "short_logo_audit_report",
        "experiment4_report",
        "experiment4_baseline_report", "full_tests_report",
    ):
        raw_path = promotion.get(key)
        expected_sha = promotion.get(f"{key}_sha256")
        evidence = Path(raw_path).expanduser().resolve() if raw_path else None
        actual_sha = (
            hashlib.sha256(evidence.read_bytes()).hexdigest()
            if evidence is not None and evidence.is_file() else None
        )
        if not isinstance(expected_sha, str) or actual_sha != expected_sha:
            mismatches[key] = {
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "path": str(evidence) if evidence is not None else raw_path,
            }
        if evidence is not None and evidence.is_file():
            try:
                payload = json.loads(evidence.read_text("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                payload = {}
            evidence_payloads[key] = payload if isinstance(payload, dict) else {}
    from .audit_full_regression import regression_suite_source_sha256
    from .build_identity import evaluation_source_sha256

    trainer_digest = hashlib.sha256(b"pcdc-wordmark-trainer-source/v1\0")
    trainer_digest.update(wordmark_prior_source_sha256().encode("ascii"))
    trainer_digest.update(b"\0")
    trainer_digest.update(
        (PROJECT / "vice_compiler/train_wordmark_prior.py").read_bytes()
    )
    current_trainer = trainer_digest.hexdigest()
    short_digest = hashlib.sha256(b"pcdc-wordmark-short-logo-audit/v1\0")
    short_digest.update(wordmark_prior_source_sha256().encode("ascii"))
    short_digest.update(b"\0")
    short_digest.update(current_trainer.encode("ascii"))
    short_digest.update(b"\0")
    short_digest.update(
        (PROJECT / "vice_compiler/audit_wordmark_short_logo.py").read_bytes()
    )
    current_short_audit = short_digest.hexdigest()
    phase4_evaluator = evaluation_source_sha256(
        "vice_compiler/experiment4_textline.py",
    )
    live_evidence = {
        "training_report_trainer": (
            evidence_payloads.get("training_report", {}).get(
                "trainer_source_sha256"
            ),
            current_trainer,
        ),
        "preflight_report_trainer": (
            evidence_payloads.get("preflight_report", {}).get(
                "trainer_source_sha256"
            ),
            current_trainer,
        ),
        "short_logo_audit_source": (
            evidence_payloads.get("short_logo_audit_report", {}).get(
                "audit_source_sha256"
            ),
            current_short_audit,
        ),
        "experiment4_evaluator": (
            evidence_payloads.get("experiment4_report", {}).get(
                "evaluation_source_sha256"
            ),
            phase4_evaluator,
        ),
        "experiment4_baseline_evaluator": (
            evidence_payloads.get("experiment4_baseline_report", {}).get(
                "evaluation_source_sha256"
            ),
            phase4_evaluator,
        ),
        "full_regression_evaluator": (
            evidence_payloads.get("full_tests_report", {}).get(
                "evaluation_source_sha256"
            ),
            regression_suite_source_sha256(),
        ),
    }
    for key, (actual, current) in live_evidence.items():
        if actual != current:
            mismatches[key] = {"expected": current, "actual": actual}
    if mismatches:
        raise RuntimeError(f"wordmark-prior promotion mismatch: {mismatches}")
    return promotion


def _checkpoint_identity(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return str(path), int(stat.st_mtime_ns), int(stat.st_size)


@lru_cache(maxsize=2)
def _load_checkpoint_cached(
    identity: tuple[str, int, int],
) -> tuple[WordmarkPriorNet, torch.device, dict[str, Any]]:
    path = Path(identity[0])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    payload = torch.load(path, map_location=device, weights_only=False)
    if payload.get("schema") != "pcdc-wordmark-prior-checkpoint/v1":
        raise ValueError("unsupported wordmark-prior checkpoint schema")
    if payload.get("vocabulary_sha256") != WORDMARK_VOCAB_SHA256:
        raise ValueError("wordmark-prior vocabulary mismatch")
    if (
        payload.get("model_data_contract_sha256")
        != wordmark_prior_source_sha256()
    ):
        raise ValueError("wordmark-prior model/data contract is stale")
    config = WordmarkPriorConfig(**dict(payload.get("config", {})))
    config.validate()
    model = WordmarkPriorNet(config).to(device)
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()
    return model, device, payload


def load_wordmark_prior(
    checkpoint: Path | None = None,
) -> tuple[WordmarkPriorNet, torch.device, dict[str, Any]] | None:
    resolved = resolve_wordmark_prior_checkpoint(checkpoint)
    if resolved is None:
        return None
    try:
        return _load_checkpoint_cached(_checkpoint_identity(resolved))
    except (OSError, RuntimeError, TypeError, ValueError, KeyError):
        return None


def _bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _prepare(
    request: WordmarkPriorInput, config: WordmarkPriorConfig,
) -> _PreparedWordmark | None:
    source = np.asarray(request.certified_support, bool)
    observed = np.asarray(request.observed_ink, np.float32)
    if (
        source.ndim != 2 or observed.shape != source.shape
        or not np.isfinite(observed).all()
    ):
        return None
    encoded = wordmark_token_ids(
        request.recognized_text, max_characters=config.max_characters,
    )
    box = _bbox(source)
    if box is None or encoded is None:
        return None
    x1, y1, x2, y2 = box
    crop = np.clip(observed[y1:y2, x1:x2], 0.0, 1.0)
    crop_height, crop_width = crop.shape
    if crop_height < 2 or crop_width < 3:
        return None
    margin_y = max(2, config.image_height // 14)
    margin_x = max(3, config.image_width // 40)
    available_height = config.image_height - 2 * margin_y
    available_width = config.image_width - 2 * margin_x
    scale = min(
        available_width / crop_width, available_height / crop_height,
    )
    normalized_width = max(1, int(round(crop_width * scale)))
    normalized_height = max(1, int(round(crop_height * scale)))
    normalized_x = (config.image_width - normalized_width) // 2
    normalized_y = (config.image_height - normalized_height) // 2
    interpolation = (
        cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    )
    scale_x = normalized_width / crop_width
    scale_y = normalized_height / crop_height

    # Keep the exact certified-support normalization used before this adapter,
    # but project a bounded native context into the otherwise empty model
    # margins.  The caller deliberately supplies contrast evidence in a halo;
    # cropping exactly to the damaged support bbox discarded that evidence and
    # made restoration of an outer stem or terminal mathematically impossible.
    # The inverse projection below is bound to the same affine map and to a
    # small native context, so this cannot turn into an unbounded canvas edit.
    context_pad = max(2, min(12, int(round(0.12 * crop_height))))
    px1 = max(0, x1 - context_pad)
    py1 = max(0, y1 - context_pad)
    px2 = min(source.shape[1], x2 + context_pad)
    py2 = min(source.shape[0], y2 + context_pad)
    context = np.clip(observed[py1:py2, px1:px2], 0.0, 1.0)
    transform = np.asarray((
        (scale_x, 0.0, normalized_x - scale_x * (x1 - px1)),
        (0.0, scale_y, normalized_y - scale_y * (y1 - py1)),
    ), np.float32)
    normalized = cv2.warpAffine(
        context, transform, (config.image_width, config.image_height),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
        borderValue=0.0,
    )
    # Preserve byte-equivalent core normalization; only the model margins gain
    # the newly reachable contrast context.
    normalized[
        normalized_y:normalized_y + normalized_height,
        normalized_x:normalized_x + normalized_width,
    ] = cv2.resize(
        crop, (normalized_width, normalized_height),
        interpolation=interpolation,
    )
    # Lazy: the warm compiler path never imports Pillow/training data unless a
    # promoted or explicit checkpoint is actually enabled.
    from .wordmark_prior_data import wordmark_observation_features
    tokens, text_length = encoded
    pnx1 = max(0, int(np.floor(normalized_x + (px1 - x1) * scale_x)))
    pny1 = max(0, int(np.floor(normalized_y + (py1 - y1) * scale_y)))
    pnx2 = min(
        config.image_width,
        int(np.ceil(normalized_x + (px2 - x1) * scale_x)),
    )
    pny2 = min(
        config.image_height,
        int(np.ceil(normalized_y + (py2 - y1) * scale_y)),
    )
    return _PreparedWordmark(
        features=wordmark_observation_features(normalized),
        tokens=tokens, text_length=text_length, source=source,
        bbox_xyxy=box,
        normalized_xyxy=(
            normalized_x, normalized_y,
            normalized_x + normalized_width,
            normalized_y + normalized_height,
        ),
        projection_xyxy=(px1, py1, px2, py2),
        projection_normalized_xyxy=(pnx1, pny1, pnx2, pny2),
    )


def propose_wordmark_masks(
    requests: Iterable[WordmarkPriorInput], *, checkpoint: Path | None = None,
    minimum_iou: float = 0.42, maximum_change_fraction: float = 0.55,
) -> tuple[WordmarkPriorProposal | None, ...]:
    rows = tuple(requests)
    if not rows:
        return ()
    loaded = load_wordmark_prior(checkpoint)
    if loaded is None:
        return tuple(None for _ in rows)
    model, device, payload = loaded
    prepared_rows: list[_PreparedWordmark | None] = []
    for row in rows:
        try:
            prepared_rows.append(_prepare(row, model.config))
        except (MemoryError, RuntimeError, TypeError, ValueError, cv2.error):
            prepared_rows.append(None)
    prepared = tuple(prepared_rows)
    valid_indices = tuple(
        index for index, row in enumerate(prepared) if row is not None
    )
    results: list[WordmarkPriorProposal | None] = [None] * len(rows)
    if not valid_indices:
        return tuple(results)
    try:
        features = torch.from_numpy(np.stack([
            prepared[index].features for index in valid_indices  # type: ignore[union-attr]
        ])).to(device=device, dtype=torch.float32)
        tokens = torch.from_numpy(np.stack([
            prepared[index].tokens for index in valid_indices  # type: ignore[union-attr]
        ])).to(device=device, dtype=torch.long)
        lengths = torch.tensor([
            prepared[index].text_length for index in valid_indices  # type: ignore[union-attr]
        ], device=device, dtype=torch.long)
        with torch.inference_mode():
            output = model(features, tokens, lengths)
            probabilities = torch.sigmoid(
                output["support_logits"],
            )[:, 0].cpu().numpy()
            component_probability = torch.softmax(
                output["component_logits"], dim=1,
            ).cpu().numpy()
            hole_probability = torch.softmax(
                output["hole_logits"], dim=1,
            ).cpu().numpy()
        expected_batch = len(valid_indices)
        expected_support = (
            expected_batch, model.config.image_height, model.config.image_width,
        )
        expected_topology = (
            expected_batch, model.config.topology_classes,
        )
        if (
            probabilities.shape != expected_support
            or component_probability.shape != expected_topology
            or hole_probability.shape != expected_topology
            or not np.isfinite(probabilities).all()
            or not np.isfinite(component_probability).all()
            or not np.isfinite(hole_probability).all()
        ):
            raise ValueError("wordmark inference returned malformed tensors")
    except (
        IndexError, KeyError, MemoryError, RuntimeError, TypeError, ValueError,
        cv2.error,
    ):
        if device.type == "cuda":
            torch.cuda.empty_cache()
        return tuple(results)
    support_threshold = float(payload.get("support_threshold", 0.5))
    repair_threshold = float(
        payload.get("topology_repair_confidence_threshold", 1.01)
    )
    for batch_index, request_index in enumerate(valid_indices):
        row = prepared[request_index]
        assert row is not None
        predicted = (
            int(np.argmax(component_probability[batch_index])),
            int(np.argmax(hole_probability[batch_index])),
        )
        confidence = float(min(
            np.max(component_probability[batch_index]),
            np.max(hole_probability[batch_index]),
        ))
        sx1, sy1, sx2, sy2 = row.bbox_xyxy
        nx1, ny1, nx2, ny2 = row.normalized_xyxy
        x1, y1, x2, y2 = row.projection_xyxy
        scale_x = (nx2 - nx1) / max(1, sx2 - sx1)
        scale_y = (ny2 - ny1) / max(1, sy2 - sy1)
        # Sample the bounded native context through the exact inverse affine
        # used by _prepare.  Then overwrite the incumbent bbox with the old
        # resize path byte-for-byte: adding reachable margins must not move or
        # rescale any already certified source pixel.
        try:
            inverse_projection = np.asarray((
                (scale_x, 0.0, nx1 + scale_x * (x1 - sx1)),
                (0.0, scale_y, ny1 + scale_y * (y1 - sy1)),
            ), np.float32)
            native_probability = cv2.warpAffine(
                probabilities[batch_index], inverse_projection,
                (x2 - x1, y2 - y1),
                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT, borderValue=0.0,
            )
            native_probability[
                sy1 - y1:sy2 - y1, sx1 - x1:sx2 - x1,
            ] = cv2.resize(
                probabilities[batch_index, ny1:ny2, nx1:nx2],
                (sx2 - sx1, sy2 - sy1), interpolation=cv2.INTER_LINEAR,
            )
            native, _threshold, matched = decode_wordmark_support(
                native_probability, expected_topology=predicted,
                preferred_threshold=support_threshold,
                allow_repair=confidence >= repair_threshold,
            )
            if not matched or topology_signature(native) != predicted:
                continue
        except (MemoryError, RuntimeError, TypeError, ValueError, cv2.error):
            # The learned lane is optional.  A single malformed prediction or
            # OpenCV allocation failure must not discard healthy siblings or
            # take down the certified non-neural vectorization path.
            continue
        rebuilt = np.zeros_like(row.source)
        rebuilt[y1:y2, x1:x2] = native
        intersection = int(np.sum(rebuilt & row.source))
        union = int(np.sum(rebuilt | row.source))
        source_iou = intersection / max(1, union)
        edit_fraction = int(np.sum(rebuilt != row.source)) / max(
            1, int(np.sum(row.source)),
        )
        if source_iou < minimum_iou or edit_fraction > maximum_change_fraction:
            continue
        rebuilt.setflags(write=False)
        results[request_index] = WordmarkPriorProposal(
            support_mask=rebuilt, predicted_topology=predicted,
            topology_confidence=confidence,
            support_threshold=support_threshold,
            repair_confidence_threshold=repair_threshold,
            source_iou=source_iou, source_edit_fraction=edit_fraction,
            checkpoint_epoch=int(payload.get("epoch", 0)),
        )
    return tuple(results)


def propose_wordmark_mask(
    observed_ink: np.ndarray, recognized_text: str,
    certified_support: np.ndarray, *, checkpoint: Path | None = None,
    minimum_iou: float = 0.42, maximum_change_fraction: float = 0.55,
) -> WordmarkPriorProposal | None:
    return propose_wordmark_masks((WordmarkPriorInput(
        observed_ink=observed_ink, recognized_text=recognized_text,
        certified_support=certified_support,
    ),), checkpoint=checkpoint, minimum_iou=minimum_iou,
        maximum_change_fraction=maximum_change_fraction)[0]

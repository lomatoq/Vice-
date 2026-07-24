"""Experiment B: clean-input identity test for the wordmark prior.

Feeds the model its own CLEAN rendering target (no degradation) with the exact
oracle OCR string, balanced across line lengths, on held-out font families.
This separates two competing explanations of the long-line topology collapse:

- clean long lines still fail  -> the output representation/alignment is the
  ceiling (D1/D2 of the 2026-07-24 external audit);
- clean passes, degraded fails -> the inverse/degradation encoder is the
  ceiling (data/observability problem).

It also measures pixels-per-glyph of the fixed 64x256 letterbox canvas per
length (groundwork for Experiment A, the length x px-per-glyph matrix).

The wordmark modules are imported from an immutable training snapshot so the
fail-closed checkpoint contract (model/data SHA, family split SHA) is honored,
never bypassed: a checkpoint that does not match the snapshot source aborts.

Usage:
  C:\\Python312\\python.exe diagnose_wordmark_clean_identity.py \
      --source-root .training_snapshots/wordmark_full_v4_20260723 \
      --checkpoint models/wordmark_prior_candidate_v1_epoch3.pt
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

SUPPORT_THRESHOLDS = (0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sample_fixed_length_text(generator, length: int, characters: str) -> str:
    # Mirrors the snapshot's _sample_text alphabet modes, minus the two-word
    # mode, so requested lengths stay exact for the per-length matrix.
    mode = int(generator.integers(0, 5))
    if mode == 0:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    elif mode == 1:
        alphabet = "abcdefghijklmnopqrstuvwxyz"
    elif mode == 2:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    elif mode == 3:
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    else:
        alphabet = characters.rstrip(" ")
    return "".join(generator.choice(tuple(alphabet), size=length).tolist())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root", type=Path,
        default=ROOT / ".training_snapshots" / "wordmark_full_v4_20260723",
    )
    parser.add_argument(
        "--checkpoint", type=Path,
        default=ROOT / "models" / "wordmark_prior_candidate_v1_epoch3.pt",
    )
    parser.add_argument(
        "--font-manifest", type=Path,
        default=ROOT / "fonts" / "google-fonts-manifest.json",
    )
    parser.add_argument(
        "--font-root", type=Path, default=ROOT / "fonts" / "google-fonts",
    )
    parser.add_argument("--lengths", type=str, default="1,2,4,8,16,24,32")
    parser.add_argument("--samples-per-length", type=int, default=512)
    parser.add_argument(
        "--ocr-mode", choices=("exact", "corrupted", "blank"), default="exact",
        help="exact = oracle transcript; corrupted = guaranteed-wrong hint "
        "via the snapshot's own corruption; blank = single-space hint "
        "(uninformative conditioning)",
    )
    parser.add_argument(
        "--degrade", action="store_true",
        help="feed the degraded observation (training distribution) instead "
        "of the clean identity input",
    )
    parser.add_argument("--batch-size", type=int, default=48)
    parser.add_argument("--seed", type=int, default=20260724)
    parser.add_argument("--split-seed", type=int, default=20260722)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "benchmarks" / "pcdc_pre_v14"
        / "wordmark_clean_identity_diagnostic.json",
    )
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    if not (source_root / "vice_compiler").is_dir():
        raise RuntimeError(f"no vice_compiler package under {source_root}")
    sys.path.insert(0, str(source_root))

    import torch
    from vice_compiler.wordmark_prior import (
        TOPOLOGY_REPAIR_MINIMUM_CONFIDENCE,
        WORDMARK_CHARACTERS,
        WordmarkPriorConfig,
        WordmarkPriorNet,
        decode_wordmark_support,
        topology_signature,
        wordmark_prior_source_sha256,
        wordmark_token_ids,
    )
    from vice_compiler.wordmark_prior_data import (
        _corrupt_text_hint,
        _rng,
        degrade_wordmark,
        render_clean_wordmark,
        wordmark_observation_features,
    )
    from vice_compiler.glyph_prior_data import (
        load_font_records,
        split_font_families,
    )

    started = time.perf_counter()
    payload = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    contract = wordmark_prior_source_sha256()
    if payload.get("schema") != "pcdc-wordmark-prior-checkpoint/v1":
        raise RuntimeError("checkpoint schema is not pcdc-wordmark-prior-checkpoint/v1")
    if payload.get("model_data_contract_sha256") != contract:
        raise RuntimeError(
            "checkpoint contract mismatch (fail closed): "
            f"checkpoint={payload.get('model_data_contract_sha256')} "
            f"snapshot={contract}; try another --source-root snapshot"
        )
    fonts, manifest = load_font_records(
        args.font_manifest, font_root=args.font_root,
    )
    split = split_font_families(fonts, seed=args.split_seed)
    if payload.get("family_split_sha256") != split.digest:
        raise RuntimeError("checkpoint belongs to another family split (fail closed)")

    device = torch.device(
        ("cuda" if torch.cuda.is_available() else "cpu")
        if args.device == "auto" else args.device
    )
    config = WordmarkPriorConfig(**dict(payload["config"]))
    config.validate()
    model = WordmarkPriorNet(config).to(device)
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()

    lengths = tuple(int(value) for value in args.lengths.split(","))
    per_length = int(args.samples_per_length)
    test_fonts = split.test
    total = len(lengths) * per_length
    maximum_topology = config.topology_classes - 1

    probabilities = np.zeros(
        (total, config.image_height, config.image_width), np.float16,
    )
    targets = np.zeros(
        (total, config.image_height, config.image_width), bool,
    )
    head_components = np.zeros(total, np.int64)
    head_holes = np.zeros(total, np.int64)
    head_confidence = np.zeros(total, np.float64)
    true_components = np.zeros(total, np.int64)
    true_holes = np.zeros(total, np.int64)
    sample_length = np.zeros(total, np.int64)
    ink_width = np.zeros(total, np.float64)

    batch_features: list[np.ndarray] = []
    batch_tokens: list[np.ndarray] = []
    batch_text_length: list[int] = []
    batch_rows: list[int] = []

    def _flush() -> None:
        if not batch_rows:
            return
        with torch.no_grad():
            features = torch.from_numpy(np.stack(batch_features)).to(device)
            tokens = torch.from_numpy(np.stack(batch_tokens)).to(device)
            text_length = torch.tensor(
                batch_text_length, dtype=torch.long, device=device,
            )
            output = model(features, tokens, text_length)
            probability = torch.sigmoid(
                output["support_logits"],
            ).cpu().numpy()[:, 0]
            component_probability = torch.softmax(
                output["component_logits"], dim=1,
            )
            hole_probability = torch.softmax(output["hole_logits"], dim=1)
            components = torch.argmax(
                component_probability, dim=1,
            ).cpu().numpy()
            holes = torch.argmax(hole_probability, dim=1).cpu().numpy()
            confidence = np.minimum(
                torch.amax(component_probability, dim=1).cpu().numpy(),
                torch.amax(hole_probability, dim=1).cpu().numpy(),
            )
        for position, row in enumerate(batch_rows):
            probabilities[row] = probability[position].astype(np.float16)
            head_components[row] = int(components[position])
            head_holes[row] = int(holes[position])
            head_confidence[row] = float(confidence[position])
        batch_features.clear()
        batch_tokens.clear()
        batch_text_length.clear()
        batch_rows.clear()

    generated = 0
    for length_index, length in enumerate(lengths):
        for slot in range(per_length):
            row = length_index * per_length + slot
            sample = None
            for retry in range(64):
                index = row + retry * total
                generator = _rng(args.seed, index)
                font = test_fonts[int(generator.integers(0, len(test_fonts)))]
                text = _sample_fixed_length_text(
                    generator, length, WORDMARK_CHARACTERS,
                )
                if args.ocr_mode == "exact":
                    hint = text
                elif args.ocr_mode == "blank":
                    # A single serving-vocabulary punctuation token: legal for
                    # the tokenizer, carries no transcript information.
                    hint = "."
                else:
                    hint = text
                    for _attempt in range(16):
                        candidate_hint = _corrupt_text_hint(
                            text, generator, config.max_characters,
                        )
                        if candidate_hint != text:
                            hint = candidate_hint
                            break
                    if hint == text:
                        alphabet = WORDMARK_CHARACTERS.rstrip(" ")
                        position = int(generator.integers(0, len(text)))
                        replacement = text[position]
                        while replacement == text[position]:
                            replacement = alphabet[
                                int(generator.integers(0, len(alphabet)))
                            ]
                        hint = (
                            text[:position] + replacement + text[position + 1:]
                        )
                tokens = wordmark_token_ids(
                    hint, max_characters=config.max_characters,
                )
                if tokens is None:
                    continue
                token_ids, text_length = tokens
                coverage, support = render_clean_wordmark(
                    font.path, text, config,
                    seed=args.seed + 104729 * index,
                )
                if not np.any(support):
                    continue
                components, holes = topology_signature(support)
                if components > maximum_topology or holes > maximum_topology:
                    continue
                observation = coverage
                if args.degrade:
                    observation = degrade_wordmark(
                        coverage, support, seed=args.seed + 130363 * index,
                    )
                sample = (observation, support, token_ids, text_length,
                          components, holes)
                break
            if sample is None:
                raise RuntimeError(
                    f"length {length} slot {slot}: resampling exhausted"
                )
            observation, support, token_ids, text_length, components, holes = sample
            columns = np.flatnonzero(support.any(axis=0))
            targets[row] = support
            true_components[row] = components
            true_holes[row] = holes
            sample_length[row] = length
            ink_width[row] = float(columns[-1] - columns[0] + 1)
            batch_features.append(wordmark_observation_features(observation))
            batch_tokens.append(np.asarray(token_ids))
            batch_text_length.append(int(text_length))
            batch_rows.append(row)
            if len(batch_rows) >= args.batch_size:
                _flush()
            generated += 1
            if generated % 512 == 0:
                print(f"generated {generated}/{total}", flush=True)
    _flush()

    # Global threshold sweep, calibrated on this diagnostic split only.
    sweep: dict[str, dict[str, float]] = {}
    raw_matches_by_threshold: dict[float, np.ndarray] = {}
    for threshold in SUPPORT_THRESHOLDS:
        matches = np.zeros(total, bool)
        iou_total = 0.0
        for row in range(total):
            mask = probabilities[row].astype(np.float32) >= threshold
            matches[row] = topology_signature(mask) == (
                int(true_components[row]), int(true_holes[row]),
            )
            intersection = np.sum(mask & targets[row])
            union = np.sum(mask | targets[row])
            iou_total += intersection / max(1, union)
        raw_matches_by_threshold[threshold] = matches
        sweep[f"{threshold:.3f}"] = {
            "support_iou": iou_total / total,
            "raw_topology_accuracy": float(np.mean(matches)),
        }
    best_threshold = max(
        SUPPORT_THRESHOLDS,
        key=lambda value: (
            sweep[f"{value:.3f}"]["raw_topology_accuracy"],
            sweep[f"{value:.3f}"]["support_iou"],
        ),
    )
    raw_matches = raw_matches_by_threshold[best_threshold]

    decoded_matches = np.zeros(total, bool)
    decoded_iou = np.zeros(total, np.float64)
    repair_eligible = np.zeros(total, bool)
    for row in range(total):
        probability = probabilities[row].astype(np.float32)
        truth = (int(true_components[row]), int(true_holes[row]))
        predicted = (int(head_components[row]), int(head_holes[row]))
        if head_confidence[row] >= TOPOLOGY_REPAIR_MINIMUM_CONFIDENCE:
            decoded, _threshold, _matched = decode_wordmark_support(
                probability, expected_topology=predicted,
                preferred_threshold=float(best_threshold), allow_repair=True,
            )
            repair_eligible[row] = True
        else:
            decoded = probability >= best_threshold
        decoded_matches[row] = topology_signature(decoded) == truth
        intersection = np.sum(decoded & targets[row])
        union = np.sum(decoded | targets[row])
        decoded_iou[row] = intersection / max(1, union)

    component_correct = head_components == true_components
    hole_correct = head_holes == true_holes
    joint_correct = component_correct & hole_correct
    complex_mask = (true_components > 1) | (true_holes >= 4)

    def _bucket(mask: np.ndarray) -> dict[str, float]:
        count = int(np.sum(mask))
        return {
            "samples": count,
            "pixels_per_glyph_mean": float(
                np.mean(ink_width[mask] / sample_length[mask])
            ),
            "pixels_per_glyph_p10": float(
                np.percentile(ink_width[mask] / sample_length[mask], 10)
            ),
            "raw_topology_accuracy": float(np.mean(raw_matches[mask])),
            "decoded_topology_accuracy": float(np.mean(decoded_matches[mask])),
            "component_head_accuracy": float(np.mean(component_correct[mask])),
            "hole_head_accuracy": float(np.mean(hole_correct[mask])),
            "joint_topology_head_accuracy": float(np.mean(joint_correct[mask])),
            "decoded_support_iou": float(np.mean(decoded_iou[mask])),
            "repair_eligible_fraction": float(np.mean(repair_eligible[mask])),
            "mean_topology_head_confidence": float(
                np.mean(head_confidence[mask])
            ),
        }

    per_length_report = {
        str(length): _bucket(sample_length == length) for length in lengths
    }
    overall = _bucket(np.ones(total, bool))
    complex_report = (
        _bucket(complex_mask) if np.any(complex_mask) else {"samples": 0}
    )

    report = {
        "schema": "vice-wordmark-clean-identity-diagnostic/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Experiments B/E of the 2026-07-24 external audit: identity and "
            "conditioning diagnostics on held-out families, balanced lengths"
        ),
        "ocr_mode": args.ocr_mode,
        "degraded_input": bool(args.degrade),
        "source_root": str(source_root),
        "model_data_contract_sha256": contract,
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": _file_sha256(args.checkpoint),
        "checkpoint_epoch": int(payload["epoch"]),
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "family_split_sha256": split.digest,
        "seed": int(args.seed),
        "split_seed": int(args.split_seed),
        "lengths": list(lengths),
        "samples_per_length": per_length,
        "device": str(device),
        "support_threshold": float(best_threshold),
        "support_threshold_policy": "calibrated-on-this-diagnostic-split",
        "threshold_sweep": sweep,
        "overall": overall,
        "complex": complex_report,
        "per_length": per_length_report,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({
        "support_threshold": report["support_threshold"],
        "overall": overall,
        "per_length": {
            key: {
                "ppg": round(value["pixels_per_glyph_mean"], 2),
                "raw_topology": round(value["raw_topology_accuracy"], 4),
                "decoded_topology": round(
                    value["decoded_topology_accuracy"], 4,
                ),
                "joint_head": round(
                    value["joint_topology_head_accuracy"], 4,
                ),
            }
            for key, value in per_length_report.items()
        },
    }, indent=2))
    print(f"report written to {args.out}")


if __name__ == "__main__":
    main()

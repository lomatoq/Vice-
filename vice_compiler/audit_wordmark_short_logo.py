"""Independent held-out proof for one- and two-symbol wordmark priors.

Aggregate 1--32 metrics can hide a weak monogram slice.  This audit exercises
the frozen candidate on unseen font families with an exactly controlled input
length and is a required, hash-bound promotion artifact.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset

from .glyph_prior_data import GlyphFontRecord, load_font_records, split_font_families
from .train_wordmark_prior import (
    _device, _loader, _move, evaluate, wordmark_trainer_source_sha256,
)
from .wordmark_prior import (
    TOPOLOGY_REPAIR_MINIMUM_CONFIDENCE, WORDMARK_CHARACTERS,
    WordmarkPriorConfig, WordmarkPriorNet, decode_wordmark_support,
    topology_signature, wordmark_prior_source_sha256, wordmark_token_ids,
)
from .wordmark_prior_data import (
    _rng, degrade_wordmark, render_clean_wordmark, signed_distance_target,
    wordmark_observation_features,
)


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = PROJECT / "models" / "wordmark_prior_candidate_v1.pt"
DEFAULT_TRAINING_REPORT = (
    PROJECT / "benchmarks/pcdc_pre_v14/wordmark_prior_full_v1.json"
)
DEFAULT_FONT_MANIFEST = PROJECT / "fonts" / "google-fonts-manifest.json"
DEFAULT_FONT_ROOT = PROJECT / "fonts" / "google-fonts"
DEFAULT_OUT = PROJECT / "benchmarks/pcdc_pre_v14/wordmark_short_logo_audit.json"
SHORT_LOGO_LENGTHS = (1, 2)
MINIMUM_SAMPLES_PER_LENGTH = 2_048
MINIMUM_SUPPORT_IOU = 0.88
MINIMUM_TOPOLOGY_ACCURACY = 0.95
MINIMUM_HEAD_ACCURACY = 0.90
MINIMUM_SUPPORT_IOU_CVAR10 = 0.65
MINIMUM_SYMBOL_MEAN_IOU = 0.75
MINIMUM_SYMBOL_TOPOLOGY_ACCURACY = 0.85
MINIMUM_SYMBOL_HEAD_ACCURACY = 0.75


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def short_logo_audit_source_sha256() -> str:
    digest = hashlib.sha256(b"pcdc-wordmark-short-logo-audit/v1\0")
    digest.update(wordmark_prior_source_sha256().encode("ascii")); digest.update(b"\0")
    digest.update(wordmark_trainer_source_sha256().encode("ascii")); digest.update(b"\0")
    digest.update(Path(__file__).read_bytes())
    return digest.hexdigest()


class FixedLengthWordmarkDataset(Dataset):
    """Procedural held-out wordmarks whose model input length cannot drift."""

    def __init__(
        self, fonts: tuple[GlyphFontRecord, ...], *, text_length: int,
        sample_count: int, seed: int, config: WordmarkPriorConfig,
    ) -> None:
        if text_length not in SHORT_LOGO_LENGTHS:
            raise ValueError("short-logo audit length must be one or two")
        if not fonts:
            raise ValueError("short-logo audit needs held-out fonts")
        self.fonts = fonts
        self.text_length = int(text_length)
        self.sample_count = int(sample_count)
        self.seed = int(seed)
        self.config = config
        self.alphabet = WORDMARK_CHARACTERS.rstrip(" ")

    def __len__(self) -> int:
        return self.sample_count

    def _text(self, index: int, generator: np.random.Generator) -> str:
        # The leading position cycles through the complete visible serving
        # alphabet, so every one-symbol class is present regardless of RNG.
        first = self.alphabet[index % len(self.alphabet)]
        if self.text_length == 1:
            return first
        second = str(generator.choice(tuple(self.alphabet)))
        return first + second

    def _hint(self, text: str, generator: np.random.Generator) -> str:
        # Keep length fixed while still testing OCR substitutions/transposes.
        if generator.random() < 0.75:
            return text
        hint = list(text)
        if len(hint) == 2 and generator.random() < 0.35:
            hint.reverse()
        else:
            index = int(generator.integers(0, len(hint)))
            replacement = str(generator.choice(tuple(self.alphabet)))
            if replacement == hint[index]:
                replacement = self.alphabet[
                    (self.alphabet.index(replacement) + 1) % len(self.alphabet)
                ]
            hint[index] = replacement
        return "".join(hint)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        for retry in range(32):
            sample_index = int(index) + retry * max(1, self.sample_count)
            generator = _rng(self.seed, sample_index)
            font = self.fonts[int(generator.integers(0, len(self.fonts)))]
            text = self._text(int(index), generator)
            hint = self._hint(text, generator)
            tokenized = wordmark_token_ids(
                hint, max_characters=self.config.max_characters,
            )
            if tokenized is None or tokenized[1] != self.text_length:
                raise RuntimeError("short-logo audit emitted an invalid text hint")
            token_ids, text_length = tokenized
            coverage, support = render_clean_wordmark(
                font.path, text, self.config,
                seed=self.seed + 104729 * sample_index,
            )
            components, holes = topology_signature(support)
            maximum = self.config.topology_classes - 1
            if not np.any(support) or components > maximum or holes > maximum:
                continue
            observed = degrade_wordmark(
                coverage, support, seed=self.seed + 130363 * sample_index,
            )
            return {
                "features": torch.from_numpy(
                    wordmark_observation_features(observed),
                ),
                "support": torch.from_numpy(support.astype(np.float32))[None],
                "sdf": torch.from_numpy(signed_distance_target(support))[None],
                "text_tokens": torch.from_numpy(token_ids),
                "text_length": torch.tensor(text_length, dtype=torch.long),
                "components": torch.tensor(components, dtype=torch.long),
                "holes": torch.tensor(holes, dtype=torch.long),
                "audit_character_id": torch.tensor(
                    int(index) % len(self.alphabet), dtype=torch.long,
                ),
            }
        raise RuntimeError("short-logo topology resampling exhausted 32 attempts")


@torch.inference_mode()
def evaluate_symbol_slices(
    model: WordmarkPriorNet, loader, device: torch.device, *,
    support_threshold: float, repair_confidence_threshold: float,
    alphabet: str,
) -> dict[str, Any]:
    """Measure tails and every leading symbol at the frozen decode policy."""
    model.eval()
    samples: list[dict[str, Any]] = []
    grouped: dict[int, list[dict[str, Any]]] = {
        index: [] for index in range(len(alphabet))
    }
    for batch in loader:
        moved = _move(batch, device)
        output = model(
            moved["features"], moved["text_tokens"], moved["text_length"],
        )
        probabilities = torch.sigmoid(
            output["support_logits"],
        ).cpu().numpy()[:, 0]
        targets = moved["support"].cpu().numpy()[:, 0] >= 0.5
        component_probability = torch.softmax(output["component_logits"], dim=1)
        hole_probability = torch.softmax(output["hole_logits"], dim=1)
        predicted_components = torch.argmax(
            component_probability, dim=1,
        ).cpu().numpy()
        predicted_holes = torch.argmax(hole_probability, dim=1).cpu().numpy()
        component_confidence = torch.amax(
            component_probability, dim=1,
        ).cpu().numpy()
        hole_confidence = torch.amax(hole_probability, dim=1).cpu().numpy()
        true_components = moved["components"].cpu().numpy()
        true_holes = moved["holes"].cpu().numpy()
        character_ids = moved["audit_character_id"].cpu().numpy()
        for index, target in enumerate(targets):
            predicted = (
                int(predicted_components[index]), int(predicted_holes[index]),
            )
            truth = (int(true_components[index]), int(true_holes[index]))
            confidence = float(min(
                component_confidence[index], hole_confidence[index],
            ))
            selected = probabilities[index] >= support_threshold
            if (
                confidence >= TOPOLOGY_REPAIR_MINIMUM_CONFIDENCE
                and confidence >= repair_confidence_threshold
            ):
                selected, _threshold, _matched = decode_wordmark_support(
                    probabilities[index], expected_topology=predicted,
                    preferred_threshold=support_threshold, allow_repair=True,
                )
            intersection = int(np.sum(target & selected))
            union = int(np.sum(target | selected))
            row = {
                "support_iou": intersection / max(1, union),
                "topology_correct": topology_signature(selected) == truth,
                "component_head_correct": predicted[0] == truth[0],
                "hole_head_correct": predicted[1] == truth[1],
            }
            samples.append(row)
            grouped[int(character_ids[index])].append(row)
    if not samples or any(not rows for rows in grouped.values()):
        raise RuntimeError("short-logo audit did not cover every visible symbol")

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        ious = sorted(float(row["support_iou"]) for row in rows)
        tail_count = max(1, int(np.ceil(0.10 * len(ious))))
        return {
            "samples": len(rows),
            "mean_support_iou": float(np.mean(ious)),
            "support_iou_cvar10": float(np.mean(ious[:tail_count])),
            "minimum_support_iou": float(ious[0]),
            "topology_accuracy": float(np.mean([
                row["topology_correct"] for row in rows
            ])),
            "component_head_accuracy": float(np.mean([
                row["component_head_correct"] for row in rows
            ])),
            "hole_head_accuracy": float(np.mean([
                row["hole_head_correct"] for row in rows
            ])),
        }

    per_symbol = {
        alphabet[index]: summarize(rows) for index, rows in grouped.items()
    }
    aggregate = summarize(samples)
    aggregate.update({
        "minimum_symbol_mean_support_iou": min(
            row["mean_support_iou"] for row in per_symbol.values()
        ),
        "minimum_symbol_topology_accuracy": min(
            row["topology_accuracy"] for row in per_symbol.values()
        ),
        "minimum_symbol_component_head_accuracy": min(
            row["component_head_accuracy"] for row in per_symbol.values()
        ),
        "minimum_symbol_hole_head_accuracy": min(
            row["hole_head_accuracy"] for row in per_symbol.values()
        ),
        "per_symbol": per_symbol,
    })
    return aggregate


def short_logo_gate(slices: dict[str, dict[str, Any]]) -> bool:
    return all(
        int(slices.get(str(length), {}).get("samples", 0))
        >= MINIMUM_SAMPLES_PER_LENGTH
        and float(slices[str(length)].get("decoded_support_iou", 0.0))
        >= MINIMUM_SUPPORT_IOU
        and float(slices[str(length)].get("decoded_topology_accuracy", 0.0))
        >= MINIMUM_TOPOLOGY_ACCURACY
        and float(slices[str(length)].get("component_head_accuracy", 0.0))
        >= MINIMUM_HEAD_ACCURACY
        and float(slices[str(length)].get("hole_head_accuracy", 0.0))
        >= MINIMUM_HEAD_ACCURACY
        and float(slices[str(length)].get(
            "symbol_fidelity", {},
        ).get("support_iou_cvar10", 0.0)) >= MINIMUM_SUPPORT_IOU_CVAR10
        and float(slices[str(length)].get(
            "symbol_fidelity", {},
        ).get("minimum_symbol_mean_support_iou", 0.0))
        >= MINIMUM_SYMBOL_MEAN_IOU
        and float(slices[str(length)].get(
            "symbol_fidelity", {},
        ).get("minimum_symbol_topology_accuracy", 0.0))
        >= MINIMUM_SYMBOL_TOPOLOGY_ACCURACY
        and float(slices[str(length)].get(
            "symbol_fidelity", {},
        ).get("minimum_symbol_component_head_accuracy", 0.0))
        >= MINIMUM_SYMBOL_HEAD_ACCURACY
        and float(slices[str(length)].get(
            "symbol_fidelity", {},
        ).get("minimum_symbol_hole_head_accuracy", 0.0))
        >= MINIMUM_SYMBOL_HEAD_ACCURACY
        for length in SHORT_LOGO_LENGTHS
    )


def audit(
    *, candidate: Path, training_report: Path, font_manifest: Path,
    font_root: Path, output: Path, samples_per_length: int = 2_048,
    batch_size: int = 128, workers: int = 4, device_name: str = "auto",
) -> dict[str, Any]:
    if samples_per_length < MINIMUM_SAMPLES_PER_LENGTH:
        raise ValueError(
            f"short-logo audit requires >= {MINIMUM_SAMPLES_PER_LENGTH} samples/length"
        )
    checkpoint = torch.load(candidate, map_location="cpu", weights_only=False)
    training = json.loads(training_report.read_text("utf-8"))
    if (
        checkpoint.get("schema") != "pcdc-wordmark-prior-checkpoint/v1"
        or checkpoint.get("model_data_contract_sha256")
        != wordmark_prior_source_sha256()
        or checkpoint.get("trainer_source_sha256")
        != wordmark_trainer_source_sha256()
        or training.get("checkpoint_sha256") != _sha256(candidate)
    ):
        raise RuntimeError("short-logo audit candidate/training contract mismatch")
    contract = training.get("training_contract", {})
    fonts, manifest = load_font_records(font_manifest, font_root=font_root)
    split = split_font_families(fonts, seed=int(contract["family_split_seed"]))
    if (
        str(manifest["content_sha256"]) != training.get("font_manifest_sha256")
        or split.digest != training.get("family_split_sha256")
    ):
        raise RuntimeError("short-logo audit held-out font split mismatch")
    config = WordmarkPriorConfig(**checkpoint["config"])
    model = WordmarkPriorNet(config)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    device = _device(device_name)
    model.to(device).eval()
    fixed_threshold = float(checkpoint["support_threshold"])
    fixed_repair = float(checkpoint["topology_repair_confidence_threshold"])
    base_seed = int(contract["seed"]) + 3_000_017
    slices: dict[str, dict[str, Any]] = {}
    for length in SHORT_LOGO_LENGTHS:
        dataset = FixedLengthWordmarkDataset(
            split.test, text_length=length, sample_count=samples_per_length,
            seed=base_seed + 100_003 * length, config=config,
        )
        loader = _loader(
            dataset, batch_size=batch_size, workers=workers,
        )
        measured = evaluate(
            model, loader, device, thresholds=(fixed_threshold,),
            fixed_threshold=fixed_threshold,
            repair_confidence_thresholds=(fixed_repair,),
            fixed_repair_confidence_threshold=fixed_repair,
        )
        # A separate streaming pass prevents aggregate length metrics from
        # hiding a failed punctuation/letter/digit class.
        measured["symbol_fidelity"] = evaluate_symbol_slices(
            model, loader, device, support_threshold=fixed_threshold,
            repair_confidence_threshold=fixed_repair,
            alphabet=dataset.alphabet,
        )
        slices[str(length)] = measured
    passed = short_logo_gate(slices)
    payload = {
        "schema": "pcdc-wordmark-short-logo-audit/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed",
        "gate_pass": passed,
        "audit_source_sha256": short_logo_audit_source_sha256(),
        "model_data_contract_sha256": wordmark_prior_source_sha256(),
        "trainer_source_sha256": wordmark_trainer_source_sha256(),
        "checkpoint": str(candidate.resolve()),
        "checkpoint_sha256": _sha256(candidate),
        "training_report": str(training_report.resolve()),
        "training_report_sha256": _sha256(training_report),
        "font_manifest_sha256": str(manifest["content_sha256"]),
        "family_split_sha256": split.digest,
        "held_out_font_families": len({row.family for row in split.test}),
        "held_out_font_faces": len(split.test),
        "lengths": list(SHORT_LOGO_LENGTHS),
        "samples_per_length": int(samples_per_length),
        "visible_serving_alphabet": WORDMARK_CHARACTERS.rstrip(" "),
        "thresholds": {
            "minimum_samples_per_length": MINIMUM_SAMPLES_PER_LENGTH,
            "decoded_support_iou": MINIMUM_SUPPORT_IOU,
            "decoded_topology_accuracy": MINIMUM_TOPOLOGY_ACCURACY,
            "component_head_accuracy": MINIMUM_HEAD_ACCURACY,
            "hole_head_accuracy": MINIMUM_HEAD_ACCURACY,
            "support_iou_cvar10": MINIMUM_SUPPORT_IOU_CVAR10,
            "minimum_symbol_mean_support_iou": MINIMUM_SYMBOL_MEAN_IOU,
            "minimum_symbol_topology_accuracy": (
                MINIMUM_SYMBOL_TOPOLOGY_ACCURACY
            ),
            "minimum_symbol_head_accuracy": MINIMUM_SYMBOL_HEAD_ACCURACY,
        },
        "slices": slices,
        "device": str(device),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8",
    )
    temporary.replace(output)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--training-report", type=Path, default=DEFAULT_TRAINING_REPORT,
    )
    parser.add_argument("--font-manifest", type=Path, default=DEFAULT_FONT_MANIFEST)
    parser.add_argument("--font-root", type=Path, default=DEFAULT_FONT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--samples-per-length", type=int, default=2_048)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    print(json.dumps(audit(
        candidate=args.candidate, training_report=args.training_report,
        font_manifest=args.font_manifest, font_root=args.font_root,
        output=args.output, samples_per_length=args.samples_per_length,
        batch_size=args.batch_size, workers=args.workers,
        device_name=args.device,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

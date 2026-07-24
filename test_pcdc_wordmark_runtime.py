from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import cv2
import numpy as np
import torch

from vice_compiler.wordmark_prior import (
    WordmarkPriorConfig, decode_wordmark_support, topology_signature,
)
from vice_compiler.wordmark_runtime import (
    WordmarkPriorInput, _prepare, _promotion_evidence_paths_cached,
    _promotion_validation_identity,
    _validate_wordmark_prior_promotion_cached, propose_wordmark_masks,
    resolve_wordmark_prior_checkpoint,
)


class _ExactRingModel:
    def __init__(self) -> None:
        self.config = WordmarkPriorConfig(base_channels=8, text_embedding_dim=16)
        self.batch_sizes: list[int] = []

    def __call__(
        self, features: torch.Tensor, text_tokens: torch.Tensor,
        text_lengths: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        del text_tokens, text_lengths
        self.batch_sizes.append(int(features.shape[0]))
        batch = int(features.shape[0])
        component = torch.full(
            (batch, self.config.topology_classes), -12.0,
            device=features.device,
        )
        holes = component.clone()
        component[:, 1] = 12.0
        holes[:, 1] = 12.0
        return {
            "support_logits": 24.0 * features[:, 1:2] - 12.0,
            "sdf": torch.zeros_like(features[:, 0:1]),
            "component_logits": component,
            "hole_logits": holes,
        }


class _FailingModel:
    def __init__(self) -> None:
        self.config = WordmarkPriorConfig(base_channels=8, text_embedding_dim=16)

    def __call__(self, *_args, **_kwargs):
        raise RuntimeError("synthetic inference failure")


class _MalformedModel(_ExactRingModel):
    def __call__(
        self, features: torch.Tensor, text_tokens: torch.Tensor,
        text_lengths: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        output = super().__call__(features, text_tokens, text_lengths)
        output["support_logits"] = output["support_logits"][:1]
        return output


def _ring() -> np.ndarray:
    mask = np.zeros((40, 120), np.uint8)
    cv2.rectangle(mask, (8, 5), (110, 34), 1, -1)
    cv2.rectangle(mask, (25, 12), (92, 27), 0, -1)
    return mask > 0


class WordmarkRuntimeTests(unittest.TestCase):
    def test_environment_override_requires_explicit_evaluation_mode(self) -> None:
        with TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "candidate.pt"
            checkpoint.write_bytes(b"evaluation candidate")
            with patch.dict(os.environ, {
                "VICE_WORDMARK_PRIOR_CHECKPOINT": str(checkpoint),
                "VICE_WORDMARK_PRIOR_EVALUATION": "0",
            }):
                self.assertIsNone(resolve_wordmark_prior_checkpoint())
            with patch.dict(os.environ, {
                "VICE_WORDMARK_PRIOR_CHECKPOINT": str(checkpoint),
                "VICE_WORDMARK_PRIOR_EVALUATION": "1",
            }):
                self.assertEqual(
                    resolve_wordmark_prior_checkpoint(), checkpoint.resolve(),
                )

    def test_promotion_hash_validation_is_cached_until_evidence_changes(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "model.pt"
            checkpoint.write_bytes(b"checkpoint")
            reports = [root / name for name in (
                "training.json", "preflight.json", "short-logo.json",
                "experiment4.json", "experiment4-baseline.json", "full.json",
            )]
            for report in reports:
                report.write_text("{}", "utf-8")
            manifest = root / "promotion.json"
            manifest.write_text(json.dumps({
                "training_report": str(reports[0]),
                "preflight_report": str(reports[1]),
                "short_logo_audit_report": str(reports[2]),
                "experiment4_report": str(reports[3]),
                "experiment4_baseline_report": str(reports[4]),
                "full_tests_report": str(reports[5]),
            }), "utf-8")
            _promotion_evidence_paths_cached.cache_clear()
            _validate_wordmark_prior_promotion_cached.cache_clear()
            with patch(
                "vice_compiler.wordmark_runtime."
                "validate_wordmark_prior_promotion",
            ) as validate:
                first = _promotion_validation_identity(checkpoint, manifest)
                _validate_wordmark_prior_promotion_cached(first)
                _validate_wordmark_prior_promotion_cached(first)
                self.assertEqual(validate.call_count, 1)
                reports[2].write_text('{"changed":true}', "utf-8")
                changed = _promotion_validation_identity(checkpoint, manifest)
                self.assertNotEqual(first, changed)
                _validate_wordmark_prior_promotion_cached(changed)
                self.assertEqual(validate.call_count, 2)

    def test_train_serve_normalization_is_rectangular_and_deterministic(self) -> None:
        config = WordmarkPriorConfig(base_channels=8, text_embedding_dim=16)
        support = _ring()
        request = WordmarkPriorInput(
            observed_ink=support.astype(np.float32),
            recognized_text="Mastercard", certified_support=support,
        )
        first = _prepare(request, config)
        second = _prepare(request, config)
        self.assertIsNotNone(first)
        assert first is not None and second is not None
        self.assertEqual(first.features.shape, (3, 64, 256))
        self.assertEqual(first.tokens.shape, (32,))
        self.assertEqual(first.text_length, 10)
        self.assertTrue(np.array_equal(first.features, second.features))

    def test_invalid_ocr_vocabulary_fails_closed_before_inference(self) -> None:
        support = _ring()
        request = WordmarkPriorInput(
            observed_ink=support.astype(np.float32),
            recognized_text="тэкст", certified_support=support,
        )
        self.assertIsNone(_prepare(request, WordmarkPriorConfig()))

    def test_malformed_support_shape_fails_closed_before_bbox_measurement(self) -> None:
        request = WordmarkPriorInput(
            observed_ink=np.ones(8, np.float32),
            recognized_text="Logo", certified_support=np.ones(8, bool),
        )
        self.assertIsNone(_prepare(request, WordmarkPriorConfig()))

    def test_two_whole_lines_are_inferred_in_one_batch_and_recertified(self) -> None:
        support = _ring()
        model = _ExactRingModel()
        payload = {
            "support_threshold": 0.5,
            "topology_repair_confidence_threshold": 1.01,
            "epoch": 4,
        }
        requests = tuple(
            WordmarkPriorInput(
                observed_ink=support.astype(np.float32),
                recognized_text=text, certified_support=support,
            )
            for text in ("Mastercard", "Spadegaming")
        )
        with patch(
            "vice_compiler.wordmark_runtime.load_wordmark_prior",
            return_value=(model, torch.device("cpu"), payload),
        ):
            proposals = propose_wordmark_masks(requests)
        self.assertEqual(model.batch_sizes, [2])
        self.assertEqual(len(proposals), 2)
        for proposal in proposals:
            self.assertIsNotNone(proposal)
            assert proposal is not None
            self.assertEqual(proposal.predicted_topology, (1, 1))
            self.assertEqual(topology_signature(proposal.support_mask), (1, 1))
            self.assertGreater(proposal.source_iou, 0.90)
            self.assertFalse(proposal.support_mask.flags.writeable)
            np.testing.assert_array_equal(proposal.support_mask, support)

    def test_bounded_halo_can_restore_support_outside_damaged_bbox(self) -> None:
        support = _ring()
        observed = support.astype(np.float32)
        # A connected terminal is visible in the supplied contrast halo but
        # lies outside the damaged certified-support bbox.
        observed[17:23, 111:115] = 1.0
        model = _ExactRingModel()
        payload = {
            "support_threshold": 0.5,
            "topology_repair_confidence_threshold": 1.01,
            "epoch": 4,
        }
        request = WordmarkPriorInput(
            observed_ink=observed, recognized_text="Mastercard",
            certified_support=support,
        )
        with patch(
            "vice_compiler.wordmark_runtime.load_wordmark_prior",
            return_value=(model, torch.device("cpu"), payload),
        ):
            proposal = propose_wordmark_masks((request,))[0]
        self.assertIsNotNone(proposal)
        assert proposal is not None
        self.assertTrue(np.any(proposal.support_mask[17:23, 111:115]))
        self.assertEqual(topology_signature(proposal.support_mask), (1, 1))
        self.assertLessEqual(proposal.source_edit_fraction, 0.55)

    def test_unavailable_default_model_returns_aligned_none_results(self) -> None:
        support = _ring()
        request = WordmarkPriorInput(
            observed_ink=support.astype(np.float32),
            recognized_text="Logo", certified_support=support,
        )
        with patch(
            "vice_compiler.wordmark_runtime.load_wordmark_prior",
            return_value=None,
        ):
            self.assertEqual(propose_wordmark_masks((request, request)), (None, None))

    def test_optional_inference_failure_preserves_aligned_fail_open_results(
        self,
    ) -> None:
        support = _ring()
        request = WordmarkPriorInput(
            observed_ink=support.astype(np.float32),
            recognized_text="Logo", certified_support=support,
        )
        with patch(
            "vice_compiler.wordmark_runtime.load_wordmark_prior",
            return_value=(_FailingModel(), torch.device("cpu"), {}),
        ):
            self.assertEqual(
                propose_wordmark_masks((request, request)), (None, None),
            )

    def test_malformed_model_batch_preserves_aligned_fail_open_results(
        self,
    ) -> None:
        support = _ring()
        request = WordmarkPriorInput(
            observed_ink=support.astype(np.float32),
            recognized_text="Logo", certified_support=support,
        )
        with patch(
            "vice_compiler.wordmark_runtime.load_wordmark_prior",
            return_value=(_MalformedModel(), torch.device("cpu"), {}),
        ):
            self.assertEqual(
                propose_wordmark_masks((request, request)), (None, None),
            )

    def test_single_decode_failure_does_not_discard_healthy_sibling(self) -> None:
        support = _ring()
        request = WordmarkPriorInput(
            observed_ink=support.astype(np.float32),
            recognized_text="Logo", certified_support=support,
        )
        calls = 0

        def fail_first_decode(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("synthetic per-item decode failure")
            return decode_wordmark_support(*args, **kwargs)

        with (
            patch(
                "vice_compiler.wordmark_runtime.load_wordmark_prior",
                return_value=(
                    _ExactRingModel(), torch.device("cpu"), {
                        "support_threshold": 0.5,
                        "topology_repair_confidence_threshold": 1.01,
                    },
                ),
            ),
            patch(
                "vice_compiler.wordmark_runtime.decode_wordmark_support",
                side_effect=fail_first_decode,
            ),
        ):
            proposals = propose_wordmark_masks((request, request))
        self.assertIsNone(proposals[0])
        self.assertIsNotNone(proposals[1])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import cv2
import numpy as np
import torch

from vice_compiler.exact_font_provider import discover_owned_font_catalog
from vice_compiler.wordmark_prior import (
    WORDMARK_CHARACTERS, WordmarkPriorConfig, WordmarkPriorNet,
    checkpoint_payload,
    decode_wordmark_support, topology_signature, wordmark_token_ids,
    wordmark_prior_source_sha256,
)
from vice_compiler.wordmark_prior_data import (
    _rng, _sample_text, render_clean_wordmark,
    topology_importance_target, wordmark_data_recipe,
)
from vice_compiler.train_wordmark_prior import (
    _atomic_torch_save, _ordinal_count_loss, _state_dict_sha256,
    representative_pilot_gate, wordmark_trainer_source_sha256,
)


class WordmarkPriorTests(unittest.TestCase):
    def test_ordinal_count_loss_is_cuda_autocast_safe(self) -> None:
        if not torch.cuda.is_available():
            self.skipTest("CUDA is required for the production AMP regression")
        logits = torch.randn(
            (4, 65), device="cuda", dtype=torch.float32, requires_grad=True,
        )
        targets = torch.tensor((0, 7, 31, 64), device="cuda")
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            loss = _ordinal_count_loss(logits, targets)
        self.assertEqual(loss.dtype, torch.float32)
        self.assertTrue(bool(torch.isfinite(loss)))
        loss.backward()
        self.assertIsNotNone(logits.grad)
        assert logits.grad is not None
        self.assertTrue(bool(torch.all(torch.isfinite(logits.grad))))

    def test_epoch_checkpoint_write_is_atomic_and_loadable(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "best.pt"
            _atomic_torch_save({"epoch": 1, "value": torch.arange(3)}, path)
            self.assertTrue(path.is_file())
            self.assertFalse(path.with_suffix(".pt.tmp").exists())
            payload = torch.load(path, map_location="cpu", weights_only=False)
            self.assertEqual(payload["epoch"], 1)
            self.assertTrue(torch.equal(payload["value"], torch.arange(3)))

    def test_model_state_digest_changes_with_any_weight_change(self) -> None:
        model = WordmarkPriorNet(WordmarkPriorConfig(
            base_channels=8, text_embedding_dim=16,
        ))
        first = _state_dict_sha256(model)
        self.assertEqual(first, _state_dict_sha256(model))
        with torch.no_grad():
            model.support_head.bias.add_(1.0)
        self.assertNotEqual(first, _state_dict_sha256(model))

    def test_text_conditioning_accepts_whole_lowercase_line_without_cells(self) -> None:
        encoded = wordmark_token_ids("Spadegaming", max_characters=32)
        self.assertIsNotNone(encoded)
        assert encoded is not None
        tokens, length = encoded
        self.assertEqual(length, 11)
        self.assertEqual(tokens.shape, (32,))
        self.assertGreater(int(np.sum(tokens > 0)), 0)

    def test_single_glyph_and_two_letter_logos_are_first_class_inputs(self) -> None:
        single = wordmark_token_ids("Q", max_characters=32)
        pair = wordmark_token_ids("HP", max_characters=32)
        self.assertIsNotNone(single)
        self.assertIsNotNone(pair)
        assert single is not None and pair is not None
        self.assertEqual(single[1], 1)
        self.assertEqual(pair[1], 2)

    def test_ordered_whitespace_is_a_real_token_not_silently_dropped(self) -> None:
        encoded = wordmark_token_ids("ACME\t  LAB", max_characters=32)
        self.assertIsNotNone(encoded)
        assert encoded is not None
        tokens, length = encoded
        self.assertEqual(length, len("ACME LAB"))
        self.assertEqual(
            int(tokens[4]), WORDMARK_CHARACTERS.index(" ") + 1,
        )
        joined = wordmark_token_ids("ACMELAB", max_characters=32)
        assert joined is not None
        self.assertFalse(np.array_equal(tokens, joined[0]))

    def test_procedural_factory_reaches_every_serving_character(self) -> None:
        generated = tuple(
            _sample_text(_rng(20260723, index), 32)
            for index in range(4096)
        )
        covered = set().union(*(set(text) for text in generated))
        self.assertEqual(set(WORDMARK_CHARACTERS) - covered, set())
        encoded = tuple(
            wordmark_token_ids(text, max_characters=32) for text in generated
        )
        self.assertTrue(all(row is not None for row in encoded))
        lengths = tuple(row[1] for row in encoded if row is not None)
        self.assertEqual(set(lengths), set(range(1, 33)))
        self.assertEqual(
            wordmark_data_recipe()["schema"],
            "pcdc-wordmark-procedural-data/v9",
        )
        self.assertEqual(wordmark_data_recipe()["text_length"], [1, 32])

    def test_rectangular_network_emits_support_sdf_and_global_topology(self) -> None:
        config = WordmarkPriorConfig(
            base_channels=8, text_embedding_dim=16,
        )
        model = WordmarkPriorNet(config)
        encoded = wordmark_token_ids("Linux", max_characters=32)
        assert encoded is not None
        tokens, length = encoded
        output = model(
            torch.zeros((1, 3, 64, 256), dtype=torch.float32),
            torch.from_numpy(tokens)[None], torch.tensor([length]),
        )
        self.assertEqual(output["support_logits"].shape, (1, 1, 64, 256))
        self.assertEqual(output["sdf"].shape, (1, 1, 64, 256))
        self.assertEqual(output["component_logits"].shape, (1, 65))
        self.assertEqual(output["hole_logits"].shape, (1, 65))
        self.assertEqual(output["component_count_estimate"].shape, (1,))
        self.assertEqual(output["hole_count_estimate"].shape, (1,))
        self.assertEqual(
            output["token_topology_contributions"].shape, (1, 32, 2),
        )
        self.assertTrue(torch.all(
            output["token_topology_contributions"][:, length:] == 0,
        ))

    def test_topology_importance_balances_dots_counters_and_boundaries(self) -> None:
        support = np.zeros((48, 96), bool)
        support[10:39, 8:70] = True
        support[19:30, 28:48] = False
        support[7:9, 80:82] = True
        weight = topology_importance_target(support)
        self.assertEqual(weight.shape, support.shape)
        self.assertTrue(np.all(np.isfinite(weight)))
        self.assertGreater(float(weight[7, 80]), float(weight[24, 12]))
        self.assertGreater(float(weight[24, 35]), float(weight[2, 2]))
        self.assertGreater(float(weight[10, 20]), float(weight[24, 12]))

    def test_representative_pilot_gate_covers_short_and_long_topology(self) -> None:
        common = {
            "samples": 128,
            "decoded_support_iou": 0.92,
            "component_head_accuracy": 0.95,
            "hole_head_accuracy": 0.95,
            "joint_topology_head_accuracy": 0.92,
            "decoded_topology_accuracy": 0.95,
            "decoded_complex_topology_accuracy": 0.90,
        }
        report = {
            "schema": "pcdc-wordmark-prior-training/v1",
            "model_data_contract_sha256": wordmark_prior_source_sha256(),
            "trainer_source_sha256": wordmark_trainer_source_sha256(),
            "data_recipe": {"schema": "pcdc-wordmark-procedural-data/v9"},
            "training_variants": 131_072,
            "held_out_samples_per_split": 4_096,
            "held_out_test": {
                **common,
                "diagnostic_slices": {
                    "length:1": common,
                    "length:2": {**common, "decoded_topology_accuracy": 0.93},
                    "length:17-32": {
                        **common,
                        "decoded_topology_accuracy": 0.86,
                        "component_head_accuracy": 0.82,
                        "hole_head_accuracy": 0.81,
                    },
                },
            },
        }
        self.assertTrue(representative_pilot_gate(report)["passed"])
        report["held_out_test"]["diagnostic_slices"]["length:17-32"][
            "decoded_topology_accuracy"
        ] = 0.84
        self.assertFalse(representative_pilot_gate(report)["passed"])

    def test_text_encoder_preserves_character_order_not_only_multiset(self) -> None:
        torch.manual_seed(17)
        config = WordmarkPriorConfig(base_channels=8, text_embedding_dim=16)
        model = WordmarkPriorNet(config).eval()
        first = wordmark_token_ids("abc", max_characters=32)
        second = wordmark_token_ids("cba", max_characters=32)
        assert first is not None and second is not None
        first_encoded = model.encode_text(
            torch.from_numpy(first[0])[None], torch.tensor([first[1]]),
        )
        second_encoded = model.encode_text(
            torch.from_numpy(second[0])[None], torch.tensor([second[1]]),
        )
        self.assertGreater(
            float(torch.linalg.vector_norm(first_encoded - second_encoded)),
            1.0e-4,
        )

    def test_checkpoint_payload_is_an_immutable_cpu_snapshot(self) -> None:
        model = WordmarkPriorNet(WordmarkPriorConfig(
            base_channels=8, text_embedding_dim=16,
        ))
        payload = checkpoint_payload(
            model, epoch=1, font_manifest_sha256="manifest",
            family_split_sha256="split", support_threshold=0.5,
            selection_key=(1.0,),
        )
        name = "support_head.weight"
        frozen = payload["state_dict"][name].clone()
        with torch.no_grad():
            model.support_head.weight.add_(1.0)
        self.assertEqual(payload["state_dict"][name].device.type, "cpu")
        self.assertTrue(torch.equal(payload["state_dict"][name], frozen))
        self.assertFalse(torch.equal(payload["state_dict"][name], model.state_dict()[name]))

    def test_topology_decoder_selects_matching_probability_level(self) -> None:
        probability = np.full((32, 96), 0.05, np.float32)
        cv2.rectangle(probability, (5, 5), (42, 26), 0.80, -1)
        cv2.rectangle(probability, (15, 11), (30, 20), 0.30, -1)
        support, threshold, matched = decode_wordmark_support(
            probability, expected_topology=(1, 1), preferred_threshold=0.5,
        )
        self.assertTrue(matched)
        self.assertEqual(topology_signature(support), (1, 1))
        self.assertGreaterEqual(threshold, 0.30)

    def test_low_confidence_decode_does_not_chase_expected_topology(self) -> None:
        probability = np.full((32, 96), 0.05, np.float32)
        cv2.rectangle(probability, (5, 5), (42, 26), 0.80, -1)
        cv2.rectangle(probability, (15, 11), (30, 20), 0.30, -1)
        support, threshold, matched = decode_wordmark_support(
            probability, expected_topology=(1, 0), preferred_threshold=0.5,
            allow_repair=False,
        )
        self.assertFalse(matched)
        self.assertEqual(threshold, 0.5)
        self.assertEqual(topology_signature(support), (1, 1))

    def test_topology_decoder_fills_an_extra_micro_hole_within_budget(self) -> None:
        probability = np.full((32, 96), 0.05, np.float32)
        cv2.rectangle(probability, (8, 5), (70, 26), 0.90, -1)
        probability[14:17, 35:38] = 0.05
        raw = probability >= 0.5
        self.assertEqual(topology_signature(raw), (1, 1))
        support, _threshold, matched = decode_wordmark_support(
            probability, expected_topology=(1, 0), preferred_threshold=0.5,
        )
        self.assertTrue(matched)
        self.assertEqual(topology_signature(support), (1, 0))
        self.assertLessEqual(
            int(np.sum(support != raw)), max(16, round(0.03 * np.sum(raw))),
        )

    def test_topology_decoder_carves_a_missing_hole_within_budget(self) -> None:
        probability = np.full((32, 96), 0.05, np.float32)
        cv2.rectangle(probability, (8, 5), (70, 26), 0.90, -1)
        raw = probability >= 0.5
        self.assertEqual(topology_signature(raw), (1, 0))
        support, _threshold, matched = decode_wordmark_support(
            probability, expected_topology=(1, 1), preferred_threshold=0.5,
        )
        self.assertTrue(matched)
        self.assertEqual(topology_signature(support), (1, 1))
        self.assertLessEqual(
            int(np.sum(support != raw)), max(16, round(0.03 * np.sum(raw))),
        )

    def test_topology_decoder_can_recover_many_micro_counters(self) -> None:
        probability = np.full((40, 120), 0.05, np.float32)
        cv2.rectangle(probability, (8, 5), (110, 34), 0.90, -1)
        raw = probability >= 0.5
        support, _threshold, matched = decode_wordmark_support(
            probability, expected_topology=(1, 8), preferred_threshold=0.5,
        )
        self.assertTrue(matched)
        self.assertEqual(topology_signature(support), (1, 8))
        self.assertLessEqual(int(np.sum(support != raw)), 8)

    def test_topology_decoder_bridges_two_large_components(self) -> None:
        probability = np.full((32, 96), 0.05, np.float32)
        cv2.rectangle(probability, (6, 7), (35, 24), 0.90, -1)
        cv2.rectangle(probability, (43, 7), (72, 24), 0.90, -1)
        raw = probability >= 0.5
        self.assertEqual(topology_signature(raw), (2, 0))
        support, _threshold, matched = decode_wordmark_support(
            probability, expected_topology=(1, 0), preferred_threshold=0.5,
        )
        self.assertTrue(matched)
        self.assertEqual(topology_signature(support), (1, 0))
        self.assertLessEqual(
            int(np.sum(support != raw)), max(16, round(0.03 * np.sum(raw))),
        )

    def test_topology_decoder_cuts_an_articulation_pixel(self) -> None:
        probability = np.full((32, 96), 0.05, np.float32)
        cv2.rectangle(probability, (8, 7), (30, 24), 0.90, -1)
        cv2.rectangle(probability, (32, 7), (54, 24), 0.90, -1)
        probability[15, 31] = 0.90
        raw = probability >= 0.5
        self.assertEqual(topology_signature(raw), (1, 0))
        support, _threshold, matched = decode_wordmark_support(
            probability, expected_topology=(2, 0), preferred_threshold=0.5,
        )
        self.assertTrue(matched)
        self.assertEqual(topology_signature(support), (2, 0))
        self.assertLessEqual(int(np.sum(support != raw)), 1)

    def test_topology_decoder_does_not_hide_bridge_behind_probability_shortlist(
        self,
    ) -> None:
        probability = np.full((64, 160), 0.05, np.float32)
        cv2.rectangle(probability, (5, 5), (70, 58), 0.51, -1)
        cv2.rectangle(probability, (72, 5), (137, 58), 0.51, -1)
        probability[31, 71] = 0.99
        raw = probability >= 0.5
        self.assertGreater(int(np.sum(raw)), 512)
        self.assertEqual(topology_signature(raw), (1, 0))
        support, _threshold, matched = decode_wordmark_support(
            probability, expected_topology=(2, 0), preferred_threshold=0.5,
        )
        self.assertTrue(matched)
        self.assertEqual(topology_signature(support), (2, 0))
        self.assertFalse(bool(support[31, 71]))

    def test_topology_decoder_cuts_a_two_pixel_antialiased_bridge(self) -> None:
        probability = np.full((64, 160), 0.05, np.float32)
        cv2.rectangle(probability, (5, 5), (70, 58), 0.51, -1)
        cv2.rectangle(probability, (72, 5), (137, 58), 0.51, -1)
        probability[31:33, 71] = 0.99
        raw = probability >= 0.5
        self.assertEqual(topology_signature(raw), (1, 0))
        support, _threshold, matched = decode_wordmark_support(
            probability, expected_topology=(2, 0), preferred_threshold=0.5,
        )
        self.assertTrue(matched)
        self.assertEqual(topology_signature(support), (2, 0))
        self.assertLessEqual(int(np.sum(raw & ~support)), 5)

    def test_topology_decoder_recovers_a_subthreshold_dot_island(self) -> None:
        probability = np.full((32, 96), 0.05, np.float32)
        cv2.rectangle(probability, (8, 8), (60, 25), 0.90, -1)
        cv2.circle(probability, (72, 11), 1, 0.16, -1)
        raw = probability >= 0.5
        self.assertEqual(topology_signature(raw), (1, 0))
        support, _threshold, matched = decode_wordmark_support(
            probability, expected_topology=(2, 0), preferred_threshold=0.5,
        )
        self.assertTrue(matched)
        self.assertEqual(topology_signature(support), (2, 0))
        self.assertGreater(int(np.sum(support & ~raw)), 0)
        self.assertLessEqual(
            int(np.sum(support != raw)), max(16, round(0.03 * np.sum(raw))),
        )

    def test_clean_wordmark_factory_is_deterministic_and_line_level(self) -> None:
        catalog = discover_owned_font_catalog()
        self.assertTrue(catalog)
        config = WordmarkPriorConfig()
        first = render_clean_wordmark(
            catalog[0][1], "Connected", config, seed=91,
        )
        second = render_clean_wordmark(
            catalog[0][1], "Connected", config, seed=91,
        )
        self.assertTrue(np.array_equal(first[0], second[0]))
        self.assertTrue(np.array_equal(first[1], second[1]))
        self.assertTrue(np.any(first[1]))
        components, holes = topology_signature(first[1])
        self.assertGreaterEqual(components, 1)
        self.assertGreaterEqual(holes, 0)

    def test_clean_coverage_half_level_always_matches_target_support(self) -> None:
        catalog = discover_owned_font_catalog()
        self.assertTrue(catalog)
        config = WordmarkPriorConfig()
        for seed in range(40):
            coverage, support = render_clean_wordmark(
                catalog[seed % len(catalog)][1], "Outline", config, seed=seed,
            )
            self.assertTrue(np.array_equal(coverage >= 0.5, support))


if __name__ == "__main__":
    unittest.main()

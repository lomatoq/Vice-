from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw
import torch

from vice_compiler.conformal import (
    CalibrationExample, audit_conformal_coverage, calibrate_conformal_sets,
    conformal_query_set, runtime_conformal_query_set,
)
from vice_compiler.diagnose_proposal_checkpoint import (
    _bbox_gate_supports,
    _finish as _finish_checkpoint_decomposition,
    _matched as _match_checkpoint_queries,
)
from vice_compiler.evidence_ir import build_reir
from vice_compiler.hard_negative_factory import (
    CandidateRanker, applicable_hard_negative_types,
    counterfactual_feature_pairs,
    counterfactual_risk_regions, generate_hard_negatives,
    pairwise_ranking_loss, render_hard_negative_program,
)
from vice_compiler.experiment9_proposal_calibration import (
    _best_example, _prepare as _prepare_real_locus,
    _real_corpus_capacity,
    _real_calibration_selection_key, _recall_at_k, _target as _real_target,
    _split_rows as _split_real_loci, _typed_reviewed_loci,
)
from vice_compiler.evaluate_proposal_real_loci import (
    _failure_decomposition, _real_gate_rows,
)
from vice_compiler.macro_ir import MacroKind, SceneProgram
from vice_compiler.macro_registry import candidate_from_support
from vice_compiler.proposal_net import (
    HARD_NEGATIVE_TYPES, QUERY_FAMILIES, ProposalNet, ProposalNetConfig, ProposalQuery,
    _gate_text_support_probability, _global_recall_at_k_competitor,
    _same_family_instance_exclusivity_loss, _soft_iou_probability_loss,
    _support_leakage_ratio,
    proposal_net_loss, query_head_prior_score, reir_queries, union_queries,
)
from vice_compiler.proposal_instance_labels import (
    _project_mask, augmented_svg_full_support, augmented_svg_owner_targets,
    svg_owner_templates,
)
from vice_compiler.proposal_real_labels import (
    infer_owned_proposal_family, reviewed_proposal_family,
)
from vice_compiler.train_proposal_net_large import (
    LABEL_CONTRACT_VERSION, TINY_OVERFIT_REQUIRED_FAMILIES,
    V14_REQUIRED_READINESS_GATES,
    PairDataset, _balanced_structure_family_shares,
    _calibration_selection_key,
    _gate_balanced_sample_weight, _label_contract_sha256,
    _filter_supervisable_pairs, _split_group, _stable_bucket,
    _support_preimage_lattice, _svg_families,
    _validate_tiny_overfit_preflight, _validate_v14_readiness,
)


class ProposalNetPhase9Tests(unittest.TestCase):
    _COMPOUND_WORDMARK = """<svg xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 300 100">
      <rect x="2" y="8" width="62" height="72" rx="8"/>
      <g>
        <rect x="90" y="18" width="18" height="28"/>
        <rect x="116" y="17" width="17" height="29"/>
        <rect x="141" y="19" width="16" height="27"/>
        <rect x="165" y="18" width="18" height="28"/>
        <rect x="192" y="17" width="17" height="29"/>
        <rect x="220" y="19" width="16" height="27"/>
        <rect x="248" y="18" width="18" height="28"/>
        <rect x="112" y="62" width="16" height="20"/>
        <rect x="136" y="61" width="15" height="21"/>
        <rect x="159" y="63" width="16" height="19"/>
        <rect x="183" y="62" width="15" height="20"/>
        <rect x="207" y="61" width="16" height="21"/>
      </g>
    </svg>"""

    def test_checkpoint_decomposition_separates_geometry_type_and_rank(self) -> None:
        row = _finish_checkpoint_decomposition({
            "instances": 10,
            "geometry_any_at_32": 8,
            "typed_at_32": 6,
            "typed_at_5": 5,
        })
        self.assertAlmostEqual(row["geometry_loss_fraction"], 0.2)
        self.assertAlmostEqual(row["type_loss_fraction"], 0.2)
        self.assertAlmostEqual(row["rank_loss_fraction"], 0.1)

    def test_checkpoint_bbox_gate_restricts_each_query_to_its_roi(self) -> None:
        supports = np.ones((2, 4, 4), np.float32)
        boxes = np.asarray(((0.0, 0.0, 0.5, 1.0), (0.5, 0.0, 1.0, 1.0)))
        gated = _bbox_gate_supports(supports, boxes)
        self.assertTrue(np.all(gated[0, :, :2] == 1.0))
        self.assertTrue(np.all(gated[0, :, 2:] == 0.0))
        self.assertTrue(np.all(gated[1, :, :2] == 0.0))
        self.assertTrue(np.all(gated[1, :, 2:] == 1.0))

    def test_checkpoint_query_matching_is_one_to_one_and_type_aware(self) -> None:
        probability = np.full((3, len(QUERY_FAMILIES) + 1), 1e-4, np.float64)
        text = QUERY_FAMILIES.index("text_line")
        shape = QUERY_FAMILIES.index("whole_shape")
        probability[0, shape] = 0.99
        probability[1, text] = 0.98
        probability[2, text] = 0.97
        confidence = np.asarray([1.0, 0.9, 0.8], np.float64)
        left = np.asarray([[1.0, 0.0], [1.0, 0.0]], np.float64)
        right = np.asarray([[0.0, 1.0], [0.0, 1.0]], np.float64)
        supports = np.stack((left, left, right))
        target = {
            "family": np.asarray([text, text], np.int64),
            "support": np.stack((left, right)),
        }
        untyped = _match_checkpoint_queries(
            probability, confidence, supports, target, cutoff=3, typed=False,
        )
        typed = _match_checkpoint_queries(
            probability, confidence, supports, target, cutoff=3, typed=True,
        )
        self.assertEqual(len(untyped), 2)
        self.assertEqual(len({query for _iou, query in untyped.values()}), 2)
        self.assertEqual(set(typed), {0, 1})
        self.assertNotEqual(typed[0][1], 0)

    def test_instance_exclusivity_penalizes_collapsed_same_family_masks(self) -> None:
        targets = torch.zeros(2, 4, 4)
        targets[0, 1, 1] = 1.0
        targets[1, 2, 2] = 1.0
        families = torch.tensor([0, 0], dtype=torch.long)
        separated = torch.full((2, 4, 4), -8.0)
        separated[0, 1, 1] = 8.0
        separated[1, 2, 2] = 8.0
        collapsed = separated.clone()
        collapsed[0, 2, 2] = 8.0
        collapsed[1, 1, 1] = 8.0
        self.assertLess(
            _same_family_instance_exclusivity_loss(
                separated, targets, families,
            ),
            _same_family_instance_exclusivity_loss(
                collapsed, targets, families,
            ),
        )
        different = torch.tensor([0, 1], dtype=torch.long)
        self.assertEqual(
            float(_same_family_instance_exclusivity_loss(
                collapsed, targets, different,
            )),
            0.0,
        )

    def test_soft_iou_loss_penalizes_sparse_support_leakage(self) -> None:
        target = torch.zeros(1, 8, 8)
        target[:, 3:5, 3:5] = 1.0
        exact = target.clone()
        leaked = target.clone()
        leaked[:, 2:6, 2:6] = 1.0
        exact_loss = _soft_iou_probability_loss(exact, target)
        leaked_loss = _soft_iou_probability_loss(leaked, target)
        self.assertLess(float(exact_loss), float(leaked_loss))
        self.assertEqual(float(_support_leakage_ratio(exact, target)), 0.0)
        self.assertGreater(float(_support_leakage_ratio(leaked, target)), 0.0)

    def test_text_support_roi_gate_does_not_change_other_families(self) -> None:
        probability = torch.ones(1, 2, 4, 4)
        boxes = torch.tensor([[[0.0, 0.0, 0.5, 1.0], [0.0, 0.0, 0.5, 1.0]]])
        families = torch.tensor([[
            QUERY_FAMILIES.index("text_line"),
            QUERY_FAMILIES.index("whole_shape"),
        ]])
        gated = _gate_text_support_probability(
            probability, boxes, families, padding=0.0,
        )
        self.assertTrue(torch.equal(gated, probability))
        gated = _gate_text_support_probability(
            probability, boxes, families, padding=0.01,
        )
        self.assertEqual(float(gated[0, 0, :, 3].sum()), 0.0)
        self.assertTrue(torch.equal(gated[0, 1], probability[0, 1]))
        vertical = _gate_text_support_probability(
            probability, boxes, families, padding=0.01,
            vertical_only=True,
        )
        self.assertTrue(torch.equal(vertical[0, 0], probability[0, 0]))

    def test_label_contract_has_explicit_source_bound_identity(self) -> None:
        self.assertEqual(
            LABEL_CONTRACT_VERSION,
            "pcdc-explicit-owner-counterfactual-mixed-replay-labels/v4",
        )
        digest = _label_contract_sha256()
        self.assertEqual(len(digest), 64)
        int(digest, 16)

    def test_real_locus_recall_is_global_top_k_and_type_correct(self) -> None:
        sample = {
            "id": "real-text", "semantic_class": "text",
            "family": "text_line",
        }
        wrong = [
            ("text_line", 0.01, 0.95, "ProposalNet", 0.99 - i * 0.01,
             "whole_shape", f"wrong-{i}")
            for i in range(5)
        ]
        correct = (
            "text_line", 0.80, 0.90, "ProposalNet", 0.70, "text_line",
            "correct",
        )
        entries = {"real-text": [*wrong, correct]}
        self.assertEqual(_recall_at_k([sample], entries, 5)["text"], 0.0)
        self.assertEqual(_recall_at_k([sample], entries, 6)["text"], 1.0)

    def test_real_gate_fails_missing_rare_slices_and_small_sample_counts(self) -> None:
        metrics = {
            "overall": 1.0, "text": 1.0, "glyph_group": 1.0,
            "small_shape": 1.0, "layer_knockout": 1.0,
        }
        counts = {
            "text": 15, "small_shape": 10, "layer_knockout": 7,
            "stroke_diagram": 0, "gradient": 0, "codec_detail": 0,
        }
        gates = _real_gate_rows(metrics, counts, overall_count=44)
        self.assertTrue(all(not row["passed"] for row in gates.values()))
        self.assertIn("stroke_diagram", gates)
        self.assertIn("gradient", gates)
        self.assertIn("codec_detail", gates)

    def test_real_failure_decomposition_separates_geometry_type_and_rank(self) -> None:
        samples = [{
            "id": "text", "semantic_class": "text", "family": "text_line",
        }]
        entries = {"text": [
            ("whole_shape", 0.99, 0.80, "ProposalNet", 0.99, "whole_shape"),
            ("text_line", 0.20, 0.75, "ProposalNet", 0.20, "text_line"),
            ("glyph_group", 0.10, 0.70, "ProposalNet", 0.10, "glyph_group"),
            *[
                ("whole_shape", 0.98 - index * 0.05, 0.10,
                 "ProposalNet", 0.98 - index * 0.05, "whole_shape")
                for index in range(5)
            ],
        ]}
        rows = _failure_decomposition(samples, entries)
        self.assertEqual(rows["text"]["geometry_any_recall_at_32"], 1.0)
        self.assertEqual(rows["text"]["typed_recall_at_32"], 1.0)
        self.assertEqual(rows["text"]["typed_recall_at_5"], 0.0)
        self.assertEqual(rows["glyph_group"]["typed_recall_at_32"], 1.0)

    def test_real_finetune_selection_uses_weakest_required_slice(self) -> None:
        balanced = _real_calibration_selection_key({
            "overall": 0.97, "text": 0.99,
            "glyph_group": 0.99,
            "small_shape": 0.98, "layer_knockout": 0.95,
            "stroke_diagram": 0.98, "gradient": 0.95,
            "codec_detail": 0.95,
        })
        high_overall_weak_text = _real_calibration_selection_key({
            "overall": 1.0, "text": 0.90,
            "glyph_group": 1.0,
            "small_shape": 1.0, "layer_knockout": 1.0,
            "stroke_diagram": 1.0, "gradient": 1.0,
            "codec_detail": 1.0,
        })
        self.assertGreater(balanced, high_overall_weak_text)

    def test_real_selection_uses_next_weakest_observed_slice(self) -> None:
        first = _real_calibration_selection_key({
            "overall": 0.90, "text": 0.90, "glyph_group": 0.80,
            "gradient": 0.25,
        })
        second = _real_calibration_selection_key({
            "overall": 0.95, "text": 0.75, "glyph_group": 0.99,
            "gradient": 0.25,
        })
        # Equal weakest gradient margins: the next-weakest observed class wins,
        # not the larger mean/overall score.
        self.assertGreater(first, second)

    def test_real_locus_finetune_matches_highres_lattice_and_glyph_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.png"
            image = Image.new("RGBA", (32, 32), "white")
            ImageDraw.Draw(image).rectangle((10, 12, 20, 16), fill="black")
            image.save(path)
            support = np.zeros((32, 32), bool)
            support[12:17, 10:21] = True
            flat = support.reshape(-1)
            starts = np.flatnonzero(flat & ~np.pad(flat[:-1], (1, 0)))
            ends = np.flatnonzero(flat & ~np.pad(flat[1:], (0, 1))) + 1
            runs = [[int(start), int(end - start)] for start, end in zip(starts, ends)]
            locus = {
                "id": "text-real", "semantic_class": "text",
                "source": {"path": str(path), "category": "unit"},
            }
            review = {
                "support_size": [32, 32], "support_rle": runs,
                "roi_xyxy": [10, 12, 21, 17], "components": 1,
                "holes": 0, "text_line_membership": "yes",
                "layer_relation": "none", "proposal_family": "text_line",
            }
            sample = _prepare_real_locus(
                locus, review, size=128, support_size=64,
            )
            self.assertEqual(sample["support"].shape, (64, 64))
            config = ProposalNetConfig(
                hidden_dim=64, query_count=8, decoder_layers=1,
                attention_heads=8, parameter_dim=12, mask_upsample=2,
            )
            target = _real_target(sample, config, torch.device("cpu"))
            self.assertEqual(target["support"].shape, (2, 64, 64))
            self.assertEqual(
                target["family"].tolist(),
                [QUERY_FAMILIES.index("text_line"),
                 QUERY_FAMILIES.index("glyph_group")],
            )

    def test_sampling_bucket_is_never_an_implicit_proposal_label(self) -> None:
        locus = {
            "id": "filled-arrow", "semantic_class": "stroke_diagram",
            "source": {"path": "arrow.png"},
        }
        review = {"status": "evidence_reviewed", "macro_family": "stroke_diagram"}
        typed, excluded = _typed_reviewed_loci([locus], {locus["id"]: review})
        self.assertFalse(typed)
        self.assertEqual(excluded[0]["reason"], "missing-explicit-proposal-family")
        self.assertIsNone(reviewed_proposal_family(review))

    def test_one_real_logo_expands_to_multiple_typed_query_instances(self) -> None:
        locus = {
            "id": "one-symbol-logo", "semantic_class": "small_shape",
            "source": {
                "path": "logo.png", "source_asset": "owned-logo.svg",
            },
        }
        geometry = {
            "support_size": [8, 8], "support_rle": [[0, 8]],
            "roi_xyxy": [0, 0, 8, 1], "components": 1, "holes": 0,
        }
        review = {
            "status": "evidence_reviewed",
            "proposal_instances": [
                {
                    **geometry, "id": "mark",
                    "proposal_family": "whole_shape",
                },
                {
                    **geometry, "id": "paint",
                    "proposal_family": "appearance_model",
                },
                {
                    **geometry, "id": "repeat",
                    "proposal_family": "symmetry_repeat_group",
                },
            ],
        }
        typed, excluded = _typed_reviewed_loci(
            [locus], {locus["id"]: review},
        )
        self.assertFalse(excluded)
        self.assertEqual(len(typed), 3)
        self.assertEqual(
            {row["proposal_family"] for row in typed},
            {"whole_shape", "appearance_model", "symmetry_repeat_group"},
        )
        self.assertEqual(
            {row["source_locus_id"] for row in typed}, {"one-symbol-logo"},
        )
        splits = _split_real_loci(typed)
        self.assertEqual(sum(bool(rows) for rows in splits.values()), 1)

    def test_real_relation_contract_supervises_only_observable_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "repeat.png"
            Image.new("RGBA", (8, 8), "white").save(path)
            locus = {
                "id": "repeat-real", "semantic_class": "small_shape",
                "source": {"path": str(path), "category": "unit"},
            }
            review = {
                "support_size": [8, 8], "support_rle": [[0, 8]],
                "roi_xyxy": [0, 0, 8, 1], "components": 1, "holes": 0,
                "proposal_family": "symmetry_repeat_group",
                "relation_contract": {
                    "schema": "query-relations/v1",
                    "family": "symmetry_repeat_group",
                    "positive": ["same_group", "repeat"],
                    "observable": ["same_group", "repeat", "mirror"],
                },
            }
            sample = _prepare_real_locus(locus, review)
            self.assertEqual(
                sample["relations"].tolist(),
                [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            )
            self.assertEqual(
                sample["relation_mask"].tolist(),
                [1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            )

    def test_owned_generator_provenance_retypes_filled_diagram_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            family = root / "arrow"
            family.mkdir()
            svg = family / "fixture.svg"
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', "utf-8")
            locus = {
                "semantic_class": "stroke_diagram",
                "source": {"source_asset": str(svg)},
            }
            review = {"status": "ground_truth_derived"}
            proposal_family, provenance = infer_owned_proposal_family(locus, review)
            self.assertEqual(proposal_family, "whole_shape")
            self.assertIn("arrow", provenance or "")

    def test_real_locus_split_keeps_source_asset_family_in_one_partition(self) -> None:
        loci = []
        for semantic_class in ("text", "small_shape"):
            for asset in range(12):
                for variant in range(2):
                    loci.append({
                        "id": f"{semantic_class}-{asset}-{variant}",
                        "semantic_class": semantic_class,
                        "source": {"source_asset": f"asset-{semantic_class}-{asset}"},
                    })
        splits = _split_real_loci(loci)
        owners = {}
        for split, rows in splits.items():
            for source in {row["source"]["source_asset"] for row in rows}:
                self.assertNotIn(source, owners)
                owners[source] = split
        self.assertEqual(set(splits), {"train", "calibration", "test"})
        self.assertTrue(all(splits.values()))

    def test_real_finetune_preflight_fails_before_training_on_missing_families(self) -> None:
        splits = {
            "train": [{"proposal_family": "text_line"}] * 120,
            "calibration": [{"proposal_family": "text_line"}] * 100,
            "test": [{"proposal_family": "text_line"}] * 100,
        }
        capacity = _real_corpus_capacity(splits)
        self.assertFalse(capacity["passed"])
        self.assertTrue(capacity["calibration_gates"]["text_line"]["passed"])
        self.assertTrue(capacity["calibration_gates"]["glyph_group"]["passed"])
        self.assertFalse(capacity["calibration_gates"]["stroke_network"]["passed"])

    def test_split_groups_prevent_font_library_and_theme_leakage(self) -> None:
        calibri_a = {
            "source": "synthetic-text",
            "source_id": "text-shape:calibri:first-word:a1",
        }
        calibri_b = {
            "source": "synthetic-text",
            "source_id": "text-shape:calibri:other-word:b2",
        }
        self.assertEqual(_split_group(calibri_a), _split_group(calibri_b))
        self.assertEqual(
            _stable_bucket(_split_group(calibri_a)),
            _stable_bucket(_split_group(calibri_b)),
        )
        icon_a = {
            "source": "iconify", "collection": "mdi", "source_id": "mdi:a",
        }
        icon_b = {
            "source": "iconify", "collection": "mdi", "source_id": "mdi:b",
        }
        self.assertEqual(_split_group(icon_a), _split_group(icon_b))
        local_light = {"source": "local", "source_id": "local:light:storm"}
        local_dark = {"source": "local", "source_id": "local:dark:storm"}
        self.assertEqual(_split_group(local_light), _split_group(local_dark))
        open_text = {
            "source": "synthetic-open-text", "source_id": "open-text:a",
            "font_family": "Atkinson", "font_sha256": "a" * 64,
            "owner_contract": {
                "schema": "explicit-svg-groups/v1", "owner_ids": ["row-0"],
            },
        }
        self.assertEqual(_split_group(open_text), "font-family:Atkinson")

    def test_clean_svg_owner_factory_separates_mark_and_text_rows(self) -> None:
        templates = svg_owner_templates(self._COMPOUND_WORDMARK)
        self.assertEqual(len(templates.text_masks), 2)
        self.assertEqual(len(templates.mark_masks), 1)
        self.assertFalse(templates.full_mask.flags.writeable)
        self.assertFalse(any(mask.flags.writeable for mask in (
            *templates.text_masks, *templates.mark_masks,
        )))
        text_union = np.logical_or.reduce(templates.text_masks)
        self.assertFalse(np.any(text_union & templates.mark_masks[0]))
        self.assertTrue(np.array_equal(
            text_union | templates.mark_masks[0], templates.full_mask,
        ))

    def test_compound_svg_labels_follow_recorded_pair_augmentation(self) -> None:
        templates = svg_owner_templates(self._COMPOUND_WORDMARK)
        row = {
            "id": "compound", "source_id": "local:compound",
            "source": "local", "collection": "local-train-corpus",
            "size": 128,
            "augmentation": {
                "scale": 0.78, "shift_x": 2, "shift_y": -1,
                "rotate_degrees": 2.0,
            },
        }
        observed = _project_mask(
            templates.full_mask, size=128, scale=0.78, shift_x=2,
            shift_y=-1, rotate_degrees=2.0,
        )
        targets, alignment_iou = augmented_svg_owner_targets(
            templates, row, observed,
        )
        self.assertAlmostEqual(alignment_iou, 1.0)
        self.assertEqual(
            [family for family, _mask in targets],
            ["text_line", "text_line", "glyph_group", "whole_shape"],
        )

    def test_clean_full_support_is_target_not_degraded_raster_support(self) -> None:
        templates = svg_owner_templates(self._COMPOUND_WORDMARK)
        row = {
            "size": 128,
            "augmentation": {
                "scale": 0.78, "shift_x": 2, "shift_y": -1,
                "rotate_degrees": 0.0,
            },
        }
        exact = _project_mask(
            templates.full_mask, size=128, scale=0.78, shift_x=2,
            shift_y=-1, rotate_degrees=0.0,
        )
        degraded = exact.copy()
        degraded[:, 48:55] = False
        clean, alignment_iou = augmented_svg_full_support(
            self._COMPOUND_WORDMARK, row, degraded,
        )
        self.assertGreater(alignment_iou, 0.80)
        self.assertTrue(np.any(clean[:, 48:55]))
        self.assertGreater(int(clean.sum()), int(degraded.sum()))

    def test_pair_dataset_uses_owner_instances_not_full_scene_text_masks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "vectors").mkdir()
            (root / "images").mkdir()
            (root / "vectors" / "compound.svg").write_text(
                self._COMPOUND_WORDMARK, "utf-8",
            )
            templates = svg_owner_templates(self._COMPOUND_WORDMARK)
            support = _project_mask(
                templates.full_mask, size=128, scale=0.78, shift_x=2,
                shift_y=-1, rotate_degrees=0.0,
            )
            rgba = np.full((128, 128, 4), 255, np.uint8)
            rgba[support, :3] = 0
            Image.fromarray(rgba, "RGBA").save(root / "images" / "compound.png")
            row = {
                "id": "compound", "source_id": "local:compound",
                "source": "local", "collection": "local-train-corpus",
                "input_png": "images/compound.png",
                "target_svg": "vectors/compound.svg", "size": 128,
                "augmentation": {
                    "scale": 0.78, "background": "white", "shift_x": 2,
                    "shift_y": -1, "rotate_degrees": 0.0,
                    "blur_radius": 0, "noise_sigma": 0,
                    "jpeg_quality": None,
                },
            }
            families = {"compound": _svg_families(row, root)}
            sample = PairDataset((row,), root, families)[0]
            names = [QUERY_FAMILIES[index] for index in sample["family"]]
            self.assertEqual(names.count("text_line"), 2)
            self.assertEqual(names.count("glyph_group"), 1)
            self.assertEqual(names.count("whole_shape"), 1)
            self.assertEqual(names.count("risk_hard_negative"), 1)
            risk_index = names.index("risk_hard_negative")
            self.assertIn(
                int(sample["hard_negative"][risk_index]),
                range(len(HARD_NEGATIVE_TYPES)),
            )
            text_supports = sample["support"][
                np.asarray(names) == "text_line"
            ]
            self.assertEqual(len(text_supports), 2)
            self.assertFalse(np.array_equal(text_supports[0], text_supports[1]))

    def test_blank_raster_pair_is_excluded_instead_of_teaching_hallucination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            visible = np.full((32, 32, 4), 255, np.uint8)
            visible[8:24, 10:22, :3] = 0
            blank = np.full((32, 32, 4), 255, np.uint8)
            Image.fromarray(visible, "RGBA").save(root / "visible.png")
            Image.fromarray(blank, "RGBA").save(root / "blank.png")
            (root / "target.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 16">'
                '<rect width="12" height="16"/></svg>', "utf-8",
            )
            shared = {
                "target_svg": "target.svg", "size": 32,
                "augmentation": {
                    "scale": 0.5, "shift_x": 0, "shift_y": 0,
                    "rotate_degrees": 0,
                },
            }
            rows = [
                {**shared, "id": "visible", "input_png": "visible.png"},
                {**shared, "id": "blank", "input_png": "blank.png"},
            ]
            accepted, rejected = _filter_supervisable_pairs(rows, root)
            self.assertEqual([row["id"] for row in accepted], ["visible"])
            self.assertEqual(rejected, ({
                "id": "blank", "reason": "unobservable-raster",
            },))

    def test_xml_valid_empty_svg_is_excluded_before_training(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rgba = np.full((32, 32, 4), 255, np.uint8)
            rgba[8:24, 10:22, :3] = 0
            Image.fromarray(rgba, "RGBA").save(root / "visible.png")
            (root / "empty.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 12 16"><path fill="none" '
                'd="M0 0h12v16H0z"/></svg>', "utf-8",
            )
            row = {
                "id": "empty-render", "input_png": "visible.png",
                "target_svg": "empty.svg", "size": 32,
                "augmentation": {
                    "scale": 0.5, "shift_x": 0, "shift_y": 0,
                    "rotate_degrees": 0,
                },
            }
            accepted, rejected = _filter_supervisable_pairs((row,), root)
            self.assertFalse(accepted)
            self.assertEqual(rejected, ({
                "id": "empty-render",
                "reason": "invalid-clean-render-target",
                "error": "ValueError",
            },))

    def test_unaligned_compound_owner_pair_is_excluded_not_full_scene_labelled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "vectors").mkdir()
            (root / "images").mkdir()
            (root / "vectors" / "compound.svg").write_text(
                self._COMPOUND_WORDMARK, "utf-8",
            )
            rgba = np.full((128, 128, 4), 255, np.uint8)
            rgba[105:125, 2:18, :3] = 0
            Image.fromarray(rgba, "RGBA").save(root / "images" / "wrong.png")
            row = {
                "id": "wrong-owner", "source_id": "local:wrong-owner",
                "source": "local", "collection": "local-train-corpus",
                "input_png": "images/wrong.png",
                "target_svg": "vectors/compound.svg", "size": 128,
                "augmentation": {
                    "scale": 0.78, "shift_x": 0, "shift_y": 0,
                    "rotate_degrees": 0,
                },
            }
            accepted, rejected = _filter_supervisable_pairs((row,), root)
            self.assertFalse(accepted)
            self.assertIn(
                rejected[0]["reason"], {
                    # The global aligned-target proof may reject the row before
                    # the more specific owner proof.  Either reason preserves
                    # the invariant under test: a misregistered compound asset
                    # never becomes a full-scene training label.
                    "target-alignment-below-proof-floor",
                    "owner-alignment-below-proof-floor",
                },
            )
            self.assertIn("alignment_iou", rejected[0])

    def test_training_sampler_oversamples_fixed_gate_slices_only(self) -> None:
        base = {"id": "base", "source": "icons", "augmentation": {}}
        self.assertEqual(
            _gate_balanced_sample_weight(base, ("whole_shape",)), 1.0,
        )
        text = {**base, "id": "text", "source": "synthetic-text"}
        self.assertEqual(
            _gate_balanced_sample_weight(
                text, ("text_line", "glyph_group"),
            ), 1.65,
        )
        small_id = next(
            f"small-{index}" for index in range(1000)
            if hashlib.sha256(f"small-{index}".encode()).digest()[0] < 96
        )
        small = {
            **base, "id": small_id, "source": "synthetic-geometry",
        }
        self.assertEqual(
            _gate_balanced_sample_weight(small, ("whole_shape",)), 3.0,
        )
        degraded_layer = {
            **base, "id": "layer", "augmentation": {"jpeg_quality": 30},
        }
        self.assertAlmostEqual(
            _gate_balanced_sample_weight(
                degraded_layer, ("whole_shape", "layer_relation"),
            ), 1.8,
        )
        self.assertEqual(
            _gate_balanced_sample_weight(
                {**base, "id": "stroke"},
                ("whole_shape", "stroke_network"),
            ), 48.0,
        )
        self.assertEqual(
            _gate_balanced_sample_weight(
                {**base, "id": "repeat"},
                ("whole_shape", "symmetry_repeat_group"),
            ), 12.0,
        )
        self.assertEqual(
            _gate_balanced_sample_weight(
                {**base, "id": "appearance"},
                ("whole_shape", "appearance_model"),
            ), 4.0,
        )
        # The explicitly balanced structural supplement must not inherit the
        # scarcity multipliers that are only justified for legacy rows.
        structure = {
            **base, "id": "balanced-structure",
            "source": "synthetic-structure-v2",
        }
        for family in (
            "stroke_network", "appearance_model", "layer_relation",
            "symmetry_repeat_group",
        ):
            self.assertEqual(
                _gate_balanced_sample_weight(
                    structure, ("whole_shape", family),
                ), 1.0,
            )
        self.assertAlmostEqual(
            _gate_balanced_sample_weight(
                {**structure, "augmentation": {"jpeg_quality": 64}},
                ("whole_shape", "stroke_network"),
            ), 1.2,
        )

    def test_balanced_structure_preflight_rejects_hidden_family_skew(self) -> None:
        typed = (
            "stroke_network", "appearance_model", "layer_relation",
            "symmetry_repeat_group",
        )
        rows = [
            {"id": family, "source": "synthetic-structure-v2"}
            for family in typed
        ]
        families = {family: (family,) for family in typed}
        shares = _balanced_structure_family_shares(
            rows, np.ones(len(rows), np.float64), families,
        )
        self.assertEqual(set(shares), set(typed))
        self.assertTrue(all(abs(value - 0.25) < 1e-12 for value in shares.values()))
        skewed = _balanced_structure_family_shares(
            rows, np.asarray((48.0, 4.0, 1.5, 12.0)), families,
        )
        self.assertGreater(skewed["stroke_network"], 0.70)

    def test_checkpoint_selection_uses_weakest_calibration_gate_not_train_loss(self) -> None:
        def metrics(overrides: dict[str, float]) -> dict:
            values = {
                "overall": 0.97, "text_line": 0.99, "glyph_group": 0.99,
                "small_shape": 0.98, "layer_relation": 0.95,
                "stroke_network": 0.98, "appearance_model": 0.95,
                "symmetry_repeat_group": 0.95,
                "risk_hard_negative": 0.95,
            }
            values.update(overrides)
            return {
                family: {
                    "neural_only_recall_at_5_iou50": recall,
                    "mean_best_soft_iou_at_5": 0.80,
                }
                for family, recall in values.items()
            }

        balanced = _calibration_selection_key(metrics({}))
        high_overall_weak_text = _calibration_selection_key(metrics({
            "overall": 0.995, "text_line": 0.95,
        }))
        self.assertGreater(balanced, high_overall_weak_text)

    def test_large_training_refuses_failed_or_stale_tiny_overfit_preflight(self) -> None:
        from vice_compiler.build_identity import evaluation_source_sha256

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "candidate.pt"
            checkpoint.write_bytes(b"model")
            cache = root / "filter.json"
            cache.write_text("{}", "utf-8")
            config = ProposalNetConfig(
                text_bbox_gate_padding=0.04,
                text_bbox_gate_vertical_only=True,
            )
            report = {
                "schema": "pcdc-proposal-tiny-overfit-preflight/v1",
                "split": "train-only", "checkpoint_written": False,
                "passed": True,
                "evaluation_source_sha256": evaluation_source_sha256(
                    "vice_compiler/preflight_proposal_overfit.py",
                ),
                "checkpoint_sha256": hashlib.sha256(b"model").hexdigest(),
                "filter_cache_sha256": hashlib.sha256(b"{}").hexdigest(),
                "label_contract_sha256": _label_contract_sha256(),
                "pair_root": str(root.resolve()),
                "text_bbox_gate_padding": 0.04,
                "text_bbox_gate_vertical_only": True,
                "probe_model_config": asdict(config),
                "minimum_text_line_recall_at_5": 0.99,
                "best_text_line_recall_at_5": 1.0,
                "owner_count_rows": {"2": 16, "3": 16},
                "required_overfit_families": list(
                    TINY_OVERFIT_REQUIRED_FAMILIES
                ),
                "minimum_family_instances": 16,
                "family_instance_counts": {
                    family: 16 for family in TINY_OVERFIT_REQUIRED_FAMILIES
                },
                "minimum_family_recall_at_5": 0.95,
                "best_minimum_required_recall_at_5": 1.0,
                "best_recall_at_5_by_family": {
                    family: 1.0 for family in TINY_OVERFIT_REQUIRED_FAMILIES
                },
                "best_overall_recall_at_5": 1.0,
            }
            path = root / "preflight.json"
            path.write_text(json.dumps(report), "utf-8")
            accepted = _validate_tiny_overfit_preflight(
                path, config=config, checkpoint=checkpoint,
                pair_root=root, filter_cache=cache,
            )
            self.assertTrue(accepted["passed"])
            report["best_recall_at_5_by_family"]["stroke_network"] = 0.94
            path.write_text(json.dumps(report), "utf-8")
            with self.assertRaisesRegex(RuntimeError, "all_head_recall_gate"):
                _validate_tiny_overfit_preflight(
                    path, config=config, checkpoint=checkpoint,
                    pair_root=root, filter_cache=cache,
                )
            report["best_recall_at_5_by_family"]["stroke_network"] = 1.0
            report["passed"] = False
            path.write_text(json.dumps(report), "utf-8")
            with self.assertRaisesRegex(RuntimeError, "stale, or failed"):
                _validate_tiny_overfit_preflight(
                    path, config=config, checkpoint=checkpoint,
                    pair_root=root, filter_cache=cache,
                )

    def test_large_training_requires_one_hash_bound_all_gate_verdict(self) -> None:
        from vice_compiler.build_identity import (
            compiler_source_sha256, evaluation_source_sha256,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "candidate.pt"
            checkpoint.write_bytes(b"model")
            cache = root / "filter.json"
            cache.write_text("{}", "utf-8")
            config = ProposalNetConfig(
                mask_upsample=2, spatial_positioning=True,
                text_bbox_gate_padding=0.04,
                text_bbox_gate_vertical_only=True,
            )
            report = {
                "schema": "pcdc-v14-training-readiness/v1",
                "status": "TRAIN", "training_authorized": True,
                "compiler_source_sha256": compiler_source_sha256(),
                "evaluation_source_sha256": evaluation_source_sha256(
                    "vice_compiler/pre_v14_readiness.py",
                ),
                "label_contract_version": LABEL_CONTRACT_VERSION,
                "label_contract_sha256": _label_contract_sha256(),
                "pair_root": str(root.resolve()),
                "corpus_data_contract_sha256": "corpus-contract",
                "filter_cache_sha256": hashlib.sha256(b"{}").hexdigest(),
                "initialization_checkpoint_sha256": hashlib.sha256(
                    b"model"
                ).hexdigest(),
                "proposal_config": asdict(config),
                "required_gates": {
                    name: True for name in V14_REQUIRED_READINESS_GATES
                },
            }
            path = root / "readiness.json"
            path.write_text(json.dumps(report), "utf-8")
            accepted = _validate_v14_readiness(
                path, config=config, checkpoint=checkpoint,
                pair_root=root, filter_cache=cache,
                corpus_data_contract_sha256="corpus-contract",
            )
            self.assertTrue(accepted["training_authorized"])
            report["required_gates"]["experiment4_textline"] = False
            path.write_text(json.dumps(report), "utf-8")
            with self.assertRaisesRegex(RuntimeError, "NO-TRAIN"):
                _validate_v14_readiness(
                    path, config=config, checkpoint=checkpoint,
                    pair_root=root, filter_cache=cache,
                    corpus_data_contract_sha256="corpus-contract",
                )
            report["required_gates"] = {
                name: True for name in V14_REQUIRED_READINESS_GATES
                if name != "canonical_plan_traceability"
            }
            path.write_text(json.dumps(report), "utf-8")
            with self.assertRaisesRegex(RuntimeError, "NO-TRAIN"):
                _validate_v14_readiness(
                    path, config=config, checkpoint=checkpoint,
                    pair_root=root, filter_cache=cache,
                    corpus_data_contract_sha256="corpus-contract",
                )

    def test_query_network_outputs_all_contract_fields_and_trains(self) -> None:
        torch.manual_seed(7)
        config = ProposalNetConfig(
            hidden_dim=64, query_count=8, decoder_layers=1,
            attention_heads=8, parameter_dim=12,
        )
        model = ProposalNet(config)
        image = torch.rand(2, 4, 64, 64)
        output = model(image)
        self.assertEqual(output["family_logits"].shape, (2, 8, 9))
        self.assertEqual(output["support_logits"].shape, (2, 8, 16, 16))
        target = []
        for family in (0, 2):
            support = torch.zeros(1, 16, 16)
            support[:, 4:12, 3:13] = 1.0
            target.append({
                "family": torch.tensor([family], dtype=torch.long),
                "bbox": torch.tensor([[3 / 16, 4 / 16, 13 / 16, 12 / 16]]),
                "support": support,
                "parameters": torch.zeros(1, 12),
                "parameter_mask": torch.ones(1, 12),
                "topology": torch.tensor([[1, 0]], dtype=torch.long),
                "relations": torch.zeros(1, 8),
            })
        losses = proposal_net_loss(output, target)
        self.assertIn("global_top5_rank", losses)
        self.assertTrue(torch.isfinite(losses["global_top5_rank"]))
        self.assertTrue(torch.isfinite(losses["total"]))
        self.assertGreaterEqual(float(losses["total"].detach()), 0.0)
        losses["total"].backward()
        self.assertTrue(any(
            parameter.grad is not None and torch.isfinite(parameter.grad).all()
            for parameter in model.parameters()
        ))
        queries = model.infer(image[:1], confidence_floor=0.0)[0]
        self.assertTrue(queries)
        for query in queries:
            query.validate()
            self.assertEqual(len(query.parameters), 12)
            self.assertEqual(len(query.covariance), 12)
        batched = model.infer(image, confidence_floor=0.0)
        for batch_index in range(2):
            single = model.infer(
                image[batch_index:batch_index + 1], confidence_floor=0.0,
            )[0]
            self.assertEqual(
                [row.id for row in batched[batch_index]],
                [row.id for row in single],
            )

    def test_relation_loss_does_not_turn_unknown_tokens_into_negatives(self) -> None:
        torch.manual_seed(19)
        config = ProposalNetConfig(
            hidden_dim=32, query_count=4, decoder_layers=1,
            attention_heads=8, parameter_dim=4,
        )
        output = ProposalNet(config)(torch.rand(1, 4, 32, 32))
        support = torch.zeros(1, 8, 8)
        support[:, 2:6, 2:6] = 1.0
        target = {
            "family": torch.tensor([QUERY_FAMILIES.index("whole_shape")]),
            "bbox": torch.tensor([[0.25, 0.25, 0.75, 0.75]]),
            "support": support,
            "parameters": torch.zeros(1, 4),
            "parameter_mask": torch.ones(1, 4),
            "topology": torch.tensor([[1, 0]]),
            "relations": torch.ones(1, 8),
            "relation_mask": torch.zeros(1, 8),
            "hard_negative": torch.tensor([len(HARD_NEGATIVE_TYPES)]),
        }
        losses = proposal_net_loss(output, [target])
        self.assertEqual(float(losses["relation_affinity"]), 0.0)
        target["relation_mask"][0, 0] = 1.0
        observed = proposal_net_loss(output, [target])
        self.assertGreater(float(observed["relation_affinity"]), 0.0)

    def test_global_top5_competitor_accounts_for_all_positive_slots(self) -> None:
        negatives = torch.tensor([0.90, 0.80, 0.70, 0.60, 0.50, 0.40])
        self.assertAlmostEqual(float(_global_recall_at_k_competitor(
            negatives, positive_count=1, k=5,
        )), 0.50)
        self.assertAlmostEqual(float(_global_recall_at_k_competitor(
            negatives, positive_count=2, k=5,
        )), 0.60)
        self.assertAlmostEqual(float(_global_recall_at_k_competitor(
            negatives, positive_count=5, k=5,
        )), 0.90)
        self.assertAlmostEqual(float(_global_recall_at_k_competitor(
            negatives, positive_count=7, k=5,
        )), 0.90)

    def test_high_resolution_mask_head_uses_stride_two_lateral_features(self) -> None:
        config = ProposalNetConfig(
            hidden_dim=64, query_count=8, decoder_layers=1,
            attention_heads=8, parameter_dim=12, mask_upsample=2,
        )
        output = ProposalNet(config)(torch.rand(1, 4, 64, 64))
        self.assertEqual(output["support_logits"].shape, (1, 8, 32, 32))

    def test_spatial_positioning_exposes_absolute_2d_identity(self) -> None:
        config = ProposalNetConfig(
            hidden_dim=64, query_count=8, decoder_layers=1,
            attention_heads=8, parameter_dim=12, mask_upsample=2,
            spatial_positioning=True,
        )
        model = ProposalNet(config)
        reference = torch.zeros(1, 64, 5, 7)
        position = model._position_features(reference)
        self.assertEqual(position.shape, (1, 4, 5, 7))
        self.assertAlmostEqual(float(position[0, 0, 0, 0]), -1.0)
        self.assertAlmostEqual(float(position[0, 0, 0, -1]), 1.0)
        self.assertAlmostEqual(float(position[0, 1, 0, 0]), -1.0)
        self.assertAlmostEqual(float(position[0, 1, -1, 0]), 1.0)
        output = model(torch.rand(1, 4, 64, 64))
        self.assertEqual(output["support_logits"].shape, (1, 8, 32, 32))
        output["support_logits"].mean().backward()
        self.assertIsNotNone(model.position_projection.weight.grad)

    def test_support_preimage_lattice_never_erases_thin_real_support(self) -> None:
        support = np.zeros((128, 128), bool)
        support[63, 63] = True
        projected = _support_preimage_lattice(support, 32)
        self.assertEqual(projected.shape, (32, 32))
        self.assertEqual(int(projected.sum()), 1)

    def test_classical_geometry_and_neural_queries_form_one_bounded_union(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shape.png"
            image = Image.new("RGB", (96, 64), "white")
            ImageDraw.Draw(image).ellipse((18, 10, 62, 54), fill="black")
            image.save(path)
            reir = build_reir(path)
            classical = reir_queries(reir, max_queries=32)
            self.assertTrue(classical)
            soft = np.zeros((16, 24), np.float32)
            soft.setflags(write=False)
            neural = ProposalQuery(
                id="neural-test", family="whole_shape",
                roi_xyxy=(0.1, 0.1, 0.7, 0.9), soft_support=soft,
                parameters=(0.0, 0.0), covariance=(1.0, 1.0),
                confidence=0.95, relation_tokens=(), topology_code=(1, 0),
                hard_negative_class=None,
                provenance=("unit-neural-query", "must-pass-certificates"),
            )
            merged = union_queries(classical, (neural,), max_per_family=4)
            self.assertLessEqual(
                sum(row.family == "whole_shape" for row in merged), 4,
            )
            self.assertIn("neural-test", {row.id for row in merged})

    def test_split_conformal_sets_hit_class_coverage_and_expand_uncertainty(self) -> None:
        examples = []
        for family in ("text_line", "whole_shape"):
            for index in range(30):
                examples.append(CalibrationExample(
                    family=family,
                    type_confidence=0.70 + 0.01 * (index % 20),
                    support_iou=0.75 + 0.008 * (index % 20),
                    source_group=f"asset-{index}",
                ))
        calibration = calibrate_conformal_sets(
            examples, target_coverage=0.99,
        )
        coverage = audit_conformal_coverage(examples, calibration)
        self.assertTrue(all(value >= 0.99 for value in coverage.values()))
        rows = []
        for index, confidence in enumerate((0.95, 0.70, 0.40, 0.20)):
            support = np.zeros((8, 8), np.float32)
            support.setflags(write=False)
            rows.append(ProposalQuery(
                id=f"q{index}", family="whole_shape",
                roi_xyxy=(0.0, 0.0, 1.0, 1.0), soft_support=support,
                parameters=(0.0,), covariance=(1.0,), confidence=confidence,
                relation_tokens=(), topology_code=(1, 0),
                hard_negative_class=None, provenance=("unit",),
            ))
        selected = conformal_query_set(rows, calibration, maximum_per_family=4)
        self.assertGreaterEqual(len(selected), 2)
        self.assertEqual(selected[0].id, "q0")

    def test_conformal_runtime_prefix_is_the_calibrated_support_rank_rule(self) -> None:
        examples = [
            CalibrationExample(
                family="whole_shape", type_confidence=0.9,
                support_iou=0.8, source_group=f"asset-{index}",
                admission_rank=(5 if index >= 198 else 1),
                candidate_count=10,
            )
            for index in range(200)
        ]
        calibration = calibrate_conformal_sets(
            examples, target_coverage=0.99, minimum_class_examples=100,
        )
        threshold = calibration.by_family()["whole_shape"].threshold
        self.assertAlmostEqual(threshold, 0.4)
        rows = []
        for index in range(10):
            support = np.zeros((8, 8), np.float32)
            support.setflags(write=False)
            rows.append(ProposalQuery(
                id=f"rank-{index + 1}", family="whole_shape",
                roi_xyxy=(0.0, 0.0, 1.0, 1.0), soft_support=support,
                parameters=(0.0,), covariance=(1.0,),
                confidence=1.0 - index / 20.0, relation_tokens=(),
                topology_code=(1, 0), hard_negative_class=None,
                provenance=("unit",),
            ))
        selected = conformal_query_set(
            rows, calibration, maximum_per_family=10,
        )
        self.assertEqual(
            [row.id for row in selected],
            [f"rank-{index}" for index in range(1, 6)],
        )

    def test_real_conformal_rank_never_uses_target_iou_as_tie_break(self) -> None:
        sample = {
            "family": "whole_shape", "source_group": "asset-1",
        }
        entries = [
            ("whole_shape", 0.8, 0.10, "ProposalNet", 0.8,
             "whole_shape", "a-wrong-first"),
            ("whole_shape", 0.8, 0.90, "ProposalNet", 0.8,
             "whole_shape", "z-correct-second"),
        ]
        example = _best_example(sample, entries)
        self.assertEqual(example.admission_rank, 2)
        self.assertEqual(example.candidate_count, 2)

    def test_runtime_conformal_transaction_includes_global_quality_cap(self) -> None:
        examples = [
            CalibrationExample(
                family=family, type_confidence=0.9, support_iou=0.8,
                source_group=f"{family}-{index}", admission_rank=3,
                candidate_count=4,
            )
            for family in ("whole_shape", "text_line")
            for index in range(200)
        ]
        calibration = calibrate_conformal_sets(
            examples, target_coverage=0.99, minimum_class_examples=100,
        )
        rows = []
        for family in ("whole_shape", "text_line"):
            for index in range(4):
                support = np.zeros((8, 8), np.float32)
                support.setflags(write=False)
                rows.append(ProposalQuery(
                    id=f"{family}-{index}", family=family,
                    roi_xyxy=(0.0, 0.0, 1.0, 1.0), soft_support=support,
                    parameters=(0.0,), covariance=(1.0,),
                    confidence=0.99 - 0.01 * index,
                    relation_tokens=(), topology_code=(1, 0),
                    hard_negative_class=None, provenance=("unit",),
                ))
        admitted = runtime_conformal_query_set(
            rows[:4], rows[4:], calibration, maximum_queries=3,
        )
        self.assertEqual(len(admitted), 3)
        self.assertEqual(
            [row.id for row in admitted],
            ["text_line-0", "whole_shape-0", "text_line-1"],
        )

    def test_program_hard_negative_factory_and_ranker_cover_all_near_misses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ring.png"
            image = Image.new("RGB", (48, 48), "white")
            ImageDraw.Draw(image).ellipse((8, 8, 40, 40), fill="black")
            image.save(path)
            reir = build_reir(path)
            support = np.asarray(image.convert("L")) < 128
            candidate = candidate_from_support(
                reir, family="shape", mask=support,
                roi_xyxy=(8, 8, 41, 41), evidence_token_ids=(), score=1.0,
                provenance=("phase9-hard-negative-fixture",),
                kind=MacroKind.SHAPE, components=1, holes=0,
            )
            self.assertIsNotNone(candidate)
            candidate = replace(candidate, program=SceneProgram("Shape/circle", (
                ("cx", 24.0), ("cy", 24.0), ("radius", 16.0),
            )))
            negatives = generate_hard_negatives(candidate)
            self.assertEqual(
                {row.negative_type for row in negatives}, set(HARD_NEGATIVE_TYPES),
            )
            self.assertTrue(all(
                row.support_size == (48, 48)
                and row.render_sha256
                and len(row.positive_features) == 16
                and len(row.negative_features) == 16
                and (
                    not row.applicable
                    or row.positive_features != row.negative_features
                )
                for row in negatives
            ))
            for row in negatives:
                rendered_support, render, raster_applicable = (
                    render_hard_negative_program(row.program)
                )
                self.assertEqual(
                    hashlib.sha256(render.tobytes()).hexdigest(),
                    row.render_sha256,
                )
                self.assertEqual(
                    int(rendered_support.sum()),
                    sum(length for _start, length in row.rendered_support_rle),
                )
                self.assertGreaterEqual(
                    int(raster_applicable), int(row.applicable),
                )
            self.assertLessEqual(sum(row.applicable for row in negatives), 4)
            self.assertTrue(all(
                not row.applicable for row in negatives
                if row.negative_type in {
                    "split_glyph", "fuse_letters", "wrong_layer",
                    "gradient_band_explosion", "stroke_fill_confusion",
                }
            ))
            feature_pairs = counterfactual_feature_pairs(support)
            risk_regions = counterfactual_risk_regions(support)
            self.assertEqual(set(feature_pairs), set(HARD_NEGATIVE_TYPES))
            self.assertEqual(set(risk_regions), set(HARD_NEGATIVE_TYPES))
            for name in HARD_NEGATIVE_TYPES:
                positive_features, negative_features, applicable = feature_pairs[name]
                region, region_applicable = risk_regions[name]
                self.assertEqual(len(positive_features), 16)
                self.assertEqual(len(negative_features), 16)
                self.assertFalse(region.flags.writeable)
                self.assertEqual(applicable, region_applicable)
            layer_allowed = applicable_hard_negative_types(("layer_relation",))
            semantic = counterfactual_risk_regions(
                support, allowed_types=layer_allowed,
            )
            self.assertTrue(semantic["wrong_layer"][1])
            self.assertFalse(semantic["gradient_band_explosion"][1])
            ranker = CandidateRanker(feature_dim=12, hidden_dim=24)
            positive = torch.ones(10, 12)
            negative = torch.zeros(10, 12)
            loss = pairwise_ranking_loss(ranker, positive, negative)
            self.assertTrue(torch.isfinite(loss))
            loss.backward()
            self.assertTrue(any(parameter.grad is not None for parameter in ranker.parameters()))

    def test_all_neural_heads_have_bounded_proposal_only_effects(self) -> None:
        support = np.zeros((20, 40), bool)
        support[5:15, 8:32] = True
        support.setflags(write=False)
        observed = (0.5, 0.5, 0.6, 0.5, 0.3, 1.0)

        def query(*, parameters=observed, covariance=(0.01,) * 6,
                  topology=(1, 0), relation=1.0, relation_tokens=None,
                  provenance=("ProposalNet-query",)):
            return ProposalQuery(
                id="head-prior", family="text_line",
                roi_xyxy=(0.2, 0.2, 0.8, 0.8), soft_support=support.astype(np.float32),
                parameters=tuple(parameters), covariance=tuple(covariance),
                confidence=0.5,
                relation_tokens=(
                    (("text_membership", relation),)
                    if relation_tokens is None else relation_tokens
                ),
                topology_code=topology, hard_negative_class=None,
                provenance=provenance,
            )

        good, provenance = query_head_prior_score(
            query(), support, expected_relations=("text_membership",),
        )
        bad_parameters, _ = query_head_prior_score(
            query(parameters=(2.0,) * 6), support,
            expected_relations=("text_membership",),
        )
        uncertain_parameters, _ = query_head_prior_score(
            query(parameters=(2.0,) * 6, covariance=(100.0,) * 6), support,
            expected_relations=("text_membership",),
        )
        bad_topology, _ = query_head_prior_score(
            query(topology=(6, 4)), support,
            expected_relations=("text_membership",),
        )
        bad_relation, _ = query_head_prior_score(
            query(relation=0.0), support,
            expected_relations=("text_membership",),
        )
        classical, classical_provenance = query_head_prior_score(
            query(provenance=("classical",)), support,
            expected_relations=("text_membership",),
        )
        conjunctive, _ = query_head_prior_score(
            query(relation_tokens=(
                ("same_group", 1.0), ("text_membership", 1.0),
            )), support, expected_relation_groups=(
                ("same_group",), ("text_membership",),
            ),
        )
        missing_conjunct, _ = query_head_prior_score(
            query(relation_tokens=(("text_membership", 1.0),)), support,
            expected_relation_groups=(
                ("same_group",), ("text_membership",),
            ),
        )
        self.assertGreater(good, bad_parameters)
        self.assertGreater(uncertain_parameters, bad_parameters)
        self.assertGreater(good, bad_topology)
        self.assertGreater(good, bad_relation)
        self.assertGreater(conjunctive, missing_conjunct)
        self.assertLessEqual(abs(good - 0.5), 0.08)
        self.assertLessEqual(abs(bad_parameters - 0.5), 0.08)
        self.assertEqual(classical, 0.5)
        self.assertIn("proposal-only-head-prior;court-still-mandatory", provenance)
        self.assertEqual(
            classical_provenance, ("classical-query-no-neural-head-prior",),
        )

    def test_runtime_text_cache_binds_every_proposal_query_field(self) -> None:
        from vice_compiler.runtime_service import _proposal_queries_digest

        support = np.zeros((4, 6), np.float32)
        support[1:3, 2:5] = 0.75
        support.setflags(write=False)
        base = ProposalQuery(
            id="cache-query", family="text_line",
            roi_xyxy=(0.1, 0.2, 0.8, 0.9), soft_support=support,
            parameters=(0.25, 0.5), covariance=(0.1, 0.2),
            confidence=0.9,
            relation_tokens=(("text_membership", 0.8),),
            topology_code=(1, 1), hard_negative_class="split_glyph",
            provenance=("ProposalNet-query", "cache-contract"),
        )
        baseline = _proposal_queries_digest((base,))
        variants = (
            replace(base, id="cache-query-2"),
            replace(base, family="whole_shape"),
            replace(base, roi_xyxy=(0.0, 0.2, 0.8, 0.9)),
            replace(base, soft_support=np.ascontiguousarray(support[:, :5])),
            replace(base, parameters=(0.35, 0.5)),
            replace(base, covariance=(0.2, 0.2)),
            replace(base, confidence=0.8),
            replace(base, relation_tokens=(("text_membership", 0.7),)),
            replace(base, topology_code=(2, 1)),
            replace(base, hard_negative_class="fuse_letters"),
            replace(base, provenance=("ProposalNet-query", "changed")),
        )
        variant_digests = {
            _proposal_queries_digest((row,)) for row in variants
        }
        self.assertEqual(len(variant_digests), len(variants))
        self.assertNotIn(baseline, variant_digests)
        self.assertNotEqual(
            _proposal_queries_digest((base,)),
            _proposal_queries_digest((base, base)),
        )


if __name__ == "__main__":
    unittest.main()

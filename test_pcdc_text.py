from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch

from vice_compiler.certificates import topology_signature
from vice_compiler.evidence_ir import build_reir
from vice_compiler.glyph_prior import (
    GlyphPriorConfig, GlyphPriorNet, checkpoint_payload,
)
from vice_compiler.design_program import _design_operator
from vice_compiler.exact_font_provider import (
    OcrLineHint, ReirExactFontProvider, discover_owned_font_catalog,
)
from vice_compiler.export_writer import (
    _candidate_support, _text_elements, render_text_delivery,
)
from vice_compiler.macro_registry import (
    build_base_registry, decode_token_mask, extend_registry,
)
from vice_compiler.macro_ir import MacroKind, SceneProgram
from vice_compiler.proposal_net import ProposalQuery
from vice_compiler.runtime_service import (
    _opaque_linear_rgb, _text_ink_from_exact_render, _text_overlap_metrics,
)
from vice_compiler.text_macros import (
    ExactFontEvidence, _claims, _line_from_mask,
    _chromatic_completion_pair_proved,
    _enclosing_physical_midline_proved,
    _ocr_edge_counter_extension_proved,
    _joint_appearance, _ocr_physical_midline_text_support,
    _ocr_adaptive_glyph_preimage,
    _ocr_evidence_glyph_cell_edges,
    _glyph_prior_topology_contract,
    _ocr_neural_glyph_preimage,
    _ocr_semantic_topology_contract, _repair_one_ocr_glyph_topology,
    _ocr_ownership_topology_compatible,
    _physical_midline_text_support,
    _semantic_ocr_complete_line_proved,
    _semantic_glyph_observations,
    _topology_constrained_component_subset,
    classify_text_effect_layers,
    generate_text_macros,
    glyph_catastrophe_count, materialize_font_free_geometry, propose_text_lines,
    repeated_glyph_em, select_text_line_with_court,
    topology_preserving_sdf_glyph,
)


class TextMacroPhase4Tests(unittest.TestCase):
    def test_enclosing_physical_midline_requires_bounded_source_proof(self) -> None:
        fallback = np.zeros((24, 80), bool)
        fallback[6:18, 5:15] = True
        fallback[6:18, 25:35] = True
        fallback[6:18, 45:55] = True
        candidate = fallback.copy()
        candidate[6:18, 4:16] = True
        candidate[6:18, 24:36] = True
        candidate[6:18, 44:56] = True
        line = SimpleNamespace(
            score=0.80,
            sources=("persistent-physical-midline-topology",),
        )
        self.assertTrue(_enclosing_physical_midline_proved(
            fallback, candidate, line,
            candidate_score=0.72, fallback_score=0.60,
            candidate_topology_error=2, fallback_topology_error=4,
        ))
        oversized = cv2.dilate(
            candidate.astype(np.uint8), np.ones((9, 9), np.uint8),
        ) > 0
        self.assertFalse(_enclosing_physical_midline_proved(
            fallback, oversized, line,
            candidate_score=0.80, fallback_score=0.60,
            candidate_topology_error=1, fallback_topology_error=4,
        ))
        self.assertFalse(_enclosing_physical_midline_proved(
            fallback, candidate,
            SimpleNamespace(
                score=0.80, sources=("uncorroborated-threshold",),
            ),
            candidate_score=0.72, fallback_score=0.60,
            candidate_topology_error=2, fallback_topology_error=4,
        ))

    def test_chromatic_completion_requires_nested_threshold_pair(self) -> None:
        fallback = np.zeros((24, 96), bool)
        for left in (4, 24, 44):
            fallback[7:17, left:left + 8] = True
        candidate = fallback.copy()
        for left in (64, 80):
            candidate[7:17, left:left + 8] = True
        witness = candidate.copy()
        for left in (4, 24, 44, 64, 80):
            witness[6:7, left:left + 8] = True
        sources = (
            "both-polarities", "multithreshold-native-ink",
            "persistent-physical-midline-topology",
        )
        candidate_line = SimpleNamespace(id="core", score=0.86, sources=sources)
        witness_line = SimpleNamespace(id="outer", score=0.84, sources=sources)
        self.assertTrue(_chromatic_completion_pair_proved(
            fallback, candidate, witness, candidate_line, witness_line,
            candidate_score=0.78, fallback_score=0.60,
        ))
        self.assertFalse(_chromatic_completion_pair_proved(
            fallback, candidate, witness, candidate_line,
            SimpleNamespace(
                id="outer", score=0.84,
                sources=("single-threshold",),
            ),
            candidate_score=0.78, fallback_score=0.60,
        ))

    def test_semantic_ocr_complete_line_requires_all_source_walls(self) -> None:
        values = dict(
            recognized_glyphs=11,
            incumbent_topology=(42, 6), candidate_topology=(6, 6),
            line_score=0.89, local_contrast=0.14,
            local_line_score=0.73, local_fallback_score=0.60,
            candidate_score=0.70, fallback_score=0.52,
            overlap=0.95, horizontal_span_recall=0.98, area_ratio=1.9,
        )
        self.assertTrue(_semantic_ocr_complete_line_proved(**values))
        self.assertFalse(_semantic_ocr_complete_line_proved(
            **{**values, "horizontal_span_recall": 0.80},
        ))
        self.assertFalse(_semantic_ocr_complete_line_proved(
            **{**values, "incumbent_topology": (12, 6)},
        ))
        self.assertFalse(_semantic_ocr_complete_line_proved(
            **{**values, "candidate_score": 0.60},
        ))

    def test_ocr_cannot_drift_an_already_stable_physical_topology(self) -> None:
        values = dict(
            edge_counter_extension=False, local_fallback_empty=False,
            stable_local_incumbent=True,
            fallback_topology=(15, 6), persistent_topology=(15, 6),
            ownership_topology=(16, 7), local_fallback_topology=(15, 6),
        )
        self.assertFalse(_ocr_ownership_topology_compatible(**values))
        self.assertTrue(_ocr_ownership_topology_compatible(
            **{**values, "ownership_topology": (15, 6)},
        ))
        self.assertTrue(_ocr_ownership_topology_compatible(
            **{**values, "edge_counter_extension": True},
        ))

    def test_solid_canvas_carrier_cannot_beat_physical_text_ink(self) -> None:
        generated = generate_text_macros(self.reir, max_line_proposals=12)
        fallback = np.ones((self.reir.height, self.reir.width), bool)
        decision = select_text_line_with_court(
            self.reir, generated, legacy_support=fallback,
        )
        self.assertFalse(decision.fallback_used)
        self.assertEqual(
            decision.reason, "solid-canvas-carrier-text-recovery",
        )
        self.assertEqual(topology_signature(decision.support_mask), (4, 6))

    def test_uppercase_ocr_contract_repairs_native_counter_aliasing(self) -> None:
        contract = _ocr_semantic_topology_contract("STORmCRRFT")
        self.assertIsNotNone(contract)
        assert contract is not None
        glyphs, counters = contract
        self.assertEqual(len(glyphs), 10)
        self.assertEqual(sum(counters), 4)

        lower = _glyph_prior_topology_contract("Spadegaming")
        self.assertIsNotNone(lower)
        assert lower is not None
        lower_glyphs, lower_components, lower_counters = lower
        self.assertEqual("".join(lower_glyphs), "Spadegaming")
        self.assertEqual(sum(lower_components), 12)
        self.assertEqual(sum(lower_counters), 7)
        self.assertIsNone(_ocr_semantic_topology_contract("Spadegaming"))

        short_mixed = _glyph_prior_topology_contract("KfC")
        self.assertEqual(short_mixed, (("K", "f", "C"), (1, 1, 1), (0, 0, 0)))

        aliased_o = np.ones((7, 4), bool)
        repaired_o = _repair_one_ocr_glyph_topology(
            aliased_o, expected_holes=1, character="O",
        )
        self.assertIsNotNone(repaired_o)
        assert repaired_o is not None
        self.assertEqual(topology_signature(repaired_o), (1, 1))

        aliased_s = np.asarray([
            [1, 1, 1], [1, 0, 1], [1, 1, 0], [0, 1, 1],
            [1, 0, 1], [1, 1, 1], [1, 1, 1],
        ], bool)
        self.assertEqual(topology_signature(aliased_s), (1, 2))
        repaired_s = _repair_one_ocr_glyph_topology(
            aliased_s, expected_holes=0, character="S",
        )
        self.assertIsNotNone(repaired_s)
        assert repaired_s is not None
        self.assertEqual(topology_signature(repaired_s), (1, 0))

    def test_adaptive_glyph_preimage_uses_per_glyph_topology_plateaus(self) -> None:
        source = np.zeros((14, 44), bool)
        for left in (2, 12, 22, 32):
            source[2:12, left:left + 8] = True
        distance = np.where(source, 0.90, 0.0).astype(np.float32)
        result = _ocr_adaptive_glyph_preimage(
            source, distance, "ABCD", noise_floor=0.01,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(topology_signature(result), (4, 4))
        self.assertFalse(result.flags.writeable)
        self.assertFalse(np.any(result[:, :2]))
        self.assertFalse(np.any(result[:, 40:]))

    def test_ocr_cell_boundaries_follow_source_ink_valleys(self) -> None:
        source = np.zeros((14, 44), bool)
        for left, right in ((0, 7), (9, 17), (23, 31), (36, 44)):
            source[2:12, left:right] = True
        edges = _ocr_evidence_glyph_cell_edges(source, "CCCC")
        self.assertEqual(len(edges), 5)
        self.assertEqual((edges[0], edges[-1]), (0, 44))
        self.assertTrue(all(
            not np.any(source[:, edge]) for edge in edges[1:-1]
        ))
        self.assertNotEqual(edges, (0, 11, 22, 33, 44))

    def test_neural_glyph_preimage_is_separate_and_topology_gated(self) -> None:
        config = GlyphPriorConfig(
            image_size=32, base_channels=8, character_embedding_dim=4,
        )
        model = GlyphPriorNet(config)
        for parameter in model.parameters():
            torch.nn.init.zeros_(parameter)
        with torch.no_grad():
            model.pixel_heads.bias[0] = 8.0
            model.component_head.bias[1] = 8.0
            model.hole_head.bias[0] = 8.0
        source = np.zeros((20, 44), bool)
        for left in (3, 13, 23, 33):
            source[4:16, left:left + 7] = True
        visible = np.ones((20, 44, 3), np.float32)
        visible[source] = 0.0
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "glyph.pt"
            torch.save(checkpoint_payload(
                model, epoch=1, manifest_sha256="a" * 64,
                split_sha256="b" * 64, selection_key=(1.0, 1.0),
            ), checkpoint)
            result = _ocr_neural_glyph_preimage(
                source, visible, "IIII", checkpoint=checkpoint,
            )
        self.assertIsNotNone(result)
        self.assertEqual(topology_signature(result), (4, 0))

    def test_neural_topology_decoder_prunes_only_disconnected_islands(self) -> None:
        probability = np.full((32, 32), 0.05, np.float32)
        cv2.circle(probability, (16, 16), 10, 0.92, -1)
        cv2.circle(probability, (16, 16), 4, 0.04, -1)
        for point in ((2, 2), (28, 3), (3, 28), (28, 28)):
            cv2.circle(probability, point, 1, 0.88, -1)
        source = probability >= 0.5
        source[:5, :5] = False
        source[:6, 26:] = False
        source[26:, :6] = False
        source[26:, 26:] = False
        decoded, _threshold, matched = (
            _topology_constrained_component_subset(
                probability, source, (1, 1), 0.5,
            )
        )
        self.assertTrue(matched)
        self.assertEqual(topology_signature(decoded), (1, 1))
        self.assertFalse(decoded[2, 2])

    def test_ocr_cells_group_fragments_as_glyphs_for_repeated_em(self) -> None:
        connected_word = np.zeros((20, 48), bool)
        connected_word[5:15, 4:44] = True
        glyphs = _semantic_glyph_observations(
            connected_word, "line", "AAAA",
        )
        self.assertEqual(len(glyphs), 4)
        self.assertTrue(all(row.semantic_character == "A" for row in glyphs))
        self.assertEqual(len(repeated_glyph_em(glyphs)), 1)

    def test_compound_text_paths_remain_typed_in_design_ir(self) -> None:
        expected = {
            "single-custom-glyph": "CustomGlyph",
            "knockout-text": "KnockoutText",
            "outlined-text-group": "OutlinedTextGroup",
            "outlined-shadowed-text-group": "ShadowedTextGroup",
        }
        for path, operator in expected.items():
            self.assertEqual(
                _design_operator(
                    SceneProgram(f"TextLine/{path}", ()),
                    MacroKind.TEXT_LINE,
                ),
                operator,
            )

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "text.png"
        image = Image.new("RGB", (180, 56), "white")
        draw = ImageDraw.Draw(image)
        font_path = Path(r"C:\Windows\Fonts\arialbd.ttf")
        self.font_path = font_path
        font = (
            ImageFont.truetype(str(font_path), 28)
            if font_path.is_file() else ImageFont.load_default()
        )
        draw.text((9, 8), "BOBO", font=font, fill=(12, 18, 28))
        image.save(self.path)
        self.reir = build_reir(self.path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_line_proposals_are_reir_direct_bounded_and_immutable(self) -> None:
        started = time.perf_counter()
        proposals = propose_text_lines(self.reir, max_proposals=12)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.assertTrue(proposals)
        self.assertLessEqual(len(proposals), 12)
        self.assertLess(elapsed_ms, 200.0)
        for proposal in proposals:
            proposal.validate(self.reir)
            self.assertFalse(proposal.support_mask.flags.writeable)
            self.assertTrue(any(
                source in proposal.sources
                for source in (
                    "lightweight-query-token", "both-polarities",
                    "component-alignment",
                )
            ))

    def test_background_voids_are_not_promoted_as_inverse_text(self) -> None:
        proposals = propose_text_lines(self.reir, max_proposals=12)
        self.assertTrue(any(
            proposal.polarity in {"token", "native-ink-coverage", "dark-on-light"}
            for proposal in proposals
        ))
        self.assertFalse(any(
            proposal.polarity == "light-on-dark" for proposal in proposals
        ))

    def test_full_scene_emblem_is_not_promoted_to_textline(self) -> None:
        source = Path(self.temp.name) / "emblem.png"
        image = Image.new("RGB", (160, 160), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((4, 4, 156, 156), fill=(230, 35, 25))
        draw.polygon(((0, 68), (160, 34), (160, 50), (0, 86)), fill="white")
        draw.polygon(((0, 116), (160, 76), (160, 94), (0, 134)), fill="white")
        image.save(source)
        emblem = build_reir(source)
        proposals = propose_text_lines(emblem, max_proposals=12)
        self.assertFalse(any(
            "OCR" not in proposal.sources
            and (proposal.roi_xyxy[2] - proposal.roi_xyxy[0])
                / max(1, proposal.roi_xyxy[3] - proposal.roi_xyxy[1]) < 1.15
            for proposal in proposals
        ))

    def test_aligned_word_lane_survives_broad_logo_token_quota(self) -> None:
        source = Path(self.temp.name) / "word-beside-logo.png"
        image = Image.new("RGB", (150, 56), "white")
        draw = ImageDraw.Draw(image)
        font = (
            ImageFont.truetype(str(self.font_path), 28)
            if self.font_path.is_file() else ImageFont.load_default()
        )
        draw.text((5, 8), "Linux", font=font, fill=(12, 18, 28))
        # A large adjacent mark creates stronger broad foreground tokens.  It
        # must not starve the bounded stable-component TextLine lane.
        draw.ellipse((104, 3, 147, 50), fill=(12, 18, 28))
        image.save(source)
        reir = build_reir(source)
        proposals = propose_text_lines(reir, max_proposals=12)
        self.assertTrue(proposals)
        self.assertTrue(any(
            "stable-small-component-line" in proposal.sources
            and proposal.roi_xyxy[2] < 104
            for proposal in proposals
        ))

    def test_sdf_dual_loop_path_preserves_components_and_counters(self) -> None:
        ring = np.zeros((48, 48), np.uint8)
        cv2.circle(ring, (24, 24), 15, 1, -1)
        cv2.circle(ring, (24, 24), 7, 0, -1)
        rebuilt = topology_preserving_sdf_glyph(ring > 0, 5.0)
        self.assertEqual(glyph_catastrophe_count(ring > 0, rebuilt), 0)
        self.assertFalse(rebuilt.flags.writeable)

    def test_gcr_counts_affected_glyphs_not_raw_hole_delta(self) -> None:
        reference = np.zeros((48, 80), bool)
        reference[12:36, 24:56] = True
        candidate = np.zeros_like(reference)
        candidate[4:44, 8:72] = True
        holes = 0
        for y in range(8, 40, 4):
            for x in range(12, 68, 4):
                if reference[y, x]:
                    continue
                candidate[y, x] = False
                holes += 1
                if holes >= 40:
                    break
            if holes >= 40:
                break
        self.assertGreaterEqual(topology_signature(candidate)[1], 32)
        self.assertEqual(glyph_catastrophe_count(reference, candidate), 1)

        separate = np.zeros((32, 64), bool)
        separate[8:24, 6:22] = True
        separate[8:24, 38:54] = True
        fused = separate.copy()
        fused[15:17, 22:38] = True
        self.assertEqual(glyph_catastrophe_count(separate, fused), 2)

    def test_physical_midline_removes_weak_aa_bridge_but_keeps_real_aa(self) -> None:
        source = Path(self.temp.name) / "aa-bridge.png"
        pixels = np.full((32, 64, 3), 255, np.uint8)
        support = np.zeros((32, 64), bool)
        support[9:25, 8:18] = True
        support[9:25, 23:33] = True
        pixels[support] = (12, 18, 28)

        # A >50%-coverage edge belongs to the recoverable glyph midline.
        real_aa = np.zeros_like(support)
        real_aa[8, 9:17] = True
        support |= real_aa
        pixels[real_aa] = (170, 170, 170)

        # These near-background pixels make the token 8-connected, but carry
        # nowhere near physical midline coverage and must not prove fusion.
        weak_bridge = np.zeros_like(support)
        weak_bridge[20, 18:23] = True
        support |= weak_bridge
        pixels[weak_bridge] = (235, 235, 235)
        Image.fromarray(pixels, "RGB").save(source)
        reir = build_reir(source)

        certified = _physical_midline_text_support(reir, support)
        self.assertIsNotNone(certified)
        assert certified is not None
        self.assertEqual(topology_signature(support)[0], 1)
        self.assertEqual(topology_signature(certified)[0], 2)
        self.assertTrue(np.all(certified[real_aa]))
        self.assertFalse(np.any(certified[weak_bridge]))
        self.assertFalse(certified.flags.writeable)

        line = _line_from_mask(
            reir, support, polarity="token",
            sources=("unit-physical-AA-evidence",), raw_score=0.9,
        )
        self.assertIsNotNone(line)
        assert line is not None
        self.assertEqual(topology_signature(line.support_mask)[0], 2)
        fused_claims = _claims(
            line, support, (), readability=1.0, render_evidence=1.0,
        )
        self.assertFalse(fused_claims.no_unproven_fusion)
        self.assertFalse(fused_claims.hard_valid)

    def test_ocr_physical_subset_tolerates_splits_but_cannot_fuse(self) -> None:
        source = Path(self.temp.name) / "ocr-jpeg-connectivity.png"
        pixels = np.full((36, 96, 3), 255, np.uint8)
        support = np.zeros((36, 96), bool)
        for left in (7, 29, 51, 73):
            support[8:29, left:left + 8] = True
            pixels[8:29, left:left + 8] = (18, 18, 18)
        # Three source-observed AA bridges make one Otsu component.  Their
        # unequal coverage makes connectivity vary across physical levels.
        for left, value in ((15, 172), (59, 166)):
            support[18:20, left:left + 14] = True
            pixels[18:20, left:left + 14] = (value, value, value)
        Image.fromarray(pixels, "RGB").save(source)
        reir = build_reir(source)

        self.assertIsNone(_physical_midline_text_support(reir, support))
        recovered = _ocr_physical_midline_text_support(
            reir, support, "ABCD",
        )
        self.assertIsNotNone(recovered)
        assert recovered is not None
        self.assertFalse(np.any(recovered & ~support))
        self.assertGreaterEqual(
            topology_signature(recovered)[0], topology_signature(support)[0],
        )
        self.assertFalse(recovered.flags.writeable)

        line = _line_from_mask(
            reir, support, polarity="token",
            sources=("OCR", "ocr-text:ABCD"), raw_score=1.0,
        )
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn(
            "OCR-bounded-physical-subset-with-connectivity-uncertainty",
            line.sources,
        )

    def test_ocr_edge_counter_proof_recovers_truncated_final_glyph(self) -> None:
        semantic = np.zeros((24, 120), bool)
        for index in range(11):
            left = 4 + 9 * index
            semantic[6:18, left:left + 6] = True
            if index < 5:
                semantic[9:15, left + 2:left + 4] = False
        physical = semantic.copy()
        physical[6:18, 105:112] = True
        physical[9:15, 107:110] = False
        semantic_line = SimpleNamespace(
            id="semantic", support_mask=semantic,
            sources=(
                "OCR", "ocr-text:CODERSRANK.I",
                "OCR-semantic-digital-preimage-topology",
            ),
        )
        physical_line = SimpleNamespace(
            id="physical", score=0.98,
            sources=(
                "OCR", "ocr-text:CODERSRANK.I",
                "persistent-physical-midline-topology",
            ),
        )
        self.assertTrue(_ocr_edge_counter_extension_proved(
            "CODERSRANK.I", physical_line, physical, (semantic_line,),
        ))
        no_counter = physical.copy()
        no_counter[9:15, 107:110] = True
        self.assertFalse(_ocr_edge_counter_extension_proved(
            "CODERSRANK.I", physical_line, no_counter, (semantic_line,),
        ))

    def test_ocr_modal_color_distance_recovers_colored_word(self) -> None:
        source = Path(self.temp.name) / "colored-word.png"
        image = Image.new("RGB", (180, 56), "white")
        draw = ImageDraw.Draw(image)
        font = (
            ImageFont.truetype(str(self.font_path), 28)
            if self.font_path.is_file() else ImageFont.load_default()
        )
        draw.text((9, 8), "BOBO", font=font, fill=(190, 155, 95))
        image.save(source, quality=35)
        reir = build_reir(source)
        proposals = propose_text_lines(
            reir, max_proposals=12,
            ocr_hints=(("BOBO", (7, 6, 100, 45), 1.0),),
        )
        colored = [
            proposal for proposal in proposals
            if "OCR-color-distance-to-modal-background" in proposal.sources
        ]
        self.assertTrue(colored)
        self.assertTrue(all(
            not np.any(proposal.support_mask[:, 105:])
            for proposal in colored
        ))

    def test_neural_glyph_prior_retries_after_physical_line_decode(self) -> None:
        source = Path(self.temp.name) / "late-neural-word.png"
        image = Image.new("RGB", (180, 56), "white")
        draw = ImageDraw.Draw(image)
        font = (
            ImageFont.truetype(str(self.font_path), 28)
            if self.font_path.is_file() else ImageFont.load_default()
        )
        draw.text((9, 8), "BOBO", font=font, fill=(190, 155, 95))
        image.save(source, quality=35)
        reir = build_reir(source)
        calls: list[np.ndarray] = []

        def fake_prior(
            support: np.ndarray, _visible: np.ndarray, _text: str,
        ) -> np.ndarray | None:
            calls.append(np.asarray(support, bool).copy())
            if len(calls) == 1:
                # The early raw OCR-colour attempt fails.  The second call is
                # required to consume a materialized physical TextLine.
                return None
            result = np.asarray(support, bool).copy()
            result.setflags(write=False)
            return result

        with patch(
            "vice_compiler.text_macros._ocr_neural_glyph_preimage",
            side_effect=fake_prior,
        ):
            proposals = propose_text_lines(
                reir, max_proposals=12,
                ocr_hints=(("BOBO", (7, 6, 100, 45), 1.0),),
            )

        self.assertEqual(len(calls), 2)
        self.assertTrue(any(
            "late-neural-after-certified-physical-line" in proposal.sources
            for proposal in proposals
        ))

    def test_ocr_local_ownership_preserves_adjacent_mark(self) -> None:
        source = Path(self.temp.name) / "mark-and-colored-word.jpg"
        image = Image.new("RGB", (180, 56), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((5, 10, 35, 40), fill=(175, 20, 30))
        draw.ellipse((12, 17, 28, 33), fill="white")
        font = (
            ImageFont.truetype(str(self.font_path), 28)
            if self.font_path.is_file() else ImageFont.load_default()
        )
        draw.text((48, 8), "BOBO", font=font, fill=(190, 155, 95))
        image.save(source, quality=40)
        reir = build_reir(source)

        class HintOnlyProvider:
            def line_hints(self):
                return (OcrLineHint("BOBO", (46, 6, 140, 45), 1.0),)

            def __call__(self, _reir, _line):
                return ()

        generated = generate_text_macros(
            reir, exact_font_provider=HintOnlyProvider(),
            max_line_proposals=12,
        )
        next(
            proposal for proposal in generated.proposals
            if "OCR-color-distance-to-modal-background" in proposal.sources
        )
        # The incumbent retains the adjacent mark but sees only a fragment of
        # the word.  The court may rewrite the OCR ROI, never the mark ROI.
        fallback = np.zeros((reir.height, reir.width), bool)
        fallback[:, :40] = (
            np.linalg.norm(
                reir.raster.straight_rgba[:, :40, :3]
                - np.ones((1, 1, 3), np.float32), axis=2,
            ) > 0.20
        )
        mark_before = fallback[:, :40].copy()
        decision = select_text_line_with_court(
            reir, generated, legacy_support=fallback,
        )
        self.assertFalse(decision.fallback_used)
        self.assertEqual(decision.reason, "ocr-local-ownership-recovery")
        self.assertIsNotNone(decision.preserved_fallback_mask)
        self.assertTrue(np.array_equal(
            decision.support_mask[:, :40], mark_before,
        ))
        self.assertGreater(
            int(np.sum(decision.support_mask[:, 70:])),
            int(np.sum(fallback[:, 70:])),
        )

    def test_single_glyph_query_emits_explicit_custom_glyph_macro(self) -> None:
        source = Path(self.temp.name) / "custom-glyph.png"
        image = Image.new("RGB", (64, 64), "white")
        draw = ImageDraw.Draw(image)
        draw.polygon(((31, 7), (53, 52), (37, 44), (29, 57),
                      (23, 43), (10, 51)), fill=(12, 18, 28))
        image.save(source)
        reir = build_reir(source)
        support = np.zeros((64, 64), np.float32)
        support[5:59, 7:56] = 1.0
        support.setflags(write=False)
        query = ProposalQuery(
            id="custom-glyph-query", family="glyph_group",
            roi_xyxy=(7 / 64, 5 / 64, 56 / 64, 59 / 64),
            soft_support=support, parameters=(), covariance=(),
            confidence=0.98, relation_tokens=(), topology_code=(1, 0),
            hard_negative_class=None, provenance=("unit-custom-glyph",),
        )
        generated = generate_text_macros(
            reir, max_line_proposals=8, proposal_queries=(query,),
        )
        custom = [
            record for record in generated.records
            if record.path == "single-custom-glyph"
        ]
        self.assertTrue(custom)
        self.assertTrue(all(len(
            next(line for line in generated.proposals
                 if line.id == record.line_id).glyphs
        ) == 1 for record in custom))
        self.assertTrue(all(record.claims.hard_valid for record in custom))

    def test_detached_dot_and_stem_remain_one_custom_symbol(self) -> None:
        source = Path(self.temp.name) / "detached-custom-glyph.png"
        image = Image.new("RGB", (48, 64), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 22, 28, 55), fill=(10, 14, 20))
        draw.ellipse((20, 6, 28, 14), fill=(10, 14, 20))
        image.save(source)
        reir = build_reir(source)
        support = np.zeros((64, 48), np.float32)
        support[22:56, 20:29] = 1.0
        support[6:15, 20:29] = 1.0
        support.setflags(write=False)
        query = ProposalQuery(
            id="detached-symbol", family="glyph_group",
            roi_xyxy=(18 / 48, 4 / 64, 31 / 48, 58 / 64),
            soft_support=support, parameters=(), covariance=(), confidence=0.99,
            relation_tokens=(), topology_code=(2, 0),
            hard_negative_class=None, provenance=("unit-detached-symbol",),
        )
        generated = generate_text_macros(
            reir, max_line_proposals=12, proposal_queries=(query,),
        )
        composite = [
            record for record in generated.records
            if record.path == "single-custom-glyph"
            and "single-composite-custom-glyph-query" in next(
                line for line in generated.proposals
                if line.id == record.line_id
            ).sources
        ]
        self.assertTrue(composite)
        self.assertTrue(all(
            dict(record.candidate.program.parameters)["glyphs"] == 1
            and dict(record.candidate.program.parameters)["observed_fragments"] == 2
            for record in composite
        ))
        fallback = np.asarray(support, bool).copy()
        fallback[3:5, 34:36] = True
        decision = select_text_line_with_court(
            reir, generated, legacy_support=fallback,
        )
        self.assertFalse(decision.fallback_used)
        self.assertEqual(decision.selected_path, "single-custom-glyph")
        self.assertEqual(
            decision.reason, "single-composite-glyph-query-recovery",
        )
        self.assertEqual(topology_signature(decision.support_mask), (2, 0))

    def test_side_by_side_fragments_are_not_one_custom_symbol(self) -> None:
        source = Path(self.temp.name) / "side-by-side-fragments.png"
        image = Image.new("RGB", (64, 48), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 7, 20, 41), fill="black")
        draw.rectangle((42, 7, 54, 41), fill="black")
        image.save(source)
        reir = build_reir(source)
        support = np.zeros((48, 64), np.float32)
        support[7:42, 8:21] = 1.0
        support[7:42, 42:55] = 1.0
        support.setflags(write=False)
        query = ProposalQuery(
            id="two-neighbours", family="glyph_group",
            roi_xyxy=(6 / 64, 5 / 48, 57 / 64, 44 / 48),
            soft_support=support, parameters=(), covariance=(), confidence=0.99,
            relation_tokens=(), topology_code=(2, 0),
            hard_negative_class=None, provenance=("unit-two-neighbours",),
        )
        generated = generate_text_macros(
            reir, max_line_proposals=12, proposal_queries=(query,),
        )
        self.assertFalse(any(
            "single-composite-custom-glyph-query" in line.sources
            for line in generated.proposals
        ))

    def test_classical_topology_consensus_recovers_inverse_single_glyph(self) -> None:
        source = Path(self.temp.name) / "single-zero.png"
        image = Image.new("RGB", (32, 40), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((6, 3, 26, 37), fill=(8, 12, 20))
        draw.ellipse((12, 10, 20, 30), fill="white")
        image.save(source)
        reir = build_reir(source)
        soft = np.zeros((40, 32), np.float32)
        cv2.ellipse(soft, (16, 20), (10, 17), 0, 0, 360, 1.0, -1)
        cv2.ellipse(soft, (16, 20), (4, 10), 0, 0, 360, 0.0, -1)
        soft.setflags(write=False)
        query = ProposalQuery(
            id="single-counter-query", family="glyph_group",
            roi_xyxy=(4 / 32, 1 / 40, 28 / 32, 39 / 40),
            soft_support=soft, parameters=(), covariance=(),
            confidence=0.99, relation_tokens=(), topology_code=(1, 1),
            hard_negative_class=None, provenance=("unit-single-counter",),
        )
        generated = generate_text_macros(
            reir, max_line_proposals=12, proposal_queries=(query,),
        )
        custom = [
            record for record in generated.records
            if record.path == "single-custom-glyph"
        ]
        self.assertTrue(custom)
        line = next(
            line for line in generated.proposals
            if line.id == custom[0].line_id
        )
        line = replace(line, sources=(
            *line.sources,
            "single-custom-glyph-classical-consensus",
            "token-polarity-reconciled-to-consensus-topology",
        ), score=max(0.90, line.score))
        generated = replace(generated, proposals=tuple(
            line if row.id == line.id else row
            for row in generated.proposals
        ))
        inverse_incumbent = ~np.asarray(line.support_mask, bool)
        decision = select_text_line_with_court(
            reir, generated, legacy_support=inverse_incumbent,
        )
        self.assertFalse(decision.fallback_used)
        self.assertEqual(decision.selected_path, "single-custom-glyph")
        self.assertEqual(
            decision.reason, "single-glyph-consensus-polarity-recovery",
        )
        self.assertEqual(topology_signature(decision.support_mask), (1, 1))

    def test_classical_threshold_consensus_recovers_solid_single_glyph(self) -> None:
        source = Path(self.temp.name) / "single-dot.jpg"
        supersampled = Image.new("RGB", (248, 192), "white")
        draw = ImageDraw.Draw(supersampled)
        draw.ellipse((96, 36, 215, 155), fill=(8, 12, 20))
        image = supersampled.resize((62, 48), Image.Resampling.LANCZOS)
        image.save(source, quality=50)
        reir = build_reir(source)
        generated = generate_text_macros(reir, max_line_proposals=12)
        custom = [
            record for record in generated.records
            if record.path == "single-custom-glyph"
        ]
        self.assertTrue(custom)
        line = next(
            row for row in generated.proposals
            if row.id == custom[0].line_id
            and "single-solid-glyph-classical-consensus" in row.sources
        )
        fallback = np.asarray(line.support_mask, bool).copy()
        for x in (25, 33, 41, 49):
            fallback[3:5, x:x + 2] = True
        decision = select_text_line_with_court(
            reir, generated, legacy_support=fallback,
        )
        self.assertFalse(decision.fallback_used)
        self.assertEqual(decision.selected_path, "single-custom-glyph")
        self.assertEqual(
            decision.reason, "single-glyph-threshold-consensus-recovery",
        )
        self.assertEqual(topology_signature(decision.support_mask), (1, 0))

    def test_tiny_solid_symbol_is_not_replaced_by_its_inverse_canvas(self) -> None:
        source = Path(self.temp.name) / "tiny-solid-symbol.png"
        image = Image.new("RGB", (20, 16), "white")
        ImageDraw.Draw(image).rectangle((6, 3, 17, 12), fill="black")
        image.save(source)
        reir = build_reir(source)
        generated = generate_text_macros(reir, max_line_proposals=8)
        custom = [
            record for record in generated.records
            if record.path == "single-custom-glyph"
        ]
        self.assertTrue(custom)
        incumbent_token = max(
            (token for token in reir.proposal_tokens if token.family == "text"),
            key=lambda token: token.score,
        )
        incumbent = decode_token_mask(
            incumbent_token, (reir.height, reir.width),
        )
        self.assertIsNotNone(incumbent)
        assert incumbent is not None
        reference = np.zeros((16, 20), bool)
        reference[3:13, 6:18] = True
        incumbent_iou = np.sum(reference & incumbent) / np.sum(
            reference | incumbent
        )
        custom_lines = [
            line for line in generated.proposals
            if any(record.line_id == line.id for record in custom)
        ]
        candidate_iou = max(
            np.sum(reference & line.support_mask) / np.sum(
                reference | line.support_mask
            )
            for line in custom_lines
        )
        self.assertGreaterEqual(incumbent_iou, 0.90)
        self.assertGreaterEqual(candidate_iou, 0.90)

    def test_connected_multi_counter_word_emits_outlined_group_macro(self) -> None:
        source = Path(self.temp.name) / "outlined-word.png"
        image = Image.new("RGB", (180, 56), "white")
        draw = ImageDraw.Draw(image)
        for left in (2, 55, 108):
            draw.rounded_rectangle(
                (left, 3, left + 68, 52), radius=13,
                outline=(245, 65, 25), width=3,
            )
        image.save(source)
        reir = build_reir(source)
        generated = generate_text_macros(reir, max_line_proposals=12)
        outlined = [
            record for record in generated.records
            if record.path == "outlined-text-group"
        ]
        self.assertTrue(outlined)
        self.assertTrue(all(
            "wide-connected-multi-counter-evidence" in record.candidate.provenance
            and record.claims.persistent_counters >= 2
            and record.claims.hard_valid
            and tuple(layer.role for layer in record.effect_layers) == ("outline",)
            for record in outlined
        ))
        from vice_compiler.export_writer import _text_elements
        rows = _text_elements(
            reir, outlined[0].candidate, 'fill="#000000"', generated,
        )
        self.assertTrue(rows)
        self.assertTrue(all('data-pcdc-text-effect="outline"' in row for row in rows))

    def test_shadowed_text_is_partitioned_into_ordered_source_layers(self) -> None:
        source = Path(self.temp.name) / "shadowed-word.png"
        image = Image.new("RGB", (150, 52), "white")
        draw = ImageDraw.Draw(image)
        support = np.zeros((52, 150), bool)
        for left in (12, 52, 92):
            draw.rectangle((left + 3, 11, left + 23, 39), fill=(95, 105, 125))
            draw.rectangle((left, 8, left + 20, 36), fill=(20, 28, 42))
            support[11:40, left + 3:left + 24] = True
            support[8:37, left:left + 21] = True
        image.save(source)
        reir = build_reir(source)
        line = _line_from_mask(
            reir, support, polarity="token",
            sources=("unit-shadow-relation",), raw_score=0.95,
        )
        self.assertIsNotNone(line)
        assert line is not None
        line = replace(line, appearance=_joint_appearance(reir, line.support_mask))
        effects = classify_text_effect_layers(reir, line)
        self.assertEqual(tuple(layer.role for layer in effects), ("shadow", "fill"))
        union = np.zeros_like(support)
        for layer in effects:
            union |= layer.support_mask
        np.testing.assert_array_equal(union, support)
        self.assertNotEqual(effects[0].offset_xy, (0, 0))

    def test_spatially_disjoint_multicolour_text_preserves_fill_layers(self) -> None:
        source = Path(self.temp.name) / "multicolour-word.png"
        image = Image.new("RGB", (150, 52), "white")
        draw = ImageDraw.Draw(image)
        support = np.zeros((52, 150), bool)
        draw.rectangle((6, 10, 35, 40), fill=(220, 25, 35))
        support[10:41, 6:36] = True
        for left in (75, 105, 135):
            draw.rectangle((left, 13, min(149, left + 10), 38), fill=(210, 145, 25))
            support[13:39, left:min(150, left + 11)] = True
        image.save(source)
        reir = build_reir(source)
        line = _line_from_mask(
            reir, support, polarity="token",
            sources=("unit-multicolour-fill",), raw_score=0.95,
        )
        self.assertIsNotNone(line)
        assert line is not None
        line = replace(line, appearance=_joint_appearance(reir, line.support_mask))
        effects = classify_text_effect_layers(reir, line)
        self.assertEqual(tuple(layer.role for layer in effects), ("fill", "fill"))
        union = np.zeros_like(support)
        for layer in effects:
            union |= layer.support_mask
        np.testing.assert_array_equal(union, support)
        self.assertGreater(
            np.linalg.norm(
                np.asarray(effects[0].straight_rgba[:3])
                - np.asarray(effects[1].straight_rgba[:3])
            ),
            0.10,
        )

    def test_knockout_text_requires_canvas_through_local_carrier_proof(self) -> None:
        source = Path(self.temp.name) / "knockout-word.png"
        image = Image.new("RGB", (150, 52), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((4, 4, 145, 47), fill=(22, 35, 62))
        support = np.zeros((52, 150), bool)
        for left in (14, 54, 94):
            draw.rectangle((left, 10, left + 20, 39), fill="white")
            support[10:40, left:left + 21] = True
        image.save(source)
        reir = build_reir(source)
        line = _line_from_mask(
            reir, support, polarity="token",
            sources=("unit-local-carrier",), raw_score=0.95,
        )
        self.assertIsNotNone(line)
        assert line is not None
        line = replace(line, polarity="light-on-dark")
        effects = classify_text_effect_layers(reir, line)
        self.assertEqual(tuple(layer.role for layer in effects), ("knockout",))
        generated = generate_text_macros(reir, max_line_proposals=32)
        knockout = [
            record for record in generated.records
            if record.path == "knockout-text"
        ]
        self.assertTrue(knockout)
        self.assertTrue(all(
            tuple(layer.role for layer in record.effect_layers) == ("knockout",)
            for record in knockout
        ))
        carrier = np.zeros((52, 150), bool)
        carrier[4:48, 4:146] = True
        for left in (14, 54, 94):
            carrier[10:40, left:left + 21] = False
        decision = select_text_line_with_court(
            reir, generated, legacy_support=carrier,
        )
        self.assertFalse(decision.fallback_used)
        self.assertEqual(decision.selected_path, "knockout-text")
        self.assertEqual(
            decision.reason, "knockout-carrier-negative-loop-recovery",
        )

    def test_inverse_canvas_fallback_recovers_minority_ink_line(self) -> None:
        generated = generate_text_macros(self.reir, max_line_proposals=12)
        line = generated.proposals[0]
        # Supply the independent polarity evidence that a real both-polarity
        # proposal carries, while retaining the ordinary generated candidate
        # and its exact support certificate.
        polarity_line = replace(
            line, sources=(*line.sources, "both-polarities"),
        )
        generated = replace(
            generated,
            proposals=(polarity_line, *generated.proposals[1:]),
        )
        x1, y1, x2, y2 = line.roi_xyxy
        inverse_canvas = np.zeros((self.reir.height, self.reir.width), bool)
        inverse_canvas[y1:y2, x1:x2] = True
        holes = 0
        for y in range(y1 + 2, y2 - 2, 3):
            for x in range(x1 + 2, x2 - 2, 3):
                if not line.support_mask[y, x]:
                    inverse_canvas[y, x] = False
                    holes += 1
                if holes >= 40:
                    break
            if holes >= 40:
                break
        self.assertEqual(topology_signature(inverse_canvas), (1, 40))
        decision = select_text_line_with_court(
            self.reir, generated, legacy_support=inverse_canvas,
        )
        self.assertFalse(decision.fallback_used)
        self.assertEqual(decision.reason, "inverse-canvas-polarity-recovery")
        self.assertEqual(
            topology_signature(decision.support_mask),
            topology_signature(line.support_mask),
        )

    def test_exact_scene_text_mask_detects_erased_glyph_catastrophe(self) -> None:
        line = propose_text_lines(self.reir, max_proposals=1)[0]
        source_rgba = np.clip(np.rint(
            self.reir.raster.straight_rgba * 255.0
        ), 0, 255).astype(np.uint8)
        recovered, contrast = _text_ink_from_exact_render(
            line, _opaque_linear_rgb(source_rgba),
            audit_domain=line.support_mask,
        )
        iou, precision, recall = _text_overlap_metrics(
            line.support_mask, recovered,
        )
        self.assertGreater(contrast, 0.055)
        self.assertGreater(iou, 0.90)
        self.assertGreater(precision, 0.90)
        self.assertGreater(recall, 0.90)
        self.assertEqual(
            glyph_catastrophe_count(line.support_mask, recovered), 0,
        )

        erased = np.full_like(source_rgba, 255)
        erased[..., 3] = 255
        missing, _contrast = _text_ink_from_exact_render(
            line, _opaque_linear_rgb(erased),
            audit_domain=line.support_mask,
        )
        self.assertGreater(
            glyph_catastrophe_count(line.support_mask, missing), 0,
        )

    def test_exact_scene_text_mask_ignores_foreign_scene_components(self) -> None:
        line = propose_text_lines(self.reir, max_proposals=1)[0]
        reference = np.asarray(line.support_mask, bool)
        rendered_rgba = np.clip(np.rint(
            self.reir.raster.straight_rgba * 255.0
        ), 0, 255).astype(np.uint8)

        # Put a foreground-colored foreign mark near the line but outside the
        # certified text delivery.  A rectangular ROI classifier used to
        # attribute this component to the TextLine.
        outside = ~cv2.dilate(
            reference.astype(np.uint8), np.ones((3, 3), np.uint8),
        ).astype(bool)
        x1, y1, x2, y2 = line.roi_xyxy
        roi = np.zeros_like(reference)
        roi[max(0, y1 - 1):min(reference.shape[0], y2 + 1),
            max(0, x1 - 1):min(reference.shape[1], x2 + 1)] = True
        choices = np.argwhere(outside & roi)
        self.assertGreater(len(choices), 0)
        foreign_y, foreign_x = (int(value) for value in choices[0])
        rendered_rgba[foreign_y, foreign_x, :3] = 0
        rendered_rgba[foreign_y, foreign_x, 3] = 255

        recovered, _contrast = _text_ink_from_exact_render(
            line, _opaque_linear_rgb(rendered_rgba),
            audit_domain=reference,
        )
        self.assertFalse(recovered[foreign_y, foreign_x])

        # The same pixel must be charged when exact TextLine delivery owns it:
        # domain scoping removes foreign marks, not real writer inventions.
        spurious_domain = reference.copy()
        spurious_domain[foreign_y, foreign_x] = True
        with_spurious, _contrast = _text_ink_from_exact_render(
            line, _opaque_linear_rgb(rendered_rgba),
            audit_domain=spurious_domain,
        )
        self.assertTrue(with_spurious[foreign_y, foreign_x])
        self.assertGreater(
            glyph_catastrophe_count(reference, with_spurious), 0,
        )

    def test_all_text_paths_enter_cmir_and_exact_font_is_fail_open(self) -> None:
        def exact_provider(_reir, line):
            return (ExactFontEvidence(
                id=f"exact-{line.id}", font_file="owned-test-font.ttf",
                recognized_text="BOBO", support_mask=line.support_mask,
                retrieval_score=0.99, silhouette_iou=1.0,
                max_boundary_deviation_px=0.0, tracking_em=0.02,
                x_scale=1.0, y_scale=1.0, offset_xy=(0.0, 0.0),
                provenance=("unit-exact-font",),
            ),)

        generated = generate_text_macros(
            self.reir, exact_font_provider=exact_provider,
            max_line_proposals=8,
        )
        self.assertTrue(generated.proposals)
        self.assertGreater(generated.exact_font_attempted, 0)
        self.assertGreater(generated.exact_font_admitted, 0)
        paths = {record.path for record in generated.records}
        self.assertIn("exact-font", paths)
        self.assertIn("font-free-dual-loop", paths)
        self.assertIn("conservative-outline", paths)
        self.assertTrue(all(record.claims.hard_valid for record in generated.records))
        cmir = extend_registry(
            self.reir, build_base_registry(self.reir), generated.candidates
        )
        cmir.validate()

        def broken_provider(_reir, _line):
            raise RuntimeError("OCR/font retrieval unavailable")

        fail_open = generate_text_macros(
            self.reir, exact_font_provider=broken_provider,
            max_line_proposals=4,
        )
        self.assertGreater(fail_open.exact_font_attempted, 0)
        self.assertEqual(fail_open.exact_font_admitted, 0)
        self.assertTrue(any(
            record.path == "conservative-outline"
            for record in fail_open.records
        ))

    def test_repeated_glyph_em_is_bounded(self) -> None:
        proposal = propose_text_lines(self.reir, max_proposals=1)[0]
        prototypes = repeated_glyph_em(
            proposal.glyphs, iterations=3, residual_limit=0.30
        )
        for prototype in prototypes:
            self.assertLessEqual(prototype.iterations, 3)
            self.assertGreaterEqual(len(prototype.member_ids), 2)
            self.assertFalse(prototype.normalized_mask.flags.writeable)
            self.assertLessEqual(
                max(value for _glyph_id, value in prototype.residual_fraction),
                0.30,
            )

    def test_losing_lines_remain_lazy_until_selected_geometry(self) -> None:
        generated = generate_text_macros(
            self.reir, max_line_proposals=8,
        )
        deferred = [
            record for record in generated.records
            if record.path in {"font-free-dual-loop", "conservative-outline"}
        ]
        self.assertTrue(deferred)
        self.assertTrue(all(not record.dual_loop_glyphs for record in deferred))
        self.assertTrue(all(not record.prototypes for record in deferred))
        self.assertTrue(all(
            ("geometry_state", "deferred-after-local-court")
            in record.candidate.program.parameters
            for record in deferred
        ))

        candidate_ids = [record.candidate.id for record in generated.records]
        self.assertEqual(len(candidate_ids), len(set(candidate_ids)))

        selected = generated.proposals[0]
        rebuilt, loops, prototypes = materialize_font_free_geometry(
            self.reir, selected,
        )
        self.assertEqual(len(loops), len(selected.glyphs))
        self.assertFalse(rebuilt.flags.writeable)
        self.assertEqual(
            glyph_catastrophe_count(selected.support_mask, rebuilt), 0
        )
        for prototype in prototypes:
            self.assertFalse(prototype.normalized_mask.flags.writeable)

    def test_font_free_continuous_parameters_change_exact_delivery(self) -> None:
        generated = generate_text_macros(
            self.reir, max_line_proposals=8,
        )
        deployable = []
        for record in generated.records:
            if record.path in {"exact-font", "semantic-font-idealization"}:
                continue
            rendered = render_text_delivery(
                self.reir, record.candidate, generated,
                width=self.reir.width * 4,
            )
            if rendered is not None:
                deployable.append((record, rendered))
        self.assertTrue(deployable)
        record, before = deployable[0]
        parameter_names = {
            name for name, _value in record.candidate.program.parameters
        }
        continuous_names = {
            name for name, _value in record.candidate.continuous_params
        }
        self.assertTrue(continuous_names)
        self.assertTrue(continuous_names <= parameter_names)
        expected = {
            "baseline", "x_height", "cap_height", "overshoot", "slant",
            "tracking", "shared_stem_width",
        }
        self.assertTrue(expected <= continuous_names)
        deltas = {
            "baseline": 0.5, "x_height": 1.0, "cap_height": 1.0,
            "overshoot": 0.5, "slant": 0.03, "tracking": 0.5,
            "shared_stem_width": 0.5,
        }
        for name, delta in deltas.items():
            with self.subTest(variable=name):
                parameters = dict(record.candidate.program.parameters)
                parameters[name] = float(parameters[name]) + delta
                parameters["refined_source_id"] = record.candidate.id
                refined = replace(
                    record.candidate,
                    id=f"refined-text-delivery-test-{name}",
                    program=SceneProgram(
                        record.candidate.program.operator,
                        tuple(parameters.items()),
                    ),
                )
                after = render_text_delivery(
                    self.reir, refined, generated,
                    width=self.reir.width * 4,
                )
                self.assertIsNotNone(after)
                assert after is not None
                self.assertFalse(np.array_equal(before, after))

        text = _text_elements(
            self.reir, record.candidate, 'fill="#000"', generated,
        )
        self.assertTrue(text)

    def test_ocr_prior_can_run_without_pricing_catalog_font_search(self) -> None:
        hint = OcrLineHint("BOBO", (7, 5, 105, 46))
        provider = ReirExactFontProvider(
            self.reir, ocr_hints=(hint,), font_catalog=(),
            enable_font_search=False,
        )
        generated = generate_text_macros(
            self.reir, exact_font_provider=provider, max_line_proposals=8,
        )
        self.assertTrue(any(
            "OCR" in proposal.sources for proposal in generated.proposals
        ))
        self.assertEqual(generated.exact_font_attempted, 0)
        self.assertEqual(generated.exact_font_admitted, 0)
        self.assertEqual(provider.audits, ())

    def test_real_exact_font_provider_reads_reir_and_passes_silhouette_wall(self) -> None:
        if not self.font_path.is_file():
            self.skipTest("Arial Bold is unavailable")
        hint = OcrLineHint("BOBO", (7, 5, 105, 46))
        provider = ReirExactFontProvider(
            self.reir, ocr_hints=(hint,),
            font_catalog=(("Arial Bold", str(self.font_path)),),
            max_fonts=1, top_k=1, refine_rounds=2,
        )
        generated = generate_text_macros(
            self.reir, exact_font_provider=provider,
            max_line_proposals=8,
        )
        ocr_proposals = sum(
            "OCR" in proposal.sources for proposal in generated.proposals
        )
        self.assertGreater(ocr_proposals, 0)
        unique_ocr_queries = {
            (
                next((source.split(":", 1)[1] for source in proposal.sources
                      if source.startswith("ocr-text:")), ""),
                proposal.roi_xyxy,
            )
            for proposal in generated.proposals if "OCR" in proposal.sources
        }
        self.assertEqual(generated.exact_font_attempted, len(unique_ocr_queries))
        self.assertGreater(generated.exact_font_admitted, 0)
        exact = [record for record in generated.records
                 if record.path == "exact-font"]
        self.assertTrue(exact)
        self.assertTrue(all(record.claims.hard_valid for record in exact))
        support = _candidate_support(self.reir, exact[0].candidate)
        rows = _text_elements(
            self.reir, exact[0].candidate, 'fill="#000000"', generated,
        )
        self.assertTrue(rows)
        self.assertIn('data-pcdc-text-geometry="exact-font-outline"', rows[0])
        semantic_record = replace(
            exact[0], path="semantic-font-idealization",
        )
        semantic_generated = replace(
            generated,
            records=tuple(
                semantic_record if row.candidate.id == exact[0].candidate.id
                else row for row in generated.records
            ),
        )
        semantic_rows = _text_elements(
            self.reir, semantic_record.candidate, 'fill="#000000"',
            semantic_generated,
        )
        self.assertEqual(semantic_rows, rows)
        delivered = render_text_delivery(
            self.reir, exact[0].candidate, generated,
        )
        self.assertIsNotNone(delivered)
        assert delivered is not None
        rendered = delivered[..., 3] >= 128
        self.assertEqual(
            topology_signature(rendered), topology_signature(support),
        )
        self.assertGreaterEqual(
            int(np.sum(rendered & support))
            / max(1, int(np.sum(rendered | support))),
            0.82,
        )
        high_resolution = render_text_delivery(
            self.reir, exact[0].candidate, generated,
            width=2 * self.reir.width,
        )
        self.assertIsNotNone(high_resolution)
        assert high_resolution is not None
        self.assertEqual(high_resolution.shape[1], 2 * self.reir.width)
        self.assertEqual(
            high_resolution.shape[0], 2 * delivered.shape[0],
        )
        self.assertGreater(int(np.sum(high_resolution[..., 3] >= 128)), 0)
        self.assertTrue(provider.audits)
        self.assertTrue(all(audit.fonts_considered <= 1 for audit in provider.audits))
        self.assertTrue(any(audit.elapsed_ms < 200.0 for audit in provider.audits))

    def test_exact_font_bank_discovers_nested_drop_in_fonts(self) -> None:
        if not self.font_path.is_file():
            self.skipTest("Arial Bold is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            nested = Path(directory) / "display" / "bold"
            nested.mkdir(parents=True)
            copied = nested / "owned-display.ttf"
            shutil.copyfile(self.font_path, copied)
            catalog = discover_owned_font_catalog((directory,))
        matching = [
            path for _name, path in catalog
            if Path(path).name == "owned-display.ttf"
        ]
        self.assertEqual(matching, [str(copied)])

    def test_default_exact_font_bank_is_exactly_the_licensed_manifest(self) -> None:
        catalog = discover_owned_font_catalog()
        manifest = Path("fonts/google-fonts-manifest.json")
        payload = json.loads(manifest.read_text("utf-8"))
        self.assertEqual(len(catalog), payload["font_count"])
        expected = {
            str((Path("fonts/google-fonts") / row["font_path"]).resolve()).casefold()
            for row in payload["fonts"]
        }
        self.assertEqual(
            {str(Path(path).resolve()).casefold() for _name, path in catalog},
            expected,
        )
        self.assertFalse(any(
            str(Path(path)).casefold().startswith(
                str(Path(r"C:\Windows\Fonts")).casefold()
            )
            for _name, path in catalog
        ))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from vice_compiler.cell_complex import CellComplex, plan_local_refinement
from vice_compiler.certificates import topology_signature
from vice_compiler.evidence_ir import EvidenceCache, build_reir
from vice_compiler.macro_registry import decode_token_mask
from vice_compiler.derive_locus_gt import (
    _best_support_alignment,
    _photometric_alignment,
    _render_svg_rgba,
    derive,
    encode_rle,
)
from vice_compiler.experiment1_evidence_coverage import (
    _topology_recall,
    decode_support_rle,
)


class ReirContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        image = Image.new("RGBA", (96, 64), (9, 220, 17, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, 42, 54), fill=(230, 30, 20, 255))
        draw.ellipse((48, 12, 86, 50), fill=(20, 80, 230, 220))
        draw.ellipse((58, 22, 76, 40), fill=(255, 255, 255, 0))
        self.path = self.root / "fixture.png"
        image.save(self.path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_reir_is_immutable_complete_and_bounded(self) -> None:
        reir = build_reir(self.path, max_dim=512)
        reir.validate()
        self.assertEqual((reir.width, reir.height), (96, 64))
        self.assertLessEqual(
            len(reir.hierarchy.nodes), 2 * reir.hierarchy.leaf_count
        )
        np.testing.assert_array_equal(
            np.unique(reir.hierarchy.leaf_labels),
            np.arange(reir.hierarchy.leaf_count, dtype=np.int32),
        )
        self.assertTrue(all(
            node.area > 0
            and node.bbox_xyxy[0] < node.bbox_xyxy[2]
            and node.bbox_xyxy[1] < node.bbox_xyxy[3]
            for node in reir.hierarchy.nodes
        ))
        self.assertEqual(
            reir.boundary_pyramid[0].probability.shape, (64, 96)
        )
        self.assertEqual(
            reir.boundary_pyramid[1].probability.shape, (16, 24)
        )
        transparent = reir.raster.straight_rgba[..., 3] == 0
        self.assertTrue(
            np.all(reir.raster.straight_rgba[..., :3][transparent] == 0)
        )
        self.assertFalse(reir.raster.oklab.flags.writeable)
        self.assertEqual(len(reir.formation_posterior.hypotheses), 4)
        self.assertEqual(
            reir.boundary_pyramid[0].phase_congruency.shape, (64, 96)
        )
        self.assertEqual(
            reir.boundary_pyramid[0].cross_scale_persistence.shape, (64, 96)
        )
        self.assertTrue(reir.interfaces.half_edges)
        self.assertTrue(
            all(interface.provenance for interface in reir.interfaces.interfaces)
        )
        self.assertTrue(reir.proposal_tokens)
        self.assertTrue(any(
            token.provenance == "fine-topology-threshold-bank"
            and token.support_size == (96, 64)
            for token in reir.proposal_tokens
        ))

    def test_content_addressed_cache_round_trip(self) -> None:
        cache = EvidenceCache(self.root / "cache")
        first, first_hit = cache.get_or_build(self.path)
        second, second_hit = cache.get_or_build(self.path)
        self.assertFalse(first_hit)
        self.assertTrue(second_hit)
        self.assertEqual(first.source_sha256, second.source_sha256)
        second.validate()

    def test_cache_miss_when_reir_implementation_identity_changes(self) -> None:
        cache = EvidenceCache(self.root / "versioned-cache")
        with patch(
            "vice_compiler.evidence_ir.reir_implementation_sha256",
            return_value="1" * 64,
        ):
            first, first_hit = cache.get_or_build(self.path)
        with patch(
            "vice_compiler.evidence_ir.reir_implementation_sha256",
            return_value="2" * 64,
        ):
            second, second_hit = cache.get_or_build(self.path)
            third, third_hit = cache.get_or_build(self.path)
        self.assertFalse(first_hit)
        self.assertFalse(second_hit)
        self.assertTrue(third_hit)
        self.assertNotEqual(
            first.config_fingerprint, second.config_fingerprint,
        )
        self.assertEqual(
            second.config_fingerprint, third.config_fingerprint,
        )

    def test_cold_cache_publication_is_safe_for_concurrent_same_key(self) -> None:
        payload = build_reir(self.path)
        cache = EvidenceCache(self.root / "concurrent-cache")
        barrier = threading.Barrier(4)

        def build_once(*_args, **_kwargs):
            barrier.wait(timeout=10.0)
            return payload

        def request(_index: int):
            return cache.get_or_build(self.path)

        with patch("vice_compiler.evidence_ir.build_reir", side_effect=build_once):
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(request, range(4)))
        self.assertTrue(all(not hit for _reir, hit in results))
        cached, hit = cache.get_or_build(self.path)
        self.assertTrue(hit)
        cached.validate()
        self.assertEqual(len(tuple(cache.root.glob("*.pkl"))), 1)
        self.assertEqual(len(tuple(cache.root.glob("*.tmp"))), 0)

    def test_cold_cache_publication_is_safe_across_cache_instances(self) -> None:
        payload = build_reir(self.path)
        root = self.root / "multi-instance-concurrent-cache"
        caches = [EvidenceCache(root) for _index in range(4)]
        barrier = threading.Barrier(len(caches))

        def build_once(*_args, **_kwargs):
            barrier.wait(timeout=10.0)
            return payload

        def request(index: int):
            return caches[index].get_or_build(self.path)

        with patch("vice_compiler.evidence_ir.build_reir", side_effect=build_once):
            with ThreadPoolExecutor(max_workers=len(caches)) as pool:
                results = list(pool.map(request, range(len(caches))))
        self.assertTrue(all(not hit for _reir, hit in results))
        cached, hit = EvidenceCache(root).get_or_build(self.path)
        self.assertTrue(hit)
        cached.validate()
        self.assertEqual(len(tuple(root.glob("*.pkl"))), 1)
        self.assertEqual(len(tuple(root.glob("*.tmp"))), 0)

    def test_half_edge_twins_are_involutive(self) -> None:
        graph = build_reir(self.path).interfaces
        for edge in graph.half_edges:
            twin = graph.half_edges[edge.twin]
            self.assertEqual(twin.twin, edge.id)
            self.assertEqual((twin.origin, twin.target), (edge.target, edge.origin))

    def test_text_line_token_support_excludes_unrelated_large_dark_object(self) -> None:
        path = self.root / "text-beside-emblem.png"
        image = Image.new("RGB", (120, 50), "white")
        draw = ImageDraw.Draw(image)
        for x in (5, 18, 31, 44):
            draw.rectangle((x, 10, x + 7, 22), fill="black")
        draw.rectangle((82, 3, 116, 46), fill="black")
        image.save(path)
        reir = build_reir(path)
        tokens = [
            token for token in reir.proposal_tokens
            if token.provenance == "stable-small-component-line"
        ]
        self.assertTrue(tokens)
        for token in tokens:
            support = decode_token_mask(token, (reir.height, reir.width))
            self.assertIsNotNone(support)
            x1, y1, x2, y2 = token.bbox_xyxy
            outside = support.copy()
            outside[y1:y2, x1:x2] = False
            self.assertFalse(np.any(outside))

    def test_outlined_word_uses_minority_ink_not_canvas_background(self) -> None:
        path = self.root / "outlined-word.png"
        image = Image.new("RGB", (180, 56), "white")
        draw = ImageDraw.Draw(image)
        # One connected outlined word-like carrier with three counters.
        for left in (2, 55, 108):
            draw.rounded_rectangle(
                (left, 3, left + 68, 52), radius=13,
                outline=(245, 65, 25), width=3,
            )
        image.save(path)
        reir = build_reir(path)
        rows = []
        for token in reir.proposal_tokens:
            if token.family != "text":
                continue
            support = decode_token_mask(token, (reir.height, reir.width))
            if support is not None:
                rows.append((token, support))
        self.assertTrue(rows)
        self.assertTrue(all(float(mask.mean()) <= 0.65 for _token, mask in rows))
        self.assertTrue(any(
            topology_signature(mask)[1] >= 3 and float(mask.mean()) < 0.40
            for _token, mask in rows
        ))


class SupportMaskTests(unittest.TestCase):
    def test_rle_round_trip_contract(self) -> None:
        mask = decode_support_rle([[0, 2], [5, 3]], 4, 2)
        self.assertEqual(mask.astype(int).ravel().tolist(), [1, 1, 0, 0, 0, 1, 1, 1])

    def test_overlapping_runs_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid support RLE"):
            decode_support_rle([[0, 3], [2, 2]], 4, 2)

    def test_encoder_decoder_round_trip(self) -> None:
        expected = np.zeros((9, 13), dtype=bool)
        expected[1:5, 0:8] = True
        expected[6:, 10:] = True
        actual = decode_support_rle(encode_rle(expected), 13, 9)
        np.testing.assert_array_equal(actual, expected)

    def test_adaptive_source_mask_rejects_codec_halo(self) -> None:
        gt = np.zeros((24, 64), dtype=bool)
        gt[8:16, :] = True
        halo = np.zeros_like(gt)
        halo[6:18, :] = True
        rgba = np.full((24, 64, 4), 255, dtype=np.uint8)
        rgba[halo, :3] = 235
        rgba[gt, :3] = 20
        _source, proof = _best_support_alignment(rgba, gt)
        self.assertGreaterEqual(proof["minimum_coverage"], 0.99)
        self.assertGreaterEqual(proof["iou"], 0.99)

    def test_full_canvas_photometric_proof(self) -> None:
        rgb = np.full((24, 31, 3), 240, dtype=np.uint8)
        proof = _photometric_alignment(rgb, rgb.copy())
        self.assertEqual(proof["rgb_mae_255"], 0.0)
        self.assertAlmostEqual(proof["grayscale_ssim"], 1.0, places=5)

    def test_svg_render_uses_exact_height_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "aspect.svg"
            path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="301" height="100" '
                'viewBox="0 0 301 100"><rect width="301" height="100"/></svg>',
                encoding="utf-8",
            )
            rgba, mode = _render_svg_rgba(path, 482, 160)
        self.assertEqual(rgba.shape, (160, 482, 4))
        self.assertEqual(mode, "height_only")

    def test_opaque_svg_adapter_extracts_design_not_canvas(self) -> None:
        """An opaque SVG background must never become one fake glyph."""
        with tempfile.TemporaryDirectory() as directory:
            corpus = Path(directory)
            svg = corpus / "ring.svg"
            source = corpus / "ring.png"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" '
                'viewBox="0 0 64 64">'
                '<rect width="64" height="64" fill="white"/>'
                '<circle cx="32" cy="32" r="20" fill="black"/>'
                '<circle cx="32" cy="32" r="9" fill="white"/>'
                '</svg>',
                encoding="utf-8",
            )
            rgba, _mode = _render_svg_rgba(svg, 64, 64)
            Image.fromarray(rgba, mode="RGBA").save(source)
            manifest = {
                "schema": "pcdc-real-locus-corpus/v1",
                "total": 1,
                "loci": [{
                    "id": "opaque-ring",
                    "semantic_class": "text",
                    "source": {
                        "path": str(source),
                        "source_asset": str(svg),
                    },
                    "image": {"width": 64, "height": 64},
                }],
            }
            review = {
                "schema": "pcdc-real-locus-review/v1", "reviews": {}
            }
            (corpus / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            (corpus / "review.json").write_text(
                json.dumps(review), encoding="utf-8"
            )

            report = derive(corpus)
            persisted = json.loads(
                (corpus / "review.json").read_text(encoding="utf-8")
            )["reviews"]["opaque-ring"]

        self.assertEqual(report["derived_total"], 1)
        self.assertLess(persisted["support_area"], 64 * 64 * 0.65)
        self.assertEqual((persisted["components"], persisted["holes"]), (1, 1))
        self.assertIn("opaque_rgb", persisted["provenance"]["alignment"]["gt_mask_method"])
        self.assertEqual(
            persisted["provenance"]["adapter"],
            "owned-svg-ground-truth-adapter/v4",
        )


class TopologyRecallTests(unittest.TestCase):
    @staticmethod
    def _token(mask: np.ndarray):
        from types import SimpleNamespace

        return SimpleNamespace(
            support_bits=np.packbits(
                mask, axis=None, bitorder="little"
            ).tobytes(),
            support_rle=(),
            support_size=(mask.shape[1], mask.shape[0]),
        )

    @staticmethod
    def _reir(tokens):
        from types import SimpleNamespace

        labels = np.zeros((6, 8), dtype=np.int32)
        return SimpleNamespace(
            hierarchy=SimpleNamespace(
                leaf_labels=labels, leaf_count=1, nodes=()
            ),
            proposal_tokens=tuple(tokens),
        )

    def test_union_of_admissible_tokens_can_preserve_topology(self) -> None:
        support = np.zeros((6, 8), dtype=bool)
        support[1:5, 1:7] = True
        left = np.zeros_like(support)
        left[1:5, 1:4] = True
        right = np.zeros_like(support)
        right[1:5, 4:7] = True
        score = _topology_recall(
            self._reir((self._token(left), self._token(right))),
            support,
            np.zeros_like(support),
            1,
            0,
        )
        self.assertEqual(score, 1.0)

    def test_full_canvas_candidate_has_one_component_and_no_holes(self) -> None:
        support = np.ones((6, 8), dtype=bool)
        score = _topology_recall(
            self._reir(()), support, support.copy(), 1, 0
        )
        self.assertEqual(score, 1.0)


class LocalRefinementTests(unittest.TestCase):
    def test_transaction_splits_core_without_mutating_reir(self) -> None:
        labels = np.zeros((10, 12), dtype=np.int32)
        boundary = np.zeros((10, 12), dtype=bool)
        labels.setflags(write=False)
        boundary.setflags(write=False)
        complex_ = CellComplex(
            core_labels=labels,
            boundary_mask=boundary,
            cells=(),
            boundary_bands=(),
            microfeatures=(),
        )
        proposed = np.zeros((10, 12), dtype=bool)
        proposed[:, 6] = True
        transaction = plan_local_refinement(
            complex_, proposed, (0, 0, 12, 10), minimum_support=4
        )
        self.assertTrue(transaction.accepted)
        self.assertEqual(len(transaction.children), 2)
        self.assertFalse(np.any(complex_.boundary_mask))
        self.assertFalse(transaction.child_labels.flags.writeable)


if __name__ == "__main__":
    unittest.main()

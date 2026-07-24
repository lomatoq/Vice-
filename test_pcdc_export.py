from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np
from PIL import Image, ImageDraw

from vice_compiler.evidence_ir import build_reir
from vice_compiler.export_writer import (
    _free_curve_element, _mask_path, export_scene, render_shape_delivery,
    render_svg_roundtrip, render_svg_roundtrip_roi, scene_to_svg,
)
from vice_compiler.certificates import topology_signature
from vice_compiler.legacy_best import LegacyBestResolver
from vice_compiler.macro_extractor import extract_visible_scene
from vice_compiler.macro_ir import MacroKind, SceneProgram
from vice_compiler.macro_registry import (
    build_base_registry, candidate_from_support, extend_registry,
    rekey_draft_candidate,
)
from vice_compiler.visible_scene import build_visible_scene
from vice_compiler.runtime_service import _legacy_solution
from vice_compiler.production_court import RuntimeMacroCourt


class ProofCarryingExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "circle.png"
        image = Image.new("RGB", (96, 96), "white")
        ImageDraw.Draw(image).ellipse((20, 20, 76, 76), fill=(30, 80, 190))
        image.save(self.source)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _scene(self):
        reir = build_reir(self.source)
        y, x = np.indices((96, 96))
        support = (x - 48) ** 2 + (y - 48) ** 2 <= 28 ** 2
        candidate = candidate_from_support(
            reir, family="shape", mask=support, roi_xyxy=(20, 20, 77, 77),
            evidence_token_ids=(), score=4.0, provenance=("export-fixture",),
            kind=MacroKind.SHAPE, components=1, holes=0, prefix="export-circle",
        )
        self.assertIsNotNone(candidate)
        candidate = replace(
            candidate, program=SceneProgram("Shape/circle", (
                ("cx", 48.0), ("cy", 48.0), ("radius", 28.0),
            )), continuous_params=(("cx", 48.0), ("cy", 48.0), ("radius", 28.0)),
            covariance=(0.1, 0.1, 0.1),
        )
        candidate = rekey_draft_candidate(candidate, prefix="export-circle")
        cmir = extend_registry(reir, build_base_registry(reir), (candidate,))
        solution = extract_visible_scene(cmir, reir.hierarchy, time_budget_ms=100.0)
        self.assertIn(candidate.id, solution.selected_ids)
        return reir, cmir, build_visible_scene(cmir, solution)

    def test_native_svg_roundtrip_has_circle_and_no_embedded_raster(self) -> None:
        reir, cmir, scene = self._scene()
        svg, native, fallback = scene_to_svg(reir, cmir, scene)
        self.assertIn("<circle", svg)
        self.assertNotIn("<image", svg)
        self.assertGreaterEqual(native, 1)
        rendered = render_svg_roundtrip(svg, width=96)
        self.assertEqual(rendered.shape, (96, 96, 4))
        # The analytic center must retain the source blue, while the corner is
        # the independently estimated background.
        self.assertGreater(int(rendered[48, 48, 2]), int(rendered[48, 48, 0]))
        self.assertGreater(int(rendered[0, 0, :3].mean()), 240)

    def test_exact_roi_roundtrip_matches_the_same_full_svg_crop(self) -> None:
        reir, cmir, scene = self._scene()
        svg, _native, _fallback = scene_to_svg(reir, cmir, scene)
        full = render_svg_roundtrip(svg, width=96)
        roi = (13, 17, 81, 75)
        cropped = render_svg_roundtrip_roi(svg, roi_xyxy=roi)
        expected = full[17:75, 13:81]
        difference = np.abs(cropped.astype(np.int16) - expected.astype(np.int16))
        # Same renderer and integer pixel grid: only sub-quantum AA coverage
        # at vector boundaries may differ when resvg tiles the viewport.
        self.assertLessEqual(np.count_nonzero(difference) / difference.size, 0.005)
        self.assertLessEqual(int(difference.max(initial=0)), 32)
        np.testing.assert_array_equal(
            cropped[10:30, 10:30], expected[10:30, 10:30],
        )

    def test_thin_mask_path_uses_pixel_cells_without_stem_collapse(self) -> None:
        mask = np.zeros((24, 40), bool)
        mask[4:20, 4] = True; mask[4:20, 12] = True
        mask[11, 4:13] = True
        mask[4, 20:31] = True; mask[19, 20:31] = True
        mask[4:20, 20] = True; mask[4:20, 30] = True
        path = _mask_path(mask)
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="24" '
            'viewBox="0 0 40 24">'
            f'<path d="{path}" fill="#000" fill-rule="evenodd"/></svg>'
        )
        rendered = render_svg_roundtrip(svg, width=40)[..., 3] >= 128
        np.testing.assert_array_equal(rendered, mask)
        self.assertEqual(topology_signature(rendered), topology_signature(mask))

    def test_free_curve_court_delivery_is_the_final_serialized_element(self) -> None:
        reir = build_reir(self.source)
        y, x = np.indices((96, 96))
        support = (x - 48) ** 2 + (y - 48) ** 2 <= 40 ** 2
        candidate = candidate_from_support(
            reir, family="shape", mask=support,
            roi_xyxy=(8, 8, 89, 89), evidence_token_ids=(), score=4.0,
            provenance=("free-curve-delivery-fixture",), kind=MacroKind.SHAPE,
            components=1, holes=0, prefix="export-free-curve",
        )
        self.assertIsNotNone(candidate)
        candidate = replace(
            candidate, program=SceneProgram("Shape/free_curve", (
                ("contour_vertices", int(support.sum())),
                ("visible_color_union", 1),
            )), continuous_params=(("contour_vertices", float(support.sum())),),
            covariance=(0.1,),
        )
        candidate = rekey_draft_candidate(candidate, prefix="export-free-curve")
        element = _free_curve_element(reir, candidate, support)
        self.assertIsNotNone(element)
        delivery = render_shape_delivery(reir, candidate)
        self.assertIsNotNone(delivery)
        document = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" '
            f'viewBox="0 0 96 96">{element}</svg>'
        )
        serialized = render_svg_roundtrip(document, width=96)
        np.testing.assert_array_equal(delivery, serialized)
        delivered_mask = delivery[..., 3] >= 128
        self.assertEqual(topology_signature(delivered_mask), (1, 0))
        self.assertEqual(
            topology_signature(delivered_mask), topology_signature(support),
        )
        court = object.__new__(RuntimeMacroCourt)
        court.reir = reir
        court._shape = {candidate.id: SimpleNamespace(
            source_mask=support, rendered_mask=support, primitive="free_curve",
            boundary_p95_px=0.0, angular_coverage=1.0,
            candidate=candidate,
        )}
        court_delivery = court._delivered_masks(candidate)
        self.assertIsNotNone(court_delivery)
        _evidence, court_mask, _tolerance, _structural, exact_macro = court_delivery
        self.assertIsNotNone(exact_macro)
        np.testing.assert_array_equal(court_mask, delivered_mask)
        np.testing.assert_array_equal(
            np.rint(exact_macro[..., 3] * 255.0).astype(np.uint8),
            serialized[..., 3],
        )

    def test_unproved_small_free_curve_fails_closed(self) -> None:
        reir = build_reir(self.source)
        y, x = np.indices((96, 96))
        support = (x - 48) ** 2 + (y - 48) ** 2 <= 10 ** 2
        candidate = candidate_from_support(
            reir, family="shape", mask=support,
            roi_xyxy=(38, 38, 59, 59), evidence_token_ids=(), score=4.0,
            provenance=("free-curve-fail-closed-fixture",),
            kind=MacroKind.SHAPE, components=1, holes=0,
            prefix="export-free-curve-small",
        )
        self.assertIsNotNone(candidate)
        candidate = replace(
            candidate, program=SceneProgram("Shape/free_curve", (
                ("contour_vertices", int(support.sum())),
                ("visible_color_union", 1),
            )), continuous_params=(("contour_vertices", float(support.sum())),),
            covariance=(0.1,),
        )
        candidate = rekey_draft_candidate(
            candidate, prefix="export-free-curve-small",
        )
        self.assertIsNone(_free_curve_element(reir, candidate, support))
        self.assertIsNone(render_shape_delivery(reir, candidate))
        court = object.__new__(RuntimeMacroCourt)
        court.reir = reir
        court._shape = {candidate.id: SimpleNamespace(
            source_mask=support, rendered_mask=support, primitive="free_curve",
            boundary_p95_px=0.0, angular_coverage=1.0,
            candidate=candidate,
        )}
        self.assertIsNone(court._delivered_masks(candidate))

    def test_all_five_targets_are_real_files_and_vector_targets_are_editable(self) -> None:
        reir, cmir, scene = self._scene()
        for target in ("svg", "png", "pdf", "eps", "dxf"):
            artifact = export_scene(
                reir, cmir, scene, self.root / f"out.{target}", target=target,
            )
            self.assertEqual(artifact.target, target)
            self.assertGreater(artifact.bytes, 20)
            self.assertEqual(len(artifact.sha256), 64)
            self.assertEqual(artifact.raster_images_embedded, 0)
            if target != "png":
                self.assertGreater(artifact.editable_score, 0.0)

    def test_real_legacy_fallback_is_hash_checked_and_exported_exactly(self) -> None:
        source = self.root / "7_case_src.png"
        Image.new("RGB", (32, 24), "white").save(source)
        legacy_dir = self.root / "legacy" / "case" / source.stem
        legacy_dir.mkdir(parents=True)
        payload = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 24" '
            'width="32" height="24">\n'
            '<rect width="100%" height="100%" fill="#fff"/>\n'
            '<circle cx="16" cy="12" r="7" fill="#123456"/>\n</svg>\n'
        )
        (legacy_dir / "03_rebuilt_filled.svg").write_text(payload, "utf-8")
        (legacy_dir / "report.json").write_text(
            '{"input": "7_case_src.png"}', "utf-8",
        )
        reir = build_reir(source)
        artifact = LegacyBestResolver((self.root / "legacy",)).resolve(source, reir)
        self.assertIsNotNone(artifact)
        cmir = build_base_registry(reir, legacy_artifact=artifact)
        self.assertEqual(len(cmir.legacy_ids), 1)
        solution = _legacy_solution(cmir)
        self.assertFalse(solution.used_atomic_fallback)
        scene = build_visible_scene(cmir, solution)
        exported, native, fallback = scene_to_svg(reir, cmir, scene)
        self.assertEqual(exported, payload)
        self.assertEqual(native, 0)
        self.assertEqual(fallback, 2)


if __name__ == "__main__":
    unittest.main()

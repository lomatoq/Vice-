from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image, ImageDraw

from vice_compiler.abstraction_egraph import guarded_abstract
from vice_compiler.design_program import adapt_export_ir, build_design_program
from vice_compiler.evidence_ir import build_reir
from vice_compiler.export_writer import render_svg_roundtrip, scene_to_svg
from vice_compiler.macro_extractor import extract_visible_scene
from vice_compiler.macro_ir import MacroKind, SceneProgram
from vice_compiler.macro_registry import (
    build_base_registry, candidate_from_support, extend_registry,
    rekey_draft_candidate,
)
from vice_compiler.visible_scene import build_visible_scene


class DesignAbstractionPhase8Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _two_circle_fixture(self):
        path = Path(self.temp.name) / "repeat.png"
        image = Image.new("RGB", (140, 70), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 15, 40, 45), fill="black")
        draw.ellipse((80, 15, 110, 45), fill="black")
        image.save(path)
        reir = build_reir(path)
        y, x = np.indices((70, 140))
        candidates = []
        for index, cx in enumerate((25, 95)):
            support = (x - cx) ** 2 + (y - 30) ** 2 <= 15 ** 2
            candidate = candidate_from_support(
                reir, family="shape", mask=support,
                roi_xyxy=(cx - 15, 15, cx + 16, 46),
                evidence_token_ids=(), score=4.0,
                provenance=("phase8-repeat-fixture", str(index)),
                kind=MacroKind.SHAPE, components=1, holes=0,
                prefix="phase8-circle",
            )
            self.assertIsNotNone(candidate)
            candidate = replace(
                candidate,
                program=SceneProgram("Shape/circle", (
                    ("cx", float(cx)), ("cy", 30.0), ("radius", 15.0),
                )),
                continuous_params=(
                    ("cx", float(cx)), ("cy", 30.0), ("radius", 15.0),
                ), covariance=(1.0, 1.0, 1.0),
            )
            candidates.append(rekey_draft_candidate(
                candidate, prefix="phase8-circle",
            ))
        cmir = extend_registry(reir, build_base_registry(reir), candidates)
        solution = extract_visible_scene(cmir, reir.hierarchy, time_budget_ms=100.0)
        self.assertTrue(all(row.id in solution.selected_ids for row in candidates))
        scene = build_visible_scene(cmir, solution)
        return reir, cmir, scene, build_design_program(cmir, scene)

    def _two_circle_program(self):
        return self._two_circle_fixture()[3]

    def test_duplicate_instances_become_guarded_repeat_and_shrink_cost(self) -> None:
        program = self._two_circle_program()
        result = guarded_abstract(program, max_nodes=512)
        result.validate()
        reachable = {
            result.extracted.by_id()[node_id].operator
            for node_id in result.extracted.reachable_ids()
        }
        self.assertIn("Repeat", reachable)
        self.assertLess(result.cost_after.total, result.cost_before.total)
        accepted = [
            row for row in result.rewrites
            if row.sketch == "duplicate-instances-to-Repeat/Map" and row.accepted
        ]
        self.assertTrue(accepted)
        self.assertEqual(
            result.original.visible_owner_digest,
            result.extracted.visible_owner_digest,
        )

    def test_cheaper_abstraction_is_consumed_as_render_exact_svg_xir(self) -> None:
        reir, cmir, scene, program = self._two_circle_fixture()
        abstraction = guarded_abstract(program, max_nodes=512)
        flat, _flat_native, _flat_fallback = scene_to_svg(reir, cmir, scene)
        semantic, _native, _fallback = scene_to_svg(
            reir, cmir, scene, design_program=abstraction.extracted,
        )
        self.assertIn('data-pcdc-xir="Repeat"', semantic)
        self.assertNotEqual(flat, semantic)
        np.testing.assert_array_equal(
            render_svg_roundtrip(flat, width=reir.width),
            render_svg_roundtrip(semantic, width=reir.width),
        )

    def test_exact_concentric_cutout_becomes_ring(self) -> None:
        path = Path(self.temp.name) / "ring.png"
        image = Image.new("RGB", (96, 96), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((18, 18, 78, 78), fill="black")
        draw.ellipse((35, 35, 61, 61), fill="white")
        image.save(path)
        reir = build_reir(path)
        outer = np.zeros((96, 96), np.uint8)
        inner = np.zeros((96, 96), np.uint8)
        cv2.circle(outer, (48, 48), 30, 1, -1)
        cv2.circle(inner, (48, 48), 13, 1, -1)
        annulus = (outer > 0) & ~(inner > 0)
        rows = []
        for name, mask, radius, role, holes in (
            ("outer", annulus, 30.0, "outer", 1),
            ("inner", inner > 0, 13.0, "inner_cutout", 0),
        ):
            candidate = candidate_from_support(
                reir, family="shape", mask=mask,
                roi_xyxy=(18, 18, 79, 79), evidence_token_ids=(), score=4.0,
                provenance=("phase8-ring-fixture", name),
                kind=MacroKind.SHAPE, components=1, holes=holes,
                prefix=f"phase8-{name}",
            )
            self.assertIsNotNone(candidate)
            candidate = replace(candidate, program=SceneProgram("Shape/circle", (
                ("cx", 48.0), ("cy", 48.0), ("radius", radius), ("role", role),
            )), continuous_params=(
                ("cx", 48.0), ("cy", 48.0), ("radius", radius),
            ), covariance=(1.0, 1.0, 1.0))
            rows.append(rekey_draft_candidate(candidate, prefix=f"phase8-{name}"))
        cmir = extend_registry(reir, build_base_registry(reir), rows)
        solution = extract_visible_scene(cmir, reir.hierarchy, time_budget_ms=100.0)
        self.assertTrue(all(row.id in solution.selected_ids for row in rows))
        program = build_design_program(cmir, build_visible_scene(cmir, solution))
        result = guarded_abstract(program, max_nodes=512)
        reachable = {
            result.extracted.by_id()[node_id].operator
            for node_id in result.extracted.reachable_ids()
        }
        self.assertIn("Ring", reachable)

    def test_near_circle_free_curve_is_never_an_egraph_idealization(self) -> None:
        path = Path(self.temp.name) / "free.png"
        image = Image.new("RGB", (72, 72), "white")
        draw = ImageDraw.Draw(image)
        draw.polygon(((18, 35), (25, 18), (46, 16), (57, 34),
                      (49, 55), (27, 57)), fill="black")
        image.save(path)
        reir = build_reir(path)
        support = np.asarray(image.convert("L")) < 128
        candidate = candidate_from_support(
            reir, family="shape", mask=support,
            roi_xyxy=(16, 16, 58, 58), evidence_token_ids=(), score=4.0,
            provenance=("phase8-near-circle-fixture",), kind=MacroKind.SHAPE,
            components=1, holes=0, prefix="phase8-free",
        )
        self.assertIsNotNone(candidate)
        candidate = replace(candidate, program=SceneProgram("Shape/free_curve", (
            ("contour_vertices", 6), ("circularity", 0.99),
        )))
        candidate = rekey_draft_candidate(candidate, prefix="phase8-free")
        cmir = extend_registry(reir, build_base_registry(reir), (candidate,))
        solution = extract_visible_scene(cmir, reir.hierarchy)
        self.assertIn(candidate.id, solution.selected_ids)
        program = build_design_program(cmir, build_visible_scene(cmir, solution))
        result = guarded_abstract(program)
        self.assertTrue(any(
            row.sketch == "near-circle-to-perfect-circle"
            and not row.accepted and row.guard.startswith("forbidden")
            for row in result.rewrites
        ))
        self.assertFalse(any(
            node.operator == "Circle"
            and candidate.id in node.source_macro_ids
            for node in result.extracted.nodes
        ))

    def test_one_design_program_adapts_to_all_export_structures(self) -> None:
        program = guarded_abstract(self._two_circle_program(), max_nodes=512).extracted
        for target in ("svg", "eps", "pdf", "dxf", "png"):
            export = adapt_export_ir(program, target=target, mode="native")
            export.validate()
            self.assertEqual(export.source_program_digest, program.program_digest)
        for mode in ("flattened", "cutout", "stacked", "gap-filler"):
            export = adapt_export_ir(program, target="svg", mode=mode)
            export.validate()
            self.assertEqual(export.mode, mode)


if __name__ == "__main__":
    unittest.main()

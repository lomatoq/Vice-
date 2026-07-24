from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image, ImageDraw

from vice_compiler.continuous_refine import refine_selected_scene
from vice_compiler.evidence_ir import build_reir
from vice_compiler.macro_extractor import extract_visible_scene
from vice_compiler.macro_ir import MacroKind, SceneProgram
from vice_compiler.macro_registry import (
    build_base_registry, candidate_from_support, extend_registry,
    rekey_draft_candidate,
)
from vice_compiler.visible_scene import build_visible_scene


class ContinuousRefinementPhase7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _circle_scene(self):
        path = Path(self.temp.name) / "circle.png"
        image = Image.new("RGB", (96, 96), "white")
        ImageDraw.Draw(image).ellipse((27, 27, 69, 69), fill="black")
        image.save(path)
        reir = build_reir(path)
        y, x = np.indices((96, 96))
        support = (x - 48) ** 2 + (y - 48) ** 2 <= 21 ** 2
        candidate = candidate_from_support(
            reir, family="shape", mask=support,
            roi_xyxy=(27, 27, 70, 70), evidence_token_ids=(), score=4.0,
            provenance=("phase7-circle-fixture",), kind=MacroKind.SHAPE,
            components=1, holes=0, prefix="phase7-circle",
        )
        self.assertIsNotNone(candidate)
        candidate = replace(
            candidate,
            program=SceneProgram("Shape/circle", (
                ("cx", 46.0), ("cy", 49.5), ("radius", 18.0),
            )),
            continuous_params=(("cx", 46.0), ("cy", 49.5), ("radius", 18.0)),
            covariance=(4.0, 4.0, 9.0),
        )
        candidate = rekey_draft_candidate(candidate, prefix="phase7-circle")
        cmir = extend_registry(reir, build_base_registry(reir), (candidate,))
        solution = extract_visible_scene(cmir, reir.hierarchy, time_budget_ms=100.0)
        self.assertIn(candidate.id, solution.selected_ids)
        return reir, cmir, build_visible_scene(cmir, solution), candidate

    def test_sparse_refinement_improves_native_circle_without_discrete_changes(self) -> None:
        reir, cmir, scene, candidate = self._circle_scene()
        owners_before = scene.owner_by_leaf
        result = refine_selected_scene(
            reir, cmir, scene, max_iterations=30, samples_per_shape=64,
        )
        result.validate()
        refined = next(row for row in result.macros if row.macro_id == candidate.id)
        values = dict(refined.refined_params)
        self.assertTrue(refined.committed)
        self.assertAlmostEqual(values["cx"], 48.0, delta=0.08)
        self.assertAlmostEqual(values["cy"], 48.0, delta=0.08)
        self.assertAlmostEqual(values["radius"], 21.0, delta=0.12)
        self.assertLess(refined.native_error_after, refined.native_error_before)
        self.assertLess(result.final_cost, result.initial_cost)
        self.assertEqual(owners_before, scene.owner_by_leaf)
        self.assertEqual(result.selected_ids, scene.selected_macro_ids)
        self.assertLessEqual(result.function_evaluations, 30)
        self.assertIn(
            "SDF+render_residual", {factor.kind for factor in result.factors},
        )

    def test_physical_arclength_weighting_is_sampling_invariant(self) -> None:
        reir, cmir, scene, candidate = self._circle_scene()
        coarse = refine_selected_scene(
            reir, cmir, scene, max_iterations=30, samples_per_shape=64,
        )
        dense = refine_selected_scene(
            reir, cmir, scene, max_iterations=30, samples_per_shape=256,
        )
        coarse_values = dict(next(
            row for row in coarse.macros if row.macro_id == candidate.id
        ).refined_params)
        dense_values = dict(next(
            row for row in dense.macros if row.macro_id == candidate.id
        ).refined_params)
        for name in ("cx", "cy", "radius"):
            self.assertAlmostEqual(coarse_values[name], dense_values[name], delta=0.05)

    def test_topology_certificate_violation_rolls_back_macro(self) -> None:
        path = Path(self.temp.name) / "ring.png"
        image = Image.new("RGB", (96, 96), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((22, 22, 74, 74), fill="black")
        draw.ellipse((38, 38, 58, 58), fill="white")
        image.save(path)
        reir = build_reir(path)
        support = np.zeros((96, 96), np.uint8)
        cv2.circle(support, (48, 48), 26, 1, -1)
        cv2.circle(support, (48, 48), 10, 0, -1)
        candidate = candidate_from_support(
            reir, family="shape", mask=support > 0,
            roi_xyxy=(22, 22, 75, 75), evidence_token_ids=(), score=4.0,
            provenance=("phase7-rollback-fixture",), kind=MacroKind.SHAPE,
            components=1, holes=1, prefix="phase7-bad-circle",
        )
        self.assertIsNotNone(candidate)
        # Deliberately incompatible type: a circle program cannot satisfy the
        # certified ring topology, so the transaction must not commit it.
        candidate = replace(
            candidate,
            program=SceneProgram("Shape/circle", (
                ("cx", 48.0), ("cy", 48.0), ("radius", 24.0),
            )),
            continuous_params=(("cx", 48.0), ("cy", 48.0), ("radius", 24.0)),
            covariance=(1.0, 1.0, 4.0),
        )
        candidate = rekey_draft_candidate(candidate, prefix="phase7-bad-circle")
        cmir = extend_registry(reir, build_base_registry(reir), (candidate,))
        solution = extract_visible_scene(cmir, reir.hierarchy, time_budget_ms=100.0)
        self.assertIn(candidate.id, solution.selected_ids)
        scene = build_visible_scene(cmir, solution)
        result = refine_selected_scene(reir, cmir, scene, max_iterations=20)
        row = next(item for item in result.macros if item.macro_id == candidate.id)
        self.assertFalse(row.committed)
        self.assertEqual(row.rollback_reason, "certificate-topology-violation")
        self.assertEqual(row.refined_program, row.original_program)

    def test_common_graph_has_area_symmetry_and_pairwise_interface_factors(self) -> None:
        path = Path(self.temp.name) / "shared-interface.png"
        image = Image.new("RGB", (96, 56), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 10, 47, 45), fill=(20, 20, 20))
        draw.rectangle((48, 10, 87, 45), fill=(95, 95, 95))
        image.save(path)
        reir = build_reir(path)
        candidates = []
        for index, (x1, x2) in enumerate(((8, 48), (48, 88))):
            support = np.zeros((56, 96), bool)
            support[10:46, x1:x2] = True
            candidate = candidate_from_support(
                reir, family="shape", mask=support,
                roi_xyxy=(x1, 10, x2, 46), evidence_token_ids=(),
                score=4.0, provenance=(f"phase7-interface-{index}",),
                kind=MacroKind.SHAPE, components=1, holes=0,
                prefix=f"phase7-interface-{index}",
            )
            self.assertIsNotNone(candidate)
            assert candidate is not None
            candidate = replace(
                candidate,
                program=SceneProgram("Shape/rectangle", (
                    ("x", float(x1)), ("y", 10.0),
                    ("width", float(x2 - x1)), ("height", 36.0),
                )),
                continuous_params=(
                    ("x", float(x1)), ("y", 10.0),
                    ("width", float(x2 - x1)), ("height", 36.0),
                ),
                covariance=(0.25, 0.25, 0.5, 0.5),
            )
            candidates.append(rekey_draft_candidate(
                candidate, prefix=f"phase7-interface-{index}",
            ))
        cmir = extend_registry(
            reir, build_base_registry(reir), tuple(candidates),
        )
        solution = extract_visible_scene(
            cmir, reir.hierarchy, time_budget_ms=100.0,
        )
        self.assertTrue(all(
            candidate.id in solution.selected_ids for candidate in candidates
        ))
        scene = build_visible_scene(cmir, solution)
        result = refine_selected_scene(
            reir, cmir, scene, max_iterations=8,
        )
        kinds = {factor.kind for factor in result.factors}
        self.assertIn("coverage_render_residual", kinds)
        self.assertIn("symmetry_x_axis_evidence", kinds)
        self.assertIn("pairwise_shared_interface", kinds)
        result.validate()

    def test_free_curve_anchors_receive_sdf_g1_g2_and_coverage_factors(self) -> None:
        path = Path(self.temp.name) / "parametric-free-curve.png"
        image = Image.new("RGB", (96, 96), "white")
        ImageDraw.Draw(image).ellipse((18, 28, 78, 68), fill="black")
        image.save(path)
        reir = build_reir(path)
        support = np.zeros((96, 96), np.uint8)
        cv2.ellipse(support, (48, 48), (30, 20), 0, 0, 360, 1, -1)
        candidate = candidate_from_support(
            reir, family="shape", mask=support > 0,
            roi_xyxy=(18, 28, 79, 69), evidence_token_ids=(), score=4.0,
            provenance=("phase7-free-curve-fixture",), kind=MacroKind.SHAPE,
            components=1, holes=0, prefix="phase7-free-curve",
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        points = tuple(
            (
                48.0 + 30.0 * float(np.cos(angle)),
                48.0 + 20.0 * float(np.sin(angle)),
            )
            for angle in np.linspace(0.0, 2.0 * np.pi, 12, endpoint=False)
        )
        continuous = tuple(
            (f"curve_p{index}_{axis}", float(point[coordinate]))
            for index, point in enumerate(points)
            for coordinate, axis in enumerate(("x", "y"))
        )
        parameters = (
            ("curve_point_count", len(points)), ("curve_tension", 1.0),
            *continuous,
        )
        candidate = replace(
            candidate,
            program=SceneProgram("Shape/free_curve", parameters),
            continuous_params=(("curve_tension", 1.0), *continuous),
            covariance=(0.01, *(0.25 for _row in continuous)),
        )
        candidate = rekey_draft_candidate(
            candidate, prefix="phase7-free-curve",
        )
        cmir = extend_registry(reir, build_base_registry(reir), (candidate,))
        solution = extract_visible_scene(
            cmir, reir.hierarchy, time_budget_ms=100.0,
        )
        self.assertIn(candidate.id, solution.selected_ids)
        scene = build_visible_scene(cmir, solution)
        result = refine_selected_scene(
            reir, cmir, scene, max_iterations=4, samples_per_shape=32,
        )
        kinds = {factor.kind for factor in result.factors}
        self.assertIn("curve_control_point_SDF", kinds)
        self.assertIn("curve_G1_structural+G2_curvature", kinds)
        self.assertIn("coverage_render_residual", kinds)
        result.validate()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw

from vice_compiler.evidence_ir import build_reir
from vice_compiler.layer_solver import (
    LayerOrderCue, build_layered_scene, solve_layer_order,
)
from vice_compiler.macro_extractor import extract_visible_scene
from vice_compiler.macro_ir import MacroKind, SceneProgram
from vice_compiler.macro_registry import (
    build_base_registry, candidate_from_support, extend_registry,
    rekey_draft_candidate,
)
from vice_compiler.visible_scene import build_visible_scene


class LayerPhase6Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_visible_ownership_is_frozen_before_typed_hidden_completion(self) -> None:
        path = Path(self.temp.name) / "occlusion.png"
        image = Image.new("RGB", (128, 96), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((18, 20, 74, 76), fill=(220, 40, 40))
        draw.rectangle((50, 14, 108, 82), fill=(30, 80, 210))
        image.save(path)
        reir = build_reir(path)

        y, x = np.indices((96, 128))
        full_circle = (x - 46) ** 2 + (y - 48) ** 2 <= 28 ** 2
        rectangle = np.zeros((96, 128), bool)
        rectangle[14:83, 50:109] = True
        visible_circle = full_circle & ~rectangle

        circle = candidate_from_support(
            reir, family="shape", mask=visible_circle,
            roi_xyxy=(18, 20, 75, 77), evidence_token_ids=(), score=4.0,
            provenance=("phase6-test-circle",), kind=MacroKind.SHAPE,
            components=1, holes=0, prefix="phase6-circle",
        )
        self.assertIsNotNone(circle)
        circle = replace(circle, program=SceneProgram("Shape/circle", (
            ("cx", 46.0), ("cy", 48.0), ("radius", 28.0),
        )))
        circle = rekey_draft_candidate(circle, prefix="phase6-circle")

        occluder = candidate_from_support(
            reir, family="shape", mask=rectangle,
            roi_xyxy=(50, 14, 109, 83), evidence_token_ids=(), score=4.0,
            provenance=("phase6-test-occluder",), kind=MacroKind.SHAPE,
            components=1, holes=0, prefix="phase6-rectangle",
        )
        self.assertIsNotNone(occluder)
        occluder = replace(occluder, program=SceneProgram("Shape/rectangle", (
            ("x", 50), ("y", 14), ("width", 59), ("height", 69),
        )))
        occluder = rekey_draft_candidate(occluder, prefix="phase6-rectangle")

        cmir = extend_registry(
            reir, build_base_registry(reir), (circle, occluder),
        )
        solution = extract_visible_scene(cmir, reir.hierarchy, time_budget_ms=200.0)
        self.assertIn(circle.id, solution.selected_ids)
        self.assertIn(occluder.id, solution.selected_ids)
        visible = build_visible_scene(cmir, solution)
        owners_before = visible.owner_by_leaf

        layered = build_layered_scene(reir, cmir, visible)
        layered.validate(reir, cmir)
        self.assertEqual(owners_before, layered.visible_scene.owner_by_leaf)
        self.assertIn("visible-support-finalized-first", layered.provenance)
        self.assertTrue(any(
            edge.back_id == circle.id and edge.front_id == occluder.id
            for edge in layered.order_graph.edges
        ))
        completion = next(
            row for row in layered.hidden_completions
            if row.source_macro_id == circle.id
            and row.occluder_macro_id == occluder.id
        )
        self.assertEqual(completion.primitive, "circle")
        self.assertGreater(int(completion.hidden_mask.sum()), 100)
        self.assertTrue(np.all(completion.hidden_mask <= rectangle))
        self.assertTrue(layered.render_check.valid)
        self.assertTrue(layered.render_check.opaque_occlusion_proof)
        self.assertGreater(layered.render_check.hidden_pixels, 100)
        self.assertLessEqual(
            layered.render_check.rmse,
            layered.render_check.baseline_rmse + 0.0025,
        )
        self.assertLessEqual(
            sum(abs(a - b) for a, b in zip(
                layered.render_check.rendered_topology,
                layered.render_check.source_topology,
            )),
            sum(abs(a - b) for a, b in zip(
                layered.render_check.baseline_topology,
                layered.render_check.source_topology,
            )),
        )
        self.assertTrue(layered.background_proposals)

    def test_confidence_weighted_order_rejects_lowest_cycle_edge(self) -> None:
        graph = solve_layer_order(("a", "b", "c"), (
            LayerOrderCue("a", "b", 0.90, "typed-contour-continuation"),
            LayerOrderCue("b", "c", 0.80, "text-top-layer-prior"),
            LayerOrderCue("c", "a", 0.60, "weak-T-junction"),
        ))
        graph.validate()
        self.assertEqual(len(graph.edges), 2)
        self.assertEqual(len(graph.rejected_cycle_edges), 1)
        self.assertEqual(graph.rejected_cycle_edges[0].back_id, "c")
        self.assertEqual(graph.rejected_cycle_edges[0].front_id, "a")
        self.assertEqual(graph.local_alternative_components, 1)

    def test_local_cycle_alternative_beats_greedy_edge_insertion(self) -> None:
        graph = solve_layer_order(("a", "b", "c", "d"), (
            LayerOrderCue("a", "b", 0.90, "ab"),
            LayerOrderCue("b", "c", 0.90, "bc"),
            LayerOrderCue("c", "a", 0.89, "ca"),
            LayerOrderCue("c", "d", 0.90, "cd"),
            LayerOrderCue("d", "b", 0.89, "db"),
        ))
        graph.validate()
        accepted = {(row.back_id, row.front_id) for row in graph.edges}
        self.assertEqual(accepted, {
            ("a", "b"), ("c", "a"), ("c", "d"), ("d", "b"),
        })
        self.assertAlmostEqual(graph.orientation_objective, 3.58)
        self.assertEqual(graph.local_alternative_components, 1)

    def test_transparent_canvas_is_an_explicit_background_candidate(self) -> None:
        path = Path(self.temp.name) / "transparent.png"
        image = Image.new("RGBA", (80, 64), (0, 0, 0, 0))
        ImageDraw.Draw(image).ellipse((20, 12, 60, 52), fill=(15, 80, 190, 255))
        image.save(path)
        reir = build_reir(path)
        cmir = build_base_registry(reir)
        solution = extract_visible_scene(cmir, reir.hierarchy)
        visible = build_visible_scene(cmir, solution)
        self.assertTrue(any(
            row.translucent_contributors and row.background_id
            for row in visible.paint_ownership_by_leaf
        ))
        self.assertTrue(all(
            len(row.translucent_contributors) <= row.contribution_limit
            for row in visible.paint_ownership_by_leaf
        ))
        layered = build_layered_scene(reir, cmir, visible)
        self.assertIn(
            "transparent_canvas",
            {row.kind for row in layered.background_proposals},
        )
        self.assertEqual(layered.selected_background.kind, "transparent_canvas")


if __name__ == "__main__":
    unittest.main()

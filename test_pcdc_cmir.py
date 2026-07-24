from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw

from vice_compiler.atlas_renderer import ExactRoiAtlas
from vice_compiler.cell_complex import plan_local_refinement
from vice_compiler.certificates import mask_sha256, seal_bundle
from vice_compiler.column_generation import run_column_generation
from vice_compiler.conflict_components import typed_conflict_components
from vice_compiler.evidence_ir import build_reir
from vice_compiler.export_writer import _candidate_support
from vice_compiler.hierarchy_dp import solve_hierarchy_dp
from vice_compiler.experiment3_certificate_discrimination import _make_pair
from vice_compiler.local_court import compare_in_local_court
from vice_compiler.local_refinement_lattice import materialize_local_refinements
from vice_compiler.macro_extractor import (
    extract_visible_scene, rollback_conflict_components,
)
from vice_compiler.macro_ir import MacroKind, registry_digest
from vice_compiler.macro_registry import (
    build_base_registry, candidate_from_support, extend_registry,
)
from vice_compiler.visible_scene import build_visible_scene
from vice_compiler.renderer_posterior import synthetic_renderer_posterior


class CmirPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "fixture.png"
        image = Image.new("RGBA", (96, 64), (250, 250, 250, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((7, 8, 44, 54), fill=(25, 40, 210, 255))
        draw.ellipse((52, 12, 87, 49), fill=(220, 35, 30, 255))
        image.save(self.path)
        self.reir = build_reir(self.path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_base_registry_has_symmetric_conflicts_and_atomic_cover(self) -> None:
        cmir = build_base_registry(self.reir)
        cmir.validate()
        self.assertNotEqual(
            cmir.registry_hash,
            registry_digest(cmir.candidates),
        )
        self.assertEqual(len(cmir.atomic_ids), self.reir.hierarchy.leaf_count)
        atomic = [candidate for candidate in cmir.candidates
                  if candidate.kind is MacroKind.ATOMIC_FALLBACK]
        self.assertEqual(
            sum(candidate.core_bits for candidate in atomic),
            (1 << cmir.leaf_count) - 1,
        )

    def test_hierarchy_dp_is_an_exact_cover(self) -> None:
        cmir = build_base_registry(self.reir)
        solution = solve_hierarchy_dp(cmir, self.reir.hierarchy)
        self.assertTrue(solution.feasible)
        self.assertEqual(
            solution.covered_bits, (1 << cmir.leaf_count) - 1
        )

    def test_oracle_macro_replaces_base_without_losing_feasibility(self) -> None:
        cmir = build_base_registry(self.reir)
        mask = np.zeros((self.reir.height, self.reir.width), dtype=bool)
        mask[8:55, 7:45] = True
        oracle = candidate_from_support(
            self.reir, family="small_shape", mask=mask,
            roi_xyxy=(7, 8, 45, 55), evidence_token_ids=(),
            score=4.0, provenance=("unit-test-oracle",),
            kind=MacroKind.ORACLE, components=1, holes=0,
            prefix="oracle-test",
        )
        self.assertIsNotNone(oracle)
        cmir = extend_registry(self.reir, cmir, (oracle,))
        components = typed_conflict_components(cmir)
        self.assertEqual(len(components), 1)
        solution = extract_visible_scene(cmir, self.reir.hierarchy)
        self.assertTrue(solution.feasible)
        self.assertTrue(solution.fallback_always_feasible)
        self.assertIn(oracle.id, solution.selected_ids)
        scene = build_visible_scene(cmir, solution)
        scene.validate(cmir)

    def test_master_selection_is_independent_of_wall_clock_jitter(self) -> None:
        base = build_base_registry(self.reir)
        mask = np.zeros((self.reir.height, self.reir.width), dtype=bool)
        mask[8:55, 7:45] = True
        alternatives = []
        for index in range(12):
            candidate = candidate_from_support(
                self.reir, family="small_shape", mask=mask,
                roi_xyxy=(7, 8, 45, 55), evidence_token_ids=(),
                score=4.0 - 0.05 * index,
                provenance=("deterministic-master-fixture", str(index)),
                kind=MacroKind.ORACLE, components=1, holes=0,
                prefix=f"deterministic-oracle-{index}",
            )
            self.assertIsNotNone(candidate)
            alternatives.append(candidate)
        cmir = extend_registry(self.reir, base, tuple(alternatives))
        with patch(
            "vice_compiler.macro_extractor.time.perf_counter",
            side_effect=(0.0, 1000.0),
        ):
            loaded = extract_visible_scene(
                cmir, self.reir.hierarchy, time_budget_ms=1.0,
            )
        with patch(
            "vice_compiler.macro_extractor.time.perf_counter",
            side_effect=(0.0, 0.00001),
        ):
            idle = extract_visible_scene(
                cmir, self.reir.hierarchy, time_budget_ms=1.0,
            )
        self.assertEqual(loaded.selected_ids, idle.selected_ids)
        self.assertEqual(loaded.utility, idle.utility)
        self.assertEqual(
            loaded.fallback_reason,
            "deterministic-work-budget-returned-valid-best",
        )

    def test_column_generation_is_bounded_and_has_no_manual_risk_gate(self) -> None:
        result = run_column_generation(
            self.reir, rounds=3, max_columns_per_oracle=4,
            extraction_budget_ms=80.0,
        )
        self.assertTrue(result.solution.feasible)
        self.assertFalse(result.used_manual_risk_threshold)
        self.assertLessEqual(
            result.final_columns - result.initial_columns,
            3 * 7 * 4,
        )
        self.assertTrue(any(record.generated_columns for record in result.rounds))

    def test_marginal_rollback_reextracts_only_blamed_conflict_component(self) -> None:
        base = build_base_registry(self.reir)
        rectangle = np.zeros((self.reir.height, self.reir.width), bool)
        rectangle[8:55, 7:45] = True
        circle_y, circle_x = np.indices((self.reir.height, self.reir.width))
        circle = (circle_x - 70) ** 2 + (circle_y - 31) ** 2 <= 18 ** 2
        rows = []
        for name, mask, roi in (
            ("rectangle", rectangle, (7, 8, 45, 55)),
            ("circle", circle, (52, 12, 89, 50)),
        ):
            candidate = candidate_from_support(
                self.reir, family="small_shape", mask=mask,
                roi_xyxy=roi, evidence_token_ids=(), score=4.0,
                provenance=("marginal-rollback-fixture", name),
                kind=MacroKind.ORACLE, components=1, holes=0,
                prefix=f"rollback-{name}",
            )
            self.assertIsNotNone(candidate); rows.append(candidate)
        cmir = extend_registry(self.reir, base, rows)
        incumbent = extract_visible_scene(cmir, self.reir.hierarchy)
        self.assertTrue(all(row.id in incumbent.selected_ids for row in rows))
        rollback = rollback_conflict_components(
            cmir, self.reir.hierarchy, incumbent, (rows[0].id,),
        )
        self.assertNotIn(rows[0].id, rollback.solution.selected_ids)
        self.assertIn(rows[1].id, rollback.solution.selected_ids)
        self.assertEqual(rollback.retained_typed_ids, (rows[1].id,))
        self.assertTrue(rollback.solution.exact_cover)

    def test_court_selected_boundary_materializes_child_fallback_cells(self) -> None:
        # Bind a genuine sealed local-court proof to a typed column.
        posterior = synthetic_renderer_posterior(source_id="refinement-unit")
        atlas = ExactRoiAtlas()
        pair = _make_pair("ideal_circle_vs_jagged_overfit", 2, posterior, atlas)
        decision = compare_in_local_court(
            pair.observed, pair.evidence_support,
            pair.correct, pair.competitor, posterior, atlas=atlas,
        )
        self.assertTrue(decision.candidate_selected)
        delivery = np.zeros((self.reir.height, self.reir.width), bool)
        delivery[12:50, 20:76] = True
        draft = candidate_from_support(
            self.reir, family="shape", mask=delivery,
            roi_xyxy=(20, 12, 76, 50), evidence_token_ids=(), score=4.0,
            provenance=("local-refinement-unit",), kind=MacroKind.ORACLE,
            prefix="refinement-oracle",
        )
        self.assertIsNotNone(draft)
        # Court bundles are identity-bound.  Rebind the fixture identity while
        # retaining this candidate's actual ownership/support contract.
        from dataclasses import replace
        proof = seal_bundle(replace(
            decision.candidate_bundle, candidate_id=draft.id,
            support=replace(
                decision.candidate_bundle.support,
                support_size=(self.reir.width, self.reir.height),
                roi_xyxy=(0, 0, self.reir.width, self.reir.height),
                support_sha256=mask_sha256(
                    np.ones((self.reir.height, self.reir.width), bool)
                ),
                support_pixels=self.reir.width * self.reir.height,
                scored_pixels=self.reir.width * self.reir.height,
                core_bits=draft.core_bits,
                interface_ids=draft.boundary_interfaces,
            ),
            digest="",
        ))
        certified = draft.with_proof_bundle(proof)
        boundary = cv2.morphologyEx(
            delivery.astype(np.uint8), cv2.MORPH_GRADIENT,
            np.ones((3, 3), np.uint8),
        ) > 0
        transaction = plan_local_refinement(
            self.reir.cells, boundary, (0, 0, self.reir.width, self.reir.height),
        )
        self.assertTrue(transaction.accepted)

        class FakeCourt:
            def refinement_transaction(self, candidate_id):
                return transaction if candidate_id == certified.id else None

            def delivery_mask(self, candidate_id):
                return delivery if candidate_id == certified.id else None

        cmir = extend_registry(
            self.reir, build_base_registry(self.reir), (certified,),
        )
        refined = materialize_local_refinements(
            self.reir, cmir, FakeCourt(), maximum_cells=256,
        )
        refined.cmir.validate()
        self.assertGreater(refined.cmir.leaf_count, cmir.leaf_count)
        self.assertEqual(len(refined.cmir.atomic_ids), refined.cmir.leaf_count)
        remapped = refined.cmir.by_id()[certified.id]
        self.assertNotEqual(
            remapped.core_bits, (1 << refined.cmir.leaf_count) - 1,
        )
        solution = extract_visible_scene(refined.cmir, self.reir.hierarchy)
        self.assertTrue(solution.exact_cover)
        self.assertIn(certified.id, solution.selected_ids)
        self.assertTrue(any(
            refined.cmir.by_id()[candidate_id].kind is MacroKind.ATOMIC_FALLBACK
            for candidate_id in solution.selected_ids
        ))
        scene = build_visible_scene(refined.cmir, solution)
        self.assertEqual(
            len(scene.interface_geometry), refined.cmir.interface_count,
        )
        lookup = refined.cmir.by_id()
        for geometry in scene.interface_geometry:
            self.assertEqual(
                geometry.active_boundary,
                geometry.owner_a != geometry.owner_b,
            )
            if geometry.active_boundary:
                self.assertIn(
                    geometry.interface_id,
                    lookup[geometry.owner_a].boundary_interfaces,
                )
                self.assertIn(
                    geometry.interface_id,
                    lookup[geometry.owner_b].boundary_interfaces,
                )
            else:
                self.assertNotIn(
                    geometry.interface_id,
                    lookup[geometry.owner_a].boundary_interfaces,
                )

        class NoBoundaryHintCourt:
            def refinement_transaction(self, candidate_id):
                return None

            def delivery_mask(self, candidate_id):
                return delivery if candidate_id == certified.id else None

        # Regression: an exact delivered ownership must be inserted even when
        # the old boundary-only planner says it does not split a stripped core
        # cell.  Otherwise a tiny core claim can paint a much larger SVG shape.
        no_hint = materialize_local_refinements(
            self.reir, cmir, NoBoundaryHintCourt(), maximum_cells=256,
        )
        remapped = no_hint.cmir.by_id()[certified.id]
        owned = np.zeros_like(delivery)
        for atomic in no_hint.cmir.candidates:
            if (
                atomic.kind is MacroKind.ATOMIC_FALLBACK
                and atomic.core_bits & remapped.core_bits
            ):
                owned |= _candidate_support(self.reir, atomic)
        np.testing.assert_array_equal(owned, delivery)


if __name__ == "__main__":
    unittest.main()

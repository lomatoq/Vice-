from __future__ import annotations

import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw

from vice_compiler.appearance_macros import generate_appearance_macros
from vice_compiler.atlas_renderer import ExactRoiAtlas
from vice_compiler.certificates import mask_sha256, topology_signature
from vice_compiler.cleanup_macros import generate_cleanup_macros
from vice_compiler.evidence_ir import build_reir
from vice_compiler.export_writer import (
    render_appearance_delivery,
    render_codec_delivery,
    render_group_delivery,
    render_shape_delivery,
    render_stroke_delivery,
)
from vice_compiler.macro_ir import MacroKind, SceneProgram
from vice_compiler.macro_registry import build_base_registry, extend_registry
from vice_compiler.master_problem import MasterSolution
from vice_compiler.phase5_macros import (
    Phase5Budgets,
    extract_phase5_scene,
    generate_phase5_macros,
)
from vice_compiler.production_court import RuntimeMacroCourt
from vice_compiler.proposal_net import ProposalQuery
from vice_compiler.shape_macros import (
    generate_shape_macros,
    materialize_repeated_group_members,
)
from vice_compiler.stroke_macros import generate_stroke_macros
from vice_compiler.text_macros import TextMacroSet, generate_text_macros
from vice_compiler.visible_scene import build_visible_scene


class WholeShapePhase5Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "shapes.png"
        image = Image.new("RGB", (220, 100), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 10, 38, 40), fill="black")
        draw.ellipse((48, 10, 78, 40), fill="black")
        draw.ellipse((90, 8, 128, 46), fill="black")
        draw.ellipse((100, 18, 118, 36), fill="white")
        draw.rounded_rectangle((140, 8, 205, 44), radius=10, fill="black")
        draw.polygon(((20, 88), (48, 50), (76, 88)), fill="black")
        image.save(self.path)
        self.reir = build_reir(self.path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_shape_fits_are_native_bounded_certified_columns(self) -> None:
        started = time.perf_counter()
        generated = generate_shape_macros(
            self.reir, max_rois=64, max_per_roi=4,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.assertTrue(generated.records)
        self.assertLessEqual(generated.rois_considered, 64)
        self.assertLessEqual(len(generated.records), 64 * 4)
        self.assertLess(elapsed_ms, 750.0)
        primitives = {row.primitive for row in generated.records}
        self.assertTrue({"circle", "ring", "triangle"}.issubset(primitives))
        for row in generated.records:
            row.validate(self.reir)
            self.assertFalse(row.source_mask.flags.writeable)
            self.assertFalse(row.rendered_mask.flags.writeable)
            self.assertEqual(
                (
                    row.candidate.certificates.components,
                    row.candidate.certificates.holes,
                ),
                topology_signature(row.rendered_mask),
            )
            self.assertIn("digital-preimage-feasible", row.candidate.prerequisite_claims)
            self.assertIn("native-topology-preserved", row.candidate.prerequisite_claims)

        cmir = extend_registry(
            self.reir, build_base_registry(self.reir), generated.candidates,
        )
        cmir.validate()
        candidate_ids = {row.id for row in cmir.candidates}
        self.assertTrue(all(row.candidate.id in candidate_ids for row in generated.records))

    def test_repeated_parameter_groups_compete_before_selection(self) -> None:
        generated = generate_shape_macros(self.reir)
        circle_groups = [row for row in generated.groups if row.primitive == "circle"]
        self.assertTrue(circle_groups)
        group = circle_groups[0]
        self.assertGreaterEqual(len(group.member_ids), 2)
        self.assertGreater(group.mdl_saving_bits, 0.0)
        self.assertIn(
            "members-compete-with-independent-shapes",
            group.candidate.prerequisite_claims,
        )
        cmir = extend_registry(
            self.reir, build_base_registry(self.reir), generated.candidates,
        )
        self.assertIn(group.candidate.id, {row.id for row in cmir.candidates})
        original = materialize_repeated_group_members(
            group, generated.records,
        )
        scaled = materialize_repeated_group_members(
            group, generated.records,
            shared_scale=float(dict(group.shared_parameters)["scale"]) * 1.12,
        )
        self.assertTrue(original and scaled)
        self.assertNotEqual(
            original[0].program.parameters, scaled[0].program.parameters,
        )
        parameters = tuple(
            (name, value * 1.12 if name == "shared_scale" else value)
            for name, value in group.candidate.program.parameters
        ) + (("refined_source_id", group.candidate.id),)
        refined = replace(
            group.candidate,
            program=SceneProgram(group.candidate.program.operator, parameters),
        )
        before = render_group_delivery(
            self.reir, group.candidate, SimpleNamespace(shapes=generated),
        )
        after = render_group_delivery(
            self.reir, refined, SimpleNamespace(shapes=generated),
        )
        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        self.assertFalse(np.array_equal(before, after))

    def test_linear_repeat_group_exposes_deployable_shared_gap(self) -> None:
        path = Path(self.temp.name) / "equal-gap-circles.png"
        image = Image.new("RGB", (150, 60), "white")
        draw = ImageDraw.Draw(image)
        for center_x in (25, 65, 105):
            draw.ellipse(
                (center_x - 10, 20, center_x + 10, 40), fill="black",
            )
        image.save(path)
        reir = build_reir(path)
        generated = generate_shape_macros(
            reir, max_rois=32, max_per_roi=8,
        )
        groups = [
            row for row in generated.groups
            if "shared_gap" in dict(row.candidate.program.parameters)
        ]
        self.assertTrue(groups)
        group = groups[0]
        gap = float(dict(group.candidate.program.parameters)["shared_gap"])
        self.assertIn("shared_gap", dict(group.candidate.continuous_params))
        before = render_group_delivery(
            reir, group.candidate, SimpleNamespace(shapes=generated),
        )
        parameters = tuple(
            (name, gap * 1.12 if name == "shared_gap" else value)
            for name, value in group.candidate.program.parameters
        ) + (("refined_source_id", group.candidate.id),)
        refined = replace(
            group.candidate, id="refined-repeat-gap-test",
            program=SceneProgram(group.candidate.program.operator, parameters),
        )
        after = render_group_delivery(
            reir, refined, SimpleNamespace(shapes=generated),
        )
        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        self.assertFalse(np.array_equal(before, after))

    def test_free_curve_control_points_change_exact_svg_delivery(self) -> None:
        path = Path(self.temp.name) / "free-curve.png"
        image = Image.new("RGB", (120, 90), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 12, 96, 78), fill="black")
        draw.ellipse((62, 27, 114, 73), fill="black")
        image.save(path)
        reir = build_reir(path)
        generated = generate_shape_macros(
            reir, max_rois=32, max_per_roi=12,
        )
        records = [
            row for row in generated.records
            if row.primitive == "free_curve"
            and "curve_point_count" in dict(row.candidate.program.parameters)
        ]
        self.assertTrue(records)
        record = records[0]
        continuous = dict(record.candidate.continuous_params)
        self.assertIn("curve_p0_x", continuous)
        self.assertIn("curve_tension", continuous)
        before = render_shape_delivery(reir, record.candidate)
        self.assertIsNotNone(before)
        parameters = tuple(
            (name, float(value) + 0.25 if name == "curve_p0_x" else value)
            for name, value in record.candidate.program.parameters
        ) + (("refined_source_id", record.candidate.id),)
        refined = replace(
            record.candidate, id="refined-free-curve-test",
            program=SceneProgram(record.candidate.program.operator, parameters),
        )
        after = render_shape_delivery(reir, refined)
        self.assertIsNotNone(after)
        assert before is not None and after is not None
        self.assertFalse(np.array_equal(before, after))

    def test_occluded_color_union_keeps_visible_ownership_separate(self) -> None:
        path = Path(self.temp.name) / "occluded-circle.png"
        image = Image.new("RGB", (128, 128), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 120, 120), fill=(225, 35, 30))
        draw.rectangle((56, 0, 72, 128), fill="white")
        image.save(path)
        reir = build_reir(path)
        generated = generate_shape_macros(reir, max_rois=64, max_per_roi=4)
        completed = [
            row for row in generated.records
            if row.primitive in {"circle", "ellipse"}
            and row.candidate.hidden_geometry is not None
        ]
        self.assertTrue(completed)
        row = max(completed, key=lambda value: int(value.rendered_mask.sum()))
        self.assertGreater(int(row.rendered_mask.sum()), int(row.source_mask.sum()))
        self.assertEqual(
            row.candidate.certificates.components,
            topology_signature(row.source_mask)[0],
        )
        self.assertIn(
            "visible-ownership-before-hidden-completion",
            row.candidate.prerequisite_claims,
        )

    def test_one_compound_logomark_is_a_whole_shape_not_forced_text(self) -> None:
        path = Path(self.temp.name) / "compound-logomark.png"
        image = Image.new("RGB", (144, 96), "white")
        draw = ImageDraw.Draw(image)
        ink = (24, 68, 154)
        draw.polygon(((18, 74), (42, 18), (57, 18), (34, 74)), fill=ink)
        draw.polygon(((52, 74), (76, 18), (91, 18), (68, 74)), fill=ink)
        draw.ellipse((94, 24, 126, 56), fill=ink)
        image.save(path)
        reir = build_reir(path)
        phase5 = generate_phase5_macros(
            reir, budget=Phase5Budgets(
                shape_rois=64, shapes_per_roi=4, stroke_rois=4,
                appearance_rois=4, appearances_per_roi=2, codec_loci=4,
            ), parallel=False,
        )
        compound = [
            row for row in phase5.shapes.records
            if row.primitive == "free_curve"
            and topology_signature(row.source_mask)[0] == 3
        ]
        self.assertTrue(compound)
        record = compound[0]
        self.assertEqual(record.candidate.kind, MacroKind.SHAPE)
        self.assertEqual(record.candidate.program.operator, "Shape/free_curve")
        self.assertIn("phase5-whole-shape", record.candidate.provenance)
        delivered = render_shape_delivery(reir, record.candidate)
        self.assertIsNotNone(delivered)
        assert delivered is not None
        self.assertEqual(
            topology_signature(delivered[..., 3] >= 128),
            topology_signature(record.source_mask),
        )
        court = RuntimeMacroCourt(
            reir, phase5,
            TextMacroSet((), (), 0, 0, ("empty-test-text-set",)),
            atlas=ExactRoiAtlas(), exact_request_limit=8,
        )
        certified = court.certify(record.candidate)
        self.assertIsNotNone(certified)
        self.assertEqual(court.audit().unsupported_delivery, 0)

    def test_one_ambiguous_symbol_keeps_text_and_shape_hypotheses(self) -> None:
        path = Path(self.temp.name) / "ambiguous-one-symbol.png"
        image = Image.new("RGB", (96, 96), "white")
        draw = ImageDraw.Draw(image)
        draw.polygon(((16, 78), (42, 14), (54, 14), (80, 78)), fill="black")
        draw.polygon(((35, 58), (48, 27), (61, 58)), fill="white")
        image.save(path)
        reir = build_reir(path)
        support = np.asarray(image.convert("L")) < 128
        soft_support = support.astype(np.float32)
        soft_support.setflags(write=False)

        def query(family: str) -> ProposalQuery:
            return ProposalQuery(
                id=f"ambiguous-symbol:{family}", family=family,
                roi_xyxy=(16 / 96, 14 / 96, 81 / 96, 79 / 96),
                soft_support=soft_support, parameters=(), covariance=(),
                confidence=0.99,
                relation_tokens=(
                    (("text_membership", 0.99),)
                    if family in {"text_line", "glyph_group"} else ()
                ),
                topology_code=topology_signature(support),
                hard_negative_class=None,
                provenance=("unit-ambiguous-one-symbol",),
            )

        queries = (query("glyph_group"), query("whole_shape"))
        text = generate_text_macros(
            reir, proposal_queries=queries, max_line_proposals=8,
            max_exact_per_line=0,
        )
        phase5 = generate_phase5_macros(
            reir, proposal_queries=queries,
            budget=Phase5Budgets(
                shape_rois=8, shapes_per_roi=4, stroke_rois=4,
                appearance_rois=2, appearances_per_roi=2, codec_loci=2,
            ),
            parallel=False,
        )
        self.assertTrue(text.records)
        self.assertTrue(phase5.shapes.records)
        self.assertIn(
            MacroKind.TEXT_LINE, {row.candidate.kind for row in text.records},
        )
        self.assertIn(
            MacroKind.SHAPE,
            {row.candidate.kind for row in phase5.shapes.records},
        )
        court = RuntimeMacroCourt(
            reir, phase5, text, atlas=ExactRoiAtlas(), exact_request_limit=16,
        )
        text_certificates = tuple(
            court.certify(row.candidate) for row in text.records
        )
        self.assertEqual(len(text_certificates), len(text.records))
        self.assertIn("single-custom-glyph", {row.path for row in text.records})
        self.assertEqual(court.audit().unsupported_delivery, 0)
        self.assertTrue(any(
            court.certify(row.candidate) is not None
            for row in phase5.shapes.records
        ))
        self.assertGreaterEqual(court.audit().considered, len(text.records) + 1)

    def test_stroke_graphs_compete_with_filled_regions(self) -> None:
        path = Path(self.temp.name) / "strokes.png"
        image = Image.new("RGB", (190, 84), "white")
        draw = ImageDraw.Draw(image)
        draw.line((8, 15, 82, 15), fill="black", width=5)
        draw.line((125, 8, 125, 54), fill="black", width=5)
        draw.line((98, 31, 172, 31), fill="black", width=5)
        image.save(path)
        reir = build_reir(path)
        started = time.perf_counter()
        generated = generate_stroke_macros(reir)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.assertTrue(generated.records)
        self.assertLessEqual(generated.rois_considered, 64)
        self.assertLess(elapsed_ms, 750.0)
        kinds = {row.macro_type for row in generated.records}
        self.assertIn("single_stroke", kinds)
        self.assertIn("axes_grid", kinds)
        for row in generated.records:
            row.validate(reir)
            self.assertTrue(row.graph.edges)
            self.assertIn(
                "competes-with-filled-region-hierarchy",
                row.candidate.prerequisite_claims,
            )
        cmir = extend_registry(
            reir, build_base_registry(reir), generated.candidates,
        )
        cmir.validate()
        record = max(generated.records, key=lambda row: row.iou)
        parameters = tuple(
            (name, float(value) * 1.35 if name == "width" else value)
            for name, value in record.candidate.program.parameters
        ) + (("refined_source_id", record.candidate.id),)
        refined = replace(
            record.candidate,
            program=SceneProgram(record.candidate.program.operator, parameters),
        )
        bundle = SimpleNamespace(strokes=generated)
        before = render_stroke_delivery(reir, record.candidate, bundle)
        after = render_stroke_delivery(reir, refined, bundle)
        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        self.assertGreater(
            int(np.sum(after[..., 3] > 0)),
            int(np.sum(before[..., 3] > 0)),
        )

        harmful_parameters = tuple(
            (name, float(value) * 5.0 if name == "width" else value)
            for name, value in record.candidate.program.parameters
        ) + (("refined_source_id", record.candidate.id),)
        harmful = replace(
            record.candidate,
            id="refined-harmful-stroke-width",
            program=SceneProgram(
                record.candidate.program.operator, harmful_parameters,
            ),
        )
        empty_records = SimpleNamespace(records=())
        phase5 = SimpleNamespace(
            shapes=SimpleNamespace(records=(), groups=()),
            strokes=generated,
            appearances=empty_records,
            cleanup=empty_records,
        )
        court = RuntimeMacroCourt(
            reir, phase5,
            TextMacroSet((), (), 0, 0, ("empty-test-text-set",)),
            atlas=ExactRoiAtlas(), exact_request_limit=8,
        )
        self.assertIsNone(court.certify_refined(
            record.candidate.id, harmful,
        ))
        audit = court.audit()
        self.assertEqual(audit.considered, 1)
        self.assertEqual(audit.rejected, 1)
        self.assertEqual(audit.unsupported_delivery, 0)

    def test_closed_frame_keeps_hole_in_native_rerender(self) -> None:
        path = Path(self.temp.name) / "frame.png"
        image = Image.new("RGB", (140, 90), "white")
        ImageDraw.Draw(image).rectangle((12, 15, 110, 70), outline="black", width=5)
        image.save(path)
        reir = build_reir(path)
        generated = generate_stroke_macros(reir)
        frames = [row for row in generated.records if row.macro_type == "frame"]
        self.assertTrue(frames)
        self.assertTrue(all(topology_signature(row.rendered_mask)[1] >= 1 for row in frames))

    def test_collinear_dash_train_becomes_one_measured_svg_pattern(self) -> None:
        path = Path(self.temp.name) / "dashed-stroke.png"
        image = Image.new("RGB", (180, 64), "white")
        draw = ImageDraw.Draw(image)
        for x in range(12, 150, 22):
            draw.line((x, 30, x + 11, 30), fill="black", width=5)
        image.save(path)
        reir = build_reir(path)
        generated = generate_stroke_macros(reir)
        dashed = [row for row in generated.records if row.graph.dash_pattern]
        self.assertTrue(dashed)
        row = max(dashed, key=lambda value: value.iou)
        self.assertEqual(row.macro_type, "dashed_stroke")
        self.assertEqual(len(row.graph.edges), 1)
        self.assertAlmostEqual(row.graph.dash_pattern[0], 11.0, delta=1.0)
        self.assertAlmostEqual(row.graph.dash_pattern[1], 11.0, delta=1.0)
        from types import SimpleNamespace

        from vice_compiler.export_writer import _stroke_elements
        elements = _stroke_elements(
            row.candidate, (0, 0, 0, 1.0),
            SimpleNamespace(strokes=generated),
        )
        self.assertEqual(len(elements), 1)
        self.assertIn('stroke-dasharray="', elements[0])

    def test_arrowhead_becomes_a_native_stroke_marker(self) -> None:
        path = Path(self.temp.name) / "arrow.png"
        image = Image.new("RGB", (150, 64), "white")
        draw = ImageDraw.Draw(image)
        draw.line((12, 32, 118, 32), fill="black", width=5)
        draw.polygon(((118, 21), (140, 32), (118, 43)), fill="black")
        image.save(path)
        reir = build_reir(path)
        generated = generate_stroke_macros(reir)
        marked = [row for row in generated.records if row.graph.markers]
        self.assertTrue(marked)
        row = max(marked, key=lambda value: value.iou)
        self.assertIn("arrow-end", row.graph.markers)
        from types import SimpleNamespace

        from vice_compiler.export_writer import _stroke_elements
        elements = _stroke_elements(
            row.candidate, (0, 0, 0, 1.0),
            SimpleNamespace(strokes=generated),
        )
        self.assertTrue(any("<marker " in element for element in elements))
        self.assertTrue(any('marker-end="url(#' in element for element in elements))

    def test_partitioned_frame_is_classified_as_swimlane_structure(self) -> None:
        path = Path(self.temp.name) / "swimlanes.png"
        image = Image.new("RGB", (180, 100), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((12, 12, 166, 86), outline="black", width=5)
        draw.line((14, 37, 164, 37), fill="black", width=5)
        draw.line((14, 62, 164, 62), fill="black", width=5)
        image.save(path)
        reir = build_reir(path)
        generated = generate_stroke_macros(reir)
        self.assertIn(
            "swimlane_structure",
            {row.macro_type for row in generated.records},
        )

    def test_appearance_models_compete_without_early_palette_quantization(self) -> None:
        path = Path(self.temp.name) / "gradient.png"
        width, height = 160, 72
        x = np.linspace(0.0, 1.0, width, dtype=np.float32)
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        rgba[..., 0] = np.tile((30 + 180 * x).astype(np.uint8), (height, 1))
        rgba[..., 1] = np.tile((70 + 80 * x).astype(np.uint8), (height, 1))
        rgba[..., 2] = 210
        rgba[..., 3] = 255
        Image.fromarray(rgba, "RGBA").save(path)
        reir = build_reir(path)
        started = time.perf_counter()
        generated = generate_appearance_macros(reir)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.assertLessEqual(generated.rois_considered, 32)
        self.assertLessEqual(len(generated.records), 32 * 4)
        self.assertEqual(
            len({row.candidate.id for row in generated.records}),
            len(generated.records),
        )
        self.assertLess(elapsed_ms, 1500.0)
        full = [
            row for row in generated.records
            if int(row.support_mask.sum()) >= int(0.8 * width * height)
        ]
        self.assertIn("solid", {row.model for row in full})
        linear = [row for row in full if row.model == "linear_gradient"]
        self.assertTrue(linear)
        self.assertGreater(linear[0].improvement_over_solid, 0.80)
        self.assertGreater(linear[0].directional_alignment, 0.90)
        base_delivery = render_appearance_delivery(reir, linear[0])
        parameters = tuple(
            (name, (float(value) + 35.0) % 360.0
             if name == "angle_deg" else value)
            for name, value in linear[0].candidate.program.parameters
        ) + (("refined_source_id", linear[0].candidate.id),)
        refined = replace(
            linear[0].candidate,
            program=SceneProgram(
                linear[0].candidate.program.operator, parameters,
            ),
        )
        refined_delivery = render_appearance_delivery(
            reir, linear[0], refined,
        )
        self.assertIsNotNone(base_delivery)
        self.assertIsNotNone(refined_delivery)
        self.assertFalse(np.array_equal(base_delivery, refined_delivery))
        for row in generated.records:
            row.validate(reir)
            self.assertIn(
                "palette-late-constraint-not-early-quantized",
                row.candidate.prerequisite_claims,
            )
        extend_registry(
            reir, build_base_registry(reir), generated.candidates,
        ).validate()

    def test_overlapping_alpha_shapes_form_one_bounded_ordered_stack_column(self) -> None:
        path = Path(self.temp.name) / "alpha-stack.png"
        width, height = 96, 72
        # Compose in the same linear-premultiplied domain used by canonical
        # REIR, then encode straight sRGB.  This is an identifiable physical
        # two-layer source, not a hand-authored class label.
        linear = np.zeros((height, width, 4), np.float32)
        back_mask = np.zeros((height, width), bool)
        front_mask = np.zeros((height, width), bool)
        back_mask[12:60, 8:62] = True
        front_mask[7:53, 35:87] = True
        back_alpha, front_alpha = 0.50, 0.55
        back_rgb = np.asarray((0.82, 0.03, 0.02), np.float32)
        front_rgb = np.asarray((0.01, 0.05, 0.84), np.float32)
        linear[back_mask, :3] = back_rgb * back_alpha
        linear[back_mask, 3] = back_alpha
        linear[front_mask, :3] = (
            front_rgb * front_alpha
            + linear[front_mask, :3] * (1.0 - front_alpha)
        )
        linear[front_mask, 3] = (
            front_alpha + linear[front_mask, 3] * (1.0 - front_alpha)
        )
        alpha = linear[..., 3]
        straight_linear = np.zeros_like(linear[..., :3])
        np.divide(
            linear[..., :3], np.maximum(alpha[..., None], 1e-8),
            out=straight_linear, where=alpha[..., None] > 1e-8,
        )
        srgb = np.where(
            straight_linear <= 0.0031308, 12.92 * straight_linear,
            1.055 * np.power(straight_linear, 1.0 / 2.4) - 0.055,
        )
        encoded = np.dstack((srgb, alpha[..., None]))
        Image.fromarray(
            np.clip(np.rint(encoded * 255.0), 0, 255).astype(np.uint8), "RGBA",
        ).save(path)
        reir = build_reir(path)

        def query(identifier: str, box: tuple[int, int, int, int]) -> ProposalQuery:
            support = np.zeros((height, width), np.float32)
            x1, y1, x2, y2 = box
            support[y1:y2, x1:x2] = 1.0
            support.setflags(write=False)
            return ProposalQuery(
                id=identifier, family="layer_relation",
                roi_xyxy=(x1 / width, y1 / height, x2 / width, y2 / height),
                soft_support=support, parameters=(), covariance=(),
                confidence=0.995, relation_tokens=(("front_of", 0.95),),
                topology_code=(1, 0), hard_negative_class=None,
                provenance=("unit-alpha-layer",),
            )

        generated = generate_appearance_macros(
            reir, max_rois=24, max_models_per_roi=4,
            proposal_queries=(
                query("back", (8, 12, 62, 60)),
                query("front", (35, 7, 87, 53)),
            ),
        )
        stacks = [
            row for row in generated.records
            if row.model == "ordered_translucent_stack"
        ]
        self.assertTrue(stacks)
        stack = min(stacks, key=lambda row: row.residual_rmse)
        stack.validate(reir)
        self.assertEqual(len(stack.stack_layers), 2)
        self.assertLess(stack.residual_rmse, 0.03)
        delivery = render_appearance_delivery(reir, stack)
        self.assertIsNotNone(delivery)
        self.assertLess(float(np.mean(np.abs(
            delivery[..., 3].astype(np.float32) / 255.0
            - reir.raster.straight_rgba[..., 3]
        ))), 0.02)

        base = build_base_registry(reir)
        cmir = extend_registry(reir, base, (stack.candidate,))
        stack_candidate = cmir.by_id()[stack.candidate.id]
        selected = [stack_candidate.id]
        for candidate in cmir.candidates:
            if (
                candidate.kind is MacroKind.ATOMIC_FALLBACK
                and candidate.core_bits & stack_candidate.core_bits == 0
            ):
                selected.append(candidate.id)
        solution = MasterSolution(
            selected_ids=tuple(selected), utility=0.0,
            covered_bits=(1 << cmir.leaf_count) - 1,
            feasible=True, exact_cover=True, used_atomic_fallback=True,
            fallback_always_feasible=True, solve_ms=0.0,
            exact_components=1, bounded_components=0,
        )
        visible = build_visible_scene(cmir, solution)
        owned_cells = [
            row for row in visible.paint_ownership_by_leaf
            if visible.owner_by_leaf[row.cell_id] == stack_candidate.id
        ]
        self.assertTrue(owned_cells)
        self.assertTrue(all(
            len(row.translucent_contributors) == row.contribution_limit == 2
            and row.background_id == "canvas-background"
            for row in owned_cells
        ))

    def test_three_overlapping_alpha_shapes_generate_certified_k3_stack(self) -> None:
        path = Path(self.temp.name) / "alpha-stack-k3.png"
        width, height = 112, 84
        linear = np.zeros((height, width, 4), np.float32)
        masks = []
        for box in ((8, 12, 66, 65), (28, 19, 86, 75), (48, 7, 104, 58)):
            mask = np.zeros((height, width), bool)
            x1, y1, x2, y2 = box
            mask[y1:y2, x1:x2] = True
            masks.append(mask)
        paints = (
            (np.asarray((0.86, 0.025, 0.02), np.float32), 0.46),
            (np.asarray((0.02, 0.78, 0.04), np.float32), 0.53),
            (np.asarray((0.025, 0.04, 0.88), np.float32), 0.61),
        )
        for mask, (rgb, alpha) in zip(masks, paints):
            linear[mask, :3] = (
                rgb * alpha + linear[mask, :3] * (1.0 - alpha)
            )
            linear[mask, 3] = alpha + linear[mask, 3] * (1.0 - alpha)
        alpha = linear[..., 3]
        straight_linear = np.zeros_like(linear[..., :3])
        np.divide(
            linear[..., :3], np.maximum(alpha[..., None], 1e-8),
            out=straight_linear, where=alpha[..., None] > 1e-8,
        )
        srgb = np.where(
            straight_linear <= 0.0031308, 12.92 * straight_linear,
            1.055 * np.power(straight_linear, 1.0 / 2.4) - 0.055,
        )
        encoded = np.dstack((srgb, alpha[..., None]))
        Image.fromarray(
            np.clip(np.rint(encoded * 255.0), 0, 255).astype(np.uint8), "RGBA",
        ).save(path)
        reir = build_reir(path)

        def query(identifier: str, mask: np.ndarray) -> ProposalQuery:
            support = mask.astype(np.float32)
            support.setflags(write=False)
            ys, xs = np.nonzero(mask)
            return ProposalQuery(
                id=identifier, family="layer_relation",
                roi_xyxy=(
                    float(xs.min()) / width, float(ys.min()) / height,
                    float(xs.max() + 1) / width, float(ys.max() + 1) / height,
                ),
                soft_support=support, parameters=(), covariance=(),
                confidence=0.995, relation_tokens=(("front_of", 0.95),),
                topology_code=(1, 0), hard_negative_class=None,
                provenance=("unit-alpha-layer-k3",),
            )

        generated = generate_appearance_macros(
            reir, max_rois=24, max_models_per_roi=4,
            proposal_queries=tuple(
                query(f"layer-{index}", mask)
                for index, mask in enumerate(masks)
            ),
        )
        stacks = [
            row for row in generated.records
            if row.model == "ordered_translucent_stack"
            and len(row.stack_layers) == 3
        ]
        self.assertTrue(stacks)
        expected_order = tuple(mask_sha256(mask) for mask in masks)
        self.assertTrue(all(
            tuple(layer.support_digest for layer in row.stack_layers)
            == expected_order
            for row in stacks
        ))
        stack = min(stacks, key=lambda row: row.residual_rmse)
        stack.validate(reir)
        self.assertEqual(
            tuple(layer.support_digest for layer in stack.stack_layers),
            expected_order,
        )
        self.assertEqual(dict(stack.parameters)["layer_count"], 3)
        self.assertIn(
            "triple-overlap-held-out", stack.candidate.provenance,
        )
        self.assertTrue(any(
            note.startswith("triple_overlap_rmse=")
            for note in stack.candidate.certificates.notes
        ))
        self.assertLess(stack.residual_rmse, 0.03)
        delivery = render_appearance_delivery(reir, stack)
        self.assertIsNotNone(delivery)
        visible = reir.raster.straight_rgba[..., 3] > 0.01
        rendered = delivery.astype(np.float32) / 255.0
        self.assertLess(float(np.mean(np.abs(
            rendered[..., 3] - reir.raster.straight_rgba[..., 3]
        ))), 0.02)
        rendered_linear = np.where(
            rendered[..., :3] <= 0.04045,
            rendered[..., :3] / 12.92,
            np.power((rendered[..., :3] + 0.055) / 1.055, 2.4),
        )
        rendered_premultiplied = (
            rendered_linear * rendered[..., 3, None]
        )
        self.assertLess(float(np.mean(np.abs(
            rendered_premultiplied[visible]
            - reir.raster.linear_premultiplied_rgba[..., :3][visible]
        ))), 0.045)

        base = build_base_registry(reir)
        cmir = extend_registry(reir, base, (stack.candidate,))
        stack_candidate = cmir.by_id()[stack.candidate.id]
        selected = [stack_candidate.id]
        for candidate in cmir.candidates:
            if (
                candidate.kind is MacroKind.ATOMIC_FALLBACK
                and candidate.core_bits & stack_candidate.core_bits == 0
            ):
                selected.append(candidate.id)
        solution = MasterSolution(
            selected_ids=tuple(selected), utility=0.0,
            covered_bits=(1 << cmir.leaf_count) - 1,
            feasible=True, exact_cover=True, used_atomic_fallback=True,
            fallback_always_feasible=True, solve_ms=0.0,
            exact_components=1, bounded_components=0,
        )
        visible_scene = build_visible_scene(cmir, solution)
        owned_cells = [
            row for row in visible_scene.paint_ownership_by_leaf
            if visible_scene.owner_by_leaf[row.cell_id] == stack_candidate.id
        ]
        self.assertTrue(owned_cells)
        self.assertTrue(all(
            len(row.translucent_contributors) == row.contribution_limit == 3
            and row.background_id == "canvas-background"
            for row in owned_cells
        ))

    def test_codec_residual_creates_fixed_posterior_counterfactuals_only(self) -> None:
        path = Path(self.temp.name) / "codec-circle.jpg"
        image = Image.new("RGB", (96, 96), "white")
        ImageDraw.Draw(image).ellipse((20, 20, 75, 75), fill=(30, 70, 160))
        image.save(path, quality=35, subsampling=2)
        reir = build_reir(path)
        raster_before = reir.raster.linear_premultiplied_rgba.tobytes()
        generated = generate_cleanup_macros(reir, max_loci=8)
        self.assertTrue(generated.loci)
        self.assertTrue(generated.records)
        kinds = {row.counterfactual for row in generated.records}
        self.assertIn("remove_halo_confetti", kinds)
        self.assertTrue(kinds.issubset({
            "keep_detail", "remove_halo_confetti", "restore_ideal_shape",
            "attach_detail_to_text_stroke", "preserve_engraving",
        }))
        self.assertEqual(
            {row.posterior_digest for row in generated.records},
            {generated.renderer_posterior.digest},
        )
        self.assertEqual(
            len({row.candidate.id for row in generated.records}),
            len(generated.records),
        )
        for row in generated.records:
            row.validate(reir, generated.renderer_posterior)
            self.assertEqual(
                len(row.model_mean_nll),
                len(generated.renderer_posterior.models),
            )
            self.assertIn(
                "residual-never-mutates-vsir",
                row.candidate.prerequisite_claims,
            )
        self.assertEqual(
            raster_before, reir.raster.linear_premultiplied_rgba.tobytes(),
        )
        extend_registry(
            reir, build_base_registry(reir), generated.candidates,
        ).validate()

        # The production route must execute the same raster-free SVG delivery
        # it certifies.  Previously this lane stopped at generation and every
        # codec candidate was rejected as an unsupported preview.
        phase5 = extract_phase5_scene(
            reir, budget=Phase5Budgets(
                shape_rois=4, shapes_per_roi=2, stroke_rois=4,
                appearance_rois=4, appearances_per_roi=2, codec_loci=8,
            ), time_budget_ms=50.0,
        ).bundle
        codec_record = phase5.cleanup.records[0]
        delivery = render_codec_delivery(reir, codec_record)
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.shape, (reir.height, reir.width, 4))
        self.assertGreater(int(np.sum(delivery[..., 3] > 0)), 0)
        court = RuntimeMacroCourt(
            reir, phase5,
            TextMacroSet((), (), 0, 0, ("empty-test-text-set",)),
            atlas=ExactRoiAtlas(), exact_request_limit=8,
        )
        court.certify(codec_record.candidate)
        audit = court.audit()
        self.assertEqual(audit.considered, 1)
        self.assertEqual(audit.unsupported_delivery, 0)

    def test_risk_query_adds_a_bounded_codec_locus_before_fitting(self) -> None:
        soft = np.zeros((24, 24), np.float32)
        soft[10:11, 11:12] = 1.0
        soft.setflags(write=False)
        query = ProposalQuery(
            id="risk-q", family="risk_hard_negative",
            roi_xyxy=(0.0, 0.0, 1.0, 1.0), soft_support=soft,
            parameters=(), covariance=(), confidence=0.95,
            relation_tokens=(), topology_code=(1, 0),
            hard_negative_class="preserve_jpeg_halo",
            provenance=("unit-risk-query",),
        )
        generated = generate_cleanup_macros(
            self.reir, max_loci=4, proposal_queries=(query,),
        )
        guided = [
            row for row in generated.records
            if any(
                value.startswith("proposal-query:risk-q")
                for value in row.candidate.provenance
            )
        ]
        self.assertTrue(guided)
        self.assertLessEqual(len(generated.loci), 4)
        self.assertEqual(
            {row.counterfactual for row in guided},
            {"remove_halo_confetti"},
        )

    def test_all_phase5_lanes_share_one_bounded_registry_and_valid_fallback(self) -> None:
        budget = Phase5Budgets(
            shape_rois=12, shapes_per_roi=3, stroke_rois=12,
            appearance_rois=8, appearances_per_roi=3, codec_loci=8,
        )
        extracted = extract_phase5_scene(
            self.reir, budget=budget, time_budget_ms=100.0,
        )
        extracted.bundle.validate(self.reir)
        extracted.cmir.validate()
        self.assertLessEqual(
            extracted.bundle.counts["total"], budget.maximum_columns,
        )
        self.assertTrue(extracted.solution.feasible)
        self.assertTrue(extracted.solution.exact_cover)
        self.assertTrue(extracted.solution.fallback_always_feasible)
        self.assertIn(
            "all-lanes-compete-in-one-cmir", extracted.bundle.provenance,
        )


if __name__ == "__main__":
    unittest.main()

"""Materialization v2 — commit M2-01 gate: contracts only.

Gate (plan S7): canonical digest deterministic; invalid programs fail.
No runtime wiring is exercised here on purpose.
"""

from __future__ import annotations

import hashlib
import math
import unittest

from vice_compiler.vector_program import (
    CircularArcSpan,
    ClosedPathProgram,
    CubicSpan,
    LinearGradientPaint,
    LineSpan,
    ProgramValidationError,
    SolidPaint,
    TextVectorProgram,
    VectorPaintLayer,
    canonical_json,
    flatten_path,
    format_number,
    path_data,
    polygon_area,
    program_digest,
    program_primitive_census,
    quantize,
    seal_program,
    serialize_text_vector_program,
    validate_text_vector_program,
)

BLACK = (0.0, 0.0, 0.0, 1.0)


def _square(id_: str, x0: float, y0: float, size: float, role="positive"):
    corners = [
        (x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size),
    ]
    spans = tuple(
        LineSpan(p0=corners[index], p1=corners[(index + 1) % 4])
        for index in range(4)
    )
    return ClosedPathProgram(
        id=id_, role=role, spans=spans, fill_rule="nonzero",
    )


def _program(paths, layers=None, family="test-family") -> TextVectorProgram:
    paths = tuple(paths)
    if layers is None:
        layers = (
            VectorPaintLayer(
                id="layer-0", path_ids=tuple(p.id for p in paths),
                paint=SolidPaint(rgba_linear=BLACK), z_index=0,
            ),
        )
    return TextVectorProgram(
        id="program-0", source_line_id="text-line-0", geometry_family=family,
        paths=paths, layers=tuple(layers),
    )


class CanonicalDigestTests(unittest.TestCase):
    def test_digest_is_deterministic_across_instances(self) -> None:
        first = seal_program(_program([_square("p0", 1.0, 2.0, 4.0)]))
        second = seal_program(_program([_square("p0", 1.0, 2.0, 4.0)]))
        self.assertEqual(first.program_sha256, second.program_sha256)
        self.assertEqual(
            first.exact_fragment_sha256, second.exact_fragment_sha256,
        )
        self.assertEqual(len(first.program_sha256), 64)

    def test_fragment_digest_matches_serialized_bytes(self) -> None:
        program = seal_program(_program([_square("p0", 0.0, 0.0, 3.0)]))
        fragment = serialize_text_vector_program(program)
        self.assertEqual(
            program.exact_fragment_sha256,
            hashlib.sha256(fragment.encode("utf-8")).hexdigest(),
        )

    def test_digest_changes_with_geometry(self) -> None:
        first = seal_program(_program([_square("p0", 0.0, 0.0, 3.0)]))
        second = seal_program(_program([_square("p0", 0.0, 0.0, 3.5)]))
        self.assertNotEqual(first.program_sha256, second.program_sha256)

    def test_canonical_json_is_sorted_and_compact(self) -> None:
        program = seal_program(_program([_square("p0", 0.0, 0.0, 3.0)]))
        text = canonical_json(program)
        self.assertNotIn(", ", text)
        self.assertIn('"serializer_version"', text)
        # Digest domain excludes the digests themselves.
        self.assertNotIn(program.program_sha256, text)

    def test_repr_is_not_the_hash_source(self) -> None:
        program = seal_program(_program([_square("p0", 0.0, 0.0, 3.0)]))
        self.assertNotEqual(
            program_digest(program),
            hashlib.sha256(repr(program).encode("utf-8")).hexdigest(),
        )

    def test_quantization_is_idempotent(self) -> None:
        value = 1.0 / 3.0
        once = quantize(value)
        self.assertEqual(once, quantize(once))
        self.assertEqual(format_number(once), format_number(quantize(once)))

    def test_sealed_program_revalidates(self) -> None:
        program = seal_program(_program([_square("p0", 0.0, 0.0, 3.0)]))
        validate_text_vector_program(program)  # must not raise


class ValidationTests(unittest.TestCase):
    def test_open_path_fails(self) -> None:
        spans = (
            LineSpan(p0=(0.0, 0.0), p1=(4.0, 0.0)),
            LineSpan(p0=(4.0, 0.0), p1=(4.0, 4.0)),
        )
        path = ClosedPathProgram(
            id="p0", role="positive", spans=spans, fill_rule="nonzero",
        )
        with self.assertRaises(ProgramValidationError):
            seal_program(_program([path]))

    def test_broken_chain_fails(self) -> None:
        spans = (
            LineSpan(p0=(0.0, 0.0), p1=(4.0, 0.0)),
            LineSpan(p0=(9.0, 0.0), p1=(4.0, 4.0)),
            LineSpan(p0=(4.0, 4.0), p1=(0.0, 0.0)),
        )
        path = ClosedPathProgram(
            id="p0", role="positive", spans=spans, fill_rule="nonzero",
        )
        with self.assertRaises(ProgramValidationError):
            seal_program(_program([path]))

    def test_non_finite_coordinate_fails(self) -> None:
        spans = (
            LineSpan(p0=(0.0, 0.0), p1=(float("inf"), 0.0)),
            LineSpan(p0=(float("inf"), 0.0), p1=(0.0, 0.0)),
        )
        path = ClosedPathProgram(
            id="p0", role="positive", spans=spans, fill_rule="nonzero",
        )
        with self.assertRaises(ProgramValidationError):
            seal_program(_program([path]))

    def test_zero_radius_arc_fails(self) -> None:
        arc = CircularArcSpan(
            p0=(0.0, 0.0), p1=(0.0, 0.0), center=(0.0, 0.0),
            radius=0.0, clockwise=True,
        )
        path = ClosedPathProgram(
            id="p0", role="positive", spans=(arc,), fill_rule="nonzero",
        )
        with self.assertRaises(ProgramValidationError):
            seal_program(_program([path]))

    def test_arc_endpoint_off_circle_fails(self) -> None:
        arc_a = CircularArcSpan(
            p0=(4.0, 0.0), p1=(-4.0, 0.0), center=(0.0, 0.0),
            radius=4.0, clockwise=True,
        )
        arc_b = CircularArcSpan(
            p0=(-4.0, 0.0), p1=(4.0, 0.0), center=(0.0, 0.0),
            radius=9.0, clockwise=True,
        )
        path = ClosedPathProgram(
            id="p0", role="positive", spans=(arc_a, arc_b),
            fill_rule="nonzero",
        )
        with self.assertRaises(ProgramValidationError):
            seal_program(_program([path]))

    def test_unknown_layer_path_id_fails(self) -> None:
        layer = VectorPaintLayer(
            id="layer-0", path_ids=("missing",),
            paint=SolidPaint(rgba_linear=BLACK), z_index=0,
        )
        with self.assertRaises(ProgramValidationError):
            seal_program(_program([_square("p0", 0.0, 0.0, 3.0)], [layer]))

    def test_duplicate_path_ids_fail(self) -> None:
        with self.assertRaises(ProgramValidationError):
            seal_program(_program([
                _square("p0", 0.0, 0.0, 3.0), _square("p0", 9.0, 9.0, 3.0),
            ]))

    def test_duplicate_z_index_fails(self) -> None:
        paths = [_square("p0", 0.0, 0.0, 8.0), _square("p1", 20.0, 0.0, 8.0)]
        layers = [
            VectorPaintLayer(
                id="layer-0", path_ids=("p0",),
                paint=SolidPaint(rgba_linear=BLACK), z_index=3,
            ),
            VectorPaintLayer(
                id="layer-1", path_ids=("p1",),
                paint=SolidPaint(rgba_linear=BLACK), z_index=3,
            ),
        ]
        with self.assertRaises(ProgramValidationError):
            seal_program(_program(paths, layers))

    def test_uncontained_negative_loop_fails(self) -> None:
        outer = _square("p0", 0.0, 0.0, 10.0)
        stray = _square("p1", 40.0, 40.0, 2.0, role="negative")
        layer = VectorPaintLayer(
            id="layer-0", path_ids=("p0", "p1"),
            paint=SolidPaint(rgba_linear=BLACK), z_index=0,
        )
        with self.assertRaises(ProgramValidationError):
            seal_program(_program([outer, stray], [layer]))

    def test_contained_negative_loop_passes(self) -> None:
        outer = _square("p0", 0.0, 0.0, 10.0)
        hole = _square("p1", 3.0, 3.0, 4.0, role="negative")
        layer = VectorPaintLayer(
            id="layer-0", path_ids=("p0", "p1"),
            paint=SolidPaint(rgba_linear=BLACK), z_index=0,
        )
        program = seal_program(_program([outer, hole], [layer]))
        validate_text_vector_program(program)

    def test_unsorted_gradient_stops_fail(self) -> None:
        paint = LinearGradientPaint(
            p0=(0.0, 0.0), p1=(10.0, 0.0),
            stops=((0.9, BLACK), (0.1, (1.0, 1.0, 1.0, 1.0))),
        )
        layer = VectorPaintLayer(
            id="layer-0", path_ids=("p0",), paint=paint, z_index=0,
        )
        with self.assertRaises(ProgramValidationError):
            seal_program(_program([_square("p0", 0.0, 0.0, 5.0)], [layer]))

    def test_gradient_stop_outside_unit_range_fails(self) -> None:
        paint = LinearGradientPaint(
            p0=(0.0, 0.0), p1=(10.0, 0.0),
            stops=((0.0, BLACK), (1.4, (1.0, 1.0, 1.0, 1.0))),
        )
        layer = VectorPaintLayer(
            id="layer-0", path_ids=("p0",), paint=paint, z_index=0,
        )
        with self.assertRaises(ProgramValidationError):
            seal_program(_program([_square("p0", 0.0, 0.0, 5.0)], [layer]))

    def test_tampered_digest_is_rejected(self) -> None:
        program = seal_program(_program([_square("p0", 0.0, 0.0, 3.0)]))
        tampered = TextVectorProgram(
            id=program.id, source_line_id=program.source_line_id,
            geometry_family=program.geometry_family, paths=program.paths,
            layers=program.layers,
            glyph_path_groups=program.glyph_path_groups,
            exact_fragment_sha256=program.exact_fragment_sha256,
            program_sha256="0" * 64, provenance=program.provenance,
        )
        with self.assertRaises(ProgramValidationError):
            validate_text_vector_program(tampered)


class SerializerTests(unittest.TestCase):
    def test_line_span_emits_L_not_cubic(self) -> None:
        program = seal_program(_program([_square("p0", 0.0, 0.0, 4.0)]))
        fragment = serialize_text_vector_program(program)
        self.assertIn("L", fragment)
        self.assertNotIn("C", fragment.split('d="')[1].split('"')[0])

    def test_arc_span_emits_A(self) -> None:
        top = CircularArcSpan(
            p0=(4.0, 0.0), p1=(-4.0, 0.0), center=(0.0, 0.0),
            radius=4.0, clockwise=True,
        )
        bottom = CircularArcSpan(
            p0=(-4.0, 0.0), p1=(4.0, 0.0), center=(0.0, 0.0),
            radius=4.0, clockwise=True,
        )
        path = ClosedPathProgram(
            id="p0", role="positive", spans=(top, bottom),
            fill_rule="nonzero",
        )
        program = seal_program(_program([path]))
        data = path_data(program.paths[0])
        self.assertEqual(data.count("A"), 2)
        self.assertTrue(data.endswith("Z"))
        self.assertEqual(program_primitive_census(program),
                         {"circular_arc": 2})

    def test_cubic_span_emits_C(self) -> None:
        spans = (
            CubicSpan(
                p0=(0.0, 0.0), c1=(3.0, 5.0), c2=(7.0, 5.0), p1=(10.0, 0.0),
            ),
            LineSpan(p0=(10.0, 0.0), p1=(0.0, 0.0)),
        )
        path = ClosedPathProgram(
            id="p0", role="positive", spans=spans, fill_rule="nonzero",
        )
        program = seal_program(_program([path]))
        self.assertIn("C", path_data(program.paths[0]))

    def test_layers_serialize_in_z_order(self) -> None:
        paths = [_square("p0", 0.0, 0.0, 8.0), _square("p1", 20.0, 0.0, 8.0)]
        layers = [
            VectorPaintLayer(
                id="top", path_ids=("p1",),
                paint=SolidPaint(rgba_linear=(1.0, 0.0, 0.0, 1.0)), z_index=5,
                semantic_role="detail",
            ),
            VectorPaintLayer(
                id="bottom", path_ids=("p0",),
                paint=SolidPaint(rgba_linear=BLACK), z_index=1,
            ),
        ]
        program = seal_program(_program(paths, layers))
        fragment = serialize_text_vector_program(program)
        self.assertLess(
            fragment.index('data-pcdc-layer-role="fill"'),
            fragment.index('data-pcdc-layer-role="detail"'),
        )

    def test_gradient_emits_defs(self) -> None:
        paint = LinearGradientPaint(
            p0=(0.0, 0.0), p1=(10.0, 0.0),
            stops=((0.0, BLACK), (1.0, (1.0, 1.0, 1.0, 1.0))),
        )
        layer = VectorPaintLayer(
            id="layer-0", path_ids=("p0",), paint=paint, z_index=0,
        )
        program = seal_program(_program([_square("p0", 0.0, 0.0, 10.0)], [layer]))
        fragment = serialize_text_vector_program(program)
        self.assertIn("<defs>", fragment)
        self.assertIn("linearGradient", fragment)
        self.assertIn("url(#", fragment)

    def test_serialization_is_stable_under_reserialization(self) -> None:
        program = seal_program(_program([_square("p0", 1.5, 2.5, 4.25)]))
        first = serialize_text_vector_program(program)
        second = serialize_text_vector_program(seal_program(program))
        self.assertEqual(first, second)


class GeometryHelperTests(unittest.TestCase):
    def test_flatten_closes_the_loop(self) -> None:
        square = _square("p0", 0.0, 0.0, 6.0)
        points = flatten_path(square)
        self.assertLess(math.dist(points[0], points[-1]), 1.0e-9)

    def test_polygon_area_matches_square(self) -> None:
        square = _square("p0", 0.0, 0.0, 6.0)
        self.assertAlmostEqual(abs(polygon_area(flatten_path(square))), 36.0, 6)

    def test_circle_flatten_area_matches_analytic(self) -> None:
        top = CircularArcSpan(
            p0=(5.0, 0.0), p1=(-5.0, 0.0), center=(0.0, 0.0),
            radius=5.0, clockwise=True,
        )
        bottom = CircularArcSpan(
            p0=(-5.0, 0.0), p1=(5.0, 0.0), center=(0.0, 0.0),
            radius=5.0, clockwise=True,
        )
        path = ClosedPathProgram(
            id="p0", role="positive", spans=(top, bottom),
            fill_rule="nonzero",
        )
        area = abs(polygon_area(flatten_path(path, samples=256)))
        self.assertAlmostEqual(area, math.pi * 25.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()

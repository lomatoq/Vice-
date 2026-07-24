from __future__ import annotations

import json
import tempfile
from unittest.mock import patch
from types import SimpleNamespace
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
try:
    import pytest
except ImportError:  # Project tests are also designed to run directly.
    class _Approx:
        def __init__(self, expected, abs=1e-12):
            self.expected, self.tolerance = expected, abs

        def __eq__(self, actual):
            return builtins.abs(actual - self.expected) <= self.tolerance

    class _Raises:
        def __init__(self, exception, match=None):
            self.exception, self.match = exception, match

        def __enter__(self):
            return self

        def __exit__(self, kind, value, traceback):
            if kind is None or not issubclass(kind, self.exception):
                return False
            if self.match is not None and self.match not in str(value):
                raise AssertionError(f"{value!r} does not contain {self.match!r}")
            return True

    class _Mark:
        @staticmethod
        def parametrize(*_args, **_kwargs):
            return lambda function: function

    class _PytestFallback:
        mark = _Mark()
        approx = staticmethod(lambda expected, abs=1e-12: _Approx(expected, abs))
        raises = staticmethod(lambda exception, match=None: _Raises(exception, match))

    import builtins
    pytest = _PytestFallback()
from PIL import Image

from vice_scene.appearance import fit_region_appearance, infer_appearances
from vice_scene.boundary_solver import (InterfaceRun, fit_interface_run,
                                        physical_residual_cost,
                                        solve_shared_interfaces)
from vice_scene.config import EngineConfig
from vice_scene.contracts import (
    Appearance, GeometryPrimitive, LayerEdge, Rect, RenderModel, SceneGraph,
)
from vice_scene.evidence_cache import EvidenceCache
from vice_scene.evidence_model import (DeterministicEvidenceModel,
                                       evidence_cache_key)
from vice_scene.export_scene import (export_dxf, export_pdf_or_eps, export_png,
                                     export_svg, scene_to_svg)
from vice_scene.font_synthetic import font_text_scene
from vice_scene.ingest import decode_raster
from vice_scene.legacy_adapter import LegacyResult
from vice_scene.optimizer import (OptimizationAudit, _breakdown,
                                  assert_monotonic)
from vice_scene.pipeline import _exact_font_path_supported, process_scene
from vice_scene.raster_profile import diagnose_raster
from vice_scene.raster_profile import _text_field
from vice_scene.render_models import (forward_model_catalog, render_scene,
                                      ForwardScore, score_forward,
                                      select_forward_model)
from vice_scene.scene_graph import SceneBuildResult
from vice_scene.residual import residual_add_prune
from vice_scene.shape_models import (_fit_circle, _fit_hole_geometry,
                                     render_geometry_mask,
                                     tournament_region)
from vice_scene.synthetic import (DegradationStep, canonical_smoke_scene,
                                  coverage_scene, render_synthetic,
                                  render_with_family, reproduce_fixture,
                                  write_fixture)
from vice_scene.text_scene import (GlyphInstance, apply_exact_font_substitution,
                                   font_free_sdf_reconstruct,
                                   glyph_catastrophe_count)
from vice_scene.topology import (RegionProposal, TopologyHypothesis,
                                 _shortlist_topologies,
                                 build_topology_hypotheses)
from vice_scene.training_data import exact_scene_labels, write_training_sample


def _write_smoke(path: Path) -> None:
    Image.fromarray(render_scene(canonical_smoke_scene()), "RGBA").save(path)


def _region_from_geometry(primitive: GeometryPrimitive, *, size: int = 72,
                          hole: GeometryPrimitive | None = None) -> RegionProposal:
    negatives = ((hole,),) if hole is not None else ()
    mask = render_geometry_mask((size, size), (primitive,), negatives, supersample=4) > 127
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP,
                                            cv2.CHAIN_APPROX_NONE)
    assert contours and hierarchy is not None
    outer = max((i for i, row in enumerate(hierarchy[0]) if row[3] < 0),
                key=lambda i: abs(cv2.contourArea(contours[i])))
    holes = tuple(contours[i][:, 0, :].astype(np.float32) + .5
                  for i, row in enumerate(hierarchy[0]) if row[3] == outer)
    y, x = np.nonzero(mask)
    return RegionProposal(
        "fixture", 0, mask, float(mask.sum()),
        (int(x.min()), int(y.min()), int(x.max() + 1), int(y.max() + 1)),
        contours[outer][:, 0, :].astype(np.float32) + .5, holes, None, 1.0,
    )


def test_scene_contract_roundtrip_and_dag_guard() -> None:
    scene = canonical_smoke_scene()
    assert SceneGraph.from_json(scene.to_json()) == scene
    with pytest.raises(ValueError, match="cycle"):
        replace(scene, layer_edges=(LayerEdge("shape-circle", "shape-rounded"),
                                    LayerEdge("shape-rounded", "shape-circle"))).validate()
    with pytest.raises(ValueError, match="parent graph contains a cycle"):
        replace(scene, shapes=(replace(scene.shapes[0], parent="shape-rounded"),
                               replace(scene.shapes[1], parent="shape-circle"))).validate()


DECODER_CASES = [
    (".png", "PNG"), (".jpg", "JPEG"), (".bmp", "BMP"),
    (".webp", "WEBP"), (".gif", "GIF"), (".tiff", "TIFF"),
]


@pytest.mark.parametrize("suffix,format_name", DECODER_CASES)
def test_canonical_ingest_supported_decoders(tmp_path: Path, suffix: str,
                                             format_name: str) -> None:
    path = tmp_path / f"source{suffix}"
    image = Image.new("RGBA", (9, 7), (180, 30, 70, 128))
    if format_name == "JPEG":
        image = image.convert("RGB")
    image.save(path, format=format_name)
    raster = decode_raster(path)
    raster.validate()
    assert (raster.width, raster.height) == (9, 7)
    assert raster.source.format in {format_name, "JPG"}


def test_ingest_alpha_and_pixel_transform(tmp_path: Path) -> None:
    path = tmp_path / "alpha.png"
    rgba = np.zeros((4, 6, 4), np.uint8)
    rgba[..., :3] = (255, 0, 255)  # hidden RGB must be discarded
    rgba[1:3, 2:5] = (64, 128, 192, 128)
    Image.fromarray(rgba, "RGBA").save(path)
    raster = decode_raster(path, crop=(1, 1, 5, 4))
    assert raster.rgba_srgb_straight[0, 0, :3].tolist() == [0.0, 0.0, 0.0]
    assert raster.rgba_linear_premul.shape == (3, 4, 4)
    assert raster.source.canonical_from_source[2] == pytest.approx(-1.0)
    assert raster.source.canonical_from_source[5] == pytest.approx(-1.0)


def test_ingest_fractional_crop_and_exif_orientation(tmp_path: Path) -> None:
    fractional = tmp_path / "fractional.png"
    Image.new("RGBA", (7, 5), (30, 60, 90, 255)).save(fractional)
    cropped = decode_raster(fractional, crop=(1.2, .8, 4.1, 3.2))
    assert (cropped.width, cropped.height) == (4, 4)
    assert cropped.source.crop_rect_source == Rect(1.0, 0.0, 5.0, 4.0)
    assert cropped.source.canonical_from_source[2] == pytest.approx(-1.0)
    oriented = tmp_path / "oriented.jpg"
    exif = Image.Exif(); exif[274] = 6
    Image.new("RGB", (4, 2), (100, 80, 20)).save(oriented, exif=exif)
    decoded = decode_raster(oriented)
    assert (decoded.width, decoded.height) == (2, 4)
    assert decoded.source.crop_rect_source == Rect(0.0, 0.0, 4.0, 2.0)


def test_synthetic_manifest_exact_reproduction(tmp_path: Path) -> None:
    manifest = write_fixture(
        tmp_path, canonical_smoke_scene(), seed=7,
        degradations=(DegradationStep("gamma", (1.1,)),),
    )
    assert len(manifest.output_sha256) == 64
    assert reproduce_fixture(tmp_path)


def test_feature_dense_scene_and_degradation_graph(tmp_path: Path) -> None:
    scene = coverage_scene(19)
    families = {shape.model_family for shape in scene.shapes}
    assert {"ring", "generic-bezier", "ribbon", "glyph-custom"} <= families
    assert any(item.kind.endswith("gradient") for item in scene.appearances)
    degradations = (
        DegradationStep("sharpen", (.4, .7)),
        DegradationStep("rotate", (.25,)),
        DegradationStep("palette", (12,)),
        DegradationStep("scan-noise", (1.0, 99)),
        DegradationStep("alpha-roundtrip-error", (.25,)),
    )
    image = render_synthetic(scene, RenderModel(), degradations)
    assert image.shape == (120, 160, 4) and image.dtype == np.uint8
    target = tmp_path / "sample.npz"
    write_training_sample(target, scene, input_rgba=image,
                          degradation_manifest=tuple({"kind": item.kind,
                                                      "parameters": item.parameters}
                                                     for item in degradations))
    archive = np.load(target, allow_pickle=False)
    metadata = json.loads(str(archive["metadata_json"]))
    assert metadata["policy"] if "policy" in metadata else metadata["schema"]
    assert len(exact_scene_labels(scene)["draw_order"]) == len(scene.shapes)


def test_licensed_font_scene_exact_outlines() -> None:
    font = Path(r"C:\Windows\Fonts\arial.ttf")
    if not font.is_file():
        return
    scene = font_text_scene(font, "Aa0", width=180, height=80, font_size=48)
    scene.validate()
    assert scene.shapes and all(shape.model_family == "glyph-font-synthetic"
                                for shape in scene.shapes)
    assert any(shape.negative_loops for shape in scene.shapes)


def test_text_profile_detects_light_glyphs_on_dark_field() -> None:
    gray_u8 = np.full((44, 96), 36, np.uint8)
    cv2.putText(gray_u8, "CITY", (7, 31), cv2.FONT_HERSHEY_SIMPLEX,
                .75, 245, 2, cv2.LINE_AA)
    gray = gray_u8.astype(np.float32) / 255.0
    gx = cv2.Scharr(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Scharr(gray, cv2.CV_32F, 0, 1)
    edge = np.sqrt(gx * gx + gy * gy)
    edge /= max(float(np.percentile(edge, 99)), 1e-6)
    field, probability = _text_field(gray, np.clip(edge, 0.0, 1.0))
    assert probability >= .5 and float(np.mean(field > .2)) > .01


def test_evidence_heads_ranges_and_cache(tmp_path: Path) -> None:
    source = tmp_path / "smoke.png"
    _write_smoke(source)
    raster = decode_raster(source)
    _, fields = diagnose_raster(raster)
    model = DeterministicEvidenceModel()
    bundle = model.infer(raster, fields, (1.0, .5))
    bundle.validate()
    key = evidence_cache_key(raster.source.source_hash, model.version, (1.0, .5))
    cache = EvidenceCache(tmp_path / "cache")
    cache.store(key, bundle)
    loaded = cache.load(key, source_hash=raster.source.source_hash,
                        model_version=model.version)
    assert loaded is not None
    assert loaded.levels[1].heads["boundary_prob"].shape == (16, 16)


def test_evidence_cache_key_binds_inference_implementation() -> None:
    arguments = ("source-sha", "model/version", (1.0, .5))
    with patch(
        "vice_scene.evidence_model.scene_evidence_implementation_sha256",
        return_value="implementation-a",
    ):
        first = evidence_cache_key(*arguments)
    with patch(
        "vice_scene.evidence_model.scene_evidence_implementation_sha256",
        return_value="implementation-b",
    ):
        changed = evidence_cache_key(*arguments)
        repeated = evidence_cache_key(*arguments)
    assert changed != first
    assert repeated == changed


def test_trainable_evidence_checkpoint_shapes_and_ranges(tmp_path: Path) -> None:
    import torch
    from vice_scene.neural_evidence import (HEAD_CHANNELS, TorchEvidenceModel,
                                            HYBRID_NEURAL_HEADS, HybridEvidenceModel,
                                            _activate, build_scene_evidence_net,
                                            select_best_evidence_model)
    model = build_scene_evidence_net(base_channels=8)
    raw = model(torch.zeros(1, 7, 33, 31))
    assert set(raw) == set(HEAD_CHANNELS)
    assert all(tuple(value.shape[-2:]) == (33, 31) for value in raw.values())
    checkpoint = tmp_path / "evidence.pt"
    torch.save({"state_dict": model.state_dict(), "base_channels": 8}, checkpoint)
    source = tmp_path / "source.png"
    _write_smoke(source)
    raster = decode_raster(source)
    _, fields = diagnose_raster(raster)
    bundle = TorchEvidenceModel(checkpoint, device="cpu").infer(raster, fields, (1.0, .5))
    bundle.validate()
    probabilities = ("boundary_prob", "coverage_alpha", "corner_prob", "corner_type",
                     "junction_prob", "shape_class_logits", "text_line_prob", "glyph_occupancy",
                     "stroke_centerline_prob", "symmetry_evidence", "uncertainty")
    assert all(np.all((bundle.levels[0].heads[name] >= 0)
                         & (bundle.levels[0].heads[name] <= 1))
               for name in probabilities)
    logits = np.asarray([[[-2.0, 2.0, 0.0, 1.0]]], np.float32)
    activated = _activate("shape_class_logits", logits)
    assert np.all((activated > 0.0) & (activated < 1.0))
    assert activated[0, 0, 0] < .2 and activated[0, 0, 1] > .8
    selection = select_best_evidence_model(tmp_path / "missing-promoted.pt")
    assert not selection.checkpoint_loaded
    assert selection.fallback_reason == "promoted evidence checkpoint is missing"
    assert selection.model.version.startswith("deterministic-evidence/")
    candidate = tmp_path / "candidate.pt"
    torch.save({"state_dict": model.state_dict(), "base_channels": 8,
                "schema": "vice-scene-evidence-checkpoint/1",
                "status": "candidate"}, candidate)
    hybrid = HybridEvidenceModel(candidate, device="cpu")
    hybrid_bundle = hybrid.infer(raster, fields, (1.0,))
    deterministic = DeterministicEvidenceModel().infer(raster, fields, (1.0,))
    learned = TorchEvidenceModel(candidate, device="cpu").infer(raster, fields, (1.0,))
    for name in deterministic.levels[0].heads:
        expected = (learned.levels[0].heads[name] if name in HYBRID_NEURAL_HEADS
                    else deterministic.levels[0].heads[name])
        assert np.array_equal(hybrid_bundle.levels[0].heads[name], expected)


def test_evidence_training_reads_train_split_only(tmp_path: Path) -> None:
    from train_scene_evidence import _split_files

    train = tmp_path / "train"; train.mkdir()
    validation = tmp_path / "validation"; validation.mkdir()
    test = tmp_path / "test"; test.mkdir()
    (train / "a.npz").touch(); (validation / "b.npz").touch(); (test / "c.npz").touch()
    assert _split_files(tmp_path, "train") == [train / "a.npz"]


def test_soft_appearance_does_not_materialize_aa_colours(tmp_path: Path) -> None:
    source = tmp_path / "smoke.png"
    _write_smoke(source)
    raster = decode_raster(source)
    profile, fields = diagnose_raster(raster)
    evidence = DeterministicEvidenceModel().infer(raster, fields, (1.0, .5, .25))
    appearances = infer_appearances(raster, profile)
    topologies = build_topology_hypotheses(appearances, evidence)
    assert appearances.appearances[appearances.background_index].rgba_linear[3] == 0.0
    assert all(len(item.regions) == 2 for item in topologies)


def test_opaque_background_island_can_be_foreground_knockout(tmp_path: Path) -> None:
    image = np.full((24, 24, 4), 255, np.uint8)
    image[3:21, 3:21, :3] = (210, 35, 45)
    image[8:16, 9:15, :3] = 255
    source = tmp_path / "opaque-knockout.png"
    Image.fromarray(image, "RGBA").save(source)
    raster = decode_raster(source)
    profile, fields = diagnose_raster(raster)
    evidence = DeterministicEvidenceModel().infer(raster, fields, (1.0, .5))
    appearances = infer_appearances(raster, profile, max_colors=4)
    topology = build_topology_hypotheses(appearances, evidence, top_k=1)[0]
    islands = [region for region in topology.regions
               if region.appearance_index == appearances.background_index]
    assert islands and all(region.bbox[0] > 0 and region.bbox[1] > 0
                           and region.bbox[2] < raster.width
                           and region.bbox[3] < raster.height
                           for region in islands)


def test_topology_shortlist_preserves_balanced_detail_proposal() -> None:
    rows = [SimpleNamespace(id="coarse", score=.10, operations=("coarse",)),
            SimpleNamespace(id="morph", score=.11, operations=("morph",)),
            SimpleNamespace(id="balanced", score=.14,
                            operations=("soft-spatial-proposal-sigma-0.65",))]
    selected = _shortlist_topologies(rows, 2)
    assert rows[0] in selected and rows[2] in selected


def test_analytic_gradient_beats_solid_when_supported(tmp_path: Path) -> None:
    width, height = 32, 20
    x = np.linspace(0.05, .9, width, dtype=np.float32)
    linear = np.zeros((height, width, 4), np.float32)
    linear[..., 0] = x
    linear[..., 1] = .2
    linear[..., 2] = .1
    linear[..., 3] = 1.0
    from vice_scene.ingest import linear_to_srgb
    path = tmp_path / "gradient.png"
    Image.fromarray((np.dstack((linear_to_srgb(linear[..., :3]), linear[..., 3])) * 255 + .5).astype(np.uint8), "RGBA").save(path)
    raster = decode_raster(path)
    solid = Appearance("a", "solid", (.45, .2, .1, 1.0))
    fitted = fit_region_appearance(raster, np.ones((height, width), bool), solid)
    assert fitted.kind == "linear-gradient"
    assert len(fitted.stops) == 2


_d_t = np.linspace(-np.pi / 2, np.pi / 2, 24)
_d_arc = np.column_stack((12 + 36 * .45 + 36 * .55 * np.cos(_d_t),
                          12 + 48 * .5 + 48 * .5 * np.sin(_d_t)))
_d_points = tuple(map(tuple, np.vstack(((12, 12), _d_arc, (12, 60), (12, 12)))))
_ribbon_x = np.linspace(8, 64, 29)
_ribbon_center = 36 + 5 * np.sin((_ribbon_x - 8) / 56 * np.pi)
_ribbon_points = tuple(map(tuple, np.vstack((
    np.column_stack((_ribbon_x, _ribbon_center - 4)),
    np.column_stack((_ribbon_x[::-1], _ribbon_center[::-1] + 4)),
    (_ribbon_x[0], _ribbon_center[0] - 4),
))))


SHAPE_CASES = [
    ("circle", GeometryPrimitive("circle", (36, 36, 18)), None),
    ("ellipse", GeometryPrimitive("ellipse", (36, 36, 20, 12, 23)), None),
    ("rectangle", GeometryPrimitive("rect", (36, 36, 34, 22, 17)), None),
    ("rounded-rectangle", GeometryPrimitive("rounded-rect", (36, 36, 36, 24, 0, 5)), None),
    ("triangle", GeometryPrimitive("triangle", points=((8, 60), (27, 8), (66, 51), (8, 60))), None),
    ("isosceles-triangle", GeometryPrimitive("triangle", points=((10, 58), (36, 10), (62, 58), (10, 58))), None),
    ("quadrilateral", GeometryPrimitive("quadrilateral", points=((10, 55), (18, 14), (58, 10), (64, 58), (10, 55))), None),
    ("star-3", GeometryPrimitive("star", (36, 36, 24, 10, 3, -.5)), None),
    ("star-4", GeometryPrimitive("star", (36, 36, 24, 10, 4, -.5)), None),
    ("star-5", GeometryPrimitive("star", (36, 36, 24, 10, 5, -.5)), None),
    ("star-6", GeometryPrimitive("star", (36, 36, 24, 10, 6, -.5)), None),
    ("D-shape", GeometryPrimitive("D-shape", (1,), points=_d_points), None),
    ("ring", GeometryPrimitive("circle", (36, 36, 24)), GeometryPrimitive("circle", (36, 36, 13))),
    ("ribbon", GeometryPrimitive("polyline", points=_ribbon_points), None),
]


@pytest.mark.parametrize("family,primitive,hole", SHAPE_CASES)
def test_whole_shape_family_is_in_tournament(family: str, primitive: GeometryPrimitive,
                                             hole: GeometryPrimitive | None) -> None:
    region = _region_from_geometry(primitive, hole=hole)
    best, candidates = tournament_region(region)
    assert family in {candidate.family for candidate in candidates}
    assert best.family == family


def test_complete_circle_lsq_rejects_unidentifiable_giant_arc() -> None:
    theta = np.linspace(np.deg2rad(80), np.deg2rad(100), 40)
    contour = np.column_stack((32 + 110 * np.cos(theta),
                               -95 + 110 * np.sin(theta))).astype(np.float32)
    mask = np.zeros((64, 64), np.uint8)
    cv2.polylines(mask, [np.round(contour).astype(np.int32).reshape(-1, 1, 2)],
                  False, 1, 2)
    assert _fit_circle(mask, contour, (), None) is None


def test_angular_glyph_counter_is_not_forced_to_an_ellipse() -> None:
    contour = np.asarray(((4, 4), (18, 4), (18, 7), (9, 7),
                          (9, 15), (18, 15), (18, 18), (4, 18),
                          (4, 4)), np.float32)
    geometry = _fit_hole_geometry(contour)
    assert len(geometry) == 1 and geometry[0].kind == "polyline"


def test_physical_cost_is_lattice_invariant() -> None:
    coarse_x = np.linspace(0.0, 10.0, 21)
    fine_x = np.linspace(0.0, 10.0, 81)
    coarse_points = np.column_stack((coarse_x, np.zeros_like(coarse_x)))
    fine_points = np.column_stack((fine_x, np.zeros_like(fine_x)))
    coarse_residual = .25 + .1 * np.sin(coarse_x)
    fine_residual = .25 + .1 * np.sin(fine_x)
    assert physical_residual_cost(coarse_residual, coarse_points) == pytest.approx(
        physical_residual_cost(fine_residual, fine_points), abs=2e-4)


def test_shared_boundary_analytic_curve_vocabulary() -> None:
    angle = np.linspace(0.0, 1.4, 33)
    points = np.column_stack((20 + 9 * np.cos(angle), 15 + 9 * np.sin(angle)))
    geometry = fit_interface_run(InterfaceRun(0, 1, points, np.ones(33, np.float32)))
    assert len(geometry) == 1 and geometry[0].kind == "circular-arc"


def test_shared_interface_is_one_object() -> None:
    labels = np.full((8, 10), -1, np.int32)
    labels[:, :5] = 0
    labels[:, 5:] = 1
    regions = (
        RegionProposal("r0", 0, labels == 0, 40, (0, 0, 5, 8),
                       np.array([[0, 0], [5, 0], [5, 8], [0, 8]], np.float32), (), None, 1),
        RegionProposal("r1", 1, labels == 1, 40, (5, 0, 10, 8),
                       np.array([[5, 0], [10, 0], [10, 8], [5, 8]], np.float32), (), None, 1),
    )
    topology = TopologyHypothesis("t", regions, labels, -1, 0.0, ())
    edges = solve_shared_interfaces(topology, ("s0", "s1"))
    shared = [edge for edge in edges if {edge.left_shape, edge.right_shape} == {"s0", "s1"}]
    assert len(shared) == 1
    assert shared[0].geometry[0].kind == "line"


def test_shared_interface_consumes_bounded_subpixel_offsets() -> None:
    labels = np.full((8, 10), -1, np.int32)
    labels[:, :5] = 0
    labels[:, 5:] = 1
    regions = (
        RegionProposal("r0", 0, labels == 0, 40, (0, 0, 5, 8),
                       np.array([[0, 0], [5, 0], [5, 8], [0, 8]], np.float32), (), None, 1),
        RegionProposal("r1", 1, labels == 1, 40, (5, 0, 10, 8),
                       np.array([[5, 0], [10, 0], [10, 8], [5, 8]], np.float32), (), None, 1),
    )
    topology = TopologyHypothesis("t", regions, labels, -1, 0.0, ())
    offsets = np.zeros((8, 10, 2), np.float32)
    offsets[..., 0] = .25
    edges = solve_shared_interfaces(topology, ("s0", "s1"),
                                    np.ones((8, 10), np.float32), offsets)
    shared = next(edge for edge in edges
                  if {edge.left_shape, edge.right_shape} == {"s0", "s1"})
    points = np.asarray(shared.geometry[0].points)
    assert float(np.mean(points[:, 0])) == pytest.approx(5.25, abs=.03)


def test_bbox_local_geometry_render_matches_full_lattice_crop() -> None:
    positive = (GeometryPrimitive("rounded-rect", (83.2, 57.7, 31.5, 18.25, 17.0, 4.1)),)
    negative = ((GeometryPrimitive("circle", (83.0, 57.5, 3.75)),),)
    full = render_geometry_mask((140, 180), positive, negative, supersample=4)
    x0, y0, x1, y1 = 58, 38, 110, 82
    local = render_geometry_mask((y1 - y0, x1 - x0), positive, negative,
                                 supersample=4, origin=(x0, y0))
    assert np.array_equal(local, full[y0:y1, x0:x1])


def test_glyph_catastrophe_metric() -> None:
    descriptor = (0.0,) * 10
    before = (GlyphInstance("a", (0, 0, 5, 8), 8, 8, 1, 1, 1, descriptor),)
    after = (replace(before[0], counters=0),)
    assert glyph_catastrophe_count(before, after) == 1


def test_font_free_sdf_preserves_components_and_counters() -> None:
    mask = np.zeros((24, 24), np.uint8)
    cv2.rectangle(mask, (4, 3), (18, 20), 1, -1)
    cv2.rectangle(mask, (8, 7), (14, 16), 0, -1)
    rebuilt = font_free_sdf_reconstruct(mask > 0, 4.0)
    assert cv2.connectedComponents(rebuilt.astype(np.uint8))[0] == 2
    contours, hierarchy = cv2.findContours(rebuilt.astype(np.uint8), cv2.RETR_CCOMP,
                                            cv2.CHAIN_APPROX_SIMPLE)
    assert hierarchy is not None and sum(row[3] >= 0 for row in hierarchy[0]) == 1


def test_exact_font_path_a_creates_scene_hypothesis() -> None:
    scene = canonical_smoke_scene()
    glyph_scene = replace(scene, shapes=tuple(replace(shape, model_family="glyph")
                                              for shape in scene.shapes))
    points = [np.array([[5, 5], [25, 5]], float), np.array([[25, 5], [25, 25]], float),
              np.array([[25, 25], [5, 25]], float), np.array([[5, 25], [5, 5]], float)]
    curves = [SimpleNamespace(degree=1, control=value) for value in points]
    trial = apply_exact_font_substitution(glyph_scene, {
        "bbox": (0, 0, 32, 32), "loops": [curves], "font": "Fixture Sans",
        "text": "A", "iou": .98,
    })
    assert trial is not None
    assert any(shape.model_family == "glyph-font" for shape in trial.shapes)
    trial.validate()


def test_optimizer_monotonic_guard() -> None:
    assert_monotonic((OptimizationAudit("good", True, 2.0, 1.0, ""),
                      OptimizationAudit("rollback", False, 1.0, 3.0, "")))
    with pytest.raises(AssertionError):
        assert_monotonic((OptimizationAudit("bad", True, 1.0, 1.1, ""),))


def test_exact_font_path_requires_resolvable_native_text() -> None:
    font = Path(r"C:\Windows\Fonts\arial.ttf")
    if not font.is_file():
        return
    tiny = font_text_scene(font, "TEST", width=96, height=28, font_size=10)
    large = font_text_scene(font, "TEST", width=180, height=64, font_size=30)
    assert not _exact_font_path_supported(tiny)
    assert _exact_font_path_supported(large)


def test_global_mdl_does_not_reward_component_or_glyph_collapse() -> None:
    """A better-supported detailed text scene must survive the global court.

    This is the minimal regression for the production failure where a
    15-region/6-glyph scene beat a 58-region/37-glyph scene solely because
    local candidate MDLs were summed as if each were a full-image penalty.
    """
    def build(shape_count: int, glyph_count: int,
              topology_score: float) -> SceneBuildResult:
        shapes = tuple(SimpleNamespace(
            negative_loops=(), model_family=("glyph" if index < glyph_count else "generic"),
            confidence=1.0,
        ) for index in range(shape_count))
        graph = SimpleNamespace(shapes=shapes, constraints=())
        selected = {f"shape-{index}": SimpleNamespace(mdl=.014)
                    for index in range(shape_count)}
        return SceneBuildResult(graph, {}, selected, f"topology-{shape_count}",
                                topology_score)

    model = RenderModel("hard", supersample=1)
    coarse = _breakdown(
        build(15, 6, .100),
        ForwardScore(model, .190, .0, .0, .0),
    )
    detailed = _breakdown(
        build(58, 37, .135),
        ForwardScore(model, .160, .0, .0, .0),
    )
    assert coarse.mdl == pytest.approx(detailed.mdl)
    assert detailed.total < coarse.total


def test_forward_court_selects_known_renderer(tmp_path: Path) -> None:
    source = tmp_path / "smoke.png"
    _write_smoke(source)
    raster = decode_raster(source)
    winner, scores = select_forward_model(
        canonical_smoke_scene(), raster,
        forward_model_catalog(("clean-aa", "hard", "blur-0.6", "gamma-1.8", "jpeg-70")),
    )
    assert winner.model.name == "clean-aa"
    assert len(scores) == 5


def test_forward_score_is_premultiplied_alpha_exact(tmp_path: Path) -> None:
    scene = replace(canonical_smoke_scene(), appearances=(
        replace(canonical_smoke_scene().appearances[0],
                rgba_linear=(.8, .1, .05, .37)),
        canonical_smoke_scene().appearances[1],
    ))
    source = tmp_path / "alpha.png"
    Image.fromarray(render_scene(scene), "RGBA").save(source)
    score = score_forward(scene, decode_raster(source), RenderModel())
    assert score.color_mae < 2e-3 and score.alpha_mae < 2e-3


def test_independent_synthetic_renderer_adapter() -> None:
    scene = canonical_smoke_scene()
    analytic = render_with_family(scene, "vice-analytic")
    pillow = render_with_family(scene, "pillow-polygon")
    assert analytic.shape == pillow.shape == (32, 32, 4)
    assert np.mean(np.abs(analytic.astype(float) - pillow.astype(float))) < 15.0
    opencv = render_with_family(scene, "opencv-polygon")
    assert opencv.shape == analytic.shape


def test_export_adapters_and_native_elements(tmp_path: Path) -> None:
    scene = canonical_smoke_scene()
    svg = scene_to_svg(scene, mode="stacked")
    assert "<circle" in svg and 'fill-rule="evenodd"' in svg
    no_hole_shapes = tuple(replace(shape, negative_loops=())
                           if shape.id == "shape-rounded" else shape for shape in scene.shapes)
    assert "<rect" in scene_to_svg(replace(scene, shapes=no_hole_shapes), mode="stacked")
    export_svg(tmp_path / "scene.svg", scene, mode="cutout")
    assert '<mask id="cutout-' in (tmp_path / "scene.svg").read_text(encoding="utf-8")
    export_pdf_or_eps(tmp_path / "scene.pdf", scene, mode="cutout")
    export_pdf_or_eps(tmp_path / "scene.eps", scene, mode="cutout")
    export_dxf(tmp_path / "scene.dxf", scene, mode="cutout")
    export_png(tmp_path / "scene-4x-aa.png", scene, scale=4, antialias=True)
    export_png(tmp_path / "scene-native-hard.png", scene, scale=1, antialias=False)
    export_png(tmp_path / "scene-custom.png", scene, size=(77, 53), antialias=True)
    assert Image.open(tmp_path / "scene-custom.png").size == (77, 53)
    assert 'data-group-by="layer"' in scene_to_svg(scene, group_by="layer")
    assert "<circle" not in scene_to_svg(scene, preserve_parametric=False)
    assert all((tmp_path / name).stat().st_size > 100 for name in
               ("scene.svg", "scene.pdf", "scene.eps", "scene.dxf"))


def test_residual_add_one_and_remove_one(tmp_path: Path) -> None:
    target = np.zeros((32, 32, 4), np.uint8)
    target[10:19, 12:21] = (230, 40, 20, 255)
    source = tmp_path / "target.png"
    Image.fromarray(target, "RGBA").save(source)
    raster = decode_raster(source)
    empty = SceneGraph(32, 32, (), (), ())
    added, audits = residual_add_prune(empty, raster,
                                       lambda graph: 2.0 - .5 * len(graph.shapes),
                                       threshold=.05, min_area_px=2)
    assert len(added.shapes) == 1 and any(row.action == "add" and row.accepted
                                         for row in audits)
    weak = replace(added, shapes=(replace(added.shapes[0], confidence=.0,
                                         provenance=("residual-add",)),))
    pruned, prune_audits = residual_add_prune(
        weak, raster, lambda graph: float(len(graph.shapes)), threshold=10.0)
    assert not pruned.shapes and any(row.action == "prune" and row.accepted
                                    for row in prune_audits)


def test_residual_repair_caps_rejected_attempts(tmp_path: Path) -> None:
    target = np.zeros((48, 48, 4), np.uint8)
    for y in (3, 13, 23, 33):
        for x in (3, 15, 27):
            target[y:y + 5, x:x + 5] = (220, 50, 30, 255)
    source = tmp_path / "many-residuals.png"
    Image.fromarray(target, "RGBA").save(source)
    raster = decode_raster(source)
    empty = SceneGraph(48, 48, (), (), ())
    _result, audits = residual_add_prune(
        empty, raster, lambda _graph: 1.0,
        threshold=.05, min_area_px=2, max_additions=4, max_attempts=3)
    assert sum(row.action == "add" for row in audits) <= 3


def test_residual_repair_cannot_add_a_whole_canvas_eraser(tmp_path: Path) -> None:
    target = np.full((48, 48, 4), (255, 255, 255, 255), np.uint8)
    target[4:44, 4:44] = (220, 40, 30, 255)
    source = tmp_path / "broad-residual.png"
    Image.fromarray(target, "RGBA").save(source)
    raster = decode_raster(source)
    empty = SceneGraph(48, 48, (), (), ())
    result, audits = residual_add_prune(
        empty, raster, lambda graph: 0.0 if graph.shapes else 1.0,
        threshold=.05, min_area_px=2, max_additions=4, max_attempts=4)
    assert not result.shapes
    assert any("broad residual" in row.reason for row in audits)


def test_end_to_end_32px_smoke(tmp_path: Path) -> None:
    source = tmp_path / "smoke.png"
    _write_smoke(source)
    report = process_scene(source, tmp_path / "out", config=EngineConfig(topology_k=4))
    output = tmp_path / "out" / "smoke"
    assert report["regions"] == 2
    assert report["templates"] == {"circle": 1, "rounded-rectangle": 1}
    for name in ("01_contour.png", "02_primitive_map.svg", "02_primitive_map.png",
                 "03_rebuilt_filled.svg", "03_rebuilt_filled.png", "04_corners.png",
                 "scene.json", "decision_trace.json", "config.json", "profile.json", "report.json"):
        assert (output / name).is_file(), name
    trace = json.loads((output / "decision_trace.json").read_text(encoding="utf-8"))
    assert {row["stage"] for row in trace["records"]} >= {
        "ingest", "evidence", "appearance", "topology", "scene-build",
        "optimizer", "final-court", "residual", "export",
    }


def test_explicit_legacy_fallback_contract(tmp_path: Path) -> None:
    source = tmp_path / "source.png"; _write_smoke(source)
    legacy_output = tmp_path / "out" / "source"
    with (patch("vice_scene.pipeline._process_scene_impl", side_effect=RuntimeError("fixture")),
          patch("vice_scene.legacy_adapter.run_legacy",
                return_value=LegacyResult({"regions": 1}, legacy_output, "paper-regions"))):
        report = process_scene(source, tmp_path / "out",
                               config=EngineConfig(allow_legacy_fallback=True))
    assert report["engine"] == "legacy-fallback"
    assert (legacy_output / "scene_fallback.json").is_file()


def _run_direct() -> None:
    with tempfile.TemporaryDirectory(dir=Path.cwd() / "tmp") as raw:
        root = Path(raw)
        test_scene_contract_roundtrip_and_dag_guard()
        for index, (suffix, format_name) in enumerate(DECODER_CASES):
            target = root / f"decoder-{index}"
            target.mkdir()
            test_canonical_ingest_supported_decoders(target, suffix, format_name)
        target = root / "alpha"; target.mkdir(); test_ingest_alpha_and_pixel_transform(target)
        target = root / "exif"; target.mkdir(); test_ingest_fractional_crop_and_exif_orientation(target)
        target = root / "synthetic"; target.mkdir(); test_synthetic_manifest_exact_reproduction(target)
        target = root / "synthetic-dense"; target.mkdir(); test_feature_dense_scene_and_degradation_graph(target)
        test_licensed_font_scene_exact_outlines()
        test_text_profile_detects_light_glyphs_on_dark_field()
        target = root / "evidence"; target.mkdir(); test_evidence_heads_ranges_and_cache(target)
        target = root / "neural"; target.mkdir(); test_trainable_evidence_checkpoint_shapes_and_ranges(target)
        target = root / "evidence-split"; target.mkdir(); test_evidence_training_reads_train_split_only(target)
        target = root / "appearance"; target.mkdir(); test_soft_appearance_does_not_materialize_aa_colours(target)
        target = root / "knockout"; target.mkdir(); test_opaque_background_island_can_be_foreground_knockout(target)
        test_topology_shortlist_preserves_balanced_detail_proposal()
        target = root / "gradient"; target.mkdir(); test_analytic_gradient_beats_solid_when_supported(target)
        for family, primitive, hole in SHAPE_CASES:
            test_whole_shape_family_is_in_tournament(family, primitive, hole)
        test_complete_circle_lsq_rejects_unidentifiable_giant_arc()
        test_angular_glyph_counter_is_not_forced_to_an_ellipse()
        test_physical_cost_is_lattice_invariant()
        test_shared_boundary_analytic_curve_vocabulary()
        test_shared_interface_is_one_object()
        test_shared_interface_consumes_bounded_subpixel_offsets()
        test_bbox_local_geometry_render_matches_full_lattice_crop()
        test_glyph_catastrophe_metric()
        test_font_free_sdf_preserves_components_and_counters()
        test_exact_font_path_a_creates_scene_hypothesis()
        test_optimizer_monotonic_guard()
        test_global_mdl_does_not_reward_component_or_glyph_collapse()
        test_exact_font_path_requires_resolvable_native_text()
        target = root / "forward"; target.mkdir(); test_forward_court_selects_known_renderer(target)
        target = root / "forward-alpha"; target.mkdir(); test_forward_score_is_premultiplied_alpha_exact(target)
        test_independent_synthetic_renderer_adapter()
        target = root / "export"; target.mkdir(); test_export_adapters_and_native_elements(target)
        target = root / "residual"; target.mkdir(); test_residual_add_one_and_remove_one(target)
        target = root / "residual-cap"; target.mkdir(); test_residual_repair_caps_rejected_attempts(target)
        target = root / "residual-broad"; target.mkdir(); test_residual_repair_cannot_add_a_whole_canvas_eraser(target)
        target = root / "end-to-end"; target.mkdir(); test_end_to_end_32px_smoke(target)
        target = root / "fallback"; target.mkdir(); test_explicit_legacy_fallback_contract(target)
    print("scene build checks: OK")


if __name__ == "__main__":
    _run_direct()

"""Fast Strike-6 gates for variable strokes and internal seam underpaint."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import geometry_vectorizer as gv


def _rectangle_loop(x0: float, y0: float, x1: float, y1: float,
                    template: str = "rect") -> gv.FittedLoop:
    points = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)
    curves = [gv.Curve(1, np.vstack((points[index], points[(index + 1) % 4])))
              for index in range(4)]
    return gv.FittedLoop(points, curves, template)


def test_pelt_finds_physical_width_changepoint() -> None:
    widths = np.r_[np.full(30, 4.0), np.full(30, 9.0)]
    segments = gv._pelt_width_segments(widths)
    assert [(start, end) for start, end, _width in segments] == [(0, 30), (30, 60)]
    assert [width for _start, _end, width in segments] == [4.0, 9.0]


def test_variable_width_stroke_passes_topology_render_court() -> None:
    mask = np.zeros((80, 180), np.uint8)
    cv2.line(mask, (15, 40), (90, 40), 255, 5)
    cv2.line(mask, (88, 40), (165, 40), 255, 11)
    specs = gv._detect_variable_strokes(mask > 0, analysis_scale=1)
    assert specs is not None
    assert len(specs) >= 2
    widths = [float(spec[0]) for spec in specs]
    assert max(widths) - min(widths) >= 2.0


def test_constant_ribbon_stays_in_existing_single_width_lane() -> None:
    mask = np.zeros((60, 150), np.uint8)
    cv2.line(mask, (15, 30), (135, 30), 255, 7)
    cv2.circle(mask, (15, 30), 4, 255, -1)
    cv2.circle(mask, (135, 30), 4, 255, -1)
    assert gv._detect_variable_strokes(mask > 0, analysis_scale=1) is None


def test_shared_underpaint_has_no_external_silhouette_path() -> None:
    left = np.zeros((40, 60), bool)
    right = np.zeros_like(left)
    left[5:35, 5:30] = True
    right[5:35, 30:55] = True
    reference = np.full((40, 60, 3), 255, np.uint8)
    reference[left] = (20, 80, 160)
    reference[right] = (230, 120, 40)
    underpaint = gv._shared_edge_underpaint_regions([left, right], reference, 1)
    assert len(underpaint) == 1
    stroke = underpaint[0].stroke
    assert stroke[4] == "butt"
    segment = stroke[1][0].control
    assert np.allclose(segment, [[30.0, 5.0], [30.0, 35.0]])


def test_multiscale_reference_render_has_no_internal_background_seam() -> None:
    left = np.zeros((40, 60), bool)
    right = np.zeros_like(left)
    left[5:35, 5:30] = True
    right[5:35, 30:55] = True
    reference = np.full((40, 60, 3), 255, np.uint8)
    reference[left] = (20, 80, 160)
    reference[right] = (230, 120, 40)
    regions = gv._shared_edge_underpaint_regions([left, right], reference, 1)
    regions += [
        gv.Region((20, 80, 160), int(left.sum()),
                  [_rectangle_loop(5, 5, 30, 35)]),
        gv.Region((230, 120, 40), int(right.sum()),
                  [_rectangle_loop(30, 5, 55, 35)]),
    ]
    for scale in (1, 2, 4):
            image = np.asarray(gv.render_regions(
                regions, (60, 40), outline=False, scale=scale), np.uint8)
            x = 30
            y0, y1 = 10, 30
            seam = image[y0:y1, max(0, x - 1):min(image.shape[1], x + 1)]
            assert not np.any(np.all(seam >= 250, axis=2)), (scale, seam.max())


def test_underpaint_width_is_measured_by_real_svg_renderer() -> None:
    gv._UNDERPAINT_WIDTH_CACHE[0] = None
    gv._UNDERPAINT_RENDERER_AUDIT.clear()
    width = gv._calibrate_underpaint_width()
    assert width > 0.0
    assert any(item.get("renderer") == "resvg" and item.get("available")
               for item in gv._UNDERPAINT_RENDERER_AUDIT), gv._UNDERPAINT_RENDERER_AUDIT
    assert all(item.get("scales") == [0.5, 1.0, 2.0]
               for item in gv._UNDERPAINT_RENDERER_AUDIT if item.get("available"))


def test_multiscale_svg_has_no_seam_in_resvg() -> None:
    import resvg_py

    left = np.zeros((40, 60), bool)
    right = np.zeros_like(left)
    left[5:35, 5:30] = True
    right[5:35, 30:55] = True
    reference = np.full((40, 60, 3), 255, np.uint8)
    reference[left] = (20, 80, 160)
    reference[right] = (230, 120, 40)
    regions = gv._shared_edge_underpaint_regions([left, right], reference, 1)
    regions += [
        gv.Region((20, 80, 160), int(left.sum()),
                  [_rectangle_loop(5, 5, 30, 35)]),
        gv.Region((230, 120, 40), int(right.sum()),
                  [_rectangle_loop(30, 5, 55, 35)]),
    ]
    def no_white_seam(image: Image.Image, scale: float) -> None:
        rgb = np.asarray(image.convert("RGB"), np.uint8)
        x = int(round(30 * scale))
        y0, y1 = int(round(10 * scale)), int(round(30 * scale))
        seam = rgb[y0:y1, max(0, x - 1):min(rgb.shape[1], x + 1)]
        assert seam.size and not np.any(np.all(seam >= 250, axis=2)), (
            scale, rgb.shape, seam.max())

    with tempfile.TemporaryDirectory(prefix="v_ice_svg_gate_") as temporary:
        root = Path(temporary)
        gv.write_svgs(root, regions, (60, 40))
        svg = (root / "03_rebuilt_filled.svg").read_text(encoding="utf-8")
        for scale in (0.5, 1.0, 2.0):
            width = int(round(60 * scale))
            resvg_png = resvg_py.svg_to_bytes(svg_string=svg, width=width)
            no_white_seam(Image.open(io.BytesIO(resvg_png)), scale)


if __name__ == "__main__":
    test_pelt_finds_physical_width_changepoint()
    test_variable_width_stroke_passes_topology_render_court()
    test_constant_ribbon_stays_in_existing_single_width_lane()
    test_shared_underpaint_has_no_external_silhouette_path()
    test_multiscale_reference_render_has_no_internal_background_seam()
    test_underpaint_width_is_measured_by_real_svg_renderer()
    test_multiscale_svg_has_no_seam_in_resvg()
    print("Stroke/seam regression checks: PASS")

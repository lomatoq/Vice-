"""Fast synthetic gates for Strike-4 digital circle intent."""

from __future__ import annotations

from io import BytesIO

import cv2
import numpy as np
from PIL import Image

import geometry_vectorizer as gv


def _contour(mask: np.ndarray, mode: int = cv2.RETR_EXTERNAL) -> np.ndarray:
    contours, _hierarchy = cv2.findContours(mask, mode, cv2.CHAIN_APPROX_NONE)
    chosen = max(contours, key=lambda value: abs(cv2.contourArea(value)))
    points = chosen.reshape(-1, 2).astype(float)
    return np.vstack((points, points[:1]))


def _line_chain(loop: np.ndarray) -> list:
    return [gv.Curve(1, np.vstack((loop[index], loop[index + 1])))
            for index in range(len(loop) - 1)]


def test_circle_is_separable_but_square_and_ellipse_are_not() -> None:
    circle = np.zeros((72, 72), np.uint8)
    cv2.circle(circle, (36, 36), 12, 255, -1)
    assert gv._circular_separability(_contour(circle), 0.25)["feasible"]

    square = np.zeros_like(circle)
    cv2.rectangle(square, (22, 22), (50, 50), 255, -1)
    assert not gv._circular_separability(_contour(square), 0.25)["feasible"]

    ellipse = np.zeros_like(circle)
    cv2.ellipse(ellipse, (36, 36), (17, 10), 0, 0, 360, 255, -1)
    assert not gv._circular_separability(_contour(ellipse), 0.25)["feasible"]


def test_circle_wins_mdl_tournament_only_after_feasibility() -> None:
    mask = np.zeros((72, 72), np.uint8)
    cv2.circle(mask, (36, 36), 12, 255, -1)
    loop = _contour(mask)
    winner = gv._digital_circle_tournament(loop, _line_chain(loop), 0.25)
    assert winner is not None
    assert len(winner) == 4
    assert all(curve.degree == 3 for curve in winner)


def test_q30_circle_keeps_a_codec_derived_outlier_budget() -> None:
    clean = np.full((96, 96, 3), 255, np.uint8)
    cv2.circle(clean, (48, 48), 13, (15, 15, 15), -1)
    stream = BytesIO()
    Image.fromarray(clean).save(stream, format="JPEG", quality=30, subsampling=0)
    stream.seek(0)
    observed = Image.open(stream)
    old = gv._CODEC_CONDITION[0]
    try:
        gv._CODEC_CONDITION[0] = gv.estimate_jpeg_condition(observed)
        gray = np.asarray(observed.convert("L"), np.uint8)
        binary = (gray < 128).astype(np.uint8) * 255
        result = gv._circular_separability(_contour(binary), 1.0)
        assert result["feasible"], result
        assert result["outlier_budget"] > 0, result
        assert result["outliers"] <= result["outlier_budget"]
    finally:
        gv._CODEC_CONDITION[0] = old


def test_repeated_radius_group_prior_shares_only_supported_radius() -> None:
    loops = []
    for center, radius in ((np.array([20.0, 20.0]), 10.0),
                           (np.array([52.0, 20.0]), 10.1)):
        angles = np.linspace(0.0, 2.0 * np.pi, 64, endpoint=False)
        source = center + radius * np.column_stack((np.cos(angles), np.sin(angles)))
        curves = gv._tag_arcs(
            gv._ellipse_curves(center, np.array([radius, radius]), 0.0), center, radius)
        loops.append(gv.FittedLoop(source, curves, "paper-circle-court"))
    regions = [gv.Region((0, 0, 0), 100, [loop]) for loop in loops]
    gv._regularize_repeated_circle_radii(regions)
    radii = [float(region.loops[0].curves[0].meta[3]) for region in regions]
    assert abs(radii[0] - radii[1]) < 1e-12, radii


def test_concentric_ring_court_shares_center_without_changing_hole() -> None:
    loops = []
    for center, radius in ((np.array([36.04, 35.98]), 15.0),
                           (np.array([35.96, 36.02]), 8.0)):
        angles = np.linspace(0.0, 2.0 * np.pi, 96, endpoint=False)
        source = center + radius * np.column_stack((np.cos(angles), np.sin(angles)))
        loops.append(gv.FittedLoop(source, _line_chain(np.vstack((source, source[:1]))),
                                   "incumbent"))
    region = gv.Region((15, 15, 15), 1000, loops)
    before_count = len(region.loops)
    gv._regularize_concentric_rings([region])
    assert len(region.loops) == before_count == 2
    centers = [np.asarray(loop.curves[0].meta[2], float) for loop in region.loops]
    assert np.linalg.norm(centers[0] - centers[1]) < 1e-12, centers
    radii = [float(loop.curves[0].meta[3]) for loop in region.loops]
    assert max(radii) > min(radii)
    assert {loop.template for loop in region.loops} == {
        "paper-concentric-ring-outer", "paper-concentric-ring-inner"}


def test_q30_ring_degradation_keeps_persistent_hole_and_shared_center() -> None:
    clean = np.full((96, 96, 3), 255, np.uint8)
    cv2.circle(clean, (48, 48), 15, (15, 15, 15), 4)
    stream = BytesIO()
    Image.fromarray(clean).save(stream, format="JPEG", quality=30, subsampling=0)
    stream.seek(0)
    observed = Image.open(stream)
    mask = np.asarray(observed.convert("L"), np.uint8) < 128
    loops = []
    for source in gv.mask_loops(mask):
        closed = np.vstack((source, source[:1]))
        loops.append(gv.FittedLoop(np.asarray(source, float), _line_chain(closed),
                                   "incumbent-q30"))
    assert len(loops) == 2
    region = gv.Region((15, 15, 15), int(mask.sum()), loops)
    old_condition = gv._CODEC_CONDITION[0]
    try:
        gv._CODEC_CONDITION[0] = gv.estimate_jpeg_condition(observed)
        gv._DIGITAL_CIRCLE_AUDIT.clear()
        gv._regularize_concentric_rings([region])
        assert len(region.loops) == 2
        assert all(loop.template.startswith("paper-concentric-ring-")
                   for loop in region.loops)
        assert gv._DIGITAL_CIRCLE_AUDIT[-1]["persistent_hole"] is True
    finally:
        gv._CODEC_CONDITION[0] = old_condition


def _crescent_mask() -> np.ndarray:
    mask = np.zeros((64, 64), np.uint8)
    cv2.circle(mask, (32, 32), 7, 255, -1)
    cv2.circle(mask, (35, 30), 6, 0, -1)
    return mask


def test_deliberate_crescent_abstains_without_codec_evidence() -> None:
    loop = _contour(_crescent_mask())
    old_condition, old_observation = gv._CODEC_CONDITION[0], gv._CODEC_OBSERVATION[0]
    try:
        gv._DIGITAL_CIRCLE_AUDIT.clear()
        gv._CODEC_CONDITION[0] = None
        gv._CODEC_OBSERVATION[0] = None
        assert gv._digital_circle_tournament(loop, _line_chain(loop), 1.0) is None
        assert gv._DIGITAL_CIRCLE_AUDIT[-1]["winner"] == "deliberate-crescent"
        assert "abstain" in gv._DIGITAL_CIRCLE_AUDIT[-1]["reason"]
    finally:
        gv._CODEC_CONDITION[0] = old_condition
        gv._CODEC_OBSERVATION[0] = old_observation


def test_full_circle_wins_only_when_forward_codec_explains_crescent() -> None:
    clean = np.full((64, 64, 3), 255, np.uint8)
    cv2.circle(clean, (32, 32), 7, (12, 12, 12), -1)
    stream = BytesIO()
    Image.fromarray(clean).save(stream, format="JPEG", quality=30, subsampling=0)
    stream.seek(0)
    observed_image = Image.open(stream)
    loop = _contour(_crescent_mask())
    old_condition, old_observation = gv._CODEC_CONDITION[0], gv._CODEC_OBSERVATION[0]
    try:
        gv._DIGITAL_CIRCLE_AUDIT.clear()
        gv._CODEC_CONDITION[0] = gv.estimate_jpeg_condition(observed_image)
        gv._CODEC_OBSERVATION[0] = np.asarray(observed_image.convert("RGB"), np.uint8)
        winner = gv._digital_circle_tournament(loop, _line_chain(loop), 1.0)
        assert winner is not None, gv._DIGITAL_CIRCLE_AUDIT[-1]
        audit = gv._DIGITAL_CIRCLE_AUDIT[-1]
        assert audit["winner"] == "circle", audit
        assert audit["reason"] == "forward-degradation-explains-missing-side"
    finally:
        gv._CODEC_CONDITION[0] = old_condition
        gv._CODEC_OBSERVATION[0] = old_observation


def test_real_crescent_survives_same_q30_forward_court() -> None:
    crescent = _crescent_mask()
    clean = np.full((64, 64, 3), 255, np.uint8)
    clean[crescent > 0] = (12, 12, 12)
    stream = BytesIO()
    Image.fromarray(clean).save(stream, format="JPEG", quality=30, subsampling=0)
    stream.seek(0)
    observed_image = Image.open(stream)
    loop = _contour(crescent)
    old_condition, old_observation = gv._CODEC_CONDITION[0], gv._CODEC_OBSERVATION[0]
    try:
        gv._DIGITAL_CIRCLE_AUDIT.clear()
        gv._CODEC_CONDITION[0] = gv.estimate_jpeg_condition(observed_image)
        gv._CODEC_OBSERVATION[0] = np.asarray(observed_image.convert("RGB"), np.uint8)
        winner = gv._digital_circle_tournament(loop, _line_chain(loop), 1.0)
        assert winner is None
        audit = gv._DIGITAL_CIRCLE_AUDIT[-1]
        assert audit["winner"] == "deliberate-crescent", audit
        assert audit["reason"] == "missing-side-not-codec-explained-abstain"
    finally:
        gv._CODEC_CONDITION[0] = old_condition
        gv._CODEC_OBSERVATION[0] = old_observation


if __name__ == "__main__":
    test_circle_is_separable_but_square_and_ellipse_are_not()
    test_circle_wins_mdl_tournament_only_after_feasibility()
    test_q30_circle_keeps_a_codec_derived_outlier_budget()
    test_repeated_radius_group_prior_shares_only_supported_radius()
    test_concentric_ring_court_shares_center_without_changing_hole()
    test_q30_ring_degradation_keeps_persistent_hole_and_shared_center()
    test_deliberate_crescent_abstains_without_codec_evidence()
    test_full_circle_wins_only_when_forward_codec_explains_crescent()
    test_real_crescent_survives_same_q30_forward_court()
    print("Digital circle court regression checks: PASS")

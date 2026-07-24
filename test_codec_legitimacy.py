"""Short synthetic calibration gates for Strike-3 codec evidence."""

from __future__ import annotations

from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageDraw

import geometry_vectorizer as gv


def _clean_vector_raster() -> Image.Image:
    image = Image.new("RGB", (128, 96), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((13, 13, 114, 81), radius=12,
                           fill=(238, 244, 250), outline=(18, 45, 72), width=3)
    draw.line((25, 63, 50, 35, 78, 54, 103, 27), fill=(20, 92, 178), width=3)
    return image


def _jpeg_observation(quality: int = 37) -> Image.Image:
    stream = BytesIO()
    _clean_vector_raster().save(stream, format="JPEG", quality=quality,
                                subsampling=0)
    stream.seek(0)
    return Image.open(stream)


def test_metadata_qtable_is_recovered_exactly() -> None:
    observed = _jpeg_observation(quality=37)
    condition = gv.estimate_jpeg_condition(observed)
    assert condition["detected"]
    assert condition["source"] == "metadata"
    assert abs(int(condition["quality"]) - 37) <= 1, condition
    assert np.array_equal(condition["qtable"],
                          np.asarray(observed.quantization[0], np.float32).reshape(8, 8))


def test_dct_interval_likelihood_prefers_true_clean_hypothesis() -> None:
    observed_image = _jpeg_observation(quality=35)
    observed = np.asarray(observed_image.convert("RGB"), np.uint8)
    true_hypothesis = np.asarray(_clean_vector_raster(), np.uint8)
    false_hypothesis = true_hypothesis.copy()
    cv2.circle(false_hypothesis, (61, 26), 5, (0, 0, 0), -1)
    condition = gv.estimate_jpeg_condition(observed_image)
    true_cost = gv._dct_bin_penalties(observed, true_hypothesis, condition)
    false_cost = gv._dct_bin_penalties(observed, false_hypothesis, condition)
    assert len(true_cost) == len(false_cost) > 0
    assert float(np.mean(true_cost)) < float(np.mean(false_cost))


def test_qtable_is_recovered_after_jpeg_is_resaved_as_png() -> None:
    png_like = _jpeg_observation(quality=35).convert("RGB")
    condition = gv.estimate_jpeg_condition(png_like)
    assert condition["detected"], condition
    assert condition["source"] == "coefficient-lattice"
    assert abs(int(condition["quality"]) - 35) <= 5, condition
    assert condition["false_alarm"] <= 0.05
    assert condition["bin_false_alarm"] <= 0.05


def test_png_without_codec_evidence_abstains() -> None:
    clean = Image.new("RGB", (96, 96), (240, 240, 240))
    condition = gv.estimate_jpeg_condition(clean)
    assert not condition["detected"], condition
    assert condition["false_alarm"] > 0.05


def test_full_forward_grid_prefers_clean_truth_after_gamma_psf_chroma_jpeg() -> None:
    clean = np.asarray(_clean_vector_raster(), np.uint8)
    encoded = np.power(clean.astype(np.float32) / 255.0, 1.0 / 1.3)
    encoded = cv2.GaussianBlur(encoded, (0, 0), 0.65,
                               borderType=cv2.BORDER_REPLICATE)
    degraded = np.clip(np.rint(encoded * 255.0), 0, 255).astype(np.uint8)
    stream = BytesIO()
    Image.fromarray(degraded).save(stream, format="JPEG", quality=35,
                                   subsampling=2)
    stream.seek(0)
    observed_image = Image.open(stream)
    observed = np.asarray(observed_image.convert("RGB"), np.uint8)
    condition = gv.estimate_jpeg_condition(observed_image)
    condition["gamma_candidates"] = (1.0, 1.3)
    condition["psf_candidates"] = (0.0, 0.65)
    condition["chroma_candidates"] = ("420",)
    false = clean.copy()
    cv2.rectangle(false, (54, 20), (67, 32), (0, 0, 0), -1)
    true_models = gv._forward_codec_models(clean, observed_image.size, condition)
    false_models = gv._forward_codec_models(false, observed_image.size, condition)
    grid = condition["grid"]
    phase = (int(grid.get("phase_x", 0)), int(grid.get("phase_y", 0)))
    qtable = np.asarray(condition["qtable"], np.float32)
    true_best = gv._best_forward_codec_likelihood(observed, true_models, qtable, phase)
    false_best = gv._best_forward_codec_likelihood(observed, false_models, qtable, phase)
    assert true_best is not None and false_best is not None
    assert float(np.mean(true_best[0])) < float(np.mean(false_best[0]))
    theta_grid = gv._forward_codec_theta_grid(condition)
    assert all(int(theta["supersample"]) >= 8 for theta in theta_grid)
    assert {theta["gamma"] for theta in theta_grid} == {1.0, 1.3}
    assert {theta["psf_sigma"] for theta in theta_grid} == {0.0, 0.65}
    assert {theta["chroma_mode"] for theta in theta_grid} == {"420"}


def test_forward_codec_court_preserves_a_real_small_accent() -> None:
    detailed = np.asarray(_clean_vector_raster(), np.uint8).copy()
    cv2.circle(detailed, (61, 26), 2, (12, 30, 55), -1)
    stream = BytesIO()
    Image.fromarray(detailed).save(stream, format="JPEG", quality=32,
                                   subsampling=0)
    stream.seek(0)
    observed_image = Image.open(stream)
    observed = np.asarray(observed_image.convert("RGB"), np.uint8)
    missing = np.asarray(_clean_vector_raster(), np.uint8)
    condition = gv.estimate_jpeg_condition(observed_image)
    condition["gamma_candidates"] = (1.0,)
    condition["psf_candidates"] = (0.0,)
    detailed_models = gv._forward_codec_models(detailed, observed_image.size, condition)
    missing_models = gv._forward_codec_models(missing, observed_image.size, condition)
    grid = condition["grid"]
    phase = (int(grid.get("phase_x", 0)), int(grid.get("phase_y", 0)))
    qtable = np.asarray(condition["qtable"], np.float32)
    detailed_best = gv._best_forward_codec_likelihood(
        observed, detailed_models, qtable, phase)
    missing_best = gv._best_forward_codec_likelihood(
        observed, missing_models, qtable, phase)
    assert detailed_best is not None and missing_best is not None
    assert float(np.mean(detailed_best[0])) < float(np.mean(missing_best[0]))
    accent = np.zeros((96 * 4, 128 * 4), bool)
    cv2.circle(accent.view(np.uint8), (61 * 4, 26 * 4), 2 * 4, 1, -1)
    assert gv._codec_feature_persistent(
        accent, analysis_scale=4,
        qtable=np.asarray(condition["qtable"], np.float32))


if __name__ == "__main__":
    test_metadata_qtable_is_recovered_exactly()
    test_dct_interval_likelihood_prefers_true_clean_hypothesis()
    test_qtable_is_recovered_after_jpeg_is_resaved_as_png()
    test_png_without_codec_evidence_abstains()
    test_full_forward_grid_prefers_clean_truth_after_gamma_psf_chroma_jpeg()
    test_forward_codec_court_preserves_a_real_small_accent()
    print("Codec legitimacy regression checks: PASS")

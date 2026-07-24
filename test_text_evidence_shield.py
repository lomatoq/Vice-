"""Fast synthetic gates for the Strike-2 text evidence shield."""

from __future__ import annotations

import cv2
import numpy as np

import geometry_vectorizer as gv


def _soft_ring() -> np.ndarray:
    mask = np.zeros((48, 64), np.uint8)
    cv2.ellipse(mask, (32, 24), (18, 14), 0, 0, 360, 255, -1)
    cv2.ellipse(mask, (32, 24), (8, 6), 0, 0, 360, 0, -1)
    return cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (5, 5), 0.8)


def test_persistent_alpha_topology_keeps_counter_obligation() -> None:
    alpha = _soft_ring()
    signature = gv._persistent_line_signature(alpha, area_floor=4)
    assert signature["components"] == 1, signature
    assert signature["holes"] == 1, signature


def test_ambiguity_crf_cannot_close_persistent_counter() -> None:
    alpha = _soft_ring()
    # Add an ambiguous alpha island near the glyph without deleting the hard
    # annulus evidence.  Pairwise smoothing may absorb or reject the island,
    # but the counter is a non-negotiable filtration obligation.
    alpha[7:11, 29:35] = np.maximum(alpha[7:11, 29:35], 0.46)
    baseline = alpha >= 0.5
    signature = gv._persistent_line_signature(alpha, area_floor=4)
    candidate = gv._text_ambiguity_crf(alpha, baseline, signature, area_floor=4)
    assert candidate is not None
    _material, components, holes = gv._interior_component_mask(candidate, 4)
    assert components >= signature["components"]
    assert holes >= signature["holes"]


def test_constant_width_hypothesis_is_topology_vetoed() -> None:
    alpha = _soft_ring()
    baseline = alpha >= 0.5
    signature = gv._persistent_line_signature(alpha, area_floor=4)
    candidate, _width_cv = gv._skeleton_width_hypothesis(
        baseline, alpha, signature, area_floor=4)
    if candidate is not None:
        _material, components, holes = gv._interior_component_mask(candidate, 4)
        assert components >= signature["components"]
        assert holes >= signature["holes"]


if __name__ == "__main__":
    test_persistent_alpha_topology_keeps_counter_obligation()
    test_ambiguity_crf_cannot_close_persistent_counter()
    test_constant_width_hypothesis_is_topology_vetoed()
    print("Text evidence shield regression checks: PASS")

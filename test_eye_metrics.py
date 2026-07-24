"""Dependency-light regression checks for Council N1 eye meters."""
from __future__ import annotations

import numpy as np

import benchmark_vai as bv


def test_local_defeat_finds_the_bad_tile() -> None:
    src = np.full((64, 64, 3), 255.0)
    ren = src.copy()
    ren[32:64, 32:64] = 0.0
    same = bv.local_defeat_meter(src, src)
    bad = bv.local_defeat_meter(ren, src)
    assert same["local_de_max"] == 0.0
    assert bad["local_de_max"] > 50.0
    assert bad["local_de_x"] >= 40 and bad["local_de_y"] >= 40


def test_text_distance_is_normalized() -> None:
    assert bv._normal_levenshtein("AARCH", "AARCH") == 0.0
    assert bv._normal_levenshtein("AARCH", "") == 1.0
    assert 0.0 < bv._normal_levenshtein("BANK", "B4NK") < 1.0
    assert bv._bbox_iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert bv._bbox_iou((0, 0, 5, 5), (6, 6, 10, 10)) == 0.0


def test_component_census_sees_lost_counter() -> None:
    src = np.full((48, 48, 3), 255.0)
    src[8:40, 8:40] = 0.0
    src[17:31, 17:31] = 255.0
    ren = src.copy()
    ren[17:31, 17:31] = 0.0
    same = bv.component_census_meter(src, src)
    filled = bv.component_census_meter(ren, src)
    assert same["census_errors"] == 0, same
    assert filled["holes_lost"] >= 1, filled
    assert filled["census_errors"] >= 1, filled


def test_region_colour_catches_one_wrong_element() -> None:
    src = np.full((64, 64, 3), 255.0)
    src[8:28, 8:28] = (220, 30, 40)
    src[36:56, 36:56] = (20, 70, 220)
    wrong = src.copy()
    wrong[36:56, 36:56] = (20, 210, 60)
    same = bv.region_color_meter(src, src)
    bad = bv.region_color_meter(wrong, src)
    assert same["region_de2000_p95"] == 0.0, same
    assert same["de_region_max"] == 0.0, same
    assert bad["region_de2000_p95"] > 2.3, bad
    assert bad["de_region_max"] > 2.3, bad


def test_rot90_symmetry_break() -> None:
    plus = np.zeros((41, 41), bool)
    plus[8:33, 17:24] = True
    plus[17:24, 8:33] = True
    damaged = plus.copy()
    damaged[8:15, 17:24] = False
    assert bv.rot90_iou(plus) > 0.99
    assert bv.rot90_iou(damaged) < bv.rot90_iou(plus) - 0.1


if __name__ == "__main__":
    test_local_defeat_finds_the_bad_tile()
    test_text_distance_is_normalized()
    test_component_census_sees_lost_counter()
    test_region_colour_catches_one_wrong_element()
    test_rot90_symmetry_break()
    print("Council N1 eye-meter checks: PASS")

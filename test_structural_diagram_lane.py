"""Short Strike-5 gates for line graphs and global dashed boxes."""

from __future__ import annotations

import cv2
import numpy as np

import geometry_vectorizer as gv


def _linechart() -> np.ndarray:
    image = np.full((180, 240, 3), 255, np.uint8)
    cv2.line(image, (35, 145), (215, 145), (15, 15, 15), 2)
    cv2.line(image, (35, 145), (35, 25), (15, 15, 15), 2)
    series = np.array([[40, 130], [82, 91], [124, 112],
                       [169, 51], [208, 72]], np.int32)
    cv2.polylines(image, [series], False, (25, 90, 180), 2)
    cv2.rectangle(image, (25, 18), (222, 158), (225, 225, 225), 2)
    return image


def test_lsd_nfa_graph_accepts_connected_linechart() -> None:
    specs, carved = gv._extract_structural_line_network(_linechart())
    assert carved is not None
    assert len(specs) >= 3
    assert gv._STRUCTURAL_DIAGRAM_AUDIT[-1]["accepted"]
    assert gv._STRUCTURAL_DIAGRAM_AUDIT[-1]["evidence_ratio"] >= \
        gv._STRUCTURAL_DIAGRAM_AUDIT[-1]["required_ratio"]


def test_small_clean_icon_sheet_does_not_arm_graph_lane() -> None:
    image = np.full((180, 240, 3), 255, np.uint8)
    for row in range(2):
        for col in range(5):
            x = 15 + 44 * col
            y = 25 + 75 * row
            cv2.rectangle(image, (x, y), (x + 20, y + 20), (20, 20, 20), 2)
            cv2.circle(image, (x + 10, y + 42), 5, (60, 90, 150), -1)
    specs, carved = gv._extract_structural_line_network(image)
    assert specs == []
    assert carved is None


def test_coloured_dashed_box_is_assembled_before_any_side_is_carved() -> None:
    image = np.full((160, 220, 3), 245, np.uint8)
    color = (210, 40, 120)
    for x in range(35, 180, 14):
        cv2.line(image, (x, 30), (x + 8, 30), color, 2)
        cv2.line(image, (x, 125), (x + 8, 125), color, 2)
    for y in range(35, 120, 14):
        cv2.line(image, (30, y), (30, y + 8), color, 2)
    # Deliberately weak fourth side: only three linelets.  The full rectangle
    # hypothesis supplies its narrow predicted corridor and NFA context.
    for y in (45, 73, 101):
        cv2.line(image, (185, y), (185, y + 8), color, 2)
    specs, carved = gv._extract_global_dash_boxes(image)
    assert carved is not None
    assert len(specs) == 4
    audit = gv._STRUCTURAL_DIAGRAM_AUDIT[-1]
    assert audit["kind"] == "global-dashed-rectangle"
    assert audit["evidence_nfa"] > audit["model_code"]


def test_lone_decoration_row_is_not_a_box() -> None:
    image = np.full((120, 220, 3), 250, np.uint8)
    for x in range(30, 190, 16):
        cv2.line(image, (x, 60), (x + 7, 60), (30, 130, 90), 2)
    specs, carved = gv._extract_global_dash_boxes(image)
    assert specs == []
    assert carved is None


if __name__ == "__main__":
    test_lsd_nfa_graph_accepts_connected_linechart()
    test_small_clean_icon_sheet_does_not_arm_graph_lane()
    test_coloured_dashed_box_is_assembled_before_any_side_is_carved()
    test_lone_decoration_row_is_not_a_box()
    print("Structural diagram lane regression checks: PASS")

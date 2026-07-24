"""Synthetic safety check for CC-matched sanctuary repair."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

import geometry_vectorizer as gv


def main() -> int:
    image = Image.new("RGB", (90, 36), "white")
    draw = ImageDraw.Draw(image)
    for x in (8, 24, 40, 56, 72):
        draw.rectangle((x, 10, x + 7, 25), fill="black")
    pixels = np.asarray(image, np.uint8)
    anchors = np.asarray(((255, 255, 255), (0, 0, 0)), np.uint8)
    labels = np.zeros((36, 90), np.int16)
    # Fragment each intact source glyph into two labelled islands.
    for x in (8, 24, 40, 56, 72):
        labels[10:17, x:x + 8] = 1
        labels[19:26, x:x + 8] = 1
    repaired = gv._repair_sanctuary_labels(
        labels, pixels, anchors, image, 1, [(3, 4, 87, 32)])
    _, count, _ = gv._interior_component_mask(repaired[4:32, 3:87] == 1, 4)
    assert count == 5, (count, gv._GLYPH_REPAIR_AUDIT)
    assert gv._GLYPH_REPAIR_AUDIT and gv._GLYPH_REPAIR_AUDIT[0]["accepted"]
    # OCR-free counter-word router: one short baseline, six material chunks and
    # three native counters.  A vertically scattered icon arrangement with the
    # same primitive count must not be mistaken for text.
    word = Image.new("RGB", (120, 24), "white")
    word_draw = ImageDraw.Draw(word)
    for x in (6, 24, 42):
        word_draw.rectangle((x, 8, x + 9, 15), fill="black")
        word_draw.rectangle((x + 3, 10, x + 6, 13), fill="white")
    for x in (60, 78, 96):
        word_draw.rectangle((x, 8, x + 8, 15), fill="black")
    routed = gv._candidate_counter_word_boxes(word)
    assert len(routed) == 1, routed

    scattered = Image.new("RGB", (120, 40), "white")
    scattered_draw = ImageDraw.Draw(scattered)
    for index, x in enumerate((6, 24, 42, 60, 78, 96)):
        y = 4 if index % 2 == 0 else 26
        scattered_draw.rectangle((x, y, x + 8, y + 7), fill="black")
        if index < 3:
            scattered_draw.rectangle((x + 2, y + 2, x + 5, y + 5), fill="white")
    assert not gv._candidate_counter_word_boxes(scattered)
    print("glyph sanctuary repair: PASS", gv._GLYPH_REPAIR_AUDIT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

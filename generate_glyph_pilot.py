"""Generate a small, reviewable single-glyph SVG pilot corpus.

The pilot deliberately uses one known font and a tiny fixed character bank.  It
is meant to validate exact-C0 annotations before any glyph examples enter CNN
training, not to provide broad font coverage by itself.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parent
DEFAULT_FONT = Path(r"C:/Windows/Fonts/arial.ttf")
DEFAULT_OUT = ROOT / "datasets" / "text_glyph_pilot_sources"
PILOT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZaego"


def generate(font_path: Path, out: Path, chars: str = PILOT_CHARS) -> dict:
    font = TTFont(font_path)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for index, char in enumerate(chars):
        glyph_name = cmap.get(ord(char))
        if glyph_name is None:
            continue
        glyph = glyph_set[glyph_name]
        bounds_pen = BoundsPen(glyph_set)
        glyph.draw(bounds_pen)
        if bounds_pen.bounds is None:
            continue
        xmin, ymin, xmax, ymax = map(float, bounds_pen.bounds)
        span = max(xmax - xmin, ymax - ymin, 1.0)
        margin = max(24.0, 0.10 * span)
        width = xmax - xmin + 2.0 * margin
        height = ymax - ymin + 2.0 * margin

        # Font outlines use y-up while SVG uses y-down.  Transform coordinates
        # in the path itself because the exact-GT loader intentionally rejects
        # unresolved SVG transform stacks.
        path_pen = SVGPathPen(glyph_set)
        transform = (1.0, 0.0, 0.0, -1.0, -xmin + margin, ymax + margin)
        glyph.draw(TransformPen(path_pen, transform))
        path_data = path_pen.getCommands()
        filename = f"{index:02d}_{ord(char):04x}_{char}.svg"
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width:.3f}" height="{height:.3f}" '
            f'viewBox="0 0 {width:.3f} {height:.3f}">'
            f'<path fill="#111111" fill-rule="nonzero" d="{path_data}"/>'
            f'</svg>\n'
        )
        (out / filename).write_text(svg, encoding="utf-8")
        records.append({"index": index, "char": char, "codepoint": ord(char),
                        "glyph": glyph_name, "file": filename})

    manifest = {
        "kind": "single-glyph-exact-c0-review-pilot",
        "font": str(font_path),
        "characters": chars,
        "count": len(records),
        "records": records,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--chars", default=PILOT_CHARS)
    args = parser.parse_args()
    result = generate(args.font, args.out, args.chars)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

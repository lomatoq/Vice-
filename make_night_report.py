"""Render side-by-side proof sheets: source | ours-BEFORE | ours-AFTER | VAI.

Reads benchmarks/vai_baseline_before_20260712.json (before) and the after run's
work dirs, renders every SVG at a common display height, and tiles the four
panels per stem into benchmarks/night_report/<stem>.png plus one index sheet
of the most-improved offenders.

Usage: python make_night_report.py [--stems a,b,c] [--height 220]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from PIL import Image, ImageDraw, ImageFont

from benchmark_vai import VAI_DIR, WORK, find_source, render_svg

OUT = Path(__file__).parent / "benchmarks" / "night_report"


def _caption(width: int, text: str) -> Image.Image:
    strip = Image.new("RGB", (max(width, 40), 18), (245, 245, 247))
    draw = ImageDraw.Draw(strip)
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
    draw.text((3, 3), text, fill=(30, 30, 34), font=font)
    return strip


def _fit(img: Image.Image, height: int) -> Image.Image:
    scale = height / img.height
    w = max(1, round(img.width * scale))
    resample = Image.Resampling.NEAREST if scale >= 1 else Image.Resampling.LANCZOS
    return img.resize((w, height), resample)


def sheet_for(stem: str, before_tag: str, after_tag: str, height: int) -> Image.Image | None:
    src = find_source(stem)
    if src is None:
        return None
    panels: list[tuple[str, Image.Image]] = [("source", Image.open(src).convert("RGB"))]
    W = panels[0][1].size[0]
    for label, svg in (
        ("ours BEFORE", WORK / before_tag / stem / f"{src.stem}" / "03_rebuilt_filled.svg"),
        ("ours AFTER", WORK / after_tag / stem / f"{src.stem}" / "03_rebuilt_filled.svg"),
        ("vectorizer.ai", VAI_DIR / f"{stem}_vai.svg"),
    ):
        if svg.exists():
            try:
                panels.append((label, render_svg(svg, W * max(1, height // max(1, panels[0][1].height)))))
            except Exception:
                continue
    if len(panels) < 3:
        return None
    tiles = []
    for label, img in panels:
        fitted = _fit(img, height)
        tile = Image.new("RGB", (fitted.width, height + 18), (255, 255, 255))
        tile.paste(fitted, (0, 0))
        tile.paste(_caption(fitted.width, label), (0, height))
        tiles.append(tile)
    gap = 6
    total = sum(t.width for t in tiles) + gap * (len(tiles) + 1)
    sheet = Image.new("RGB", (total, height + 18 + 2 * gap), (232, 233, 238))
    x = gap
    for tile in tiles:
        sheet.paste(tile, (x, gap))
        x += tile.width + gap
    return sheet


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before-tag", default="paper-regions-before")
    ap.add_argument("--after-tag", default="paper-regions")
    ap.add_argument("--stems", default=None)
    ap.add_argument("--height", type=int, default=220)
    args = ap.parse_args()

    if args.stems:
        stems = [s.strip() for s in args.stems.split(",") if s.strip()]
    else:
        before = json.loads((Path("benchmarks/vai_baseline_before_20260712.json"))
                            .read_text(encoding="utf-8"))
        scored = []
        for row in before["rows"]:
            ours = row.get("ours") or {}
            badness = ((ours.get("staircase_runs") or 0) * 5
                       + (row.get("fallback_loops") or 0) * 3
                       + (ours.get("seam_px") or 0) * 0.2
                       + (ours.get("kinks_per_100px") or 0) * 0.3)
            scored.append((badness, row["stem"]))
        stems = [stem for _, stem in sorted(scored, reverse=True)[:14]]

    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for stem in stems:
        sheet = sheet_for(stem, args.before_tag, args.after_tag, args.height)
        if sheet is not None:
            path = OUT / f"{stem}.png"
            sheet.save(path)
            made.append(path)
            print("sheet:", path.name)
    print(f"{len(made)} sheets -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

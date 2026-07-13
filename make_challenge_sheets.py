"""Proof sheets for the blind challenge: worst cases, eyes-first.

For each selected item: SRC crop | OURS render | VAI render, 3x upscaled,
labelled with the deficit metrics.  Output: challenge_pack/eval/sheets/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from PIL import Image, ImageDraw, ImageFont

PACK = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack")
EVAL = PACK / "eval"
SHEETS = EVAL / "sheets"
ZOOM = 3


def render(svg: Path, width: int) -> Image.Image:
    import io
    import resvg_py
    png = resvg_py.svg_to_bytes(svg_string=svg.read_text(encoding="utf-8"), width=width)
    img = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    base = Image.new("RGB", img.size, (255, 255, 255))
    base.paste(img, mask=img.split()[3])
    return base


def sheet(row: dict, tag: str) -> None:
    k = row["item"]
    crop_p = EVAL / "crops" / f"item{k:03}.png"
    ours_p = EVAL / "ours" / f"item{k:03}" / f"item{k:03}" / "03_rebuilt_filled.svg"
    vai_p = EVAL / "items" / f"item{k:03}_vai.svg"
    if not (crop_p.exists() and vai_p.exists()):
        return
    src = Image.open(crop_p).convert("RGB")
    W = src.width * ZOOM
    panels = [src.resize((W, src.height * ZOOM), Image.NEAREST)]
    for svg in (ours_p, vai_p):
        try:
            panels.append(render(svg, W) if svg.exists() else Image.new("RGB", (W, panels[0].height), (250, 220, 220)))
        except Exception:
            panels.append(Image.new("RGB", (W, panels[0].height), (250, 220, 220)))
    h = max(p.height for p in panels)
    gap, head = 14, 46
    canvas = Image.new("RGB", (W * 3 + gap * 4, h + head + gap), (24, 26, 30))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 15)
        small = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        font = small = ImageFont.load_default()
    o, v = row.get("ours", {}), row.get("vai", {})

    def fmt(m, nd=3):
        a, b = o.get(m), v.get(m)
        fa = f"{a:.{nd}f}" if isinstance(a, (int, float)) else "-"
        fb = f"{b:.{nd}f}" if isinstance(b, (int, float)) else "-"
        return f"{fa}|{fb}"

    title = (f"item{k:03}  {row['category']}  {Path(row['source']).name}   "
             f"iou {fmt('ink_iou')}  mae {fmt('mae', 1)}  kink {fmt('kinks_per_100px', 2)}  round {fmt('roundness', 4)}")
    draw.text((gap, 8), title, fill=(235, 235, 240), font=font)
    for i, (p, lab) in enumerate(zip(panels, ("SRC", "OURS", "VAI"))):
        x = gap + i * (W + gap)
        canvas.paste(p, (x, head))
        draw.text((x, head - 18), lab, fill=(160, 200, 255), font=small)
    SHEETS.mkdir(exist_ok=True)
    canvas.save(SHEETS / f"{tag}_item{k:03}.png")
    print(f"  {tag}_item{k:03}.png <- {row['source']}")


def main() -> int:
    report = json.loads((EVAL / "report.json").read_text(encoding="utf-8"))
    rows = [x for x in report["rows"]
            if isinstance(x.get("ours", {}).get("ink_iou"), (int, float))
            and isinstance(x.get("vai", {}).get("ink_iou"), (int, float))]

    def deficit(metric, lower_better=True):
        def key(x):
            a, b = x["ours"].get(metric), x["vai"].get(metric)
            if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                return 0.0
            return (a - b) if lower_better else (b - a)
        return key

    picks: dict[int, tuple[dict, str]] = {}
    for tag, metric, lower in (("iou", "ink_iou", False), ("kink", "kinks_per_100px", True),
                               ("round", "roundness", True)):
        pool = [x for x in rows if isinstance(x["ours"].get(metric), (int, float))
                and isinstance(x["vai"].get(metric), (int, float))]
        pool.sort(key=deficit(metric, lower), reverse=True)
        for x in pool[:5]:
            picks.setdefault(x["item"], (x, f"worst_{tag}"))
    for row, tag in picks.values():
        sheet(row, tag)
    print(f"sheets -> {SHEETS}  ({len(picks)} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

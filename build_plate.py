"""Assemble the challenge pack into VAI-feed PLATES (no annotations).

Rules:
- Each plate <= 2.0 MP: vectorizer.ai downscales anything over ~2.1 MP
  (measured in VAI_RULES.md), which would silently destroy the scale-
  sensitive tests (16px text must reach VAI at 16px).
- Items are pasted at their NATIVE pixel size on white, generous padding,
  shelf-packed by rows, grouped by category, NO labels on the plate.
- plate_layout.json records every item's plate, bbox and source, so the VAI
  result SVG can be cut back into per-item pieces automatically.
- A *_annotated.png twin (labels drawn) is written for HUMAN review only —
  never feed that one to VAI.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from PIL import Image, ImageDraw, ImageFont

PACK = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack")
OUT = PACK / "plates"
PAD = 28
PLATE_W = 1620
PLATE_MAX_H = 1230          # 1620*1230 = 1.99 MP < VAI's ~2.1 MP cap

# which raster goes on the plate, per category (native scale is the test!)
PICK = {
    "small_text": ["__h24.png", "__h16.png", "__h48_q50.jpg"],
    "logos": ["__h160.png", "__h64_q30.jpg"],
    "ui_icons": ["__h64.png", "__h64_q40.jpg", "pair_"],
    "gradients": ["__h160.png", "__h64.png"],
    "transparency": ["__h128_alpha.png"],
    "jpeg_dirty": [".jpg"],
    "diagrams": ["__h260.png", "__h140.png", "__h200_q45.jpg", "__h192.png", "__h96.png"],
}
LIMIT_PER_CAT = {"small_text": 26, "logos": 20, "ui_icons": 12, "gradients": 14,
                 "transparency": 4, "jpeg_dirty": 10, "diagrams": 30}


def collect() -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for cat, patterns in PICK.items():
        cat_dir = PACK / cat
        if not cat_dir.is_dir():
            continue
        chosen: list[Path] = []
        for p in sorted(cat_dir.iterdir()):
            if p.suffix.lower() not in (".png", ".jpg"):
                continue
            if any(pat in p.name for pat in patterns):
                chosen.append(p)
        for p in chosen[:LIMIT_PER_CAT.get(cat, 12)]:
            items.append((cat, p))
    return items


def main() -> int:
    OUT.mkdir(exist_ok=True)
    items = collect()
    print(f"plate items: {len(items)}")

    loaded = []
    for cat, p in items:
        img = Image.open(p)
        if img.mode == "RGBA":                    # transparency test: composite
            base = Image.new("RGB", img.size, (255, 255, 255))
            base.paste(img, mask=img.split()[3])
            img = base
        else:
            img = img.convert("RGB")
        if img.width > PLATE_W - 2 * PAD:         # long charts: fit width
            s = (PLATE_W - 2 * PAD) / img.width
            img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
        loaded.append((cat, p, img))

    # shelf packing, category-grouped order
    plates: list[list[tuple[str, Path, Image.Image, int, int]]] = [[]]
    x, y, row_h = PAD, PAD, 0
    for cat, p, img in loaded:
        if x + img.width + PAD > PLATE_W:
            x = PAD
            y += row_h + PAD
            row_h = 0
        if y + img.height + PAD > PLATE_MAX_H:
            plates.append([])
            x, y, row_h = PAD, PAD, 0
        plates[-1].append((cat, p, img, x, y))
        x += img.width + PAD
        row_h = max(row_h, img.height)

    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
    layout = []
    for pi, plate_items in enumerate(plates, 1):
        h = max(iy + im.height for _, _, im, _, iy in plate_items) + PAD
        plate = Image.new("RGB", (PLATE_W, h), (255, 255, 255))
        annotated = Image.new("RGB", (PLATE_W, h), (255, 255, 255))
        for cat, p, im, ix, iy in plate_items:
            plate.paste(im, (ix, iy))
            annotated.paste(im, (ix, iy))
            layout.append({"plate": pi, "category": cat,
                           "source": str(p.relative_to(PACK)),
                           "bbox": [ix, iy, ix + im.width, iy + im.height]})
        draw = ImageDraw.Draw(annotated)
        for cat, p, im, ix, iy in plate_items:
            draw.rectangle([ix - 3, iy - 3, ix + im.width + 3, iy + im.height + 3],
                           outline=(200, 60, 60), width=1)
            draw.text((ix, max(0, iy - 13)), f"{cat}:{p.stem[:26]}",
                      fill=(160, 40, 40), font=font)
        mp = PLATE_W * h / 1e6
        plate.save(OUT / f"plate_{pi:02}.png")
        annotated.save(OUT / f"plate_{pi:02}_annotated.png")
        print(f"plate_{pi:02}.png  {PLATE_W}x{h}  {mp:.2f} MP  items={len(plate_items)}")
    (OUT / "plate_layout.json").write_text(json.dumps(layout, indent=1), encoding="utf-8")
    print("layout ->", OUT / "plate_layout.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Build the blind-holdout challenge pack (external-audit validation wave).

Sources:
  1) User-collected SVG originals:  C:/Users/nirrt/Toolset/Test Icons
  2) Corpus:                        C:/Users/nirrt/Toolset/v-ize train/dataset

Output:  C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack/
  <category>/<stem>.svg                 original vector GT (untouched copy)
  <category>/<stem>__h{N}.png           clean resvg render at height N
  <category>/<stem>__h{N}_q{Q}.jpg      JPEG-degraded variant
  <category>/<stem>__h{N}_alpha.png     RGBA render (transparency category)
  jpeg_dirty/                           nastiest combos picked across the pack
  vai/README.txt                        drop-slot for user's vectorizer.ai refs
  manifest.json                         every file: source, category, params
  REVIEW_SHEETS/<category>.png          contact sheet for the user's review

Deterministic: sorted orders, fixed pick counts, no randomness.
Categories are assigned by SVG-source heuristics (gradient/opacity tags,
viewBox aspect) — the review sheets exist precisely so a human can veto.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from PIL import Image, ImageDraw, ImageFont

USER_DIR = Path(r"C:/Users/nirrt/Toolset/Test Icons")
CORPUS = Path(r"C:/Users/nirrt/Toolset/v-ize train/dataset")
OUT = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack")

CATS = ["logos", "small_text", "ui_icons", "transparency", "gradients",
        "jpeg_dirty", "diagrams"]


def render_svg_h(svg_path: Path, height: int, keep_alpha: bool = False) -> Image.Image | None:
    import resvg_py
    try:
        png = resvg_py.svg_to_bytes(svg_string=svg_path.read_text(encoding="utf-8"),
                                    height=height)
        img = Image.open(io.BytesIO(bytes(png)))
    except Exception:
        return None
    if keep_alpha:
        return img.convert("RGBA")
    base = Image.new("RGB", img.size, (255, 255, 255))
    rgba = img.convert("RGBA")
    base.paste(rgba, mask=rgba.split()[3])
    return base


def svg_flags(svg_path: Path) -> dict:
    text = svg_path.read_text(encoding="utf-8", errors="replace")
    vb = re.search(r'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)', text)
    aspect = float(vb.group(1)) / max(1e-6, float(vb.group(2))) if vb else 1.0
    return {
        "gradient": bool(re.search(r"<(linear|radial)Gradient", text)),
        "opacity": bool(re.search(r'opacity\s*[:=]\s*"?0?\.\d', text)),
        "aspect": round(aspect, 2),
        "paths": len(re.findall(r"<path\b", text)),
    }


def classify_user_svg(flags: dict) -> str:
    if flags["gradient"]:
        return "gradients"
    if flags["opacity"]:
        return "transparency"
    if flags["aspect"] >= 2.4:
        return "small_text"          # wide wordmark-ish
    return "logos"


def save_variants(svg: Path, cat_dir: Path, manifest: list, category: str,
                  heights=(24, 64, 160), jpegs=((160, 60), (64, 30)),
                  alpha: bool = False) -> None:
    stem = re.sub(r"\s+", "_", svg.stem)
    dst_svg = cat_dir / f"{stem}.svg"
    if not dst_svg.exists():
        shutil.copy2(svg, dst_svg)
    manifest.append({"file": str(dst_svg.relative_to(OUT)), "source": str(svg),
                     "category": category, "kind": "vector-gt"})
    renders: dict[int, Image.Image] = {}
    for h in heights:
        img = render_svg_h(svg, h)
        if img is None:
            continue
        renders[h] = img
        p = cat_dir / f"{stem}__h{h}.png"
        img.save(p)
        manifest.append({"file": str(p.relative_to(OUT)), "source": str(svg),
                         "category": category, "kind": "render", "height": h})
    for h, q in jpegs:
        if h not in renders:
            continue
        p = cat_dir / f"{stem}__h{h}_q{q}.jpg"
        renders[h].save(p, "JPEG", quality=q, subsampling=2)
        manifest.append({"file": str(p.relative_to(OUT)), "source": str(svg),
                         "category": category, "kind": "jpeg", "height": h, "q": q})
    if alpha:
        img = render_svg_h(svg, 128, keep_alpha=True)
        if img is not None:
            p = cat_dir / f"{stem}__h128_alpha.png"
            img.save(p)
            manifest.append({"file": str(p.relative_to(OUT)), "source": str(svg),
                             "category": category, "kind": "alpha-render", "height": 128})


def contact_sheet(cat_dir: Path, out_png: Path, tile: int = 120) -> None:
    thumbs = []
    for p in sorted(cat_dir.glob("*__h64.png")) or sorted(cat_dir.glob("*__h*.png"))[:40]:
        try:
            img = Image.open(p).convert("RGB")
        except Exception:
            continue
        scale = tile / max(img.size)
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
        thumbs.append((p.name.split("__")[0], img))
    if not thumbs:
        return
    cols = 6
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tile + 8) + 8, rows * (tile + 26) + 8), (238, 239, 243))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
    for k, (name, img) in enumerate(thumbs):
        r, c = divmod(k, cols)
        x = 8 + c * (tile + 8)
        y = 8 + r * (tile + 26)
        sheet.paste(img, (x + (tile - img.width) // 2, y + (tile - img.height) // 2))
        draw.text((x, y + tile + 2), name[:20], fill=(40, 40, 45), font=font)
    sheet.save(out_png)


def main() -> int:
    manifest: list[dict] = []
    for cat in CATS:
        (OUT / cat).mkdir(parents=True, exist_ok=True)
    (OUT / "vai").mkdir(exist_ok=True)
    (OUT / "REVIEW_SHEETS").mkdir(exist_ok=True)
    (OUT / "vai" / "README.txt").write_text(
        "Кладзі сюды vectorizer.ai вынікі для файлаў пака: <stem>_vai.svg\n",
        encoding="utf-8")

    # ---- 1) user-collected SVGs --------------------------------------------
    user_svgs = sorted(USER_DIR.glob("*.svg"))
    print(f"user svgs: {len(user_svgs)}")
    for svg in user_svgs:
        flags = svg_flags(svg)
        cat = classify_user_svg(flags)
        save_variants(svg, OUT / cat, manifest, cat,
                      alpha=(cat == "transparency"))
        manifest[-1]["flags"] = flags

    # ---- 2) corpus picks ----------------------------------------------------
    # small text: three fonts x two words, tiny renders are the point
    ts = CORPUS / "text_shapes" / "svg"
    for font_dir in ["arial", "ariblk", "georgia"]:
        d = ts / font_dir
        if not d.is_dir():
            continue
        for svg in sorted(d.glob("*.svg"))[:2]:
            save_variants(svg, OUT / "small_text", manifest, "small_text",
                          heights=(16, 24, 48), jpegs=((48, 50),))

    # ui icons: mono + colorful families
    ic = CORPUS / "icons" / "iconify"
    picks = [("cib", 2), ("devicon", 2), ("emojione", 2),
             ("circle-flags", 1), ("cryptocurrency-color", 1)]
    for fam, k in picks:
        d = ic / fam
        if not d.is_dir():
            continue
        for svg in sorted(d.glob("*.svg"))[:k]:
            cat = "gradients" if fam in ("emojione", "cryptocurrency-color") else "ui_icons"
            save_variants(svg, OUT / cat, manifest, cat,
                          heights=(32, 64), jpegs=((64, 40),))

    # diagrams / occlusion / frames from synthetic geometry
    sg = CORPUS / "synthetic_geometry" / "svg"
    for fam, k in [("arrow", 2), ("overlap", 2), ("badge", 1), ("monogram-frame", 1)]:
        d = sg / fam
        if not d.is_dir():
            continue
        for svg in sorted(d.glob("*.svg"))[:k]:
            save_variants(svg, OUT / "diagrams", manifest, "diagrams",
                          heights=(96, 192), jpegs=((192, 55),))

    # real raster+vector pairs (as-is, no re-render): 3 pieces
    rvp_img = CORPUS / "raster_vector_pairs" / "images" / "128"
    rvp_vec = CORPUS / "raster_vector_pairs" / "vectors"
    if rvp_img.is_dir() and rvp_vec.is_dir():
        for img_p in sorted(rvp_img.glob("*.png"))[:3]:
            vec = next(iter(sorted(rvp_vec.glob(img_p.stem + "*"))), None)
            dst_i = OUT / "ui_icons" / f"pair_{img_p.name}"
            shutil.copy2(img_p, dst_i)
            manifest.append({"file": str(dst_i.relative_to(OUT)), "source": str(img_p),
                             "category": "ui_icons", "kind": "raster-of-pair"})
            if vec:
                dst_v = OUT / "ui_icons" / f"pair_{img_p.stem}{vec.suffix}"
                shutil.copy2(vec, dst_v)
                manifest.append({"file": str(dst_v.relative_to(OUT)), "source": str(vec),
                                 "category": "ui_icons", "kind": "vector-gt"})

    # ---- 3) nasty combos into jpeg_dirty ------------------------------------
    nasty = [row for row in manifest if row.get("kind") == "jpeg" and row.get("q", 99) <= 40]
    for row in nasty[:12]:
        src = OUT / row["file"]
        dst = OUT / "jpeg_dirty" / Path(row["file"]).name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            manifest.append({**row, "file": str(dst.relative_to(OUT)),
                             "category": "jpeg_dirty", "kind": "jpeg-copy"})

    # ---- 4) review sheets + manifest ----------------------------------------
    for cat in CATS:
        contact_sheet(OUT / cat, OUT / "REVIEW_SHEETS" / f"{cat}.png")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    from collections import Counter
    counts = Counter(r["category"] for r in manifest)
    print("files per category:", dict(counts))
    print("total manifest rows:", len(manifest))
    print("OUT:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

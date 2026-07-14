"""Blind challenge-pack evaluation: OURS vs VAI on the fed plates.

Inputs: challenge_pack/plates/plate_NN.png (what VAI saw),
        plate_NN_vai.svg (VAI results), plate_layout.json (item bboxes).

Per item:
  crop      = plate cell crop (the EXACT raster both sides must explain)
  vai item  = VAI paths whose bbox-center falls in the cell, re-wrapped as an
              SVG with the cell's viewBox (geometry untouched)
  ours item = geometry_vectorizer.process() on the crop (flagship mode)
Meters (reused from benchmark_vai): geometry (wobble, g2, kinks, staircase,
micro) + raster (iou/ssim/mae vs crop, seams, roundness).  Aggregates per
category: win counts, medians AND p95 tails (the audit's requirement).

Usage: python challenge_eval.py [--plates 1,2,3] [--limit N] [--mode paper-regions]
Output: challenge_pack/eval/{items/*, ours/*, report.json, sheets/*.png}
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import numpy as np
from PIL import Image

PACK = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack")
PLATES = PACK / "plates"
EVAL = PACK / "eval"


def split_vai(plate_no: int, layout: list[dict]) -> dict[int, Path]:
    """Cut plate_NN_vai.svg into per-item SVGs by bbox-center assignment."""
    from svgpathtools import parse_path
    svg_path = PLATES / f"plate_{plate_no:02}_vai.svg"
    if not svg_path.exists():
        return {}
    text = svg_path.read_text(encoding="utf-8", errors="replace")
    # capture whole <path .../> elements verbatim (keep fills etc.)
    elements = re.findall(r"<path\b[^>]*/>|<path\b[^>]*>.*?</path>", text, flags=re.S)
    cells = [(k, item) for k, item in enumerate(layout) if item["plate"] == plate_no]
    assigned: dict[int, list[str]] = {k: [] for k, _ in cells}
    for el in elements:
        m = re.search(r'\bd="([^"]+)"', el)
        if not m:
            continue
        try:
            p = parse_path(m.group(1))
            if not len(p):
                continue
            x0, x1, y0, y1 = p.bbox()
        except Exception:
            continue
        cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        area = max(1e-6, (x1 - x0) * (y1 - y0))
        for k, item in cells:
            bx0, by0, bx1, by1 = item["bbox"]
            if bx0 - 6 <= cx <= bx1 + 6 and by0 - 6 <= cy <= by1 + 6:
                # near-full-plate background paths belong to nobody
                if area > 4.0 * (bx1 - bx0) * (by1 - by0):
                    break
                assigned[k].append(el)
                break
    out: dict[int, Path] = {}
    (EVAL / "items").mkdir(parents=True, exist_ok=True)
    for k, item in cells:
        if not assigned[k]:
            continue
        bx0, by0, bx1, by1 = item["bbox"]
        w, h = bx1 - bx0, by1 - by0
        body = "".join(assigned[k])
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" '
               f'viewBox="{bx0} {by0} {w} {h}" width="{w}" height="{h}">'
               f'<rect x="{bx0}" y="{by0}" width="{w}" height="{h}" fill="#ffffff"/>'
               f"{body}</svg>")
        p = EVAL / "items" / f"item{k:03}_vai.svg"
        p.write_text(svg, encoding="utf-8")
        out[k] = p
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plates", default="1,2,3,4")
    ap.add_argument("--limit", type=int, default=10_000)
    ap.add_argument("--mode", default="paper-regions")
    args = ap.parse_args()
    plate_nos = [int(x) for x in args.plates.split(",")]

    import importlib.util
    spec = importlib.util.spec_from_file_location("bv", ROOT / "benchmark_vai.py")
    bv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bv)
    import geometry_vectorizer as gv

    layout = json.loads((PLATES / "plate_layout.json").read_text(encoding="utf-8"))
    EVAL.mkdir(exist_ok=True)
    (EVAL / "ours").mkdir(exist_ok=True)
    (EVAL / "crops").mkdir(exist_ok=True)

    vai_items: dict[int, Path] = {}
    for pn in plate_nos:
        vai_items.update(split_vai(pn, layout))
    print(f"vai items split: {len(vai_items)}")

    rows: list[dict] = []
    done = 0
    for k, item in enumerate(layout):
        if item["plate"] not in plate_nos or k not in vai_items:
            continue
        if done >= args.limit:
            break
        done += 1
        plate_img = Image.open(PLATES / f"plate_{item['plate']:02}.png").convert("RGB")
        bx0, by0, bx1, by1 = item["bbox"]
        crop = plate_img.crop((bx0, by0, bx1, by1))
        crop_p = EVAL / "crops" / f"item{k:03}.png"
        crop.save(crop_p)
        row = {"item": k, "category": item["category"], "source": item["source"],
               "size": [bx1 - bx0, by1 - by0]}
        W = bx1 - bx0
        # OURS: fit AND meters in a FRESH subprocess per item.  Long-lived
        # processes that interleave many fits/meters drift (2026-07-14: solo
        # and pair runs perfectly deterministic; an 8-item chain reproducibly
        # bent item043 kinks 1.76 -> 8.07 — one chain bent the FIT, another
        # bent the METER on a byte-identical SVG).  eval_one_item.py isolates.
        import subprocess
        r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "eval_one_item.py"),
                            str(crop_p), str(EVAL / "ours" / f"item{k:03}"), str(W), args.mode],
                           capture_output=True, text=True, cwd=str(ROOT))
        try:
            row["ours"] = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            row["ours"] = {"error": ("subprocess: " + (r.stderr or r.stdout)).strip()[:150]}
        svg = vai_items[k]
        if svg is not None and svg.exists():
            meters = {}
            try:
                meters.update(bv.geometry_meters(svg, W))
                meters.update(bv.roundness_meter(svg, W))
                meters.update(bv.raster_meters(svg, crop_p))
            except Exception as exc:
                meters["error"] = f"{type(exc).__name__}: {exc}"[:150]
            row["vai"] = meters
        rows.append(row)
        o, v = row.get("ours", {}), row.get("vai", {})
        print(f"[{done:3}] item{k:03} {item['category'][:12]:12} "
              f"iou {o.get('ink_iou')}|{v.get('ink_iou')} "
              f"kink {o.get('kinks_per_100px')}|{v.get('kinks_per_100px')}", flush=True)

    # aggregate per category with medians and p95
    def agg(rows_c: list[dict]) -> dict:
        out = {}
        for meter in bv.KEY_METERS:
            ours_v, vai_v, wins, ties, total = [], [], 0, 0, 0
            for r in rows_c:
                o, v = r.get("ours", {}).get(meter), r.get("vai", {}).get(meter)
                if o is None or v is None:
                    continue
                total += 1
                ours_v.append(o)
                vai_v.append(v)
                if abs(o - v) < 1e-9:
                    ties += 1
                elif (o < v) == (meter in bv.LOWER_BETTER):
                    wins += 1
            if total:
                out[meter] = {
                    "wins": f"{wins}+{ties}t/{total}",
                    "med": [round(float(np.median(ours_v)), 4), round(float(np.median(vai_v)), 4)],
                    "p95": [round(float(np.percentile(ours_v, 95)), 4), round(float(np.percentile(vai_v, 95)), 4)],
                }
        return out

    cats = sorted({r["category"] for r in rows})
    report = {"mode": args.mode, "n_items": len(rows),
              "per_category": {c: agg([r for r in rows if r["category"] == c]) for c in cats},
              "overall": agg(rows), "rows": rows}
    (EVAL / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("\n=== OVERALL (wins; med ours|vai; p95 ours|vai) ===")
    for meter, d in report["overall"].items():
        print(f"  {meter:18} {d['wins']:>10}  med {d['med'][0]} | {d['med'][1]}  p95 {d['p95'][0]} | {d['p95'][1]}")
    print("report ->", EVAL / "report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

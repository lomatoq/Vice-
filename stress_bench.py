"""Wave B: controlled-degradation stress bench against ANALYTICAL ground truth.

benchmark_vai measures us against VAI outputs and the challenge harness
against the (possibly degraded) input raster; neither isolates ROBUSTNESS.
Here the truth is the clean GT-SVG render itself: rasterise a vector-GT
item, apply a controlled degradation, vectorise the degraded raster, and
meter the RESULT against the CLEAN render — iou/mae (raster_meters with
src = GT render), boundary P/R/F + Hausdorff95, and Euler deltas
(components/holes).  Tails (p90/p95) per condition are the deliverable:
they show which degradations break which invariants.

Items: a balanced subset of the challenge pack's vector-gt entries (the
blind FROZEN report is untouched - these are the OPEN items).  Runs are
per-item subprocesses (stress_one.py) per the isolation discipline.

Usage:  stress_bench.py [--items N_PER_CAT] [--width W] [--conditions a,b]
Output: benchmarks/stress_report.json (+ per-run rows)
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).parent
PACK = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/challenge_pack")
WORK = ROOT / "benchmarks" / "stress_work"
OUT_JSON = ROOT / "benchmarks" / "stress_report.json"
PY = sys.executable


def degrade(img: Image.Image, condition: str) -> Image.Image:
    """The controlled degradation grid.  Each condition is one REALISTIC
    acquisition path, not an adversarial soup."""
    rgb = img.convert("RGB")
    if condition == "clean":
        return rgb
    if condition.startswith("q"):                      # jpeg round-trip
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=int(condition[1:]), subsampling=2)
        return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    if condition.startswith("blur"):
        return rgb.filter(ImageFilter.GaussianBlur(float(condition[4:])))
    if condition.startswith("gamma"):                  # display gamma shift + mild jpeg
        g = float(condition[5:])
        arr = np.asarray(rgb, np.float32) / 255.0
        arr = np.power(arr, g)
        out = Image.fromarray((arr * 255.0 + 0.5).astype(np.uint8))
        buf = io.BytesIO()
        out.save(buf, format="JPEG", quality=60, subsampling=2)
        return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    if condition == "upscale":                         # web-resized artwork
        w, h = rgb.size
        small = rgb.resize((max(8, int(w * 0.62)), max(8, int(h * 0.62))),
                           Image.Resampling.BILINEAR)
        return small.resize((w, h), Image.Resampling.BICUBIC)
    raise ValueError(condition)


def pick_items(per_cat: int) -> list[dict]:
    man = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
    gt = [it for it in man if it.get("kind") == "vector-gt"]
    by_cat: dict[str, list[dict]] = {}
    for it in sorted(gt, key=lambda x: x["file"]):
        by_cat.setdefault(it["category"], []).append(it)
    out = []
    for cat in sorted(by_cat):
        out.extend(by_cat[cat][:per_cat])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", type=int, default=2)
    ap.add_argument("--width", type=int, default=160)
    ap.add_argument("--conditions", default="clean,q60,q30,blur0.7,gamma1.3,upscale")
    ap.add_argument("--engine", default="ours", choices=["ours", "vtracer", "potrace"])
    args = ap.parse_args()

    import importlib.util
    spec = importlib.util.spec_from_file_location("bv", ROOT / "benchmark_vai.py")
    bv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bv)

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    items = pick_items(args.items)
    WORK.mkdir(parents=True, exist_ok=True)
    rows = []
    t0 = time.time()
    for it in items:
        svg = PACK / it["file"]
        stem = svg.stem
        try:
            gt_img = bv.render_svg(svg, args.width)
        except Exception as exc:
            print(f"skip {stem}: render {exc}", flush=True)
            continue
        gt_path = WORK / f"{stem}__gt.png"
        gt_img.convert("RGB").save(gt_path)
        for cond in conditions:
            tag = f"{stem}__{cond}"
            deg_path = WORK / f"{tag}.png"
            degrade(gt_img, cond).save(deg_path)
            out_dir = WORK / "runs" / (tag if args.engine == "ours" else f"{tag}__{args.engine}")
            r = subprocess.run(
                [PY, str(ROOT / "stress_one.py"), str(deg_path), str(gt_path),
                 str(out_dir), str(args.width), args.engine],
                capture_output=True, text=True, timeout=900)
            line = (r.stdout.strip().splitlines() or ["{}"])[-1]
            try:
                meters = json.loads(line)
            except Exception:
                meters = {"error": (r.stderr or line)[:300]}
            meters.update({"item": stem, "category": it["category"], "condition": cond})
            rows.append(meters)
            flag = "ERR" if "error" in meters else ""
            print(f"[{len(rows)}] {tag}: iou {meters.get('ink_iou')} bF {meters.get('boundary_f')} "
                  f"h95 {meters.get('hausdorff95')} eulerC {meters.get('comp_delta')} {flag}",
                  flush=True)
    # aggregate per condition
    agg: dict[str, dict] = {}
    for cond in conditions:
        sel = [r for r in rows if r["condition"] == cond and "error" not in r]
        entry: dict = {"n": len(sel)}
        for k in ("ink_iou", "boundary_f", "hausdorff95", "mae"):
            vals = np.asarray([r[k] for r in sel if r.get(k) is not None], float)
            if len(vals):
                entry[k] = {"med": round(float(np.median(vals)), 4),
                            "p90": round(float(np.percentile(vals, 90)), 4),
                            "p95": round(float(np.percentile(vals, 95)), 4)}
        entry["euler_breaks"] = int(sum(1 for r in sel
                                        if r.get("comp_delta") or r.get("hole_delta")))
        agg[cond] = entry
    out_json = (OUT_JSON if args.engine == "ours"
                else OUT_JSON.with_name(f"stress_report_{args.engine}.json"))
    out_json.write_text(json.dumps({"width": args.width, "engine": args.engine, "rows": rows,
                                    "aggregate": agg,
                                    "secs": round(time.time() - t0, 1)},
                                   indent=1), encoding="utf-8")
    print(json.dumps(agg, indent=1))
    print("->", out_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())

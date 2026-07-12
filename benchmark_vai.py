"""Stage-0 harness (METHOD_ICE_BY.md §4): paired A/B against real vectorizer.ai output.

Corpus: C:/Users/nirrt/Toolset/v-ice pictures/vai/<stem>_vai.svg  (real VAI SVGs)
        C:/Users/nirrt/Toolset/v-ice pictures/CORPUS_REVIEW/<stem>.png  (sources)

Per image, both OUR SVG and the VAI SVG get the same artifact meters:
  geometry (from path data, resolution-normalized to native px):
    wobble        mean of (dkappa/ds)^2 integrated inside segments, per unit length
    g2_steps      mean |delta kappa| across G1-smooth joins (tangent jump < 4 deg)
    kinks_per_100px  joins with tangent jump in [4, 25) deg — unintended kinks
    staircase_runs   runs of >=4 consecutive sub-2.2px segments with alternating
                     near-orthogonal turns — vectorized jaggies
    micro_segs    segments with chord < 0.75px
  raster (render vs source):
    ink_iou, mae, rmse (sanity floor only — idealization legally moves pixels)
    seam_px       native-px^2 area of thin enclosed background-colored cracks
                  at 4x that are NOT background in the source
    ssim          grayscale SSIM at native scale
    roundness     mean relative radial RMS over circle-intent subpaths
    mirror_iou    best vertical/horizontal mirror self-IoU of the ink (source
                  column shows the intent ceiling)

Usage:
  python benchmark_vai.py [--mode paper-regions] [--n 50] [--all] [--reuse]
                          [--stems a,b,c]
Snapshot: benchmarks/vai_snapshot.json (previous kept as vai_snapshot_prev.json).
Primary gates per METHOD_ICE: staircase_runs, seam_px, wobble, judge win-rate.
MAE/RMSE are diagnostics, never acceptance criteria.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import numpy as np
from PIL import Image

VAI_DIR = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/vai")
SRC_DIRS = [Path(r"C:/Users/nirrt/Toolset/v-ice pictures/problem cases/Small"),
            ROOT / "web_preview/uploads"]
OUT = ROOT / "benchmarks"
WORK = OUT / "vai_work"

_SRC_INDEX: dict[str, Path] | None = None


def _source_index() -> dict[str, Path]:
    """stem -> the ACTUAL raster VAI processed (NNN_<stem>_src.png files).

    CORPUS_REVIEW/<stem>.png files are often different renditions (e.g.
    betsoft_512.png is 2548x420 while the VAI svg viewBox is 512x256), so only
    *_src.png files are trusted, validated by viewBox aspect at pairing time.
    """
    global _SRC_INDEX
    if _SRC_INDEX is None:
        import re as _re
        _SRC_INDEX = {}
        for d in SRC_DIRS:
            if not d.exists():
                continue
            for f in sorted(d.glob("*_src.png")):
                m = _re.match(r"^\d+_(.+)_src$", f.stem)
                key = m.group(1) if m else f.stem[:-4]
                _SRC_INDEX.setdefault(key, f)
    return _SRC_INDEX


def find_source(stem: str) -> Path | None:
    idx = _source_index()
    src = idx.get(stem) or idx.get(stem + "_vai")
    if src is None:
        return None
    import re as _re
    vai_svg = VAI_DIR / f"{stem}_vai.svg"
    m = _re.search(r'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)',
                   vai_svg.read_text(encoding="utf-8", errors="replace"))
    if m:
        vb_w, vb_h = float(m.group(1)), float(m.group(2))
        W, H = Image.open(src).size
        if vb_w > 0 and vb_h > 0 and abs((W / H) / (vb_w / vb_h) - 1.0) > 0.05:
            return None  # aspect mismatch: not the raster VAI actually saw
    return src


# ------------------------------------------------------------------ rendering
def render_svg(svg_path: Path, width: int) -> Image.Image:
    import resvg_py
    png = resvg_py.svg_to_bytes(svg_string=svg_path.read_text(encoding="utf-8"),
                                width=width)
    img = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    base = Image.new("RGB", img.size, (255, 255, 255))
    base.paste(img, mask=img.split()[3])
    return base


def _bg_of(arr: np.ndarray) -> np.ndarray:
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    return np.median(border, axis=0)


# ------------------------------------------------------------------ geometry meters
def _svg_scale(svg_path: Path, native_w: int) -> float:
    import re
    text = svg_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)', text)
    if not m:
        return 1.0
    vb_w = float(m.group(1))
    return native_w / vb_w if vb_w > 0 else 1.0


def _parse_paths(svg_path: Path):
    """Regex + parse_path: robust to '%' attribute values that break svg2paths."""
    import re as _re
    from svgpathtools import parse_path
    text = svg_path.read_text(encoding="utf-8", errors="replace")
    paths = []
    for d in _re.findall(r'<path\b[^>]*?\bd="([^"]+)"', text):
        try:
            p = parse_path(d)
            if len(p):
                paths.append(p)
        except Exception:
            continue
    return paths


def geometry_meters(svg_path: Path, native_w: int) -> dict:
    """Path-space meters, coordinates normalized so 1 unit == 1 native pixel."""
    paths = _parse_paths(svg_path)
    if not paths:
        return {"wobble": None, "g2_steps": None, "kinks_per_100px": None,
                "staircase_runs": None, "micro_segs": None, "total_len": None,
                "segments": None}
    s = _svg_scale(svg_path, native_w)

    wobble_num = 0.0
    total_len = 0.0
    g2_steps: list[float] = []
    kinks = 0
    micro = 0
    stair_runs = 0
    n_segs = 0
    K = 8

    for path in paths:
        segs = [seg for seg in path if seg.length() > 1e-9]
        if not segs:
            continue
        n_segs += len(segs)
        # Per-segment analytic curvature -> wobble inside segments.
        seg_info = []  # (chord_px, tan_in, tan_out, k_in, k_out)
        for seg in segs:
            try:
                L = seg.length() * s
            except Exception:
                continue
            chord = abs(seg.end - seg.start) * s
            if chord < 0.75:
                micro += 1
            total_len += L
            ts = [(i + 0.5) / K for i in range(K)]
            ks = []
            for t in ts:
                try:
                    ks.append(seg.curvature(t) / s)  # 1/px
                except Exception:
                    ks.append(0.0)
            ds = max(L / K, 1e-6)
            for a, b in zip(ks, ks[1:]):
                wobble_num += ((b - a) / ds) ** 2 * ds
            try:
                tan_in = seg.unit_tangent(0.02)
                tan_out = seg.unit_tangent(0.98)
            except Exception:
                d = seg.end - seg.start
                tan_in = tan_out = d / abs(d) if abs(d) > 0 else 1 + 0j
            seg_info.append((chord, tan_in, tan_out, ks[0], ks[-1]))

        # Joins (closed loop -> wrap around).
        m = len(seg_info)
        for i in range(m):
            j = (i + 1) % m
            if m == 1:
                break
            _, _, t_out, _, k_out = seg_info[i]
            _, t_in, _, k_in, _ = seg_info[j]
            dot = (t_out.real * t_in.real + t_out.imag * t_in.imag)
            ang = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
            if ang < 4.0:
                g2_steps.append(abs(k_in - k_out))
            elif ang < 25.0:
                kinks += 1

        # Staircase runs: >=4 consecutive short segments, alternating turns.
        chords = [c for c, *_ in seg_info]
        tangs = [(t_in, t_out) for _, t_in, t_out, _, _ in seg_info]
        run = 0
        last_cross_sign = 0
        for i in range(m):
            j = (i + 1) % m
            short = chords[i] < 2.2 and chords[j] < 2.2
            t_a, t_b = tangs[i][1], tangs[j][0]
            cross = t_a.real * t_b.imag - t_a.imag * t_b.real
            dot = t_a.real * t_b.real + t_a.imag * t_b.imag
            ang = math.degrees(math.atan2(abs(cross), dot))
            alternating = 55.0 <= ang <= 125.0 and (
                last_cross_sign == 0 or (cross > 0) != (last_cross_sign > 0))
            if short and alternating:
                run += 1
                last_cross_sign = 1 if cross > 0 else -1
                if run == 3:  # 4 segments = 3 alternating short joins
                    stair_runs += 1
            else:
                run = 0
                last_cross_sign = 0

    return {
        "wobble": round(wobble_num / total_len, 4) if total_len else None,
        "g2_steps": round(float(np.mean(g2_steps)), 4) if g2_steps else 0.0,
        "kinks_per_100px": round(100.0 * kinks / total_len, 3) if total_len else None,
        "staircase_runs": stair_runs,
        "micro_segs": micro,
        "total_len": round(total_len, 1),
        "segments": n_segs,
    }


def roundness_meter(svg_path: Path, native_w: int) -> dict:
    """Circle-intent subpaths: relative radial RMS of the Taubin fit."""
    from vectorize_papers import fit_circle

    paths = _parse_paths(svg_path)
    if not paths:
        return {"roundness": None, "circles": 0}
    s = _svg_scale(svg_path, native_w)
    residuals = []
    for path in paths:
        for sub in path.continuous_subpaths():
            if not sub.isclosed():
                continue
            try:
                L = sub.length() * s
            except Exception:
                continue
            if L < 12.0:
                continue
            pts = np.array([[sub.point(i / 64).real * s, sub.point(i / 64).imag * s]
                            for i in range(64)])
            fit = fit_circle(pts)
            if fit is None:
                continue
            _center, r, rms = fit
            if r < 2.0 or r > 4.0 * native_w:
                continue
            rel = float(rms / r)
            if rel < 0.04:  # reads as an intended circle
                residuals.append(rel)
    return {"roundness": round(float(np.mean(residuals)), 5) if residuals else None,
            "circles": len(residuals)}


# ------------------------------------------------------------------ raster meters
def raster_meters(svg_path: Path, src: Path) -> dict:
    src_img = np.asarray(Image.open(src).convert("RGB"), float)
    H, W = src_img.shape[:2]
    render = render_svg(svg_path, W)
    if render.size != (W, H):
        render = render.resize((W, H), Image.LANCZOS)
    ren = np.asarray(render, float)

    mae = float(np.mean(np.abs(ren - src_img)))
    rmse = float(np.sqrt(np.mean((ren - src_img) ** 2)))
    bg = _bg_of(src_img)
    ink_src = np.sum(np.abs(src_img - bg), axis=2) > 90
    ink_ren = np.sum(np.abs(ren - bg), axis=2) > 90
    union = int(np.sum(ink_src | ink_ren))
    iou = float(np.sum(ink_src & ink_ren)) / union if union else 1.0

    try:
        from skimage.metrics import structural_similarity
        gray_s = np.mean(src_img, axis=2)
        gray_r = np.mean(ren, axis=2)
        ssim = float(structural_similarity(gray_s, gray_r, data_range=255.0))
    except Exception:
        ssim = None

    return {"mae": round(mae, 2), "rmse": round(rmse, 2),
            "ink_iou": round(iou, 4),
            "ssim": round(ssim, 4) if ssim is not None else None,
            "seam_px": seam_meter(svg_path, src_img, bg),
            "mirror_iou": round(mirror_iou(ink_ren), 4)}


def seam_meter(svg_path: Path, src_img: np.ndarray, src_bg: np.ndarray) -> float:
    """Thin enclosed background-colored cracks at 4x that the source does not have.

    Red-team spec: gate on CONNECTED crack areas, not single AA samples; 'exactly
    zero uncovered pixels' is unachievable under anti-aliasing.
    """
    import cv2
    H, W = src_img.shape[:2]
    hi = np.asarray(render_svg(svg_path, W * 4), float)
    hb = _bg_of(hi)
    bgish = np.sum(np.abs(hi - hb), axis=2) < 75  # near-background at 4x
    n, lab, stats, cent = cv2.connectedComponentsWithStats(
        bgish.astype(np.uint8), connectivity=8)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    seam_area_hi = 0
    for i in range(1, n):
        if i in border:
            continue
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 4:
            continue
        w_box = stats[i, cv2.CC_STAT_WIDTH]
        h_box = stats[i, cv2.CC_STAT_HEIGHT]
        comp = (lab == i).astype(np.uint8)
        thickness = float(cv2.distanceTransform(comp, cv2.DIST_L2, 3).max())
        if thickness > 2.0:  # >0.5 native px thick: a real hole, not a seam
            continue
        if max(w_box, h_box) < 8:  # <2 native px long: AA noise
            continue
        cx, cy = cent[i]
        sx = min(int(cx / 4), src_img.shape[1] - 1)
        sy = min(int(cy / 4), src_img.shape[0] - 1)
        if np.sum(np.abs(src_img[sy, sx] - src_bg)) < 75:
            continue  # source really is background here
        seam_area_hi += int(area)
    return round(seam_area_hi / 16.0, 2)  # native px^2


def mirror_iou(ink: np.ndarray) -> float:
    """Best vertical/horizontal mirror self-IoU of the ink mask."""
    ys, xs = np.nonzero(ink)
    if not len(xs):
        return 1.0
    best = 0.0
    for axis in (0, 1):
        lo, hi = (xs.min(), xs.max()) if axis == 0 else (ys.min(), ys.max())
        center0 = (lo + hi) / 2.0
        for off in np.arange(-2.0, 2.01, 0.5):
            c = center0 + off
            if axis == 0:
                ref_x = np.clip(np.round(2 * c - xs).astype(int), 0, ink.shape[1] - 1)
                refl = np.zeros_like(ink)
                refl[ys, ref_x] = True
            else:
                ref_y = np.clip(np.round(2 * c - ys).astype(int), 0, ink.shape[0] - 1)
                refl = np.zeros_like(ink)
                refl[ref_y, xs] = True
            union = np.sum(ink | refl)
            if union:
                best = max(best, float(np.sum(ink & refl)) / union)
    return best


# ------------------------------------------------------------------ driver
def frozen_stems(n: int) -> list[str]:
    """Deterministic reference subset: sha1-sorted stems with validated sources."""
    stems = []
    for svg in sorted(VAI_DIR.glob("*_vai.svg")):
        stem = svg.name[:-8]
        if find_source(stem) is not None:
            stems.append(stem)
    stems.sort(key=lambda s: hashlib.sha1(s.encode()).hexdigest())
    return stems[:n]


def measure_one(stem: str, mode: str, reuse: bool, run_tag: str | None = None) -> dict | None:
    src = find_source(stem)
    if src is None:
        return {"stem": stem, "error": "no validated source raster"}
    vai_svg = VAI_DIR / f"{stem}_vai.svg"
    W = Image.open(src).size[0]

    out_dir = WORK / (run_tag or mode) / stem
    ours_svg = out_dir / src.stem / "03_rebuilt_filled.svg"
    row: dict = {"stem": stem}
    t0 = time.time()
    if not (reuse and ours_svg.exists()):
        import geometry_vectorizer as gv
        try:
            rep = gv.process(src, out_dir, smoothing=mode)
        except Exception as exc:
            return {"stem": stem, "error": f"{type(exc).__name__}: {exc}"}
        row["fallback_loops"] = sum(v for k, v in rep["templates"].items()
                                    if k.endswith("-fallback"))
        row["prims"] = rep.get("rendered_primitive_count")
    else:
        report = out_dir / src.stem / "report.json"
        if report.exists():
            rep = json.loads(report.read_text(encoding="utf-8"))
            row["fallback_loops"] = sum(v for k, v in rep.get("templates", {}).items()
                                        if k.endswith("-fallback"))
            row["prims"] = rep.get("rendered_primitive_count")
    row["secs"] = round(time.time() - t0, 1)

    for tag, svg in (("ours", ours_svg), ("vai", vai_svg)):
        if not svg.exists():
            row[tag] = {"error": "missing svg"}
            continue
        meters = {}
        meters.update(geometry_meters(svg, W))
        meters.update(roundness_meter(svg, W))
        meters.update(raster_meters(svg, src))
        row[tag] = meters

    # Source's own symmetry = the intent ceiling for mirror_iou.
    src_img = np.asarray(Image.open(src).convert("RGB"), float)
    ink = np.sum(np.abs(src_img - _bg_of(src_img)), axis=2) > 90
    row["src_mirror_iou"] = round(mirror_iou(ink), 4)
    return row


KEY_METERS = ["staircase_runs", "seam_px", "wobble", "g2_steps",
              "kinks_per_100px", "micro_segs", "roundness", "ink_iou",
              "ssim", "mae"]
LOWER_BETTER = {"staircase_runs", "seam_px", "wobble", "g2_steps",
                "kinks_per_100px", "micro_segs", "roundness", "mae"}


def aggregate(rows: list[dict]) -> dict:
    agg: dict = {"n": len(rows), "wins": {}, "means": {}}
    for meter in KEY_METERS:
        ours_vals, vai_vals, wins, ties, total = [], [], 0, 0, 0
        for row in rows:
            o = row.get("ours", {}).get(meter)
            v = row.get("vai", {}).get(meter)
            if o is None or v is None:
                continue
            total += 1
            ours_vals.append(o)
            vai_vals.append(v)
            if abs(o - v) < 1e-9:
                ties += 1
            elif (o < v) == (meter in LOWER_BETTER):
                wins += 1
        if total:
            agg["wins"][meter] = f"{wins}+{ties}t/{total}"
            agg["means"][meter] = {"ours": round(float(np.mean(ours_vals)), 4),
                                   "vai": round(float(np.mean(vai_vals)), 4)}
    return agg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="paper-regions")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--reuse", action="store_true",
                    help="reuse existing outputs in benchmarks/vai_work")
    ap.add_argument("--stems", default=None, help="comma list overrides the subset")
    ap.add_argument("--fit-profile", default=None,
                    choices=["production", "text-safe"])
    ap.add_argument("--corner-policy", default=None,
                    choices=["production", "tiny-safe", "cnn-conservative"])
    ap.add_argument("--snapshot", default="vai_snapshot.json",
                    help="snapshot filename under benchmarks/")
    args = ap.parse_args()

    if args.fit_profile or args.corner_policy:
        import geometry_vectorizer as gv
        if args.fit_profile:
            gv._PAPER_FIT_PROFILE = args.fit_profile
        if args.corner_policy:
            gv._CORNER_POSTPROCESS_POLICY = args.corner_policy
        print(f"A/B overrides: fit_profile={args.fit_profile} "
              f"corner_policy={args.corner_policy}")

    if args.stems:
        stems = [s.strip() for s in args.stems.split(",") if s.strip()]
    else:
        stems = frozen_stems(10_000 if args.all else args.n)
    OUT.mkdir(exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    run_tag = args.mode
    if args.fit_profile or args.corner_policy:
        run_tag += f"_{args.fit_profile or 'prod'}_{args.corner_policy or 'prod'}"

    rows = []
    for i, stem in enumerate(stems, 1):
        row = measure_one(stem, args.mode, args.reuse, run_tag)
        if row is None:
            continue
        rows.append(row)
        o, v = row.get("ours", {}), row.get("vai", {})
        print(f"[{i:3}/{len(stems)}] {stem:28} "
              f"stair {o.get('staircase_runs')}|{v.get('staircase_runs')}  "
              f"seam {o.get('seam_px')}|{v.get('seam_px')}  "
              f"wob {o.get('wobble')}|{v.get('wobble')}  "
              f"iou {o.get('ink_iou')}|{v.get('ink_iou')}  "
              f"fb {row.get('fallback_loops')}  {row.get('secs')}s", flush=True)

    agg = aggregate([r for r in rows if "error" not in r])
    print("\n=== OURS vs VAI (wins+ties/total; means ours|vai) ===")
    for meter in KEY_METERS:
        if meter in agg["wins"]:
            m = agg["means"][meter]
            print(f"  {meter:18} {agg['wins'][meter]:>10}   {m['ours']} | {m['vai']}")

    snap = OUT / args.snapshot
    if snap.exists():
        snap.replace(snap.with_name(snap.stem + "_prev.json"))
    snap.write_text(json.dumps({"mode": args.mode, "rows": rows, "aggregate": agg},
                               indent=1), encoding="utf-8")
    print(f"\nSnapshot -> {snap}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

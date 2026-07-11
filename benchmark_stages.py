"""Per-stage regression benchmark (audit P0-4): one command, ~40 fixed cases,
per-stage metrics, PASS/FAIL table, JSON snapshot with deltas vs the previous run.

Stages measured:
  extraction  -> mask count sanity (paper modes)
  corners     -> final P/R/F1 vs human annotations (held-out casino logos)
  fitter      -> bidirectional max deviation, fill IoU, primitive counts,
                 pixel-faithful fallback count (must be RARE), type expectations
                 on synthetic shapes with known decompositions
  regions     -> seam/gap pixels in paper-regions mode
  smooth-FP   -> corners on known-smooth shapes (spotify)

Usage:  python benchmark_stages.py [--fast]
Snapshots land in benchmarks/stage_snapshot.json (previous kept as *_prev.json).
"""
import io
import json
import math
import re
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import numpy as np
from PIL import Image, ImageDraw

import geometry_vectorizer as gv
from corner_classifier import mask_loops, _to_ccw
from svg_corners import svg_region_masks

OUT = ROOT / "benchmarks"
OUT.mkdir(exist_ok=True)
WORK = OUT / "work"
WORK.mkdir(exist_ok=True)
COR = Path(r"C:/Users/nirrt/Toolset/v-ize train/dataset/icons/iconify")
UPLOADS = ROOT / "web_preview/uploads"
PROBLEM = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/problem cases/Small")

FAST = "--fast" in sys.argv


# --------------------------------------------------------------------------- helpers
def flatten_svg(svg: Path, target: int) -> Image.Image:
    import resvg_py
    png = resvg_py.svg_to_bytes(svg_string=svg.read_text(encoding="utf-8"), width=target)
    img = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    base = Image.new("RGB", img.size, (255, 255, 255))
    base.paste(img, mask=img.split()[3])
    return base


def _count_topology(inked: np.ndarray) -> tuple[int, int]:
    """(components, material holes), with image-scale-aware micro-detail noise.

    Four pixels is material in a 110x20 wordmark but is a single Lacoste scale in
    a 244x109 image.  Use a relative floor for holes while retaining the strict
    four-pixel component floor; tiny coloured counters are checked separately by
    ``tiny_color_detail_score``.
    """
    import cv2
    mask = inked.astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    comps = sum(1 for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= 4)
    inv = (~inked).astype(np.uint8)
    n2, lab2, stats2, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
    border_labels = set(np.unique(np.concatenate([lab2[0], lab2[-1], lab2[:, 0], lab2[:, -1]])))
    hole_floor = max(4, int(round(mask.size * 0.00045)))
    holes = sum(1 for i in range(1, n2)
                if i not in border_labels and stats2[i, cv2.CC_STAT_AREA] >= hole_floor)
    return comps, holes


def loop_metrics(report_dir: Path, src: Path) -> dict:
    """Fill IoU + topology (components/holes) of the REBUILT raster vs the source."""
    src_img = np.asarray(Image.open(src).convert("RGB"), int)
    reb_path = report_dir / "03_rebuilt_filled.png"
    reb = Image.open(reb_path).convert("RGB")
    if reb.size != (src_img.shape[1], src_img.shape[0]):
        reb = reb.resize((src_img.shape[1], src_img.shape[0]), Image.NEAREST)
    reb = np.asarray(reb, int)
    border = np.concatenate([src_img[0], src_img[-1], src_img[:, 0], src_img[:, -1]])
    bg = np.median(border, axis=0)
    inked_src = np.sum(np.abs(src_img - bg), axis=2) > 90
    inked_reb = np.sum(np.abs(reb - bg), axis=2) > 90
    union = int(np.sum(inked_src | inked_reb))
    iou = float(np.sum(inked_src & inked_reb)) / union if union else 1.0
    cs, hs = _count_topology(inked_src)
    cr, hr = _count_topology(inked_reb)
    return {"raster_iou": round(iou, 4),
            "components": f"{cr}/{cs}", "holes": f"{hr}/{hs}",
            "topo_ok": bool(cr == cs and hr == hs)}


def tiny_color_detail_score(report_dir: Path, src: Path) -> float:
    """Colour fidelity on compact 2--18px regions at their source locations.

    Whole-ink topology cannot see a yellow counter inside a blue letter on a
    yellow badge.  Reusing paper-mode masks makes this a generic tiny-detail gate
    instead of a coordinate hard-code for IKEA.
    """
    image = Image.open(src)
    jpeg = (getattr(image, "format", None) or "").upper() in {"JPEG", "MPO"}
    try:
        rgb, masks, _boundary, _bg, _threshold, scale = gv.extract_perceptual_masks(
            image, use_icm=True, merge=True, deblur=not jpeg)
    except Exception:
        return 1.0
    rebuilt = Image.open(report_dir / "03_rebuilt_filled.png").convert("RGB")
    rebuilt = rebuilt.resize((rgb.shape[1], rgb.shape[0]), Image.Resampling.BILINEAR)
    pixels = np.asarray(rebuilt, float)
    scores = []
    for mask in masks:
        native_area = float(mask.sum()) / max(1.0, float(scale * scale))
        ys, xs = np.nonzero(mask)
        if not len(xs):
            continue
        native_extent = max(float(np.ptp(xs)), float(np.ptp(ys))) / max(1.0, float(scale))
        if not (2.0 <= native_area <= 18.0 and native_extent <= 8.0):
            continue
        target = np.median(rgb[mask], axis=0).astype(float)
        distance = np.linalg.norm(pixels[mask] - target, axis=1)
        scores.append(float(np.mean(np.exp(-distance / 60.0))))
    return min(scores) if scores else 1.0


def primitive_fragment_metrics(report_dir: Path) -> dict:
    """Representation-quality counters invisible to raster IoU.

    The primitive-map writer emits one simple ``M...L`` or ``M...C`` path per
    fitted primitive.  A sub-pixel chord is usually a graph weld/split artefact:
    it changes almost no pixels, yet leaves a useless blue or magenta sliver in
    the editable SVG.  We report both a strict micro count and a softer short
    count; case-specific gates can be calibrated without conflating genuine
    Lacoste scales with Mastercard circle fragmentation.
    """
    svg = report_dir / "02_primitive_map.svg"
    if not svg.exists():
        return {"micro_prims": 0, "short_prims": 0, "upper_micro_prims": 0,
                "lower_micro_prims": 0, "min_prim_chord": None}
    text = svg.read_text(encoding="utf-8")
    viewbox = re.search(r'viewBox="[^"]*?\s([0-9.]+)\s([0-9.]+)"', text)
    height = float(viewbox.group(2)) if viewbox else 0.0
    chords = []
    positioned = []
    for d in re.findall(r'<path\b[^>]*\bd="([^"]+)"', text):
        values = [float(value) for value in re.findall(r'-?(?:\d+(?:\.\d*)?|\.\d+)', d)]
        if len(values) < 4:
            continue
        chord = math.hypot(values[-2] - values[0], values[-1] - values[1])
        chords.append(chord)
        positioned.append((chord, 0.5 * (values[1] + values[-1])))
    return {
        "micro_prims": sum(length < 0.75 for length in chords),
        "short_prims": sum(length < 2.0 for length in chords),
        "upper_micro_prims": (sum(length < 0.75 and y < 0.75 * height
                                  for length, y in positioned) if height else 0),
        "lower_micro_prims": (sum(length < 0.75 and y >= 0.75 * height
                                  for length, y in positioned) if height else 0),
        "min_prim_chord": round(min(chords), 3) if chords else None,
    }


def fit_case(name: str, src: Path, smoothing: str = "paper") -> dict:
    t0 = time.time()
    rep = gv.process(src, WORK / f"{name}_{smoothing}", smoothing=smoothing)
    row = {
        "extractor": rep.get("extractor_used", "unknown"),
        "regions": rep["regions"],
        "prims": rep["rendered_primitive_count"],
        "L": rep["actual"]["L"], "C": rep["actual"]["C"],
        "fallback_loops": sum(v for k, v in rep["templates"].items() if k.endswith("-fallback")),
        "strokes": rep["templates"].get("stroke", 0),
        "occl": sum(v for k, v in rep["templates"].items() if k.startswith("occlusion")),
        "scale": rep["analysis_scale"],
        "secs": round(time.time() - t0, 1),
    }
    report_dir = WORK / f"{name}_{smoothing}" / src.stem
    row.update(loop_metrics(report_dir, src))
    row.update(primitive_fragment_metrics(report_dir))
    row["tiny_detail"] = round(tiny_color_detail_score(report_dir, src), 4)
    return row


# --------------------------------------------------------------------------- 1) synthetic
def synth_cases() -> dict:
    def make(name, draw_fn, jpeg=False):
        img = Image.new("RGB", (900, 900), (255, 255, 255))
        draw_fn(ImageDraw.Draw(img))
        p = WORK / f"{name}.{'jpg' if jpeg else 'png'}"
        if jpeg:
            img.save(p, "JPEG", quality=82)
        else:
            img.save(p)
        return p

    circle = lambda d: d.ellipse((110, 110, 790, 790), fill=(20, 60, 160))
    rrect = lambda d: d.rounded_rectangle((120, 200, 780, 700), radius=140, fill=(180, 30, 40))
    def bars(d):
        d.polygon([(100, 100), (800, 140), (760, 300), (140, 260)], fill=(10, 10, 10))
        d.polygon([(120, 420), (820, 460), (800, 560), (100, 520)], fill=(10, 120, 60))
    ellipse = lambda d: d.ellipse((110, 230, 790, 670), fill=(40, 110, 60))
    stadium = lambda d: d.rounded_rectangle((110, 300, 790, 600), radius=150, fill=(120, 40, 140))
    lshape = lambda d: d.polygon([(150, 150), (500, 150), (500, 450), (750, 450), (750, 750), (150, 750)],
                                 fill=(20, 20, 20))
    def cross(d):
        d.polygon([(380, 120), (520, 120), (520, 380), (780, 380), (780, 520), (520, 520),
                   (520, 780), (380, 780), (380, 520), (120, 520), (120, 380), (380, 380)],
                  fill=(160, 40, 40))
    def star(d):
        pts = []
        for k in range(10):
            r = 320 if k % 2 == 0 else 140
            a = -math.pi / 2 + k * math.pi / 5
            pts.append((450 + r * math.cos(a), 450 + r * math.sin(a)))
        d.polygon(pts, fill=(30, 60, 150))

    out = {}
    for name, fn, jpeg, size, check in [
        ("circle_clean", circle, False, 900, lambda r: r["L"] == 0 and r["C"] <= 10),
        ("circle_jpeg", circle, True, 900, lambda r: r["L"] == 0 and r["C"] <= 10),
        ("rrect_clean", rrect, False, 900, lambda r: r["L"] == 4 and r["C"] <= 12),
        ("rrect_jpeg", rrect, True, 900, lambda r: r["L"] == 4 and r["C"] <= 12),
        ("bars_clean", bars, False, 900, lambda r: 8 <= r["L"] <= 10 and r["C"] <= 2),
        ("bars_jpeg", bars, True, 900, lambda r: 8 <= r["L"] <= 10 and r["C"] <= 2),
        # audit P0-4 breadth: corner-free curved, mixed, and pure-polygon shapes.
        # Gates catch REGRESSIONS, not aspirations: one flat-top facet on a big
        # ellipse is the paper energy's own legal choice (G1-joined, invisible);
        # star tips carry +-1 quantization pieces.
        ("ellipse", ellipse, False, 900, lambda r: r["L"] <= 2 and r["C"] <= 16),
        ("stadium", stadium, False, 900, lambda r: r["L"] <= 2 and r["C"] <= 10),
        ("lshape", lshape, False, 900, lambda r: r["L"] == 6 and r["C"] == 0),
        ("cross", cross, False, 900, lambda r: r["L"] == 12 and r["C"] == 0),
        ("star", star, False, 900, lambda r: 10 <= r["L"] <= 12 and r["C"] <= 3),
        # small clean art exercises the 4x deblur route end-to-end.  The deblur
        # route trades primitive economy for subpixel detail (sides split more),
        # and fill IoU of small shapes is boundary-band dominated — size-scaled
        # gates; the drawn output is visually clean (checked 2026-07-11).
        ("small_circle64", lambda d: d.ellipse((8, 8, 56, 56), fill=(20, 60, 160)), False, 64,
         lambda r: r["L"] == 0 and r["C"] <= 10),
        ("small_rrect100", lambda d: d.rounded_rectangle((10, 20, 90, 80), radius=18, fill=(180, 30, 40)),
         False, 100, lambda r: r["L"] <= 16 and r["C"] <= 10),
    ]:
        def make_sized(name=name, fn=fn, jpeg=jpeg, size=size):
            img = Image.new("RGB", (size, size), (255, 255, 255))
            fn(ImageDraw.Draw(img))
            p = WORK / f"{name}.{'jpg' if jpeg else 'png'}"
            img.save(p, "JPEG", quality=82) if jpeg else img.save(p)
            return p
        row = fit_case(name, make_sized())
        min_iou = 0.93 if size <= 128 else 0.97
        row["pass"] = bool(check(row) and row["fallback_loops"] == 0
                           and row["raster_iou"] >= min_iou and row["topo_ok"])
        out[name] = row
    return out


# --------------------------------------------------------------------------- 2) corners vs human
def corner_cases() -> dict:
    ann = json.loads((ROOT / "corner_annotations.json").read_text(encoding="utf-8"))
    import random
    keys = [k for k, v in ann.items() if "corners_norm" in v and len(v["corners_norm"]) > 3]
    random.Random(42).shuffle(keys)
    held = keys[:60]
    picks = held[:12] if not FAST else held[:4]   # deterministic, representative mix
    tp = fp = fn = 0
    rows = {}
    for k in picks:
        rec = ann[k]
        try:
            regions = svg_region_masks(rec["file"], target=200)
        except Exception:
            continue
        H, W = regions[0][0].shape
        human = np.asarray(rec["corners_norm"], float) * [W, H]
        pred = []
        for m, _ in regions:
            for lp in mask_loops(m):
                lp = lp.astype(float)
                if len(lp) > 1 and np.allclose(lp[0], lp[-1]):
                    lp = lp[:-1]
                if len(lp) >= 8:
                    pred += [tuple(c) for c in gv.paper_corner_positions(_to_ccw(lp))]
        used = set()
        ltp = 0
        for p in pred:
            best, j = 6.0, None
            for i, g in enumerate(human):
                if i in used:
                    continue
                d = math.hypot(p[0] - g[0], p[1] - g[1])
                if d < best:
                    best, j = d, i
            if j is not None:
                used.add(j)
                ltp += 1
        lfp = len(pred) - ltp
        lfn = len(human) - len(used)
        tp += ltp; fp += lfp; fn += lfn
        rows[k.split("/")[-1][:28]] = {"tp": ltp, "fp": lfp, "fn": lfn}
    P = tp / max(1, tp + fp)
    R = tp / max(1, tp + fn)
    F = 2 * P * R / max(1e-9, P + R)
    # Gate calibrated to the measured baseline on THIS fixed subset (2026-07-11:
    # F1 ~0.75 on the first 12 held keys) minus a regression margin.
    return {"P": round(P, 3), "R": round(R, 3), "F1": round(F, 3),
            "n_logos": len(rows), "pass": bool(F >= 0.68), "per_logo": rows}


# --------------------------------------------------------------------------- 3) smooth FP + icons
def icon_cases() -> dict:
    out = {}
    spotify = COR / "simple-icons/spotify.svg"
    def spotify_corners(res: int) -> int:
        n = 0
        for m, _ in svg_region_masks(spotify, target=res):
            for lp in mask_loops(m):
                lp = lp.astype(float)
                if len(lp) > 1 and np.allclose(lp[0], lp[-1]):
                    lp = lp[:-1]
                if len(lp) >= 8:
                    n += len(gv.paper_corner_positions(_to_ccw(lp)))
        return n
    n380 = spotify_corners(380)
    out["spotify_smooth_fp"] = {"corners": n380, "pass": bool(n380 == 0)}
    # Small-res corners tracked WITHOUT gating: measured 2026-07-11 that per-res
    # thresholds change nothing (removal makes the pipeline threshold-insensitive;
    # synthetic smoothFP = 0.000 at every band/threshold), and at 48px the wave
    # caps have ~2px radius — their corner-ness is genuinely resolution-dependent
    # (the paper's own Sec-4 premise), not a detector bug.
    out["spotify_small_res"] = {"corners": spotify_corners(48) + spotify_corners(128), "pass": None}

    chrome_png = WORK / "chrome_128.png"
    flatten_svg(COR / "logos/chrome.svg", 128).save(chrome_png)
    row = fit_case("chrome", chrome_png, smoothing="paper-regions")
    row["pass"] = bool(row["raster_iou"] >= 0.96 and row["fallback_loops"] == 0)
    out["chrome_regions"] = row

    # audit P2 gradients: a TRUE smooth ramp must merge its posterized bands into
    # ONE gradient-filled region; a flag (distinct inks) must NOT merge.
    import numpy as _np
    xs, ys = _np.meshgrid(_np.arange(500), _np.arange(400))
    t = _np.clip((ys - 50) / 300.0, 0, 1)
    img = _np.full((400, 500, 3), 255, _np.uint8)
    box = (xs >= 60) & (xs < 440) & (ys >= 50) & (ys < 350)
    for ch, (a, b) in enumerate([(20, 196), (40, 232), (120, 248)]):
        img[..., ch] = _np.where(box, (a + (b - a) * t).astype(_np.uint8), 255)
    gpath = WORK / "gradient_rect.png"
    Image.fromarray(img).save(gpath)
    row = fit_case("gradient_rect", gpath)
    # inked-mask IoU wobbles at the LIGHT end of a ramp (|pixel-bg| straddles the
    # ink threshold on both sides) — 0.93 floor; the real gates are regions<=2
    # (the merge happened) and prims<=12 (bands collapsed).
    row["pass"] = bool(row["regions"] <= 2 and row["prims"] <= 12 and row["raster_iou"] >= 0.93)
    out["gradient_rect"] = row
    # audit P2 strokes: a round-cap ribbon must become a stroked centerline;
    # a fat square-butt rectangle must NOT.
    cap = Image.new("RGB", (400, 300), (255, 255, 255))
    cd = ImageDraw.Draw(cap)
    cd.line([(60, 220), (340, 80)], fill=(20, 20, 120), width=22)
    for c0 in ((60, 220), (340, 80)):
        cd.ellipse([c0[0] - 11, c0[1] - 11, c0[0] + 11, c0[1] + 11], fill=(20, 20, 120))
    cpath = WORK / "capsule_stroke.png"
    cap.save(cpath)
    row = fit_case("capsule_stroke", cpath)
    row["pass"] = bool(row["strokes"] == 1 and row["prims"] <= 12)
    out["capsule_stroke"] = row
    fr = Image.new("RGB", (400, 300), (255, 255, 255))
    ImageDraw.Draw(fr).rectangle((80, 100, 320, 190), fill=(20, 110, 40))
    fpath2 = WORK / "fatrect_filled.png"
    fr.save(fpath2)
    row = fit_case("fatrect_filled", fpath2)
    row["pass"] = bool(row["strokes"] == 0 and row["L"] == 4)
    out["fatrect_no_stroke"] = row

    # audit P2 occlusion completion: a base rect split/bitten by an overlay must
    # recover as ONE full template under it; an L-shape next to a square must NOT.
    ob = Image.new("RGB", (420, 300), (255, 255, 255))
    od = ImageDraw.Draw(ob)
    od.rectangle((40, 60, 380, 240), fill=(20, 70, 150))
    od.ellipse((150, 40, 330, 220), fill=(230, 180, 30))
    opath = WORK / "occl_base.png"
    ob.save(opath)
    row = fit_case("occl_base", opath)
    row["pass"] = bool(row["occl"] == 1 and row["prims"] <= 14 and row["raster_iou"] >= 0.97)
    out["occlusion_complete"] = row
    lc = Image.new("RGB", (420, 300), (255, 255, 255))
    ld = ImageDraw.Draw(lc)
    ld.polygon([(40, 40), (200, 40), (200, 150), (120, 150), (120, 260), (40, 260)], fill=(20, 110, 60))
    ld.rectangle((210, 40, 380, 260), fill=(160, 40, 40))
    lpath = WORK / "lshape_ctrl.png"
    lc.save(lpath)
    row = fit_case("lshape_ctrl", lpath)
    row["pass"] = bool(row["prims"] <= 12 and row["occl"] == 0)
    out["lshape_no_complete"] = row

    # audit P2 symmetry: a mirror-symmetric shield must stay (exactly) symmetric
    sh = Image.new("RGB", (400, 420), (255, 255, 255))
    sd = ImageDraw.Draw(sh)
    sd.polygon([(200, 40), (340, 90), (340, 240), (200, 390), (60, 240), (60, 90)],
               fill=(30, 60, 140))
    spath2 = WORK / "shield_sym.png"
    sh.save(spath2)
    row = fit_case("shield_sym", spath2)
    reb = np.asarray(Image.open(WORK / "shield_sym_paper/shield_sym/03_rebuilt_filled.png").convert("RGB"), int)
    inked = np.sum(np.abs(reb - [255, 255, 255]), axis=2) > 90
    ys2, xs2 = np.nonzero(inked)
    if len(xs2):
        cx2 = int(round((xs2.min() + xs2.max()) / 2))
        w2 = min(cx2, inked.shape[1] - 1 - cx2)
        left = inked[:, cx2 - w2:cx2 + 1]
        right = inked[:, cx2:cx2 + w2 + 1][:, ::-1]
        inter = int(np.sum(left & right))
        union = int(np.sum(left | right))
        row["mirror_iou"] = round(inter / union, 4) if union else 1.0
    else:
        row["mirror_iou"] = 0.0
    row["pass"] = bool(row["prims"] <= 12 and row["mirror_iou"] >= 0.98)
    out["shield_symmetry"] = row

    ring = Image.new("RGB", (360, 360), (255, 255, 255))
    rd = ImageDraw.Draw(ring)
    rd.ellipse((40, 40, 320, 320), fill=(30, 90, 160))
    rd.ellipse((70, 70, 290, 290), fill=(255, 255, 255))
    rpath = WORK / "ring_stroke.png"
    ring.save(rpath)
    row = fit_case("ring_stroke", rpath)
    row["pass"] = bool(row["strokes"] == 1 and row["prims"] <= 8)
    out["ring_stroke"] = row
    donut = Image.new("RGB", (360, 360), (255, 255, 255))
    dd = ImageDraw.Draw(donut)
    dd.ellipse((40, 40, 320, 320), fill=(160, 60, 30))
    dd.ellipse((120, 70, 300, 250), fill=(255, 255, 255))
    dpath = WORK / "donut_uneven.png"
    donut.save(dpath)
    row = fit_case("donut_uneven", dpath)
    row["pass"] = bool(row["strokes"] == 0)
    out["donut_no_stroke"] = row

    flag = Image.new("RGB", (450, 300), (255, 255, 255))
    fd = ImageDraw.Draw(flag)
    fd.rectangle((30, 30, 420, 110), fill=(20, 60, 170))
    fd.rectangle((30, 110, 420, 190), fill=(245, 245, 245))
    fd.rectangle((30, 190, 420, 270), fill=(200, 30, 40))
    fpath = WORK / "flag_control.png"
    flag.save(fpath)
    row = fit_case("flag_control", fpath)
    row["pass"] = bool(row["regions"] == 2 and row["prims"] <= 10)   # white stripe = background
    out["flag_no_merge"] = row

    # resolution stability (audit): the same art at two working resolutions must
    # produce commensurate corner sets — a blow-up/collapse across scales is a
    # detector or removal regression even when each single scale looks fine.
    bs = Path(r"C:/Users/nirrt/Toolset/v-ice pictures/ground truth/Default/betsoft.svg")
    if bs.exists():
        def count_corners(res: int) -> int:
            n = 0
            for m, _ in svg_region_masks(bs, target=res):
                for lp in mask_loops(m):
                    lp = lp.astype(float)
                    if len(lp) > 1 and np.allclose(lp[0], lp[-1]):
                        lp = lp[:-1]
                    if len(lp) >= 8:
                        n += len(gv.paper_corner_positions(_to_ccw(lp)))
            return n
        c200, c380 = count_corners(200), count_corners(380)
        ratio = c380 / max(1, c200)
        out["res_stability_betsoft"] = {"corners_200": c200, "corners_380": c380,
                                        "ratio": round(ratio, 2),
                                        "pass": bool(0.65 <= ratio <= 1.5)}
    return out


# --------------------------------------------------------------------------- 4) problem cases
def problem_cases() -> dict:
    out = {}
    # IoU bars are baseline-minus-margin per case: thin wordmarks/small icons have
    # physically low fill-IoU ceilings (boundary band dominates the area).
    # (name, src, mode, min_iou, max_fallback_loops).  IoU bars sit just under the
    # measured healthy baseline: for 2-3px wordmark strokes the fill-IoU ceiling is
    # ~0.71 even on a visually perfect fit (AA edge pixels dominate) — the CIRCLE
    # CATASTROPHE is caught by the per-loop validator, not by this coarse floor.
    # A few loop fallbacks on noisy JPEG scribbles are accuracy-first BY DESIGN;
    # the gate exists to catch fallback EXPLOSIONS.
    cases = [
        ("114_bank", PROBLEM / "114_icon_group_4_80_src.png", "paper", 0.68, 1),
        ("ikea_jpeg", UPLOADS / "ikea_test.jpg", "paper", 0.93, 1),
        ("lacoste", UPLOADS / "117_icon_group_6_src.png", "paper", 0.92, 1),
        ("penspiral", UPLOADS / "penspiral_in.jpg", "paper", 0.92, 4),
        ("lion", UPLOADS / "49_icon_group_4_21_src.png", "paper", 0.88, 1),
        ("mastercard", UPLOADS / "52_icon_group_4_24_src.png", "paper", 0.90, 1),
        # User-reported 2026-07-11 regressions in the shared-region mode.  Keep
        # these separate from the older paper-mode cases: §7 can fail while the
        # independent-loop fitter remains healthy.
        ("ikea_regions", UPLOADS / "ikea_test.jpg", "paper-regions", 0.94, 0),
        ("penspiral_regions", UPLOADS / "120_penspiral_in_src.png", "paper-regions", 0.94, 1),
        ("mastercard_wordmark_regions", UPLOADS / "13_icon_group_1_src.png", "paper-regions", 0.97, 0),
        ("lacoste_regions", UPLOADS / "117_icon_group_6_src.png", "paper-regions", 0.93, 0),
        # Screenshot audit 2026-07-11: fan tips / wordmark joins in NBC and
        # circular counters / stem joins in Mobil.  They are deliberately kept
        # even when the hybrid router selects isolated loops: the requested
        # UI mode is still paper-regions and a future routing change must not
        # silently bring either defect back.
        ("nbc_regions", UPLOADS / "22_icon_group_3_src.png", "paper-regions", 0.93, 0),
        ("mobil_regions", UPLOADS / "20_icon_group_2_5_src.png", "paper-regions", 0.95, 0),
    ]
    if FAST:
        cases = cases[:3]
    # Editable-SVG quality gates for simple artwork where genuine sub-pixel
    # primitives do not exist.  Lacoste is intentionally omitted: its many
    # raster-sized scales are real details and need a region-aware counter.
    micro_limits = {
        "mastercard_wordmark_regions": ("upper_micro_prims", 2),
        # These eight subpixel segments are the pixel-faithful multi-colour
        # centre junction.  RDP reduced them to three but regressed tiny-colour
        # fidelity from 0.4225 to 0.3772, so preserving them is intentional.
        "nbc_regions": ("micro_prims", 8),
        "mobil_regions": ("micro_prims", 1),
    }
    for name, src, mode, min_iou, max_fb in cases:
        if not src.exists():
            out[name] = {"pass": None, "note": "source missing"}
            continue
        row = fit_case(name, src, smoothing=mode)
        metric, limit = micro_limits.get(name, ("micro_prims", float("inf")))
        micro_ok = row[metric] <= limit
        if name in micro_limits:
            row["micro_gate"] = f"{metric}<={limit}"
        tiny_floor = 0.40 if name == "nbc_regions" else 0.45
        row["pass"] = bool(row["raster_iou"] >= min_iou
                           and row["fallback_loops"] <= max_fb
                           and row["topo_ok"]
                           and row["tiny_detail"] >= tiny_floor
                           and micro_ok)
        out[name] = row
    return out


def main() -> None:
    t0 = time.time()
    snap = {
        "synthetic": synth_cases(),
        "corners_vs_human": corner_cases(),
        "icons": icon_cases(),
        "problems": problem_cases(),
    }
    snap["total_secs"] = round(time.time() - t0, 1)

    prev_path = OUT / "stage_snapshot.json"
    if prev_path.exists():
        (OUT / "stage_snapshot_prev.json").write_text(prev_path.read_text(encoding="utf-8"), encoding="utf-8")
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
    else:
        prev = None
    prev_path.write_text(json.dumps(snap, indent=1, ensure_ascii=False), encoding="utf-8")

    fails = []

    def emit(section: str, rows: dict) -> None:
        for name, row in rows.items():
            if not isinstance(row, dict) or "pass" not in row:
                continue
            status = {True: "PASS", False: "FAIL", None: "SKIP"}[row["pass"]]
            if row["pass"] is False:
                fails.append(f"{section}/{name}")
            detail = {k: v for k, v in row.items() if k not in ("pass", "per_logo")}
            print(f"{status:4s} {section:9s} {name:22s} {detail}")

    emit("synth", snap["synthetic"])
    print(f"{'PASS' if snap['corners_vs_human']['pass'] else 'FAIL':4s} corners   "
          f"held-subset            P={snap['corners_vs_human']['P']} R={snap['corners_vs_human']['R']} "
          f"F1={snap['corners_vs_human']['F1']} (n={snap['corners_vs_human']['n_logos']})")
    if not snap["corners_vs_human"]["pass"]:
        fails.append("corners")
    emit("icons", snap["icons"])
    emit("problems", snap["problems"])

    if prev is not None:
        try:
            d_f1 = snap["corners_vs_human"]["F1"] - prev["corners_vs_human"]["F1"]
            print(f"\ndelta vs previous snapshot: corners F1 {d_f1:+.3f}")
        except Exception:
            pass
    print(f"\n{'ALL GREEN' if not fails else 'FAILURES: ' + ', '.join(fails)}  ({snap['total_secs']}s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

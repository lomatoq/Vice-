"""Hunt #2b: machine search v2 — kink-aware objective, multi-res spotify.

v1 (81 configs) optimised event-F1 alone and closed at superset 0.20 /
cap 0.8; the blind pack then confirmed KINKS as the #1 systematic loss and
the production gate exposed 2 cap corners on the 380px spotify waves that
v1's single-loop probe never saw.  v2 therefore:

  objective   = F1 - 0.02 * p95(kink_energy over the same val fits)
                (signed: config F1 spread is ~0.02 wide, kink p95 spread is
                 ~2-8 /100px — one kink/100px trades as 0.02 F1)
  constraints = star {L:10..12, C<=4}, lshape {L==6, C==0},
                spotify PRODUCTION corners at 380 == 0  (the open target),
                spotify-711 kinks <= 2 (v1's guarantee kept)
  knobs       = cap {0.5, 0.65, 0.8}, superset {0.20, 0.25},
                G1 weight {6, 8, 10}  (floor/slope frozen at 2.2/5.0 — v1
                showed F1 flat across them)

Resumable via benchmarks/price_search_v2.jsonl.  Winner promotion stays a
separate gated commit.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import numpy as np

OUT = ROOT / "benchmarks" / "price_search_v2.jsonl"

GRID = {
    "cap": [0.5, 0.65, 0.8],
    "superset": [0.20, 0.25],
    "g1w": [6.0, 8.0, 10.0],
}
FLOOR, SLOPE = 2.2, 5.0


def apply_config(gv, cfg: dict) -> None:
    gv._corner_price = lambda p: max(FLOOR, 1.0 + SLOPE * (1.0 - float(np.clip(p, 0.0, 1.0))))
    gv._JOINT_SUPERSET_THRESHOLD = cfg["superset"]
    gv._JOINT_CAP_PRICE = cfg["cap"]
    gv._PAPER_G1_W = cfg["g1w"]


def loop_kinks(gv, fl) -> int:
    if fl is None or len(fl.curves) < 2:
        return 0
    k = 0
    for i in range(len(fl.curves)):
        ta = gv._tangent_out(fl.curves[i])
        tb = gv._tangent_in(fl.curves[(i + 1) % len(fl.curves)])
        if float(np.degrees(np.arccos(np.clip(float(ta @ tb), -1, 1)))) > 12.0:
            k += 1
    return k


def probes(gv) -> dict:
    from PIL import Image, ImageDraw
    from vectorize_papers import mask_loops
    out = {}
    img = Image.new("RGB", (900, 900), "white")
    d = ImageDraw.Draw(img)
    d.polygon([(450 + (320 if k % 2 == 0 else 140) * math.cos(-math.pi / 2 + k * math.pi / 5),
                450 + (320 if k % 2 == 0 else 140) * math.sin(-math.pi / 2 + k * math.pi / 5))
               for k in range(10)], fill=(30, 60, 150))
    a = np.array(img.convert("L")) < 128
    loop = max(mask_loops(a.astype(np.uint8)), key=len).astype(float)
    fl = gv._fit_loop_joint(loop, 32.0 / 900.0, 1.0)
    kinds = {}
    for c in (fl.curves if fl else []):
        kinds[c.degree] = kinds.get(c.degree, 0) + 1
    out["star_L"] = kinds.get(1, 0)
    out["star_C"] = kinds.get(3, 0) + kinds.get(2, 0)

    img2 = Image.new("RGB", (900, 900), "white")
    d2 = ImageDraw.Draw(img2)
    d2.polygon([(100, 100), (700, 100), (700, 400), (450, 400), (450, 750), (100, 750)],
               fill=(30, 60, 150))
    a2 = np.array(img2.convert("L")) < 128
    loop2 = max(mask_loops(a2.astype(np.uint8)), key=len).astype(float)
    fl2 = gv._fit_loop_joint(loop2, 32.0 / 900.0, 1.0)
    kinds2 = {}
    for c in (fl2.curves if fl2 else []):
        kinds2[c.degree] = kinds2.get(c.degree, 0) + 1
    out["lshape_L"] = kinds2.get(1, 0)
    out["lshape_C"] = kinds2.get(3, 0) + kinds2.get(2, 0)

    # spotify multi-res: PRODUCTION corners (joint with classic fallback),
    # all loops — this is exactly what benchmark_stages gates at 380.
    from svg_corners import svg_region_masks
    from eval_joint_corners import joint_corner_positions
    probe = Path(r"C:/Users/nirrt/Toolset/v-ize train/dataset/icons/iconify/logos/spotify-icon.svg")
    out["spotify380_prod"] = -1
    out["spotify_kinks"] = -1
    if probe.is_file():
        n380 = 0
        for mask, _ in svg_region_masks(probe, target=380):
            for lp in mask_loops(mask):
                lp = lp.astype(float)
                if len(lp) == 711:              # v1's probe loop: BEFORE trim
                    fl3 = gv._fit_loop_joint(np.asarray(lp, float), 32.0 / 380.0, 1.0)
                    out["spotify_kinks"] = loop_kinks(gv, fl3)
                if len(lp) > 1 and np.allclose(lp[0], lp[-1]):
                    lp = lp[:-1]
                if len(lp) < 8:
                    continue
                sa = float(np.sum(lp[:, 0] * np.roll(lp[:, 1], -1) - np.roll(lp[:, 0], -1) * lp[:, 1]))
                if sa < 0:
                    lp = lp[::-1]
                pred = joint_corner_positions(lp)
                n380 += len(pred) if pred is not None else len(gv.paper_corner_positions(lp))
        out["spotify380_prod"] = n380
    return out


def f1_and_kinks(gv, limit: int = 250, tolerance: float = 3.0) -> tuple[float, float]:
    from svg_corner_gt import iter_shard_examples
    from eval_joint_corners import joint_corner_positions
    dataset = ROOT / "datasets" / "corner_gt_v4_perceptual_events"
    tp = fp = fn = 0
    seen = 0
    kink_rates: list[float] = []
    for points, labels, meta in iter_shard_examples(dataset, {"val"}):
        if seen >= limit:
            break
        loop = np.asarray(points, float)
        event_ids = np.asarray(meta["event_ids"])
        if len(loop) < 24:
            continue
        seen += 1
        pred = joint_corner_positions(loop)
        if pred is None:
            positions = gv.paper_corner_positions(loop)
            pred = np.asarray(positions, float) if len(positions) else np.empty((0, 2))
        else:
            # kink rate on the SAME fit the production path would ship
            fl = gv._fit_loop_joint(loop, 32.0 / max(16.0, float(np.ptp(loop[:, 0]) + np.ptp(loop[:, 1])) / 2), 1.0)
            if fl is not None:
                per = float(np.sum([np.linalg.norm(np.diff(gv.eval_curve(c, 8), axis=0), axis=1).sum()
                                    for c in fl.curves]))
                kink_rates.append(100.0 * loop_kinks(gv, fl) / max(1.0, per))
        events = []
        for eid in np.unique(event_ids):
            if eid < 0:
                continue
            events.append(loop[event_ids == eid].mean(axis=0))
        events = np.asarray(events, float) if events else np.empty((0, 2))
        m_e, m_p = set(), set()
        if len(pred) and len(events):
            dmat = np.linalg.norm(pred[:, None, :] - events[None, :, :], axis=2)
            order = np.dstack(np.unravel_index(np.argsort(dmat, axis=None), dmat.shape))[0]
            for pi, ei in order:
                if dmat[pi, ei] > tolerance:
                    break
                if pi in m_p or ei in m_e:
                    continue
                m_p.add(int(pi))
                m_e.add(int(ei))
        tp += len(m_e)
        fp += len(pred) - len(m_p)
        fn += len(events) - len(m_e)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    p95 = float(np.percentile(kink_rates, 95)) if kink_rates else 0.0
    return f1, p95


def main() -> int:
    import geometry_vectorizer as gv
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.dumps(json.loads(line)["config"], sort_keys=True))
            except Exception:
                continue
    keys = list(GRID)
    combos = list(itertools.product(*(GRID[k] for k in keys)))
    print(f"{len(combos)} configs, {len(done)} already done")
    best = None
    for combo in combos:
        cfg = dict(zip(keys, combo))
        key = json.dumps(cfg, sort_keys=True)
        if key in done:
            continue
        apply_config(gv, cfg)
        try:
            pr = probes(gv)
            # spotify380_prod stays OBSERVATIONAL: the first sweep showed 2 cap
            # corners at EVERY (cap, superset, g1w) in range — these knobs do
            # not reach them; closing that is a separate mechanism hunt.
            ok = (10 <= pr["star_L"] <= 12 and pr["star_C"] <= 4
                  and pr["lshape_L"] == 6 and pr["lshape_C"] == 0
                  and 0 <= pr["spotify_kinks"] <= 2)
            f1, p95 = f1_and_kinks(gv) if ok else (0.0, 99.0)
        except Exception as exc:
            pr = {"error": str(exc)[:120]}
            ok, f1, p95 = False, 0.0, 99.0
        score = f1 - 0.02 * p95 if ok else -99.0
        rec = {"config": cfg, "probes": pr, "constraints_ok": ok,
               "f1": round(f1, 4), "kink_p95": round(p95, 3), "score": round(score, 4)}
        with OUT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(rec, flush=True)
        if ok and (best is None or score > best[0]):
            best = (score, cfg)
    print("BEST:", best)
    return 0


if __name__ == "__main__":
    sys.exit(main())

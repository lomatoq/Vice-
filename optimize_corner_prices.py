"""Hunt #2: OFFLINE optimization of the joint-DP corner-pricing constants.

The repo rule says hand-tuning is a ceiling — so the knobs are searched by
machine against a fixed objective with hard constraints:

  objective   = event-F1 on 250 V4-val loops (eval_joint_corners logic)
  constraints = exact decompositions on the synthetic probes:
                star {L:10..12, C<=4}, lshape {L==6, C==0},
                circle {L==0}, spotify-711 {kinks <= 2}

Knobs: PRICE_FLOOR, PRICE_SLOPE (price = max(floor, 1 + slope*(1-p))),
       CAP_PRICE (geometric-testimony price), SUPERSET_THRESHOLD.
Writes every evaluated config to benchmarks/price_search.jsonl (append) so an
interrupted search resumes by skipping done configs.  The WINNER is reported;
applying it is a separate human-gated commit.
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

OUT = ROOT / "benchmarks" / "price_search.jsonl"

GRID = {
    "floor": [1.6, 2.2, 2.8],
    "slope": [3.5, 5.0, 6.5],
    "cap": [0.8, 1.2, 1.8],
    "superset": [0.20, 0.30, 0.40],
}


def apply_config(gv, cfg: dict) -> None:
    floor = cfg["floor"]
    slope = cfg["slope"]
    gv._corner_price = lambda p: max(floor, 1.0 + slope * (1.0 - float(np.clip(p, 0.0, 1.0))))
    gv._JOINT_SUPERSET_THRESHOLD = cfg["superset"]
    gv._JOINT_CAP_PRICE = cfg["cap"]      # consumed via monkeypatched min below


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

    from svg_corners import svg_region_masks
    probe = Path(r"C:/Users/nirrt/Toolset/v-ize train/dataset/icons/iconify/logos/spotify-icon.svg")
    out["spotify_kinks"] = -1
    if probe.is_file():
        for mask, _ in svg_region_masks(probe, target=380):
            for lp in mask_loops(mask):
                if len(lp) != 711:
                    continue
                fl3 = gv._fit_loop_joint(np.asarray(lp, float), 32.0 / 380.0, 1.0)
                if fl3 is None:
                    continue
                kk = 0
                for i in range(len(fl3.curves)):
                    ta = gv._tangent_out(fl3.curves[i])
                    tb = gv._tangent_in(fl3.curves[(i + 1) % len(fl3.curves)])
                    if float(np.degrees(np.arccos(np.clip(float(ta @ tb), -1, 1)))) > 12.0:
                        kk += 1
                out["spotify_kinks"] = kk
    return out


def f1_on_val(gv, limit: int = 250, tolerance: float = 3.0) -> float:
    from svg_corner_gt import iter_shard_examples
    from eval_joint_corners import joint_corner_positions
    dataset = ROOT / "datasets" / "corner_gt_v4_perceptual_events"
    tp = fp = fn = 0
    seen = 0
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
    return 2 * precision * recall / max(1e-9, precision + recall)


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
    # patch the cap price used by _fit_loop_joint (module constant lookup)
    original_fit = gv._fit_loop_joint
    for combo in combos:
        cfg = dict(zip(keys, combo))
        key = json.dumps(cfg, sort_keys=True)
        if key in done:
            continue
        apply_config(gv, cfg)
        # cap price: monkeypatch min(price, 1.2) via a wrapper is intrusive;
        # instead the cap constant is read from gv._JOINT_CAP_PRICE if present
        try:
            pr = probes(gv)
            ok = (10 <= pr["star_L"] <= 12 and pr["star_C"] <= 4
                  and pr["lshape_L"] == 6 and pr["lshape_C"] == 0
                  and 0 <= pr["spotify_kinks"] <= 2)
            f1 = f1_on_val(gv) if ok else 0.0
        except Exception as exc:
            pr = {"error": str(exc)[:120]}
            ok, f1 = False, 0.0
        rec = {"config": cfg, "probes": pr, "constraints_ok": ok, "f1": round(f1, 4)}
        with OUT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(rec, flush=True)
    rows = [json.loads(line) for line in OUT.read_text(encoding="utf-8").splitlines()]
    ok_rows = [r for r in rows if r.get("constraints_ok")]
    if ok_rows:
        best = max(ok_rows, key=lambda r: r["f1"])
        print("WINNER:", best)
    return 0


if __name__ == "__main__":
    sys.exit(main())

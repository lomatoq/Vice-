"""D2 step 1: re-quantise the paper's 157 training pairs into OUR pipeline's
conditions, so the corner RF learns the staircases it will actually see.

Per pair (boundary Nx2, corners.1 indices), three derived domains:
  native  - rasterise the polygon (cv2.fillPoly, 1px grid, 8x subpixel shift)
            and re-trace with OUR mask_loops -> our cell-edge staircase
            (integer lattice, axis-aligned 1px steps; the paper's marching
            squares emits edge-midpoint vertices instead - different
            quantisation, which is exactly the domain gap D2 measured).
  q30     - the same mask through PNG->JPEG q30->binarise 128: JPEG block
            shift + ringing, our degraded-input domain.
  db4     - production deblur path: grayscale mask -> resize 4x LANCZOS ->
            binarise 0.5 -> mask_loops on the 4x lattice (coords stay in 4x
            units, matching analysis_scale=4).  Only from res 32: the span
            becomes 128 == the largest model bucket; 64/128 sources would
            give spans 256/512 that have no bucket and would dilute it.

Corner labels transfer to the nearest new vertex.  Tolerance is a LATTICE
property, not a resolution fraction: measured miss distribution (diag
2026-07-15) has its bulk at 0.71px (half-pixel diagonal) plus a second
cluster at 1.5-3.0px = acute tips rounded by the staircase, max 4.12px.
Blunted tips MUST stay labelled (nearest staircase vertex IS the blunted
apex) or the model learns to miss exactly the production tip failures; so
tol 3.5px at res 32 (a wrong-feature match risk cap on a 32px glyph) and
4.5px at >=64, same in source px for q30/db4.  Drops are recorded in the
manifest - a high rate flags a broken variant, not a tuning knob.

Output: datasets/retrain_step1/<domain>/<shape>__<idx>/<bucket>_boundary.txt
        + _corners.1.txt (one index per line), manifest.json with per-entry
        provenance, and a PIL QC sheet benchmarks/retrain_step1_qc.png.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from vectorize_papers import mask_loops, signed_area  # noqa: E402
from retrain_corner_rf import DATA, load_pairs  # noqa: E402

OUT = ROOT / "datasets" / "retrain_step1"
QC_PNG = ROOT / "benchmarks" / "retrain_step1_qc.png"


def rasterize(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Raster faithful to the corpus convention.  The released boundaries are
    unit-step chains THROUGH PIXEL CENTRES of the boundary pixels, so the
    original raster = interior pixels + the boundary pixels themselves.
    Plain fillPoly reproduces exactly that (it fills the interior AND draws
    the outline, i.e. centre-on-polygon is included).  Area evidence at res
    32: polygon-area ratio of the true raster ~= 1 + perim/(2*area) ~= 1.13;
    plain fillPoly measures 1.167, while an 8x-supersampled centre-in-polygon
    raster (step-1 v1) measures 1.055 - HALF A PIXEL THINNER all around,
    which shifted every staircase and poisoned v1 training (uniform F1 drop
    at res 64 on every domain)."""
    shift = 4.0 - np.floor(pts.min(axis=0))
    p = pts + shift
    h = int(np.ceil(p[:, 1].max())) + 5
    w = int(np.ceil(p[:, 0].max())) + 5
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [np.round(p * 8).astype(np.int32)], 1, shift=3)
    return mask.astype(bool), shift


def biggest_loop(mask: np.ndarray) -> np.ndarray | None:
    loops = mask_loops(mask)
    if not loops:
        return None
    loop = max(loops, key=lambda l: abs(signed_area(l)))
    if len(loop) < 9:
        return None
    return loop[:-1].copy()  # drop the closing duplicate vertex


def transfer_labels(new_pts: np.ndarray, gt_corners: np.ndarray,
                    tol: float) -> tuple[np.ndarray, int]:
    """Label transfer to the TURNING APEX among vertices within tol.

    v1 used the euclidean-nearest vertex, which on a staircase is often the
    step NEIGHBOUR of the true apex (a half-pixel diagonal decides); the
    stencil then learns displaced targets - one of the two v1 poisons.
    The apex choice mirrors production _recenter_corners: strongest local
    turn wins, distance only breaks ties."""
    if len(gt_corners) == 0:
        return np.empty(0, dtype=int), 0
    n = len(new_pts)
    w = 3
    va = new_pts - np.roll(new_pts, w, axis=0)
    vb = np.roll(new_pts, -w, axis=0) - new_pts
    na = np.linalg.norm(va, axis=1)
    nb = np.linalg.norm(vb, axis=1)
    cosang = np.clip(np.sum(va * vb, axis=1) / np.maximum(na * nb, 1e-9), -1.0, 1.0)
    turn = np.degrees(np.arccos(cosang))
    tree = cKDTree(new_pts)
    # Injective assignment: two GT corners must not collapse onto one apex
    # (a short serif has TWO corners 3px apart - unique() would merge them
    # and silently delete ~20% of labels, measured).  Strongest-turn corner
    # claims its apex first; a taken vertex yields the next-best candidate.
    balls = []
    for gi, g in enumerate(gt_corners):
        cand = tree.query_ball_point(g, tol)
        if not cand:
            balls.append((gi, []))
            continue
        d = np.linalg.norm(new_pts[np.asarray(cand)] - g, axis=1)
        ranked = sorted(range(len(cand)),
                        key=lambda i: (-turn[cand[i]], float(d[i])))
        balls.append((gi, [(int(cand[i]), float(turn[cand[i]])) for i in ranked]))
    order = sorted(range(len(balls)),
                   key=lambda j: -(balls[j][1][0][1] if balls[j][1] else -1.0))
    used: set[int] = set()
    chosen: list[int] = []
    dropped = 0
    for j in order:
        _, ranked = balls[j]
        pick = next((v for v, _ in ranked if v not in used), None)
        if pick is None:
            dropped += 1
            continue
        used.add(pick)
        chosen.append(pick)
    return (np.asarray(sorted(chosen), dtype=int) if chosen else np.empty(0, int)), dropped


def save_pair(dirpath: Path, bucket: int, pts: np.ndarray, corner_idx: np.ndarray) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    np.savetxt(dirpath / f"{bucket}_boundary.txt", pts, fmt="%.4f")
    (dirpath / f"{bucket}_corners.1.txt").write_text(
        "\n".join(str(int(i)) for i in corner_idx), encoding="utf-8")


def main() -> int:
    manifest: list[dict] = []
    skipped: list[dict] = []
    qc_tiles: list[tuple[str, np.ndarray, np.ndarray]] = []
    for res in (32, 64, 128):
        pairs = load_pairs(res)
        for i, (name, shape, pts, labels) in enumerate(pairs):
            gt = pts[labels == 1]
            mask, shift = rasterize(pts)
            tol = 3.5 if res == 32 else 4.5
            variants: list[tuple[str, np.ndarray | None, np.ndarray, float, int]] = []

            # native: our staircase of the clean raster
            variants.append(("native", biggest_loop(mask), gt + shift, tol, res))

            # q30: JPEG round-trip of the mask
            ok, buf = cv2.imencode(".jpg", (mask * 255).astype(np.uint8),
                                   [cv2.IMWRITE_JPEG_QUALITY, 30])
            if ok:
                dec = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
                mq = dec >= 128
                variants.append(("q30", biggest_loop(mq) if mq.any() else None,
                                 gt + shift, tol, res))

            # db4: LANCZOS 4x + threshold 0.5, coords on the 4x lattice
            if res == 32:
                up = cv2.resize((mask * 255).astype(np.float32), None, fx=4, fy=4,
                                interpolation=cv2.INTER_LANCZOS4)
                m4 = up >= 127.5
                variants.append(("db4", biggest_loop(m4) if m4.any() else None,
                                 (gt + shift) * 4.0, tol * 4.0, 128))

            for domain, loop, gt_t, tol, bucket in variants:
                if loop is None:
                    skipped.append({"name": name, "domain": domain, "res": res})
                    continue
                cidx, dropped = transfer_labels(loop, gt_t, tol)
                dirpath = OUT / domain / f"{shape}__{res}_{i:03d}"
                save_pair(dirpath, bucket, loop, cidx)
                manifest.append({
                    "base": shape, "domain": domain, "src_res": res,
                    "res": bucket, "dir": str(dirpath.relative_to(OUT)),
                    "n_pts": int(len(loop)), "n_corners": int(len(cidx)),
                    "n_gt": int(len(gt_t)), "dropped": dropped})
                if shape in ("axe", "key", "whale") and res == 64:
                    qc_tiles.append((f"{shape}/{domain}", loop, loop[cidx]))
            if shape in ("axe", "key", "whale") and res == 64:
                qc_tiles.append((f"{shape}/orig", pts + shift, gt + shift))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(
        json.dumps({"entries": manifest, "skipped": skipped}, indent=1),
        encoding="utf-8")

    # QC sheet: polyline + corner dots, one tile per (shape, domain)
    from PIL import Image, ImageDraw
    tile = 220
    if qc_tiles:
        cols = 4
        rows = (len(qc_tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tile, rows * tile), "white")
        drw = ImageDraw.Draw(sheet)
        for k, (title, poly, cpts) in enumerate(qc_tiles):
            ox, oy = (k % cols) * tile, (k // cols) * tile
            lo, hi = poly.min(axis=0), poly.max(axis=0)
            s = (tile - 40) / max(1.0, float((hi - lo).max()))
            def tx(p):
                return (ox + 20 + (p[0] - lo[0]) * s, oy + 20 + (p[1] - lo[1]) * s)
            drw.line([tx(p) for p in np.vstack([poly, poly[:1]])], fill=(60, 60, 200), width=1)
            for c in cpts:
                x, y = tx(c)
                drw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(220, 30, 30))
            drw.text((ox + 6, oy + 4), title, fill=(0, 0, 0))
        QC_PNG.parent.mkdir(exist_ok=True)
        sheet.save(QC_PNG)

    # summary to stdout
    per = {}
    for e in manifest:
        key = (e["domain"], e["src_res"])
        d = per.setdefault(key, {"n": 0, "gt": 0, "kept": 0, "drop": 0, "pts": 0, "src_pts": 0})
        d["n"] += 1
        d["gt"] += e["n_gt"]
        d["kept"] += e["n_corners"]
        d["drop"] += e["dropped"]
        d["pts"] += e["n_pts"]
    for (dom, res), d in sorted(per.items()):
        print(f"{dom:7s} res {res:3d}: pairs {d['n']:3d}  gt {d['gt']:4d} kept {d['kept']:4d} "
              f"dropped {d['drop']:3d} ({100.0 * d['drop'] / max(1, d['gt']):.1f}%)  "
              f"mean pts {d['pts'] / max(1, d['n']):.0f}")
    print(f"skipped variants: {len(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

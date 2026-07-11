"""Export OUR human corner annotations into the Hoshyari paper's exact dataset format, so they
can (a) be added to the paper's training set as first-class per-resolution examples with ZERO
snap error (corner = vertex INDEX on that resolution's boundary), and (b) be reviewed/fixed in
the paper's own label_ui.py (which saves to _corners.2.txt and never overwrites ours).

Layout (sibling of the paper's decent-res, never touching their files):
  C:/Users/nirrt/Toolset/Paper_training/ours-decent-res/<stem>__r<i>_l<j>/
      {res}_boundary.txt   ordered boundary points of one loop (paper convention: x y per line)
      {res}_corners.1.txt  0-based vertex indices of the corners on that boundary
      {res}_image.png      the region mask raster (for reference, like the paper)

Corners are cleaned per-loop exactly like training (_clean_corners_on_loop: re-centred onto the
local turning maximum, soft <40deg dropped), so the exported labels match the paper's annotation
statistics (median turn ~90deg, corners on turning maxima).

Usage:
  C:/Python312/python.exe export_to_paper_format.py --stems 4theplayer,1spin4win
  C:/Python312/python.exe export_to_paper_format.py            (all new-format annotations)
"""
from __future__ import annotations
import argparse, json, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image
import corner_classifier as CC
from svg_corners import svg_region_masks

OUT_ROOT = Path(r"C:/Users/nirrt/Toolset/Paper_training/ours-decent-res")
RESOLUTIONS = (32, 64, 128, 256)
MIN_VERTS = 12


def export_logo(stem: str, rec: dict, resolutions=RESOLUTIONS) -> int:
    norm = np.asarray(rec["corners_norm"], float).reshape(-1, 2)
    written = 0
    for res in resolutions:
        try:
            regions = svg_region_masks(rec["file"], target=res)
        except Exception:
            continue
        for ri, (mask, _) in enumerate(regions):
            H, W = mask.shape
            corners = norm * [W, H] if len(norm) else norm
            for li, loop in enumerate(CC.mask_loops(mask)):
                if len(loop) > 1 and np.allclose(loop[0], loop[-1]):
                    loop = loop[:-1]
                lp = CC._to_ccw(loop.astype(np.float64))
                if len(lp) < MIN_VERTS:
                    continue
                clean = CC._clean_corners_on_loop(lp, corners) if len(corners) else corners
                # cleaned corners ARE loop vertices -> exact indices
                idx = sorted({int(np.argmin(np.linalg.norm(lp - c, axis=1))) for c in clean})
                d = OUT_ROOT / f"{stem}__r{ri}_l{li}"
                d.mkdir(parents=True, exist_ok=True)
                np.savetxt(d / f"{res}_boundary.txt", lp, fmt="%.1f")
                np.savetxt(d / f"{res}_corners.1.txt", np.asarray(idx, int), fmt="%d")
                Image.fromarray((mask.astype(np.uint8)) * 255).save(d / f"{res}_image.png")
                written += 1
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems", type=str, default="",
                    help="comma-separated logo stems to export (default: all new-format)")
    a = ap.parse_args()
    ann = json.loads(CC.HUMAN_ANN.read_text())
    stems = [s for s in a.stems.split(",") if s] or \
            [k for k, v in ann.items() if "corners_norm" in v and len(v["corners_norm"]) > 0]
    total = 0
    for stem in stems:
        rec = ann.get(stem)
        if not rec or "corners_norm" not in rec:
            print(f"skip {stem}: no new-format annotation")
            continue
        n = export_logo(stem, rec)
        total += n
        print(f"{stem}: {n} loop-res files")
    print(f"exported {total} boundary files -> {OUT_ROOT}")
    print("review any of them with the paper's UI, e.g.:")
    print(f'  cd "{OUT_ROOT}" && C:/Python312/python.exe "../decent-res/label_ui.py" <dir-name> 64 1')


if __name__ == "__main__":
    main()

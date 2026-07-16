"""One stress-bench run in a FRESH process (isolation discipline, see
eval_one_item.py): vectorise a DEGRADED raster, meter the result against
the CLEAN GT render.  stdout: one JSON line.

Usage: stress_one.py <degraded.png> <gt_render.png> <out_dir> <W>
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    degraded = Path(sys.argv[1])
    gt_png = Path(sys.argv[2])
    out_dir = Path(sys.argv[3])
    width = int(sys.argv[4])
    engine = sys.argv[5] if len(sys.argv) > 5 else "ours"

    import numpy as np
    import cv2
    import importlib.util
    spec = importlib.util.spec_from_file_location("bv", ROOT / "benchmark_vai.py")
    bv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bv)

    meters: dict = {}
    try:
        if engine == "vtracer":
            out_dir.mkdir(parents=True, exist_ok=True)
            svg = out_dir / f"{degraded.stem}__vtracer.svg"
            if not svg.exists():
                import vtracer
                vtracer.convert_image_to_svg_py(str(degraded), str(svg),
                                                colormode="color")
        else:
            import geometry_vectorizer as gv
            svg = out_dir / degraded.stem / "03_rebuilt_filled.svg"
            if not svg.exists():
                gv.process(degraded, out_dir, smoothing="paper-regions")
        # raster meters vs the CLEAN GT render (not the degraded input)
        meters.update(bv.raster_meters(svg, gt_png))
        ren = np.asarray(bv.render_svg(svg, width), float)
        from PIL import Image
        gt_img = np.asarray(Image.open(gt_png).convert("RGB"), float)
        if ren.shape != gt_img.shape:
            gt_img = np.asarray(Image.open(gt_png).convert("RGB").resize(
                (ren.shape[1], ren.shape[0])), float)
        bnd = bv.boundary_meters(ren, gt_img)
        meters.update(bnd if isinstance(bnd, dict) else {})
        # Euler deltas: components/holes of ink masks, ours vs GT
        def euler(arr):
            bg = np.median(np.vstack([arr[0], arr[-1], arr[:, 0], arr[:, -1]]), axis=0)
            ink = (np.sum(np.abs(arr - bg), axis=2) > 90).astype(np.uint8)
            n_comp, _ = cv2.connectedComponents(ink, connectivity=8)
            inv = (1 - ink)
            n_holes, _, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
            border_touch = 0
            for c in range(1, n_holes):
                x, y, w, h, a = stats[c]
                if x == 0 or y == 0 or x + w == ink.shape[1] or y + h == ink.shape[0]:
                    border_touch += 1
            return n_comp - 1, (n_holes - 1) - border_touch
        c_ours, h_ours = euler(ren)
        c_gt, h_gt = euler(gt_img)
        meters["comp_delta"] = int(c_ours - c_gt)
        meters["hole_delta"] = int(h_ours - h_gt)
    except Exception as exc:
        meters = {"error": f"{type(exc).__name__}: {exc}"[:300]}
    print(json.dumps(meters))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Loader for the Hoshyari et al. 2018 released training set (Paper_training/): real
human-annotated corner ground truth in the paper's own format.

decent-res/<name>/{res}_boundary.txt  : ordered pixel-corner points of the region boundary loop
decent-res/<name>/{res}_corners.1.txt : 0-based indices into the boundary marked as corners
small-res/{8,16}/shape<N>_boundary.txt + _corners.1.txt : same, for the 8x8 / 16x16 shapes

Each example is a closed boundary loop plus the xy of its human corners — exactly what the RF
featurizer (_labels) and the CNN (signal + _labels_for) consume, with ZERO snapping error since
the corner index already points at the true boundary vertex.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np

ROOT = Path(r"C:/Users/nirrt/Toolset/Paper_training")


def _load(boundary_path: Path, corners_path: Path):
    try:
        loop = np.loadtxt(boundary_path, dtype=float)
        # Empty corner files are intentional smooth negatives in the released set.
        idx = (np.atleast_1d(np.loadtxt(corners_path, dtype=int))
               if corners_path.stat().st_size else np.zeros(0, dtype=int))
    except Exception:
        return None
    if loop.ndim != 2 or loop.shape[1] != 2 or len(loop) < 12:
        return None
    idx = idx[(idx >= 0) & (idx < len(loop))]
    return loop, loop[idx] if len(idx) else np.zeros((0, 2))


def paper_examples(resolutions=(32, 64, 128, 256), include_small=True, root: Path = ROOT):
    """Yield (loop (N,2) float, corner_xy (K,2) float, res int, name str)."""
    out = []
    dec = root / "decent-res"
    if dec.is_dir():
        for md in sorted(p for p in dec.iterdir() if p.is_dir()):
            for res in resolutions:
                rec = _load(md / f"{res}_boundary.txt", md / f"{res}_corners.1.txt")
                if rec is not None:
                    out.append((rec[0], rec[1], res, md.name))
    if include_small:
        sr = root / "small-res"
        for res_dir in ("8", "16"):
            d = sr / res_dir
            if not d.is_dir():
                continue
            for bp in sorted(d.glob("*_boundary.txt")):
                cp = bp.with_name(bp.name.replace("_boundary.txt", "_corners.1.txt"))
                rec = _load(bp, cp)
                if rec is not None:
                    out.append((rec[0], rec[1], int(res_dir), f"{res_dir}/{bp.stem}"))
    return out


if __name__ == "__main__":
    ex = paper_examples()
    from collections import Counter
    byres = Counter(r for *_, r, _ in [(a, b, c, d) for a, b, c, d in ex])
    print(f"{len(ex)} paper examples")
    print("by resolution:", dict(sorted(Counter(e[2] for e in ex).items())))
    print("total corners:", sum(len(e[1]) for e in ex))
    print("sample:", ex[0][3], "loop", ex[0][0].shape, "corners", ex[0][1].shape)

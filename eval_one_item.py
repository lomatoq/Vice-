"""Fit + meters for ONE challenge item in a FRESH process.

Long-lived processes that interleave many fits and meters drift (found
2026-07-14: solo and pair runs are perfectly deterministic, an 8-item
chain reproducibly changes item043 kinks 1.76 -> 8.07 — in one chain the
FIT drifted, in another the METER did, while single-shot runs always
agree).  Until the root cause is caught, every multi-item harness runs
each item through this script; stdout is one JSON line.

Usage: eval_one_item.py <crop.png> <out_dir> <W> [mode]
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
    crop = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    width = int(sys.argv[3])
    mode = sys.argv[4] if len(sys.argv) > 4 else "paper-regions"

    import importlib.util
    spec = importlib.util.spec_from_file_location("bv", ROOT / "benchmark_vai.py")
    bv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bv)
    import geometry_vectorizer as gv

    meters: dict = {}
    svg = out_dir / crop.stem / "03_rebuilt_filled.svg"
    try:
        if not svg.exists():
            gv.process(crop, out_dir, smoothing=mode)
        meters.update(bv.geometry_meters(svg, width))
        meters.update(bv.roundness_meter(svg, width))
        meters.update(bv.raster_meters(svg, crop))
    except Exception as exc:
        meters["error"] = f"{type(exc).__name__}: {exc}"[:150]
    print(json.dumps(meters))
    return 0


if __name__ == "__main__":
    sys.exit(main())

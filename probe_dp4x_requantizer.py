"""N2 read-only instrumentation for the production deblur-4x corner path.

Runs the fixed challenge item057 crop through the real flagship route while
recording every ``_native_density_probabilities`` call.  This intentionally
duplicates the current requantizer only to expose its units and fallback path;
it does not alter production decisions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).parent
ITEM057 = Path(r"C:\Users\nirrt\Toolset\v-ice pictures\challenge_pack\eval\crops\item057.png")
OUT = ROOT / "benchmarks" / "probes" / "item057_dp4x"
MODE = "paper"  # direct production loop lane; region-graph wiring is an N4 fix


def _extent(loop: np.ndarray) -> float:
    return float((np.ptp(loop[:, 0]) + np.ptp(loop[:, 1])) / 2.0)


def _current_requantized_loop(loop: np.ndarray) -> tuple[np.ndarray | None, str]:
    """Mechanical copy of the pre-fix D3 geometry, with failure reasons."""
    try:
        shift = np.floor(loop.min(axis=0)) - 8.0
        pts = np.round(loop - shift).astype(np.int32)
        h = int(pts[:, 1].max()) + 9
        w = int(pts[:, 0].max()) + 9
        h4, w4 = ((h + 3) // 4) * 4, ((w + 3) // 4) * 4
        mask4 = np.zeros((h4, w4), np.uint8)
        cv2.fillPoly(mask4, [pts], 1)
        native = mask4.reshape(h4 // 4, 4, w4 // 4, 4).mean(axis=(1, 3)) >= 0.5
        if not native.any():
            return None, "empty-block-reduction"
        from vectorize_papers import mask_loops, signed_area
        loops = mask_loops(native)
        if not loops:
            return None, "no-retraced-loop"
        nat = max(loops, key=lambda lp: abs(signed_area(lp)))
        if len(nat) > 1 and np.allclose(nat[0], nat[-1]):
            nat = nat[:-1]
        if len(nat) < 24:
            return np.asarray(nat, float), "short-retrace"
        return np.asarray(nat, float), "requantized"
    except Exception as exc:  # diagnostic must report, not hide, failures
        return None, f"exception:{type(exc).__name__}"


def _corner_candidate_stats(probs: np.ndarray | None) -> dict:
    if probs is None or not len(probs):
        return {"max": None, "above_020": 0, "local_max_020": 0}
    probs = np.asarray(probs, float)
    above = probs >= 0.20
    maxima = above & (probs >= np.roll(probs, 1)) & (probs >= np.roll(probs, -1))
    return {"max": round(float(probs.max()), 5),
            "above_020": int(above.sum()), "local_max_020": int(maxima.sum())}


def main() -> int:
    if not ITEM057.is_file():
        raise FileNotFoundError(ITEM057)

    import geometry_vectorizer as gv

    original_native = gv._native_density_probabilities
    original_corner = gv._corner_probabilities
    records: list[dict] = []
    active: dict | None = None

    def corner_spy(loop: np.ndarray):
        if active is not None:
            active["probability_input_extents"].append(round(_extent(np.asarray(loop, float)), 4))
            active["probability_input_vertices"].append(int(len(loop)))
        return original_corner(loop)

    def native_spy(loop: np.ndarray, coarse: np.ndarray, lattice_scale: int = 1):
        nonlocal active
        if lattice_scale != 4:
            return original_native(loop, coarse, lattice_scale)
        nat, status = _current_requantized_loop(np.asarray(loop, float))
        loop_extent = _extent(loop)
        record = {
            "loop_vertices": int(len(loop)),
            "coarse_vertices": int(len(coarse)),
            "median_vertex_spacing_native_px": round(float(np.median(np.linalg.norm(
                np.roll(loop, -1, axis=0) - loop, axis=1))), 6),
            "loop_extent_native_px": round(loop_extent, 4),
            "coarse_extent_native_px": round(_extent(coarse), 4),
            "requant_status": status,
            "requant_vertices": None if nat is None else int(len(nat)),
            "requant_extent_px": None if nat is None else round(_extent(nat), 4),
            "requant_to_loop_extent_ratio": None if nat is None or loop_extent <= 0
                else round(_extent(nat) / loop_extent, 4),
            "probability_input_extents": [],
            "probability_input_vertices": [],
        }
        records.append(record)
        active = record
        try:
            result = original_native(loop, coarse, lattice_scale)
            record["result_vertices"] = None if result is None else int(len(result))
            record["fixed_candidate_stats"] = _corner_candidate_stats(result)
            # The legacy production branch on this item either classified the
            # quarter-sized retrace or fell back to coarse.  Reproduce that
            # classifier input to reveal whether a safe complexity key exists.
            legacy_input = nat if nat is not None and len(nat) >= 24 else np.asarray(coarse, float)
            legacy_probs = original_corner(np.asarray(legacy_input, float))
            if legacy_probs is not None and len(legacy_input) != len(coarse):
                from scipy.spatial import cKDTree
                shift = np.floor(loop.min(axis=0)) - 8.0
                legacy_world = np.asarray(legacy_input, float) * 4.0 + shift[None, :]
                _, legacy_indices = cKDTree(legacy_world).query(coarse)
                legacy_probs = np.asarray(legacy_probs, float)[legacy_indices]
            record["legacy_candidate_stats"] = _corner_candidate_stats(legacy_probs)
            return result
        finally:
            active = None

    gv._corner_probabilities = corner_spy
    gv._native_density_probabilities = native_spy
    try:
        gv.process(ITEM057, OUT, smoothing=MODE)
    finally:
        gv._native_density_probabilities = original_native
        gv._corner_probabilities = original_corner

    for row in records:
        prob_extents = row["probability_input_extents"]
        req_extent = row["requant_extent_px"]
        coarse_extent = row["coarse_extent_native_px"]
        if not prob_extents:
            row["observed_path"] = "rf-or-no-classifier-call"
        elif req_extent is not None and abs(prob_extents[-1] - req_extent) < abs(prob_extents[-1] - coarse_extent):
            row["observed_path"] = "requantized"
        else:
            row["observed_path"] = "classic-probability-fallback"

    scale4 = len(records)
    fallback = sum(r["observed_path"] == "classic-probability-fallback" for r in records)
    ratios = [r["requant_to_loop_extent_ratio"] for r in records
              if r["requant_to_loop_extent_ratio"] is not None]
    report = {
        "item": 57,
        "input": str(ITEM057),
        "smoothing": MODE,
        "scale4_calls": scale4,
        "fallback_calls": fallback,
        "fallback_rate": round(fallback / max(1, scale4), 4),
        "median_requant_to_loop_extent_ratio": None if not ratios else round(float(np.median(ratios)), 4),
        "hypothesis_extent_quartered": bool(ratios and float(np.median(ratios)) < 0.35),
        "calls": records,
    }
    report_path = ROOT / "benchmarks" / "probe_dp4x_item057_postfix.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "calls"}, indent=2))
    print("->", report_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

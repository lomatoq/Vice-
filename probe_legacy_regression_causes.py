"""Focused, non-tuning ablations for regressions in the incumbent Best route."""

from __future__ import annotations

import json
from pathlib import Path

import benchmark_stages as stages
import geometry_vectorizer as gv


ROOT = Path(__file__).resolve().parent


def main() -> int:
    targets = {
        "bars_clean": ROOT / "benchmarks" / "work" / "bars_clean.png",
        "cross": ROOT / "benchmarks" / "work" / "cross.png",
    }
    snapshot = json.loads((ROOT / "benchmarks" / "stage_snapshot.json").read_text(
        encoding="utf-8"))
    original_variable = gv._detect_variable_strokes
    original_stroke = gv._detect_stroke
    rows = []
    try:
        gv._detect_variable_strokes = lambda mask, analysis_scale: None
        gv._detect_stroke = lambda mask, analysis_scale: None
        for name, source in targets.items():
            candidate = stages.fit_case(f"{name}_no_underpaint", source,
                                        smoothing="paper")
            rows.append({
                "name": name,
                "baseline": snapshot["synthetic"][name],
                "no_shared_edge_underpaint": candidate,
            })
    finally:
        gv._detect_variable_strokes = original_variable
        gv._detect_stroke = original_stroke
    output = ROOT / "benchmarks" / "legacy_stroke_lane_ablation.json"
    output.write_text(json.dumps({
        "schema": "vice-legacy-focused-ablation/1",
        "mechanism": "_detect_variable_strokes + _detect_stroke",
        "rows": rows,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output)
    for row in rows:
        base = row["baseline"]
        trial = row["no_shared_edge_underpaint"]
        print(row["name"],
              f"regions {base['regions']}->{trial['regions']}",
              f"prims {base['prims']}->{trial['prims']}",
              f"iou {base['raster_iou']}->{trial['raster_iou']}",
              f"seconds {base['secs']}->{trial['secs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

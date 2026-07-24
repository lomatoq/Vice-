"""Ablate the post-baseline DP/physical-geometry changes on fixed canaries."""

from __future__ import annotations

import json
from pathlib import Path

import benchmark_stages as stages
import geometry_vectorizer as gv


ROOT = Path(__file__).resolve().parent


def main() -> int:
    snapshot = json.loads((ROOT / "benchmarks" / "stage_snapshot.json").read_text(
        encoding="utf-8"))
    settings = {
        "_DP_PHYSICAL_FIDELITY": False,
        "_DP_UNCERTAINTY_NORMALIZATION": False,
        "_DP_CORRELATION_WEIGHTING": False,
        "_DP_MDL_CODING": False,
        "_JOINT_IDEAL_APEX_CAPS": False,
    }
    originals = {name: getattr(gv, name) for name in settings}
    rows = []
    try:
        for name, value in settings.items():
            setattr(gv, name, value)
        for name, source in {
            "shield_symmetry": ROOT / "benchmarks" / "work" / "shield_sym.png",
        }.items():
            trial = stages.fit_case(f"{name}_legacy_dp", source, smoothing="paper")
            rows.append({"name": name, "baseline": snapshot["icons"][name],
                         "legacy_dp": trial})
    finally:
        for name, value in originals.items():
            setattr(gv, name, value)
    output = ROOT / "benchmarks" / "legacy_dp_ablation.json"
    output.write_text(json.dumps({
        "schema": "vice-legacy-focused-ablation/1",
        "settings": settings,
        "rows": rows,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for row in rows:
        base, trial = row["baseline"], row["legacy_dp"]
        print(row["name"], f"prims {base['prims']}->{trial['prims']}",
              f"iou {base['raster_iou']}->{trial['raster_iou']}",
              f"seconds {base['secs']}->{trial['secs']}")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

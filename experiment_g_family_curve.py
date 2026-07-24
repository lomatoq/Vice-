"""Experiment G (audit S16-G) at the retrieval/construction level.

Holds the protocol constant (composed operators, unseen-font mode, same GT
sampling from the attested held-out families) and varies ONLY the retrieval
bank size: 81 attested families vs a 600-family subset vs the full v2 bank.
If the unseen-family metric rises with family count, style diversity - not
sample count - is the binding data axis (the audit's D5), and the
family_learning_curve readiness gate closes.

Usage:
  C:\\Python312\\python.exe experiment_g_family_curve.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "benchmarks" / "pcdc_pre_v14"
PYTHON = sys.executable
SAMPLES_PER_LENGTH = 48


def build_subset_bank(source: Path, target: Path, family_limit: int) -> int:
    bank = json.loads(source.read_text(encoding="utf-8"))
    families_sorted = sorted({
        face["family"] for face in bank["faces"].values()
    })[:family_limit]
    keep = set(families_sorted)
    faces = {
        key: face for key, face in bank["faces"].items()
        if face["family"] in keep
    }
    import numpy as np
    names = bank["feature_names"]
    table = np.array([
        [face["features"][name] for name in names]
        for face in faces.values()
    ])
    bank["faces"] = faces
    bank["normalization"] = {
        name: {
            "mean": float(table[:, column].mean()),
            "std": float(max(1e-6, table[:, column].std())),
        }
        for column, name in enumerate(names)
    }
    target.write_text(json.dumps(bank, indent=1), encoding="utf-8")
    return len(keep)


def run_point(label: str, bank_path: Path, out_path: Path) -> dict:
    subprocess.run([
        PYTHON, str(ROOT / "diagnose_vector_topology_recall.py"),
        "--composition", "composed", "--exclude-gt-family",
        "--skip-bank-check", "--descriptors", str(bank_path),
        "--samples-per-length", str(SAMPLES_PER_LENGTH),
        "--out", str(out_path),
    ], check=True, cwd=str(ROOT))
    report = json.loads(out_path.read_text(encoding="utf-8"))
    families = len({
        face["family"]
        for face in json.loads(
            bank_path.read_text(encoding="utf-8")
        )["faces"].values()
    })
    return {
        "label": label,
        "families": families,
        "faces": report["retrieval_bank_faces"],
        "unseen_metric": report["overall"]["recall_at_8"],
        "recall_at_1": report["overall"]["recall_at_1"],
        "artifact": out_path.name,
    }


def main() -> None:
    started = time.perf_counter()
    v2 = BENCH / "font_style_descriptors_v2full.json"
    mid = BENCH / "font_style_descriptors_v2mid600.json"
    build_subset_bank(v2, mid, 600)
    points = [
        run_point(
            "attested-81", BENCH / "font_style_descriptors.json",
            BENCH / "g_point_attested81.json",
        ),
        run_point("v2-600", mid, BENCH / "g_point_v2mid600.json"),
        run_point("v2-full", v2, BENCH / "g_point_v2full.json"),
    ]
    rising = points[-1]["unseen_metric"] > points[0]["unseen_metric"] + 0.02
    report = {
        "schema": "vice-experiment-g-family-curve/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": (
            "composed operators, unseen-font, samples_per_length "
            f"{SAMPLES_PER_LENGTH}, GT from attested held-out families"
        ),
        "points": points,
        "rising": bool(rising),
        "elapsed_seconds": time.perf_counter() - started,
    }
    out = BENCH / "experiment_g_family_curve.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["points"], indent=2))
    print("rising:", rising)
    print(f"curve written to {out}")


if __name__ == "__main__":
    main()

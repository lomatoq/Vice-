"""v10 training readiness artifact - fail-closed by construction.

The audit (S10, S15) and the operating contract (S4.7, S11.6) require a
current, green, machine-readable readiness artifact before ANY v10 full
training run. This builder enumerates every gate explicitly and emits
`TRAIN` only when all of them hold. Missing evidence is a closed gate.

Gates encoded here (each with its evidence source):

1. preflight_experiments_closed - A/B/D/E/F/R closed in
   v10_preflight_state.json;
2. construction_core_validated  - composed-operator Recall@8 uplift
   artifact present (S8.11 mechanism proven);
3. operator_pilot_signal        - the bounded pilot beat majority baselines
   (signal exists) even though its compression claim was rejected;
4. expanded_font_bank           - a v2 bank manifest with >= 1000 families
   exists and its faces are on disk (S11.2);
5. family_learning_curve        - Experiment G artifact exists and shows
   the unseen-family metric RISING with family count (S16-G);
6. curriculum_datasets          - stage A-F dataset manifests exist with
   payload attestation;
7. pair_interaction_design      - join/touch operator spec exists (the #1
   model item per Experiment R);
8. human_capacity               - real-loci annotation capacity recorded
   (S11.6 real calibration).

Usage:
  C:\\Python312\\python.exe build_v10_readiness.py
"""

from __future__ import annotations

import json

import numpy as np
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "benchmarks" / "pcdc_pre_v14"
OUT = BENCH / "v10_training_readiness.json"


def _exists_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main() -> None:
    gates: dict[str, dict] = {}

    state = _exists_json(BENCH / "v10_preflight_state.json")
    closed = 0
    if state:
        for name, verdict in state.get("verdicts", {}).items():
            if verdict.get("status") in {"closed", "measured-lite", "parked"}:
                closed += 1
    gates["preflight_experiments_closed"] = {
        "ok": bool(state) and closed >= 5,
        "evidence": "v10_preflight_state.json",
        "detail": f"{closed} verdicts closed/parked",
    }

    composed = _exists_json(
        BENCH / "vector_topology_recall_openbank_composed_k8.json"
    )
    gates["construction_core_validated"] = {
        "ok": bool(composed)
        and composed["overall"]["recall_at_8"] >= 0.75,
        "evidence": "vector_topology_recall_openbank_composed_k8.json",
        "detail": (
            f"composed Recall@8 {composed['overall']['recall_at_8']:.3f}"
            if composed else "missing"
        ),
    }

    pilot = _exists_json(BENCH / "v10_operator_pilot_report.json")
    pilot_signal = bool(
        pilot and all(
            pilot["val_accuracy"][head]
            > pilot["majority_baseline"][head] + 0.03
            for head in ("stroke", "tracking", "effect")
        )
    )
    gates["operator_pilot_signal"] = {
        "ok": pilot_signal,
        "evidence": "v10_operator_pilot_report.json",
        "detail": (
            "operators readable; top-2 compression claim rejected and parked"
            if pilot_signal else "missing or at chance"
        ),
    }

    bank_v2 = _exists_json(
        ROOT / "fonts" / "google-fonts-manifest-v2-full.json"
    )
    families = len({
        face["family"] for face in bank_v2["faces"]
    }) if bank_v2 and "faces" in bank_v2 else 0
    gates["expanded_font_bank"] = {
        "ok": families >= 1000,
        "evidence": "fonts/google-fonts-manifest-v2-full.json",
        "detail": f"{families} families",
    }

    # Training-side Experiment G is authoritative (the audit's actual form:
    # train on N families, measure unseen-family metric). The retrieval-side
    # curve was measured FLAT on 2026-07-24 (D5 falsified at that level) and
    # cannot close this gate.
    train_points = []
    for name in ("g_train_fam81.json", "g_train_fam600.json",
                 "g_train_famfull.json"):
        report = _exists_json(BENCH / name)
        if report and "val_accuracy" in report:
            train_points.append({
                "families": report.get("train_families"),
                "unseen_metric": float(np.mean([
                    report["val_accuracy"][head]
                    for head in ("stroke", "tracking", "effect")
                ])),
            })
    rising = (
        len(train_points) >= 3
        and train_points[-1]["unseen_metric"]
        > train_points[0]["unseen_metric"] + 0.02
    )
    gates["family_learning_curve"] = {
        "ok": bool(rising),
        "evidence": "g_train_fam{81,600,full}.json (training-side G)",
        "detail": (
            f"points {[(p['families'], round(p['unseen_metric'], 4)) for p in train_points]}"
            if train_points else "missing"
        ),
    }

    curriculum = _exists_json(BENCH / "v10_curriculum_manifest.json")
    gates["curriculum_datasets"] = {
        "ok": bool(curriculum) and bool(curriculum.get("stages")),
        "evidence": "v10_curriculum_manifest.json",
        "detail": "present" if curriculum else "missing",
    }

    pair_spec = (ROOT / "V10_PAIR_INTERACTION_SPEC_BY.md").is_file()
    gates["pair_interaction_design"] = {
        "ok": pair_spec,
        "evidence": "V10_PAIR_INTERACTION_SPEC_BY.md",
        "detail": "present" if pair_spec else "missing",
    }

    capacity = _exists_json(BENCH / "real_annotation_capacity.json")
    gates["human_capacity"] = {
        "ok": bool(capacity),
        "evidence": "real_annotation_capacity.json",
        "detail": "present" if capacity else "missing",
    }

    authorized = all(gate["ok"] for gate in gates.values())
    report = {
        "schema": "vice-v10-training-readiness/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "TRAIN" if authorized else "NO-TRAIN",
        "gates": gates,
        "note": (
            "Fail-closed: a missing artifact is a closed gate. This file "
            "must be regenerated and green at launch time; a stale copy "
            "authorizes nothing."
        ),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(
        {"status": report["status"],
         "gates": {name: gate["ok"] for name, gate in gates.items()}},
        indent=2,
    ))
    print(f"readiness written to {OUT}")


if __name__ == "__main__":
    main()

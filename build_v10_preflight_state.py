"""Machine-readable state of the v10 preflight experiments (audit S17 step 1).

Aggregates the diagnostic artifacts produced by
diagnose_wordmark_clean_identity.py and diagnose_template_warp_oracle.py into
one hash-bound JSON verdict file. Reruns are idempotent; missing artifacts are
reported as open, never silently skipped.

Usage:
  C:\\Python312\\python.exe build_v10_preflight_state.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "benchmarks" / "pcdc_pre_v14"
OUT = BENCH / "v10_preflight_state.json"

IDENTITY_MATRIX = {
    ("clean", "exact"): "wordmark_clean_identity_v4epoch3_3584.json",
    ("clean", "corrupted"): "wordmark_identity_clean_ocrcorrupted_3584.json",
    ("clean", "blank"): "wordmark_identity_clean_ocrblank_3584.json",
    ("degraded", "exact"): "wordmark_identity_degraded_ocrexact_3584.json",
    ("degraded", "corrupted"):
        "wordmark_identity_degraded_ocrcorrupted_3584.json",
    ("degraded", "blank"): "wordmark_identity_degraded_ocrblank_3584.json",
}
TEMPLATE_RUNS = {
    "fixed": "template_warp_oracle_fixed_896.json",
    "dynamic": "template_warp_oracle_dynamic_896.json",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(name: str) -> tuple[dict | None, dict]:
    path = BENCH / name
    if not path.is_file():
        return None, {"artifact": name, "status": "missing"}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, {
        "artifact": name,
        "status": "present",
        "sha256": _sha256(path),
        "created_at": data.get("created_at"),
        "schema": data.get("schema"),
    }


def main() -> None:
    artifacts: list[dict] = []
    matrix: dict[str, dict] = {}
    for (source, ocr_mode), name in IDENTITY_MATRIX.items():
        data, meta = _load(name)
        artifacts.append(meta)
        if data is None:
            continue
        matrix[f"{source}/{ocr_mode}"] = {
            "raw_topology": data["overall"]["raw_topology_accuracy"],
            "decoded_topology": data["overall"]["decoded_topology_accuracy"],
            "joint_head": data["overall"]["joint_topology_head_accuracy"],
            "len32_raw": data["per_length"]["32"]["raw_topology_accuracy"],
            "checkpoint_sha256": data.get("checkpoint_sha256"),
        }
    template: dict[str, dict] = {}
    for arena, name in TEMPLATE_RUNS.items():
        data, meta = _load(name)
        artifacts.append(meta)
        if data is None:
            continue
        template[arena] = {
            "selected_topology": data["overall"][
                "selected_topology_accuracy"
            ],
            "oracle_topology": data["overall"]["oracle_topology_accuracy"],
            "selected_edit_distance": data["overall"][
                "selected_topology_edit_distance"
            ],
            "oracle_edit_distance": data["overall"][
                "oracle_topology_edit_distance"
            ],
            "selected_iou_gt": data["overall"]["selected_iou_gt"],
            "oracle_iou_gt": data["overall"]["oracle_iou_gt"],
            "len32": data["per_length"]["32"],
        }

    verdicts: dict[str, dict] = {}
    clean = matrix.get("clean/exact")
    degraded = matrix.get("degraded/exact")
    if clean and degraded:
        verdicts["experiment_B_clean_identity"] = {
            "status": "closed",
            "fact_clean_len32_raw": clean["len32_raw"],
            "fact_degraded_len32_raw": degraded["len32_raw"],
            "conclusion": (
                "degradation inversion dominates (x{:.1f} gap at len 32); "
                "representation also insufficient at 32 on clean "
                "({:.3f} < 0.95)".format(
                    clean["len32_raw"] / max(1e-6, degraded["len32_raw"]),
                    clean["len32_raw"],
                )
            ),
        }
    corrupted = matrix.get("degraded/corrupted")
    blank = matrix.get("degraded/blank")
    if degraded and corrupted and blank:
        verdicts["experiment_E_ocr_conditioning"] = {
            "status": "closed",
            "fact_wrong_hint_cost_raw": round(
                degraded["raw_topology"] - corrupted["raw_topology"], 6,
            ),
            "fact_blank_hint_cost_raw": round(
                degraded["raw_topology"] - blank["raw_topology"], 6,
            ),
            "conclusion": (
                "hypothesis D4 (hard-OCR poisoning) falsified for v4: the "
                "mask ignores transcript content; blank hint costs ~2pt, so "
                "the transcript is used only as a generic prior - v10 needs "
                "explicit layout/content conditioning to exploit it"
            ),
        }
    verdicts["experiment_A_length_ppg"] = {
        "status": "measured-lite",
        "fact": (
            "fixed 64x256 letterbox: ~39.9 px/glyph at L=1 down to ~7.6 at "
            "L=32; raw clean topology holds >=0.965 down to ~10 ppg"
        ),
        "remaining": "training-side dynamic-width variant is a v10 decision",
    }
    verdicts["experiment_C_oracle_layout"] = {
        "status": "parked",
        "reason": (
            "feeding oracle glyph boxes to the v4 model needs a new "
            "conditioning path (net-new architecture change); the fitter's "
            "per-glyph offset stage already exercises layout externally"
        ),
    }
    if template:
        verdicts["experiment_D_oracle_template"] = {
            "status": "closed" if len(template) == 2 else "running",
            "arenas": {
                arena: {
                    "oracle_iou_gt": values["oracle_iou_gt"],
                    "oracle_edit_distance": values["oracle_edit_distance"],
                }
                for arena, values in template.items()
            },
        }
    else:
        verdicts["experiment_D_oracle_template"] = {"status": "running"}

    state = {
        "schema": "vice-v10-preflight-state/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "held_out_family_split_seed": 20260722,
            "sample_seed": 20260724,
            "lengths": [1, 2, 4, 8, 16, 24, 32],
            "checkpoint": "models/wordmark_prior_candidate_v1_epoch3.pt",
            "source_snapshot":
                ".training_snapshots/wordmark_full_v4_20260723",
        },
        "identity_matrix": matrix,
        "template_warp_oracle": template,
        "verdicts": verdicts,
        "standing_blocks": {
            "v9_full_run": "forbidden (no new hypothesis; audit S6)",
            "proposalnet_v14": "NO-TRAIN (PRE_V14_READINESS_AUDIT.md)",
            "vai_parity": "not proven (V_ICE_CURRENT_AUDIT.md)",
        },
        "artifacts": artifacts,
    }
    OUT.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps(state["verdicts"], indent=2))
    print(f"state written to {OUT}")


if __name__ == "__main__":
    main()

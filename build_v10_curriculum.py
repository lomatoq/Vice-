"""v10 curriculum manifest + Stage-A pilot shard (audit S10, Stage A-F).

Stage A ("clean glyph program prior") gets a REAL, materialized,
payload-attested pilot shard: for every face of the v2 bank, eight sampled
characters are rendered clean at 256 px and their template topology is
recorded. Later stages are DEFINED with generator specs and prerequisites,
not fabricated: the readiness gate stays honest about what is materialized
versus declared.

Usage:
  C:\\Python312\\python.exe build_v10_curriculum.py
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "benchmarks" / "pcdc_pre_v14"
SHARD_DIR = ROOT / "datasets" / "v10_curriculum_stage_a_pilot"
CHARS = "ABEGHKMOQRSagoeikx0248&"
CHARS_PER_FACE = 8


def main() -> None:
    from diagnose_vector_topology_recall import _glyph_topology

    started = time.perf_counter()
    bank = json.loads(
        (ROOT / "fonts" / "google-fonts-manifest-v2-full.json")
        .read_text(encoding="utf-8")
    )
    rng = np.random.default_rng(20260724)
    records = []
    skipped = 0
    for face in bank["faces"]:
        path = ROOT / face["path"]
        chosen = rng.choice(
            list(CHARS), size=CHARS_PER_FACE, replace=False,
        )
        for character in chosen:
            topology = _glyph_topology(str(path), str(character))
            if topology is None:
                skipped += 1
                continue
            records.append({
                "face_sha256": face["sha256"],
                "family": face["family"],
                "character": str(character),
                "components": topology[0],
                "holes": topology[1],
            })
    SHARD_DIR.mkdir(parents=True, exist_ok=True)
    shard_path = SHARD_DIR / "stage_a_pilot_records.jsonl"
    payload = "\n".join(json.dumps(row) for row in records) + "\n"
    shard_path.write_text(payload, encoding="utf-8")
    payload_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    manifest = {
        "schema": "vice-v10-curriculum/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "font_bank": "fonts/google-fonts-manifest-v2-full.json",
        "font_bank_content_sha256": bank["content_sha256"],
        "stages": {
            "A_clean_glyph_program": {
                "status": "pilot-shard-materialized",
                "payload": str(shard_path.relative_to(ROOT)).replace("\\", "/"),
                "payload_sha256": payload_sha,
                "records": len(records),
                "skipped_renders": skipped,
                "generator": (
                    "per-glyph 256px clean render + topology signature; "
                    "full stage adds template shortlist, variant labels, "
                    "SDF/corner targets (audit S10 Stage A)"
                ),
                "gate": "unseen-family per-glyph topology >= 99.9%",
            },
            "B_clean_line_layout": {
                "status": "defined",
                "generator": (
                    "variable length 1-32, dynamic width, oracle transcript "
                    "+ oracle boxes from the vector font source"
                ),
                "prerequisite": "Stage A model green",
                "gate": "line exact topology >= 99% clean",
            },
            "C_visual_layout_inference": {
                "status": "defined",
                "generator": "Stage B minus oracle boxes",
                "prerequisite": "Stage B green",
                "gate": "layout Recall@K, per-glyph crop ownership",
            },
            "D_degradation_inverse": {
                "status": "defined",
                "generator": (
                    "blur/JPEG/gamma/resampling over Stage B/C corpora; "
                    "renderer family held out per audit S11.4"
                ),
                "prerequisite": "Stage C green",
                "gate": "candidate topology Recall@K (not top-1 mask)",
            },
            "E_ocr_uncertainty": {
                "status": "defined",
                "generator": (
                    "N-best transcripts, token posteriors, corrupted flags "
                    "(audit S13; hard-wrong-token forbidden per Experiment E)"
                ),
                "prerequisite": "Stage D green",
                "gate": "no degradation from OCR conditioning",
            },
            "F_real_locus_calibration": {
                "status": "blocked-on-human-capacity",
                "generator": "expanded reviewed loci 2k-5k (audit S11.6)",
                "prerequisite": "human annotation capacity decision",
                "gate": "delivered SVG effect + human court",
            },
        },
        "note": (
            "Only Stage A carries a materialized attested payload; stages "
            "B-E are generator specs gated on their prerequisites; stage F "
            "is blocked on the human capacity decision. The readiness gate "
            "must not read 'defined' as 'materialized'."
        ),
        "elapsed_seconds": time.perf_counter() - started,
    }
    out = BENCH / "v10_curriculum_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        f"stage-A shard: {len(records)} records ({skipped} skipped), "
        f"sha {payload_sha[:16]}..., {manifest['elapsed_seconds']:.0f}s"
    )
    print(f"manifest -> {out}")


if __name__ == "__main__":
    main()

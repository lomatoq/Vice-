"""Create the immutable Phase-0 PCDC truth ledger for V-ICE Best."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
PICTURES = Path(r"C:/Users/nirrt/Toolset/v-ice pictures")
PLAN = Path(
    r"C:/Users/nirrt/Downloads/V-ICE_proof_carrying_design_compiler_plan_ru_v2.md"
)
DEFAULT_OUT = PROJECT / "PCDC_BASELINE_FREEZE.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _entry(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        return {"path": str(resolved), "exists": False}
    return {
        "path": str(resolved),
        "exists": True,
        "size": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def _git(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *command],
            cwd=PROJECT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def build_freeze() -> dict[str, Any]:
    core_paths = [
        PROJECT / "geometry_vectorizer.py",
        PROJECT / "vectorize_papers.py",
        PROJECT / "web_preview" / "worker.py",
        PROJECT / "web_preview" / "server.py",
        PROJECT / "web_preview" / "index.html",
    ]
    model_paths = sorted(
        path for path in (PROJECT / "models").glob("*") if path.is_file()
    )
    benchmark_paths = [
        PROJECT / "benchmarks" / "vai_snapshot_production_fresh50_final.json",
        PICTURES / "challenge_pack" / "plates" / "plate_layout.json",
        PICTURES / "challenge_pack" / "eval" / "report_blind_FROZEN.json",
        PROJECT / "benchmarks" / "pcdc_phase0" / "completeness_report.json",
        PROJECT / "datasets" / "pcdc_real_loci_v1" / "manifest.json",
    ]
    files = {
        "canonical_plan": _entry(PLAN),
        "production_core": [_entry(path) for path in core_paths],
        "models": [_entry(path) for path in model_paths],
        "benchmark_truth": [_entry(path) for path in benchmark_paths],
    }
    missing = [
        entry["path"]
        for group in (
            [files["canonical_plan"]],
            files["production_core"],
            files["models"],
            files["benchmark_truth"],
        )
        for entry in group
        if not entry.get("exists")
    ]
    status = _git(["status", "--short"])
    return {
        "schema": "pcdc-baseline-freeze/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategic_target": "V-ICE Proof-Carrying Design Compiler",
        "production_default": "V-ICE Best / paper-regions",
        "experimental_policy": (
            "Scene Engine is archived experimental and cannot be promoted"
        ),
        "promotion_policy": (
            "PCDC remains isolated until all canonical promotion gates pass"
        ),
        "git": {
            "head": _git(["rev-parse", "HEAD"]),
            "dirty": bool(status),
            "status_sha256": (
                hashlib.sha256(status.encode("utf-8")).hexdigest()
                if status is not None
                else None
            ),
        },
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "files": files,
        "complete": not missing,
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    payload = build_freeze()
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": payload["complete"],
                "path": str(args.out),
                "missing": payload["missing"],
                "git": payload["git"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return int(not payload["complete"])


if __name__ == "__main__":
    raise SystemExit(main())


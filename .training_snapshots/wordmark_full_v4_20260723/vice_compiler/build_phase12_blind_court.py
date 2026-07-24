"""Build the locked, resolution-honest Phase-12 V-ICE/VAI blind court."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from PIL import Image


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    PROJECT / "benchmarks" / "pcdc_experiment12" / "runs" / "promotion" / "report.json"
)
COURT_ROOT = PROJECT / "benchmarks" / "pcdc_experiment12" / "blind_vai_court"
PRIVATE_MANIFEST = COURT_ROOT / "human_manifest.json"
REVIEW_PATH = COURT_ROOT / "review.json"
WEB_ASSETS = PROJECT / "web_preview" / "phase12_blind_assets"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8",
    )
    temporary.replace(path)


def _stable_side(case_id: str, seed: int) -> str:
    digest = hashlib.sha256(f"{seed}\0{case_id}".encode("utf-8")).digest()
    return "A" if digest[0] & 1 else "B"


def _asset_path(row: dict, key: str) -> Path:
    if key == "ours":
        raw = row.get("exports", {}).get("svg", {}).get("path")
    elif key == "vai":
        raw = row.get("reference")
    else:
        raw = row.get("source")
    path = Path(str(raw or ""))
    if not path.is_file():
        raise FileNotFoundError(f"missing {key} asset for {row.get('id')}: {path}")
    return path.resolve()


def _native_size(source: Path, row: dict) -> tuple[int, int]:
    size = row.get("size")
    if isinstance(size, list) and len(size) == 2:
        return int(size[0]), int(size[1])
    with Image.open(source) as image:
        return image.size


def build_court(
    report_path: Path = DEFAULT_REPORT, *, seed: int = 20260722,
    court_root: Path = COURT_ROOT, web_assets: Path = WEB_ASSETS,
) -> dict:
    private_manifest = court_root / "human_manifest.json"
    review_path = court_root / "review.json"
    report = json.loads(report_path.read_text("utf-8"))
    rows = list(report.get("rows", []))
    if report.get("schema") != "pcdc-experiment12/v1":
        raise ValueError("Phase-12 report schema is unsupported")
    if not rows or any(row.get("status") != "ok" for row in rows):
        raise ValueError("blind court requires a complete error-free campaign")
    web_assets.mkdir(parents=True, exist_ok=True)
    cases = []
    fingerprint = str(report.get("compiler_fingerprint", ""))
    for position, row in enumerate(rows):
        case_id = str(row["id"])
        source = _asset_path(row, "source")
        ours = _asset_path(row, "ours")
        vai = _asset_path(row, "vai")
        width, height = _native_size(source, row)
        token = hashlib.sha256(
            f"{seed}\0{fingerprint}\0{case_id}".encode("utf-8")
        ).hexdigest()[:20]
        source_suffix = source.suffix.lower()
        if source_suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            source_suffix = ".png"
        source_name = f"{token}_source{source_suffix}"
        a_name = f"{token}_a.svg"; b_name = f"{token}_b.svg"
        ours_side = _stable_side(case_id, seed)
        a_source, b_source = (ours, vai) if ours_side == "A" else (vai, ours)
        shutil.copy2(source, web_assets / source_name)
        shutil.copy2(a_source, web_assets / a_name)
        shutil.copy2(b_source, web_assets / b_name)
        cases.append({
            "id": case_id, "position": position,
            "suite": str(row.get("suite", "unknown")),
            "slice": str(row.get("category") or row.get("suite") or "unknown"),
            "native_size": [width, height],
            "a_url": f"/phase12_blind_assets/{a_name}",
            "b_url": f"/phase12_blind_assets/{b_name}",
            "source_url": f"/phase12_blind_assets/{source_name}",
            "ours_side": ours_side,
            "source_sha256": _sha256(source),
            "ours_sha256": _sha256(ours), "vai_sha256": _sha256(vai),
        })
    identity_payload = {
        "campaign_report_sha256": _sha256(report_path),
        "compiler_fingerprint": fingerprint, "seed": int(seed),
        "cases": [{
            key: row[key] for key in (
                "id", "slice", "native_size", "a_url", "b_url",
                "source_url", "ours_side", "source_sha256", "ours_sha256",
                "vai_sha256",
            )
        } for row in cases],
    }
    court_id = "phase12-" + hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20]
    manifest = {
        "schema": "pcdc-phase12-blind-vai-manifest/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "court_id": court_id, "locked": True, "seed": int(seed),
        "campaign_report": str(report_path.resolve()),
        "campaign_report_sha256": _sha256(report_path),
        "compiler_fingerprint": fingerprint,
        "expected_count": len(cases),
        "display_contract": {
            "live_svg": True, "equal_viewport": True, "zoom_pan": True,
            "raster_downsample_forbidden": True,
        },
        "cases": cases,
    }
    if review_path.is_file():
        existing = json.loads(review_path.read_text("utf-8"))
        if existing.get("court_id") not in {None, court_id} and existing.get("answers"):
            raise RuntimeError("a different locked court already has answers")
    _write_json(private_manifest, manifest)
    if not review_path.is_file():
        _write_json(review_path, {
            "schema": "pcdc-phase12-blind-vai-court/v1",
            "court_id": court_id, "locked": True,
            "expected_count": len(cases),
            "display_contract": manifest["display_contract"],
            "answers": {}, "complete_count": 0,
        })
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--seed", type=int, default=20260722)
    args = parser.parse_args()
    manifest = build_court(args.report, seed=args.seed)
    print(json.dumps({
        "court_id": manifest["court_id"],
        "expected_count": manifest["expected_count"],
        "url": "/phase12_blind.html",
        "manifest": str(PRIVATE_MANIFEST),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

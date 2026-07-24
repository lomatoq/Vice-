"""BUILD_FREEZE manifest creation and verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

from .config import EngineConfig


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FREEZE = ROOT / "BUILD_FREEZE.json"
ROOT_FILES = (
    "benchmark_vai.py", "build_vai_crop_court.py", "challenge_eval.py",
    "eval_one_item.py", "generate_scene_evidence_dataset.py", "run_vectorizer.py",
    "test_scene_engine.py", "train_scene_evidence.py", "validate_scene_evidence.py",
    "validate_scene_evidence_real_ab.py",
    "validate_scene_campaign.py", "validate_scene_synthetic.py",
    "vectorizer_ai_svg_forensics.py",
    "VICE_SCENE_IMPLEMENTATION_MATRIX_BY.md", "web_preview/index.html",
    "web_preview/server.py", "web_preview/worker.py",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(config: EngineConfig | None = None) -> dict:
    import cv2
    import numpy
    import torch

    config = config or EngineConfig()
    code_paths = sorted(Path("vice_scene") / path.name
                        for path in (ROOT / "vice_scene").glob("*.py"))
    code_paths += [Path(item) for item in ROOT_FILES if (ROOT / item).is_file()]
    code = [_file_row(ROOT / relative, relative.as_posix()) for relative in code_paths]
    models = []
    for relative in (Path("models/scene_evidence.pt"),
                     Path("models/scene_evidence.promoted.pt")):
        if (ROOT / relative).is_file():
            models.append(_file_row(ROOT / relative, relative.as_posix()))
    external_plan = Path(
        r"C:\Users\nirrt\Downloads\vectorizer_ai_clean_room_research_bundle\VectorizerAI_clean_room_reverse_engineering_plan_by.md")
    plans = [_file_row(external_plan, str(external_plan))] if external_plan.is_file() else []
    datasets = _dataset_inventory()
    payload = {
        "schema": "vice-build-freeze/1",
        "engine": "vice-scene",
        "engine_version": config.engine_version,
        "policy": "no tuning after freeze until the validation campaign completes",
        "config": json.loads(config.canonical_json()),
        "config_hash": config.hash,
        "code": code,
        "models": models,
        "plans": plans,
        "datasets": datasets,
        "runtime": {
            "python": platform.python_version(), "platform": platform.platform(),
            "numpy": numpy.__version__, "opencv": cv2.__version__,
            "torch": torch.__version__, "cuda_available": bool(torch.cuda.is_available()),
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True)
    payload["freeze_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def write_freeze(path: Path = DEFAULT_FREEZE,
                 config: EngineConfig | None = None) -> dict:
    payload = build_manifest(config)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n", encoding="utf-8")
    return payload


def verify_freeze(path: Path = DEFAULT_FREEZE) -> tuple[bool, tuple[str, ...]]:
    frozen = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    freeze_hash = frozen.pop("freeze_hash", None)
    canonical = json.dumps(frozen, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True)
    actual_freeze_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if freeze_hash != actual_freeze_hash:
        errors.append("manifest freeze_hash mismatch")
    for section in ("code", "models", "plans", "datasets"):
        for row in frozen.get(section, []):
            source = Path(row["path"])
            if not source.is_absolute():
                source = ROOT / source
            if not source.is_file():
                errors.append(f"missing {section} file: {row['path']}")
            elif sha256_file(source) != row["sha256"]:
                errors.append(f"hash mismatch: {row['path']}")
    config = EngineConfig()
    if config.hash != frozen.get("config_hash"):
        errors.append("default EngineConfig changed")
    return not errors, tuple(errors)


def _dataset_inventory() -> list[dict]:
    rows: dict[str, dict] = {}

    def add(path: Path) -> None:
        if path.is_file():
            rows[str(path)] = _file_row(path, str(path))

    for name in ("vai_snapshot_production_fresh50_final.json",
                 "vai_snapshot.json", "vai_crop_court_manifest.json"):
        add(ROOT / "benchmarks" / name)
    try:
        import benchmark_vai as benchmark
        for stem in benchmark.frozen_stems(10_000):
            source = benchmark.find_source(stem)
            if source is not None:
                add(source)
            add(benchmark.VAI_DIR / f"{stem}_vai.svg")
    except Exception:
        pass
    plates = Path(r"C:\Users\nirrt\Toolset\v-ice pictures\challenge_pack\plates")
    add(plates / "plate_layout.json")
    for pattern in ("plate_*.png", "plate_*_vai.svg"):
        for path in sorted(plates.glob(pattern)):
            add(path)
    return [rows[key] for key in sorted(rows)]


def _file_row(path: Path, label: str) -> dict:
    return {"path": label, "bytes": path.stat().st_size,
            "sha256": sha256_file(path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--path", type=Path, default=DEFAULT_FREEZE)
    args = parser.parse_args()
    if args.write:
        payload = write_freeze(args.path)
        print(f"BUILD_FREEZE {payload['freeze_hash']} -> {args.path}")
        return 0
    okay, errors = verify_freeze(args.path)
    print("BUILD_FREEZE: OK" if okay else "BUILD_FREEZE: FAIL")
    for error in errors:
        print(error)
    return 0 if okay else 1


if __name__ == "__main__":
    raise SystemExit(main())

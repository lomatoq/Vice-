"""Isolated one-item PCDC compile and frozen meter worker for Phase 12."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _meters(svg: Path, source: Path, width: int) -> dict:
    import benchmark_vai as benchmark

    result = {}
    result.update(benchmark.geometry_meters(svg, width))
    result.update(benchmark.roundness_meter(svg, width))
    result.update(benchmark.raster_meters(svg, source))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", default="balanced")
    parser.add_argument(
        "--profile", choices=("faithful", "balanced", "idealized"),
        default="balanced",
    )
    parser.add_argument("--all-exports", action="store_true")
    parser.add_argument("--no-reference-meters", action="store_true")
    parser.add_argument("--proposal-checkpoint", type=Path)
    parser.add_argument("--proposal-manifest", type=Path)
    parser.add_argument("--candidate-evaluation", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        from PIL import Image
        import psutil

        from .export_writer import export_scene, scene_to_svg
        from .runtime_service import PersistentCompilerService

        with Image.open(args.source) as image:
            width, height = image.size
        if args.candidate_evaluation and not (
            args.proposal_checkpoint is not None
            and args.proposal_manifest is not None
        ):
            raise ValueError(
                "candidate evaluation requires checkpoint and manifest"
            )
        service_kwargs = {}
        if args.proposal_checkpoint is not None:
            service_kwargs["proposal_checkpoint"] = args.proposal_checkpoint
        if args.proposal_manifest is not None:
            service_kwargs["proposal_promotion_manifest"] = args.proposal_manifest
        service_kwargs["allow_candidate_evaluation"] = bool(
            args.candidate_evaluation
        )
        service = PersistentCompilerService(**service_kwargs)
        try:
            result = service.compile(
                args.source, mode=args.mode, profile=args.profile,
            )
        finally:
            service.close()
        delivered_program = (
            result.abstraction.extracted
            if result.best_stage == "T4" and result.abstraction is not None
            else None
        )
        delivered_layers = (
            result.layered_scene
            if result.best_stage in {"T3", "T4"} else None
        )
        svg_path = args.output / "result.svg"
        artifact = export_scene(
            result.reir, result.cmir, result.visible_scene, svg_path,
            phase5_bundle=result.phase5_bundle,
            text_macros=result.text_macros,
            layered_scene=delivered_layers,
            design_program=delivered_program,
        )
        # A second serialization of the same immutable XIR must be identical.
        repeated_svg, _native, _fallback = scene_to_svg(
            result.reir, result.cmir, result.visible_scene,
            phase5_bundle=result.phase5_bundle,
            text_macros=result.text_macros,
            layered_scene=delivered_layers,
            design_program=delivered_program,
        )
        deterministic_export = hashlib.sha256(
            repeated_svg.encode("utf-8")
        ).hexdigest() == hashlib.sha256(
            svg_path.read_text("utf-8").encode("utf-8")
        ).hexdigest()

        exports = {"svg": asdict(artifact)}
        if args.all_exports:
            for target in ("png", "pdf", "eps", "dxf"):
                exported = export_scene(
                    result.reir, result.cmir, result.visible_scene,
                    args.output / f"result.{target}", target=target,
                    phase5_bundle=result.phase5_bundle,
                    text_macros=result.text_macros,
                    layered_scene=delivered_layers,
                    design_program=(
                        delivered_program if target == "svg" else None
                    ),
                )
                exports[target] = asdict(exported)

        ours = _meters(svg_path, args.source, width)
        reference = None
        if args.reference is not None and not args.no_reference_meters:
            if not args.reference.is_file():
                raise FileNotFoundError(args.reference)
            reference = _meters(args.reference, args.source, width)
        process = psutil.Process()
        payload = {
            "schema": "pcdc-phase12-item/v1", "status": "ok",
            "source": str(args.source.resolve()),
            "source_sha256": _sha256(args.source),
            "reference": (
                str(args.reference.resolve()) if args.reference is not None else None
            ),
            "reference_sha256": (
                _sha256(args.reference) if args.reference is not None else None
            ),
            "size": [width, height], "mode": args.mode,
            "wall_ms": (time.perf_counter() - started) * 1000.0,
            "runtime": result.summary(), "best_stage": result.best_stage,
            "selected_macros": len(result.solution.selected_ids),
            "deterministic_export": deterministic_export,
            "exports": exports, "ours": ours, "reference_metrics": reference,
            "working_set_mib": process.memory_info().rss / (1024.0 * 1024.0),
            "proposal_worker": {
                "device": service.proposal_worker.device,
                "error": service.proposal_worker.error,
                "candidate_evaluation": bool(args.candidate_evaluation),
                "checkpoint": str(service.proposal_worker.checkpoint),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, default=str))
        return 0
    except BaseException as error:
        print(json.dumps({
            "schema": "pcdc-phase12-item/v1", "status": "error",
            "source": str(args.source),
            "error": f"{type(error).__name__}: {error}"[:1000],
            "traceback": traceback.format_exc(limit=20)[-8000:],
            "wall_ms": (time.perf_counter() - started) * 1000.0,
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

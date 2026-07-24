"""Command-line interface for the parallel V-ICE Scene Engine."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import EngineConfig
from .pipeline import process_scene


def main() -> int:
    parser = argparse.ArgumentParser(description="V-ICE scene-first inverse-graphics vectorizer")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=Path("test_runs") / "scene")
    parser.add_argument("--max-colors", type=int, default=24)
    parser.add_argument("--topology-k", type=int, default=4)
    parser.add_argument("--ablate", action="append", default=[])
    parser.add_argument("--deterministic-evidence", action="store_true",
                        help="ignore the promoted checkpoint for an auditable A/B run")
    parser.add_argument("--evidence-checkpoint", type=Path,
                        help="explicit promoted/staging checkpoint for a frozen A/B run")
    args = parser.parse_args()
    config_values = {
        "max_colors": args.max_colors, "topology_k": args.topology_k,
        "ablations": tuple(sorted(set(args.ablate))),
    }
    if args.deterministic_evidence:
        config_values["evidence_checkpoint"] = None
    elif args.evidence_checkpoint is not None:
        config_values["evidence_checkpoint"] = str(args.evidence_checkpoint.resolve())
    config = EngineConfig(**config_values)
    files = []
    for path in args.inputs:
        if path.is_dir():
            files.extend(sorted(child for child in path.iterdir()
                                if child.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}))
        else:
            files.append(path)
    for path in files:
        report = process_scene(path, args.out, config=config)
        print(f"{path.name}: {report['regions']} shapes, {report['rendered_primitive_count']} primitives, {report['resource']['wall_seconds']:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

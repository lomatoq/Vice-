"""Generate deterministic evidence training data from owned source scenes only.

No Vectorizer.AI output or external vectorizer output is accepted by this tool.
Every sample stores its source SceneGraph, exact labels, renderer and degradation
provenance so the corpus can be independently reproduced and audited.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from vice_scene.contracts import RenderModel
from vice_scene.font_synthetic import font_text_scene
from vice_scene.synthetic import (DegradationStep, available_renderer_families,
                                  coverage_scene, random_scene,
                                  render_synthetic)
from vice_scene.training_data import write_training_sample


def _recipe(rng: np.random.Generator, sample_seed: int) -> tuple[DegradationStep, ...]:
    candidates = [
        (),
        (DegradationStep("gaussian-blur", (float(rng.uniform(.2, 1.1)),)),),
        (DegradationStep("resize", (float(rng.uniform(.45, .85)),)),),
        (DegradationStep("gamma", (float(rng.uniform(.75, 1.35)),)),),
        (DegradationStep("jpeg", (float(rng.integers(20, 96)),)),),
        (DegradationStep("sharpen", (float(rng.uniform(.2, .9)), .7)),),
        (DegradationStep("translate", (float(rng.uniform(-.45, .45)),
                                        float(rng.uniform(-.45, .45)))),),
        (DegradationStep("rotate", (float(rng.uniform(-1.2, 1.2)),)),),
        (DegradationStep("palette", (float(rng.integers(4, 25)),)),),
        (DegradationStep("scan-noise", (float(rng.uniform(.5, 4.0)),
                                         float(sample_seed))),),
        (DegradationStep("alpha-roundtrip-error", (float(rng.uniform(.2, .8)),)),),
        (DegradationStep("recompress", (float(rng.integers(25, 80)),
                                         float(rng.integers(2, 4)))),),
    ]
    first = candidates[int(rng.integers(0, len(candidates)))]
    # A second independent degradation is included in one quarter of samples.
    if rng.random() < .25:
        second = candidates[int(rng.integers(0, len(candidates)))]
        return first + second
    return first


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--count", type=int, default=512)
    parser.add_argument("--width", type=int, default=160)
    parser.add_argument("--height", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--external-renderers", action="store_true",
                        help="also use discovered Chromium/resvg adapters")
    parser.add_argument("--font", action="append", type=Path, default=[],
                        help="font licensed by the caller for synthetic training; repeatable")
    args = parser.parse_args()
    if args.count <= 0 or min(args.width, args.height) < 32:
        parser.error("count must be positive and dimensions must be at least 32")
    renderers = list(available_renderer_families())
    if not args.external_renderers:
        renderers = [item for item in renderers
                     if item in {"vice-analytic", "pillow-polygon", "opencv-polygon"}]
    args.output.mkdir(parents=True, exist_ok=True)
    for font in args.font:
        if not font.is_file():
            parser.error(f"font does not exist: {font}")
    rng = np.random.default_rng(args.seed)
    rows = []
    for index in range(args.count):
        sample_seed = int(rng.integers(0, 2**31 - 1))
        if args.font and index % 8 == 7:
            words = ("Vector", "ideal", "Aa09", "round", "glyph")
            scene = font_text_scene(args.font[index % len(args.font)],
                                    words[index % len(words)], width=args.width,
                                    height=args.height,
                                    font_size=min(58.0, args.height * .64))
        elif index % 4 == 0 and args.width >= 160 and args.height >= 120:
            scene = coverage_scene(sample_seed, args.width, args.height)
        else:
            scene = random_scene(sample_seed, args.width, args.height,
                                 shape_count=int(rng.integers(4, 13)))
        renderer = renderers[index % len(renderers)]
        degradations = _recipe(rng, sample_seed)
        model = RenderModel(
            name=f"synthetic-{renderer}", supersample=int(rng.choice((4, 8))),
            gamma=float(rng.choice((1.8, 2.0, 2.2, 2.4))),
            blur_sigma=float(rng.choice((0.0, 0.0, .25))),
        )
        image = render_synthetic(scene, model, degradations, renderer=renderer)
        split_value = int(hashlib.sha256(str(sample_seed).encode()).hexdigest()[:8], 16) % 10
        split = "train" if split_value < 8 else ("validation" if split_value == 8 else "test")
        relative = Path(split) / f"sample-{index:06d}.npz"
        write_training_sample(
            args.output / relative, scene, input_rgba=image, renderer=renderer,
            degradation_manifest=tuple(asdict(item) for item in degradations),
        )
        rows.append({"index": index, "seed": sample_seed, "split": split,
                     "path": relative.as_posix(), "renderer": renderer,
                     "render_model": asdict(model),
                     "degradations": [asdict(item) for item in degradations],
                     "input_sha256": hashlib.sha256(image.tobytes()).hexdigest()})
    manifest = {
        "schema": "vice-synthetic-dataset/1",
        "seed": args.seed,
        "count": args.count,
        "renderers": renderers,
        "policy": "owned-source-scenes-only; no Vectorizer.AI output",
        "samples": rows,
    }
    (args.output / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"generated {args.count} samples in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Frozen synthetic oracle, renderer-holdout and calibration validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from vice_scene.contracts import RenderModel
from vice_scene.ingest import decode_raster
from vice_scene.oracle_diagnostics import run_oracle_diagnostics
from vice_scene.render_models import (ScoreCalibration, forward_model_catalog,
                                      render_scene, select_forward_model)
from vice_scene.synthetic import (DegradationStep, available_renderer_families,
                                  canonical_smoke_scene, coverage_scene,
                                  random_scene, render_synthetic,
                                  render_with_family)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path,
                        default=Path("benchmarks/scene_synthetic_validation"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    rows = []

    renderer_scenes = (canonical_smoke_scene(), random_scene(8701, 96, 72, 7))
    for family in available_renderer_families():
        for index, scene in enumerate(renderer_scenes):
            try:
                first = render_with_family(scene, family)
                second = render_with_family(scene, family)
                deterministic = bool(np.array_equal(first, second))
                analytic = render_with_family(scene, "vice-analytic")
                row = {
                    "renderer": family, "scene": index,
                    "deterministic": deterministic,
                    "rgba_mae_vs_analytic": float(np.mean(np.abs(
                        first.astype(np.float32) - analytic.astype(np.float32)))),
                    "sha256": hashlib.sha256(first.tobytes()).hexdigest(),
                }
                if first.shape != analytic.shape or not deterministic:
                    failures.append(f"renderer invariant: {family}/scene-{index}")
            except Exception as exc:
                row = {"renderer": family, "scene": index,
                       "error": f"{type(exc).__name__}: {exc}"}
                failures.append(f"renderer failed: {family}/scene-{index}")
            rows.append(row)

    # These compositions are deliberately absent from the forward-model bank;
    # they form a deterministic unseen-degradation holdout.
    recipes = (
        (DegradationStep("rotate", (.37,)),
         DegradationStep("scan-noise", (1.35, 9101))),
        (DegradationStep("resize", (.63,)),
         DegradationStep("recompress", (47, 2))),
        (DegradationStep("sharpen", (.55, .8)),
         DegradationStep("alpha-roundtrip-error", (.42,))),
        (DegradationStep("palette", (9,)),
         DegradationStep("translate", (.31, -.27))),
    )
    degradation_rows = []
    dense = coverage_scene(779)
    for index, recipe in enumerate(recipes):
        first = render_synthetic(dense, RenderModel(), recipe,
                                 renderer="vice-analytic")
        second = render_synthetic(dense, RenderModel(), recipe,
                                  renderer="vice-analytic")
        deterministic = bool(np.array_equal(first, second))
        if not deterministic:
            failures.append(f"degradation determinism: recipe-{index}")
        degradation_rows.append({
            "recipe": [{"kind": item.kind, "parameters": item.parameters}
                       for item in recipe],
            "deterministic": deterministic,
            "sha256": hashlib.sha256(first.tobytes()).hexdigest(),
        })

    scene = canonical_smoke_scene()
    models = forward_model_catalog(
        ("clean-aa", "hard", "blur-0.6", "gamma-1.8", "jpeg-70"))
    selector_rows = []
    confidences = []
    outcomes = []
    calibration = ScoreCalibration()
    selector_root = args.out / "selector"
    selector_root.mkdir(exist_ok=True)
    for model in models:
        image = render_scene(scene, model=model)
        source = selector_root / f"{model.name}.png"
        Image.fromarray(image, "RGBA").save(source)
        winner, scores = select_forward_model(scene, decode_raster(source), models)
        values = np.asarray([item.nll for item in scores], np.float64)
        logits = -(values - values.min()) / max(1e-9, calibration.temperature)
        probabilities = np.exp(logits - logits.max())
        probabilities /= probabilities.sum()
        expected = next(index for index, item in enumerate(scores)
                        if item.model.name == model.name)
        confidence = float(probabilities[expected])
        correct = winner.model.name == model.name
        confidences.append(confidence); outcomes.append(float(correct))
        selector_rows.append({
            "source_model": model.name, "selected_model": winner.model.name,
            "correct": correct, "source_model_probability": confidence,
            "scores": {item.model.name: item.nll for item in scores},
        })
    oracle = run_oracle_diagnostics(args.out / "oracle")
    if oracle["proposal_family_recall_mean"] < 1.0:
        failures.append("proposal family recall below 1.0 on canonical family bank")
    if oracle["selector_exact_rate"] < 1.0:
        failures.append("real selector rejected an available oracle proposal")
    brier = float(np.mean((np.asarray(confidences) - np.asarray(outcomes)) ** 2))
    payload = {
        "schema": "vice-scene-synthetic-validation/1",
        "policy": "post-freeze metrics only; no tuning",
        "renderer_holdout": rows,
        "unseen_degradations": degradation_rows,
        "selector": {
            "rows": selector_rows,
            "accuracy": float(np.mean(outcomes)),
            "mean_source_probability": float(np.mean(confidences)),
            "brier": brier,
            "calibration_temperature": calibration.temperature,
        },
        "proposal_selector_separation": oracle,
        "failures": failures,
        "passed_invariants": not failures,
    }
    target = args.out / "synthetic_validation.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                 sort_keys=True) + "\n", encoding="utf-8")
    print(f"renderer families: {len(available_renderer_families())}")
    print(f"selector accuracy: {payload['selector']['accuracy']:.3f}")
    print(f"proposal family recall: {oracle['proposal_family_recall_mean']:.3f}")
    print(f"oracle-proposal selector rate: {oracle['selector_exact_rate']:.3f}")
    print(f"report -> {target}")
    for failure in failures:
        print(f"FAIL: {failure}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

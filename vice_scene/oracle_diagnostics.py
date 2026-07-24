"""Synthetic proposal/selector separation for the frozen ablation campaign.

The diagnostics deliberately use owned source scenes.  They answer two
different questions which ordinary end-to-end metrics conflate:

* did the scene proposal machinery contain a good explanation when an oracle
  (the exact source raster) selects from its candidates?;
* does the real forward-model selector choose the exact scene when the oracle
  proposal is present beside controlled wrong proposals?
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image

from .appearance import infer_appearances
from .contracts import GeometryPrimitive, RenderModel, SceneGraph
from .evidence_model import DeterministicEvidenceModel
from .ingest import decode_raster
from .optimizer import optimize_scenes
from .raster_profile import diagnose_raster
from .render_models import score_forward
from .scene_graph import SceneBuildResult, build_scene_graph, replace_shape_candidate
from .synthetic import (DegradationStep, canonical_smoke_scene, random_scene,
                        render_synthetic)
from .topology import build_topology_hypotheses


def run_oracle_diagnostics(output: Path, seeds: tuple[int, ...] = (19, 71, 193)) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    scenes = (canonical_smoke_scene(32),) + tuple(
        random_scene(seed, width=64, height=48, shape_count=5) for seed in seeds
    )
    for index, truth in enumerate(scenes):
        rows.append(_one_scene(truth, output / f"scene-{index:02d}", index))
    result = {
        "schema": "vice-scene-oracle-ablation/1",
        "policy": "owned-source-scenes-only; exact scene never used for training",
        "rows": rows,
        "proposal_family_recall_mean": float(np.mean(
            [row["proposal_oracle"]["family_recall"] for row in rows])),
        "selector_exact_rate": float(np.mean(
            [row["oracle_proposals_real_selector"]["exact_selected"] for row in rows])),
    }
    (output / "oracle_diagnostics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def _one_scene(truth: SceneGraph, root: Path, seed: int) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    clean_model = RenderModel("clean-aa", supersample=4, gamma=2.2)
    clean = render_synthetic(truth, clean_model, (), renderer="vice-analytic")
    clean_path = root / "clean.png"
    Image.fromarray(clean, "RGBA").save(clean_path)
    clean_raster = decode_raster(clean_path)

    profile, fields = diagnose_raster(clean_raster)
    evidence = DeterministicEvidenceModel().infer(clean_raster, fields)
    appearances = infer_appearances(clean_raster, profile, max_colors=24, seed=seed + 17)
    topologies = build_topology_hypotheses(appearances, evidence, top_k=4)
    builds = tuple(build_scene_graph(clean_raster, topology, appearances, evidence)
                   for topology in topologies)

    # Proposal court: the oracle may inspect the exact clean target but may
    # select only from graphs actually proposed by the engine.
    candidates: list[tuple[str, SceneGraph]] = []
    proposed_families: set[str] = set()
    for build_index, build in enumerate(builds):
        candidates.append((f"topology-{build_index}:initial", build.graph))
        for shape_id, alternatives in sorted(build.alternatives.items()):
            for rank, alternative in enumerate(alternatives):
                proposed_families.add(alternative.family)
                try:
                    graph = replace_shape_candidate(build.graph, shape_id, alternative)
                except ValueError:
                    continue
                candidates.append((f"topology-{build_index}:{shape_id}:{rank}:{alternative.family}",
                                   graph))
    scored = sorted((score_forward(graph, clean_raster, clean_model).nll, name)
                    for name, graph in candidates)
    exact_nll = score_forward(truth, clean_raster, clean_model).nll
    truth_families = {_canonical_family(shape.model_family) for shape in truth.shapes}
    canonical_proposed = {_canonical_family(family) for family in proposed_families}
    proposal = {
        "candidate_graphs": len(candidates),
        "truth_families": sorted(truth_families),
        "proposed_families": sorted(canonical_proposed),
        "family_recall": (len(truth_families & canonical_proposed) /
                          max(1, len(truth_families))),
        "oracle_selected": scored[0][1],
        "oracle_selected_nll": scored[0][0],
        "exact_scene_nll": exact_nll,
        "proposal_gap_to_exact": scored[0][0] - exact_nll,
    }

    # Selector court: the exact source scene is explicitly present alongside
    # controlled colour, geometry and draw-order errors.  The selector sees a
    # degraded raster and does not receive the source-scene identity.
    observed = render_synthetic(
        truth, RenderModel("synthetic-observed", supersample=4, gamma=2.2),
        (DegradationStep("gamma", (1.12,)),
         DegradationStep("jpeg", (82.0,))),
        renderer="pillow-polygon",
    )
    observed_path = root / "observed.png"
    Image.fromarray(observed, "RGBA").save(observed_path)
    observed_raster = decode_raster(observed_path)
    proposal_graphs = (("exact", truth), *_controlled_wrong_proposals(truth))
    oracle_builds = tuple(SceneBuildResult(graph, {}, {}, name)
                          for name, graph in proposal_graphs)
    selected = optimize_scenes(
        oracle_builds, observed_raster,
        ("clean-aa", "hard", "blur-0.6", "gamma-1.8", "jpeg-70"),
        enable_forward_court=True, max_local_moves=0,
    )
    chosen_index = int(selected.hypothesis.id.rsplit("-", 1)[-1])
    chosen_name = proposal_graphs[chosen_index][0]
    selector = {
        "proposal_names": [name for name, _graph in proposal_graphs],
        "selected": chosen_name,
        "exact_selected": chosen_name == "exact",
        "score": selected.hypothesis.score_breakdown.total,
        "runner_up": selected.runner_up_total,
        "render_model": selected.hypothesis.render_model.name,
    }
    return {"scene": seed, "size": [truth.width, truth.height],
            "proposal_oracle": proposal,
            "oracle_proposals_real_selector": selector}


def _controlled_wrong_proposals(scene: SceneGraph) -> tuple[tuple[str, SceneGraph], ...]:
    appearances = list(scene.appearances)
    first = appearances[0]
    rgba = list(first.rgba_linear)
    rgba[0] = float(np.clip(rgba[0] + (0.18 if rgba[0] < .72 else -.18), 0.0, 1.0))
    appearances[0] = replace(first, rgba_linear=tuple(rgba),
                             provenance=first.provenance + ("oracle-wrong-colour",))
    wrong_colour = replace(scene, appearances=tuple(appearances))
    wrong_colour.validate()

    loops = list(scene.loops)
    first_loop = loops[0]
    first_primitive = first_loop.primitives[0]
    shifted = _shift_primitive(first_primitive, 1.5, -1.0)
    loops[0] = replace(first_loop,
                       primitives=(shifted, *first_loop.primitives[1:]))
    wrong_geometry = replace(scene, loops=tuple(loops))
    wrong_geometry.validate()

    shapes = tuple(replace(shape, layer=len(scene.shapes) - 1 - shape.layer)
                   for shape in scene.shapes)
    edges = tuple(replace(edge, below=edge.above, above=edge.below)
                  for edge in reversed(scene.layer_edges))
    wrong_order = replace(scene, shapes=shapes, layer_edges=edges)
    wrong_order.validate()
    return (("wrong-colour", wrong_colour),
            ("wrong-geometry", wrong_geometry),
            ("wrong-order", wrong_order))


def _canonical_family(family: str) -> str:
    aliases = {"rect": "rectangle", "rounded-rect": "rounded-rectangle"}
    if family == "star" or family.startswith("star-"):
        return "star"
    return aliases.get(family, family)


def _shift_primitive(primitive: GeometryPrimitive, dx: float,
                     dy: float) -> GeometryPrimitive:
    points = tuple((x + dx, y + dy) for x, y in primitive.points)
    parameters = list(primitive.parameters)
    if len(parameters) >= 2 and primitive.kind in {
            "circle", "ellipse", "rect", "rounded-rect", "star"}:
        parameters[0] += dx
        parameters[1] += dy
    elif primitive.kind == "line" and len(parameters) >= 4:
        parameters[0] += dx; parameters[1] += dy
        parameters[2] += dx; parameters[3] += dy
    return replace(primitive, parameters=tuple(parameters), points=points,
                   provenance=primitive.provenance + ("oracle-wrong-shift",))


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path,
                        default=Path("benchmarks/scene_oracle_diagnostics"))
    args = parser.parse_args()
    result = run_oracle_diagnostics(args.out)
    print(json.dumps({key: value for key, value in result.items() if key != "rows"},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

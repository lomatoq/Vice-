"""End-to-end scene-first orchestration and legacy-compatible artifact contract."""

from __future__ import annotations

import json
import os
import time
import tracemalloc
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .appearance import infer_appearances
from .config import EngineConfig
from .contracts import SceneHypothesis, write_scene
from .evidence_cache import EvidenceCache
from .evidence_model import NeutralEvidenceModel, evidence_cache_key
from .neural_evidence import EvidenceModelSelection, select_best_evidence_model
from .export_scene import export_png, export_svg
from .idealize import idealize_scene
from .ingest import decode_raster
from .optimizer import assert_monotonic, optimize_scenes
from .raster_profile import diagnose_raster
from .render_models import (forward_model_catalog, marginalized_forward_nll,
                            score_forward, select_forward_model)
from .residual import residual_add_prune
from .scene_graph import SceneBuildCache, SceneBuildResult, build_scene_graph
from .text_scene import apply_exact_font_substitution, integrate_text_scene
from .topology import build_topology_hypotheses
from .trace import DecisionTrace, timed_stage


def process_scene(image_path: Path, output_root: Path, *, config: EngineConfig | None = None,
                  route: str = "auto") -> dict:
    """Public isolated API with an explicit, disabled-by-default legacy fallback."""
    resolved = config or EngineConfig()
    try:
        return _process_scene_impl(image_path, output_root, config=resolved, route=route)
    except Exception as exc:
        if not resolved.allow_legacy_fallback:
            raise
        from .legacy_adapter import run_legacy
        legacy = run_legacy(image_path, output_root,
                            mode=resolved.legacy_fallback_mode, route=route)
        fallback = {
            "schema": "vice-scene-fallback/1",
            "scene_error": f"{type(exc).__name__}: {exc}"[:1000],
            "legacy_mode": legacy.mode,
            "config_hash": resolved.hash,
        }
        legacy.output_directory.mkdir(parents=True, exist_ok=True)
        (legacy.output_directory / "scene_fallback.json").write_text(
            json.dumps(fallback, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        report = dict(legacy.report)
        report.update({"engine": "legacy-fallback", "scene_fallback": fallback})
        return report


def _process_scene_impl(image_path: Path, output_root: Path, *, config: EngineConfig,
                        route: str = "auto") -> dict:
    """Vectorize one raster into an immutable scene and standard V-ICE assets."""
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    tracemalloc.start()
    output = output_root / image_path.stem
    output.mkdir(parents=True, exist_ok=True)

    raster = decode_raster(image_path, max_pixels=config.max_input_pixels)
    trace = DecisionTrace(raster.source.source_hash, config.hash)
    trace.add("ingest", "canonical-decode", reason="one decode/crop/resize transform",
              outputs=("rgba_srgb_straight", "rgba_linear_premul", "oklab", "alpha_native"),
              format=raster.source.format, native_size=(raster.width, raster.height), route=route)

    with timed_stage(trace, "raster-profile"):
        profile, profile_fields = diagnose_raster(raster)
    trace.add("raster-profile", "diagnose", reason="spatial profile, never a global route switch",
              artwork_prob=profile.artwork_prob, text_prob=profile.text_probability,
              diagram_prob=profile.diagram_probability, gradient_prob=profile.gradient_probability)

    with timed_stage(trace, "evidence"):
        if config.enabled("evidence"):
            checkpoint = None
            if config.evidence_checkpoint:
                configured = Path(config.evidence_checkpoint)
                checkpoint = (configured if configured.is_absolute()
                              else Path(__file__).resolve().parent.parent / configured)
            evidence_selection = select_best_evidence_model(checkpoint)
            model = evidence_selection.model
        else:
            model = NeutralEvidenceModel()
            evidence_selection = EvidenceModelSelection(
                model, None, False, "evidence module disabled by ablation")
        key = evidence_cache_key(raster.source.source_hash, model.version,
                                 config.evidence_scales)
        cache = EvidenceCache(Path(__file__).resolve().parent.parent / ".vice_scene_cache")
        evidence = cache.load(key, source_hash=raster.source.source_hash,
                              model_version=model.version)
        cache_hit = evidence is not None
        if evidence is None:
            evidence = model.infer(raster, profile_fields, config.evidence_scales)
            cache.store(key, evidence)
    trace.add("evidence", "multi-head-inference", reason="frozen evidence API",
              accepted=True, cache_hit=cache_hit, model_version=evidence.model_version,
              checkpoint=evidence_selection.checkpoint,
              checkpoint_loaded=evidence_selection.checkpoint_loaded,
              fallback_reason=evidence_selection.fallback_reason,
              levels=len(evidence.levels), heads=sorted(evidence.levels[0].heads))

    with timed_stage(trace, "appearance"):
        appearances = infer_appearances(raster, profile, max_colors=config.max_colors,
                                        seed=config.random_seed)
    trace.add("appearance", "soft-mixture", reason="late palette projection",
              outputs=tuple(item.id for item in appearances.appearances),
              cluster_count=len(appearances.appearances),
              background_index=appearances.background_index)

    with timed_stage(trace, "topology"):
        topologies = build_topology_hypotheses(
            appearances, evidence,
            top_k=config.topology_k if config.enabled("topology") else 1,
            min_area_px=config.min_shape_area_px,
            max_regions=config.max_regions,
        )
    for topology in topologies:
        trace.add("topology", "hypothesis", reason="top-K split/merge proposal",
                  outputs=(topology.id,), score_after=topology.score,
                  region_count=len(topology.regions), operations=topology.operations)

    builds: list[SceneBuildResult] = []
    scene_build_cache = SceneBuildCache()
    with timed_stage(trace, "scene-build"):
        for topology in topologies:
            build = build_scene_graph(
                raster, topology, appearances, evidence,
                allow_gradients=config.enabled("appearance"),
                whole_shapes=config.enabled("whole_shapes"),
                shared_boundaries=config.enabled("shared_boundaries"),
                cache=scene_build_cache,
            )
            if config.enabled("text_scene"):
                graph, text_lines, exact_font_proposals = integrate_text_scene(
                    build.graph, topology, raster,
                    evidence.levels[0].heads["text_line_prob"],
                    glyph_occupancy=evidence.levels[0].heads["glyph_occupancy"],
                    stroke_centerline_prob=evidence.levels[0].heads["stroke_centerline_prob"],
                    stroke_half_width=evidence.levels[0].heads["stroke_half_width"],
                )
                build = replace(build, graph=graph)
                trace.add("text-scene", "font-free-path-B",
                          reason="line-level glyph scene with persistent counters",
                          text_lines=len(text_lines), glyphs=sum(len(line.glyphs) for line in text_lines),
                          exact_font_proposals=len(exact_font_proposals),
                          legacy_path_a_available=_legacy_font_available())
            builds.append(build)
            trace.add("scene-build", "assemble-vector-graph", outputs=(topology.id,),
                      shapes=len(build.graph.shapes), interfaces=len(build.graph.interfaces),
                      corners=len(build.graph.corners), constraints=len(build.graph.constraints))

    with timed_stage(trace, "optimizer"):
        optimized = optimize_scenes(
            tuple(builds), raster, config.forward_models,
            enable_forward_court=config.enabled("forward_court"),
        )
        assert_monotonic(optimized.audits)
    for audit in optimized.audits:
        trace.add("optimizer", audit.action, accepted=audit.accepted,
                  reason=audit.details, score_before=audit.score_before,
                  score_after=audit.score_after)
    trace.add("optimizer", "select-scene", reason="global posterior/MDL court",
              outputs=(optimized.hypothesis.id,),
              score_after=optimized.hypothesis.score_breakdown.total,
              runner_up=optimized.runner_up_total, abstained=optimized.abstained,
              abstain_reasons=optimized.abstain_reasons,
              render_model=optimized.hypothesis.render_model.name)

    graph = optimized.hypothesis.graph
    chosen_model = optimized.hypothesis.render_model
    score_fn = lambda candidate: score_forward(candidate, raster, chosen_model).nll
    font_path_supported = _exact_font_path_supported(graph)
    if (config.enabled("exact_font_path") and profile.text_probability >= .08
            and font_path_supported):
        with timed_stage(trace, "exact-font-path-A"):
            try:
                from .legacy_adapter import exact_font_substitutions
                font_substitutions = exact_font_substitutions(raster)
            except Exception as exc:
                font_substitutions = []
                trace.add("exact-font-path-A", "adapter-failure", accepted=False,
                          reason=f"fail-open: {type(exc).__name__}: {exc}"[:300])
            for substitution in font_substitutions:
                trial = apply_exact_font_substitution(graph, substitution)
                if trial is None:
                    continue
                before = score_fn(graph)
                after = score_fn(trial)
                # Existing Path A already passed OCR/font/topology/boundary walls;
                # the scene court adds a final global-render rollback.
                accepted = after <= before + .00075
                trace.add("exact-font-path-A", "font-outline-hypothesis",
                          accepted=accepted, reason="strict silhouette + global forward court",
                          score_before=before, score_after=after,
                          font=substitution.get("font"), text=substitution.get("text"),
                          iou=substitution.get("iou"))
                if accepted:
                    graph = trial
    elif config.enabled("exact_font_path") and profile.text_probability >= .08:
        trace.add("exact-font-path-A", "skip", accepted=False,
                  reason="no line with >=3 glyphs at >=14px native ink height")
    if config.enabled("idealization"):
        with timed_stage(trace, "idealization"):
            graph, idealization_audits = idealize_scene(
                graph, score_fn,
                symmetry_evidence=evidence.levels[0].heads["symmetry_evidence"],
            )
        for audit in idealization_audits:
            trace.add("idealization", audit.action, accepted=audit.accepted,
                      reason="accuracy-budgeted snapshot/rollback",
                      inputs=audit.affected, score_before=audit.score_before,
                      score_after=audit.score_after)
        if not idealization_audits:
            trace.add("idealization", "no-change", reason="no supported idealization move")

    if config.enabled("residual_repair"):
        with timed_stage(trace, "residual"):
            graph, residual_audits = residual_add_prune(
                graph, raster, score_fn, threshold=config.residual_add_threshold,
                min_area_px=config.residual_min_area_px,
                max_additions=config.residual_max_additions,
                max_attempts=config.residual_max_attempts,
            )
        for audit in residual_audits:
            trace.add("residual", audit.action, accepted=audit.accepted,
                      reason=audit.reason, score_before=audit.score_before,
                      score_after=audit.score_after, area_px=audit.area_px)
        if not residual_audits:
            trace.add("residual", "no-change", reason="no supported residual component")

    with timed_stage(trace, "final-court"):
        final_models = (forward_model_catalog(config.forward_models)
                        if config.enabled("forward_court")
                        else (chosen_model,))
        final_forward, forward_scores = select_forward_model(
            graph, raster, final_models)
    final_hypothesis = SceneHypothesis(
        id=optimized.hypothesis.id, graph=graph, render_model=final_forward.model,
        evidence_refs=optimized.hypothesis.evidence_refs,
        score_breakdown=replace(optimized.hypothesis.score_breakdown,
                                render_nll=marginalized_forward_nll(forward_scores)),
        provenance=optimized.hypothesis.provenance + ("final-forward-court",),
    )
    trace.add("final-court", "select-render-model", reason="renderer-model marginalization",
              render_model=final_forward.model.name, score_after=final_forward.nll,
              candidates={item.model.name: item.nll for item in forward_scores})

    with timed_stage(trace, "export"):
        export_svg(output / "03_rebuilt_filled.svg", graph, mode="stacked",
                   gap_filler=config.enabled("gap_filler"))
        export_svg(output / "02_primitive_map.svg", graph, mode="stacked",
                   gap_filler=False, primitive_map=True)
        export_png(output / "03_rebuilt_filled.png", graph, scale=4, antialias=True)
        export_png(output / "03_rebuilt_filled_native.png", graph, scale=1, antialias=False)
        export_png(output / "03_rebuilt_filled_4x_aliased.png", graph, scale=4,
                   antialias=False)
        _write_primitive_map_png(output / "02_primitive_map.png", graph)
        _write_contour_preview(output / "01_contour.png", raster, graph)
        _write_corner_preview(output / "04_corners.png", raster, graph)
        write_scene(output / "scene.json", graph)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - started_wall
    primitive_counts = Counter(primitive.kind for loop in graph.loops for primitive in loop.primitives)
    family_counts = Counter(shape.model_family for shape in graph.shapes)
    report = {
        "engine": "vice-scene",
        "engine_version": config.engine_version,
        "config_hash": config.hash,
        "source_hash": raster.source.source_hash,
        "extractor_used": f"scene:{evidence.model_version}",
        "analysis_scale": 1,
        "regions": len(graph.shapes),
        "closed_contours": len(graph.loops),
        "rendered_primitive_count": sum(primitive_counts.values()),
        "actual": dict(sorted(primitive_counts.items())),
        "templates": dict(sorted(family_counts.items())),
        "topology_hypotheses": len(topologies),
        "interfaces": len(graph.interfaces),
        "corners": len(graph.corners),
        "constraints": len(graph.constraints),
        "render_model": final_forward.model.name,
        "render_nll": marginalized_forward_nll(forward_scores),
        "render_map_nll": final_forward.nll,
        "abstained": optimized.abstained,
        "abstain_reasons": list(optimized.abstain_reasons),
        "worst_window": final_forward.worst_window,
        "cache_hit": cache_hit,
        "resource": {
            "wall_seconds": elapsed,
            "cpu_seconds": time.process_time() - started_cpu,
            "tracemalloc_current_bytes": current,
            "tracemalloc_peak_bytes": peak,
            "pid": os.getpid(),
        },
        "profile": {
            "artwork_prob": profile.artwork_prob,
            "photo_prob": profile.photo_prob,
            "text_probability": profile.text_probability,
            "diagram_probability": profile.diagram_probability,
            "gradient_probability": profile.gradient_probability,
            "transparency_probability": profile.transparency_probability,
        },
        "artifacts": {
            "scene": "scene.json", "trace": "decision_trace.json",
            "config": "config.json", "profile": "profile.json",
        },
    }
    (output / "config.json").write_text(config.canonical_json() + "\n", encoding="utf-8")
    (output / "profile.json").write_text(json.dumps(asdict(profile), ensure_ascii=False,
                                                      indent=2, default=_json_default) + "\n",
                                           encoding="utf-8")
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
    trace.add("export", "publish-artifacts", reason="legacy-compatible names + canonical scene",
              outputs=tuple(report["artifacts"].values()), wall_seconds=elapsed)
    trace.write(output / "decision_trace.json")
    return report


def _write_contour_preview(path: Path, raster, graph) -> None:
    rgba = (raster.rgba_srgb_straight * 255 + .5).astype(np.uint8)
    base = Image.new("RGB", (raster.width, raster.height), "white")
    source = Image.fromarray(rgba, "RGBA")
    base.paste(source, mask=source.getchannel("A"))
    draw = ImageDraw.Draw(base)
    from .shape_models import primitive_points
    loops = {item.id: item for item in graph.loops}
    for shape in graph.shapes:
        for loop_id in (shape.positive_loop, *shape.negative_loops):
            points = []
            for primitive in loops[loop_id].primitives:
                points.extend(primitive_points(primitive, 96).tolist())
            if len(points) >= 2:
                draw.line([tuple(row) for row in points] + [tuple(points[0])],
                          fill=(20, 20, 20), width=1)
    base.resize((raster.width * 4, raster.height * 4), Image.Resampling.NEAREST).save(path)


def _write_corner_preview(path: Path, raster, graph) -> None:
    rgba = (raster.rgba_srgb_straight * 255 + .5).astype(np.uint8)
    image = Image.fromarray(rgba, "RGBA").resize((raster.width * 4, raster.height * 4),
                                                  Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(image)
    for corner in graph.corners:
        x, y = corner.position[0] * 4, corner.position[1] * 4
        radius = 2.5 if corner.role == "junction" else 1.7
        draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                     fill=(30, 115, 255, 255), outline=(255, 255, 255, 255))
    image.save(path)


def _write_primitive_map_png(path: Path, graph) -> None:
    from .shape_models import primitive_points
    colors = {"line": (38, 99, 235, 255), "circle": (245, 145, 30, 255),
              "ellipse": (245, 145, 30, 255), "rect": (22, 163, 74, 255),
              "rounded-rect": (22, 163, 74, 255)}
    image = Image.new("RGBA", (graph.width * 4, graph.height * 4), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    for loop in graph.loops:
        for primitive in loop.primitives:
            points = primitive_points(primitive, 96)
            if len(points) >= 2:
                scaled = [(float(x * 4), float(y * 4)) for x, y in points]
                if primitive.kind not in {"line", "quadratic", "cubic"}:
                    scaled.append(scaled[0])
                draw.line(scaled, fill=colors.get(primitive.kind, (196, 57, 173, 255)), width=2)
    image.save(path)


def _legacy_font_available() -> bool:
    try:
        from .legacy_adapter import legacy_exact_font_available
        return legacy_exact_font_available()
    except Exception:
        return False


def _exact_font_path_supported(graph) -> bool:
    """Gate the expensive OCR/font catalog path on resolvable native text.

    Windows OCR is not reliable below roughly 14 px of ink height.  The
    font-free path remains active there; spending seconds on an empty exact
    font court cannot improve the scene.
    """
    from .shape_models import primitive_points
    loops = {loop.id: loop for loop in graph.loops}
    groups: dict[str, list] = {}
    for shape in graph.shapes:
        if not shape.model_family.startswith("glyph") or not shape.semantic_group:
            continue
        points = [primitive_points(primitive, 48)
                  for primitive in loops[shape.positive_loop].primitives]
        points = [row for row in points if len(row)]
        if points:
            groups.setdefault(shape.semantic_group, []).append(
                (shape.topology_id, np.vstack(points)))
    for rows in groups.values():
        glyphs = {topology_id for topology_id, _points in rows}
        cloud = np.vstack([points for _topology_id, points in rows])
        height = float(np.max(cloud[:, 1]) - np.min(cloud[:, 1]))
        width = float(np.max(cloud[:, 0]) - np.min(cloud[:, 0]))
        if len(glyphs) >= 3 and height >= 14.0 and width >= 20.0:
            return True
    return False


def _json_default(value):
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(type(value).__name__)

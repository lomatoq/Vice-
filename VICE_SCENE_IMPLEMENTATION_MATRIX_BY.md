# V-ICE Scene Engine — implementation matrix

Source of truth: `VectorizerAI_clean_room_reverse_engineering_plan_by.md`.
This matrix records implementation, the short build-phase exit check, and the
post-freeze validation obligation.  A module being implemented is not a claim
that it beats Vectorizer.AI; promotion is decided only by the frozen campaign
and the human court.

| Build | Required capability | Implementation | Build-phase exit evidence | Status before freeze |
|---|---|---|---|---|
| 1. Contracts and scene graph | Immutable IDs; raster/profile; evidence pyramid; shape/interface/constraint graph; topology, layer DAG, provenance | `vice_scene/contracts.py`, `scene_graph.py`, `trace.py` | JSON round-trip, render, duplicate/reference/parent-cycle/DAG guards in `test_scene_engine.py` | Implemented |
| 2. Canonical ingest | Decoders, EXIF, ICC policy, alpha cleanup, one transform, linear premultiplied/native coordinates | `vice_scene/ingest.py`, `raster_profile.py` | PNG/JPEG/WebP/BMP/TIFF/GIF, fractional crop, EXIF, transparent-RGB and pixel-centre checks | Implemented |
| 3. Synthetic data and renderer factory | Scene generator, independent renderers, degradations, exact labels, deterministic manifest/provenance | `vice_scene/synthetic.py`, `training_data.py`, `font_synthetic.py`, `generate_scene_evidence_dataset.py` | Exact manifest reproduction; feature-dense scene; analytic/Pillow/OpenCV adapters | Implemented |
| 4. Evidence backbone | Boundary/normal/offset/coverage, region/color, corner/junction, shapes, text/stroke/symmetry, uncertainty | `vice_scene/neural_evidence.py`, `evidence_model.py`, `evidence_cache.py`, `train_scene_evidence.py` | All head shape/range checks and candidate-checkpoint round trip | Implemented; no checkpoint is promoted without validation |
| 5. Appearance hypotheses | Solid/linear/radial/alpha, mixture uncertainty, late palette, gradient-vs-region MDL | `vice_scene/appearance.py` | Analytic gradient fit and AA/composite-colour suppression fixtures | Implemented |
| 6. Topology hypothesis builder | Component tree, RAG, top-K split/merge, holes/containment, occlusion, tiny shapes | `vice_scene/topology.py` | Canonical hole/adjacency/containment/occlusion and sparse-membership fixtures | Implemented |
| 7. Whole-shape solver | Published shape families plus rings/ribbons, covariance, digital preimage, serialization | `vice_scene/shape_models.py` | Exact tournament winner for circle, ellipse, rectangle, rounded rectangle, triangle, isosceles triangle, quadrilateral, stars 3–6, D, ring and ribbon | Implemented |
| 8. Shared-boundary solver | Interface-once geometry, physical arclength, line/arc/ellipse/Q/C, DP adapter, corridors, corners/junctions | `vice_scene/boundary_solver.py`, `corner_graph.py` | Shared-interface singleton, analytic arc vocabulary and lattice-invariant physical cost | Implemented |
| 9. Text scene | Line proposals, joint colour/coverage, exact-font A, font-free B, repeated prototypes, counters, top layer | `vice_scene/text_scene.py`, `font_synthetic.py`, `legacy_adapter.py` | Synthetic font outlines, font-free component/counter preservation, exact-font graph substitution | Implemented |
| 10. Global optimizer and idealizer | Graph/layer moves, continuous fits, local re-fit, symmetry/repetition/fairing, uncertainty simplification, topology gates, abstention | `vice_scene/optimizer.py`, `idealize.py` | Monotonic-objective guard, accepted/rejected rollback audits, draw-order court | Implemented |
| 11. Forward-model court | AA, gamma/PSF, alpha compositing, JPEG scoring, marginalization, calibration | `vice_scene/render_models.py` | Tiny known-renderer selection and premultiplied-alpha exactness | Implemented |
| 12. Residual add/prune | Residual components, missing shape/hole, artifact rejection, prune, immutable baseline | `vice_scene/residual.py` | Add-one and remove-one fixtures with graph-reference validation | Implemented |
| 13. Export and cleaned PNG | Canonical renderer; SVG/EPS/PDF/DXF; cutout/stacked; grouping; preserve/flatten; curve fallback; gap fill; AA/hard PNG | `vice_scene/export_scene.py`, `gap_filler.py` | Native SVG primitives, real vector cutout masks, flattened fallback, schema/round-trip and native/4×/custom PNG checks | Implemented |
| 14. Integration and traceability | CLI/API/UI route; explicit legacy fallback; cache; isolation; full trace; ablations; resources | `vice_scene/pipeline.py`, `__main__.py`, `config.py`, `freeze.py`, `benchmark_vai.py`, `eval_one_item.py`, `challenge_eval.py`, `run_vectorizer.py`, `web_preview/*` | End-to-end 32×32 smoke, deterministic artifacts, fallback contract, stage/resource trace | Implemented |

## Build-freeze and validation contract

- `python -m vice_scene.freeze --write` records code/model/config/plan and
  corpus hashes in `BUILD_FREEZE.json`.
- `validate_scene_campaign.py` refuses to start if any frozen input changed.
- The campaign runs the synthetic oracle/build suite, legacy regressions,
  stage suite, VAI50, the 115-item pack, structural SVG forensics, automatic
  module/pair/legacy/oracle ablations, and builds the resolution-honest blind
  crop court.
- `Best` remains the incumbent route until the human court and all promotion
  gates pass.  This prevents an experimental scene engine from silently
  regressing production output.

## Deliberate clean-room boundary

Vectorizer.AI SVGs are evaluation-only.  Dataset generation and evidence
training accept owned synthetic source scenes and caller-licensed fonts; they
do not ingest VAI geometry as labels.  Structural forensics records observable
output properties only and does not claim access to a proprietary
implementation.

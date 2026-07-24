# V-ICE Scene Engine — frozen implementation and mathematics audit

Freeze: `33bc0d63e4b82734bcb5349f5d19385ac16b0fbdc6e31074814728c90238758f`

Policy: this document records evidence only.  No frozen source, config, model,
or corpus was tuned while the validation campaign was running.

## Executive verdict

The 14 short build-phase exits are implemented and their isolated fixtures pass.
That does **not** mean the full plan is substantively complete.  The frozen real
campaign demonstrates that the current Scene Engine is neither competitive with
Vectorizer.AI nor production-safe.  It must stay experimental and must not replace
the incumbent `Best` route.

At the first 28 equal-input VAI cases:

- ink IoU: Scene wins `1/28`; median `0.7229` versus VAI `0.9613`;
- SSIM: Scene wins `0/28`; median `0.6805` versus `0.9650`;
- boundary F: Scene wins `0/28`; median `0.9012` versus `1.0000`;
- Hausdorff95: Scene wins `0/28`; median `3.965 px` versus `0 px`;
- seams: Scene mean `28.3932 px²` versus `0.3171 px²`;
- kinks/100 px: Scene mean `27.2288` versus `3.3809`;
- every completed Scene row has a non-zero catastrophic-locus rate;
- a 2430×2430 sheet exceeded `40.24 GiB` worker RSS and had to be terminated
  before system OOM; it is recorded as a failed item, not omitted.

The apparent wins in `wobble` and `g2_steps` are not evidence of superior
geometry: heavily simplified, missing, or semantically destroyed shapes can have
low curve wobble.  The fidelity, topology, text, and local-catastrophe meters show
the actual defeat.

## Build-by-build completeness

| Build | Formal exit | Substantive plan target | Frozen assessment |
|---|---:|---:|---|
| 1 Contracts/graph | PASS | Mostly present | Complete enough as infrastructure |
| 2 Canonical ingest | PASS | Present | Complete enough as infrastructure |
| 3 Synthetic factory | PASS | Real diverse training corpus | Partial: generators/labels exist, but only smoke-scale evidence exists |
| 4 Evidence backbone | PASS | Trained multi-head evidence | Partial: no promoted `scene_evidence` checkpoint; production uses deterministic heuristics |
| 5 Appearance | PASS | Coverage-aware late appearance inference | Partial: opaque RGB/JPEG antialias coverage is not inferred |
| 6 Topology | PASS | Real top-K split/merge graph search | Partial: four fixed argmax/blur/morph variants, not a combinatorial graph court |
| 7 Whole shapes | PASS | Accurate and efficient whole-object recovery | Partial: families exist, but fragmentation and full-canvas tournaments dominate real cases |
| 8 Shared boundaries | PASS | One interface = one exported geometry | Partial: interfaces are metadata; final shapes/export still render independent loops |
| 9 Text scene | PASS | Joint line/glyph/counter reconstruction | Partial: weak font-free silhouettes and rarely successful exact-font substitution |
| 10 Optimizer/idealizer | PASS | Joint discrete/continuous factor optimization | Partial: at most 24 local reclassifications and ±1 layer moves; symmetry may remain metadata |
| 11 Forward court | PASS | Renderer-aware selection correlated with perception | Partial: low NLL accepts visibly destroyed text and structural artifacts |
| 12 Residual repair | PASS | Local, bounded add/prune | Partial: repeated global renders make it extremely slow and can add colored barnacles |
| 13 Export | PASS | Faithful editable multi-format output | API present; real structural/fidelity gates fail |
| 14 Integration/trace | PASS | Production-safe jobs, budgets and diagnostics | Partial: synchronous 20-minute UI/server timeout, timeout retry, no progress/cancel contract |

Thus “implemented” in `VICE_SCENE_IMPLEMENTATION_MATRIX_BY.md` means that a
module/API and its narrow exit fixture exist.  It is not a claim that the plan's
real-world capability has been achieved.

## P0 mathematical and architectural defects

### 1. Antialias coverage and subpixel offset are mathematically wrong for opaque images

`vice_scene/evidence_model.py:128` computes
`subpixel = (0.5 - alpha) * normal`.  On an ordinary opaque PNG/JPEG,
`alpha = 1` everywhere, so the model emits a spurious `-0.5 px` offset at every
edge.  At `evidence_model.py:154`, `coverage_alpha` is just file alpha, not
foreground/background mixture coverage.  RGB antialias pixels therefore become
appearance regions/shapes instead of subpixel evidence.  The destroyed tiny
Mercedes case (109 shapes in 467.9 s) is a direct example.

Required correction: estimate edge coverage jointly from local foreground and
background colors in linear premultiplied space; keep file alpha and rasterizer
coverage as separate variables; validate signed offsets against analytic
subpixel oracle labels.

### 2. Most promised evidence heads are dead outputs

The model emits `subpixel_offset`, `coverage_alpha`, `shape_class_logits`,
`glyph_occupancy`, `stroke_centerline_prob`, `stroke_half_width`, and
`symmetry_evidence`, but the production graph does not consume them.  Real
consumers are mainly boundary/uncertainty and `text_line_prob`.  Tensor range
tests therefore passed while the heads had no causal effect.

Required correction: add a consumer/ablation contract for every head.  A head is
not implemented until turning it off changes a targeted oracle and the expected
real slice.

### 3. “Top-K topology” is not top-K split/merge inference

`vice_scene/topology.py:91-105` creates argmax, Gaussian sigma 0.65/1.15, and one
morphological-close variant.  With `min_area_px = 0.125`, antialias/noise fragments
survive as regions.  There is no best-first split/merge search over a region graph
with topology, coverage, and semantic costs.

Required correction: region-adjacency proposal queue with explicit merge, split,
hole, occlusion-completion, and text-group moves; deduplicate by graph canonical
form; use calibrated proposal recall and oracle-selector diagnostics.

### 4. Shared interfaces do not own exported geometry

`scene_graph.py` computes interface objects, but `export_scene.py` and the forward
renderer use each shape's independent `graph.loops`.  “One interface, one
geometry” is therefore descriptive metadata rather than the geometry source of
truth.  This permits duplicate borders, cracks, and inconsistent adjacent curves.

Required correction: store each boundary segment once with oriented references
from both incident faces; assemble shape cycles from shared segments at render and
export time; reject non-manifold or duplicate interface ownership.

### 5. The optimizer is local enumeration, not a global scene optimizer

`optimizer.py` caps work at 24 shape moves and tests only the current layer or
one neighboring layer.  Constraints mostly enter as a small scalar bonus.
`idealize.py` detects mirror symmetry after geometric passes and appends a
constraint without applying mirrored geometry.  There is no continuous joint fit
of shared control points, radii, baselines, widths, gaps, and layer/order.

Required correction: sparse factor graph with robust raster/boundary factors,
hard topology walls, shared parameters for repetition/symmetry, alternating
discrete proposals and bounded local continuous solves, with snapshot rollback.

### 6. Text is handled too late and too weakly

General scene segmentation first fragments antialiased glyphs.  Font-free Path B
then works mostly from masks/SDF offsets; baseline, stem, repetition, counter and
spacing constraints are not jointly fit.  Exact-font Path A often produces no
proposal.  The 289×228 Mastercard source required 2457.1 s, returned 248
primitives and `abstained=false`; the word `mastercard` is visually destroyed
despite render NLL `0.0467`.

Required correction: detect text groups before general color-region expansion;
infer glyph components and counters jointly; share stem/baseline/x-height/spacing
parameters; court exact-font and font-free line hypotheses against structural,
OCR, local-boundary and topology objectives rather than global NLL alone.

### 7. Candidate and residual courts have full-canvas complexity

`shape_models.py:759` allocates a supersampled full-image canvas for candidate
rendering.  This is repeated across families and regions.  Residual add/prune and
optimizer trials repeatedly render the complete scene.  On fragmented images the
cost grows with candidates × shapes × models × full-canvas pixels.

Observed examples:

- `plankgaming_512`: 2026.0 s;
- `betsoft_512`: 2011.5 s, 366 primitives, ink IoU `0.0847` versus VAI `0.9966`;
- `icon_group_3_2`: 1137.2 s;
- `icon_group_1` Mastercard: 2457.1 s;
- `SYNTH_SHEET`: >1010 s and >40.24 GiB RSS before termination.

Required correction: bbox-local distance-transform scoring, cached compositing,
incremental dirty rectangles, strict proposal budgets, early semantic lanes,
per-stage wall/memory limits, and a quality-preserving fast fallback.

### 8. Abstention measures ambiguity, not absolute failure

The current rule abstains only when the best and runner-up totals are within
`0.0025`.  Two equally bad hypotheses can have a larger gap; catastrophic outputs
therefore report high confidence.  No completed observed case abstained, including
the examples above.

Required correction: calibrated absolute failure model using worst-locus damage,
topology persistence, component census, glyph catastrophe, structural explosion,
resource projection, and out-of-distribution evidence—not posterior gap alone.

### 9. Existing aggregate metrics can reward degenerate output

Whole-image IoU/SSIM/NLL and curve smoothness hide missing objects, destroyed text,
or simplification.  The old `Best` stage suite similarly had high IoU while
failing topology and exploding to hundreds of micro-shapes.

Required promotion objective: lexicographic hard gates for topology, glyph
catastrophe, local worst-window damage, duplicate/shared-boundary integrity,
editability/shape explosion, and resource budgets; only then optimize perceptual
and smoothness scores.

### 10. Browser transport guarantees `Failed to fetch` on slow items

`web_preview/app.js:26-27` aborts after 20 minutes.  `web_preview/server.py:85-99`
also applies a 20-minute worker timeout and retries once, so a request can be
aborted while the server burns another 20 minutes.  Mastercard's frozen 40.95
minute runtime reproduces the user's observed failure exactly.

Required correction: asynchronous job IDs, progress events, cancellation, one
global budget, atomic publishing, no retry on deterministic timeout/OOM, and a
bounded fallback result that the UI can display.

## Promotion decision

`DO_NOT_PROMOTE`.  Keep `Best` as default and label Scene Engine experimental.
The campaign must still account for all 50 items, the 115 blind pack, ablations,
oracles, forensics, and the resolution-honest human court.  Those remaining runs
are diagnostic obligations; they cannot reverse the already-failed P0 promotion
gates without a new build and a new freeze.

## What the clean-room VAI SVG forensics actually supports

The supplied forensics tool inspected 131 real VAI SVGs.  Observable export
facts—not claims about proprietary internals—are:

- 125/131 files contain filled compound paths with multiple subpaths;
- 81/131 are conservatively classified cutout-like; the other 50 are mixed;
- only 17/131 use native SVG circle/ellipse/rect-style elements;
- command totals are `C 36,288`, `Q 28,038`, `L 19,399`, `A 12,294`;
- median graphics count is 18 (mean 59.5; tail max 2050);
- only 13/131 show likely early non-scaling gap-filler strokes;
- groups/transforms are also rare (13/131).

This supports a scene/shape inference model followed by an output-representation
transform: VAI is not merely exporting detected native primitives, not merely
Potrace contours, and not using gap-filler strokes as a universal repair.  Its
fast idealization is most plausibly achieved by proposing low-dimensional whole
objects/text groups early and optimizing local evidence, then serializing them
mostly as compound paths.  Our frozen engine instead creates many color regions
first and tries to recover semantics afterward, which is both slower and less
stable.

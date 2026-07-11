# Corner Dataset V2

Dataset V2 learns the perceptual distinction between a real corner and a
pixel staircase. Ground truth comes from SVG structure, not from a detector.

## Definition

- `0` — negative boundary vertex. This includes every raster stair-step,
  straight section, smooth Bézier/arc and rounded join.
- `1` — structural corner: a visible C0 discontinuity between SVG tangents.
- `2` — occlusion corner: a visible corner introduced by another painted
  shape clipping the current shape.

Rounded extrema are never positive merely because they accumulate a large
turn. Short alternating line staircases are rejected using signed-turn
coherence. Labels are generated independently at 24, 32, 48, 64, 96, 128,
192 and 256 px, so a feature may disappear at a small operating scale.

SVGs containing transforms, clip paths, masks, filters or `<use>` references
are currently rejected and counted in the manifest. This keeps the first
dataset label-clean; support can be added later without contaminating V2.

## Pilot

```powershell
python build_corner_dataset.py --files 80 --preview-files 80
```

- Dataset: `datasets/corner_gt_v2_pilot/manifest.json`
- Review: <http://localhost:8877/corner-dataset/>
- Review decisions are kept in browser local storage. Use **Export review
  JSON** to persist/send them.

The review uses red dots for structural corners, magenta for occlusion corners
and blue for the complete boundary. Images are nearest-neighbour enlarged so
the negative raster staircase remains visible.

### Fixing labels in the review

- Select **+ structural** and click close to a blue boundary vertex to add a
  missed real corner.
- `Shift+click` (or select **+ occlusion**) adds an occlusion corner.
- Right-click (or select **remove**) deletes the nearest corner.
- **Save review** writes decisions and corrections to
  `datasets/corner_gt_v2_pilot/review.json`.

The CNN loader applies these overrides by `(file, resolution, loop, vertex)`;
they are training labels, not visual-only marks. Rejected icon cards are skipped
by the loader. **Export JSON** remains available as a portable backup.

## CNN training

```powershell
python corner_cnn.py --train `
  --svg-gt datasets/corner_gt_v2_pilot `
  --svg-gt-repeat 1 `
  --cache datasets/corner_gt_v2_train_cache.pkl
```

Only the dataset's `train` split is loaded. Structural and occlusion labels are
both positive for the current binary CNN, while their original types remain in
the NPZ shards for separate evaluation.

## Focused incremental training

Large logos are not the first source to annotate when a failure can be covered by
exact procedural data.  The CNN trainer can add:

- a deterministic Arial single-glyph bank at 12--128 px (`--paper-letters`);
- thin rectangles, diamonds, trapezoids, chevrons, notches and zigzags;
- round-capped quadratic/S-curve negatives for smooth ribbon boundaries.

Always write a candidate checkpoint and compare it before promotion:

```powershell
python corner_cnn.py --train `
  --out models/corner_cnn_focused_candidate.pt `
  --init models/corner_cnn.pt --lr 0.0001 --epochs 2 `
  --shapes 3000 --neg 3500 --text 1200 --corpus 0 `
  --paper 1 --paper-letters 2 `
  --svg-gt datasets/corner_gt_v4_perceptual_events --svg-gt-repeat 2 `
  --cache tmp/corner_focused_cache.pkl

python compare_corner_detectors.py `
  --model models/corner_cnn.pt `
  --model models/corner_cnn_focused_candidate.pt `
  --out benchmarks/corner_detector_focused_comparison.json

python benchmark_focused_synth.py `
  --model models/corner_cnn.pt `
  --model models/corner_cnn_focused_candidate.pt `
  --out benchmarks/focused_synth_comparison.json
```

The checkpoint now records its training config, source-tag counts, vertex count
and positive rate.  Do not replace `models/corner_cnn.pt` unless both the reviewed
event split and the focused held-out letters/curves improve.

## Parameterised primitive corpus

`generate_primitive_corpus.py` creates small, label-clean SVGs instead of asking
for whole logos to be annotated.  Its grammar contains four explicit event
classes:

- smooth: ellipses, rings, rounded rectangles and round-cap arc ribbons;
- structural: thin quads, polygons, stars, zigzags, chevrons, notches, steps
  and crosses;
- mixed: line/arc D-shapes, half-discs, flat capsules and cusp teardrops;
- occlusion: overlapping circles, circle/bar cuts, T/X junctions and
  multi-colour fan shapes.

The generator writes deterministic `train`, `val` and `test` directories plus a
manifest containing every parameter.  One SVG is later rasterised at all
resolutions, so variants of the same shape cannot leak between splits.

```powershell
python generate_primitive_corpus.py `
  --out datasets/primitive_svg_v1 --count 20000 --seed 20260711

python build_corner_dataset.py `
  --root datasets/primitive_svg_v1 `
  --out datasets/primitive_corner_v1 `
  --preview test_runs/primitive_corner_v1_review `
  --resolutions 12,16,20,24,32,48,64,96,128,192,256 `
  --allow-empty-resolutions
```

`--allow-empty-resolutions` is important for 1--2 px strokes: it skips only a
scale where the complete shape vanished, rather than rejecting its useful
higher-resolution samples.

Training can combine the reviewed logo/event set and the generated primitives
in one candidate checkpoint:

```powershell
python corner_cnn.py --train `
  --out models/corner_cnn_primitives_candidate.pt `
  --init models/corner_cnn.pt --lr 0.0001 --epochs 2 `
  --text-corpus 5000 `
  --svg-gt datasets/corner_gt_v4_perceptual_events `
  --svg-gt datasets/primitive_corner_v1 `
  --svg-gt-repeat 1 `
  --paper 1 --paper-letters 2
```

The existing font corpus is still useful, but it is not a substitute for this
grammar: letters cover counters and terminals; primitives cover smooth-versus-
sharp joins, thin geometry, junctions and occlusion events independently.

`--text-corpus` is explicit because the existing icon corpus loader never read
`C:/Users/nirrt/Toolset/v-ize train/dataset/text_shapes/svg`.  The new loader
samples all 45 font directories evenly and uses a stable 80/10/10 path hash;
training reads only the 80% split.  `--text` remains the smaller on-the-fly bank
rendered from Windows font files, and both sources can be used together.

## Balanced batched fine-tuning

Variable loop lengths now support exact per-example circular padding inside a
length-bucketed batch.  Positions beyond each true loop length are masked from
the loss, and frozen BatchNorm retains the production checkpoint statistics.
The batched forward is regression-tested against individual forwards.

```powershell
python corner_cnn.py --train `
  --out models/corner_cnn_hybrid_large_v1.pt `
  --init models/corner_cnn.pt --lr 0.00003 --epochs 2 `
  --pos-weight-scale 0.20 --batch-size 16 `
  --balanced-sampling --freeze-bn `
  --cache tmp/corner_primitives_candidate_cache.pkl
```

The balanced epoch policy is 30% primitive families (uniform within family),
30% reviewed SVG events, 15% real/synthetic text, 15% smooth negatives, 5%
structural synthesis and 5% paper/auxiliary data.  On the 38,174-loop cache this
reduced two epochs from about 13 minutes to 53 seconds on an RTX 4070.

Production uses one model per loop, not an ensemble: the original CNN at 0.28
for extent <=4 px or boundary density >8 vertices/px, and the new large-loop
checkpoint at 0.36 otherwise.  The policy was selected on val and then passed
both untouched test splits.

## Review-first single-glyph pilot

The first text follow-up is intentionally small: 30 Arial glyph SVGs (`A-Z`
plus `a/e/g/o`) at six operating resolutions (`12,16,20,24,32,48`), for 180
reviewable views.  Unlike the legacy `--text-corpus` path, the pilot is built
with `svg_corner_gt.py` exact C0 joins and paper-compatible short-span events.

```powershell
python generate_glyph_pilot.py

python build_corner_dataset.py `
  --root datasets/text_glyph_pilot_sources `
  --out datasets/corner_gt_text_glyph_pilot `
  --preview test_runs/text_glyph_pilot_review `
  --files 30 --scan 30 --preview-files 30 `
  --resolutions 12,16,20,24,32,48 `
  --allow-empty-resolutions
```

The pilot must be reviewed before it is supplied through `--svg-gt`.  Its goal
is to validate the annotation definition and the difficult low-resolution
counters/terminals, not to claim broad font coverage.  A successful pilot is
followed by font-held-out coverage, arc-length-normalised CNN inputs,
event-recall calibration and topology-preservation gates; none of those gates
should be skipped merely because this small set trains successfully.

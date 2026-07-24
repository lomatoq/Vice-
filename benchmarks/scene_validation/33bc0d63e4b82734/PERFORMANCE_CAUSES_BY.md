# Frozen Scene performance cause audit

The VAI50 ledger records median wall time `204.330 s`, p95 `2018.724 s`, and
maximum `2457.081 s`.  Stage totals over completed cases are dominated by:

1. `scene-build`: `12,265.882 s`;
2. `residual`: `2,873.451 s`;
3. `optimizer`: `835.201 s`;
4. `topology`: `802.227 s`.

## Scene-build repeats full-canvas work

`pipeline.py` builds every topology hypothesis independently.  The common
four-hypothesis set often contains identical region masks produced by argmax and
two spatial blurs.  Nevertheless `build_scene_graph()` reruns appearance fitting,
whole-shape tournaments, shared boundaries and text integration for every copy.

Each shape candidate also calls `render_geometry_mask(mask.shape, ...,
supersample=4)`, allocating and scoring a 4× full-image canvas.  This is repeated
across candidate families and digital-preimage refinements.  The correlation
between scene-build time and region count is `0.6245`, but sparse 512×512 cases
are also pathological: `egtdigitalgames_512` has only four regions yet spends
`469.989 s` in scene-build.

Required fix: bbox-local origin-aware candidate rasterization; mask-hash cache
across topology hypotheses; deduplicate topologies by canonical region graph
before building; dirty-rectangle forward scoring.

## Residual `max_additions` does not cap rejected proposals

`residual_add_prune()` increments `additions` only after an accepted proposal.
The guard `additions >= max_additions` therefore caps accepted shapes, not
attempts.  If every candidate is rejected, it evaluates every connected
residual component down to the two-pixel floor, and every attempt performs a
shape tournament plus a full-scene forward render.

In `egtdigitalgames_512`, the trace contains about ninety rejected `add` trials
and spends `269.565 s` in residual repair.  Several trials cover only two or
three pixels, even though none improves the incumbent.

Required fix: separate `max_attempts` and `max_accepts`; rank by predicted local
benefit; local court before global verification; stop below a calibrated area/
damage threshold; cache the incumbent render and update only dirty rectangles.

## Structural explosion compounds both costs

Worst completed outputs include 514 primitives (`icon_group_7`), 366
(`betsoft_512`), 344 (`icon_group_4_7`) and 286 (`icon_group_4_17`).  Full-scene
optimizer/residual renders then scale with both proposal count and scene size.
The new build needs a hard editability/shape-explosion gate before expensive
global refinement, not merely an MDL term inside an already huge hypothesis.


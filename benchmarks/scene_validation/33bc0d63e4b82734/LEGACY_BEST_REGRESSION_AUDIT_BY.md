# Incumbent `Best` regression audit

The current stage snapshot has 12 red cases that were all green in the previous
snapshot.  This confirms a real regression in the incumbent route; it is not a
display-resolution artifact and not caused by the experimental Scene route.

| Case | Previous → current regions | Previous → current primitives | Previous → current IoU | Topology |
|---|---:|---:|---:|---|
| bars_clean | 2 → 18 | 9 → 60 | .9925 → .9656 | preserved |
| bars_jpeg | 2 → 18 | 9 → 60 | .9925 → .9656 | preserved |
| cross | 1 → 8 | 12 → 9 | 1.0000 → .9389 | preserved |
| occlusion_complete | 2 → 3 | 12 → 387 | .9982 → .9996 | preserved, structure explodes |
| lshape_no_complete | 2 → 2 | 10 → 13 | 1.0000 → 1.0000 | preserved, contract fails |
| shield_symmetry | 1 → 1 | 7 → 150 | .9968 → .9952 | preserved, structure explodes |
| flag_no_merge | 2 → 2 | 8 → 11 | .9877 → .9937 | preserved, contract fails |
| lion | 9 → 7 | 429 → 141 | .9388 → .9006 | **broken** |
| mastercard | 47 → 170 | 465 → 1048 | .9426 → .9434 | **broken** |
| ikea_regions | 9 → 10 | 117 → 124 | .9497 → .7210 | preserved, fidelity collapses |
| mastercard_wordmark_regions | 14 → 37 | 440 → 1239 | .9923 → .9727 | **broken** |
| nbc_regions | 11 → 58 | 97 → 635 | .9716 → .8896 | preserved, structure explodes |

## Proven cause for the basic filled-shape regressions

A focused runtime ablation disabled only `_detect_variable_strokes` and
`_detect_stroke`, leaving the rest of the current pipeline intact:

| Case | Current | Stroke lane off |
|---|---|---|
| bars_clean | 18 regions, 60 primitives, IoU .9656, 135.7 s | **2 regions, 9 primitives, IoU .9925, 19.1 s** |
| cross | 8 regions, 9 primitives, IoU .9389, 137.9 s | **1 region, 12 primitives, IoU 1.0000, 9.0 s** |

The ablated outputs exactly recover the previous region/primitive/fidelity
signature.  A second split ablation identifies the exact branch:

| Ablation | bars_clean | cross |
|---|---|---|
| variable-width detector off | **2 regions, 9 prims, .9925 IoU, 22.3 s** | **1 region, 12 prims, 1.0000 IoU, 8.7 s** |
| constant-width detector off | 18 regions, 60 prims, .9656 IoU, 119.3 s | 8 regions, 9 prims, .9389 IoU, 119.0 s |

Thus `_detect_variable_strokes`, not `_detect_stroke`, falsely decomposes the
ordinary filled polygons and is responsible for these two regressions and their
roughly 7–15× runtime increase.  The constant-width detector adds about 17–19 s
on these already-broken cases but does not change their geometry.

Artifacts: `benchmarks/legacy_stroke_lane_ablation.json` and
`benchmarks/legacy_stroke_lane_split_ablation.json`.

## Required incumbent repair

The variable-width detector must not run as an unconditional replacement on
every mask.  It needs a hard filled-polygon veto and a bounded arbitration court:

1. preserve the incumbent filled-loop candidate;
2. propose a stroke only when medial-axis width, cap evidence, and topology make
   the filled explanation implausible;
3. compare local raster boundary and structural complexity;
4. accept only if topology is identical, IoU/boundary do not regress, and the
   representation is materially simpler;
5. otherwise retain the exact filled incumbent.

The other ten red cases still require individual causal ablations.  No claim is
made here that the stroke lane explains them all.

One negative result is also recorded: jointly reverting the new physical-DP,
uncertainty/correlation, MDL and ideal-apex flags did **not** change
`shield_symmetry` (150 primitives and IoU .9952 in both variants).  The shield
explosion is therefore not attributed to those flags; its cause remains open.
Artifact: `benchmarks/legacy_dp_ablation.json`.

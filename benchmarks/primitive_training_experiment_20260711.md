# Primitive + wordmark CNN experiment — 2026-07-11

Production checkpoint was never overwritten.

## Training set

- 38,174 loop examples
- 6,871,012 boundary vertices
- 3.3605% positive vertices
- 992/1,000 sampled `text_shapes/svg` wordmarks accepted
- reviewed V4 train split + primitive pilot train split
- 726 deterministic Arial glyph loops + 157 paper loops

Reusable cache: `tmp/corner_primitives_candidate_cache.pkl` (about 214 MB).

## Checkpoints

| Checkpoint | Epochs | LR | positive-weight scale | Decision |
|---|---:|---:|---:|---|
| `corner_cnn_primitives_candidate.pt` | 2 | 1e-4 | 0.50 | reject: excess false positives |
| `corner_cnn_primitives_precision_candidate.pt` | 1 | 5e-5 | 0.25 | reject: small-resolution recall loss |
| `corner_cnn_primitives_balanced_candidate.pt` | 1 | 5e-5 | 0.35 | reject: worse F1 on both smoke sets |

## Fixed 500-loop smoke results at threshold 0.28

| Dataset / model | Precision | Recall | F1 | FP / loop |
|---|---:|---:|---:|---:|
| primitive / production | 0.5976 | 0.8648 | 0.7068 | 1.154 |
| primitive / scale 0.50 | 0.5581 | 0.8678 | 0.6793 | 1.362 |
| primitive / scale 0.25 | 0.6965 | 0.7689 | 0.7309 | 0.664 |
| primitive / scale 0.35 | 0.6192 | 0.8073 | 0.7008 | 0.984 |
| V4 / production | 0.6303 | 0.8559 | 0.7260 | 2.042 |
| V4 / scale 0.25 | 0.6718 | 0.7768 | 0.7205 | 1.544 |
| V4 / scale 0.35 | 0.6167 | 0.8210 | 0.7043 | 2.076 |

The scale-0.25 candidate improved primitive precision, but its V4 recall at
32–64 px fell materially. Threshold calibration on V4 val did not recover the
production F1. It also failed the end-to-end logo gate: Mastercard, Mobil and
NBC were unchanged; Lacoste used fewer primitives but raster IoU fell from
0.9428 to 0.9379 and gained a visible micro-artifact.

## Conclusion

Do not promote any candidate. The next training experiment should change data
sampling, not keep sweeping a global BCE weight:

1. family-balanced batches (smooth/structural/mixed/occlusion/text/V4);
2. length buckets with padding + masked BCE so the GPU can batch loops;
3. explicit smooth false-positive and small-resolution recall validation gates;
4. a separate shared-circle graph fix for Mastercard, which is not a CNN issue.

## Final batched hybrid

The follow-up implementation added exact variable-length circular batches,
family-balanced sampling and smooth zero-event metrics.  Two epochs at batch 16
completed in 53 seconds.  The promoted large-loop checkpoint is
`models/corner_cnn_hybrid_large_v1.pt`; the original `models/corner_cnn.pt`
remains the small/complex-loop safety model.

Final routing selected on val: old CNN@0.28 for extent <=4 px or boundary
density >8 vertices/px; new CNN@0.36 otherwise.  Untouched test results:

| Dataset | Production F1 | Hybrid F1 | Production FP/loop | Hybrid FP/loop |
|---|---:|---:|---:|---:|
| primitive test | 0.7005 | 0.7407 | 1.3077 | 1.0325 |
| V4 test | 0.7284 | 0.7291 | 2.1422 | 2.0863 |

Graph-scope co-circular recovery reduced Mastercard from 223 to 191 primitives,
upper-logo micro fragments from 4 to 1, and improved raster IoU from 0.9863 to
0.9901.  A subpixel RDP experiment reduced NBC micro fragments from 8 to 3,
but regressed tiny-colour fidelity from 0.4225 to 0.3772 and was therefore
reverted.  The eight NBC centre-junction segments remain intentionally
pixel-faithful; Lacoste scales likewise retain their observed tiny topology.

## Certified end-to-end logo gate

The final production route and shared-circle graph pass were regenerated into
`test_runs/certified_v2` and checked with the same raster/topology metrics:

| Logo | Raster IoU | Components | Holes | Micro primitives | Tiny-detail score |
|---|---:|---:|---:|---:|---:|
| Mastercard | 0.9901 | 11 / 11 | 4 / 4 | 11 (upper logo: 1) | 1.0000 |
| Mobil | 0.9849 | 6 / 6 | 2 / 2 | 0 | 1.0000 |
| NBC | 0.9855 | 9 / 9 | 2 / 2 | 8 | 0.4225 |
| Lacoste | 0.9380 | 8 / 8 | 2 / 2 | 50 | 1.0000 |

All formal gates pass.  The NBC micro-segments and Lacoste scale fragments are
not removed globally because the attempted simplification demonstrably erased
real subpixel colour/detail information.

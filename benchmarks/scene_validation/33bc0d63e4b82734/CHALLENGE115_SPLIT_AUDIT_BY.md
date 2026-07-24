# Challenge-115 VAI crop-split audit

The initial validation-only splitter was rejected before the campaign because
it extracted only `<path>` elements.  The four supplied VAI plates also contain
native circles, ellipses and rectangles, many with transforms.  A path-only
split would therefore have biased the blind comparison against VAI.

The corrected splitter:

1. preserves paths, circles, ellipses, rectangles, lines, polygons and
   polylines in original draw order;
2. applies the VAI plate transform convention when assigning native geometry;
3. preserves the plate-sized compound white background/cutout path in every
   raster crop, while excluding it from per-cell path-space geometry meters;
4. writes separate raster-faithful and geometry-only SVGs;
5. refuses to run if element census coverage or raster reproduction fails.

Pre-campaign proof:

| Plate | Cells | Graphics | Cell-assigned | Shared compound | Unassigned | Coverage |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 67 | 1,530 | 1,529 | 1 | 0 | 100% |
| 2 | 32 | 1,176 | 1,175 | 1 | 0 | 100% |
| 3 | 6 | 1,443 | 1,442 | 1 | 0 | 100% |
| 4 | 10 | 1,030 | 1,029 | 1 | 0 | 100% |

Across all 115 cells, an isolated SVG was rendered and compared against the
same cell cropped from the complete VAI plate render:

- mean absolute channel error: `0.024440 / 255`;
- p95 cell MAE: `0.097500 / 255`;
- maximum cell MAE: `0.225586 / 255`;
- all configured census and raster-fidelity gates: `PASS`.

The remaining sub-1/255 differences occur only at crop boundaries and are far
below the quality differences under test.  The runner persists the same proof
as `challenge115_bounded/split_audit.json` before evaluating V-ICE.


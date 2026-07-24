# Frozen metric implementation audit

The frozen campaign's negative promotion verdict is robust because its raster
fidelity, topology, local-catastrophe and resource gates all fail badly.  The
audit nevertheless found two omissions that make the metric implementation
less trustworthy than its API surface suggests.

## 1. OCR legibility was implemented but dead

`benchmark_vai.py` defines `ocr_legibility_meter()` and calls it only from
`eye_meters()`.  `eye_meters()` itself has no callers.  The production benchmark
path calls `raster_meters()`, which includes local damage, component census,
persistent topology, catastrophic loci and group regularity, but not OCR.

Consequence: destroyed words can receive no text-specific penalty.  This is
consistent with the frozen Mastercard result: visibly broken `mastercard`, low
global render NLL, and `abstained=false`.

Validation response: `run_scene_ocr_audit.py` computes the omitted metric on
every completed Challenge-115 `small_text` pair without rerunning vectorization.
The corrected build must call OCR/glyph-structure scoring from the actual
promotion path and treat severe text loss as a hard gate.

## 2. Path-space geometry ignores native SVG primitives

`_parse_paths()` extracts only `<path d="...">`.  Consequently
`geometry_meters()` and `roundness_meter()` ignore native `<circle>`, `<ellipse>`,
`<rect>`, `<line>`, `<polygon>` and `<polyline>` elements and do not apply SVG
transforms.  Raster-space metrics still see these elements, so the core fidelity
verdict is unaffected, but path smoothness/editability comparisons can be
incomplete or biased.

This matters particularly for Challenge-115: the four VAI plates contain 1,196
native circles/ellipses/rectangles in addition to paths.  The corrected crop
splitter preserves all of them for raster comparison, but the frozen
path-geometry meter still cannot score them.

Required correction: one transform-aware SVG geometry iterator shared by
geometry, roundness, structural census and crop tooling, with unit tests proving
equivalent metrics for a circle encoded as `<circle>`, an arc path and a
transformed ellipse.

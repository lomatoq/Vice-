# V-ICE plan completion audit

Date: 2026-07-19  
Authority: `C:\Users\nirrt\Downloads\V-ICE_global_solutions_by.md`

This audit tracks the implementation against the document's Strike 0–6 plan.
It does not substitute a synthetic score for the deferred full blind/human
court.  Long corpus runs remain deliberately deferred by the owner.

## Strike 0 — measurement contract

- Geometry tails include kink CVaR and detail CVaR.
- Raster gates include local defeat, component census, persistent topology,
  catastrophic-locus CVaR and repeated-group regularity.
- Conditions are reported by scale/layout/format, not averaged away.
- The crop court uses live SVG candidates, native source pixels, 0.5×/1×/2×,
  a 4× pixel diagnostic, light/dark backgrounds, hashes and crop viewboxes.
- Gate: `python test_strike0_metrics.py` — PASS.

## Strike 1 — density-invariant DP

- Fidelity is a physical arclength integral rather than a sample-count sum.
- Uncertainty/correlation weighting and native-pixel corridors are explicit.
- Primitive and corner prices use MDL/log-odds evidence.
- 1× vs 4× contract: star 10/10 with max 0.7446 native-px delta; L-shape
  6/6 with 0 delta; rectangle 4/4 with 0 delta.
- Gates: `test_dp_physical_fidelity.py`,
  `test_dp_physical_fidelity_hot_path.py`, `test_dp4x_contract.py` — PASS.

## Strike 2 — text evidence shield

- Persistent line/component/hole obligations protect glyph topology.
- The ambiguity band has a line-level CRF proposal and a skeleton-width
  hypothesis; uncertain repairs abstain.
- Gates: `test_text_evidence_shield.py`, `test_glyph_repair.py` — PASS.

## Strike 3 — Codec Legitimacy Court

- JPEG qtable/grid is read from metadata or recovered from a coefficient
  lattice after JPEG→PNG resaving, with an a-contrario confidence gate.
- Hypotheses are rendered through the document's deterministic forward chain:
  8× linear-light raster, pixel integration, gamma grid, measured PSF,
  native downsample, chroma mode and JPEG DCT-bin likelihood.
- Nearby qtable scales and grid phases must preserve the ranking; a small or
  unstable margin abstains. Persistent topology is an unconditional veto.
- Synthetic known-JPEG gates cover true-simple confetti preference, real accent
  survival, gamma/PSF/4:2:0 and clean-PNG abstention.
- Gate: `python test_codec_legitimacy.py` — PASS.

## Strike 4 — Digital Circle Court

- Circle feasibility uses confident inside/outside digital-preimage samples;
  q30 outliers come from codec uncertainty.
- Tournament includes circle, ellipse, rounded rectangle and generic loop.
- Existing nested loops have an explicit concentric-ring BIC court with shared
  centre, ordered radii and unchanged persistent hole.
- A physically concave 5–15px loop becomes an explicit deliberate-crescent
  hypothesis. A full circle wins only when the qtable/phase-stable forward
  degradation court explains the observed missing side.
- Repeated circles share a radius only when the group BIC wins.
- Synthetic gates cover clean circle/square/ellipse, q30 circle, q30 ring,
  codec-explained crescent and a real crescent that must survive.
- Gate: `python test_digital_circle_court.py` — PASS.

## Strike 5 — structural diagram lane

- LSD NFA, directional openings and a collinear/orthogonal graph isolate only
  a validated line network.
- Dashed boxes are assembled globally; weak sides are accepted only inside the
  predicted fourth-side corridor.
- Rectangle-cycle and small two-family collateral vetoes prevent logo frames
  and decoration rows from entering the diagram lane.
- Gates include line chart, weak-fourth-side box, clean icon sheet, lone row and
  the Colgate collateral smoke.
- Gate: `python test_structural_diagram_lane.py` — PASS.

## Strike 6 — stroke restoration and seams

- Stable topology-preserving skeleton branches use PELT/BIC width segments and
  a render-back topology/silhouette veto.
- Shared-edge underpaint exists only on internal interfaces, uses butt caps and
  never extends the outer silhouette.
- Underpaint width is measured from actual renderer AA support at 0.5×/1×/2×;
  installed `resvg` measured a one-sided support of 0.75 native px.
- Multiscale seam tests passed in both `resvg` and the in-app Chromium SVG
  renderer with zero white interface pixels at 0.5×, 1× and 2×.
- Gate: `python test_stroke_seams.py` — PASS.

## Integration evidence

- Targeted Strike 0–6 suite: 10/10 scripts PASS.
- `py_compile` and `git diff --check`: PASS.
- Real Best smoke: 29.5 s, isolated worker survived, 6 regions, 13 contours,
  172 primitives; structural lane abstained on the logo collateral.
- HTTP preview smoke: 1.23 s and a valid SVG response; the listener remained
  alive, so the former browser `Failed to fetch` failure did not recur.
- UI: `V-ICE Best` remains selected by default; separate `Хуткі draft · 1–2 с`
  and `Вектарызаваць · Best` actions are visible at
  `http://127.0.0.1:8877/`.

## Deliberately deferred proof

- Full VAI/corpus regression and tail tables.
- Human blind text/roundness/crop votes.
- A statistically defensible “best in the world” claim.

Those are evaluation steps, not missing implementation. The blind crop court
is available from the UI for the owner's later approval run.

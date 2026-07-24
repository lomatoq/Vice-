# V-ICE ProposalNet v14 — fail-closed readiness audit

Date: 2026-07-22  
Canonical plan: `V-ICE_proof_carrying_design_compiler_plan_ru_v2.md`  
Current decision: **NO-TRAIN**

This is the current audit, not a claim that a green unit-test suite proves
quality. ProposalNet v14 may start only after one hash-bound readiness report
contains every required gate and says `TRAIN`.

## What is fixed and tested now

- Current compiler SHA-256 is
  `bbf33a5b1d38eaa37db06f29b87248e522d394ad8d96d5df6138d8c4c012ebc4`;
  its complete regression gate is **262/262 passed**.
- The licensed runtime font bank exactly matches its manifest: **81 families,
  241 files**, upstream revision
  `684b69db51d59a3137ec0152fa3a3afc6f1b3814`.
- Label contract is now `pcdc-explicit-owner-counterfactual-mixed-replay-labels/v4`.
  Every old v13 checkpoint/preflight is intentionally stale and cannot launch
  v14 training.
- All eight relation tokens have explicit positive/observable supervision.
  Unknown relations are masked, not silently trained as negatives.
- Runtime family priors are conjunctive where required: for example text needs
  `same_group AND text_membership`; layer needs `same_group AND front_of AND
  behind`.
- All ten hard-negative classes are generated only where semantically valid.
  Their canonical SceneProgram is now the object that is rendered and hashed;
  there is no inert “program” beside an unrelated mask renderer.
- Filter-cache bootstrap can scan and freeze a corpus before training; it no
  longer requires a training report that cannot exist yet.
- The readiness validator rejects a missing or extra gate name as well as a
  false value.
- Conformal calibration and runtime now share one exact admission transaction:
  classical/neural union, family prefix and final Fast/Balanced/Max global cap.
- Five calibration leaks/divergences were removed:
  target-IoU tie breaking, PIL-only preprocessing, raw logits without the text
  support gate, below-runtime-floor queries, and batch-index-dependent query IDs.
- A v4 candidate cannot be authorized or promoted unless a hash-bound held-out
  replay proves at least 99% type+support coverage after the exact final cap in
  **Fast, Balanced and Max**.
- Phase 7 is now one deployable sparse graph, not an analytic-shape-only
  report: curve anchors, physical G1/G2 regularization, coverage, pairwise
  shared interfaces, symmetry, text, stroke, appearance/alpha/gradient and
  repeated scale/gap parameters all feed exact production delivery. Every
  changed macro is re-keyed, exact-rerendered, re-courted and rolled back on a
  certificate or full-scene regression.
- The machine readiness verdict currently has exactly three green launch gates:
  full regression, licensed font-bank identity and runtime-conformal harness
  equivalence. The other thirteen required gates remain closed.

## Current blocking gates

### B01 — Phase 4 TextLine is not green

The last exact run was below the canonical gate: GCR reduction about 44% versus
the required 70%, warm p95 above 200 ms/line, and exact-font admission did not
produce a passing reviewed result. The larger licensed font bank fixes the old
coverage limitation but the current source must be rerun and pass both the
machine gate and a digest-bound human court.

### B02 — Foundational experiments are stale

Experiments 1, 1B, 2, 3 and 5 were produced by older or unbound compiler bytes.
They must all pass again on one frozen compiler SHA. Experiment 4 must also be
rerun on that same SHA.

### B03 — No promotable v4 corpus exists yet

The old mixed v13 corpus was built under older relation and hard-negative
semantics. It cannot train v4. A new corpus must be generated, filtered and
exhaustively materialized. Per split it must have at least 100 examples for
every query family, hard-negative class, relation positive/negative and all 16
parameter dimensions, while satisfying the fixed Recall@5 oracle-capacity
floors.

### B04 — Renderer/degradation holdouts are still missing

The existing typed supplements declare only `resvg-pillow/v1`. The final data
factory still needs at least four attested render paths, including an engine
that is absent from training, plus a degradation family absent from training.
Source groups must remain disjoint; renderer variants of one design may not be
split across train and test.

### B05 — Real Locus calibration capacity is insufficient

The current 300-locus corpus is far below the plan target of 2k–5k reviewed
loci. It also lacks the fixed minimum of 100 calibration instances per required
family and adequate held-out test counts for stroke, risk and
symmetry/repetition. A conformal threshold equal to 1.0 is explicitly rejected
as vacuous.

### B06 — Final pre-training proofs do not exist

After source/data/config freeze, all of these must be newly generated and bound
to the same bytes:

- full regression report;
- plan traceability report;
- untouched source/font/icon/renderer/degradation/semantic holdout seal;
- tiny multi-instance overfit;
- anti-forgetting pilot;
- two-run CUDA reproducibility report;
- real calibration-capacity report;
- exact runtime-conformal harness proof.

### B07 — v13 is not evidence for v14

The existing v13 initialization was trained on the superseded v3 contract and
performed badly in the user's real examples. It is not `Best`, not a production
fallback-quality claim and not a v14 launch proof. Any reuse is initialization
only and must pass the new overfit, anti-forgetting and held-out gates.

### B08 — VAI parity is still unproved

Even a passing ProposalNet is only a proposal source. Promotion still requires
the full OFF/ON campaign, zero catastrophic topology/counter/canvas failures,
VAI50 and challenge115 completeness, live-SVG blind comparison, no key slice
below 45%, overall parity at least 50% (target above 55%), and Balanced warm
p50/p95 plus hard timeout gates.

## Required execution order

1. Finish plan-to-code traceability and repair remaining pre-Phase-9 gaps.
2. Finish the multi-renderer/degradation-disjoint v4 data factory.
3. Generate a fresh corpus and run the exhaustive supervision/oracle audit.
4. Expand and seal the real-locus calibration/test evidence.
5. Freeze source, data, config, fonts, renderers and thresholds.
6. Rerun Experiments 1, 1B, 2, 3, 4 and 5 plus the complete regression suite.
7. Pass tiny overfit, anti-forgetting and CUDA reproducibility.
8. Produce exactly one all-green `TRAIN` readiness report.
9. Train one v14 candidate; then run exact runtime coverage, OFF/ON and blind
   VAI parity before any promotion.

At the time of this report, training remains deliberately blocked.

# V-ICE Vectorizer — Open Problems Dossier (for external review)

> **TL;DR па-беларуску.** Мы будуем вектарызатар растравых лагатыпаў/іконак,
> які па 8 з 10 метрык ужо б'е vectorizer.ai (VAI), але ў сляпым чалавечым
> судзе прайграе 3:11 — вока карае разбураныя дробныя літары мацней, чым
> любыя нашы перамогі. Ніжэй — усе адкрытыя праблемы з лікамі, усе тупікі
> (каб не прапаноўваць паўторна) і канкрэтныя пытанні, дзе патрэбны свежы
> погляд. Дакумент самадастатковы: чытач не мае доступу да кода/гісторыі.

---

## 0. What this system is (5 lines)

Raster logo/icon → colour palette (median-cut + hue families + region-
adjacency merges) → per-region masks → boundary loops (pixel-exact
staircase tracing) → primitive fitting via Cornucopia-style shortest-path
DP over line/arc/elliptic-arc/clothoid/cubic with a hard per-midpoint
interval law (±0.5px) and corner-as-priced-DP-decision (CNN probabilities
→ prices) → shared-interface region graph (fit-once, seam-free) → SVG.
Degraded inputs may take a 4× learned-deblur path. Reference paper:
Hoshyari et al. 2018 (perception-driven semi-structured boundaries).

**What already works well (do NOT re-suggest):** interval-law fitting;
joint corner+primitive DP with machine-calibrated prices; fit-once region
graph (zero seams by construction); relative circle court; tortuosity
merge for JPEG boundaries; dash-grid detection→stroke+dasharray emission;
corner detection at native density for 4×-lattice inputs; per-line OCR +
exact font substitution when the font is retrievable; engraving law
(locally-darkest interior relief survives merges); post-fit kink critic
(raster-judged surgical pair merges); stress bench vs analytical GT with
vtracer/potrace baselines; blind human A/B harness.

**Scoreboard vs VAI** (blind pack, 115 unseen items): we lead 8/10 meters
(MAE ×2.2, G2 ×10, micro-segments ×32, ink-IoU, SSIM, wobble, seams,
staircases). We trail on **kinks** (median 2.11 vs 0.83; wins 28/115) and
**roundness** (wins 31%). Human blind court round 1: **we 3 : VAI 11 : 1
tie** — the decisive gap is perceptual, not metric.

## 1. Rules of engagement (constraints any proposal must respect)

- Every constant ships with a written justification tied to a measured
  failure; hand-tuned thresholds without evidence are rejected.
- Candidate mechanisms get at most 2 attempts, must pass regression gates
  (a stage suite + a 50-item corpus benchmark) and are REVERTED on net
  corpus harm even if their target case improves.
- Topology is sacred (holes/counters/components must survive).
- The final judge is a human eye next to VAI output; metrics only guard
  regressions.
- Determinism required (multi-item harnesses run per-item subprocesses).

## 2. P0 — the perceptual front

### P0.1 Small-glyph destruction (the blind-court killer)
- **Symptoms:** item053 "AARCH" renders as blue rubble; item043 a branch-
  tip circle becomes a crescent; item027 colour artefacts on small D/O;
  item081 a lowercase "o" filled solid. Human court: all these lost to
  VAI despite VAI's own visible flaws. Related: item114 ("bank") emits 1
  connected component where the ground truth has 6 (letters bleed
  together); h24-class micro-letter kinks.
- **Tried:** exact font-substitution works when OCR + font retrieval
  succeed (pixel-perfect on clear wordmarks); a v1 "glyph consensus"
  (post-fit vertical snapping of glyph extrema to a shared baseline/
  x-height) was built and reverted: it moved IoU −0.009..−0.012 without
  touching kinks — the damage lives INSIDE letter contours, not in
  inter-glyph jitter.
- **Current design (not yet built):** per-text-line consensus DURING
  fitting, not after: estimate per-line baseline/cap-height/x-height/stem
  width from all glyph loops of an OCR line box (medians), then constrain
  the fits (horizontal extrema snap to the shared heights within ±0.6px;
  vertical stems take the shared width via LSQ shift of both sides),
  gated by line-IoU not degrading.
- **Fresh-eyes question:** is there a stronger frame than per-line grids —
  e.g. joint multi-glyph fitting with shared stroke-width and shared
  curvature classes, or a cheap glyph-integrity score that could VETO the
  palette/merge steps that shred glyphs before fitting ever starts?

### P0.2 The "lane" problem (when to trust ragged evidence)
- **Symptoms:** three mechanisms are parked, each PROVEN on its target
  class and each vetoed by the 50-item corpus because the same pixel
  signature describes both disease and legitimate content:
  1. *Confetti court* — q30 contact-smear flecks around icons (absorb
     barnacles + delete edge-born dust): target item57-v1 kinks 15.2→3.1,
     but clean icon sheets lose real captions/accents.
  2. *Junction stub absorption* — sub-2px curve stubs at region-graph
     junctions (quantisation caps): 068 kinks 8.85→7.45, 059 8.53→7.25,
     057 14.2→9.7 — but dense sheets pay wobble ×2.5 (thousands of
     junctions each nudged).
  3. *Row-coherence immunity* — letter-spaced captions vs merge
     absorption: cures the worst stress-bench tail completely
     (h95 16.2→0.95) but resurrects q30 junk rows corpus-wide.
- **Dead discriminators (measured, do not re-propose):** global ring-noise
  meter (the diseased item measures 0.0 — smear is local); L-ramp ratio
  (caption glyphs ramp MORE than dust: 0.61–1.03 vs 0.28–0.59); fleck-to-
  large-mask ratio (collages span 0.86–9.0 around the diseased 3.0);
  cohort "same-colour brothers" fraction (smear flecks are each other's
  brothers at 0.78; clean sheets span 0.44–0.82).
- **Fresh-eyes question:** any runtime-computable signal that separates
  "codec residue near shapes" from "deliberate small design elements"?
  Or is the honest answer only a learned perceptual judge (we lean this
  way — see P3.1)? A cheap self-supervised proxy (e.g. re-compress the
  input at q30 and diff — codec artefacts are unstable under recompression,
  design is stable) has NOT been tried yet and might be the missing lane
  key. Critique welcome.

## 3. P1 — metric gaps vs VAI

### P1.1 Kinks (median 2.11 vs 0.83)
- Corpus median went 5.5 → 4.6 over three days; the remaining tail is
  concentrated in q30-class inputs (the parked lane mechanisms above
  would cut it — blocked by P0.2) and in TRUE micro-creases: on the KA
  cube, 18 of 22 candidate kink loci are genuine facet creases the
  raster court correctly refuses to smooth.
- Machine price search for the corner-DP (81 configs) hit a ceiling:
  price levers no longer move kink p95. A planned re-run with p95 in the
  objective has not happened.
- **Question:** given most residual kinks are either (a) genuine creases
  or (b) codec junk needing a lane — is there a third class we're blind
  to? A reviewer pass over 10 worst kink items with fresh eyes may find
  one.

### P1.2 Roundness (wins 31%)
- Median 0.0093 vs VAI 0.0017. The relative circle court + MDL handicap
  shipped; a unified small-closed-shape tournament (circle/ellipse/
  rounded-rect/generic with description-cost scale) is designed, unbuilt.
- Failure mode from the human court: item043 branch-tip circle became a
  crescent — the circle court exists but small dirty rings still lose to
  generic loops. **Question:** best robust criterion for "this small
  blob is MEANT to be a perfect circle" under q30 noise?

### P1.3 Lost-detail tail (Hausdorff95)
- p95 halved in a day (11.35→5.07) via the engraving law, but vtracer
  holds 1.3–2.3 under EVERY degradation — proof the details are
  recoverable from the same inputs. Remaining named cases: the q30 medal
  (engraved digit's contrast dies before the palette under jpeg — no
  palette-level fix can see it), goodtimesstudios' letter-spaced caption
  (→ P0.1), 082-class dark rims (below).

## 4. P2 — named single-class defects (each has a measured trail)

- **082 rims:** dark 1px halo ring around shapes on q30 (kink source).
  Two palette-family merge attempts changed nothing — the rim is not a
  palette family; it forms at per-pixel label ASSIGNMENT (Gibbs-overshoot
  pixels land on an existing dark anchor). Planned: reassignment-stage
  absorption when a thin component is a ring hugging exactly one region
  (ring-share ≥80%) with moderate dE. Guard needed: must not kill the
  engraving law (interior vs boundary-hugging is the discriminator).
- **q30 medal:** engraved relief flattens below palette visibility under
  jpeg; only a pre-palette contrast-aware pass (or accepting the loss)
  can address it.
- **104-q45 linechart:** jpeg fattens 1px axes (thickness p90 1.9 vs 1.2
  bound) and dissolves connector components (1 of 3) — the diagram-lane
  auto-signature honestly fails; needs noise-robust structure detection
  (projection-Hough over components is the reserved idea; forcing the
  lane manually measured WORSE, so detection is genuinely the blocker).
- **Dashed-BOX assembly:** a pink dashed annotation FRAME (item111)
  passes dash laws with only 2 of 4 sides (others under the 6-dash
  floor); half-carving a box costs iou. Needs box-level assembly of dash
  groups.
- **Swimlane micro-seams (111):** 150px² of hairline cracks where large
  pale regions abut without paint-order apron; fix candidates: bleed for
  "both-late-painted neighbours" pairs or a post-process seam heal.
- **106 thin frames / line-width restore:** 1px box frames and chart
  axes fuse into one multi-width region; two whole-region stroke attempts
  reverted (a mid-grey-anchor "fix" was rejected ON PRINCIPLE — it faked
  width via an AA shell region). Reserved design: skeleton-branch width
  split with per-branch stroke emission.
- **Euler meter artefact:** topology stats on gradient fills are noise
  (fixed ink threshold); metering should reuse the quantise mask.
- **Gamma condition:** stress bench found gamma1.3+jpeg is the WORST
  detail-killer (h95 p90 7.2–7.9), worse than plain q30 — and our noise
  meter does not fire on gamma shifts at all.

## 5. P3 — strategic builds in flight

- **P3.1 Stage-3 perceptual judge (Counterfactual-Locus frame):** the
  blind A/B harness works (round 1 done, 15 pairs, manifest-decoded);
  next: locus-level collector (2–4 alternative renders of ONE ambiguous
  fragment per question), then a preference model as one voice in the
  explanation court. This is the designated answer to P0.2's lane
  problem and to "ragged-faithful vs intent-smooth" decisions generally.
- **P3.2 Per-condition corner models:** retrained paper-recipe RFs beat
  our production CNN by +0.43 F1 on 4×-deblur-conditioned data (CNN
  collapses to precision 0.13 there); models saved, integration of the
  deblur-lane model pending. Related open sore: the joint-DP machinery
  itself keeps thousands of C0s when fed 4×-lattice loops end-to-end
  (P~0.11 for ANY classifier) — we sidestep by detecting corners at
  native density, but cycles fitted at 4× remain fragile.
- **P3.3 Validation completion:** per-crop VAI rerun (user task,
  PRIORITY_30 prepared); DreamSim/human pairwise at scale; public
  baselines beyond vtracer/potrace.

## 6. Dead ends protocol (do not re-suggest)

1. Global content-based native/deblur switch (format must decide;
   content-switch broke fine-detail items).
2. Full-slack intervals on the native path (roundness/wobble pay, zero
   kink gain).
3. Palette-level dash rescue (anchor returns but dashes die downstream
   AND the extra anchor steals axes' AA: iou 0.747→0.613).
4. Mid-grey anchor for 1px frames (fakes width, rejected on principle).
5. Neutral-dashed component signature at chart scale (dashes fuse in
   pairs; needs line-level grouping — since shipped as D-dash).
6. Circle-rescue p92 (hurt teardrop shapes).
7. Post-fit vertical glyph snapping (damage is inside contours).
8. The four lane discriminators listed in P0.2.
9. Unconditional junction-stub drop AND its sagitta-courted variant
   (corpus wobble; see P0.2 item 2).
10. Row-coherence immunity inside the region merge (corpus veto; the
    anchor-stage half alone buys nothing).
11. 8×D4 reflection-max at inference (model already symmetric).

## 7. Questions where fresh ideas pay most

1. **Lane detection** (P0.2): a runtime signal for "this area is codec
   residue" that survives our dead-discriminator list? Is recompression
   instability (jpeg-cycle the input, diff) a sound lane key?
2. **Glyph integrity before fitting** (P0.1): how would you keep 6px
   letters whole through palette quantisation — joint colour assignment
   per OCR line? per-glyph colour voting? something else?
3. **Small-circle intent** (P1.2): a robust "meant to be a circle" test
   for 5–15px dirty rings that beats relative-residual courts?
4. **4×-lattice DP economics** (P3.2): would you re-tune the corner
   machinery for 4-unit steps, or is native-density detection + price
   transfer (our current path) the right permanent answer?
5. **Anything obviously missing** given the scoreboard: 8/10 meters green
   yet 3:11 in human court — what third explanation besides small-text
   destruction and counter-fill polarity would you investigate?

## 8. File map (for reference)

- `geometry_vectorizer.py` — fitting core, DP, courts, process().
- `region_graph.py` — shared-interface graph, junction rules (parked
  stub-absorption block inside, commented).
- `subpixel_mininet.py` — palette (compact_palette), deblur net, dash
  detector (unhooked), engraving fold-guard (parked half).
- `text_substitution.py` — OCR, font snap, consensus_align_lines (v1,
  call reverted).
- `benchmark_vai.py` / `benchmark_stages.py` / `challenge_eval.py` /
  `eval_one_item.py` — harnesses; `stress_bench.py`+`stress_one.py` —
  degradation stand (3 engines); `preference_collector.py` — blind A/B.
- Plans/logs: `NEXT_STRIKES_BY.md` (living plan with all trails),
  `NIGHT_REPORT_BY.md`, `PROJECT_STATE_AND_GAPS_BY.md`.
- Repo: https://github.com/lomatoq/Vice- (full history, ~100 commits).

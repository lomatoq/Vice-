# PCDC: актуальная сверка канонического плана с production-кодом

Дата сверки: 2026-07-21  
Канонический план: `V-ICE_proof_carrying_design_compiler_plan_ru_v2.md`  
Правило аудита: требование считается выполненным только если механизм реализован,
вызывается production runtime, влияет на доставляемый файл и покрыт тестом или
измеренным прогоном того же пути.

## Честный вердикт

Архитектура PCDC уже существенно ближе к плану, чем было зафиксировано в старом
аудите: production runtime использует dual pricing, обязательный local court,
proof bundles, три Pareto-профиля, локальное уточнение клеток, full-scene
transaction, marginal rollback и SVG XIR. Однако гипотеза **ещё не доказана**:
полная frozen campaign не запущена, ProposalNet v2 ещё обучается, translucent
ownership и явные interface variables отсутствуют, а blind parity с VAI не
измерена.

Нельзя утверждать ни «план выполнен полностью», ни «достигнут parity с VAI».
Можно утверждать, что production graph теперь реально проверяет большую часть
центральной гипотезы, а найденные ухудшения fail-closed откатываются в T1/T0.

Статусы:

- **WIRED** — production использует механизм и есть тест/живой прогон;
- **PARTIAL** — production использует существенную часть, но семантика плана
  реализована не полностью;
- **TRAINING / NOT PROMOTED** — кандидат существует, но production checkpoint
  не заменён до прохождения gate и downstream ablation;
- **MISSING** — требуемого механизма нет;
- **NOT RUN** — реализация есть, но promotion evidence отсутствует.

## C01–C17: критическая матрица

| ID | Требование плана | Текущий production-путь | Статус | Остаточный риск |
|---|---|---|---|---|
| C01 | Настоящий V-ICE Best как транзакционный fallback | `legacy_best.py`, `legacy_scene_adapter`, hash-checked exact SVG passthrough | **WIRED** | Best — только безопасный пол, не quality target. Если frozen artifact отсутствует, используется T1 hierarchy fallback. |
| C02 | 2–4 раунда dual-guided typed pricing | `runtime_service.py -> run_column_generation`; Fast/Balanced/Max используют 2/3/4 раунда | **WIRED / PARTIAL scheduling** | Typed generators пока создают bounded pool заранее; dual prices направляют admission, но не полностью ленивую генерацию каждого семейства. |
| C03 | ProposalNet направляет поиск до fitting | warm worker запускается сразу после REIR; queries передаются в text/shape/stroke/appearance generation до fit | **WIRED; model v2 TRAINING** | Старый large checkpoint честный gate провалил и не promoted. v2 должен пройти global Recall@K, conformal и downstream ablation. |
| C04 | Каждый admitted typed macro несёт проверенный proof bundle | `RuntimeMacroCourt.certify` обязателен в column generation; extractor вызывается с `require_proofs=True` | **WIRED** | `proof_bundle` остаётся optional на уровне общего dataclass для base/draft rows, но production typed selection без proof закрыт. |
| C05 | Cheap→expensive fixed-posterior court и exact ROI atlas | production court: color/SDF/topology/approx/exact/perceptual cascade; `ExactRoiAtlas`; exact delivery render reuse | **WIRED** | Некоторые типы fail-closed как unsupported delivery; нужно масштабное распределение exact/pruned counts. |
| C06 | Weighted set partitioning с proof/resource/group/topology/layer/interface constraints | exact cover, conflict components, proof gate, resource limits, group alternatives, text-lane exclusivity, delivered-pixel conflicts | **PARTIAL+** | Нет явной переменной «ровно одна геометрия на internal interface» и полного factor graph для всех prerequisite/layer contributions. |
| C07 | Transactional lazy local cell refinement | `plan_local_refinement` вызывается court; после сертификата `materialize_local_refinements` создаёт bounded child lattice и atomic fallback для каждого child | **WIRED** | Candidate-created interfaces пока не становятся новыми полноценными interface variables; это связано с C06. |
| C08 | 1 opaque owner либо <=K ordered translucent contributions + background | VSIR exact cover моделирует opaque ownership; alpha appearances существуют | **MISSING / PARTIAL appearance only** | Нет bounded K-stack и совместного ordered translucent solve. Полупрозрачные перекрытия не соответствуют §3.8. |
| C09 | Faithful/balanced/idealized Pareto finalists | `ExtractionProfile`, `build_profile_finalists`, `choose_profile_finalist`; requested idealized может проиграть dominance | **WIRED** | Нужна campaign-проверка, что профили дают реально различимые и полезные сцены. |
| C10 | Human preference выбирает только среди Pareto finalists и умеет abstain | runtime имеет optional `FinalistPreferenceSelector`; deterministic fallback при abstain | **PARTIAL** | Нет promoted learned human-preference checkpoint и подтверждённого <=0.5% catastrophic selection. |
| C11 | Один full render, marginal blame, rollback конфликтного набора и re-extraction affected components | exact candidate/baseline render cache; court marginal order; rollback closure; affected-component extraction; cached composite re-audit | **WIRED / bounded** | Re-extraction в основном возвращает affected region к base/retained typed set; не перебирает богатый новый typed alternative pool. |
| C12 | Continuous refinement реально достигает output при фиксированной topology | selected analytic shapes refine, recourt, rekey, CMIR/VSIR replace, затем writer сериализует refined parameters | **PARTIAL+** | Поддержаны не все macro families; text/stroke/general free-curve continuous factor graph неполон. |
| C13 | DPIR/guarded abstraction/XIR реально достигает writers | semantic SVG writer принимает delivered DPIR/XIR и сохраняет exact leaf markup | **WIRED for SVG / PARTIAL globally** | PDF/EPS/DXF не используют полный semantic XIR и требуют отдельной fidelity freeze. |
| C14 | Hidden completion и layer order после visible cover с exact verification | opaque typed hidden completions, DAG/cycle checks, rekey и downstream export wired | **PARTIAL+** | Neural pairwise order, local cycle alternatives и translucent stack отсутствуют; hidden lane ограничена analytic opaque carriers. |
| C15 | Resource certificates реально ограничивают job | `ProductionMasterConstraints`, fitting/render/memory/solver limits, runtime hard contracts | **WIRED / PARTIAL scheduling** | Generator work всё ещё partly eager, поэтому certificate не предотвращает всю ненужную pre-fit работу. |
| C16 | Native hot core: hierarchy, interfaces, DP, exact solver, screening, SDF, atlas | Rust: conflict bitsets, circle SDF, atlas packing | **PARTIAL** | Hierarchy, factor solve и большая часть court остаются Python/NumPy; speed gate нельзя считать закрытым. |
| C17 | Полная frozen Phase-12 campaign и blind VAI court | resumable item worker/harness существуют; выполнены только targeted smoke/debug прогоны | **NOT RUN** | Нет 50/50 + 115/115 completeness, frozen blind parity, slice gates и статистики warm p95. |

## Что дополнительно исправлено во время этой сверки

### 1. Честный ProposalNet gate

Старый `proposal_net_large_candidate.pt` не promoted. Его evaluator считал top-K
отдельно по family и мог повторно засчитывать один query нескольким instances;
conformal gate также мог пройти vacuously при отсутствующей family. Честная
переоценка дала провал `glyph_group` и non-vacuous conformal.

В v2 исправлено:

- global top-K по всем query families;
- one-to-one Hungarian instance matching;
- отдельные fixed gates Recall@5;
- missing family fails closed;
- no-object downweight;
- negative confidence supervision;
- hard-negative head loss;
- измеряемые geometry-parameter targets;
- source-disjoint small-shape augmentation;
- conservative semantic labels.

Текущий v2 run: `benchmarks/pcdc_proposal_large_v2`; checkpoint не будет
promoted без честного report gate и downstream ablation.

### 2. Text full-scene catastrophe gate

`VisibleRenderAudit` теперь хранит для каждого выбранного TextLine:

- source/rendered/baseline topology;
- component/counter catastrophe count;
- line-local IoU, precision, recall и contrast;
- regression относительно incumbent.

Global averages больше не могут скрыть разрушение букв. Cached marginal rollback
пересчитывает тот же text gate для реально retained scene.

### 3. Взаимоисключение text hypotheses и polarity validity

Два threshold-варианта одного line/lane больше не могут быть выбраны как два
paint layers. Дополнительно negative spaces между буквами не могут стать
`light-on-dark` TextLine: foreground обязан быть minority в полном line box и
маска обязана объяснять большинство пикселей своего foreground-класса.

### 4. Court теперь проверяет точный production text delivery

Text court рендерит те же SVG fragments, которые пишет export writer, а не
идеализированную бинарную proxy-mask. Replacement ownership отдельно включает
однопиксельный AA fringe, чтобы под новым glyph path не оставались ghost bands
старого fallback.

### 5. Исправлена фундаментальная геометрия fallback writer

OpenCV contour проходит через центры boundary pixels. Старый `_mask_path`
ошибочно использовал такой contour как SVG boundary, из-за чего тонкие stems,
counters и AA bands сжимались или исчезали. Для масок, где contour area
физически несовместима с union pixel cells, writer теперь использует точный
run-length union прямоугольных pixel cells.

На живом `textline_099_source.png` только это исправление изменило T1:

| Метрика | До | После |
|---|---:|---:|
| Ink IoU | 0.7226 | 0.9264 |
| SSIM | 0.8704 | 0.9908 |
| normalized MAE | 0.03577 | 0.00583 |
| topology error | 24 | 12 |
| catastrophic loci | 17 | 2 |

Это крупное улучшение базового доставляемого SVG, но topology error 12 и два
catastrophic loci означают, что пример всё ещё не прошёл topology promotion.

## Актуальная трассировка по подсистемам

### REIR / CMIR / VSIR

- Canonical decode, alpha shielding, linear premultiplied RGBA, Oklab,
  formation posterior, boundary pyramid, UCM hierarchy, inclusion trees,
  cells/bands/microfeatures: **WIRED**.
- REIR остаётся immutable; local refinement создаёт derived CMIR lattice:
  **WIRED**.
- Opaque exact cover: **WIRED**.
- Ordered translucent K-stack: **MISSING**.
- Half-edge evidence хранится: **WIRED as evidence**; единая выбранная interface
  geometry: **MISSING**.

### Court / extractor / transaction

- Mandatory proof-carrying typed admission: **WIRED**.
- Fixed posterior, cheap→exact cascade и atlas: **WIRED**.
- 2/3/4 pricing rounds: **WIRED**.
- Proof/resource/group/text-lane/pixel conflict checks: **WIRED**.
- Explicit interface variables и полный prerequisite factor graph: **PARTIAL**.
- Three Pareto profiles: **WIRED**.
- One exact full-scene transaction и affected rollback: **WIRED**.
- Full-scene transaction теперь включает blind-meter-compatible worst-locus
  damage: catastrophic locus count/rate/severity, boundary CVaR/p99 и
  persistent component/hole losses. Любой structural regression относительно
  incumbent fail-closed откатывает T2, даже если средние IoU/MAE улучшились.
- T3 continuous geometry больше не может попасть в writer только по локальному
  recourt: один cached T2 full render дополняется bounded exact SVG ROI recheck
  изменённой геометрии; regression откатывает refinement. Лимит `<=1` final
  full render сохранён.

### Text

- REIR-direct proposals, SWT/alignment/OCR/both polarities: **WIRED**.
- Exact font fail-open lane: **WIRED**, Max-only by budget.
- Font-free topology program и repeated-glyph EM: **WIRED**.
- Production-delivery proof и local Glyph Catastrophe gate: **WIRED**.
- Exact font/glyph recovery ещё не даёт VAI-like idealization на общем corpus:
  **NOT PROVEN**.
- Single custom glyph, knockout/outline/shadow group operators: **MISSING**.

### Shapes / strokes / layers / appearance

- Analytic shapes and bounded free curve: **WIRED**, но identifiability/corpus
  coverage ещё не доказаны.
- Stroke graph/width/cap/join: **PARTIAL**; dash/markers/swimlanes: **MISSING**.
- Opaque layer DAG/hidden completion: **PARTIAL+**.
- Solid/linear/radial appearance: **WIRED** where exact writer exists.
- Translucent joint ownership and late global `max_colors`: **MISSING/PARTIAL**.

### Runtime / export

- Persistent service, caches, warm proposal worker, one evidence pass, bounded
  contracts, anytime safe checkpoint: **WIRED**.
- SVG semantic delivery: **WIRED**.
- PDF/EPS/DXF semantic parity: **PARTIAL**.
- Native hot core и Balanced speed promotion: **NOT COMPLETE**.

## Оставшиеся blockers в правильном порядке

1. Дождаться ProposalNet v2; принять его только по fixed global gates и
   downstream candidate/quality ablation.
2. Реализовать explicit interface variables и factor constraints, затем
   обновлять interfaces для derived local-refinement lattice.
3. Реализовать bounded ordered translucent ownership (`K` contributions +
   background), не имитировать его одним opaque owner.
4. Закрыть оставшиеся text catastrophes на real corpus; отдельно измерить exact
   font retrieval, custom glyph и knockout/outline/shadow slices.
5. Завершить stroke dash/marker/z-order и layer cycle alternatives.
6. Перенести hierarchy/interface screening/exact small solve в native hot core,
   если profiling подтверждает их долю.
7. Запустить frozen Phase-12: VAI50 50/50, challenge 115/115, deterministic
   repeats, topology/speed/slice gates.
8. Провести новый blind live-SVG VAI court. Promotion только при parity >=50%,
   target >55%, без key slice <45% и без whole-scene catastrophes.

## Promotion gates, которые пока не закрыты

- **Completeness:** 50/50 + 115/115, 0 timeout/OOM — не запущено.
- **Topology:** shipping non-regression gate wired; абсолютные 0 whole-scene
  catastrophes ещё не достигнуты даже на `text-099`.
- **Proposal:** honest Recall@5 gates — v2 training.
- **Selector:** acceptable >=93%, catastrophic <=0.5% — нет frozen campaign.
- **Text:** GCR -70% vs Best, human >=75%, no class regression — не измерено.
- **VAI:** blind parity >=50%, target >55% — не измерено.
- **Speed:** warm p50 <=2 s, p95 <=5 s, no >15 s — targeted smokes недостаточны.

Итог: продолжать реализацию и измерения нужно; текущая система уже намного
безопаснее и точнее старого Best на найденных тонких масках, но VAI parity пока
не доказана.

# 2026-07-21 correction: explicit interface factors are now wired

This correction supersedes the older C06/C07 and REIR/CMIR/VSIR statements
above that say explicit interface variables or derived child interfaces are
missing.

- `CandidateMacroIR` now stores one canonical endpoint pair per interface and
  validates that every candidate claims exactly the interfaces crossed by its
  core ownership.
- Transactional local refinement reconstructs the complete 4-neighbour
  half-edge graph for child cells, remaps every atomic/base/typed column to the
  derived interface IDs, and reseals typed support certificates against those
  IDs.
- `VisibleSceneIR` now materializes exactly one deterministic geometry
  assignment for every internal interface. Active owner boundaries require
  symmetric claims from both selected macros; absorbed same-owner interfaces
  are explicit continuation geometries. Any mismatch fails closed.
- Layer-order cues now consume the final CMIR interface graph. Original REIR
  boundary observations are used only when the endpoint graph is identical,
  so derived IDs can never alias unrelated source evidence.
- Interface dual prices are a single factor (opposite-side claims are averaged,
  never double-counted), and every pricing oracle consumes each interface dual
  once.
- Verification: all `test_pcdc_*.py` tests pass (80/80), including derived
  child-interface symmetry and exact VSIR geometry assignment.

Remaining C06 limitation: the wider prerequisite/layer contribution graph is
still partial. Remaining C08 limitation: ordered translucent K-stack ownership
is still missing. These are separate from the now-wired opaque interface
factor contract.

# 2026-07-21 correction: ProposalNet status

The honest v2 candidate completed and failed promotion: overall Recall@5 was
0.95415 (<0.97), text/glyph 0.97961 (<0.99), layer 0.93970 (<0.95), small shape
0.96840 (<0.98), and conformal calibration was vacuous for layer relations.
It was not promoted. A v3 continuation from that exact checkpoint/split is
running; it remains a candidate until both the fixed gate and downstream PCDC
ablation pass.

# 2026-07-21 correction: additional literal plan gaps closed

- Layer §13.3 cycle handling now runs an exact maximum-confidence DAG order
  search inside every interaction component of at most eight owners. It uses
  a deterministic bounded greedy fallback only for larger components. This
  implements local cycle alternatives; the older C14 statement above is stale
  on that point.
- CMIR registry hashes now bind interface endpoints, every candidate boundary
  claim, and alpha bounds in addition to core/conflict/proof identity.
- Macro candidates carry finite measured alpha bounds. VSIR no longer labels a
  translucent owner as opaque: every cell is explicitly either one opaque
  owner, or one currently certified translucent contribution plus an explicit
  background and a hard contribution limit. Multi-contribution overlap remains
  missing, so C08 is improved but not closed.
- `pi_topology` and `pi_layer` are no longer inert zero fields. Immutable REIR
  topology/layer proposal residuals price only candidates that actually carry
  the corresponding topology or layer claim; every pricing oracle consumes
  those factors through the same reduced-gain function.
- Collinear rhythmic dash evidence (at least three components, bounded length,
  gap and normal-axis variance) is fitted as one centerline plus a measured
  `stroke-dasharray`, rerendered on the native lattice, and serialized by the
  SVG writer. Markers and swimlanes remain missing.
- `prerequisite_claims` is now a closed machine-checkable vocabulary. Every
  production claim is resolved against a concrete topology/geometry/render/
  support/structural/program invariant; an unknown or misspelled claim rejects
  the typed macro instead of being silently ignored.
- Because the CMIR wire contract changed (explicit endpoints and alpha bounds),
  its schema is now `pcdc-cmir/v2`; old v1 payloads cannot masquerade as the
  stronger format.
- Verification after these changes: all `test_pcdc_*.py` tests pass (82/82).

# 2026-07-21 correction: physical court, text routing, and remaining Phase-5 macros

This correction supersedes the older status rows for C08, ProposalNet v3,
markers/swimlanes, and single custom glyphs.

- Replacement ownership in the local production court is now composited with
  the canonical canvas background exactly as the SVG writer delivers it. It is
  no longer cleared to transparent black. On the real
  `88_icon_group_4_57_src.png` locus this removed the impossible colour-mass
  contradiction (candidate/fallback bounds are now about 0.107/0.118 rather
  than the old >2 error).
- The Bayesian renderer LCB is now factored through the fallback-conditioned
  posterior `q_F(m) ∝ w_m p(I|F,m)`. This posterior is fixed before inspecting
  candidate H, and `E_qF[delta] - z*sd_qF` is checked to remain below the exact
  marginal log Bayes factor. On the same real locus the erroneous prior-LCB
  changed from `-2123.645` to `+1121.347`; the TextLine now passes the local
  court. A genuinely ambiguous renderer posterior remains fail-closed.
- The `stable-small-component-line` REIR token now owns only its selected
  component labels. It no longer leaks a whole-image dark foreground mask into
  the text lane, and the bounded shortlist reserves one slot for this physical
  line proposal so a broad emblem token cannot starve it.
- ProposalNet v3 completed and failed the fixed promotion gate (overall
  Recall@5 0.957985, text 0.980921, glyph 0.976316, small 0.968404, layer
  0.957286; non-vacuous conformal false). It was not promoted. V4 is training
  from v3 with an added global top-5 ranking loss and remains candidate-only.
- Arrowhead evidence is represented by native SVG markers. Partitioned
  orthogonal frames are explicitly classified as swimlane structures. Dash,
  marker and swimlane support is therefore wired; broad real-corpus coverage
  is still unproven.
- `glyph_group` queries may now emit an explicit `single-custom-glyph` macro.
  It competes with font-free/conservative alternatives under the same support,
  topology and production-delivery court; arbitrary one-component foreground
  masks are still rejected without the typed query evidence.
- Ordered translucent ownership is now a real bounded macro, not a singleton
  label. Two overlapping translucent supports are fitted from exclusive
  pixels; both source-over orders are tested on a held-out overlap; only a
  low-residual identifiable order enters CMIR. The exact-cover solver selects
  the entire stack as one column, VSIR exposes its two ordered contributors
  plus background (`K=2`, hard maximum 3), and SVG emits the same two native
  Porter-Duff layers. Unidentifiable overlaps fail open to ordinary candidates.
  Three-layer proposal generation is not yet implemented even though the IR
  and validator allow `K<=3`.
- Current proof-carrying regression suite: 91/91 tests pass. This is an
  implementation invariant only; it does not establish VAI parity or close the
  frozen Phase-12 campaign.

Remaining text gap: typed knockout and outlined/shadowed text-group operators,
plus real-corpus catastrophe and human-preference targets. Remaining system
gaps: native hot core, semantic PDF/EPS/DXF parity, complete frozen campaigns,
and a new blind live-SVG VAI court.

# 2026-07-21 correction: exact free-curve delivery and deterministic master

- The production court used to certify `Shape/free_curve` from its internal
  mask while the writer could silently serialize a different generic contour.
  A hidden `_mask_to_path` typo also made every fitted-path attempt throw and
  return empty. The writer and court now share one `_free_curve_element`; the
  court renders that exact SVG fragment, and failure of its fitted-path proof
  rejects the typed candidate. There is no unproved generic fallback.
- On real `88_icon_group_4_57_src.png`, the former orange-underline culprit
  `shape-free_curve-87b3fa9d6e43a75a` can no longer create six pinholes in the
  final SVG. All 12 unsupported tiny free-curve alternatives fail closed before
  selection. The remaining full-scene rejection is a separate TextLine locus
  and is not counted as fixed here.
- Exact-component selection no longer commits a scheduler-dependent partial
  DFS when a wall-clock deadline expires. The time allowance is converted to a
  deterministic work certificate; exact search runs only when the complete
  component tree fits, otherwise that entire component uses the stable bounded
  fallback. A scheduler-jitter regression test verifies identical selected IDs
  and utility.
- Current full PCDC regression suite after these changes: 94/94 pass.

# 2026-07-21 correction: TextLine physical proof and honest human/GCR gates

- The TextLine certificate no longer promotes near-background AA pixels into
  opaque glyph bridges.  It derives a per-component physical coverage midline
  and requires connectivity to persist at 45/50/62 percent levels.  On real
  `88_icon_group_4_57_src.png` this separates the fused `L`/`i+n` support,
  removes the global `persistent_components_lost` regression, and allows the
  balanced result to commit at T2 rather than roll back to T0.
- Text proposal dedup now unions independent evidence provenance instead of
  discarding it with a losing duplicate score.  High-IoU masks with different
  topology are not duplicates.  Native microtext keeps one bounded,
  full-line, coverage-diverse shortlist slot; partial-word replacements fail a
  horizontal completeness wall.
- A dense inverse canvas can no longer masquerade as persistent text.  A
  separately proven both-polarity minority-ink line may replace it only when
  the incumbent is over 75 percent dense, contains at least 32 implausible
  holes, preserves the full line span, and wins exact render evidence by at
  least 0.12.  This fixes the real `chevereto` background-as-text failure.
- Glyph Catastrophe Rate was corrected from an unbounded absolute component/
  hole-count delta to component-correspondence accounting.  Each source glyph
  component is charged once for missing/split/fused/counter damage and every
  unsupported output component once.  One inverse canvas with 737 holes no
  longer counts as 733 independent glyph catastrophes.  IoU remains a
  separate fidelity metric.
- Font-free materialisation now checks component correspondence and IoU after
  SDF reconstruction, not just equality of aggregate topology counts.  It
  falls back to certified line support when thin glyphs move.  Repeated-glyph
  EM prototypes are now transactionally materialised into delivered geometry;
  per-instance and full-line topology/IoU walls reject unsafe prototypes.
- Human preference answers are cryptographically bound to both candidate and
  legacy mask digests plus the blinded side.  All 100 old answers are correctly
  marked stale after output changes; the previous apparent human pass must not
  be cited for the current algorithm.
- ProposalNet v4 completed and failed promotion: overall Recall@5 0.960439,
  text 0.983553, glyph 0.980263, small-shape 0.968404, layer 0.957286, with
  vacuous required-family conformal calibration.  It was not promoted.  V5 is
  training from the v4 checkpoint with target-weighted risk/small-shape and
  text/glyph mask, box, and global-top5 supervision; it remains candidate-only.
- Current honest font-free Experiment 4 (before the latest conservative
  replacement-margin rerun) has 100/100 topology non-regression and improves
  mean support IoU, but does not meet the 70 percent correspondence-GCR target.
  The old raw-count report is invalid under the corrected metric.  A new blind
  human court is required after outputs stabilize.
- Current full proof-carrying regression suite: 102/102 pass.  This still does
  not establish VAI parity.

# 2026-07-22 correction: Phase-5 execution closure and ProposalNet v11/v12

This correction supersedes every older statement that Phase 5 was fully
production-wired merely because its generators and Complexity Stress passed.

- All five Phase-5 generators remain implemented and bounded: whole shapes,
  stroke networks, appearance models, codec/detail counterfactuals and
  repeated-parameter groups.  `report_current_k4.json` passes all four
  Complexity Stress gates on all seven canonical cases; the largest observed
  Phase-5 candidate pool is 392 under the fixed 624-column ceiling.
- A production call-graph audit found that codec/detail candidates were in the
  shared CMIR and stress counts but `RuntimeMacroCourt` rejected every one as
  `unsupported_delivery`.  The lane is now closed end-to-end: court and SVG
  export share one raster-free, bounded pixel-run delivery restricted to the
  certified micro-locus.  No `<image>` or unrelated padded context is emitted.
- `risk_hard_negative` ProposalNet queries are now consumed before codec
  counterfactual fitting.  They may add a bounded micro-locus, but they grant no
  semantic keep/delete right: every alternative still uses the frozen
  image-level renderer posterior and the same production court.
- Phase-5 regression tests now include an execution assertion that a codec
  candidate is recognized by the production court rather than counted only by
  its generator, plus a bounded neural-risk query test.  The focused Phase-5
  suite passes 14/14 after the change.
- ProposalNet v11 (64x64 support head at 128px input) was honestly rejected,
  not promoted.  Test Recall@5 is overall 0.924916, text-line 0.827998,
  glyph-group 0.826834, small-shape 0.988673, layer 0.936620.  This is a large
  text gain over v9 (~0.71), but still far below the frozen 0.99 text/glyph
  gate and 0.97 overall gate; required conformal calibration remains vacuous.
- v11 failure decomposition proves the main deficit is geometry, not ranking:
  across 3,436 text/glyph targets, any-family top-32 geometry recall is
  0.858265, typed top-32 is 0.834983 and typed top-5 is 0.827998.  Approximate
  losses are therefore 14.17 percentage points geometry, 2.33 type and only
  0.70 rank.  Multi-row typed Recall@5 is 0.158470 and real local-owner text is
  0.360140, versus 0.870476 on synthetic text.
- The architectural cause found in that audit is that decoder memory was fed
  without explicit 2-D identity.  Equal-looking rows were effectively an
  unordered feature set.  v12 adds x/y and quadratic spatial coordinates to
  decoder memory and dynamic mask features while initializing every existing
  weight from v11.  It is training as a separate candidate; production remains
  on the prior safe checkpoint until fixed Recall@5, non-vacuous conformal and
  downstream OFF/ON gates all pass.
- The canonical Data Factory scale is not reached: current large pretraining
  has 60,190 rendered variants and 45 hardcoded font families, versus the plan
  target of 0.5--2M variants, millions of glyph crops and 2k--5k reviewed real
  loci.  The current real corpus has 300 reviewed loci, 205 with derived GT;
  v11/v12 large pretraining does not mix those loci into its 59,647 accepted
  raster/vector pairs.
- The separate real-locus trainer was stale at a hardcoded 32x32 support
  lattice and would fail against the v11/v12 64x64 head.  It also trained and
  gated text_line without the independently required glyph_group family, and
  allowed a wrong-family query into conformal best-example selection.  It now
  derives lattice size from checkpoint config, trains both text/glyph targets,
  gates glyph Recall@5 and conformal separately, filters calibration by type,
  and binds the fine-tune checkpoint to code+manifest+review hashes.
- The old 300-locus Experiment-9 `passed` report is not a promotion proof: its
  tiny calibration split produced threshold 1.0 in every family.  The current
  source-disjoint split has 47 calibration loci (only 4--14 per semantic
  class).  The
  corrected trainer requires at least 100 calibration examples and threshold
  below 1.0 for each required family, so it fails closed until the real corpus
  is expanded.
- A new read-only evaluation of immutable v11 on the current 44-locus
  source-disjoint reviewed test split exposes the actual domain gap: neural
  global Recall@5 is 0.477273 overall, 0.333333 text, 0.133333 glyph-group,
  0.714286 layer, 0.0 stroke, 0.0 gradient and 1.0 small-shape.  The report is
  `benchmarks/pcdc_proposal_large_v11_hires/real_locus_evaluation.json`.
  Therefore the 0.924916 synthetic/vector-pair overall score is not evidence
  that ProposalNet learned the real task.  v11 remains rejected and future
  model selection must expose this real diagnostic alongside synthetic gates.

This closes the discovered Phase-5 production disconnect.  It still does not
establish VAI parity: per-lane perceptual/VAI ablations, the frozen Phase-12
campaign and blind live-SVG comparison remain required.

# 2026-07-22 continuation: real transfer proof and balanced replay inputs

- v12's explicit 2-D position is now supported by both synthetic and real
  evidence. Its epoch-3 best improves synthetic weakest-gate selection to
  0.857017 and real test overall/text/layer Recall@5 to
  0.545455/0.466667/0.857143. It does not improve real glyph-group (0.133333)
  and leaves real stroke/gradient at 0.0, so it remains candidate-only.
- The previous real evaluator could appear to pass while rare typed classes
  were absent. It now requires stroke, gradient and codec/detail together
  with text, glyph, shape and layer, plus minimum held-out sample counts.
- Data Factory v2 now has two proof-bound supplements ready for the next
  ablation: 7,200 open-font explicit-owner text pairs and 8,000 typed structural
  pairs balanced across stroke/gradient/layer/repeat. A no-copy mixed manifest
  binds those to all 60,190 legacy replay pairs, for 75,390 total.
- Split preflight proves zero group overlap. The supplement contributes at
  least 136 calibration and 164 test pairs to every structural family, and
  600 calibration / 1,000 test pairs to each text/glyph family. Factory code,
  license/font manifest, source rows, pair rows and payload origins are hashed.
- These artifacts close the training-data plumbing gap, not the quality gate.
  Required next evidence is mixed-replay training, final real evaluation,
  non-vacuous conformal coverage, runtime OFF/ON ablation and blind VAI parity.

## Final v12 evidence

- All six spatial-ablation epochs completed. Epoch 6 is the bound best
  checkpoint; v12 remains rejected. Synthetic test Recall@5 is 0.928792
  overall, 0.839057 text, 0.839639 glyph, 0.991909 small-shape and 0.927817
  layer, with failed conformal and required gates.
- Final real test is 0.568182 overall, 0.533333 text, 0.133333 glyph, 0.857143
  layer, 0.0 stroke and 0.0 gradient. Every class nevertheless has
  geometry-any@32 = 1.0. The losses are now proved to be type/rank losses:
  text typed32/typed5 = 1.0/0.533333, glyph = 0.866667/0.133333, gradient =
  0.25/0.0 and stroke = 0.0/0.0.
- v13 consequently changes labels/data/replay and class gates while preserving
  the spatial geometry architecture. It does not hide the failure behind a
  new geometry head or lower threshold.

# 2026-07-22 correction: v13 is preflight-bound, not another blind version

- The initial v13 process was terminated before epoch 1 completed after an
  audit proved that old legacy scarcity weights distorted the new balanced
  structural replay. Conditional structure mass was 73.86% stroke but only
  2.19% layer. The corrected, hard-gated shares are 24.32--25.65% for all four
  typed families.
- A second stale assumption was removed before restart: risk hard-negative
  targets occur on about 87% of both new supplement strata, so their old
  sparse-corpus 1.65 class and 1.85 positive boosts over-weighted a slice that
  already passes its immutable baseline gate. The risk target/head/gate remain;
  only the obsolete extra multipliers are gone.
- A clean epochs=0 run revalidated every payload attestation, the filter cache,
  74,703 accepted labels, source/font/typed-structure split boundaries,
  calibration/test instance floors, global top-5 capacity and the exact
  30%/30%/40% replay contract. Current code, checkpoint and report agree on
  label-contract SHA256
  `6f1672dc700d51ec82820e3f6ddcf41c5710ec8f1d3144e10b921dfec1026033`.
- Full project discovery passes 231/231 tests. Exact contract sources and the
  epoch-0 checkpoint are archived before the clean v13 restart.
- The downstream proof chain was audited before training: v2 remains
  sidecar/gate bound, candidate calibration must match exact candidate bytes,
  Phase 12 checks every declared conformal family, and promotion additionally
  requires a valid complete BUILD_FREEZE. No v2 model is production-enabled by
  these compatibility changes alone.
- Remaining scale claims stay open: this is the next real-held-out learning
  curve point, not evidence for the eventual 0.5--2M rendered variants,
  million-glyph bank, 2k--5k reviewed real loci, or VAI parity.

# 2026-07-22 correction: Phase-0 class is not a Phase-9 model label

- The plan requires each real locus to have a reviewed macro family. The old UI
  stored only the six corpus sampling buckets, while Phase 9 silently mapped
  those buckets to neural query families. This violated the annotation
  contract: a filled arrow/badge/overlap chosen for the broad `diagrams`
  bucket was evaluated as `stroke_network`, and full clean design support in
  `codec_detail` was evaluated as a codec-risk support mask.
- `review.proposal_family` is now a separate typed field. Experiment 9 and the
  immutable evaluator accept only this explicit field; missing labels fail
  closed and are counted. An owned-SVG provenance migration safely typed 196
  loci and left 104 for review. No previous human mask or coarse Phase-0 field
  was overwritten.
- Consequently the old v11/v12/v13 structural real metrics are retained only
  as historical diagnostics under the invalid coarse mapping. The corrected
  typed subset is still too small and has zero proved stroke/risk loci, so it
  cannot authorize fine-tuning, conformal calibration, promotion or a VAI
  parity claim.

# 2026-07-22 Phase-5/model status after the v13 audit

- Phase 5 matches the document's five required implementation lanes and has
  production-path tests for each. Complexity Stress passes its bounded test
  battery. The phase is code-complete; perceptual/VAI parity remains open and
  cannot be inferred from those unit/stress gates.
- v13 is a failed learning-curve point, not the production model. The frozen
  required synthetic gates fail on overall, text, glyph, layer, stroke and
  repeat, and conformal sets remain vacuous. Corrected typed-real evidence is
  too small for promotion and lacks proved stroke/risk classes.
- The v13 text bottleneck is now localized to multi-instance support geometry,
  not family typing or top-5 ranking. Single lines are near 0.93 geometry
  recall, while two- and three-line owners collapse to roughly 0.54 and 0.14.
  This explains why adding fonts or epochs alone could not be treated as a
  sufficient fix.
- The retained pre-v14 change is a TextLine-only hard vertical ROI prior plus
  same-family instance exclusivity and correct sparse foreground balancing.
  Read-only bbox gating and train-only overfit probes support this direction;
  all-family gating, soft edges and full-batch optimization were measured and
  rejected.
- A new fail-closed trainer dependency implements the user's requested
  "check everything before training" rule. No expensive ProposalNet run may
  start until the exact candidate/data/config/current-code tuple passes a
  >=0.99 train-only two-/three-row overfit gate. The current bound probe passes
  at 1.000 on all 80 line instances. This closes only the instance-learning
  prerequisite; the broader pre-v14 readiness audit still blocks training on
  Phase-4, hard-negative, holdout, calibration and anti-forgetting evidence.
- Because the old test slice was used for root-cause parameter sweeps, future
  promotion requires a newly untouched holdout. New licensed font families
  are therefore useful. The former last multi-row instance failure is closed;
  incomplete typed-real coverage and the other readiness gaps remain.

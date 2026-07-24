---
title: "V-ICE PCDC: глыбокі аўдыт wordmark prior і план v10"
date: 2026-07-24
language: be
status: "canonical diagnosis and redesign proposal"
source_priority:
  - "2026-07-23 wordmark audit"
  - "2026-07-22 quality audit"
  - "2026-07-22 ProposalNet readiness audit"
  - "superseded construction ledger only as historical evidence"
core_verdict: "stop scaling v9; replace monolithic whole-line mask prediction with compositional topology-by-construction TextProgramMacro"
---

# V-ICE PCDC: глыбокі аўдыт wordmark prior і план v10

> **Паходжанне:** знешні рэцэнзент, 2026-07-24, на аснове нашых актуальных аўдытаў
> (`WORDMARK_V1_LIVE_AUDIT_BY.md`, `V_ICE_CURRENT_AUDIT.md`,
> `PRE_V14_READINESS_AUDIT.md` — гл. frontmatter вышэй). Апісаная гісторыя v4–v9 —
> рэальная гісторыя PCDC-часткі праекта (снапшоты
> `.training_snapshots/wordmark_full_*_20260723/`). Заўвага: PCDC-файлы жывуць
> у галоўным каталогу праекта і зараз не пад git — пойнтэры ў `CLAUDE.md`, Частка I.

## 0. Кароткі вердыкт

PCDC як агульная архітэктура **не правалілася**. REIR, CMIR, hierarchy, extractor,
fixed-posterior court, certificates, typed macros, continuous refinement, runtime budgets
і fail-closed promotion — правільны фундамент.

Бягучы blocker значна вузейшы:

> **Whole-line wordmark prior спрабуе аднавіць exact topology доўгага слова як адзін
> raster mask і некалькі глабальных count heads. Гэта representation ceiling, а не
> недахоп epochs, thresholds або яшчэ аднаго auxiliary head.**

v4–v8 ужо праверылі амаль усе «танныя» варыянты вакол гэтай representation:

- больш data/epochs;
- global counts;
- additive per-token counts;
- token/residual decomposition;
- spatial density heads;
- асобны encoder;
- decoder bridges/neck cuts;
- threshold calibration.

Яны не стварылі learning curve да production gate. v9 вярнуўся да best-known v5
матэматыкі і прайшоў толькі 300-step tiny-overfit. Таму яшчэ адзін full 2M v9 run
з высокай верагоднасцю будзе дарагім паўторам ужо адмоўнага эксперыменту.

## Канчатковая рэкамендацыя

Зрабіць **v10 TextProgramMacro**:

```text
variable-width raster line
+ OCR N-best / soft recognition features
+ explicit monotonic character layout
+ retrieved topology-bearing glyph templates
+ topology-preserving style deformation
+ explicit ligature/effect operators
+ per-character free-form fallback
→ K compositional TextLine programs
→ existing PCDC court and extractor
```

Ключавая змена:

- topology не «прадказваецца пасля pixels»;
- topology **канструюецца з glyph programs**;
- neural model прадказвае layout, style, variant і bounded deformation;
- PCDC выбірае паміж некалькімі line programs і legacy fallback.

Гэта medium-hard лакальная перабудова Phase 4, а не перапісванне ўсяго PCDC.

---

# 1. Якая справаздача цяпер з'яўляецца ісцінай

У дакументах ёсць гістарычныя супярэчнасці. Гэта нармальна для append-only engineering log,
але небяспечна для рашэнняў.

## 1.1. Прыярытэт крыніц

1. **Актуальны wordmark audit ад 2026-07-23** — галоўная крыніца.
2. **Quality/blocker audit ад 2026-07-22** — актуальная сістэмная ацэнка.
3. **ProposalNet readiness audit ад 2026-07-22** — актуальны `NO-TRAIN`.
4. **Historical construction status** — толькі доказ, што modules існавалі і некалі
   праходзілі construction gates. Ён сам пазначаны як superseded.

## 1.2. Што нельга лічыць актуальным proof

Historical Phase 4 паведамляў GCR reduction 76.4% і full pass. Пазнейшы audit знайшоў,
што primary GCR быў вылічаны не па планавым line-level вызначэнні. На тых жа outputs
line-level reduction быў каля 15.9%, а не 45–76%.

Таксама стары construction ledger не з'яўляецца production proof, бо пазнейшы audit
знайшоў disconnects паміж:

- implemented modules;
- runtime path;
- delivered SVG;
- proof bundle;
- current compiler hash.

## 1.3. Унутраная часовая супярэчнасць у апошнім wordmark audit

У пачатку файла гаворыцца пра v4 full run, які навучаецца. Але пазнейшыя numbered entries
68–74 ужо апісваюць:

- v4 epoch-3 diagnostic blocked;
- v5 negative representative smoke;
- v6 negative;
- v7/v8 negative;
- v9 як rollback да v5 з decoder fixes і толькі tiny-overfit proof.

Для рашэнняў трэба лічыць апошні numbered event аўтарытэтным:

> **Актыўная v9 не мае representative held-out proof і не мае права ісці ў full run.**

---

# 2. Што ў праекце сапраўды ўжо добра

Гэта важна, каб не перапісаць працуючы фундамент.

## 2.1. PCDC decomposition

У вас ужо ёсць правільнае раздзяленне:

```text
evidence
→ candidates/macros
→ extraction
→ court/certificates
→ refinement
→ export
```

Гэта значна мацней за стары monolithic Scene Engine.

## 2.2. Proposal/selector diagnostics

Раней праект не ведаў:

- correct candidate адсутнічае;
- correct candidate ёсць, але selector памыляецца;
- renderer памыляецца;
- proof stale.

Цяпер гэтыя failure modes у асноўным разведзены.

## 2.3. Fail-closed lifecycle

Checkpoint не ўключаецца толькі таму, што файл існуе. Promotion прывязаны да:

- model/data contract;
- trainer/evaluator source;
- checkpoint hash;
- Experiment 4 OFF/ON;
- full regression;
- preflight;
- runtime manifest;
- BUILD_FREEZE artifacts.

Гэта вельмі добрая production discipline.

## 2.4. Runtime architecture

Хвілінныя tails старога Scene Engine прыбраны:

- persistent workers;
- bounded budgets;
- Rust core;
- exact ROI atlas;
- valid anytime fallback.

Current historical Experiment 10 паказваў sub-3.2 s p95 нават у Max на малым
real-locus campaign. Гэта не канчатковы production proof, але architecture больш не
выглядае fundamentally exponential.

## 2.5. Data/audit hygiene

Ужо закрыты сур'ёзныя класы памылак:

- train/test threshold leakage;
- OCR bag-of-characters;
- serving vocabulary gaps;
- length range gaps;
- nondeterministic CUDA op;
- checkpoint live alias;
- stale REIR caches;
- concurrent cache publication;
- resource leaks;
- corpus payload attestation;
- evaluator SHA staleness;
- exact delivered-output OFF/ON proof.

Гэта азначае, што наступны model failure будзе значна больш інфарматыўным.

---

# 3. Дакладная гісторыя wordmark prior

## 3.1. Стары per-glyph prior

Ён:

- навучыўся на synthetic held-out;
- але не змяніў ніводнага з 100 delivered TextLine SVG;
- таму не быў production mechanism;
- правільна застаўся disabled optional lane.

Гэта быў downstream-effect failure: нават добры standalone score не дасягнуў shipping path.

## 3.2. Whole-line v4

Мэта была разумнай: пазбавіцца character-cell seams і прадказваць wordmark цалкам.

На 2M recipe epoch 3:

```text
support IoU              0.91793
exact topology           0.53100
complex topology         0.48967
component head           0.7393
hole head                0.5898
joint exact              0.4995
```

Support добры, topology дрэнная.

### Length decomposition

```text
length 1:
  component/hole 0.968 / 0.968
  raw topology   0.942

length 2:
  component/hole 0.962 / 0.934
  raw topology   0.925

length 17–32:
  component      0.604
  hole           0.417
  joint          0.296
  raw topology   0.323
```

Гэта галоўны дыягнастычны факт усяго праекта.

### Observability decomposition

Калі degraded input яшчэ захоўвае topology:

```text
joint head 0.870
raw mask   0.924
```

Калі degradation topology разбурыў:

```text
joint head 0.401
raw mask   0.425
```

То-бок мадэль добра чысціць тое, што ўжо бачыць, але слаба аднаўляе latent glyph structure,
калі pixels сапраўды неідэнтыфікаваныя.

## 3.3. v5

Дададзены:

- additive per-glyph count prior;
- complexity balancing;
- topology-weighted support;
- decoder repairs.

Representative 8,192-unique / 10-epoch test:

```text
support                   0.85189
decoded topology          0.29980
complex topology          0.25488
component/hole/joint      0.32178 / 0.16846 / 0.07861
length 17–32 topology     0.15696
repair eligibility        2.69%
```

Oracle analysis:

```text
best fixed threshold exact       0.20947
per-sample threshold oracle      0.33105
head + support oracle            0.34619
```

Гэта закрыла гіпотэзу «патрэбен лепшы threshold/fusion».

## 3.4. v6

Canonical per-token targets і line residual supervision:

- істотна палепшылі continuous count MAE;
- пагоршылі categorical joint;
- не палепшылі decoded topology;
- 32k probe застаўся каля 0.302 topology.

Гэта паказвае:

> Лепшая рэгрэсія counts не ператвараецца ў правільную spatial topology.

## 3.5. v7/v8

Spatial component/counter density heads:

- perfect-overfit;
- collapsed на unseen fonts;
- асобны encoder не выратаваў;
- topology засталася каля 0.30.

Гэта закрывае гіпотэзу «count head проста павінен быць spatial».

## 3.6. v9

v9:

- вяртае best-known v5 architecture;
- захоўвае AMP fix;
- захоўвае decoder bridge/neck repairs;
- праходзіць 300-step smoke з perfect metrics.

Але perfect 300-step smoke ўжо шмат разоў не прадказваў held-out behavior.

### Вывад

v9 з'яўляецца **code stabilization**, не новай model hypothesis.

---

# 4. Чаму topology падае з даўжынёй: матэматычны разбор

## 4.1. Exact-line metric multiplicative

Няхай верагоднасць правільнай topology аднаго glyph — `p`.

Калі line exact патрабуе, каб усе `L` glyphs былі правільнымі:

```math
P(line exact) ≈ p^L
```

Каб атрымаць 95% exact topology:

```text
L=17 → p ≈ 99.699%
L=32 → p ≈ 99.840%
```

Нават вельмі добрая per-glyph accuracy 96.5% дае:

```text
0.965^32 ≈ 0.320
```

Гэта амаль дакладна супадае з observed long-line raw topology `0.323`.

## 4.2. Што гэта азначае

Observed 0.323 не абавязкова азначае, што кожны glyph жахлівы.

Гэта можа азначаць:

- большасць glyphs правільная;
- але амаль у кожным доўгім wordmark ёсць адзін counter/bridge/component error.

Для чалавечага ўспрымання гэта ўсё роўна catastrophe: адной зламанай літары дастаткова.

## 4.3. Чаму monolithic mask decoder амаль не можа прайсці gate

Каб адзін stochastic pixel decoder даў 95% exact topology на 32-char lines, ён мусіць
мець амаль 99.84% topology reliability на кожным glyph, уключаючы:

- tiny counters;
- dots;
- weak bridges;
- OCR errors;
- unseen font families;
- JPEG/gamma/blur;
- outlines і shadows.

Гэта нерэалістычная форма гарантыі для binary-mask prediction.

## 4.4. Як прайсці gate рэальна

Topology павінна быць:

- узята з discrete glyph template/program;
- захавана topology-preserving deformation;
- зменена толькі explicit topology operator;
- праверана line-level court.

Тады model не павінен «выпадкова не перарэзаць bridge» 32 разы запар.
Bridge існуе ў program па канструкцыі.

---

# 5. Ранжыраваны diagnosis

## D1 — Representation ceiling: вельмі высокая ўпэўненасць, critical impact

Whole-line support mask + global/component/hole heads — няправільная output representation.

Праблемы:

- topology — глабальная статыстыка, не construction;
- count не паказвае, дзе hole/component;
- pixel decoder можа зрабіць любую колькасць tiny topology flips;
- exact topology становіцца выпадковым вынікам threshold;
- decoder repair працуе толькі на 2.7–10.2% cases;
- long-line exact error multiplicative.

### Evidence

Усе v4–v8 змены losses/heads не зрушылі representative topology вышэй ~0.30–0.55.

### Fix difficulty

**Medium-hard**, але лакальна ў TextLine lane.

---

## D2 — Missing explicit token-to-spatial alignment: высокая ўпэўненасць

Ordered BiGRU выправіў anagram bug, але ordered sequence embedding яшчэ не гарантуе:

- які character адпавядае якім columns;
- дзе яго left/right bounds;
- дзе baseline;
- дзе overlap;
- дзе ligature;
- які local visual evidence належыць token.

Публічныя text-мадэлі, якія добра трымаюць структуру, выразна мадэлююць:

- ordered points;
- character positions;
- local glyph features;
- global line interactions.

### Fix difficulty

**Medium**.

---

## D3 — Spatial-resolution / fixed-canvas bottleneck: высокая верагоднасць, яшчэ не даказана

Length 1–2 амаль праходзіць; 17–32 collapsing.

Магчымыя прычыны:

1. long lines фізічна сціскаюцца ў fixed-width tensor;
2. model receptive field/attention dilute local details;
3. global heads маюць вялікі count range;
4. exact metric compounding.

Трэба аддзяліць гэта ад compositional failure праз px-per-glyph matrix.

### Fix difficulty

- variable-width/dynamic padding: **easy-medium**;
- tiled/local-global transformer: **medium**.

---

## D4 — Hard OCR conditioning under corruption: высокая верагоднасць

Калі training дае няправільны hard OCR string, але патрабуе clean target, model атрымлівае
супярэчлівую задачу:

- слухаць OCR → намаляваць няправільныя glyphs;
- ігнараваць OCR → мінімізаваць visual loss.

У выніку conditioning можа стаць слабым або шкодным.

### Fix

- OCR N-best;
- token posterior/CTC lattice;
- confidence;
- non-categorical recognizer features;
- explicit unknown token;
- асобны candidate на кожную transcript hypothesis.

### Fix difficulty

**Medium**.

---

## D5 — Style diversity bottleneck: высокая верагоднасць

2,000,000 variants — не 2,000,000 font styles.

Current bank:

```text
81 families
241 faces
```

Гэта добра для reproducibility, але слаба для custom logos і unseen display lettering.

Rendering/degradation diversity не заменіць shape/style diversity.

### Fix

- тысячы open font families;
- variable-font axes;
- procedural topology variants;
- style deformations;
- outlines/inlines/shadows/stencil/ligatures;
- real logo-locus calibration.

### Fix difficulty

**Data-engineering heavy, mathematically straightforward**.

---

## D6 — Pixel loss underweights topology-critical pixels: высокая ўпэўненасць

Counter boundary або one-pixel bridge можа складаць <0.1% line crop.

Pixel loss атрымлівае вялікі gain ад bulk stems і амаль не карае:

- адзін запоўнены hole;
- адзін cut bridge;
- fused adjacent glyphs;
- missing dot.

### Fix

Нават у v10 патрэбны:

- per-glyph normalized loss;
- per-hole/per-component normalized loss;
- topology-critical pixel weighting;
- SDF/corner losses;
- character recognition cycle;
- exact program topology gate.

Але loss alone не заменіць representation.

### Fix difficulty

**Easy-medium пасля compositional representation**.

---

## D7 — Repair topology after decoding: высокая ўпэўненасць

Post-decoder bridge/neck repair карысны як safety net, але не як core generator.

Repair eligibility:

```text
2.69% у v5 smoke
10.2% у v4 diagnostic
```

Большасць topology errors не даходзіць да repair.

### Fix

Topology by construction; repair застаецца толькі для free-form fallback.

---

## D8 — Promotion gate змешвае proposal quality і final-output quality: сярэдне-высокая ўпэўненасць

Wordmark prior — proposal source ў PCDC.

Але standalone gate патрабуе top-1 exact topology 0.95 на ўсім distribution.

Для ambiguous degraded OCR гэта можа быць неідэнтыфікавана.

Правільнае раздзяленне:

### Proposal model gate

- topology/support Recall@K;
- transcript Recall@K;
- calibration;
- candidate diversity;
- no impossible candidate;
- runtime.

### Delivered-system gate

- exact topology/GCR;
- no line regression;
- human preference;
- OFF/ON delivered SVG;
- PCDC selector quality.

Top-1 standalone accuracy застаецца diagnostic, не адзіным promotion law.

---

## D9 — Proof graph / stale-report treadmill: высокая ўпэўненасць, medium impact

Пасля амаль кожнай runtime/compiler праўкі Experiments 1/1B/2/3/5 становяцца stale.

Гэта правільна fail-closed, але занадта грубы dependency hash ператварае працу ў rerun treadmill.

### Fix

Machine-generated transitive proof DAG:

```text
artifact
  depends_on:
    semantic model AST hash
    data contract hash
    relevant runtime closure hash
    relevant evaluator closure hash
    dataset payload hash
```

Змена wordmark decoder не павінна invalidated unrelated stroke experiment, калі іх
dependency closures не перасякаюцца.

### Fix difficulty

**Easy-medium**, вялікая эканомія часу.

---

## D10 — ProposalNet не з'яўляецца цяперашнім blocker: вельмі высокая ўпэўненасць

ProposalNet v14 правільна `NO-TRAIN`.

Пакуль TextLine generator не мае production-quality candidate family, ProposalNet толькі
хутчэй прапануе слабыя candidates.

---

# 6. Што не рабіць

## Не запускаць full v9 2M

v9 не новая hypothesis. Ён вяртаецца да v5, якая ўжо праваліла representative unseen pilot.

## Не дадаваць v10 count head

Global, additive, spatial density counts ужо правераны.

## Не паніжаць topology gate

Гэта толькі схавае чалавечую catastrophe.

## Не павялічваць repair confidence coverage штучна

Repair, які працуе на слабых random predictions, ужо быў асобна закрыты.

## Не рабіць ProposalNet раней TextLine v10

Proposal recall слабога macro не дае якасці.

## Не лічыць 2M variants доказам data scale

Патрэбна learning curve па **unique font families/topology styles**, не па колькасці
degradation samples.

---

# 7. VAI SVG forensics: важны знешні доказ

Аналіз загружаных VAI SVG дае моцную structural падказку.

## eyecon

- роўна 6 filled paths;
- 6 spatially separated letters;
- disconnected/counter parts захоўваюцца як subpaths аднаго glyph;
- няма `<text>` element;
- mixed `A/Q/C/L` geometry.

## enterra

- 1 symbol path + 7 letter paths;
- два repeated `e` пасля незалежнага rasterize/crop/normalize маюць silhouette IoU `0.983`;
- два repeated `r` маюць IoU `0.988`;
- raw SVG `d` не exact-identical, то-бок гэта не проста copy-transform;
- моцна сумяшчальна з shared glyph prototype або line-level repeated-glyph regularity.

## Вывад

VAI output выглядае:

```text
one glyph-level shape per character
+ compound subpaths for counters/disconnected parts
+ strong repeated-glyph consistency
```

Гэта падтрымлівае compositional TextLine program значна мацней, чым whole-line mask.

---

# 8. v10: Compositional Topology-by-Construction Wordmark Prior

Назва модуля:

# `TextProgramMacro v10`

## 8.1. Выхад мадэлі

Не адзін mask.

Мадэль выдае `K` line programs:

```python
TextLineProgram:
    transcript_hypothesis
    line_geometry
    global_style
    glyph_instances[]
    pair_interactions[]
    line_effects[]
    topology_signature
    confidence
```

Кожны glyph:

```python
GlyphInstance:
    character_or_unknown
    topology_variant
    template_id
    affine_layout
    topology_preserving_warp
    local_style_residual
    positive_loops
    negative_loops
```

---

## 8.2. Input representation

### Raster

- normalize line orientation;
- normalize height;
- **preserve aspect ratio and pixels-per-glyph**;
- dynamic width/padding;
- для very long lines — sliding/local-global encoding, не squeeze.

### REIR channels

- linear luminance/chroma;
- coverage/alpha evidence;
- boundary strength;
- signed distance to stable threshold masks;
- gradient/normal;
- component-tree features;
- source confidence.

### OCR

Не адзін hard string.

- N-best transcripts;
- per-token probabilities;
- CTC lattice/penultimate features;
- confidence;
- unknown token;
- optional unconditioned candidate.

---

## 8.3. Visual encoder

Hybrid:

- convolutional stem для local edges/counters;
- column/patch tokens;
- local-window attention;
- global line tokens;
- no global average pooling as the only spatial summary.

---

## 8.4. Explicit monotonic layout head

Адзін ordered query на token.

Прадказвае:

- glyph center;
- width;
- height;
- baseline offset;
- affine transform;
- kerning;
- overlap;
- visibility;
- ligature membership.

Constraints:

```text
centers monotonic
width > 0
bounded overlap
shared baseline/x-height/cap classes
```

Training спачатку з oracle boxes з vector font source.

---

## 8.5. Style encoder

Два ўзроўні.

### Global style

- weight;
- contrast;
- slant;
- terminal family;
- corner roundness;
- width/proportion;
- overall deformation.

### Local style

- per-glyph patches;
- character-dependent details;
- local terminal/curve behavior.

Training:

- same-font different-text consistency;
- different-font contrastive separation;
- cross-reconstruction:
  style from word A + content of word B → font A word B.

---

## 8.6. Template retrieval bank

З вялікай legal font library.

Для кожнага character:

- retrieve top-K topology/style-near glyph templates;
- include common topology variants;
- include variable-font axis samples;
- include generic archetypes.

Retrieval can be:

- precomputed glyph embeddings;
- approximate nearest neighbor;
- line-level style shortlist;
- per-character refinement.

### Чаму retrieval

Topology template ужо мае:

- correct components;
- correct counters;
- legal curves;
- editable structure.

Мадэль не павінна навучацца нанава, што `B` звычайна мае два counters.

---

## 8.7. Topology-preserving deformation

Асноўны glyph path:

```text
template glyph
→ diffeomorphic/bijective bounded warp
→ style operators
```

Topology-preserving warp не можа:

- стварыць hole;
- закрыць hole;
- разарваць component;
- зліць components.

Гэта дае topology guarantee by construction.

Losses:

- source render fit;
- smoothness;
- Jacobian positivity;
- bounded deformation;
- corner correspondence;
- shared line style.

---

## 8.8. Explicit topology-changing operators

Некаторыя styles сапраўды змяняюць topology.

Яны не павінны ўзнікаць як pixel accident.

Discrete operators:

- single-/double-story `a/g`;
- open/closed `4`;
- slashed zero;
- stencil cuts;
- disconnected dot/accent;
- inline;
- outline;
- shadow;
- deliberate gap/break;
- ligature;
- connected script;
- knockout.

Кожны operator мае:

- known topology delta;
- source evidence gate;
- separate candidate;
- PCDC certificate.

---

## 8.9. Free-form fallback glyph

Для сапраўды custom lettering, дзе font template не падыходзіць:

```text
image crop
+ character/unknown
+ style
→ SDF
+ probabilistic corner field
+ positive/negative loop candidates
```

Выкарыстоўваць ідэі:

- VecFontSDF;
- Joint SDF + Corner Field;
- DualVector positive/negative loops.

Гэта fallback candidate, не default для ўсіх glyphs.

---

## 8.10. Whole-line composition без cell seams

Glyph fields змяшчаюцца на shared line canvas.

- union/boolean composition;
- overlaps allowed;
- counters remain negative paths;
- no clipping to independent character cells;
- pair interaction fields для adjacent glyphs;
- line effects асобнымі layers.

Так вы захоўваеце перавагу whole-line route, але topology compositional.

---

## 8.11. Pairwise/short-span interaction model

Для:

- ligatures;
- cursive joins;
- touching letters;
- shared strokes;
- kerning-induced overlaps.

Model на spans даўжыні 2–4:

```text
none
overlap only
join
ligature
shared stroke
deliberate separation
```

Гэта значна лягчэй, чым генерыраваць усю 32-char topology адным mask decoder.

---

## 8.12. Inference solver

Для кожнай OCR hypothesis:

- K glyph variants per position;
- pair interaction variants;
- layout score;
- style consistency;
- local raster evidence.

Semi-Markov / dynamic-programming selection:

```text
O(L · K² · interaction_states)
```

Выдаць 4–16 finalists.

PCDC court:

- rerender;
- topology certificate;
- source support;
- OCR/readability;
- baseline comparison;
- exact delivery.

---

# 9. Самы хуткі практычны выйгрыш: v9.5 Template-Warp lane

Поўная v10 можа заняць некалькі engineering iterations.

Прамежкавы production-safe lane:

## 9.1. Candidate generation

1. OCR N-best.
2. Retrieve top 8–16 fonts/styles.
3. Render whole line.
4. Optimize:
   - scale;
   - tracking;
   - x/y anisotropy;
   - slant;
   - per-glyph width/offset;
   - bounded SDF warp.
5. Preserve template topology.
6. Submit candidates to existing court.

## 9.2. Exact-font lane застаецца асобнай

- strict exact match;
- true font outlines;
- current wall не паніжаць.

Approximate template lane:

- не сцвярджае, што знайшоў font;
- з'яўляецца semantic proposal;
- можа быць адхілены court.

## 9.3. Чаму гэта можа даць вялікі gain хутка

- counters/components legal by construction;
- line consistency;
- repeated glyphs;
- editable curves;
- нізкая inference cost;
- выкарыстоўвае ўжо гатовы PCDC court.

## 9.4. Абмежаванні

Не закрые:

- extreme custom lettering;
- pictographic glyphs;
- complex connected scripts;
- non-font logo marks.

Для іх патрэбны free-form v10 branch.

---

# 10. Training curriculum v10

## Stage A — Clean glyph program prior

Input:

```text
character
font/style references
```

Output:

- template shortlist;
- topology variant;
- SDF/curve deformation;
- corner field.

No blur/JPEG.

Gate:

```text
unseen-family per-glyph topology >99.9%
vector/render fidelity
```

## Stage B — Clean line layout/compositor

- variable length 1–32;
- dynamic width;
- oracle transcript;
- oracle character boxes;
- ligatures/effects.

Gate:

```text
line exact topology >99%
layout accuracy
```

## Stage C — Visual layout inference

- remove oracle boxes;
- infer ordered token positions from clean raster.

Gate:

```text
layout Recall@K
per-glyph crop ownership
```

## Stage D — Degradation inverse encoder

- freeze most glyph generator initially;
- blur/JPEG/gamma/resampling;
- recover style/layout from degraded source.

Gate:

```text
candidate topology Recall@K, not only top-1 mask
```

## Stage E — OCR uncertainty

- exact transcript;
- N-best;
- soft features;
- substitutions/deletions/insertions;
- unknown token.

Wrong hard transcript always explicitly marked as uncertain.

## Stage F — Real-locus ranking/calibration

- minimal real annotations;
- candidate preferences;
- topology requirements;
- delivered SVG effect.

---

# 11. Data redesign

## 11.1. Measure diversity correctly

Track separately:

```text
unique families
unique faces
variable-axis samples
glyph topology variants
line effects
source strings
renderers
degradations
```

`2M variants` alone is not useful.

## 11.2. Font families

Current 81 families are insufficient for broad style generalization.

Use:

- full legally usable Google Fonts repository;
- variable fonts;
- other auditable OFL/Apache collections;
- deduplicate near-identical families;
- split by family and upstream project.

## 11.3. Topology variants

Explicitly generate:

- a/g variants;
- 4 variants;
- zero/Ø/slash;
- dotted/disconnected glyphs;
- stencils;
- inline/outline;
- shadows;
- ligatures;
- custom breaks;
- connected scripts;
- condensed/extended forms.

## 11.4. Renderer diversity

- FreeType;
- DirectWrite;
- browser/Skia;
- Cairo/resvg;
- Pillow;
- custom analytic renderer;
- hinting on/off;
- subpixel phases;
- hold out at least one entire renderer family.

## 11.5. Complexity-balanced sampler

Balance by:

- length bucket;
- pixels per glyph;
- number of components;
- number of holes;
- glyph with tiny counters;
- effect class;
- OCR severity;
- font family;
- renderer;
- degradation.

Do not let simple sans-serif uppercase dominate.

## 11.6. Real data

Current 300-locus corpus is enough for diagnostics, not final calibration.

Target:

- 2k–5k reviewed loci;
- multi-instance annotation;
- enough per rare family;
- source-group-disjoint splits.

---

# 12. Losses

## 12.1. Primary losses

### Layout

- center/width/height;
- baseline;
- monotonicity;
- kerning;
- overlap state.

### Template/variant

- retrieval ranking;
- topology variant classification;
- OCR transcript ranking.

### Glyph geometry

- SDF;
- coverage;
- boundary;
- corner field;
- curve samples;
- warp smoothness/Jacobian.

### Style

- same-font consistency;
- contrastive family/style;
- global/local disentanglement.

### Composition

- whole-line render;
- character recognition cycle;
- repeated-glyph consistency;
- pair interaction.

## 12.2. Topology losses

Topology by construction — primary guarantee.

Для free-form branch auxiliary:

- per-component normalized loss;
- per-hole normalized loss;
- Betti matching / spatial-aware persistence;
- Topograph-like critical region loss;
- clDice only for thin stroke connectivity.

## 12.3. Critical pixel weighting

Upweight pixels whose flip changes:

- component count;
- hole count;
- glyph ownership;
- bridge connectivity.

Гэта можна атрымаць з digital topology simple-point analysis на GT masks.

## 12.4. Не выкарыстоўваць

- global count MAE як галоўны signal;
- адзін Euler scalar;
- pure pixel BCE/Dice;
- topology repair як core objective.

---

# 13. OCR conditioning

## 13.1. Чаму hard OCR небяспечны

Калі transcript wrong, categorical prior можа прымусіць model намаляваць не той character.

## 13.2. Правільны interface

```python
RecognitionCondition:
    nbest_strings
    nbest_log_probs
    per_position_token_probs
    recognizer_features
    confidence
    unknown_probability
```

## 13.3. Candidate policy

- high confidence → вузкі transcript set;
- medium → 4–8 hypotheses;
- low → unconditioned/custom-glyph candidate + legacy;
- no OCR → glyph-group/whole-shape paths remain available.

## 13.4. Training

Ніколі не падаваць wrong hard token як быццам ён correct truth.

Выкарыстоўваць:

- soft labels;
- explicit corrupted flag;
- candidate ranking;
- transcript marginalization.

---

# 14. Правільныя метрыкі

## 14.1. Per-glyph

- component exact;
- hole exact;
- topology exact;
- support IoU;
- boundary F;
- corner error.

## 14.2. Whole line

- exact line topology;
- topology edit distance;
- Glyph Catastrophe Rate;
- worst-character CVaR;
- OCR readability;
- repeated-glyph consistency.

## 14.3. Candidate model

- transcript Recall@K;
- topology Recall@K;
- support Recall@K;
- oracle-best delivered render;
- calibration;
- diversity without duplicates.

## 14.4. Selector

- accuracy conditional on acceptable candidate existing;
- catastrophic selection rate;
- fallback correctness.

## 14.5. Length-normalized dashboard

Абавязкова plot:

```text
metric vs length
metric vs pixels/glyph
metric vs holes/glyph
metric vs components/glyph
metric vs OCR corruption
```

Aggregate mean хавае галоўны failure.

---

# 15. Promotion gates: прапанаваная карэкцыя

## 15.1. v10 proposal model

### Clean/oracle-transcript

```text
per-glyph topology >=99.9%
line topology >=99% on length 1–32
```

### Degraded candidate generator

```text
topology Recall@8 >=99%
support Recall@8 >=99%
transcript Recall@K >=99% on OCR-observable subset
no class floor <97%
```

### Runtime

```text
warm p95 candidate generation <100 ms/line
```

## 15.2. Delivered PCDC system

```text
line exact topology >=95% identifiable subset
zero reviewed topology regression
GCR reduction >=70%
mean IoU non-regression
human decisive preference >=75% vs legacy
```

Ambiguous/unidentifiable cases:

- calibrated abstention/fallback;
- no forced hallucination;
- candidate-set coverage metric.

## 15.3. Exact-font

Keep current strict wall.

## 15.4. Approximate-template lane

Promotion based on delivered OFF/ON output, not font identity.

---

# 16. Рашальныя эксперыменты да новага вялікага train

## Experiment A — Length × pixels-per-glyph matrix

### Setup

Адны і тыя ж font families і strings:

1. current canvas policy;
2. dynamic width, fixed pixels/glyph;
3. multiple pixels/glyph levels.

Lengths:

```text
1, 2, 4, 8, 16, 24, 32
```

### Signal

Калі dynamic width рэзка аднаўляе long topology — галоўны bottleneck spatial resolution.

### Stop

Не запускаць v10 full training, пакуль гэта не вымерана.

---

## Experiment B — Clean-input identity test

Input = clean target, oracle OCR.

### Interpretation

- long topology <95% → output representation/alignment fundamentally wrong;
- clean passes, degraded fails → inverse encoder/data problem.

---

## Experiment C — Oracle layout

Падаць exact character boxes/placements.

### Interpretation

- topology jumps → alignment head is bottleneck;
- no jump → glyph/style generator is bottleneck.

---

## Experiment D — Oracle template/style

Падаць true font template або nearest known template.

### Interpretation

- topology/render jumps → retrieval/template lane has high value;
- little gain → custom/free-form branch needed.

---

## Experiment E — OCR conditioning matrix

Compare:

- exact transcript;
- hard corrupted;
- N-best;
- token posterior;
- penultimate recognizer feature;
- no OCR.

### Stop

Калі hard corrupted worse, забараніць яго ў production interface.

---

## Experiment F — Candidate topology Recall@K

Generate K variants per glyph/line.

Measure:

- correct topology present?
- court selects it?

Гэта аддзяляе generator vs selector.

---

## Experiment G — Style-family learning curve

Hold total samples constant.

Train on:

```text
81
300
1000+
families
```

Plot unseen-family topology.

### Interpretation

Калі curve расце з families, не з epochs — data style diversity confirmed.

---

## Experiment H — v9.5 template lane

На 100 real lines:

- exact font;
- approximate template top-8;
- template + bounded warp;
- legacy.

Gate:

```text
GCR improvement
human preference
topology non-regression
p95
```

Гэта найбольш інфармацыйна-танны production experiment.

---

# 17. Рэкамендаваны implementation order

## Step 0 — Stop

- не запускаць full v9;
- ProposalNet застаецца NO-TRAIN;
- зафіксаваць diagnostics checkpoint.

## Step 1 — Metrics and datasets

- per-glyph annotations;
- length/px-per-glyph metrics;
- topology edit distance;
- candidate Recall@K;
- current-state machine report.

## Step 2 — v9.5 template lane

- expanded font bank;
- style retrieval;
- OCR N-best;
- whole-line template optimization;
- bounded SDF warp;
- PCDC candidates.

## Step 3 — v10 layout

- variable-width encoder;
- ordered token queries;
- oracle-layout curriculum;
- line metric variables.

## Step 4 — topology-by-construction glyph program

- template topology variants;
- diffeomorphic deformation;
- explicit effects/operators;
- positive/negative loops.

## Step 5 — free-form glyph fallback

- SDF + corner field;
- DualVector-like loops;
- top-K candidates.

## Step 6 — line interactions

- ligatures;
- overlaps;
- outlines/shadows;
- repeated glyph EM.

## Step 7 — degraded inverse encoder

- renderer diversity;
- OCR uncertainty;
- complexity-balanced training.

## Step 8 — real calibration

- expand loci;
- candidate ranking;
- human court.

## Step 9 — hash-bound reruns

- current dependency proof graph;
- Experiments 1/1B/2/3/4/5 only after source freeze;
- then ProposalNet readiness.

---

# 18. Наколькі гэта лёгка выправіць

## Easy: некалькі дзён engineering

- спыніць v9;
- зрабіць length/px-per-glyph matrix;
- clean/oracle layout tests;
- per-glyph metric;
- proof dependency DAG;
- VAI structure forensics;
- dynamic-width loader prototype.

## Medium: адзін сур'ёзны iteration

- approximate font-template lane;
- OCR N-best interface;
- explicit layout head;
- semi-Markov candidate selection;
- large font retrieval bank.

Гэта ўжо можа даць вялікі practical quality gain.

## Medium-hard: асноўная v10

- topology-preserving glyph deformation;
- explicit topology variants;
- line compositor;
- style disentanglement;
- candidate training/evaluation.

Гэта не перапіс PCDC, але новы TextLine generator.

## Hard, optional second wave

- robust free-form direct vector decoder;
- extreme custom logos;
- multilingual scripts;
- full direct SVG generation.

Не трэба чакаць гэтага, каб перамагчы бягучыя wordmark failures.

---

# 19. Чаканы вынік

## Калі зрабіць толькі v9.5

Верагодны gain:

- clear/medium custom wordmarks;
- counters;
- repeated letters;
- line consistency;
- speed.

Не закрые ўсе custom marks.

## Калі зрабіць v10 compositional

Мэта рэалістычная:

- topology by construction;
- long lines не маюць stochastic line-mask failure;
- repeated glyphs consistent;
- no character-cell seams;
- OCR uncertainty represented;
- editable per-glyph output;
- PCDC retains fail-closed safety.

## Што застанецца пасля v10

- unknown pictorial marks;
- extremely degraded unidentifiable text;
- complex connected scripts;
- non-text ProposalNet scale/calibration;
- Phase 12 VAI campaign.

---

# 20. Асноўны research basis

## Glyph/global-local structure

- GlyphMastero, CVPR 2025:
  local individual characters + global text-line interactions.
- Scene Text Telescope, CVPR 2021:
  text-level layout + character position/content.
- TATT, CVPR 2022:
  global semantic text attention and structure consistency.
- DeepSolo, CVPR 2023:
  ordered explicit point queries jointly representing text semantics and location.

## Spatial/layout decoupling

- GlyphSpatialNet, CVPR 2026:
  shape-position decoupling and spatial-preserving rendering.
- FontAdapter, 2025:
  direct font-data training misses nuanced attributes; two-stage curriculum.

## OCR uncertainty

- NCAP, WACV 2025:
  incorrect categorical text prior can hurt; non-categorical features and soft/hard mixing
  improve robustness.
- TextSR, 2025:
  character-to-shape priors with OCR-error robustness.
- TIGER, CVPR 2026:
  restore glyph structure first, then enhance image.

## Vector glyph representation

- VecFontSDF, CVPR 2023:
  SDF → quadratic Bézier glyphs.
- Joint Implicit Neural Representation, ICCV 2023:
  SDF + probabilistic corner field.
- DualVector, CVPR 2023:
  positive and negative paths, directly relevant to counters.
- DeepVecFont-v2, CVPR 2023:
  Transformers/self-refinement for long complex vector sequences.
- VecFusion, CVPR 2024:
  raster stage followed by vector topology/control-point stage.

## Topology-aware auxiliary losses

- Betti matching;
- spatial-aware persistent matching;
- Topograph;
- clDice for thin/tubular structures.

## Font data

- Official Google Fonts repository:
  redistributable font files, per-family license metadata, mostly OFL with some Apache/UFL,
  and variable-font axis metadata.

---

# 21. Final answer

## Што не так

Не optimizer.
Не AMP.
Не threshold.
Не decoder shortlist.
Не недахоп 2M samples.

Галоўная памылка:

> **Мадэль павінна вывесці topology доўгага wordmark як пабочны вынік аднаго pixel mask.**

## Як выправіць

> **Зрабіць topology discrete, compositional і by-construction:
> character programs + layout + style deformation + explicit interactions.**

## Ці трэба перапісваць увесь праект

Не.

- PCDC core застаецца.
- Courts/certificates застаюцца.
- Extractor застаецца.
- Runtime architecture застаецца.
- Перапрацоўваецца Phase 4 TextLine candidate generator.
- ProposalNet чакае.

## Ці лёгка

- першы template-based gain — адносна лёгка;
- поўны v10 — medium-hard;
- гэта рэальны engineering path, не адкрытая даследчая бездань.

## Найважнейшы наступны крок

Не train.

Спачатку запусціць:

1. length × pixels-per-glyph;
2. clean identity;
3. oracle layout;
4. oracle template;
5. OCR conditioning matrix.

Пасля гэтых пяці experiments стане дакладна вядома, якая частка v10 патрэбна першай.

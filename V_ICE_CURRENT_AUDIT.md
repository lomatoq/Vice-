# V-ICE: актуальны аўдыт якасці і блокеры да VAI-парытэту

Дата: 2026-07-22  
Крыніца патрабаванняў: `V-ICE_proof_carrying_design_compiler_plan_ru_v2.md`  
Бягучы вердыкт: **не production-ready, VAI-парытэт не даказаны**.

Гэты файл адмыслова не выдае passing unit tests за якасць вектарызацыі.
Production promotion заблакаваны, пакуль не пройдуць рэальныя topology,
human-preference, runtime і blind VAI gates на адным frozen compiler hash.

## 1. Што ў папярэдняй ацэнцы было няправільна

### 1.1. GCR быў палічаны не паводле плана

План вызначае Glyph Catastrophe Rate як долю text lines, дзе згублены хоць
адзін persistent stem, counter або glyph component. Папярэдні Experiment 4
складваў колькасць пашкоджаных connected components і называў гэта GCR.

- стары паказаны вынік: прыкладна **45.36% reduction**;
- рэальны line-level вынік таго ж run: legacy 44 catastrophic lines,
  candidate 37, гэта толькі **15.91% reduction**;
- абавязковы gate плана: **не менш за 70%**.

Метрыка выпраўлена: primary GCR цяпер line-level; component severity
рэпартуецца асобна і не можа падмяніць gate.

### 1.2. Connected component памылкова лічыўся літарай

У старым font-free route кожны disconnected SVG/raster component станавіўся
`GlyphObservation`. Гэта няправільна для:

- JPEG-разарванай літары;
- `i/j` і дыякрытыкі;
- outline/shadow text;
- слоў, што засталіся адным connected component;
- SVG, дзе адна літара складаецца з некалькіх paths.

Цяпер OCR дае толькі ordered glyph cells/character contract; фізічны support
застаецца source-derived. Repeated-glyph EM групуе па semantic character, але
OCR-групаванне не мае права само зрабіць proposal admissible.

### 1.3. Наяўны SDF route не быў generative glyph prior

Функцыя `topology_preserving_sdf_glyph` толькі рухала адзін SDF threshold і
адкочвалася да зыходных pixels пры topology change. Гэта не рэалізоўвала
патрабаваныя планам:

- positive і negative loops/counters;
- character-conditioned clean glyph recovery;
- topology code;
- optional stroke skeleton;
- навучанне на мільёнах open-font glyph crops;
- font-family-disjoint validation.

Traceability audit цяпер больш не пазначае гэты пункт complete толькі таму,
што ў кодзе ёсць функцыя з `SDF` у назве.

## 2. Што цяпер рэалізавана

### 2.1. OCR і бяспечнае text recovery

- local-only TrOCR у optional Max lane, fail-open без checkpoint;
- source-bounded crop ensemble без filename/GT leakage;
- поўная OCR line recovery толькі пры topology, overlap і render proofs;
- ownership gate не дае сцерці суседнюю mark/icon;
- асобная adaptive per-glyph topology-plateau proposal;
- OCR proposal quota і vertical diversity для multi-row text;
- near-tie semantic top-pair rule толькі пры амаль роўным exact render score.

На дыягнастычным real subset гэта, сярод іншага, змяніла Pear JPEG component
severity 10→1, не пагоршыўшы CODERSRANK; аднак гэта не замяняе поўны
Experiment 4.

### 2.2. Generative font-free glyph model

Дададзены character-conditioned U-Net proposal model з асобнымі heads:

- clean support;
- signed distance field;
- optional skeleton;
- component topology code;
- counter/hole topology code.

Мадэль не выдае production SVG. Яе mask праходзіць exact expected-topology,
source-overlap/change bounds, пасля чаго застаецца асобнай proposal у агульным
local render court.

### 2.3. Навучальныя даныя і split

- ліцэнзійны manifest: **241 font files, 81 font families**;
- ліцэнзіі і bytes правяраюцца па SHA-256;
- train/calibration/test split робіцца па font family, а не па sample;
- uniform family sampling, каб вялікая сям'я не дамінавала;
- clean high-resolution target + scale/subpixel/blur/noise/color/JPEG variants;
- deterministic `(seed, epoch, index)` stream;
- 12-bit фізічная feature lattice ліквідуе float32 SIMD nondeterminism;
- 4×500,000 = **2,000,000 unique training variants** у бягучым candidate run.

### 2.4. Fail-closed checkpoint lifecycle

Failed або проста створаны candidate не актывуецца ў runtime. Promotion
патрабуе адначасова:

1. held-out font-family topology accuracy ≥97%;
2. held-out support IoU ≥0.90;
3. hash-matched Experiment 4 machine gate;
4. digest-bound Experiment 4 human preference gate;
5. поўны regression report на тым жа compiler hash;
6. асобны production promotion manifest.

Без manifest production path ігнаруецца. Для эксперыменту candidate можна
ўключыць толькі відавочным local environment override.

## 3. Праверана перад поўным glyph-prior train

- Python bytecode/static import check: passed;
- поўны regression suite: **280/280 passed**;
- glyph data/model preflight: passed;
- license manifest: passed;
- family split disjointness: passed;
- deterministic repeated sample: passed;
- clean target адрозніваецца ад degradation input: passed;
- finite forward/backward/optimizer step: passed;
- checkpoint save/load і resume binding: tested;
- failed checkpoint cannot become production model: tested;
- Experiment 1 на актуальным hash: passed:
  - support Recall@32: 99.73%;
  - class floor: 99.52%;
  - macro-family recall: 99.67%;
  - p95: 157.8 ms.

## 4. Што яшчэ не працуе або не даказана

### B01. Experiment 4 не зялёны

Апошні поўны result быў да новай glyph model і ўжо stale. Карэктны line-level
GCR быў толькі каля 15.91%, а патрэбна ≥70%. Пасля навучання патрэбны новы
machine run на 100 real lines і новая digest-bound human review.

### B02. Exact-font lane не паказаў карысці

У апошнім поўным run `exact_font_admitted = 0`, а optional exact p95 быў каля
2.1 s/line. 241 licensed fonts ліквідуюць вузкі catalog, але не даказваюць,
што exact retrieval купляе якасць. Калі новы run зноў дае zero admission,
expensive exploration мусіць быць выключана з default Max cascade або жорстка
абмежавана top-pair case.

### B03. Warm TextLine latency нестабільная

Папярэднія p95 вагаліся прыкладна ад 185 да 207 ms пры gate <200 ms. Пасля
source freeze патрэбны некалькі паўторных warm-only runs; адзін выпадковы run
не з'яўляецца доказам.

### B04. Рэшткавыя цяжкія text families

Да generative model асноўная component severity заставалася ў:

- spadegaming;
- stormcraft;
- smartsoft;
- cardano;
- pearfiction;
- выпадках без надзейнай source text ownership.

Existing threshold/oracle proposals маглі зняць толькі малую частку гэтай
рэшты, таму court tuning адзін не мог дасягнуць 70% gate.

### B05. Human preference пасля новага output адсутнічае

Старыя answers не пераносяцца: review прывязана да digest абедзвюх SVG
alternatives. Пасля новага output патрэбна новая сляпая ацэнка ў native/live
SVG resolution, без штучнага памяншэння vector preview.

### B06. Foundational reports павінны быць на адным hash

Experiment 1 ужо перазапушчаны. Experiments 1B, 2, 3 і 5 павінны таксама
прайсці пасля апошняга compiler edit. Любая наступная змена Python compiler
source робіць гэтыя reports stale.

### B07. ProposalNet v14 training яшчэ заблакаваны

Асобная query ProposalNet не павінна трэніравацца, пакуль не зялёныя:

- full regression;
- Experiments 1/1B/2/3/4/5;
- glyph-prior held-out training;
- complete plan traceability;
- real calibration capacity;
- renderer/degradation-disjoint untouched holdout;
- runtime conformal equivalence;
- tiny multi-instance overfit;
- anti-forgetting;
- two-run CUDA reproducibility;
- licensed font/runtime identity.

### B08. Data diversity для ProposalNet недастатковая

Typed supplements усё яшчэ не даказалі патрабаваныя незалежныя render paths
і held-out degradation family. Патрэбен corpus, дзе renderer/degradation,
source asset, font family, icon library і semantic class не працякаюць паміж
split’амі.

### B09. Real Locus Corpus малы для канчатковай calibration

Ёсць 300 seed loci, але план патрабуе прыкладна 2k–5k manually reviewed real
loci і не менш за патрэбную колькасць кожнага рэдкага class у calibration/test.
Conformal threshold 1.0 або адсутны class лічыцца vacuous, а не success.

### B10. VAI-парытэт не правераны

Нават passing glyph prior і ProposalNet — толькі proposal sources. Канчатковы
доказ патрабуе:

- VAI50 + challenge115 без пропускаў;
- 0 timeout/OOM;
- 0 catastrophic counter/canvas/layer failures;
- live-SVG blind comparison;
- ніводнага ключавога slice ніжэй за 45%;
- агульны parity не менш за 50%, мэта >55%;
- Balanced warm p50/p95 і hard timeout gates.

## 5. Чаму VAI выглядае больш «ідэалізавана»

Па знешнім output нельга сумленна сцвярджаць дакладную закрытую архітэктуру
Vectorizer.AI. Назіраемая розніца, аднак адпавядае semantic reconstruction:
сістэма распазнае, што pixels з'яўляюцца літарай, circle, repeated group або
stroke, і аднаўляе latent clean geometry замест tracing кожнай JPEG/AA
няроўнасці.

V-ICE раней занадта часта пачынаў з ужо пашкоджанага baseline і спрабаваў
лакальна яго «падчысціць». PCDC кірунак правільны толькі тады, калі generative
macros канкуруюць з fallback ад пачатку, а topology/render certificates не
дазваляюць idealization выдумаць geometry. Менавіта гэта цяпер правяраецца;
простае зніжэнне парогаў або яшчэ адна ProposalNet version праблему не вырашыць.

## 6. Бягучы парадак работ

1. Давучыць glyph-prior candidate і праверыць held-out family gates.
2. Калі model gate пройдзены — запусціць Experiment 4 з candidate override.
3. Разабраць кожную catastrophic line, а не толькі average metric.
4. Дасягнуць machine GCR ≥70%, zero reviewed-line regression і warm p95 <200ms.
5. Правесці новую blind human review.
6. Перазапусціць усе foundational/full gates на адным frozen hash.
7. Толькі пасля all-green readiness дазволіць ProposalNet v14 training.
8. Пасля гэтага — поўная OFF/ON і blind VAI parity campaign перад promotion.


# ProposalNet: честный аудит и статус переобучения

Дата: 2026-07-21  
Production checkpoint: `models/proposal_net_v1.pt`  
Отклонённый large candidate: `models/proposal_net_large_candidate.pt`  
Текущий v2 candidate: `models/proposal_net_large_candidate_v2.pt`

## Вердикт

Ни `proposal_net_v1.pt`, ни первый large candidate нельзя считать
валидированным production proposal model. v1 был пилотом на 300 loci с
vacuous conformal sets. Первый large run был обучен на 60 190 pairs, но его
evaluation contract завышал/искажал Recall@K; после честного пересчёта он
провалил glyph-group gate. Оба checkpoint не promoted.

ProposalNet v2 сейчас обучается отдельно и не заменит production checkpoint
автоматически. Promotion возможен только после fixed report gate и downstream
production ablation.

## Почему v1 gate был невалиден

1. Class-conditional conformal thresholds были равны `1.0`, то есть наборы
   получались заведомо vacuous.
2. `hybrid_support_recall_at_32` включал classical REIR proposals и не измерял
   causal neural recall.
3. Calibration/test имели всего десятки примеров и один target на crop.
4. Continuous parameter target был нулевым с полностью нулевой mask.
5. Hard-negative ranker обучался и проверялся на одной искусственной матрице.
6. До production wiring neural output не влиял на candidate generation.

## Первый large run: измеренный провал

Report: `benchmarks/pcdc_proposal_large/report.json`  
Training: 60 190 pairs, CUDA, 8 epochs, около 6883 s.

Neural-only старый Recall@32:

| Family | Recall |
|---|---:|
| appearance | 0.9625 |
| glyph_group | 0.0838 |
| layer | 0.9845 |
| risk | 0.9264 |
| stroke | 0.9434 |
| text_line | 0.9296 |
| whole_shape | 0.9772 |

Этот checkpoint **не promoted**. Низкий glyph-group recall был реальным
красным сигналом, но evaluator дополнительно имел две ошибки:

- K применялся фактически отдельно по families, а не как global query budget;
- один query мог повторно засчитываться нескольким glyph instances.

Поэтому run нельзя ни принять, ни корректно сравнивать с новым контрактом.

## Что исправлено в ProposalNet v2

### Training objective

- DETR-style no-object class downweighted до `0.10`, чтобы 30 пустых slots не
  подавляли positives.
- Confidence head получает matched=1 и unmatched=0 supervision.
- Hard-negative head имеет явный CE loss для JPEG halo, jagged overfit/noise,
  remove-real-accent/blur.
- Parameter head учится на 16 измеряемых geometry descriptors, а не на нулевой
  target/mask.
- Glyph-group target обозначает целую group/line, а не каждый connected glyph.

### Dataset labels

- Text label только для synthetic text.
- Layer label только для procedural overlap или явных opacity/mask/clip cues.
- Stroke label только для stroke-only scenes.
- Appearance label только для gradient-painted shapes.
- Repeat label только для повторных `<use>` references.
- 37.5% synthetic geometry получают deterministic source-disjoint small-shape
  recomposition; image и support трансформируются одинаково.
- Vanished masks fail-closed и не создают пустой bbox target.
- SVG semantic labels кэшируются per source/target.

### Evaluation contract v2

- global top-K по всем query families;
- one-to-one Hungarian instance matching;
- честные Recall@5 gates:
  - overall >= 97%;
  - text_line >= 99%;
  - glyph_group >= 99%;
  - small_shape >= 98%;
  - layer >= 95%;
- slice должен иметь >=100 instances, иначе gate fails closed;
- отсутствие required family явно проваливает gate;
- conformal threshold обязан быть non-vacuous.

## Текущий run

Directory: `benchmarks/pcdc_proposal_large_v2`  
Progress: `benchmarks/pcdc_proposal_large_v2/progress.json`  
Report: `benchmarks/pcdc_proposal_large_v2/report.json`  
Checkpoint: `models/proposal_net_large_candidate_v2.pt`

Configuration:

- 60 190 pairs;
- image size 128;
- hidden dim 128;
- 32 queries;
- 3 decoder layers;
- parameter dim 16;
- batch 64;
- 8 epochs;
- CUDA;
- source-disjoint train/calibration/test split.

## Promotion contract

Даже если report gate пройден, checkpoint не становится production model без
ablation на том же runtime graph:

1. ProposalNet OFF vs ON на frozen sources.
2. Измерить typed proposal recall до fit и accepted certified columns.
3. Измерить whole-scene topology, GCR, blind preference и runtime.
4. Не допустить ухудшения key slices или safe fallback.
5. Проверить deterministic repeated inference и conformal coverage.

Только после этого `DEFAULT_PROPOSAL_CHECKPOINT` может быть переключён на v2.

## Обновление 2026-07-22: честный статус v9–v12

Старое описание v2 выше сохранено как история, но больше не является текущим
статусом модели.

- После исправления source-owner labels и renderability audit принято 59 647
  из 60 190 raster/vector pairs; 543 пары fail-closed.  Split строго
  source-family-disjoint: 43 416 train / 6 806 calibration / 9 425 test.
  Raw sources: 26 000 Iconify, 16 000 synthetic text, 16 000 synthetic
  geometry и 2 190 local/logo renders.  Supervised family counts remain very
  imbalanced: text/glyph по 18 046, whole-shape 42 544, layer 4 091,
  appearance 502, repeat 194 и stroke только 50.  Поэтому v12 проверяет
  spatial text hypothesis; его нельзя выдавать за хорошо обученную universal
  Phase-5 model даже если aggregate text улучшится.
- Лучший низкоразрешённый v9 был отклонён: overall Recall@5 0.875374,
  text 0.709255, glyph 0.705471, small shape 0.991909, layer 0.936620.
- Исправление математической ошибки global-top5 loss отдельно проверено в
  v10 и тоже отклонено: text/glyph и overall стали хуже.  Значит ranking loss
  был реальным багом, но не галоўным bottleneck.
- v11 поднял support lattice с 32x32 до 64x64 и дал measured test:
  overall 0.924916, text 0.827998, glyph 0.826834, small 0.988673,
  layer 0.936620.  Модель не promoted; conformal gate не пройден.
- Oracle capacity не мешает gate: global Recall@5 ceiling на test равен
  0.995191, а по каждой required family — 1.0.  То есть текущий провал — не
  артефакт невозможной метрики.
- Разложение 3 436 text/glyph targets: geometry-any@32 0.858265,
  typed@32 0.834983, typed@5 0.827998.  Главная потеря — маска/instance
  geometry.  Особенно: `<1%` area 0.0, `1–3%` 0.302013, multi-row 0.158470,
  real local-owner 0.360140.  Synthetic text уже 0.870476.
- v12 — чистая архитектурная ablation: явная абсолютная 2-D позиция в
  Transformer memory и mask path, все старые веса взяты из лучшего v11.
  Тренировка идёт в `benchmarks/pcdc_proposal_large_v12_spatial`; production
  checkpoint не меняется до прохождения всех frozen gates.
- Data Factory пока существенно ниже плана: 60 190 variants против целевых
  0.5–2M, 45 hardcoded Windows font families вместо широкого open-font/glyph
  factory и 300 reviewed real loci (205 derived GT) вместо 2k–5k.  Эти real
  loci не смешаны в large v11/v12 pretraining.
- Отдельный real-locus fine-tuner был несовместим с 64x64 mask head и не
  супервизировал/gate'ил glyph_group.  Это исправлено; type-correct conformal и
  hash binding данных таксама дададзены.  Пры цяперашніх 47 calibration loci
  non-vacuous 99% conformal немагчымы, таму стары `passed` отчёт з
  threshold=1.0 прызнаны непрыдатным для promotion.
- Read-only real test выявил катастрофический domain gap v11: overall 0.477273,
  text 0.333333, glyph-group 0.133333, layer 0.714286, stroke 0.0, gradient
  0.0, small-shape 1.0.  Это immutable evaluation без fine-tune на 44
  source-disjoint reviewed loci.  Следовательно, synthetic overall 0.924916
  нельзя больше использовать как proxy готовности модели.

## 2026-07-22: v12 interim transfer and Data Factory v2

- The best v12 spatial checkpoint after epoch 3 improves the frozen synthetic
  calibration selection key from v11's `(0.845306, 0.929580, 0.766021)` to
  `(0.857017, 0.931178, 0.775974)`. Epoch 4 was worse and did not replace it.
- A read-only evaluation of that exact epoch-3 checkpoint on the same immutable
  real test split improves overall Recall@5 from 0.477273 to 0.545455, text
  from 0.333333 to 0.466667 and layer from 0.714286 to 0.857143. Glyph-group
  remains 0.133333 and both stroke and gradient remain 0.0. Spatial identity
  is a real improvement, but v12 still fails promotion decisively.
- Real evaluation now fails closed on every typed class, not only the five old
  aggregate gates. Stroke, gradient and codec/detail are required, as is a
  minimum held-out sample floor. The 44-locus test split is explicitly too
  small for promotion even if its point estimates were high.
- A licensed open-font bank is bound by font, license and content hashes: 36
  families and 116 font files. The first controlled text learning-curve set
  contains 1,800 clean sources and 7,200 degraded pairs: 1,060 two-row, 383
  three-row and 357 glyph-crop sources. Each row is an explicit named SVG
  owner; no connected-component guess is used as its label.
- A second typed factory addresses the classes that scored zero on real data:
  2,000 clean sources and 8,000 degraded pairs, balanced across stroke network,
  appearance/gradient, layer relation and symmetry/repeat. Its family labels
  come from the generator contract, not SVG tag-count heuristics.
- The immutable mixed v13 preflight contains 75,390 pairs: the 60,190 legacy
  replay rows plus both supplements. Split groups do not overlap. Declared
  calibration/test counts exceed 100 for every new family; entire font
  families and every augmentation of one source remain in one partition.
- Factory code hashes, font-manifest hash, source/pair row hashes, payload
  origins and their attestations are all bound before mixed training. v13 is
  not allowed to start until v12 finishes, because changing the active trainer
  during v12 would invalidate its recorded label contract.

### Final v12 result

- v12 completed all six epochs. Epoch 6 is the immutable best checkpoint with
  calibration key `(0.857854, 0.931114, 0.771752)` and SHA256
  `f4588b86c5e1593efbebea797bc4763b7fd99541225139fb9801cd28d18ed4e6`.
  Its exact v1 label-contract sources are archived beside the report.
- Synthetic test improves over v11 to overall 0.928792, text 0.839057 and
  glyph 0.839639. Small-shape is 0.991909 and layer 0.927817. The required
  gate and conformal calibration still fail, so v12 is rejected.
- Final source-disjoint real test improves further to overall 0.568182 and text
  0.533333, while glyph remains 0.133333, layer 0.857143, stroke 0.0 and
  gradient 0.0. This checkpoint was never promoted.
- The new real failure decomposition changes the diagnosis materially:
  geometry-any@32 is 1.0 for every test class. Text typed@32 is 1.0 but typed@5
  is 0.533333; glyph is 0.866667 vs 0.133333; gradient is 0.25 vs 0.0; stroke
  typed@32 is 0.0. The dominant remaining problem is family typing/ranking,
  not missing support geometry. The v13 typed replay is therefore a controlled
  response to measured failure, not an unmotivated scale increase.

### v13 frozen preflight correction

- The first v13 attempt was stopped before completing epoch 1. Its source-level
  replay mass was nominally 30% text / 30% structure / 40% legacy, but the
  balanced structural supplement inherited scarcity multipliers from the old
  harvested corpus. This made its four-family conditional sampler mass
  appearance 6.03%, layer 2.19%, stroke 73.86% and repeat 17.93%.
- Balanced structural rows now use an equal family prior while legacy rows
  retain their justified scarcity weights. The frozen preflight measures
  appearance 25.13%, layer 24.32%, stroke 25.65% and repeat 24.90%; a hard
  20--30% envelope rejects future hidden skew before model construction.
- Explicit degradation replay supplies a risk target on about 87% of each new
  supplement. The stale risk class/positive boosts (1.65/1.85), inherited from
  the sparse corpus, were removed. The risk query, hard-negative classifier and
  fixed 95% held-out gate remain active; the immutable v12 baseline already
  passes that slice at 95.70%.
- The final epoch-0 preflight admits 74,703 of 75,390 pairs, with 55,459 train,
  8,132 calibration and 11,112 test rows. Every required test slice has at
  least 164 instances, split groups are disjoint, and the aggregate top-5
  oracle capacity is above the required gate.
- Current source, preflight checkpoint and report all bind label-contract SHA256
  `6f1672dc700d51ec82820e3f6ddcf41c5710ec8f1d3144e10b921dfec1026033`.
  The eight exact source files are archived under
  `benchmarks/pcdc_proposal_large_v13_mixed/label_contract_sources_preflight`.
  Full project discovery passes 231/231 tests before the clean v13 restart.
- Candidate authorization, Phase-12 aggregation and final promotion now accept
  this v2 contract only behind the same hash-bound sidecars. Real conformal
  evidence is read from the candidate's evaluation manifest, not a default v9
  report; every declared required family is checked; and a valid complete
  BUILD_FREEZE is a mandatory campaign gate.
- This preflight validates the controlled 75k learning-curve run. It does not
  claim the plan's eventual 0.5--2M variant, million-glyph or 2k--5k reviewed
  real-locus scale, and it does not establish Vectorizer.AI parity.

### 2026-07-22: real-label contract correction discovered during v13

- The 300-locus corpus field `semantic_class` was created as a balanced Phase-0
  sampling bucket, but Experiment 9 and the read-only evaluator silently used
  it as a ProposalNet query label. This was invalid. The `diagrams` bucket, for
  example, contains filled arrows, badges, overlap scenes and monogram frames;
  none of the 18 owned-SVG rows is an actual stroke network. The old reported
  stroke Recall@5 of 0.0 therefore mixed a model failure with wrong ground
  truth. The codec bucket similarly had clean full-design support rather than
  a codec-residual support locus.
- The review UI could not record a typed ProposalNet family at all: its
  `macro_family` choices were the same six sampling buckets. A separate
  `proposal_family` field now uses the actual query contract. Training and
  evaluation refuse to infer it from `semantic_class` or `macro_family`.
- An objective owned-SVG-only migration proved 196/300 labels: 83 text-line,
  69 whole-shape (including correctly retyped filled diagram assets), 30
  appearance and 14 layer-relation loci. The other 104 remain explicitly
  untyped; no threshold was lowered and no heuristic label was promoted to
  truth. The UI opens on those missing labels and exposes a typed-family
  filter. Codec/risk rows additionally need a separate residual support mask,
  not merely a family dropdown.
- Re-evaluating v13 epoch 1 on the corrected typed subset changes diagnostic
  test overall Recall@5 from the misleading 0.6364 to 0.7931. Text is 0.8571,
  glyph-group 0.5714, whole-shape 1.0, layer 1.0 on only two test loci, and
  appearance 0.0. Stroke/risk are reported as missing evidence rather than
  false zero-recall classes. The subset is far below promotion sample floors.
- Epoch 2 slightly improves synthetic calibration but regresses the corrected
  real calibration/test curve. All epochs are archived so the final candidate
  is not selected from synthetic aggregate alone. These per-epoch test reads
  are diagnostic learning-curve evidence and are not a frozen promotion test.

## 2026-07-22: final v13 result and mandatory pre-v14 instance preflight

- Phase 5 is implemented across all five plan lanes: whole-shape typed macros,
  stroke networks, appearance/gradients, codec/detail counterfactuals and
  repeated-parameter groups. Each lane reaches the production court/export
  path. The focused Phase-5 suite is 14/14 and Complexity Stress is 7/7 cases
  plus 4/4 gates. This is implementation completeness, not a VAI parity claim.
- v13 completed four epochs and was rejected. Its frozen synthetic test is
  overall 0.905773, text-line 0.712048, glyph-group 0.904218, layer 0.936170,
  stroke 0.936170, repeat 0.915094, appearance 1.0, risk 0.970149 and small
  shape 0.991909. Required Recall and non-vacuous conformal gates fail.
- A read-only decomposition of all 11,112 test rows proves the main text loss
  is support geometry: text geometry-any@32 is 0.7374, typed@32 0.7214 and
  typed@5 0.7120. Thus geometry/type/rank loss fractions are approximately
  26.26%/1.60%/0.93%. Single-line geometry recall is 0.9258, two-line 0.5394,
  three-line 0.1417; synthetic-open-text glyph union is 0.9802 while its
  individual text lines are 0.4699. More ranking weight cannot fix this.
- The verified repair direction is instance-local support: same-family
  exclusivity, foreground balance up to the true sparse-mask ratio, and a
  TextLine-only vertical ROI prior. Applying the old checkpoint's own bbox as
  a diagnostic vertical gate increases synthetic-open-text text Recall@5 from
  0.4522 to 0.7326 at the best inspected hard padding while leaving non-text
  query families ungated. A universal all-family ROI gate was rejected because
  it regressed shapes/strokes/repeats.
- Train-only tiny-overfit probes write no checkpoint. The original objective
  reaches only 0.625 on 80 text instances after 120 steps and 0.7875 after 480.
  Instance exclusivity, the TextLine-only vertical ROI, sparse foreground
  balance, soft IoU and a bounded sparse false-positive leakage term reach
  1.000 after 960 steps on all 80 line instances. The former final three-row
  Cinzel miss is closed; final failure count is zero. Full-batch, 128-pixel
  mask-lateral and soft-edge ablations were worse and are not retained.
- Large training now refuses to start without a train-only, checkpoint-,
  filter-cache-, pair-root-, config- and current-label-contract-bound preflight
  with at least 16 two-row plus 16 three-row scenes and best text Recall@5
  >=0.99. The current bound report passes at 1.000. This closes the instance-
  learning preflight only; v14 remains blocked by the separate full readiness
  audit (Phase-4, data/holdout, hard-negative, calibration and anti-forgetting
  requirements).
- The old synthetic test was inspected during ROI root-cause sweeps and is now
  diagnostic only for this design choice. A future candidate needs parameters
  frozen on calibration and a new untouched font-family/real holdout. The
  licensed bank currently contains 36 families and 116 font files; adding new
  licensed families is useful primarily to create that untouched holdout.
- After the diagnostic, objective, runtime and fail-closed trainer changes,
  Phase 9 passes 37/37 focused tests and full project discovery passes 243/243.

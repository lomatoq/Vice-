# V-ICE: полный технический handoff по известным проблемам

Дата среза: 2026-07-20  
Workspace: `C:\Users\nirrt\Toolset\v-ice part`  
Цель проекта: clean-room векторизатор, который по perceptual quality, идеализации,
топологии, тексту, редактируемости и скорости не уступает Vectorizer.AI (VAI).

## 1. Короткий честный статус

**Текущий verdict: FAIL / DO_NOT_PROMOTE.**

- Production default в интерфейсе должен оставаться `V-ICE Best`.
- Новый `Scene Engine` существует как experimental route, но пока заметно хуже VAI и
  имеет topology/text catastrophes.
- Полный Build 1–14 из clean-room плана реализован на уровне архитектурных модулей и
  контрактов. Это не означает, что модули достигли нужного качества.
- После последних исправлений три тяжёлых Scene-кейса сильно восстановились
  относительно сломанной версии, но до VAI parity всё ещё далеко.
- Обученный evidence checkpoint хорошо прошёл synthetic held-out, но **ухудшил все три
  real-image A/B case и был отозван из production**.
- Новая полная frozen VAI50/115 campaign после последних исправлений ещё не запускалась.
  Старый frozen verdict поэтому остаётся единственным общим verdict.

## 2. Что именно требуется от эксперта

Нужен разбор не очередных локальных thresholds, а причин, почему связка
`learned evidence -> topology -> scene graph -> global court` не переносится с synthetic
на реальные логотипы и почему text/geometry recovery значительно слабее VAI.

Просьба дать ответы на вопросы из раздела 13 и предложить staged plan с измеримыми exit
criteria. Особенно важны:

1. Правильные dense targets/losses/calibration для boundary, topology, glyph и uncertainty.
2. Как строить topology/text hypotheses **до** необратимой palette/component segmentation.
3. Как учить/оценивать proposal recall отдельно от selector quality.
4. Как получить VAI-подобную идеализацию текста и полной геометрии без OCR/font lookup как
   единственной опоры.
5. Как сделать это быстро: сейчас обычный Scene job занимает десятки секунд, старые
   frozen tails доходили до минут.

## 3. Общие frozen-результаты против VAI

Это результаты старого frozen Scene build до remediation 2026-07-20. Они всё ещё важны,
потому что новая полная campaign не завершена.

### VAI50

- 31 complete, 19 resource failures, missing output: 0.
- Scene topology catastrophes: **31/31**.
- VAI topology catastrophes: **0/31**.
- Mean SSIM: V-ICE Scene `0.6629`, VAI `0.9615`.
- Mean ink IoU: V-ICE Scene `0.7033`, VAI `0.9499`.
- Mean MAE: V-ICE Scene `26.47`, VAI `5.16`.
- Runtime p50 `204 s`, p95 `2019 s`.
- Итог: **FAIL**.

### Challenge pack 115

- 27 complete, 88 timeout/resource failures.
- SSIM wins over VAI: 0.
- IoU wins over VAI: 0.
- MAE wins over VAI: 1.
- Итог: **FAIL**.

### Ablations

- 8 complete, 43 timeout.
- Основные resource bottlenecks: topology/evidence/geometry search.
- Из-за количества timeout causal выводы слабые: полная матрица не набрала достаточного
  покрытия.

## 4. Что пользователь визуально видит плохим

Наблюдения подтверждаются метриками и SVG inspection:

1. Лишние shapes возникают «из ниоткуда» и перекрывают правильную сцену.
2. Буквы распадаются на независимые фрагменты, теряют counters, получают ложные holes или
   сливаются.
3. Текст остаётся копией raster artifacts вместо восстановления общей baseline,
   одинаковых stroke classes, повторяющихся glyph prototypes и аккуратных counters.
4. Круги/дуги и smooth silhouettes часто превращаются в угловатые polylines; иногда
   наоборот короткий почти прямой fragment ошибочно объявляется огромным кругом.
5. Painter order и knockout geometry ошибочны: белая область может быть принята за фон,
   residual-eraser или лишнюю верхнюю фигуру.
6. Глобально «приличные» SSIM/IoU могут скрывать локальную катастрофу в логотипе/тексте.
7. Scene route работает 20–40 секунд даже на маленьких примерах; старая frozen версия
   доходила до минут и десятков минут.
8. VAI визуально восстанавливает более простую и регулярную geometry, а V-ICE чаще либо
   overfits raster noise, либо удаляет semantic detail.

Пользовательские примеры:

- `C:\Users\nirrt\OneDrive\Изображения\Снимки экрана\Screenshot 2026-07-19 111526.png`
- `C:\Users\nirrt\OneDrive\Изображения\Снимки экрана\Screenshot 2026-07-19 111908.png`

## 5. Текущий diagnostic subset после исправлений

Это **не новая общая campaign**, а три локализованных regression cases.

| Case | Сломанный Scene | Current deterministic Scene | Что всё ещё плохо |
|---|---:|---:|---|
| Dunkin `94_icon_group_4_62` | SSIM `0.601`, IoU `0.712`, `24.7 s` | SSIM `0.7507`, IoU `0.8152`, MAE `14.60`, `21.0–22.5 s` | 5 catastrophic loci; components/counters теряются; VAI SSIM около `0.96` |
| Mastercard `52_icon_group_4_24` | SSIM `0.370`, IoU `0.558`, `26.0 s` | SSIM `0.7681`, IoU `0.8925`, MAE `11.22`, `18.1–19.6 s` | текст фрагментирован; 3 catastrophic loci; VAI всё ещё заметно чище |
| City Breach `98_icon_group_4_66` | SSIM `0.067`, IoU `0.659`, `61.3 s` | SSIM `0.4804`, IoU `0.8381`, MAE `46.67`, `23.9 s` | 10 catastrophic loci; ложные holes/outlined glyphs; огромный residual/color error |

## 6. Главный текущий отрицательный эксперимент: learned evidence

### Что было сделано

- Clean-room training corpus: `datasets/scene_evidence_cleanroom_v1`.
- 512 scenes, split по manifest: train/validation/test.
- Renderer families: analytic, Pillow polygon, OpenCV polygon.
- Degradations: blur, resize, gamma, JPEG/recompression, sharpen, subpixel
  translation/rotation, palette, scan noise, alpha round-trip.
- Font samples: DejaVu Sans из matplotlib (open-license), плюс font-free custom glyphs.
- Multi-head U-Net-like model, 32 base channels, 12 epochs, batch 8, RTX 4070.
- Training loss: `11.143 -> 4.225`.
- Candidate: `models/scene_evidence.candidate.pt`.
- Candidate SHA-256:
  `BF6661C7D86795C8BA07CBC2AFDA56998EDAE531A504DBFC36EA33B872A2EC35`.
- Независимый promotion corpus: `datasets/scene_evidence_promotion_v1`, 256 scenes,
  другой seed `20260721`.

### Pure neural head result

На development validation нейросеть улучшила semantic/appearance heads, но сильно проиграла
classical differential geometry:

| Head | Candidate MAE | Deterministic MAE | Candidate / baseline |
|---|---:|---:|---:|
| symmetry | `0.1439` | `0.8382` | `0.17×` |
| text line | `0.0998` | `0.3044` | `0.33×` |
| shape class | `0.1536` | `0.3529` | `0.44×` |
| glyph occupancy | `0.0660` | `0.1263` | `0.52×` |
| stroke half-width | `0.0020` | `0.0038` | `0.53×` |
| uncertainty | `0.0673` | `0.0763` | `0.88×` |
| subpixel offset | `0.0325` | `0.0186` | `1.75×` worse |
| boundary probability | `0.1052` | `0.0333` | `3.15×` worse |
| boundary normal | `0.3008` | `0.0527` | `5.71×` worse |
| stroke centerline | `0.1093` | `0.0118` | `9.30×` worse |
| corner type | `0.1075` | `0.0076` | `14.16×` worse |

### Hybrid routing

Для защиты geometry classical heads были оставлены для boundary/normal/offset/corners/
junction/centerline/region. Neural использовался только для coverage, shape class, text,
glyph occupancy, stroke width, symmetry, uncertainty.

Synthetic result:

- Development validation: hybrid `0.0594` vs deterministic `0.1335`.
- Development test: hybrid `0.0568` vs deterministic `0.1321`.
- Manifest-disjoint promotion validation: `0.0577` vs `0.1350`.
- Manifest-disjoint promotion test: `0.0633` vs `0.1341`.
- Все synthetic gates прошли.

### Real-image A/B: провал

| Case | Hybrid SSIM / time | Deterministic SSIM / time | Catastrophic loci, hybrid vs det |
|---|---:|---:|---:|
| Dunkin | `0.7470`, `27.77 s` | `0.7507`, `21.04 s` | `8` vs `5` |
| Mastercard | `0.7609`, `21.89 s` | `0.7681`, `18.07 s` | `4` vs `3` |
| City Breach | `0.4725`, `37.07 s` | `0.4804`, `23.88 s` | `16` vs `10` |

На City также регрессировали IoU и MAE. Ни одной aggregate победы по SSIM/IoU/MAE/
catastrophe count нет. Hybrid checkpoint перемещён в
`models/scene_evidence.real_ab_rejected.pt`; production-файла
`models/scene_evidence.promoted.pt` сейчас **нет**.

Machine-readable reports:

- `benchmarks/scene_evidence_hybrid_development_validation.json`
- `benchmarks/scene_evidence_independent_promotion.json`
- `benchmarks/scene_evidence_real_ab.json`
- `benchmarks/scene_evidence_real_ab_manifest.json`

### Высоковероятные причины synthetic -> real domain gap

1. **Synthetic scene distribution слишком простая.** Большинство random scenes — изолированные
   circles/ellipses/rects/stars; сложный coverage scene повторяется структурно. Реальные logos
   имеют брендовые glyphs, dense touching components, knockouts, outline/fill ambiguity,
   antialiased compositing и неизвестный preprocessing.
2. **Неполные/слабые labels.** `junction_prob` в текущем factory почти всегда нулевой;
   `subpixel_offset` target равен нулю; `uncertainty = 1 - boundary` не моделирует реальную
   ambiguity; corner types упрощены; shape labels per-pixel не кодируют instance/topology.
3. **Loss не соответствует downstream cost.** Pixel BCE/Dice может уменьшать average MAE,
   но небольшой systematic bias меняет component split/merge и создаёт topology catastrophe.
4. **Нет calibration по real source domain.** Head probabilities используются как priors/
   thresholds, хотя neural calibration измерена только на synthetic.
5. **Text labels не учат строковую структуру.** Per-pixel text/glyph masks не дают baseline,
   character grouping, counter identity, repeated prototype, tracking и stroke-family targets.
6. **Нейросеть запускается в fresh worker.** Import/load/CUDA startup добавляет секунды;
   production worker isolation конфликтует с low latency.

## 7. Оставшиеся архитектурные проблемы

### 7.1. Topology строится слишком рано из appearance components

Текущий pipeline сначала делает appearance clustering, затем component topology, затем
text integration. Если буква/knockout уже слита или разделена palette/component mask, text stage
получает повреждённую сцену. Нужна конкуренция нескольких instance/topology hypotheses, где
text/glyph grouping участвует до irreversible segmentation commit.

### 7.2. Нет измеренного proposal-recall upper bound на реальном наборе

Мы пока не знаем отдельно:

- правильной сцены/shape/text hypothesis вообще нет среди candidates;
- правильная hypothesis есть, но court выбирает не её;
- forward renderer неверно оценивает candidate;
- MDL/semantic prior перевешивает physical evidence.

Synthetic oracle diagnostics есть, но реального oracle/proxy upper-bound breakdown нет.

### 7.3. Text recovery остаётся слабым

- Exact-font Path A зависит от OCR/font catalog и часто неприменим к logos/custom lettering.
- Font-free Path B восстанавливает каждый glyph локально и недостаточно использует line-level
  shared parameters.
- Repeated glyph prototypes, baseline, x-height/cap-height, stroke classes и counters существуют
  в контрактах, но не являются достаточно сильной joint optimization problem.
- Нет learned glyph-shape prior/SDF decoder, обученного на широком legally-owned corpus.
- Нет отдельного catastrophic text objective, который гарантированно запрещает потерю counters
  и component identity при небольшом выигрыше raster loss.

### 7.4. Forward-model court недостаточно идентифицируем

Несколько разных scene/topology candidates могут давать близкий downsampled render. Current
NLL/SSIM-like score не всегда отличает «правильную идеальную geometry» от overfit geometry.
Нужны calibrated likelihood, perceptual/structural terms и explicit posterior uncertainty.

### 7.5. Shape priors слишком слабые или не там применяются

Full-shape tournament реализован, но neural shape prior влияет слабо и per-region. Он не делает
joint repeated-radius/equal-gap/model-family inference. Поэтому VAI-подобная регуляризация
появляется нестабильно.

### 7.6. Occlusion/painter model недостаточно силён

Draw order, parents и negative loops представлены, но гипотезы скрытых продолжений и shared
boundaries ограничены. White background/knockout ambiguity частично исправлена только
детерминированным правилом isolated background islands.

### 7.7. Residual repair лечит симптомы

Теперь residual не может добавить full-canvas eraser, но сам подход остаётся локальным
add/prune после уже выбранной сцены. Он не должен компенсировать неверную topology/background
hypothesis.

### 7.8. Скорость не production-grade

- Current deterministic Scene: примерно 18–24 s на Mastercard/Dunkin, около 24 s на City.
- Hybrid: 22–37 s на тех же небольших изображениях.
- Старый frozen tail: p50 204 s, p95 2019 s.
- Источники стоимости: top-K topology, per-region shape tournaments/refinement, multi-renderer
  court, exact-font path, fresh-process Python/Torch/CUDA startup.
- Evidence cache помогает только повторному source hash, но не первой пользовательской задаче.

### 7.9. Abstention не решает пользовательскую задачу

Engine умеет abstain/оставаться alternative route, но пользователю нужен стабильно хороший
output. Высокий abstention rate может защитить production default, но не приблизить качество VAI.

## 8. Почему метрики раньше не замечали деградации

1. Global SSIM/IoU усредняют большую белую/одноцветную площадь и могут почти не штрафовать
   сломанную маленькую надпись.
2. Boundary F-score высокий даже при неверном painter order, лишних holes или неправильной
   semantic grouping.
3. Pixel MAE может улучшиться от «ластика»/background overlay, который структурно полностью
   неверен.
4. Generic Betti/component counts зависят от threshold и не сопоставляют semantic loci.
5. Geometry smoothness метрики могут наградить гладкую, но неправильную фигуру.
6. Старые campaign results содержали много timeouts; surviving subset создавал selection bias.
7. Blind court раньше показывал vector в неудобном разрешении. Сейчас существует
   resolution-honest crop court (`build_vai_crop_court.py`, `web_preview/court.html`), но его
   нужно повторно зафиксировать и провалидировать в новой campaign.

Метрики, которые уже добавлены для снижения blind spots: persistent Betti curve, catastrophic
loci, counters, components lost/added/fused, local DE worst window, boundary tail/CVaR,
roundness/kinks, repeated geometry violations. Они всё ещё не заменяют human blind court.

## 9. Критические математические/кодовые ошибки, уже найденные и исправленные

Эксперту важно не тратить время на повторное обнаружение этих старых bugs:

1. Global optimizer суммировал local per-shape MDL и тем самым награждал удаление букв/
   components. Исправлено на mean per-shape MDL + отдельный topology proposal score.
2. Topology score записывался в trace, но не участвовал в global objective. Исправлено.
3. Cheap shortlist удалял единственную detail-preserving topology до physical court.
   Balanced `sigma=0.65` hypothesis теперь сохраняется.
4. Exact-font OCR/catalog запускался даже когда text невозможно разрешить; добавлен physical gate.
5. Text profiler видел только dark-on-light; добавлена light-on-dark polarity.
6. Residual мог добавить shape площадью 87% canvas как верхний eraser; запрещено >35% canvas.
7. Algebraic circle LSQ принимал короткий почти прямой fragment как огромный circle с center за
   bbox; добавлен extent/center identifiability wall.
8. Любой hole contour с >=8 points превращался в ellipse; теперь нужен physical RMS <=0.45 px.
9. Opaque border background всегда удалялся, включая isolated white knockouts; теперь удаляется
   только border-connected background component.
10. Neural `shape_class_logits` и `corner_type` после BCE использовались без sigmoid; исправлено.
11. Training script через общий `rglob` смешивал train/validation/test; теперь обучение жёстко
    ограничено `train/` и требует clean-room manifest.
12. Отсутствие promoted checkpoint раньше было silent fallback; теперь причина и фактический
    model version записываются в DecisionTrace.

Regression suite после этих fixes: `test_scene_engine.py` PASS, `unittest` 58/58 PASS,
compileall PASS. После последних lifecycle scripts suite нужно повторить перед новым freeze.

## 10. Отрицательные эксперименты, которые не следует повторять без новой гипотезы

1. Hard AA palette collapse `10 -> 4`: быстрее, но Dunkin SSIM `0.746 -> 0.690`, IoU
   `0.808 -> 0.785`.
2. Background/paint coverage projection: SSIM `0.679`, IoU `0.774`.
3. Global polyline simplification tube increase: IoU `0.808 -> 0.801`, без meaningful speed win.
4. Pure learned evidence replacement: synthetic aggregate лучше, но boundary/normal/corner/
   centerline heads хуже в 3–14 раз.
5. Hybrid semantic evidence promotion: synthetic PASS, real A/B FAIL на всех трёх кейсах и
   latency regression.

## 11. Реализованные модули и их maturity

| Module | Код | Статус качества |
|---|---|---|
| Immutable contracts / scene graph | `vice_scene/contracts.py`, `scene_graph.py` | Контракты и round-trip есть; real graph recovery слабый |
| Canonical ingest | `ingest.py`, `raster_profile.py` | Unit coverage хороший |
| Synthetic factory | `synthetic.py`, `training_data.py`, `font_synthetic.py` | Инфраструктура есть; distribution/labels недостаточны |
| Evidence | `evidence_model.py`, `neural_evidence.py` | Deterministic default; learned candidate rejected на real A/B |
| Appearance | `appearance.py` | Soft hypotheses есть; palette/topology coupling остаётся проблемой |
| Topology | `topology.py` | top-K есть; proposal recall на real неизвестен |
| Whole shapes | `shape_models.py` | Семейства есть; selection/identifiability нестабильны |
| Shared boundaries/corners | `boundary_solver.py`, `corner_graph.py` | Physical contracts есть; joint topology слабая |
| Text | `text_scene.py`, `font_synthetic.py` | Path A/B есть; качество real logos недостаточно |
| Global optimizer | `optimizer.py`, `idealize.py` | Критический MDL bug исправлен; objective не откалиброван на semantic risk |
| Forward court | `render_models.py` | Synthetic selection есть; real identifiability/calibration слабая |
| Residual | `residual.py` | Catastrophic eraser закрыт; это не замена topology recovery |
| Export | `export_scene.py` | SVG/PNG/PDF/EPS/DXF adapters есть |
| Trace/cache/freeze | `pipeline.py`, `trace.py`, `evidence_cache.py`, `freeze.py` | Audit есть; новый build ещё не frozen/campaigned |

## 12. Reproduction

Из workspace root:

```powershell
python -X utf8 test_scene_engine.py
python -X utf8 -m unittest discover -p "test_*.py"
python -m compileall -q vice_scene
```

Проверка synthetic evidence candidate:

```powershell
python -X utf8 validate_scene_evidence.py `
  .\datasets\scene_evidence_promotion_v1 `
  .\models\scene_evidence.candidate.pt `
  --training-dataset .\datasets\scene_evidence_cleanroom_v1 `
  --out .\benchmarks\scene_evidence_independent_promotion.json `
  --device cuda
```

Real-image gate (ожидаемый текущий результат: FAIL):

```powershell
python -X utf8 validate_scene_evidence_real_ab.py `
  .\models\scene_evidence.candidate.pt `
  .\benchmarks\scene_evidence_independent_promotion.json `
  --out .\benchmarks\scene_evidence_real_ab.json
```

Current deterministic Scene run:

```powershell
python -X utf8 -m vice_scene "PATH_TO_IMAGE.png" `
  --out .\test_runs\scene --topology-k 2 --deterministic-evidence
```

UI/API: `http://127.0.0.1:8877/`  
Blind court: `http://127.0.0.1:8877/court.html`

## 13. Конкретные вопросы эксперту

1. Какие dense labels здесь принципиально неверны? Нужны ли boundary distance field,
   signed distance/coverage, instance embeddings, watershed seeds, affinity graph, occlusion
   order, tangent/corner types вместо текущих per-pixel masks?
2. Как правильно определить uncertainty target: aleatoric degradation posterior, ensemble
   variance, entropy over topology hypotheses или learned calibration residual?
3. Нужен ли neural proposal generator для instances/loops, а не dense semantic heads?
4. Какой objective лучше гарантирует topology preservation: differentiable Euler/Betti losses,
   contour matching, instance affinity, minimum-cost graph decoding или discrete structured loss?
5. Как строить font-free logo text prior: glyph autoencoder/SDF diffusion, retrieval bank,
   repeated-prototype EM, stroke skeleton grammar или другое?
6. Должен ли text engine работать параллельно с appearance topology и отдавать competing scene
   hypotheses до palette commit?
7. Как сделать oracle-proposal/real-selector и real-proposal/oracle-selector experiment на
   реальном raster, где true SVG неизвестен?
8. Как calibrate forward likelihood так, чтобы идеальная geometry выигрывала у raster-noise
   overfit, но small semantic detail не исчезал?
9. Какой real clean-room corpus нужен по масштабу и покрытию? Нужны ли миллионы процедурных
   scenes, licensed SVG corpora, self-supervised degradation inversion, hard-negative mining?
10. Как избежать train/test leakage при использовании human/VAI comparison только для оценки?
11. Какой production architecture даст <2–5 s cold latency: persistent GPU worker, batched
    evidence service, proposal caching, reduced topology beam, coarse-to-fine search?
12. Какие три эксперимента дадут максимальный information gain до следующей дорогой VAI50/115
    campaign?

## 14. Ограничения clean-room

- VAI SVG/output нельзя использовать как training data.
- VAI допускается только как evaluation/human comparison и structural black-box observation.
- Не обходить оплату, authentication или technical restrictions.
- Training data: собственные source scenes, legally usable fonts/SVG, собственные renderers и
  degradations.
- Нельзя подгонять параметры по frozen test после BUILD_FREEZE.

## 15. Ключевые документы и артефакты

- Исходный план:
  `C:\Users\nirrt\Downloads\vectorizer_ai_clean_room_research_bundle\VectorizerAI_clean_room_reverse_engineering_plan_by.md`
- Implementation matrix: `VICE_SCENE_IMPLEMENTATION_MATRIX_BY.md`
- Последний remediation report: `P0_SCENE_OBJECTIVE_REMEDIATION_BY.md`
- Старый полный verdict/report: `P0_REMEDIATION_RESULTS_BY.md`
- Scene package: `vice_scene/`
- Evidence training: `generate_scene_evidence_dataset.py`, `train_scene_evidence.py`
- Synthetic promotion gate: `validate_scene_evidence.py`
- Real A/B gate: `validate_scene_evidence_real_ab.py`
- Full campaign orchestrator: `validate_scene_campaign.py`
- Bounded campaigns: `run_scene_vai50_bounded.py`, `run_scene_challenge115_bounded.py`,
  `run_scene_ablations_bounded.py`
- Current candidate: `models/scene_evidence.candidate.pt`
- Rejected promoted checkpoint: `models/scene_evidence.real_ab_rejected.pt`

## 16. Требуемый формат ответа эксперта

Желательно вернуть:

1. Diagnosis с ранжированием причин по вероятности и impact.
2. Что в текущей математике/labels/objective неверно принципиально.
3. Новую architecture diagram и data/label schema.
4. 3–5 staged experiments с budget, expected signal и stop condition.
5. Promotion gates для synthetic, real held-out, VAI50/115 и human blind court.
6. Отдельный план для text/logo recovery.
7. Отдельный план ускорения до production latency.


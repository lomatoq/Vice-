# V-ICE: вынікі поўнага clean-room аўдыту і P0-выпраўленняў

Дата: 2026-07-20  
План-крыніца: `VectorizerAI_clean_room_reverse_engineering_plan_by.md`  
Замарожаны Scene Engine hash: `33bc0d63e4b82734bcb5349f5d19385ac16b0fbdc6e31074814728c90238758f`

## Кароткі verdict

Усе Build 1–14 з плана прадстаўлены ў кодзе і маюць кантракты, feature flags,
DecisionTrace і ізаляваны end-to-end route. Але гэта **архітэктурная
рэалізацыя, а не доказ якасці**. Замарожаная validation campaign сумленна
праваліла promotion rule: Scene Engine нельга рабіць default і нельга называць
лепшым за VectorizerAI. Production default застаецца выпраўлены legacy
`paper-regions` (`V-ICE Best`).

Гэта не супярэчнасць: план рэалізаваны як сістэма, але яго гіпотэза пра тое,
што першая рэалізацыя Scene Engine адразу пераможа VAI, не пацверджана.

## Пакрыццё Build 1–14

| Build | Рэалізацыя | Стан пасля validation |
|---|---|---|
| 1. Contracts/scene graph | `vice_scene/contracts.py`, `scene_graph.py` | schema/round-trip/smoke працуюць |
| 2. Canonical ingest | `ingest.py`, `raster_profile.py` | native coordinates, alpha, EXIF/ICC contracts ёсць |
| 3. Synthetic factory | `synthetic.py`, `training_data.py`, generator scripts | deterministic manifests і renderer/degradation fixtures ёсць |
| 4. Evidence backbone | `evidence_model.py`, `neural_evidence.py`, `evidence_cache.py` | API і checkpoint policy ёсць; evidence v2 не дае production-якасці |
| 5. Appearance hypotheses | `appearance.py` | late palette/solid/gradient hypotheses ёсць |
| 6. Topology hypotheses | `topology.py` | top-K, holes/containment/split-merge ёсць; solver дарагі |
| 7. Whole shapes | `shape_models.py` | published families + ring/ribbon tournaments ёсць |
| 8. Shared boundaries | `boundary_solver.py`, `corner_graph.py` | interface-once і physical-cost ёсць |
| 9. Text scene | `text_scene.py`, `font_synthetic.py` | Path A/B і persistent counters ёсць; real text tail яшчэ слабейшы за VAI |
| 10. Optimizer/idealizer | `optimizer.py`, `idealize.py` | rollback, symmetry, simplicity, abstention contracts ёсць |
| 11. Forward court | `render_models.py` | AA/gamma/blur/JPEG model selection ёсць |
| 12. Residual add/prune | `residual.py` | bounded immutable proposals ёсць |
| 13. Export | `export_scene.py`, `gap_filler.py` | SVG + native/4x PNG; adapters/transform contracts ёсць |
| 14. Integration/traceability | `pipeline.py`, `config.py`, `trace.py`, `freeze.py` | CLI/API, isolation, cache, ablations, resource accounting ёсць |

Такім чынам, “зрабіць усе модулі” выканана. “Стаць лепш за VAI” — не
выканана і не маскіруецца зялёнымі unit-тэстамі.

## Замарожаная кампанія: што фактычна атрымалася

### VAI50

- Улічана 50/50: 31 complete, 19 resource failures; прапушчаных элементаў 0.
- Promotion gate: `FAIL / DO_NOT_PROMOTE`.
- На 31 завершанай пары: сярэдні SSIM 0.6629 супраць 0.9615 у VAI;
  ink-IoU 0.7033 супраць 0.9499; MAE 26.47 супраць 5.16.
- Scene лепшы па асобных геаметрычных proxy (напрыклад, G2 і часткова
  roundness), але значна прайграе ў выглядзе, колеры, topology tail і latency.
- 31/31 завершаных Scene-вынікаў былі catastrophic па агульным frozen gate;
  у VAI — 0/31.
- p50 runtime 204.33 с, p95 2018.72 с; 18 з 31 даўжэй за 120 с.

Крыніца: `benchmarks/scene_validation/33bc0d63e4b82734/vai50_freeze_ledger.json`.

### Blind challenge 115

- Улічана 115/115: 27 complete, 88 timeout.
- Promotion gate: `FAIL`.
- На завершаных 27: SSIM-wins 0/27, ink-IoU-wins 0/27, MAE-wins 1/27.
- Гэта не “няма дадзеных”: timeout запісаны як resource failure і сам па сабе
  валiць production gate.

Крыніца: `benchmarks/scene_validation/33bc0d63e4b82734/challenge115_bounded/report.json`.

### Ablations

- 51 bounded jobs: 8 complete, 43 timeout.
- Адключэнне evidence+topology на двух малых кейсах скараціла час прыкладна да
  24–28 с; baseline/большасць варыянтаў не ўкладваліся ў 60 с.
- Гэта моцнае сведчанне, што галоўны latency bottleneck — combinatorial
  topology/scene search і яго паўторныя full renders, а не файл upload або UI.
- Матрыца недастатковая для causal quality verdict па ўсіх модулях, бо 84%
  спроб скончыліся timeout.

Крыніца: `benchmarks/scene_validation/33bc0d63e4b82734/ablations_bounded/ablation_matrix.json`.

## Чаму вынікі на скрыншотах былі дрэнныя

1. Structural-diagram lane рабіў destructive carve па слабым NFA-сігнале і
   ствараў формы “з ніадкуль”. Цяпер для auto-route патрабуецца evidence ratio
   ≥4; слабыя сеткі abstain.
2. Text/wordmark праходзіў праз агульны junction graph пасля правільнай
   segmentation і губляў counters/раздзяленне. Дададзены topology-preserving
   glyph/known-template courts.
3. Тонкія compound rings ацэньваліся як filled disc супраць annulus; потым
   дарагі DP ператвараў намер “ідэальны круг” у сотні лакальных кавалкаў.
   Дададзены вузкі joint court для дзвюх незалежна кругавых, канцэнтрычных
   межаў; rectangle/polygon не могуць выпадкова выйграць на compound-рэгіёне.
4. Perceptual retrace паўтараў восем поўных трасіровак нават пасля exact
   topology repair. Цяпер exact repair з'яўляецца законнай ніжняй мяжой і
   retrace прапускаецца.
5. Path-affine calibration рабіў амаль 3700 renders на 10 paths. Захаваны тыя
   ж дапушчальныя значэнні і hard gates, але пошук заменены на deterministic
   two-pass coordinate descent (~540 renders).
6. UI пасля завяршэння працягваў лічыць elapsed time ад `time.time()`, таму
   гатовы job выглядаў як усё больш павольны. Цяпер выкарыстоўваецца
   `finished_at`.

## Свежыя production-вынікі карыстальніцкіх правалаў

| Кейс | Час worker | Topology | MAE | Ink-IoU | SSIM | Boundary F |
|---|---:|---:|---:|---:|---:|---:|
| Lion, Best | 83.17 с | 7/1 = source | 4.092 | 0.96898 | 0.97179 | 1.0000 |
| Mastercard, Best | 90.59 с | 5/7 = source | 4.026 | 0.95958 | 0.94535 | 0.98831 |

Lion быў ~159.6 с да joint circle court. Новы круг ідэальны і runtime амаль
удвая меншы. Pixel SSIM на 0.00157 ніжэй за ранейшы raw-contour incumbent
(0.97336), але вышэй за валідную VAI-пару (0.96696), topology дакладная, а
геаметрычны intent мацнейшы. Гэта свядомы вузкі idealization trade-off, а не
схаваны “зялёны” metric.

На Mastercard свежы Best лепшы за валідную VAI-пару па MAE (4.026 супраць
4.427), крыху лепшы па SSIM (0.94535 супраць 0.94324) і захоўвае 5/7 topology,
тады як VAI render мае 5/6. Па ink-IoU VAI усё яшчэ лепшы (0.96974 супраць
0.95958). Значыць, гэта змяшаны, а не абсалютны win.

Дадатковыя валідныя пары:

- wordmark: VAI крыху лепшы (SSIM 0.97063 супраць 0.97033; IoU 0.99315
  супраць 0.98995), topology ў абодвух 11/4;
- Dunkin: V-ICE лепшы па MAE/IoU, VAI крыху лепшы па SSIM; topology V-ICE
  25/7, VAI 26/7;
- для NBC source `22_icon_group_3_src.png` няма пацверджанай VAI-пары:
  наяўны VAI stem адпавядае іншаму source/resolution. Ён выключаны з
  head-to-head verdict, а не падменены зручным вынікам.

## Regression і матэматычны аўдыт пасля выпраўленняў

- `python -m unittest discover -p "test_*.py"`: **58/58 PASS**.
- DP physical-fidelity: PASS.
- DP hot-path physical-fidelity: PASS.
- Structural diagram lane: PASS.
- Scene build contracts: PASS.
- Strike-0 metrics/live-court contracts: PASS.
- Full stage suite: **ALL GREEN**, 270.2 с.
- 13 synthetic cases: PASS.
- Human-corner held subset: P=0.776, R=0.918, F1=0.841, 12 logos.
- 12/12 named problem cases: PASS, у тым ліку IKEA, Mastercard wordmark,
  Lacoste, NBC, Mobil, Lion і Mastercard.
- `py_compile/compileall`: PASS.
- Source-only `git diff --check`: PASS. Агульны worktree check засмечаны
  ранейшымі/generated CRLF SVG/JSON artifacts і не выкарыстоўваецца як доказ
  чысціні source diff.

Актуальны stage snapshot: `benchmarks/stage_snapshot.json`.

## Blind court і UI

- Стары human court быў несумленны: vector side паказваўся ў іншай
  эфектыўнай раздзяляльнасці.
- Новы court мае 12 blind cards, аднолькавы viewport, source + абедзве SVG
  hypotheses, 2× default і 4× zoom; правераны 36/36 assets.
- Production endpoint асінхронны, цяжкая праца ідзе ў асобным worker process,
  job можна апытваць/адмяняць, а completed elapsed больш не расце.

Лакальны UI: `http://127.0.0.1:8877/`  
Blind court: `http://127.0.0.1:8877/court.html`

## Што яшчэ патрэбна да сапраўднага “лепшы ў свеце”

Scene Engine застаецца experimental. Каб вярнуцца да promotion:

1. Змяніць exhaustive topology/renderer search на bounded coarse-to-fine
   proposal generation з bbox-local incremental scoring і жорсткім cap.
2. Навучыць evidence model на ўласным renderer/degradation corpus; цяперашні
   deterministic/weak checkpoint не вырашае glyph і appearance ambiguity.
3. Зрабіць text line/glyph hypotheses першакласнымі да palette commit, а не
   спадзявацца на post-hoc OCR/font recovery.
4. Паўтарыць новую frozen VAI50/115 кампанію толькі пасля новага BUILD_FREEZE.
5. Патрабаваць адначасова human non-inferiority, topology-tail, perceptual
   metrics, editability і production latency. Ні адзін сярэдні SSIM не мае
   права адзін “апрувіць” сістэму.

Да гэтага моманту сумленны статус: **legacy Best істотна выпраўлены і прыдатны
для ручнога тэставання; Scene route пабудаваны, але DO_NOT_PROMOTE; доказу
“самы лепшы вектарызатар у свеце” няма**.

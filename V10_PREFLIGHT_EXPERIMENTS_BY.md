# V10 preflight: рашальныя эксперыменты да любога новага трэніну

Дата адкрыцця: 2026-07-24.
Кантракт: `CLAUDE.md` Частка II; план: `EXTERNAL_AUDIT_WORDMARK_V10_20260724.md` §16–17.
Статус дакумента: **жывы**; аўтарытэтны апошні нумараваны запіс.

Мэта: перад v9.5/v10 закрыць пяць пытанняў знешняга аўдыту (Experiments A–E),
каб дакладна ведаць, якая частка v10 патрэбна першай. Ніякіх full runs:
толькі bounded diagnostics на ўжо існуючых чэкпойнтах і дадзеных.

---

## Сесійная табліца ісціны (2026-07-24)

- **CURRENT TRUTH:** v9 = стабілізацыя v5-кода, толькі 300-step smoke
  (`WORDMARK_V1_LIVE_AUDIT_BY.md` №74); ProposalNet v14 `NO-TRAIN`
  (`PRE_V14_READINESS_AUDIT.md`); VAI-парытэт не даказаны
  (`V_ICE_CURRENT_AUDIT.md`); GPU-трэніроўка НЕ ідзе (праверана 2026-07-24:
  адзіны python-працэс — web preview server).
- **OPEN BLOCKER:** доўгарадковая exact topology wordmark prior
  (repr. ceiling паводле знешняга аўдыту D1) — не пацверджана
  ізалявана ад observability/px-per-glyph.
- **KNOWN NEGATIVE EVIDENCE:** v4–v8 (лічбы ў
  `EXTERNAL_AUDIT_WORDMARK_V10_20260724.md` §3): global/additive/spatial
  count heads, threshold/fusion oracle, рэгрэсія counts — усё закрыта.
- **TOP COMPETING EXPLANATIONS:**
  A. representation ceiling (mask+counts не выражаюць long-line topology);
  B. spatial bottleneck (64×256 канвас душыць px/glyph пры L≥17);
  C. inverse/degradation encoder (мадэль чысціць бачнае, не аднаўляе латэнтнае);
  D. hard-OCR conditioning шкодзіць пры карупцыі.
- **CHEAPEST DECISIVE EXPERIMENT:** B (clean identity) — раздзяляе A/B ад C
  без ніякага трэніну; + ppg-вымярэнне для B-гіпотэзы.
- **STOP CONDITION:** гл. кожны эксперымент ніжэй.
- **FILES LIKELY TO CHANGE:** `diagnose_wordmark_clean_identity.py` (новы),
  `benchmarks/pcdc_pre_v14/wordmark_clean_identity_*.json` (новыя артэфакты).
- **PROOF IMPACT:** нічога не інвалідуецца — толькі новыя дыягностыкі,
  прадакшн-шлях не кранаецца.

---

## Experiment B — clean-input identity (СТАТУС: запушчаны)

### Hypothesis card

- **Problem:** доўгія радкі валяць exact topology (v4 epoch3: len 17–32 raw
  0.323 на degraded held-out). Невядома, колькі з гэтага — інверсія
  дэградацыі, а колькі — сама рэпрэзентацыя/канвас.
- **Мechanism:** падаць мадэлі яе ўласны ЧЫСТЫ target (без degrade) з
  дакладным OCR; калі doўгія чыстыя радкі ўсё роўна валяцца — столь у
  рэпрэзентацыі/alignment (D1/D2); калі чыстыя праходзяць — вузкае месца
  inverse encoder/data (D-degradation), і v10-прыярытэт зрушваецца.
- **Setup:** чэкпойнт `models/wordmark_prior_candidate_v1_epoch3.pt` пад
  нязменным снапшотам `.training_snapshots/wordmark_full_v4_20260723`
  (SHA-кантракты правераны, fail-closed захаваны); held-out families
  (split-seed 20260722, digest звераны з чэкпойнтам); lengths
  {1,2,4,8,16,24,32} × 512; seed 20260724.
- **Positive control:** length 1–2 павінны быць блізкія да degraded-паказчыкаў
  length 1–2 (0.94+) або вышэй.
- **Negative control:** прадакшн не кранаецца; скрыпт read-only да мадэлі.
- **Expected signal:** калі repr. ceiling — clean len-32 raw topology ≪ 0.95;
  калі observability — clean len-32 ≈ 1.0 і рэзкі кантраст з degraded 0.323.
- **Stop condition:** вынік адназначны ў абодва бакі; паўтор не патрэбны.
- **Budget:** ~хвіліны GPU (RTX 4070), 3584 сэмплаў, адзін прагон.

### Запіс 1 — smoke (24 сэмплы, не доказ, толькі праверка канвеера)

Скрыпт працуе, кантракт/спліт супалі. Папярэдні сігнал (n=8/даўжыню):
clean raw topology 1.0 нават на len 32; joint HEAD на len 32 — 0.375;
ppg: len1 ≈ 39 px, len32 ≈ 7.6 px. Чакаем поўны прагон.

### Запіс 2 — поўны прагон 3584 (2026-07-24, ВЫНІК)

Артэфакт: `benchmarks/pcdc_pre_v14/wordmark_clean_identity_v4epoch3_3584.json`
(чэкпойнт epoch3, SHA у артэфакце; 49.4 s на RTX 4070; парог 0.50
calibrated-on-this-split).

| L | ppg,px | raw topo | decoded topo | joint head |
|---|--------|----------|--------------|------------|
| 1 | 39.9 | 0.9844 | 0.9863 | 0.9824 |
| 2 | 39.5 | 0.9805 | 0.9727 | 0.9316 |
| 4 | 37.6 | 0.9863 | 0.9512 | 0.8848 |
| 8 | 28.2 | 0.9766 | 0.8984 | 0.7910 |
| 16 | 15.1 | 0.9648 | 0.8652 | 0.5840 |
| 24 | 10.1 | 0.9648 | 0.9082 | 0.4316 |
| 32 | 7.6 | 0.8965 | 0.8848 | 0.3125 |

Overall: raw 0.9648, decoded 0.9238, joint head 0.7026, IoU 0.9974.

**Факты:**

1. Чысты ўваход трымае raw topology 0.965 агулам і 0.897 на len 32 —
   супраць 0.323 на degraded len 17–32 (аўдыт v4 epoch3). Разрыў ×2.8
   на доўгіх радках — дамінантная кампанента правалу гэта **інверсія
   дэградацыі**, не raw-дэкодэр на чыстым.
2. Count heads валяцца з даўжынёй НАВАТ на чыстым уваходзе:
   joint 0.982 → 0.312 (манатонна). Гэта столь рэпрэзентацыі
   глабальных лічыльнікаў, незалежная ад degradation.
3. **Свежы негатыў: head-conditioned repair ШКОДЗІЦЬ на чыстым уваходзе** —
   decoded 0.924 < raw 0.965 агулам; горш за ўсё на сярэдніх даўжынях
   (len 8: 0.898 супраць raw 0.977). Рамонт, ведзены памылковымі heads,
   разбурае правільную raw-тапалогію.
4. ppg-вымярэнне (Experiment A-lite): 39.9 px/glyph (L=1) → 7.6 (L=32);
   raw topology трымаецца ≥0.965 да ppg≈10 і правальваецца на 7.6
   (len 32: 0.897). Уплыў squeeze ёсць, але меншы за degradation-разрыў.

**Высновы (моцныя inference, не факты):**

- Па інтэрпрэтацыі аўдыту §16-B спраўджваюцца АБОДВА бакі: clean len 32
  raw 0.897 < 0.95 → рэпрэзентацыя/alignment недастатковая на макс.
  даўжынях; clean ≫ degraded → inverse encoder — галоўны маштабны фактар.
- Пацверджана «не дадаваць v10 count head» (аўдыт §6): heads не проста
  бескарысныя — праз repair яны актыўна шкодзяць.
- v9 full run застаецца дэаўтарызаваным: ён атрымаў бы ў спадчыну і
  count-heads-столь, і inverse-разрыў.
- Прыярытэт v9.5 Template-Warp lane узмацняецца: template дае і latent
  structure для degraded (закрывае п.1), і topology by construction
  (закрывае п.2–3).

### Запіс 3 — поўная матрыца 2×3: уваход × OCR-рэжым (2026-07-24, ВЫНІК)

Той жа пратакол (3584, held-out, балансаваныя даўжыні); артэфакты
`benchmarks/pcdc_pre_v14/wordmark_identity_{clean,degraded}_ocr{exact,corrupted,blank}_3584.json`.
`blank` = адзін кропкавы токен (без інфармацыі).

| уваход/OCR | raw | decoded | joint head | len32 raw |
|---|---|---|---|---|
| clean/exact | 0.9648 | 0.9238 | 0.7026 | 0.8965 |
| clean/corrupted | 0.9643 | 0.9082 | 0.6719 | 0.9004 |
| clean/blank | 0.9132 | 0.8836 | 0.6102 | 0.7617 |
| degraded/exact | 0.6454 | 0.6443 | 0.6166 | 0.2285 |
| degraded/corrupted | 0.6451 | 0.6281 | 0.5759 | 0.2305 |
| degraded/blank | 0.6230 | 0.6136 | 0.5167 | 0.2090 |

**Факты (Experiment E закрыты):**

1. **Няправільны hard transcript не каштуе НІЧОГА для маскі**
   (raw 0.6454 супраць 0.6451; len32 0.2285 супраць 0.2305). Гіпотэза D4
   («wrong hard OCR цягне маску да няправільных гліфаў») — сфальсіфікавана
   для v4-архітэктуры.
2. Але БЕЗ транскрыпту горш (clean raw −5.2 пт, len32 −13.5 пт): мадэль
   выкарыстоўвае транскрыпт як агульны prior даўжыні/чарніла, не як змест.
   Інфармацыя ёсць — цяперашні інтэрфейс не ўмее яе есці. Гэта прамы аргумент
   за v10 explicit layout/content conditioning, а не за N-best у v4-форме.
3. Heads чытаюць транскрыпт крыху больш за маску: joint −4.1 пт ад карупцыі
   на degraded (0.6166 → 0.5759).
4. **Degraded-B на адным пратаколе з clean-B:** degraded/exact len32 raw
   0.2285 супраць clean/exact 0.8965 — разрыў ×3.9, дамінантнасць інверсіі
   дэградацыі пацверджана і на балансаваным пратаколе.

**Выснова для v10-дызайну:** OCR-небяспека не ў «атручванні» маскі, а ў
марнаванні транскрыпту. Патрэбны інтэрфейс, дзе транскрыпт becomes
канструкцыя (layout + templates), а не embedding-падказка.

---

## Experiment A — length × pixels-per-glyph (СТАТУС: вымярэнне ppg ідзе разам з B)

Цяперашняя палітыка канваса (снапшот і бягучы код ідэнтычныя ў гэтым):
aspect-preserving letterbox у фіксаваныя 64×256 з палямі
(`wordmark_prior_data.py::render_clean_wordmark`), г.зн. px/glyph ∝ 1/L.
Вымярэнне ppg на чыстых рэндэрах уваходзіць у справаздачу Experiment B
(палі `pixels_per_glyph_*` per length). Поўны трэніровачны варыянт A
(dynamic width пры фікс. ppg) патрабуе змены рэпрэзентацыі — толькі пасля
вынікаў B і рашэння па v9.5/v10.

## Experiment C — oracle layout (СТАТУС: чарга)

Патрабуе новага conditioning-шляху (падаць exact glyph boxes) — net-new
для мадэлі; праектуецца пасля вынікаў B.

## Experiment D — oracle template + layout fit (СТАТУС: поўныя прагоны ідуць)

Пабудаваны `diagnose_template_warp_oracle.py` — ядро будучай v9.5-лініі
ў дыягностычнай форме: oracle font+transcript, НЕвядомыя рэндэр-параметры
фітуюцца з degraded raster праз каскад §9.1: аналітычны трэкінг з
назіранай шырыні → пер-гліфныя НАКОПНЫЯ зрухі (манатонны layout, ±3px/крок)
→ пер-гліфны x-scale → строук → яўныя тапалагічныя аператары
none/connected/outline (§8.8). Дзве арэны: fixed 64×256 (супастаўляльна
з мадэллю) і dynamic (ppg захаваны — рэжым сапраўднай лініі).
Селекцыя дваістая (§9.3): selected (па назіранні) і oracle (столь
генератара, па GT). Метрыкі ўключаюць topology edit distance.

Урокі адладкі (правераны вачыма на overlay'ях, застаюцца ў дызайне v9.5):
- глабальная сетка трэкінгу не дае 0.5px/гліф на 32 гліфах — толькі
  накопныя пер-гліфныя зрухі трымаюць доўгі радок;
- выраўноўванне па bbox шумнай маскі ламаецца ад degradation-астраўкоў —
  трэба robust-кампаненты і мяккі (float) скорынг;
- растравая дылатацыя строука зліпае суседзяў, парог закрывае валасяныя
  каўнтэры — класы памылак, якіх ВЕКТАРНАЯ эмісія з аналітычнай тапалогіяй
  пазбягае канструктыўна; таму фінальны суддзя лініі мусіць быць
  посерыёрны рэндэр-суд, а не голы IoU парогавай маскі.

## Experiment E — OCR conditioning matrix (СТАТУС: ЗАКРЫТЫ, гл. Запіс 3 вышэй)

N-best у v4/v9 непрадстаўляльны (адзін hard string); карупцыйны кантраст
вымераны: масцы ўсё роўна (D4 сфальсіфікавана), транскрыпт недавыкарыстаны.

---

## Правілы гэтага дакумента

- Кожны запуск дадае нумараваны запіс з датай, seed, SHA чэкпойнта і
  спасылкай на JSON-артэфакт у `benchmarks/pcdc_pre_v14/`.
- Ніякі вынік тут не з'яўляецца promotion proof; гэта дыягностыкі
  ўзроўню §9.1–9.2 кантракта.
- Адмоўныя вынікі не выдаляюцца.

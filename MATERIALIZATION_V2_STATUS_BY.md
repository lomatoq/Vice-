# Materialization v2 — бягучы стан (§19 handoff)

Дата: 2026-07-26. План: `V-ICE_MaterializationV2_implementation_plan_by.md`
(audited_commit 11c4482aa). Гэты файл — адзіны дакумент бягучага стану гэтай
працы; ledger-запісы ў `WORDMARK_V1_LIVE_AUDIT_BY.md`.

---

# Current verdict

Пабудаваны і пратэставаны **поўны ланцуг Materialization v2**: фінальная
вектарная праграма стала першакласным аб'ектам, кандыдаты спаборнічаюць
ДА суда, суд судзіць дакладныя фрагменты, а экспарцёр серыялізуе
пераможцу без уласнай геаметрыі. Усе гейты камітаў M2-01…M2-10 зялёныя
на 106 юніт-тэстах + 37 рэгрэсійных.

**Дастаўлены вынік ёсць (ledger 107):** на 100 рэальных лоцы маршрут
спрацаваў на 43 радках, дастаўленыя байты змяніліся на ўсіх 43, дастаўленая
маска — ні на адным; 0 рэгрэсій, 100/100 not_worse. На 21 радку fair-праграма
дае медыяну 8 path-камандаў замест 1774 (~200×).

**Прамоўшн НЕ адбыўся і не заяўляецца.** Маршрут схаваны за фіча-флагам
`VICE_TEXT_MATERIALIZATION_V2=0/1`; пры выключаным флагу дастаўка
байт-у-байт ранейшая. Дастаўленага чалавечага доказу яшчэ няма — новы
сляпы раўнд магчымы толькі пасля source-freeze (план M4 у §9).

---

# What changed

| камміт | што | гейт |
|---|---|---|
| M2-01 | `vector_program.py`: кантракт праграмы, валідацыя, кананічны дайджэст, SVG-пісьменнік | 29/29 |
| M2-02 | `text_materialization.py` + `svg_fragment_renderer.py`: faithful-праграма з парытэтам рэндэру, обгортка легасі-фітэра | 17/17 |
| M2-04 | `local_court.py`: `evaluation_support` побач з `claimed_support` (ownership ≠ score domain) | 5/5 |
| M2-05 | `materialization_certificates.py`: адпаведнасць кампанентаў, карыдоры раздзялення 1×/2×/4×, delivery identity | 14/14 |
| M2-06 | `coverage_evidence.py` + `wobble_metrics.py` + `fair_curve_program.py` + `shared_primitive_fitting.py`: субпіксельная мяжа, fairness-матэматыка, лексікаграфічны DP line/arc/cubic/faithful | 16/16 |
| M2-07 | `appearance_transport.py`: салентныя колеры, транспарт, completeness-сертыфікат | 13/13 |
| M8 | `text_vector_court.py`: гонка матэрыялізацый з M8.3-парадкам | 9/9 |
| M2-08 | `program_refinement.py`: рэфайн рэальных параметраў праграмы з замарожанай структурай | 8/8 |
| M2-09/M10 | `export_writer._materialization_v2_elements`: экспарцёр аддае фрагмент суда | у складзе гейтаў вышэй |
| M2-10 | `experiment4_textline`: схема v3, `materialization_identity`, `delivered_materialization` па радках | 11/11 рэгрэсіі |
| M0 | `experiment_materialization_oracle.py`: падтрымка × матэрыялізатар | — (вымяральны) |

---

# What was measured

**Сінтэтычны кантроль (96 px, антыаліяснае пакрыццё):**

| форма | пераможца | спаны | супраць faithful |
|---|---|---|---|
| круг | fair | 3 дугі | 240 прамавугольнікаў |
| літара O | fair | 10 | 512 |
| закруглены прамавуг. | fair (нічыя па фізіцы → fairness) | 8 | 160 |
| дзве паласы | fair (нічыя → fairness) | 14 | 288 |
| зубчастая форма | **faithful** | 980 | fair прайграў фізічна |

Гэта і ёсць мэта плана §0: гібрыд, які дае дакладныя прымітывы там, дзе
доказ дазваляе, і сумленныя пікселі там, дзе не.

**Хуткасць:** fair DP p50 210 мс / p95 334 мс на кантур (96 px); гонка
цалкам на рэальным лоцы 1.7 с p50 / 7.0 с p95. Бюджэт §12 (p50 50 мс /
p95 150 мс) **не выкананы**; план §10 наўпрост адкладае натыўнае
паскарэнне да чалавечага сігналу — лічба зафіксавана, не схаваная.

**M0-аракул (6 рэальных лоцы, smoke):** цяперашні гладкі фітэр
**адмаўляецца** на рэальных wordmark-падтрымках (`legacy-pixel-fallback`,
turning density 0.0 — праграмы няма зусім), v2 выбраў fair на 1/6.

---

# What was falsified

1. **«Судзіць матэрыялізатар супраць бінарнай маскі»** — метадалагічна
   несапраўдна: піксельная копія тады аптымальная па азначэнні. Аракул
   пераведзены на пакрыццё з крыніцы.
2. **«Лесвіца з прамавугольнікаў нечэсная па пабудове»** — не
   вымяраецца па-шляхова (кожны прамавугольнік выпуклы, 2π). Сумленная
   мера — паварот на адзінку даўжыні.
3. **«Радыус можна маштабаваць»** — не: пры фіксаваных канцах радыус не
   можа быць меншы за палову хорды; для перамаштабавання кальца патрэбна
   зменная падобнасці.
4. **«Fairness — жорсткае вета ў рэфайне»** — не: сціск кальца ПАВЫШАЕ
   шчыльнасць павароту; §M9.4 адкатвае толькі рэгрэс fairness без
   выйгрышу рэндэру.

---

# What remains unproven

- Перцэптыўны выйгрыш: машынныя лічбы ідэнтычныя па пабудове (тая ж
  маска), таму карысць гладкасці бачная толькі воку на маштабаванні —
  без сляпога раўнда гэта гіпотэза, не факт.
- Перцэптыўны эфект: новы сляпы раўнд не збіраўся (патрабуе source-freeze
  па §9 M4 і новых дайджэстаў).
- Прадакшн-латэнтнасць (§12) — вядома, што не выканана.
- M9 у поўным аб'ёме: зменныя цяпер — радыус дугі і падобнасць кантура;
  канцы адрэзкаў, ручкі кубікаў, per-glyph афіны і параметры фарбы яшчэ
  не ў оптымізатары.
- Appearance v2 у дастаўцы: сертыфікат і кандыдаты ёсць, але лэйн
  дастаўляе адзін fill-слой (шматслойная дастаўка — наступны крок).

---

# Current blockers in priority order

1. **Латэнтнасць**: full p95 5577→6687 мс на лоцы (+20%); бюджэт §12
   не выкананы.
2. **Чалавечы доказ**: новы сляпы раўнд пасля source-freeze.
3. **Шматслойная дастаўка колеру** — без яе 58 нічыіх суда не
   зрушацца.
4. **Phase-7 інтэграцыя**: refine цяпер асобная функцыя; трэба ўключыць
   у `continuous_refine` як стадыю пасля выбару праграмы.

---

# Exact next experiment

Прагон `experiment4_textline --approximate-template --stage-d-upstream`
з `VICE_TEXT_MATERIALIZATION_V2=1` супраць таго ж прагону з флагам 0,
па-радкова: `delivered_materialization.family`, `candidate_gcr`,
`candidate_iou`, `not_worse`. Стоп-умова: любая радковая рэгрэсія GCR
або not_worse=false → флаг застаецца выключаным і прычына запісваецца.

---

# Commands to reproduce

```bash
C:\Python312\python.exe -m unittest test_pcdc_vector_program test_pcdc_text_materialization test_pcdc_fair_curves test_pcdc_text_separation test_pcdc_appearance_transport test_pcdc_materialization_court test_pcdc_delivery_identity
```

```bash
C:\Python312\python.exe -m vice_compiler.experiment_materialization_oracle --limit 24
```

```bash
VICE_TEXT_MATERIALIZATION_V2=1 C:\Python312\python.exe -m vice_compiler.experiment4_textline --approximate-template --stage-d-upstream --out benchmarks/pcdc_pre_v14/experiment4_m2v2_report.json
```

---

# Artifacts and hashes

- Модулі: `vice_compiler/{vector_program,text_materialization,
  svg_fragment_renderer,coverage_evidence,wobble_metrics,fair_curve_program,
  materialization_certificates,appearance_transport,text_vector_court,
  program_refinement,experiment_materialization_oracle}.py`,
  `shared_primitive_fitting.py`.
- Тэсты: `test_pcdc_{vector_program,text_materialization,fair_curves,
  text_separation,appearance_transport,materialization_court,
  delivery_identity}.py`.
- Справаздачы: `benchmarks/pcdc_pre_v14/experiment_materialization_oracle*.json`,
  `experiment4_m2v2_report.json` (у працы).
- Ідэнтычнасць: `SERIALIZER_VERSION = vice-text-vector-program/1`,
  `RENDERER_VERSION = resvg_py/document-roundtrip/1`; кожная праграма
  нясе `program_sha256` і `exact_fragment_sha256`.

---

# Promotion status

**BLOCKED.** Флаг выключаны па змаўчанні; дастаўка з флагам 0 —
байт-ідэнтычная запісанай. Промоўшн магчымы толькі пасля: (1) дастаўленага
прагону без радковых рэгрэсій, (2) латэнтнасці ў бюджэце §12,
(3) новага сляпога чалавечага раўнда ≥75% (§12 Human).

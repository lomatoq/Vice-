# V-ICE Scene Engine: objective/topology remediation

Дата: 2026-07-20  
Версія пасля выпраўленняў: `0.1.1`, deterministic evidence `v3`

## Verdict

Знойдзены і выпраўлены некалькі незалежных матэматычных прычын катастрафічных
вынікаў Scene Engine. На трох розных frozen-кейсах адначасова палепшыліся
якасць і час. Аднак гэта дыягнастычны subset, а не новая поўная VAI50/115
кампанія. Таму замарожаны verdict застаецца **FAIL / DO_NOT_PROMOTE**, а
production default — `V-ICE Best`.

## Выпраўленыя прычыны

1. **Памылковы глабальны MDL.** Лакальны model-choice MDL сумаваўся па ўсіх
   рэгіёнах у objective з per-pixel render NLL. Таму сцэна магла палепшыць score,
   проста выдаліўшы літары і кампаненты. Цяпер у глабальным судзе выкарыстоўваецца
   сярэдні per-shape MDL, а region-count prior жыве ў topology score. Сам topology
   score раней запісваўся ў trace, але ў optimizer наогул не выкарыстоўваўся.
2. **Занадта ранні topology prune.** Cheap shortlist цяпер захоўвае
   detail-preserving `sigma=0.65` гіпотэзу, каб coarse score не мог выкінуць яе да
   physical forward court.
3. **Дарагі бессэнсоўны exact-font Path A.** OCR/font-catalog court прапускаецца,
   калі няма лініі з ≥3 glyphs і native ink-height ≥14 px. Font-free Path B пры
   гэтым застаецца актыўным.
4. **Аднанакіраваны text detector.** Профіль шукаў толькі цёмны тэкст на светлым
   фоне. Цяпер ён аналізуе абедзве палярнасці; deterministic evidence узняты да
   `v3`, каб стары cache не падмяняў новыя палі.
5. **Full-canvas residual eraser.** Residual repair мог прыняць кампанент у 87%
   кадра і пакласці яго верхнім пластом, бо “гумка” памяншала loss дрэннай сцэны.
   Residual цяпер строга лакальны; кампаненты >35% кадра вяртаюцца ў
   topology/background diagnosis і не экспартуюцца як новы shape.
6. **Неабмежаваны circle LSQ.** Кароткі амаль прамы codec-фрагмент мог даць
   алгебраічна дакладны круг радыусам 40–80 px па-за сваім evidence bbox. Лакальны
   crop хаваў footprint, а export перакрываў увесь кадр. Complete-circle LSQ цяпер
   мае extent/centre wall; partial arcs застаюцца асобным RANSAC hypothesis.
7. **Безумоўныя ellipse holes.** Любая ўнутраная пятля з ≥8 кропкамі прымусова
   рабілася эліпсам. Цяпер ellipse прымаецца толькі пры physical RMS ≤0.45 native
   px; angular glyph counters захоўваюцца як polyline.
8. **Opaque background памылкова заўсёды выкідаўся.** Border-connected фон усё
   яшчэ не экспартуецца, але ізаляваныя астравы таго ж колеру цяпер могуць быць
   сапраўднымі белымі glyph/knockout shapes. Празрысты outside па-ранейшаму ніколі
   не становіцца paint.

## Вымераны subset A/B

| Frozen case | Да: SSIM / IoU / час | Пасля: SSIM / IoU / час | Дадатковы вынік |
|---|---:|---:|---|
| Dunkin (`94_icon_group_4_62`) | 0.601 / 0.712 / 24.7 s | **0.751 / 0.815 / 22.5 s** | boundary F 0.996, H95 0.95 px |
| Mastercard (`52_icon_group_4_24`) | 0.370 / 0.558 / 26.0 s | **0.768 / 0.893 / 19.6 s** | MAE 60.61 → 11.22; two circle primitives recovered |
| City Breach (`98_icon_group_4_66`) | 0.067 / 0.659 / 61.3 s | **0.480 / 0.838 / 23.3 s** | boundary F 0.986, H95 0.95 px |

Гэта вялікі recovery адносна frozen Scene, але не VAI parity. У прыватнасці,
font-free glyph reconstruction і painter topology яшчэ губляюць/дадаюць counters,
а palette/coverage ambiguity без навучанага evidence checkpoint не вырашана.

## Адхіленыя эксперыменты

- Hard AA-palette collapse 10→4 паскорыў Dunkin да 24.4 s, але знізіў SSIM
  0.746→0.690 і IoU 0.808→0.785 — адкачана.
- Background/paint coverage projection дала 21.2 s, але SSIM 0.679 і IoU 0.774
  — адкачана: deterministic mixture phase недастаткова надзейная.
- Агульнае павелічэнне polyline simplification tube знізіла IoU 0.808→0.801
  пры амаль нязменным SSIM — адкачана.

## Regression

- `python -X utf8 test_scene_engine.py`: **PASS**.
- `python -X utf8 -m unittest discover -p "test_*.py"`: **58/58 PASS**.
- `python -X utf8 -m compileall -q ...`: **PASS**.
- Дададзеныя regressions правяраюць MDL component-collapse, topology shortlist,
  light-on-dark text, exact-font resolution gate, full-canvas residual eraser,
  giant-circle extent, angular-counter conic wall і opaque knockout topology.

## Што блакуе promotion

1. Няма навучанага і асобна прамоўленага evidence checkpoint, які аднаўляе
   occupancy, edge phase, glyph grouping і occlusion з degraded pixels.
2. Тэкст усё яшчэ збіраецца пасля appearance topology; патрэбны line/glyph
   hypothesis да palette commit з learned glyph prior.
3. Патрэбна новая frozen VAI50 + challenge115 кампанія на новым BUILD_FREEZE.
   Да яе нельга пераносіць subset-паляпшэнні ў агульны “лепш за VAI” verdict.

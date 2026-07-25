# V-ICE PCDC — актуальны аўдыт wordmark prior і адкрытых gates

Дата зрэзу: 2026-07-23. Статус: **не прамоўтнута; VAI parity не заяўлена**.

## Кароткі вердыкт

Стары per-glyph prior навучыўся на synthetic held-out, але не змяніў ніводнага
з 100 фінальных TextLine SVG. Ён не з'яўляецца production-рашэннем і застаецца
адключаным. Бягучы кандыдат — whole-line OCR-conditioned wordmark prior без
character-cell seams. Няпоўны v3 run спынены да epoch 1, калі audit выявіў,
што ён прапускае 1–2-сімвальныя logo. Строгі v4 preflight пройдзены, і frozen
full run ужо навучаецца на 2 000 000 унікальных wordmarks, 4 эпохах і асобных
па font family calibration/test splits па 20 000 прыкладаў.

Production па-ранейшаму fail-closed: адна наяўнасць checkpoint не ўключае
мадэль. Патрэбны ўсе strict synthetic gates, свежая model-OFF/model-ON
Experiment 4, blind human court, current full regression і hash-bound promotion.

## Што паказаў машынны plan audit

Актуальны справаздачны файл:
`benchmarks/pcdc_pre_v14/plan_traceability.json`.

Адкрыта 8 патрабаванняў:

1. Перазапусціць Experiment 1 на бягучым compiler hash.
2. Перазапусціць Experiment 1B.
3. Перазапусціць Experiment 2.
4. Перазапусціць Experiment 3.
5. Атрымаць поўны 2M wordmark checkpoint, які праходзіць unseen gates.
6. Даказаць, што менавіта гэты checkpoint змяняе certified delivered SVG.
7. Перазапусціць Experiment 4 OFF/ON і прайсці machine + human gates.
8. Перазапусціць Experiment 5.

Experiments 1/1B/2/3/5 раней праходзілі, але іх справаздачы цяпер састарэлі па
compiler source SHA пасля wordmark runtime інтэграцыі. Яны не залічваюцца па
старых лічбах.

## Вымераны scaling signal, але яшчэ не production proof

100k unique × 4 epochs probe:
`benchmarks/pcdc_pre_v14/wordmark_prior_scale_probe_recalibrated_fine_thresholds.json`.

- decoded support IoU: `0.92577`;
- decoded exact topology: `0.5526`;
- decoded complex topology: `0.53853`;
- calibration выбрала support threshold `0.85`;
- calibration выбрала topology-repair confidence `0.70`.

IoU ужо вышэй мінімальнага `0.88`, але topology далёка ніжэй production gate
`0.95` (`0.90` для complex). Таму гэты checkpoint правільна адхілены.

Актуальны pass preflight v4:
`benchmarks/pcdc_pre_v14/wordmark_prior_preflight_v4.json`.

- serving vocabulary: `69/69`, missing `""`;
- family disjointness/determinism/topology diversity: pass;
- serving length range: усе 32 значэнні `1–32`;
- 1500-step IoU: `1.000`;
- exact/complex topology: `1.000 / 1.000`;
- component/hole heads: `1.000 / 1.000`;
- дзве незалежныя CUDA loss-траекторыі маюць адзін SHA
  `8f532603a715b6761fbddc9c07eaf652e62642e6e9dafc8ec8e481ab2c88a7c5`;
- дзве final weight states маюць адзін SHA
  `28f7a1d90dc6c7eda8ae9d212bfff1798b1ac3923d7d5f03e94580af4f7a91c7`;
- model/data contract SHA:
  `61d786d233ae293424cf82b1f6f0bb23258db9df35ba0862bec7201284425d0c`;
- trainer source SHA:
  `9548320a0c975623bf478364269253fe00b154ff590642e3084100d4e4876d70`.

## Памылкі, знойдзеныя перад/падчас поўнага навучання

1. OCR encoder першапачаткова губляў парадак сімвалаў і бачыў anagram як адзін
   bag-of-characters. Заменена на ordered bidirectional GRU + position embedding.
2. Test threshold першапачаткова калібраваўся на самім test split. Цяпер ўсе
   thresholds выбіраюцца толькі на calibration families і фіксуюцца на test.
3. Outline input і target маглі супярэчыць. Цяпер coverage `>=0.5` строга
   эквівалентны target support.
4. Best `state_dict()` быў live alias і мог непрыкметна стаць апошняй эпохай.
   Цяпер checkpoint snapshot immutable.
5. Held-out evaluator назапашваў поўныя probability maps і мог патрабаваць
   >1 GB RAM. Цяпер evaluation streaming/two-pass.
6. Per-sample TTF reopening і oversized canvases галадалі GPU. Уведзены
   canonical cached font rendering і bounded workers.
7. Topology repair прымяняўся да нізкаўпэўненых выпадковых head predictions.
   Цяпер confidence threshold выбіраецца на calibration split.
8. Runtime inverse projection памылкова ўключаў model margins у content resize,
   што скажала native geometry. Выпраўлена exact content projection.
9. Runtime вылічваў contrast halo, але абразаў яго па старым damaged bbox.
   Знешні штрых фізічна нельга было аднавіць. Цяпер core mapping захаваны
   byte-equivalent, halo праектуецца ў model margins, а native expansion
   абмежавана і паўторна topology/source сертыфікуецца.
10. Whole-line vocabulary праходзіў праз стары per-glyph кантракт. Радкі кшталту
    `A+B`/`co-op` маглі быць у training vocabulary, але не даходзілі да runtime.
    Цяпер glyph і wordmark reachability contracts асобныя і правераныя end-to-end.
11. Traceability мог скласці training proof аднаго checkpoint з Experiment 4
    іншага checkpoint. Цяпер абляцыя абавязкова супадае па exact SHA-256.
12. BUILD_FREEZE патрабаваў прамоўтнуць адхілены per-glyph prior, хаця яго
    downstream-effect gate быў 0/100 і promotion быў немагчымы. Гэта быў
    лагічны deadlock. Цяпер яго адсутнасць замарожваецца як explicit optional
    disabled lane; whole-line checkpoint + manifest застаюцца required.
13. Pre-v14 readiness прымаў толькі стары traceability schema v1, у той час як
    актуальны аўдытар выдае v2. Дададзена fail-closed падтрымка абодвух schema.
14. Promotion manifest захоўваў hashes training/Experiment4/full-regression,
    але runtime не пераправяраў самі evidence-файлы. Цяпер іх падмена або
    выдаленне адключае checkpoint, а ўсе тры справаздачы ўваходзяць у
    BUILD_FREEZE artifact closure.
15. Поўная promotion validation магла паўторна чытаць checkpoint і evidence на
    кожны warm request. Дададзены stat-keyed cache: нязменны build не плаціць
    паўторны multi-megabyte hash, але любая змена evidence інвалідуе cache.
16. Serving vocabulary меў `&@.-_+`, але factory выкарыстоўваў зрэз першых 62
    сімвалаў і ніколі іх не генераваў; whitespace цалкам выкідваўся, таму
    `ACME LAB` і `ACMELAB` мелі адзін condition. Першы full run спынены да
    эпохі 1. Recipe v3 генеруе ўсе 69/69 tokens, уключае two-word targets і
    захоўвае нармалізаваны ordered-space token. Новы full run пачаты толькі
    пасля паўторнага pass preflight.
17. Model/runtime дазвалялі да 32 ordered tokens, але factory абмяжоўваўся 18;
    радкі 19–32 былі serving-only. У v3 target range стаў `3–32`, internal
    space увайшоў у той жа ліміт, а preflight пачаў патрабаваць абодва extremes.
18. CUDA seed не гарантаваў deterministic kernels; жорсткі mode выявіў
    недэтэрмінаваны `AdaptiveMaxPool2d.backward`. Ён заменены эквівалентным
    full-spatial `torch.amax`; два 1500-step runs цяпер bit-identical.
19. Training/evaluation source не ўваходзіў у model/data hash. Цяпер асобны
    trainer SHA звязвае preflight, checkpoint, report і promotion; змена loss,
    calibration ці gate-кода робіць доказ stale.
20. Чатырохэпохавы run захоўваў checkpoint толькі ў канцы. Цяпер пасля кожнай
    эпохі atomic `*_latest.pt` захоўвае цэласны best-so-far snapshot; canonical
    candidate па-ранейшаму з'яўляецца толькі пасля independent held-out test.
21. Whole-line lane памылкова атрымліваў крыніцу, выбраную па per-glyph
    topology contract. Для joined/cursive wordmark гэта магла быць заведама
    горшая маска. Цяпер per-glyph і whole-line lanes незалежныя: glyph lane
    выбірае topology-cell match, wordmark lane — наймацнейшы сертыфікаваны
    physical line і прадказвае ўласную global topology.
22. Optional wordmark inference магла абваліць усю звычайную вектарызацыю пры
    CUDA OOM, malformed row/tensor або памылцы native decode. Цяпер preparation,
    output shape/finite validation, batched forward і кожны per-item decode
    fail-open; няспраўная мадэль толькі
    адхіляе сваю прапанову, а здаровы sibling і deterministic fallback
    захоўваюцца. Гэта праверана асобнымі RuntimeError/per-item regressions.
23. Promotion tool правяраў толькі адзін model-ON Experiment 4 і мог прыняць
    checkpoint без доказу, што ён увогуле змяніў delivered SVG адносна
    model-OFF. Цяпер promotion абавязкова прымае exact model-OFF baseline:
    той жа current compiler, input/font/OCR identities і тыя ж 100 unique loci;
    патрабуе хаця б адзін зменены mask/SVG, не горшы mean IoU, адсутнасць line
    regressions і warm p95 `<200 ms/line`. Baseline report і яго SHA дададзены
    ў runtime manifest/cache і BUILD_FREEZE artifact closure; zero-delta
    promotion асобна праверана як забароненая.
24. Паспяховы preflight быў абавязковы пры запуску trainer, але яго файл не
    ўваходзіў у promotion artifact closure. Цяпер promotion асобна пераправярае
    ўсе 9 v4 checks, bit-identical loss/state hashes, model/data/trainer/font/
    family-split identities і роўнасць data recipe з training report. Сам
    preflight report і SHA замарожваюцца ў runtime manifest і BUILD_FREEZE.
25. Адзін process-global `VICE_WORDMARK_PRIOR_CHECKPOINT` мог уключыць
    непрамоўтнуты checkpoint па-за BUILD_FREEZE. Цяпер env override дзейнічае
    толькі разам з яўным `VICE_WORDMARK_PRIOR_EVALUATION=1`; production default
    без гэтага флага fail-closed, а прамы Path override застаецца толькі для
    ізаляваных probes. End-to-end Experiment 4 tests абноўлены на гэты кантракт.
26. Font manifest быў license/hash-bound, але test suite не даказваў cmap
    coverage whole-line serving vocabulary. Правераны ўсе 241 face з 81 family:
    кожны мае ўсе 69 ASCII/space tokens, памылак адкрыцця і missing glyphs няма.
    Дададзены поўны regression test; састарэлыя лічбы 36/116 у README выпраўлены
    на фактычныя 81/241.
27. v3 лічыў wordmark толькі радок даўжынёй ад 3 сімвалаў. Гэта цалкам выключала
    аднагліфавыя monogram/logo і двухлітарныя HP/GE/VW як з training, так і з
    runtime. Full run спынены да epoch 1. Data contract v4 цяпер роўна `1–32`:
    tokenizer, procedural sampler, OCR corruption, runtime reachability,
    traceability і promotion маюць адзін дыяпазон; асобныя unit/integration
    tests даказваюць `Q` і `HP`. Новы full run забаронены да свежага v4
    bit-identical preflight.
28. v4 preflight называў праверку дыяпазону «fully covered», але фактычна
    правяраў толькі наяўнасць крайніх даўжынь `1` і `32`. Такі gate мог прапусціць
    непрадстаўленыя ў sample даўжыні `2…31`. Цяпер ён патрабуе дакладную роўнасць
    назіранага мноства `{1…32}`; фіксаваны 256-sample seed фактычна пакрывае ўсе
    32 даўжыні, а regression test патрабуе поўнае мноства, не толькі min/max.
29. Адной праверкі tokenizer было недастаткова для сцвярджэння, што кароткі logo
    даходзіць да inference. Дададзены end-to-end regression праз сапраўдныя
    `build_reir -> OCR-bounded physical TextLine -> late whole-line batch` для
    `Q` і `HP`. Абодва фактычна трапляюць у адзін bounded wordmark runtime batch;
    такім чынам ніжнія physical-line gates не адмяняюць новы кантракт `1–32`.
30. Promotion давяраў boolean `serving_*_fully_covered`, але не правяраў самі
    спісы preflight evidence. Цяпер ён fail-closed патрабуе дакладны
    `observed_text_lengths == [1…32]`, дакладны serving alphabet, усе token ids і
    пусты missing set. Асобны regression даказвае, што нават пры пакінутым `true`
    выдаленне адной даўжыні з evidence блакуе promotion.
31. «Адзін сімвал» не заўсёды азначае OCR-літару. Правераны і асобны шлях для
    невядомага аднаэлементнага logomark: ProposalNet/classical threshold
    consensus выдае typed `CustomGlyph`, які канкуруе ў тым жа extractor і не
    патрабуе прыдуманага OCR-тэксту. Тры актуальныя regressions (query,
    countered inverse glyph, solid glyph) прайшлі; `Q/HP` дадаткова пакрываюць
    OCR-conditioned whole-line шлях.
32. `EvidenceCache` быў content-addressed толькі па input/config/schema, але не
    па рэалізацыі REIR. Таму пасля матэматычных выпраўленняў эксперыменты маглі
    ціха загружаць старыя proposal tokens і мераць не той код. Cache fingerprint
    цяпер уключае SHA поўнага лакальнага REIR implementation closure і версіі
    Python/NumPy/OpenCV/Pillow. Regression падмяняе implementation identity і
    даказвае абавязковы miss, пасля чаго паўтор новай версіі дае hit.
33. Менавіта stale REIR схаваў рэальны h16 solid-symbol failure
    `text-043-e6e9f6b20c8c`: справаздача мела `0` line proposals і IoU `0.0083`
    (адзін піксель супраць 120-pixel GT), хоць topology `(1,0)` выглядала
    «правільнай». Свежы REIR захоўвае наймацнейшы з ідэнтычных threshold masks,
    дапускае bounded solid isolated mark як `CustomGlyph` і дае `2` proposals,
    `6` columns, candidate IoU `0.9167` (fresh legacy `0.75`).
34. Experiment 4 раней gate-іў topology/GCR і сярэдняе магло схаваць амаль пусты
    output. Дададзены machine gates: absolute minimum IoU `>=0.25`, bottom-10%
    CVaR не горшы за legacy, candidate mean не горшы за legacy, нуль per-line
    IoU regressions больш за `0.05`. Асобны тэст даказвае, што topology-correct
    one-pixel output цяпер блакуе campaign.
35. Асобны persistent cache у старой scene-first галіне меў падобную рызыку:
    key улічваў input, scales і радок/checkpoint version, але не рэальны код
    preprocessing, deterministic evidence і hybrid routing. Яго key цяпер
    уключае SHA поўнага лакальнага implementation closure і версіі
    Python/NumPy/OpenCV/Pillow; regression даказвае, што змена implementation
    identity абавязкова стварае іншы key. In-memory `FontGlyphCache` не
    перажывае працэс, але раней не адрозніваў REIR math/config пры аднолькавым
    source: key цяпер уключае `reir.config_fingerprint` і exact-font mode, што
    праверана miss/miss/hit regression. `SceneBuildCache` ствараецца асобна на
    адзін малюнак і такой stale-рызыкі не мае.
36. Нават раўнамерныя `1–32` training/test samples маглі быць схаваныя ў
    агульных held-out averages: дрэнная аднагліфавая якасць складала б толькі
    каля 3.1% test. Дададзены асобны hash-bound short-logo audit на unseen font
    families: не менш за 2048 прыкладаў для length `1` і асобна `2`, поўны
    visible serving alphabet у вядучай пазіцыі, exact/substituted/transposed OCR
    hints і per-length gates IoU `>=0.88`, topology `>=0.95`, component/hole
    heads `>=0.90`. Каб і гэта сярэдняе не схавала адну дрэнную літару/лічбу/
    punctuation, трэці streaming pass лічыць bottom-10% IoU CVaR і метрыкі
    кожнага з 68 visible symbols; gates патрабуюць CVaR `>=0.65`, worst-symbol
    mean IoU `>=0.75`, topology `>=0.85`, heads `>=0.75`. Promotion і
    production manifest fail-closed патрабуюць гэты artifact; regression
    даказвае, што IoU `0.20` толькі для length `1` блакуе promotion пры добрых
    агульных метрыках.
37. PCDC `EvidenceCache` рабіў atomic replace, але ўсе concurrent cold requests
    аднаго input/key пісалі ў адзін і той жа `<key>.pkl.tmp`; pickle streams
    маглі перакрыцца, а адзін request мог перанесці/выдаліць temp іншага. Кожны
    writer цяпер атрымлівае ўнікальны temp у тым жа каталогу, flush+`fsync`,
    пасля чаго atomic replace і cleanup. Barrier regression прымушае 4 threads
    адначасова публікаваць адзін cold key, правярае валідны наступны hit, адзін
    final `.pkl` і адсутнасць пакінутых temp-файлаў.
38. Адзін logo-symbol можа фізічна мець некалькі адасобленых частак (`i`, `!`,
    `:` або кастомны знак). Glyph-group query раней правільна знаходзіў увесь
    support, але segmenter называў dot+stem двума glyphs і таму не выпускаў/
    не выбіраў `CustomGlyph`. Цяпер асобны physical certificate патрабуе 2–4
    вузкія вертыкальна сумешчаныя кампаненты, native overlap `>=0.95`, не больш
    за 2% candidate-only і 6% tiny incumbent residue, плюс render margin
    `>=0.05`. Ён выпускае і рэальна выбірае адзін composite `CustomGlyph`;
    side-by-side fragments/літары не атрымліваюць certificate. Абодва выпадкі
    пакрыты regressions.
39. Experiment 1B ужо разлічваў worst semantic-class recall (`class_floor`),
    але забываў уключыць яго ў gate; Experiment 2 таксама паказваў per-class
    acceptable rate, аднак прымаў рашэнне толькі па overall `>=0.98`. У абодвух
    выпадках добры average мог схаваць поўны/вялікі правал аднаго класа. Цяпер
    абодва gates дадаткова патрабуюць `class_floor >=0.95`; negative regressions
    з overall `0.99` і class floor `0.20` абавязкова fail.
40. Experiment 3 меў тую ж average-blindness па сямі adversarial certificate
    pair types: `correct_choice_rate >=0.95` мог схаваць кепскую дыскрымінацыю
    аднаго тыпу. Machine gate цяпер дадаткова патрабуе worst `pair_type_floor
    >=0.90`; negative regression з overall `0.99` і type floor `0.20` fail.
    Experiment 5 ужо выкарыстоўвае `all(...)` па кожным case/probe для limits,
    fallback, timeout/OOM і near-linearity, таму аналагічнага прапуску там няма.
41. Справаздачы эксперыментаў былі прывязаныя да production compiler і native
    runtime, але не да кода самога evaluator/gate. Таму выпраўленне метрыкі або
    парога не абавязкова рабіла старую «зялёную» справаздачу састарэлай. Цяпер
    Experiments 1, 1B, 2, 3, 4, 5, 9, 10 і фінальная Phase-12 кампанія запісваюць
    SHA поўнага лакальнага import-closure evaluator. Traceability, wordmark
    promotion, ProposalNet pre-training readiness/authorization, BUILD_FREEZE і
    фінальны proposal promotion
    fail-closed патрабуюць менавіта актуальны evaluator SHA; model-OFF і model-ON
    справаздачы Experiment 4 таксама павінны мець адзін актуальны evaluator.
    Negative regressions даказваюць, што падмена гэтага SHA блакуе ablation і
    promotion нават пры добрых метрыках і актуальным compiler SHA.
42. «Адзін знак» нельга атаясамліваць з адной літарай або адным connected
    contour. Phase-5 ужо мог сабраць same-ink часткі ў адзін typed whole-shape,
    але production exporter адхіляў такі compound `Shape/free_curve`: fitter
    чакаў фактычна адзін closed spline. Цяпер кожны кампанент фіціцца асобна,
    compound path прымаецца толькі пры дакладнай topology, boundary F `>=0.97`
    і native-lattice IoU `>=0.92`; інакш ён fail-closed. End-to-end regression
    з трохчасткавым адвольным logomark даказвае `MacroKind.SHAPE`, не TextLine,
    topology-identical SVG delivery і рэальна certified `RuntimeMacroCourt`
    без unsupported delivery. Гэта асобны шлях ад length-1 wordmark і ад вузкага
    multi-component `CustomGlyph`.
43. Full-regression report таксама мог састарэць пасля дадання або ўзмацнення
    unit tests без змены production compiler. Цяпер report захоўвае асобны SHA
    runner-а і ўсіх `test*.py`, якія знаходзіць `unittest discover`; wordmark і
    glyph promotion патрабуюць актуальны SHA. Таму новая compound-logomark
    regression і ўсе наступныя тэсты рэальна становяцца promotion gate, а не
    проста неабавязковай праверкай. Падменены regression SHA асобна блакуе
    wordmark promotion.
44. Правераны ранейшы канфлікт Bayesian render LCB з pixel residual і
    color-mass bound. Абодва physical residuals цяпер лічацца пасля той жа
    image-formation hypothesis і з candidate-independent fallback-conditioned
    вагамі `q_F`, што і pairwise Bayes factor. Калі triangle-inequality
    color-mass lower bound кандыдата вышэй за вымераны fallback L1, гэта hard
    dominance: кандыдат адхіляецца яшчэ да exact atlas; паўторная праверка ёсць
    пасля exact render. Асобны adversarial regression даказвае, што robust
    posterior не можа выбраць кандыдат, які добра трапляе ў 93.75% пікселяў,
    але дадае фізічна немагчымую каляровую масу на астатніх.
45. Нават правільны promotion-time evaluator gate не інвалідаваў ужо
    прамоўтнуты wordmark model пасля змены trainer/audit/Experiment-4/test-suite
    кода, калі production compiler bytes не мяняліся. Runtime validation цяпер
    не толькі правярае SHA шасці evidence-файлаў, але і параўноўвае іх унутраныя
    trainer, short-logo audit, model-OFF/model-ON evaluator і full-regression
    identities з жывымі source identities. Regression перападпісвае report SHA
    у manifest, але пакідае састарэлы evaluator: runtime усё роўна fail-closed
    адключае model.
46. Тая ж post-promotion stale-рызыка была ў ProposalNet: candidate-evaluation
    manifest і production sidecar мелі hashes справаздач/checkpoint, але runtime
    не ведаў жывую версію Experiment 9 і Phase-12 evaluator. Authorization і
    promotion цяпер запісваюць абодва evaluator SHA; candidate runtime патрабуе
    актуальны Experiment 9, production runtime — актуальныя Experiment 9 і
    Phase 12. Асобныя negative regressions падмяняюць гэтыя палі пры нязменным
    checkpoint і даказваюць fail-closed.
47. Optional per-glyph prior меў яшчэ слабейшы runtime check: правяраў толькі
    checkpoint/model/compiler палі manifest і не перачытваў тры promotion
    evidence-файлы. Цяпер runtime правярае training, Experiment 4 і full-tests
    file SHA, а таксама жывую актуальнасць Experiment-4 evaluator і ўсяго test
    suite. Regression мяняе full-tests evaluator, абнаўляе яго SHA ў manifest і
    ўсё роўна атрымлівае fail-closed `None` замест загрузкі старой мадэлі.
    Поўная праверка кешуецца па stat identities checkpoint/manifest/evidence:
    два нязменныя runtime выклікі робяць адну validation, а змена evidence
    абавязкова дае cache miss і паўторны fail-closed check.

48. `glyph_prior_source_sha256()` хэшаваў увесь `glyph_prior.py`, таму чыста
    runtime-ахоўная праўка памылкова зрабіла ўжо навучаны checkpoint «састарэлым».
    Кантракт заменены на кананічны AST-хэш толькі навучальнай архітэктуры,
    input/target/degradation data recipe і topology decode. Гістарычны raw-v1
    checkpoint дапускаецца толькі праз яўную migration-сувязь і толькі пакуль
    бягучы semantic-v2 AST мае замацаваны хэш; любая рэальная змена матэматыкі
    аўтаматычна разрывае сумяшчальнасць. Regression правярае як станоўчы
    migration path, так і fail-closed пры падмене semantic anchor.

49. Proposal pre-v14 readiness дадаткова прывязваў glyph-prior training proof да
    поўнага compiler SHA. Гэта паўтарала тую ж памылку ўжо на ўзроўні authorization:
    runtime/evaluator праўка патрабавала дарагога retraining, хоць model/data/decode
    матэматыка не змянілася. Readiness цяпер правярае checkpoint, training report і
    semantic model/data contract; любая runtime-праўка па-ранейшаму абавязкова
    інвалідуе і патрабуе свежыя downstream A/B, full regression і promotion proof.

50. Proposal v13 mixed corpus утрымліваў толькі `typed-generator/v1`: ён меў shape
    owners, але не меў сапраўдных positive/negative supervision для relation heads.
    Таму добры synthetic Recall@5 не даказваў `layer_relation`,
    `symmetry_repeat_group`, `stroke_network`, `appearance_model` і
    `risk_hard_negative`. Створаны `typed-generator/v2` relation corpus на 8000
    hash-bound pairs: па 1000 source prototypes для appearance, layer relation,
    stroke network і repeat/symmetry, з яўным `query-relations/v1` contract.

51. Базавы external raster/vector corpus на 60 190 pairs меў толькі незаверсіянаваны
    `summary.json`: можна было змяніць raster/SVG payload, не змяніўшы replay
    manifest. Дададзены fail-closed external attestation: SHA summary, pairs JSONL,
    кожнага raster/SVG, pair/file counts і generator source. Mixed-corpus builder
    прымае толькі правераны override і паўторна звярае payload identity; tamper
    regression абавязкова блакуе зборку.

52. Real Proposal calibration раней магла стартаваць без доказу, што reviewed
    corpus фізічна змяшчае дастаткова model-facing labels. Новы capacity audit
    аддзяляе Phase-0 sampling bucket ад яўнага `proposal_family`, робіць
    source-group-disjoint split і fail-closed паказвае дакладныя дэфіцыты. Бягучы
    набор мае 300 reviewed loci, але толькі 196 typed rows і нулявую ёмістасць для
    repeat/risk/stroke; сінтэтыка не можа быць падстаўлена замест real calibration.
    Гэта яшчэ не закрыты gate: патрэбна multi-instance real annotation/derivation,
    каб 300 real loci з плана маглі даць усе патрэбныя Proposal query instances.

53. Experiment 9 памылкова лічыў «адзін real locus = адна Proposal family». Гэта
    асабліва няправільна для лагатыпа: адзін знак можа адначасова быць compound
    whole-shape, мець appearance field, repeat/symmetry або layer relation і пры
    гэтым не быць тэкстам. Review contract цяпер backward-compatible падтрымлівае
    некалькі `proposal_instances` з незалежнымі mask/ROI/family на адзін locus;
    усе instances аднаго source застаюцца ў адным leakage-safe split. Для
    relation families дададзены яўны positive/observable `query-relations/v1`
    contract: невядомая relation больш не навучае фальшывы negative. Phase-9
    regressions: 46/46.

54. Папярэдні one-symbol proof даказваў compound whole-shape і асобна length-1
    wordmark, але не даказваў рэальную канкурэнцыю інтэрпрэтацый для аднаго
    неадназначнага знака. Дададзены production regression з A-падобным mark: адзін
    і той жа source support адначасова ўваходзіць як `glyph_group →
    single-custom-glyph` і `whole_shape`; абодва delivery paths падтрымліваюцца
    Runtime Court, пасля чаго text/glyph гіпотэза можа быць законна адхілена
    фізікай, а shape — сертыфікавана. `text_line` без OCR тут не падмяняе
    `glyph_group`: гэта розныя query contracts.

55. Backend multi-instance contract без UI быў бы фармальна існуючым, але
    непрыдатным для рэальнай разметкі. `locus_review` цяпер умее дадаваць,
    пераключаць, абнаўляць і выдаляць асобныя Proposal masks, выбіраць
    positive/observable relation evidence і захоўваць іх разам з нязменным
    Phase-0 root review. Browser add→switch→save smoke на ізаляванай копіі corpus
    захаваў `whole_shape` і `symmetry_repeat_group` з `same_group,repeat`; console
    errors няма, арыгінальны 300-locus `review.json` застаўся byte-for-byte
    нязменным.

56. Proposal filter-cache меў схаваны end-to-end CLI ordering bug: імпарт модуля і
    unit-level `build_filter_cache_from_scan()` працавалі, але `python -m
    vice_compiler.proposal_filter_cache` выклікаў `main()` да аб'яўлення
    `_write_cache`. Таму поўны 75 390-pair preflight пасля дарагога скану падаў з
    `NameError` і не пакідаў cache. Entry point перанесены ў канец модуля; дададзены
    subprocess-рэгрэс, які на сапраўдным PNG/SVG corpus запускае менавіта module CLI
    і патрабуе запісаны v2 cache. Усе чатыры filter-cache tests праходзяць, Ruff
    чысты. Поўны scan завершаны: 75 390 raw, 74 728 accepted, 662 fail-closed
    rejected (400 `unobservable-raster`, 237
    `owner-alignment-below-proof-floor`, 25 `invalid-clean-render-target`);
    cache прывязаны да corpus і filter-semantics SHA.

57. Поўны regression suite выявіў Windows race у content-addressed REIR cache:
    чатыры cold requests аднаго ключа стваралі асобныя temp-файлы, але канкурэнтны
    `os.replace()` часам падаў з `WinError 5`. Publication цяпер мае instance lock,
    правярае валіднага пераможцу з тым жа content/implementation key і робіць
    абмежаваны retry толькі для часовага Windows `PermissionError`; сапсаваны або
    непублікаваны cache не маскіруецца. Дададзены асобны regression для чатырох
    незалежных `EvidenceCache` instances. Абодва concurrency tests вытрымалі 20
    паўторных прагонаў; пасля фікса поўны suite: 463 passed + 273 subtests.

58. Пасля змены REIR былі перазапушчаны, а не перамаркіраваны старыя reports:
    Experiment 1, 1B, 2, 3 і 5 на тым зрэзе прайшлі. Literal plan traceability
    меў роўна тры blockers, усе ў Phase 4: фінальны wordmark checkpoint, fresh
    OFF/ON delivered-output proof і Experiment 4 на тым жа checkpoint. Наступная
    праўка `proposal_data_contract.py` зноў змяніла compiler closure, таму гэтыя
    reports сумленна лічацца stale і павінны быць перазапушчаны перад readiness;
    старыя вынікі не будуць прыняты праз падмену hash.

59. Першы поўны Proposal-v14 head-supervision audit знайшоў 7 998 памылак
    матэрыялізацыі, якіх не бачылі manifest-level праверкі. Прычынай быў auxiliary
    `risk_hard_negative`: PairDataset законна дадаваў гэты target да typed source,
    але relation parser памылкова патрабаваў, каб auxiliary target меў тую ж
    semantic family, што і базавы macro. Цяпер толькі гэты дакладна вызначаны
    auxiliary target вяртае пустое relation supervision; любы іншы family mismatch
    па-ранейшаму падае fail-closed. Дададзены end-to-end regression, які
    матэрыялізуе кожны generated PairDataset row, а аўдытар захоўвае поўныя
    problem/source/split histograms замест першых ста памылак.

60. External corpus attestation v1 прывязваў wrapper, але не сапраўдны generator
    raster/vector payload. Schema v2 цяпер правярае і SHA рэальнага
    `build_raster_vector_pairs.py`, і renderer prefix. Усе 60 190 external pairs
    маюць attested `cairosvg-pillow-png/v1` або
    `cairosvg-pillow-jpeg/v1`; адсутны ці падменены renderer больш не можа
    непрыкметна трапіць у mixed corpus.

61. Раней renderer holdout існаваў толькі як поле ў справаздачы, а не як
    неперасячальная formation pipeline. Structure factory цяпер стварае рэальныя
    WebP roundtrips толькі для hash-split TEST. Пасля новага aligned-target
    fail-closed filter прынята 389: 94 appearance, 103 layer, 82 stroke і 110
    repeat. У TRAIN/CAL WebP няма; PairDataset бачыць іх як codec degradation і
    дае адпаведны risk target. Mixed corpus мае 75 390 raw / 73 368 accepted
    pairs без undeclared renderer.

62. Дададзены асобны `audit_untouched_holdout`, які павінен быць запушчаны да
    існавання v14 checkpoint. Ён не абмяжоўваецца path/split labels: хэшуе input
    і target payload, правярае group, renderer і degradation disjointness, мінімум
    300 held-out rows і мінімум 80 прыкладаў кожнай з чатырох typed families.
    Фактычны current-hash pre-training audit прайшоў на 389 WebP rows:
    group overlap 0,
    duplicate input payload 0, duplicate target payload 0; checkpoint на момант
    sealing не існаваў. Такім чынам копія таго ж растра або SVG пад іншым шляхам
    ужо лічыцца leakage.

63. Кароткі лагатып не можа класіфікавацца толькі па колькасці сімвалаў. Для
    аднаго знака production захоўвае тры розныя гіпотэзы: вядомы glyph,
    `single-custom-glyph` і `whole_shape`/free curve. Два незалежныя regressions
    праходзяць: складаны адзінкавы mark не прымушаецца быць тэкстам, а
    A-падобны амбівалентны mark адначасова даходзіць да text/glyph і shape
    delivery ў Runtime Court. Neural length-1/2 gate застаецца асобным і павінен
    быць правераны на фінальным, а не прамежкавым checkpoint.

64. Другі exhaustive v14 audit скараціў 7 998 materialization errors да аднаго,
    але не быў памылкова прыняты за PASS. Застаўся субпіксельны
    `synthetic-geometry` polygon: у JPEG было пяць назіраемых пікселяў, а
    transformed clean SVG support быў пусты. Filter раней правяраў clean template,
    але не яго фактычны recorded transform; цяпер кожны accepted row абавязаны мець
    непусты aligned target. Той жа аўдыт паказаў, што held-out меў менш за 100
    `mirror`, `gradient_band_explosion` і `stroke_fill_confusion` labels. Парогі
    не паніжаны: mirror formation перабалансаваны і захоўвае адначасова законныя
    `repeat+mirror` tokens, а appearance/stroke/layer атрымліваюць свой semantic
    counterfactual раней за generic rotation. Structural 8k і mixed 75 390
    перабудаваны. Current exhaustive audit цяпер прайшоў на 73 368 accepted
    pairs: `error_count=0`, усе 9 supervision slices ва ўсіх splits, усе 10
    hard-negative classes, усе 8 relation tokens з positive і observed-negative
    supervision, усе 16 parameter dimensions, renderer/origin attestation,
    split disjointness і top-5 mathematical feasibility.

65. Readiness называў існуючы Proposal probe `tiny_multi_instance_overfit`, але
    ён выбіраў толькі 32 text rows з двума/трыма owners і правяраў толькі
    `text_line`. Такі report нічога не даказваў пра glyph, whole/small shape,
    layer, stroke, appearance, repeat і risk heads. Probe цяпер матэрыялізуе
    train-only набор праз сапраўдны PairDataset, патрабуе мінімум 16 instances
    кожнай з дзевяці required slices, выключае rows з матэматычна немагчымым
    global top-5 і прымае толькі адзін joint step, дзе ўсе family Recall@5
    адначасова не ніжэй 0.95, text не ніжэй 0.99 і overall не ніжэй 0.97.
    Стары text-only JSON больш не праходзіць validator.

66. `anti_forgetting_pilot` і `cuda_reproducibility` у readiness раней былі
    толькі чаканымі schema/boolean, без генератара і без binding да мадэлі.
    Дададзены bounded pre-training dynamics audit: дзве незалежныя AMP CUDA
    replicas пачынаюць з таго ж init checkpoint, вучацца на all-head train set і
    правяраюцца на group-disjoint legacy text/glyph/whole/small anchors.
    Anti-forgetting абмяжоўвае family/overall/IoU/loss drift; reproducibility
    патрабуе аднолькавыя loss-trace SHA, final state SHA, metrics і verdict.
    Абодва reports прывязваюцца да checkpoint, filter, label contract, config,
    compiler і evaluator SHA і ніколі не запісваюць checkpoint.

67. Поўны SVG target filter адкрыў не metric regression, а native resource
    leak: PIL image wrappers і in-memory buffers не закрываліся яўна, а resvg
    захоўваў process handles пры тысячах розных SVG. ThreadPool таму разрастаўся
    да 24–27 тысяч handles і не мог быць бяспечным production proof. Усе PIL /
    BytesIO render paths у label, owner, export і posterior кодзе цяпер
    закрываюцца і вяртаюць незалежныя array copies. Поўны filter выконваецца
    канечнымі ProcessPool-хвалямі па 4 workers, таму native state выдаляецца
    пасля кожнай хвалі; Windows worker-respawn deadlock праз
    `max_tasks_per_child` не выкарыстоўваецца. Current run завяршыўся без
    назапашвання handles: 75 390 raw, 73 368 accepted, 2 022 rejected. З іх
    1 548 не прайшлі alignment IoU floor, 400 мелі пусты raster support, 48 —
    owner alignment, 25 — invalid clean render і 1 — empty aligned clean target.
    Парог не паніжаўся. Exact PairDataset dry-run пасля filter матэрыялізаваў
    108 train-only rows і набраў мінімум 16 instances кожнай з дзевяці required
    supervision slices.

68. Full wordmark v4 не мае права быць прамоўтнуты па добрым pixel IoU.
    Epoch 3 на 2M-рецэпце даў calibration `decoded_support_iou=0.91793`, але
    `decoded_topology_accuracy=0.53100` і complex topology `0.48967`. Асобная
    2 048-sample family-disjoint дыягностыка пацвердзіла прычыну: component
    head accuracy `0.7393`, hole head `0.5898`, joint `0.4995`; top-3 адпаведна
    `0.9077/0.8262`, а repair пры calibration-fixed confidence 0.90 закранае
    толькі 10.2% радкоў. Гэта не threshold tuning problem. 65-way global count
    heads і pixel loss недастаткова вучаць дробныя counters/components пад
    OCR corruption. Дадатковы 4 096-row slice audit паказаў, што адна-/двухзнакавыя
    лога не з'яўляюцца крыніцай агульнага правалу: length-1 мае component/hole
    `0.968/0.968` і raw topology `0.942`, length-2 — `0.962/0.934` і raw topology
    `0.925`. Правал канцэнтруецца ў length 17–32: component `0.604`, hole
    `0.417`, joint `0.296`, raw topology `0.323`. Калі observed topology яшчэ
    цэлая, joint head дае `0.870` і raw mask `0.924`; калі degradation яе
    разбурыў, толькі `0.401/0.425`. Значыць v5 патрабуе additive per-glyph count
    prior, complexity-balanced supervision і topology-weighted support loss, а
    не толькі больш эпох. Epoch 3 checkpoint захаваны толькі як diagnostic
    (`59EA36…AE5D`) і заблакаваны. Наступны full run забаронены без
    representative corrupted-OCR/topology pilot, topology-weighted support
    objective і count/decode redesign.

69. Current exhaustive Proposal v14 head audit фактычна прайшоў усе 15 gates,
    але яго schema не запісвае `compiler_source_sha256` і
    `evaluation_source_sha256`. Readiness таму слушна пакідае
    `training_data_and_head_supervision` blocking, нягледзячы на
    `error_count=0`. Hashes нельга дапісваць постфактум: пасля заканчэння
    frozen wordmark run генератар audit будзе bind-нуты да current compiler /
    evaluator source, і ўсе 73 368 accepted rows павінны быць правераны нанова.

70. Першы production-AMP запуск пасля v5 redesign падаў да epoch 1, хоць
    tiny-overfit праходзіў. `_ordinal_count_loss()` выклікаў probability-form
    `binary_cross_entropy` у CUDA autocast, што PyTorch наўмысна забараняе.
    Выпраўленне не замяняе loss іншай алгебрай: арыгінальная FP32 BCE аперацыя
    ізалявана ў `autocast(enabled=False)`. Асобны CUDA FP16 forward/backward
    regression правярае finite loss і gradients. Алгебраічна разгорнуты
    `-y log p -(1-y) log(1-p)` варыянт быў адхілены: ён змяніў rounding,
    tiny-overfit IoU знізіўся да `0.9347`, topology да `0.75`. Канчатковы AMP
    fix пабайтна аднавіў стары loss/state hash.

71. v5 прайшла strict preflight, але bounded 8 192-unique/10-epoch smoke на
    2 048 unseen test font samples не прайшоў: support `0.85189`, decoded
    topology `0.29980`, complex `0.25488`, component/hole/joint heads
    `0.32178/0.16846/0.07861`; length 17–32 topology толькі `0.15696`.
    Repair быў eligible на `2.69%`, таму decoder не з'яўляецца асноўнай
    прычынай. Best fixed threshold самога degraded raster даў `0.20947` exact,
    per-sample threshold oracle — толькі `0.33105`; head+support oracle даў
    толькі `0.34619`. Значыць ні threshold tuning, ні просты fusion не могуць
    закрыць gate, і 131k pilot на гэтай крывой забаронены.

72. v6 праверыла гіпотэзу пра identifiable token/residual decomposition:
    canonical per-token targets і line-effect residual supervision палепшылі
    continuous MAE на 8k з `3.86/7.87` да `2.59/4.23`, але пагоршылі final
    categorical joint `0.0786 → 0.0576` і не палепшылі decoded topology.
    32 768-unique/4-epoch probe таксама застаўся на `0.30200` decoded topology;
    heads `0.33081/0.19458/0.08765`, long topology `0.13836`. Гэта даказвае,
    што brute-force diversity без іншай representation не дае патрэбнай
    learning curve. v6 заблакавана.

73. v7/v8 праверылі spatial component/counter density representation. v7
    detached density head perfect-overfit-іўся, але на unseen fonts collapsed
    да component/hole/joint `0.10986/0.10400/0.00928`; constant-count bias быў
    каля `+8/+9` для length 1–2 і `−3.2` components для length 17–32. v8
    асобны spatial encoder прыбраў gradient interference і хутка прайшоў
    tiny-overfit, але 8k test усё адно даў толькі
    `0.25684/0.12842/0.04395` heads і `0.29932` decoded topology. Абедзве
    гіпотэзы адмоўныя і не маюць права ісці ў 32k/131k/full training.

74. Актыўны v9 кантракт вяртае best-known v5 additive count architecture,
    захоўваючы даказаныя AMP fix і decoder repairs. Decoder цяпер не хавае
    high-confidence bridge за probability-only top-512 shortlist і ўмее
    bounded one-/two-pixel neck cuts; regressions пакрываюць абодва выпадкі.
    v9 300-step smoke прайшоў з support `0.98656` і
    decoded/complex/long/head `1.0`; яго loss trace і final-state SHA пабайтна
    супалі з добрай v5 траекторыяй. Гэта толькі стабілізацыя best-known кода,
    не доказ promotion: representative pilot і full run усё яшчэ забаронены.

75. Прэфлайт v10 (2026-07-24): чатыры рашальныя дыягностыкі закрыты без
    адзінай трэніроўкі — усе на epoch-3 чэкпойнце пад нязменным снапшотам
    v4, held-out сем'і, балансаваныя даўжыні 1–32 (артэфакты ў
    `benchmarks/pcdc_pre_v14/`, жывы пратакол
    `V10_PREFLIGHT_EXPERIMENTS_BY.md`, машынны стан
    `v10_preflight_state.json`).
    (B) Clean-identity: чысты ўваход трымае raw topology 0.9648 агулам і
    0.8965 на len32 супраць 0.2285 на degraded — інверсія дэградацыі
    дамінуе (×3.9); count heads валяцца нават на чыстым уваходзе
    (joint 0.982 → 0.312 па даўжынях), а head-conditioned repair на чыстым
    ШКОДЗІЦЬ (decoded 0.924 < raw 0.965) — свежы негатыў супраць любога
    count head у v10.
    (E) Матрыца 2×3 уваход×OCR: гарантавана няправільны hard transcript
    не каштуе масцы нічога (0.6451 супраць 0.6454) — гіпотэза атручвання
    D4 сфальсіфікавана; але пусты хінт губляе 5.2 пт — транскрыпт
    выкарыстоўваецца толькі як prior даўжыні/чарніла, і v10 explicit
    layout-conditioning абгрунтавана вымярэннем.
    (A/D3) Прамое вымярэнне канваснай столі: пры 7.6–10 ppg нават
    ORACLE-шаблон не супадае з растравай тапалогіяй (exact 0.023–0.055 на
    len 24–32, edit distance 17–20), пры захаваным 35–40 ppg — 0.375–0.398
    і ПЛОСКІ IoU 0.72–0.78. Фіксаваны канвас 64×256 разбурае доўгі радок
    фізічна, да любой мадэлі; dynamic width абавязковы для v10.
    (D) Шаблонны фіт (аналітычны трэкінг з назіранай шырыні + накопныя
    пер-гліфныя зрухі + пер-гліфная шырыня + яўныя аператары
    none/connected/outline) памыляецца толькі лакальнымі ±1 near-miss
    (edit лінейны па L, ~0.31/гліф на растры 64px вышыні), не абвалам;
    лайт-суд без gamma/PSF-пасерыёру губляе 10 пт exact супраць
    GT-oracle — незалежнае пацверджанне неабходнасці fixed-posterior суда.
    Вердыкт нязменны: full v9 run забаронены; наступны крок —
    v9.5 template-warp lane на роднай раздзяляльнасці з вектарнай
    тапалогіяй by construction. Retrieval-скрын (Experiment F: top-8 па
    стылявых дэскрыптарах 241 твару, рэжым unseen-font) лічыцца.

76. Experiment F закрыты (2026-07-24): approximate retrieval замест
    oracle-шрыфта каштуе толькі ~0.11 exact topology і ~0.12 IoU
    (0.5603/0.7684 → 0.4509/0.6459 у openbank k=8), а рэжым unseen-font
    (GT-сям'я выключана з банка, gt-face@8 = 0) практычна роўны openbank
    (0.4330/0.6365) — лінія генералізуецца на шрыфты па-за банкам.
    Монаграмы амаль вырашаны без дакладнага шрыфта (L=1: 0.906–0.938 пры
    40 ppg), і на L=1 union top-8 кандыдатаў абыгрывае адзін oracle-шрыфт
    (0.9375 супраць 0.8750) — разнастайнасць кандыдатнага мноства
    пацверджана. Слабы v0-дэскрыптарны пошук (gt-face@8 = 18%,
    blur-зрушэнне) амаль не ўплывае: вузкае месца пратакола — растравы
    фіт/лайт-суд, не retrieval. Поўны handoff фазы прэфлайту —
    `V10_PREFLIGHT_EXPERIMENTS_BY.md`; далей — вектарная эмісія
    кандыдатаў, Recall@K на вектарным узроўні і Experiment H на 100
    рэальных радках праз існуючы PCDC-суд.

77. v9.5 approximate-template lane пабудавана і ўпершыню змяніла рэальны
    delivered SVG (2026-07-24). Правайдэр
    `vice_compiler/template_warp_provider.py` (пратакол ExactFontProvider):
    стылявое сеянне па банку 241 твару замест pricing-сцяны; top-8 фітаў
    праз прадакшн font_match; provenance `no-font-identity-claim`. Уласны
    маршрут `approximate-template` у `generate_text_macros` з
    доказна-абгрунтаванай сцяной (атрыбуцыйная проба: line.score≥0.94
    забівала 18/18 пры якасці фітаў 13/18; новыя сцены стражэй па
    геаметрыі: IoU 0.50, падлога line.score 0.80). Experiment H на 100
    рэальных лоці: 92 спробы, першы судовы выйгрыш — `text-015` IoU
    0.564→0.614, нуль рэгрэсій; GCR пакуль без зруху (37/44); optional
    p95 3.8 s — бюджэт фітаў наперадзе. Дадаткова закрыты Experiment R:
    вектарны Recall@8 = 0.617 упіраецца ў столь кампазіцыі (truth==сума
    гліфаў толькі 41–54% на доўгіх радках) — pair interactions (§8.11)
    цяпер №1 чаргі v10-мадэлі. Тэсты: text 45/45, experiment4 11/11.
    Усе ранейшыя hash-bound справаздачы лічацца застарэлымі да source
    freeze і rerun'аў (§17 Step 9).

78. Ядро v10 пацверджана канструкцыйна (2026-07-24): вымярэнне
    кандыдатнай тапалогіі на СКАМПАНАВАНАЙ лініі пад яўнымі парнымі
    аператарамі §8.11 (усяго 9 дэтэрмінаваных варыянтаў: трэкінг ±0.10 ×
    shared-stroke 0/2/4, без ніякай трэніроўкі) паднімае vector-level
    Recall@8 з 0.617 да 0.810 агулам (L=1: 1.000, L=4: 0.969, L=8:
    0.885). Столь «сумы гліфаў» прабіта на ўсіх даўжынях. Пазіцыя
    нейроннай часткі v10 удакладнена вымярэннем: прадказваць, якія
    аператары/варыянты прапаноўваць (layout, join, variant, effect), а не
    маляваць пікселі. Рэшта разрыву да гейта 0.99 — шчыльнейшыя/фітаваныя
    варыянты, лепшы пошук, free-form fallback (§8.9). Артэфакт:
    `benchmarks/pcdc_pre_v14/vector_topology_recall_openbank_composed_k8.json`.

79. Першая нейронная кампанента v10 прайшла абмежаваны пілот (2026-07-24,
    §23-клас, адзін прагон, без цюнінгу, гейты запісаны да старту):
    CNN «degraded raster → {stroke, tracking, effect}» з метка-рэплэем
    з самога генератара. Пазітыў: аператары §8.11 чытаюцца — усе тры
    галавы б'юць majority (tracking 0.70/0.45, effect 0.83/0.71,
    stroke 0.51/0.39, held-out сем'і). Негатыў па загадзя запісаным
    stop-condition: top-2 прадказаных варыянтаў губляе 9.2 пт Recall@8
    супраць поўнага 9-варыянтнага перабору (0.696/0.789) — заяўка
    «top-2 дастаткова» адхілена і паркуецца. Пілот нічога не аўтарызуе;
    наступная законная пастаноўка — крывая Recall(top-M) і багацейшы
    ўваход (REIR-каналы). Артэфакт:
    `benchmarks/pcdc_pre_v14/v10_operator_pilot_report.json`.

80. Банк пашыраны да поўнага легальнага рэпазіторыя (§11.2: 2001 сям'я /
    3726 твараў / 3.9 ГБ на запіненай рэвізіі; атэставаны 241-банк не
    кранаецца) — і Experiment G на retrieval-узроўні даў НЕГАТЫЎ:
    крывая unseen-font composed Recall@8 па памеры банка {81, 600, 1987
    сем'яў} ПЛОСКАЯ (0.8006 / 0.7946 / 0.7946). Гіпотэза D5 знешняга
    аўдыту («тысячы сем'яў») для тапалагічнага пошуку сфальсіфікавана:
    класы тапалогіі гліфаў пакрыты малым банкам; звязваючая вось —
    кампазіцыйныя аператары і шчыльнасць варыянтнай сеткі. Пабудаваны
    fail-closed readiness-канвеер v10 (`build_v10_readiness.py`,
    `v10_training_readiness.json`): статус NO-TRAIN, 4/8 гейтаў зялёныя
    (прэфлайт, канструкцыйнае ядро, сігнал пілота, pair-interaction
    spec); адкрытыя — training-side G, curriculum-маніфесты, human
    capacity. Спецыфікацыя аператараў: `V10_PAIR_INTERACTION_SPEC_BY.md`.

81. Readiness v10 дасягнуў 7/8 (2026-07-24, статус NO-TRAIN трымаецца
    правільна): Stage-A curriculum-шард матэрыялізаваны і атэставаны
    (29 695 гліф-запісаў над банкам v2, sha-прывязка), карыстальнік
    задэклараваў рэальную рэв'ю-ёмістасць ~2000 лоці/дзень (запісана ў
    `real_annotation_capacity.json`; бягучая чарга рэв'ю ПУСТАЯ — усе
    300 лоці разгледжаны, пашырэнне чаргі з `v-ice pictures` — наступны
    інжынерны крок). Training-side Experiment G таксама пляскаты
    (0.679/0.671/0.690 пры 81/600/1985 сем'ях) — D5 не звязвае
    аператарную задачу; апошні адкрыты гейт `family_learning_curve`
    чакае Stage-A-зандаж (форма гліфаў). Поўны спіс гейтаў:
    `v10_training_readiness.json`.

82. **READINESS v10: TRAIN (8/8), упершыню** (2026-07-24). Апошні гейт
    закрыў Stage-A зандаж формы гліфаў: joint 0.8410 → 0.8825 → 0.8765
    пры 81/600/1985 сем'ях — крывая расце (+4.2 пт), насычэнне ~600.
    D5-трылогія закрыта: аператары і пошук — пляскатыя (не звязвае),
    форма гліфаў — расце (звязвае). Практычная норма Stage A: банк
    600–1000 сем'яў; далейшая разнастайнасць — у рэндэры/дэградацыі
    (§11.4). TRAIN аўтарызуе старт праграмы v10 (Stage A) пад
    пер-запускавай §4.7-дысцыплінай (tiny overfit → representative
    pilot → full); ён НЕ аўтарызуе ні v9 full run (забарона застаецца),
    ні ProposalNet (уласны NO-TRAIN дзейнічае). Артэфакт:
    `v10_training_readiness.json`; зандажы `stage_a_probe_fam*.json`;
    трэнер `train_v10_stage_a_probe.py`.

83. Дадзеныя v10 замацаваны (2026-07-24, вечар): (а) карыстальнік
    атэставаў supervision 8849 brand/logo-запісаў uber-корпуса
    (bulk-attestation з яўным паходжаннем + 316 жывых UI-адзнак;
    `uber_supervision_attestation.json`); (б) пабудаваны family-disjoint
    спліты §11.3 (`splits/family_disjoint`): тэкст па сем'ях шрыфтоў
    (45 фэйсаў → 21 сям'я), iconify па калекцыях, local цалкам у test —
    train 192,657 / calibration 42,602 / test 43,419; (в) сумленны разрыв
    запісаны: 21 тэкставая сям'я супраць насычэння ~600 у Stage-A
    зандажы — Stage A/B тэкст трэба перагенераваць з банка v2 да
    поўнага запуску. Readiness трымае TRAIN.

84. Stage A v0 — першы сапраўдны v10-трэнінг пад §4.7 (2026-07-24, ноч):
    tiny-overfit 300 крокаў — 1.000 па ўсіх галовах; рэпрэзентатыўны пілот
    (24k, family-disjoint 1367 train / 296 test сем'яў з text_shapes_v2)
    — unseen joint topology 0.8337 пры гейце 0.999: ПІКСЕЛЬНАЯ галава
    гейт не нясе (тая ж столь валасяных каўнтэраў на 64px, што ва ўсіх
    сённяшніх вымярэннях). Высновы замацаваны: гейт Stage A нясе
    retrieval + topology by construction (§8.6), нейронная роля —
    навучаны retrieval-эмбэдынг (vector R@1 ужо 0.927 на монагліфах з
     handcrafted-фічамі; вучоны эмбэдынг — наступны крок Stage A v1).
    Чэкпойнт: models/stage_a_v0_pilot.pt (candidate, нічога не
    аўтарызуе); справаздача stage_a_v0_pilot_report.json.

85. Stage A архітэктурна закрыты трыма пілотамі + фітэр узмоцнены
    (2026-07-24, ноч): v1 (family-softmax retrieval-эмбэдынг) адхілены
    па ўласных лічбах — retrieval-topology top-1 0.807 супраць
    handcrafted 0.927 (стылявая кластэрызацыя не нясе тапалагічную
    форму). Разам з v0 (пікселі, 0.834) вердыкт: на чыстых уваходах
    гейт Stage A (99.9% unseen topology) нясе КАНСТРУКЦЫЯ — тапалогія
    шаблона аналітычная і дакладная па вызначэнні; нейронныя кампаненты
    служаць стыль-пошуку і дэфармацыі і гейцяцца Stage-D метрыкамі.
    Прадакшн-фітэр font_match атрымаў пер-гліфныя накопныя зрухі
    (флаг per_glyph_refine, па змаўчанні выключаны — існуючыя маршруты
    байт-ідэнтычныя; уключае approximate-лінія): смок 0.893→0.933
    score, IoU 0.807→0.879; тэсты text 45/45 + experiment4 11/11.
    Experiment H раунд 2 на 100 рэальных лоці лічыцца.

86. Experiment H раунды 2–3 і Stage-D старт (2026-07-24, ноч).
    H2 (пер-гліфны фітэр): якасць фітаў вырасла, дастаўленыя метрыкі
    без зменаў — вузкае месца пакрыцця на рэальных лоці цяпер
    OCR/якасць масак ліній, не фітэр. H3 (контурны экспарт для
    approximate-радкоў): ВЫМЕРАНАЯ РЭГРЭСІЯ (text-015 GCR 13→21,
    not_worse=False) — маршрут АДКАЧАНЫ па жалезным правіле; урок
    запісаны ў FONT_OUTLINE_ROUTES: контурная дастаўка вернецца толькі
    за пер-радковым рэндэр-судом. Stage-D v0 (інверсія дэградацыі на
    парах uber, рэплэй кампазіцыі .cjs-білдэра, family-disjoint):
    прэфлайт прайшоў пасля трох выпраўленых памылак (alpha-калапс
    transparent-фону, BatchNorm-калапс на малых банках → GroupNorm,
    дывергенцыя lr → cosine; tiny 0.987); пілот-спроба 1 не прабіла
    Otsu (0.596/0.654 IoU пры лепшым topology-edit 3.86/4.34) —
    дыягназ: бюджэт крокаў (~1000 на 16k) быў заніжаны; спроба 2
    з epochs=12 лічыцца.

87. Stage-D v0 ПРЫПАРКАВАНЫ пасля дзвюх сумленных спроб (§21):
    спроба 2 (12 эпох, ~3000 крокаў) дала IoU 0.616 супраць Otsu 0.654 —
    +2 пт ад патраення крокаў, крывая пляскатая. Захаваны пазітыў:
    мадэль у АБЕДЗВЮХ спробах выйграе topology edit distance
    (3.52/3.86 супраць 4.34 baseline) — структура чытаецца лепш за
    классіку нават пры горшых межах. Наступная законная карта (новая
    гіпотэза, не рэтрай): REIR-каналы на ўваходзе замест голага шэрага
    растру + гейт на цяжкім падмностве дэградацый (Otsu блізкі да
    ідэалу на лёгкіх парах і хавае каштоўнасць мадэлі ў агрэгаце) +
    лоссы §12. Артэфакты: stage_d_v0_pilot_report.json,
    stage_d_v0_pilot_attempt2_report.json; чэкпойнты пад candidate-імёнамі.

88. Дзень запячатаны freeze-кандыдатам (2026-07-24, ноч):
    `BUILD_FREEZE_candidate_20260724.json`, freeze_hash 40b81350...,
    complete=false / promotion_ready=false — СУМЛЕННА, бо прапушчанае
    гэта гейтаваная будучыня: непрамоўтнуты wordmark_prior.pt (так і
    трэба), ProposalNet promotion (NO-TRAIN дзейнічае), human-court
    маніфесты (патрэбен новы сляпы раунд). Усе выканальныя пункты плана
    на гэтую дату выкананы да сваіх гейтаў; далейшыя крокі патрабуюць
    або ўдзелу чалавека (суд/рэв'ю), або новых hypothesis-карт пасля
    паркоўкі (Stage-D REIR-уваход), або гейтаваных поўных трэніровак.

89. Re-seal выкананы + Stage-D сям'я механізмаў прыпаркавана з
    data-знаходкай (2026-07-24, глыбокая ноч). (а) Hash-bound пералікі
    Experiments 1/1B/2/3/5 супраць сённяшняга кампілятара: УСЕ
    passed/gate_pass=true; freeze-кандыдат абноўлены
    (4f87908a...), няпоўны толькі па гейтаваных пазіцыях (правільна).
    (б) Stage-D v1 (observation-каналы + цяжкае падмноства) не прабіў
    гейт (IoU 0.6165 супраць Otsu 0.6576) — і выявіў галоўнае: Otsu
    на «цяжкім» падмностве амаль не прасядае, бо дэградацыі
    uber-пар занадта мяккія (blur<=0.9, noise<=5.5, jpeg>=76) супраць
    рэальнага дамена V-ICE. Сям'я «support-над-Otsu на гэтых парах»
    паркуецца; захаваны пазітыў — мадэль стабільна выйграе topology
    edit (3.41-3.86 супраць 4.34) ва ўсіх трох спробах. Наступная
    карта — data-side (§11.4): пары/аўгментацыі wordmark-класа
    жорсткасці, калібраваныя да real-locus размеркавання, і толькі
    потым нейронная інверсія.

90. ПЕРШЫ GATE PASS трэніровачнага механізму v10 (2026-07-24, канец
    ночы): Stage-D v2/v3 — нейронная інверсія пад дэградацыяй
    wordmark-класа над геаметрыяй uber-пар. Незалежны пацвярджальны
    прагон (новы seed 20260730, §16.1-гейт, запісаны ДА запуску):
    topology edit 3.00 супраць Otsu 19.06 (6.35× пры патрабаванні ≥3×),
    IoU 0.734 супраць 0.732 (не горш) — супадае з першым прагонам
    (2.98). Пад брутальнай дэградацыяй класіка шматкуецца тапалагічна,
    мадэль трымае структуру. Дысцыпліна захавана: v2 па сваім
    (памылкова IoU-першым) гейце запісаны як failed; v3-карта
    выраўнавана да іерархіі §16.1 ДА прагону. Гэта адкрывае карту
    поўнага Stage-D запуску (патрэбны яшчэ: крывая па сэмплах,
    preflight-артэфакт, бюджэт) — наступная сесія. Артэфакты:
    stage_d_v2_pilot_report.json, stage_d_v3_confirm_report.json;
    чэкпойнты пад candidate-імёнамі.

91. Recall(top-M) крывая закрыта, мадэль захавана (2026-07-25 ноч):
    top-1 0.6250 / top-2 0.7083 / top-5 0.7708 / top-6 0.7798 пры поўным
    пераборы 0.7887 (той жа дэтэрмінаваны пілот, чэкпойнт
    models/v10_operator_pilot.pt). Вердыкт: аператарная мадэль дае
    каштоўны ПАРАДАК (top-1 = 79% поўнага пакрыцця), але жорсткая
    кампрэсія да 2 варыянтаў страчвае 8 пт — прадакшн-ужытак гэта
    рангавы early-exit пры ацэнцы варыянтаў у судзе, не абрэзка
    кандыдатнага мноства. Паралельна: крывая па сэмплах Stage-D
    манатонная (0.7071/0.7207/0.7345 IoU; 3.46/3.24/3.00 edit) —
    §4.7-перадумовы поўнага запуску сабраны, preflight-карта
    запісана (stage_d_full_run_preflight.json), поўны запуск
    24k×20 эпох ідзе (candidate-чэкпойнт).

92. ПОЎНЫ Stage-D запуск — GATE PASS (2026-07-25, світанак). Першы
    full-scale трэнінг v10 у гісторыі праекта, пад запісаным preflight
    (24k×20 эпох, hard cap 4 гадз): unseen-family IoU 0.7619 супраць
    Otsu 0.7391 (мадэль упершыню выйграе і па пікселях) і topology
    edit 2.59 супраць 19.59 — перавага 7.56× пры гейце ≥3×.
    Маштабаванне жывое (0.7345@16k → 0.7619@24k×20). Чэкпойнт:
    models/stage_d_full_candidate_v1.pt — CANDIDATE: promotion
    патрабуе delivered-output доказу (падключэнне як support-бустар
    approximate-лініі і пералік Experiment H — наступная сесія).
    На гэтым выкананы ЎСЕ пункты плана, фізічна магчымыя без
    удзелу чалавека; чакаюць: сляпы суд (карыстальнік), Stage-D
    у прадакшн-канвееры, промоушн-цыкл.

93. Delivered-output доказ Stage-D кандыдата: НЕГАТЫЎ, promotion
    заблакаваны правільна (2026-07-25, раніца). H5 (бустар жыўцом у
    поўным канвееры на 100 рэальных лоці): дастаўленыя метрыкі
    ідэнтычныя baseline, ранейшы выйгрыш text-015 знік (буставаны
    таргет прайграе суд там, дзе сыры выйграваў), нуль рэгрэсій
    (fail-open зноў чысты), p95 +44ms ад інферэнсу. Дыягназ:
    synthetic→real domain gap — 7.56× перавага на сінтэтыцы не
    пераносіцца на рэальныя лінii. Механізм застаецца candidate з
    флагам off; наступны рух магчымы ТОЛЬКІ праз рэальныя дадзеныя:
    (а) карыстальнікаў рэв'ю-корпус (2k/дзень ужо ідзе) як
    fine-tune/calibration крыніца, (б) сляпы чалавечы суд. На гэтым
    套 план выкананы да апошняга пункта, выканальнага без чалавека:
    кожны правад пабудаваны, кожнае вымярэнне зроблена, апошняе
    вярнула чысты адказ, які рухаецца толькі рэальнымі дадзенымі.

94. Real-фінтюн дуга закрыта поўнасцю (2026-07-25, раніца).
    (а) Фінтюн на 300 чалавечых масках: GATE PASS — held-out рэальны
    IoU 0.790 супраць Otsu 0.425 (+36.5 пт), да-фінтюновы кандыдат
    меў 0.155 (колькаснае пацверджанне domain gap).
    (б) Змешаны фінтюн з 4000 атэставаных карыстальнікам (па яго
    ўказанні; real ×10): 0.766/10.69 — прайграе чыстаму real
    (0.790/9.60) і валіць edit-гейт; сінтэтыка адыграла сваё ў
    pretrain, прадакшн-кандыдат = stage_d_realft_candidate_v1.pt.
    (в) H7 (realft-бустар жыўцом): дастаўка зноў байт-ідэнтычная
    baseline. ДЫЯГНАЗ ДАКЛАДНЫ: канфлікт праводкі — фіт раўняецца на
    ачышчаную падтрымку, а admission-сцены мераюць супраць сырой
    line.support; чым лепшы бустар, тым большы разрыў са сцяной.
    Правільная інтэграцыя — узровень line-proposals/REIR (ачыстка
    ДА сцен), гэта карта наступнай сесіі. Флагі off, рэгрэсій нуль
    ва ўсіх прагонах, promotion правільна заблакаваны да
    delivered-доказу на новай праводцы.

95. Пытанне маштабу сінтэтыкі ў real-фінтюне закрыта манатоннай
    крывой (2026-07-25): real-only 0.790/9.60 (PASS) → +4000
    атэставаных 0.766/10.69 (fail) → +8849 0.740/10.77 (fail) —
    строга ўніз з ростам сінтэтычнай долі. 70k-мікс НЕ запускаецца
    (правіла падаючай крывой); карыстальнікавы 8849-набор адыграў
    сваю ролю ў pretrain (стартавы чэкпойнт фінтюна — сінтэтычны
    full-run), а рэальны гейт корміцца рэальнымі масками. Пашырэнне
    verify-корпуса да ўсіх iconify (~70k) працягваецца як актыў
    чаргі/будучых pretrain. Прадакшн-кандыдат нязменны:
    stage_d_realft_candidate_v1.pt.

96. Палярнасны механізм пацверджаны лічбай, але мікс у фінтюне
    зачынены дзвюма спробамі (2026-07-25): у старым міксе сінтэтыка
    ішла ink-high, рэальныя радкі — люмінанс (процілеглая палярнасць
    у адным банку). Фікс --mix-polarity luminance (псеўда-люмінанс
    ink_lum*obs+0.5*(1-obs) з рэальнай яркасцю чарніла іконкі)
    вярнуў edit 10.69→9.95 і IoU 0.766→0.772 на mix-4000 — механізм
    рэальны, АЛЕ real-only (0.790/9.60) застаецца наперадзе. Дзве
    спробы з механізмам паміж імі → мікс у фінтюн-стадыю больш не
    пераспрабоўваецца. Новы рычаг маштабу — PRETRAIN: pre-finetune
    0.155 даказвае, што цяперашні ink-канвенцыйны претрэйн амаль не
    пераносіцца ў рэальны дамен; luminance-кансістэнтны претрэйн
    24k×20 з аўта-ланцугом у real-фінтюн запушчаны (--polarity
    luminance у train_v10_stage_d.py). Лесвіца карыстальніка: калі
    дасць прырост над 0.790 → 70k → увесь uber (557k пар).

97. Luminance-претрэйн — прарыў маштабнай лесвіцы; H8 — першы жывы
    стрэл лэйна і тапалагічны гард (2026-07-25 вечар). (а) Претрэйн
    24k×20 у luminance-канвенцыі (--polarity luminance, псеўда-люмінанс
    з рэальнай яркасцю чарніла пары) прайшоў свой гейт І ў ланцугу
    real-фінтюна пабіў real-only па АБОДВУХ метрыках: IoU 0.8185
    (было 0.790), edit 8.90 (было 9.60), pre-finetune 0.155→0.419 —
    канвенцыя і была галоўнай дзіркай пераносу. Прыступка «70k і
    болей» адкрыта: запушчаны претрэйн на ЎСІХ 83,454 прыдатных парах
    (size=96, rotate=0) з аўта-ланцугом у фінтюн; стоп-умова — не
    паб'е 0.8185/8.90 → 557k не адкрываецца. (б) H8 (upstream-лэйн
    жыўцом): мадэль УПЕРШЫНЮ сама змяніла дастаўлены вынік —
    text-015 +0.05 IoU, але тапалогія [34,5]→[25,3] пры эталоне
    [38,6], GCR 13→20: пікcельны суд сляпы да злітых гліфаў (§16.1).
    Урок замацаваны канструкцыйна: _body_topology_signature-гард у
    _stage_d_support_refinements (дрэйф цельных кампанентаў ≤
    max(1,10%), контуры ≤1; спекі чысціць можна). H8b (гард, стары
    чэкпойнт; чаканне: тоесна бэйзлайну) і H8c (гард + lum-чэкпойнт
    0.8185) у палёце. Fine-tune-мікс застаецца зачыненым (ledger 96).

98. H8-арка закрыта поўнай праўдай; маштабная лесвіца спынена на 24k
    (2026-07-25 ноч). (а) ПАПРАЎКА запісу 94: «H7 delivered identical»
    быў няправільны — raw-size бустэр у fit-target МОЎЧКІ ЗАБІВАЎ
    text-015 win (v8: template прайграў суд, [34,5], mean −0.0005 да
    v6). (б) H8b == v6 на 100/100 радках (дайджэсты байт-у-байт):
    тапалагічны гард верыфікаваны, [25,3]/GCR13 — гэта законны
    v6-win, а не рэгрэсія; H8-рэкавэры (без гарда) даваў тую ж
    сігнатуру з горшымі гліфамі (GCR 20) — гард рэжа справядліва
    (зонд: 10 камп.→1, дрэйф 9). H8c (lum-чэкпойнт) тоесны — upstream
    -лэйн жывы, fail-closed, пакуль no-op на гэтым корпусе; прычына —
    мадэль вучаная на квадратных іконках, доўгі тонкі радок пасля
    letterbox фузіцца (картка: line-shaped crops). Кэш-аўдыт: у
    exp4 кэшуецца ТОЛЬКІ REIR (ключ без Stage-D — карэктна, бо
    Stage-D дзейнічае пасля), але справаздача НЕ біндзіць Stage-D
    чэкпойнт-хэш — дзірка правенансу, картка на фікс. (в) Сід-матрыца
    2×3: lum-24k edit 8.90/8.89/9.24 vs lum-80k 9.16/9.27/9.66
    (адзін гейт-fail) — 24k выйграе галоўную метрыку 3/3 пры
    нязначнай IoU-перавазе 80k; стоп-умова прыступкі спрацавала:
    557k ЗАЧЫНЕНА (прадстаўленне перад маштабам, §11.1). Кандыдат:
    stage_d_realft_from_lum.pt (дэфолтны сід, без адбору па val).

99. Аўдыт якасці датасэта (5-агентны, 2026-07-25 ноч) — банк здаровы
    структурна, хворы размеркаваннем; фонавая канвенцыя ўсё яшчэ
    хлусіла. Факты: (а) супервізія пар НЕ атручана (replay-фэйлаў
    0/800, зрушэнні p90 2.4px); рэальныя дэфекты малыя: ~3% clean —
    «нябачнае чарніла» (fill≈фон у grayscale, вучыць галюцынаваць),
    рэдкі displaced-support клас (off-center viewBox). (б) Тыпавы
    склад трэйна: 52% synthetic-text (УСЕ з v1 = 21 сям'я!), 30%
    iconify, 18% geometry, 0% рэальных лога (усе 313 у test па
    family-disjoint — сумленна). Разрывы супраць рэальнага дамену:
    дзіркавы дэфіцыт 4.3× (holes≥4: 8.7% vs 37.7%), звышшырокіх
    2.8× зашмат (aspect>5: 31.6% vs 11.3%). (в) Спліты чыстыя:
    0 exact cross-split, 11 near-dup24 — пераважна icon-аліасы.
    (г) ГАЛОЎНАЕ: рэальны фон амаль белы (31.1% пікс >0.98 vs 0.5%
    у сінтэтыцы), рэальнае чарніла медыяна 0.462 — УНУТРЫ майго
    skip-акна |ink-0.5|<0.08: плоскі 0.5-фон і не вучыў ink-on-white,
    і выкідаў 18% радкоў памылкова. (д) text_shapes_v2 (150k, 1957
    сем'яў) у банку НЯМА — рэзерв. Умяшанне (флагі, старыя рэжымы
    некранутыя): --polarity luminance-bg (фон = медыяна бартоў САМОЙ
    пары; скіп — сапраўдная нябачнасць |ink-bg|<0.12, закрывае і
    дэфект (а)) і --balance real-profile (квоты: wide≤12%,
    plain≤15%, hole-rich заўсёды). Два ланцугі 24k→realft у палёце
    (bg-фікс асобна / bg+баланс асобна); мэта — пабіць 0.8185/8.90;
    стоп — дзве спробы механізму.

100. Фонавы фікс — пацверджаны чэмпіён; рэбаланс запаркаваны; v2-
    кампазіцыйная прыступка ў палёце (2026-07-25 позняя ноч).
    Сід-матрыца lumbg: 0.8293/8.05, 0.8294/8.07, 0.8289/8.15 —
    б'е flat-0.5 (0.8185-0.8217 / 8.89-9.24) 3/3 па АБЕДЗВЮХ
    метрыках, разбег мізэрны. НОВЫ Stage-D кандыдат:
    stage_d_realft_from_lumbg.pt (pretrain stage_d_lumbg_v1.pt).
    Pre-finetune 0.477 — сінтэтыка ўпершыню б'е Otsu (0.425) на
    рэале без адзінай рэальнай маскі. Рэбаланс real-profile
    (0.8238/8.29) прайграў bg-фіксу сам-насам — 1-я спроба
    выкарыстана, паркінг (другая — толькі з іншым механізмам
    квот). Наступная прыступка запушчана: --mix-text-v2 —
    18k пар + 6k радкоў text_shapes_v2 (пакрыццё сем'яў 21→1957
    пры нязменным аб'ёме 24k; ink/bg сэмплююцца з замеранага
    рэальнага размеркавання, кантраст ≥0.12, family-disjoint праз
    v2 train_ids). Промоўшн па-ранейшаму заблакаваны: дастаўленага
    win у Stage-D няма (H9 з новым чэкпойнтам — пасля v2-прыступкі).

101. ПЕРШЫ ДАСТАЎЛЕНЫ WIN Stage-D (H9) і закрыццё v2-дамешкі
    (2026-07-26 світанак). (а) v2-мікс закрыты дзвюма механізм-
    абгрунтаванымі спробамі: 25% → 0.8342/8.32, 10% → 0.8343/8.26 —
    абедзве ставяць IoU-рэкорд і абедзве прайграюць чэмпіёну па
    edit (8.05–8.15); заканамернасць: разнастайнасць сем'яў купляе
    пікселі, плаціць тапалогіяй. Парк з зафіксаваным механізмам.
    (б) H9 (exp4, upstream-лэйн, чэмпіён stage_d_realft_from_lumbg):
    supраць v6 змяніўся РОЎНА адзін радок — text-006: GCR 8→6,
    IoU +0.009, тапалогія 53→44 камп. (эталон 38), дзіркі 4→5
    (эталон 6); 100/100 not_worse, нуль рэгрэсій. Механізм чысты:
    рэкавэры-support нарадзіў новую лінію, яна прайшла фізічныя
    гейты і тапалагічны гард, яе font-free-dual-loop матэрыялізацыя
    выйграла суд. Гэта model-ON/model-OFF delivered-доказ (n=1 win,
    0 рэгрэсій). Дэфолтны чэкпойнт лэйна абноўлены на чэмпіёна
    (лэйн застаецца env-гейтаваным VICE_STAGE_D_UPSTREAM). Статус:
    кандыдат; промоўшн-гейт не пройдзены (патрэбны frozen campaign
    + human court). Наступны рычаг дастаўкі: line-shaped кропы —
    фузія доўгіх радкоў (text-015) па-ранейшаму рэжацца гардам.

102. Line-канвас арка: інфраструктура гатова, флор пакуль не ўзяты,
    вырашае H10 (2026-07-25/26). Трэнер/фінтюн/бустэр параметрызаваны
    канвасам (квадратны шлях байт-той-жа); line-претрэйн 12k @96×384
    прайшоў свой гейт (0.9194/1.40 vs Otsu 0.9061/4.59). Тры фінтюн-
    прагоны на рэале: агульны гейт 0.8859/9.21 - fail (гейт быў
    мíс-спецыфікаваны: 62 val-радкі ўсіх аспектаў для мадэлі, што
    дэплоіцца толькі на aspect>2.5); спецыялісцкі (aspect≥2, §16.2)
    0.8495/12.77 - fail; пасля рамонту імплементацыйнага дэфекту
    (INTER_AREA на ўпскейле = блочны nearest, якога сінтэтыка не
    ўтрымлівае; цяпер cubic-on-upscale, у інферэнсе прывязана да
    канваса чэкпойнта) 0.8452/10.81 і фармальны gate_pass - але ён
    ВАКУУМНЫ (§11.5): кубічны letterbox абрушыў Otsu-бэйзлайн да
    edit 116; супраць асэнсаванага бэйзлайна (9.38) флор не ўзяты.
    IoU-перавага стабільная (+38-43pt над Otsu на радках). Чэкпойнт
    пакінуты пад яўным імем stage_d_line_realft_cubic.pt (не
    candidate); gate-фэйлавы агульны перайменаваны ў
    *_rejected_generalgate.pt, каб fail-closed лэйн яго не падхапіў.
    H10 (aspect-роўтынг: радкі → line-мадэль праз яўны env, іншае →
    квадратны чэмпіён; гард+суд вырашаюць) у палёце. Правенанс-дзірка
    закрыта: exp4 біндзіць stage_d_identity (sha256 абодвух
    чэкпойнтаў + флаг лэйна).

103. H10/H11: палітыка «другога шанцу» замацавана дастаўленым доказам
    (2026-07-26 раніца). H10 (эксклюзіўны роўтынг wide→line) АДНЯЎ
    H9-win на text-006 (line-рэкавэры зрэзаў гард → адкат у legacy,
    GCR 6→8) пры новым win text-045 (+0.011 IoU ад line-мадэлі) —
    нета мінус па §16.1; эксклюзіўны роўтынг = лесвічны fallback,
    забаронены Часткай I. H11 (wide ROI прапануе АБЕДЗВЕ рэкавэры,
    гард фільтруе кожную, суд выбірае): text-006 win вярнуўся +
    text-045 win застаўся, 100/100 not_worse, mean IoU
    0.773795 — найлепшы дастаўлены стан (v6 0.773592 → H9 0.773685
    → H11 0.773795). Line-чэкпойнт застаецца пад яўным env (не
    candidate: трэніровачны флор не ўзяты, ledger 102), але мае
    ПЕРШЫ дастаўлены ўклад — гард+суд арбітруюць пер-кейс, як і
    задумана. Фінальная канфігурацыя дня: upstream-лэйн env-гейт,
    square-дэфолт = stage_d_realft_from_lumbg.pt, line праз
    VICE_STAGE_D_LINE_CHECKPOINT. Дастаўлены рахунак сесіі: 2 win
    (text-006 GCR 8→6, text-045 IoU +0.011), 0 рэгрэсій.

104. Line-флор запаркаваны канчаткова чатырма лічбамі; court-пакет
    для чалавечага суда гатовы (2026-07-26). (а) Флор edit≤9.385
    (сумленны AREA-Otsu) не ўзяты ніводным механізмам: pairs-AREA
    12.77, pairs-cubic 10.81 (лепшы; па дарозе адрамантаваны рэальны
    дэфект INTER_AREA-упскейлу), v2-primary 12.04, topology-weighted
    loss 14.81 (перагнуў — фрагментацыя). Стоп напісаны загадзя —
    спрацаваў; далей line-мадэль працуе толькі пер-кейс праз
    гард+суд (яе text-045 win у дастаўцы застаецца). Рэадкрыццё —
    толькі з новым прадстаўленнем (не новым порогам/лосам). (б) H12:
    outline-суд жывы, 0 паставак, 0 дрэйфу — H3-клас рэгрэсій
    канструкцыйна немагчымы. (в) Сляпы court-пакет v2 пабудаваны
    пад фінальным H11≡H12 станам: 100 кейсаў, 100/100 поўных
    дайджэстаў, review-шкілет 0/100; чакае карыстальніка
    (web_preview/server.py, court=exact; гейт: ≥100 адказаў,
    preference_rate ≥ 0.75). Промоўшн: machine-гейт усё яшчэ
    чырвоны (pixel_fidelity), чалавечы гейт адкрыты да суда —
    статус «кандыдат», перамогі не заяўляюцца.

105. ПЕРШЫ digest-валідны чалавечы суд textline-дастаўкі: гейт НЕ
    пройдзены — і гэта галоўны навігацыйны факт (2026-07-26).
    Карыстальнік адсудзіў 100/100 сляпых пар (усе адказы нясуць
    поўны digest-кантракт): 58 нічыіх, 23 legacy, 19 кандыдат —
    preference 45.2% пры гейце ≥75%. Па §3 чалавечы суд б'е
    агрэгатныя метрыкі: промоўшн заблакаваны канчаткова. Тры
    перцэптыўныя класы правалу з нататак (14 шт.): (I) «А
    пікcельнае, Б крывое» — ідэалізацыя хістка крывіць лініі
    (шлях single-custom-glyph = 13/23 legacy-перамог); на гэтых жа
    радках кандыдат меў ВЫШЭЙШУЮ IoU (+0.088 у сярэднім) — жалезны
    доказ сляпой плямы пікcельнага суда: вока судзіць ГЛАДКАСЦЬ і
    раўнасць ліній, не пікселі; (II) згубленыя колеры/дэталі
    (градыенты, другасныя пласты) — прычына 58 нічыіх «абодва
    дрэнныя»; (III) фузія рамкі (text-085 «усё злілося»).
    Наступныя карткі якасці — з ГЭТАГА суда, не з машынных
    метрык: (1) гладкасць/вернасць крывых у font-free
    матэрыялізацыі (G1/дугі замест хісткіх ламаных) з
    перцэптыўным гейтам; (2) захаванне каляровых пластоў і
    дэталяў; (3) анты-фузія рамак. H13 (валідацыйны прагон,
    біндзінг раўнда ў справаздачу) у палёце. Машынны
    pixel_fidelity-гейт разабраны асобна: трымаюць 5 радкоў, у 4
    кандыдат==legacy пабайтава (агульны стары правал
    evidence-слоя), пяты кандыдат лепшы за legacy але ніжэй
    абсалютнага флору — гейт адчыніцца рамонтам лоцы, не цюнінгам.

## Дакладны promotion gate для full checkpoint

Checkpoint не можа стаць `models/wordmark_prior.pt`, пакуль адначасова не
выканана:

- `decoded_support_iou >= 0.88`;
- `decoded_topology_accuracy >= 0.95`;
- `decoded_complex_topology_accuracy >= 0.90`;
- component head accuracy `>= 0.90`;
- hole head accuracy `>= 0.90`;
- 2 000 000 unique training variants з даўжынёй `1–32`;
- 20 000 calibration + 20 000 unseen test samples на disjoint font families;
- асобныя unseen length-1 і length-2 зрэзы па `>=2048` праходзяць short-logo
  IoU/topology/head gates;
- свежы Experiment 4 мае той жа checkpoint SHA;
- мадэль змяняе хаця б адзін delivered mask/SVG;
- няма line topology regressions і mean IoU не горшы за model-OFF;
- warm p95 `<200 ms/line` у Experiment 4;
- machine і blind human gates праходзяць;
- current full unittest/native-runtime proof праходзіць;
- promotion manifest прывязаны да checkpoint, model/data contract і compiler
  source SHA.

## Што яшчэ не даказана

- Поўная 2M training/test справаздача яшчэ не скончана.
- Няма свежага current-hash Experiment 4 OFF/ON для full checkpoint.
- Няма новага blind human review для фактычна змененых SVG.
- Не створаны новы complete BUILD_FREEZE.
- Phase 12 (VAI50 50/50 + Challenge115 115/115 + locked blind VAI court) не
  запушчана на гэтым build.
- Таму сцвярджаць «лепей за VAI» зараз нельга.

## Бягучая праверка кода

На гэтым зрэзе прайшлі:

- wordmark model/data/trainer tests: 18/18;
- wordmark runtime: 11/11;
- wordmark integration/reachability: 4/4;
- checkpoint promotion tests: 1/1;
- Experiment 4 binding/semantic tests: 10/10;
- traceability SHA-binding tests: 2/2;
- fixed-posterior/digital-circle court: 12/12;
- Phase 5–8: 30/30;
- Phase 9: 46/46;
- Phase 11 targeted freeze verification: passed.
- current hash-bound Python regression: 367/367.

Поўны regression suite і ўсе runtime timing gates трэба паўтарыць пасля
завяршэння GPU training, каб CPU worker contention не сказіў p95.

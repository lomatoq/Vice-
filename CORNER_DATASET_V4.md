# Corner dataset V4: perceptual events

Preview: `http://localhost:8877/corner-dataset-v4/`

Dataset: `datasets/corner_gt_v4_perceptual_events/`.

## Што азначаюць кропкі

- `point event`: звычайны геаметрычны C0-вугал — адна чырвоная вяршыня.
- `short-span event`: адзін візуальны вугал трапіў у прамую піксельную
  пляцоўку да 2 px — чырвонымі пазначаюцца абодва канцы. Яны маюць адзін
  `event_id`; гэта не два незалежныя вуглы і не гатовая дуга.
- `occlusion event`: новы бачны вугал ад перакрыцця — фіялетавая кропка.
- На гладкай крывой, скругленні і звычайнай raster-лесвічцы падзей няма.

У review UI `events` — колькасць сэнсавых кутоў, `labels` — колькасць
навучальных vertex-labels. Жоўты адрэзак злучае гатовую span-пару.

## Як правіць

1. Для аднаго выразнага кута выбраць `+ structural` і націснуць на вяршыню.
2. Калі кут візуальна ляжыць пасярэдзіне кароткай пляцоўкі, выбраць
   `+ short span` і націснуць на пляцоўку. UI паставіць два канцы адным
   history-action; `Ctrl+Z` прыбярэ абодва разам.
3. Каб прыбраць памылку, выбраць `remove event / brush`: адзін клік выдаляе
   ўсю point/span/occlusion-падзею, а заціснутая мыш працуе як гумка. Увесь
   мазок з'яўляецца адным history-action.
4. `clear` каля канкрэтнага памеру прыбірае ўсе яго меткі, не закранаючы
   астатнія resolution; адзін `Ctrl+Z` цалкам вяртае гэты view.
5. На дугах, колах, эліпсах, скругленнях і лесвічцы нічога не ставіць.
6. Для кута, створанага аклюзіяй, выкарыстоўваць `+ occlusion`.

Кнопка `raw` адкрывае вялікі 720px bitmap-рэдактар. Яго лакальная панэль
`+ corner / + short span / + occlusion / remove event / brush` змяняе той жа
resolution і тую ж history, што і маленькі canvas; справа застаецца чысты raw
ў фактычным памеры для кантролю.

## Фармат shard

Акрамя `points`, `labels` і `offsets`, кожны NPZ мае:

- `event_ids: int32` — loop-local id або `-1` для negative vertex;
- `event_kinds: uint8` — `0 none`, `1 point`, `2 short_span`, `3 occlusion`.

Vertex-classifier можа па-ранейшаму навучацца на `labels`. Геаметрычны decoder
павінен спачатку згрупаваць вынік па `event_ids`; для `short_span` пачатковая
пазіцыя латэнтнага кута — сярэдзіна паміж двума endpoints, пасля чаго fitter
параўноўвае sharp join, кароткую дугу і G1-працяг паводле render/perceptual loss.

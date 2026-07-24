# Frozen Challenge-115 result

Freeze: `33bc0d63e4b82734bcb5349f5d19385ac16b0fbdc6e31074814728c90238758f`

Every item was attempted under the same 30-second worker budget. A timeout is
an accounted failure, not an omitted row.

## Coverage and resources

| Slice | Completed | Timeout |
|---|---:|---:|
| small text | 17 | 9 |
| logos | 0 | 20 |
| UI icons | 1 | 11 |
| gradients | 0 | 13 |
| transparency | 0 | 4 |
| dirty JPEG | 0 | 10 |
| diagrams | 9 | 21 |
| **total** | **27** | **88** |

The promotion gate is `FAIL`. In particular, there is no completed evidence at
all for four entire slices (logos, gradients, transparency and dirty JPEG).

## Equal-input quality on the 27 completed pairs

- Ink IoU: V-ICE wins `0/27`; median `0.8985` versus VAI `0.9903`.
- SSIM: V-ICE wins `0/27`; median `0.8756` versus VAI `0.9931`.
- Catastrophic-locus rate: V-ICE wins `0` with `11` ties; median `0.0169`
  versus VAI `0.0`.
- Small text: IoU median `0.8220` versus `0.9844`; SSIM `0.8131` versus
  `0.9867`.
- Diagrams: IoU median `0.9737` versus `0.9955`; SSIM `0.9593` versus
  `0.9970`.
- The only completed UI-icon case had IoU `0.9185` versus `0.9928` and a
  catastrophic-locus rate `0.2382` versus `0.0`.

Smoothness wins on simplified/missing output are not promotion evidence. The
fidelity, topology, local-catastrophe and resource gates take precedence.

## OCR audit

The previously dead OCR metric found source text in only one of the 17 completed
small-text crops. On that one comparable crop, V-ICE OCR loss was `0.6` and VAI
loss was `0.0`. Sixteen crops were below the OCR engine's detection floor.

Therefore OCR must be part of the real gate, but it cannot stand alone for tiny
text. Component/counter persistence, stem and baseline consistency, glyph
occupancy, and worst-window damage are mandatory even when OCR returns no line.

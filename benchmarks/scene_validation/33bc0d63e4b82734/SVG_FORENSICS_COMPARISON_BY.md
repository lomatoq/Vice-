# Scene versus Vectorizer.AI SVG structural forensics

Freeze: `33bc0d63e4b82734bcb5349f5d19385ac16b0fbdc6e31074814728c90238758f`

This is an observable-output comparison, not a claim about Vectorizer.AI's
private implementation.  Scene statistics use only the 30 completed
`03_rebuilt_filled.svg` files.  Primitive/debug maps are excluded.  VAI
statistics use the 131 supplied VAI SVG files.

| Observable | Scene finals (30) | VAI outputs (131) |
|---|---:|---:|
| Median graphics/file | 71 | 18 |
| Mean graphics/file | 168.3 | 59.5 |
| Maximum graphics/file | 841 | 2050 |
| Files with compound filled paths | 27 | 125 |
| Native parametric SVG elements, total | 201 | 135 |
| Files with likely gap-filler strokes | 25 | 13 |
| Files with groups | 30 | 13 |
| `L` commands, total | 46,849 | 19,399 |
| `C` commands, total | 744 | 36,288 |
| `Q` commands, total | 122 | 28,038 |
| `A` commands, total | 655 | 12,294 |

The populations have different sizes, so raw command totals are deliberately
not treated as a direct quality score.  They nevertheless show a very large
representation difference: even with only 30 files, Scene emits more than
twice as many line commands as the 131-file VAI corpus, while VAI relies heavily
on cubic, quadratic, and arc geometry.  Scene also uses likely gap-filler
strokes in 25/30 completed outputs versus 13/131 VAI outputs.

The supported engineering conclusion is that the frozen Scene build carries
early raster/colour fragmentation into its final representation and repairs it
with many line segments and gap fillers.  The VAI outputs are consistent with
earlier whole-object/text/curve inference followed by compound-path
serialization.  That conclusion agrees with the fidelity, topology,
editability, and runtime failures in the frozen VAI50 campaign.

Source artifacts:

- `svg_forensics_scene_finals.json` / `.md`
- `svg_forensics_vai_only.json` / `.md`


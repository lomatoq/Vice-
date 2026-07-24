# SVG structural forensics report

> Heuristics are deliberately conservative. A structural pattern is evidence about an export, not proof of the proprietary internal implementation.

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\betsoft_512\5_betsoft_512_src\03_rebuilt_filled.svg`

- SHA-256: `6148e121b852291066266d5328aa746de3de1df2f1992b11a0f7f14f00442e3c`
- Bytes: 118255
- Root size: `512` × `256`; viewBox `0 0 512 256`
- Graphics: 199; groups: 9; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 3
- Clip/mask references or definitions: 0
- Transformed elements: 1
- Coordinate precision: `{"count": 9198, "min": 0, "median": 6.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 195,
  "stop": 36,
  "linearGradient": 17,
  "g": 9,
  "circle": 3,
  "svg": 1,
  "defs": 1,
  "radialGradient": 1,
  "rect": 1
}
```

### Path commands

```json
{
  "L": 3924,
  "M": 453,
  "Z": 362,
  "C": 34,
  "A": 25,
  "Q": 10
}
```

### Native parameterized elements

```json
{
  "circle": 3,
  "rect": 1
}
```

### Fill-rule counts

```json
{
  "evenodd": 104,
  "default/nonzero": 95
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fee95c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 187,
    "tag": "path",
    "id": "shape-132",
    "groups": [
      "g@1"
    ],
    "fill": "#fef080",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 188,
    "tag": "path",
    "id": "shape-133",
    "groups": [
      "g@1"
    ],
    "fill": "#fef080",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 189,
    "tag": "path",
    "id": "shape-residual-134",
    "groups": [
      "g@1"
    ],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 257,
    "commands": {
      "M": 257,
      "L": 3163,
      "Z": 257
    },
    "transform": null
  },
  {
    "index": 190,
    "tag": "path",
    "id": "shape-16",
    "groups": [
      "g@2"
    ],
    "fill": "#fef080",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 191,
    "tag": "path",
    "id": "shape-17",
    "groups": [
      "g@3"
    ],
    "fill": "url(#gradient-appearance-shape-17)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 192,
    "tag": "path",
    "id": "shape-18",
    "groups": [
      "g@4"
    ],
    "fill": "url(#gradient-appearance-shape-18)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 10,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 193,
    "tag": "path",
    "id": "shape-19",
    "groups": [
      "g@5"
    ],
    "fill": "url(#gradient-appearance-shape-19)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 194,
    "tag": "path",
    "id": "shape-20",
    "groups": [
      "g@6"
    ],
    "fill": "url(#gradient-appearance-shape-20)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 195,
    "tag": "path",
    "id": "shape-21",
    "groups": [
      "g@7"
    ],
    "fill": "url(#gradient-appearance-shape-21)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 196,
    "tag": "path",
    "id": "shape-23",
    "groups": [
      "g@7"
    ],
    "fill": "url(#gradient-appearance-shape-23)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 197,
    "tag": "path",
    "id": "shape-29",
    "groups": [
      "g@8"
    ],
    "fill": "url(#gradient-appearance-shape-29)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 198,
    "tag": "path",
    "id": "shape-31",
    "groups": [
      "g@9"
    ],
    "fill": "url(#gradient-appearance-shape-31)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\egtdigitalgames_512\7_egtdigitalgames_512_src\03_rebuilt_filled.svg`

- SHA-256: `6a8ebaa4509b3e9b1ee09dd723f0474a7328be44b6eb8e9a6ff9b9e1b910f75c`
- Bytes: 3015
- Root size: `512` × `512`; viewBox `0 0 512 512`
- Graphics: 4; groups: 1; max group depth: 1
- Export-mode clue: **ambiguous/mixed (heuristic)**
- Multi-subpath filled paths: 1
- Clip/mask references or definitions: 0
- Transformed elements: 1
- Coordinate precision: `{"count": 248, "min": 0, "median": 5.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 3,
  "svg": 1,
  "g": 1,
  "rect": 1
}
```

### Path commands

```json
{
  "L": 115,
  "M": 4,
  "Z": 4
}
```

### Native parameterized elements

```json
{
  "rect": 1
}
```

### Fill-rule counts

```json
{
  "evenodd": 3,
  "default/nonzero": 1
}
```

### Notes

- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "rect",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "#e42314",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 485.7125 259.825)"
  },
  {
    "index": 1,
    "tag": "path",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "#e42314",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 15,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "#e42314",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 14,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@1"
    ],
    "fill": "#e42314",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 86,
      "Z": 2
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 0,
    "tag": "rect",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "#e42314",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 485.7125 259.825)"
  },
  {
    "index": 1,
    "tag": "path",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "#e42314",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 15,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "#e42314",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 14,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@1"
    ],
    "fill": "#e42314",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 86,
      "Z": 2
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\eyecon_512\8_eyecon_512_src\03_rebuilt_filled.svg`

- SHA-256: `d697a036fac3cd30d1194b9c5d43d6cb35795279d7b1151fd63fef373f260013`
- Bytes: 10765
- Root size: `512` × `213`; viewBox `0 0 512 213`
- Graphics: 6; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 3
- Clip/mask references or definitions: 0
- Transformed elements: 0
- Coordinate precision: `{"count": 934, "min": 1, "median": 6.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 6,
  "svg": 1,
  "g": 1
}
```

### Path commands

```json
{
  "L": 458,
  "M": 9,
  "Z": 9
}
```

### Native parameterized elements

```json
{}
```

### Fill-rule counts

```json
{
  "evenodd": 6
}
```

### Notes

- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 35,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": "shape-5",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 32,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": "shape-4",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 13,
      "Z": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 35,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": "shape-5",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 32,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": "shape-4",
    "groups": [
      "g@1"
    ],
    "fill": "#fece1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 13,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_1\13_icon_group_1_src\03_rebuilt_filled.svg`

- SHA-256: `a6d6d7bcebef43c4d32182c6942abc1c8ee0273f7ec550667c7bb280a63b5c9e`
- Bytes: 122195
- Root size: `289` × `228`; viewBox `0 0 289 228`
- Graphics: 519; groups: 5; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 2
- Clip/mask references or definitions: 0
- Transformed elements: 24
- Coordinate precision: `{"count": 6094, "min": 0, "median": 1.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 491,
  "stop": 86,
  "linearGradient": 37,
  "rect": 21,
  "radialGradient": 6,
  "g": 5,
  "circle": 4,
  "ellipse": 3,
  "svg": 1,
  "defs": 1
}
```

### Path commands

```json
{
  "L": 1981,
  "M": 493,
  "Z": 220,
  "A": 67,
  "C": 57,
  "Q": 19
}
```

### Native parameterized elements

```json
{
  "rect": 21,
  "circle": 4,
  "ellipse": 3
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 301,
  "evenodd": 218
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fa8213",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e17527",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f2c4a9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f44011",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 19
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 20
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 22
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eca5a9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f44011",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eca5a9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eca5a9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f44011",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eca5a9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da1026",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e54320",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f6afa8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#921020",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 17
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#921020",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 10
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa5a8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa5a8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#040407",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa5a8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#921020",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fa8213",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e17527",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f2c4a9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fbcb92",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 507,
    "tag": "path",
    "id": "shape-300",
    "groups": [
      "g@1"
    ],
    "fill": "#ffeec6",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 508,
    "tag": "path",
    "id": "shape-301",
    "groups": [
      "g@1"
    ],
    "fill": "#ffeec6",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 509,
    "tag": "path",
    "id": "shape-14",
    "groups": [
      "g@2"
    ],
    "fill": "url(#gradient-appearance-shape-14)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 12,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 510,
    "tag": "path",
    "id": "shape-17",
    "groups": [
      "g@3"
    ],
    "fill": "url(#gradient-appearance-shape-17)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 16,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 511,
    "tag": "path",
    "id": "shape-69",
    "groups": [
      "g@4"
    ],
    "fill": "#08090b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 512,
    "tag": "rect",
    "id": "shape-114",
    "groups": [
      "g@4"
    ],
    "fill": "#08090b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-33.690063 142.769226 202.153824)"
  },
  {
    "index": 513,
    "tag": "path",
    "id": "shape-73",
    "groups": [
      "g@5"
    ],
    "fill": "#08090b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 514,
    "tag": "path",
    "id": "shape-155",
    "groups": [
      "g@5"
    ],
    "fill": "#08090b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 515,
    "tag": "path",
    "id": "shape-250",
    "groups": [
      "g@5"
    ],
    "fill": "#eee1e5",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 516,
    "tag": "path",
    "id": "shape-251",
    "groups": [
      "g@5"
    ],
    "fill": "#c81a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 517,
    "tag": "path",
    "id": "shape-252",
    "groups": [
      "g@5"
    ],
    "fill": "#eee1e5",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 518,
    "tag": "path",
    "id": "shape-253",
    "groups": [
      "g@5"
    ],
    "fill": "#eee1e5",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_3_10\24_icon_group_3_10_src\03_rebuilt_filled.svg`

- SHA-256: `7733c84fdbf4d92537e02f7593304a838b51fd5fbb5117c567fd5ce2b682fa60`
- Bytes: 22169
- Root size: `145` × `76`; viewBox `0 0 145 76`
- Graphics: 99; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 1
- Clip/mask references or definitions: 0
- Transformed elements: 2
- Coordinate precision: `{"count": 1342, "min": 0, "median": 1.0, "p90": 1, "max": 6}`

### Element vocabulary

```json
{
  "path": 96,
  "stop": 6,
  "linearGradient": 3,
  "rect": 2,
  "svg": 1,
  "defs": 1,
  "g": 1,
  "circle": 1
}
```

### Path commands

```json
{
  "L": 470,
  "M": 117,
  "Z": 67,
  "A": 11,
  "C": 11
}
```

### Native parameterized elements

```json
{
  "rect": 2,
  "circle": 1
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 53,
  "evenodd": 46
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ac8c7e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ac8c7e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#906c67",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ac8c7e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#5f241b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#5f241b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ac8c7e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#5f241b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9d0c4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9d0c4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9d0c4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9d0c4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9d0c4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9d0c4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9d0c4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9d0c4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#906c67",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#906c67",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#6f3d37",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#5f241b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9d0c4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d7bfb8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cbaa9e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#6f3d37",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#5f241b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bea8a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c5ada6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4c0b03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ac8c7e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ac8c7e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#906c67",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ac8c7e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bba59f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#5f241b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#5f241b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 87,
    "tag": "path",
    "id": "shape-37",
    "groups": [
      "g@1"
    ],
    "fill": "#673028",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": "shape-38",
    "groups": [
      "g@1"
    ],
    "fill": "#673028",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": "shape-39",
    "groups": [
      "g@1"
    ],
    "fill": "#3e0401",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": "shape-40",
    "groups": [
      "g@1"
    ],
    "fill": "#673028",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": "shape-41",
    "groups": [
      "g@1"
    ],
    "fill": "#f3e1d8",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": "shape-42",
    "groups": [
      "g@1"
    ],
    "fill": "#3e0401",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": "shape-43",
    "groups": [
      "g@1"
    ],
    "fill": "#f3e1d8",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": "shape-44",
    "groups": [
      "g@1"
    ],
    "fill": "#f3e1d8",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": "shape-45",
    "groups": [
      "g@1"
    ],
    "fill": "#3e0401",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": "shape-46",
    "groups": [
      "g@1"
    ],
    "fill": "#3e0401",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": "shape-47",
    "groups": [
      "g@1"
    ],
    "fill": "#82534d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": "shape-residual-48",
    "groups": [
      "g@1"
    ],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 22,
    "commands": {
      "M": 22,
      "L": 111,
      "Z": 22
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_3_2\27_icon_group_3_2_src\03_rebuilt_filled.svg`

- SHA-256: `d6f7b55d941b793fb13336e334ceff63d644b819044bdabed688708f9d2043ab`
- Bytes: 69500
- Root size: `123` × `132`; viewBox `0 0 123 132`
- Graphics: 291; groups: 4; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 3
- Clip/mask references or definitions: 0
- Transformed elements: 6
- Coordinate precision: `{"count": 3652, "min": 0, "median": 1.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 285,
  "stop": 34,
  "linearGradient": 11,
  "radialGradient": 6,
  "g": 4,
  "ellipse": 4,
  "rect": 2,
  "svg": 1,
  "defs": 1
}
```

### Path commands

```json
{
  "L": 1260,
  "M": 289,
  "Z": 133,
  "A": 35,
  "C": 34,
  "Q": 12
}
```

### Native parameterized elements

```json
{
  "ellipse": 4,
  "rect": 2
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 162,
  "evenodd": 129
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#928783",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#928783",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#928783",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#928783",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#786c67",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#60514a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#60514a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#6a5d57",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 23
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 12
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#60514a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#60514a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#382720",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8a19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#382720",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8a19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8f8682",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8a19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8a19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8a19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8a19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8a19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#5b4e48",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#382720",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#60514a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8a19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#382720",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#382720",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#382720",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8a19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#382720",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#382720",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8a19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#928783",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aaa29e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2f190e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#928783",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#928783",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#402c23",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 279,
    "tag": "path",
    "id": "shape-143",
    "groups": [
      "g@1"
    ],
    "fill": "#220e05",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 280,
    "tag": "path",
    "id": "shape-144",
    "groups": [
      "g@1"
    ],
    "fill": "#392114",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 281,
    "tag": "path",
    "id": "shape-145",
    "groups": [
      "g@1"
    ],
    "fill": "#392114",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 282,
    "tag": "path",
    "id": "shape-146",
    "groups": [
      "g@1"
    ],
    "fill": "#220e05",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 283,
    "tag": "path",
    "id": "shape-147",
    "groups": [
      "g@1"
    ],
    "fill": "#897c76",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 284,
    "tag": "path",
    "id": "shape-148",
    "groups": [
      "g@1"
    ],
    "fill": "#47362e",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 285,
    "tag": "path",
    "id": "shape-149",
    "groups": [
      "g@1"
    ],
    "fill": "#220e05",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 286,
    "tag": "path",
    "id": "shape-9",
    "groups": [
      "g@2"
    ],
    "fill": "url(#gradient-appearance-shape-9)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 28,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 287,
    "tag": "rect",
    "id": "shape-42",
    "groups": [
      "g@2"
    ],
    "fill": "#e3dbd7",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-56.309933 85.884605 109.423073)"
  },
  {
    "index": 288,
    "tag": "path",
    "id": "shape-74",
    "groups": [
      "g@3"
    ],
    "fill": "#c1b6b2",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 289,
    "tag": "path",
    "id": "shape-75",
    "groups": [
      "g@3"
    ],
    "fill": "#47362e",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 290,
    "tag": "path",
    "id": "shape-85",
    "groups": [
      "g@4"
    ],
    "fill": "#e3dbd7",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_16\43_icon_group_4_16_src\03_rebuilt_filled.svg`

- SHA-256: `473da57d9229ed0597df6d2b483d27fe82b25ee472a6e86b8b9686b2d88d2e7c`
- Bytes: 53781
- Root size: `83` × `85`; viewBox `0 0 83 85`
- Graphics: 189; groups: 4; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 3
- Clip/mask references or definitions: 0
- Transformed elements: 3
- Coordinate precision: `{"count": 3086, "min": 0, "median": 1.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 184,
  "stop": 20,
  "linearGradient": 6,
  "radialGradient": 4,
  "g": 4,
  "rect": 3,
  "circle": 2,
  "svg": 1,
  "defs": 1
}
```

### Path commands

```json
{
  "L": 1126,
  "M": 191,
  "Z": 58,
  "A": 32,
  "C": 30,
  "Q": 2
}
```

### Native parameterized elements

```json
{
  "rect": 3,
  "circle": 2
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 138,
  "evenodd": 51
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5d57c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5d57c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5d57c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5d57c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4b71d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4b71d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 20
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5d57c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5d57c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 12
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 15
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 20
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dddc20",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b8b81a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b8b81a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dddc20",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bab91d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cccb1e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b8b81a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d4cc6b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dddc20",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bfbe1d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e6bf42",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#edeba0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d4cc6b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cfc47c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa217",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e7dda0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cdbb6b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e7dda0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cfc47c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c6c5c1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c6c5c1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cf7c7b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a69c9c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cf7c7b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e0453e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cd6a69",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e0453e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cfc47c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa217",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa217",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa217",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa217",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e7dda0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#070701",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#070701",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#171704",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#070701",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa217",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#262708",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#89890f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa217",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa217",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa217",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#89890f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3f3f08",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7a7a7a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7a7a7a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a69c9c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#be8886",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#afa217",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d7cd1f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8a8910",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8a8910",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5d57c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5d57c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5d57c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5d57c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4b71d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4b71d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f4eb25",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7b619",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 20
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 177,
    "tag": "path",
    "id": "shape-42",
    "groups": [
      "g@2"
    ],
    "fill": "#242407",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 178,
    "tag": "path",
    "id": "shape-44",
    "groups": [
      "g@2"
    ],
    "fill": "#eedd24",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 179,
    "tag": "path",
    "id": "shape-45",
    "groups": [
      "g@2"
    ],
    "fill": "#8d8c14",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 180,
    "tag": "path",
    "id": "shape-46",
    "groups": [
      "g@2"
    ],
    "fill": "#383810",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 181,
    "tag": "path",
    "id": "shape-47",
    "groups": [
      "g@2"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 182,
    "tag": "path",
    "id": "shape-49",
    "groups": [
      "g@2"
    ],
    "fill": "#bcbb19",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 183,
    "tag": "path",
    "id": "shape-50",
    "groups": [
      "g@2"
    ],
    "fill": "#f9f825",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 184,
    "tag": "path",
    "id": "shape-52",
    "groups": [
      "g@2"
    ],
    "fill": "#595910",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 185,
    "tag": "path",
    "id": "shape-55",
    "groups": [
      "g@2"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 186,
    "tag": "path",
    "id": "shape-56",
    "groups": [
      "g@2"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 187,
    "tag": "path",
    "id": "shape-8",
    "groups": [
      "g@3"
    ],
    "fill": "#d25a54",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 188,
    "tag": "path",
    "id": "shape-37",
    "groups": [
      "g@4"
    ],
    "fill": "#a8a7a7",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_17\44_icon_group_4_17_src\03_rebuilt_filled.svg`

- SHA-256: `6ce296fe7728b63c21bcfd87269a836d3f3a7f2249dcae075c4fa0df30f9d539`
- Bytes: 175608
- Root size: `76` × `92`; viewBox `0 0 76 92`
- Graphics: 606; groups: 5; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 4
- Clip/mask references or definitions: 0
- Transformed elements: 9
- Coordinate precision: `{"count": 9827, "min": 0, "median": 1, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 588,
  "stop": 76,
  "linearGradient": 30,
  "circle": 9,
  "radialGradient": 8,
  "g": 5,
  "ellipse": 5,
  "rect": 4,
  "svg": 1,
  "defs": 1
}
```

### Path commands

```json
{
  "L": 3578,
  "M": 691,
  "Z": 268,
  "C": 91,
  "A": 81,
  "Q": 10
}
```

### Native parameterized elements

```json
{
  "circle": 9,
  "ellipse": 5,
  "rect": 4
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 441,
  "evenodd": 165
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cfa06a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 16
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dbc179",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dbc179",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9a367",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9a367",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9a367",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9a367",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9a367",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c8b06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 10
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c1ab6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9a367",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bea76a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9a367",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dbc179",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dbc179",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ceb672",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bea76a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dbc179",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bea76a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bea76a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cfa06a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cfa06a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cfa06a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c5b180",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dbc179",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 15
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e0b475",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bea76a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9a367",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9a367",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9a367",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ceb672",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9a367",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dbc179",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dbc179",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dbc179",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#730517",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#730517",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c08c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#af7648",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8a422b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#af7648",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cfa06a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8cd81",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 16
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4a067",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b6a167",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#dbc179",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 594,
    "tag": "path",
    "id": "shape-205",
    "groups": [
      "g@2"
    ],
    "fill": "#170700",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 595,
    "tag": "path",
    "id": "shape-37",
    "groups": [
      "g@3"
    ],
    "fill": "url(#gradient-appearance-shape-37)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 15,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 596,
    "tag": "circle",
    "id": "shape-62",
    "groups": [
      "g@3"
    ],
    "fill": "#170700",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 597,
    "tag": "circle",
    "id": "shape-64",
    "groups": [
      "g@3"
    ],
    "fill": "#2a1801",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 598,
    "tag": "path",
    "id": "shape-79",
    "groups": [
      "g@3"
    ],
    "fill": "#170700",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 599,
    "tag": "path",
    "id": "shape-117",
    "groups": [
      "g@3"
    ],
    "fill": "#170700",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 600,
    "tag": "path",
    "id": "shape-126",
    "groups": [
      "g@3"
    ],
    "fill": "#dbbf72",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 601,
    "tag": "path",
    "id": "shape-159",
    "groups": [
      "g@3"
    ],
    "fill": "#2a1801",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 602,
    "tag": "path",
    "id": "shape-164",
    "groups": [
      "g@3"
    ],
    "fill": "#dbbf72",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 603,
    "tag": "path",
    "id": "shape-168",
    "groups": [
      "g@3"
    ],
    "fill": "#dbbf72",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 604,
    "tag": "path",
    "id": "shape-137",
    "groups": [
      "g@4"
    ],
    "fill": "#624a23",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 605,
    "tag": "path",
    "id": "shape-149",
    "groups": [
      "g@5"
    ],
    "fill": "#2a1801",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_18\45_icon_group_4_18_src\03_rebuilt_filled.svg`

- SHA-256: `b94cca8f17a3e974d02d81a7d80e5200163d69079321f9cdf34264082987f418`
- Bytes: 119842
- Root size: `83` × `84`; viewBox `0 0 83 84`
- Graphics: 251; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 1
- Clip/mask references or definitions: 0
- Transformed elements: 4
- Coordinate precision: `{"count": 9059, "min": 0, "median": 6, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 241,
  "stop": 28,
  "linearGradient": 14,
  "circle": 6,
  "rect": 3,
  "svg": 1,
  "defs": 1,
  "g": 1,
  "ellipse": 1
}
```

### Path commands

```json
{
  "L": 3887,
  "M": 399,
  "Z": 257,
  "C": 35,
  "A": 25,
  "Q": 7
}
```

### Native parameterized elements

```json
{
  "circle": 6,
  "rect": 3,
  "ellipse": 1
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 152,
  "evenodd": 99
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d2e35",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7c7e83",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#65676c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d2e35",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#32343d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d2e35",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#57595e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d2e35",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#32343d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7c7e83",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#57595e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3d404b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#95979d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8abb1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8abb1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#82848c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#60636b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8abb1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3d404b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#60636b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#60636b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#60636b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8abb1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#82848c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8abb1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#95979d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8abb1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#60636b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3d404b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#1c1f2b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d2e35",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3d404b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d2e35",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a2a6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#414450",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#909296",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#32343d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7c7e83",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#57595e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#65676c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8abb1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 10
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8abb1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#95979d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a2a4a8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cccfd3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a2a4a8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#32343d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#32343d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#1c1f2b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#1c1f2b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#32343d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#1c1f2b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#32343d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#6c6f77",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8abb1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#32343d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#57595e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#1c1f2b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d2e35",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0b2b7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#82848c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0b2b7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#929499",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#929499",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3d404b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cccfd3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cccfd3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a2a4a9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a2a4a9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0b2b7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0b2b7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cccfd3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0b2b7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d2e35",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7c7e83",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#65676c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d2e35",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a4a6aa",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#32343d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d2e35",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#494c56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 239,
    "tag": "path",
    "id": "shape-122",
    "groups": [
      "g@1"
    ],
    "fill": "#dadce0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 240,
    "tag": "path",
    "id": "shape-126",
    "groups": [
      "g@1"
    ],
    "fill": "#6b6d72",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 241,
    "tag": "path",
    "id": "shape-128",
    "groups": [
      "g@1"
    ],
    "fill": "#3c3e44",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 242,
    "tag": "path",
    "id": "shape-129",
    "groups": [
      "g@1"
    ],
    "fill": "#242735",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 243,
    "tag": "path",
    "id": "shape-132",
    "groups": [
      "g@1"
    ],
    "fill": "#dadce0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 244,
    "tag": "path",
    "id": "shape-135",
    "groups": [
      "g@1"
    ],
    "fill": "#dadce0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 245,
    "tag": "path",
    "id": "shape-136",
    "groups": [
      "g@1"
    ],
    "fill": "#bdc0c4",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 246,
    "tag": "path",
    "id": "shape-138",
    "groups": [
      "g@1"
    ],
    "fill": "#242735",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 247,
    "tag": "path",
    "id": "shape-139",
    "groups": [
      "g@1"
    ],
    "fill": "#a1a3a9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 248,
    "tag": "path",
    "id": "shape-140",
    "groups": [
      "g@1"
    ],
    "fill": "#7f8187",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 249,
    "tag": "path",
    "id": "shape-141",
    "groups": [
      "g@1"
    ],
    "fill": "#6b6d72",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 250,
    "tag": "path",
    "id": "shape-residual-142",
    "groups": [
      "g@1"
    ],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 159,
    "commands": {
      "M": 159,
      "L": 3231,
      "Z": 159
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_2\47_icon_group_4_2_src\03_rebuilt_filled.svg`

- SHA-256: `e172b6834ce92e466bd8859e26a0c591a95946d5829efcc8a745cad354bcf221`
- Bytes: 32018
- Root size: `188` × `75`; viewBox `0 0 188 75`
- Graphics: 130; groups: 2; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 2
- Clip/mask references or definitions: 0
- Transformed elements: 7
- Coordinate precision: `{"count": 1540, "min": 0, "median": 1.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 123,
  "stop": 32,
  "linearGradient": 10,
  "radialGradient": 6,
  "rect": 6,
  "g": 2,
  "svg": 1,
  "defs": 1,
  "ellipse": 1
}
```

### Path commands

```json
{
  "L": 468,
  "M": 125,
  "Z": 60,
  "C": 22,
  "A": 19,
  "Q": 5
}
```

### Native parameterized elements

```json
{
  "rect": 6,
  "ellipse": 1
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 72,
  "evenodd": 58
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#393939",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0580a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0580a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7b8c7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7b8c7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7b8c7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e0afa7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e0afa7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e0afa7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7c0bd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7c0bd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7c0bd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ababf",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7c0bd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7c0bd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ababf",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c4daa8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c4daa8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c4daa8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#71b075",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#71b075",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c4daa8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#add4ab",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9cb32",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eddea4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eddea4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f2c9a8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7c0bd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ababf",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7c0bd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f1d3a6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f1d3a6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ababf",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7c0bd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e0afa7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ec663f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e0afa7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f1d3a6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#feb240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fd9241",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fd9241",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f0bba7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f2c9a8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f2c9a8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d2e1df",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d2e1df",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d2e1df",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d2e1df",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#393939",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0580a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0580a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7b8c7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7b8c7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7b8c7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8ab1c9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 118,
    "tag": "path",
    "id": "shape-55",
    "groups": [
      "g@1"
    ],
    "fill": "#bddce0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 119,
    "tag": "path",
    "id": "shape-56",
    "groups": [
      "g@1"
    ],
    "fill": "#e4e6dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 120,
    "tag": "path",
    "id": "shape-57",
    "groups": [
      "g@1"
    ],
    "fill": "#e4e6dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 121,
    "tag": "path",
    "id": "shape-58",
    "groups": [
      "g@1"
    ],
    "fill": "#e4e6dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 122,
    "tag": "path",
    "id": "shape-59",
    "groups": [
      "g@1"
    ],
    "fill": "#e4e6dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 123,
    "tag": "path",
    "id": "shape-60",
    "groups": [
      "g@1"
    ],
    "fill": "#e4e6dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 124,
    "tag": "path",
    "id": "shape-61",
    "groups": [
      "g@1"
    ],
    "fill": "#e4e6dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 125,
    "tag": "path",
    "id": "shape-62",
    "groups": [
      "g@1"
    ],
    "fill": "#e4e6dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 126,
    "tag": "path",
    "id": "shape-63",
    "groups": [
      "g@1"
    ],
    "fill": "#ffa444",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 127,
    "tag": "path",
    "id": "shape-64",
    "groups": [
      "g@1"
    ],
    "fill": "#e4e6dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 128,
    "tag": "path",
    "id": "shape-65",
    "groups": [
      "g@1"
    ],
    "fill": "#fb7c3e",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 129,
    "tag": "path",
    "id": "shape-31",
    "groups": [
      "g@2"
    ],
    "fill": "#bddce0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_20\48_icon_group_4_20_src\03_rebuilt_filled.svg`

- SHA-256: `f350d6719be1481fdb7af902e96e2f7e4129d21e5af48296aecf6f2d6f1c6c97`
- Bytes: 165062
- Root size: `83` × `79`; viewBox `0 0 83 79`
- Graphics: 386; groups: 3; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 4
- Clip/mask references or definitions: 0
- Transformed elements: 8
- Coordinate precision: `{"count": 11506, "min": 0, "median": 6.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 376,
  "stop": 48,
  "linearGradient": 15,
  "radialGradient": 9,
  "ellipse": 5,
  "g": 3,
  "rect": 3,
  "circle": 2,
  "svg": 1,
  "defs": 1
}
```

### Path commands

```json
{
  "L": 4754,
  "M": 524,
  "Z": 265,
  "C": 81,
  "A": 50,
  "Q": 7
}
```

### Native parameterized elements

```json
{
  "ellipse": 5,
  "rect": 3,
  "circle": 2
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 269,
  "evenodd": 117
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e486ad",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e486ad",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e486ad",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e486ad",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e5689d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e486ad",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c46a9e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e486ad",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e486ad",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e486ad",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e486ad",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e5689d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cf78a9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cf78a9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e0c054",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e0c054",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d2b15c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e0c054",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f8df8e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f8df8e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d2b15c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bfa276",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d2b15c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d2b15c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d2b15c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f8df8e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f8df8e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#edc19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#edc19d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b79c65",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bfa276",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f8df8e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bc9e6c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9bbd2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e486ad",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e486ad",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b03f84",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ab387e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e99bba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 374,
    "tag": "path",
    "id": "shape-44",
    "groups": [
      "g@2"
    ],
    "fill": "#37196e",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 375,
    "tag": "path",
    "id": "shape-95",
    "groups": [
      "g@2"
    ],
    "fill": "#37196e",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 376,
    "tag": "path",
    "id": "shape-17",
    "groups": [
      "g@3"
    ],
    "fill": "url(#gradient-appearance-shape-17)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 13,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 377,
    "tag": "path",
    "id": "shape-22",
    "groups": [
      "g@3"
    ],
    "fill": "url(#gradient-appearance-shape-22)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 11,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 378,
    "tag": "path",
    "id": "shape-31",
    "groups": [
      "g@3"
    ],
    "fill": "#eec9dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 379,
    "tag": "path",
    "id": "shape-60",
    "groups": [
      "g@3"
    ],
    "fill": "#e57eab",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 380,
    "tag": "path",
    "id": "shape-66",
    "groups": [
      "g@3"
    ],
    "fill": "#eec9dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 381,
    "tag": "path",
    "id": "shape-79",
    "groups": [
      "g@3"
    ],
    "fill": "#eec9dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 382,
    "tag": "path",
    "id": "shape-105",
    "groups": [
      "g@3"
    ],
    "fill": "#eec9dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 383,
    "tag": "path",
    "id": "shape-113",
    "groups": [
      "g@3"
    ],
    "fill": "#e57eab",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 384,
    "tag": "path",
    "id": "shape-115",
    "groups": [
      "g@3"
    ],
    "fill": "#eec9dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 385,
    "tag": "path",
    "id": "shape-124",
    "groups": [
      "g@3"
    ],
    "fill": "#eec9dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_22\50_icon_group_4_22_src\03_rebuilt_filled.svg`

- SHA-256: `dae27adda89817f4328231bb406b3239c0e2a934f5ea6f62406b87ead8d92290`
- Bytes: 3205
- Root size: `103` × `63`; viewBox `0 0 103 63`
- Graphics: 13; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 0
- Clip/mask references or definitions: 0
- Transformed elements: 5
- Coordinate precision: `{"count": 170, "min": 0, "median": 1.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 8,
  "rect": 5,
  "stop": 2,
  "svg": 1,
  "defs": 1,
  "linearGradient": 1,
  "g": 1
}
```

### Path commands

```json
{
  "L": 51,
  "M": 8,
  "Z": 8
}
```

### Native parameterized elements

```json
{
  "rect": 5
}
```

### Fill-rule counts

```json
{
  "evenodd": 8,
  "default/nonzero": 5
}
```

### Notes

- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "rect",
    "id": "shape-0",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-0)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-26.565052 77.000008 47.500004)"
  },
  {
    "index": 1,
    "tag": "rect",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-26.565052 25.300003 47.599998)"
  },
  {
    "index": 2,
    "tag": "rect",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-38.659809 36.231712 21.914635)"
  },
  {
    "index": 3,
    "tag": "rect",
    "id": "shape-4",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-78.690071 93.519234 47.403847)"
  },
  {
    "index": 4,
    "tag": "path",
    "id": "shape-5",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 26,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": "shape-7",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "rect",
    "id": "shape-6",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 33 9)"
  },
  {
    "index": 8,
    "tag": "path",
    "id": "shape-8",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": "shape-9",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": "shape-10",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": "shape-11",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 1,
    "tag": "rect",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-26.565052 25.300003 47.599998)"
  },
  {
    "index": 2,
    "tag": "rect",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-38.659809 36.231712 21.914635)"
  },
  {
    "index": 3,
    "tag": "rect",
    "id": "shape-4",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-78.690071 93.519234 47.403847)"
  },
  {
    "index": 4,
    "tag": "path",
    "id": "shape-5",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 26,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": "shape-7",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "rect",
    "id": "shape-6",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 33 9)"
  },
  {
    "index": 8,
    "tag": "path",
    "id": "shape-8",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": "shape-9",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": "shape-10",
    "groups": [
      "g@1"
    ],
    "fill": "#263a2f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": "shape-11",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": "shape-12",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_24\52_icon_group_4_24_src\03_rebuilt_filled.svg`

- SHA-256: `e83ed37e5091e38f51928aeee8364fa75c1ff7cc5641f58ca52b7ca75feed6e2`
- Bytes: 8093
- Root size: `98` × `65`; viewBox `0 0 98 65`
- Graphics: 39; groups: 2; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 0
- Clip/mask references or definitions: 0
- Transformed elements: 3
- Coordinate precision: `{"count": 400, "min": 0, "median": 0.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 33,
  "circle": 3,
  "rect": 3,
  "stop": 2,
  "g": 2,
  "svg": 1,
  "defs": 1,
  "linearGradient": 1
}
```

### Path commands

```json
{
  "L": 112,
  "M": 33,
  "Z": 15,
  "C": 6,
  "A": 4
}
```

### Native parameterized elements

```json
{
  "circle": 3,
  "rect": 3
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 24,
  "evenodd": 15
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da622d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 11
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da622d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 12
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a65d27",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e58f56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a65d27",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a65d27",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e58f56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a65d27",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e58f56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a65d27",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da622d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 11
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#da622d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 12
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9b2924",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a65d27",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e58f56",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a65d27",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a65d27",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 27,
    "tag": "path",
    "id": "shape-10",
    "groups": [
      "g@1"
    ],
    "fill": "#12181d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": "shape-11",
    "groups": [
      "g@1"
    ],
    "fill": "#12181d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": "shape-12",
    "groups": [
      "g@1"
    ],
    "fill": "#12181d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": "shape-13",
    "groups": [
      "g@1"
    ],
    "fill": "#12181d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": "shape-14",
    "groups": [
      "g@1"
    ],
    "fill": "#12181d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": "shape-15",
    "groups": [
      "g@1"
    ],
    "fill": "#12181d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": "shape-16",
    "groups": [
      "g@1"
    ],
    "fill": "#12181d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": "shape-17",
    "groups": [
      "g@1"
    ],
    "fill": "#e99f6f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": "shape-18",
    "groups": [
      "g@1"
    ],
    "fill": "#12181d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": "shape-19",
    "groups": [
      "g@1"
    ],
    "fill": "#12181d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": "shape-20",
    "groups": [
      "g@1"
    ],
    "fill": "#e99f6f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": "shape-7",
    "groups": [
      "g@2"
    ],
    "fill": "#12181d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 26,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_33\62_icon_group_4_33_src\03_rebuilt_filled.svg`

- SHA-256: `2db7627ebc08c4607a5ebbd3fa72d85fc12725befa097c6c931276f9fb075b8a`
- Bytes: 43128
- Root size: `78` × `76`; viewBox `0 0 78 76`
- Graphics: 67; groups: 4; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 3
- Clip/mask references or definitions: 0
- Transformed elements: 2
- Coordinate precision: `{"count": 3270, "min": 0, "median": 6.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 64,
  "stop": 8,
  "linearGradient": 4,
  "g": 4,
  "rect": 2,
  "svg": 1,
  "defs": 1,
  "circle": 1
}
```

### Path commands

```json
{
  "L": 1472,
  "M": 82,
  "Z": 46,
  "A": 11,
  "C": 8,
  "Q": 3
}
```

### Native parameterized elements

```json
{
  "rect": 2,
  "circle": 1
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 39,
  "evenodd": 28
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a34a2e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a34a2e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a34a2e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a34a2e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a39b59",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9e0a03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9e0a03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e1a383",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e1a383",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9e0a03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9e0a03",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#aba282",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d482d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2d482d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9d8c4c",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a34a2e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a34a2e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a34a2e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a34a2e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b0af89",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#918535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 55,
    "tag": "path",
    "id": "shape-26",
    "groups": [
      "g@2"
    ],
    "fill": "#be9d26",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": "shape-2",
    "groups": [
      "g@3"
    ],
    "fill": "url(#gradient-appearance-shape-2)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 15,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": "shape-3",
    "groups": [
      "g@3"
    ],
    "fill": "url(#gradient-appearance-shape-3)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 18,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": "shape-4",
    "groups": [
      "g@3"
    ],
    "fill": "url(#gradient-appearance-shape-4)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 3,
    "commands": {
      "M": 3,
      "L": 154,
      "Z": 3
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "rect",
    "id": "shape-6",
    "groups": [
      "g@3"
    ],
    "fill": "#eadeb3",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-9.462322 48.662167 37.472973)"
  },
  {
    "index": 60,
    "tag": "path",
    "id": "shape-27",
    "groups": [
      "g@3"
    ],
    "fill": "#d7bf6a",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": "shape-28",
    "groups": [
      "g@3"
    ],
    "fill": "#eadeb3",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": "shape-29",
    "groups": [
      "g@3"
    ],
    "fill": "#eadeb3",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": "shape-30",
    "groups": [
      "g@3"
    ],
    "fill": "#eadeb3",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": "shape-31",
    "groups": [
      "g@3"
    ],
    "fill": "#eadeb3",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "rect",
    "id": "shape-13",
    "groups": [
      "g@4"
    ],
    "fill": "#416541",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 45 35)"
  },
  {
    "index": 66,
    "tag": "path",
    "id": "shape-16",
    "groups": [
      "g@4"
    ],
    "fill": "#416541",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_44\74_icon_group_4_44_src\03_rebuilt_filled.svg`

- SHA-256: `f2a43c77931ebd96d379ea79b39219c33b4a7976f51e75ef9c117490594f6944`
- Bytes: 5000
- Root size: `89` × `63`; viewBox `0 0 89 63`
- Graphics: 13; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 1
- Clip/mask references or definitions: 0
- Transformed elements: 2
- Coordinate precision: `{"count": 272, "min": 0, "median": 3.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 11,
  "stop": 6,
  "linearGradient": 2,
  "rect": 2,
  "svg": 1,
  "defs": 1,
  "radialGradient": 1,
  "g": 1
}
```

### Path commands

```json
{
  "L": 101,
  "M": 12,
  "Z": 6,
  "A": 2,
  "C": 2
}
```

### Native parameterized elements

```json
{
  "rect": 2
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 8,
  "evenodd": 5
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f69614",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fde077",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fde077",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f69614",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f69614",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fde077",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f69614",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fde077",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fde077",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f69614",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f69614",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fde077",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@1"
    ],
    "fill": "#fccd1b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 17,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "rect",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-2)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 65.5 52)"
  },
  {
    "index": 8,
    "tag": "rect",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-3)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 38.5 50.5)"
  },
  {
    "index": 9,
    "tag": "path",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-1)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 66,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": "shape-4",
    "groups": [
      "g@1"
    ],
    "fill": "#fff0a2",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": "shape-5",
    "groups": [
      "g@1"
    ],
    "fill": "#fff0a2",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fde077",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fde077",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f69614",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f69614",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#fde077",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@1"
    ],
    "fill": "#fccd1b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 17,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "rect",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-2)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 65.5 52)"
  },
  {
    "index": 8,
    "tag": "rect",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-3)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 38.5 50.5)"
  },
  {
    "index": 9,
    "tag": "path",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-1)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 66,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": "shape-4",
    "groups": [
      "g@1"
    ],
    "fill": "#fff0a2",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": "shape-5",
    "groups": [
      "g@1"
    ],
    "fill": "#fff0a2",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": "shape-6",
    "groups": [
      "g@1"
    ],
    "fill": "#fff0a2",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_54\85_icon_group_4_54_src\03_rebuilt_filled.svg`

- SHA-256: `af1027aa05c1b073c285a22da3cb7f82fa634d6592753703f9f290a17cbfb979`
- Bytes: 13954
- Root size: `107` × `48`; viewBox `0 0 107 48`
- Graphics: 57; groups: 2; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 1
- Clip/mask references or definitions: 0
- Transformed elements: 1
- Coordinate precision: `{"count": 775, "min": 0, "median": 1, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 56,
  "stop": 4,
  "linearGradient": 2,
  "g": 2,
  "svg": 1,
  "defs": 1,
  "rect": 1
}
```

### Path commands

```json
{
  "L": 270,
  "M": 57,
  "Z": 30,
  "A": 9,
  "C": 6,
  "Q": 3
}
```

### Native parameterized elements

```json
{
  "rect": 1
}
```

### Fill-rule counts

```json
{
  "evenodd": 29,
  "default/nonzero": 28
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9cb1c6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9cb1c6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#353535",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#010101",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 45,
    "tag": "path",
    "id": "shape-20",
    "groups": [
      "g@1"
    ],
    "fill": "#4b4b4c",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": "shape-22",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": "shape-10",
    "groups": [
      "g@1"
    ],
    "fill": "#075d94",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": "shape-24",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": "shape-23",
    "groups": [
      "g@1"
    ],
    "fill": "#4b4b4c",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": "shape-26",
    "groups": [
      "g@1"
    ],
    "fill": "#4b4b4c",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": "shape-27",
    "groups": [
      "g@1"
    ],
    "fill": "#4b4b4c",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": "shape-28",
    "groups": [
      "g@1"
    ],
    "fill": "#d5e3ec",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": "shape-29",
    "groups": [
      "g@1"
    ],
    "fill": "#d5e3ec",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": "shape-30",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": "shape-31",
    "groups": [
      "g@1"
    ],
    "fill": "#d5e3ec",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": "shape-12",
    "groups": [
      "g@2"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 11,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_55\86_icon_group_4_55_src\03_rebuilt_filled.svg`

- SHA-256: `094294944f8b1372cc2186d6612e287d2ed88912825f4672427bcd1ec248fc09`
- Bytes: 37744
- Root size: `89` × `55`; viewBox `0 0 89 55`
- Graphics: 159; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 0
- Clip/mask references or definitions: 0
- Transformed elements: 10
- Coordinate precision: `{"count": 1920, "min": 0, "median": 1.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 149,
  "stop": 18,
  "rect": 10,
  "linearGradient": 7,
  "radialGradient": 2,
  "svg": 1,
  "defs": 1,
  "g": 1
}
```

### Path commands

```json
{
  "L": 561,
  "M": 149,
  "C": 42,
  "Z": 40,
  "A": 20,
  "Q": 2
}
```

### Native parameterized elements

```json
{
  "rect": 10
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 119,
  "evenodd": 40
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 16
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a1a1a1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0f0f0f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0f0f0f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0f0f0f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0f0f0f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0f0f0f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0f0f0f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0f0f0f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0f0f0f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#0f0f0f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 16
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a0a0a0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#020202",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#101010",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 147,
    "tag": "path",
    "id": "shape-38",
    "groups": [
      "g@1"
    ],
    "fill": "#191919",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 148,
    "tag": "path",
    "id": "shape-39",
    "groups": [
      "g@1"
    ],
    "fill": "#191919",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 149,
    "tag": "path",
    "id": "shape-40",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 150,
    "tag": "path",
    "id": "shape-41",
    "groups": [
      "g@1"
    ],
    "fill": "#191919",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 151,
    "tag": "path",
    "id": "shape-42",
    "groups": [
      "g@1"
    ],
    "fill": "#dadada",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 152,
    "tag": "path",
    "id": "shape-43",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 153,
    "tag": "path",
    "id": "shape-44",
    "groups": [
      "g@1"
    ],
    "fill": "#191919",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 154,
    "tag": "path",
    "id": "shape-45",
    "groups": [
      "g@1"
    ],
    "fill": "#dadada",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 155,
    "tag": "path",
    "id": "shape-46",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 156,
    "tag": "path",
    "id": "shape-47",
    "groups": [
      "g@1"
    ],
    "fill": "#dadada",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 157,
    "tag": "path",
    "id": "shape-48",
    "groups": [
      "g@1"
    ],
    "fill": "#191919",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 158,
    "tag": "path",
    "id": "shape-49",
    "groups": [
      "g@1"
    ],
    "fill": "#000000",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_58\89_icon_group_4_58_src\03_rebuilt_filled.svg`

- SHA-256: `e60c4df11fc253651ffd3b4e2c564584e822d024b128f7c78950eddc4bc03f15`
- Bytes: 18577
- Root size: `106` × `45`; viewBox `0 0 106 45`
- Graphics: 50; groups: 2; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 1
- Clip/mask references or definitions: 0
- Transformed elements: 2
- Coordinate precision: `{"count": 1334, "min": 0, "median": 4.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 48,
  "stop": 6,
  "linearGradient": 3,
  "g": 2,
  "rect": 2,
  "svg": 1,
  "defs": 1
}
```

### Path commands

```json
{
  "L": 573,
  "M": 52,
  "Z": 21,
  "C": 6,
  "A": 4
}
```

### Native parameterized elements

```json
{
  "rect": 2
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 33,
  "evenodd": 17
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 17
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 26
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 25
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 23
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 25
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 11
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bdaa4e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bdaa4e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e7c711",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bdaa4e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bdaa4e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d3c69f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5bb27",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e7c711",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d5bb27",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d3c69f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bdaa4e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3b6583",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3b6583",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3b6583",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3b6583",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3b6583",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9c946f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9c946f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#849fae",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#849fae",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7b1a3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7b1a3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 17
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 26
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 25
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 23
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 25
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 11
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b5a06d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bdaa4e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bdaa4e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e7c711",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 38,
    "tag": "path",
    "id": "shape-13",
    "groups": [
      "g@1"
    ],
    "fill": "#54776c",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": "shape-16",
    "groups": [
      "g@1"
    ],
    "fill": "#d5be1b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": "shape-19",
    "groups": [
      "g@1"
    ],
    "fill": "#54776c",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": "shape-3",
    "groups": [
      "g@2"
    ],
    "fill": "url(#gradient-appearance-shape-3)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@2"
    ],
    "fill": "#f7cf01",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 5,
    "commands": {
      "M": 5,
      "L": 315,
      "Z": 5
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": "shape-4",
    "groups": [
      "g@2"
    ],
    "fill": "url(#gradient-appearance-shape-4)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 18,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": "shape-9",
    "groups": [
      "g@2"
    ],
    "fill": "#54776c",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": "shape-12",
    "groups": [
      "g@2"
    ],
    "fill": "#54776c",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": "shape-14",
    "groups": [
      "g@2"
    ],
    "fill": "#a5bdd9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": "shape-15",
    "groups": [
      "g@2"
    ],
    "fill": "#a9a538",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": "shape-17",
    "groups": [
      "g@2"
    ],
    "fill": "#a9a538",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": "shape-18",
    "groups": [
      "g@2"
    ],
    "fill": "#a5bdd9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_62\94_icon_group_4_62_src\03_rebuilt_filled.svg`

- SHA-256: `90d69bccb8dd81391d5f0e0c45e7c82fe2989667f6555d3fa11286bec20c53c6`
- Bytes: 10654
- Root size: `91` × `48`; viewBox `0 0 91 48`
- Graphics: 24; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 2
- Clip/mask references or definitions: 0
- Transformed elements: 3
- Coordinate precision: `{"count": 772, "min": 0, "median": 1.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 21,
  "stop": 10,
  "linearGradient": 3,
  "rect": 3,
  "radialGradient": 2,
  "svg": 1,
  "defs": 1,
  "g": 1
}
```

### Path commands

```json
{
  "L": 344,
  "M": 24,
  "Z": 18,
  "C": 1
}
```

### Native parameterized elements

```json
{
  "rect": 3
}
```

### Fill-rule counts

```json
{
  "evenodd": 15,
  "default/nonzero": 9
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d35654",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@1"
    ],
    "fill": "#cc3372",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 3,
    "commands": {
      "M": 3,
      "L": 165,
      "Z": 3
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "rect",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "#da6e16",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 63 17)"
  },
  {
    "index": 8,
    "tag": "path",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "#da6e16",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 46,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "#da6e16",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 20,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": "shape-4",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-4)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 27,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": "shape-5",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-5)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 11,
      "Z": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 12,
    "tag": "path",
    "id": "shape-6",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-6)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 12,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": "shape-8",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-8)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 26,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": "shape-10",
    "groups": [
      "g@1"
    ],
    "fill": "#ae9873",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "rect",
    "id": "shape-7",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-7)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 75 40)"
  },
  {
    "index": 16,
    "tag": "rect",
    "id": "shape-11",
    "groups": [
      "g@1"
    ],
    "fill": "#ae9873",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 44.5 41)"
  },
  {
    "index": 17,
    "tag": "path",
    "id": "shape-9",
    "groups": [
      "g@1"
    ],
    "fill": "#da6e16",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": "shape-12",
    "groups": [
      "g@1"
    ],
    "fill": "#da6e16",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": "shape-13",
    "groups": [
      "g@1"
    ],
    "fill": "#ae9873",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": "shape-14",
    "groups": [
      "g@1"
    ],
    "fill": "#ae9873",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": "shape-15",
    "groups": [
      "g@1"
    ],
    "fill": "#ae9873",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": "shape-16",
    "groups": [
      "g@1"
    ],
    "fill": "#ae9873",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": "shape-17",
    "groups": [
      "g@1"
    ],
    "fill": "#ae9873",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_63\95_icon_group_4_63_src\03_rebuilt_filled.svg`

- SHA-256: `a766f71b9f59c973fb4d4d7d2fb6be1f7d6fcc526052dec0fb9f5343e8a03bba`
- Bytes: 17594
- Root size: `85` × `49`; viewBox `0 0 85 49`
- Graphics: 70; groups: 3; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 2
- Clip/mask references or definitions: 0
- Transformed elements: 5
- Coordinate precision: `{"count": 976, "min": 0, "median": 1.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 65,
  "stop": 8,
  "rect": 5,
  "linearGradient": 3,
  "g": 3,
  "svg": 1,
  "defs": 1,
  "radialGradient": 1
}
```

### Path commands

```json
{
  "L": 326,
  "M": 67,
  "Z": 35,
  "A": 11,
  "C": 9,
  "Q": 1
}
```

### Native parameterized elements

```json
{
  "rect": 5
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 37,
  "evenodd": 33
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#2c2829",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 58,
    "tag": "path",
    "id": "shape-29",
    "groups": [
      "g@1"
    ],
    "fill": "#332f30",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": "shape-30",
    "groups": [
      "g@1"
    ],
    "fill": "#332f30",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": "shape-31",
    "groups": [
      "g@1"
    ],
    "fill": "#231f20",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": "shape-32",
    "groups": [
      "g@1"
    ],
    "fill": "#332f30",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": "shape-33",
    "groups": [
      "g@1"
    ],
    "fill": "#332f30",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": "shape-34",
    "groups": [
      "g@1"
    ],
    "fill": "#332f30",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": "shape-35",
    "groups": [
      "g@1"
    ],
    "fill": "#332f30",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": "shape-36",
    "groups": [
      "g@1"
    ],
    "fill": "#332f30",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": "shape-37",
    "groups": [
      "g@1"
    ],
    "fill": "#231f20",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": "shape-7",
    "groups": [
      "g@2"
    ],
    "fill": "url(#gradient-appearance-shape-7)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": "shape-11",
    "groups": [
      "g@3"
    ],
    "fill": "#332f30",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": "shape-12",
    "groups": [
      "g@3"
    ],
    "fill": "#332f30",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_65\97_icon_group_4_65_src\03_rebuilt_filled.svg`

- SHA-256: `7327b47cad7103bcaa1f6d8bdff57a696b2cb57f33300fd9ac33ade00cac5c6f`
- Bytes: 10576
- Root size: `95` × `43`; viewBox `0 0 95 43`
- Graphics: 39; groups: 2; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 1
- Clip/mask references or definitions: 0
- Transformed elements: 1
- Coordinate precision: `{"count": 605, "min": 0, "median": 5, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 38,
  "stop": 2,
  "g": 2,
  "svg": 1,
  "defs": 1,
  "radialGradient": 1,
  "rect": 1
}
```

### Path commands

```json
{
  "L": 218,
  "M": 39,
  "Z": 20,
  "C": 8,
  "A": 4,
  "Q": 1
}
```

### Native parameterized elements

```json
{
  "rect": 1
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 20,
  "evenodd": 19
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b72622",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b72622",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b72622",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cc2925",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b72622",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cc2925",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b72622",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#efa7a4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cc2925",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cc2925",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#802f22",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#802f22",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7a8a4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#802f22",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#802f22",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#914f44",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b7a8a4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c2b2ac",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#8a6d63",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b72622",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b72622",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b72622",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cc2925",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b72622",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cc2925",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b72622",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#efa7a4",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cc2925",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cc2925",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#802f22",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#802f22",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 27,
    "tag": "path",
    "id": "shape-15",
    "groups": [
      "g@1"
    ],
    "fill": "#9f3225",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": "shape-16",
    "groups": [
      "g@1"
    ],
    "fill": "#efe2dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": "shape-17",
    "groups": [
      "g@1"
    ],
    "fill": "#522d1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": "shape-18",
    "groups": [
      "g@1"
    ],
    "fill": "#522d1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "rect",
    "id": "shape-3",
    "groups": [
      "g@2"
    ],
    "fill": "#9f3225",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-14.036243 75.470589 27.382355)"
  },
  {
    "index": 32,
    "tag": "path",
    "id": "shape-6",
    "groups": [
      "g@2"
    ],
    "fill": "#522d1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": "shape-7",
    "groups": [
      "g@2"
    ],
    "fill": "#9f3225",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": "shape-8",
    "groups": [
      "g@2"
    ],
    "fill": "#522d1f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": "shape-9",
    "groups": [
      "g@2"
    ],
    "fill": "#efe2dd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": "shape-10",
    "groups": [
      "g@2"
    ],
    "fill": "#93766c",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": "shape-19",
    "groups": [
      "g@2"
    ],
    "fill": "#7f6358",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": "shape-21",
    "groups": [
      "g@2"
    ],
    "fill": "#7f6358",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_66\98_icon_group_4_66_src\03_rebuilt_filled.svg`

- SHA-256: `9142531305c0426c12bf869552759f86136e333564116b258b77764782975157`
- Bytes: 71865
- Root size: `90` × `44`; viewBox `0 0 90 44`
- Graphics: 135; groups: 3; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 3
- Clip/mask references or definitions: 0
- Transformed elements: 1
- Coordinate precision: `{"count": 5591, "min": 0, "median": 6, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 125,
  "stop": 32,
  "linearGradient": 13,
  "circle": 9,
  "radialGradient": 3,
  "g": 3,
  "svg": 1,
  "defs": 1,
  "rect": 1
}
```

### Path commands

```json
{
  "L": 2418,
  "M": 213,
  "Z": 124,
  "A": 22,
  "C": 19,
  "Q": 1
}
```

### Native parameterized elements

```json
{
  "circle": 9,
  "rect": 1
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 99,
  "evenodd": 36
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 27
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 25
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 13
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 13
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 19
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 10
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 10
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9a9abc",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#3233dd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7e7fc1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9a9abc",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7e7fc1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#1d1ee9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7e7fc1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#6666c8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7e7fc1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7e7fc1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7e7fc1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9a9abc",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#5252ce",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9a9abc",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7e7fc1",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9a9abc",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#5252ce",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#6666c8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#6666c8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#6666c8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#1d1ee9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9a9abc",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#6666c8",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#1d1ee9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4343d5",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 20
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 15
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c7c764",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cece53",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cece53",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cece53",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cece53",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 11
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cece53",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bbbb9a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bbbb9a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e8e81f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d9d93a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bbbb9a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c1c142",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c1c142",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c1c142",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c1c142",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 27
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b9b9ba",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 123,
    "tag": "circle",
    "id": "shape-24",
    "groups": [
      "g@2"
    ],
    "fill": "#adae51",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 124,
    "tag": "circle",
    "id": "shape-25",
    "groups": [
      "g@2"
    ],
    "fill": "#adae51",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 125,
    "tag": "circle",
    "id": "shape-22",
    "groups": [
      "g@2"
    ],
    "fill": "#adae51",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 126,
    "tag": "path",
    "id": "shape-28",
    "groups": [
      "g@2"
    ],
    "fill": "#d3d32d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 127,
    "tag": "path",
    "id": "shape-35",
    "groups": [
      "g@2"
    ],
    "fill": "#d3d32d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 128,
    "tag": "path",
    "id": "shape-37",
    "groups": [
      "g@2"
    ],
    "fill": "#d3d32d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 129,
    "tag": "path",
    "id": "shape-40",
    "groups": [
      "g@2"
    ],
    "fill": "#8d8d73",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 130,
    "tag": "path",
    "id": "shape-43",
    "groups": [
      "g@2"
    ],
    "fill": "#2b2dd3",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 131,
    "tag": "path",
    "id": "shape-45",
    "groups": [
      "g@2"
    ],
    "fill": "#d3d32d",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 132,
    "tag": "path",
    "id": "shape-46",
    "groups": [
      "g@2"
    ],
    "fill": "#8d8d73",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 133,
    "tag": "path",
    "id": "shape-48",
    "groups": [
      "g@2"
    ],
    "fill": "#2b2dd3",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 134,
    "tag": "path",
    "id": "shape-18",
    "groups": [
      "g@3"
    ],
    "fill": "#8d8d73",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 26,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_7\102_icon_group_4_7_src\03_rebuilt_filled.svg`

- SHA-256: `34355363ee21f384bdc39c3b5ee8cd464e6aa3c57fa9b4668012d149089f0457`
- Bytes: 234885
- Root size: `99` × `89`; viewBox `0 0 99 89`
- Graphics: 841; groups: 3; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 2
- Clip/mask references or definitions: 0
- Transformed elements: 7
- Coordinate precision: `{"count": 12989, "min": 0, "median": 1, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 823,
  "stop": 92,
  "linearGradient": 34,
  "radialGradient": 12,
  "circle": 10,
  "ellipse": 8,
  "g": 3,
  "svg": 1,
  "defs": 1
}
```

### Path commands

```json
{
  "L": 4619,
  "M": 934,
  "Z": 326,
  "C": 165,
  "A": 94,
  "Q": 25
}
```

### Native parameterized elements

```json
{
  "circle": 10,
  "ellipse": 8
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 626,
  "evenodd": 215
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 20
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49c78",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 17
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49867",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bf9621",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49238",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49c78",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49238",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c59820",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c59820",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4944d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b3921e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d7a01f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eac766",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eac766",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49867",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c59820",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cd9d24",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d7a01f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b3921e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ba9420",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eac766",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cd9d24",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4944d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49867",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4944d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49238",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49238",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49238",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49867",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49c78",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49867",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4944d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49238",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49238",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d7a01f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ba9420",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49867",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4944d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cd9d24",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c59820",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4944d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b3921e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b3921e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c59820",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cd9d24",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cd9d24",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cea939",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cea939",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#cd9d24",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b3921e",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bf9621",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bf9621",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c59820",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49c78",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49c78",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49238",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49238",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49238",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49238",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49867",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bf9621",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bf9621",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4944d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49867",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bf9621",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4944d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d7a01f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d7a01f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#d7a01f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 20
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49c78",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 17
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b49867",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eab722",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#bf9621",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e2a91f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 829,
    "tag": "path",
    "id": "shape-234",
    "groups": [
      "g@1"
    ],
    "fill": "#39221f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 830,
    "tag": "path",
    "id": "shape-235",
    "groups": [
      "g@1"
    ],
    "fill": "#844820",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 831,
    "tag": "path",
    "id": "shape-236",
    "groups": [
      "g@1"
    ],
    "fill": "#e0c789",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 832,
    "tag": "path",
    "id": "shape-237",
    "groups": [
      "g@1"
    ],
    "fill": "#39221f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 833,
    "tag": "path",
    "id": "shape-238",
    "groups": [
      "g@1"
    ],
    "fill": "#1d111b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 834,
    "tag": "path",
    "id": "shape-239",
    "groups": [
      "g@1"
    ],
    "fill": "#39221f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 835,
    "tag": "path",
    "id": "shape-residual-241",
    "groups": [
      "g@1"
    ],
    "fill": "#f5cc7a",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 110,
    "commands": {
      "M": 110,
      "L": 2355,
      "Z": 110
    },
    "transform": null
  },
  {
    "index": 836,
    "tag": "path",
    "id": "shape-11",
    "groups": [
      "g@2"
    ],
    "fill": "#2458a2",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 23,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 837,
    "tag": "path",
    "id": "shape-15",
    "groups": [
      "g@2"
    ],
    "fill": "#2d448a",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 36,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 838,
    "tag": "path",
    "id": "shape-211",
    "groups": [
      "g@3"
    ],
    "fill": "#9e8349",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 839,
    "tag": "path",
    "id": "shape-212",
    "groups": [
      "g@3"
    ],
    "fill": "#cf841e",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 840,
    "tag": "path",
    "id": "shape-213",
    "groups": [
      "g@3"
    ],
    "fill": "#9e8349",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_73\106_icon_group_4_73_src\03_rebuilt_filled.svg`

- SHA-256: `ee9653934cda73b25222407d5b86c9411275d753ad725639fdfa96f82dcf50fc`
- Bytes: 25381
- Root size: `88` × `41`; viewBox `0 0 88 41`
- Graphics: 108; groups: 2; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 1
- Clip/mask references or definitions: 0
- Transformed elements: 3
- Coordinate precision: `{"count": 1173, "min": 0, "median": 1, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 105,
  "stop": 22,
  "linearGradient": 11,
  "g": 2,
  "rect": 2,
  "svg": 1,
  "defs": 1,
  "ellipse": 1
}
```

### Path commands

```json
{
  "L": 406,
  "M": 106,
  "Z": 46,
  "A": 10,
  "C": 7,
  "Q": 2
}
```

### Native parameterized elements

```json
{
  "rect": 2,
  "ellipse": 1
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 63,
  "evenodd": 45
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#034b88",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#01295f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#034b88",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a2b2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a2b2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#034b88",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a2b2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#098dc6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4cb1db",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98bed9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#034b88",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a2b2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a2b2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#01295f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a2b2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a0ab",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#01194f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#076ba6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a8bd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#076ba6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#076ba6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#076ba6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#034b88",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#098dc6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#01295f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4cb1db",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a2b2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a0ab",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#989ea6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a0ab",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#01194f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#01194f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#01194f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a0ab",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#01194f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#076ba6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a2b2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a0ab",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#989ea6",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a0ab",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4cb1db",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7cddd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4cb1db",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a8bd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98bed9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#4cb1db",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a7cddd",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98bed9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#034b88",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#01295f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#034b88",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a2b2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a2b2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#034b88",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#98a2b2",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#02306a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 96,
    "tag": "path",
    "id": "shape-39",
    "groups": [
      "g@1"
    ],
    "fill": "#01093f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": "shape-40",
    "groups": [
      "g@1"
    ],
    "fill": "#023a76",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": "shape-42",
    "groups": [
      "g@1"
    ],
    "fill": "#6ac1df",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": "shape-44",
    "groups": [
      "g@1"
    ],
    "fill": "#01093f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 100,
    "tag": "path",
    "id": "shape-46",
    "groups": [
      "g@1"
    ],
    "fill": "#01093f",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 101,
    "tag": "path",
    "id": "shape-49",
    "groups": [
      "g@1"
    ],
    "fill": "#02235c",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 102,
    "tag": "path",
    "id": "shape-50",
    "groups": [
      "g@1"
    ],
    "fill": "#055997",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 103,
    "tag": "path",
    "id": "shape-51",
    "groups": [
      "g@1"
    ],
    "fill": "#089fd7",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 104,
    "tag": "path",
    "id": "shape-52",
    "groups": [
      "g@1"
    ],
    "fill": "#0979b4",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 105,
    "tag": "path",
    "id": "shape-54",
    "groups": [
      "g@1"
    ],
    "fill": "#089fd7",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 106,
    "tag": "path",
    "id": "shape-55",
    "groups": [
      "g@1"
    ],
    "fill": "#d0d7dc",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 107,
    "tag": "path",
    "id": "shape-28",
    "groups": [
      "g@2"
    ],
    "fill": "#023a76",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_75\108_icon_group_4_75_src\03_rebuilt_filled.svg`

- SHA-256: `4f60df2de5c90ec0636d162345f1640b507073c001f7f5f48d139f3f14ba715b`
- Bytes: 13828
- Root size: `77` × `41`; viewBox `0 0 77 41`
- Graphics: 13; groups: 2; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 1
- Clip/mask references or definitions: 0
- Transformed elements: 1
- Coordinate precision: `{"count": 1155, "min": 0, "median": 6, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 11,
  "g": 2,
  "svg": 1,
  "circle": 1,
  "rect": 1
}
```

### Path commands

```json
{
  "L": 543,
  "M": 19,
  "Z": 13,
  "A": 2
}
```

### Native parameterized elements

```json
{
  "circle": 1,
  "rect": 1
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 8,
  "evenodd": 5
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "circle",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": "shape-4",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "rect",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 23.5 14)"
  },
  {
    "index": 10,
    "tag": "path",
    "id": "shape-5",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": "shape-6",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a8c2e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "circle",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": "shape-4",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "rect",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 23.5 14)"
  },
  {
    "index": 10,
    "tag": "path",
    "id": "shape-5",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": "shape-6",
    "groups": [
      "g@1"
    ],
    "fill": "#e0ece9",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@2"
    ],
    "fill": "#3785dc",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 9,
    "commands": {
      "M": 9,
      "L": 507,
      "Z": 9
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_4_77\110_icon_group_4_77_src\03_rebuilt_filled.svg`

- SHA-256: `532b5b1344eb288e76f0469c65e451ac2adaa6837bea1c581a5ba29cf7c30533`
- Bytes: 11457
- Root size: `87` × `31`; viewBox `0 0 87 31`
- Graphics: 5; groups: 2; max group depth: 1
- Export-mode clue: **ambiguous/mixed (heuristic)**
- Multi-subpath filled paths: 1
- Clip/mask references or definitions: 0
- Transformed elements: 3
- Coordinate precision: `{"count": 942, "min": 0, "median": 6.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "stop": 4,
  "rect": 3,
  "g": 2,
  "path": 2,
  "svg": 1,
  "defs": 1,
  "radialGradient": 1,
  "linearGradient": 1
}
```

### Path commands

```json
{
  "L": 447,
  "M": 9,
  "Z": 9
}
```

### Native parameterized elements

```json
{
  "rect": 3
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 3,
  "evenodd": 2
}
```

### Notes

- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@1"
    ],
    "fill": "#ff0504",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 8,
    "commands": {
      "M": 8,
      "L": 444,
      "Z": 8
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "rect",
    "id": "shape-1",
    "groups": [
      "g@2"
    ],
    "fill": "url(#gradient-appearance-shape-1)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-45 24.500002 15.499999)"
  },
  {
    "index": 2,
    "tag": "rect",
    "id": "shape-2",
    "groups": [
      "g@2"
    ],
    "fill": "url(#gradient-appearance-shape-2)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 41 15.5)"
  },
  {
    "index": 3,
    "tag": "path",
    "id": "shape-4",
    "groups": [
      "g@2"
    ],
    "fill": "#ff0504",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "rect",
    "id": "shape-3",
    "groups": [
      "g@2"
    ],
    "fill": "#ff0504",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 52 17)"
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@1"
    ],
    "fill": "#ff0504",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 8,
    "commands": {
      "M": 8,
      "L": 444,
      "Z": 8
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "rect",
    "id": "shape-1",
    "groups": [
      "g@2"
    ],
    "fill": "url(#gradient-appearance-shape-1)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-45 24.500002 15.499999)"
  },
  {
    "index": 2,
    "tag": "rect",
    "id": "shape-2",
    "groups": [
      "g@2"
    ],
    "fill": "url(#gradient-appearance-shape-2)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 41 15.5)"
  },
  {
    "index": 3,
    "tag": "path",
    "id": "shape-4",
    "groups": [
      "g@2"
    ],
    "fill": "#ff0504",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "rect",
    "id": "shape-3",
    "groups": [
      "g@2"
    ],
    "fill": "#ff0504",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 52 17)"
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_5\116_icon_group_5_src\03_rebuilt_filled.svg`

- SHA-256: `351b6b3a1ae36a986e2c1474d8cebe611c5758f6c409fee590f532b35762cd1b`
- Bytes: 20856
- Root size: `327` × `105`; viewBox `0 0 327 105`
- Graphics: 62; groups: 4; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 3
- Clip/mask references or definitions: 0
- Transformed elements: 6
- Coordinate precision: `{"count": 1307, "min": 0, "median": 1, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 55,
  "stop": 16,
  "linearGradient": 6,
  "rect": 6,
  "g": 4,
  "radialGradient": 2,
  "svg": 1,
  "defs": 1,
  "circle": 1
}
```

### Path commands

```json
{
  "L": 503,
  "M": 58,
  "Z": 30,
  "A": 9,
  "C": 8,
  "Q": 2
}
```

### Native parameterized elements

```json
{
  "rect": 6,
  "circle": 1
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 35,
  "evenodd": 27
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 20
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 18
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#99b7d0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#99b7d0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#99b7d0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#99b7d0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#c2e3f7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#b4d6ea",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#9dbdd0",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a2c9e3",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#88adc9",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#7099b7",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 20
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 18
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ea2240",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 50,
    "tag": "path",
    "id": "shape-24",
    "groups": [
      "g@1"
    ],
    "fill": "#d52c48",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": "shape-25",
    "groups": [
      "g@1"
    ],
    "fill": "#d52c48",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": "shape-26",
    "groups": [
      "g@1"
    ],
    "fill": "#d52c48",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": "shape-28",
    "groups": [
      "g@1"
    ],
    "fill": "#d52c48",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": "shape-29",
    "groups": [
      "g@1"
    ],
    "fill": "#d52c48",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": "shape-30",
    "groups": [
      "g@1"
    ],
    "fill": "#d52c48",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": "shape-31",
    "groups": [
      "g@1"
    ],
    "fill": "#d52c48",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": "shape-32",
    "groups": [
      "g@1"
    ],
    "fill": "#d52c48",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": "shape-34",
    "groups": [
      "g@1"
    ],
    "fill": "#d0eefd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": "shape-8",
    "groups": [
      "g@2"
    ],
    "fill": "url(#gradient-appearance-shape-8)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": "shape-27",
    "groups": [
      "g@3"
    ],
    "fill": "#d0eefd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": "shape-33",
    "groups": [
      "g@4"
    ],
    "fill": "#d0eefd",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\icon_group_7\118_icon_group_7_src\03_rebuilt_filled.svg`

- SHA-256: `60bd9fe9d91b36bea4c52b725706a76c57b9b4da198ba5f335bf76efe57262ed`
- Bytes: 315172
- Root size: `271` × `82`; viewBox `0 0 271 82`
- Graphics: 588; groups: 6; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 6
- Clip/mask references or definitions: 0
- Transformed elements: 10
- Coordinate precision: `{"count": 23431, "min": 0, "median": 6, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "path": 569,
  "stop": 32,
  "linearGradient": 11,
  "rect": 10,
  "circle": 8,
  "g": 6,
  "radialGradient": 5,
  "svg": 1,
  "defs": 1,
  "ellipse": 1
}
```

### Path commands

```json
{
  "L": 10240,
  "M": 841,
  "Z": 495,
  "A": 106,
  "C": 57,
  "Q": 8
}
```

### Native parameterized elements

```json
{
  "rect": 10,
  "circle": 8,
  "ellipse": 1
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 365,
  "evenodd": 223
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 12
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 9
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 10
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eb3f3a",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e02018",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f9938d",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 576,
    "tag": "path",
    "id": "shape-213",
    "groups": [
      "g@5"
    ],
    "fill": "#ffc7c0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 577,
    "tag": "path",
    "id": "shape-28",
    "groups": [
      "g@6"
    ],
    "fill": "#ffc7c0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 578,
    "tag": "path",
    "id": "shape-43",
    "groups": [
      "g@6"
    ],
    "fill": "#e45551",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 579,
    "tag": "circle",
    "id": "shape-44",
    "groups": [
      "g@6"
    ],
    "fill": "#e45551",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 580,
    "tag": "path",
    "id": "shape-74",
    "groups": [
      "g@6"
    ],
    "fill": "#ffc7c0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 581,
    "tag": "path",
    "id": "shape-135",
    "groups": [
      "g@6"
    ],
    "fill": "#e45551",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 582,
    "tag": "path",
    "id": "shape-244",
    "groups": [
      "g@6"
    ],
    "fill": "#e45551",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 583,
    "tag": "path",
    "id": "shape-248",
    "groups": [
      "g@6"
    ],
    "fill": "#ffc7c0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 584,
    "tag": "path",
    "id": "shape-249",
    "groups": [
      "g@6"
    ],
    "fill": "#ffc7c0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 585,
    "tag": "path",
    "id": "shape-250",
    "groups": [
      "g@6"
    ],
    "fill": "#ffc7c0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 586,
    "tag": "path",
    "id": "shape-252",
    "groups": [
      "g@6"
    ],
    "fill": "#ffc7c0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 587,
    "tag": "path",
    "id": "shape-253",
    "groups": [
      "g@6"
    ],
    "fill": "#e45551",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\plankgaming_512\123_plankgaming_512_src\03_rebuilt_filled.svg`

- SHA-256: `a265aa572f3c75fa951ab1fe6fba6730e44fa210120e46e176089e7df4ee07a2`
- Bytes: 24850
- Root size: `512` × `227`; viewBox `0 0 512 227`
- Graphics: 72; groups: 3; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 1
- Clip/mask references or definitions: 0
- Transformed elements: 7
- Coordinate precision: `{"count": 1103, "min": 0, "median": 1, "p90": 1, "max": 6}`

### Element vocabulary

```json
{
  "path": 65,
  "stop": 54,
  "linearGradient": 26,
  "rect": 6,
  "g": 3,
  "svg": 1,
  "defs": 1,
  "radialGradient": 1,
  "ellipse": 1
}
```

### Path commands

```json
{
  "L": 425,
  "M": 66,
  "Z": 38,
  "C": 5,
  "A": 2,
  "Q": 2
}
```

### Native parameterized elements

```json
{
  "rect": 6,
  "ellipse": 1
}
```

### Fill-rule counts

```json
{
  "evenodd": 37,
  "default/nonzero": 35
}
```

### Notes

- Found early/narrow stroke-only elements consistent with a gap-filler layer; inspect colors and adjacency manually.
- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f6d98f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f3cf60",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f3cf60",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ebc860",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eed28f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ebc860",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f3cf60",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f6d98f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f6d98f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ebc860",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a48006",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#a48006",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  }
]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f6d98f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f3cf60",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#f3cf60",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ebc860",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#eed28f",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#ebc860",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "none",
    "stroke": "#e9b70b",
    "stroke_width": "0.350",
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 60,
    "tag": "path",
    "id": "shape-41",
    "groups": [
      "g@1"
    ],
    "fill": "#f1bf0b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": "shape-42",
    "groups": [
      "g@1"
    ],
    "fill": "#f6dd84",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": "shape-45",
    "groups": [
      "g@1"
    ],
    "fill": "#fbefc4",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": "shape-47",
    "groups": [
      "g@1"
    ],
    "fill": "#fbefc4",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": "shape-48",
    "groups": [
      "g@1"
    ],
    "fill": "#f6dd84",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": "shape-49",
    "groups": [
      "g@1"
    ],
    "fill": "#f6dd84",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": "shape-50",
    "groups": [
      "g@1"
    ],
    "fill": "#f1bf0b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": "shape-51",
    "groups": [
      "g@1"
    ],
    "fill": "#f1bf0b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": "shape-52",
    "groups": [
      "g@1"
    ],
    "fill": "#f1bf0b",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": "shape-53",
    "groups": [
      "g@1"
    ],
    "fill": "#fbefc4",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": "shape-29",
    "groups": [
      "g@2"
    ],
    "fill": "url(#gradient-appearance-shape-29)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": "shape-30",
    "groups": [
      "g@3"
    ],
    "fill": "url(#gradient-appearance-shape-30)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice part\benchmarks\vai_work\scene\your_logo\128_your_logo_src\03_rebuilt_filled.svg`

- SHA-256: `fad685142b266e5adc99b72868643a8f44b11a8d608b92d584b7db5e880d61de`
- Bytes: 30709
- Root size: `255` × `153`; viewBox `0 0 255 153`
- Graphics: 13; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 6
- Clip/mask references or definitions: 0
- Transformed elements: 2
- Coordinate precision: `{"count": 2464, "min": 0, "median": 6.0, "p90": 6, "max": 6}`

### Element vocabulary

```json
{
  "stop": 20,
  "path": 11,
  "radialGradient": 6,
  "linearGradient": 4,
  "rect": 2,
  "svg": 1,
  "defs": 1,
  "g": 1
}
```

### Path commands

```json
{
  "L": 1199,
  "M": 23,
  "Z": 23
}
```

### Native parameterized elements

```json
{
  "rect": 2
}
```

### Fill-rule counts

```json
{
  "evenodd": 11,
  "default/nonzero": 2
}
```

### Notes

- Native SVG parameterized elements are present; compare with a flattened export before inferring the internal detector.
- Filled paths with multiple subpaths exist, consistent with compound paths/cutouts/holes.

### Exact repeated path groups

```json
[]
```

### Potential gap-filler strokes

```json
[]
```

### First draw-order elements

```json
[
  {
    "index": 0,
    "tag": "path",
    "id": "shape-0",
    "groups": [
      "g@1"
    ],
    "fill": "#f75819",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 6,
    "commands": {
      "M": 6,
      "L": 344,
      "Z": 6
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "#f75819",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 57,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-3)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "#f75819",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 4,
    "commands": {
      "M": 4,
      "L": 219,
      "Z": 4
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": "shape-5",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-5)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "rect",
    "id": "shape-4",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-4)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 123 106)"
  },
  {
    "index": 6,
    "tag": "path",
    "id": "shape-7",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-7)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": "shape-6",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-6)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": "shape-8",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-8)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 21,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": "shape-9",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-9)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 17,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "rect",
    "id": "shape-11",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-11)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 135.5 105.5)"
  },
  {
    "index": 11,
    "tag": "path",
    "id": "shape-10",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-10)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 27,
      "Z": 1
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 1,
    "tag": "path",
    "id": "shape-2",
    "groups": [
      "g@1"
    ],
    "fill": "#f75819",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 57,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": "shape-3",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-3)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": "shape-1",
    "groups": [
      "g@1"
    ],
    "fill": "#f75819",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 4,
    "commands": {
      "M": 4,
      "L": 219,
      "Z": 4
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": "shape-5",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-5)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "rect",
    "id": "shape-4",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-4)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 123 106)"
  },
  {
    "index": 6,
    "tag": "path",
    "id": "shape-7",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-7)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": "shape-6",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-6)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "L": 126,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": "shape-8",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-8)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 21,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": "shape-9",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-9)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 17,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "rect",
    "id": "shape-11",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-11)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "rotate(-90 135.5 105.5)"
  },
  {
    "index": 11,
    "tag": "path",
    "id": "shape-10",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-10)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 27,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": "shape-12",
    "groups": [
      "g@1"
    ],
    "fill": "url(#gradient-appearance-shape-12)",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 10,
      "Z": 1
    },
    "transform": null
  }
]
```

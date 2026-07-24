# SVG structural forensics report

> Heuristics are deliberately conservative. A structural pattern is evidence about an export, not proof of the proprietary internal implementation.

## `C:\Users\nirrt\Toolset\v-ice pictures\challenge_pack\plates\plate_01_vai.svg`

- SHA-256: `e18e246a996697ec30e0efc3718eb65f7e34074e423f8bc48598230539c58b38`
- Bytes: 793365
- Root size: `None` × `None`; viewBox `0.00 0.00 1620.00 1044.00`
- Graphics: 1530; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 136
- Clip/mask references or definitions: 0
- Transformed elements: 75
- Coordinate precision: `{"count": 107018, "min": 0, "median": 2.0, "p90": 2, "max": 4}`

### Element vocabulary

```json
{
  "path": 1408,
  "circle": 44,
  "ellipse": 40,
  "rect": 38,
  "svg": 1,
  "g": 1
}
```

### Path commands

```json
{
  "A": 8641,
  "L": 5249,
  "Q": 4620,
  "C": 2139,
  "M": 1952,
  "Z": 1086
}
```

### Native parameterized elements

```json
{
  "circle": 44,
  "ellipse": 40,
  "rect": 38
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 1530
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 8,
      "A": 2,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#a6d4f0",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 34,
      "C": 32,
      "A": 53,
      "L": 15
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#afbfdf",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "A": 5,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5,
      "A": 6,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 4
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5,
      "A": 6,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 22,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "A": 5,
      "Q": 1,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "A": 5,
      "Q": 1,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 24,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 2
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 4,
      "Q": 6,
      "A": 2
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "A": 8,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8,
      "A": 9,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "A": 8,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "A": 8,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 2,
      "A": 4,
      "Q": 4
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 8,
      "L": 6,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3,
      "A": 7,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#afbfdf",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 2,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 2
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 2,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#afbfdf",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 2,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 2
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 12,
      "L": 6,
      "Q": 7,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "A": 5,
      "Q": 5,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffa380",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 10,
      "A": 22,
      "Q": 22,
      "L": 6
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#cbe5a5",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 4,
      "A": 4,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#afbfdf",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 4,
      "A": 4,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#afbfdf",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 4,
      "A": 4,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#888c93",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5,
      "A": 6,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#cbe5a5",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 4,
      "A": 4,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 9,
      "Q": 3,
      "C": 10,
      "L": 3
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#afbfdf",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8,
      "A": 9,
      "Q": 3,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 12,
      "A": 10,
      "Q": 12
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 12,
      "L": 12
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 12,
      "A": 12
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#888c93",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "A": 6,
      "C": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#888c93",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "A": 5,
      "Q": 1,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 10,
      "A": 25,
      "L": 12,
      "Q": 6
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#888c93",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 9,
      "Q": 2,
      "C": 1,
      "L": 7
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fee383",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#93d7b0",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffdbb9",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#dc9093",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#dc9093",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#93d7b0",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fee383",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#7e6303",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#92ba33",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#706843",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#93b269",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#5d396e",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#db6c4c",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#01295b",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6a6ae",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 8,
      "A": 2,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#a6d4f0",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 34,
      "C": 32,
      "A": 53,
      "L": 15
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#afbfdf",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#80a8da",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "A": 5,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5,
      "A": 6,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#808080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
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
    "index": 1518,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#fe4601",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "A": 5,
      "C": 5,
      "Q": 1,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1519,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#fe4601",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "Q": 4,
      "A": 11,
      "L": 9,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 1520,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#fe4601",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 8,
      "A": 10,
      "L": 6,
      "C": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1521,
    "tag": "rect",
    "id": null,
    "groups": [],
    "fill": "#fe4601",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(374.50,962.90) rotate(0.1)"
  },
  {
    "index": 1522,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#fe4601",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 6,
      "A": 8,
      "L": 6,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1523,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#ff8e00",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "C": 1,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1524,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "A": 3,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1525,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#ff8e00",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 5,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1526,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#ff0100",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "Q": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1527,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#fe4601",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 8,
      "A": 6,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1528,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#ff0100",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "C": 3,
      "Q": 4,
      "A": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1529,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#ff0100",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 3,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice pictures\challenge_pack\plates\plate_02_vai.svg`

- SHA-256: `064b32ed253421ab7d2c4a07ca47898e5d6f90831892571321d86f8c235b6a4f`
- Bytes: 518819
- Root size: `None` × `None`; viewBox `0.00 0.00 1620.00 1132.00`
- Graphics: 1176; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 59
- Clip/mask references or definitions: 0
- Transformed elements: 151
- Coordinate precision: `{"count": 67269, "min": 0, "median": 2, "p90": 2, "max": 4}`

### Element vocabulary

```json
{
  "path": 985,
  "ellipse": 138,
  "circle": 33,
  "rect": 20,
  "svg": 1,
  "g": 1
}
```

### Path commands

```json
{
  "A": 5206,
  "Q": 3456,
  "L": 2696,
  "M": 1378,
  "C": 1203,
  "Z": 698
}
```

### Native parameterized elements

```json
{
  "ellipse": 138,
  "circle": 33,
  "rect": 20
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 1176
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef8080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1,
      "C": 1,
      "A": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffe680",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fdc488",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f89898",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f65c20",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f86e28",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e81818",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fdab09",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fdb532",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fd9a18",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffcb57",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffd690",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef5610",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffd82a",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffe670",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1,
      "A": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8ab62c",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffe670",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffc73a",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef6701",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffbd11",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffe680",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffdb47",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fff4c6",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#b3d9a2",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8ac582",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#b3ce69",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fff4c6",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8aba49",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e2d7a9",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#818d9a",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8aba49",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#0c5e56",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "Q": 2,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#3e9e25",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8aba49",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#3e9e25",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#6ca765",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8c8690",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#647bb6",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2c3d81",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#0c5e56",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#357276",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#346930",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef8080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1,
      "C": 1,
      "A": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffd690",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f89898",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f86e28",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e81818",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef5610",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffbd11",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffc73a",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "C": 1,
      "A": 2,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffd690",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffbd11",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef5610",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef6701",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffe680",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffdb47",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffd82a",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffe670",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8ab62c",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fff1a9",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fff4c6",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8aba49",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1,
      "A": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e2d7a9",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#818d9a",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8aba49",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#0c5e56",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "C": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#346930",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#6ca765",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8ac582",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#647bb6",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2c3d81",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8c8690",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ff8e81",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f2b5a7",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef8080",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#c48081",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef8080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f89898",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e81818",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f89898",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e81818",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1,
      "A": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#eb4d3f",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#b40001",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e23527",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef8080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e23527",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef8080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "A": 3
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e23527",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef8080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f2b5a7",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f2b5a7",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "A": 2,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f6c8b2",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "C": 1,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f2b5a7",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f89898",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef8080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#c48081",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 7,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef8080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f89898",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f2b5a7",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#eb4d3f",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ef8080",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1,
      "C": 1,
      "A": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffe680",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fdc488",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f89898",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f65c20",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#f86e28",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 6,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e81818",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fdab09",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fdb532",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#fd9a18",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffcb57",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ffd690",
    "stroke_width": null,
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

### Last draw-order elements

```json
[
  {
    "index": 1164,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#c4c4c5",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(636.25,1015.21) rotate(-179.9)"
  },
  {
    "index": 1165,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#c4c4c5",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1166,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#c4c4c5",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(627.51,1015.19) rotate(-177.7)"
  },
  {
    "index": 1167,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#c4c4c5",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(645.31,1015.18) rotate(-177.6)"
  },
  {
    "index": 1168,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#2e8b57",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 9,
      "A": 1,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1169,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#2e8b57",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 6,
      "L": 2,
      "A": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1170,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#2e8b57",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 5,
      "A": 1,
      "C": 1,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1171,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#c4c4c5",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(75.73,1048.46) rotate(-0.7)"
  },
  {
    "index": 1172,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#c4c4c5",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(360.35,1048.53) rotate(-2.1)"
  },
  {
    "index": 1173,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#c4c4c5",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(885.46,1048.54) rotate(-2.5)"
  },
  {
    "index": 1174,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#c4c4c5",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(894.42,1048.59) rotate(-180.2)"
  },
  {
    "index": 1175,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#68a5ab",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1,
      "A": 2,
      "L": 1,
      "Z": 1
    },
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice pictures\challenge_pack\plates\plate_03_vai.svg`

- SHA-256: `c3c9e50fe93560e695f2ea4f9f3ca7ceddbb42ff8d40be69e8b9b19762f70103`
- Bytes: 548398
- Root size: `None` × `None`; viewBox `0.00 0.00 1620.00 1228.00`
- Graphics: 1443; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 27
- Clip/mask references or definitions: 0
- Transformed elements: 552
- Coordinate precision: `{"count": 66598, "min": 0, "median": 2.0, "p90": 4, "max": 4}`

### Element vocabulary

```json
{
  "path": 829,
  "rect": 422,
  "ellipse": 176,
  "circle": 16,
  "svg": 1,
  "g": 1
}
```

### Path commands

```json
{
  "A": 5995,
  "L": 3932,
  "Q": 1641,
  "M": 1515,
  "Z": 778,
  "C": 276
}
```

### Native parameterized elements

```json
{
  "rect": 422,
  "ellipse": 176,
  "circle": 16
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 1443
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 3
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 5,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 5,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 5,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e09c95",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 5,
      "A": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 14,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 2,
      "A": 2,
      "Q": 5
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 1,
      "A": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 1,
      "A": 1,
      "Q": 5,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 21,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 5,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 23,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 25,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 6,
      "A": 10,
      "Q": 11
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 1,
      "L": 1
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#763a40",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#2d6356",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 2,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 4,
      "C": 3
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 5,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 7,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 5,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#97c5ab",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 5,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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

### Last draw-order elements

```json
[
  {
    "index": 1431,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#dbe4f0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(358.45,1091.56) rotate(-178.4)"
  },
  {
    "index": 1432,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#dbe4f0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(364.42,1091.55) rotate(-177.6)"
  },
  {
    "index": 1433,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#dbe4f0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(370.31,1091.53) rotate(-176.5)"
  },
  {
    "index": 1434,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#dbe4f0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(376.25,1091.51) rotate(-177.3)"
  },
  {
    "index": 1435,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#dbe4f0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(382.03,1091.51) rotate(-176.6)"
  },
  {
    "index": 1436,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#dbe4f0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 2,
      "Q": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1437,
    "tag": "ellipse",
    "id": null,
    "groups": [],
    "fill": "#dbe4f0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(133.29,1091.54) rotate(-178.3)"
  },
  {
    "index": 1438,
    "tag": "circle",
    "id": null,
    "groups": [],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 1439,
    "tag": "circle",
    "id": null,
    "groups": [],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 1440,
    "tag": "circle",
    "id": null,
    "groups": [],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 1441,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#f2e3c6",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 2,
      "Z": 1
    },
    "transform": null
  },
  {
    "index": 1442,
    "tag": "circle",
    "id": null,
    "groups": [],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  }
]
```

## `C:\Users\nirrt\Toolset\v-ice pictures\challenge_pack\plates\plate_04_vai.svg`

- SHA-256: `8b1f8ced619bc5b3fabe46731aa1b76e6d39b4d38e799c4aab3993ee60ebe4ed`
- Bytes: 439870
- Root size: `None` × `None`; viewBox `0.00 0.00 1620.00 1180.00`
- Graphics: 1030; groups: 1; max group depth: 1
- Export-mode clue: **cutout-like (heuristic)**
- Multi-subpath filled paths: 75
- Clip/mask references or definitions: 0
- Transformed elements: 207
- Coordinate precision: `{"count": 55688, "min": 0, "median": 2.0, "p90": 4, "max": 4}`

### Element vocabulary

```json
{
  "path": 761,
  "rect": 226,
  "ellipse": 35,
  "circle": 8,
  "svg": 1,
  "g": 1
}
```

### Path commands

```json
{
  "A": 4549,
  "L": 3969,
  "Q": 2304,
  "M": 1108,
  "Z": 514,
  "C": 351
}
```

### Native parameterized elements

```json
{
  "rect": 226,
  "ellipse": 35,
  "circle": 8
}
```

### Fill-rule counts

```json
{
  "default/nonzero": 1030
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#818282",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 10,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#171f2d",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#76797d",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 12,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#171f2d",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8b94a5",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e09c95",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1,
      "Q": 2,
      "A": 3,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e09c95",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 7,
      "A": 6,
      "C": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3,
      "A": 2
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e09c95",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "A": 8,
      "C": 4,
      "Q": 8
    },
    "transform": null
  },
  {
    "index": 12,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 3,
      "A": 2
    },
    "transform": null
  },
  {
    "index": 13,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e09c95",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1,
      "A": 2,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 15,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e09c95",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3,
      "A": 5,
      "L": 3,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 16,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3
    },
    "transform": null
  },
  {
    "index": 17,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e09c95",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "A": 6,
      "Q": 3,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 18,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 5,
      "A": 6,
      "Q": 3
    },
    "transform": null
  },
  {
    "index": 19,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#763a40",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 20,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ce8f8e",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ce8f8e",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ce8f8e",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ce8f8e",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#ce8f8e",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 26,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 27,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 28,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 29,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 30,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 31,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 32,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 33,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 34,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 35,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 36,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 37,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 38,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 39,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 40,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 41,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 42,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 43,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 44,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 45,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 46,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 47,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 48,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 49,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 50,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 51,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 52,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 53,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 54,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 55,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 56,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 57,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 58,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 59,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 60,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 61,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 62,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 63,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 64,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 65,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 66,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 67,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 68,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 69,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 70,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 71,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 72,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 73,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 74,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 75,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 76,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 77,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 78,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 79,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 80,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 81,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 82,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 83,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 84,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 85,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 86,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 87,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 88,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 89,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 90,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 91,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 92,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 93,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 94,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 95,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 96,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 97,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 98,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 99,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "A": 4,
      "L": 4
    },
    "transform": null
  },
  {
    "index": 1,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#959daa",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#818282",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 10,
      "C": 2
    },
    "transform": null
  },
  {
    "index": 3,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#171f2d",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 1
    },
    "transform": null
  },
  {
    "index": 4,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#76797d",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 12,
      "C": 1
    },
    "transform": null
  },
  {
    "index": 5,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#171f2d",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#8b94a5",
    "stroke_width": null,
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
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e09c95",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "C": 1,
      "Q": 2,
      "A": 3,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 8,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 2,
      "A": 1
    },
    "transform": null
  },
  {
    "index": 9,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e09c95",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 7,
      "A": 6,
      "C": 1,
      "L": 2
    },
    "transform": null
  },
  {
    "index": 10,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#edf2f8",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "Q": 3,
      "A": 2
    },
    "transform": null
  },
  {
    "index": 11,
    "tag": "path",
    "id": null,
    "groups": [
      "g@1"
    ],
    "fill": null,
    "stroke": "#e09c95",
    "stroke_width": null,
    "vector_effect": "non-scaling-stroke",
    "subpaths": 1,
    "commands": {
      "M": 1,
      "L": 4,
      "A": 8,
      "C": 4,
      "Q": 8
    },
    "transform": null
  }
]
```

### Last draw-order elements

```json
[
  {
    "index": 1018,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#2b3a55",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "A": 24,
      "Q": 18,
      "L": 18,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 1019,
    "tag": "rect",
    "id": null,
    "groups": [],
    "fill": "#dbe4f0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 1020,
    "tag": "rect",
    "id": null,
    "groups": [],
    "fill": "#dbe4f0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(305.70,1024.61) rotate(0.1)"
  },
  {
    "index": 1021,
    "tag": "rect",
    "id": null,
    "groups": [],
    "fill": "#dbe4f0",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(461.80,1024.61) rotate(-0.1)"
  },
  {
    "index": 1022,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#2b3a55",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "A": 8,
      "L": 8,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 1023,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#2b3a55",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "A": 8,
      "L": 8,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 1024,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#2b3a55",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "A": 8,
      "L": 8,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 1025,
    "tag": "path",
    "id": null,
    "groups": [],
    "fill": "#2b3a55",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 2,
    "commands": {
      "M": 2,
      "A": 8,
      "L": 8,
      "Z": 2
    },
    "transform": null
  },
  {
    "index": 1026,
    "tag": "rect",
    "id": null,
    "groups": [],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 1027,
    "tag": "rect",
    "id": null,
    "groups": [],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  },
  {
    "index": 1028,
    "tag": "rect",
    "id": null,
    "groups": [],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": "translate(416.27,1109.61) rotate(0.1)"
  },
  {
    "index": 1029,
    "tag": "rect",
    "id": null,
    "groups": [],
    "fill": "#ffffff",
    "stroke": null,
    "stroke_width": null,
    "vector_effect": null,
    "subpaths": 0,
    "commands": {},
    "transform": null
  }
]
```

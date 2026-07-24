"""Fast synthetic contracts for V-ICE Strike-0 instrumentation."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cv2
import numpy as np

import benchmark_vai as bv


ROOT = Path(__file__).resolve().parent


def _canvas() -> np.ndarray:
    return np.full((72, 96, 3), 255, np.uint8)


def test_persistent_counter_loss_and_catastrophic_tail() -> None:
    source = _canvas()
    cv2.circle(source, (28, 36), 16, (10, 10, 10), 5, cv2.LINE_AA)
    good = source.copy()
    bad = source.copy()
    cv2.circle(bad, (28, 36), 13, (10, 10, 10), -1, cv2.LINE_AA)

    good_topology = bv.persistent_topology_meter(good, source)
    bad_topology = bv.persistent_topology_meter(bad, source)
    assert good_topology["persistent_beta1_error"] == 0
    assert bad_topology["persistent_beta1_error"] > 0
    assert bad_topology["any_counter_failure"] is True

    good_tail = bv.catastrophic_locus_meter(good, source)
    bad_tail = bv.catastrophic_locus_meter(bad, source)
    assert good_tail["catastrophic_locus_rate"] == 0
    assert bad_tail["catastrophic_locus_rate"] > 0
    assert bad_tail["boundary_cvar10"] > good_tail["boundary_cvar10"]


def test_repeated_width_violation() -> None:
    source = _canvas()
    for x in (12, 40, 68):
        cv2.rectangle(source, (x, 18), (x + 9, 54), (15, 15, 15), -1)
    good = source.copy()
    bad = source.copy()
    cv2.rectangle(bad, (68, 18), (68 + 16, 54), (15, 15, 15), -1)

    good_meter = bv.group_regularity_meter(good, source)
    bad_meter = bv.group_regularity_meter(bad, source)
    assert good_meter["group_regularity_violation"] == 0
    assert bad_meter["equal_width_violation"] > 0
    assert bad_meter["group_regularity_violation"] > good_meter["group_regularity_violation"]


def test_live_court_contract() -> None:
    manifest = json.loads((ROOT / "benchmarks" / "vai_crop_court_manifest.json")
                          .read_text(encoding="utf-8"))
    assert manifest["version"] >= 2
    assert manifest["display_contract"]["candidate"] == "live SVG"
    assert manifest["display_contract"]["candidate_prerasterization"] is False
    assert manifest["display_contract"]["default_scale"] == 2.0
    assert manifest["display_contract"]["scales"] == [0.5, 1.0, 2.0]
    for item in manifest["items"]:
        case = int(item["case"])
        assert (ROOT / "web_preview" / "court_assets" /
                f"case_{case:02d}_a.svg").is_file()
        assert (ROOT / "web_preview" / "court_assets" /
                f"case_{case:02d}_b.svg").is_file()


def test_svg_geometry_parser_includes_native_shapes_and_transforms() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as directory:
        target = Path(directory) / "native.svg"
        target.write_text("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60">
          <g transform="translate(10 5) scale(2)">
            <circle cx="10" cy="10" r="5"/>
            <rect x="20" y="4" width="12" height="8" rx="2"/>
          </g>
        </svg>""", encoding="utf-8")
        paths = bv._parse_paths(target)
        assert len(paths) == 2
        xmin, xmax, ymin, ymax = paths[0].bbox()
        assert max(abs(xmin - 20), abs(xmax - 40),
                   abs(ymin - 15), abs(ymax - 35)) < .1
        meters = bv.geometry_meters(target, 100)
        assert meters["segments"] and meters["total_len"] > 0


def main() -> int:
    test_persistent_counter_loss_and_catastrophic_tail()
    test_repeated_width_violation()
    test_live_court_contract()
    test_svg_geometry_parser_includes_native_shapes_and_transforms()
    print("Strike-0 metrics + live-court contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

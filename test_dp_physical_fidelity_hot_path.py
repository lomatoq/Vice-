"""Production-path guard for density-invariant paper-DP fidelity costs."""

from __future__ import annotations

import ast
import inspect
import textwrap

import geometry_vectorizer as gv
import numpy as np


def test_scale_switch_is_physical_and_reversible() -> None:
    old = gv._DP_PHYSICAL_FIDELITY
    try:
        gv._DP_PHYSICAL_FIDELITY = True
        assert gv._dp_fidelity_scale(0.25) == 0.25
        assert gv._dp_fidelity_scale(1.0) == 1.0
        gv._DP_PHYSICAL_FIDELITY = False
        assert gv._dp_fidelity_scale(0.25) == 1.0
        assert gv._dp_fidelity_scale(1.0) == 1.0
    finally:
        gv._DP_PHYSICAL_FIDELITY = old


def test_all_six_primitive_costs_use_the_segment_scale() -> None:
    """Line, arc, earc, clothoid, biarc and cubic must share one measure."""
    source = textwrap.dedent(inspect.getsource(gv.fit_segment_midpoints))
    tree = ast.parse(source)
    scale_initializers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_dp_fidelity_scale"
    ]
    scale_uses = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id == "fidelity_px"
    ]
    assert len(scale_initializers) == 1
    assert len(scale_uses) == 6


def test_sampling_measure_is_not_the_accuracy_tube() -> None:
    """A strict 0.15px tube on a native chain still represents 1px samples."""
    native = np.column_stack((np.arange(12, dtype=float), np.zeros(12)))
    dense4 = np.column_stack((np.arange(48, dtype=float) / 4.0, np.zeros(48)))
    assert gv._dp_sampling_measure(native) == 1.0
    assert gv._dp_sampling_measure(dense4) == 0.25
    source = textwrap.dedent(inspect.getsource(gv.fit_segment_midpoints))
    assert "_dp_fidelity_scale(px)" not in source
    assert "strict_interval" in source


if __name__ == "__main__":
    test_scale_switch_is_physical_and_reversible()
    test_all_six_primitive_costs_use_the_segment_scale()
    test_sampling_measure_is_not_the_accuracy_tube()
    print("DP physical-fidelity hot-path checks: PASS")

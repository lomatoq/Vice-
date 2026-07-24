"""Regression checks for the production native-unit / dense-lattice contract."""
from __future__ import annotations

import numpy as np

import geometry_vectorizer as gv
from shadow_rf_corners import _synth_loops, to_db4


def main() -> int:
    for name, native in _synth_loops().items():
        lattice = to_db4(native)
        assert lattice is not None, name
        dense_native = lattice / 4.0
        requant, world = gv._requantize_native_density_loop(dense_native, 4)
        extent_in = (np.ptp(dense_native[:, 0]) + np.ptp(dense_native[:, 1])) / 2.0
        extent_out = (np.ptp(world[:, 0]) + np.ptp(world[:, 1])) / 2.0
        assert 0.9 <= extent_out / extent_in <= 1.1, (name, extent_in, extent_out)
        assert len(requant) >= 24, name

    # A caller-unit mistake must be visible to the explicit fixed-D3 helper.
    loop = _synth_loops()["rect(4)"]
    try:
        gv._requantize_native_density_loop(loop, lattice_scale=4)
    except AssertionError as exc:
        assert "density contract mismatch" in str(exc)
    else:
        raise AssertionError("unit mismatch was silently accepted")
    print("native density contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

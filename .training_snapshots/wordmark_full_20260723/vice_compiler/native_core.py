"""ctypes bridge to dependency-free Rust runtime kernels.

The compiler stays fail-open: a source checkout without a compiled library
uses exact Python/Numpy fallbacks, while production builds expose and exercise
the same deterministic API through Rust.
"""

from __future__ import annotations

import ctypes
from pathlib import Path
import sys
from typing import Iterable

import numpy as np


PROJECT = Path(__file__).resolve().parents[1]
_NATIVE_ROOT = PROJECT / "native" / "pcdc_native_core"


def _library_names() -> tuple[str, ...]:
    if sys.platform == "win32":
        return ("pcdc_native_core.dll",)
    if sys.platform == "darwin":
        return ("libpcdc_native_core.dylib",)
    return ("libpcdc_native_core.so",)


def _load() -> ctypes.CDLL | None:
    candidates = []
    for profile in ("release", "debug"):
        candidates.extend(
            _NATIVE_ROOT / "target" / profile / name
            for name in _library_names()
        )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            library = ctypes.CDLL(str(path))
            library.pcdc_native_version.restype = ctypes.c_uint32
            library.pcdc_conflict_masks.argtypes = (
                ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t,
                ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint64),
                ctypes.c_size_t,
            )
            library.pcdc_conflict_masks.restype = ctypes.c_int32
            library.pcdc_circle_sdf.argtypes = (
                ctypes.POINTER(ctypes.c_double), ctypes.c_size_t,
                ctypes.c_double, ctypes.c_double, ctypes.c_double,
                ctypes.POINTER(ctypes.c_double),
            )
            library.pcdc_circle_sdf.restype = ctypes.c_int32
            library.pcdc_pack_atlas.argtypes = (
                ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t,
                ctypes.c_uint32, ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.POINTER(ctypes.c_uint32),
            )
            library.pcdc_pack_atlas.restype = ctypes.c_int32
            if int(library.pcdc_native_version()) == 1:
                return library
        except (OSError, AttributeError):
            continue
    return None


_LIB = _load()


def available() -> bool:
    return _LIB is not None


def backend_summary() -> dict[str, object]:
    return {
        "available": available(),
        "version": int(_LIB.pcdc_native_version()) if _LIB is not None else None,
        "language": "rust" if _LIB is not None else "python-fallback",
        "kernels": ("conflict-bitsets", "circle-sdf", "atlas-pack"),
    }


def conflict_masks(core_bits: Iterable[int]) -> tuple[int, ...]:
    rows = tuple(int(value) for value in core_bits)
    if not rows:
        return ()
    support_words = max(1, (max(value.bit_length() for value in rows) + 63) // 64)
    packed = np.zeros((len(rows), support_words), np.uint64)
    for row_index, bits in enumerate(rows):
        for word in range(support_words):
            packed[row_index, word] = (bits >> (64 * word)) & ((1 << 64) - 1)
    if _LIB is None:
        result = []
        for first, first_bits in enumerate(rows):
            mask = 0
            for second, second_bits in enumerate(rows):
                if first != second and first_bits & second_bits:
                    mask |= 1 << second
            result.append(mask)
        return tuple(result)
    output_words = (len(rows) + 63) // 64
    output = np.zeros((len(rows), output_words), np.uint64)
    status = _LIB.pcdc_conflict_masks(
        packed.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)), len(rows),
        support_words,
        output.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)), output_words,
    )
    if status != 0:
        raise RuntimeError(f"native conflict kernel failed: {status}")
    return tuple(
        int.from_bytes(output[index].tobytes(), "little")
        for index in range(len(rows))
    )


def circle_sdf(
    points_xy: np.ndarray, center: tuple[float, float], radius: float,
) -> np.ndarray:
    points = np.ascontiguousarray(points_xy, np.float64).reshape((-1, 2))
    if _LIB is None:
        return np.linalg.norm(points - np.asarray(center), axis=1) - float(radius)
    output = np.empty(len(points), np.float64)
    status = _LIB.pcdc_circle_sdf(
        points.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), len(points),
        float(center[0]), float(center[1]), float(radius),
        output.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
    )
    if status != 0:
        raise RuntimeError(f"native circle SDF kernel failed: {status}")
    return output


def pack_atlas(
    sizes_wh: Iterable[tuple[int, int]], *, target_width: int, padding: int,
) -> tuple[tuple[tuple[int, int, int, int], ...], tuple[int, int]]:
    sizes = np.ascontiguousarray(tuple(sizes_wh), np.uint32).reshape((-1, 2))
    if not len(sizes):
        raise ValueError("cannot pack an empty atlas")
    if _LIB is None:
        x = y = row_height = atlas_width = 0
        rows = []
        for width, height in sizes.tolist():
            if x and x + width > target_width:
                x = 0; y += row_height + padding; row_height = 0
            rows.append((x, y, x + width, y + height))
            atlas_width = max(atlas_width, x + width)
            x += width + padding; row_height = max(row_height, height)
        return tuple(rows), (atlas_width, y + row_height)
    output = np.zeros((len(sizes), 4), np.uint32)
    atlas = np.zeros(2, np.uint32)
    status = _LIB.pcdc_pack_atlas(
        sizes.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)), len(sizes),
        int(target_width), int(padding),
        output.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
        atlas.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
    )
    if status != 0:
        raise RuntimeError(f"native atlas kernel failed: {status}")
    placements = tuple(tuple(int(value) for value in row) for row in output)
    return placements, (int(atlas[0]), int(atlas[1]))

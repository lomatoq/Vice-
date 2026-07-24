"""Contract test for the native-coordinate JPEG grid estimator."""

from __future__ import annotations

import io
import unittest

import cv2
import numpy as np
from PIL import Image

from geometry_vectorizer import estimate_jpeg_grid


def _q30_field(width: int = 208, height: int = 208) -> Image.Image:
    """A smooth design-like field whose q30 blocking is observable."""
    yy, xx = np.mgrid[:height, :width].astype(np.float32)
    rng = np.random.default_rng(73021)
    noise = cv2.GaussianBlur(rng.normal(0.0, 1.0, (height, width)).astype(np.float32),
                             (0, 0), 7.0)
    base = 128.0 + 42.0 * np.sin(xx / 31.0) + 31.0 * np.cos(yy / 27.0) + 90.0 * noise
    rgb = np.stack((base, 0.82 * base + 23.0, 0.65 * base + 47.0), axis=2)
    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
    stream = io.BytesIO()
    image.save(stream, "JPEG", quality=30, subsampling=0)
    return Image.open(io.BytesIO(stream.getvalue())).convert("RGB")


class JpegGridContractTest(unittest.TestCase):
    def test_q30_phase_survives_native_crop(self) -> None:
        encoded = _q30_field()
        shift_x, shift_y = 3, 5
        crop = encoded.crop((shift_x, shift_y, shift_x + 192, shift_y + 192))
        result = estimate_jpeg_grid(crop, periods=(8,))
        self.assertEqual(result["period"], 8)
        self.assertEqual(result["phase_x"], (-shift_x) % 8)
        self.assertEqual(result["phase_y"], (-shift_y) % 8)
        self.assertGreater(result["confidence"], 0.10)

    def test_analysis_scale_mapping_is_explicit(self) -> None:
        encoded = _q30_field(192, 192)
        result = estimate_jpeg_grid(encoded, periods=(8,))
        self.assertEqual(result["phase_x"], 0)
        self.assertEqual(result["phase_y"], 0)
        # A native boundary x maps to x*4 on the deblur lattice, never x*4+1.
        self.assertEqual(result["phase_x"] * 4, 0)


if __name__ == "__main__":
    unittest.main()

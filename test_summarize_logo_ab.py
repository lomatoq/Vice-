import unittest

import numpy as np

from summarize_logo_ab import image_metrics


class LogoAbMetricTests(unittest.TestCase):
    def test_identical_images_have_no_changed_pixels(self):
        image = np.full((8, 9, 3), 123, dtype=np.uint8)
        metrics = image_metrics(image, image.copy())
        self.assertEqual(metrics["changed_pixels"], 0)
        self.assertEqual(metrics["changed_fraction"], 0.0)
        self.assertEqual(metrics["ssim"], 1.0)

    def test_one_changed_pixel_is_counted(self):
        first = np.zeros((8, 9, 3), dtype=np.uint8)
        second = first.copy()
        second[3, 4] = 255
        metrics = image_metrics(first, second)
        self.assertEqual(metrics["changed_pixels"], 1)
        self.assertAlmostEqual(metrics["changed_fraction"], 1 / 72, places=6)


if __name__ == "__main__":
    unittest.main()

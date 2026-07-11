import json
import tempfile
import unittest
from pathlib import Path

from build_corner_dataset import _write_review


class CornerReviewStorageTests(unittest.TestCase):
    def test_review_storage_is_namespaced_by_manifest_dataset(self):
        with tempfile.TemporaryDirectory(dir="tmp") as directory:
            preview = Path(directory)
            _write_review(preview, [], {"files": 0}, "rotated-glyph-pilot")
            page = (preview / "index.html").read_text(encoding="utf-8")
            manifest = json.loads((preview / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["dataset"], "rotated-glyph-pilot")
        self.assertIn("cornerGtReview:${namespace}", page)
        self.assertIn("loadDatasetStorage(data.dataset)", page)
        self.assertNotIn("localStorage.getItem('cornerGtReview')", page)
        self.assertNotIn("localStorage.setItem('cornerGtReview'", page)


if __name__ == "__main__":
    unittest.main()

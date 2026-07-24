from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from fontTools.ttLib import TTFont

from vice_compiler.font_license_manifest import validate_manifest
from vice_compiler.wordmark_prior import WORDMARK_CHARACTERS


class FontLicenseManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path("fonts/google-fonts-manifest.json")
        self.manifest = json.loads(self.path.read_text("utf-8"))

    def test_sparse_open_font_bank_is_hash_and_license_bound(self) -> None:
        validate_manifest(self.manifest)
        self.assertGreaterEqual(self.manifest["family_count"], 80)
        self.assertGreaterEqual(self.manifest["font_count"], 240)
        self.assertNotEqual(self.manifest["source_revision"], "unversioned")
        self.assertEqual(
            {row["license"] for row in self.manifest["fonts"]},
            {"OFL-1.1", "Ubuntu-Font-License-1.0"},
        )

    def test_tampered_font_identity_fails_closed(self) -> None:
        damaged = deepcopy(self.manifest)
        damaged["fonts"][0]["font_sha256"] = "0" * 64
        # Re-sealing the outer JSON cannot make incorrect font bytes valid.
        import hashlib
        payload = dict(damaged)
        payload.pop("content_sha256", None)
        damaged["content_sha256"] = hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "font bytes differ"):
            validate_manifest(damaged)

    def test_every_training_face_covers_the_serving_wordmark_vocabulary(
        self,
    ) -> None:
        required = {ord(character) for character in WORDMARK_CHARACTERS}
        root = self.path.parent / "google-fonts"
        for row in self.manifest["fonts"]:
            with self.subTest(font=row["font_path"]):
                font = TTFont(root / row["font_path"], lazy=True)
                try:
                    available = set((font.getBestCmap() or {}).keys())
                finally:
                    font.close()
                missing = required - available
                self.assertEqual(missing, set())


if __name__ == "__main__":
    unittest.main()

import random
import tempfile
import unittest
from pathlib import Path

import numpy as np

import build_corner_dataset as builder
import generate_primitive_corpus as generator
from svg_corner_gt import LABEL_STRUCTURAL, frame_loop_examples, visible_svg_regions


class PrimitiveGeneratorTests(unittest.TestCase):
    def test_every_family_is_parseable_and_smooth_families_have_no_c0_labels(self):
        with tempfile.TemporaryDirectory(dir="tmp") as directory:
            root = Path(directory)
            seen = set()
            for index, (make, _weight) in enumerate(generator.GENERATORS):
                example = make(random.Random(100 + index))
                seen.add(example.family)
                source = root / f"{index:02d}_{example.family}.svg"
                source.write_text(generator._svg(example), encoding="utf-8")
                frame = visible_svg_regions(source, 64)
                loops = frame_loop_examples(frame)
                self.assertTrue(loops, example.family)
                if example.event_class == "smooth":
                    structural = sum(int(np.count_nonzero(loop.labels == LABEL_STRUCTURAL)) for loop in loops)
                    self.assertEqual(structural, 0, example.family)
            self.assertGreaterEqual(len(seen), 15)

    def test_explicit_split_directories_are_respected(self):
        self.assertEqual(builder._split(Path("dataset/train/family/a.svg")), "train")
        self.assertEqual(builder._split(Path("dataset/val/family/a.svg")), "val")
        self.assertEqual(builder._split(Path("dataset/test/family/a.svg")), "test")

    def test_manifest_has_all_event_classes(self):
        with tempfile.TemporaryDirectory(dir="tmp") as directory:
            summary = generator.generate(Path(directory), count=240, seed=3)
            self.assertEqual(summary["count"], 240)
            self.assertEqual(set(summary["event_classes"]), {"smooth", "structural", "mixed", "occlusion"})
            self.assertEqual(sum(summary["splits"].values()), 240)


if __name__ == "__main__":
    unittest.main()

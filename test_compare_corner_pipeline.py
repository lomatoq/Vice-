from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import compare_corner_pipeline as pipeline


class CornerPipelineEvaluatorTests(unittest.TestCase):
    def test_positions_snap_to_nearest_vertices_and_deduplicate(self):
        loop = np.asarray([[0, 0], [5, 0], [5, 5], [0, 5]], dtype=float)
        positions = np.asarray([[4.9, 0.1], [5.0, 0.2], [0.1, 4.8]])
        mask = pipeline._positions_to_mask(loop, positions)
        np.testing.assert_array_equal(mask, [False, True, False, True])

    def test_policy_parser_is_stable_and_rejects_unknown_values(self):
        self.assertEqual(
            pipeline._parse_policies("tiny-safe,production,tiny-safe"),
            ["tiny-safe", "production"],
        )
        with self.assertRaises(ValueError):
            pipeline._parse_policies("production,magic")

    def test_detector_passes_policy_and_returns_vertex_mask(self):
        loop = np.asarray([[0, 0], [2, 0], [2, 2], [0, 2]], dtype=float)
        with patch.object(
            pipeline.geometry_vectorizer,
            "paper_corner_positions",
            return_value=np.asarray([[2.0, 0.0]]),
        ) as mocked:
            mask = pipeline._pipeline_detector("tiny-safe", "cnn")(loop)
        np.testing.assert_array_equal(mask, [False, True, False, False])
        mocked.assert_called_once_with(
            loop, detector="cnn", postprocess_policy="tiny-safe")

    def test_cnn_overrides_restore_all_routing_globals(self):
        cnn = pipeline.corner_cnn
        vectorizer = pipeline.geometry_vectorizer
        old = (
            cnn.CNN_PATH,
            vectorizer._CNN_HYBRID_MODEL_PATH,
            vectorizer._CNN_LAX_THRESHOLD,
            vectorizer._CNN_HYBRID_THRESHOLD,
        )
        model = Path("models/test-override.pt")
        with pipeline._cnn_overrides(model, 0.42):
            self.assertEqual(cnn.CNN_PATH, model.resolve())
            self.assertEqual(vectorizer._CNN_HYBRID_MODEL_PATH, model.resolve())
            self.assertEqual(vectorizer._CNN_LAX_THRESHOLD, 0.42)
            self.assertEqual(vectorizer._CNN_HYBRID_THRESHOLD, 0.42)
        self.assertEqual(
            (
                cnn.CNN_PATH,
                vectorizer._CNN_HYBRID_MODEL_PATH,
                vectorizer._CNN_LAX_THRESHOLD,
                vectorizer._CNN_HYBRID_THRESHOLD,
            ),
            old,
        )


if __name__ == "__main__":
    unittest.main()

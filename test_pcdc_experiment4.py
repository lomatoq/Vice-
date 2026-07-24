from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from vice_compiler.experiment4_textline import (
    _fidelity_tail_metrics, _glyph_prior_identity, _human_status,
    _line_gcr_reduction,
    _owned_svg_density_invariant_reference,
    _remove_canvas_edge_contamination, _semantic_text_reference, _topology,
    _wordmark_prior_identity,
)


class Experiment4SemanticReferenceTests(unittest.TestCase):
    def test_pixel_tail_gate_catches_topology_correct_near_empty_output(self) -> None:
        rows = [
            {"legacy_iou": 0.80, "candidate_iou": 0.82}
            for _ in range(19)
        ]
        rows.append({"legacy_iou": 0.01, "candidate_iou": 1.0 / 120.0})
        metrics = _fidelity_tail_metrics(rows)
        self.assertEqual(metrics["severe_low_iou_count"], 1)
        self.assertLess(metrics["candidate_min_iou"], 0.01)
        self.assertFalse(metrics["pixel_fidelity_gate"])

    def test_primary_gcr_is_a_catastrophic_line_rate_not_component_sum(self) -> None:
        rows = [
            {"legacy": 20, "candidate": 1},
            {"legacy": 1, "candidate": 0},
            {"legacy": 0, "candidate": 0},
        ]
        legacy, candidate, reduction = _line_gcr_reduction(
            rows, "legacy", "candidate",
        )
        self.assertEqual((legacy, candidate), (2, 1))
        self.assertEqual(reduction, 0.5)

    def test_owned_svg_topology_is_measured_on_density_invariant_lattice(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "counter.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 16 16">'
                '<path fill="black" fill-rule="evenodd" '
                'd="M2 1h12v14H2z M6 5v6h4V5z"/>'
                '</svg>',
                "utf-8",
            )
            result = _owned_svg_density_invariant_reference(
                {"source": {"source_asset": str(source)}},
                target_size=(16, 16), roi_xyxy=(0, 0, 16, 16),
            )
            self.assertIsNotNone(result)
            support, scope = result
            self.assertEqual(_topology(support), (1, 1))
            self.assertEqual(support.shape, scope.shape)
            self.assertGreaterEqual(support.shape[0], 512)

    def test_canvas_edge_fragments_are_not_scored_as_glyphs(self) -> None:
        support = np.zeros((200, 512), bool)
        for x in (55, 155, 255, 355):
            support[65:155, x:x + 55] = True
        # A real interior punctuation/dot remains inside the text body.
        support[70:76, 430:436] = True
        # Broken container/crop boundaries are outside the text body; the
        # right segment supplies the mandatory canvas-edge contamination cue.
        support[20:21, 20:150] = True
        support[180:181, 230:360] = True
        support[10:190, 511:512] = True
        cleaned, changed = _remove_canvas_edge_contamination(support)
        self.assertTrue(changed)
        self.assertTrue(np.all(cleaned[70:76, 430:436]))
        self.assertFalse(np.any(cleaned[20:21]))
        self.assertFalse(np.any(cleaned[180:181]))
        self.assertFalse(np.any(cleaned[:, 511:512]))

    def test_dense_knockout_carrier_is_scored_on_enclosed_glyph_loops(self) -> None:
        carrier = np.zeros((40, 100), bool)
        carrier[4:36, 3:97] = True
        carrier[10:30, 12:24] = False
        carrier[10:30, 42:54] = False
        carrier[10:30, 72:84] = False
        reference, semantics = _semantic_text_reference(
            carrier, explicit_topology=False,
            oklab=np.dstack((
                np.where(carrier, 0.55, 0.95),
                np.zeros_like(carrier, dtype=float),
                np.zeros_like(carrier, dtype=float),
            )),
        )
        self.assertEqual(semantics, "dense-knockout-carrier-negative-loops")
        self.assertEqual(cv2.connectedComponents(reference.astype(np.uint8), 8)[0] - 1, 3)
        self.assertFalse(np.any(reference & carrier))

    def test_sparse_outline_and_explicit_topology_are_never_inverted(self) -> None:
        outline = np.zeros((40, 100), bool)
        cv2.rectangle(outline, (3, 4), (96, 35), 1, 2)
        cv2.rectangle(outline, (12, 10), (24, 29), 1, 2)
        kept, semantics = _semantic_text_reference(
            outline, explicit_topology=False,
        )
        self.assertEqual(semantics, "reviewed-positive-support")
        np.testing.assert_array_equal(kept, outline)
        explicit, semantics = _semantic_text_reference(
            np.ones((20, 30), bool), explicit_topology=True,
        )
        self.assertEqual(semantics, "reviewed-positive-support")
        self.assertTrue(np.all(explicit))

    def test_multicolour_positive_logo_is_not_misread_as_knockout(self) -> None:
        carrier = np.zeros((40, 100), bool)
        carrier[4:36, 3:97] = True
        carrier[10:30, 12:24] = False
        carrier[10:30, 42:54] = False
        lab = np.zeros((40, 100, 3), float)
        lab[..., 0] = 0.55
        lab[4:20, 3:97, 0] = 0.15
        kept, semantics = _semantic_text_reference(
            carrier, explicit_topology=False, oklab=lab,
        )
        self.assertEqual(semantics, "reviewed-positive-support")
        np.testing.assert_array_equal(kept, carrier)


class Experiment4HumanReviewBindingTests(unittest.TestCase):
    def test_review_is_bound_to_both_exact_alternative_digests(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            review = root / "review.json"
            manifest = root / "human_manifest.json"
            review.write_text(json.dumps({
                "required": 1,
                "answers": {
                    "line-1": {
                        "choice": "candidate", "candidate_side": "A",
                        "candidate_mask_digest": "candidate-v1",
                        "legacy_mask_digest": "legacy-v1",
                        "candidate_svg_digest": "candidate-svg-v1",
                        "legacy_svg_digest": "legacy-svg-v1",
                    },
                },
            }), "utf-8")
            manifest.write_text(json.dumps({
                "cases": [{
                    "id": "line-1", "candidate_side": "A",
                    "candidate_mask_digest": "candidate-v1",
                    "legacy_mask_digest": "legacy-v1",
                    "candidate_svg_digest": "candidate-svg-v1",
                    "legacy_svg_digest": "legacy-svg-v1",
                }],
            }), "utf-8")
            rows = [{
                "id": "line-1", "candidate_mask_digest": "candidate-v1",
                "legacy_mask_digest": "legacy-v1",
                "candidate_svg_digest": "candidate-svg-v1",
                "legacy_svg_digest": "legacy-svg-v1",
            }]
            current = _human_status(
                review, rows=rows, manifest_path=manifest,
            )
            self.assertEqual(current["reviewed"], 1)
            self.assertEqual(current["stale"], 0)
            self.assertTrue(current["digest_validated"])
            self.assertTrue(current["gate_pass"])
            self.assertEqual(current["review_sha256"], hashlib.sha256(
                review.read_bytes(),
            ).hexdigest())
            self.assertEqual(current["manifest_sha256"], hashlib.sha256(
                manifest.read_bytes(),
            ).hexdigest())

            changed = _human_status(
                review,
                rows=[{**rows[0], "candidate_mask_digest": "candidate-v2"}],
                manifest_path=manifest,
            )
            self.assertEqual(changed["reviewed"], 0)
            self.assertEqual(changed["stale"], 1)
            self.assertFalse(changed["gate_pass"])

    def test_old_manifest_without_digests_cannot_reuse_answers(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            review = root / "review.json"
            manifest = root / "human_manifest.json"
            review.write_text(json.dumps({
                "required": 1,
                "answers": {
                    "line-1": {"choice": "tie", "candidate_side": "B"},
                },
            }), "utf-8")
            manifest.write_text(json.dumps({
                "cases": [{"id": "line-1", "candidate_side": "B"}],
            }), "utf-8")
            status = _human_status(
                review,
                rows=[{
                    "id": "line-1", "candidate_mask_digest": "candidate",
                    "legacy_mask_digest": "legacy",
                }],
                manifest_path=manifest,
            )
            self.assertEqual(status["reviewed"], 0)
            self.assertEqual(status["stale"], 1)
            self.assertFalse(status["digest_validated"])
            self.assertFalse(status["gate_pass"])


class Experiment4NeuralCheckpointBindingTests(unittest.TestCase):
    def test_wordmark_candidate_identity_is_bound_to_exact_bytes(self) -> None:
        with TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "candidate.pt"
            checkpoint.write_bytes(b"whole-line-wordmark-candidate")
            with patch(
                "vice_compiler.experiment4_textline."
                "resolve_wordmark_prior_checkpoint",
                return_value=checkpoint,
            ):
                identity = _wordmark_prior_identity()
            self.assertEqual(identity, {
                "path": str(checkpoint.resolve()),
                "sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "bytes": checkpoint.stat().st_size,
            })

    def test_disabled_neural_lanes_have_no_checkpoint_identity(self) -> None:
        with patch(
            "vice_compiler.experiment4_textline."
            "resolve_wordmark_prior_checkpoint",
            return_value=None,
        ), patch(
            "vice_compiler.experiment4_textline."
            "resolve_glyph_prior_checkpoint",
            return_value=None,
        ):
            self.assertIsNone(_wordmark_prior_identity())
            self.assertIsNone(_glyph_prior_identity())


if __name__ == "__main__":
    unittest.main()

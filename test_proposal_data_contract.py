from __future__ import annotations

import unittest

from vice_compiler.proposal_data_contract import (
    RELATION_TYPES, relation_supervision, split_group,
    typed_macro_families, uses_explicit_owner_labels,
)


class ProposalDataContractTests(unittest.TestCase):
    def test_open_font_family_is_the_split_boundary(self) -> None:
        base = {
            "source": "synthetic-open-text", "font_family": "Atkinson",
            "font_sha256": "a" * 64,
            "owner_contract": {
                "schema": "explicit-svg-groups/v1",
                "owner_ids": ["text-row-0", "text-row-1"],
            },
        }
        first = {**base, "source_id": "open-text:atkinson:first"}
        second = {**base, "source_id": "open-text:atkinson:second"}
        self.assertTrue(uses_explicit_owner_labels(first))
        self.assertEqual(split_group(first), split_group(second))

    def test_typed_structure_variants_share_source_but_not_prototype(self) -> None:
        base = {
            "source": "synthetic-structure-v2",
            "source_id": "structure-v2:stroke_network:network:1234",
            "prototype": "network",
            "macro_family_contract": {
                "schema": "typed-generator/v2",
                "families": ["stroke_network"],
            },
            "relation_contract": {
                "schema": "query-relations/v1",
                "family": "stroke_network",
                "positive": ["same_group", "stroke_membership"],
                "observable": list(RELATION_TYPES),
            },
        }
        self.assertEqual(typed_macro_families(base), ("stroke_network",))
        self.assertEqual(
            relation_supervision(base, "stroke_network"),
            (("same_group", "stroke_membership"), RELATION_TYPES),
        )
        self.assertEqual(
            relation_supervision(base, "risk_hard_negative"), ((), ()),
        )
        with self.assertRaisesRegex(ValueError, "family mismatch"):
            relation_supervision(base, "appearance_model")
        self.assertEqual(split_group({**base, "id": "variant-0"}),
                         split_group({**base, "id": "variant-1"}))
        another = {**base, "source_id": "structure-v2:stroke_network:network:9999"}
        self.assertNotEqual(split_group(base), split_group(another))

    def test_unknown_typed_family_fails_closed(self) -> None:
        row = {
            "source": "synthetic-structure-v2", "source_id": "bad",
            "macro_family_contract": {
                "schema": "typed-generator/v1", "families": ["text_line"],
            },
        }
        with self.assertRaisesRegex(ValueError, "unsupported"):
            typed_macro_families(row)

    def test_missing_relations_are_unknown_instead_of_negative(self) -> None:
        legacy = {
            "source": "synthetic-structure-v2", "source_id": "legacy",
            "macro_family_contract": {
                "schema": "typed-generator/v1",
                "families": ["stroke_network"],
            },
        }
        self.assertEqual(relation_supervision(legacy, "stroke_network"), ((), ()))

    def test_typed_v2_relation_contract_fails_closed(self) -> None:
        row = {
            "source": "synthetic-structure-v2", "source_id": "bad-relations",
            "macro_family_contract": {
                "schema": "typed-generator/v2",
                "families": ["layer_relation"],
            },
            "relation_contract": {
                "schema": "query-relations/v1", "family": "layer_relation",
                "positive": ["front_of"], "observable": ["behind"],
            },
        }
        with self.assertRaisesRegex(ValueError, "malformed"):
            typed_macro_families(row)


if __name__ == "__main__":
    unittest.main()

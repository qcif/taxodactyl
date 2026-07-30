"""Unit tests for the db_coverage.json assertion walker.

Covers each of the four rule tiers with hand-crafted expected/actual pairs:

- matching pair (no changes)
- lost species key at analysis layer (WOULD_FAIL)
- extra species key at analysis layer (WOULD_FAIL)
- int -> str leaf (WOULD_FAIL type mismatch)
- non-null -> null leaf (WOULD_FAIL non-null propagation)
- tolerated value drift within same type
- extra key below the analysis layer (TOLERATED)
"""

import copy
import unittest

from tests.integration.kit.coverage_assert import (
    ChangeKind,
    assert_matches,
    semantic_diff,
)


def _minimal_fixture() -> dict:
    """Return a minimal, valid expected/actual pair covering all layers."""
    return {
        "coverage": {
            "candidate": {
                "Spodoptera frugiperda": {
                    "target": 3919,
                    "related": {
                        "Spodoptera frugiperda": 3919,
                        "Spodoptera exigua": 618,
                    },
                    "country": {
                        "Spodoptera frugiperda": 3919,
                    },
                },
            },
            "toi": {
                "Spodoptera frugiperda": {
                    "target": 3919,
                    "related": {"Spodoptera frugiperda": 3919},
                    "country": {"Spodoptera frugiperda": 3919},
                },
            },
            "pmi": {
                "Spodoptera frugiperda": {
                    "target": 3919,
                    "related": {"Spodoptera frugiperda": 3919},
                    "country": {"Spodoptera frugiperda": 3919},
                },
            },
        },
        "ncbi_urls": {
            "Spodoptera frugiperda": {
                "blast": "https://blast.example/?tid=7108",
                "taxonomy": "https://tax.example/?tid=7108",
            },
        },
    }


class TestAssertMatches(unittest.TestCase):
    """Happy path and failure modes for ``assert_matches``."""

    def test_matching_pair(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        # Should not raise.
        assert_matches(expected, actual)

    def test_lost_species_key(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        del actual["coverage"]["candidate"]["Spodoptera frugiperda"]
        with self.assertRaises(AssertionError) as ctx:
            assert_matches(expected, actual)
        self.assertIn("candidate", str(ctx.exception))
        self.assertIn("missing required key", str(ctx.exception))

    def test_extra_species_key(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        actual["coverage"]["candidate"]["Spodoptera bogus"] = {
            "target": 1,
            "related": {},
            "country": {},
        }
        with self.assertRaises(AssertionError) as ctx:
            assert_matches(expected, actual)
        self.assertIn("unexpected extra key", str(ctx.exception))

    def test_leaf_type_mismatch_int_to_str(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        target_path = actual["coverage"]["candidate"]["Spodoptera frugiperda"]
        target_path["target"] = "3919"
        with self.assertRaises(AssertionError) as ctx:
            assert_matches(expected, actual)
        self.assertIn("type mismatch", str(ctx.exception))

    def test_non_null_propagation_int_to_null(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        target_path = actual["coverage"]["candidate"]["Spodoptera frugiperda"]
        target_path["target"] = None
        with self.assertRaises(AssertionError) as ctx:
            assert_matches(expected, actual)
        self.assertIn("non-null propagation", str(ctx.exception))

    def test_non_null_propagation_int_to_zero(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        target_path = actual["coverage"]["candidate"]["Spodoptera frugiperda"]
        target_path["target"] = 0
        with self.assertRaises(AssertionError) as ctx:
            assert_matches(expected, actual)
        self.assertIn("non-null propagation", str(ctx.exception))

    def test_value_drift_tolerated(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        target_path = actual["coverage"]["candidate"]["Spodoptera frugiperda"]
        target_path["target"] = 3920
        # Same type, both truthy -> tolerated.
        assert_matches(expected, actual)

    def test_extra_key_below_analysis_layer_tolerated(self):
        """New species appearing inside ``country``/``related`` is tolerated.

        The analysis-target layer is strict about species keys, but the
        sub-objects below it (per-species related/country counts) can drift
        as GBIF or NCBI records shift.
        """
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        country = actual["coverage"]["candidate"]["Spodoptera frugiperda"][
            "country"
        ]
        country["Spodoptera new_species"] = 42
        assert_matches(expected, actual)

    def test_null_pair_matches(self):
        """Both null at a leaf should be accepted."""
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        target_path = expected["coverage"]["candidate"][
            "Spodoptera frugiperda"
        ]
        target_path["target"] = None
        actual_target_path = actual["coverage"]["candidate"][
            "Spodoptera frugiperda"
        ]
        actual_target_path["target"] = None
        assert_matches(expected, actual)


class TestSemanticDiff(unittest.TestCase):
    """Direct inspection of the structured diff output."""

    def test_matching_pair_yields_no_changes(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        self.assertEqual(semantic_diff(expected, actual), [])

    def test_value_drift_flagged_tolerated(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        target_path = actual["coverage"]["candidate"]["Spodoptera frugiperda"]
        target_path["target"] = 3920
        changes = semantic_diff(expected, actual)
        self.assertEqual(len(changes), 1)
        self.assertIs(changes[0].kind, ChangeKind.TOLERATED)
        self.assertIn("value drift", changes[0].reason)

    def test_extra_key_below_layer_flagged_tolerated(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        related = actual["coverage"]["candidate"]["Spodoptera frugiperda"][
            "related"
        ]
        related["Spodoptera new_species"] = 7
        changes = semantic_diff(expected, actual)
        self.assertEqual(len(changes), 1)
        self.assertIs(changes[0].kind, ChangeKind.TOLERATED)

    def test_species_removal_flagged_would_fail(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        del actual["coverage"]["candidate"]["Spodoptera frugiperda"]
        changes = semantic_diff(expected, actual)
        would_fail = [c for c in changes if c.kind is ChangeKind.WOULD_FAIL]
        self.assertTrue(would_fail)
        self.assertTrue(
            any("Spodoptera frugiperda" in c.path for c in would_fail)
        )

    def test_top_level_missing_key(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        del actual["ncbi_urls"]
        changes = semantic_diff(expected, actual)
        would_fail = [c for c in changes if c.kind is ChangeKind.WOULD_FAIL]
        self.assertTrue(
            any("ncbi_urls" in c.path for c in would_fail)
        )

    def test_path_qualified_message_for_leaf_type_mismatch(self):
        expected = _minimal_fixture()
        actual = copy.deepcopy(expected)
        actual["ncbi_urls"]["Spodoptera frugiperda"]["blast"] = 123
        changes = semantic_diff(expected, actual)
        failures = [c for c in changes if c.kind is ChangeKind.WOULD_FAIL]
        self.assertEqual(len(failures), 1)
        self.assertIn("ncbi_urls", failures[0].path)
        self.assertIn("blast", failures[0].path)


if __name__ == "__main__":
    unittest.main()

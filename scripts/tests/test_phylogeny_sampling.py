import json
import unittest
from pathlib import Path
from unittest import mock

from scripts import p3_assign_taxonomy

TEST_DATA_DIR = Path(__file__).parent / "test-data"

# -----------------------------------------------------------------------------
# Test data with 32 hits across 4 species (8 each), identities 0.921-0.999
# Strong candidates:
# - Homo (0.980-0.999)
# Moderate candidates:
# - Gorilla (0.940-0.949),
# - Pongo (0.960-0.969)
# Non-candidates:
# - Pan (0.921-0.930)

TEST_HITS_JSON = TEST_DATA_DIR / "test_phylogeny_hits.json"
# -----------------------------------------------------------------------------


class TestGetAccessionsForPhylogeny(unittest.TestCase):
    """Test sampling of hit sequences for building genetic distance tree."""

    CRITERIA_CONFIG = {
        'phylogeny_min_hit_identity': 0.935,
        'phylogeny_min_seqs': 20,
        'phylogeny_max_seqs': 50,
        'phylogeny_species_max_seqs': 3,
        'phylogeny_candidate_max_seqs': 5,
    }

    def setUp(self):
        for k, v in self.CRITERIA_CONFIG.items():
            patcher = mock.patch.object(
                p3_assign_taxonomy.config.criteria,
                k,
                v,
                create=True,
            )
            patcher.start()
            self.addCleanup(patcher.stop)

        with open(TEST_HITS_JSON) as f:
            self.hits = json.load(f)

    def test_accession_selection_with_strict_candidate(self):
        result = p3_assign_taxonomy._get_accessions_for_phylogeny(
            self.hits, id_key="acc", identity_key="identity"
        )
        result_enumerated = {
            key: len([
                x for x in result
                if x[:2] == key
            ])
            for key in (
                'HS',
                'GG',
                'PP',
                'PT',
            )
        }
        self.assertIn('HS1', result)
        self.assertIn('HS8', result)
        self.assertIn('GG1', result)
        self.assertIn('GG8', result)
        self.assertIn('PP1', result)
        self.assertIn('PP8', result)
        self.assertIn('PT1', result)
        self.assertIn('PT4', result)
        self.assertIn('PT8', result)
        self.assertEqual(result_enumerated['HS'], 5)
        self.assertEqual(result_enumerated['GG'], 3)
        self.assertEqual(result_enumerated['PP'], 3)
        self.assertEqual(result_enumerated['PT'], 3)

    def test_accession_selection_with_moderate_candidate(self):
        """Remove strong candidate to make 2 species moderate candidates."""
        hits = [
            x for x in self.hits.copy()
            if not x['acc'].startswith('HS')
        ]
        result = p3_assign_taxonomy._get_accessions_for_phylogeny(
            hits, id_key="acc", identity_key="identity"
        )
        results_enumerated = {
            key: len([
                x for x in result
                if x[:2] == key
            ])
            for key in (
                'GG',
                'PP',
                'PT',
            )
        }
        self.assertIn('GG1', result)
        self.assertIn('GG8', result)
        self.assertIn('PP1', result)
        self.assertIn('PP8', result)
        self.assertIn('PT1', result)
        self.assertIn('PT8', result)
        self.assertEqual(results_enumerated['GG'], 5)
        self.assertEqual(results_enumerated['PP'], 5)
        self.assertEqual(results_enumerated['PT'], 3)

    def test_sampling_when_above_limit(self):
        # 13 hits for one species → sampling branch
        hits = [
            {
                "species": "Felis catus",
                "acc": f"A{i}",
                "identity": 0.80 + i * 0.015,
            }
            for i in range(13)
        ]
        result = p3_assign_taxonomy._get_accessions_for_phylogeny(
            hits, id_key="acc", identity_key="identity"
        )
        self.assertEqual(len(result), 5)


if __name__ == "__main__":
    unittest.main()

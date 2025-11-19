import json
import unittest
from pathlib import Path
from unittest import mock

from scripts import p3_assign_taxonomy


class TestGetAccessionsForPhylogeny(unittest.TestCase):
    """Unit-tests for sampling of hits for phylogenetic subject sequences."""

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

        # Load 32 hits across 4 species (8 each), identities 0.921-0.999
        # ~ Candidates:
        # Homo (0.980-0.999)
        # ~ Non-candidates:
        # Pan (0.921-0.930)
        # Gorilla (0.940-0.949),
        # Pongo (0.960-0.969)

        test_data_path = (
            Path(__file__).parent / "test-data" / "test_phylogeny_hits.json"
        )
        with open(test_data_path) as f:
            hits = json.load(f)
        self.result = p3_assign_taxonomy._get_accessions_for_phylogeny(
            hits, id_key="acc", identity_key="identity"
        )

    def test_accession_selection_with_strict_candidate(self):
        results_enumerated = {
            key: len([
                x for x in self.result
                if x[:2] == key
            ])
            for key in (
                'HS',
                'GG',
                'PP',
                'PT',
            )
        }
        self.assertIn('HS1', self.result)
        self.assertIn('HS8', self.result)
        self.assertIn('GG1', self.result)
        self.assertIn('GG8', self.result)
        self.assertIn('PP1', self.result)
        self.assertIn('PP8', self.result)
        self.assertIn('PT1', self.result)
        self.assertIn('PT5', self.result)
        self.assertIn('PT8', self.result)
        self.assertEqual(results_enumerated['HS'], 5)
        self.assertEqual(results_enumerated['GG'], 3)
        self.assertEqual(results_enumerated['PP'], 3)
        self.assertEqual(results_enumerated['PT'], 3)

    def test_accession_selection_with_moderate_candidate(self):
        """Remove strong candidate to make all species candidates."""
        result = [
            x for x in self.results.copy()
            if not x.startswith('HS')
        ]
        results_enumerated = {
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
        self.assertIn('PT5', result)
        self.assertIn('PT8', result)
        self.assertEqual(results_enumerated['GG'], 5)
        self.assertEqual(results_enumerated['PP'], 5)
        self.assertEqual(results_enumerated['PT'], 5)

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

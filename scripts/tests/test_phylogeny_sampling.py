import unittest
from unittest import mock

from scripts import p3_assign_taxonomy


class TestGetAccessionsForPhylogeny(unittest.TestCase):
    """Unit-tests for sampling of hits for phylogenetic subject sequences."""

    def setUp(self):
        # Set a low limit so we can exercise sampling
        patcher = mock.patch.object(
            p3_assign_taxonomy.config.CRITERIA,
            "PHYLOGENY_MAX_HITS_PER_SPECIES",
            5,
            create=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_all_hits_returned_when_below_limit(self):
        hits = [
            {"species": "Pan troglodytes", "acc": "PT1", "identity": 0.98},
            {"species": "Pan troglodytes", "acc": "PT2", "identity": 0.95},
        ]
        result = p3_assign_taxonomy._get_accessions_for_phylogeny(
            hits, id_key="acc", identity_key="identity"
        )
        self.assertCountEqual(result, ["PT1", "PT2"])

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
        # should pick indices [0, 6, 12] → A0, A6, A12
        self.assertEqual(len(result), 5)
        self.assertCountEqual(result, ["A0", "A3", "A6", "A9", "A12"])

    def test_mixed_species(self):
        # 12 cat hits (sampled down to 3) + 1 dog hit (kept as-is) → 13 inputs
        cat_hits = [
            {
                "species": "Felis catus",
                "acc": f"C{i}",
                "identity": 0.80 + i * 0.015,
            }
            for i in range(12)
        ]
        dog_hit = {"species": "Canis lupus", "acc": "D0", "identity": 0.90}
        hits = cat_hits + [dog_hit]
        result = p3_assign_taxonomy._get_accessions_for_phylogeny(
            hits, id_key="acc", identity_key="identity"
        )
        # cat picks at [0,6,11] → C0, C6, C11 plus "D0"
        self.assertEqual(len(result), 6)
        self.assertCountEqual(result, ["C0", "C3", "C6", "C8", "C11", "D0"])


if __name__ == "__main__":
    unittest.main()

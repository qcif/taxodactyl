#!/usr/bin/env python3

"""Verify every HIGHER_CLASSIFICATIONS COL ID still resolves.

The GBIF v1 usage key for a HIGHER_CLASSIFICATIONS entry is looked up at
runtime from its (stable) COL taxonID via `api.get_usage_key()`. If GBIF
reloads the COL checklist and retires one of these taxonIDs, classification
filtering (`RelatedTaxaGBIF`) would silently stop matching that kingdom.
This test hits the live GBIF API to catch that early.

Not wired into an existing .vscode/launch.json entry - run directly with:

    python -m unittest tests.integration.test_gbif_classifications
"""

import unittest

import pygbif

from src.gbif.api import COL_CHECKLIST_KEY, get_usage_key
from src.utils.config import Config

config = Config()


# COL ID -> substring expected in that record's canonicalName /
# scientificName. One entry per unique gbif_col value in
# Config.HIGHER_CLASSIFICATIONS (several classification names share a
# COL ID, e.g. 'animalia'/'animal'/'animals').
EXPECTED_NAME_BY_COL_ID = {
    'N': 'animalia',
    'P': 'plantae',
    'F': 'fungi',
    'C': 'chromista',
    'CRRY6': 'bacteria',
    'CRLT8': 'archaea',
    '92e52ff4-2dc6-4b35-9339-2e92035b8daf': 'viruses',
}


class TestHigherClassificationsResolve(unittest.TestCase):

    def test_every_col_id_resolves_to_expected_kingdom(self):
        col_ids = {
            classification['gbif_col']
            for classification in config.HIGHER_CLASSIFICATIONS.values()
        }
        for col_id in col_ids:
            expected_name = EXPECTED_NAME_BY_COL_ID.get(col_id)
            self.assertIsNotNone(
                expected_name,
                f"COL ID '{col_id}' is not in EXPECTED_NAME_BY_COL_ID -"
                " add an entry for it in this test."
            )

            usage_key = get_usage_key(col_id)
            record = pygbif.species.name_usage(key=usage_key)

            self.assertEqual(record.get('datasetKey'), COL_CHECKLIST_KEY)
            canonical_or_scientific_name = (
                record.get('canonicalName') or record.get('scientificName')
            )
            self.assertTrue(
                canonical_or_scientific_name,
                f"COL ID '{col_id}' resolved to usage key {usage_key}, but"
                " that record has no canonicalName/scientificName."
            )
            self.assertIn(
                expected_name,
                canonical_or_scientific_name.lower(),
                f"COL ID '{col_id}' resolved to"
                f" '{canonical_or_scientific_name}', expected something"
                f" matching '{expected_name}'. GBIF may have retired or"
                " reassigned this COL ID - check the table in"
                " scripts/tasks/01-gbif-api-refactor.md finding 4 and update"
                " Config.HIGHER_CLASSIFICATIONS."
            )


if __name__ == '__main__':
    unittest.main()

"""Test the roll-up of DB coverage flags 5.* into flag 5."""

import logging
import tempfile
import unittest
from pathlib import Path

from src.utils.config import Config
from src.utils.flags import FLAGS, Flag

logging.disable(logging.CRITICAL)

config = Config()
TAXON = 'Pandoravirus'
CSV_NO_LOCUS = 'taxon,locus\nPandoravirus,NA\n'
CSV_LOCUS = 'taxon,locus\nPandoravirus,COI\n'


class FlagRollupTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.original = (
            config.output_dir,
            config.inputs.coverage_taxa_csv,
        )
        config.output_dir = self.out
        config.inputs.coverage_taxa_csv = self.out / 'coverage.csv'
        self.addCleanup(self._restore)

    def _reset_cache(self):
        config.__dict__.pop('coverage_rows', None)
        config.__dict__.pop('metadata', None)

    def _restore(self):
        config.output_dir, config.inputs.coverage_taxa_csv = self.original
        self._reset_cache()

    def _roll_up(self, csv_text, value_51, value_52, value_53):
        (self.out / 'coverage.csv').write_text(csv_text)
        self._reset_cache()
        query_dir = config.get_query_dir(0)
        for flag_id, value in (
            (FLAGS.DB_COVERAGE_TARGET, value_51),
            (FLAGS.DB_COVERAGE_RELATED, value_52),
            (FLAGS.DB_COVERAGE_RELATED_COUNTRY, value_53),
        ):
            Flag.write(
                query_dir, flag_id, value, target=TAXON, target_type='pmi')
        return Flag.read(query_dir)['5']['pmi'][TAXON]

    def test_error_without_locus_stays_an_error(self):
        flag = self._roll_up(CSV_NO_LOCUS, 'ERR', 'ERR', 'ERR')
        self.assertEqual(flag.level, 0)
        self.assertEqual(flag.bs_class, 'secondary')

    def test_error_with_locus_is_neutral(self):
        flag = self._roll_up(CSV_LOCUS, 'ERR', 'ERR', 'ERR')
        self.assertEqual(flag.bs_class, 'secondary')

    def test_success_without_locus_is_still_a_warning(self):
        flag = self._roll_up(CSV_NO_LOCUS, 'A', 'A', 'A')
        self.assertEqual(flag.flag_id, FLAGS.DB_COVERAGE_ALL)
        self.assertEqual(flag.value, FLAGS.B)
        self.assertEqual(flag.bs_class, 'warning')


if __name__ == '__main__':
    unittest.main()

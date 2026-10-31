"""Context selection boundaries and hit/FASTA association regressions."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from Bio.Blast import NCBIXML
from scripts.src.blast.parse_xml import parse_blast_xml
from src.utils.config.schema import ConfigSchema
from src.utils.config.mappings import PARAMS

XML = Path(__file__).parent / 'test-data/one_output.xml'


class TestBlastContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with XML.open() as handle:
            cls.record = next(NCBIXML.parse(handle))

    def parse(self, identities, cap=2000, threshold=0.935):
        record = copy.deepcopy(self.record)
        template = record.alignments[0]
        record.alignments = []
        for i, identity in enumerate(identities):
            hit = copy.deepcopy(template)
            hit.accession = str(i)
            hit.hsps = hit.hsps[:1]
            hit.hsps[0].align_length = 10000
            hit.hsps[0].identities = round(identity * 10000)
            hit.hsps[0].sbjct = 'A' + 'C' * (i % 7)
            record.alignments.append(hit)
        with patch('scripts.src.blast.parse_xml.NCBIXML.parse', return_value=[record]):
            return parse_blast_xml(XML, cap, threshold)

    def test_boundaries(self):
        cases = [([], 0), ([0.9]*37, 37), ([0.9]*2000, 500),
                 ([0.935]*2000, 500), ([0.94]*600+[0.93]*600, 1000),
                 ([0.94]*80+[0.93]*1920, 500),
                 ([0.94]*1200+[0.93]*800, 1500),
                 ([0.94]*2000, 2000), ([0.94]*750, 750)]
        for identities, expected in cases:
            with self.subTest(expected=expected, size=len(identities)):
                hits, fastas = self.parse(identities)
                self.assertEqual(len(hits[0]['hits']), expected)
                self.assertEqual(len(fastas[0]), expected)
        for cap in [1, 300, 750, 2500]:
            hits, _ = self.parse([0.99]*2600, cap)
            self.assertEqual(len(hits[0]['hits']), cap)
        hits, _ = self.parse([0.9]*2600, 2500)
        self.assertEqual(len(hits[0]['hits']), 500)

    def test_stable_sort_and_fasta_membership(self):
        hits, fastas = self.parse([0.9, 0.99, 0.98, 0.99], 3)
        self.assertEqual([h['accession'] for h in hits[0]['hits']], ['1', '3', '2'])
        self.assertEqual([r.id for r in fastas[0]], ['1', '2', '3'])
        self.assertEqual([str(r.seq) for r in fastas[0]], ['AC', 'ACC', 'ACCC'])

    def test_configurable_threshold_and_rounding(self):
        for threshold, expected in [(0, 1000), (1, 500), (0.95, 500), (0.935, 1000)]:
            hits, _ = self.parse([0.94]*1000, threshold=threshold)
            self.assertEqual(len(hits[0]['hits']), expected)
        hits, _ = self.parse([0.9354]*1000)
        self.assertEqual(len(hits[0]['hits']), 500)
        hits, _ = self.parse([0.9356]*1000)
        self.assertEqual(len(hits[0]['hits']), 1000)

    def test_multiple_queries_repeated_accessions_and_hsps(self):
        record = copy.deepcopy(self.record)
        first = copy.deepcopy(record.alignments[0])
        second = copy.deepcopy(first)
        first.accession = second.accession = 'repeated'
        first.hsps = [copy.deepcopy(first.hsps[0]), copy.deepcopy(first.hsps[0])]
        for hsp, identities, length in zip(first.hsps, [100, 180], [100, 200]):
            hsp.identities, hsp.align_length = identities, length
        first.hsps[-1].sbjct = 'AC'
        second.hsps = [second.hsps[0]]
        second.hsps[0].identities, second.hsps[0].align_length = 99, 100
        second.hsps[0].sbjct = 'GT'
        record.alignments = [first, second]
        empty = copy.deepcopy(record)
        empty.alignments = []
        with patch('scripts.src.blast.parse_xml.NCBIXML.parse', return_value=[record, empty]):
            hits, fastas = parse_blast_xml(XML, 1)
        self.assertEqual(hits[0]['hits'][0]['identity'], 0.99)
        self.assertEqual(str(fastas[0][0].seq), 'GT')
        self.assertEqual(hits[1]['hits'], [])
        self.assertEqual(fastas[1], [])
        record.alignments = [copy.deepcopy(first) for _ in range(600)]
        with patch('scripts.src.blast.parse_xml.NCBIXML.parse', return_value=[record]):
            hits, _ = parse_blast_xml(XML)
        self.assertEqual(len(hits[0]['hits']), 500)  # Aggregate .933, first HSP 1.0
        self.assertEqual(len(hits[0]['hits'][0]['hsps']), 2)

    def test_invalid_settings_all_paths(self):
        for name, invalid in [
            ('blast_max_target_seqs', [0, -1, 1.5, '1.5', True]),
            ('blast_context_min_identity', [-0.1, 1.1, float('nan'), float('inf'), True]),
        ]:
            for value in invalid:
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError):
                        ConfigSchema(**{name: value})
                    with self.assertRaises(ValueError):
                        PARAMS[name].cast(value)
                    with self.assertRaises(ValueError):
                        parse_blast_xml(XML, **{
                            'max_target_seqs' if name.endswith('seqs') else 'stopping_identity': value})
        settings = ConfigSchema(blast_context_min_identity=0, criteria={'alignment_min_identity': .98})
        self.assertEqual(settings.blast_context_min_identity, 0)
        self.assertEqual(settings.criteria.alignment_min_identity, .98)

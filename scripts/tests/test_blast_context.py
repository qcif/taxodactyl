"""Context selection boundaries and hit/FASTA association regressions."""
import copy
import json
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

from Bio import SeqIO
from Bio.Blast import NCBIXML
from scripts.src.blast.parse_xml import parse_blast_xml, select_blast_hits
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
            complete, sequences = parse_blast_xml(XML)
            before = copy.deepcopy(complete)
            selected = select_blast_hits(complete, sequences, cap, threshold)
            self.assertEqual(complete, before)
            self.assertEqual(len(complete[0]['hits']), len(identities))
            return selected

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
            hits, fastas = select_blast_hits(*parse_blast_xml(XML), 1)
        self.assertEqual(hits[0]['hits'][0]['identity'], 0.99)
        self.assertEqual(str(fastas[0][0].seq), 'GT')
        self.assertEqual(hits[1]['hits'], [])
        self.assertEqual(fastas[1], [])
        record.alignments = [copy.deepcopy(first) for _ in range(600)]
        with patch('scripts.src.blast.parse_xml.NCBIXML.parse', return_value=[record]):
            hits, _ = select_blast_hits(*parse_blast_xml(XML))
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
                        select_blast_hits([], [], **{
                            'max_target_seqs' if name.endswith('seqs') else 'stopping_identity': value})
        settings = ConfigSchema(blast_context_min_identity=0, criteria={'alignment_min_identity': .98})
        self.assertEqual(settings.blast_context_min_identity, 0)
        self.assertEqual(settings.criteria.alignment_min_identity, .98)


    def test_p1_writes_complete_json_before_selection_and_selected_assets_only(self):
        from scripts import p1_parse_blast as p1
        record = copy.deepcopy(self.record)
        first = copy.deepcopy(record.alignments[0])
        second = copy.deepcopy(first)
        first.accession = second.accession = "repeated"
        first.hsps = [first.hsps[0]]
        second.hsps = [second.hsps[0]]
        first.hsps[0].identities, first.hsps[0].align_length = 90, 100
        second.hsps[0].identities, second.hsps[0].align_length = 99, 100
        first.hsps[0].sbjct, second.hsps[0].sbjct = "AC", "GT"
        third = copy.deepcopy(first)
        third.accession = "excluded"
        third.hsps[0].identities = 80
        record.alignments = [first, second, third]
        empty = copy.deepcopy(record)
        empty.alignments = []
        with patch('scripts.src.blast.parse_xml.NCBIXML.parse', return_value=[record, empty]):
            complete, sequences = parse_blast_xml(XML)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def query_dir(i, title=None):
                path = root / f"query_{i}"
                path.mkdir(exist_ok=True)
                return path
            config = SimpleNamespace(
                output_dir=root, hits_json="all_hits.json", hits_fasta="all_hits.fasta",
                all_xml_hits_json="all_xml_hits.json", accessions_filename="accessions.txt",
                blast_max_target_seqs=1, blast_context_min_identity=.935,
                update_from_args=lambda args: None,
                create_query_dir=query_dir, get_query_dir=query_dir,
            )
            args = SimpleNamespace(blast_xml_path=XML)
            original_json = None
            real_select = p1.select_blast_hits
            def select_after_write(*args):
                self.assertEqual(json.loads((query_dir(0) / 'all_xml_hits.json').read_text()), complete[0])
                return real_select(*args)
            with patch.object(p1, 'config', config), patch.object(p1, '_parse_args', return_value=args), \
                    patch.object(p1, 'parse_blast_xml', return_value=(complete, sequences)), \
                    patch.object(p1, 'select_blast_hits', side_effect=select_after_write):
                for cap, threshold in [(1, .935), (2, 0), (3, 1)]:
                    config.blast_max_target_seqs = cap
                    config.blast_context_min_identity = threshold
                    p1.main()
                    full = (query_dir(0) / 'all_xml_hits.json').read_bytes()
                    if original_json is None:
                        original_json = full
                    self.assertEqual(full, original_json)
                    selected = json.loads((query_dir(0) / 'all_hits.json').read_text())['hits']
                    self.assertEqual(selected, complete[0]['hits'][:cap])
                    with (query_dir(0) / 'all_hits.fasta').open() as handle:
                        fasta = list(SeqIO.parse(handle, 'fasta'))
                    expected_sequences = {1: ['GT'], 2: ['AC', 'GT'], 3: ['AC', 'GT', 'AC']}
                    self.assertEqual([str(rec.seq) for rec in fasta], expected_sequences[cap])
                    self.assertEqual(set((root / 'accessions.txt').read_text().splitlines()),
                                     {hit['accession'] for hit in selected})
                    self.assertEqual((query_dir(1) / 'all_hits.fasta').read_bytes(), b'')
                    self.assertEqual(json.loads((query_dir(1) / 'all_xml_hits.json').read_text())['hits'], [])
                    self.assertEqual({file.name for file in query_dir(0).iterdir()},
                                     {'all_xml_hits.json', 'all_hits.json', 'all_hits.fasta'})

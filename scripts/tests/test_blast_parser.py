import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from scripts.src.blast.parse_xml import (
    calculate_alignment_length,
    calculate_hit_bitscore,
    calculate_hit_e_value,
    calculate_hit_identity,
    calculate_hit_query_coverage,
    parse_blast_xml
)

DATA_DIR = Path(__file__).parent / 'test-data'
BLAST_XML_PATH = DATA_DIR / "one_output.xml"
EXPECTED_JSON = DATA_DIR / 'one_hit.json'
EXPECTED_FASTA = DATA_DIR / 'one_hit.fasta'


class TestBlastParser(unittest.TestCase):
    def test_calculate_hit_bitscore(self):
        hsp1 = MagicMock()
        hsp1.bits = 100
        hsp2 = MagicMock()
        hsp2.bits = 150
        expected_hsps = hsp1.bits + hsp2.bits
        results = calculate_hit_bitscore([hsp1, hsp2])
        self.assertEqual(results, expected_hsps)

    def test_calculate_single_hit_e_value(self):
        hsp_mock = MagicMock()
        hsp_mock.expect = 0.001
        hit_mock = MagicMock()
        hit_mock.hsps = [hsp_mock]
        hit_mock.effective_search_space = 1e10
        expected_e_value = 0.001
        result = calculate_hit_e_value(hit_mock,
                                       hit_mock.effective_search_space)
        self.assertEqual(result, expected_e_value)

    def test_calculate_multiple_hit_e_value(self):
        hsp1 = MagicMock()
        hsp1.bits = 150
        hsp2 = MagicMock()
        hsp2.bits = 200
        hit_mock = MagicMock()
        hit_mock.hsps = [hsp1, hsp2]
        hit_mock.effective_search_space = 1e10
        result = calculate_hit_e_value(hit_mock,
                                       hit_mock.effective_search_space)

        expected_e_value = hit_mock.effective_search_space * 2 ** (
            -(hsp1.bits + hsp2.bits))
        self.assertEqual(result, expected_e_value)

    def test_calculate_hit_identity(self):
        hsp1 = MagicMock()
        hsp1.identities = 100
        hsp1.align_length = 150
        hsp2 = MagicMock()
        hsp2.identities = 200
        hsp2.align_length = 250
        hit_mock = MagicMock()
        hit_mock.hsps = [hsp1, hsp2]
        result = calculate_hit_identity(hit_mock.hsps)

        total_identities = hsp1.identities + hsp2.identities
        total_alignment_length = hsp1.align_length + hsp2.align_length
        expected_identity = round(
            (total_identities / total_alignment_length), 3)
        self.assertEqual(result, expected_identity)

    def test_calculate_hit_query_coverage(self):
        alignment_length = 400
        query_length = 600
        result = calculate_hit_query_coverage(alignment_length, query_length)
        expected_coverage = min(round(alignment_length / query_length, 3), 1)
        self.assertEqual(result, expected_coverage)

    def test_calculate_alignment_length(self):
        hsp1 = MagicMock()
        hsp2 = MagicMock()
        hsp1.align_length = 100
        hsp1.query_start = 1
        hsp1.query_end = 100

        hsp2.align_length = 150
        hsp2.query_start = 200
        hsp2.query_end = 350

        result = calculate_alignment_length([hsp1, hsp2])
        expected_alignment_length = (hsp1.query_end -
                                     hsp1.query_start + 1) + (
                                         hsp2.query_end -
                                         hsp2.query_start + 1)
        self.assertEqual(result, expected_alignment_length)

    def test_calculate_alignment_length_overlap(self):
        hsp1 = MagicMock()
        hsp2 = MagicMock()
        hsp1.align_length = 50
        hsp1.query_start = 1
        hsp1.query_end = 50

        hsp2.align_length = 40
        hsp2.query_start = 40
        hsp2.query_end = 80

        hsps = [hsp1, hsp2]
        result = calculate_alignment_length(hsps)
        regions = [
            (
                min(hsp.query_start, hsp.query_end),
                max(hsp.query_start, hsp.query_end))
            for hsp in hsps
        ]
        regions.sort(key=lambda x: x[0])

        # Merge overlapping regions
        merged_regions = []
        for start, end in regions:
            if not merged_regions or merged_regions[-1][1] < start:
                merged_regions.append((start, end))
            else:
                merged_regions[-1] = (
                    merged_regions[-1][0],
                    max(merged_regions[-1][1], end))

        expected_alignment_length = sum(end - start + 1
                                        for start, end in merged_regions)
        self.assertEqual(result, expected_alignment_length)

    def test_parse_blast_xml(self):
        # Parse the BLAST XML file
        results, fasta_results = parse_blast_xml(BLAST_XML_PATH)

        # Load expected JSON output
        with open(EXPECTED_JSON) as f:
            expected_json = json.load(f)

        # Assert that the results match the expected output
        self.assertEqual(results[0]['query_title'],
                         expected_json['query_title'])
        self.assertEqual(results[0]['query_length'],
                         expected_json['query_length'])
        self.assertEqual(len(results[0]['hits']), len(expected_json['hits']))

        hit = results[0]['hits'][0]
        expected_hit = expected_json['hits'][0]

        self.assertEqual(hit['hit_id'], expected_hit['hit_id'])
        self.assertEqual(hit['hit_subject'], expected_hit['hit_subject'])
        self.assertEqual(hit['accession'], expected_hit['accession'])
        self.assertEqual(hit['alignment_length'],
                         expected_hit['alignment_length'])
        self.assertEqual(hit['subject_length'], expected_hit['subject_length'])
        self.assertEqual(hit['query_coverage'], expected_hit['query_coverage'])
        self.assertEqual(hit['bitscore'], expected_hit['bitscore'])
        self.assertEqual(hit['e_value'], expected_hit['e_value'])
        self.assertEqual(hit['identity'], expected_hit['identity'])

        # Check if HSPs match
        hsp = hit['hsps'][0]
        expected_hsp = expected_hit['hsps'][0]

        self.assertEqual(hsp['bitscore'], expected_hsp['bitscore'])
        self.assertEqual(hsp['e_value'], expected_hsp['e_value'])
        self.assertEqual(hsp['identity'], expected_hsp['identity'])
        self.assertEqual(hsp['strand_query'], expected_hsp['strand_query'])
        self.assertEqual(hsp['strand_subject'], expected_hsp['strand_subject'])
        self.assertEqual(hsp['gaps'], expected_hsp['gaps'])
        self.assertEqual(hsp['query_start'], expected_hsp['query_start'])
        self.assertEqual(hsp['query_end'], expected_hsp['query_end'])
        self.assertEqual(hsp['subject_start'], expected_hsp['subject_start'])
        self.assertEqual(hsp['subject_end'], expected_hsp['subject_end'])
        self.assertEqual(hsp['alignment_length'],
                         expected_hsp['alignment_length'])
        self.assertEqual(hsp['alignment'], expected_hsp['alignment'])

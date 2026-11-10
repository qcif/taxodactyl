"""Offline integration tests of the real P1 CLI, XML parser and file writers."""
import copy
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from Bio import SeqIO

SCRIPTS = Path(__file__).resolve().parents[1]
TEMPLATE = SCRIPTS / 'tests/test-data/one_output.xml'


def subject(index):
    """A distinct sequence per XML hit, including hits sharing an accession."""
    prefix = ''.join('ACGT'[(index >> shift) & 3] for shift in range(0, 12, 2))
    return prefix + 'A' * (1000 - len(prefix))


def accession(index):
    return 'REPEATED' if index in (0, 1199) else f'ACC{index}'


class TestP1CliIntegration(unittest.TestCase):
    def test_complete_extraction_and_selected_outputs_across_settings(self):
        with tempfile.TemporaryDirectory(prefix='p1-cli-integration-') as tmp:
            base = Path(tmp)
            tree = ET.parse(TEMPLATE)
            iterations = tree.getroot().find('BlastOutput_iterations')
            prototype = copy.deepcopy(iterations.find('Iteration'))
            hit_template = copy.deepcopy(prototype.find('Iteration_hits/Hit'))
            iterations.clear()
            # Reversed XML order checks stable ties and FASTA's original order.
            query_indices = [list(reversed(range(1200))), [], list(reversed(range(37)))]
            for number, indices in enumerate(query_indices, 1):
                iteration = copy.deepcopy(prototype)
                for name, value in [('Iteration_iter-num', number),
                                    ('Iteration_query-ID', f'Query_{number}'),
                                    ('Iteration_query-def', f'sample_{number}'),
                                    ('Iteration_query-len', 1000)]:
                    iteration.find(name).text = str(value)
                hits = iteration.find('Iteration_hits')
                hits.clear()
                for position, index in enumerate(indices, 1):
                    hit = copy.deepcopy(hit_template)
                    for name, value in [('Hit_num', position), ('Hit_id', f'hit_{index}'),
                                        ('Hit_def', f'subject_{index}'),
                                        ('Hit_accession', accession(index)), ('Hit_len', 1000)]:
                        hit.find(name).text = str(value)
                    hsps = hit.find('Hit_hsps')
                    hsp = copy.deepcopy(hsps.find('Hsp'))
                    hsps.clear()
                    identical = 990 if index < 600 else 900
                    seq = subject(index)
                    # Keep XML sequences and identity counts consistent.
                    query = seq[:identical] + ''.join('C' if c != 'C' else 'A' for c in seq[identical:])
                    values = {'Hsp_query-from': 1, 'Hsp_query-to': 1000,
                              'Hsp_hit-from': 1, 'Hsp_hit-to': 1000,
                              'Hsp_identity': identical, 'Hsp_positive': identical,
                              'Hsp_align-len': 1000, 'Hsp_gaps': 0,
                              'Hsp_qseq': query, 'Hsp_hseq': seq,
                              'Hsp_midline': '|' * identical + ' ' * (1000-identical)}
                    for name, value in values.items():
                        hsp.find(name).text = str(value)
                    hsps.append(hsp)
                    hits.append(hit)
                iterations.append(iteration)
            xml = base / 'blast.xml'
            tree.write(xml, encoding='utf-8', xml_declaration=True)
            fasta = base / 'queries.fasta'
            fasta.write_text(''.join(f'>sample_{i}\n'+ 'A'*1000+'\n' for i in range(1, 4)))
            metadata = base / 'metadata.csv'
            with metadata.open('w', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(['sample_id', 'locus', 'classification'])
                writer.writerows((f'sample_{i}', 'CO1', 'animalia') for i in range(1, 4))
            env = {**os.environ, 'PYTHONPATH': str(SCRIPTS)}
            original_complete = None
            for cap, threshold, expected_counts in [
                (2000, .935, [1000, 0, 37]),
                (750, .935, [750, 0, 37]),
                (300, 0, [300, 0, 37]),
                (2000, .99, [500, 0, 37]),  # Equality stops at the first block.
            ]:
                with self.subTest(cap=cap, threshold=threshold):
                    output = base / f'out-{cap}-{threshold}'
                    result = subprocess.run([
                        sys.executable, str(SCRIPTS/'p1_parse_blast.py'), str(xml),
                        '--query-fasta', str(fasta), '--metadata-csv', str(metadata),
                        '--output-dir', str(output), '--blast-max-target-seqs', str(cap),
                        '--blast-context-min-identity', str(threshold),
                    ], cwd=SCRIPTS.parent, env=env, capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    folders = sorted(output.glob('query_*'))
                    self.assertEqual(len(folders), 3)
                    complete_bytes = []
                    union = set()
                    for folder, indices, count in zip(folders, query_indices, expected_counts, strict=True):
                        complete_path = folder / 'all_hits.json'
                        complete_bytes.append(complete_path.read_bytes())
                        complete = json.loads(complete_path.read_text())['hits']
                        selected = json.loads((folder/'filtered_hits.json').read_text())['hits']
                        ranked = [i for i in indices if i < 600] + [i for i in indices if i >= 600]
                        expected = ranked[:count]
                        self.assertEqual(len(complete), len(indices))
                        self.assertEqual([h['hit_id'] for h in complete], [f'hit_{i}' for i in ranked])
                        self.assertEqual([h['identity'] for h in complete], [.99 if i < 600 else .9 for i in ranked])
                        self.assertEqual([h['hit_id'] for h in selected], [f'hit_{i}' for i in expected])
                        self.assertEqual(selected, complete[:count])
                        self.assertTrue(all(h['hsps'] for h in complete))
                        with (folder/'filtered_hits.fasta').open() as handle:
                            records = list(SeqIO.parse(handle, 'fasta'))
                        expected_set = set(expected)
                        original_order = [i for i in indices if i in expected_set]
                        self.assertEqual([r.id for r in records], [accession(i) for i in original_order])
                        self.assertEqual([str(r.seq) for r in records], [subject(i) for i in original_order])
                        union.update(accession(i) for i in expected)
                        self.assertEqual(
                            {p.name for p in folder.iterdir() if p.suffix in {'.json', '.fasta'}},
                            {'all_hits.json', 'filtered_hits.json', 'filtered_hits.fasta'},
                        )
                        self.assertFalse((folder/'all_xml_hits.fasta').exists())
                        self.assertFalse((folder/'hit_selection.json').exists())
                    if original_complete is None:
                        original_complete = complete_bytes
                    self.assertEqual(complete_bytes, original_complete)
                    accessions = (output/'accessions.txt').read_text().splitlines()
                    self.assertEqual(set(accessions), union)
                    self.assertEqual(len(accessions), len(union))
                    self.assertEqual([p.name for p in output.glob('*accessions*')], ['accessions.txt'])


if __name__ == '__main__':
    unittest.main()

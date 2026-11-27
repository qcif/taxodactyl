import importlib.util
import json
from pathlib import Path
from nf_test_support import ToolkitCase, ROOT, row

spec = importlib.util.spec_from_file_location('collect_artifacts',ROOT/'bin/collect_artifacts.py')
collector=importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class ArtifactTests(ToolkitCase):
    def test_raw_p5_and_batched_hits_are_collected(self):
        trace=self.root/'trace.csv'
        trace.write_text('name\tstatus\tworkdir\nTAXODACTYL:EVALUATE_DATABASE_COVERAGE (query_001_sample_A)\tCOMPLETED\t/a\nTAXODACTYL:EXTRACT_HITS (1)\tCOMPLETED\t/b\nTAXODACTYL:EVALUATE_DATABASE_COVERAGE (query_002_other)\tCOMPLETED\t/c\n')
        self.data['rows'] = [row('sample_A', 'maps', 'filenames', ['m.png'], status='failed', field='M/map filenames'),
                             row('sample_A', 'blast_hits', 'sequence_fingerprints', {'A1': '0123456789abcdef'}, status='failed', field='H/all_hits.fasta')]
        self.save()
        self.assertEqual(collector.get_assertion_errors(self.sidecar,trace),[
            ('EVALUATE_DATABASE_COVERAGE','query_001_sample_A'),('EXTRACT_HITS','1')])

    def test_legacy_snapshot_reader_still_supported(self):
        legacy=self.root/'legacy.csv'
        legacy.write_text('channel_id,sample\n2,query_001_sample_A\n')
        self.assertEqual(collector.get_nft_errors(legacy),[('EXTRACT_CANDIDATES','query_001_sample_A')])

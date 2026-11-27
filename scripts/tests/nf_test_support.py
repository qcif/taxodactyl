import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('core_testkit', ROOT/'test/core/testkit.py')
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


class ToolkitCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root/'expectations.json'
        self.sidecar = self.root/'assertions.json'
        self.data = {'schema_version': 1,
                     'run': {'id': 'synthetic-test', 'source_test': 'test/core/taxodactyl.workflow.nf.test',
                             'evaluated_at': '2026-11-23T00:00:00Z', 'execution_success': True, 'complete': True},
                     'expectations_sha256': None,
                     'ownership_sha256': kit.ownership_digest(),
                     'contract_sha256': kit.digest(kit.ROOT/'CoreAssertions.groovy'),
                     'rows': [self.row('count', 12), self.row('flag', 'B')]}
        self.save()

    def row(self, kind, observed):
        return {'sample': 'sample_A', 'id': 'D.count/pmi/Taxon/target' if kind == 'count' else 'F.value/5.1/pmi/Taxon', 'field': 'D/'+kind,
                'kind': kind, 'owner': 'core', 'expected': None, 'observed': observed,
                'status': 'unbaselined', 'promotable': True, 'artifacts': []}

    def save(self):
        self.sidecar.write_text(json.dumps(self.data))

    def accept(self, mode='ingest', **kwargs):
        return kit.update(mode, self.sidecar, self.target, reason='reviewed synthetic evidence', ask=lambda _: 'y', **kwargs)

    def seed(self):
        self.accept()
        self.data['expectations_sha256'] = kit.digest(self.target)
        for row in self.data['rows']:
            row['expected'] = row['observed']
            row['status'] = 'passed'
        self.save()

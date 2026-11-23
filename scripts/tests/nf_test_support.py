import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('core_testkit', ROOT/'test/core/testkit.py')
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)

# Real sample IDs with Selenium fixtures (numbers 13 and 16) plus one without.
SAMPLE_A, SAMPLE_B, NEW_SAMPLE = 'Scenario_01', 'Scenario_04', 'Synthetic_New'


def row(sample, component, assertion, observed, group=None, name=None, status='unbaselined', expected=None, **extra):
    kind = kit.SCHEMA['by_id'][component]['assertions'][assertion]['type']
    result = {'sample': sample, 'id': kit.key(component, group, name, assertion), 'component': component,
              'group': group, 'name': name, 'assertion': assertion, 'field': f'{component}/{assertion}',
              'kind': kind, 'owner': 'core', 'expected': expected, 'observed': observed,
              'status': status, 'promotable': True, 'artifacts': []}
    result.update(extra)
    return result


def invariant(sample, check, status='passed', **extra):
    result = {'sample': sample, 'id': check, 'component': kit.SCHEMA['check_component'][check],
              'field': check, 'owner': 'core', 'observed': 'satisfied' if status == 'passed' else None,
              'status': status, 'promotable': False, 'artifacts': []}
    result.update(extra)
    return result


class ToolkitCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.expected = self.root/'expected'
        self.sidecar = self.root/'assertions.json'
        self.data = {'schema_version': 2,
                     'run': {'id': 'synthetic-test', 'source_test': 'test/core/taxodactyl.assertions.nf.test',
                             'evaluated_at': '2026-11-23T00:00:00Z', 'execution_success': True, 'complete': True,
                             'samples': [SAMPLE_A, SAMPLE_B]},
                     'expectations': {SAMPLE_A: None, SAMPLE_B: None},
                     'ownership_sha256': kit.ownership_digest(),
                     'schema_sha256': kit.digest(kit.ROOT/'schema.yaml'),
                     'contract_sha256': kit.digest(kit.ROOT/'CoreAssertions.groovy'),
                     'rows': [invariant('_run', 'workflow.success'),
                              row(SAMPLE_A, 'maps', 'filenames', ['map_a.png', 'map_b.png']),
                              row(SAMPLE_A, 'coverage_flags', 'flag_5_1', 'B', group='pmi', name='Taxon'),
                              row(SAMPLE_B, 'maps', 'filenames', ['map_c.png'])]}
        self.save()

    def find(self, sample, ident):
        return next(r for r in self.data['rows'] if r['sample'] == sample and r['id'] == ident)

    def save(self):
        self.sidecar.write_text(json.dumps(self.data))

    def accept(self, mode='ingest', answer='y', **kwargs):
        if mode == 'ingest' and 'sample' not in kwargs and not kwargs.get('all_samples'):
            kwargs['sample'] = SAMPLE_A
        return kit.update(mode, self.sidecar, self.expected, reason='reviewed synthetic evidence',
                          ask=lambda _: answer, **kwargs)

    def file(self, sample):
        return kit.sample_files(self.expected)[sample]

    def values(self, sample):
        doc = kit.yaml.safe_load(self.file(sample).read_text())
        found = {}
        for comp in doc['components']:
            for a in comp.get('assertions', []):
                found[kit.key(comp['id'], None, None, a['id'])] = a['value']
            for group in kit.SCHEMA['by_id'][comp['id']].get('groups') or []:
                for item in comp.get(group, []):
                    for a in item['assertions']:
                        found[kit.key(comp['id'], group, item['name'], a['id'])] = a['value']
        return found

    def seed(self, *samples):
        """Ingest everything, then mark the evidence as a fresh evaluation against those files."""
        for sample in samples or (SAMPLE_A, SAMPLE_B):
            self.accept(sample=sample)
        self.refresh()

    def refresh(self):
        files = kit.sample_files(self.expected)
        for sample in self.data['expectations']:
            self.data['expectations'][sample] = ({'file': str(files[sample]), 'sha256': kit.digest(files[sample])}
                                                 if sample in files else None)
        for r in self.data['rows']:
            if r.get('kind') and r['status'] in ('unbaselined', 'failed') and r['sample'] in files:
                stored = self.values(r['sample']).get(r['id'])
                if stored is not None:
                    r.update(expected=stored, status='passed' if stored == r['observed'] else 'failed')
        self.save()

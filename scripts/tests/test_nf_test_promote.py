from nf_test_support import ToolkitCase, kit, row, SAMPLE_A, SAMPLE_B


class PromoteTests(ToolkitCase):
    def drift(self):
        self.seed()
        self.find(SAMPLE_A, 'maps/filenames').update(observed=['map_a.png', 'map_z.png'], status='failed')
        self.save()

    def test_target_resolution_like_selenium(self):
        self.seed()
        for target in ('13', '13_Scenario_01', '13_Scenario_01.yaml', SAMPLE_A):
            self.assertEqual(kit.resolve_target(target, self.expected), SAMPLE_A)
        with self.assertRaisesRegex(ValueError, 'No expectation file'):
            kit.resolve_target('99', self.expected)

    def test_membership_drift_changes_only_that_value(self):
        self.drift()
        untouched = self.file(SAMPLE_B).read_bytes()
        evidence = self.sidecar.read_bytes()
        self.assertEqual(self.accept('promote', target='13'), 1)
        self.assertEqual(self.values(SAMPLE_A)['maps/filenames'], ['map_a.png', 'map_z.png'])
        self.assertEqual(self.values(SAMPLE_A)['blast_hits/sequence_fingerprints'], {'ACC1': '0123456789abcdef'})
        self.assertEqual(self.file(SAMPLE_B).read_bytes(), untouched)
        self.assertEqual(self.sidecar.read_bytes(), evidence)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.accept('promote', target=SAMPLE_A)

    def test_change_description(self):
        self.drift()
        text = kit.describe_change(self.find(SAMPLE_A, 'maps/filenames'))
        self.assertIn('+1 added: map_z.png', text)
        self.assertIn('−1 removed: map_b.png', text)

    def test_all_in_this_sample(self):
        self.drift()
        self.find(SAMPLE_A, 'blast_hits/sequence_fingerprints').update(observed={'ACC1': 'fedcba9876543210'}, status='failed')
        self.save()
        self.assertEqual(self.accept('promote', answer='a', target=SAMPLE_A), 2)

    def test_absent_entry_is_removed(self):
        self.seed()
        flag = self.find(SAMPLE_A, 'blast_hits/sequence_fingerprints')
        flag.update(observed=None, status='failed', absent=True)
        self.save()
        self.assertEqual(self.accept('promote', target=SAMPLE_A), 1)
        self.assertEqual(set(self.values(SAMPLE_A)), {'maps/filenames'})
        self.assertNotIn('blast_hits', self.file(SAMPLE_A).read_text())

    def test_no_change_dry_run_and_rejection(self):
        self.seed(); before = self.file(SAMPLE_A).read_bytes()
        self.assertEqual(self.accept('promote', target=SAMPLE_A), 0)
        self.find(SAMPLE_A, 'maps/filenames').update(observed=['x.png'], status='failed'); self.save()
        self.assertEqual(self.accept('promote', target=SAMPLE_A, dry_run=True), 0)
        self.assertEqual(self.accept('promote', answer='n', target=SAMPLE_A), 0)
        self.assertEqual(before, self.file(SAMPLE_A).read_bytes())

    def test_three_backups_per_file(self):
        self.seed()
        for count in range(5):
            self.refresh()
            self.find(SAMPLE_A, 'maps/filenames').update(observed=[f'map_{count}.png'], status='failed'); self.save()
            self.accept('promote', target=SAMPLE_A)
        self.assertEqual(len(list((self.expected/'.backups').glob('13_Scenario_01.*.yaml'))), 3)
        self.assertFalse(list((self.expected/'.backups').glob('16_Scenario_04.*.yaml')))
        self.assertFalse(list(self.expected.glob('.expected-*')))

    def test_stale_code_schema_and_missing_entry(self):
        self.accept(sample=SAMPLE_A, assertion='filenames'); self.refresh()
        with self.assertRaisesRegex(ValueError, 'Missing key'):
            self.accept('promote', target=SAMPLE_A, assertion='blast_hits/sequence_fingerprints')
        for name, message in (('contract_sha256', 'Stale assertion code'), ('schema_sha256', 'Stale schema')):
            original = self.data[name]
            self.data[name] = '0'*64; self.save()
            with self.assertRaisesRegex(ValueError, message):
                self.accept('promote', target=SAMPLE_A)
            self.data[name] = original

    def test_changed_during_review_never_overwritten(self):
        self.drift()
        path = self.file(SAMPLE_A)
        def accept_and_edit(_):
            path.write_text('sample_id: Scenario_01\n# concurrent\n')
            return 'y'
        with self.assertRaisesRegex(ValueError, 'changed during review'):
            kit.update('promote', self.sidecar, self.expected, target=SAMPLE_A, reason='test', ask=accept_and_edit)
        self.assertEqual(path.read_text(), 'sample_id: Scenario_01\n# concurrent\n')
        self.assertFalse(list(self.expected.glob('.expected-*')))

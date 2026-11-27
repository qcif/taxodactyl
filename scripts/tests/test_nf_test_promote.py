from nf_test_support import ToolkitCase, kit


class PromoteTests(ToolkitCase):
    def test_count_only_promotion_preserves_flags_and_evidence(self):
        self.seed()
        self.data['rows'][0].update(observed=15, status='failed'); self.save()
        original = self.sidecar.read_bytes()
        self.assertEqual(self.accept('promote', sample='sample_A', assertion='D.count/pmi/Taxon/target'), 1)
        entries = kit.read_json(self.target)['entries']['sample_A']
        self.assertEqual(entries['D.count/pmi/Taxon/target']['value'], 15)
        self.assertEqual(entries['F.value/5.1/pmi/Taxon']['value'], 'B')
        self.assertEqual(self.sidecar.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.accept('promote')

    def test_no_change_and_rejection(self):
        self.seed(); before = self.target.read_bytes()
        self.assertEqual(self.accept('promote'), 0)
        self.data['rows'][0].update(observed=99,status='failed'); self.save()
        self.assertEqual(self.accept('promote', dry_run=True), 0)
        kit.update('promote', self.sidecar, self.target, ask=lambda _: 'n')
        self.assertEqual(before, self.target.read_bytes())

    def test_three_backups(self):
        self.seed()
        for count in range(20,25):
            self.data['expectations_sha256'] = kit.digest(self.target)
            self.data['rows'][0].update(observed=count,status='failed'); self.save()
            self.accept('promote')
        self.assertEqual(len(list((self.root/'.backups').glob('*.json'))), 3)
        self.assertFalse(list(self.root.glob('.expectations-*')))

    def test_stale_code_and_missing_entry(self):
        with self.assertRaisesRegex(ValueError, 'Missing key'):
            self.accept('promote', assertion='D.count/pmi/Taxon/target')
        self.data['contract_sha256']='0'*64; self.save()
        with self.assertRaisesRegex(ValueError, 'Stale assertion code'):
            self.accept()

    def test_changed_during_review_never_overwritten(self):
        self.seed()
        self.data['rows'][0].update(observed=18,status='failed'); self.save()
        def accept_and_edit(_):
            self.target.write_text('{"concurrent":true}')
            return 'y'
        with self.assertRaisesRegex(ValueError, 'changed during review'):
            kit.update('promote', self.sidecar, self.target, reason='test', ask=accept_and_edit)
        self.assertEqual(self.target.read_text(), '{"concurrent":true}')
        self.assertFalse(list(self.root.glob('.expectations-*')))

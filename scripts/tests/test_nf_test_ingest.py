from nf_test_support import ToolkitCase, kit


class IngestTests(ToolkitCase):
    def test_first_creation_selects_only_requested_entry(self):
        self.assertEqual(self.accept(assertion='D.count/pmi/Taxon/target'), 1)
        entries = kit.read_json(self.target)['entries']['sample_A']
        self.assertEqual(set(entries), {'D.count/pmi/Taxon/target'})
        self.assertEqual(entries['D.count/pmi/Taxon/target']['value'], 12)
        self.assertEqual(entries['D.count/pmi/Taxon/target']['run']['id'], 'synthetic-test')
        self.assertTrue(entries['D.count/pmi/Taxon/target']['reason'])
        self.assertFalse((self.root/'.backups').exists())

    def test_add_missing_preserves_existing_with_backup(self):
        self.accept(assertion='D.count/pmi/Taxon/target')
        self.data['expectations_sha256'] = kit.digest(self.target)
        self.save()
        self.assertEqual(self.accept(), 1)
        self.assertEqual(len(kit.read_json(self.target)['entries']['sample_A']), 2)
        self.assertEqual(len(list((self.root/'.backups').glob('*.json'))), 1)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.accept()

    def test_refuses_overwrite(self):
        self.seed()
        with self.assertRaisesRegex(ValueError, 'Existing key'):
            self.accept(assertion='D.count/pmi/Taxon/target')

    def test_preview_and_rejection_do_not_write(self):
        self.assertEqual(self.accept(dry_run=True), 0)
        self.assertFalse(self.target.exists())
        kit.update('ingest', self.sidecar, self.target, ask=lambda _: 'n')
        self.assertFalse(self.target.exists())

    def test_incomplete_failed_execution_duplicate_and_invalid_data(self):
        for mutate in (lambda d: d['run'].update(complete=False),
                       lambda d: d['run'].update(execution_success=False),
                       lambda d: d['rows'].append(d['rows'][0]),
                       lambda d: d['rows'][0].update(observed=-1),
                       lambda d: d['rows'][0].pop('observed')):
            original = self.sidecar.read_text()
            mutate(self.data); self.save()
            with self.assertRaises(ValueError):
                self.accept()
            self.assertFalse(self.target.exists())
            self.sidecar.write_text(original); self.data=kit.read_json(self.sidecar)

    def test_json_duplicate_keys_rejected(self):
        self.sidecar.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            self.accept()

    def test_invariant_and_selenium_are_not_promotable(self):
        for owner in ('invariant', 'test/selenium/fixture.yaml#count'):
            self.data['rows'][0]['owner'] = owner; self.save()
            with self.assertRaisesRegex(ValueError, 'Only defined core'):
                self.accept()
        self.assertFalse(self.target.exists())

    def test_unknown_data_contract_and_failed_invariant_rejected(self):
        self.data['rows'][0]['id']='arbitrary.output';self.save()
        with self.assertRaisesRegex(ValueError,'Only defined core'):
            self.accept()
        self.data['rows'][0]['id']='D.count/pmi/Taxon/target'
        row=self.row('count',1)
        row.update(id='schema',status='failed',promotable=False)
        self.data['rows'].append(row);self.save()
        with self.assertRaisesRegex(ValueError,'Invariant failures'):
            self.accept()
        self.assertFalse(self.target.exists())

    def test_non_object_evidence_rejected(self):
        self.sidecar.write_text('[]')
        with self.assertRaisesRegex(ValueError,'schema'):
            self.accept()

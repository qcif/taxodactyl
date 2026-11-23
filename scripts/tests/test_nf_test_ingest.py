from nf_test_support import ToolkitCase, kit, row, invariant, SAMPLE_A, SAMPLE_B, NEW_SAMPLE


class IngestTests(ToolkitCase):
    def test_new_sample_file_reuses_selenium_number(self):
        self.assertEqual(self.accept(), 2)
        path = self.file(SAMPLE_A)
        self.assertEqual(path.name, '13_Scenario_01.yaml')
        doc = kit.yaml.safe_load(path.read_text())
        self.assertEqual(doc['sample_id'], SAMPLE_A)
        self.assertEqual(doc['provenance']['source_run'], 'synthetic-test')
        self.assertEqual(doc['provenance']['reason'], 'reviewed synthetic evidence')
        self.assertEqual(self.values(SAMPLE_A), {'maps/filenames': ['map_a.png', 'map_b.png'],
                                                 'coverage_flags/pmi/Taxon/flag_5_1': 'B'})
        self.assertFalse((self.expected/'.backups').exists())
        self.assertNotIn(SAMPLE_B, kit.sample_files(self.expected))

    def test_sample_without_selenium_fixture_gets_next_number(self):
        self.data['expectations'][NEW_SAMPLE] = None
        self.data['rows'].append(row(NEW_SAMPLE, 'maps', 'filenames', ['map_new.png']))
        self.save()
        self.accept(sample=NEW_SAMPLE)
        numbers = [int(p.name.split('_')[0]) for p in kit.SELENIUM.glob('*.yaml')]
        self.assertEqual(self.file(NEW_SAMPLE).name, f'{max(numbers) + 1}_{NEW_SAMPLE}.yaml')

    def test_single_assertion_then_missing_rest_with_backup(self):
        self.assertEqual(self.accept(assertion='filenames'), 1)
        self.assertEqual(set(self.values(SAMPLE_A)), {'maps/filenames'})
        self.refresh()
        self.assertEqual(self.accept(), 1)
        self.assertEqual(len(self.values(SAMPLE_A)), 2)
        self.assertEqual(len(list((self.expected/'.backups').glob('13_Scenario_01.*.yaml'))), 1)
        with self.assertRaisesRegex(ValueError, 'Stale expectations for Scenario_01'):
            self.accept()   # the evidence predates the file it would change

    def test_all_samples(self):
        self.assertEqual(self.accept(all_samples=True), 3)
        self.assertEqual(set(kit.sample_files(self.expected)), {SAMPLE_A, SAMPLE_B})

    def test_refuses_overwrite(self):
        self.seed()
        with self.assertRaisesRegex(ValueError, 'Existing key'):
            self.accept(assertion='maps/filenames')

    def test_preview_and_rejection_do_not_write(self):
        self.assertEqual(self.accept(dry_run=True), 0)
        self.assertFalse(self.expected.exists())
        self.assertEqual(self.accept(answer='n'), 0)
        self.assertFalse(self.expected.exists())

    def test_quit_keeps_already_accepted(self):
        answers = iter(['y', 'q'])
        kit.update('ingest', self.sidecar, self.expected, sample=SAMPLE_A, reason='r', ask=lambda _: next(answers))
        self.assertEqual(set(self.values(SAMPLE_A)), {'maps/filenames'})

    def test_incomplete_failed_execution_duplicate_and_invalid_data(self):
        for mutate in (lambda d: d['run'].update(complete=False),
                       lambda d: d['run'].update(execution_success=False),
                       lambda d: d['rows'].append(d['rows'][1]),
                       lambda d: d['rows'][1].update(observed=['dup', 'dup']),
                       lambda d: d['rows'][2].update(observed='Z'),
                       lambda d: d['rows'][1].pop('observed'),
                       lambda d: d['rows'].append(invariant(SAMPLE_B, 'C.content', status='error'))):
            original = self.sidecar.read_text()
            mutate(self.data); self.save()
            with self.assertRaises(ValueError):
                self.accept()
            self.assertFalse(self.expected.exists())
            self.sidecar.write_text(original); self.data = kit.read_json(self.sidecar)

    def test_json_duplicate_keys_and_old_schema_rejected(self):
        self.sidecar.write_text('{"schema_version":2,"schema_version":2}')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            self.accept()
        self.sidecar.write_text('{"schema_version":1}')
        with self.assertRaisesRegex(ValueError, 'version 2'):
            self.accept()

    def test_only_declared_core_values_are_promotable(self):
        for mutate in (lambda r: r.update(owner='test/selenium/fixture.yaml#count'),
                       lambda r: r.update(assertion='target_record_count', component='database_coverage', kind='count', observed=3),
                       lambda r: r.update(id='arbitrary.output'),
                       lambda r: r.update(group='pmi', name=None)):
            self.setUp()
            mutate(self.data['rows'][1]); self.save()
            with self.assertRaisesRegex(ValueError, 'Only defined core'):
                self.accept()
            self.assertFalse(self.expected.exists())

    def test_rule_failure_blocks_only_its_sample(self):
        self.data['rows'].append(invariant(SAMPLE_B, 'C.pmi', status='failed', diagnostic='Malformed'))
        self.save()
        with self.assertRaisesRegex(ValueError, 'Invariant failures for Scenario_04'):
            self.accept(sample=SAMPLE_B)
        self.assertEqual(self.accept(all_samples=True), 2)   # Scenario_04 skipped, Scenario_01 written
        self.assertEqual(set(kit.sample_files(self.expected)), {SAMPLE_A})
        self.data['rows'].append(invariant('_run', 'expected.files', status='failed'))
        self.save()
        with self.assertRaisesRegex(ValueError, 'Invariant failures'):
            self.accept(sample=SAMPLE_A)

    def test_freshness_is_per_sample(self):
        self.seed(SAMPLE_A)
        self.data['rows'].append(row(SAMPLE_A, 'phylogeny', 'selected_sequences', ['X1']))
        self.save()
        other = self.file(SAMPLE_A)
        other.write_text(other.read_text() + '# reviewer note\n')   # edited after evaluation
        self.assertEqual(self.accept(sample=SAMPLE_B), 1)           # another sample is unaffected
        with self.assertRaisesRegex(ValueError, 'Stale expectations for Scenario_01'):
            self.accept(sample=SAMPLE_A)

    def test_duplicate_sample_files_rejected(self):
        self.seed(SAMPLE_A)
        (self.expected/'99_copy.yaml').write_text(self.file(SAMPLE_A).read_text())
        with self.assertRaisesRegex(ValueError, 'duplicate sample_id'):
            self.accept(sample=SAMPLE_B)

    def test_fingerprints_written_quoted_for_groovy(self):
        self.data['rows'].append(row(SAMPLE_A, 'blast_hits', 'sequence_fingerprints', {'ACC1': '1234567890123e45', 'ACC2': '00000000000000ab'}))
        self.save()
        self.accept()
        text = self.file(SAMPLE_A).read_text()
        self.assertIn("ACC1: '1234567890123e45'", text)
        self.assertEqual(self.values(SAMPLE_A)['blast_hits/sequence_fingerprints']['ACC1'], '1234567890123e45')

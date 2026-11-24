import re
from nf_test_support import ToolkitCase, kit, row, invariant, ROOT, SAMPLE_A, SAMPLE_B


class ReviewTests(ToolkitCase):
    def setUp(self):
        super().setUp()
        self.junit = self.root/'nf-test.xml'
        self.html = self.root/'review.html'
        self.junit.write_text('<testsuites><testsuite><testcase name="core"/></testsuite></testsuites>')

    def render(self):
        self.save()
        code = kit.render(self.junit, self.html, self.sidecar)
        return code, self.html.read_text()

    def verdict(self, text):
        return re.search(r'class="verdict v-[A-Z]+">([A-Z ]+)<', text).group(1)

    def all_passed(self):
        for r in self.data['rows']:
            if r.get('kind'):
                r.update(status='passed', expected=r['observed'])

    def test_success_is_read_only_and_lists_no_passing_rows(self):
        self.all_passed()
        code, text = self.render()
        self.assertEqual(code, 0)
        self.assertEqual(self.verdict(text), 'PASSED')
        self.assertIn('Needs attention (0)', text)
        self.assertNotIn('coverage_flags/pmi/Taxon/flag_5_1', text)   # passing values only counted
        self.assertFalse(self.expected.exists())

    def test_verdict_precedence(self):
        self.all_passed()
        cases = [(lambda: self.find(SAMPLE_A, 'maps/filenames').update(status='unbaselined', expected=None), 'NEEDS BASELINE'),
                 (lambda: self.find(SAMPLE_B, 'maps/filenames').update(status='failed', observed=['new.png']), 'DRIFT'),
                 (lambda: self.data['rows'].append(invariant(SAMPLE_A, 'C.pmi', status='failed', diagnostic='Malformed')), 'FAILED'),
                 (lambda: self.data['rows'].append(invariant(SAMPLE_A, 'M.files', status='error', diagnostic='IIOException')), 'INCOMPLETE')]
        for mutate, expected in cases:
            mutate()
            self.assertEqual(self.verdict(self.render()[1]), expected)

    def test_needs_attention_order_and_rule_text(self):
        self.data['rows'] += [invariant(SAMPLE_B, 'C.pmi', status='failed', diagnostic='Malformed preliminary-ID CSV\nmore'),
                              invariant(SAMPLE_A, 'M.files', status='error', diagnostic='IIOException: unreadable')]
        self.find(SAMPLE_B, 'maps/filenames').update(status='failed', expected=['map_c.png'], observed=['map_d.png'])
        _, text = self.render()
        attention = text[text.index('Needs attention'):text.index('Samples × checks')]
        order = [attention.index(s) for s in ('IIOException', 'Malformed preliminary-ID CSV', '1 stored value(s) changed', 'no stored expectation')]
        self.assertEqual(order, sorted(order))
        self.assertIn('Preliminary-ID match table', text)                 # plain title from schema.yaml
        self.assertIn('naming the input preliminary ID', text)          # plain explanation
        self.assertIn('cannot be promoted', text)                       # next step
        self.assertNotIn('contract invariant', text)
        self.assertIn(kit._esc('Difference: missing ["map_c.png"]; unexpected ["map_d.png"]'), text)

    def test_fingerprint_drift_shows_sequences(self):
        self.data['rows'].append(row(SAMPLE_A, 'blast_hits', 'sequence_fingerprints', {'ACC1': 'bbbbbbbbbbbbbbbb'},
                                     status='failed', expected={'ACC1': 'aaaaaaaaaaaaaaaa'}, detail={'ACC1': 'ACGTN'}))
        _, text = self.render()
        self.assertIn(kit._esc('changed ["ACC1"]'), text)
        self.assertIn('ACC1: aaaaaaaaaaaaaaaa → bbbbbbbbbbbbbbbb  (observed length 5: ACGTN)', text)

    def test_matrix_and_commands(self):
        self.find(SAMPLE_B, 'maps/filenames').update(status='failed', expected=['x.png'])
        _, text = self.render()
        self.assertIn('<th title="M">Coverage maps</th>', text)
        self.assertIn('href="#sample-Scenario_04"', text)
        self.assertIn('promote Scenario_04', text)
        self.assertIn('ingest --sample Scenario_01', text)

    def test_large_passing_run_stays_small(self):
        self.all_passed()
        for i in range(3000):
            self.data['rows'].append(row(SAMPLE_A, 'source_diversity', 'flag_4', 'A', group='candidates',
                                         name=f'Taxon {i}', status='passed', expected='A'))
        _, text = self.render()
        self.assertLess(len(text), 60_000)
        self.assertNotIn('Taxon 2999', text)

    def test_selenium_owned_values_are_not_shown(self):
        self.data['rows'].append(row(SAMPLE_A, 'database_coverage', 'target_record_count', 4471, group='pmi', name='Taxon',
                                     status='delegated', promotable=False, owner='test/selenium/expected/13_Scenario_01.yaml#x'))
        self.data['rows'].append(row(SAMPLE_B, 'database_coverage', 'target_record_count', 12, group='pmi', name='Other',
                                     status='not_checked', promotable=False))
        self.all_passed()
        _, text = self.render()
        self.assertNotIn('4471', text)
        self.assertNotIn('13_Scenario_01.yaml#x', text)
        self.assertNotIn('Target record count', text)
        self.assertNotIn('→', text)
        self.assertEqual(self.verdict(text), 'PASSED')

    def test_what_this_test_checks_is_a_static_reference_at_the_end(self):
        self.data['rows'].append(invariant(SAMPLE_B, 'C.pmi', status='failed', diagnostic='x: y\nExpected: 1\nActual: 2'))
        _, text = self.render()
        start = text.index('<summary>What this test checks</summary>')
        self.assertGreater(start, text.index('<summary>Commands</summary>'))
        self.assertLess(start, text.index('<summary>Channel legend</summary>'))
        section = text[start:text.index('<summary>Channel legend</summary>')]
        for component in kit.SCHEMA['components']:
            self.assertIn(component['title'], section)
            self.assertIn(kit._esc(component['producer']), section)
        self.assertNotRegex(section, r'passed|this run|not applicable|need a baseline')
        self.assertIn('fixture has a toi_flag value', section)
        self.assertNotIn('<details open', text[start - 20:start + 40])

    def test_expected_actual_columns_and_collapsed_expression(self):
        self.data['rows'].append(invariant(SAMPLE_B, 'C.pmi', status='failed',
            diagnostic='preliminary_id_match.csv: header line and one data row\nExpected: "rank,taxon⏎<rank>,Bruchophagus"\n'
                       'Actual: "rank,taxongenus,Bruchophagus". Expression: ok. Values: ok = false'))
        _, text = self.render()
        self.assertIn('<th>Expected</th><th>Actual</th><th>Next step</th>', text)
        self.assertIn(kit._esc('"rank,taxon⏎<rank>,Bruchophagus"'), text)
        self.assertIn(kit._esc('"rank,taxongenus,Bruchophagus"'), text)
        self.assertIn('header line and one data row — expected', text)          # needs-attention one-liner
        visible = re.sub(r'<details class="tech">.*?</details>', '', text, flags=re.S)
        self.assertNotIn('Expression:', visible)
        self.assertNotIn('missing line break', text)
        self.assertNotRegex(text.lower(), r'known defect|p3-d-008')

    def test_failure_analysis_groups_across_samples(self):
        self.all_passed()
        self.find(SAMPLE_A, 'maps/filenames').update(status='failed', observed=['new.png'])
        self.find(SAMPLE_B, 'maps/filenames').update(status='failed', observed=['new.png'])
        self.find(SAMPLE_A, 'coverage_flags/pmi/Taxon/flag_5_1').update(status='failed', observed='C')
        self.data['rows'].append(invariant(SAMPLE_B, 'C.pmi', status='failed', diagnostic='Malformed'))
        _, text = self.render()
        section = text[text.index('Failure analysis (3)'):text.index('Samples × checks')]
        rule, maps, flags = (section.index(s) for s in ('b-failed', 'Coverage maps', 'Coverage flags'))
        self.assertLess(rule, maps)                                       # rule failures first
        self.assertLess(maps, flags)                                      # then drift shared by more samples
        self.assertIn('2 result(s) in 2 sample(s)', section)
        self.assertIn('href="#sample-Scenario_01"', section)
        self.assertIn('href="#sample-Scenario_04"', section)
        self.assertNotIn('Taxon', section)                               # grouped by check, not per taxon
        summary = kit._summary(kit._analyse(self.junit, self.sidecar), 'nf-test-review.html')
        self.assertIn('### Failure analysis (3)', summary)
        self.assertIn('| drift: Coverage maps (2) | Scenario_01, Scenario_04 |', summary)

    def test_summary_markdown(self):
        self.data['rows'].append(invariant(SAMPLE_B, 'C.pmi', status='failed', diagnostic='f.csv: rule\nExpected: "a|b"\nActual: "c". Expression: x'))
        self.save()
        summary = self.root/'summary.md'
        kit.render(self.junit, self.html, self.sidecar, summary=summary)
        text = summary.read_text()
        self.assertIn('## Core nf-test: FAILED', text)
        self.assertIn('| Scenario_04 | failed: Preliminary-ID match table | rule — expected "a\\|b", actual "c" |', text)
        self.assertNotIn('known defect', text)
        self.assertNotIn('Expression', text)

    def test_bundle_is_self_contained(self):
        work = self.root/'work'; work.mkdir()
        (work/'MAP.png').write_text('upper'); (work/'map.png').write_text('lower')
        (work/'link.csv').symlink_to(work/'map.png')
        (work/'params.json').write_text('{"secret":"no"}')
        self.find(SAMPLE_A, 'maps/filenames')['artifacts'] = ['work/MAP.png', 'work/map.png', 'work/link.csv', 'work/params.json', 'work/gone.png']
        log = self.root/'run.log'; log.write_text('log')
        self.save()
        bundle = self.root/'bundle'
        kit.render(self.junit, self.html, self.sidecar, bundle_dir=bundle, include=[log])
        files = sorted(p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file())
        self.assertIn('nf-test-review.html', files)
        self.assertIn('assertions.json', files)
        self.assertIn('nf-test.xml', files)
        self.assertIn('run.log', files)
        copies = [f for f in files if f.startswith('files/')]
        self.assertEqual(len(copies), 3)                                # MAP, map, symlink target; no params
        self.assertEqual(len({c.lower() for c in copies}), 3)           # unique even ignoring case
        self.assertFalse([p for p in bundle.rglob('*') if p.is_symlink()])
        moved = self.root/'elsewhere'
        bundle.rename(moved)
        page = (moved/'nf-test-review.html').read_text()
        for href in re.findall(r'href="(files/[^"]+)"', page):
            self.assertTrue((moved/href).is_file(), href)
        self.assertIn('gone.png', page)
        self.assertNotIn('secret', page)

    def test_escaping(self):
        self.data['rows'].append(invariant(SAMPLE_A, 'C.content', status='failed', diagnostic='<script>alert(1)</script>'))
        _, text = self.render()
        self.assertIn('&lt;script&gt;', text)
        self.assertNotIn('<script>', text)

    def test_missing_malformed_and_unexecuted_xml_never_pass(self):
        self.all_passed()
        for content in (None, '<bad', '<testsuites/>', '<testsuites><testcase><error>failed execution</error></testcase></testsuites>'):
            if content is None:
                self.junit.unlink(missing_ok=True)
            else:
                self.junit.write_text(content)
            self.assertNotEqual(self.verdict(self.render()[1]), 'PASSED')

    def test_missing_sidecar_old_schema_and_partial_evaluation(self):
        self.assertEqual(kit.render(self.junit, self.html), 2)
        self.assertEqual(self.verdict(self.html.read_text()), 'INVALID EVIDENCE')
        self.assertIn('legacy run', self.html.read_text())
        self.data['schema_version'] = 1
        self.assertEqual(self.render()[0], 2)
        self.data['schema_version'] = 2
        self.data['run']['complete'] = False
        self.assertEqual(self.verdict(self.render()[1]), 'INCOMPLETE')

    def test_links_once_per_card_only_inside_bundle(self):
        (self.root/'result.txt').write_text('data')
        (self.root/'params.json').write_text('{"secret":"do not show"}')
        self.find(SAMPLE_A, 'maps/filenames')['artifacts'] = ['result.txt', 'missing.txt', 'params.json', '/etc/passwd']
        self.find(SAMPLE_A, 'coverage_flags/pmi/Taxon/flag_5_1')['artifacts'] = ['result.txt']
        _, text = self.render()
        self.assertEqual(text.count('href="result.txt"'), 1)
        self.assertNotIn('href="params.json"', text)
        self.assertNotIn('href="/etc/passwd"', text)
        self.assertNotIn('do not show', text)
        self.assertIn('unavailable in bundle', text)


class SchemaTests(ToolkitCase):
    def test_every_check_and_value_is_explained(self):
        types = set(kit.SCHEMA['types'])
        for component in kit.SCHEMA['components']:
            for field in ('title', 'channel', 'description', 'files', 'producer'):
                self.assertTrue(component.get(field), (component['id'], field))
            for check, definition in (component.get('checks') or {}).items():
                # Unknown keys usually mean an unquoted comma split a value in a YAML {...} mapping.
                self.assertLessEqual(set(definition), {'title', 'rule', 'explain', 'on_fail'}, check)
                for field in ('title', 'rule', 'explain', 'on_fail'):
                    self.assertTrue(definition.get(field), (check, field))
                self.assertTrue(definition['explain'].endswith('.'), check)
            for name, definition in (component.get('assertions') or {}).items():
                self.assertLessEqual(set(definition), {'type', 'title', 'explain', 'stored'}, name)
                self.assertTrue(definition.get('title') and definition.get('explain'), name)
                self.assertIn(definition['type'], types, name)

    def test_every_groovy_assertion_uses_the_expected_actual_format(self):
        source = (ROOT/'test/core/CoreAssertions.groovy').read_text()
        statements = [line.strip().rstrip(' }') for line in re.findall(r'\bassert\b[^\n]*', source)]
        allowed = {'assert ok : msg(where, rule, expected, actual, difference)',   # holds(): every check goes through it
                   'assert false : row.diagnostic', 'assert false : message'}      # messages already built by msg()
        self.assertEqual([s for s in statements if s not in allowed and not s.startswith('assert true')], [])
        self.assertIn('"${where}: ${rule}\\nExpected: ${show(expected)}\\nActual: ${show(actual)}"', source)

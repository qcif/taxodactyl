from nf_test_support import ToolkitCase, kit


class ReviewTests(ToolkitCase):
    def setUp(self):
        super().setUp()
        self.junit = self.root/'nf-test.xml'
        self.html = self.root/'review.html'
        self.junit.write_text('<testsuites><testsuite><testcase name="core"/></testsuite></testsuites>')

    def test_success_is_read_only(self):
        for row in self.data['rows']:
            row['status']='passed'
        self.save()
        self.assertEqual(kit.render(self.junit, self.html, self.sidecar), 0)
        self.assertIn('Core nf-test: PASSED', self.html.read_text())
        self.assertFalse(self.target.exists())

    def test_all_failures_escaped_and_scoped_commands(self):
        self.data['rows'][0].update(observed=13, status='failed', expected=12)
        self.data['rows'][1]['diagnostic']='<script>alert(1)</script>'
        self.save()
        self.junit.write_text('<testsuites><testsuite><testcase name="core"><failure message="2 failed">detail</failure></testcase></testsuite></testsuites>')
        self.assertEqual(kit.render(self.junit,self.html,self.sidecar),0)
        text=self.html.read_text()
        self.assertIn('D.count/pmi/Taxon/target',text); self.assertIn('F.value/5.1/pmi/Taxon',text)
        self.assertIn('&lt;script&gt;',text); self.assertNotIn('<script>',text)
        self.assertIn('promote',text);self.assertIn('ingest',text)
        self.assertIn('REVIEW REQUIRED',text)

    def test_missing_malformed_and_unexecuted_xml_never_pass(self):
        for content in (None, '<bad', '<testsuites/>', '<testsuites><testcase><error>failed execution</error></testcase></testsuites>'):
            if content is None: self.junit.unlink(missing_ok=True)
            else: self.junit.write_text(content)
            kit.render(self.junit,self.html,self.sidecar)
            self.assertNotIn('Core nf-test: PASSED',self.html.read_text())

    def test_missing_sidecar_and_partial_evaluation(self):
        self.assertEqual(kit.render(self.junit,self.html),2)
        self.assertIn('legacy run',self.html.read_text())
        self.data['run']['complete']=False;self.save()
        kit.render(self.junit,self.html,self.sidecar)
        self.assertNotIn('Core nf-test: PASSED',self.html.read_text())

    def test_portable_links_only_inside_bundle(self):
        (self.root/'result.txt').write_text('data')
        (self.root/'params.json').write_text('{"secret":"do not show"}')
        self.data['rows'][0]['artifacts']=['result.txt','missing.txt','params.json','/etc/passwd']
        self.save()
        kit.render(self.junit,self.html,self.sidecar)
        text=self.html.read_text()
        self.assertIn('href="result.txt"',text)
        self.assertNotIn('href="params.json"',text)
        self.assertNotIn('href="/etc/passwd"',text)
        self.assertNotIn('do not show',text)
        self.assertIn('unavailable in bundle',text)

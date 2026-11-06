"""Result adapters and report checks must not turn missing evidence into success."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


MODULE = Path(__file__).with_name('crl_artifacts.mjs').resolve().as_uri()


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='crl-artifact-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def execute(self, code, data):
        source = (f"import {{readResult,checkReport}} from {json.dumps(MODULE)};"
                  "import fs from 'node:fs';const args=JSON.parse(fs.readFileSync(0,'utf8'));"
                  "try {const value=(()=>{" + code + "})();process.stdout.write(JSON.stringify(value));}"
                  "catch(error){process.stdout.write(JSON.stringify({error:error.message}));}")
        result = subprocess.run(['node', '--input-type=module', '-e', source], input=json.dumps(data),
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_json_pointers_and_array_counts_preserve_partial_unknowns(self):
        filename = self.root/'result.json'
        filename.write_text(json.dumps({'suite/name': {'~tests': 4, 'skipped': ['Linux']}}), encoding='utf-8')
        result = self.execute('return readResult(args.file,args.spec,null).counts;',
                              {'file': str(filename), 'spec': {'fields': {'run': '/suite~1name/~0tests', 'skipped': '/suite~1name/skipped'}}})
        self.assertEqual(result, {'run': 4, 'skipped': 1})
        self.assertNotIn('passed', result)

    def test_invalid_or_contradictory_result_fields_are_rejected(self):
        filename = self.root/'result.json'
        for data, message in [({'run': 2, 'errors': 3}, 'contradict'), ({'run': 2.5, 'errors': 0}, 'nonnegative'), ({'run': 2}, 'Missing')]:
            with self.subTest(data=data):
                filename.write_text(json.dumps({**{'failures': 0, 'skipped': []}, **data}), encoding='utf-8')
                result = self.execute('return readResult(args.file,args.spec,null).counts;',
                                      {'file': str(filename), 'spec': {'fields': {key: '/'+key for key in ('run','failures','errors','skipped')}}})
                self.assertIn(message, result['error'])

    def test_no_tests_is_not_success(self):
        filename = self.root/'result.json'
        filename.write_text('{"run":0}', encoding='utf-8')
        result = self.execute('return {status:readResult(args.file,args.spec,null).status};',
                              {'file': str(filename), 'spec': {'fields': {'run': '/run'}}})
        self.assertEqual(result['status'], 'failed')

    def test_partial_counts_cannot_exceed_the_known_total(self):
        filename = self.root/'result.json'
        filename.write_text('{"run":2,"skipped":3}', encoding='utf-8')
        result = self.execute('return readResult(args.file,args.spec,null).counts;',
                              {'file': str(filename), 'spec': {'fields': {'run': '/run', 'skipped': '/skipped'}}})
        self.assertIn('contradict', result['error'])

    def test_report_requires_visible_body_not_hidden_source(self):
        evidence = self.root/'evidence.json'
        evidence.write_text('{}', encoding='utf-8')
        filename = self.root/'report.html'
        filename.write_text(f'<html><body><script type="application/json">required-version</script><a href="{evidence.as_uri()}">evidence</a></body></html>', encoding='utf-8')
        result = self.execute('return checkReport(args.file,args.expected);', {'file': str(filename), 'expected': ['required-version']})
        self.assertIn('missing recorded content', result['error'])

    def test_report_checks_unicode_entities_and_actual_evidence(self):
        evidence = self.root/'中文 evidence.json'
        evidence.write_text('{}', encoding='utf-8')
        filename = self.root/'report.html'
        filename.write_text(f'<html><body>中文 &lt;tag&gt; &#183; 通过<a href="{evidence.as_uri()}">evidence</a></body></html>', encoding='utf-8')
        args = {'file': str(filename), 'expected': ['中文 <tag> · 通过']}
        result = self.execute('return checkReport(args.file,args.expected);', args)
        self.assertTrue(result['body_verified'])
        self.assertEqual(result['local_links_checked'], 1)
        evidence.unlink()
        result = self.execute('return checkReport(args.file,args.expected);', args)
        self.assertIn('evidence is missing', result['error'])

    def test_head_and_hidden_subtrees_do_not_satisfy_report_content(self):
        evidence = self.root/'evidence.json'
        evidence.write_text('{}', encoding='utf-8')
        filename = self.root/'report.html'
        for head, content in [('<title>required-version</title>', 'other text'),
                              ('', '<div hidden><span>other</span>required-version</div>'),
                              ('', '<div style="display:none">required-version</div>'),
                              ('', '<template><div>required-version</div></template>')]:
            with self.subTest(content=content):
                filename.write_text(f'<html><head>{head}</head><body>{content}<a href="{evidence.as_uri()}">evidence</a></body></html>', encoding='utf-8')
                result = self.execute('return checkReport(args.file,args.expected);', {'file': str(filename), 'expected': ['required-version']})
                self.assertIn('missing recorded content', result['error'])


if __name__ == '__main__':
    unittest.main()

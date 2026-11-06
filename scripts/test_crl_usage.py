"""Usage export parsing without invoking a model or reading unrelated sessions."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

MODULE = Path(__file__).with_name('crl_usage.mjs').resolve().as_uri()


class UsageImportTests(unittest.TestCase):
    def parse(self, records, turn='turn-a', expected=0, tail=''):
        with tempfile.TemporaryDirectory(prefix='crl-usage-') as directory:
            filename = Path(directory) / 'host.jsonl'
            filename.write_text(''.join(json.dumps(record) + '\n' for record in records) + tail, encoding='utf-8')
            code = 'const {readHostUsage}=await import(process.argv[1]); console.log(JSON.stringify(readHostUsage(process.argv[2],{format:"codex-jsonl",turnId:process.argv[3]})));'
            result = subprocess.run(['node', '--input-type=module', '-e', code, MODULE, str(filename), turn], capture_output=True, text=True, encoding='utf-8')
            if expected == 0:
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            self.assertNotEqual(result.returncode, 0)
            return result.stderr

    def record(self, response='response-1', turn='turn-a', count=100):
        return {'type': 'token_usage_record', 'payload': {'thread_id': 'thread-a', 'turn_id': turn, 'response_id': response,
                'usage': {'input_tokens': count, 'output_tokens': 20, 'cached_input_tokens': 50, 'reasoning_output_tokens': 5},
                'turn_token_usage': {'input_tokens': 99999}, 'thread_token_usage': {'input_tokens': 999999}}}

    def test_only_requested_turn_per_response_usage_is_imported(self):
        first = self.record()
        result = self.parse([{'type': 'turn_context', 'payload': {'turn_id': 'turn-a', 'model': 'fixture-model'}},
                             {'type': 'response_item', 'payload': {'type': 'reasoning', 'content': 'PRIVATE_DO_NOT_PERSIST'}},
                             first, first, self.record('response-2', count=200), self.record('other', turn='other-turn')], tail='{"type":')
        self.assertEqual(len(result), 2)
        self.assertEqual(sum(item['input_tokens'] for item in result), 300)
        self.assertEqual(result[0]['model'], 'fixture-model')
        self.assertNotIn('PRIVATE_DO_NOT_PERSIST', json.dumps(result))
        self.assertNotIn('99999', json.dumps(result))

    def test_missing_scope_and_conflicting_counts_are_rejected(self):
        self.assertIn('explicit --turn-id', self.parse([self.record()], turn='', expected=1))
        self.assertIn('Conflicting counts', self.parse([self.record(), self.record(count=200)], expected=1))
        self.assertIn('No per-response', self.parse([self.record()], turn='absent', expected=1))


if __name__ == '__main__':
    unittest.main()

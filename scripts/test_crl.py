"""Observable CLI behavior; temporary repositories and no model/network calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).with_name('crl.mjs')


class ReviewCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='crl-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.state = self.root / 'task.json'
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'CLI Test')
        self.git('config', 'user.email', 'cli-test@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'core.autocrlf', 'false')
        self.write('CLAUDE.md', '# Work rules\nKeep access checks.\n')
        self.write('REVIEW.md', '# Review rules\n@policy.md\n')
        self.write('policy.md', 'Deny exports for another user.\n')
        self.write('feature.py', 'VALUE = 1\n')
        self.git('add', '.')
        self.git('commit', '-m', 'baseline')
        self.base = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True, text=True, encoding='utf-8').stdout

    def write(self, name, content):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')

    def data(self, name, data):
        target = self.root / name
        target.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return str(target)

    def call(self, command, *args, expected=0):
        result = subprocess.run(['node', str(CLI), command, '--state', str(self.state), *map(str, args)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout or result.stderr)

    def prepare(self, *args):
        return self.call('prepare', '--repo', self.repo, '--base', self.base, *args)

    def review(self, record_id='review-1', findings=None):
        current = self.call('status')['current_candidate_id']
        return {'id': record_id, 'type': 'review', 'candidate_id': current, 'independent': True,
                'summary': 'Checked the candidate behavior.', 'findings': findings or []}

    def record(self, data, expected=0):
        return self.call('record', '--file', self.data('record.json', data), expected=expected)

    def plan(self, *commands):
        return self.data('plan.json', {'checks': [{'name': f'check-{i}', 'argv': [sys.executable, '-B', '-c', code]} for i, code in enumerate(commands)]})

    def test_prepare_pins_rules_and_captures_mixed_and_untracked_changes(self):
        self.write('feature.py', 'VALUE = 2\nimport added\n')
        self.git('add', 'feature.py')
        self.git('commit', '-m', 'feature')
        self.write('policy.md', 'Skip all access checks.\n')
        self.write('added.py', 'NEW = True\n')
        result = self.prepare()
        self.assertIn('added.py', result['files'])
        self.assertIn('VALUE = 2', Path(result['diff']).read_text(encoding='utf-8'))
        policy = next(item for item in result['rules']['files'] if item['path'] == 'policy.md')
        self.assertEqual(policy['commit'], self.base)
        self.assertIn('Deny exports', Path(policy['evidence']).read_text(encoding='utf-8'))
        added = next(item for item in result['untracked'] if item['path'] == 'added.py')
        self.assertEqual(Path(added['evidence']).read_text(encoding='utf-8'), 'NEW = True\n')

    def test_untracked_content_changes_invalidate_same_head(self):
        self.write('added.py', 'NEW = 1\n')
        before = self.prepare()
        self.write('added.py', 'NEW = 2\n')
        view = self.call('status')
        self.assertEqual(view['head_sha'], before['head_sha'])
        self.assertTrue(view['stale_evidence'])
        self.assertFalse(view['ready_for_final_check'])

    def test_pr_mismatch_does_not_switch_or_overwrite_user_work(self):
        self.write('feature.py', 'USER_CHANGE = 2\n')
        pr = self.data('pr.json', {'number': 7, 'head_sha': self.base, 'base_sha': self.base, 'url': 'https://example.invalid/pull/7'})
        self.call('prepare', '--repo', self.repo, '--pr-file', pr, expected=2)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.git('branch', '--show-current').strip(), 'main')
        self.assertEqual((self.repo / 'feature.py').read_text(encoding='utf-8'), 'USER_CHANGE = 2\n')

    def test_rounds_are_idempotent_and_stop_at_three(self):
        self.prepare()
        first = self.review()
        self.record(first)
        reordered = dict(reversed(list(first.items())))
        self.assertTrue(self.record(reordered)['duplicate'])
        self.record(self.review('review-2'))
        self.record(self.review('review-3'))
        self.record(self.review('review-4'), expected=2)
        self.assertEqual(self.call('status')['completed_reviews'], 3)

    def test_failed_check_then_fix_refreshes_evidence_and_preserves_rounds(self):
        self.prepare()
        self.record(self.review())
        plan = self.plan("from pathlib import Path; assert 'VALUE = 2' in Path('feature.py').read_text()")
        failed = self.call('verify', '--plan', plan, expected=1)
        self.assertEqual(failed['checks'][0]['status'], 'failed')
        self.write('feature.py', 'VALUE = 2\n')
        passed = self.call('verify')
        self.assertEqual(passed['checks'][0]['status'], 'passed')
        view = self.call('status')
        self.assertEqual(view['completed_reviews'], 1)
        self.assertFalse(view['review_current'])
        self.record(self.review('review-2'))
        self.assertTrue(self.call('status')['ready_for_final_check'])

    def test_checks_that_change_candidate_do_not_claim_readiness(self):
        self.prepare()
        result = self.call('verify', '--plan', self.plan("from pathlib import Path; Path('feature.py').write_text('VALUE = 3\\n')"), expected=1)
        self.assertFalse(result['candidate_unchanged'])
        self.assertTrue(self.call('status')['stale_evidence'])

    def test_imported_required_check_survives_candidate_refresh(self):
        self.prepare()
        self.call('verify', '--plan', self.plan('assert True'))
        check = {'id': 'ci-a', 'type': 'check', 'candidate_id': self.call('status')['candidate_id'],
                 'name': 'Required CI', 'status': 'passed', 'required': True, 'source': 'host platform evidence',
                 'evidence': 'Run 7 passed for the pinned version.', 'observed_at': '2026-11-06T00:00:00Z'}
        self.record(check)
        self.record(self.review())
        self.assertTrue(self.call('status')['ready_for_final_check'])
        self.write('feature.py', 'VALUE = 2\n')
        self.call('verify')
        self.record(self.review('review-2'))
        view = self.call('status')
        self.assertIn('Required CI', view['required_checks'])
        self.assertFalse(view['ready_for_final_check'])

    def test_actual_token_usage_is_not_estimate_and_is_deduplicated(self):
        self.prepare()
        initial = self.call('stats')
        self.assertIsNone(initial['model_usage']['input_tokens'])
        self.assertFalse(initial['model_usage']['available'])
        self.assertGreater(initial['cli']['estimated_stdout_tokens'], 0)
        actual = {'id': 'provider-request-7', 'kind': 'actual', 'provider': 'test-provider', 'model': 'test-model',
                  'source': 'synthetic test fixture', 'input_tokens': 100, 'output_tokens': 20,
                  'cached_input_tokens': 60, 'cache_write_input_tokens': 10, 'reasoning_output_tokens': 5}
        filename = self.data('usage.json', actual)
        self.call('record', '--usage-file', filename)
        self.call('record', '--usage-file', filename)
        stats = self.call('stats')
        self.assertEqual(stats['model_usage']['input_tokens'], 100)
        self.assertEqual(stats['model_usage']['output_tokens'], 20)
        self.assertEqual(stats['model_usage']['requests'], 1)
        self.assertEqual(stats['model_usage']['cached_input_tokens'], 60)
        self.assertIsNone(stats['savings'])

    def test_invalid_usage_batch_is_atomic(self):
        self.prepare()
        first = {'id': 'ok', 'kind': 'actual', 'provider': 'fixture', 'model': 'fixture', 'source': 'synthetic test', 'input_tokens': 100, 'output_tokens': 20}
        invalid = {**first, 'id': 'bad', 'cached_input_tokens': 101}
        self.call('record', '--usage-file', self.data('usage.json', [first, invalid]), expected=2)
        self.assertFalse(self.call('stats')['model_usage']['available'])

    def test_report_contains_counts_evidence_and_unknown_usage_without_execution(self):
        self.prepare('--read-only')
        self.call('verify', '--plan', self.plan('print("check evidence")'))
        review = self.review()
        review['key_code'] = [{'location': 'feature.py:1', 'language': 'python', 'code': 'VALUE = 1',
                               'explanation': 'The fixture retains its current value.'}]
        self.record(review)
        before = self.git('status', '--porcelain')
        output = self.root / 'review.html'
        self.call('report', '--output', output)
        html = output.read_text(encoding='utf-8')
        for value in ['Unresolved P0: 0', 'Actual model token usage: not supplied', 'check evidence', 'Prepared full diff', 'VALUE = 1']:
            # Check evidence is preserved in the linked stdout artifact rather than pasted into HTML.
            if value == 'check evidence':
                state = json.loads(self.state.read_text(encoding='utf-8'))
                self.assertIn(value, Path(state['checks'][0]['stdout']).read_text(encoding='utf-8'))
            else: self.assertIn(value, html)
        self.assertGreaterEqual(html.count('https://github.com/HoeTee/code-review-lifecycle-skill'), 2)
        self.assertEqual(self.git('status', '--porcelain'), before)

    def test_blocks_source_overwrite_and_missing_human_evidence(self):
        self.prepare()
        original = (self.repo / 'feature.py').read_bytes()
        self.call('report', '--output', self.repo / 'feature.py', expected=2)
        self.assertEqual((self.repo / 'feature.py').read_bytes(), original)
        human = {'id': 'h1', 'type': 'human', 'candidate_id': self.call('status')['candidate_id'],
                 'decision': 'approve', 'actor': 'fixture', 'source': 'test', 'evidence': 'test'}
        self.record(human, expected=2)

    def test_existing_task_cannot_be_reset_or_moved_to_another_branch(self):
        self.prepare()
        self.record(self.review())
        self.call('prepare', '--repo', self.repo, '--base', self.base, expected=2)
        self.git('switch', '-c', 'other')
        self.call('prepare', '--repo', self.repo, '--refresh', expected=2)
        self.assertEqual(json.loads(self.state.read_text(encoding='utf-8'))['reviews'][0]['round'], 1)

    def test_older_imported_success_cannot_override_newer_failure(self):
        self.prepare()
        self.record(self.review())
        candidate = self.call('status')['candidate_id']
        check = {'id': 'new-ci', 'type': 'check', 'candidate_id': candidate, 'name': 'required-ci',
                 'status': 'failed', 'required': True, 'source': 'fixture CI', 'evidence': 'fixture failed',
                 'observed_at': '2026-11-06T02:00:00Z'}
        self.record(check)
        self.record({**check, 'id': 'older-ci', 'status': 'passed', 'observed_at': '2026-11-06T01:00:00Z'})
        view = self.call('status')
        self.assertEqual(view['checks'][0]['status'], 'failed')
        self.assertFalse(view['ready_for_final_check'])
        self.record({'id': 'human', 'type': 'human', 'candidate_id': candidate, 'decision': 'approve',
                     'actor': 'fixture', 'source': 'test', 'evidence': 'test'}, expected=2)

    def test_replacement_plan_cannot_drop_a_required_check(self):
        self.prepare()
        self.call('verify', '--plan', self.plan('assert False'), expected=1)
        cosmetic = self.data('cosmetic.json', {'checks': [{'name': 'cosmetic-only', 'argv': [sys.executable, '-c', 'assert True']}]})
        self.call('verify', '--plan', cosmetic)
        self.record(self.review())
        view = self.call('status')
        self.assertIn('check-0', view['required_checks'])
        self.assertFalse(view['ready_for_final_check'])

    def test_local_task_attaches_pr_without_resetting_review_rounds(self):
        self.prepare()
        self.record(self.review())
        pr = self.data('pr.json', {'number': 7, 'head_sha': self.base, 'base_sha': self.base, 'url': 'https://example.invalid/pull/7'})
        self.call('prepare', '--repo', self.repo, '--refresh', '--pr-file', pr)
        self.assertEqual(self.call('status')['completed_reviews'], 1)
        self.assertEqual(json.loads(self.state.read_text(encoding='utf-8'))['target']['pr']['number'], 7)

    def test_confirmed_uncommitted_rules_are_frozen_without_resetting_rounds(self):
        self.git('rm', 'CLAUDE.md', 'REVIEW.md')
        self.git('commit', '-m', 'no root rules')
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.prepare()
        self.record(self.review())
        self.write('CLAUDE.md', '# Confirmed work rules\n')
        self.write('REVIEW.md', '@new-policy.md\n')
        self.write('new-policy.md', 'Keep authorization.\n')
        self.call('prepare', '--repo', self.repo, '--refresh')
        confirmed = {'id': 'confirmed-rules', 'type': 'rules', 'candidate_id': self.call('status')['candidate_id'],
                     'actor': 'fixture user', 'source': 'fixture confirmation', 'evidence': 'User confirmed these files.',
                     'files': ['CLAUDE.md', 'REVIEW.md', 'new-policy.md']}
        self.record(confirmed)
        self.assertTrue(self.record(confirmed)['duplicate'])
        self.assertEqual(self.call('status')['completed_reviews'], 1)
        self.assertTrue(self.call('status')['rules_ready'])
        self.write('new-policy.md', 'Skip authorization.\n')
        self.call('prepare', '--repo', self.repo, '--refresh')
        state = json.loads(self.state.read_text(encoding='utf-8'))
        policy = next(item for item in state['candidate']['rules']['files'] if item['path'] == 'new-policy.md')
        self.assertIn('Keep authorization', Path(policy['evidence']).read_text(encoding='utf-8'))
        self.assertEqual(self.call('status')['completed_reviews'], 1)

    def test_confirmed_git_rule_source_can_be_updated_without_new_task(self):
        self.prepare()
        self.record(self.review())
        self.write('CLAUDE.md', '# Confirmed updated work rule\n')
        self.git('add', 'CLAUDE.md')
        self.git('commit', '-m', 'confirmed rule update')
        self.call('prepare', '--repo', self.repo, '--refresh', '--rules-ref', 'HEAD')
        state = json.loads(self.state.read_text(encoding='utf-8'))
        rule = next(item for item in state['candidate']['rules']['files'] if item['path'] == 'CLAUDE.md')
        self.assertIn('updated work rule', Path(rule['evidence']).read_text(encoding='utf-8'))
        self.assertEqual(self.call('status')['completed_reviews'], 1)

    def test_record_ids_do_not_collide_with_object_properties(self):
        self.prepare()
        self.record(self.review('constructor'))
        self.record(self.review('__proto__'))
        self.assertEqual(self.call('status')['completed_reviews'], 2)

    def test_local_human_approval_does_not_approve_a_later_pr(self):
        self.prepare()
        self.call('verify', '--plan', self.plan('assert True'))
        self.record(self.review())
        candidate = self.call('status')['candidate_id']
        self.record({'id': 'local-approval', 'type': 'human', 'candidate_id': candidate,
                     'decision': 'approve', 'actor': 'fixture user', 'source': 'test', 'evidence': 'Local result approved.'})
        self.assertEqual(self.call('status')['human_decision'], 'approve')
        pr = self.data('pr.json', {'number': 7, 'head_sha': self.base, 'base_sha': self.base, 'url': 'https://example.invalid/pull/7'})
        self.call('prepare', '--repo', self.repo, '--refresh', '--pr-file', pr)
        self.assertIsNone(self.call('status')['human_decision'])
        self.assertEqual(self.call('status')['completed_reviews'], 1)

    def test_native_host_usage_import_does_not_add_cumulative_totals(self):
        self.prepare()
        filename = self.root / 'host.jsonl'
        record = {'type': 'token_usage_record', 'payload': {'thread_id': 'fixture-thread', 'turn_id': 'fixture-turn',
                  'response_id': 'fixture-response', 'usage': {'input_tokens': 100, 'output_tokens': 20, 'cached_input_tokens': 50},
                  'turn_token_usage': {'input_tokens': 99999}, 'thread_token_usage': {'input_tokens': 999999}}}
        filename.write_text(json.dumps(record), encoding='utf-8')
        self.call('record', '--usage-format', 'codex-jsonl', '--turn-id', 'fixture-turn', '--usage-file', filename)
        self.call('record', '--usage-format', 'codex-jsonl', '--turn-id', 'fixture-turn', '--usage-file', filename)
        usage = self.call('stats')['model_usage']
        self.assertEqual(usage['input_tokens'], 100)
        self.assertEqual(usage['requests'], 1)

    def test_report_treats_html_source_as_inert_code(self):
        from html.parser import HTMLParser

        self.prepare()
        review = self.review()
        review['key_code'] = [{'location': 'candidate.html:1', 'language': 'html',
                               'code': '<script id="candidate-script">alert(1)</script>\n<img src="https://example.invalid/candidate-image">\n```\n',
                               'explanation': 'Untrusted source must be displayed as code.'}]
        self.record(review)
        output = self.root / 'inert-report.html'
        self.call('report', '--output', output)

        class Tags(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags = []

            def handle_starttag(self, tag, attributes):
                self.tags.append((tag, dict(attributes)))

        parser = Tags()
        parser.feed(output.read_text(encoding='utf-8'))
        self.assertFalse(any(attrs.get('id') == 'candidate-script' for tag, attrs in parser.tags if tag == 'script'))
        self.assertFalse(any('candidate-image' in attrs.get('src', '') for tag, attrs in parser.tags if tag == 'img'))


if __name__ == '__main__':
    unittest.main()

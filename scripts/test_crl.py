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

    def test_finish_uses_generated_input_and_batches_checks_and_report(self):
        prepared = self.prepare('--read-only')
        draft = Path(prepared['review_input'])
        review = json.loads(draft.read_text(encoding='utf-8'))
        self.assertEqual(review['candidate_id'], prepared['candidate_id'])
        self.assertFalse(review['independent'])
        self.call('verify', '--plan', self.plan('assert True'))
        review.update(summary='Checked the behavior and consumer.', independent=True)
        review['key_code'] = [{'path': 'feature.py', 'start_line': 1, 'end_line': 1,
                              'explanation': 'The existing value remains one.'}]
        review['checks'] = [{'name': 'Word UAT', 'source': 'Project requirements', 'evidence': 'Outside offline scope',
                             'observed_at': '2026-11-07T00:00:00Z', 'required': True, 'status': 'not_run'}]
        draft.write_text(json.dumps(review), encoding='utf-8')
        output = self.root / 'report.html'
        result = self.call('finish', '--output', output)
        self.assertEqual(result['review_round'], 1)
        self.assertTrue(result['validation']['body_verified'])
        self.assertFalse(result['ready_for_final_check'])
        self.assertIsNone(result['human_decision'])
        self.assertIn('VALUE = 1', output.read_text(encoding='utf-8'))
        retry = self.call('finish', '--output', output)
        self.assertTrue(retry['duplicate'])
        self.assertEqual(self.call('status')['completed_reviews'], 1)

    def test_finish_report_failure_keeps_review_and_retry_does_not_add_round(self):
        prepared = self.prepare()
        filename = Path(prepared['review_input'])
        data = json.loads(filename.read_text(encoding='utf-8'))
        data.update(summary='Completed review.', independent=True)
        filename.write_text(json.dumps(data), encoding='utf-8')
        blocker = self.root / 'not-a-directory'
        blocker.write_text('retained', encoding='utf-8')
        failure = self.call('finish', '--output', blocker / 'report.html', expected=2)
        self.assertTrue(failure['review_recorded'])
        self.assertEqual(self.call('status')['completed_reviews'], 1)
        result = self.call('finish', '--output', self.root / 'fixed-report.html')
        self.assertTrue(result['duplicate'])
        self.assertEqual(result['review_round'], 1)
        self.assertEqual(blocker.read_text(encoding='utf-8'), 'retained')

    def test_finish_rejects_empty_or_stale_review_without_recording_it(self):
        self.prepare()
        output = self.root / 'report.html'
        self.call('finish', '--output', output, expected=2)
        self.assertEqual(self.call('status')['completed_reviews'], 0)
        filename = Path(json.loads(self.state.read_text(encoding='utf-8'))['review_input'])
        data = json.loads(filename.read_text(encoding='utf-8'))
        data.update(summary='Review of old content.', independent=True)
        filename.write_text(json.dumps(data), encoding='utf-8')
        self.write('feature.py', 'VALUE = 2\n')
        self.call('finish', '--output', output, expected=2)
        self.assertEqual(self.call('status')['completed_reviews'], 0)
        self.assertFalse(output.exists())

    def test_finish_never_overwrites_input_at_the_reserved_report_draft(self):
        prepared = self.prepare()
        original = json.loads(Path(prepared['review_input']).read_text(encoding='utf-8'))
        original.update(summary='Completed review.', independent=True)
        reserved = Path(str(self.state)+'.report.md')
        reserved.write_text(json.dumps(original), encoding='utf-8')
        before = reserved.read_bytes()
        result = self.call('finish', '--file', reserved, '--output', self.root/'report.html', expected=2)
        self.assertIn('reserved report draft', result['error'])
        self.assertEqual(reserved.read_bytes(), before)
        self.assertEqual(self.call('status')['completed_reviews'], 0)

    def test_repair_verification_refreshes_the_default_review_input(self):
        prepared = self.prepare()
        filename = Path(prepared['review_input'])
        first = json.loads(filename.read_text(encoding='utf-8'))
        first.update(summary='First review completed.', independent=True)
        filename.write_text(json.dumps(first), encoding='utf-8')
        self.call('finish', '--output', self.root/'first.html')
        self.write('feature.py', 'VALUE = 2\n')
        self.call('verify', '--plan', self.plan("from pathlib import Path; assert 'VALUE = 2' in Path('feature.py').read_text()"))
        second = json.loads(filename.read_text(encoding='utf-8'))
        self.assertNotEqual(first['candidate_id'], second['candidate_id'])
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(second['summary'], '')
        self.assertFalse(second['independent'])
        second.update(summary='Re-reviewed the repaired candidate.', independent=True)
        filename.write_text(json.dumps(second), encoding='utf-8')
        result = self.call('finish', '--output', self.root/'second.html')
        self.assertEqual(result['review_round'], 2)
        self.assertTrue(result['ready_for_final_check'])
        self.assertTrue(list(Path(str(self.state)+'.evidence/review-inputs').glob('*.json')))

    def test_code_excerpt_membership_uses_literal_paths(self):
        self.write('picka.py', 'SAFE = 1\n')
        self.git('add', 'picka.py')
        self.git('commit', '-m', 'tracked source')
        self.write('.gitignore', 'pick*\n')
        self.write('pick[a].py', 'PRIVATE_FIXTURE = 1\n')
        self.assertNotIn('pick[a].py', self.git('ls-files', '--others', '--exclude-standard'))
        prepared = self.prepare()
        filename = Path(prepared['review_input'])
        data = json.loads(filename.read_text(encoding='utf-8'))
        data.update(summary='Reviewed the actual candidate.', independent=True)
        data['key_code'] = [{'path': 'pick[a].py', 'start_line': 1, 'end_line': 1, 'explanation': 'Not a candidate file.'}]
        filename.write_text(json.dumps(data), encoding='utf-8')
        result = self.call('finish', '--output', self.root/'report.html', expected=2)
        self.assertIn('belong to the candidate', result['error'])
        self.assertEqual(self.call('status')['completed_reviews'], 0)

    def test_verify_collects_fresh_json_and_env_without_wrapper_script(self):
        self.write('.gitignore', 'results.json\n')
        self.prepare()
        code = ("import os,json; from pathlib import Path; "
                "assert os.environ['CRL_FIXTURE']=='explicit'; "
                "Path('results.json').write_text(json.dumps({'run':5,'failures':0,'errors':0,'skipped':[{'reason':'Windows'}]}))")
        spec = {'path': 'results.json', 'fields': {key: '/' + key for key in ('run', 'failures', 'errors', 'skipped')}}
        plan = self.data('plan.json', {'checks': [{'name': 'unit', 'argv': [sys.executable, '-B', '-c', code],
                                                  'env': {'CRL_FIXTURE': 'explicit'}, 'results': [spec]}]})
        result = self.call('verify', '--plan', plan)
        counts = result['checks'][0]['results'][0]['counts']
        self.assertEqual(counts, {'run': 5, 'failures': 0, 'errors': 0, 'skipped': 1, 'passed': 4})
        filename = Path(json.loads(self.state.read_text(encoding='utf-8'))['review_input'])
        review = json.loads(filename.read_text(encoding='utf-8'))
        review.update(summary='Reviewed offline behavior.', independent=True)
        filename.write_text(json.dumps(review), encoding='utf-8')
        output = self.root / 'report.html'
        self.call('finish', '--output', output)
        self.assertIn('Tests run: 5; passed: 4; failures: 0; errors: 0; skipped: 1.', output.read_text(encoding='utf-8'))
        self.write('results.json', 'not the captured evidence')
        snapshot = Path(result['checks'][0]['results'][0]['evidence'])
        self.assertEqual(json.loads(snapshot.read_text(encoding='utf-8'))['run'], 5)

    def test_unchanged_missing_or_failing_json_cannot_pass_required_check(self):
        self.write('.gitignore', 'results.json\n')
        self.prepare()
        self.write('results.json', json.dumps({'run': 3, 'errors': 0}))
        spec = {'path': 'results.json', 'fields': {'run': '/run', 'errors': '/errors'}}
        plan = self.data('plan.json', {'checks': [{'name': 'unit', 'argv': [sys.executable, '-B', '-c', 'pass'], 'results': [spec]}]})
        result = self.call('verify', '--plan', plan, expected=1)
        self.assertIn('not refreshed', result['checks'][0]['results'][0]['error'])
        (self.repo / 'results.json').unlink()
        result = self.call('verify', expected=1)
        self.assertIn('not produced', result['checks'][0]['results'][0]['error'])
        code = "from pathlib import Path; Path('results.json').write_text('{\"run\":3,\"errors\":1}')"
        plan = self.data('plan-failure.json', {'checks': [{'name': 'unit', 'argv': [sys.executable, '-B', '-c', code], 'results': [spec]}]})
        result = self.call('verify', '--plan', plan, expected=1)
        self.assertEqual(result['checks'][0]['exit_code'], 0)
        self.assertEqual(result['checks'][0]['status'], 'failed')

    def test_invalid_result_file_preserves_preceding_executed_checks(self):
        (self.repo/'folder').mkdir()
        self.prepare()
        plan = self.data('plan.json', {'checks': [
            {'name': 'first', 'argv': [sys.executable, '-B', '-c', 'print("executed")']},
            {'name': 'invalid-result', 'argv': [sys.executable, '-B', '-c', 'pass'],
             'results': [{'path': 'folder', 'fields': {'run': '/run'}}]},
        ]})
        result = self.call('verify', '--plan', plan, expected=1)
        self.assertEqual([c['status'] for c in result['checks']], ['passed', 'failed'])
        self.assertIn('regular file', result['checks'][1]['results'][0]['error'])
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(len(state['checks']), 2)
        self.assertIn('executed', Path(state['checks'][0]['stdout']).read_text(encoding='utf-8'))

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


    def test_direct_verification_preserves_argv_environment_counts_and_reuse(self):
        self.write('.gitignore', 'result.json\n')
        self.prepare()
        code = ("import json,os,sys; from pathlib import Path; "
                "assert os.environ['CRL_LITERAL']=='a=b with spaces'; "
                "assert sys.argv[1:]==['--plan','literal | argument']; "
                "Path('result.json').write_text(json.dumps({'run':3,'failures':0,'errors':0,'skipped':[]}))")
        first = self.call('verify', '--env', 'CRL_LITERAL=a=b with spaces', '--timeout-ms', '30000',
                          '--result', 'result.json', '--', sys.executable, '-B', '-c', code, '--plan', 'literal | argument')
        self.assertEqual(first['checks'][0]['results'][0]['counts']['passed'], 3)
        self.assertEqual(self.call('verify')['checks'][0]['status'], 'passed')
        self.assertFalse((self.root/'plan.json').exists())

    def test_direct_verification_rejects_mixed_or_incomplete_inputs_without_execution(self):
        self.prepare()
        marker = self.root/'unexpected.txt'
        code = f"from pathlib import Path; Path({str(marker)!r}).write_text('executed')"
        plan = self.plan(code)
        for args in [('--plan', plan, '--', sys.executable, '-c', code),
                     ('--env', 'BAD', '--', sys.executable, '-c', code),
                     ('--env', 'SAME=1', '--env', 'SAME=2', '--', sys.executable, '-c', code),
                     ('--timeout-ms', 'Infinity', '--', sys.executable, '-c', code),
                     ('--result', 'result.json'), ('--',)]:
            with self.subTest(args=args):
                self.call('verify', *args, expected=2)
                self.assertFalse(marker.exists())

    def test_direct_result_failures_are_not_hidden_by_successful_exit(self):
        self.write('.gitignore', 'result.json\n')
        self.prepare()
        code = "from pathlib import Path; Path('result.json').write_text('{\"run\":2,\"failures\":1,\"errors\":0,\"skipped\":[]}')"
        result = self.call('verify', '--result', 'result.json', '--', sys.executable, '-B', '-c', code, expected=1)
        self.assertEqual(result['checks'][0]['status'], 'failed')
        self.assertEqual(result['checks'][0]['results'][0]['counts']['failures'], 1)

    def test_atomic_record_render_validate_do_not_repeat_checks_or_reviews(self):
        self.write('.gitignore', 'count.txt\n')
        prepared = self.prepare()
        self.assertIn('finding_fields', prepared['next'])
        code = "from pathlib import Path; p=Path('count.txt'); p.write_text(str(int(p.read_text())+1) if p.exists() else '1')"
        self.call('verify', '--', sys.executable, '-B', '-c', code)
        review = json.loads(Path(prepared['review_input']).read_text(encoding='utf-8'))
        review.update(summary='Independent review with a confirmed access defect.', independent=True,
                      findings=[{'priority':'P1','title':'Check ownership','location':'feature.py:1',
                                 'trigger':'Another user requests this value.','impact':'The value is disclosed.',
                                 'evidence':'Synthetic fixture; the recorded source is feature.py.'}],
                      key_code=[{'path':'feature.py','start_line':1,'end_line':1,'explanation':'The current value.'}])
        self.record(review)
        output = self.root/'atomic.html'
        self.assertFalse(output.exists())
        state = json.loads(self.state.read_text(encoding='utf-8'))
        finding = state['reviews'][0]['data']['findings'][0]
        self.assertEqual((finding['id'],finding['status'],finding['blocking']), ('finding-1','open',True))
        self.assertEqual(state['reviews'][0]['data']['key_code'][0]['code'], 'VALUE = 1')
        rendered = self.call('render', '--output', output)
        self.assertIsNone(rendered['validation'])
        self.assertFalse(rendered['ready_for_final_check'])
        original = output.read_bytes()
        self.call('validate', '--output', output)
        self.call('validate', '--output', output)
        self.assertEqual(output.read_bytes(), original)
        self.assertEqual((self.repo/'count.txt').read_text(), '1')
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(len(state['reviews']), 1)
        self.assertEqual(len(state['checks']), 1)
        self.assertIsNone(state['human'])
        self.assertTrue(self.record(review)['duplicate'])

    def test_validate_rejects_modified_page_and_new_recorded_evidence(self):
        self.prepare()
        self.record(self.review())
        output = self.root/'report.html'
        self.call('render', '--output', output)
        original = output.read_bytes()
        output.write_bytes(original+b'<!-- altered -->')
        self.assertIn('changed since rendering', self.call('validate', '--output', output, expected=2)['error'])
        output.write_bytes(original)
        self.record(self.review('review-2'))
        self.assertIn('evidence changed', self.call('validate', '--output', output, expected=2)['error'])
        self.call('render', '--output', output)
        self.call('validate', '--output', output)
        self.write('feature.py', 'VALUE = 9\n')
        self.assertIn('candidate changed', self.call('validate', '--output', output, expected=2)['error'])

    def test_atomic_record_cannot_default_away_blockers_or_accept_risk(self):
        self.prepare()
        base = {'priority':'P1','title':'Access defect','location':'feature.py:1','trigger':'Cross-user read.',
                'impact':'Disclosure.','evidence':'Source fixture.'}
        for extra in ({'blocking':False}, {'status':'accepted_risk'}):
            with self.subTest(extra=extra):
                review = self.review()
                review['findings'] = [{**base, **extra}]
                self.record(review, expected=2)
        self.assertEqual(self.call('status')['completed_reviews'], 0)

    def test_direct_verification_keeps_missing_result_counts_unknown_or_failed(self):
        self.prepare()
        plain = self.call('verify', '--', sys.executable, '-B', '-c', 'print("no count result")')
        self.assertEqual(plain['checks'][0]['results'], [])
        missing = self.call('verify', '--result', 'absent.json', '--', sys.executable, '-B', '-c', 'pass', expected=1)
        self.assertEqual(missing['checks'][0]['results'][0]['status'], 'unavailable')

    def test_report_sidecar_cannot_overwrite_tracked_source(self):
        self.write('.gitignore', '*.html\n')
        self.write('report.html.crl.json', 'USER_SOURCE_DO_NOT_OVERWRITE\n')
        self.git('add', '.')
        self.git('commit', '-m', 'source file beside an ignored HTML output')
        self.prepare()
        output = self.repo/'report.html'
        for command in ('render', 'report'):
            with self.subTest(command=command):
                self.call(command, '--output', output, expected=2)
                self.assertEqual((self.repo/'report.html.crl.json').read_text(), 'USER_SOURCE_DO_NOT_OVERWRITE\n')
                self.assertFalse(output.exists())
        self.assertEqual(self.git('status', '--porcelain').strip(), '')

    def test_render_requires_validation_before_claiming_final_check_readiness(self):
        self.prepare()
        self.call('verify', '--', sys.executable, '-B', '-c', 'pass')
        self.record(self.review())
        output = self.root/'ready.html'
        rendered = self.call('render', '--output', output)
        self.assertTrue(rendered['technical_checks_ready'])
        self.assertTrue(rendered['validation_required'])
        self.assertFalse(rendered['ready_for_final_check'])
        self.assertTrue(self.call('validate', '--output', output)['ready_for_final_check'])

    def test_report_manifest_cannot_collide_with_task_state(self):
        self.state = self.root/'collision.html.crl.json'
        prepared = self.prepare()
        output = self.root/'collision.html'
        for command in ('render', 'report'):
            with self.subTest(command=command):
                result = self.call(command, '--output', output, expected=2)
                self.assertIn('cannot overwrite state', result['error'])
                state = json.loads(self.state.read_text(encoding='utf-8'))
                self.assertEqual(state['task_id'], prepared['task_id'])
                self.assertEqual(state['schema_version'], 1)
                self.assertFalse(output.exists())

    def test_range_alias_and_canonical_input_are_the_same_review(self):
        prepared = self.prepare()
        guide = prepared['next']['key_code']
        self.assertEqual(guide['example']['range'], [1, 10])
        self.assertEqual(guide['max_lines'], 200)
        review = self.review()
        review['key_code'] = [{'path':'feature.py','range':[1,1],'explanation':'The current value.'}]
        self.record(review)
        item = review['key_code'][0]
        item['start_line'],item['end_line'] = item.pop('range')
        self.assertTrue(self.record(review)['duplicate'])
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(len(state['reviews']), 1)
        self.assertEqual(state['reviews'][0]['data']['key_code'][0]['code'], 'VALUE = 1')

    def test_range_alias_cannot_hide_conflicts_or_invalid_bounds(self):
        self.prepare()
        for fields in [{'range':[1]}, {'range':[1,'1']}, {'range':[0,1]}, {'range':[1,201]},
                       {'range':'1-1; echo x'}, {'range':'1-2-3'},
                       {'range':[1,1],'start_line':2}, {'start':1,'end':1}]:
            with self.subTest(fields=fields):
                review = self.review()
                review['key_code'] = [{'path':'feature.py','explanation':'The value.',**fields}]
                result = self.record(review, expected=2)
                if fields == {'start':1,'end':1}:
                    self.assertIn('see prepare.next.key_code', result['error'])
        self.assertEqual(self.call('status')['completed_reviews'], 0)

    def test_observed_range_string_and_array_are_the_same_review(self):
        self.prepare()
        review = self.review()
        review['key_code'] = [{'path':'feature.py','range':'1-1','explanation':'The value.'}]
        self.record(review)
        review['key_code'][0]['range'] = [1,1]
        self.assertTrue(self.record(review)['duplicate'])
        self.assertEqual(self.call('status')['completed_reviews'], 1)


if __name__ == '__main__':
    unittest.main()

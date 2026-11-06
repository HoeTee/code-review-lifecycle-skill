#!/usr/bin/env node
// Deterministic review tools. This module contains no model client or model calls.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { parseArgs } from 'node:util';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { readHostUsage } from './crl_usage.mjs';
import { resultSpecs, fileIdentity, readResult, checkReport } from './crl_artifacts.mjs';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const HELP = `Code Review Lifecycle tools (Node.js 20+; no model calls)
Usage: node scripts/crl.mjs <command> --state /absolute/task.json [options]
  prepare  --repo PATH [--base REF] [--rules-ref REF] [--pr-file JSON]
           [--read-only] [--refresh]
  verify   [--result JSON] -- EXE ARGS  run one explicit check; no plan file needed
           --plan JSON                 advanced multi-check plan
  render   --output HTML               render saved evidence only
  validate --output HTML               check an existing report only
  finish   [--file REVIEW] --output HTML (existing callers)
                                       record review, check state, render and check report
  record   --file JSON                 record review, imported check, or human decision
           --usage-file JSON           import normalized host-reported token usage
           --usage-format codex-jsonl --turn-id ID --usage-file JSONL
                                       read existing per-response host metadata only
  status   [--details]                 current version, rounds, findings, checks
  stats                               recorded host usage and CLI output estimates
  report   --output PATH               render recorded content with the bundled CLI
Options: --pretty, --json (JSON is the default), --help
Put state and output outside the work tree or in a Git-ignored directory.
Review/usage formats and limits: references/cli.md
`;
const COMMAND_HELP = {
  prepare: `prepare --repo PATH --base REF [--read-only] [--refresh]
Returns pinned diff/rule paths and review_input, an editable JSON template.
Read the full applicable rules and diff. Fill semantic conclusions in the template.
`,
  verify: `verify [--check-name NAME] [--env KEY=VALUE] [--timeout-ms N] [--result JSON] -- EXE ARGS
Runs explicit argv without a shell. Repeated --env/--result are allowed.
--result uses root run/failures/errors/skipped fields; unknown schemas need --plan.
Later verify calls reuse the saved command. --plan JSON supports multiple/custom checks.
{"checks":[{"name":"unit","argv":["python","-m","unittest"],"env":{"PYTHONDONTWRITEBYTECODE":"1"},"results":[{"path":"results.json","fields":{"run":"/run","failures":"/failures","errors":"/errors","skipped":"/skipped"}}]}]}
env and results are optional. Result paths are relative to check cwd; fields are explicit JSON pointers.
Missing, unchanged, invalid or failing required results fail the check; unknown counts stay unknown.
`,
  finish: `finish [--file REVIEW] --output HTML
Uses prepare's review_input by default. Fill summary, independent, findings and optional key_code/checks.
Facts (versions, commands, test counts, totals, links) come from state; do not repeat them in summary.
Finding: id, priority P0/P1/P2, title, location, trigger, impact, evidence, status, blocking.
key_code: {path,start_line,end_line,explanation}, or {location,code,explanation,language}.
Optional checks: name, source, evidence, observed_at, required, status (imported observations).
One call records the round/checks, checks the candidate, renders and validates HTML, and returns a short status.
Render failures keep the completed review. Retry the same input without prepare; it does not add a round.
No human approval is recorded. Findings and failed checks remain visible.
`,
  record: `record --file REVIEW_INPUT (or an explicit check/human/rules record)
Review: retain prepare's id/candidate_id; fill summary, independent and findings.
Finding: priority, title, location, trigger, impact, evidence. ID/open/blocking defaults are automatic.
key_code: path, range:[start,end], explanation; "start-end" and start_line/end_line are also accepted (1..200 lines).
Records only: no checks are executed and no report is rendered.
`,
  render: `render --output HTML
Build HTML and its .crl.json validation manifest from saved evidence only.
Does not add reviews or rerun checks. Run validate before delivery.
`,
  validate: `validate --output HTML
Check the existing page, manifest, candidate, recorded evidence and local links.
Does not render, rerun checks, record reviews or grant approval.
`,
};
const optionTypes = {
  state: 'string', repo: 'string', base: 'string', 'rules-ref': 'string',
  'pr-file': 'string', plan: 'string', file: 'string', 'usage-file': 'string',
  env: 'string', result: 'string', 'check-name': 'string', 'timeout-ms': 'string',
  output: 'string', 'usage-format': 'string', 'turn-id': 'string', refresh: 'boolean', 'read-only': 'boolean',
  details: 'boolean', pretty: 'boolean', json: 'boolean', help: 'boolean',
};
const started = performance.now();
let values, command, checkArgv = [];
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const digest = value => crypto.createHash('sha256').update(value).digest('hex');
const stableJSON = value => JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item);
const own = (object, key) => object != null && Object.hasOwn(object, key) ? object[key] : undefined;
const setOwn = (object, key, value) => Object.defineProperty(object, key, { value, enumerable: true, configurable: true, writable: true });
const now = () => new Date().toISOString();
const text = (value, name) => { assert(typeof value === 'string' && value.trim(), `${name} must be nonempty text`); return value; };
const readJSON = filename => JSON.parse(fs.readFileSync(filename, 'utf8').replace(/^\uFEFF/, ''));
const isWithin = (root, filename) => { const rel = path.relative(root, filename); return rel === '' || (!rel.startsWith(`..${path.sep}`) && rel !== '..' && !path.isAbsolute(rel)); };
const pathKey = filename => process.platform === 'win32' ? path.resolve(filename).toLowerCase() : path.resolve(filename);

function git(repo, args, optional = false) {
  const result = spawnSync('git', ['-C', repo, ...args], { maxBuffer: 128 * 1024 * 1024 });
  if (result.error) throw result.error;
  if (result.status !== 0 && !optional) throw new Error(`git ${args[0]} failed: ${result.stderr.toString('utf8').trim()}`);
  return result.status === 0 ? result.stdout : null;
}
const gitText = (repo, args, optional = false) => git(repo, args, optional)?.toString('utf8').trim() ?? null;
const resolveRef = (repo, ref) => {
  assert(typeof ref === 'string' && !ref.startsWith('-'), 'Invalid Git revision');
  return gitText(repo, ['rev-parse', '--verify', '--end-of-options', `${ref}^{commit}`]);
};
function safeArtifact(repo, filename) {
  const absolute = path.resolve(filename);
  // Resolve existing ancestors, so a symlinked artifact directory cannot hide a source overwrite.
  let ancestor = absolute;
  while (!fs.existsSync(ancestor)) ancestor = path.dirname(ancestor);
  const real = path.resolve(fs.realpathSync(ancestor), path.relative(ancestor, absolute));
  if (isWithin(repo, real)) {
    const relative = path.relative(repo, real).split(path.sep).join('/');
    assert(relative && git(repo, ['check-ignore', '-q', '--', relative], true) !== null,
      'Artifacts must be outside the work tree or in a Git-ignored directory');
  }
  return absolute;
}
function atomicWrite(filename, data) {
  fs.mkdirSync(path.dirname(filename), { recursive: true });
  const temporary = `${filename}.${crypto.randomUUID()}.tmp`;
  try { fs.writeFileSync(temporary, data, { mode: 0o600 }); fs.renameSync(temporary, filename); }
  finally { if (fs.existsSync(temporary)) fs.unlinkSync(temporary); }
}
function hashFile(filename) {
  const hash = crypto.createHash('sha256');
  const fd = fs.openSync(filename, 'r');
  try {
    const buffer = Buffer.alloc(1024 * 1024);
    let size;
    while ((size = fs.readSync(fd, buffer, 0, buffer.length, null)) > 0) hash.update(buffer.subarray(0, size));
  } finally { fs.closeSync(fd); }
  return hash.digest('hex');
}
function snapshot(repo, base, rulesIdentity = base) {
  const head = resolveRef(repo, 'HEAD');
  const branch = gitText(repo, ['symbolic-ref', '--quiet', '--short', 'HEAD'], true);
  const mergeBase = gitText(repo, ['merge-base', base, head]);
  const diffArgs = ['--binary', '--no-ext-diff', '--no-textconv', '--no-renames'];
  const patch = git(repo, ['diff', ...diffArgs, mergeBase, '--']);
  const index = git(repo, ['diff', '--cached', ...diffArgs, head, '--']);
  const dirty = git(repo, ['diff', ...diffArgs, head, '--']);
  const files = git(repo, ['diff', '--name-only', '--no-renames', '-z', mergeBase, '--']).toString('utf8').split('\0').filter(Boolean);
  const untracked = git(repo, ['ls-files', '--others', '--exclude-standard', '-z']).toString('utf8').split('\0').filter(Boolean).sort().map(name => {
    const absolute = path.join(repo, name), stat = fs.lstatSync(absolute);
    const kind = stat.isSymbolicLink() ? 'symlink' : stat.isFile() ? 'file' : 'other';
    assert(kind !== 'other', `Unsupported untracked entry: ${name}`);
    const hash = kind === 'symlink' ? digest(fs.readlinkSync(absolute)) : hashFile(absolute);
    return { path: name, kind, sha256: hash, bytes: stat.size };
  });
  const identity = { head, branch, base, rules: rulesIdentity, merge_base: mergeBase, patch: digest(patch), index: digest(index), untracked };
  return { id: digest(JSON.stringify(identity)), head, branch, merge_base: mergeBase, patch, untracked,
    files: [...new Set([...files, ...untracked.map(item => item.path)])].sort(), dirty: dirty.length > 0 || index.length > 0 || untracked.length > 0 };
}
function collectRules(repo, sha, files, directory, approved = {}) {
  const pending = new Set(['CLAUDE.md', 'REVIEW.md']), records = [], gaps = [];
  const trustedPaths = new Set(git(repo, ['ls-tree', '-r', '--name-only', '-z', sha]).toString('utf8').split('\0'));
  for (const filename of files) {
    let dir = path.posix.dirname(filename);
    while (dir !== '.') {
      for (const name of ['CLAUDE.md', 'REVIEW.md']) {
        const rule = `${dir}/${name}`;
        if (own(approved, rule) || trustedPaths.has(rule)) pending.add(rule);
      }
      dir = path.posix.dirname(dir);
    }
  }
  const visited = new Set();
  for (const filename of pending) {
    if (visited.has(filename)) continue;
    visited.add(filename);
    assert(visited.size <= 200, 'Rule include limit exceeded; inspect includes manually');
    const confirmation = own(approved, filename);
    const bytes = confirmation ? fs.readFileSync(confirmation.evidence) : git(repo, ['show', `${sha}:${filename}`], true);
    if (confirmation) assert(digest(bytes) === confirmation.sha256, `Confirmed rule evidence changed: ${filename}`);
    if (bytes === null) { gaps.push(`Missing trusted rule or include: ${filename}`); continue; }
    const destination = path.join(directory, 'rules', ...filename.split('/'));
    atomicWrite(destination, bytes);
    records.push({ path: filename, commit: confirmation ? null : sha, source: confirmation ? 'user-confirmed snapshot' : 'trusted Git commit', evidence: destination, sha256: digest(bytes) });
    // Preserve full source for the agent. Only standalone @path / @"path with spaces" includes are collected.
    const contents = bytes.toString('utf8');
    for (const match of contents.matchAll(/(?:^|\s)@(?:"([^"\r\n]+)"|'([^'\r\n]+)'|([^\s`<>"']+))/gm)) {
      const raw = (match[1] ?? match[2] ?? match[3]).replace(/[),;]+$/, '').replace(/\\/g, '/');
      const included = path.posix.normalize(path.posix.join(path.posix.dirname(filename), raw));
      if (path.posix.isAbsolute(raw) || /^[A-Za-z]:|^~/.test(raw) || included === '..' || included.startsWith('../')) {
        gaps.push(`Include outside trusted Git tree requires explicit handling: ${raw}`); continue;
      }
      pending.add(included);
    }
  }
  return { files: records, gaps, note: 'Read the complete applicable rules. Nonstandard includes and rule conflicts still require agent inspection.' };
}
function saveCandidate(state, captured, statePath) {
  const folder = `${statePath}.evidence/${captured.id}`;
  const diff = path.join(folder, 'tracked.diff');
  atomicWrite(diff, captured.patch);
  const newFiles = [];
  for (const item of captured.untracked) {
    const source = path.join(state.target.repo, item.path);
    if (item.kind === 'file' && item.bytes <= 1024 * 1024) {
      const destination = path.join(folder, 'untracked', ...item.path.split('/'));
      atomicWrite(destination, fs.readFileSync(source));
      newFiles.push({ ...item, evidence: destination });
    } else newFiles.push({ ...item, evidence: null, note: item.kind === 'symlink' ? 'Target text only; not followed' : 'Large file not embedded; inspect explicitly' });
  }
  const rules = collectRules(state.target.repo, state.target.rules_sha, captured.files, folder, state.approved_rules);
  const after = current(state);
  assert(after.id === captured.id, 'Candidate changed during capture; retry prepare');
  state.candidate = { id: captured.id, head_sha: captured.head, branch: captured.branch, captured_at: now(),
    diff, files: captured.files, untracked: newFiles, rules };
}
function validateState(state) {
  assert(state.schema_version === 1 && state.target && state.candidate, 'Unsupported or invalid task state');
  for (const key of ['reviews', 'checks', 'usage', 'commands']) assert(Array.isArray(state[key]), `Invalid state.${key}`);
  text(state.target.repo, 'target.repo');
}
function current(state) {
  const overrides = Object.entries(state.approved_rules ?? {}).map(([name, rule]) => [name, rule.sha256]).sort(([a], [b]) => a.localeCompare(b));
  const identity = state.target.rules_sha + (overrides.length ? `:${digest(stableJSON(overrides))}` : '');
  return snapshot(state.target.repo, state.target.base_sha, identity);
}
function readPR(filename) {
  const pr = readJSON(filename);
  assert(Number.isSafeInteger(pr.number) && pr.number > 0, 'PR number must be a positive integer');
  for (const key of ['head_sha', 'base_sha', 'url']) text(pr[key], `pr.${key}`);
  return pr;
}
function sameTaskTree(state, captured) {
  assert(captured.branch === state.target.branch, 'Task branch changed; prepare an isolated candidate for the reviewed version');
  assert(git(state.target.repo, ['merge-base', '--is-ancestor', state.target.initial_head, captured.head], true) !== null,
    'Current HEAD is not based on the original reviewed version');
}
function reviewInput(state, statePath) {
  const filename = `${statePath}.review.json`;
  const prior = fs.existsSync(filename) ? readJSON(filename) : null;
  if (!prior || prior.candidate_id !== state.candidate.id || own(state.record_index, prior.id)) {
    if (prior) atomicWrite(path.join(`${statePath}.evidence`, 'review-inputs', `${digest(stableJSON(prior))}.json`), `${JSON.stringify(prior, null, 2)}\n`);
    atomicWrite(filename, `${JSON.stringify({ type: 'review', id: `review-${crypto.randomUUID()}`,
      candidate_id: state.candidate.id, independent: false, summary: '', findings: [], key_code: [], checks: [] }, null, 2)}\n`);
  }
  return filename;
}
function prepare(state, statePath) {
  const repo = fs.realpathSync(gitText(path.resolve(values.repo ?? '.'), ['rev-parse', '--show-toplevel']));
  safeArtifact(repo, statePath);
  if (state) {
    assert(values.refresh, 'Task exists; use --refresh to preserve review history and counters');
    assert(repo === state.target.repo, 'Task belongs to another repository');
    assert(!values['read-only'] || state.read_only, 'Refresh cannot change the task permission mode');
    const before = current(state); sameTaskTree(state, before);
    if (values['pr-file']) {
      const pr = readPR(values['pr-file']);
      assert(!state.target.pr || state.target.pr.number === pr.number && state.target.pr.url === pr.url, 'Refresh cannot change to a different PR');
      assert(before.head === resolveRef(repo, pr.head_sha) && !before.dirty, 'PR metadata requires a clean candidate at the observed PR head');
      state.target.pr = pr;
      state.target.base_sha = resolveRef(repo, values.base ?? pr.base_sha);
      assert(state.target.base_sha === resolveRef(repo, pr.base_sha), 'Explicit base differs from observed PR base');
      state.target.base_confirmed = true;
      const ruleSha = resolveRef(repo, values['rules-ref'] ?? state.target.base_sha);
      if (ruleSha !== state.target.rules_sha || values['rules-ref']) state.approved_rules = {};
      state.target.rules_sha = ruleSha;
    } else if (values.base) {
      state.target.base_sha = resolveRef(repo, values.base);
      state.target.base_confirmed = true;
      state.target.rules_sha = resolveRef(repo, values['rules-ref'] ?? state.target.base_sha);
      state.approved_rules = {};
    } else if (values['rules-ref']) {
      state.target.rules_sha = resolveRef(repo, values['rules-ref']);
      state.approved_rules = {};
    }
    const captured = current(state);
    saveCandidate(state, captured, statePath);
  } else {
    assert(!values.refresh, 'No existing task to refresh');
    const pr = values['pr-file'] ? readPR(values['pr-file']) : null;
    const defaultRef = gitText(repo, ['symbolic-ref', '--quiet', 'refs/remotes/origin/HEAD'], true);
    const ref = values.base ?? pr?.base_sha ?? defaultRef ?? 'HEAD';
    const base = resolveRef(repo, ref), head = resolveRef(repo, 'HEAD');
    if (pr) assert(base === resolveRef(repo, pr.base_sha), 'Explicit base differs from observed PR base');
    const rules = resolveRef(repo, values['rules-ref'] ?? base);
    const captured = snapshot(repo, base, rules);
    if (pr) assert(head === resolveRef(repo, pr.head_sha) && !captured.dirty,
      'PR repair requires a clean working tree at the pinned PR head; use an isolated worktree');
    state = { schema_version: 1, task_id: crypto.randomUUID(), created_at: now(), read_only: Boolean(values['read-only']),
      target: { repo, base_sha: base, rules_sha: rules, base_confirmed: Boolean(values.base || pr || defaultRef),
        initial_head: head, branch: captured.branch, pr },
      reviews: [], checks: [], usage: [], commands: [], human: null, plan: null, approved_rules: {}, rule_decisions: [], record_index: {} };
    saveCandidate(state, captured, statePath);
  }
  state.review_input = reviewInput(state, statePath);
  return { state, result: { task_id: state.task_id, read_only: state.read_only, candidate_id: state.candidate.id, review_input: state.review_input,
    head_sha: state.candidate.head_sha, base_sha: state.target.base_sha, rules_sha: state.target.rules_sha,
    base_confirmed: state.target.base_confirmed, files: state.candidate.files,
    diff: state.candidate.diff, untracked: state.candidate.untracked,
    rules: state.candidate.rules, remaining_reviews: 3 - state.reviews.length,
    next: { verify: 'verify [--env KEY=VALUE] [--timeout-ms N] [--result JSON] -- EXE ARGS',
      result_fields: 'Root run/failures/errors/skipped; custom schemas use --plan.',
      review_fields: ['summary', 'independent', 'findings'],
      finding_fields: ['priority', 'title', 'location', 'trigger', 'impact', 'evidence'],
      finding_defaults: { id: 'finding-1, finding-2, ...', status: 'open', blocking: 'true for P0/P1; false for P2 unless specified' },
      key_code: { example: { path: 'relative/source.ext', range: [1, 10], explanation: 'Explain this code.' },
        range_string: '1-10', alternative_fields: ['path', 'start_line', 'end_line', 'explanation'], max_lines: 200 },
      delivery: ['record --file REVIEW_INPUT', 'render --output HTML', 'validate --output HTML'],
      note: 'Reuse the current node/CLI/--state prefix. Batch known sequential actions in one host call; do not reread CLI docs or state for normal use.' } } };
}
function integer(value, name) { assert(Number.isSafeInteger(value) && value >= 0, `${name} must be a nonnegative safe integer`); return value; }
function usageRecord(state, filename) {
  const data = readHostUsage(filename, { format: values['usage-format'] ?? 'normalized', turnId: values['turn-id'] });
  const records = Array.isArray(data) ? data : [data];
  assert(records.length > 0, 'No usage records supplied');
  let added = 0;
  for (const record of records) {
    for (const key of ['id', 'source', 'provider', 'model']) text(record[key], `usage.${key}`);
    assert(record.kind === 'actual', 'Usage imports must be actual host-reported counts; estimates are separate');
    integer(record.input_tokens, 'input_tokens'); integer(record.output_tokens, 'output_tokens');
    for (const key of ['cached_input_tokens', 'cache_write_input_tokens', 'reasoning_output_tokens']) if (record[key] != null) integer(record[key], key);
    if (record.cached_input_tokens != null) assert(record.cached_input_tokens <= record.input_tokens, 'Cached input exceeds total input');
    if (record.cache_write_input_tokens != null) assert(record.cache_write_input_tokens <= record.input_tokens, 'Cache-write input exceeds total input');
    if (record.cached_input_tokens != null && record.cache_write_input_tokens != null) assert(record.cached_input_tokens + record.cache_write_input_tokens <= record.input_tokens, 'Cache input subsets exceed total input');
    if (record.reasoning_output_tokens != null) assert(record.reasoning_output_tokens <= record.output_tokens, 'Reasoning tokens exceed total output');
    const previous = state.usage.find(item => item.id === record.id);
    if (previous) { assert(stableJSON(previous) === stableJSON(record), 'Usage ID reused with different content'); continue; }
    state.usage.push(record); added++;
  }
  for (const key of ['input_tokens', 'output_tokens']) integer(state.usage.reduce((total, item) => total + item[key], 0), `total ${key}`);
  return { usage_records_added: added, note: 'Counts cover imported requests only. The CLI did not call a model.' };
}
function recordResult(state, statePath, supplied = null, candidate = null) {
  if (!supplied) {
    assert(Boolean(values.file) !== Boolean(values['usage-file']), 'Supply exactly one of --file or --usage-file');
    if (values['usage-file']) return usageRecord(state, values['usage-file']);
  }
  const source = supplied ?? readJSON(values.file);
  const data = source.type === 'review' ? materializeReview(state, source) : source;
  text(data.id, 'id');
  const recordHash = digest(stableJSON(data)), prior = own(state.record_index, data.id);
  if (prior) {
    assert(prior.hash === recordHash, 'Record ID reused with different content');
    return { duplicate: true, type: prior.type };
  }
  const done = result => {
    setOwn(state.record_index ??= {}, data.id, { type: data.type, hash: recordHash });
    return result;
  };
  const captured = candidate ?? current(state);
  assert(captured.id === state.candidate.id && data.candidate_id === captured.id, 'Result must match the current prepared candidate; refresh or verify first');
  if (data.type === 'review') {
    const previous = state.reviews.find(item => item.id === data.id);
    if (previous) { assert(stableJSON(previous.data) === stableJSON(data), 'Review ID reused with different content'); return { review_round: previous.round, duplicate: true }; }
    assert(state.reviews.length < 3, 'Three completed reviews already recorded; stop automatic repair and present a concrete replan');
    text(data.summary, 'review.summary');
    assert(typeof data.independent === 'boolean' && Array.isArray(data.findings), 'Review needs independent:boolean and findings:array');
    const ids = new Set();
    for (const finding of data.findings) {
      for (const key of ['id', 'title', 'location', 'trigger', 'impact', 'evidence']) text(finding[key], `finding.${key}`);
      assert(!ids.has(finding.id), 'Duplicate finding ID'); ids.add(finding.id);
      assert(['P0', 'P1', 'P2'].includes(finding.priority), 'Finding priority must be P0/P1/P2');
      assert(['open', 'resolved', 'not_applicable', 'accepted_risk'].includes(finding.status), 'Invalid finding status');
      assert(typeof finding.blocking === 'boolean', 'finding.blocking must be boolean');
      if (finding.status === 'open' && ['P0', 'P1'].includes(finding.priority)) assert(finding.blocking, 'Open P0/P1 findings must block');
      if (finding.status === 'accepted_risk') text(finding.decision_evidence, 'accepted-risk decision_evidence');
    }
    assert(data.key_code == null || Array.isArray(data.key_code), 'key_code must be an array');
    for (const item of data.key_code ?? []) {
      for (const key of ['location', 'code', 'explanation']) text(item[key], `key_code.${key}`);
      assert(/^[a-z0-9_-]*$/i.test(item.language ?? ''), 'Invalid code language');
    }
    state.reviews.push({ id: data.id, round: state.reviews.length + 1, recorded_at: now(), data });
    return done({ review_round: state.reviews.length, candidate_id: captured.id });
  }
  if (data.type === 'check') {
    for (const key of ['name', 'source', 'evidence', 'observed_at']) text(data[key], `check.${key}`);
    assert(!Number.isNaN(Date.parse(data.observed_at)) && /(?:Z|[+-]\d{2}:\d{2})$/i.test(data.observed_at), 'Check observation time must include a timezone');
    assert(['passed', 'failed', 'not_run'].includes(data.status) && typeof data.required === 'boolean', 'Invalid imported check');
    const previous = state.checks.find(item => item.record_id === data.id);
    if (previous) { assert(stableJSON(previous.data) === stableJSON(data), 'Check ID reused with different content'); return { duplicate: true }; }
    state.checks.push({ record_id: data.id, name: data.name, candidate_id: data.candidate_id,
      status: data.status, required: data.required, observed_at: data.observed_at, source: data.source, evidence: data.evidence, data });
    return done({ check_recorded: data.name, provenance: 'imported; not executed by CLI' });
  }
  if (data.type === 'human') {
    assert(['approve', 'request_changes', 'defer'].includes(data.decision), 'Invalid human decision');
    for (const key of ['actor', 'source', 'evidence']) text(data[key], `human.${key}`);
    if (data.decision === 'approve') assert(status(state).ready_for_final_check, 'Complete recorded technical checks before final human approval');
    state.human = { ...data, pr: state.target.pr ? structuredClone(state.target.pr) : null, recorded_at: now() };
    return done({ decision_recorded: data.decision, note: 'Recorded human evidence does not replace required platform approval or merge authorization.' });
  }
  if (data.type === 'rules') {
    for (const key of ['actor', 'source', 'evidence']) text(data[key], `rules.${key}`);
    assert(Array.isArray(data.files) && data.files.length > 0, 'Confirmed rules need an explicit file list');
    const previous = (state.rule_decisions ?? []).find(item => item.id === data.id);
    if (previous) { assert(stableJSON(previous) === stableJSON(data), 'Rule decision ID reused with different content'); return { duplicate: true }; }
    const approved = { ...(state.approved_rules ?? {}) };
    for (const name of data.files) {
      text(name, 'rule path');
      const normalized = path.posix.normalize(name.replace(/\\/g, '/'));
      assert(!path.posix.isAbsolute(normalized) && !/^[A-Za-z]:/.test(normalized) && normalized !== '..' && !normalized.startsWith('../'), 'Rule path must be inside the repository');
      const source = path.join(state.target.repo, normalized);
      assert(fs.lstatSync(source).isFile() && isWithin(state.target.repo, fs.realpathSync(source)), 'Confirmed rule must be a regular repository file');
      const bytes = fs.readFileSync(source);
      const evidence = path.join(`${statePath}.evidence`, 'confirmed-rules', digest(data.id), normalized);
      atomicWrite(evidence, bytes);
      setOwn(approved, normalized, { evidence, sha256: digest(bytes), decision_id: data.id });
    }
    state.approved_rules = approved;
    (state.rule_decisions ??= []).push(data);
    saveCandidate(state, current(state), statePath);
    return done({ rules_recorded: data.files, candidate_id: state.candidate.id, completed_reviews: state.reviews.length,
      note: 'Only record rules actually confirmed by the user. Frozen content is reused; later candidate edits do not change trusted rules.' });
  }
  throw new Error('Record type must be review, check, human, or rules');
}
function validatePlan(plan) {
  assert(Array.isArray(plan.checks) && plan.checks.length > 0, 'Plan needs at least one explicit check');
  const names = new Set();
  for (const check of plan.checks) {
    text(check.name, 'check.name'); assert(!names.has(check.name), 'Duplicate check name'); names.add(check.name);
    assert(Array.isArray(check.argv) && check.argv.length > 0 && check.argv.every(arg => typeof arg === 'string' && !arg.includes('\0')), 'Each argv must be a nonempty array of strings');
    text(check.argv[0], 'executable');
    assert(check.required == null || typeof check.required === 'boolean', 'required must be boolean');
    assert(check.timeout_ms == null || (Number.isSafeInteger(check.timeout_ms) && check.timeout_ms > 0 && check.timeout_ms <= 3600000), 'timeout_ms must be 1..3600000');
    assert(check.env == null || (typeof check.env === 'object' && !Array.isArray(check.env)
      && Object.entries(check.env).every(([key, value]) => key && !/[=\0]/.test(key) && typeof value === 'string' && !value.includes('\0'))), 'check.env must contain explicit string values');
    resultSpecs(check.results);
  }
}
function verificationPlan(state) {
  const directOptions = ['env', 'result', 'check-name', 'timeout-ms'].some(key => values[key] != null);
  assert(!values.plan || (!checkArgv.length && !directOptions), 'Use either --plan or a direct command, not both');
  if (!checkArgv.length) {
    assert(!directOptions, 'Direct-check options require -- EXE ARGS');
    return values.plan ? readJSON(values.plan) : state.plan;
  }
  const env = {}, names = new Set();
  for (const item of values.env ?? []) {
    const split = item.indexOf('='), key = item.slice(0, split), value = item.slice(split + 1);
    assert(split > 0, '--env needs KEY=VALUE');
    const identity = process.platform === 'win32' ? key.toLowerCase() : key;
    assert(!names.has(identity), 'Duplicate --env key'); names.add(identity); setOwn(env, key, value);
  }
  const check = { name: values['check-name'] ?? 'project-check', argv: checkArgv, env };
  if (values['timeout-ms'] != null) {
    assert(/^[1-9]\d*$/.test(values['timeout-ms']), '--timeout-ms must be a positive integer');
    check.timeout_ms = Number(values['timeout-ms']);
  }
  if (values.result) check.results = values.result.map(filename => ({ path: filename,
    fields: Object.fromEntries(['run', 'failures', 'errors', 'skipped'].map(key => [key, `/${key}`])) }));
  return { checks: [check] };
}
function verify(state, statePath) {
  const plan = verificationPlan(state);
  assert(plan, 'Supply -- EXE ARGS or --plan for the first verification'); validatePlan(plan);
  const captured = current(state); sameTaskTree(state, captured);
  if (captured.id !== state.candidate.id && state.reviews.length >= 3 && state.reviews.at(-1).data.findings.some(item => item.status === 'open' && item.blocking)) {
    throw new Error('Review budget exhausted with blockers; stop automatic repair and present a replan');
  }
  if (captured.id !== state.candidate.id) {
    saveCandidate(state, captured, statePath);
    state.review_input = reviewInput(state, statePath);
  }
  if (!state.review_input || !fs.existsSync(state.review_input)) state.review_input = reviewInput(state, statePath);
  state.plan = plan;
  const results = [];
  for (const check of plan.checks) {
    const stamp = now(), id = crypto.randomUUID();
    const cwd = path.resolve(state.target.repo, check.cwd ?? '.');
    assert(isWithin(state.target.repo, fs.realpathSync(cwd)), 'Check cwd must be inside the repository');
    const declared = resultSpecs(check.results).map(spec => {
      const filename = path.resolve(cwd, spec.path);
      try { return { spec, filename, before: fileIdentity(filename) }; }
      catch (error) { return { spec, filename, before: null, probe_error: error.message }; }
    });
    const result = spawnSync(check.argv[0], check.argv.slice(1), { cwd, shell: false,
      env: { ...process.env, ...check.env }, timeout: check.timeout_ms ?? 120000, maxBuffer: 8 * 1024 * 1024, windowsHide: true });
    const folder = `${statePath}.evidence/checks`, stdout = path.join(folder, `${id}.stdout.txt`), stderr = path.join(folder, `${id}.stderr.txt`);
    atomicWrite(stdout, result.stdout ?? Buffer.alloc(0));
    atomicWrite(stderr, Buffer.concat([result.stderr ?? Buffer.alloc(0), Buffer.from(result.error ? `\n${result.error.message}` : '')]));
    const entry = { record_id: id, name: check.name, candidate_id: captured.id, status: !result.error && result.status === 0 ? 'passed' : 'failed',
      required: check.required ?? true, observed_at: stamp, finished_at: now(), source: 'CLI execution',
      exit_code: result.status, signal: result.signal, stdout, stderr, argv: check.argv };
    entry.results = [];
    for (const { spec, filename, before, probe_error } of declared) {
      try {
        assert(!probe_error, `Could not inspect result before execution: ${probe_error}`);
        const summary = readResult(filename, spec, before);
        const evidence = path.join(folder, `${id}.result-${entry.results.length}.json`);
        atomicWrite(evidence, summary.bytes);
        entry.results.push({ source: filename, evidence, sha256: digest(summary.bytes), counts: summary.counts,
          status: summary.status, required: spec.required ?? true });
        if (summary.status === 'failed' && (spec.required ?? true)) entry.status = 'failed';
      } catch (error) {
        entry.results.push({ source: filename, status: 'unavailable', error: error.message, required: spec.required ?? true });
        if (spec.required ?? true) entry.status = 'failed';
      }
    }
    state.checks.push(entry); results.push(entry);
  }
  const stable = current(state).id === captured.id;
  return { candidate_id: captured.id, review_input: state.review_input, candidate_unchanged: stable,
    checks: results.map(({ name, status, exit_code, stdout, stderr, results: summaries }) => ({ name, status, exit_code, stdout, stderr, results: summaries })),
    exit_code: stable && results.every(item => !item.required || item.status === 'passed') ? 0 : 1 };
}
function tokenStats(state) {
  const sum = key => state.usage.reduce((total, item) => total + item[key], 0);
  const optional = key => state.usage.length && state.usage.every(item => item[key] != null) ? sum(key) : null;
  return {
    model_usage: { available: state.usage.length > 0, coverage: 'imported_requests_only', requests: state.usage.length,
      input_tokens: state.usage.length ? sum('input_tokens') : null,
      output_tokens: state.usage.length ? sum('output_tokens') : null,
      cached_input_tokens: optional('cached_input_tokens'), cache_write_input_tokens: optional('cache_write_input_tokens'),
      reasoning_output_tokens: optional('reasoning_output_tokens'),
      sources: [...new Set(state.usage.map(item => item.source))] },
    cli: { completed_calls: state.commands.length, failed_calls: state.commands.filter(item => item.exit_code !== 0).length,
      elapsed_ms: state.commands.reduce((n, item) => n + item.elapsed_ms, 0),
      stdout_bytes: state.commands.reduce((n, item) => n + item.stdout_bytes, 0),
      estimated_stdout_tokens: state.commands.reduce((n, item) => n + item.estimated_stdout_tokens, 0),
      estimate_method: 'ceil(stdout UTF-8 bytes / 4); heuristic, not a model tokenizer or billable usage' },
    savings: null,
    note: 'No model calls. Actual usage is supplied by the host. Estimates cover CLI stdout only; no measured savings baseline.' };
}
function status(state, captured = current(state)) {
  const stale = captured.id !== state.candidate.id;
  const review = state.reviews.at(-1), reviewCurrent = Boolean(review && !stale && review.data.candidate_id === captured.id);
  const findings = review?.data.findings ?? [], counts = { P0: 0, P1: 0, P2: 0 };
  for (const finding of findings) if (finding.status === 'open') counts[finding.priority]++;
  const keyFor = check => `${check.data?.type === 'check' ? 'imported' : 'local'}:${check.name}`;
  const latest = new Map();
  for (const check of state.checks) if (check.candidate_id === captured.id) {
    const key = keyFor(check), previous = latest.get(key);
    const time = Date.parse(check.observed_at), oldTime = previous ? Date.parse(previous.observed_at) : -Infinity;
    const rank = { passed: 0, not_run: 1, failed: 2 };
    if (!previous || time > oldTime || time === oldTime && rank[check.status] > rank[previous.status]) latest.set(key, check);
  }
  const checks = [...latest.values()];
  const required = new Set((state.plan?.checks ?? []).filter(item => item.required !== false).map(item => `local:${item.name}`));
  for (const check of state.checks) if (check.required) required.add(keyFor(check));
  const checksPassed = required.size > 0 && [...required].every(name => latest.get(name)?.status === 'passed');
  const blockers = findings.filter(item => item.status === 'open' && item.blocking).length;
  const rulesReady = state.target.base_confirmed && state.candidate.rules.gaps.length === 0;
  const ready = reviewCurrent && !blockers && checksPassed && rulesReady;
  const humanCurrent = state.human?.candidate_id === captured.id && !stale
    && stableJSON(state.human.pr ?? null) === stableJSON(state.target.pr ?? null);
  return { task_id: state.task_id, phase: ready ? 'human_review' : review ? 'review' : 'prepare',
    read_only: state.read_only, candidate_id: state.candidate.id, current_candidate_id: captured.id,
    head_sha: captured.head, stale_evidence: stale, completed_reviews: state.reviews.length,
    remaining_reviews: Math.max(0, 3 - state.reviews.length), review_current: reviewCurrent,
    review_independent: review?.data.independent ?? null, unresolved: counts, blockers,
    required_checks: [...required].map(key => key.slice(key.indexOf(':') + 1)), checks: checks.map(({ name, status, observed_at, source }) => ({ name, status, observed_at, source })),
    rules_ready: rulesReady, ready_for_final_check: ready,
    human_decision: humanCurrent ? state.human.decision : null,
    stop_automatic_repair: state.reviews.length >= 3 && (!reviewCurrent || blockers > 0),
    assurance: 'Recorded requirements only; semantic completeness, host permissions, independent-review availability, and platform gates remain agent responsibilities.' };
}
const md = value => String(value ?? '').replace(/[&<>]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[char]).replace(/[\\`*_[\]{}|#!]/g, '\\$&').replace(/\r?\n/g, ' ');
const fileLink = (label, filename) => `[${md(label)}](${pathToFileURL(filename).href})`;
const reportIdentity = state => {
  const { commands, updated_at, ...content } = state;
  return digest(stableJSON(content));
};
function validateReport(state, captured = current(state)) {
  const output = safeArtifact(state.target.repo, text(values.output, '--output'));
  const manifest = readJSON(`${output}.crl.json`);
  assert(manifest.candidate_id === captured.id,
    'Report candidate changed; render the current recorded evidence first');
  assert(manifest.state_identity === reportIdentity(state), 'Recorded evidence changed since rendering; render again');
  assert(manifest.output_sha256 === hashFile(output), 'Report changed since rendering');
  const validation = checkReport(output, manifest.expected);
  assert(current(state).id === captured.id, 'Candidate changed during report validation');
  return { output, candidate_id: captured.id, validation, ready_for_final_check: status(state, captured).ready_for_final_check };
}
function report(state, statePath, captured = current(state), validate = true) {
  text(values.output, '--output');
  const output = safeArtifact(state.target.repo, values.output);
  const manifestPath = safeArtifact(state.target.repo, `${output}.crl.json`);
  for (const filename of [output, manifestPath]) assert(pathKey(filename) !== pathKey(statePath)
    && !pathKey(filename).startsWith(`${pathKey(statePath)}.`), 'Report cannot overwrite state or its evidence');
  const view = status(state, captured), stats = tokenStats(state), review = state.reviews.at(-1)?.data;
  const lines = ['---', 'title: Code review lifecycle', 'subtitle: Recorded review evidence and final human check', 'template: doc', 'theme: blueprint', 'mode: light', 'lang: en', '---',
    '## A Review status', `PR: ${md(state.target.pr?.url ?? 'Local candidate')}`, `Commit: ${md(view.head_sha)}`,
    `Base: ${state.target.base_sha}`, `Candidate: ${view.current_candidate_id}`, `Phase: ${view.phase}`,
    `Unresolved P0: ${view.unresolved.P0} · P1: ${view.unresolved.P1} · P2: ${view.unresolved.P2}`,
    `AI reviews: ${view.completed_reviews}/3. Evidence stale: ${view.stale_evidence}. Review matches candidate: ${view.review_current}.`,
    `Independent review reported: ${view.review_independent ?? 'not supplied'}.`,
    `Recorded checks ready for final human check: ${view.ready_for_final_check}. Human decision: ${md(view.human_decision ?? 'pending')}.`,
    '', md(review?.summary ?? 'No completed review recorded.'), '',
    '## B Findings and code', 'Latest recorded review; inspect the version status above before using this evidence.', ''];
  const sorted = [...(review?.findings ?? [])].sort((a, b) => a.priority.localeCompare(b.priority));
  if (!sorted.length) lines.push('No confirmed findings recorded.');
  for (const finding of sorted) lines.push(`### ${finding.priority} ${md(finding.title)}`, `${md(finding.location)} · ${md(finding.status)} · Blocking: ${finding.blocking}`,
    `Trigger: ${md(finding.trigger)}`, `Impact: ${md(finding.impact)}`, `Evidence: ${md(finding.evidence)}`, '');
  for (const code of review?.key_code ?? []) {
    const fence = '`'.repeat(Math.max(3, ...[...code.code.matchAll(/`+/g)].map(match => match[0].length + 1)));
    // am treats html/svg/flow fences as executable/visual components. Repository source is always inert text.
    lines.push(`### ${md(code.location)}`, md(code.explanation), `Source language: ${md(code.language ?? 'not supplied')}.`, `${fence}text`, code.code, fence, '');
  }
  lines.push('## C Checks and source evidence', '| Check | Result | Observed | Source |', '|---|---|---|---|');
  for (const check of state.checks) lines.push(`| ${md(check.name)} | ${md(check.status)}${check.candidate_id === view.current_candidate_id ? '' : ' (older candidate)'} | ${md(check.observed_at)} | ${md(check.source)} |`);
  const expected = [view.head_sha, state.target.base_sha, view.current_candidate_id,
    `Unresolved P0: ${view.unresolved.P0} · P1: ${view.unresolved.P1} · P2: ${view.unresolved.P2}`];
  for (const check of state.checks) for (const item of check.results ?? []) {
    if (item.counts) {
      const count = item.counts;
      const summary = `Tests run: ${count.run ?? 'unknown'}; passed: ${count.passed ?? 'unknown'}; failures: ${count.failures ?? 'unknown'}; errors: ${count.errors ?? 'unknown'}; skipped: ${count.skipped ?? 'unknown'}.`;
      lines.push('', `${md(check.name)}: ${summary}`, fileLink('Result JSON snapshot', item.evidence));
      expected.push(summary);
    } else lines.push('', `${md(check.name)} result unavailable: ${md(item.error)}`);
  }
  lines.push('', fileLink('Prepared full diff', state.candidate.diff));
  for (const rule of state.candidate.rules.files) lines.push(`- ${fileLink(rule.path, rule.evidence)} · ${md(rule.commit ?? rule.source)}`);
  for (const item of state.candidate.untracked) lines.push(`- New file ${md(item.path)}: ${item.evidence ? fileLink('snapshot', item.evidence) : md(item.note)}`);
  for (const gap of state.candidate.rules.gaps) lines.push(`- Missing rule evidence: ${md(gap)}`);
  for (const check of state.checks) if (check.stdout) lines.push(`- ${md(check.name)}: ${fileLink('stdout', check.stdout)} · ${fileLink('stderr', check.stderr)}`);
  lines.push('', '## D Token records', stats.model_usage.available
    ? `Host-reported usage for ${stats.model_usage.requests} imported requests: input ${stats.model_usage.input_tokens}, output ${stats.model_usage.output_tokens}.`
    : 'Actual model token usage: not supplied. This is not a zero-token claim.',
  `Cached input: ${stats.model_usage.cached_input_tokens ?? 'not supplied'}. Cache-write input: ${stats.model_usage.cache_write_input_tokens ?? 'not supplied'}. Reasoning output: ${stats.model_usage.reasoning_output_tokens ?? 'not supplied'}.`,
  `CLI stdout estimate: ${stats.cli.estimated_stdout_tokens} tokens from ${stats.cli.stdout_bytes} UTF-8 bytes. Method: bytes divided by four, rounded up per call.`,
  'The estimate is not provider usage or measured savings. The CLI does not call a model.', '',
  '## E Final human check', 'Check the final behavior, key code, actual evidence, and remaining risks. Request changes or defer when needed.',
  'Only the requirements recorded here were checked by these tools. The agent must still check applicable project and platform requirements.',
  'A recorded chat decision does not replace required platform approval or merge authorization. This page does not merge or approve a PR.');
  const draft = `${statePath}.report.md`;
  atomicWrite(draft, `${lines.join('\n')}\n`);
  const temporary = `${output}.${crypto.randomUUID()}.html`;
  let validation;
  try {
    const result = spawnSync(process.execPath, [path.join(SCRIPT_DIR, 'render_html.mjs'), 'render', draft, '-o', temporary, '--no-open', '--theme', 'blueprint', '--mode', 'light'], { encoding: 'utf8', windowsHide: true, maxBuffer: 8 * 1024 * 1024 });
    assert(!result.error && result.status === 0, `Report renderer failed: ${result.stderr ?? result.error?.message ?? ''}`);
    validation = validate ? checkReport(temporary, expected) : null;
    assert(current(state).id === captured.id, 'Candidate changed during report generation; evidence remains tied to its original candidate');
    atomicWrite(output, fs.readFileSync(temporary));
    atomicWrite(manifestPath, `${JSON.stringify({ candidate_id: captured.id, state_identity: reportIdentity(state),
      output_sha256: hashFile(output), expected })}\n`);
  } finally { if (fs.existsSync(temporary)) fs.unlinkSync(temporary); }
  return { output, draft, candidate_id: view.current_candidate_id, ready_for_final_check: validate && view.ready_for_final_check,
    technical_checks_ready: view.ready_for_final_check, validation_required: !validate, validation, model_usage: stats.model_usage };
}
function materializeReview(state, input) {
  const data = structuredClone(input);
  if (Array.isArray(data.findings)) data.findings = data.findings.map((finding, index) => ({
    id: `finding-${index + 1}`, status: 'open', blocking: ['P0', 'P1'].includes(finding.priority), ...finding,
  }));
  for (const item of data.key_code ?? []) {
    if (item.code != null) continue;
    if (Object.hasOwn(item, 'range')) {
      const range = typeof item.range === 'string' && /^\d+\s*-\s*\d+$/.test(item.range)
        ? item.range.split('-').map(Number) : item.range;
      assert(Array.isArray(range) && range.length === 2, 'key_code.range must be [start,end] or "start-end"');
      for (const [index, key] of ['start_line', 'end_line'].entries()) {
        assert(!Object.hasOwn(item, key) || item[key] === range[index], `Conflicting key_code.${key} and range`);
        item[key] = range[index];
      }
      delete item.range;
    }
    text(item.path, 'key_code.path');
    const filename = path.resolve(state.target.repo, item.path);
    const relative = path.relative(state.target.repo, filename).split(path.sep).join('/');
    assert(isWithin(state.target.repo, filename) && fs.lstatSync(filename).isFile()
      && isWithin(state.target.repo, fs.realpathSync(filename)), 'Code excerpt must be a regular repository file');
    assert(git(state.target.repo, ['--literal-pathspecs', 'ls-files', '--error-unmatch', '--', relative], true) !== null
      || state.candidate.untracked.some(entry => entry.path === relative && entry.kind === 'file'), 'Code excerpt must belong to the candidate');
    assert(Number.isSafeInteger(item.start_line) && Number.isSafeInteger(item.end_line),
      'key_code needs integer start_line/end_line or range:[start,end]; see prepare.next.key_code');
    assert(item.start_line > 0 && item.end_line >= item.start_line && item.end_line-item.start_line < 200,
      'Code range must contain 1..200 lines');
    const source = fs.readFileSync(filename, 'utf8').split(/\r?\n/);
    assert(item.end_line <= source.length, 'Code range exceeds file');
    item.code = source.slice(item.start_line-1, item.end_line).join('\n');
    item.location = `${item.path}:${item.start_line}`;
  }
  return data;
}
function finish(state, statePath) {
  text(values.output, '--output');
  safeArtifact(state.target.repo, values.output);
  const inputPath = values.file ?? state.review_input ?? `${statePath}.review.json`;
  assert(pathKey(values.output) !== pathKey(inputPath), 'Report cannot overwrite its review input');
  assert(pathKey(inputPath) !== pathKey(`${statePath}.report.md`), 'Review input collides with the reserved report draft; use prepare\'s review_input');
  const input = readJSON(inputPath);
  assert(input.type === 'review', 'finish accepts a completed review only');
  const captured = current(state);
  sameTaskTree(state, captured);
  assert(captured.id === state.candidate.id && input.candidate_id === captured.id, 'Review input must match the current prepared candidate');
  assert(input.checks == null || Array.isArray(input.checks), 'review.checks must be an array');
  const data = materializeReview(state, input);
  const observations = data.checks ?? [];
  delete data.checks;
  const recorded = recordResult(state, statePath, data, captured);
  for (const [index, check] of observations.entries()) recordResult(state, statePath,
    { ...check, type: 'check', id: check.id ?? `${input.id}:check:${index}`, candidate_id: input.candidate_id }, captured);
  try {
    const page = report(state, statePath, captured), view = status(state, captured);
    return { candidate_id: captured.id, review_round: recorded.review_round ?? state.reviews.find(item => item.id === input.id)?.round,
      duplicate: recorded.duplicate ?? false, unresolved: view.unresolved, ready_for_final_check: view.ready_for_final_check,
      human_decision: view.human_decision, output: page.output, draft: page.draft, validation: page.validation,
      checks: view.checks, exit_code: 0 };
  } catch (error) {
    // The review really completed. Preserve it, so retrying publication cannot spend another round.
    return { candidate_id: captured.id, review_recorded: true, completed_reviews: state.reviews.length,
      error: error.message, retry: 'Retry finish with the same input after fixing the report issue; do not prepare a new review', exit_code: 2 };
  }
}
function main() {
  const args = process.argv.slice(2), separator = args.indexOf('--');
  const parsed = parseArgs({ args: separator < 0 ? args : args.slice(0, separator),
    options: Object.fromEntries(Object.entries(optionTypes).map(([key, type]) => [key, { type, ...(['env', 'result'].includes(key) ? { multiple: true } : {}) }])), allowPositionals: true });
  values = parsed.values; command = parsed.positionals[0];
  if (values.help || !command || command === 'help') { process.stdout.write(COMMAND_HELP[command] ?? HELP); return; }
  assert(['prepare', 'verify', 'finish', 'record', 'status', 'stats', 'report', 'render', 'validate'].includes(command), 'Unknown command; use --help');
  assert(parsed.positionals.length === 1, 'Unexpected positional arguments');
  if (separator >= 0) { assert(command === 'verify', '-- EXE ARGS is only valid for verify'); checkArgv = args.slice(separator + 1); assert(checkArgv.length, 'Missing executable after --'); }
  assert(command === 'verify' || !['env', 'result', 'check-name', 'timeout-ms'].some(key => values[key] != null), 'Direct-check options are only valid for verify');
  const statePath = path.resolve(text(values.state, '--state'));
  const existing = fs.existsSync(statePath) ? readJSON(statePath) : null;
  if (existing) { validateState(existing); safeArtifact(existing.target.repo, statePath); }
  else assert(command === 'prepare', 'No task state; run prepare first');
  fs.mkdirSync(path.dirname(statePath), { recursive: true });
  const lock = `${statePath}.lock`;
  let fd;
  try { fd = fs.openSync(lock, 'wx', 0o600); fs.writeSync(fd, `${process.pid}\n`); }
  catch (error) { if (error.code === 'EEXIST') throw new Error('Task state is locked; inspect the lock owner before retrying'); throw error; }
  try {
    // Re-read after acquiring the lock, preventing a lost update between readers.
    let state = fs.existsSync(statePath) ? readJSON(statePath) : null;
    if (state) validateState(state);
    const previousState = state ? structuredClone(state) : null;
    let result, exitCode = 0;
    try {
      if (command === 'prepare') ({ state, result } = prepare(state, statePath));
      else if (command === 'verify') { result = verify(state, statePath); exitCode = result.exit_code; }
      else if (command === 'finish') { result = finish(state, statePath); exitCode = result.exit_code; }
      else if (command === 'record') result = recordResult(state, statePath);
      else if (command === 'status') {
        result = status(state);
        if (values.details) result.details = { candidate: state.candidate, reviews: state.reviews, checks: state.checks, human: state.human };
      } else if (command === 'stats') result = tokenStats(state);
      else if (command === 'report') result = report(state, statePath);
      else if (command === 'render') result = report(state, statePath, current(state), false);
      else if (command === 'validate') result = validateReport(state);
    } catch (error) { state = previousState; result = { error: error.message }; exitCode = 2; }
    const output = JSON.stringify(result, null, values.pretty ? 2 : 0) + '\n';
    if (state) {
      const bytes = Buffer.byteLength(output);
      state.commands.push({ command, observed_at: now(), elapsed_ms: Math.round(performance.now() - started), exit_code: exitCode,
        stdout_bytes: bytes, estimated_stdout_tokens: Math.ceil(bytes / 4) });
      state.updated_at = now();
      atomicWrite(statePath, `${JSON.stringify(state, null, 2)}\n`);
    }
    process.stdout.write(output); process.exitCode = exitCode;
  } finally { fs.closeSync(fd); fs.unlinkSync(lock); }
}
try { main(); }
catch (error) { process.stderr.write(`${JSON.stringify({ error: error.message })}\n`); process.exitCode = 2; }

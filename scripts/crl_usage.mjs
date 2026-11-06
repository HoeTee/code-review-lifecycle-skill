// Read existing usage exports only. No provider SDK, tokenizer, or model call.
import fs from 'node:fs';

function* lines(filename) {
  const fd = fs.openSync(filename, 'r'), buffer = Buffer.alloc(64 * 1024);
  let pending = Buffer.alloc(0), dropping = false, count;
  try {
    while ((count = fs.readSync(fd, buffer, 0, buffer.length, null)) > 0) {
      const bytes = Buffer.concat([pending, buffer.subarray(0, count)]);
      let start = 0, end;
      while ((end = bytes.indexOf(10, start)) !== -1) {
        if (!dropping && end - start <= 1024 * 1024) yield bytes.subarray(start, end).toString('utf8');
        dropping = false; start = end + 1;
      }
      pending = bytes.subarray(start);
      if (pending.length > 1024 * 1024) { pending = Buffer.alloc(0); dropping = true; }
    }
    // JSONL permits a complete last record without a newline; an actively appended partial line is ignored.
    if (!dropping && pending.length) {
      const final = pending.toString('utf8');
      if (/"type"\s*:\s*"(?:token_usage_record|turn_context)"/.test(final)) {
        try { JSON.parse(final); yield final; } catch { /* Incomplete metadata is not a completed usage record. */ }
      }
    }
  } finally { fs.closeSync(fd); }
}

export function readHostUsage(filename, { format = 'normalized', turnId } = {}) {
  if (format === 'normalized') return JSON.parse(fs.readFileSync(filename, 'utf8').replace(/^\uFEFF/, ''));
  if (format !== 'codex-jsonl') throw new Error('usage-format must be normalized or codex-jsonl');
  if (typeof turnId !== 'string' || !turnId.trim()) throw new Error('codex-jsonl requires an explicit --turn-id; no whole-session import');
  const requests = new Map();
  let model = 'not_supplied';
  for (const line of lines(filename)) {
    // Skip message bodies, reasoning and tool payloads before parsing JSON.
    if (!/"type"\s*:\s*"(?:token_usage_record|turn_context)"/.test(line)) continue;
    let record;
    try { record = JSON.parse(line); }
    catch { throw new Error('Malformed usage/context metadata line; no usage imported'); }
    const payload = record.payload ?? {};
    if (payload.turn_id !== turnId) continue;
    if (record.type === 'turn_context') {
      if (typeof payload.model === 'string' && payload.model.trim()) model = payload.model;
      continue;
    }
    if (record.type !== 'token_usage_record') continue;
    if (typeof payload.thread_id !== 'string' || !payload.thread_id || typeof payload.response_id !== 'string' || !payload.response_id) {
      throw new Error('Usage metadata needs thread_id and response_id');
    }
    const usage = payload.usage;
    if (!usage || typeof usage !== 'object') throw new Error('Usage record has no per-response usage');
    const id = `codex:${payload.thread_id}:${turnId}:${payload.response_id}`;
    const item = { id, kind: 'actual', source: 'Codex token_usage_record (per response)', provider: 'codex-host',
      model, input_tokens: usage.input_tokens, output_tokens: usage.output_tokens };
    for (const key of ['cached_input_tokens', 'cache_write_input_tokens', 'reasoning_output_tokens']) {
      if (usage[key] != null) item[key] = usage[key];
    }
    const previous = requests.get(id);
    if (previous && JSON.stringify(previous) !== JSON.stringify(item)) throw new Error('Conflicting counts for the same host response; inspect before importing');
    requests.set(id, item);
  }
  if (!requests.size) throw new Error('No per-response token usage found for the requested turn');
  return [...requests.values()];
}

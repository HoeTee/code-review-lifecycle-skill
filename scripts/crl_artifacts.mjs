// Fixed JSON-result and HTML checks. No model calls or project-specific rules.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const assert = (condition, message) => { if (!condition) throw new Error(message); };
const fields = new Set(['run', 'failures', 'errors', 'skipped']);

export function resultSpecs(value = []) {
  assert(Array.isArray(value), 'check.results must be an array');
  for (const spec of value) {
    assert(spec && typeof spec.path === 'string' && spec.path.trim(), 'Result needs a path');
    assert(spec.fields && typeof spec.fields === 'object' && !Array.isArray(spec.fields) && Object.keys(spec.fields).length,
      'Result needs explicit JSON-pointer fields');
    for (const [key, pointer] of Object.entries(spec.fields)) {
      assert(fields.has(key), `Unknown result field: ${key}`);
      assert(typeof pointer === 'string' && (pointer === '' || pointer.startsWith('/')), 'Result fields use JSON pointers');
    }
    assert(spec.required == null || typeof spec.required === 'boolean', 'Result required must be boolean');
  }
  return value;
}

export function fileIdentity(filename) {
  try {
    const stat = fs.statSync(filename, { bigint: true });
    assert(stat.isFile(), 'Result must be a regular file');
    return `${stat.dev}:${stat.ino}:${stat.size}:${stat.mtimeNs}:${stat.ctimeNs}`;
  } catch (error) { if (error.code === 'ENOENT') return null; throw error; }
}

export function readResult(filename, spec, before) {
  const identity = fileIdentity(filename);
  assert(identity != null, 'Declared result file was not produced');
  assert(identity !== before, 'Declared result file was not refreshed by this check');
  const stat = fs.statSync(filename);
  assert(stat.size <= 8 * 1024 * 1024, 'Result JSON exceeds 8 MiB');
  const bytes = fs.readFileSync(filename);
  assert(fileIdentity(filename) === identity, 'Result changed during capture');
  const source = JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/, ''));
  const counts = {};
  for (const [field, pointer] of Object.entries(spec.fields)) {
    let value = source;
    for (const part of pointer === '' ? [] : pointer.slice(1).split('/').map(s => s.replace(/~1/g, '/').replace(/~0/g, '~'))) {
      assert(value != null && typeof value === 'object' && Object.hasOwn(value, part), `Missing result field: ${pointer}`);
      value = value[part];
    }
    if (Array.isArray(value) && field !== 'run') value = value.length;
    assert(Number.isSafeInteger(value) && value >= 0, `Result ${field} must be a nonnegative integer or countable array`);
    counts[field] = value;
  }
  const unsuccessful = (counts.failures ?? 0) + (counts.errors ?? 0) + (counts.skipped ?? 0);
  assert(Number.isSafeInteger(unsuccessful) && (counts.run == null || unsuccessful <= counts.run), 'Result counts contradict total run');
  if (['run', 'failures', 'errors', 'skipped'].every(key => key in counts)) {
    counts.passed = counts.run - unsuccessful;
  }
  const failed = counts.run === 0 || (counts.failures ?? 0) > 0 || (counts.errors ?? 0) > 0;
  return { bytes, counts, status: failed ? 'failed' : 'passed' };
}

const entities = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
const decode = value => value.replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi, (whole, key) => {
  if (!key.startsWith('#')) return entities[key.toLowerCase()];
  const code = key[1].toLowerCase() === 'x' ? parseInt(key.slice(2), 16) : parseInt(key.slice(1), 10);
  return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : whole;
});

export function checkReport(filename, expected) {
  const html = fs.readFileSync(filename, 'utf8');
  assert(/<html\b/i.test(html) && /<body\b/i.test(html), 'Renderer did not produce an HTML document');
  const body = reportBody(html);
  for (const value of expected) assert(body.includes(String(value).replace(/\s+/g, ' ')), `Report body is missing recorded content: ${value}`);
  let localLinks = 0;
  for (const match of html.matchAll(/<a\b[^>]*\bhref\s*=\s*(["'])(.*?)\1/gi)) {
    const href = decode(match[2]);
    if (!href.startsWith('file:')) continue;
    const target = fileURLToPath(new URL(href));
    assert(fs.existsSync(target) && fs.statSync(target).isFile(), `Report evidence is missing: ${path.basename(target)}`);
    localLinks++;
  }
  assert(localLinks > 0, 'Report has no local evidence links');
  return { body_verified: true, local_links_checked: localLinks };
}

// Inspect document text, excluding head, raw source and explicitly hidden subtrees.
// This is a structural check; it does not certify arbitrary CSS or JS visibility.
function reportBody(html) {
  const opening = /<body\b[^>]*>/i.exec(html), closing = html.toLowerCase().lastIndexOf('</body>');
  assert(opening && closing >= opening.index + opening[0].length, 'Report body is incomplete');
  const source = html.slice(opening.index + opening[0].length, closing), lower = source.toLowerCase();
  const stack = [], parts = [], voids = new Set(['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']);
  let cursor = 0;
  const visible = () => !stack.at(-1)?.hidden;
  while (cursor < source.length) {
    const start = source.indexOf('<', cursor);
    if (visible()) parts.push(source.slice(cursor, start < 0 ? source.length : start));
    if (start < 0) break;
    if (source.startsWith('<!--', start)) {
      const end = source.indexOf('-->', start + 4); cursor = end < 0 ? source.length : end + 3; continue;
    }
    let end = start + 1, quote = null;
    for (; end < source.length; end++) {
      const char = source[end];
      if (quote) { if (char === quote) quote = null; }
      else if (char === '"' || char === "'") quote = char;
      else if (char === '>') break;
    }
    if (end >= source.length) break;
    const tag = source.slice(start, end + 1), match = /^<\s*(\/?)\s*([a-z][\w:-]*)/i.exec(tag);
    cursor = end + 1;
    if (!match) continue;
    const name = match[2].toLowerCase();
    if (match[1]) {
      for (let index = stack.length-1; index >= 0; index--) if (stack[index].name === name) { stack.length = index; break; }
      continue;
    }
    if (name === 'script' || name === 'style') {
      const close = lower.indexOf(`</${name}`, cursor), finish = close < 0 ? -1 : source.indexOf('>', close);
      cursor = finish < 0 ? source.length : finish + 1; continue;
    }
    const attributes = tag.slice(match[0].length, -1);
    const attribute = key => {
      const value = new RegExp(`(?:^|\\s)${key}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i').exec(attributes);
      return value ? decode(value[1] ?? value[2] ?? value[3]) : '';
    };
    const hidden = !visible() || ['template','noscript'].includes(name) || /(?:^|\s)hidden(?:\s|=|$)/i.test(attributes)
      || attribute('aria-hidden').toLowerCase() === 'true' || /(?:display\s*:\s*none|visibility\s*:\s*hidden)\b/i.test(attribute('style'));
    if (!voids.has(name) && !/\/\s*>$/.test(tag)) stack.push({ name, hidden });
  }
  return decode(parts.join(' ')).replace(/\s+/g, ' ');
}

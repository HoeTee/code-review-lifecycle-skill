import { copyFile, mkdir, mkdtemp, readFile, readdir, rmdir, unlink, writeFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

const renderer = fileURLToPath(new URL('./vendor/answer-me-with-html/am.mjs', import.meta.url));
const usage = `Code Review Lifecycle · HTML
  render <draft.md|-> -o <page.html> [--footer "整行署名"]
  patch <page.html> --panel <ID|title> [panel.md | --from <panel.md>] [--footer "整行署名"]
  help <format|patch|组件名>
  list

默认保留原版样式、隐藏工具栏，使用本 skill 的项目署名。
--footer 自定义署名；--footer "" 隐藏署名。patch 保留上次的署名设置。
输出仅为 HTML；不自动打开浏览器。支持 --template、--theme、--mode、--style。`;
const pageEnd = /<\/body>\s*<\/html>\s*$/;
const savedOptions = /<script id="crl-page-options" type="application\/json">([^\r\n]*)<\/script>\s*$/;
const escapeHtml = text => text.replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

async function pageOptions(html, footer) {
  if (!html.includes('</head>') || !pageEnd.test(html)) throw new Error('渲染器未生成完整 HTML。');
  const css = await readFile(new URL('../assets/html-page.css', import.meta.url), 'utf8');
  let page = html.replace('</head>', `<style id="crl-page-style">\n${css}\n</style>\n</head>`);
  let options = '';
  if (footer !== undefined) {
    const credit = footer.trim() ? `<p class="am-colophon">${escapeHtml(footer.trim())}</p>` : '';
    page = page.replace(/<p class="am-colophon">[\s\S]*?<\/p>/, () => credit);
    const data = JSON.stringify({ footer }).replace(/</g, '\\u003c');
    options = `<script id="crl-page-options" type="application/json">${data}</script>\n`;
  }
  const notices = new URL('./vendor/answer-me-with-html/licenses/', import.meta.url);
  const files = (await readdir(notices)).sort();
  const licenses = await Promise.all([
    readFile(new URL('./vendor/answer-me-with-html/LICENSE', import.meta.url), 'utf8'),
    ...files.map(file => readFile(new URL(file, notices), 'utf8')),
  ]);
  const notice = licenses.join('\n\n').replace(/-->/g, '-- >');
  return page.replace(pageEnd, () => `${options}</body>\n<!-- answer-me-with-html licenses\n${notice}\n-->\n</html>\n`);
}

function run(args, input) {
  const result = spawnSync(process.execPath, [renderer, ...args], {
    encoding: 'utf8', input, stdio: [input === undefined ? 'inherit' : 'pipe', 'pipe', 'pipe'],
    windowsHide: true, maxBuffer: 8 * 1024 * 1024,
    env: { ...process.env, AM_NO_UPDATE_CHECK: '1', AM_HOME: process.env.AM_HOME || join(tmpdir(), 'code-review-lifecycle-html') },
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error((result.stderr || result.stdout || 'HTML 生成失败。').trim());
  return result;
}

async function main(args) {
  const { values, positionals: [command, input, ...rest] } = parseArgs({
    args, allowPositionals: true,
    options: {
      out: { type: 'string', short: 'o' }, footer: { type: 'string' },
      panel: { type: 'string' }, from: { type: 'string' },
      template: { type: 'string' }, theme: { type: 'string' }, mode: { type: 'string' }, style: { type: 'string' },
      'no-open': { type: 'boolean' }, help: { type: 'boolean', short: 'h' },
    },
  });
  if (values.help || !command || (command === 'help' && !input)) return console.log(usage);
  if (command === 'list' || (command === 'help' && !['video', 'theme'].includes(input))) {
    const result = run([command, ...(input ? [input] : [])]);
    process.stdout.write(result.stdout);
    process.stderr.write(result.stderr);
    return;
  }
  if (!['render', 'patch'].includes(command) || !input) throw new Error(usage);
  if (command === 'patch' && (!values.panel || values.out || rest.length > 1 || (values.from && rest.length))) {
    throw new Error('patch 需要 --panel，可指定一个面板草稿，并在原 HTML 路径更新。');
  }
  if (command === 'render' && rest.length) throw new Error(usage);
  if (command === 'render' && !values.out) throw new Error('render 需要 -o <page.html>。');
  const output = resolve(command === 'patch' ? input : values.out);
  if (!/\.html$/i.test(output)) throw new Error('输出路径必须以 .html 结尾。');
  if (command === 'render' && input !== '-' && resolve(input).toLowerCase() === output.toLowerCase()) throw new Error('输入和输出文件不能相同。');
  const temporary = await mkdtemp(join(tmpdir(), 'crl-html-'));
  const staged = join(temporary, 'page.html');
  try {
    let footer = values.footer;
    let stdin;
    const defaults = {};
    const upstream = command === 'render' ? ['render', input, '-o', staged] : ['patch', staged, '--panel', values.panel];
    if (command === 'patch') {
      const original = await readFile(output, 'utf8');
      const root = original.match(/<html\b[^>]*>/i)?.[0] ?? '';
      if (/\sdata-video\b/i.test(root)) throw new Error('此入口仅更新 HTML 说明页。');
      const saved = original.slice(0, original.lastIndexOf('</body>')).match(savedOptions);
      if (footer === undefined && saved) footer = JSON.parse(saved[1]).footer;
      await copyFile(output, staged);
      const panelDraft = values.from ?? rest[0];
      if (panelDraft) upstream.push('--from', panelDraft);
    } else {
      if (input === '-') stdin = readFileSync(0, 'utf8');
      const lines = (stdin ?? await readFile(input, 'utf8')).split(/\r\n?|\n/);
      const end = lines[0]?.trim() === '---' ? lines.findIndex((line, index) => index > 0 && line.trim() === '---') : 0;
      const meta = lines.slice(1, Math.max(1, end));
      if (!meta.some(line => /^\s*theme\s*:/.test(line))) defaults.theme = 'blueprint';
      if (!meta.some(line => /^\s*mode\s*:/.test(line))) defaults.mode = 'light';
    }
    for (const key of ['template', 'theme', 'mode', 'style']) {
      const value = values[key] ?? defaults[key];
      if (value !== undefined) upstream.push('--' + key, value);
    }
    upstream.push('--no-open');
    const result = run(upstream, stdin);
    const page = await pageOptions(await readFile(staged, 'utf8'), footer);
    await mkdir(dirname(output), { recursive: true });
    await writeFile(output, page, 'utf8');
    process.stdout.write(result.stdout.replaceAll(staged, output));
    process.stderr.write(result.stderr);
  } finally {
    await unlink(staged).catch(error => { if (error.code !== 'ENOENT') throw error; });
    await rmdir(temporary);
  }
}

main(process.argv.slice(2)).catch(error => { console.error(error.message); process.exitCode = 1; });

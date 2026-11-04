import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const template = new URL("../assets/review-page.html", import.meta.url);
const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => entities[char]);
const decodeEntities = (value) => value.replace(/&(amp|lt|gt|quot|#39|#96);/g, (entity) => ({
  "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&#96;": "`",
})[entity]);
const plain = (value) => escapeHtml(decodeEntities(value));
const linesOf = (value) => value.replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n").split("\n");

function safeHref(value) {
  if (/^#[\w-]+$/.test(value)) return value;
  try {
    const url = new URL(decodeEntities(value));
    return ["http:", "https:", "file:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function inline(text) {
  const pattern = /\\([\\`*_[\]|])|`([^`\n]+)`|\[((?:\\[\\[\]|]|[^\]\\\n])+)\]\(([^\s)]+)\)|\*\*([^*\n]+)\*\*|\*([^*\n]+)\*/g;
  let html = "";
  let offset = 0;
  for (const match of text.matchAll(pattern)) {
    const [raw, escaped, code, label, url, strong, emphasis] = match;
    html += plain(text.slice(offset, match.index));
    if (escaped) html += escapeHtml(escaped);
    else if (code) html += `<code>${plain(code)}</code>`;
    else if (label) {
      const href = safeHref(url);
      const labelText = plain(label.replace(/\\([\\[\]|])/g, "$1"));
      html += href ? `<a href="${escapeHtml(href)}">${labelText}</a>` : labelText;
    } else if (strong) html += `<strong>${plain(strong)}</strong>`;
    else html += `<em>${plain(emphasis)}</em>`;
    offset = match.index + raw.length;
  }
  return html + plain(text.slice(offset));
}

function tableCells(line) {
  return line.trim().replace(/^\|/, "").replace(/(?<!\\)\|$/, "").split(/(?<!\\)\|/).map((cell) => cell.trim());
}

function tableCell(text) {
  const status = text.match(/^(ok|no|warn)\s+(.+)$/);
  return status ? `<span class="badge ${status[1]}">${inline(status[2])}</span>` : inline(text);
}

function table(lines) {
  const header = tableCells(lines[0]).map((cell) => `<th scope="col">${inline(cell)}</th>`).join("");
  const rows = lines.slice(2).map((line) => {
    const cells = tableCells(line).map((cell) => `<td>${tableCell(cell)}</td>`).join("");
    return `<tr>${cells}</tr>`;
  });
  return `<div class="table-scroll"><table><thead><tr>${header}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
}

const fence = /^ {0,3}```(.*)$/;
const closingFence = /^ {0,3}```\s*$/;
const divider = /^\s*:?-{3,}:?\s*$/;
const listItem = /^\s*([-+*]|\d+\.)\s+(.+)$/;
const isTable = (lines, i) => lines[i].includes("|") && Boolean(lines[i + 1]?.includes("|"))
  && tableCells(lines[i + 1]).every((cell) => divider.test(cell));

function fenced(info, content) {
  const [kind, ...args] = info.trim().split(/\s+/);
  if (kind === "kv") {
    const cols = Number(args.find((arg) => arg.startsWith("cols="))?.slice(5) ?? 2);
    const width = Number.isInteger(cols) && cols >= 1 && cols <= 6 ? cols : 2;
    const items = content.filter((line) => line.trim()).map((line) => {
      const pair = line.match(/^(\* )?([^:：]+)[:：]\s*(.*)$/);
      return pair ? `<div${pair[1] ? ' class="wide"' : ""}><dt>${inline(pair[2])}</dt><dd>${inline(pair[3])}</dd></div>`
        : `<div><dt>${inline(line)}</dt><dd></dd></div>`;
    });
    return `<dl class="facts" style="--fact-cols:${width}">${items.join("")}</dl>`;
  }
  if (kind === "callout") {
    const tone = ["ok", "warn", "err", "info"].includes(args[0]) ? args.shift() : "info";
    const title = args.length ? `<strong>${inline(args.join(" "))}</strong>` : "";
    return `<aside class="callout ${tone}">${title}${blocks(content)}</aside>`;
  }
  if (kind === "flow") {
    const rows = content.filter((line) => line.trim()).map((line) => {
      const steps = line.split(/\s+--?>\s+/).map((step) => `<span>${inline(step)}</span>`);
      return `<div class="flow">${steps.join('<b aria-hidden="true">→</b>')}</div>`;
    });
    return rows.join("");
  }
  return `<pre><code>${escapeHtml(content.join("\n"))}</code></pre>`;
}

function blocks(lines) {
  const html = [];
  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const opening = line.match(fence);
    if (opening) {
      const start = ++i;
      while (i < lines.length && !closingFence.test(lines[i])) i++;
      html.push(fenced(opening[1], lines.slice(start, i)));
      if (i < lines.length) i++;
      continue;
    }
    if (isTable(lines, i)) {
      const start = i;
      i += 2;
      while (i < lines.length && /^\s*\|/.test(lines[i])) i++;
      html.push(table(lines.slice(start, i)));
      continue;
    }
    const item = line.match(listItem);
    if (item) {
      const tag = /^\d/.test(item[1]) ? "ol" : "ul";
      const items = [];
      while (i < lines.length) {
        const entry = lines[i].match(listItem);
        if (!entry || (/^\d/.test(entry[1]) ? "ol" : "ul") !== tag) break;
        items.push(`<li>${inline(entry[2])}</li>`);
        i++;
      }
      html.push(`<${tag}>${items.join("")}</${tag}>`);
      continue;
    }
    if (/^>\s?/.test(line)) {
      const quoted = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) quoted.push(lines[i++].replace(/^>\s?/, ""));
      html.push(`<blockquote>${blocks(quoted)}</blockquote>`);
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const level = Math.max(3, heading[1].length);
      html.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      i++;
      continue;
    }
    const paragraph = [line];
    while (++i < lines.length && lines[i].trim() && !fence.test(lines[i]) && !isTable(lines, i)
      && !listItem.test(lines[i]) && !/^(?:#{1,6}\s|>)/.test(lines[i])) paragraph.push(lines[i]);
    html.push(`<p>${inline(paragraph.join(" "))}</p>`);
  }
  return html.join("\n");
}

function frontMatter(lines) {
  const end = lines[0] === "---" ? lines.indexOf("---", 1) : -1;
  if (end === -1) return { meta: {}, start: 0 };
  const meta = {};
  for (const line of lines.slice(1, end)) {
    const match = line.match(/^([a-z][a-z-]*):\s*(.*)$/);
    if (match) meta[match[1]] = match[2].replace(/^(["'])(.*)\1$/, "$2");
  }
  return { meta, start: end + 1 };
}

function panelsOf(lines, start = 0) {
  const panels = [];
  let insideFence = false;
  for (let i = start; i < lines.length; i++) {
    if ((insideFence ? closingFence : fence).test(lines[i])) {
      insideFence = !insideFence;
      continue;
    }
    const heading = !insideFence && lines[i].match(/^##\s+(.+?)(?:\s+\{([^}]*)\})?\s*$/);
    if (!heading) continue;
    const key = heading[1].match(/^([A-Z])\s+(.+)$/);
    panels.push({ index: i, name: heading[1], key: key?.[1], title: key?.[2] ?? heading[1],
      span: Number(heading[2]?.match(/(?:^|\s)span=(\d+)/)?.[1] ?? 1) });
  }
  return panels;
}

function renderPage(source, options) {
  const lines = linesOf(source);
  const { meta, start } = frontMatter(lines);
  const mode = options.mode ?? meta.mode ?? "light";
  const theme = options.theme ?? meta.theme ?? "blueprint";
  const layout = options.template ?? meta.template ?? "doc";
  if (!["light", "dark", "auto"].includes(mode) || !["blueprint", "shadcn"].includes(theme)
    || !["doc", "sheet"].includes(layout)) throw new Error("Unsupported theme, mode, or template");

  const title = meta.title || "Code Review Lifecycle";
  const lang = /^[a-z]{2,3}(?:-[a-zA-Z0-9]+)*$/.test(meta.lang ?? "") ? meta.lang : "en";
  const panels = panelsOf(lines, start);
  const intro = blocks(lines.slice(start, panels[0]?.index ?? lines.length));
  const columns = Number(meta.cols);
  const cols = layout === "doc" ? 1 : Number.isInteger(columns) && columns >= 1 && columns <= 3 ? columns : 2;
  const content = panels.map((panel, i) => {
    const panelBody = blocks(lines.slice(panel.index + 1, panels[i + 1]?.index ?? lines.length));
    const label = panel.key ? `<span class="panel-key">${panel.key}</span>` : "";
    return `<section class="panel" style="--span:${Math.min(Math.max(panel.span, 1), cols)}"><h2>${label}${inline(panel.title)}</h2><div class="panel-body">${panelBody}</div></section>`;
  }).join("\n");

  const values = {
    LANG: lang, TITLE: plain(title), THEME: theme, MODE: mode, COLS: cols,
    SUBTITLE: meta.subtitle ? `<p class="subtitle">${inline(meta.subtitle)}</p>` : "",
    META: meta.source ? `<p class="source-note">${inline(meta.source)}</p>` : "",
    INTRO: intro ? `<div class="intro">${intro}</div>` : "",
    CONTENT: content,
    SOURCE: JSON.stringify({ source, options }).replaceAll("<", "\\u003c"),
  };
  return readFileSync(template, "utf8").replace(/@@([A-Z]+)@@/g, (_, name) => values[name]);
}

function recoverSource(page) {
  const saved = page.match(/<script id="review-source" type="application\/json">([\s\S]*?)<\/script>/);
  if (saved) return JSON.parse(saved[1]);
  const old = page.match(/<textarea id="am-source"[^>]*>([\s\S]*?)<\/textarea>/);
  if (old) return { source: decodeEntities(old[1]).replace(/^\n/, ""), options: {} };
  throw new Error("The page does not contain an editable source draft");
}

function updatePanel(source, key, replacement) {
  const lines = linesOf(source);
  const panels = panelsOf(lines, frontMatter(lines).start);
  const matches = panels.filter((panel) => [panel.name, panel.title, panel.key].includes(key));
  if (matches.length !== 1) throw new Error(`Expected one panel matching "${key}"`);
  const panel = matches[0];
  const index = panels.indexOf(panel);
  const next = panels[index + 1]?.index ?? lines.length;
  const revised = linesOf(replacement.trim());
  const headings = panelsOf(revised);
  if (headings.length > 1 || (headings.length === 1 && headings[0].index !== 0)) {
    throw new Error("Provide only the replacement for one panel");
  }
  if (!headings.length) revised.unshift(lines[panel.index], "");
  return [...lines.slice(0, panel.index), ...revised, "", ...lines.slice(next)].join("\n");
}

const usage = `Usage:
  node scripts/render_html.mjs render <draft.md|-> -o <page.html> [--no-open]
  node scripts/render_html.mjs patch <page.html> --panel <letter-or-title> <panel.md|-> [--no-open]
  node scripts/render_html.mjs help [format|patch]

Render options: --theme blueprint|shadcn, --mode light|dark|auto, --template doc|sheet.
Draft format: optional frontmatter (title, subtitle, source, lang, theme, mode, template, cols);
## headings for panels, {span=2} for full-width panels, plus Markdown paragraphs, links,
lists, tables, quotes, code fences, and the kv, callout, and flow blocks.`;

function parseOptions(args) {
  const flags = new Map([["-o", "output"], ["--output", "output"], ["--panel", "panel"],
    ["--theme", "theme"], ["--mode", "mode"], ["--template", "template"]]);
  const options = {};
  const files = [];
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--no-open") continue;
    if (flags.has(arg)) {
      const value = args[++i];
      if (!value || value.startsWith("--")) throw new Error(`Missing value for ${arg}`);
      options[flags.get(arg)] = value;
    } else if (arg.startsWith("-") && arg !== "-") {
      throw new Error(`Unknown option: ${arg}`);
    } else files.push(arg);
  }
  return { files, options };
}

function readDraft(path) {
  return readFileSync(path === "-" ? 0 : path, "utf8");
}

function main([command, ...args]) {
  if (!command || ["help", "--help", "-h"].includes(command) || args.includes("--help")) {
    console.log(usage);
    return;
  }
  const { files, options: { output, panel, ...appearance } } = parseOptions(args);
  let source;
  let target;
  let view = appearance;
  if (command === "render" && files.length === 1 && output && !panel) {
    if (files[0] !== "-" && resolve(files[0]) === resolve(output)) throw new Error("Use a different output path");
    source = readDraft(files[0]);
    target = output;
  } else if (command === "patch" && files.length === 2 && files[0] !== "-" && panel && !output) {
    target = files[0];
    const original = recoverSource(readFileSync(target, "utf8"));
    source = updatePanel(original.source, panel, readDraft(files[1]));
    view = { ...original.options, ...appearance };
  } else throw new Error(usage);
  const page = renderPage(source, view);
  mkdirSync(dirname(resolve(target)), { recursive: true });
  writeFileSync(target, page, "utf8");
  console.log(`Rendered ${resolve(target)}`);
}

try {
  main(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  process.exitCode = 2;
}

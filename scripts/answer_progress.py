"""Project a task snapshot to Markdown, then use the selected am renderer."""
from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime, tzinfo
from html import escape
from pathlib import Path
from urllib.parse import quote, urlparse

LABELS = {"running": "正在执行", "waiting_user": "等待所需结果或决定", "blocked": "遇到阻断",
          "failed": "执行失败", "not_started": "尚未开始", "completed": "已完成"}
PHASE_LABELS = {"prepare": "确定审查范围", "review": "审查与验证", "human_review": "人工审核",
                "pre_pr": "PR 前", "in_pr": "PR 中", "post_pr": "PR 后"}
ACTION_LABELS = {"technical_replan": "三轮后的方案决策", "final_review": "合并前最终人工审核",
                 "target_acceptance": "真实环境验收结果", "missing_information": "缺少必要信息"}


def check_badge(value: object) -> str:
    if value in {"passed", "success", "approved", "no_blockers"}:
        return "ok 通过"
    if value in {"failed", "failure", "error", "timed_out", "changes_required"}:
        return "no 未通过"
    if value in {"in_progress", "running", "third_review_running", "fourth_review_running"}:
        return "warn 进行中"
    if value in {"pending", "queued", "waiting"}:
        return "warn 待处理"
    if value in {"not_run", "not_started"}:
        return "warn 未执行"
    if value == "cancelled":
        return "warn 已取消"
    if value == "completed":
        return "warn 已结束，结果未记录"
    return "warn 未记录"


def text(value: object) -> str:
    value = escape(str(value), quote=False).replace("`", "&#96;")
    return value.replace("[", "\\[").replace("]", "\\]").replace("|", "\\|").replace("\n", " ").strip()


def paragraphs(value: str) -> str:
    # Preserve facts while separating long status sentences for reading.
    return "\n\n".join(text(part) for part in re.split(r"(?<=[。！？；])", value) if part.strip())


def link(label: str, href: str) -> str:
    if urlparse(href).scheme not in {"https", "http", "file"}:
        raise ValueError("Evidence links must use http, https or file")
    return f"[{text(label)}]({quote(href, safe=':/?=&%#@+~;,$!*')})"


def when(value: str, zone: tzinfo) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(zone).strftime("%Y-%m-%d %H:%M")


def build_draft(state: dict, state_path: Path) -> str:
    view = state.get("presentation", {})
    display_zone = datetime.fromisoformat(state["updated_at"].replace("Z", "+00:00")).tzinfo
    if display_zone is None:
        raise ValueError("The task's display time must include a timezone")
    for key, allowed, default in (("theme", {"shadcn", "blueprint"}, "blueprint"),
                                  ("template", {"doc", "sheet"}, "doc"),
                                  ("mode", {"light", "dark", "auto"}, "light")):
        if view.get(key, default) not in allowed:
            raise ValueError(f"Unsupported presentation {key}")
    pending = any(c["status"] == "pending" for c in state["goal"]["criteria"])
    conclusion = "全流程尚未结案" if pending else LABELS[state["status"]]
    tone = "err" if state["status"] == "failed" else "warn" if pending else "ok"
    issues = [item for item in state["issues"] if item["blocking"]]
    owners = "、".join(dict.fromkeys(item["owner"] for item in issues)) or state["next_step"]["owner"]
    lines = ["---", f"template: {view.get('template', 'doc')}", f"theme: {view.get('theme', 'blueprint')}",
             f"mode: {view.get('mode', 'light')}", "lang: zh", "cols: 2",
             f"title: {text(state['project'])} · 当前进度",
             f"subtitle: {PHASE_LABELS[state['phase']]} · {LABELS[state['status']]}",
             f"source: 状态记录 {when(state['updated_at'], display_zone)}（{display_zone}）", "---", "",
             f"**{text(state['user_message'])}**", "", "## A 当前状态 {span=2}", "",
             f"```callout {tone} {conclusion}", paragraphs(state["current_action"]), "```", "",
             "```kv cols=2", f"当前阶段: {PHASE_LABELS[state['phase']]}",
             f"当前版本: {text(state['source_commit'][:8])}", f"卡点责任: {text(owners)}",
             f"下一步责任: {text(state['next_step']['owner'])}", "```", ""]
    for issue in issues:
        lines.extend([f"**卡点：{text(issue['title'])}**", ""])
        if state["status"] in {"failed", "blocked"}:
            lines.extend([paragraphs(issue["impact"]), ""])
    if state.get("prs"):
        lines.extend(["**PR 检查与合并分别记录：**", "", "| PR | 审核版本 | CI | 独立 AI | 人审 | 合并 |", "|---|---|---|---|---|---|"])
        for pr in state["prs"]:
            ai = check_badge(pr.get("ai_status"))
            if pr.get("ai_completed_reviews") is not None:
                ai += f"（{text(pr['ai_completed_reviews'])}次）"
            merged = "ok 已合并" if pr.get("merged") is True else "warn 未合并" if pr.get("merged") is False else "warn 未记录"
            lines.append(f"| #{text(pr.get('number', '未记录'))} | {text(str(pr.get('head') or '未记录')[:8])} | {check_badge(pr.get('ci_status'))} | {ai} | {check_badge(pr.get('human_status'))} | {merged} |")
        lines.extend(["", "CI 与 AI 可以并行；通过检查、人工通过和实际合并是不同状态。", ""])
    lines.extend(["## B 你现在需要做什么", ""])
    if state["user_actions"]:
        for action in state["user_actions"]:
            if action.get("kind") in ACTION_LABELS:
                lines.extend([f"**当前关口：{ACTION_LABELS[action['kind']]}**", ""])
            lines.extend([f"**{text(action['question'])}**", "", paragraphs(action["recommendation"]), "",
                          paragraphs(action.get("reply_hint", "")), ""])
            if action.get("instruction"):
                lines.extend(["在当前对话回复以下内容：", "", "```text", action["instruction"], "```", ""])
            lines.extend(["影响：" + paragraphs(action["impact"]), ""])
    else:
        lines.extend(["**暂时无需操作。**", "", paragraphs(state["user_message"]), ""])
    lines.extend(["**接下来：**", "", paragraphs(state["next_step"]["text"]), "",
                  "## C 审查阶段", "", "| 阶段 | 状态 | 当前记录 |", "|---|---|---|"])
    for phase in state["phases"]:
        label = "待反馈" if phase["status"] == "waiting_user" else LABELS[phase["status"]]
        badge = "ok 已完成" if phase["status"] == "completed" else "warn " + label
        lines.append(f"| {PHASE_LABELS[phase['id']]} | {badge} | {text(phase['note'])} |")
    lines.extend(["", "## D 审查结果与证据", ""])
    delivery_criterion = next((c for c in state["goal"]["criteria"] if c["id"] == "delivery"), {})
    evidence = delivery_criterion.get("evidence")
    delivery = delivery_criterion.get("evidence_href")
    if not delivery and isinstance(evidence, str) and urlparse(evidence).scheme in {"https", "http", "file"}:
        delivery = evidence
    if delivery:
        lines.extend([link("打开交付包", delivery), ""])
    elif evidence:
        lines.extend(["交付依据：" + text(evidence), ""])
    if state["results"]:
        lines.extend(["| 结果 | 说明 |", "|---|---|"])
        lines.extend(f"| **{text(item['value'])}** | {text(item['label'])} |" for item in state["results"])
        lines.append("")
    chosen = [item for item in state["links"] if item["href"] != delivery][:3]
    if chosen:
        lines.extend([" · ".join(link(item["label"], item["href"]) for item in chosen), ""])
    lines.extend(["## E 原始证据，按需查看", "", "| 核对内容 | 结果 | 记录时间与入口 |", "|---|---|---|"])
    for check in state["checks"][:5]:
        badge = {"passed": "ok 已通过", "failed": "no 未通过", "not_run": "warn 待执行"}[check["status"]]
        label = when(check["observed_at"], display_zone) if check.get("observed_at") else "查看记录"
        source = link(label, check["href"]) if check.get("href") else "见完整状态记录"
        lines.append(f"| {text(check['title'])} | {badge} | {source} |")
    for check in state["checks"][:5]:
        if check.get("command"):
            lines.extend(["", f"**{text(check['title'])}：片段与说明**", "", paragraphs(check["summary"]),
                          "", "```text", check["command"], "```", ""])
    lines.extend(["", "检查保留各自的记录时间。页面换版不代表重新执行检查。", "",
                  link("完整检查、文件与历史", state_path.resolve().as_uri()), "",
                  paragraphs(state.get("boundary", "")), "", "本页是进度快照；Agent 更新后重新打开即可。", ""])
    return "\n".join(lines)


def render_answer_progress(state: dict, state_path: Path, output: Path) -> None:
    view = state.get("presentation", {})
    explicit = view.get("am_cli")
    cli = Path(explicit) if explicit else Path(__file__).resolve().with_name("render_html.mjs")
    if not cli.is_file():
        raise ValueError(f"HTML renderer not found: {cli}")
    node = shutil.which("node")
    if node is None:
        raise ValueError("HTML rendering requires Node.js 20 or newer")
    draft = build_draft(state, state_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    draft_path = output.with_suffix(".view.md")
    draft_path.write_text(draft, encoding="utf-8")
    subprocess.run([node, str(cli), "render", str(draft_path), "-o", str(output), "--no-open"], check=True)

<div align="center">

**English** · [Simplified Chinese](docs/README.zh-CN.md) · [Japanese](docs/README.ja.md)

# Code Review Lifecycle

**AI-assisted code review, from local changes to a human merge decision.**

A shared Agent Skill for **Codex**, **Claude Code**, and **OpenCode**.

[![CI](https://github.com/HoeTee/code-review-lifecycle-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/HoeTee/code-review-lifecycle-skill/actions/workflows/ci.yml)
[![Agent Skill](https://img.shields.io/badge/Agent_Skill-Codex%20%C2%B7%20Claude%20Code%20%C2%B7%20OpenCode-5c4ee5?style=flat-square)](references/agent-support.md)
[![MIT license](https://img.shields.io/badge/license-MIT-f4c430?style=flat-square)](LICENSE)

[Quick start](#install-and-try-it) · [Workflow](#workflow) · [Capabilities](#what-the-skill-does) · [Example](#example-review) · [FAQ](#faq) · [Guides](#repository-guide)

<code>npx skills add HoeTee/code-review-lifecycle-skill</code>

</div>

<p align="center">
  <img src="docs/media/review-lifecycle-hero.webp" width="860" alt="A code diff, verification evidence, and a human review decision connected through the review lifecycle.">
</p>

Ask your coding agent to review a change. It reads the repository's rules, identifies the local changes or PR, and checks the affected code and behavior. When fixes are authorized, it follows findings through verification and re-review.

The human reviewer gets key code, actual check results, remaining risks, and a clear decision to make. Review evidence stays tied to the PR and commit it describes.

## Install and try it

From your project directory, run:

```sh
npx skills add HoeTee/code-review-lifecycle-skill --agent codex claude-code opencode
```

You need Git and Node.js 22.20 or newer for the [skills installer](https://www.npmjs.com/package/skills). Keep only the agents you use after `--agent`. Add `--global` for a user-wide installation.

### Ask for a review

```text
Use the code-review-lifecycle skill to review my changes.
```

| Agent | Start the skill |
| --- | --- |
| Codex | Invoke `$code-review-lifecycle`. |
| Claude Code | Run `/code-review-lifecycle` followed by your request. |
| OpenCode | Ask it to load `code-review-lifecycle` and describe your task. |

Start with local changes, an open PR, or a revised commit. The agent determines the review target and comparison base. PR and CI operations use your existing repository access. [Agent setup and requirements](references/agent-support.md)

## Workflow

| Before a PR | During PR review | Before merge |
| --- | --- | --- |
| Read the rules and identify the change. | Verify findings, fix with authorization, and re-review. | Give a person the evidence to decide. |
| **Result:** review scope, findings, and local evidence. | **Result:** revision checks and CI matched to the reviewed commit. | **Result:** a review brief and an explicit human decision. |

You can enter at any stage. Reviews are read-only by default. Fixes, pushes, comments, and other platform writes need authorization for the corresponding action.

### 1. Before a PR: understand the change

Read the applicable `CLAUDE.md` and `REVIEW.md` before analyzing the diff. Load rules and their included files from the same trusted baseline. Changes to the rules are themselves part of the review.

Identify staged, unstaged, committed, and relevant untracked changes. Follow affected callers, consumers, shared state, and failure paths. Run applicable checks or inspect existing evidence. Use an independent review context when the host provides one. [Review scope and rules](references/review-target.md)

### 2. During PR review: check each revision

Pin the PR base and head, then inspect CI, logs, findings, and discussion threads. Check that the evidence applies to the current version.

With fixes authorized, verify each finding, fix confirmed problems in scope, and repeat the affected checks. Re-review the revised code and its effects. The AI review cycle ends when blockers clear, with up to three completed rounds by default. If blockers remain after round three, automatic fixes stop and the agent explains the remaining problem and proposes a next step. [Review and revision](references/pr-workflow.md)

### 3. Before merge: put the decision in human hands

After required checks pass and blockers are addressed, prepare a brief with the behavior before and after the change, key code, actual evidence, unverified areas, and decisions still open. Keep the full diff and source available.

A person approves, requests changes, or defers. Record that decision against the PR and reviewed commit. New changes that affect the decision require the relevant checks and review again. Repository approval rules still apply. [Human review](references/human-review.md)

The workflow draws on the Claude Code team's practices for early review, bounded review rounds, and explanations of key code. [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/)

## What the skill does

| Capability | What you get |
| --- | --- |
| Automatic review scope | The local candidate or existing PR, a confirmed base, and relevant new files included in the review. |
| Call-path and impact analysis | Checks of inputs, shared interfaces, state changes, downstream consumers, and failure propagation. |
| Independent AI review | Findings checked in a context separate from the author when available, with triggers, impact, and evidence. |
| Behavior-based verification | Relevant unit, API, integration, end-to-end, build, and real-task checks, with actual results and limits. |
| Re-review after fixes | Original findings checked against the revised code, related effects, and still-valid evidence. |
| PR and CI evidence | Check results and discussion status matched to the reviewed commit and actual fix. |
| Code explanations for people | The reason for a change, the code that matters, and the questions that need human judgment. |
| Review progress | A reusable HTML report with the reviewed version, stage, evidence, blockers, and next action. |

Product UI verification can include screenshots when required. Generated explanation and review pages are checked for content and links without a screenshot pass.

## Example review

### Access is revoked while an export is waiting

A user queues a CSV export, then loses access before the worker runs. The reviewer follows the request into the worker and finds that the worker can still generate the file.

With fixes authorized, the author adds a permission check at execution time and a regression test. Re-review confirms that revoked access prevents file creation and checks the CI result for that commit. A person then decides whether `Export unavailable` explains the outcome clearly enough.

![Illustrative review brief for PR 42 at commit a1b2c3d. CI passed, AI blockers resolved, and a human decision is pending.](docs/media/export-review-preview.png)

*Illustrative case, not a live PR. [Read the example brief](docs/showcase/export-review.md).*

<details>
<summary><strong>Render this example locally</strong></summary>

From a clone of this repository:

```sh
node scripts/render_html.mjs render docs/showcase/export-review.md -o export-review.html --no-open
```

</details>

## FAQ

<details>
<summary><strong>Does installing the skill start reviews automatically?</strong></summary>

Ask your coding agent to use the skill. The package supplies instructions, references, templates, and a report renderer. Unattended reviews need a separately configured trigger and agent runner.

</details>

<details>
<summary><strong>Do I need another model or a review service?</strong></summary>

Use your coding agent's available tools and review capabilities. Independent review needs a context separate from the author. When that capability is unavailable, the agent reports the limitation and distinguishes author self-checks from independent review.

</details>

<details>
<summary><strong>Will the agent change code or push to GitHub?</strong></summary>

A review is read-only by default. You can authorize fixes, PR updates, or other writes. Each action stays within that authorization and the repository's permissions.

</details>

<details>
<summary><strong>Does passing CI count as human approval?</strong></summary>

CI results, AI review, and the human decision are recorded separately. Required checks must pass, and any required platform approval must come from an eligible person. Decisions apply to the reviewed version.

</details>

<details>
<summary><strong>What runs locally, and what tools do I need?</strong></summary>

The skill runs through your coding agent and its tools. Git identifies changes. Remote PR and CI access needs platform authentication. The bundled HTML renderer needs Node.js 20 or newer; the installation requirement above also covers it. Rendering a progress snapshot additionally needs Python 3.

The skill instructions and reference guides are mainly in Chinese. This README is available in English, Chinese, and Japanese.

</details>

## Repository guide

| Guide | Use it to |
| --- | --- |
| [SKILL.md](SKILL.md) and [agent support](references/agent-support.md) | Find the shared entry point, invocation, and host requirements. |
| [Review scope and rules](references/review-target.md) and [review template](assets/REVIEW.template.md) | Understand how the skill chooses a diff and applies repository rules. |
| [Review and revision](references/pr-workflow.md) and [human review](references/human-review.md) | Follow findings through fixes, re-review, and a human decision. |
| [Verification](references/verification.md) | Select checks from the change and its effects. |
| [Progress reports](references/progress-interaction.md) and [evidence reuse](references/execution-efficiency.md) | Track the review and preserve evidence that still applies. |
| [GitHub](references/platforms/github.md) and [Gitee](references/platforms/gitee.md) | Connect to the platform and inspect PR and CI evidence. |
| [Progress example](assets/progress.example.json) and [validation scenarios](references/validation-scenarios.md) | Try a snapshot or check changes to the skill. |

<details>
<summary><strong>Render the progress example or run the checks</strong></summary>

From a clone of this repository:

```sh
python scripts/render_progress.py assets/progress.example.json --output progress-example.html
python -B -m unittest discover -s scripts -v
```

GitHub Actions runs the same test suite for pull requests and pushes to `main`. It checks progress evidence, HTML rendering, panel updates, and bundled renderer integrity.

</details>

## Feedback and contributions

Found a missed defect, a false positive, or an unclear instruction? [Open an issue](https://github.com/HoeTee/code-review-lifecycle-skill/issues) with your agent, the reviewed version, the request, and a small reproduction or expected result.

Improvements to the instructions, examples, tests, and translations are welcome through [pull requests](https://github.com/HoeTee/code-review-lifecycle-skill/pulls).

## License

The project's own work is licensed under the [MIT License](LICENSE).

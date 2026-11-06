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

**Request a review → read trusted rules → identify the change → AI review ↔ authorized fixes → PR checks → human decision → merge handoff.**

You can start with local changes or an existing PR. A local-only request ends with a review report. PR creation, updates, and merging require authorization for those actions.

The YAML below describes the agent's workflow. The agent follows [SKILL.md](SKILL.md) and the linked guides; this block is not an executable GitHub Actions configuration.

```yaml
workflow:
  trigger: "Ask your agent to review a change or PR"
  default_mode: read_only
  max_ai_review_rounds: 3  # One total across local review and the PR.

  stages:
    - id: read_rules
      owner: agent
      action: "Read trusted CLAUDE.md, REVIEW.md, and included rules"
      if_root_rules_missing: "Draft missing rules; ask before writing; continue independent checks"
      if_references_missing: "Report missing paths and affected checks"

    - id: identify_change
      owner: agent
      action: "Choose local changes or a PR; pin the base and reviewed version"
      local_scope: "Include in-scope committed, staged, unstaged, and untracked changes"
      pr_scope: "Review the pinned PR head; list extra local changes separately"

    - id: ai_review
      owner: independent_reviewer_when_available
      action: "Review the full diff, affected callers, failure paths, and available checks"
      output: "Verified P0/P1/P2 findings, evidence, and unresolved counts"

    - id: resolve_findings
      owner: author_or_authorized_agent
      with_fix_authorization: "Fix confirmed problems; rerun checks; return to ai_review"
      without_fix_authorization: "Report findings and blockers; keep code unchanged"
      on_repeated_failure: "If two fixes share a premise and fail the same check, test that premise"
      after_round_three_with_blockers: "Stop automatic fixes; diagnose and propose options"
      if_local_only: "Deliver the report and any authorized fixes; no PR is required"

    - id: pr_checks
      owner: agent_and_ci
      when: "A PR exists, or PR delivery is requested and authorized"
      action: "Create or update only as authorized; match CI and threads to base/head"
      on_new_code: "Return to ai_review within the same three-round total"
      on_failed_or_missing_checks: "Resolve within authorization or report the blocker"
      ready_when: "Required checks pass, evidence is sufficient, and no blockers remain"

    - id: human_review
      owner: human
      requires: "A PR and the ready_when conditions above"
      input: "Exact commit, P0/P1/P2 summary, key code, evidence, risks, and decisions"
      approve: "Record the decision for the reviewed version"
      request_changes: "Return to authorized fixes and review within the remaining rounds"
      defer: "Wait for the human decision; preserve the evidence"

    - id: merge_handoff
      owner: authorized_merger
      requires: "Human approval, passing checks, repository rules, and merge authorization"
      on_changed_version: "Repeat affected checks and review; reconfirm affected decisions"
      result: "Merge when authorized, or hand off with remaining merge conditions"
```

The round limit applies to every return to AI review. Creating a PR, changing methods, or resuming a session does not reset it. If further review would exceed the limit, stop the automatic loop and present a concrete plan for a decision. CI retries do not consume another review round.

CI and AI review can run in parallel for an existing PR. Its available CI evidence is inspected during review; the final PR check confirms that all required results apply to the version sent to the human. Missing independent-review capability is reported as a limitation.

[Review scope and trusted rules](references/review-target.md) · [Missing-rule drafts](references/review-rules.md) · [Review and revision](references/pr-workflow.md) · [Human review and P0/P1/P2](references/human-review.md)

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

# Code Review Lifecycle

**AI-assisted code review, from local changes to a human merge decision.**

A shared Agent Skill for Codex, Claude Code, and OpenCode. It reads your repository's rules, identifies the change to review, checks the affected behavior, and follows findings through authorized fixes and re-review.

Ask it to review your changes. Start before a PR exists, bring an open PR, or return after a revision. The agent determines the review target and continues from the relevant stage.

[📦 Install](#install-and-try-it) · [🧭 Workflow](#workflow) · [🔎 Capabilities](#what-the-skill-does) · [📄 Example](#example-review) · [📚 Guides](#repository-guide)

[Simplified Chinese](docs/README.zh-CN.md) · [Japanese](docs/README.ja.md)

## Install and try it

Run this in your project with Git and Node.js 22.20 or newer, as required by the `skills` installer. List only the agents you use after `--agent`. Add `--global` to install for your user account. [Installer package](https://www.npmjs.com/package/skills)

```sh
npx skills add HoeTee/code-review-lifecycle-skill --agent codex claude-code opencode
```

| Agent | How to start |
| --- | --- |
| Codex | Invoke `$code-review-lifecycle`. |
| Claude Code | Run `/code-review-lifecycle` followed by your request. |
| OpenCode | Ask OpenCode to load `code-review-lifecycle` and describe your task. |

> Use the `code-review-lifecycle` skill to review my changes.

PR and CI operations use your existing repository permissions. The bundled HTML renderer runs on Node.js 20 or newer. [Agent support](references/agent-support.md)

<p align="center">
  <img src="docs/media/review-lifecycle-hero.webp" width="780" alt="A code diff, verification evidence, and a human approval stamp connected through the review lifecycle.">
</p>

## Workflow

| Stage | Main question | Review outcome |
| --- | --- | --- |
| **1. Before a PR** | What changed, and what could it break? | A defined review target, verified findings, and local check results. |
| **2. During PR review** | Do the fixes work on the current commit? | Findings addressed, relevant checks repeated, and PR/CI evidence matched to the reviewed version. |
| **3. Before merge** | Does a person have enough evidence to decide? | A review brief with key code, remaining risks, and an explicit human decision. |

You can enter at any stage. A review is read-only by default. Fixes, pushes, comments, and other platform writes require authorization for the corresponding action.

### 1. Before a PR: review the local change

The agent first reads the applicable `CLAUDE.md` and `REVIEW.md`. Review rules and their included files come from the same trusted baseline. Changes to those rules are themselves reviewable changes.

It identifies staged changes, unstaged changes, relevant new files, and committed branch changes. A clean working tree still gets compared with the appropriate base. You do not need to supply every path or Git command.

The review follows affected callers, consumers, shared state, and failure paths. It runs applicable project checks or inspects existing evidence, with an independent reviewer when the host supports a separate review context. Each finding includes its location, trigger, impact, and verification evidence. [Review targets and rules](references/review-target.md)

### 2. During PR review: verify, fix, and re-review

For an open PR, the agent records the exact base and head commits used for the review. It reads CI results, failure logs, review comments, and thread state. A green check on an older commit does not validate the current change.

When fixes are authorized, it checks the finding, addresses the confirmed problem and related instances in scope, and repeats the affected checks. Re-review compares the last reviewed commit with the new one. A changed base or impact scope triggers a fresh look at the full diff.

Each PR has up to three completed AI review rounds by default, ending early when blockers are cleared. If blockers remain after round three, automatic fixes pause. The agent explains what stalled and proposes a next step. [PR review and revision](references/pr-workflow.md)

### 3. Before merge: make the human decision clear

After the required technical checks and blockers are addressed, the agent prepares a brief for the human reviewer. It explains the behavior before and after the change, key code and call paths, actual check results, unverified areas, and decisions still open. The full diff and source remain available.

The person explicitly approves, requests changes, or defers. The decision is recorded against the PR and reviewed commit. New changes that affect the decision go back through the relevant checks and review. Required platform approvals follow the repository's rules. [Human review and evidence](references/human-review.md)

The workflow draws on the Claude Code team's practices for early review, limits on review rounds, and explanations of the code a reviewer needs to understand. [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/)

## What the skill does

| Capability | What it does in a review |
| --- | --- |
| **Automatic review scope** | Chooses the local candidate or existing PR, resolves its comparison base, and includes relevant untracked files. |
| **Call-path and impact analysis** | Follows inputs, shared interfaces, state changes, downstream consumers, and failure propagation beyond the changed lines. |
| **Independent AI review** | Uses a context separate from the author when available. Verifies findings and distinguishes new defects, existing defects, and unverified concerns. |
| **Behavior-based verification** | Selects relevant unit, API, integration, end-to-end, build, and real-task checks. Records what actually ran and what remains unverified. |
| **Review after each fix** | Checks the revised behavior and related effects, preserves valid evidence, and limits repeated review rounds. |
| **PR and CI evidence** | Matches checks and review conclusions to the current commit. Checks thread resolution against the actual fix. |
| **Code explanations for people** | Explains why a change is needed, how the affected code works, and where a person's judgment is required. |
| **Progress and context recovery** | Keeps the reviewed version, stage, evidence, blockers, and next action in a reusable HTML report. Resumes with still-valid task context. |

Verification follows the changed behavior and repository requirements. Product UI checks can include screenshots. Generated explanation and review pages are checked for content and links without a screenshot pass.

These are instructions your coding agent executes with its available tools. Independent review needs a separate review context. Remote operations need platform access. The skill follows your configured CI and approval gates. [Agent support](references/agent-support.md) · [Verification](references/verification.md) · [Progress reports](references/progress-interaction.md)

## Example review

A user queues a CSV export, then loses access before the worker runs. The AI reviewer traces the request into the worker and finds that the worker can still generate the file.

With fixes authorized, the author adds a second permission check and a regression test that confirms no file is written after access is revoked. Re-review checks the fix and the CI result for that commit. A person then decides whether `Export unavailable` gives users enough information.

![Illustrative review brief for PR 42 at commit a1b2c3d. CI passed, AI blockers resolved, and a human decision is pending.](docs/media/export-review-preview.png)

*Illustrative PR. The preview was rendered from the [example brief](docs/showcase/export-review.md) with the bundled HTML renderer.*

<details>
<summary>Render the example locally</summary>

```sh
node scripts/render_html.mjs render docs/showcase/export-review.md -o export-review.html --no-open
```

</details>

## Repository guide

| Start here | What it covers |
| --- | --- |
| [SKILL.md](SKILL.md) | The shared entry point and how the agent chooses a stage. |
| [Review target and rules](references/review-target.md) and [review rules template](assets/REVIEW.template.md) | See how the skill chooses a diff and applies repository rules. |
| [PR review and revision](references/pr-workflow.md) and [human review](references/human-review.md) | Follow findings through fixes, re-review, and a human decision. |
| [Verification](references/verification.md) | Choose checks based on the change and its effects. |
| [Progress reports](references/progress-interaction.md) and [context and evidence reuse](references/execution-efficiency.md) | Track the stage and resume with evidence that still applies. |
| [GitHub](references/platforms/github.md) and [Gitee](references/platforms/gitee.md) | Connect to the platform and inspect PR and CI evidence. |
| [Progress data](assets/progress.example.json) and [validation scenarios](references/validation-scenarios.md) | Try a local snapshot or verify a change to the skill. |

The skill instructions, templates, and reference guides are mainly in Chinese. To render the bundled local progress example, run this from the repository with Python 3 and Node.js 20 or newer.

```sh
python scripts/render_progress.py assets/progress.example.json --output progress-example.html
```

Run `python -B -m unittest discover -s scripts -v` to check progress evidence, HTML rendering and panel updates, and the integrity of the bundled renderer. GitHub Actions runs the same suite for pull requests and pushes to `main`.

## License

The project’s own work is licensed under the [MIT License](LICENSE).

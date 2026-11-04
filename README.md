# Code Review Lifecycle

**Review changes with AI. Give people the evidence to decide what ships.**

An Agent Skill for Codex, Claude Code, and OpenCode. Start with an existing PR or follow a change from acceptance criteria through delivery.

[📦 Install](#install-and-try-it) · [🔎 See an example](#example-review) · [🧭 Follow the workflow](#workflow) · [📚 Browse the guides](#repository-guide)

[Simplified Chinese](docs/README.zh-CN.md) · [Japanese](docs/README.ja.md)

<p align="center">
  <img src="docs/media/review-lifecycle-hero.webp" width="780" alt="A code diff, a stack of verification evidence, and a human approval stamp connected by one trace.">
</p>

## Install and try it

Run this in your project with Node.js 20 or newer and Git. List only the agents you use after `--agent`. Add `--global` to install for your user account.

```sh
npx skills add HoeTee/code-review-lifecycle-skill --agent codex claude-code opencode
```

| Agent | How to start |
| --- | --- |
| Codex | Invoke `$code-review-lifecycle`. |
| Claude Code | Run `/code-review-lifecycle` followed by your request. |
| OpenCode | Ask OpenCode to load `code-review-lifecycle` and describe your task. |

> Use the `code-review-lifecycle` skill to review this PR. Show me the findings, which checks ran on this revision, and what I need to decide before merging.

PR and CI operations use your existing repository permissions. The HTML renderer is bundled. [Agent support](references/agent-support.md) · [Renderer source and licenses](scripts/vendor/answer-me-with-html/README.md)

## What you can do

| Set up a project | Review a pull request | Investigate a regression |
| --- | --- | --- |
| Define acceptance criteria and reuse the repository’s test and review rules. | Verify AI findings, recheck fixes, and prepare a brief for the human reviewer. | Match logs to the deployed revision, then plan a fix and a way to verify it. |
| [Project setup](references/project-setup.md) | [PR workflow](references/pr-workflow.md) | [Delivery and recovery](references/delivery-recovery.md) |

## Example review

A user queues a CSV export, then loses access before the worker runs. The AI reviewer traces the request into the worker and finds that the worker can still generate the file. The author adds a second permission check and a regression test that confirms no file is written after access is revoked.

The reviewer gets a brief with the finding, the checks that ran, and the decision still open. In this example, a person decides whether `Export unavailable` gives users enough information.

![Illustrative review brief for PR 42 at commit a1b2c3d. CI passed, AI blockers resolved, and a human decision is pending.](docs/media/export-review-preview.png)

*Illustrative PR. The preview was rendered from the [example brief](docs/showcase/export-review.md) with the bundled HTML renderer.*

<details>
<summary>Render the example locally</summary>

```sh
node scripts/render_html.mjs render docs/showcase/export-review.md -o export-review.html --no-open
```

</details>

## Workflow

| Stage | What gets recorded |
| --- | --- |
| **Before the PR** | Acceptance criteria, affected behavior, local checks, and their results. |
| **Open the PR** | The current revision and required CI results. CI and AI review can run in parallel. |
| **Review and revise** | Verified findings, fixes, and evidence from the revised commit. |
| **Human review and merge** | The reviewer’s decision, evidence, and remaining risks for the reviewed commit. |
| **After merge** | The merge commit and, when in scope, release, deployment, and target environment results. |

### AI review and revision

An independent reviewer reads the diff and follows relevant call paths when that capability is available. A finding gives the location, trigger, impact, and a way to verify it. The author checks the evidence and fixes confirmed defects. Later passes recheck the fixes and their effects.

The cycle ends when no blockers remain and runs for up to three completed review rounds by default. If blockers remain after round three, the agent pauses automated fixes, explains why the approach stalled, and proposes a next step. [PR workflow and AI review](references/pr-workflow.md)

### Human review and the merge decision

The human reviewer sees what changed, key code excerpts, a link to the full diff, the checks that ran, and what still needs judgment. They explicitly approve, request changes, or defer. The decision is recorded against the PR and reviewed commit. Changes that affect the decision go back through the relevant checks and review. [Human review and evidence](references/human-review.md)

The workflow draws on the Claude Code team’s practices for early review, limits on review rounds, and explanations of the code a reviewer needs to understand. [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/)

## Repository guide

| Start here | What it covers |
| --- | --- |
| [SKILL.md](SKILL.md) | The shared entry point and how the agent chooses a stage. |
| [Project setup](references/project-setup.md) and [review rules template](assets/REVIEW.template.md) | Adapt the workflow to your existing `AGENTS.md`, `CLAUDE.md`, or `REVIEW.md`. |
| [Verification](references/verification.md) | Choose checks based on the change and its effects. |
| [GitHub](references/platforms/github.md) and [Gitee](references/platforms/gitee.md) | Connect to the platform and inspect PR and CI evidence. |
| [Progress data](assets/progress.example.json) and [validation scenarios](references/validation-scenarios.md) | Try a local snapshot or verify a change to the skill. |

The skill instructions, templates, and reference guides are mainly in Chinese. To render the bundled local progress example, run this from the repository with Python 3 and Node.js 20 or newer.

```sh
python scripts/render_progress.py assets/progress.example.json --output progress-example.html
```

If you change the progress renderer, run `python -m unittest discover -s scripts`.

## License

The project’s own work is licensed under the [MIT License](LICENSE). The bundled HTML renderer, fonts, and dependencies retain their [upstream licenses](scripts/vendor/answer-me-with-html/README.md).

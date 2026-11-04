# Code Review Lifecycle

[Simplified Chinese](docs/README.zh-CN.md) · [Japanese](docs/README.ja.md)

**A skill for reviewing pull requests and delivering changes with Codex, Claude Code, and OpenCode.**

AI finds issues and rechecks fixes. A human reviewer gets a short brief with what changed, which checks ran, and what still needs a decision. Start with an existing PR or follow a change from acceptance criteria through delivery.

[📦 Install](#install-and-try-it) · [🔎 See an example](#example-review) · [🧭 Follow the workflow](#workflow) · [📚 Browse the guides](#repository-guide)

## Install and try it

Run this from the target project with Node.js 20 or newer and Git. List only the agents you use after `--agent`. Add `--global` to install for your user account.

```sh
npx skills add HoeTee/code-review-lifecycle-skill --agent codex claude-code opencode
```

| Agent | How to start |
| --- | --- |
| Codex | Invoke `$code-review-lifecycle`. |
| Claude Code | Run `/code-review-lifecycle` followed by your request. |
| OpenCode | Ask OpenCode to load the `code-review-lifecycle` skill and describe your task. |

**Try it on an existing PR.**

> Use the `code-review-lifecycle` skill to review this PR. Show me the findings, checks for the current revision, and decisions I need to make before merging.

**Other ways to start**

- **Set up a project.** “Use the `code-review-lifecycle` skill to propose local checks, CI requirements, and review rules for this repository. Start from our existing project instructions.”
- **Investigate a regression.** “Use the `code-review-lifecycle` skill to compare these logs with the deployed revision and propose a fix and a way to verify it.”

PR and CI actions require repository access and the relevant permissions. Platform guides cover GitHub and Gitee. HTML explainers use the bundled Answer me with HTML renderer. [Agent support](references/agent-support.md) · [GitHub guide](references/platforms/github.md) · [Gitee guide](references/platforms/gitee.md) · [Renderer source and licenses](scripts/vendor/answer-me-with-html/README.md)

## Example review

Suppose a PR changes who can export project data. A user starts an export, then loses access while the job is still queued. This illustrative review shows how a finding becomes evidence for a decision.

| Handoff | What the reviewer sees |
| --- | --- |
| **AI finding** | The request handler checks access, but the queue worker starts the export without checking again. If access is revoked between those steps, the worker can still generate the file. |
| **Fix and verification** | Check access again in the worker. Add a regression test that queues a job, revokes access, runs the worker, and confirms that no file is written. Attach the test result to the revised commit. |
| **Human decision** | The review brief shows the request handler, worker, and regression result alongside the full diff. The reviewer decides whether `Export unavailable` gives users enough information when access is revoked. |

## Workflow

The workflow draws on the Claude Code team’s practices for early review, limiting review rounds, and explaining the code a person needs to understand. This skill uses those practices to prepare a final human review tied to a specific PR and commit. [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/)

| Stage | What happens | What gets recorded |
| --- | --- | --- |
| **Before the PR** | Read the repository rules, define acceptance criteria, implement the change, and run the relevant local checks. Use an independent review pass when available. | Expected behavior, verification commands, and local results. |
| **Open the PR** | Describe the behavior change. Run or inspect required CI checks and start AI review. CI and review can run in parallel. | PR link, current revision, CI results, and findings. |
| **Review and revise** | Verify findings, fix confirmed defects, and review the revised change. Repeat within the review limit. | Finding disposition and evidence from the revised commit. |
| **Human review and merge** | Once required checks pass and blocking findings are resolved, present the review brief. Merge after a human approves and the repository’s merge requirements are met. | The decision, evidence, and risks for the reviewed PR and commit. |
| **After merge** | Record the merge. If release or deployment is in scope, verify the result in the target environment. Use a new fix PR for a regression that requires a code change. | Merge commit, release or deployment status, and target environment results where applicable. |

### AI review and revision

Use an independent reviewer with separate context from the author when that capability is available. The first pass reads the full diff and follows the relevant call paths. Each finding should identify the code location, trigger, impact, and how to verify it. The author checks the evidence, fixes confirmed defects, and documents the reason when a finding does not apply. Subsequent passes focus on the fix and its effects on related code.

The default is **up to three completed AI review rounds per PR**. End the cycle when no blockers remain. If the third review still finds blockers, pause automated fixes, assess why the approach stalled, and propose the next step with the evidence already collected. [PR workflow and AI review guide](references/pr-workflow.md)

### Human review and the merge decision

The review brief starts with the decisions the reviewer needs to make. Show the intended behavior, what changed, and the key code excerpts with a link to the full diff. Include the checks that ran, their results, how AI findings were handled, and the risks the checks leave open.

The reviewer explicitly approves, requests changes, or defers. Record the decision against the PR and reviewed commit. If a later commit changes the basis for the decision, verify and review the affected parts again. The repository’s rules determine who can provide any required platform approval. [Human review and evidence guide](references/human-review.md)

## Repository guide

Start with the project’s existing `AGENTS.md`, `CLAUDE.md`, or other working instructions. Keep project rules in their existing source and link to it from review guidance. If you need a `REVIEW.md`, use the template to define what blocks a merge, what evidence each change needs, and what the reviewer should check. Keep the evidence for each change with its PR and revision. [Project setup guide](references/project-setup.md) · [Review rules template](assets/REVIEW.template.md)

| If you want to… | Start here |
| --- | --- |
| See what the agent reads and how it selects a stage | [SKILL.md](SKILL.md) |
| Design local and CI checks for a real behavior change | [Verification guide](references/verification.md) |
| Track a rollout or investigate a failure after merge | [Delivery and recovery guide](references/delivery-recovery.md) |
| Inspect the progress data or maintain the workflow | [Example progress data](assets/progress.example.json) · [Validation scenarios](references/validation-scenarios.md) |

The skill instructions, templates, and reference guides are mainly in Chinese. To preview the bundled local progress example, run the following from this repository with Python 3 and Node.js 20 or newer.

```sh
python scripts/render_progress.py assets/progress.example.json --output progress-example.html
```

If you change the progress renderer, run its tests with `python -m unittest discover -s scripts`. For changes to the workflow itself, use the scenario guide to check both what the skill does and what it reports. [Validation scenarios](references/validation-scenarios.md)

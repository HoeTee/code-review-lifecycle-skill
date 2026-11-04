# Code Review Lifecycle

[English](#code-review-lifecycle) · [简体中文](#简体中文) · [日本語](#日本語)

**A Codex skill for reviewing and delivering code changes.** Start with acceptance criteria, verify the change locally and in CI, then give a human reviewer the evidence to make a merge decision. Use the full workflow or start with the stage you need.

[Install](#install-and-try-it) · [Example review](#example-review) · [Workflow](#workflow) · [Repository guide](#repository-guide)

The workflow draws on the Claude Code team’s practices for reviewing early, limiting review rounds, and explaining the code a person needs to understand. This skill uses those practices to prepare a final human review tied to a specific PR and commit. [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/)

## Install and try it

Run this from the target project directory with Node.js, `npx`, and Git installed. Add `--global` to install for your user account.

```sh
npx skills add HoeTee/code-review-lifecycle-skill --agent codex
```

In Codex, pick the starting point that matches your task.

- **Review an existing PR.** “Use `$code-review-lifecycle` to review this PR. Show me the findings, checks for the current revision, and decisions I need to make before merge.”
- **Set up a project.** “Use `$code-review-lifecycle` to propose local checks, CI requirements, and review rules for this repository. Start from our existing project instructions.”
- **Investigate a regression.** “Use `$code-review-lifecycle` to compare these logs with the deployed revision and propose a fix and a way to verify it.”

PR and CI actions require repository access and the relevant permissions. Platform guides cover GitHub and Gitee. Default HTML explainers use a separately installed skill. [GitHub guide](references/platforms/github.md) · [Gitee guide](references/platforms/gitee.md) · [HTML renderer installation](https://github.com/QingYunA/answer-me-with-html#install)

## Example review

Suppose a PR changes who can export project data. A user starts an export, then loses access while the job is still queued. This illustrative review shows how a finding becomes evidence for a decision.

| Handoff | What the reviewer sees |
| --- | --- |
| **AI finding** | The request handler checks access, but the queue worker starts the export without checking again. If access is revoked between those steps, the worker can still generate the file. |
| **Fix and verification** | Check access again in the worker. Add a regression test that queues a job, revokes access, runs the worker, and confirms that no file is written. Attach the test result to the revised commit. |
| **Human decision** | The review brief shows the request handler, worker, and regression result alongside the full diff. The reviewer decides whether `Export unavailable` gives users enough information when access is revoked. |

## Workflow

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
| See what Codex reads and how it selects a stage | [SKILL.md](SKILL.md) |
| Design local and CI checks for a real behavior change | [Verification guide](references/verification.md) |
| Track a rollout or investigate a failure after merge | [Delivery and recovery guide](references/delivery-recovery.md) |
| Inspect the progress data or maintain the workflow | [Example progress data](assets/progress.example.json) · [Validation scenarios](references/validation-scenarios.md) |

The skill instructions, templates, and reference guides are mainly in Chinese. To preview the bundled local progress example, run the following from this repository with Python 3 and the HTML renderer installed.

```sh
python scripts/render_progress.py assets/progress.example.json --output progress-example.html
```

If you change the progress renderer, run its tests with `python -m unittest discover -s scripts`. For changes to the workflow itself, use the scenario guide to check both what the skill does and what it reports. [Validation scenarios](references/validation-scenarios.md)

## 简体中文

这是一个面向 Codex 的代码审查与交付 skill。流程从明确验收标准和本地验证开始，经过 PR、CI、AI 审查和返修，再由人审核当前版本。合并后按任务要求交付，并在目标环境验收。它参考了 Claude Code 团队的早期审查、审查轮次上限和关键代码解释做法。 [Claude Code 团队的代码审查实践](https://claude.dev/blog/solving-code-review-at-anthropic/)

- **AI 审查**检查 diff 和相关调用链，给出问题位置、触发条件、影响和验证办法。作者核实并修复，审查者复核。默认每个 PR 最多三轮。第三轮仍有阻断项时，暂停自动返修，说明原因并提出下一步。 [AI 审查流程](references/pr-workflow.md)
- **人工审核**看行为变化、关键代码、完整 diff、实际检查结果和剩余风险。审核人明确选择通过、要求修改或暂缓，结论绑定对应 PR 和提交。 [人工审核材料](references/human-review.md)

例如，AI 发现导出任务在排队后没有重新检查权限。作者修复后用回归测试确认权限撤回时不会生成文件。人再根据实际行为决定，现有的提示语是否足够清楚。 [查看示例](#example-review)

按上方命令安装后，可以在 Codex 中说“用 `$code-review-lifecycle` 审查这个 PR，告诉我当前提交验证了什么，还有哪些事项需要我在合并前决定。”默认 HTML 说明页需要单独安装渲染 skill。 [安装与试用](#install-and-try-it) · [HTML 渲染器](https://github.com/QingYunA/answer-me-with-html#install)

## 日本語

Codex 向けのコードレビューとリリースを支援するスキルです。受け入れ条件の明確化とローカル検証から始め、PR の CI、AI レビュー、修正と再確認へ進みます。人が対象の変更をレビューしてからマージし、必要に応じて対象環境で動作を確認します。Claude Code チームの早期レビュー、レビュー回数の上限、重要なコードの解説を参考にしています。 [Claude Code チームのコードレビュー](https://claude.dev/blog/solving-code-review-at-anthropic/)

- **AI レビュー**では差分と関連する呼び出し経路を調べ、問題箇所、発生条件、影響、確認方法を示します。作成者が指摘を確認して修正し、レビュー担当が再確認します。既定では PR ごとに最大 3 回です。3 回目でもマージを妨げる問題が残る場合は、自動修正を止め、原因と次の対応案を示します。 [AI レビューの手順](references/pr-workflow.md)
- **人によるレビュー**では、動作の変更点、重要なコード、差分全体、実際の検証結果、残るリスクを確認します。承認、修正依頼、保留の判断を対象の PR とコミットにひも付けます。 [人によるレビューの資料](references/human-review.md)

たとえば、待機中のエクスポート処理が実行時にアクセス権を再確認しない問題を AI が指摘します。修正後は、権限が取り消された場合にファイルが生成されないことをテストします。利用者に表示するメッセージが十分に分かりやすいかは、人が判断します。 [レビュー例](#example-review)

インストール後、Codex で「`$code-review-lifecycle` でこの PR をレビューし、現在のコミットの検証結果とマージ前に判断すべき点を示してください」と依頼します。既定の HTML 解説には別途レンダラーが必要です。スキル本体と参照資料は主に中国語です。 [インストールと使い方](#install-and-try-it) · [HTML レンダラー](https://github.com/QingYunA/answer-me-with-html#install)

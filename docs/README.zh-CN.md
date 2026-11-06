<div align="center">

[English](../README.md) · **简体中文** · [日本語](README.ja.md)

# Code Review Lifecycle

**从本地改动到人工合并决定，让 AI 审查、返修和验证连成一条流程。**

Codex、Claude Code 和 OpenCode 共用一份 Agent Skill。

[![CI](https://github.com/HoeTee/code-review-lifecycle-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/HoeTee/code-review-lifecycle-skill/actions/workflows/ci.yml)
[![Agent Skill](https://img.shields.io/badge/Agent_Skill-Codex%20%C2%B7%20Claude%20Code%20%C2%B7%20OpenCode-5c4ee5?style=flat-square)](../references/agent-support.md)
[![MIT license](https://img.shields.io/badge/license-MIT-f4c430?style=flat-square)](../LICENSE)

[快速开始](#安装与试用) · [审查流程](#审查流程) · [能力](#能做什么) · [示例](#示例) · [常见问题](#常见问题) · [资料](#进一步了解)

<code>npx skills add HoeTee/code-review-lifecycle-skill</code>

</div>

<p align="center">
  <img src="media/review-lifecycle-hero.webp" width="860" alt="代码差异、验证证据和人工审核决定连成一条审查流程。">
</p>

让 coding agent 审查一次改动。它先读取仓库规则，识别本地改动或已有 PR，再检查受影响的代码和行为。AI 阶段在本次范围内修复已确认缺陷，完成验证与复审，最后交给人检查。

人工审核者看到关键代码、实际检查结果、剩余风险和明确的待决定项。每份证据都对应它实际检查的 PR 和提交。

## 安装与试用

在项目目录运行：

```sh
npx skills add HoeTee/code-review-lifecycle-skill --agent codex claude-code opencode
```

需要 Git 和 Node.js 22.20 或更新版本，以满足 [skills 安装器](https://www.npmjs.com/package/skills) 要求。`--agent` 后只保留使用的 Agent。添加 `--global` 可安装到用户范围。

### 发起一次审查

```text
使用 code-review-lifecycle skill，做下 code review。
```

| Agent | 如何开始 |
| --- | --- |
| Codex | 调用 `$code-review-lifecycle`。 |
| Claude Code | 输入 `/code-review-lifecycle`，随后写明请求。 |
| OpenCode | 请它加载 `code-review-lifecycle` skill，再说明任务。 |

可以从本地改动、已有 PR 或返修后的提交开始。Agent 自动确定待审对象与比较基线。PR 和 CI 操作沿用现有仓库权限。[Agent 接入与要求](../references/agent-support.md)

## 审查流程

![整个 Skill 的工作流：可信规则与固定范围，AI 审查、修复、验证和复审循环，当前 PR 与 CI，最后由人检查并交接合并。](media/review-workflow.png)

*使用 Answer me with HTML 单独生成的工作流介绍图。[查看完整尺寸](media/review-workflow.svg) · [下载并本地打开 HTML 介绍页](showcase/review-workflow.html) · [内容源稿](showcase/review-workflow.md)。*

1. **确定审查范围。** 读取可信仓库规则，固定范围与版本。
2. **由 AI 审查并修复。** AI 审查代码、修复范围内已确认缺陷、验证并复审。本地和 PR 审查默认合计最多三轮，常规修复不逐项等待人工批准。
3. **最后由人检查。** 必需检查通过、阻断清除后，展示关键代码、发现、证据、风险和待判断项。人针对该版本选择通过、要求修改或暂缓。

明确要求只读时只交报告、不修改。本地任务可在交付本地修复与报告后结束。提交、推送、PR 写入和合并需要对应授权。CI 和 AI 结果不能代替最终人工批准。

[审查范围与规则](../references/review-target.md) · [审查与返修](../references/pr-workflow.md) · [人工审核](../references/human-review.md)

流程参考 Claude Code 团队的早期审查、有限轮次和关键代码解释做法。[Claude Code 团队的代码审查实践](https://claude.dev/blog/solving-code-review-at-anthropic/)

## 能做什么

| 能力 | 你能获得什么 |
| --- | --- |
| 自动确定审查范围 | 本地候选或已有 PR、确认的基线，以及纳入审查的相关新文件。 |
| 调用链与影响分析 | 输入、共享接口、状态变化、下游消费方和失败传播的检查结果。 |
| 独立 AI 审查 | 能力可用时，由独立上下文核实发现，写明触发条件、后果和证据。 |
| 按行为选择验证 | 相关单元、接口、集成、端到端、构建和真实任务检查，以及实际结果与限制。 |
| 返修后复审 | 对照新版本核对原发现、相关影响和仍有效的证据。 |
| PR 与 CI 证据 | 对应当前受审提交及实际修复的检查结果和讨论状态。 |
| 面向人的代码解释 | 为什么改、哪些代码影响判断、哪些问题需要人决定。 |
| 审查进度 | 可复用的 HTML 报告，记录版本、阶段、证据、卡点和下一步。 |

产品界面可按要求截图验证。生成的说明页和审查报告核对内容与链接，不做截图验收。

## 工具 CLI 与 token 记录

Agent 使用共用 Node.js CLI 收集 Git 证据、执行明确检查、增量记录状态并生成报告。CLI 不调用模型，也不判断缺陷是否成立。

| 命令 | 作用 |
|---|---|
| `prepare` | 固定候选，保存差异、新文件和可信规则证据。 |
| `verify` | 执行明确检查计划，保存实际结果。 |
| `record` / `status` | 记录发现、轮次、必需检查及版本对应关系。 |
| `report` / `stats` | 渲染已有记录，查看 token 用量。 |

可导入宿主实际提供的输入、输出和缓存 token，按请求 ID 去重。没有实际用量时显示未知。CLI stdout 粗略估算单列，不代表模型推理量或已测节省率。[CLI 与用量格式](../references/cli.md)

## 示例

### 导出任务等待执行时，用户权限被撤回

用户提交 CSV 导出后，在 Worker 执行前失去访问权限。审查者沿请求追到 Worker，发现它仍能生成文件。

Agent 补上执行时的权限检查和回归测试。复审确认权限撤回后不会生成文件，并核对对应提交的 CI。最后由人判断 `Export unavailable` 是否解释清楚了结果。

![虚构 PR 42、提交 a1b2c3d 的 HTML 审核报告示例，展示已处理的 AI 发现和待完成的人工决定。](media/export-review-preview.png)

*这是虚构案例。[查看示例材料](showcase/export-review.md)。*

<details>
<summary><strong>在本地生成示例页面</strong></summary>

在本仓库的克隆目录运行：

```sh
node scripts/render_html.mjs render docs/showcase/export-review.md -o export-review.html --no-open
```

</details>

## 常见问题

<details>
<summary><strong>安装后会自动开始审查吗？</strong></summary>

需要向 coding agent 发起请求。随包内容包括指令、参考资料、模板和报告渲染器。无人值守的审查需要另行配置触发器和 Agent 执行入口。

</details>

<details>
<summary><strong>需要再配置模型或审查服务吗？</strong></summary>

使用当前 coding agent 的工具与审查能力。独立审查需要与作者分开的上下文。能力不可用时，如实报告限制，并区分作者自检与独立审查。

</details>

<details>
<summary><strong>会修改代码或推送 GitHub 吗？</strong></summary>

默认流程包含本次范围内已确认缺陷的本地修复、验证与复审。明确要求只读时不修改。提交、推送、PR 更新和合并需要对应授权及仓库权限。

</details>

<details>
<summary><strong>CI 通过就等于人工批准吗？</strong></summary>

CI、AI 审查和人工决定分别记录。必需检查需要通过，平台要求的人工审批由有资格的人完成。结论只适用于已审核版本。

</details>

<details>
<summary><strong>在哪里运行，需要哪些工具？</strong></summary>

Skill 由 coding agent 使用现有工具执行。Git 用于识别改动，远端 PR 和 CI 需要平台认证。随包 HTML 渲染器需要 Node.js 20 或更新版本，上述安装环境也能运行。渲染进度快照另需 Python 3。

Skill 正文和参考资料主要为中文。README 提供英文、中文和日文版。

</details>

## 进一步了解

| 资料 | 用途 |
| --- | --- |
| [SKILL.md](../SKILL.md) 与 [Agent 支持](../references/agent-support.md) | 共享入口、调用方式与宿主要求。 |
| [审查范围与规则](../references/review-target.md) 与 [审核模板](../assets/REVIEW.template.md) | 怎样选取 diff、应用仓库规则。 |
| [审查与返修](../references/pr-workflow.md) 与 [人工审核](../references/human-review.md) | 跟进发现、修复、复审和人工决定。 |
| [验证方法](../references/verification.md) | 从行为变化与影响选择检查。 |
| [进度报告](../references/progress-interaction.md) 与 [证据复用](../references/execution-efficiency.md) | 跟踪审查，保留仍有效的证据。 |
| [GitHub](../references/platforms/github.md) 与 [Gitee](../references/platforms/gitee.md) | 接入平台并核对 PR 和 CI。 |
| [进度样例](../assets/progress.example.json) 与 [验证场景](../references/validation-scenarios.md) | 试跑快照或检查 Skill 修改。 |

<details>
<summary><strong>渲染进度样例或运行检查</strong></summary>

在本仓库的克隆目录运行：

```sh
python scripts/render_progress.py assets/progress.example.json --output progress-example.html
python -B -m unittest discover -s scripts -v
```

GitHub Actions 对 PR 和推送到 `main` 的提交运行同一组测试，检查进度证据、HTML 渲染、面板更新和随包渲染器完整性。

</details>

## 反馈与贡献

发现漏检、误报或指令不清楚？可以[提交 Issue](https://github.com/HoeTee/code-review-lifecycle-skill/issues)，附上所用 Agent、受审版本、请求，以及最小复现或预期结果。

指令、示例、测试和翻译的改进可以通过 [PR](https://github.com/HoeTee/code-review-lifecycle-skill/pulls) 提交。

## 许可证

项目自身的工作采用 [MIT License](../LICENSE)。

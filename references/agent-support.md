# Agent 支持

三个 Agent 加载同一个 `SKILL.md`，共用审查规则、参考资料和渲染器。`agents/openai.yaml` 是 Codex 的展示配置。

| Agent | 调用方式 |
| --- | --- |
| Codex | 在提示中调用 `$code-review-lifecycle`。 |
| Claude Code | 输入 `/code-review-lifecycle`，随后写明任务。 |
| OpenCode | 在提示中请它加载 `code-review-lifecycle` skill，再写明任务。 |

例如，说「做下 code review」。Agent 按 [审查对象与规则](review-target.md) 识别待审版本。安装命令见 [README](../README.md#install-and-try-it)。

- PR 和 CI 访问需要本环境具备对应平台的认证与权限。复用可用的连接器或 CLI，按 [PR 流程](pr-workflow.md)记录实际能力。
- 独立 AI 审查需要与作者分开的审查上下文。没有独立能力时，说明缺项并保留已执行的验证结果。
- HTML 使用随包的 `scripts/render_html.mjs`。使用当前加载的 `SKILL.md` 所在目录定位脚本。HTML 需要 Node.js 20 或更新版本，进度状态脚本另需 Python 3。
- 审查范围和人工审核规则见 [人工审核](human-review.md)。

[Agent Skills 规范](https://agentskills.io/specification) · [Claude Code Skills](https://code.claude.com/docs/en/skills) · [OpenCode Skills](https://opencode.ai/docs/skills/)

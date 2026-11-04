# Code Review Lifecycle

[English](../README.md) · 简体中文 · [日本語](README.ja.md)

**面向 Codex 的 PR 审查与交付 skill。**

AI 找出问题并复核修复。审核人拿到一份简明说明，能看到改动了什么、跑过哪些检查、还需要决定什么。可以从已有 PR 开始，也可以从验收标准、本地验证一路走到合并和交付。

流程参考了 Claude Code 团队的早期审查、审查轮次上限和关键代码解释做法。 [Claude Code 团队的代码审查实践](https://claude.dev/blog/solving-code-review-at-anthropic/)

## 安装与试用

安装后，可以在 Codex 中说“用 `$code-review-lifecycle` 审查这个 PR，告诉我当前提交验证了什么，还有哪些事项需要我在合并前决定。”默认 HTML 说明页需要单独安装渲染 skill。 [安装与试用](../README.md#install-and-try-it) · [HTML 渲染器](https://github.com/QingYunA/answer-me-with-html#install)

## 审查流程

- **AI 审查**检查 diff 和相关调用链，给出问题位置、触发条件、影响和验证办法。作者核实并修复，审查者复核。默认每个 PR 最多三轮。第三轮仍有阻断项时，暂停自动返修，说明原因并提出下一步。 [AI 审查流程](../references/pr-workflow.md)
- **人工审核**看行为变化、关键代码、完整 diff、实际检查结果和剩余风险。审核人明确选择通过、要求修改或暂缓，结论绑定对应 PR 和提交。 [人工审核材料](../references/human-review.md)

## 示例

例如，AI 发现导出任务在排队后没有重新检查权限。作者修复后用回归测试确认权限撤回时不会生成文件。人再根据实际行为决定，现有的提示语是否足够清楚。 [查看示例](../README.md#example-review)

---
name: code-review-lifecycle
description: 审查当前仓库的代码改动、分支或已有 PR，自动确定范围与基线，修复已确认问题并验证、复审，最后准备人工检查材料。明确只读时仅交付审查结果。
---

# Code Review Lifecycle

Codex、Claude Code 和 OpenCode 共用此入口。用户只需说「做下 code review」。Agent 自己定位仓库、取得待审改动并说明证据。调用与权限见 [Agent 支持](references/agent-support.md)。

## 确定性工具入口

固定操作使用 `node /ABSOLUTE/SKILL/scripts/crl.mjs`，每个命令只承担一个明确职责：prepare 固定审查材料，verify 执行指定检查，record 保存结论，render 生成页面，validate 检查已有页面。CLI 不调用模型，Agent 继续负责读规则、查代码、判断与修复。

先读取 prepare 返回的 `next` 与 `review_input`，正常使用不读 CLI 源码、整份状态或格式参考。单个已有检查直接用 `verify --state TASK [--env KEY=VALUE] [--timeout-ms N] [--result JSON] -- EXE ARGS`，工具保存计划，后续 verify 复用。`--result` 读取明确指定的根 run/failures/errors/skipped 字段；多检查或自定义结果结构才读 [CLI](references/cli.md) 并用 --plan。工具不猜测试命令，没有可靠计数时保留未知。

模板只填简短结论、实际独立性、发现和必要解释。每条发现只需 priority、title、location、trigger、impact、evidence；ID、open 状态及 P0/P1 阻断默认由工具补入，其他状态和项目要求的 P2 阻断须明确提供。代码片段可给路径和行号，record 自动提取。版本、命令、计数和链接不在 summary 重抄。

审查完成后分别调用 `record --file REVIEW_INPUT`、`render --output HTML`、`validate --output HTML`。这三个固定动作在一次宿主工具调用里依次执行，检查退出码，失败即停；不要每个动作都额外发起一轮模型响应。validate 只检查，不重新渲染或运行测试。正常流程不另写整理和页面检查脚本。status、stats 按当前调查或用量需求调用；finish/report 仅兼容已有调用，不再作为默认入口。

控制进入模型的内容：先定位函数和消费者，再按范围读取；可信规则和首轮完整 diff 仍须完整读取。大文件分段阅读并记录已读范围，不先输出整文件、截断后再重新输出。长日志先读结果摘要，失败时只补相关段落。没有同任务实测，不宣称节省率。

## 默认流程

1. 定位当前任务的仓库和规则来源。审查前先读取适用的 `CLAUDE.md` 和 `REVIEW.md`，并遵守宿主已加载的仓库指令。PR 的审核规则从目标分支或可信默认分支读取。按 [审查对象与规则](references/review-target.md) 取得可信规则；缺少根规则文件时按 [规则草案](references/review-rules.md) 调查、给完整草案并请用户确认，确认前不擅自写入。可确认的独立审查继续进行。
2. 根据任务关联的 PR、本地改动和已提交的分支差异自动选定审查对象。锁定版本与基线，再分析 diff。工作区干净也要检查已提交的分支改动。有可确认的范围就先审。
3. 读取 `prepare` 保存的完整适用规则、首轮完整 diff、变更意图和受影响调用链，使用独立审查方法核实发现。根据 [验证方法](references/verification.md) 选择明确检查命令，由 `verify` 执行，现有连接器取得的 CI 结果通过 `record` 保存；区分已执行、导入、静态核对和待验证。
4. 按 [发现分级](references/human-review.md#发现分级与排序) 先给 P0/P1/P2 未解决数量及关键影响，再按级别排序。每项写明级别、是否阻断、文件与行号、触发条件、实际后果和依据。没有需修复项时直说，并说明验证范围。
5. AI 阶段包含审查、修复、验证和复审。主 Agent 修复范围内已确认问题，不逐条请求人工批准；明确只读时只报告。每次实际完成审查后用 record 保存该轮；返修前先保存，再验证新候选和复审，不到最后才计轮。交付时用 render、validate 生成和检查报告。按 [人工审核](references/human-review.md) 把结论、关键解释、风险与待决定项交给人最后检查。仍有阻断时给问题报告，不请求最终合并批准。

顺序为：读取可信规则 → 锁定范围与版本 → 按缺项准备规则草案并请用户确认 → AI 审查、修复、验证与复审 → 核对必需检查 → 人工最终检查。缺失草案的确认不妨碍已有可信要求下的独立审查。

## 内置方法按条件读取

本包只有 `SKILL.md` 是 Skill 入口。`references/methods/*.md` 是普通参考文件，不靠各自的 description 自动触发，也不要求安装同名 Skill。先按下表选择，再读取对应全文；不要一次加载全部方法。

| 当前需要 | 读取的方法 | 交回当前步骤的结果 |
|---|---|---|
| 当前入口、调用链或架构事实不清楚 | [实现解释](references/methods/how.md) | 有源码依据的模块、接口及状态归属 |
| 设计理由或历史约束影响判断 | [设计依据](references/methods/why.md) | 已确认依据、推断与未知项 |
| 共享接口、状态、配置或产物的消费者受影响 | [变更影响核对](references/methods/blast-radius.md) | 下游风险与关键前提的核实结果 |
| 首轮 AI 审查或返修复审 | [独立审查](references/methods/adversarial-review.md) | 已核实发现、疑点与证据 |
| 准备规则草案、PR 说明或人审报告 | [技术表达](references/methods/technical-writing.md) | 读者能据此判断的材料 |
| 上述文字存在含糊、重复或空话 | [表达校准](references/methods/unslop.md) | 保留条件、证据和未知项的清楚表述 |

项目的可信 `CLAUDE.md`、`REVIEW.md` 提供契约与通过条件，方法提供调查和检查办法。方法不得自行修改契约、放宽必需检查或扩大授权；具体冲突按 [规则核对](references/review-target.md#先读取仓库规则) 处理。整理架构事实不调用完整 `architect` 设计流程。方法完成后回到原步骤，不另起生命周期。

## 审查与复审

- 启动本流程，包括只说「做下 code review」，默认包含本次范围内已确认缺陷的本地修复、验证与复审，无需逐条或逐轮批准。明确只读、仅报告或仅方案时不修改。提交、推送、评论及合并沿用各自授权，不由本地修复自动授予。流程与轮次记录见 [PR 与复审](references/pr-workflow.md)。
- 主 Agent 负责 AI 阶段的修复与验证，独立审查角色只读固定受审版本，两者区分上下文。有独立审查能力时使用；缺项时如实标记，作者自检不计为独立审查。
- 审查使用内置的 [独立审查方法](references/methods/adversarial-review.md)；共享接口、状态或产物变化时结合 [变更影响核对](references/methods/blast-radius.md)。方法沿用已确定的规则、范围、版本、授权和必需检查，不另选最后一次提交或另起返修循环。技术审查结果不代替人工决定。
- 同一组待审改动的任务默认最多三轮 AI 审查，本地审查计数随任务继承到 PR。阻断项清除就结束。第三轮仍有阻断项时停止自动返修，说明原因、可行方案和待决定事项。创建 PR、切换方法或恢复会话不重置计数。
- 复审比较上一次受审版本与新版本，核对原发现及相关影响。基线或影响范围改变时，重新核对完整 diff。必需检查未通过或证据不足时，记录阻断原因。
- 人工意见记录实际结论。平台要求人类审批时，由有资格的人在平台完成。聊天确认和 AI 结果各自标明来源。

## 聊天与 HTML

每次实质性答复同时给聊天正文和 HTML 页面。正文说明受审对象、主要发现、已验证与未验证范围、待决定事项及下一步。普通工具旁白无需生成页面。用户明确要求其他呈现时按该次要求。

HTML 使用随包的 `scripts/render_html.mjs`，需要 Node.js 20 或更新版本。默认浅色图纸。任务更新沿用固定入口。缺少运行环境或渲染失败时，说明缺项并继续给出聊天结果。命令、状态格式和交互见 [进度与交互](references/progress-interaction.md)。

截图和视觉验收用于被审查产品的界面。`answer-me-with-html` 生成的说明页、进度页和审查报告不做截图或视觉验收，按 [页面检查规则](references/progress-interaction.md#核对页面) 核对生成结果。

维护此 skill 时使用 [验证场景](references/validation-scenarios.md) 核对范围选择、规则来源、复审与证据。

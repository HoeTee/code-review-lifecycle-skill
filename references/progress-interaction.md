# 审查进度与交互

实质性答复提供聊天结果和 HTML。聊天先说明受审范围、主要发现、已验证与未验证范围、阻断项和用户待决定事项。普通工具旁白不逐条生成页面。

同一任务复用一个进度入口。需要持续跟踪的审查记录目标、受审版本、当前动作、检查证据、时间和下一步。没有用户待办时直接说明。技术复盘、最终人工审核和缺少必要信息要分别标记。

有 PR 时列出当前 head、CI、独立 AI 审查、人审和实际平台状态。本地候选与远端 PR 分开标记。证据时间保留实际检查时间。新提交影响结论时更新受审版本与受影响证据。

## 生成页面

说明页从 Markdown 草稿生成。需要 Node.js 20 或更新版本。以下脚本路径以已加载的 `SKILL.md` 目录为准。

```sh
node /ABSOLUTE/SKILL/scripts/render_html.mjs render /ABSOLUTE/draft.md -o /ABSOLUTE/page.html --no-open
```

HTML 说明页统一使用随包入口，无需另装页面 skill。默认 sheet / blueprint / light；header、字体字号、表格和自动布局沿用随包原版，只隐藏工具栏。只输出 HTML。页首字段、组件选择和署名示例见 [HTML 内容模型](html-explainer.md)。

用同一入口的 `help format` 查草稿格式，`list` 列组件。已有页面只改一个面板时看 `help patch`；patch 继续隐藏工具栏并保留自定义署名。任务快照用随包脚本渲染：

```sh
python /ABSOLUTE/SKILL/scripts/render_progress.py /ABSOLUTE/task.progress.json --output /ABSOLUTE/task.html
```

新快照的目标模式为 `review`，阶段为 `prepare`、`review`、`human_review`。见 [状态样例](../assets/progress.example.json)。脚本兼容已有快照。记录文本证据用 `evidence`，链接另用 `evidence_href`。

默认渲染器为随包入口，仍接受既有的 `presentation.renderer: answer-me-with-html` 状态值。默认署名包含 code-review-lifecycle-skill 和 Star on GitHub，均链接本项目；`presentation.footer` 可指定整行文字，空字符串隐藏署名。显式选择 `presentation.renderer: native` 时使用旧内置模板；其外观不适用本说明。既有 `presentation.am_cli` 可继续指定自定义入口，自定义入口需自行支持所用参数。工具缺失或渲染失败时，报告缺项并保留聊天结果。

## 核对页面

首屏回答当前阶段、版本、是否需要人行动和下一步。证据可展开。页面是静态快照，复制指令和查看证据分别标明。按钮与平台动作仅在实际接通时关联。

`answer-me-with-html` 生成的说明页、进度页和审查报告不启动浏览器截图或视觉验收。检查渲染命令退出状态、HTML 文件生成、关键正文、证据、版本和链接目标即可，更新面板后同样检查这些内容。

截图范围按页面用途判断。被审查产品的网页、桌面应用或其他界面可按项目要求截图，即使产品本身使用 HTML。产品截图可以作为证据链接或插图放进报告。

正例：验证产品页面上的权限提示并保存截图，再生成审查报告，检查报告中的文字与证据链接。
反例：把生成的审查报告当成产品页面截图验收，或因报告免截图而跳过实际产品的视觉检查。

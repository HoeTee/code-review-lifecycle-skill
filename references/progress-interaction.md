# 审查进度与交互

实质性答复提供聊天结果和 HTML。聊天先说明受审范围、主要发现、已验证与未验证范围、阻断项和用户待决定事项。普通工具旁白不逐条生成页面。

同一任务复用一个进度入口。需要持续跟踪的审查记录目标、受审版本、当前动作、检查证据、时间和下一步。没有用户待办时直接说明。技术复盘、最终人工审核和缺少必要信息要分别标记。

有 PR 时列出当前 head、CI、独立 AI 审查、人审和实际平台状态。本地候选与远端 PR 分开标记。证据时间保留实际检查时间。新提交影响结论时更新受审版本与受影响证据。

## 生成页面

说明页从 Markdown 草稿生成。需要 Node.js 20 或更新版本。以下脚本路径以已加载的 `SKILL.md` 目录为准。

```sh
node /ABSOLUTE/SKILL/scripts/render_html.mjs render /ABSOLUTE/draft.md -o /ABSOLUTE/page.html --no-open --theme blueprint --mode light
```

用同一入口的 `help format` 查草稿格式。已有页面只改一个面板时看 `help patch`。任务快照用随包脚本渲染：

```sh
python /ABSOLUTE/SKILL/scripts/render_progress.py /ABSOLUTE/task.progress.json --output /ABSOLUTE/task.html
```

新快照的目标模式为 `review`，阶段为 `prepare`、`review`、`human_review`。见 [状态样例](../assets/progress.example.json)。脚本兼容已有快照。记录文本证据用 `evidence`，链接另用 `evidence_href`。

默认渲染器是随包的 Answer me with HTML，默认主题为浅色图纸。显式选择 `presentation.renderer: native` 时使用内置模板。既有 `presentation.am_cli` 可继续指定自定义入口。工具缺失或渲染失败时，报告缺项并保留聊天结果。

## 核对页面

首屏回答当前阶段、版本、是否需要人行动和下一步。证据可展开。页面是静态快照，复制指令和查看证据分别标明。按钮与平台动作仅在实际接通时关联。

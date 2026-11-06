# 确定性工具 CLI 与 token 记录

多检查、自定义结果结构、外部记录或恢复任务时读取本节。正常单检查使用 prepare 的 next，无需先读本节。CLI 不调用模型，不配置模型 API，也不判断代码缺陷是否成立。Agent 读取可信规则、理解代码并修复问题；CLI 执行取证、显式检查、结构校验、状态记录和渲染。

## 入口与任务文件

需要 Node.js 20 或更新版本及 Git，不新增 npm 依赖。`scripts/crl.mjs` 以当前加载的 Skill 目录定位。所有命令默认返回 JSON，`--pretty` 仅改变缩进。

```sh
node /ABSOLUTE/SKILL/scripts/crl.mjs prepare --repo /ABSOLUTE/REPO --state /ABSOLUTE/task.json --base CONFIRMED_BASE
node /ABSOLUTE/SKILL/scripts/crl.mjs verify --state /ABSOLUTE/task.json -- python -m unittest
node /ABSOLUTE/SKILL/scripts/crl.mjs record --state /ABSOLUTE/task.json --file /ABSOLUTE/task.json.review.json
node /ABSOLUTE/SKILL/scripts/crl.mjs render --state /ABSOLUTE/task.json --output /ABSOLUTE/task.html
node /ABSOLUTE/SKILL/scripts/crl.mjs validate --state /ABSOLUTE/task.json --output /ABSOLUTE/task.html
```

上面的路径与基线由 Agent 根据当前任务填写，用户无需提供这些技术参数。任务文件放在已约定的产物目录，位于工作树之外或 Git 忽略目录。状态、证据和页面分别存放；不写到源码文件。一个任务复用同一状态文件，多个任务分开保存。

每条命令对应独立动作，不因保存记录而运行测试，不因检查页面而重新生成页面。record、render、validate 的固定依赖在一次宿主调用内依次执行，失败即停；不逐项回到模型决定固定的下一步。CLI 只更新自己的状态和证据。verify 的命令由 Agent 根据项目规则明确提供，仍须符合任务和宿主权限。CLI 不是沙箱。提交、推送、评论与合并沿用原授权。

## prepare：固定版本与规则证据

Agent 先识别用户明确关联的 PR、本地候选和可信比较基线，不能用 CLI 代替用户意图判断。

- 本地任务用 `--base` 传入已确认基线；可选 `--rules-ref` 指定已确认的可信规则提交。未提供时尝试本地 `origin/HEAD`；不能确认默认分支则只取本地 HEAD 范围并标明 `base_confirmed: false`，Agent 补取基线。
- PR 任务通过 `--pr-file` 接收现有连接器或 CLI 返回的 `number`、`url`、`head_sha`、`base_sha`。CLI 不另建平台接入；初次准备必须是固定 PR head 上的干净工作树，不匹配时由 Agent 准备隔离工作树。
- 记录暂存、未暂存、已提交差异和未跟踪文件，保存完整 tracked diff 及相关新文件快照。大于 1 MiB 的新文件只记录路径、大小和哈希，Agent 继续按实际类型检查。符号链接不跟随。
- 从同一可信提交提取根规则、受影响目录规则和可识别的 `@path` 引用。保留完整原文；未识别语法、外部引用、规则冲突及文件是否与本次有关，仍由 Agent 核对。
- 缺少根规则按 [规则草案](review-rules.md) 给完整初稿并请用户确认，CLI 不生成或采用规则。

准备结果给出候选 ID、diff、规则与新文件证据位置。Agent 必须读取完整适用规则、首轮完整 diff 和必要调用链，不能把短 JSON 当作已经审查。

同时返回 `review_input` 文件，已填写记录 ID 与候选 ID。直接补充语义内容，保留这些自动字段。空 summary 不能提交；`independent` 默认 false，确有独立上下文才改为 true。刷新未完成候选时保留同版本草稿；prepare 或 verify 捕获新候选后自动生成新稿并归档旧稿，轮次仍沿任务累计。

`next` 返回正常命令的最小语法、发现字段和默认值。正常调用只需这些信息，不为寻找工具而读取源码或整份状态。

`prepare --refresh` 更新同一任务的候选，保留审查历史和轮次；不得通过另建任务清零。本地修复后 `verify` 也会在原任务分支上捕获新候选，旧审查与旧检查不自动变为新版本证据。新基线、PR 元数据和规则来源的调整必须有对应事实或用户确认，不能借此降低规则。

本地任务创建 PR 后，`prepare --refresh --pr-file ...` 关联该 PR；需匹配当前干净候选，不换任务或清零。取得新的可信基线或已确认的规则提交时，可在同一 refresh 中传入 `--base` 或 `--rules-ref`。规则身份参与候选 ID，受影响证据重新核对。

已经使用手工计数的进行中任务继续沿用原记录，本轮不要为了换工具重新计数。新任务使用 CLI 后持续复用状态文件。

## verify：执行明确的检查计划

一个已有检查不需要先写计划文件：

```sh
node /ABSOLUTE/SKILL/scripts/crl.mjs verify --state /ABSOLUTE/task.json --env PYTHONDONTWRITEBYTECODE=1 --timeout-ms 600000 --result data/results.json -- python scripts/check.py
```

这是接口示例，命令与路径由当前项目的真实入口替换。`--` 之后是原样 argv；不使用隐式 shell。重复 --env 接收多个明确变量；重复 --result 接收多个结果。每个指定 JSON 必须提供根 run/failures/errors/skipped，且本轮有更新；不会猜其他结构或日志内容。没有结果文件时省略 --result，计数保持未知。默认检查名为 project-check；需要分别保留不同检查时显式使用 --check-name。后续只调用 verify 复用已保存命令。

多检查或自定义 JSON 结构才使用 `--plan`，不能与直接命令或其选项混用。计划格式如下。

计划为 JSON 对象，包含非空 `checks` 数组。每项包括：

| 字段 | 含义 |
|---|---|
| `name` | 此计划中唯一的检查名 |
| `argv` | 非空字符串数组：可执行文件及每个参数 |
| `required` | 是否必需，默认 true |
| `cwd` | 仓库内工作目录，默认根目录 |
| `timeout_ms` | 1 到 3600000，默认 120000 |
| `env` | 可选的明确环境变量字符串映射，直接传给子进程，不需要额外 shell 包装 |
| `results` | 可选结果数组，每项有 path、fields 及可选 required（默认 true） |

命令不经隐式 shell。需要 shell 功能时，计划明确列出 shell 可执行文件及参数。Windows 的 `.cmd` 入口也应通过明确的宿主执行方式调用。CLI 不拼接不可信 shell 字符串。

首次传入明确命令或 --plan；后续 verify 复用保存的计划。选择来自项目必需检查与 Agent 的语义判断，CLI 不会从自然语言生成测试。

每次保存候选 ID、实际命令、退出状态、时间和 stdout/stderr。必需检查失败返回 1；输入或执行准备错误返回 2。检查改变候选内容时标为证据失效，不请求最终批准。CLI 只知道已登记的检查，Agent 还需核对项目和平台的完整要求。

例如，已有 JSON 提供 run、failures、errors、skipped 时，登记 `{"path":"data/results.json","fields":{"run":"/run","failures":"/failures","errors":"/errors","skipped":"/skipped"}}`。fields 使用明确 JSON pointer；后三项可从数组长度计数。工具保存本轮新生成的原始文件快照与计数，不解析自然语言日志或调用模型。路径相对检查 cwd，映射随计划复用，不写入某个项目的业务规则。

必需结果缺失、未更新、格式错误、计数矛盾、无测试或存在失败/错误时，检查失败。命令非零退出不能被 JSON 中的成功计数覆盖。跳过按实际数量报告；项目的必需集成检查仍按原命令与规则执行。未声明或未提供的计数保持未知。

## record、render、validate：独立交付动作

record --file 接收 prepare 的 review_input。Agent 填写 summary、independent、findings 及必要 key_code，不重复抄写版本、命令、测试计数或完整状态。每条发现填写 priority、title、location、trigger、impact、evidence；未给 ID 时按本轮顺序补入，status 默认 open，blocking 对 P0/P1 默认 true、P2 默认 false。项目契约要求阻断的 P2 需显式设置 true，不能用默认值放宽要求。P0/P1 的 open 发现不能显式改成不阻断，accepted_risk 仍需真实决定证据。

`key_code` 可用 `{path,range:[起行,止行],explanation}` 或 `{path,start_line,end_line,explanation}`，range 也接受明确的十进制字符串 `"起行-止行"`。工具统一格式，再从候选提取 1 到 200 行原文；也兼容 location/code/explanation。提取时 range 与起止字段同时提供必须一致，不能猜冲突值。prepare.next 给出示例、字段及上限，不要求 Agent 额外查询格式。原文作为不可执行文本展示。

平台观察或未运行项使用独立的 record check 格式，保持导入来源，不冒充 CLI 执行。

render 只用已保存的证据生成 HTML 和 `.crl.json` 校验清单，不增加审查轮次或运行测试。validate 只核对该 HTML 的哈希、记录身份、候选版本、正文与本地链接，不重渲染或运行测试。清单属于页面产物，不手工编辑。页面、记录或候选变化会拒绝旧验证；记录更新后重新 render，再 validate。检查排除 head、源脚本和明确隐藏的子树，仍不能认证任意 CSS/JS 的最终可见性或业务语义。退出 0 表示当前动作成功；是否可最终人审仍看 ready_for_final_check。

渲染失败只重试 render；校验失败先定位原因，仅页面改变时重渲染，缺失证据先补证据，不重跑无关检查或重记审查。record 的相同输入重试不多计轮。工具不生成缺陷判断或人工批准；返修前保存已完成轮次，沿原三轮上限继续。

## finish：已有调用兼容

finish 保留原先记录、生成和检查的组合行为，report 保留重渲染并检查行为。新任务不以它们为默认入口，不把兼容调用再与独立动作叠加。finish 接收 review_input 及可选 checks，失败重试沿用同一输入，不重置轮次。

## record：增量记录，不代替判断

`--file` 接收以下记录；记录必须有唯一 `id` 和当前 `candidate_id`。相同 ID 的同内容重试不重复计数，异内容拒绝。更新候选前不能把旧结果记到新版本。

| `type` | 必需内容 |
|---|---|
| `review` | `summary`、`independent` 布尔值及 `findings` 数组；仅在一次审查实际完成后记录 |
| `check` | 导入检查的 `name`、`source`、`evidence`、带时区的 `observed_at`、`required` 及 `status`：passed、failed 或 not_run |
| `human` | `decision`：approve、request_changes 或 defer；`actor`、`source`、`evidence` |
| `rules` | 用户已确认但尚未提交的规则：`files` 为仓库内明确文件列表；记录真实 `actor`、`source`、`evidence` |

缺少根规则时先按原流程给草案并咨询。确认后写入获准文件，再 refresh 捕获候选，使用 `rules` 记录冻结已确认的根规则及相关引用文件。它不要求额外提交；以后候选修改这些文件时，审查仍读取已冻结内容。未确认的引用不会自动成为可信规则。既有确认可按原规则复用，Agent 不得因工具提供了这个入口而虚构用户批准。

同名检查依据观察时间选最新结果，不以到达顺序覆盖；同一时间的冲突以失败优先。既有必需检查在任务内持续保留，替换计划不能静默删除。CLI 执行的检查与外部导入检查分开标识，不能用同名本地检查代替平台结果。

每条 finding 包含 `id`、`priority`（P0/P1/P2）、`title`、`location`、`trigger`、`impact`、`evidence`、`status` 及 `blocking`。状态为 open、resolved、not_applicable 或 accepted_risk；接受风险还需真实的 `decision_evidence`。未解决 P0/P1 默认阻断，不把未验证疑点写成确认发现。

需要解释关键代码时，review 可含 `key_code` 数组，每项为 `location`、`language`、`code`、`explanation`。说明与片段来自真实受审代码。CLI 仅转录和渲染，不生成解释。

前三次已完成审查沿任务累积。第三次仍未通过按 [PR 流程](pr-workflow.md) 停止自动返修并交有界复盘；CLI 拒绝自动记录第四次，不自动批准或增加预算。作者自检记录 `independent: false`，不能冒充独立审查。

人审记录必须来自真实用户或平台结论，Agent 不可自行构造“人已批准”。聊天结论不替代平台原生审批。`status` 的 `ready_for_final_check` 只核对已登记的技术条件，不证明所有业务要求已被覆盖。

## token：实际用量与估算分开

参考 [Answer me with HTML 的 benchmark 记录](https://github.com/QingYunA/answer-me-with-html/blob/main/bench/README.md)：保留原始用量来源，区分输入、输出和缓存。这里不复制其样本数字，也不把它的节省比例用于本项目。

```sh
node /ABSOLUTE/SKILL/scripts/crl.mjs record --state /ABSOLUTE/task.json --usage-file /ABSOLUTE/host-usage.json
node /ABSOLUTE/SKILL/scripts/crl.mjs stats --state /ABSOLUTE/task.json
```

用量文件为一个对象或对象数组，由宿主已有用量导出整理，不为了取用量额外调用模型：

| 字段 | 定义 |
|---|---|
| `id` | 唯一请求 ID，或能识别会话与轮次的唯一标识，用于去重 |
| `kind` | 固定 actual；估算不走这个入口 |
| `source`、`provider`、`model` | 原始用量的来源及适用模型；不填凭据或私有接口 |
| `input_tokens` | 此请求的总输入，包含缓存读写部分 |
| `output_tokens` | 此请求的总输出，包含单列的推理部分 |
| `cached_input_tokens` | 可选；总输入中的缓存读取量 |
| `cache_write_input_tokens` | 可选；总输入中的缓存写入量 |
| `reasoning_output_tokens` | 可选；总输出中的推理量 |

所有计数为非负整数。输入输出已包含相应子项，不能再把缓存或推理重复加到总量。宿主若将未缓存输入、缓存读和缓存写分列，先合并为这里的总输入。累计会话快照须先取对应任务的差分，不能逐次相加；没有可靠请求归属时不导入。

Codex 已有的 JSONL 用量记录可直接读取，无需 Agent 重写计数：

```sh
node /ABSOLUTE/SKILL/scripts/crl.mjs record --state /ABSOLUTE/task.json --usage-file /EXPLICIT/HOST/session.jsonl --usage-format codex-jsonl --turn-id EXACT_TURN_ID
```

文件与轮次由宿主提供或按已知会话定位，不扫描用户所有历史。导入器只处理指定轮次的 `token_usage_record.payload.usage`，按响应 ID 去重，忽略 `turn_token_usage`、`thread_token_usage` 等累计快照。不把消息、推理正文、工具输出或会话路径写入统计。未完成的文件尾不作为完整用量。其它宿主继续导入上面的标准格式；没有可靠用量时保留未知。

`stats.model_usage` 只覆盖导入的请求，不声称任务所有用量都已取得。未提供的实际值为 null；缺少的子项保留未知，不补零。

每次工具调用另外记录命令名、退出状态、耗时、CLI stdout 字节数，以及 `ceil(UTF-8 bytes / 4)` 的粗略输出 token 估算。它不含模型推理、工具输入、其它工具或后续解释，也不是任何模型的精确分词或计费记录。遥测不记录命令参数或环境变量。

`stats` 返回此前已完成调用的汇总，本次查询在完成后才进入记录。报告也展示真实用量与估算。没有同任务、同质量的对照样本时，`savings` 为 null，不宣称节省率。

## report 与恢复

正常交付分别使用 record、render、validate，已保存结论只重渲染时从 render 开始，不重记轮次或重跑检查。报告保留版本、P0/P1/P2、命令日志、结果快照、关键片段与人审状态。自动结构检查不能代替语义核对，按 [页面检查](progress-interaction.md#核对页面) 补核内容，不做报告截图。

任务状态采用锁与原子替换。锁冲突时先核对锁中进程和归属；不要自动删除未知执行者的锁。失败记录保留实际状态，重试复用原任务和记录 ID。CLI 不能保证外部工具不改文件，执行前后仍核对候选。

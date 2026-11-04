# GitHub 分支：只在选定 GitHub 后读取

先沿用用户明确指定的操作方式。
已有满足当前任务需要且已验证可用的连接时，直接复用。
采用 CLI 路径时，才检查并准备本机 `git` 和 `gh`。
不把 CLI 二进制放进 skill 或项目仓库。

## 工具与认证

```powershell
git --version
gh --version
```

缺少 Git 时，先按 [Git 安装分支](git.md)选择当前系统的步骤。
仅在缺少 `gh` 且采用 CLI 路径时，执行下面适用的一组安装命令。
已有版本满足任务要求时复用，不主动升级。

### Windows / PowerShell

前置条件：WinGet 可用；没有时按官方页面选对应架构的安装器。

```powershell
winget --version
winget install --id GitHub.cli --source winget
```

安装后打开新的终端窗口，再运行 `gh --version`。
[GitHub CLI 官方 Windows 安装说明](https://github.com/cli/cli/blob/trunk/docs/install_windows.md)

### Linux / shell

先读取 `/etc/os-release`、架构及所需包管理器版本，只执行对应分支。
Debian / Ubuntu：以下步骤使用官方软件源，前提是能使用 sudo 和访问该源。

```sh
sudo apt-get update
sudo apt-get install -y wget ca-certificates
sudo install -d -m 755 /etc/apt/keyrings
task_keyring="$(mktemp)"
wget -nv -O "$task_keyring" https://cli.github.com/packages/githubcli-archive-keyring.gpg
sudo install -m 644 "$task_keyring" /etc/apt/keyrings/githubcli-archive-keyring.gpg
sudo install -d -m 755 /etc/apt/sources.list.d
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt-get update
sudo apt-get install -y gh
```

逐步执行，任何一步失败都停止后续安装并处理原因。
复用该源前核对现有配置；不覆盖用户有意指定的其他来源。

Fedora / RPM，先运行 `dnf --version`。DNF5 分支：

```sh
sudo dnf install dnf5-plugins
sudo dnf config-manager addrepo --from-repofile=https://cli.github.com/packages/rpm/gh-cli.repo
sudo dnf install gh
```

DNF4 分支：

```sh
sudo dnf install 'dnf-command(config-manager)'
sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
sudo dnf install gh
```

其他发行版按 [GitHub CLI 官方 Linux 安装说明](https://github.com/cli/cli/blob/trunk/docs/install_linux.md)补齐。
执行时核对官方源与签名说明，安装后运行 `gh --version`。
本资料提供常用系统分支，不把所有 Linux 发行版当成相同环境。

### 身份与仓库验证

需要登录时执行 `gh auth login --hostname HOST`。
已有登录先执行 `gh auth status --hostname HOST`，不重复登录。
用 `gh repo view HOST/OWNER/REPO` 验证目标仓库访问。
HOST、仓库和目标分支由项目事实确定；GitHub.com 的 HOST 是 github.com。
下文 R 代表已确定的 HOST/OWNER/REPO，NUMBER 等大写占位符执行前替换，不当作默认 main。

版本与认证命令适用于 Windows 和 Linux；占位符按实际平台填写。

## 只执行当前需要的操作

先核对本地仓库与分支，推送属于授权写操作：

```sh
git status --short
git remote -v
git branch --show-current
git rev-parse HEAD
git push -u REMOTE FEATURE_BRANCH
```

查询与审查：

```sh
gh pr view NUMBER --repo R --json number,url,state,baseRefName,baseRefOid,headRefName,headRefOid,reviewDecision,statusCheckRollup
gh pr diff NUMBER --repo R
gh pr checks NUMBER --repo R --required
gh run view RUN_ID --repo R --log-failed
gh pr view NUMBER --repo R --comments
gh api --hostname HOST --paginate repos/OWNER/REPO/pulls/NUMBER/reviews
gh api --hostname HOST --paginate repos/OWNER/REPO/pulls/NUMBER/comments
```

评论列表和 review 不等于线程解决状态。需要线程状态时使用已选连接器，或执行随包只读 GraphQL 查询。
[查询文件](../../assets/github-review-threads.graphql)的绝对路径由当前 skill 位置确定，替换 QUERY_FILE：

```sh
gh api graphql --hostname HOST --paginate -F owner=OWNER -F repo=REPO -F number=NUMBER -F "query=@QUERY_FILE"
```

查询仅取每个线程首条评论用于定位；完整行内意见用上面的分页接口读取。
实例缺少所需能力时说明缺项，不能默认线程全部已处理。
必需检查未设置或结果列表为空，不等于自动满足项目验证清单。
有等待中的任务按任务状态等待或回报，不通过无限重跑消耗轮次。

以下写操作仅在对应任务已授权时执行。多行正文由 Agent 写进 UTF-8 文件，再通过 --body-file 传入，避免 shell 转义错误：

```sh
gh pr create --repo R --base BASE_BRANCH --head FEATURE_BRANCH --title "TITLE" --body-file BODY_FILE
gh pr edit NUMBER --repo R --body-file BODY_FILE
gh pr comment NUMBER --repo R --body-file REVIEW_FILE
```

AI 意见发布为明确标注的技术意见。代记用户验收要标明来源与 commit，不能冒充用户 Approve。
真实有资格的人按平台完成要求的审批；已有分支规则必须满足。
所有门槛与合并授权具备后，再读取当前 head，以实际仓库策略选择 merge、squash 或 rebase。
例如项目选择 squash 时：

```sh
gh pr merge NUMBER --repo R --squash --match-head-commit REVIEWED_HEAD_SHA
gh pr view NUMBER --repo R --json state,mergedAt,mergeCommit
```

不要使用 --admin 绕过门槛，也不要默认删除分支。
进入合并队列等异步路径时回读实际状态，不能因命令返回就宣称已合并。

## 需要配置 CI 时

先复用项目已有 CI。
采用 Actions 时，编辑 `.github/workflows/*.yml`，使用项目已登记检查、依赖和实际命令；在授权范围提交并推送。
不把此 skill 的格式校验或示例脚本测试当成业务 CI。
实际执行成功后核对检查名称与必需状态，另行验证对应分支规则确实生效。
使用已选定的连接器或 `gh` 读取实际运行和失败日志。
只有需要自托管 runner 时，才按其手册准备执行器。
具体测试命令来自项目验证清单，不在本平台手册写死。

官方参考：
- https://github.com/cli/cli/blob/trunk/docs/install_windows.md
- https://cli.github.com/manual/gh_auth_login
- https://cli.github.com/manual/gh_pr
- https://docs.github.com/en/actions/tutorials/build-and-test-code/python

补充参考：[gh api](https://cli.github.com/manual/gh_api)、[PR view](https://cli.github.com/manual/gh_pr_view)、[merge](https://cli.github.com/manual/gh_pr_merge)。

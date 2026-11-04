# Gitee 分支：只在选择 Gitee 后读取

先读用户手册或该实例适用的说明，确定现有连接器、CLI、API 或网页入口。
用户已指定的方式优先，已验证有效的连接复用；不假定必须存在统一官方 Gitee CLI。
代码传输用 Git，缺 Git 时才读 [Git 安装](git.md)。Git 传输和 PR/CI 能力分别验证。

## 可选 Python API 执行器

只有采用兼容 Gitee API v5 的 HTTP 路径时，使用随包 [gitee_api.py](../../scripts/gitee_api.py)。
它使用 Python 标准库；已有连接器或用户 CLI 能完成时不另装 Python。
执行前从当前 SKILL.md 路径确定脚本绝对路径，下文 SCRIPT_FILE、OWNER、REPO、NUMBER、API_BASE 均由实际任务填写。

检查已有 Python，优先复用当前项目兼容解释器。缺少独立工具运行环境才执行安装。
Windows / PowerShell，WinGet 可用时的独立 Python 3.14 示例：

```powershell
winget install --id Python.Python.3.14 -e --source winget
```

安装后打开新终端，运行 python --version。该版本不替代项目声明的运行版本。
Linux / Debian、Ubuntu：

```sh
sudo apt-get update
sudo apt-get install -y python3
python3 --version
```

Fedora / dnf：

```sh
sudo dnf install python3
python3 --version
```

未覆盖环境按其 Python 手册补齐。Linux 下将后续 python 换为已确认的 python3 或解释器绝对路径。
认证按所选手册通过环境变量 GITEE_TOKEN 注入，不放进命令参数、正文文件或输出。令牌未提供时只可预览，不能声称已连接。
默认 API_BASE 为 https://gitee.com/api/v5；内网实例必须核对路径、网络、认证与协议兼容性。

## 只读验证与反馈

```sh
python SCRIPT_FILE --api-base API_BASE --path user --select login,id
python SCRIPT_FILE --api-base API_BASE --path repos/OWNER/REPO --select full_name,default_branch
python SCRIPT_FILE --api-base API_BASE --path repos/OWNER/REPO/pulls/NUMBER
python SCRIPT_FILE --api-base API_BASE --path repos/OWNER/REPO/pulls/NUMBER/commits
python SCRIPT_FILE --api-base API_BASE --path repos/OWNER/REPO/pulls/NUMBER/comments
```

接口名称与返回字段须与当前实例手册一致；实际 diff、审查状态和 CI 若不是这些 API 提供，绑定其实际读取入口。
helper 不自动分页；列表按实例支持的 page/per_page 用 JSON 参数文件传给 --body-file，持续读取到结束，不以第一页当完整。
记录接口返回的源提交、目标基础以及本次检查关联。无法核对必需门槛时保留未验证。

## 授权后的写操作

创建 PR 前，Agent 根据当前分支、目标分支及验证事实写 PR_JSON_FILE，字段为 title、head、base、body。
先预览，再在已有授权内实际发送：

```sh
python SCRIPT_FILE --api-base API_BASE --path repos/OWNER/REPO/pulls --method POST --body-file PR_JSON_FILE --select number,html_url --dry-run
python SCRIPT_FILE --api-base API_BASE --path repos/OWNER/REPO/pulls --method POST --body-file PR_JSON_FILE --select number,html_url
```

更新说明时按实例契约 PATCH repos/OWNER/REPO/pulls/NUMBER；评论按 POST repos/OWNER/REPO/pulls/NUMBER/comments，JSON 文件字段由该契约确定。
评论与变更分别回读确认，AI 技术意见和代记的人类验收标明来源及对应版本。
合并接口、审批限制和线程处理按该实例手册实施，不能从 GitHub 命令或一个 HTTP 成功推定。
helper 未实现自动重试写请求、CI 配置或权限推断；失败后先核对远端状态，避免重复创建。
默认 HTTPS，私有 CA 可用 --ca-file。只有手册明确的本地/内网 HTTP 才使用 --allow-http。
query token 的要求来自 API v5 契约，避免记录含凭据的请求 URL；helper 输出会脱敏，不使用 verbose 导出原凭据。

## CI 与工具绑定

识别实际使用的 Gitee 流水线或其他 CI，再只读所需手册。
项目资料写明配置位置、触发、执行器、必需检查、运行和日志的实际查询工具/命令及账号能力。
缺少 API/CLI 步骤时从官方或用户手册补齐并保存，不能只写“接入 CI”或声称 helper 自动设置了流水线。
仅网页可操作时按当前允许的浏览器工具执行；工具缺失才准备。
按实际操作回读记录：已认证、仓库可访问、PR 写入、CI 触发及规则有效分别确认。

参考：[Gitee OpenAPI](https://gitee.com/api/v5/swagger)、[API 规范](https://gitee.com/api/v5/swagger_doc)、[流水线](https://help.gitee.com/enterprise/pipeline)、[Windows Python](https://learn.microsoft.com/en-us/windows/dev-environment/python)。

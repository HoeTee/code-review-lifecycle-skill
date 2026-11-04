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

## 意见与 CI

经授权发表评论时，按实例手册向对应 PR 的评论接口提交。标明技术意见来源与受审版本。回读实际线程状态和审批要求。

读取已有流水线的必需检查、运行和日志。核对检查与受审版本的关系。仅能通过网页查看时，使用当前允许的浏览器入口。

参考：[Gitee OpenAPI](https://gitee.com/api/v5/swagger)、[API 规范](https://gitee.com/api/v5/swagger_doc)、[流水线](https://help.gitee.com/enterprise/pipeline)、[Windows Python](https://learn.microsoft.com/en-us/windows/dev-environment/python)。

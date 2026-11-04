# Git 安装分支：仅在本次需要 Git 且没有可用版本时读取

先运行 `git --version`；已有兼容版本时直接复用，不为本次任务强制升级。
安装在实际执行 Git 的机器，不复制工具二进制进 skill 或仓库。
以下是条件安装步骤，只有当前任务需要且工具缺失时才执行。

## Windows / PowerShell

前置条件：WinGet 可用，且当前账号能按系统要求安装应用。

```powershell
winget --version
winget install --id Git.Git -e --source winget
```

安装后打开新的终端窗口，再运行 `git --version`。
没有 WinGet 时，按 [Git 官方 Windows 安装入口](https://git-scm.com/install/windows)选择适合架构的安装器。
该入口列出的 WinGet 包不是 Git for Windows 项目维护的包。
不为了安装一个工具而预先搭建整套其他包管理器。

## Linux / shell

先读取发行版，再选择唯一适用的命令分支。

```sh
cat /etc/os-release
uname -m
```

Debian / Ubuntu：

```sh
sudo apt-get update
sudo apt-get install -y git
```

Fedora / 使用 dnf 的发行版：

```sh
sudo dnf install git
```

其他发行版按照 [Git 官方 Linux 安装入口](https://git-scm.com/install/linux)补齐命令。
安装后运行 `git --version`。
无 sudo 或网络受限时，按该机器管理方式准备用户态工具或请求必要协助，不宣称安装完成。

## 安装后的边界

Git 能运行只证明本机工具可用。
随后按目标仓库手册验证 remote、认证、仓库访问与所需操作。
GitHub、Gitee 的 PR 与 CI 接入由各自分支处理。

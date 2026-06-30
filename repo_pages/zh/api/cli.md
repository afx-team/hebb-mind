---
description: "hebb 命令行完整参考：初始化 AI 智能体记忆、下载 embedding 模型、运行系统托管的后台服务，并配置 MCP、Claude Code 集成与各项参数。"
---

# CLI 命令参考

Hebb Mind 提供单一的 `hebb` 命令，覆盖 setup、模型管理、集成、服务和配置等场景。

## 全局选项

```bash
hebb --version    # 显示版本号
hebb --help       # 显示帮助信息
```

## hebb setup

准备开箱即用环境：必要时初始化 workspace，根据内容语言与 profile 选择 embedding 模型，根据网络区域选择 HuggingFace 下载源，下载并验证模型。**不会**启动服务。

```bash
hebb setup [--language auto|en|zh|multi] [--region auto|cn|global] [--profile default|fast|best]
```

| 选项 | 默认 | 说明 |
|------|------|------|
| `--language` | `auto` | 选择内容语言；`auto` 按系统 locale 推断 |
| `--region` | `auto` | `cn` 走 `https://hf-mirror.com`；`global` 走 HuggingFace 官方 |
| `--profile` | `default` | 选择模型档位，详见下表 |

`--profile` 决定下载哪个 embedding 模型：

| Profile | 英语（`en`） | 中文 / 多语言（`zh`、`multi`） |
|---------|-------------|------------------------------|
| `default`（默认） | `all-MiniLM-L6-v2`（约 90MB） | `intfloat/multilingual-e5-small`（约 470MB，多语言） |
| `fast` | `all-MiniLM-L6-v2`（约 90MB，最小） | `all-MiniLM-L6-v2`（约 90MB） |
| `best` | `BAAI/bge-large-en-v1.5`（高质量，1–2GB） | `BAAI/bge-m3`（高质量，1–2GB） |

裸 `hebb setup`（即 `--profile default`）只会下载**小模型**：英语约 90MB，多语言约 470MB，**且仅在本地尚未缓存该模型时才下载**，已缓存则直接复用、不会重复下载。需要更高检索质量时再显式使用 `hebb setup --profile best` 拉取 bge 系列大模型（1–2GB）。

`setup` 不启动服务，完成后运行 `hebb service install` 以安装并启动后台服务。

`hebb setup` 首次运行会在工作目录创建：

- `hebb.json` — 配置文件
- `hebb.db` — SQLite 数据库（含 5 个默认分区）
- `knowledge_graph.json` — 空的知识图谱

## hebb service

Hebb Mind 统一通过操作系统的后台服务管理器运行 —— macOS 用 launchd，
Linux 用 systemd，Windows 用任务计划程序。**没有前台 `start` 命令**，
进程的生命周期完全由系统管理。

```bash
hebb service install    [--scope user|system]
hebb service uninstall  [--scope user|system]
hebb service start      [--scope user|system]
hebb service stop       [--scope user|system]
hebb service restart    [--scope user|system]
```

| 选项 | 默认 | 说明 |
|------|------|------|
| `--scope user` | ✔ | 用户级安装，**无需管理员权限**。对应 macOS LaunchAgent / `systemctl --user` 单元 / 用户级计划任务 |
| `--scope system` | -- | 系统级安装。需要 `sudo`（macOS / Linux）或管理员（Windows），开机即随系统启动 |

服务读取 `hebb.json` 中的 host/port。修改后请运行 `hebb service restart` 让新配置生效。

| 平台 | 查看 | 日志 |
|------|------|------|
| macOS | `launchctl print gui/$(id -u)/com.hebb.server` | `tail -f /tmp/hebb.log /tmp/hebb.err` |
| Linux（user） | `systemctl --user status hebb` | `journalctl --user -u hebb -f` |
| Linux（system） | `sudo systemctl status hebb` | `journalctl -u hebb -f` |
| Windows | `schtasks /Query /TN "HebbMind" /FO LIST /V` | `%TEMP%\hebb.log` |

> **Linux 提示**：`systemctl --user` 默认只在用户登录期间运行。若希望注销
> 后或开机时也继续运行，请执行一次 `loginctl enable-linger $USER`。

## hebb status

一次性查看：OS 服务注册状态、HTTP 健康、调度器任务。

```bash
hebb status [--url URL]
```

输出示例：

```
launchd (com.hebb.server) (OS: Darwin)
  Installed: yes
  Running:   yes
  Logs:      tail -f /tmp/hebb.log /tmp/hebb.err

Server is running at http://127.0.0.1:8321 (v0.1.1)

Scheduler Jobs
┌──────────────────┬───────────────────────────┐
│ Job              │ Next Run                  │
├──────────────────┼───────────────────────────┤
│ consolidation_job│ 2026-04-18T18:00:00+08:00 │
│ forgetting_job   │ 2026-04-17T11:00:00+08:00 │
└──────────────────┴───────────────────────────┘
```

## hebb console

在默认浏览器中打开 Hebb Mind Web 控制台；执行前会先健康检查，若服务未运行则给出安装/启动提示。

```bash
hebb console            # 浏览器打开
hebb console --print    # 只打印 URL（适合 CI/SSH）
```

## hebb doctor

对 Python 版本、配置文件、workspace、LLM、embedding 模型缓存、Web 控制台资源、服务可达性、Claude Code / Codex MCP 注册逐项检查，输出 `[OK]`/`[WARN]`/`[FAIL]`。

```bash
hebb doctor
```

## hebb model

查看或预下载 embedding 模型。

```bash
hebb model status
hebb model prefetch [--model MODEL_ID] [--region auto|cn|global]
```

`status` 显示当前 provider、模型、维度、语言策略、下载源以及是否已缓存。

`prefetch` 将模型下载到 workspace 的 `models/` 目录并加载一次以确认维度；如果带上 `--model`，还会同时更新 `embedding_provider`、`embedding_model` 和 `embedding_dim`。

## hebb memory

记忆批量操作。

```bash
hebb memory reembed [--partition NAME] [--batch-size 64] [--dry-run] [--restart] [--yes]
```

`reembed` 遍历所有记忆（或指定分区），用**当前配置**的 embedder 重新计算向量。切换 `embedding_model` 或 `embedding_dim` 之后用 —— 维度变化时启动会自动重建向量表，再用此命令把已有记忆的向量补回去。

- `--partition NAME` —— 只处理指定分区。
- `--batch-size N` —— 每批 N 条（默认 64，最大 512）。
- `--dry-run` —— 只统计不写入。
- `--restart` —— 强制丢弃已有断点，从头开始。
- `-y / --yes` —— 跳过确认。在非交互式 shell 中必须传。

会在 `<workspace>/reembed.checkpoint.json` 写断点文件，每处理 ~32 条 flush 一次。中断后**再跑一次同样的命令**即可续跑，只处理剩下的。成功跑完自动删除断点；如果两次运行之间 embedder 模型 / 维度 / partition 范围有任何变化，旧断点会被自动丢弃重新开始。

完整流程见 [切换 Embedding 模型](../guide/switch-embedding-model.md)。

## hebb mcp

MCP 服务命令。

```bash
hebb mcp serve
```

`serve` 在 stdio 模式下启动 MCP 服务，提供 `write_memory`、`search_memory`、`consolidate` 工具。本质是 FastAPI 服务的轻量代理，因此使用前请确保后台服务已安装（`hebb service install`）；若服务未运行，MCP 会自动请求 OS 服务管理器拉起。在 Claude Desktop、Cursor、Continue 等 MCP 客户端中配置该命令以接入 Hebb Mind。

## hebb claude-code

Claude Code 集成。安装钩子并注册 MCP 服务。

```bash
hebb claude-code install   [--scope project|user]   # 默认: project
hebb claude-code uninstall [--scope project|user]
hebb claude-code recall      # SessionStart 钩子：注入跨会话记忆
hebb claude-code prompt      # UserPromptSubmit 钩子：召回与本次提问相关的记忆
hebb claude-code stop        # Stop 钩子：记录本轮对话
```

`install --scope project` 写入当前目录的 `.claude/`；`--scope user` 写入 `~/.claude/`。

三个钩子各司其职：

- `recall`（SessionStart）—— 会话开始时，把跨会话的相关记忆注入上下文。
- `prompt`（UserPromptSubmit）—— 每次提交提问时，**召回**与提问相关的记忆并注入；它**不写入**任何内容。
- `stop`（Stop）—— 助手回合结束时，从 transcript 抓取最后一轮「用户 + 助手」对话写入工作区（`source` 为 `hook:stop`，按 `session_id + 轮次` 去重）。

> Stop 钩子只**写入本轮对话**，**不触发巩固**。巩固按 `consolidation_time` 定时任务运行，或手动调用 `POST /api/v1/admin/consolidate`。

## hebb codex

Codex 原生 MCP 与生命周期 hooks 集成。项目 scope 写入
`.codex/config.toml` 和 `.codex/hooks.json`；用户 scope 通过
`codex mcp add` 注册 MCP，并写入 `~/.codex/hooks.json`。

```bash
hebb codex install   [--scope project|user]   # 默认 project；当前项目
hebb codex uninstall [--scope project|user]   # 默认 project；当前项目
hebb codex recall    # SessionStart hook 入口
hebb codex prompt    # UserPromptSubmit hook 入口
hebb codex stop      # Stop hook 入口
```

`--scope user` 表示当前 OS 用户级配置，对该用户的所有 Codex 项目生效；
不加时等价于 `--scope project`，只写当前目录的 `.codex/`。

通过 `codex mcp list` 验证 MCP，并在 Codex 中通过 `/hooks` 审核 hooks。

## hebb config

通过 CLI 管理 `hebb.json`。

### config list

打印所有配置（敏感字段自动脱敏）。

```bash
hebb config list
```

### config get

获取单个配置值。合成键 `workspace` 会返回解析后的工作目录。

```bash
hebb config get llm_model
hebb config get workspace
```

### config set

设置配置值（自动类型转换：`"true"` → `True`，`"8000"` → `8000`）。

```bash
hebb config set llm_api_key sk-your-key
hebb config set llm_model openai/gpt-4o
hebb config set port 9000
hebb config set embedding_enabled false
hebb config set home /data/hebb
```

### config path

打印当前 `hebb.json` 的完整路径。

```bash
hebb config path
```

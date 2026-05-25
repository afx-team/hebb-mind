# CLI 命令参考

Hebb Mind 提供单一的 `hebb` 命令，覆盖 setup、模型管理、集成、服务和配置等场景。

## 全局选项

```bash
hebb --version    # 显示版本号
hebb --help       # 显示帮助信息
```

## hebb setup

准备开箱即用环境：必要时初始化 workspace，根据内容语言选择 embedding 模型，根据网络区域选择 HuggingFace 下载源，下载并验证模型。**不会**启动服务。

```bash
hebb setup [--language auto|en|zh|multi] [--region auto|cn|global] [--profile default|fast|best]
```

| 选项 | 默认 | 说明 |
|------|------|------|
| `--language` | `auto` | `en` → `BAAI/bge-large-en-v1.5`；`zh`/`multi` → `BAAI/bge-m3`；`auto` 按系统 locale 推断 |
| `--region` | `auto` | `cn` 走 `https://hf-mirror.com`；`global` 走 HuggingFace 官方 |
| `--profile` | `default` | `fast` 偏向小模型；`best` 偏向高质量 |

`setup` 不启动服务，完成后运行 `hebb start`。

## hebb init

离线初始化项目目录。创建配置文件、SQLite 数据库和空的知识图谱。

```bash
hebb init [--dir DIR] [--force]
```

| 选项 | 默认 | 说明 |
|------|------|------|
| `--dir DIR` | `HEBB_HOME` 或 `~/.hebb/` | 初始化目录 |
| `--force` | -- | 覆盖已有配置并重置 SQLite 数据库 |

执行后会创建：

- `hebb.json` — 配置文件
- `hebb.db` — SQLite 数据库（含 5 个默认分区）
- `knowledge_graph.json` — 空的知识图谱

## hebb start

启动 FastAPI 服务。

```bash
hebb start [--host HOST] [--port PORT] [--reload] [-d|--daemon]
```

| 选项 | 默认 | 说明 |
|------|------|------|
| `--host` | 配置文件 `host`（`0.0.0.0`） | 监听地址 |
| `--port` | 配置文件 `port`（`8321`） | 端口 |
| `--reload` | -- | 启用 uvicorn 热重载（开发模式） |
| `-d`, `--daemon` | -- | 后台运行；PID 写入 `<workspace>/hebb.pid` |

如果同地址已经在运行，命令会直接退出而不再启动。

## hebb stop

停止正在运行的服务（优先读取 PID 文件，回退到 `lsof -ti :PORT`）。

```bash
hebb stop [--url URL]
```

## hebb restart

先 stop 再 start。

```bash
hebb restart [--host HOST] [--port PORT] [--reload] [-d|--daemon]
```

## hebb status

健康检查并打印调度器任务表。

```bash
hebb status [--url URL]
```

输出示例：

```
Server is running (v0.1.1)

Scheduler Jobs
┌──────────────────┬───────────────────────────┐
│ Job              │ Next Run                  │
├──────────────────┼───────────────────────────┤
│ consolidation_job│ 2026-04-18T18:00:00+08:00 │
│ forgetting_job   │ 2026-04-17T11:00:00+08:00 │
└──────────────────┴───────────────────────────┘
```

## hebb doctor

对 Python 版本、配置文件、workspace、LLM、embedding 模型缓存、Web 控制台资源、服务可达性、Claude Code / Codex MCP 注册逐项检查，输出 `[OK]`/`[WARN]`/`[FAIL]`。

```bash
hebb doctor
```

## hebb workspace

打印解析后的工作目录。解析顺序：

1. `HEBB_HOME` 环境变量
2. 由当前目录向上查找到的 `hebb.json` 所在目录
3. `~/.hebb/`（默认）

```bash
hebb workspace
```

## hebb model

查看或预下载 embedding 模型。

```bash
hebb model status
hebb model prefetch [--model MODEL_ID] [--region auto|cn|global]
```

`status` 显示当前 provider、模型、维度、语言策略、下载源以及是否已缓存。

`prefetch` 将模型下载到 workspace 的 `models/` 目录并加载一次以确认维度；如果带上 `--model`，还会同时更新 `embedding_provider`、`embedding_model` 和 `embedding_dim`。

## hebb service

安装/卸载开机自启的系统服务。Linux 写入 `systemd` 单元；macOS 写入 `launchd` plist。

```bash
hebb service install
hebb service uninstall
```

安装后查看与停止：

| 平台 | 查看 | 停止 |
|------|------|------|
| Linux | `systemctl status hebb` / `journalctl -u hebb -f` | `systemctl stop hebb` |
| macOS | `launchctl print gui/$(id -u)/com.hebb.server` | `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.hebb.server.plist` |

## hebb mcp

在 stdio 模式下启动 MCP 服务，提供 `write_memory`、`search_memory`、`consolidate` 工具。本质是 FastAPI 服务的轻量代理，因此使用前请确保 `hebb start` 已运行。

```bash
hebb mcp
```

在 Claude Desktop、Cursor、Continue 等 MCP 客户端中配置该命令以接入 Hebb Mind。

## hebb cc

Claude Code 集成。安装钩子并注册 MCP 服务。

```bash
hebb cc install   [--scope project|user]   # 默认: project
hebb cc uninstall [--scope project|user]
hebb cc recall      # SessionStart 钩子
hebb cc write       # UserPromptSubmit 钩子
hebb cc stop        # Stop 钩子（巩固 + 清理）
```

`install --scope project` 写入当前目录的 `.claude/`；`--scope user` 写入 `~/.claude/`。

## hebb codex

Codex CLI 集成（封装 `codex mcp add/remove`）。

```bash
hebb codex install   [--scope user|project]   # 默认: user
hebb codex uninstall [--scope user|project]
```

可通过 `codex mcp list` 验证。

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

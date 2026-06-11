---
description: "为 Claude Code 接入长期记忆：一条命令安装 MCP 工具与会话 Hooks，实现跨会话自动召回、按回合写入与定时巩固。"
---

# Claude Code 集成

Hebb Mind 与 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 深度集成，提供 **MCP 工具**（手动记忆操作）和 **Hooks 自动记忆层**（跨会话自动召回 + 按回合写入）。

## 概览

| 模式 | 功能 | 工作方式 |
|------|------|---------|
| **MCP Server** | 手动调用 `write_memory`、`search_memory`、`consolidate`、`ingest_conversation` | Claude 按需调用工具 |
| **Hooks（自动记忆）** | 提示提交时召回相关记忆；会话结束时按回合写入对话 | Claude Code hooks 在会话生命周期事件中触发 |

推荐两者同时使用 — MCP 用于显式记忆操作，Hooks 用于无感的后台记忆。

受支持的安装路径只有 `hebb claude-code install`。本仓库**没有**发布 plugin marketplace，请勿通过 marketplace 路径安装。

## 安装

```bash
pipx install hebb-mind         # 安装 CLI（后续升级用 `pipx upgrade hebb-mind`）
hebb setup                     # 初始化并预下载 Embedding 模型
hebb claude-code install --scope user   # 注入 hooks + MCP 到 Claude Code
```

没装 `pipx`？参考 [安装 → 如果还没装 pipx](./installation.md#如果还没装-pipx)。

重启 Claude Code 即可生效。Hebb Mind 会自动：

- **召回（SessionStart）** 每次会话开始时加载跨会话记忆，注入上下文
- **召回（UserPromptSubmit）** 每次提交提示时，召回与该提示相关的记忆并注入（这一步**只读不写**）
- **写入（Stop）** 会话/回合结束时，从 transcript 抓取最后一轮用户 + 助手对话写入工作区

巩固**不会**在 Stop 时运行 —— 它按 `consolidation_time` 定时执行，或通过 `POST /api/v1/admin/consolidate` 手动触发。

### 作用域

默认将 hooks 写入**项目级** `.claude/settings.json`。全局安装：

```bash
hebb claude-code install --scope user   # 写入 ~/.claude/settings.json
```

### 卸载

```bash
hebb claude-code uninstall              # 从 settings 中移除 hooks + MCP
```

## Hooks 工作原理

Claude Code [hooks](https://docs.anthropic.com/en/docs/claude-code/hooks) 是在会话生命周期事件中触发的 shell 命令。Hebb Mind 注册了三个：

```
SessionStart ──────→ hebb claude-code recall ──→ 搜索 API ──→ stdout（注入上下文）
UserPromptSubmit ──→ hebb claude-code prompt ──→ 搜索 API ──→ stdout（注入与提示相关的记忆，只读不写）
Stop ──────────────→ hebb claude-code stop ───→ 写入 API（按回合存入工作区）
```

对应的 CLI 子命令是 `recall`、`prompt`、`stop`（**没有 `write` 这个命令**）。

### 召回（SessionStart）

新会话开始时，`hebb claude-code recall` 搜索相关记忆并输出到 stdout，Claude Code 将其注入对话上下文。

- 搜索 `top_k=20`，返回最多 10 条
- **过滤当前会话记忆** — 它们已在上下文中，无需重复
- 输出格式：

```xml
<cross-session-memory source="hebb" count="3">
[mem_preference] (score=0.85 tags=[food, preference]) 用户喜欢吃三文鱼
[mem_semantic] (score=0.72 tags=[coding]) 用户偏好 TypeScript
[mem_episodic] (score=0.68) 上次会话调试了 auth 中间件
</cross-session-memory>
```

### 提示召回（UserPromptSubmit）

每次用户提交提示时，`hebb claude-code prompt` 会**召回**与该提示相关的记忆并注入上下文。注意：这一步**只检索、不写入** —— 它做的是召回，而不是把用户消息存进库。

### 写入（Stop）

用户回合的**写入**发生在 **Stop** 钩子。`hebb claude-code stop` 从 transcript 中抓取最后一轮（用户 + 助手）对话，写入 `mem_hippocampus` 工作区，标记 `source: "hook:stop"`，并按 `session_id + 回合序号`去重。

巩固**不在** Stop 时运行 —— 会话结束只负责把这一轮写进工作区收件箱；记忆的整理（分类到长期分区、去重、打标签）由 `consolidation_time` 定时任务或手动 `POST /api/v1/admin/consolidate` 完成。

## MCP Server

MCP 服务提供显式记忆工具，Claude 可在对话中主动调用：

| 工具 | 描述 | 参数 |
|------|------|------|
| `write_memory` | 写入记忆到工作区 | `content`, `tags?`, `importance?` |
| `search_memory` | 混合检索（向量+关键词+图谱） | `query`, `top_k?` |
| `consolidate` | 触发记忆巩固 | 无 |
| `ingest_conversation` | 摄入一段对话导出（Claude Code JSONL / ChatGPT JSON / 纯文本），逐轮存储 | `content`, `format_hint?`, `importance?` |

### 仅 MCP 配置

如果只需要 MCP 工具而不需要 hooks，在 `.mcp.json` 中填 `hebb-mcp` 的**绝对路径**（GUI / launchd 下 `PATH` 往往不含 pipx 的 bin 目录，裸命令会静默启动失败）。先用 `which hebb-mcp`（Windows：`where hebb-mcp`）查出路径：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/Users/you/.local/bin/hebb-mcp"
    }
  }
}
```

也可以使用 Claude Code 官方 MCP 命令（同样建议传绝对路径）：

```bash
claude mcp add --transport stdio --scope user hebb -- "$(which hebb-mcp)"
claude mcp list
```

详见 [MCP 集成](./mcp-integration.md) 了解 Claude Desktop、Cursor 和远程服务配置。

## 配置

Hooks 使用与主服务相同的 `hebb.json` 配置，无需额外配置。

如果 hook 触发时服务未运行，会请求 OS 服务管理器（launchd / systemd / 任务计划程序）拉起它。如果服务尚未安装，先运行一次 `hebb service install`。

远程服务可通过环境变量指定：

```bash
export HEBB_URL=http://192.168.1.100:8321
```

## 故障排查

### Hooks 未触发

检查 hooks 是否已注册：

```bash
cat .claude/settings.json | grep "hebb claude-code"
```

如果为空，重新运行 `hebb claude-code install`。

### 没有召回记忆

检查服务是否运行且有记忆数据：

```bash
hebb status
curl http://localhost:8321/api/v1/memories?limit=5
```

### 召回速度慢

冷启动后首次召回需要加载嵌入模型。`hebb setup` 会提前下载默认模型，让这条链路更可预期。建议保持服务常驻：`hebb service install`（OS 服务管理器会在崩溃和重启后自动拉起）。

---
description: "通过 MCP 把 Claude Code、Codex、Cursor、Claude Desktop 接入 AI 智能体长期记忆：写入、向量加关键词混合检索召回，并触发记忆巩固。"
---

# MCP 集成

Hebb Mind 提供 MCP (Model Context Protocol) 服务，将记忆操作暴露为工具。Claude Code、Codex、Cursor 等 MCP 客户端可以直接使用。

## 前提条件

Hebb Mind 统一以操作系统后台服务运行（macOS launchd / Linux systemd / Windows 任务计划程序）。MCP 服务启动时若发现后台服务未运行，会自动请求 OS 服务管理器拉起：

```bash
hebb setup              # 首次使用 — 选择模型和镜像源
hebb service install    # 注册后台服务（默认用户级，无需管理员权限）
```

## 可用工具

| 工具 | 描述 | 参数 |
|------|------|------|
| `write_memory` | 写入记忆到海马体工作区 | `content`, `tags?`, `importance?` |
| `search_memory` | 混合检索（向量+关键词+图谱） | `query`, `top_k?` |
| `consolidate` | 触发记忆巩固 | 无 |
| `ingest_conversation` | 摄入一段对话导出（Claude Code JSONL / ChatGPT JSON / 纯文本）—— 自动识别格式、规整每一轮、逐轮存储 | `content`, `format_hint?`, `importance?` |

::: tip 关于 `command` 路径
下面所有 `.mcp.json` / `claude_desktop_config.json` 示例为简洁起见写的是裸 `hebb-mcp`。**对桌面 GUI 应用（Claude Desktop、Cursor）以及由 launchd 拉起的进程，请改填绝对路径** —— 这类环境的 `PATH` 往往不含 pipx 的 bin 目录，裸命令会静默启动失败。先用 `which hebb-mcp`（Windows：`where hebb-mcp`）查出路径，例如 `/Users/you/.local/bin/hebb-mcp`。或者直接走 `hebb claude-code install` / `hebb codex install`，安装器会自动解析绝对路径。
:::

## 配置

MCP 服务自动从 `hebb.json` 发现服务地址。大多数情况下无需任何配置，只需添加命令即可。

如果服务运行在远程主机或非默认地址，可通过 `HEBB_URL` 环境变量指定：

### Claude Code

推荐：

```bash
hebb claude-code install --scope user
```

仅 MCP：

在项目目录下创建 `.mcp.json`（把 `/absolute/path/to/hebb-mcp` 替换为 `which hebb-mcp` 的输出）：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

或在全局配置 `~/.claude.json` 中添加相同内容。

如果服务运行在非默认地址，可以显式指定：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp",
      "env": {
        "HEBB_URL": "http://192.168.1.100:8321"
      }
    }
  }
}
```

### Codex

推荐：

```bash
hebb codex install   # Codex 全局注册 MCP 服务（仅全局）
codex mcp list
```

Codex 原生命令（建议传 `hebb-mcp` 的绝对路径）：

```bash
codex mcp add hebb -- "$(which hebb-mcp)"
```

### Claude Desktop

在 `claude_desktop_config.json`（macOS 通常位于 `~/Library/Application Support/Claude/claude_desktop_config.json`）中添加。Claude Desktop 是 GUI 应用，因此**必须**填 `hebb-mcp` 的绝对路径（取自 `which hebb-mcp`）：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

### Cursor

打开 **Settings → Features → MCP**，添加（Cursor 是 GUI 应用 —— 请用 `which hebb-mcp` 给出的绝对路径）：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

## 工作原理

```
Claude Code / Codex / Cursor
        │ (stdio)
        v
  hebb-mcp (MCP 服务)
        │ (HTTP 调用)
        v
  hebb _serve (REST API, 端口 8321, 由 OS 服务管理器拉起)
        │
  存储 / Embedding / 检索
```

MCP 服务是一个薄包装层，将 MCP 工具调用转换为对运行中 Hebb Mind 服务的 HTTP 请求。所有存储、向量和检索逻辑都在主服务中。

## CLI 使用

也可以直接启动 MCP 服务：

```bash
hebb mcp serve
```

以 stdio 模式运行，适合与 MCP 客户端直接集成。

## 使用示例

配置完成后，AI 助手可以：

1. **存储上下文**：「记住用户偏好 TypeScript 而不是 JavaScript」
2. **后续召回**：「用户的语言偏好是什么？」
3. **整理记忆**：触发巩固，将记忆分类到对应分区

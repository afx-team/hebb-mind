---
description: "通过 MCP 把 Claude Code、Codex、Cursor、Windsurf、VS Code 等 15+ 客户端接入 AI 智能体长期记忆：写入、向量加关键词混合检索召回，并触发记忆巩固。"
---

# MCP 集成

Hebb Mind 提供 MCP (Model Context Protocol) 服务，将记忆操作暴露为工具。任何兼容 MCP 的客户端都可以直接使用。下面是完整的快速接入矩阵 —— 找到你的客户端，粘贴配置即可。

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

## 快速接入矩阵

::: tip 关于 `command` 路径
下面所有示例中的 `/absolute/path/to/hebb-mcp` 是占位符。**对桌面 GUI 应用（Claude Desktop、Cursor、Windsurf、LM Studio 等）以及由 launchd 拉起的进程，必须改填绝对路径** —— 这类环境的 `PATH` 往往不含 pipx 的 bin 目录，裸命令会静默启动失败。先用 `which hebb-mcp`（Windows：`where hebb-mcp`）查出路径。或者直接走 `hebb claude-code install` / `hebb codex install`，安装器会自动解析绝对路径。
:::

如果 Hebb Mind 服务运行在远程主机或非默认地址，添加 `env` 块设置 `HEBB_URL`：

```json
"env": { "HEBB_URL": "http://192.168.1.100:8321" }
```

### 有一键安装器的客户端

#### Claude Code

```bash
hebb claude-code install --scope user   # hooks + MCP，自动解析绝对路径
```

仅 MCP（项目级 `.mcp.json` 或全局 `~/.claude.json`）：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Codex

```bash
hebb codex install   # 项目级 MCP + 生命周期 hooks（默认）
codex mcp list
```

Codex 原生命令：

```bash
codex mcp add hebb -- "$(which hebb-mcp)"
```

### 通过配置接入的客户端

#### Amp

Amp CLI 通过 `amp mcp add` 命令注册 MCP 服务器，配置写入 `.amp/settings.json`（项目级）或 `~/.config/amp/settings.json`（全局）：

```bash
amp mcp add hebb -- /absolute/path/to/hebb-mcp
```

或直接编辑 `.amp/settings.json`：

```json
{
  "amp.mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Claude Desktop

在 `claude_desktop_config.json`（macOS：`~/Library/Application Support/Claude/claude_desktop_config.json`；Windows：`%APPDATA%\Claude\claude_desktop_config.json`）中添加。Claude Desktop 是 GUI 应用，**必须**填绝对路径：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Cline

Cline 将 MCP 配置存储在 `~/.cline/data/settings/cline_mcp_settings.json`（VS Code 扩展）。打开 Cline 面板 → MCP Servers 图标 → Configure 标签 → Configure MCP Servers，添加：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp",
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

#### Copilot (VS Code)

VS Code 中的 Copilot 使用与 VS Code 原生 MCP 相同的 `.vscode/mcp.json`（见下方）。也可以通过命令面板添加：

```text
MCP: Add Server → stdio → name: hebb → command: /absolute/path/to/hebb-mcp
```

#### Cursor

编辑 `~/.cursor/mcp.json`（全局）或 `.cursor/mcp.json`（项目级）。通过 **Settings → Tools & MCP → New MCP Server** 打开，或直接创建文件：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Gemini CLI

编辑 `~/.gemini/settings.json`，添加 `mcpServers` 条目：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Goose

编辑 `~/.config/goose/config.yaml`（macOS/Linux）或 `%APPDATA%\Block\goose\config\config.yaml`（Windows），在 `extensions` 下添加：

```yaml
extensions:
  hebb:
    type: stdio
    name: hebb
    enabled: true
    cmd: /absolute/path/to/hebb-mcp
    args: []
    envs: {}
    timeout: 300
```

或使用 CLI 向导：`goose configure` → Add Extension → Stdio Extension → 名称: `hebb`，命令: `/absolute/path/to/hebb-mcp`。

#### Kiro

编辑 `.kiro/settings/mcp.json`（工作区级）或 `~/.kiro/settings/mcp.json`（用户级）。通过命令面板 **Kiro: Open workspace MCP config** 打开：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp",
      "args": [],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

#### LM Studio

LM Studio 采用与 Cursor 相同的 `mcp.json` 格式。配置文件位于 `~/.lmstudio/mcp.json`（macOS/Linux）或 `%USERPROFILE%\.lmstudio\mcp.json`（Windows）。通过 **Program** 标签 → **Install → Edit mcp.json** 打开：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### opencode

编辑 `opencode.json`（项目级）或 `~/.config/opencode/opencode.json`（全局），在 `mcp` 键下添加：

```json
{
  "mcp": {
    "hebb": {
      "type": "local",
      "command": ["/absolute/path/to/hebb-mcp"],
      "enabled": true
    }
  }
}
```

或使用 CLI：`opencode mcp add` → 名称: `hebb`，类型: `local`，命令: `/absolute/path/to/hebb-mcp`。

#### VS Code（原生 MCP）

VS Code（1.102+）原生支持 MCP。编辑 `.vscode/mcp.json`（工作区级）或通过命令面板 **MCP: Open User Configuration** 打开。注意：VS Code 使用 `"servers"`（不是 `"mcpServers"`）：

```json
{
  "servers": {
    "hebb": {
      "type": "stdio",
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

或从命令行添加：

```bash
code --add-mcp '{"name":"hebb","command":"/absolute/path/to/hebb-mcp"}'
```

#### Warp

Warp 通过 `Settings → MCP`（GUI）支持 MCP 服务器。添加新的 stdio 服务器：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Windsurf

编辑 `~/.codeium/windsurf/mcp_config.json`（macOS/Linux）或 `%USERPROFILE%\.codeium\windsurf\mcp_config.json`（Windows）。通过命令面板 **Windsurf: Configure MCP Servers** 打开：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

### 其他客户端

以下客户端支持 MCP，但配置界面仅限 UI 或仍在演进中。使用标准的 `mcpServers` JSON 格式，粘贴到客户端的 MCP 设置界面：

| 客户端 | 配置位置 | 说明 |
|--------|---------|------|
| **Antigravity** | 编辑器 MCP 设置（UI） | Google 的智能体 IDE；通过 `Settings → MCP` 配置 |
| **Factory** | Factory MCP 配置（UI） | 参考 Factory 文档确认格式 |
| **Junie (JetBrains)** | IDE MCP 设置（UI） | JetBrains AI 助手；`Settings → Tools → MCP` |
| **Qodo Gen** | IDE 插件 MCP 配置（UI） | VS Code 扩展；通过插件设置配置 |

每个客户端添加：

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
Claude Code / Codex / Cursor / Windsurf / VS Code / ...
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

智能体在对话中自然地使用这些工具，无需显式 API 调用。

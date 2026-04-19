# MCP 集成

Hippocampus 提供 MCP (Model Context Protocol) 服务，将记忆操作暴露为工具。Claude Code、Cursor 等 MCP 客户端可以直接使用。

## 安装

```bash
pip install afx-hippocampus[mcp]
```

## 前提条件

需要先启动 hippocampus 服务：

```bash
hippocampus init     # 首次使用
hippocampus start
```

## 可用工具

| 工具 | 描述 | 参数 |
|------|------|------|
| `write_memory` | 写入记忆到海马体工作区 | `content`, `tags?`, `importance?` |
| `search_memory` | 混合检索（向量+关键词+图谱） | `query`, `top_k?` |
| `consolidate` | 触发记忆巩固 | 无 |

## 配置

### Claude Code

在项目目录下创建 `.mcp.json`：

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp",
      "cwd": "/path/to/your/project"
    }
  }
}
```

或在全局配置 `~/.claude.json` 中添加。

### Claude Desktop

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp",
      "cwd": "/path/to/your/project"
    }
  }
}
```

### Cursor

在 Cursor MCP 设置中添加相同配置。

::: tip
`cwd` 必须指向包含 `hippocampus.json` 的目录，MCP 服务通过该配置找到运行中的服务地址和端口。
:::

## 工作原理

```
Claude Code / Cursor
        │ (stdio)
        v
  hippocampus-mcp (MCP 服务)
        │ (HTTP 调用)
        v
  hippocampus start (REST API, 端口 8321)
        │
  存储 / Embedding / 检索
```

MCP 服务是一个薄包装层，将 MCP 工具调用转换为对运行中 Hippocampus 服务的 HTTP 请求。所有存储、向量和检索逻辑都在主服务中。

## CLI 使用

也可以直接启动 MCP 服务：

```bash
hippocampus mcp
```

以 stdio 模式运行，适合与 MCP 客户端直接集成。

## 使用示例

配置完成后，AI 助手可以：

1. **存储上下文**：「记住用户偏好 TypeScript 而不是 JavaScript」
2. **后续召回**：「用户的语言偏好是什么？」
3. **整理记忆**：触发巩固，将记忆分类到对应分区

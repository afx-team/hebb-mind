# Claude Code 集成

Hebb Mind 与 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 深度集成，提供 **MCP 工具**（手动记忆操作）和 **Hooks 自动记忆层**（跨会话自动写入/召回）。

## 概览

| 模式 | 功能 | 工作方式 |
|------|------|---------|
| **MCP Server** | 手动调用 `write_memory`、`search_memory`、`consolidate` | Claude 按需调用工具 |
| **Hooks（自动记忆）** | 自动写入每条用户消息，会话开始时召回跨会话记忆 | Claude Code hooks 在会话生命周期事件中触发 |

推荐两者同时使用 — MCP 用于显式记忆操作，Hooks 用于无感的后台记忆。

## 安装

```bash
pip install -U hebb-mind       # 安装包
hebb setup                     # 初始化并预下载 Embedding 模型
hebb claude-code install --scope user   # 注入 hooks + MCP 到 Claude Code
```

重启 Claude Code 即可生效。Hebb Mind 会自动：

- **召回** 每次会话开始时加载跨会话记忆
- **写入** 每条用户消息自动存入记忆（自动去噪、去重）
- **巩固** 会话结束时触发记忆整理

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
SessionStart ──→ hebb claude-code recall ──→ 搜索 API ──→ stdout（注入上下文）
UserPromptSubmit ──→ hebb claude-code write ──→ 去噪 + 去重 ──→ 写入 API（静默）
Stop ──→ hebb claude-code stop ──→ 巩固 API + 清理（静默）
```

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

### 写入（UserPromptSubmit）

每次用户发送消息时，`hebb claude-code write` 自动捕获：

1. **去噪** — 移除 `<system-reminder>`、`<command-name>` 等系统标签
2. **跳过琐碎消息** — 20 字符以下的内容（"ok"、"yes"、"/clear"）
3. **去重** — SHA-256 哈希检查，同一会话内不重复写入相同内容
4. **静默写入** — 无 stdout 输出，用户无感知

记忆写入 `mem_hippocampus` 工作区，标记 `source: "hook"` 和 session ID。

### 停止（Stop）

会话结束时，`hebb claude-code stop`：

1. 触发记忆巩固（将工作区记忆分类到长期分区）
2. 清理当前会话的去重状态

## MCP Server

MCP 服务提供显式记忆工具，Claude 可在对话中主动调用：

| 工具 | 描述 | 参数 |
|------|------|------|
| `write_memory` | 写入记忆到工作区 | `content`, `tags?`, `importance?` |
| `search_memory` | 混合检索（向量+关键词+图谱） | `query`, `top_k?` |
| `consolidate` | 触发记忆巩固 | 无 |

### 仅 MCP 配置

如果只需要 MCP 工具而不需要 hooks，在 `.mcp.json` 中添加：

```json
{
  "mcpServers": {
    "hebb": {
      "command": "hebb-mcp"
    }
  }
}
```

也可以使用 Claude Code 官方 MCP 命令：

```bash
claude mcp add --transport stdio --scope user hebb -- hebb-mcp
claude mcp list
```

详见 [MCP 集成](./mcp-integration.md) 了解 Claude Desktop、Cursor 和远程服务配置。

## 配置

Hooks 使用与主服务相同的 `hebb.json` 配置，无需额外配置。

如果 hook 触发时服务未运行，会自动启动。

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

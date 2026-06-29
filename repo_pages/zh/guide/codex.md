---
description: "通过 Codex 原生生命周期 hooks 与 MCP 接入自动持久记忆：支持项目级召回、回合写入、搜索、存储和巩固。"
---

# Codex 集成

Hebb Mind 通过 Codex 原生生命周期 hooks 与 MCP 完成集成：
`SessionStart` 召回跨会话上下文，`UserPromptSubmit` 检索与当前提示相关的
记忆，`Stop` 自动记录已完成的回合。MCP 另外提供 `write_memory`、
`search_memory`、`consolidate` 和 `ingest_conversation` 显式操作。

## 前提条件

- `codex` CLI 已在 `PATH` 中。
- Hebb Mind 已安装并初始化。
- 已安装后台服务；hooks 和 MCP 会把请求转发到本地 REST API。

## 项目级安装

在需要启用记忆的项目中执行：

```bash
pipx install hebb-mind
hebb setup
hebb service install
hebb codex install
```

默认 scope 是 `project`。安装器写入：

- `.codex/config.toml`：项目级 `hebb` MCP server
- `.codex/hooks.json`：自动召回与回合写入 hooks

已有的其他 Codex 配置和 hooks 会被保留。重复安装只替换 Hebb Mind
管理的条目。

`--scope` 控制配置写到哪里：

| 命令 | 生效范围 | 写入位置 |
|---|---|---|
| `hebb codex install` | 当前项目 | `.codex/config.toml` 和 `.codex/hooks.json` |
| `hebb codex install --scope project` | 当前项目 | 同上 |
| `hebb codex install --scope user` | 当前 OS 用户的所有 Codex 项目 | Codex 用户级 MCP 配置和 `~/.codex/hooks.json` |

## 激活与验证

Codex 只会在可信项目中加载项目配置，同时命令 hooks 必须经过显式审核。
在该项目中新建 Codex thread，然后执行：

```text
/hooks
```

审核并信任三个 Hebb hooks。随后在终端验证 MCP：

```bash
codex mcp list
```

## 用户级安装

如需在所有项目中启用 Hebb Mind：

```bash
hebb codex install --scope user
```

该命令通过 `codex mcp add` 注册 MCP，并把 hooks 写入
`~/.codex/hooks.json`。用户级 hooks 同样需要通过 `/hooks` 审核。

## 生命周期行为

| 事件 | Hebb 命令 | 行为 |
|---|---|---|
| `SessionStart` | `hebb codex recall` | 注入最近的跨会话上下文和偏好 |
| `UserPromptSubmit` | `hebb codex prompt` | 注入与当前提示相关的记忆 |
| `Stop` | `hebb codex stop` | 解析 Codex rollout 并写入已完成回合 |

Hook 失败时会退化为空操作，因此 Hebb 服务异常不会阻断 Codex。下一次
hook 或 MCP 启动时会请求已安装的系统服务管理器启动 Hebb Mind。

## MCP 工具

仍然可以显式要求 Codex 操作记忆：

- “记住这个项目使用 pnpm，不使用 npm。”
- “从长期记忆中查找认证方案的决策。”
- “巩固今天收集的记忆。”

可以在 `AGENTS.md` 中规定哪些决策需要持久保存，但常规跨会话召回和
回合写入已经不再依赖模型主动决定调用 MCP。

## 远程 Hebb Mind 服务

远程服务可以直接注册为用户级 MCP：

```bash
codex mcp add hebb \
  --env HEBB_URL=http://192.168.1.100:8321 \
  -- "$(which hebb-mcp)"
```

如需 hooks 使用同一远程服务，还需在启动 Codex 的环境中导出
`HEBB_URL`。

## 卸载

卸载当前项目集成：

```bash
hebb codex uninstall
```

卸载用户级集成：

```bash
hebb codex uninstall --scope user
```

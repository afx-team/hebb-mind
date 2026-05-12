# Codex 集成

Hippocampus 通过 MCP 工具集成 Codex。Codex 可以在需要时调用 `write_memory`、`search_memory`、`consolidate` 和 `ingest_conversation`。

## 安装

```bash
pip install -U afx-hippocampus
hippocampus setup
hippocampus codex install --scope user
```

验证：

```bash
codex mcp list
```

## Codex 原生命令

如果希望直接管理 MCP server：

```bash
codex mcp add hippocampus -- hippocampus-mcp
```

远程 Hippocampus 服务：

```bash
codex mcp add hippocampus --env HIPPOCAMPUS_URL=http://127.0.0.1:8321 -- hippocampus-mcp
```

## 能力边界

Codex 通过 MCP 工具进行显式记忆操作。Claude Code 额外支持 hooks，可以在会话生命周期中自动写入和召回记忆。Codex 当前没有同等 hooks 流程。

建议在项目说明中告诉 Codex 何时使用长期记忆：

```text
Use the Hippocampus MCP server when durable user preferences, project facts, or cross-session decisions should be remembered or recalled.
```

## 卸载

```bash
hippocampus codex uninstall --scope user
```

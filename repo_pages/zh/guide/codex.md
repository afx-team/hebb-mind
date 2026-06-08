# Codex 集成

Hebb Mind 通过 MCP 工具集成 Codex。Codex 可以在需要时调用 `write_memory`、`search_memory`、`consolidate` 和 `ingest_conversation`。

## 前提条件

需要已安装 Codex CLI（`hebb codex install` 内部通过 `codex mcp add` 注册 MCP 服务）。可用 `codex --version` 确认。

## 安装

```bash
pipx install hebb-mind         # 后续升级用 `pipx upgrade hebb-mind`
hebb setup
hebb service install           # 注册并启动后台服务（MCP 工具会访问它）
hebb codex install
```

::: warning 务必先 `hebb service install`
Codex 里的 MCP 工具会把请求 POST 到本地的 `127.0.0.1:8321` 服务。如果跳过 `hebb service install`，第一次让 Codex 记东西时，工具调用会以一个不透明的连接错误失败 —— 而提示「Run: hebb service install」只打在 MCP 服务的 stderr 里，Codex 界面上看不到。
:::

没装 `pipx`？参考 [安装 → 如果还没装 pipx](./installation.md#如果还没装-pipx)。

验证：

```bash
codex mcp list
```

## 作用域

Codex 通过 `codex mcp add` **全局**注册 MCP 服务，没有按项目的作用域，因此本命令是全局唯一的（`--scope` 只接受 `user`，且为默认值）。

## Codex 原生命令

如果希望直接管理 MCP server，请填 `hebb-mcp` 的**绝对路径**（GUI / launchd 下 `PATH` 往往不含 pipx 的 bin 目录，裸命令会静默启动失败）。先用 `which hebb-mcp`（Windows：`where hebb-mcp`）查出路径：

```bash
codex mcp add hebb -- "$(which hebb-mcp)"
```

远程 Hebb Mind 服务：

```bash
codex mcp add hebb --env HEBB_URL=http://192.168.1.100:8321 -- "$(which hebb-mcp)"
```

## 在 Codex 中使用

装好后，在 Codex 对话里用自然语言即可触发记忆工具，无需手写 API 调用。例如：

- **存储**：「记住这个项目用 pnpm，不用 npm。」
- **召回**：「这个项目的包管理器是什么？」
- **整理**：「把刚才这些记忆巩固一下。」

为了让 Codex 知道**何时**该动用长期记忆，建议在项目说明里加一句指引：

```text
当需要记住或召回持久的用户偏好、项目事实或跨会话决策时，使用 Hebb Mind MCP server。
```

## 能力边界

Codex 通过 MCP 工具进行显式记忆操作。Claude Code 额外支持 hooks，可以在会话生命周期中自动召回记忆、并在回合结束时写入。Codex 当前没有同等的 hooks 流程。

## 卸载

```bash
hebb codex uninstall
```

# 快速开始

一分钟内启动 Hippocampus 记忆服务。

## 1. 安装

```bash
pip install afx-hippocampus
```

需要 **Python >= 3.10**。无需外部数据库 — SQLite 内置。

## 2. 初始化

```bash
hippocampus init
```

在当前目录生成 `hippocampus.json`（配置文件）和 `hippocampus.db`（数据库）。

## 3. 启动

```bash
hippocampus start
```

打开 [http://localhost:8321/](http://localhost:8321/) 进入 Web 控制台，或 [http://localhost:8321/docs](http://localhost:8321/docs) 查看 API 文档。

## 保持运行

`hippocampus start` 默认在前台运行。后台运行：

```bash
hippocampus start -d
```

开机自启：

```bash
hippocampus service install
```

自动生成系统服务配置（Linux 使用 systemd，macOS 使用 launchd）并启用。移除：

```bash
hippocampus service uninstall
```

Docker 部署方式见 [存储后端](./advanced/storage-backends.md#docker-deployment)。

## 写入与搜索

写入一条记忆：

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "用户喜欢深色主题和紧凑布局",
    "tags": ["preference", "ui"],
    "importance_score": 7.5
  }'
```

搜索记忆：

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "UI 偏好", "top_k": 5}'
```

## 启用巩固

记忆巩固（自动将记忆分类到分区）需要一个 LLM 后端：

```bash
hippocampus config set llm_api_key sk-your-key
```

通过 [LiteLLM](https://github.com/BerriAI/litellm) 切换模型：

```bash
hippocampus config set llm_model openai/gpt-4o          # OpenAI
hippocampus config set llm_model anthropic/claude-3-haiku-20240307  # Anthropic
hippocampus config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1  # 千问/GLM/Kimi
hippocampus config set llm_model openai/qwen-plus
```

手动触发巩固：

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

## MCP 集成

在 Claude Code、Cursor 等 MCP 客户端中使用 Hippocampus：

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp"
    }
  }
}
```

详见 [MCP 集成](./guide/mcp-integration.md)。

## Claude Code 自动记忆

让 Claude Code 拥有跨会话持久记忆：

```bash
hippocampus cc install
```

自动注册三个 hooks 到 `.claude/settings.json`：

- **SessionStart** — 会话开始时召回跨会话记忆
- **UserPromptSubmit** — 每条用户消息自动写入记忆（自动去噪、去重）
- **Stop** — 会话结束时触发记忆巩固

详见 [Claude Code 集成](./guide/claude-code.md)。

## 下一步

- [安装详情](./guide/installation.md) — 可选依赖、从源码安装
- [配置](./guide/configuration.md) — 完整配置项说明
- [记忆生命周期](./concepts/memory-lifecycle.md) — 理解系统核心机制
- [API 文档](./api/memories.md) — 完整 API 参考
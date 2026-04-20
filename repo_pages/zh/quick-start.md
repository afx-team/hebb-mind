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
      "command": "hippocampus-mcp",
      "cwd": "/path/to/your/project"
    }
  }
}
```

详见 [MCP 集成](./advanced/mcp-integration.md)。

## 下一步

- [安装详情](./guide/installation.md) — 可选依赖、从源码安装
- [配置](./guide/configuration.md) — 完整配置项说明
- [记忆生命周期](./concepts/memory-lifecycle.md) — 理解系统核心机制
- [API 文档](./api/memories.md) — 完整 API 参考
# 快速开始

两条路径。60 秒路径**不需要 API Key**；5 分钟路径额外开启 LLM 巩固。

## 路径 A — 60 秒，无需 API Key

写入和混合检索完全离线运行（基于内置的本地 Embedding 模型）。

### 1. 安装

```bash
pip install -U hebb-mind
```

需要 **Python >= 3.10**。SQLite 内置，无需外部数据库。

### 2. Setup

```bash
hebb setup
```

在工作目录下生成 `hebb.json` 与 `hebb.db`，根据系统语言选择 Embedding 模型，并预下载。`language` 与 `region` 是独立参数：

```bash
hebb setup --language en --region cn      # 英文模型，国内镜像
hebb setup --language zh --region global  # 多语言模型，HuggingFace 官方源
```

### 3. 启动服务

```bash
hebb start
```

打开 <http://localhost:8321/> 进入 Web 控制台，或访问 <http://localhost:8321/docs> 查看 OpenAPI 页。运行 `hebb workspace` 可查看数据存放位置。

<!-- TODO(asset): repo_pages/public/quickstart-cast.gif (asciinema of the 60-second path) -->

<p align="center">
  <img src="/quickstart-cast.gif" alt="Asciinema 演示：60 秒完成安装、setup、启动、写入、检索" width="720">
</p>

### 4. 写入与搜索

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H 'Content-Type: application/json' \
  -d '{
    "content": "用户偏好深色模式与紧凑布局",
    "tags": ["preference", "ui"],
    "importance_score": 7.5
  }'

curl -X POST http://localhost:8321/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "UI 偏好", "top_k": 5}'
```

到这一步，向量 + 关键词 + 标签图谱的三路混合检索已完全在本地运行，无任何外部调用。

## 路径 B — 5 分钟，启用 LLM 巩固

巩固、冲突解决、标签提取需要 LLM。**未配置 `llm_api_key` 时，相关接口会静默返回空结果**（v0.1.1 已知问题，详见 [Troubleshooting](./troubleshooting.md#consolidation-no-op)）。

### 1. 配置 LLM

```bash
hebb config set llm_api_key sk-your-key
hebb config set llm_model openai/gpt-4o-mini
```

通过 [LiteLLM](https://github.com/BerriAI/litellm) 切换提供商：

```bash
# Anthropic
hebb config set llm_model anthropic/claude-3-haiku-20240307

# 通义千问 / GLM / Kimi（OpenAI 兼容端点）
hebb config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
hebb config set llm_model openai/qwen-plus
```

### 2. 触发巩固

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

或等待每日 18:00 的定时任务。巩固期间提取的标签会写入知识图谱，可通过 `GET /api/v1/graph/tags` 查看。

## 30 秒 Python SDK

<!-- requires v0.1.2 facade — see PR #N -->

```python
from hebb import HebbMind

mem = HebbMind()  # 使用 ~/.hebb/hebb.json

mem.add("用户偏好深色模式", tags=["preference", "ui"], importance=7.5)

for hit in mem.search("UI 偏好", top_k=5):
    print(hit.score, hit.content)
```

## 常驻运行

`hebb start` 默认在前台运行。后台与开机自启：

```bash
hebb start -d            # 守护进程
hebb service install     # systemd (Linux) / launchd (macOS)
hebb service uninstall   # 移除
```

Docker 部署见 [存储后端](./advanced/storage-backends.md#docker-deployment)。

## MCP 与编辑器集成

```bash
hebb cc install --scope user      # Claude Code：hooks 自动记忆
hebb codex install --scope user   # Codex：MCP 记忆工具
codex mcp list                           # 验证
```

通用 MCP 客户端（Cursor 等）：

```json
{
  "mcpServers": {
    "hebb": { "command": "hebb-mcp" }
  }
}
```

详见：[MCP 集成](./guide/mcp-integration.md) · [Claude Code 集成](./guide/claude-code.md) · [Codex 集成](./guide/codex.md)

## 下一步

- [配置](./guide/configuration.md) — 完整字段说明
- [记忆生命周期](./concepts/memory-lifecycle.md) — 系统核心机制
- [Benchmarks](./benchmarks.md) — LoCoMo / LongMemEval 结果
- [API 文档](./api/memories.md) — 完整 API 参考

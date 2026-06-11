---
description: "通过 LiteLLM 为 AI 智能体记忆配置任意大模型：OpenAI、Anthropic Claude、通义千问、智谱 GLM、Kimi 均可一键切换，Embedding 本地运行无需 API 费用。"
---

# 多模型支持

Hebb Mind 通过 [LiteLLM](https://github.com/BerriAI/litellm) 支持多种 LLM 提供商，只需修改配置即可切换模型。

## 支持的提供商

| 提供商 | 模型标识示例 | 说明 |
|--------|-------------|------|
| OpenAI | `openai/gpt-4o-mini` | 默认推荐 |
| Anthropic | `anthropic/claude-sonnet-4-20250514` | Claude 系列 |
| 通义千问 | `openai/qwen-plus` | 阿里云，需设置 `llm_base_url` |
| 智谱 GLM | `openai/glm-4` | 智谱 AI，需设置 `llm_base_url` |
| Kimi | `openai/moonshot-v1-8k` | Moonshot AI，需设置 `llm_base_url` |

## 配置方式

### OpenAI

```bash
hebb config set llm_model openai/gpt-4o-mini
hebb config set llm_api_key sk-your-openai-key
```

### Anthropic

```bash
hebb config set llm_model anthropic/claude-sonnet-4-20250514
hebb config set llm_api_key sk-ant-your-key
```

### 通义千问

```bash
hebb config set llm_model openai/qwen-plus
hebb config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
hebb config set llm_api_key sk-your-dashscope-key
```

### 智谱 GLM

```bash
hebb config set llm_model openai/glm-4
hebb config set llm_base_url https://open.bigmodel.cn/api/paas/v4
hebb config set llm_api_key your-zhipu-key
```

### Kimi

```bash
hebb config set llm_model openai/moonshot-v1-8k
hebb config set llm_base_url https://api.moonshot.cn/v1
hebb config set llm_api_key sk-your-kimi-key
```

## 国产模型说明

国产模型通常兼容 OpenAI API 格式，因此模型标识使用 `openai/` 前缀，同时设置 `llm_base_url` 指向对应的 API 端点。

## 测试连通性

配置完成后，可以通过 API 测试 LLM 连接：

```bash
curl -X POST http://localhost:8321/api/v1/admin/config/test-llm \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "api_key": "sk-your-key"
  }'
```

也可以在 Web 控制台的 Settings 页面点击 "Test Connection" 按钮测试。

## Embedding 模型

Embedding 模型使用本地的 `sentence-transformers` 运行，不依赖外部 API 调用。`hebb setup` 会根据内容语言与 `--profile` 选择默认模型。裸 `hebb setup`（`--profile default`）只下载**小模型**，避免首次运行就拉取数 GB 权重：

| Profile | 英语 | 中文 / 多语言 |
|---------|------|-------------|
| `default`（默认） | `all-MiniLM-L6-v2`（约 90MB） | `intfloat/multilingual-e5-small`（约 470MB） |
| `fast` | `all-MiniLM-L6-v2`（约 90MB） | `all-MiniLM-L6-v2`（约 90MB） |
| `best` | `BAAI/bge-large-en-v1.5`（1–2GB） | `BAAI/bge-m3`（1–2GB） |

如需更高检索质量，再显式运行 `hebb setup --profile best` 拉取 bge 系列大模型。模型仅在本地尚未缓存时才下载，已缓存则直接复用。

下载区域与语言独立。例如英语内容但在国内网络可用 `hebb setup --language en --region cn`，中文内容但在海外网络可用 `hebb setup --language zh --region global`。

如需更换：

```bash
hebb config set embedding_model "paraphrase-multilingual-MiniLM-L12-v2"
hebb config set embedding_dim 384
hebb service restart
hebb memory reembed         # 维度变了必须执行
```

::: tip
维度变化会导致已有向量失效，启动时向量表会被自动重建。重启后执行 `hebb memory reembed` 把所有记忆的向量重新算一遍。完整步骤（CLI、Web 控制台、reembed 细节）见 [切换 Embedding 模型](../guide/switch-embedding-model.md)。
:::

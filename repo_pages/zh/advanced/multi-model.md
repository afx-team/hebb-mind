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
curl -X POST http://localhost:8321/api/v1/config/test-llm \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "api_key": "sk-your-key"
  }'
```

也可以在 Web 控制台的 Settings 页面点击 "Test Connection" 按钮测试。

## Embedding 模型

Embedding 模型使用本地的 `sentence-transformers` 运行，不依赖外部 API 调用。`hebb setup` 会根据内容语言选择默认模型：

- 英语：`BAAI/bge-large-en-v1.5`
- 中文或多语言：`BAAI/bge-m3`

下载区域与语言独立。例如英语内容但在国内网络可用 `hebb setup --language en --region cn`，中文内容但在海外网络可用 `hebb setup --language zh --region global`。

如需更换：

```bash
hebb config set embedding_model "paraphrase-multilingual-MiniLM-L12-v2"
hebb config set embedding_dim 384
```

::: tip
更换 Embedding 模型后，已有记忆的向量需要重新计算。建议在切换前导出数据，切换后重新初始化并导入。
:::

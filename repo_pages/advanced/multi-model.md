# Multi-Model Support

Hippocampus supports multiple LLM providers through [LiteLLM](https://github.com/BerriAI/litellm). This enables memory consolidation with any major language model.

## Supported Providers

| Provider | Model Example | Configuration |
|----------|--------------|---------------|
| OpenAI | `openai/gpt-4o-mini` | `llm_api_key` |
| OpenAI | `openai/gpt-4o` | `llm_api_key` |
| Anthropic | `anthropic/claude-3-haiku-20240307` | `llm_api_key` |
| Anthropic | `anthropic/claude-3-5-sonnet-20241022` | `llm_api_key` |
| Qwen (Alibaba) | `openai/qwen-plus` | `llm_api_key` + `llm_base_url` |
| GLM (Zhipu) | `openai/glm-4` | `llm_api_key` + `llm_base_url` |
| Kimi (Moonshot) | `openai/moonshot-v1-8k` | `llm_api_key` + `llm_base_url` |

## Configuration

### OpenAI

```bash
hippocampus config set llm_model openai/gpt-4o-mini
hippocampus config set llm_api_key sk-your-openai-key
```

### Anthropic

```bash
hippocampus config set llm_model anthropic/claude-3-haiku-20240307
hippocampus config set llm_api_key sk-ant-your-anthropic-key
```

### Qwen (Alibaba Cloud)

```bash
hippocampus config set llm_model openai/qwen-plus
hippocampus config set llm_api_key sk-your-qwen-key
hippocampus config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
```

### GLM (Zhipu AI)

```bash
hippocampus config set llm_model openai/glm-4
hippocampus config set llm_api_key your-zhipu-key
hippocampus config set llm_base_url https://open.bigmodel.cn/api/paas/v4
```

### Kimi (Moonshot AI)

```bash
hippocampus config set llm_model openai/moonshot-v1-8k
hippocampus config set llm_api_key sk-your-moonshot-key
hippocampus config set llm_base_url https://api.moonshot.cn/v1
```

## How It Works

For Chinese model providers (Qwen, GLM, Kimi), the `openai/` prefix tells LiteLLM to use the OpenAI-compatible API format. The `llm_base_url` points to the provider's endpoint. This works because these providers implement the OpenAI chat completion API specification.

## Embedding Model

The embedding model (`all-MiniLM-L6-v2`) runs **locally** via sentence-transformers. No external API calls are needed for generating embeddings. The model is automatically downloaded on first use (~80 MB).

This means:

- Embedding is free -- no API costs
- Low latency -- no network round-trip
- Privacy -- your text never leaves the machine for embedding
- Offline capable -- works without internet after initial download

The embedding model is separate from the LLM model. You can use any LLM provider while keeping the local embedding model.

## Testing Your Configuration

After configuring a model, test the connection:

```bash
curl -X POST http://localhost:8321/api/v1/config/test-llm
```

This sends a simple test request to verify that the API key and endpoint are working correctly.

## Choosing a Model

For memory consolidation, smaller and faster models work well since the task involves classification and summarization rather than creative generation. Recommended starting points:

- **Budget-conscious**: `openai/gpt-4o-mini` or `openai/qwen-plus`
- **Higher quality**: `openai/gpt-4o` or `anthropic/claude-3-5-sonnet-20241022`
- **Chinese-language memories**: `openai/qwen-plus` or `openai/glm-4`

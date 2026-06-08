# Multi-Model Support

Hebb Mind supports multiple LLM providers through [LiteLLM](https://github.com/BerriAI/litellm). This enables memory consolidation with any major language model.

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
hebb config set llm_model openai/gpt-4o-mini
hebb config set llm_api_key sk-your-openai-key
```

### Anthropic

```bash
hebb config set llm_model anthropic/claude-3-haiku-20240307
hebb config set llm_api_key sk-ant-your-anthropic-key
```

### Qwen (Alibaba Cloud)

```bash
hebb config set llm_model openai/qwen-plus
hebb config set llm_api_key sk-your-qwen-key
hebb config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
```

### GLM (Zhipu AI)

```bash
hebb config set llm_model openai/glm-4
hebb config set llm_api_key your-zhipu-key
hebb config set llm_base_url https://open.bigmodel.cn/api/paas/v4
```

### Kimi (Moonshot AI)

```bash
hebb config set llm_model openai/moonshot-v1-8k
hebb config set llm_api_key sk-your-moonshot-key
hebb config set llm_base_url https://api.moonshot.cn/v1
```

## How It Works

For Chinese model providers (Qwen, GLM, Kimi), the `openai/` prefix tells LiteLLM to use the OpenAI-compatible API format. The `llm_base_url` points to the provider's endpoint. This works because these providers implement the OpenAI chat completion API specification.

## Embedding Model

The embedding model runs **locally** via sentence-transformers. No external API calls are needed for generating embeddings. By default, `hebb setup` selects a **small** model by content language:

- English: `all-MiniLM-L6-v2` (~90 MB)
- Chinese or multilingual: `intfloat/multilingual-e5-small` (~470 MB)

For the high-quality tier (1–2 GB), opt in with `hebb setup --profile best`:

- English: `BAAI/bge-large-en-v1.5`
- Chinese or multilingual: `BAAI/bge-m3`

Download region is independent from language. Use `hebb setup --language en --region cn` for English content on a China network, or `hebb setup --language zh --region global` for Chinese content on a global network.

To swap to a different model after first install:

```bash
hebb config set embedding_model "paraphrase-multilingual-MiniLM-L12-v2"
hebb config set embedding_dim 384
hebb service restart
hebb memory reembed         # required if the dimension changed
```

::: tip
Changing the embedding dimension invalidates all stored vectors — the vector table is auto-reset on next startup. Run `hebb memory reembed` afterwards to repopulate. See [Switch the Embedding Model](../guide/switch-embedding-model.md) for the full walkthrough (CLI, Web Console, and re-embed details).
:::

This means:

- Embedding is free -- no API costs
- Low latency -- no network round-trip
- Privacy -- your text never leaves the machine for embedding
- Offline capable -- works without internet after initial download

The embedding model is separate from the LLM model. You can use any LLM provider while keeping the local embedding model.

## Testing Your Configuration

After configuring a model, test the connection:

```bash
curl -X POST http://localhost:8321/api/v1/admin/config/test-llm \
  -H 'Content-Type: application/json' \
  -d '{"model": "openai/gpt-4o-mini", "api_key": "sk-..."}'
```

This sends a simple test request to verify that the model, API key, and endpoint are working correctly. Add `"base_url": "https://..."` for OpenAI-compatible providers (Qwen, GLM, Kimi).

## Choosing a Model

For memory consolidation, smaller and faster models work well since the task involves classification and summarization rather than creative generation. Recommended starting points:

- **Budget-conscious**: `openai/gpt-4o-mini` or `openai/qwen-plus`
- **Higher quality**: `openai/gpt-4o` or `anthropic/claude-3-5-sonnet-20241022`
- **Chinese-language memories**: `openai/qwen-plus` or `openai/glm-4`

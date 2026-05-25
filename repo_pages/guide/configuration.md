# Configuration

All configuration lives in a single file: **`hebb.json`**. No environment variables are required for local use.

For first-time users, prefer:

```bash
hebb setup --language auto --region auto
```

`language` selects the embedding model. `region` selects the HuggingFace download source. They are independent.

## CLI Config Management

```bash
# View all settings
hebb config list

# Get a single value
hebb config get llm_model

# Get computed properties (derived from workspace)
hebb config get workspace

# Set a value (saved to hebb.json immediately)
hebb config set llm_api_key sk-your-key-here

# Show config file path
hebb config path

# Show resolved workspace directory
hebb workspace

# Inspect embedding model state
hebb model status
```

## Workspace

Hebb Mind stores all data files (`hebb.db`, `knowledge_graph.json`) in a **workspace directory**. The workspace is resolved using the following precedence:

1. **`HEBB_HOME` environment variable** (highest priority)
2. **`home` field in `hebb.json`** (if set)
3. **Parent directory of `hebb.json`** (if a config file is found)
4. **`~/.hebb/`** (default fallback)

Data files always live in the workspace root and cannot be configured individually:

| File | Description |
|------|-------------|
| `hebb.db` | SQLite database |
| `knowledge_graph.json` | Knowledge graph data |

```bash
# Check the resolved workspace directory
hebb workspace
# Output: /home/user/.hebb

# Override the workspace via environment variable
export HEBB_HOME=/data/hebb

# Override the workspace via config
hebb config set home /data/hebb
```

## Full Configuration Reference

Below is a complete `hebb.json` with all available fields:

```json
{
  "storage_type": "sqlite",
  "home": null,
  "pg_url": null,
  "pg_pool_min": 2,
  "pg_pool_max": 10,
  "embedding_enabled": true,
  "embedding_model": "BAAI/bge-large-en-v1.5",
  "embedding_dim": 1024,
  "hf_endpoint": null,
  "llm_model": null,
  "llm_base_url": null,
  "llm_api_key": "sk-xxx",
  "host": "0.0.0.0",
  "port": 8321,
  "consolidation_time": "18:00",
  "forget_interval_seconds": 1800,
  "base_ttl_hours": 168,
  "decay_factor": 0.693,
  "weight_recency": 1.0,
  "weight_importance": 1.0,
  "weight_relevance": 1.0
}
```

## Field Reference

| Field | Default | Description |
|-------|---------|-------------|
| `storage_type` | `sqlite` | Storage backend: `sqlite` or `postgresql` |
| `home` | `null` | Workspace directory override. If set, data files are stored here. Can also be set via `HEBB_HOME` env var. |
| `pg_url` | `null` | PostgreSQL connection URL |
| `pg_pool_min` | `2` | Minimum PostgreSQL connection pool size |
| `pg_pool_max` | `10` | Maximum PostgreSQL connection pool size |
| `embedding_enabled` | `true` | Enable vector embeddings for similarity search |
| `embedding_model` | setup-selected | Sentence-transformers model for embeddings. English defaults to `BAAI/bge-large-en-v1.5`; Chinese/multilingual defaults to `BAAI/bge-m3`. |
| `embedding_dim` | setup-selected | Embedding vector dimension (must match model) |
| `hf_endpoint` | `null` | HuggingFace mirror endpoint. `setup --region cn` sets `https://hf-mirror.com`. |
| `llm_model` | `null` | Optional LLM model identifier via LiteLLM |
| `llm_base_url` | `null` | Custom LLM API endpoint (for Qwen, GLM, Kimi) |
| `llm_api_key` | `null` | LLM provider API key (required for consolidation) |
| `host` | `0.0.0.0` | Server bind address |
| `port` | `8321` | Server port |
| `consolidation_time` | `18:00` | Daily consolidation clock time (`HH:MM`) |
| `forget_interval_seconds` | `1800` | Forgetting job run interval (seconds) |
| `base_ttl_hours` | `168` | Base memory TTL before decay (hours, default 7 days) |
| `decay_factor` | `0.693` | Exponential decay factor for forgetting |
| `weight_recency` | `1.0` | Weight for recency in search scoring |
| `weight_importance` | `1.0` | Weight for importance in search scoring |
| `weight_relevance` | `1.0` | Weight for relevance in search scoring |

## Web Console Settings

The Web Console at [http://localhost:8321/](http://localhost:8321/) includes a **Settings** page where you can view and edit all configuration values through a graphical interface. Changes made through the Web Console are saved to `hebb.json` immediately.

## Configuration Precedence

1. `HEBB_HOME` environment variable (highest priority for workspace resolution)
2. Values in `hebb.json` (primary configuration)
3. Other environment variables prefixed with `HEBB_` (used in Docker deployments)
4. Built-in defaults

## Common Configuration Examples

### Setup language and download region

```bash
# English content, China network
hebb setup --language en --region cn

# Chinese content, global network
hebb setup --language zh --region global
```

### Disable vector search (keyword-only mode)

```bash
hebb config set embedding_enabled false
```

### Use a different LLM provider

```bash
# OpenAI
hebb config set llm_model openai/gpt-4o
hebb config set llm_api_key sk-your-openai-key

# Anthropic
hebb config set llm_model anthropic/claude-3-haiku-20240307
hebb config set llm_api_key sk-ant-your-anthropic-key

# Qwen (Alibaba)
hebb config set llm_model openai/qwen-plus
hebb config set llm_api_key sk-your-qwen-key
hebb config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
```

### Adjust memory retention

```bash
# Memories live longer (14 days base TTL)
hebb config set base_ttl_hours 336

# Slower decay
hebb config set decay_factor 0.3

# Daily consolidation at 6 PM
hebb config set consolidation_time 18:00
```

### Switch to PostgreSQL

```bash
pip install hebb-mind[pg]
hebb config set storage_type postgresql
hebb config set pg_url postgresql://user:pass@localhost/hebb
```

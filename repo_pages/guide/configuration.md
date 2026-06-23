---
description: "Configure Hebb Mind AI agent memory via a single hebb.json: CLI config commands, workspace resolution, embedding model, LLM/consolidation setup, and the full field reference."
---

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
hebb config get workspace

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
hebb config get workspace
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
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dim": 384,
  "hf_endpoint": null,
  "llm_model": null,
  "llm_base_url": null,
  "llm_api_key": null,
  "host": "127.0.0.1",
  "port": 8321,
  "consolidation_time": "18:00",
  "forget_interval_seconds": 1800,
  "half_life_days": 60,
  "k_importance": 2.0,
  "k_access": 1.5,
  "forget_threshold": 0.3,
  "forget_min_retention_days": 1,
  "weight_recency": 1.0,
  "weight_importance": 1.0,
  "weight_relevance": 1.0
}
```

`embedding_model` / `embedding_dim` above show the bare default (`hebb setup --profile default --language en`). `hebb setup` writes whatever your locale and `--profile` select — see the field table below.

## Field Reference

| Field | Default | Description |
|-------|---------|-------------|
| `storage_type` | `sqlite` | Storage backend: `sqlite` or `postgresql` |
| `home` | `null` | Workspace directory override. If set, data files are stored here. Can also be set via `HEBB_HOME` env var. |
| `pg_url` | `null` | PostgreSQL connection URL |
| `pg_pool_min` | `2` | Minimum PostgreSQL connection pool size |
| `pg_pool_max` | `10` | Maximum PostgreSQL connection pool size |
| `embedding_enabled` | `true` | Enable vector embeddings for similarity search |
| `embedding_model` | setup-selected (bare default `all-MiniLM-L6-v2`) | Sentence-transformers model for embeddings. `--profile default` selects `all-MiniLM-L6-v2` (English, ~90MB) or `intfloat/multilingual-e5-small` (Chinese/multi, ~470MB); `--profile best` selects `BAAI/bge-large-en-v1.5` / `BAAI/bge-m3` (1–2GB). Change via [Switch the Embedding Model](./switch-embedding-model.md). |
| `embedding_dim` | setup-selected (bare default `384`) | Embedding vector dimension (must match model — 384 for the default tier, 1024 for the bge tier). Dimension changes auto-reset the vector table at next start; run `hebb memory reembed` after restart. |
| `hf_endpoint` | `null` | HuggingFace mirror endpoint. `setup --region cn` sets `https://hf-mirror.com`. |
| `llm_model` | `null` | LLM model identifier via LiteLLM. **This is the gate for consolidation** — until it is set, consolidation processes zero memories. |
| `llm_base_url` | `null` | Custom LLM API endpoint (for Qwen, GLM, Kimi) |
| `llm_api_key` | `null` | LLM provider API key. Required only for hosted providers; local/proxy models do not need it. |
| `host` | `127.0.0.1` | Server bind address. Defaults to loopback for security (the server has no auth). Set to `0.0.0.0` only behind a firewall/reverse proxy. *(≤0.1.6 defaulted to `0.0.0.0`.)* |
| `port` | `8321` | Server port |
| `consolidation_time` | `18:00` | Daily consolidation clock time (`HH:MM`) |
| `forget_interval_seconds` | `1800` | Forgetting job run interval (seconds) |
| `half_life_days` | `60` | Base retention half-life in days (forgetting). Built-in regions override this; see [Dynamic Forgetting](../concepts/forgetting.md). |
| `k_importance` | `2.0` | How strongly importance extends the half-life (×importance/10) |
| `k_access` | `1.5` | How strongly access count extends the half-life (×access/10) |
| `forget_threshold` | `0.3` | Retention level below which a memory is forgotten |
| `forget_min_retention_days` | `1` | Hard floor (days) on any memory's retained lifetime |
| `weight_recency` | `1.0` | Weight for recency in search scoring |
| `weight_importance` | `1.0` | Weight for importance in search scoring |
| `weight_relevance` | `1.0` | Weight for relevance in search scoring |

## Which changes require a restart

Most fields take effect on the next request. These take effect only after `hebb service restart`:

- All `embedding_*` fields (`embedding_model`, `embedding_dim`, `embedding_enabled`, provider/API fields)
- `storage_type` and the `pg_*` fields
- `consolidation_time` and `forget_interval_seconds`
- the retrieval-pipeline toggles (`keyword_search_enabled`, `graph_search_enabled`, `lexical_boost_enabled`, …)

`llm_model`, `llm_api_key`, `llm_base_url`, `host`, `port`, and the scoring weights apply without a restart. (After an `embedding_dim` change, also run `hebb memory reembed` once the service has restarted.)

## Web Console Settings

The Web Console at [http://localhost:8321/](http://localhost:8321/) lets you view and edit configuration through a graphical interface. Infrastructure settings (LLM, embedding, storage, server) live on the **System** page; recall, consolidation, and forgetting parameters live on their respective **Activate**, **Consolidate**, and **Forget** pages. Changes are saved to `hebb.json` immediately, and fields that require a restart show a `restart required` badge.

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
# Memories live longer (120-day base half-life)
hebb config set half_life_days 120

# Forget sooner (raise the retention threshold)
hebb config set forget_threshold 0.5

# Daily consolidation at 6 PM
hebb config set consolidation_time 18:00
```

### Switch to PostgreSQL

```bash
pipx install 'hebb-mind[pg]'    # or, inside a venv: pip install -U 'hebb-mind[pg]'
hebb config set storage_type postgresql
hebb config set pg_url postgresql://user:pass@localhost/hebb
```

# Config API

The config API allows reading and updating Hebb Mind configuration at runtime. Changes are persisted to `hebb.json`.

All config endpoints are mounted under `/api/v1/admin/config`.

## Get All Settings

Retrieve all configuration values. Sensitive values (`llm_api_key`, `pg_url`, `embedding_api_key`) are masked in the response.

```
GET /api/v1/admin/config
```

**Example:**

```bash
curl http://localhost:8321/api/v1/admin/config
```

**Response (excerpt):**

```json
{
  "storage_type": "sqlite",
  "home": null,
  "embedding_enabled": true,
  "embedding_provider": "local",
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dim": 384,
  "hf_endpoint": null,
  "llm_model": null,
  "llm_base_url": null,
  "llm_api_key": "sk-x****ykey",
  "host": "0.0.0.0",
  "port": 8321,
  "consolidation_time": "18:00",
  "forget_interval_seconds": 1800,
  "base_ttl_hours": 168.0,
  "decay_factor": 0.693,
  "weight_recency": 1.0,
  "weight_importance": 1.0,
  "weight_relevance": 1.0
}
```

## Update Setting

Update a single configuration value.

```
PUT /api/v1/admin/config
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | string | Yes | Configuration field name |
| `value` | string | Yes | New value (string-encoded; the server coerces to the field's declared type) |

**Example:**

```bash
# Change the LLM model
curl -X PUT http://localhost:8321/api/v1/admin/config \
  -H "Content-Type: application/json" \
  -d '{"key": "llm_model", "value": "openai/gpt-4o"}'

# Disable embedding
curl -X PUT http://localhost:8321/api/v1/admin/config \
  -H "Content-Type: application/json" \
  -d '{"key": "embedding_enabled", "value": "false"}'

# Change the server port
curl -X PUT http://localhost:8321/api/v1/admin/config \
  -H "Content-Type: application/json" \
  -d '{"key": "port", "value": "9000"}'
```

**Response:**

```json
{
  "key": "llm_model",
  "value": "openai/gpt-4o",
  "restart_required": false
}
```

`restart_required` is `true` for fields that only take effect after restart (`storage_type`, `pg_url`, `pg_pool_min`, `pg_pool_max`, `embedding_enabled`, `embedding_provider`, `embedding_model`, `embedding_dim`, `embedding_api_key`, `embedding_base_url`, `consolidation_time`, `host`, `port`, `home`).

## Reveal Sensitive Value

Retrieve the unmasked value of a sensitive configuration field. Only `llm_api_key`, `pg_url`, and `embedding_api_key` are revealable.

```
GET /api/v1/admin/config/reveal/{key}
```

**Example:**

```bash
curl http://localhost:8321/api/v1/admin/config/reveal/llm_api_key
```

**Response:**

```json
{
  "key": "llm_api_key",
  "value": "sk-actual-api-key-here"
}
```

## Test LLM Connectivity

Send a minimal completion request to verify model/url/key. If `api_key` contains `****` (a masked value from `GET /admin/config`), the server reads the real key from `hebb.json`.

```
POST /api/v1/admin/config/test-llm
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model` | string | Yes | LiteLLM model identifier (e.g. `openai/gpt-4o-mini`) |
| `base_url` | string | No | Custom API endpoint |
| `api_key` | string | No | API key (or masked placeholder to use the saved key) |

**Example:**

```bash
curl -X POST http://localhost:8321/api/v1/admin/config/test-llm \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "api_key": "sk-your-key"}'
```

**Response (success):**

```json
{
  "success": true,
  "response": "ok",
  "model": "gpt-4o-mini"
}
```

**Response (failure):**

```json
{
  "success": false,
  "error": "AuthenticationError: Invalid API key"
}
```

## Test Embedding Connectivity

Verify a local embedding model loads, or that an embedding API responds.

```
POST /api/v1/admin/config/test-embedding
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provider` | string | Yes | `local` or `api` |
| `model` | string | Yes | Model name (HuggingFace ID for local, LiteLLM model ID for API) |
| `base_url` | string | No | Required for `api` provider |
| `api_key` | string | No | API key (or masked placeholder) |

**Response (success):**

```json
{
  "success": true,
  "dimension": 384,
  "message": "Model loaded, dimension=384, sample vector length=384"
}
```

## Embedding Status

Report the current embedding configuration and whether the local model is cached.

```
GET /api/v1/admin/config/embedding-status
```

**Response (local, cached):**

```json
{
  "enabled": true,
  "provider": "local",
  "model": "all-MiniLM-L6-v2",
  "status": "cached",
  "cached": true
}
```

Other `status` values: `not_downloaded`, `disabled`, `api`.

## Get Field Metadata

Retrieve metadata for every configuration field, useful for building config forms.

```
GET /api/v1/admin/config/fields
```

**Response (excerpt):**

```json
[
  {
    "key": "storage_type",
    "type": "string",
    "description": "'sqlite' or 'postgresql'",
    "default": "sqlite"
  },
  {
    "key": "port",
    "type": "number",
    "description": "",
    "default": 8321
  }
]
```

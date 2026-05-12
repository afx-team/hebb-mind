# Config API

The config API allows reading and updating Hippocampus configuration at runtime. Changes are persisted to `hippocampus.json`.

## Get All Settings

Retrieve all configuration values. Sensitive values (API keys, secrets) are masked in the response.

```
GET /api/v1/config
```

**Example:**

```bash
curl http://localhost:8321/api/v1/config
```

**Response:**

```json
{
  "storage_type": "sqlite",
  "home": null,
  "embedding_enabled": true,
  "embedding_model": "BAAI/bge-large-en-v1.5",
  "embedding_dim": 1024,
  "hf_endpoint": null,
  "llm_model": null,
  "llm_base_url": null,
  "llm_api_key": "sk-****",
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

## Update Setting

Update a single configuration value.

```
PUT /api/v1/config
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | string | Yes | Configuration field name |
| `value` | any | Yes | New value for the field |

**Example:**

```bash
# Change the LLM model
curl -X PUT http://localhost:8321/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"key": "llm_model", "value": "openai/gpt-4o"}'

# Disable embedding
curl -X PUT http://localhost:8321/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"key": "embedding_enabled", "value": false}'

# Change the server port
curl -X PUT http://localhost:8321/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"key": "port", "value": 9000}'
```

**Response:**

```json
{
  "status": "updated",
  "key": "llm_model",
  "value": "openai/gpt-4o"
}
```

## Reveal Sensitive Value

Retrieve the unmasked value of a sensitive configuration field.

```
GET /api/v1/config/reveal/{key}
```

**Example:**

```bash
curl http://localhost:8321/api/v1/config/reveal/llm_api_key
```

**Response:**

```json
{
  "key": "llm_api_key",
  "value": "sk-actual-api-key-here"
}
```

## Test LLM Connectivity

Test whether the configured LLM provider is reachable and the API key is valid.

```
POST /api/v1/config/test-llm
```

**Example:**

```bash
curl -X POST http://localhost:8321/api/v1/config/test-llm
```

**Response (success):**

```json
{
  "status": "ok",
  "model": "openai/gpt-4o-mini",
  "message": "LLM connection successful"
}
```

**Response (failure):**

```json
{
  "status": "error",
  "model": "openai/gpt-4o-mini",
  "message": "Authentication failed: invalid API key"
}
```

## Get Field Metadata

Retrieve metadata about all configuration fields, including types, defaults, and descriptions.

```
GET /api/v1/config/fields
```

**Example:**

```bash
curl http://localhost:8321/api/v1/config/fields
```

**Response:**

```json
[
  {
    "key": "storage_type",
    "type": "string",
    "default": "sqlite",
    "description": "Storage backend: sqlite or postgresql",
    "sensitive": false
  },
  {
    "key": "llm_api_key",
    "type": "string",
    "default": null,
    "description": "LLM provider API key",
    "sensitive": true
  }
]
```

# Memories API

The memories API provides full CRUD operations for managing memories in Hebb Mind.

Base URL: `http://localhost:8321`

## List Memories

Retrieve a paginated list of memories, optionally filtered by partition or tags.

```
GET /api/v1/memories
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `partition_id` | string | -- | Filter by partition ID |
| `tags` | string | -- | Comma-separated tags (memory must contain all listed tags) |
| `offset` | integer | 0 | Number of records to skip |
| `limit` | integer | 50 | Maximum records to return (1-200) |

**Example:**

```bash
# List all memories
curl http://localhost:8321/api/v1/memories

# List memories in semantic partition
curl "http://localhost:8321/api/v1/memories?partition_id=mem_semantic"

# Filter by tag
curl "http://localhost:8321/api/v1/memories?tags=python&limit=10"

# Filter by multiple tags (intersection)
curl "http://localhost:8321/api/v1/memories?tags=python,web&offset=20"
```

**Response:**

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "partition_id": "mem_semantic",
      "content": "Python is a high-level interpreted language",
      "importance_score": 6.0,
      "tags": ["python", "programming"],
      "metadata": {},
      "source": "consolidation",
      "created_at": "2026-04-17T10:00:00Z",
      "updated_at": "2026-04-17T10:00:00Z",
      "last_accessed_at": "2026-04-17T12:30:00Z",
      "access_count": 3,
      "expires_at": "2026-04-24T10:00:00Z"
    }
  ],
  "total": 128,
  "offset": 0,
  "limit": 50
}
```

## Get Memory

Retrieve a single memory by ID. Each call also bumps `last_accessed_at` and `access_count`, which influences the dynamic forgetting TTL.

```
GET /api/v1/memories/{memory_id}
```

```bash
curl http://localhost:8321/api/v1/memories/550e8400-e29b-41d4-a716-446655440000
```

## Create Memory

Create a new memory. By default it lands in `mem_hippocampus` (the working-memory inbox).

```
POST /api/v1/memories
```

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `content` | string | Yes | -- | Memory content (1-10000 chars) |
| `partition_id` | string | No | `mem_hippocampus` | Target partition |
| `importance_score` | float | No | 5.0 | 0-10 |
| `tags` | string[] | No | `[]` | Tag list |
| `metadata` | object | No | `{}` | Free-form metadata; reserved keys: `session_id`, `turn` |
| `source` | string | No | `null` | Origin label (`api`, `agent`, `consolidation`, ...) |

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers dark mode and compact layout",
    "tags": ["preference", "ui"],
    "importance_score": 7.5
  }'
```

Returns `201` with the full memory record (including `id`, `created_at`, `updated_at`, `last_accessed_at`, `access_count`, `expires_at`).

## Create Batch

Create multiple memories in one request; embeddings are computed in a single batched call.

```
POST /api/v1/memories/batch
```

**Request Body:** a JSON array of memory-create objects (same schema as Create).

```bash
curl -X POST http://localhost:8321/api/v1/memories/batch \
  -H "Content-Type: application/json" \
  -d '[
    {"content": "User prefers Python for backend", "tags": ["preference", "python"]},
    {"content": "Project uses PostgreSQL", "tags": ["infra", "database"], "importance_score": 8.0}
  ]'
```

Returns `201` with a JSON array of created memories.

## Ingest Conversation

Ingest a raw conversation export (auto-detect format, normalize, store as memories).

```
POST /api/v1/ingest
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Raw conversation text |
| `format_hint` | string | No | Optional format hint (e.g. `claude_code_jsonl`, `openai_chat`) |
| `partition_id` | string | No | Target partition (default `mem_hippocampus`) |
| `importance_score` | float | No | Default 5.0 |
| `source` | string | No | Source label |

**Response:**

```json
{
  "format_detected": "claude_code_jsonl",
  "turns_parsed": 12,
  "memories_created": 12,
  "warnings": []
}
```

## Update Memory

Partial update. If `content` changes, the embedding is recomputed automatically.

```
PATCH /api/v1/memories/{memory_id}
```

**Request Body:** any subset of `content`, `importance_score`, `tags`, `metadata`.

```bash
curl -X PATCH http://localhost:8321/api/v1/memories/550e8400-... \
  -H "Content-Type: application/json" \
  -d '{"importance_score": 9.0, "tags": ["python", "favorite"]}'
```

## Delete Memory

```
DELETE /api/v1/memories/{memory_id}
```

```bash
curl -X DELETE http://localhost:8321/api/v1/memories/550e8400-...
```

Returns `204 No Content`. The memory's tags are also unlinked from the knowledge graph.

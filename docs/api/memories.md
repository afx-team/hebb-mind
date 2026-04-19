# Memories API

The memories API provides full CRUD operations for managing memories in Hippocampus.

Base URL: `http://localhost:8321`

## List Memories

Retrieve a paginated list of memories, optionally filtered by partition or tag.

```
GET /api/v1/memories?partition_id=xxx&tag=xxx&skip=0&limit=20
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `partition_id` | string | -- | Filter by partition ID |
| `tag` | string | -- | Filter by tag |
| `skip` | integer | 0 | Number of records to skip |
| `limit` | integer | 20 | Maximum records to return |

**Example:**

```bash
# List all memories
curl http://localhost:8321/api/v1/memories

# List memories in semantic partition
curl "http://localhost:8321/api/v1/memories?partition_id=mem_semantic"

# List memories with a specific tag
curl "http://localhost:8321/api/v1/memories?tag=python&limit=10"
```

## Get Memory

Retrieve a single memory by ID.

```
GET /api/v1/memories/{memory_id}
```

**Example:**

```bash
curl http://localhost:8321/api/v1/memories/abc123
```

## Create Memory

Create a new memory. It will be placed in the `mem_hippocampus` (working memory) partition by default.

```
POST /api/v1/memories
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Memory content text |
| `tags` | array | No | List of tag strings |
| `importance_score` | float | No | Importance rating (0-10) |
| `partition_id` | string | No | Target partition (default: `mem_hippocampus`) |

**Example:**

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers dark mode and compact layout",
    "tags": ["preference", "ui"],
    "importance_score": 7.5
  }'
```

**Response:**

```json
{
  "id": "mem_abc123",
  "content": "User prefers dark mode and compact layout",
  "tags": ["preference", "ui"],
  "importance_score": 7.5,
  "partition_id": "mem_hippocampus",
  "access_count": 0,
  "created_at": "2026-04-17T10:30:00Z",
  "updated_at": "2026-04-17T10:30:00Z"
}
```

## Create Batch

Create multiple memories in a single request.

```
POST /api/v1/memories/batch
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `memories` | array | Yes | List of memory objects (same schema as Create) |

**Example:**

```bash
curl -X POST http://localhost:8321/api/v1/memories/batch \
  -H "Content-Type: application/json" \
  -d '{
    "memories": [
      {
        "content": "User prefers Python for backend development",
        "tags": ["preference", "python"],
        "importance_score": 6.0
      },
      {
        "content": "Project uses PostgreSQL in production",
        "tags": ["infrastructure", "database"],
        "importance_score": 8.0
      }
    ]
  }'
```

## Update Memory

Update an existing memory's content, tags, or other fields.

```
PATCH /api/v1/memories/{memory_id}
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | No | Updated content |
| `tags` | array | No | Updated tags |
| `importance_score` | float | No | Updated importance |

**Example:**

```bash
curl -X PATCH http://localhost:8321/api/v1/memories/abc123 \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers light mode and spacious layout",
    "tags": ["preference", "ui", "updated"]
  }'
```

## Delete Memory

Delete a memory by ID.

```
DELETE /api/v1/memories/{memory_id}
```

**Example:**

```bash
curl -X DELETE http://localhost:8321/api/v1/memories/abc123
```

**Response:**

```json
{
  "status": "deleted",
  "id": "abc123"
}
```

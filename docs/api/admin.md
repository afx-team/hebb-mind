# Admin API

The admin API provides endpoints for triggering background jobs and monitoring system health.

## Trigger Consolidation

Manually trigger the memory consolidation process. This processes all unprocessed memories in `mem_hippocampus`.

```
POST /api/v1/admin/consolidate
```

**Example:**

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

**Response:**

```json
{
  "status": "started",
  "message": "Consolidation job triggered"
}
```

## Trigger Forgetting

Manually trigger the forgetting job. This evaluates all memories against their dynamic TTL and removes expired ones.

```
POST /api/v1/admin/forget
```

**Example:**

```bash
curl -X POST http://localhost:8321/api/v1/admin/forget
```

**Response:**

```json
{
  "status": "started",
  "message": "Forgetting job triggered"
}
```

## System Statistics

Retrieve system-wide statistics including memory counts per partition, total memories, and knowledge graph size.

```
GET /api/v1/admin/stats
```

**Example:**

```bash
curl http://localhost:8321/api/v1/admin/stats
```

**Response:**

```json
{
  "total_memories": 1523,
  "partitions": {
    "mem_hippocampus": 12,
    "mem_semantic": 634,
    "mem_episodic": 421,
    "mem_preference": 89,
    "mem_procedural": 367
  },
  "knowledge_graph": {
    "total_tags": 245,
    "total_edges": 1102
  }
}
```

## Health Check

Simple health check endpoint. Returns 200 if the server is running.

```
GET /health
```

**Example:**

```bash
curl http://localhost:8321/health
```

**Response:**

```json
{
  "status": "ok"
}
```

## Status

Extended status information including scheduler state and background job details.

```
GET /status
```

**Example:**

```bash
curl http://localhost:8321/status
```

**Response:**

```json
{
  "status": "running",
  "version": "0.1.0",
  "storage_type": "sqlite",
  "embedding_enabled": true,
  "scheduler": {
    "consolidation": {
      "interval_seconds": 3600,
      "last_run": "2026-04-17T14:00:00Z",
      "next_run": "2026-04-17T15:00:00Z"
    },
    "forgetting": {
      "interval_seconds": 1800,
      "last_run": "2026-04-17T14:30:00Z",
      "next_run": "2026-04-17T15:00:00Z"
    }
  }
}
```

# Admin API

The admin API provides endpoints for triggering background jobs and monitoring system health.

All admin endpoints are mounted under `/api/v1/admin/`. Health and status endpoints are mounted at the root.

## Trigger Consolidation

Run consolidation immediately. Processes unprocessed memories in `mem_hippocampus` and returns the result synchronously.

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
  "processed": 8,
  "succeeded": 7,
  "failed": 1
}
```

| Field | Description |
|-------|-------------|
| `processed` | Number of memories evaluated |
| `succeeded` | Number consolidated successfully |
| `failed` | Number that failed (typically LLM errors) |

## Trigger Forgetting

Evaluate every memory's dynamic TTL and delete the expired ones. Returns the count of deleted memories.

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
  "deleted": 12
}
```

## System Statistics

Retrieve memory counts per partition, total memories, knowledge-graph size, and scheduler status.

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
  "partitions": [
    {"id": "mem_hippocampus", "name": "Hippocampus", "memory_count": 3, "enabled": true},
    {"id": "mem_semantic", "name": "Semantic Memory", "memory_count": 45, "enabled": true},
    {"id": "mem_episodic", "name": "Episodic Memory", "memory_count": 22, "enabled": true},
    {"id": "mem_preference", "name": "Preference Memory", "memory_count": 15, "enabled": true},
    {"id": "mem_procedural", "name": "Procedural Memory", "memory_count": 8, "enabled": true}
  ],
  "total_memories": 93,
  "graph": {
    "tag_count": 67,
    "edge_count": 142
  },
  "scheduler": {
    "running": true,
    "jobs": {
      "consolidation_job": {"next_run_time": "2026-04-18T18:00:00+08:00"},
      "forgetting_job":    {"next_run_time": "2026-04-17T11:00:00+08:00"}
    }
  }
}
```

## Restart Service

Restart the OS-managed Hebb Mind service. The endpoint **returns immediately**; the actual restart is dispatched ~1 second later so the HTTP response can flush before launchd / systemd / Task Scheduler kills this process. Clients should then poll `GET /health` until the new process answers.

```
POST /api/v1/admin/restart
```

**Example:**

```bash
curl -X POST http://localhost:8321/api/v1/admin/restart
```

**Response:**

```json
{
  "message": "Restart scheduled",
  "expected_downtime_seconds": 5,
  "poll": "/health"
}
```

Returns `501 Not Implemented` if the host OS isn't supported by the service manager (only macOS, Linux with systemd, and Windows Task Scheduler are supported today). The Web Console's Embedding Save flow uses this endpoint when a restart-required field has changed.

## Health Check

Lightweight liveness check for monitoring and load balancers.

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
  "status": "ok",
  "version": "0.1.6"
}
```

## Status

Extended status: scheduler jobs and embedding readiness.

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
  "version": "0.1.6",
  "scheduler": {
    "running": true,
    "jobs": {
      "consolidation_job": {"next_run_time": "2026-04-18T18:00:00+08:00"},
      "forgetting_job":    {"next_run_time": "2026-04-17T11:00:00+08:00"}
    }
  },
  "embedding": {
    "enabled": true,
    "provider": "local",
    "model": "all-MiniLM-L6-v2",
    "dimension": 384,
    "available": true
  }
}
```

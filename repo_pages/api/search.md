# Search API

The search API provides hybrid memory retrieval combining vector similarity, keyword matching, and knowledge graph traversal.

## Search Memories

```
POST /api/v1/search
```

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | -- | Search query text |
| `top_k` | integer | No | 10 | Maximum number of results (1-100) |
| `partition_ids` | string[] | No | all | Filter to specific partitions |
| `tags` | string[] | No | -- | Filter to memories with all listed tags |
| `weight_relevance` | float | No | 1.0 | Weight for relevance scoring |
| `weight_importance` | float | No | 1.0 | Weight for importance scoring |
| `weight_recency` | float | No | 1.0 | Weight for recency scoring |
| `prev_turns` | integer | No | 0 | For memories carrying `metadata.session_id`+`turn`, also surface this many turns *before* each top-k hit from the same session. Returned in `related`. |
| `next_turns` | integer | No | 0 | Symmetric to `prev_turns`. Together they implement a turn-window expansion that recovers multi-utterance facts (e.g. "I moved from my home country" + "Sweden") without dragging in the whole session. |

### Basic Search

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "UI preferences"}'
```

### Filtered Search

Search within specific partitions and tags:

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "UI preferences",
    "top_k": 5,
    "partition_ids": ["mem_preference"],
    "tags": ["ui"]
  }'
```

### Weighted Search

Adjust scoring weights to emphasize different signals:

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "recent deployment issues",
    "top_k": 10,
    "weight_relevance": 2.0,
    "weight_importance": 1.0,
    "weight_recency": 3.0
  }'
```

### Conversational Search with Turn Context

When memories are written by the Claude Code Stop hook (per-turn summaries with `metadata.session_id` and `metadata.turn`), expand each hit with adjacent turns from the same session. This is the production setup that drives the LoCoMo R@10 = 94.14% benchmark number (bge-large default) — the 2-on-each-side window recovers facts spread across consecutive utterances.

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what country did Melanie move from",
    "top_k": 10,
    "prev_turns": 2,
    "next_turns": 2
  }'
```

The expanded turns come back in `related`, deduplicated across hits.

## Response Format

```json
{
  "results": [
    {
      "memory": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "partition_id": "mem_preference",
        "content": "User prefers dark mode and compact layout",
        "importance_score": 7.5,
        "tags": ["preference", "ui"],
        "metadata": {},
        "source": "consolidation",
        "created_at": "2026-04-17T10:30:00Z",
        "updated_at": "2026-04-17T10:30:00Z",
        "last_accessed_at": "2026-04-17T15:00:00Z",
        "access_count": 5,
        "expires_at": "2026-04-25T10:30:00Z"
      },
      "score": 0.87,
      "recency_score": 0.95,
      "importance_score_normalized": 0.75,
      "relevance_score": 0.88
    }
  ],
  "related": [
    {
      "id": "661f9500-f30c-52e5-b827-557766551111",
      "partition_id": "mem_preference",
      "content": "User enabled high-contrast accessibility settings",
      "importance_score": 6.0,
      "tags": ["preference", "accessibility"],
      "metadata": {},
      "source": "api",
      "created_at": "2026-04-16T08:00:00Z",
      "updated_at": "2026-04-16T08:00:00Z",
      "last_accessed_at": "2026-04-16T08:00:00Z",
      "access_count": 1,
      "expires_at": null
    }
  ]
}
```

### Response Fields

**results** -- primary search results, ranked by `score` descending. Each entry contains:

| Field | Description |
|-------|-------------|
| `memory` | Full memory record |
| `score` | Composite weighted score |
| `recency_score` | Exponential decay based on `last_accessed_at` |
| `importance_score_normalized` | `importance_score / 10.0`, in `[0, 1]` |
| `relevance_score` | Maximum relevance across vector / keyword / graph paths |

**related** -- additional memories surfaced via knowledge-graph post-expansion. They did not match the query directly but share tags with the top results.

## Scoring Details

The composite score is the weighted average of three normalized signals:

```
score = (weight_recency * recency
       + weight_importance * importance_normalized
       + weight_relevance * relevance)
       / (weight_recency + weight_importance + weight_relevance)
```

- **Recency** -- exponential decay based on time since last access
- **Importance** -- `importance_score / 10.0`
- **Relevance** -- maximum across vector cosine, keyword BM25, and graph proximity

See [Hybrid Search](../concepts/hybrid-search.md) for the full retrieval and scoring pipeline.

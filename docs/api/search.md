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
| `top_k` | integer | No | 5 | Maximum number of results |
| `partition_ids` | array | No | all | Filter to specific partitions |
| `tags` | array | No | -- | Filter to memories with specific tags |
| `weight_relevance` | float | No | 1.0 | Weight for relevance scoring |
| `weight_importance` | float | No | 1.0 | Weight for importance scoring |
| `weight_recency` | float | No | 1.0 | Weight for recency scoring |

### Basic Search

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "UI preferences", "top_k": 5}'
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

## Response Format

```json
{
  "results": [
    {
      "id": "mem_abc123",
      "content": "User prefers dark mode and compact layout",
      "tags": ["preference", "ui"],
      "partition_id": "mem_preference",
      "importance_score": 7.5,
      "scores": {
        "recency": 0.92,
        "importance": 0.75,
        "relevance": 0.88,
        "composite": 2.55
      },
      "created_at": "2026-04-17T10:30:00Z",
      "updated_at": "2026-04-17T10:30:00Z"
    }
  ],
  "related": [
    {
      "id": "mem_def456",
      "content": "User enabled high-contrast accessibility settings",
      "tags": ["preference", "accessibility"],
      "partition_id": "mem_preference",
      "importance_score": 6.0
    }
  ]
}
```

### Response Fields

**results** -- primary search results, ranked by composite score. Each result includes:

- Memory fields (`id`, `content`, `tags`, `partition_id`, `importance_score`, timestamps)
- `scores` -- breakdown of recency, importance, relevance, and the final composite score

**related** -- additional memories found via knowledge graph expansion. These are memories connected to the top results through shared tags in the knowledge graph but did not directly match the query.

## Scoring Details

The composite score is calculated as:

```
composite = weight_recency * recency + weight_importance * importance + weight_relevance * relevance
```

- **Recency** -- exponential decay based on time since last access
- **Importance** -- normalized importance score (0-10 scale mapped to 0-1)
- **Relevance** -- maximum score across vector, keyword, and graph retrieval paths

See [Hybrid Search](../concepts/hybrid-search.md) for a full explanation of the retrieval and scoring pipeline.

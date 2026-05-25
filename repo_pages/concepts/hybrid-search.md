# Hybrid Search

Hebb Mind uses a hybrid search strategy that combines three retrieval paths in parallel, then merges and scores results using a composite formula.

## Three-Path Retrieval

### 1. Vector Path

Embedding similarity search using the query's vector representation.

- **SQLite**: uses sqlite-vec for vector operations
- **PostgreSQL**: uses pgvector for native vector search
- Computes cosine similarity between the query embedding and stored memory embeddings
- Disabled when `embedding_enabled` is set to `false`

### 2. Keyword Path

Full-text search with BM25-style ranking.

- **SQLite**: uses FTS5 (Full-Text Search 5)
- **PostgreSQL**: uses tsvector + GIN index
- Effective for exact term matching and phrase searches
- Always available regardless of embedding configuration

### 3. Graph Path

Knowledge graph neighbor traversal.

- Query tags are looked up in the knowledge graph
- Connected tags (within configurable depth) are used to find related memories
- Captures conceptual relationships that may not appear in text similarity
- See [Knowledge Graph](./knowledge-graph.md) for details

## Merging Results

Results from all three paths are merged by memory ID. When the same memory appears in multiple paths, the **maximum relevance score** across paths is used.

## Composite Scoring

Each retrieved memory receives a final composite score based on three weighted signals:

```
score = weight_recency * recency + weight_importance * importance + weight_relevance * relevance
```

### Recency

Exponential decay based on time since the memory was last accessed. Recently accessed memories score higher.

### Importance

The LLM-rated importance score (0-10), normalized for scoring.

### Relevance

The search relevance score from the retrieval path (vector similarity, keyword match, or graph proximity).

## Configuring Weights

The three weights are configurable to tune search behavior for your use case:

```bash
# Emphasize relevance (good for knowledge retrieval)
hebb config set weight_relevance 2.0
hebb config set weight_importance 1.0
hebb config set weight_recency 0.5

# Emphasize recency (good for conversational agents)
hebb config set weight_recency 2.0
hebb config set weight_relevance 1.0
hebb config set weight_importance 1.0
```

Weights can also be overridden per search request:

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "recent deployment issues",
    "top_k": 10,
    "weight_recency": 3.0,
    "weight_relevance": 1.0,
    "weight_importance": 1.0
  }'
```

## Post-Expansion

After scoring, the top results are expanded via knowledge graph edges. This step finds additional memories related to the top results by following tag connections, and returns them separately in the `related` field of the search response.

## Graceful Degradation

When vector search is disabled (`embedding_enabled: false`), the system gracefully degrades to keyword-only search plus graph retrieval. This is useful for:

- Environments where embedding models cannot be installed
- Reducing resource usage for lightweight deployments
- Testing and development

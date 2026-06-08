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

Lexical tag match against the knowledge graph.

- The query is tokenized; each token is matched against existing tag ids/labels (exact or short-substring match)
- Memories carrying a matched tag, plus their 1-hop tag neighbors, are collected
- This is a lexical tag matcher, not a semantic traversal — it cannot reach a memory whose tags share no token with the query
- See [Knowledge Graph](./knowledge-graph.md) for details

## Merging and Reranking Results

Results from the three paths are fused with **reciprocal-rank fusion (RRF)** into a single candidate list. For the displayed `relevance_score`, the **maximum relevance** across the paths that surfaced a memory is used.

By default a **cross-encoder reranker** (`rerank_enabled: true`, model `BAAI/bge-reranker-base`) then re-scores the top candidates by reading each `(query, content)` pair jointly. This is the single highest-impact retrieval-quality lever measured across LoCoMo / LongMemEval / MemBench. It degrades gracefully: if the reranker model cannot load, the searcher falls back to the calibrated hybrid score with no error. Set `rerank_enabled` to `false` to skip the model download and per-query rerank latency.

## Composite Scoring

Each retrieved memory receives a final composite score based on three weighted signals, normalized to `[0, 1]`:

```
score = (weight_recency * recency
       + weight_importance * importance
       + weight_relevance * relevance)
       / (weight_recency + weight_importance + weight_relevance)
```

### Recency

Exponential decay based on time since the memory was last accessed. Recently accessed memories score higher.

### Importance

The LLM-rated importance score (0-10), normalized for scoring.

### Relevance

The search relevance score, taken as the maximum across the retrieval paths that surfaced the memory (vector cosine similarity, keyword match, or graph tag match).

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

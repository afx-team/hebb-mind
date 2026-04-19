# Memory Lifecycle

Hippocampus processes memories through four stages, inspired by how the human hippocampus consolidates short-term experiences into long-term knowledge.

## Architecture Overview

```
          Write memory
               |
               v
    +---------------------+
    |    HIPPOCAMPUS       |     Working memory inbox
    |    (mem_hippocampus) |     All new memories land here
    +---------------------+
               |
          Consolidation Agent (periodic)
          - Recall related memories (Agentic RAG)
          - Classify into partition
          - Resolve conflicts
          - Extract tags -> Knowledge Graph
               |
      +--------+--------+--------+--------+
      v        v        v        v        v
  SEMANTIC  EPISODIC  PREFERENCE PROCEDURAL CUSTOM
   Facts    Events    Likes/     Skills     Your own
            History   Dislikes   How-to     partitions
      |        |        |        |        |
      +--------+--------+--------+--------+
               |
          Forgetting Job (periodic)
          TTL = base * (1 + log(access)) * importance * exp(-decay * days)
               |
               v
          Expired memories removed
```

## Stage 1: Ingest

New memories enter the system through the REST API and land in the **mem_hippocampus** partition -- the working memory inbox.

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers dark mode and compact layout",
    "tags": ["preference", "ui"],
    "importance_score": 7.5
  }'
```

At this stage, memories are raw and unprocessed. They sit in the inbox waiting for consolidation.

## Stage 2: Consolidate

A periodic consolidation agent processes unprocessed memories from `mem_hippocampus`:

1. **Agentic RAG** -- recalls related historical memories from all partitions to provide context
2. **Classification** -- LLM classifies the memory into the appropriate partition (semantic, episodic, preference, or procedural)
3. **Conflict resolution** -- detects contradictions with existing memories and resolves them (e.g., "user now prefers light mode" supersedes "user prefers dark mode")
4. **Tag extraction** -- extracts meaningful tags and adds them to the knowledge graph

Consolidation runs on a configurable schedule (default: every 3600 seconds / 1 hour). It can also be triggered manually:

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

See [Consolidation](./consolidation.md) for details.

## Stage 3: Retrieve

When searching memories, Hippocampus combines three signals into a composite score:

- **Recency** -- exponential decay based on time since last access. Recently accessed memories score higher.
- **Importance** -- LLM-rated score from 0 to 10 assigned during creation or consolidation.
- **Relevance** -- vector cosine similarity between the query and memory embeddings (when embedding is enabled).

The search system also performs hybrid retrieval across vector, keyword, and knowledge graph paths. See [Hybrid Search](./hybrid-search.md) for details.

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "UI preferences", "top_k": 5}'
```

## Stage 4: Forget

A periodic forgetting job computes a dynamic TTL for each memory:

```
TTL = base_ttl * (1 + log(access_count)) * (importance / 5) * exp(-decay_factor * days_since_access)
```

- Frequently accessed memories survive longer
- High-importance memories are more durable
- Neglected, low-importance memories decay and are removed

This mirrors the Ebbinghaus forgetting curve from cognitive science. See [Dynamic Forgetting](./forgetting.md) for the full formula and configuration.

## Summary

| Stage | Trigger | Key Action |
|-------|---------|------------|
| Ingest | API write | Memory stored in working inbox |
| Consolidate | Periodic / manual | Classify, resolve conflicts, extract tags |
| Retrieve | API search | Three-signal scoring + hybrid search |
| Forget | Periodic / manual | Dynamic TTL computation, expired removal |

---
description: "How AI agent memory flows through four stages -- ingest, consolidate, retrieve, forget -- with hybrid vector + keyword + knowledge-graph search and dynamic TTL forgetting."
---

# Memory Lifecycle

Hebb Mind processes memories through four stages, inspired by how the human hippocampus consolidates short-term experiences into long-term knowledge.

## Architecture Overview

<table style="width:100%; border:none; border-collapse:collapse;">
<tr>
<td align="center" colspan="5" style="padding:6px 14px; background:#1a1a2e; border-radius:8px; color:#e0e0e0; font-weight:600;">
API &middot; MCP &middot; CLI
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:18px; color:#555;">▼</td></tr>
<tr>
<td align="center" colspan="5" style="padding:10px 18px; background:#16213e; border-radius:8px;">
<b style="color:#00d2ff; font-size:16px;">HIPPOCAMPUS</b><br/>
<span style="color:#888; font-size:12px;">Working Memory Inbox</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; color:#555; padding:4px 0;">▼&nbsp; Consolidation Agent <span style="color:#666; font-size:11px;">(Agentic RAG &middot; Classify &middot; Conflict Resolve &middot; Tag Extract)</span></td></tr>
<tr>
<td align="center" style="padding:8px 12px; background:#1b4332; border-radius:6px; min-width:100px;">
<b style="color:#52b788;">SEMANTIC</b><br/><span style="color:#888; font-size:11px;">Facts & Knowledge</span>
</td>
<td align="center" style="padding:8px 12px; background:#3c1642; border-radius:6px; min-width:100px;">
<b style="color:#c77dff;">EPISODIC</b><br/><span style="color:#888; font-size:11px;">Events & History</span>
</td>
<td align="center" style="padding:8px 12px; background:#6b2d5b; border-radius:6px; min-width:100px;">
<b style="color:#ff6b6b;">PREFERENCE</b><br/><span style="color:#888; font-size:11px;">Likes & Dislikes</span>
</td>
<td align="center" style="padding:8px 12px; background:#2d3a4a; border-radius:6px; min-width:100px;">
<b style="color:#4ecdc4;">PROCEDURAL</b><br/><span style="color:#888; font-size:11px;">Skills & How-to</span>
</td>
<td align="center" style="padding:8px 12px; background:#3d3d3d; border-radius:6px; min-width:100px;">
<b style="color:#aaa;">CUSTOM</b><br/><span style="color:#888; font-size:11px;">Your Partitions</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; padding:6px 0;">
<span style="color:#555;">▼</span>&nbsp;
<span style="color:#666; font-size:12px;">Hybrid Retrieval</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">Knowledge Graph</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">Forgetting (Dynamic TTL)</span>
</td></tr>
</table>

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

Consolidation runs once per day at the time configured by `consolidation_time` (default `18:00`, server's local timezone). It can also be triggered manually:

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

See [Consolidation](./consolidation.md) for details.

## Stage 3: Retrieve

When searching memories, Hebb Mind combines three signals into a composite score:

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

A periodic forgetting job decays each memory's retention from its last access and removes it once retention drops below a threshold:

```
eff_half_life  = half_life_days * (1 + k_importance*(importance/10) + k_access*(access_count/10))
retention(idle) = exp(-idle_days / eff_half_life)
forget when retention < threshold
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

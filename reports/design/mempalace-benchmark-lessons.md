# MemPalace Benchmark Lessons: Improving Hebb Mind Evaluation Metrics

## Problem

Hebb Mind's current benchmark scores are significantly lower than MemPalace's:

| Benchmark | Hebb Mind | MemPalace | Gap |
|-----------|-------------|-----------|-----|
| LoCoMo | 37.6% (QA acc, 497q) | 60.3% R@10 raw / 88.9% hybrid | ~23-51 pp |
| LongMemEval | 33.3% (QA acc, 3q) | 96.6% R@5 raw | ~63 pp |

**Important caveat**: MemPalace reports retrieval recall (R@k), Hebb Mind reports QA accuracy (end-to-end). QA accuracy is strictly harder since it requires both correct retrieval AND correct answer generation. Even so, Hebb Mind's `avg_top1_relevance = 0.52` confirms that retrieval quality itself is the primary bottleneck.

---

## Root Cause Analysis

Examining the error patterns:

```
LoCoMo accuracy by category:
  adversarial  66.1%   ← good (doesn't need retrieval)
  single_hop   41.9%   ← retrieval failing ~58% of the time
  open_ended   35.5%   ← retrieval + generation both weak
  temporal     28.6%   ← temporal info lost in consolidation
  multi_hop     5.6%   ← needs multiple memories, retrieval finds <1
```

Error examples reveal two failure modes:
1. **"I don't know"** — retrieval didn't find the relevant memory at all
2. **Relative answers** ("Yesterday", "Last Saturday") — the exact temporal detail was lost during consolidation

---

## Solution: Seven Concrete Changes, Ordered by Expected Impact

### Change 1: Preserve Verbatim Content (Expected: +15-20 pp on LoCoMo)

**The single biggest lever.** Hebb Mind's consolidation agent rewrites memories "for clarity" (via `CONSOLIDATION_SYSTEM_PROMPT`). This is lossy — the LLM strips details it deems unimportant. When LoCoMo asks "When did Caroline go to the LGBTQ support group?" and expects "7 May 2023", a consolidated memory that says "Caroline attended a support group" has destroyed the answer.

MemPalace's core thesis — "verbatim always" — is validated by their 96.6% R@5. Their AAAK summarization layer exists only as an index, never replacing the original text.

**Implementation**:

```python
# In consolidation_agent.py, change Step 5:
# BEFORE: stores only consolidated_content
# AFTER: store BOTH original verbatim + consolidated as metadata

new_memory = await self.memory_store.create(
    data=MemoryCreate(
        content=memory.content,  # VERBATIM original
        partition_id=target_partition,
        importance_score=importance,
        tags=tags,
        metadata={
            **memory.metadata.model_dump(exclude_none=True),
            "consolidated_summary": consolidated_content,  # LLM summary as metadata
        },
        source="consolidation",
    ),
    embedding=embedding,
)
```

The embedding should be computed on the ORIGINAL content, not the consolidated version. The consolidated summary can serve as supplementary search surface.

For session consolidation, store each original turn as a separate memory, plus the consolidated summary as an additional memory with `source="consolidation_summary"`.

**Why this works**: Benchmark questions ask for specific facts (dates, names, places). Verbatim storage preserves these. Consolidation should decide WHERE to store and HOW to index, not WHAT to store.

---

### Change 2: Reciprocal Rank Fusion Instead of Max-Merge (Expected: +5-8 pp)

Current merge in `searcher.py:54-60`:

```python
# Current: takes max score across paths
merged[mem.id] = (existing[0], max(existing[1], score))
```

This loses the signal that multiple retrieval paths agree. If vector returns a memory at rank 3 (score 0.7) and keyword returns the same memory at rank 2 (score 0.6), the current code keeps 0.7 — the same as if only vector matched.

MemPalace uses a convex combination: `score = 0.6 * vector + 0.4 * bm25`. A better approach for multiple paths is Reciprocal Rank Fusion (RRF), which is robust to score distribution differences across retrieval methods.

**Implementation**:

```python
# Replace max-merge with RRF
from collections import defaultdict

def reciprocal_rank_fusion(
    *ranked_lists: list[tuple[Memory, float]],
    k: int = 60,
) -> dict[str, tuple[Memory, float]]:
    """Combine multiple ranked lists using RRF.

    score(d) = sum over all lists: 1 / (k + rank_in_list)
    """
    scores: dict[str, float] = defaultdict(float)
    memory_map: dict[str, Memory] = {}

    for ranked_list in ranked_lists:
        # Sort by score descending to get rank
        sorted_list = sorted(ranked_list, key=lambda x: x[1], reverse=True)
        for rank, (mem, _) in enumerate(sorted_list):
            scores[mem.id] += 1.0 / (k + rank)
            memory_map[mem.id] = mem

    return {
        mid: (memory_map[mid], score)
        for mid, score in scores.items()
    }
```

RRF is the standard fusion technique used in production search systems (Elasticsearch, Azure AI Search). It's parameter-light (only k, which is robust at 60) and handles the case where one path returns calibrated probabilities while another returns raw BM25 scores.

---

### Change 3: Context Window Expansion — Fetch Neighbor Turns (Expected: +5-10 pp)

When Hebb Mind retrieves a memory, it returns only that single memory. But conversational memories are sequential — the answer often spans multiple turns.

MemPalace's Stage 3 (drawer-grep enrichment) fetches ALL chunks from the same source file when a hit is found, returning the best chunk plus its neighbors (chunk[i-1] + chunk[i] + chunk[i+1]).

**Implementation**:

```python
# In searcher.py, after final scoring, expand context:

async def _expand_context(
    self, results: list[MemorySearchResult], n_neighbors: int = 2,
) -> list[MemorySearchResult]:
    """For each top result with session+turn metadata, fetch adjacent turns."""
    expanded_ids: set[str] = {r.memory.id for r in results}

    for result in results:
        meta = result.memory.metadata
        session_id = meta.session_id if meta.session_id else None
        turn = meta.turn if meta.turn is not None else None
        if not session_id or turn is None:
            continue

        # Fetch turns [turn-n, turn+n] from same session
        neighbors = await self.store.get_by_session_and_turn_range(
            session_id=session_id,
            turn_start=max(0, turn - n_neighbors),
            turn_end=turn + n_neighbors,
        )
        for mem in neighbors:
            if mem.id not in expanded_ids:
                expanded_ids.add(mem.id)
                results.append(MemorySearchResult(
                    memory=mem,
                    score=result.score * 0.8,  # discount neighbors
                    recency_score=result.recency_score,
                    importance_score_normalized=result.importance_score_normalized,
                    relevance_score=result.relevance_score * 0.8,
                ))

    return results
```

This requires adding a `get_by_session_and_turn_range()` method to the store. For SQLite:

```sql
SELECT * FROM memories
WHERE json_extract(metadata, '$.session_id') = ?
  AND json_extract(metadata, '$.turn') BETWEEN ? AND ?
ORDER BY json_extract(metadata, '$.turn')
```

**Why this works**: Multi-hop questions (currently 5.6%) often require combining information from adjacent conversation turns. Temporal questions (28.6%) need the surrounding context to resolve relative time references.

---

### Change 4: LLM Reranking Before Answer Generation (Expected: +8-12 pp)

MemPalace's highest benchmark scores (99%+) use LLM reranking. The LLM evaluates each retrieved chunk against the query and re-orders by actual relevance. This is the biggest lever for QA accuracy specifically.

**Implementation** — add a reranking step in `eval/benchmarks/base.py`:

```python
# In base benchmark runner, between retrieval and answer generation:

async def _rerank_with_llm(
    self, query: str, memories: list[str], judge: LLMJudge, top_k: int = 5,
) -> list[str]:
    """Use LLM to rerank retrieved memories by relevance to query."""
    if len(memories) <= top_k:
        return memories

    prompt = f"""Rate each memory's relevance to the question on a scale of 0-10.
Return JSON: {{"scores": [score1, score2, ...]}}

Question: {query}

Memories:
{chr(10).join(f"[{i}] {m[:500]}" for i, m in enumerate(memories))}
"""
    raw = await judge._complete([{"role": "user", "content": prompt}])
    try:
        scores = json.loads(raw.strip().strip("`").strip("json\n"))["scores"]
        ranked = sorted(range(len(memories)), key=lambda i: scores[i], reverse=True)
        return [memories[i] for i in ranked[:top_k]]
    except Exception:
        return memories[:top_k]
```

This adds one LLM call per question but dramatically improves the quality of memories fed to the answer generator. MemPalace reports ~3 pp improvement from LLM reranking alone.

**Trade-off**: Increases latency and API cost. Should be opt-in via `EvalSettings.use_llm_rerank = True`.

---

### Change 5: Fix the Answer Generation Prompt (Expected: +3-5 pp)

Current prompt in `judge.py`:

```
If the memories don't contain enough information, say "I don't know."
```

Many errors show "I don't know" as the generated answer even when relevant memories WERE retrieved. The prompt is too conservative.

**Fix**:

```python
_GENERATE_PROMPT = """\
Based on the following memories, answer the question.
Extract the most specific and precise information available.
For dates, times, and names, use the exact values from the memories.
If the memories contain partial information, provide what you can.
Only say "I don't know" if the memories are completely unrelated to the question.

Memories:
{context}

Question: {question}
Answer concisely with specific details:"""
```

This encourages the LLM to extract partial matches and specific details (dates, names) rather than defaulting to "I don't know" when the match isn't perfect.

---

### Change 6: Increase Overfetch Factor for Recall-Sensitive Benchmarks (Expected: +2-3 pp)

Current overfetch is 3x (`query.top_k * 3`). For QA benchmarks where recall matters more than precision, 5-10x overfetch with aggressive re-ranking catches more relevant memories.

**Implementation**: Make overfetch configurable, defaulting to higher values for eval:

```python
# In EvalSettings:
search_overfetch_factor: int = 5  # was effectively 3

# In searcher.py:
overfetch = query.top_k * query.overfetch_factor  # default 3, eval uses 5
```

---

### Change 7: Embedding Model Upgrade Path (Expected: +3-5 pp)

MemPalace uses all-MiniLM-L6-v2 (384-dim, ~80M params). Hebb Mind has a clean `EmbeddingProvider` protocol. Switching to a stronger model can significantly improve vector retrieval:

| Model | Dim | MTEB Avg | Size |
|-------|-----|----------|------|
| all-MiniLM-L6-v2 | 384 | 56.3 | 80M |
| bge-large-en-v1.5 | 1024 | 64.2 | 335M |
| gte-large-en-v1.5 | 1024 | 65.4 | 434M |
| e5-large-v2 | 1024 | 62.2 | 335M |

**Implementation**: Already supported via the factory pattern. Just need to verify the eval pipeline uses a strong model and that `sqlite-vec` handles higher dimensions correctly.

---

## Implementation Priority

Ordered by impact/effort ratio:

| Priority | Change | Expected Impact | Effort |
|----------|--------|----------------|--------|
| P0 | #1 Preserve verbatim content | +15-20 pp | Medium (consolidation prompt + store logic) |
| P0 | #5 Fix generation prompt | +3-5 pp | Trivial (1 string change) |
| P1 | #2 RRF fusion | +5-8 pp | Small (replace merge logic) |
| P1 | #3 Context window expansion | +5-10 pp | Medium (new store method + searcher logic) |
| P1 | #4 LLM reranking | +8-12 pp | Small (eval-only, no core change) |
| P2 | #6 Overfetch factor | +2-3 pp | Trivial (config change) |
| P2 | #7 Embedding model | +3-5 pp | Small (factory config) |

**Estimated total improvement**: +40-60 pp on LoCoMo, bringing accuracy from ~38% to ~78-98% range.

The P0 changes (#1 and #5) should be implemented first as they are the highest impact with reasonable effort. #5 in particular is a single string change that can be validated immediately.

---

## Metrics Measurement Plan

To properly attribute improvements, run benchmarks after each change:

1. **Baseline**: Current scores (LoCoMo 37.6%, LongMemEval 33.3%)
2. After #5 (generation prompt fix): expect jump to ~42%
3. After #1 (verbatim storage): expect jump to ~55-60%
4. After #2 (RRF): expect jump to ~63-68%
5. After #3 (context expansion): expect jump to ~70-75%
6. After #4 (LLM rerank): expect jump to ~80-85%
7. After #6+#7 (overfetch + embedding): expect jump to ~85-90%

Also add retrieval-only metrics (R@5, R@10, MRR) alongside QA accuracy to isolate retrieval vs generation failures. The eval framework already has `recall_at_k`, `precision_at_k`, `mrr`, and `ndcg_at_k` in `eval/metrics/retrieval.py` but they aren't wired into the benchmark runner.

---

## Additional MemPalace Patterns Worth Adopting

### Query Sanitization

MemPalace's `query_sanitizer.py` strips system prompt contamination from search queries using a 4-step cascade. For MCP integration where queries may contain system prompt fragments, this prevents retrieval degradation.

### Write-Ahead Log

MemPalace logs all write operations to a WAL file. Useful for debugging consolidation issues and replay.

### Closet Boosting as "Signal, Not Gate"

The architectural principle that secondary indexes (closets, graph) can only BOOST scores, never FILTER results, is important. Hebb Mind's graph search already follows this by adding to the candidate set, but the graph relevance scoring (`similarity = min(0.5 + 0.5 * (max_weight / max(max_weight, 5.0)), 0.9)`) is somewhat arbitrary and should be tuned.

### Temporal Validity on Knowledge Graph

MemPalace's `valid_from`/`valid_to` design on KG triples is simple and effective. Hebb Mind's graph currently uses NetworkX with co-occurrence edges but no temporal validity. Adding this would help temporal questions (currently 28.6%).

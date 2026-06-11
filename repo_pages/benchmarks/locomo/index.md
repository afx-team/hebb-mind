---
description: "LoCoMo results for AI agent memory: 95.75% session Recall@10 on 1,978 multi-session QA, MemPalace metric, via hybrid vector + keyword search and rerank."
---

# LoCoMo

[snap-research/locomo](https://github.com/snap-research/locomo) — multi-session conversations between two personas, 1,986 questions across single-hop, multi-hop, temporal, open-ended, and adversarial categories. Each conversation spans 19–32 sessions; questions test whether a memory system can surface facts that were established sessions earlier.

We report LoCoMo as **session-level Recall@10** — the same metric MemPalace publishes, so the numbers compare directly.

> **Production parity.** Ingestion calls the exact same Claude Code hook code path that fires in real usage (`src/hebb/integrations/claude_code/stop.py`, the per-turn capture hook), and retrieval goes through the same `/api/v1/search` endpoint that the MCP server, CLI, and Web Console use. The numbers below are what a user actually gets in production — not an idealised eval-only configuration. See [vs MemPalace](./vs-mempalace#production-parity-the-most-important-caveat) for how this contrasts with eval setups that diverge from their own production pipeline.

## Session-level Recall@10

No LLM at scoring time. The question is "did the retrieved set surface a memory tagged with any of the evidence sessions?". Ingestion mirrors the production Claude Code hooks (`integrations/claude_code/{write,stop}.py`): one memory per user utterance + one memory per turn round-trip with an ISO timestamp prefix, no chunking, no image captions. Search uses `prev_turns=2 / next_turns=2` context-window expansion, a date-proximity boost on query timestamps (`src/hebb/retrieval/temporal_boost.py`), and a general-English synonym group expander inside the FTS query builder (`src/hebb/retrieval/fts_query.py`). An **optional local cross-encoder rerank** pass (`src/hebb/retrieval/rerank/`, `BAAI/bge-reranker-base`) can be enabled on top.

### Embedding × rerank sweep (full 10 scenarios, 1,978q)

| Config | Embedding | Rerank | R@10 | Mean recall |
|---|---|---|---|---|
| **prod-mirror + rerank** | bge-large-1024 | bge-reranker-base | **95.75%** | 0.917 |
| prod-mirror + rerank | MiniLM-384 | bge-reranker-base | 94.69% | 0.902 |
| prod-mirror + rerank | e5-small-384 | bge-reranker-base | 94.44% | 0.903 |
| **prod-mirror (default)** | bge-large-1024 | — | **94.14%** | 0.899 |
| prod-mirror | e5-small-384 | — | 92.01% | 0.870 |
| prod-mirror | jina-v3-1024 | — | 92.01% | 0.870 |
| prod-mirror | MiniLM-384 | — | 91.41% | 0.865 |

Source: `eval/reports/locomo/matrix/<config>/locomo/v4/run-1/` and `eval/reports/locomo/matrix/SUMMARY.md`. Denominator is 1,978 not 1,986 because 8 questions carry empty/unparseable `evidence` (adversarial-by-design); per MemPalace convention they are excluded from the R@k denominator.

The shipped default (`bge-large-1024`, rerank off) scores **94.14%**. Enabling the optional cross-encoder rerank lifts it to **95.75%** — the best configuration.

### Rerank lift

| Embedding | No rerank | + rerank | Δ |
|---|---|---|---|
| bge-large-1024 | 94.14% | 95.75% | **+1.61 pp** |
| MiniLM-384 | 91.41% | 94.69% | **+3.28 pp** |
| e5-small-384 | 92.01% | 94.44% | **+2.43 pp** |

Rerank helps at every embedding tier, and helps the cheaper 384-dim embedders most — it nearly closes the embedding-capacity gap (MiniLM-384 + rerank, 94.69%, edges past bge-large-1024 with no rerank, 94.14%).

### Per-category (bge-large-1024 + rerank, headline)

| Category | R@10 |
|---|---|
| open_ended | 98.2% |
| adversarial | 97.3% |
| multi_hop | 94.1% |
| single_hop | 92.9% |
| temporal | 79.8% |

Temporal lags because LoCoMo "temporal" questions are largely inferential ("Would X be considered Y?") rather than time-anchored, so the date-proximity boost rarely fires; every other category is ≥ 92%.

## Per-competitor comparisons

- [vs MemPalace](./vs-mempalace) — same-metric R@10
- [vs mem0](./vs-mem0) — TBD (different judge / scoring; same-harness re-run pending)
- [vs Letta](./vs-letta) — TBD (no public LoCoMo result found)
- [vs Zep](./vs-zep) — same-metric QA: ~tied (Hebb ~74–78% vs Zep 75.14% on cat 1–4); Zep publishes no R@10

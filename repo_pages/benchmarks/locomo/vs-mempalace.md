# LoCoMo — Hebb Mind vs MemPalace

MemPalace publishes session-level Recall@k on the full 1,986 LoCoMo questions. Their metric and ours (see [LoCoMo](./)) are computed the same way: ground-truth `evidence` is parsed into a set of session_ids, the question counts as correct iff any GT session appears in the retrieved set (session-level **hit@10**).

## Production parity — the most important caveat

**Hebb Mind benchmarks call the same code paths as the shipped product.** The eval harness ingests every LoCoMo turn through the production Claude Code hooks (`src/hebb/integrations/claude_code/write.py` on each user prompt, `stop.py` on each turn round-trip): per-utterance memories with the same min-length filter and session-scoped dedupe; per-turn-pair summaries with the same `[<timestamp>] [<role>] …` formatting. Retrieval goes through the same `/api/v1/search` that Claude Code, the MCP server, and the Web Console all hit. **The 91.4% / 94.1% R@10 you see here is the R@10 a user actually gets in production** (94.1% on the shipped bge-large default, rerank off).

**MemPalace's benchmark does not call their production pipeline.** Our [source-level audit](https://github.com/afx-team/hebb-mind/blob/main/docs/analysis/mempalace-benchmark-deep-dive.md) of their repo finds three concrete divergences:

1. **Ingestion granularity** — the benchmark ingests one document per session (or per turn) of verbatim text; production chunks every memory into 800-character windows. Whole-session docs are much larger and more semantically coherent than the chunks a real user accumulates.
2. **Scoring pipeline** — production adds a "closet boost" (rank-based distance reduction `[0.40, 0.25, 0.15, 0.08, 0.04]` for boosted hits with cosine distance < 1.5), BM25 hybrid weighting, and neighbor-chunk enrichment. **None of these run in the benchmark.**
3. **Embedding flexibility** — production hard-codes ChromaDB's default (`all-MiniLM-L6-v2`) with no model swap; benchmark numbers sweep across MiniLM, bge-large, etc.

Quoting our audit verbatim: *"The production pipeline (closet boost, BM25 hybrid, neighbor expansion) was NOT tested in benchmarks. Benchmark numbers reflect the benchmark pipeline, not production search quality."*

This matters for the tables below: we are comparing **prod-mirror Hebb Mind** against **benchmark-only MemPalace**. The MemPalace numbers are a ceiling on what their evaluation harness produces, not a measurement of what their shipped system does.

## Headline — no rerank (R@10)

| System | R@10 | Embedding | Notes |
|---|---|---|---|
| **Hebb Mind (prod-mirror)** | **94.14%** | bge-large-1024 | Full 10 scenarios, 1,978q scored (8 adversarial excluded) |
| MemPalace bge-large hybrid | 92.40% | bge-large-1024 | Full 1,986q (MemPalace-published) |
| MemPalace MiniLM hybrid | 92.63% | MiniLM-384 | Full 1,986q (hit@10 recomputed from their released per-question data) |
| Hebb Mind (prod-mirror) | 91.41% | MiniLM-384 | Full 10 scenarios, 1,978q scored |

> A note on MemPalace's MiniLM number: their headline "88.9%" is *mean per-question recall* (`|GT ∩ retrieved| / |GT|`), not hit@10. Computed the same way as ours from their released data, the same run is **92.63% hit@10** (mean recall 0.889). We compare hit@10 to hit@10 throughout.

**Same-embedding deltas, no rerank** (the only honest comparison):

| Embedding | Hebb | MemPalace | Δ |
|---|---|---|---|
| bge-large-1024 | 94.14 | 92.40 | **+1.74 pp** |
| MiniLM-384 | 91.41 | 92.63 | **−1.22 pp** |

Without rerank we lead at the bge-large tier but trail slightly at MiniLM — MemPalace's BM25-hybrid is well tuned for the weaker 384-dim embedder. Our shipped default uses bge-large, where the prod-mirror 3-path RRF (date-proximity boost, general-English synonym expansion, prev/next-turn window) already leads.

## With rerank (R@10)

Hebb Mind now ships an optional **local cross-encoder rerank** (`BAAI/bge-reranker-base`, `src/hebb/retrieval/rerank/`) — no LLM API call, runs on CPU.

| System | R@10 | Rerank | Notes |
|---|---|---|---|
| MemPalace bge-large + Haiku rerank | 96.30% | LLM (Claude Haiku) | Full 1,986q (MemPalace-published) |
| **Hebb Mind bge-large + bge-reranker-base** | **95.75%** | local cross-encoder | Full 10 scenarios |
| Hebb Mind MiniLM + bge-reranker-base | 94.69% | local cross-encoder | Full 10 scenarios |

**Same-embedding deltas, with rerank:**

| Embedding | Hebb (+ rerank) | MemPalace (no rerank) | Δ |
|---|---|---|---|
| bge-large-1024 | 95.75 | 92.40 | **+3.35 pp** |
| MiniLM-384 | 94.69 | 92.63 | **+2.06 pp** |

The local cross-encoder lifts every embedding tier (bge-large +1.61, MiniLM +3.28, e5-small +2.43 pp) and reverses the MiniLM deficit — MiniLM + rerank (94.69%) now beats MemPalace's MiniLM hybrid by +2.06 pp and even edges past *our own* bge-large with no rerank (94.14%).

Against MemPalace's strongest published config (bge-large + **Claude Haiku** LLM rerank, 96.30%) we are **−0.55 pp** — and we close almost the entire gap with a free local cross-encoder instead of a per-query LLM call. (The previous version of this page reported −3.0 pp with "rerank not implemented; on roadmap"; it is now implemented.)

## Why the comparison is fair (and where it isn't)

Fair:
- Same metric (session-level hit@10 via evidence intersection), computed identically for both sides
- Same `top_k=10`
- Same dataset, **full 10/10 LoCoMo scenarios on both sides** (1,978 of 1,986 questions scored after excluding 8 with empty/unparseable evidence — same exclusion policy MemPalace uses)

Not strictly fair:
- We use prod-mirror per-utterance + per-pair memories (~875 memories per scenario, 8,755 total); MemPalace ingests one document per session (~19–32 documents per conversation). At equal top-k we search a much larger candidate pool, which is *harder* — but session granularity is what the metric scores at, so this favours their setup.
- MemPalace's bge-large and Haiku-rerank figures are their own published numbers (no per-question data released); only their MiniLM run could be recomputed on our exact metric.
- Embedding capacity explains the *absolute* score level, not the *gap*: the same-embedding deltas hold at both 384-dim and 1024-dim tiers.

## Source

[mempalace benchmark deep-dive §4](https://github.com/afx-team/hebb-mind/blob/main/docs/analysis/mempalace-benchmark-deep-dive.md) — source-code-level breakdown of MemPalace's hybrid v1–v5 pipeline, embedding sweep, LLM rerank schedule, and the benchmark-vs-production divergences that motivate the prod-parity callout above. Hebb Mind numbers: `eval/reports/locomo/matrix/SUMMARY.md`.

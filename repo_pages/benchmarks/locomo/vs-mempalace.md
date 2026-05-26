# LoCoMo — Hebb Mind vs MemPalace

MemPalace publishes session-level Recall@k on the full 1,986 LoCoMo questions. Their metric and ours (see [LoCoMo (a)](./)) are computed the same way: ground-truth `evidence` is parsed into a set of session_ids, the question counts as correct iff any GT session appears in the retrieved set.

## Production parity — the most important caveat

**Hebb Mind benchmarks call the same code paths as the shipped product.** The eval harness ingests every LoCoMo turn through the production Claude Code hooks (`src/hebb/integrations/claude_code/write.py` on each user prompt, `stop.py` on each turn round-trip): per-utterance memories with the same min-length filter and session-scoped dedupe; per-turn-pair summaries with the same `[<timestamp>] [<role>] …` formatting. Retrieval goes through the same `/api/v1/search` that Claude Code, the MCP server, and the Web Console all hit. **The 89.7% / 93.3% R@10 you see here is the R@10 a user actually gets in production.**

**MemPalace's benchmark does not call their production pipeline.** Our [source-level audit](https://github.com/afx-team/hebb-mind/blob/main/docs/analysis/mempalace-benchmark-deep-dive.md) of their repo finds three concrete divergences:

1. **Ingestion granularity** — the benchmark ingests one document per session (or per turn) of verbatim text; production chunks every memory into 800-character windows. Whole-session docs are much larger and more semantically coherent than the chunks a real user accumulates.
2. **Scoring pipeline** — production adds a "closet boost" (rank-based distance reduction `[0.40, 0.25, 0.15, 0.08, 0.04]` for boosted hits with cosine distance < 1.5), BM25 hybrid weighting, and neighbor-chunk enrichment. **None of these run in the benchmark.**
3. **Embedding flexibility** — production hard-codes ChromaDB's default (`all-MiniLM-L6-v2`) with no model swap; benchmark numbers sweep across MiniLM, bge-large, etc.

Quoting our audit verbatim: *"The production pipeline (closet boost, BM25 hybrid, neighbor expansion) was NOT tested in benchmarks. Benchmark numbers reflect the benchmark pipeline, not production search quality."*

This matters for the table below: we are comparing **prod-mirror Hebb Mind** against **benchmark-only MemPalace**. The MemPalace numbers below are a ceiling on what their evaluation harness produces, not a measurement of what their shipped system does.

## Headline (R@10, no LLM rerank)

| System | R@10 | Embedding | Notes |
|---|---|---|---|
| **Hebb Mind v0.1.1** | **93.3%** | bge-large-1024 | Full 10 scenarios, 1,978q scored (8 adversarial excluded) |
| MemPalace bge-large hybrid | 92.4% | bge-large-1024 | Full 1,986q |
| **Hebb Mind v0.1.1** | 89.7% | MiniLM-384 | Full 10 scenarios, 1,978q scored |
| MemPalace hybrid v5 | 88.9% | MiniLM-384 | Full 1,986q |

**Same-embedding deltas** (the only honest comparison):

| Embedding | Hebb | MemPalace | Δ |
|---|---|---|---|
| bge-large-1024 | 93.3 | 92.4 | **+0.9 pp** |
| MiniLM-384 | 89.7 | 88.9 | **+0.8 pp** |

The lead is consistent (~+0.9 pp) at both embedding tiers — i.e. the gain holds across embedding capacity, attributable to the retrieval pipeline (date-proximity boost, general-English synonym expansion, prev/next-turn window), not to a one-off advantage at any specific embedding model.

(A previous, smaller-sample run on 3 of 10 scenarios reported 92.7% with MiniLM; that headline number was over-optimistic and has been replaced with the full-coverage 89.7% above. The 3-scenario number is preserved in `eval/reports/locomo/v3/` history but not used for comparison.)

## With LLM rerank

| System | R@10 | LLM rerank | Notes |
|---|---|---|---|
| MemPalace bge-large + Haiku rerank | 96.3% | Yes | Full 1,986q |
| **Hebb Mind v0.1.1** (bge-large, no rerank) | **93.3%** | No | Full 10 scenarios |
| Hebb Mind + rerank | — | — | not implemented; on roadmap |

We are **−3.0 pp** behind MemPalace's reranked bge-large. Adding an LLM rerank pass into `MemorySearcher` is the cheapest known way to close it.

## Why the comparison is fair (and where it isn't)

Fair:
- Same metric (session-level R@k via evidence intersection)
- Same `top_k=10`
- Same dataset, **full 10/10 LoCoMo scenarios on both sides** (1,978 of 1,986 questions scored after excluding 8 with empty/unparseable evidence — same exclusion policy MemPalace uses)
- Neither system uses LLM at scoring time in this comparison

Not strictly fair:
- We use prod-mirror per-utterance + per-pair memories (~875 memories per scenario, 8,755 total); MemPalace ingests one document per session (~19–32 documents per conversation). At equal top-k we are searching a larger candidate pool, which is *harder* — but session granularity is what the metric scores at, so this favours their setup.
- The previous claim that "most of the remaining gap is embedding capacity" turned out to be wrong once we ran bge-large ourselves: the same-embedding delta is ~+0.9 pp at *both* tiers, so embedding capacity explains the *absolute* score level, not the *gap* between us and MemPalace.

## Source

[mempalace benchmark deep-dive §4](https://github.com/afx-team/hebb-mind/blob/main/docs/analysis/mempalace-benchmark-deep-dive.md) — source-code-level breakdown of MemPalace's hybrid v1–v5 pipeline, embedding sweep, LLM rerank schedule, and the benchmark-vs-production divergences that motivate the prod-parity callout above.

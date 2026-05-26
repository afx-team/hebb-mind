# LoCoMo

[snap-research/locomo](https://github.com/snap-research/locomo) — multi-session conversations between two personas, 1,986 questions across single-hop, multi-hop, temporal, open-ended, and adversarial categories. Each conversation spans 19–32 sessions; questions test whether a memory system can *answer* (not just *retrieve*) facts that were established sessions earlier.

We report LoCoMo two ways. Both share the same retrieval pipeline; they differ in what is being asked of it.

> **Production parity.** Ingestion calls the exact same Claude Code hook code paths that fire in real usage (`src/hebb/integrations/claude_code/write.py` + `stop.py`), and retrieval goes through the same `/api/v1/search` endpoint that the MCP server, CLI, and Web Console use. The numbers below are what a user actually gets in production — not an idealised eval-only configuration. See [vs MemPalace](./vs-mempalace#production-parity-the-most-important-caveat) for how this contrasts with eval setups that diverge from their own production pipeline.

## (a) Session-level Recall@10

No LLM at scoring time. The question is "did the retrieved set surface a memory tagged with any of the evidence sessions?". Ingestion mirrors the production Claude Code hooks (`integrations/claude_code/{write,stop}.py`): one memory per user utterance + one memory per turn round-trip with an ISO timestamp prefix, no chunking, no image captions. Search uses the new `prev_turns=2 / next_turns=2` context-window expansion plus a date-proximity boost on query timestamps (`src/hebb/retrieval/temporal_boost.py`) and a small general-English synonym group expander inside the FTS query builder (`src/hebb/retrieval/fts_query.py`).

| Hebb Mind config | Score | Source |
|---|---|---|
| **v0.1.1 prod-mirror, bge-large-1024, no rerank** | **93.3%** R@10 (1,978q, full 10 scenarios) | `eval/reports/locomo/v3/run-2/locomo.md` |
| v0.1.1 prod-mirror, MiniLM-384, no rerank | 89.7% R@10 (1,978q, full 10 scenarios) | `eval/reports/locomo/v3/run-1/locomo.md` |

Denominator is 1,978 not 1,986 because 8 questions carry empty/unparseable `evidence` (adversarial-by-design); per MemPalace convention they are excluded from the R@k denominator. Mean per-question recall is **0.889** under bge-large, **0.846** under MiniLM-384.

Per-category breakdown (bge-large, headline run):

| Category | R@10 |
|---|---|
| open_ended | 96.8% |
| adversarial | 93.3% |
| multi_hop | 91.6% |
| single_hop | 89.3% |
| temporal | 79.8% |

The +3.6 pp jump moving from MiniLM-384 to bge-large-1024 is concentrated in `open_ended` (+4.9) and `temporal` (+5.6) — categories where richer semantic embeddings rescue queries that the keyword path alone misses. Temporal still lags because LoCoMo "temporal" questions are inferential ("Would X be considered Y?") rather than time-anchored, so the date boost rarely fires.

## (b) End-to-end QA accuracy

Strictly harder than R@10 because the LLM must *produce* the answer, not just retrieve a candidate. Same retrieval pipeline plus a generation prompt + LLM-as-judge with semantic-equivalence rules (`eval/judge.py`).

| Hebb Mind config | Score | Source |
|---|---|---|
| **v0.1.1 raw + chunking + image captions, judge = Kimi-K2.5** | **90.3%** QA acc (497q, 3 scenarios) | `eval/reports/locomo/v1/run-1/locomo.md` |
| v0.1.1 consolidated, judge = Kimi-K2.5 | 37.6% QA acc (497q, 3 scenarios) | `eval/reports/locomo/v1/run-baseline/locomo.md` |

QA accuracy per category (90.3% run): open_ended 92.5, multi_hop 92.2, adversarial 91.1, single_hop 83.8, temporal 81.0. The +52.7 pp jump over the consolidated baseline (37.6% → 90.3%) is hybrid-retrieval-only — no change to the consolidation pipeline; see [the MemPalace benchmark lessons](https://github.com/afx-team/hebb-mind/blob/main/docs/analysis/mempalace-benchmark-deep-dive.md) for the recipe.

## Per-competitor comparisons

- [vs MemPalace](./vs-mempalace) — same-metric R@10
- [vs mem0](./vs-mem0) — TBD (different judge / scoring; same-harness re-run pending)
- [vs Letta](./vs-letta) — TBD (no public LoCoMo result found)
- [vs Zep](./vs-zep) — no public LoCoMo result; LongMemEval is their primary benchmark

# LoCoMo — Hebb Mind vs MemPalace

MemPalace publishes session-level Recall@k on the full 1,986 LoCoMo questions. Their metric and ours (see [LoCoMo (a)](./)) are computed the same way: ground-truth `evidence` is parsed into a set of session_ids, the question counts as correct iff any GT session appears in the retrieved set.

## Headline (R@10, no LLM rerank)

| System | R@10 | Embedding | Notes |
|---|---|---|---|
| MemPalace bge-large hybrid | 92.4% | bge-large-1024 | Full 1,986q |
| **Hebb Mind v0.1.1** | **89.7%** | MiniLM-384 | Full 10 scenarios, 1,978q scored (8 adversarial excluded) |
| MemPalace hybrid v5 | 88.9% | MiniLM-384 | Full 1,986q |

At the **same embedding model** (MiniLM-384) we are **+0.8 pp** over MemPalace's best non-rerank pipeline. The bge-large variant is still **−2.7 pp** ahead — a stronger embedding (1024-dim vs 384-dim) is doing real work that our date boost + synonym expansion don't fully replace.

(A previous, smaller-sample run on 3 of 10 scenarios reported 92.7%; that headline number was over-optimistic and has been replaced with the full-coverage 89.7% above. The 3-scenario number is preserved in `eval/reports/locomo/v3/` history but not used for comparison.)

## With LLM rerank

| System | R@10 | LLM rerank | Notes |
|---|---|---|---|
| MemPalace bge-large + Haiku rerank | 96.3% | Yes | Full 1,986q |
| Hebb Mind | — | — | not implemented; on roadmap |

We have not yet wired an LLM rerank pass into `MemorySearcher`. Adding one is the cheapest known way to close the remaining ~6.6 pp gap to MemPalace's reranked bge-large.

## Why the comparison is fair (and where it isn't)

Fair:
- Same metric (session-level R@k via evidence intersection)
- Same `top_k=10`
- Same dataset, **full 10/10 LoCoMo scenarios on both sides** (1,978 of 1,986 questions scored after excluding 8 with empty/unparseable evidence — same exclusion policy MemPalace uses)
- Neither system uses LLM at scoring time in this comparison

Not strictly fair:
- We use prod-mirror per-utterance + per-pair memories (~875 memories per scenario, 8,755 total); MemPalace ingests one document per session (~19–32 documents per conversation). At equal top-k we are searching a larger candidate pool, which is *harder* — but session granularity is what the metric scores at, so this favours their setup.
- MemPalace's bge-large hybrid uses a 1024-dim model trained on a more recent retrieval mixture than MiniLM-L6-v2. Most of the remaining gap is plausibly embedding capacity, not pipeline design.

## Source

[mempalace benchmark deep-dive §4](https://github.com/afx-team/hebb-mind/blob/main/reports/analysis/mempalace-benchmark-deep-dive.md) — source-code-level breakdown of MemPalace's hybrid v1–v5 pipeline, embedding sweep, and LLM rerank schedule.

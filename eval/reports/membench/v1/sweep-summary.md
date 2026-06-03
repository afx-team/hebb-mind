# MemBench full 11-category sweep — Hebb Mind vs MemPalace

**Config (all runs):** shipped default — `all-MiniLM-L6-v2` (384-d) embeddings + `BAAI/bge-reranker-base` cross-encoder rerank **ON**, raw mode (no consolidation), one memory per `[User] X [Assistant] Y` turn pair, per-scenario partitions, relevance-only search weights, **all topics** per category (movie/food/book/roles/events/multi_agent), `top_k=5`.

**Metric:** turn-level dual-key (sid ∪ global_idx) **Hit@k** — identical to MemPalace's protocol. MemPalace numbers are their published Recall@5 (movie topic, hybrid, top-5) from `docs/analysis/mempalace-benchmark-deep-dive.md`.

**Scale:** 11,996 questions, ~1.12M turn-pair memories ingested across the sweep.

| Category | n | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MemPalace@5 | Δ@5 |
|---|---|---|---|---|---|---|---|
| noisy | 1000 | 49.0% | 69.9% | **79.4%** | 89.3% | 43.4% | **+36.0pp** |
| conditional | 1000 | 53.0% | 75.5% | **86.0%** | 95.9% | 57.3% | **+28.7pp** |
| highlevel_rec | 1496 | 48.9% | 78.3% | **89.6%** | 99.1% | 76.2% | **+13.4pp** |
| post_processing | 1000 | 60.1% | 83.6% | **90.3%** | 97.2% | 56.6% | **+33.7pp** |
| knowledge_update | 1000 | 54.2% | 93.1% | 97.1% | 99.6% | 96.0% | +1.1pp |
| aggregative | 1000 | 91.6% | 98.0% | 99.1% | 99.9% | 99.3% | −0.2pp |
| simple | 1000 | 91.3% | 98.0% | 99.4% | 100.0% | 95.9% | +3.5pp |
| highlevel | 1500 | 61.1% | 96.1% | 99.7% | 100.0% | 95.8% | +3.9pp |
| RecMultiSession | 500 | 60.8% | 94.4% | 99.8% | 100.0% | — | — |
| lowlevel_rec | 1500 | 89.3% | 98.3% | 99.9% | 100.0% | 99.8% | +0.1pp |
| comparative | 1000 | 89.8% | 99.6% | 100.0% | 100.0% | 98.4% | +1.6pp |
| **OVERALL (n-weighted)** | **11996** | **68.2%** | **89.5%** | **94.6%** | **98.4%** | **80.3%** | **+14.3pp** |

**Takeaway.** Hebb Mind matches MemPalace on the easy categories (within ±4pp) and **wins decisively on all three of their hardest** — noisy +36.0pp, post_processing +33.7pp, conditional +28.7pp — plus highlevel_rec +13.4pp. The lever is the cross-encoder rerank: it pays off most exactly where verbatim-embedding retrieval collapses under distractors / conditional reasoning / post-processing. Overall **94.6% Hit@5 vs MemPalace's 80.3%** (note: our "all topics" mix and per-category n differ from their movie-topic ~8.5k-item mix, so per-category Δ is the cleaner comparison; the overall is same-methodology n-weighted).

## Per-category run mapping (in-tree reports)

| Category | Report |
|---|---|
| RecMultiSession | `eval/reports/membench/v1/run-6/` |
| noisy | `eval/reports/membench/v1/run-7/` |
| aggregative | `eval/reports/membench/v1/run-8/` |
| comparative | `eval/reports/membench/v1/run-9/` |
| knowledge_update | `eval/reports/membench/v1/run-11/` |
| post_processing | `eval/reports/membench/v1/run-12/` |
| simple | `eval/reports/membench/v1/run-13/` |
| conditional | `eval/reports/membench/v1/run-14/` |
| highlevel | `eval/reports/membench/v1/run-15/` |
| highlevel_rec | `eval/reports/membench/v1/run-16/` |
| lowlevel_rec | `eval/reports/membench/v1/run-17/` |

Regenerate this table: `.venv/bin/python eval/aggregate_membench_sweep.py --min-run 6`

## Methodology notes / gotchas

- **Per-category, not combined.** A single 1.12M-vector DB makes sqlite-vec brute-force the KNN per query (`partition_id` is a plain metadata column, not a PARTITION KEY shard) → 10–20 s/query. Each category runs in its own ≤~145k-vector DB to stay in the ~2 s/query regime. Sweep driver: `eval/run_membench_sweep.sh` + `eval/rerun_membench_missing.sh`.
- **Concurrency.** conditional + the grouped movie-cats run crashed/hung at search-concurrency 8 (suspected OOM: 16 GB box, ~2.2 GB server + 8 concurrent rerank buffers). Re-run at concurrency 4 — stable. Hit@k is concurrency-independent (stateless retrieval, `recall_strengthening` off), so conc-4 and conc-8 numbers are directly comparable.
- **Category keying.** 7 categories are `{roles, events}`-keyed, 3 are `{movie, food, book}`, RecMultiSession is `{multi_agent}`. Ran with `MEMBENCH_TOPIC=""` (all topics) so nothing is silently dropped (movie-topic-only filtering would drop RecMultiSession entirely).

---
description: "MemBench (ACL 2025) results for Hebb Mind AI agent memory: turn-level Hit@k across 11 categories, +14.3pp over MemPalace, cross-encoder rerank on hybrid retrieval."
---

# MemBench

[import-myself/Membench](https://github.com/import-myself/Membench) (ACL 2025) — multi-turn conversations across **11 categories** (simple, highlevel, knowledge_update, comparative, conditional, noisy, aggregative, highlevel_rec, lowlevel_rec, RecMultiSession, post_processing). Each conversation comes with 4-choice QA pairs whose `target_step_id` points at the specific turn(s) carrying the answer. We run the **full 11-category sweep** (all topics, 11,996 questions). MemPalace's hardest slice is `noisy` at 43.4 % Hit@5 — the most informative reverse window on the public leaderboard, and the one where our gap over them is largest.

> **Production parity.** Each item's `message_list` is ingested into a dedicated per-scenario partition as one memory per `[User] X [Assistant] Y` turn pair, with the dataset's `sid` and cross-session `global_idx` preserved on the memory's metadata. Retrieval goes through the same `/api/v1/search` the production system uses.

## How we evaluate

**Metric: turn-level Hit@k (dual-key).** For each question, retrieve top-k memories, collect both the `sid` and `global_idx` values they carry in metadata, and check whether any `target_step_id` (the dataset's integer pointer to the answer turn) appears in either set. A question is "correct" iff the intersection is non-empty. Dual-key matching is required because the dataset is inconsistent about which integer `target_step_id` points at — `sid` for some categories, `global_idx` for others. We report Hit@1 / Hit@3 / Hit@5 / Hit@10.

**Why this metric** — MemBench's ground truth (`target_step_id`) is a turn-level integer pointer, not a free-text answer. Hit@k is what the dataset's authors and MemPalace's own bench measure; the comparison vs. MemPalace's published Hit@5 is one-to-one.

We **do not** run an LLM judge on this dataset. The questions are 4-choice multiple-choice (A/B/C/D); even a system that retrieves no relevant turns will score 25 % by guessing, which would conflate retrieval failure with generation success and mask what the memory layer is actually doing.

## Hebb Mind on MemBench

**v0.1.6, prod-mirror** — `all-MiniLM-L6-v2` (384-d) embedding + `BAAI/bge-reranker-base` cross-encoder rerank (both shipped defaults), `top_k=5`, all 11 categories, all topics, 11,996 questions. Turn-level dual-key (sid ∪ global_idx) Hit@k.

| Category | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MemPalace Hit@5 | Δ@5 |
|---|---|---|---|---|---|---|
| noisy | 49.0% | 69.9% | **79.4%** | 89.3% | 43.4% | **+36.0 pp** |
| post_processing | 60.1% | 83.6% | **90.3%** | 97.2% | 56.6% | **+33.7 pp** |
| conditional | 53.0% | 75.5% | **86.0%** | 95.9% | 57.3% | **+28.7 pp** |
| highlevel_rec | 48.9% | 78.3% | **89.6%** | 99.1% | 76.2% | **+13.4 pp** |
| highlevel | 61.1% | 96.1% | 99.7% | 100.0% | 95.8% | +3.9 pp |
| simple | 91.3% | 98.0% | 99.4% | 100.0% | 95.9% | +3.5 pp |
| comparative | 89.8% | 99.6% | 100.0% | 100.0% | 98.4% | +1.6 pp |
| knowledge_update | 54.2% | 93.1% | 97.1% | 99.6% | 96.0% | +1.1 pp |
| lowlevel_rec | 89.3% | 98.3% | 99.9% | 100.0% | 99.8% | +0.1 pp |
| aggregative | 91.6% | 98.0% | 99.1% | 99.9% | 99.3% | −0.2 pp |
| RecMultiSession | 60.8% | 94.4% | 99.8% | 100.0% | — | — |
| **Overall (n-weighted)** | **68.2%** | **89.5%** | **94.6%** | **98.4%** | **80.3%** | **+14.3 pp** |

Source: `eval/reports/membench/v1/run-6` … `run-17` (one isolated run per category), aggregated in `eval/reports/membench/v1/sweep-summary.md` (regenerate with `eval/aggregate_membench_sweep.py --min-run 6`).

**The pattern is the rerank thesis.** Hebb matches MemPalace on the easy categories (within ±4 pp) and wins decisively on every hard one — **noisy +36.0 pp, post_processing +33.7 pp, conditional +28.7 pp, highlevel_rec +13.4 pp**. These are exactly the slices where verbatim-embedding retrieval collapses: distractors interleaved with signal, conditional reasoning, post-processing. The local cross-encoder re-scores the fused candidate pool and surfaces the answer turn that pure embedding similarity buries — the same lever behind our LoCoMo and LongMemEval results.

> **Why per-category, not one combined run.** sqlite-vec runs KNN as a brute-force scan over the whole vector table even with a `partition_id` filter (it's a metadata column, not a partition-key shard), so a single 1.12 M-vector database turns every query into a 10–20 s full scan. Each category therefore runs in its own ≤145 k-vector database, keeping partition-scoped search in the ~2 s/query regime. Hit@k is unaffected — retrieval is stateless and deterministic.

## Per-competitor comparisons

- **vs MemPalace** — head-to-head in the table above: same metric (turn-level Hit@5 vs `target_step_id`) and same MiniLM-384 embedding class. Hebb is **+14.3 pp overall** and **+13 to +36 pp on all four of MemPalace's hard categories**, at parity on the easy ones.

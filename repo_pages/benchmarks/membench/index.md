# MemBench

[import-myself/Membench](https://github.com/import-myself/Membench) (ACL 2025) — 1,000 multi-turn conversations per topic per category. Each conversation comes with 4-choice QA pairs whose `target_step_id` points at the specific turn(s) carrying the answer. We default to the `noisy` category on the `movie` topic — the slice where MemPalace's published number sits at 43.4 % Hit@5, the lowest of the 11 categories they tested. It is the most informative reverse window on the public leaderboard.

> **Production parity.** Each item's `message_list` is ingested into a dedicated per-scenario partition as one memory per `[User] X [Assistant] Y` turn pair, with the dataset's `sid` and cross-session `global_idx` preserved on the memory's metadata. Retrieval goes through the same `/api/v1/search` the production system uses.

## How we evaluate

**Metric: turn-level Hit@k (dual-key).** For each question, retrieve top-k memories, collect both the `sid` and `global_idx` values they carry in metadata, and check whether any `target_step_id` (the dataset's integer pointer to the answer turn) appears in either set. A question is "correct" iff the intersection is non-empty. Dual-key matching is required because the dataset is inconsistent about which integer `target_step_id` points at — `sid` for some categories, `global_idx` for others. We report Hit@1 / Hit@3 / Hit@5 / Hit@10.

**Why this metric** — MemBench's ground truth (`target_step_id`) is a turn-level integer pointer, not a free-text answer. Hit@k is what the dataset's authors and MemPalace's own bench measure; the comparison vs. MemPalace's published Hit@5 is one-to-one.

We **do not** run an LLM judge on this dataset. The questions are 4-choice multiple-choice (A/B/C/D); even a system that retrieves no relevant turns will score 25 % by guessing, which would conflate retrieval failure with generation success and mask what the memory layer is actually doing.

## Hebb Mind on MemBench

| Hebb Mind config | Hit@5 | Source |
|---|---|---|
| **v0.1.2 prod-mirror, bge-large-1024, noisy/movie** | **36.1%** (1,000 questions) | `eval/reports/membench/v1/run-4/membench.md` |

Full k-curve (same run):

| k | Hit@k |
|---|---|
| 1 | 30.2% |
| 3 | 36.1% |
| 5 | 36.1% |
| 10 | 36.2% |

Almost flat from k=3 onward — top-3 already captures the candidate pool the embedding can rank highly. The 30.2 → 36.1 jump from k=1 to k=3 is the only meaningful re-ranking lift; beyond that, misses are because the right turn never made it into the over-fetched candidate pool.

Currently noisy/movie only. The full 11-category sweep is on the roadmap; sweeping requires per-category download + 11 × 1,000 = 11,000 LLM-free ranking calls (~hour wall-clock on bge-large).

## Per-competitor comparisons

- [vs MemPalace](./vs-mempalace) — TBD (full vs-page pending; raw number above is already directly comparable)

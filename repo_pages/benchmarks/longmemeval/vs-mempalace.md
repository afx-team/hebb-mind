---
description: "Hebb Mind vs MemPalace on LongMemEval-S: same-metric session Recall@5 retrieval, same MiniLM-384 embedding. Hebb hits 99.0% R@5, 99.4% R@10, untuned."
---

# LongMemEval — Hebb Mind vs MemPalace

MemPalace and Hebb Mind both report **session-level Recall@5** on the full 500-question LongMemEval-S, computed the same way (does the top-k contain a memory from an evidence session?). MemPalace's benchmark is retrieval-only, so this is a clean, apples-to-apples retrieval comparison — same metric, same question set, same MiniLM-384 embedding.

| System | R@5 | Embedding | LLM rerank? | Notes |
|---|---|---|---|---|
| MemPalace raw | 96.6% | MiniLM-384 | No | Verbatim session docs |
| MemPalace hybrid v2 (temporal + 2-pass) | 98.4% | MiniLM-384 | No | |
| MemPalace hybrid v3 + Haiku rerank | 99.4% | MiniLM-384 | Yes | Tuned on the reported set |
| MemPalace hybrid v4 (held-out 450q) | 98.4% | MiniLM-384 | No | Honest non-overfit number |
| **Hebb Mind v0.1.6** | **99.0%** | MiniLM-384 | Yes (`bge-reranker-base`) | Production hook mirror, full 500 |

Hebb's **99.0% R@5** (R@10 99.4%, R@1 93.4%) sits at the top of MemPalace's range — matching its best hybrid+rerank configuration on the same MiniLM-384 embedding, and above its honest held-out figure (98.4%).

Source: Hebb `eval/reports/longmemeval/v3/run-14/longmemeval.md`; MemPalace [benchmark page](https://mempalaceofficial.com/reference/benchmarks.html).

## On overfitting

MemPalace's hybrid v1–v3 numbers were tuned on the same 500 questions they report; their held-out v4 (98.4% on 450 unseen) is the honest non-overfit figure. Hebb Mind does **not** train or tune on LongMemEval — there is no train/test split (we don't fit a model), so 99.0% is a single full-set run with default production settings (the same `hebb.json` a user gets out of the box).

## Beyond retrieval

MemPalace reports retrieval recall only. Hebb additionally runs the official end-to-end QA protocol — see the [main LongMemEval page](./) (79.0% with the neutral official reader) and [vs Zep](./vs-zep) / [vs Mem0](./vs-mem0) for the QA comparison.

# LongMemEval

[xiaowu0162/longmemeval-cleaned](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned) — 500 questions covering knowledge updates, multi-session reasoning, temporal reasoning, and three single-session variants. Designed to expose whether a memory system can locate and use facts inside long, time-ordered chat history.

## Hebb Mind on LongMemEval

| Hebb Mind config | Score | Source |
|---|---|---|
| **v0.1.1 consolidated, judge = Kimi-K2.5** | **33.3%** QA acc (3 questions, 3 scenarios) | `eval/reports/longmemeval/v1/run-1/longmemeval.md` |

Our LongMemEval slice is *too small to interpret* (3 questions). It exists to prove the harness works end-to-end. Increasing `--max-scenarios` is the first thing to do when reproducing. This row will be replaced once we have a `--max-scenarios=full` run.

## Per-competitor comparisons

- [vs MemPalace](./vs-mempalace) — published R@5
- [vs Zep / Graphiti](./vs-zep) — published R@5

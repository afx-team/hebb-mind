# LongMemEval — Hebb Mind vs MemPalace

MemPalace publishes Recall@5 with both raw and hybrid pipelines, plus an optional Haiku rerank pass.

| System | R@5 | Embedding | LLM rerank? | Notes |
|---|---|---|---|---|
| MemPalace raw (all-MiniLM-L6-v2) | 96.6% | MiniLM-384 | No | Verbatim session docs |
| MemPalace hybrid v1 (keyword overlap) | 97.8% | MiniLM-384 | No | |
| MemPalace hybrid v2 (temporal + 2-pass) | 98.4% | MiniLM-384 | No | |
| MemPalace hybrid v3 + Haiku rerank | 99.4% | MiniLM-384 | Yes | |
| MemPalace hybrid v4 (held-out 450q) | 98.4% | MiniLM-384 | No | Honest non-overfit number |
| **Hebb Mind v0.1.1** | — | BGE | — | Needs full-scenario run (current slice = 3 questions) |

Source: [mempalace benchmark deep-dive §4](https://github.com/afx-team/hebb-mind/blob/main/docs/analysis/mempalace-benchmark-deep-dive.md).

## Why we cannot publish a number yet

The 3-question slice (`eval/reports/longmemeval/v1/run-1/longmemeval.md`) is far below the statistical threshold to compare against MemPalace's 500. Until we have at least a 100-question run, this page intentionally leaves the Hebb Mind row blank rather than report a misleadingly precise number.

What we know structurally: every retrieval improvement that produced LoCoMo R@10 = 94.14% under bge-large (95.75% with the local cross-encoder rerank) and 91.41% under MiniLM-384 applies unchanged to LongMemEval ingestion. The hook ingestion path and search API are dataset-agnostic.

## Next step

`python -m eval run --dataset longmemeval --mode raw` (without `--max-scenarios`) generates the 500-question result. The run is bounded by judge latency, not retrieval — expect ~30–60 minutes with `concurrency=4` against a local Kimi-class model.

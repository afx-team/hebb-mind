---
description: "Hebb Mind vs Mem0 on LongMemEval: 79.0% QA with the untuned official reader plus 99.4% recall@10 shows Mem0's edge is reader-prompt engineering, not memory"
---

# LongMemEval — Hebb Mind vs Mem0

Mem0's headline LongMemEval metric is **end-to-end QA accuracy** (the official retrieve → generate → LLM-judge protocol). Mem0 does not publish session-level retrieval recall, so the head-to-head is on QA.

| System | QA accuracy | Reader LLM | Reader prompt |
|---|---|---|---|
| Mem0 | ~85–94%\* | gpt-4o / various | heavily engineered ([public](https://github.com/mem0ai/memory-benchmarks/blob/main/benchmarks/longmemeval/prompts.py)) |
| **Hebb Mind v0.1.6** | **79.0%** | DeepSeek-V4-Pro | neutral **official** reader |

\* Mem0's reported figure varies by source and setup — their own research reports ~93–94%; third-party reproductions land near ~85%.

## How to read this honestly

A same-number comparison is misleading here, for two reasons:

1. **Reader prompt does the heavy lifting.** Mem0's answer-generation prompt is public and *heavily* engineered — 13 numbered rules, a chain-of-thought scratchpad, and an explicit personalization / anti-abstention section. Hebb's 79.0% uses the **neutral official reader prompt** with zero benchmark tuning. We measured this lever directly on our own stack: swapping our restrictive reader prompt for the neutral official one moved **overall QA +12.4pp** and the **preference category +53pp**. Reader-prompt engineering alone moves the number by >10pp — independent of memory quality.

2. **Retrieval is not the bottleneck for Hebb.** Mem0 doesn't report retrieval recall; Hebb's is near-ceiling — **99.4% recall@10**, ahead of Zep's 95.5%. The evidence is almost always retrieved; what caps Hebb's QA is the (deliberately untuned) generation prompt, not the memory layer.

So Mem0's edge on this benchmark is **reader-prompt engineering, not memory quality.** We publish the untuned 79.0% as an honest floor; a comparably-engineered reader on top of Hebb's stronger retrieval (99.4% recall@10) would be expected to close the gap.

Sources: Hebb `eval/reports/longmemeval/v3/run-16` (QA) and `run-14` (retrieval); Mem0 [memory-benchmarks](https://github.com/mem0ai/memory-benchmarks), [research](https://mem0.ai/research).

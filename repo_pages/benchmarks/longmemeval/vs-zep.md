# LongMemEval — Hebb Mind vs Zep / Graphiti

LongMemEval is Zep's headline public benchmark. Zep reports **both** retrieval recall and end-to-end QA accuracy; Hebb Mind leads on both, on the same LongMemEval-S 500-question set.

## End-to-end QA accuracy

| System | QA accuracy | Reader LLM | Judge | Latency |
|---|---|---|---|---|
| **Hebb Mind v0.1.6** | **79.0%** | DeepSeek-V4-Pro | official `get_anscheck_prompt` | — |
| Zep | 71.2% | gpt-4o | official | 2.6s |
| _(full-context baseline)_ | 60.2% | gpt-4o | official | 29s |

Both follow the official LongMemEval QA protocol (retrieve → generate → per-type LLM judge). Hebb uses the **neutral official reader prompt** — no benchmark-specific tuning — so 79.0% is a floor, not a prompt-engineered ceiling.

## Retrieval recall

| System | R@1 | R@3 | R@10 |
|---|---|---|---|
| **Hebb Mind v0.1.6** | **93.4%** | **98.0%** | **99.4%** |
| Zep | 75.9% | 90.2% | 95.5% |

`recall_any@k` on the evidence sessions. Hebb is ahead at every depth, widest at rank 1 (+17.5pp) — i.e. when Hebb retrieves the right session it puts it at the top far more often.

## Split note

Both evaluate on **LongMemEval-S** — the standard 500-question set (`xiaowu0162/longmemeval`, file `longmemeval_s`, the ICLR 2025 release). (An earlier version of this page claimed we used a "cleaned/deduplicated derivative"; that was incorrect — it is the standard S set, the same one Zep's numbers are reported on.)

Sources: Hebb `eval/reports/longmemeval/v3/run-14` (retrieval) and `run-16` (QA); Zep [State of the Art Agent Memory](https://blog.getzep.com/state-of-the-art-agent-memory/).

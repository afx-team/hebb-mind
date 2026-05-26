# LoCoMo — Hebb Mind vs mem0

| System | Metric | Score | Source |
|---|---|---|---|
| **Hebb Mind v0.1.1** | QA accuracy (judge: Kimi-K2.5, 3-scenario slice) | 90.3% | [LoCoMo (b)](./) |
| **Hebb Mind v0.1.1** | Session R@10 (full 1,978q) | 89.7% | [LoCoMo (a)](./) |
| mem0 | LLM-as-judge "J" score | TBD | [mem0ai/mem0 README](https://github.com/mem0ai/mem0) |

## Why this row is TBD

mem0's published LoCoMo numbers use a different judge (typically GPT-4 / GPT-4o), a different generation prompt, and a different sampling protocol. Pulling their headline number and putting it next to ours would be misleading: a 5 pp swing on judge alone is common.

## What a fair comparison needs

To publish a same-row comparison, we need to:

1. Run mem0 through the Hebb Mind `eval/` harness so both systems use the same judge model, same generation prompt, and same ground-truth normalisation.
2. Run on the full 1,986-question set on both sides (our session-R@10 number already is; the QA-accuracy number is not yet).
3. Disclose mem0's version, embedding model, and consolidation settings.

This is on the roadmap. Open a PR if you have already done a same-harness mem0 run.

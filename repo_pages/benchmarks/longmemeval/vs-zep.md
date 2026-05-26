# LongMemEval — Hebb Mind vs Zep / Graphiti

LongMemEval is Zep's headline public benchmark. Their open-source successor, Graphiti, reports an R@5 number in their blog and on [getzep.com](https://www.getzep.com/).

| System | Metric | Score | Notes |
|---|---|---|---|
| Zep / Graphiti | R@5 | ">90%" (blog framing) | metric / split / judge details differ from the cleaned HuggingFace split |
| **Hebb Mind v0.1.1** | R@5 | — | Pending full-scenario run |

## Why this row is TBD

Zep's published numbers come from their internal evaluation harness on what looks like the original LongMemEval split. The HuggingFace `xiaowu0162/longmemeval-cleaned` we use is a deduplicated derivative; absolute numbers between the two splits are not directly comparable.

To put Hebb Mind in this table honestly we need to:

1. Run Hebb Mind on the cleaned 500-question split (Hebb side, pending).
2. Decide whether to also reproduce Zep on the cleaned split, since their public number is on the original.

## Source

Zep's Graphiti documentation: [https://help.getzep.com/](https://help.getzep.com/) (search "LongMemEval").

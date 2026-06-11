---
description: "LoCoMo AI agent memory benchmark: Hebb Mind hits 95.75% R@10 with hybrid vector + keyword recall; Letta (MemGPT) row is TBD, no first-party result."
---

# LoCoMo — Hebb Mind vs Letta

| System | Score | Source |
|---|---|---|
| **Hebb Mind** | 95.75% R@10 (bge-large + rerank) / 94.14% (bge-large default) / 91.41% (MiniLM-384), full 1,978q each | [LoCoMo](./) |
| Letta | TBD | No first-party LoCoMo result we could find in their public repo |

## Why this row is TBD

Letta (formerly MemGPT) does not publish a first-party LoCoMo result on their main repo or blog as of this writing. Third-party benchmarks have appeared but use ad-hoc judges and scenario counts.

To publish a same-row comparison, we would need to run Letta through the Hebb Mind `eval/` harness; see [vs mem0](./vs-mem0) for the same caveats.

Open a PR if Letta has since published a LoCoMo number that should be referenced here.

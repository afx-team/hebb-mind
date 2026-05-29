# LoCoMo — Hebb Mind vs Zep

| System | LoCoMo score | Metric | Source |
|---|---|---|---|
| **Hebb Mind** | 95.75% (bge-large + rerank) / 94.14% (bge-large default) / 91.41% (MiniLM-384), full 1,978q each | session-level **Recall@10** (no LLM at scoring time) | [LoCoMo](./) |
| **Hebb Mind** | **77.9%** (lenient judge) / **73.8%** (strict judge), cat 1–4 | end-to-end **QA accuracy** (LLM-as-judge) — same metric as Zep | [LoCoMo](./) |
| Zep | **75.14% ± 0.17**, cat 1–4 | end-to-end **QA accuracy** (J score) | [Zep blog](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/) |

## Same metric: end-to-end QA accuracy

Zep's 75.14% is a **J score** — an LLM-as-judge grades a *generated answer* against ground truth across LoCoMo categories 1–4 (the 446 adversarial questions excluded). That is exactly the metric and subset on which we also score Hebb Mind, so the two **are** comparable:

| System | cat 1–4 QA accuracy | Judge |
|---|---|---|
| **Hebb Mind** | **77.9%** | standard LoCoMo QA judge prompt (lenient) |
| **Hebb Mind** | **73.8%** | our own strict judge |
| Zep | **75.14% ± 0.17** | LoCoMo QA judge |

Read as a band, not a single point: **Hebb Mind lands at ~74–78% depending on judge strictness, Zep at 75.14%** — within noise of each other. Under the standard (more lenient) LoCoMo QA judge prompt, Hebb Mind's **77.9%** edges ahead; under our stricter judge it sits just below. This is *not* a controlled comparison — the answer-generation LLM differs (we used DeepSeek-V4-Pro) and the full QA pipelines were never run in one harness.

> **Caveat that dominates both numbers.** The LoCoMo LLM judge is documented to accept up to **~63% of intentionally wrong answers**, and the ground truth has ~99 wrong/misattributed gold answers ([dial481/locomo-audit](https://github.com/dial481/locomo-audit), via [MemPalace #29](https://github.com/MemPalace/mempalace/issues/29)). A ~1 pp gap on a metric with that error bar is not meaningful — treat Hebb Mind and Zep as **tied on LoCoMo QA**.

## Retrieval vs QA: why our headline is 95.75% but QA is ~77%

Our headline LoCoMo metric is **session-level Recall@10 = 95.75%** — did the retrieved set surface a memory from one of the evidence sessions? It scores *retrieval only*, no answer generated. The 18 pp gap between that and our QA accuracy is **not a retrieval gap** (retrieval is near-ceiling); it is the answer-generation model's reasoning — almost entirely LoCoMo's inferential `temporal` class (QA accuracy 33.7%, e.g. *"Would X be considered Y?"*) and `multi_hop` (64.5%). A J score is bounded by that reasoning; a recall number is not. So 95.75% R@10 and 77.9% QA describe the **same system on different axes**, and only the QA row is comparable to Zep's J score.

## About Zep's LoCoMo number

Zep's primary published benchmark is LongMemEval (Graphiti reports >90% R@5 there — see [LongMemEval — vs Zep / Graphiti](../longmemeval/vs-zep)). On **LoCoMo** specifically, Zep reports **75.14% ± 0.17** (J score) in a [blog post](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/). Treat it as a single-vendor self-reported figure produced inside a contested benchmark exchange — not a number we re-ran in our own harness.

## Bottom line

- **On end-to-end QA (the metric Zep publishes):** roughly **tied** — Hebb Mind ~74–78% vs Zep 75.14% on cat 1–4 — and the gap is well inside the LoCoMo judge's known error bar. We do not claim to beat Zep here.
- **On retrieval Recall@10 (our headline):** no comparison exists — Zep does not publish a LoCoMo recall number, and we have not re-run Zep through our harness. **Do not read 95.75% vs 75.14% as a head-to-head**; they are different axes.

If you have a same-harness Zep number (either a LoCoMo Recall@10, or Hebb Mind run through Zep's QA harness), open a PR.

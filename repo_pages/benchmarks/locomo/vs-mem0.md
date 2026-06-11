---
description: "Hebb Mind vs mem0 on LoCoMo: 95.75% retrieval Recall@10, and on mem0's own verbatim judge prompt our QA beats mem0's paper by +11pp on the same cat 1-4 set"
---

# LoCoMo — Hebb Mind vs mem0

Our headline LoCoMo metric is **session-level retrieval Recall@10** (no judge in the loop):

| System | Metric | Score | Source |
|---|---|---|---|
| **Hebb Mind** (bge-large + rerank) | Session R@10 (full 1,978q) | **95.75%** | [LoCoMo](./) |
| **Hebb Mind** (bge-large, default) | Session R@10 (full 1,978q) | 94.14% | [LoCoMo](./) |
| **Hebb Mind** (MiniLM-384) | Session R@10 (full 1,978q) | 91.41% | [LoCoMo](./) |
| mem0 | — | does not publish a retrieval-recall number | [mem0ai/mem0](https://github.com/mem0ai/mem0) |

mem0 publishes only **end-to-end QA accuracy scored by an LLM judge** (the "J score"), not retrieval recall — so there is no same-metric row for the table above. To compare on *their* metric we ran our own end-to-end QA on the identical question subset; that like-for-like is below, followed by why the QA number — on either side — is hard to trust.

## Like-for-like: same subset (cat 1–4), same metric (end-to-end QA)

mem0 evaluates **only LoCoMo categories 1–4** — the **446 adversarial questions are excluded** (their stated convention, "evaluation only on Categories 1–4", and the standard LoCoMo-QA practice, since category 5 is "the model should refuse" and has documented ground-truth problems). Subset = **~1,540 questions, not 1,986**.

To remove the judge as a confounder, we score **the same retrieved-and-generated answers two ways** on that subset.

**(a) Our own judge** (DeepSeek-V4-Pro, strict — for a list answer it requires all/all-but-one items):

| Hebb Mind end-to-end QA | Accuracy | Denominator |
|---|---|---|
| all categories | 77.0% | 1,986 |
| **categories 1–4 (mem0's subset)** | **73.8%** | 1,540 |
| adversarial only | 88.3% | 446 |

(Our all-category headline is propped up by adversarial, our strongest class; 73.8% is the comparable number.)

**(b) mem0's _exact_ judge prompt**, copied verbatim from [`benchmarks/locomo/prompts.py`](https://github.com/mem0ai/memory-benchmarks/blob/main/benchmarks/locomo/prompts.py) — a much more lenient rubric ("≥1 correct item from the gold list = CORRECT", dates within 14 days pass, paraphrases / extra detail / same-referent all pass):

| Hebb Mind, scored by mem0's judge prompt | cat 1–4 |
|---|---|
| **overall** | **77.9%** |
| multi-hop (cat 1) | 72.0% |
| temporal (cat 2) | 72.3% |
| open-domain (cat 3) | 34.4% |
| single-hop (cat 4) | 86.9% |

Swapping our judge for mem0's moves the number only **+4.1 pp** (73.8 → 77.9): their judge is more lenient, but that is *not* where the headroom is.

**(c) vs mem0's published numbers**, same subset, **same judge prompt**:

| System | cat 1–4 QA | judge | vs Hebb 77.9% |
|---|---|---|---|
| **Hebb Mind** (bge-large + rerank) | **77.9%** | mem0's, verbatim | — |
| mem0 — arXiv paper | 66.9% | mem0's | **Hebb +11.0 pp** |
| mem0 — graph (paper) | 68.4% | mem0's | **Hebb +9.5 pp** |
| mem0 — README / marketing | 91.6% | mem0's | mem0 +13.7 pp |

With mem0's **own judge prompt** on the **same 1,540-question subset**, our retrieval + answers beat mem0's **peer-reviewed paper** result by **+11 pp**. The only mem0 figure above us is the **README 91.6%**, and the judge does *not* explain that gap (matching it bought just +4 pp). It comes from two things, neither related to retrieval quality:

1. **mem0's 7-step chain-of-thought answer-generation prompt** (entity verification, temporal disambiguation, inclusion checks, …). We used a plain one-shot answer prompt; their generation harness is doing the heavy lifting.
2. **That 91.6% does not reproduce from mem0's public harness** (see next section).

Remaining caveat: the judge **model** still differs (we run DeepSeek-V4-Pro; mem0 runs GPT-4o-mini) — but the judge **prompt** is now byte-for-byte identical.

## Why the QA number — on either side — is hard to trust

**The leaderboard is contested by every participant.** Zep's audit, [*"Lies, Damn Lies, and Statistics: Is Mem0 Really SOTA in Agent Memory?"*](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/), found that a **full-context baseline (~73% J) beat mem0's best graph configuration (~68% J)** — i.e. *not using a memory system at all* scored higher, because LoCoMo conversations (~16k–26k tokens) fit in a modern context window. For balance: mem0 published a rebuttal arguing Zep misconfigured their system, and Zep's *own* 84% LoCoMo claim was separately audited down to 58.44% ([getzep/zep-papers #5](https://github.com/getzep/zep-papers/issues/5)).

**mem0's own numbers don't reproduce from the public harness.** [mem0 #3944](https://github.com/mem0ai/mem0/issues/3944) reports an LLM score of **~0.20** running their eval with GPT-4o-mini (traced to the platform stamping memories with the *current* date instead of dataset timestamps); [mem0 #2800](https://github.com/mem0ai/mem0/issues/2800) reproduces locally with scores "significantly lower than the ones I see in the paper."

**The LoCoMo ground truth itself is broken.** A public audit ([dial481/locomo-audit](https://github.com/dial481/locomo-audit), summarized in [MemPalace #29](https://github.com/MemPalace/mempalace/issues/29)) documents **~99 wrong/hallucinated/misattributed answers** across the ten conversations (honest ceiling ~93–94%, not 100%) and — decisively — that the **LoCoMo LLM judge accepts up to ~63% of intentionally wrong answers**. A judge that green-lights ~63% of deliberately wrong answers puts a large, systematic error bar on *every* LoCoMo J-score, mem0's and ours alike.

This is why we report **retrieval recall** as the headline: the ground truth is the `evidence` session set, scored by set intersection, with no judge in the loop.

## What a same-metric retrieval comparison would need

To put mem0 in the **R@10** table above we would:

1. Run mem0 through the Hebb Mind `eval/` retrieval-recall harness so both systems use session-level hit@10 via evidence intersection.
2. Run the full 1,978-question set on both sides (same exclusion policy used elsewhere on this site).
3. Disclose mem0's version and embedding model.

This is on the roadmap. Open a PR if you have already done a same-harness mem0 run.

## Sources

- Mem0 paper — [arXiv 2504.19413](https://arxiv.org/abs/2504.19413)
- mem0 judge + answer-generation prompts (used verbatim for the same-judge test) — [memory-benchmarks/benchmarks/locomo/prompts.py](https://github.com/mem0ai/memory-benchmarks/blob/main/benchmarks/locomo/prompts.py)
- Zep audit of mem0 — [blog.getzep.com](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/)
- Zep's own claim audited — [getzep/zep-papers #5](https://github.com/getzep/zep-papers/issues/5)
- mem0 reproducibility — [mem0 #3944](https://github.com/mem0ai/mem0/issues/3944), [mem0 #2800](https://github.com/mem0ai/mem0/issues/2800)
- LoCoMo ground-truth audit — [dial481/locomo-audit](https://github.com/dial481/locomo-audit), [MemPalace #29](https://github.com/MemPalace/mempalace/issues/29)
- Hebb Mind numbers — `eval/reports/locomo/matrix/SUMMARY.md` (retrieval), `eval/reports/locomo_qa/locomo-qa/v1/run-2/` (QA)

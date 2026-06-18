---
description: "Hebb Mind on PersonaMem: 69.4% on the 4-option multiple-choice personalization benchmark (589 questions, v1-32k) with raw top-10 retrieval + bge-reranker — above the ~50-52% full-context frontier oracle, vs a 25% random baseline."
---

# PersonaMem

[bowen-upenn/PersonaMem](https://huggingface.co/datasets/bowen-upenn/PersonaMem) — a **multiple-choice** personalization benchmark ([arXiv:2504.14225](https://arxiv.org/abs/2504.14225), "Know Me, Respond to Me", UPenn 2025). Each question places the model at a point in a long, evolving conversation with a simulated user and asks it to pick the **single best response out of four options** — the one consistent with the facts that user shared and how their preferences changed over time. We run the **v1 / 32k** split: 589 questions across 7 personalization "skills".

> **It is multiple-choice, not free-text QA.** Ground truth is a letter `(a)–(d)`; scoring is **exact-match on the chosen letter, with no LLM judge** — the same protocol the dataset authors use ("No LLM judges are involved in the evaluation process"). We run `mode=raw` (no consolidation) to isolate the retrieval layer.

## How we evaluate

For each question we isolate the user's conversation **up to the point the question is asked** — one Hebb partition per `(conversation, cut-point)` pair, holding exactly `turns[:end_index]`. Retrieval is restricted to that partition, so a question never sees future turns of the same user or any other persona's history. We then:

1. Retrieve the **top-10** memories for the question (`all-MiniLM-L6-v2` 384-d embedding + `BAAI/bge-reranker-base` cross-encoder rerank — both shipped defaults), via the same `/api/v1/search` endpoint the MCP server, CLI, and Web Console hit.
2. Give the reader those 10 memories + the question + the four options, and ask it to pick one letter (`DeepSeek-V4-Pro`, temperature 0).
3. Score **exact-match** on the parsed letter against the gold letter. No LLM judge, no free-text grading.

PersonaMem ships no per-question evidence id, so there is no Recall@k here — the headline is end-to-end **MCQ accuracy**.

## Reference points — read the number against these

PersonaMem is **hard**, and the right yardstick is *not* the 90%+ recall numbers from LoCoMo / LongMemEval (different task, different ceiling):

| Reference (v1-32k, full-context) | MCQ accuracy |
|---|---|
| Random baseline (4 options) | 25% |
| Best frontier LLMs — GPT-4.5 / GPT-4.1 / Gemini-1.5, **full 32k context** | **~50–52%** |
| Reasoning models (o1 / o3-mini / o4-mini / DeepSeek-R1) | no advantage (~50%) |
| Llama-4-Maverick | ~43% |

Source: [arXiv:2504.14225](https://arxiv.org/html/2504.14225v2) — frontier models "hover around 52% in a multiple-choice setting"; trimming the 128k context down to 32k by dropping irrelevant conversations gives no significant change, so the 32k oracle ≈ the 128k oracle.

## Hebb Mind on PersonaMem

**v0.1.7, production mirror** — `all-MiniLM-L6-v2` (384-d) + `BAAI/bge-reranker-base` rerank, `search_top_k=10`, `DeepSeek-V4-Pro` reader at temperature 0, 4-option MCQ exact-match, all 589 questions (v1-32k).

| Metric | Value | Source |
|---|---|---|
| **MCQ accuracy** | **69.4%** (409/589) | `eval/reports/personamem/v1/run-1/personamem.md` |

That clears the 25% chance baseline and sits **above the ~50–52% full-context frontier oracle** — while reading only the **top-10 retrieved memories**, not the full 32k conversation. The reading: for these questions, focused retrieval is enough to recover the relevant user history, consistent with the paper's own finding that dropping irrelevant context does not hurt accuracy.

### Per-skill breakdown

| Question type | Accuracy |
|---|---|
| recalling_the_reasons_behind_previous_updates | 88.9% |
| provide_preference_aligned_recommendations | 76.4% |
| recall_user_shared_facts | 74.4% |
| generalizing_to_new_scenarios | 73.7% |
| recalling_facts_mentioned_by_the_user | 70.6% |
| track_full_preference_evolution | 66.2% |
| **suggest_new_ideas** | **39.8%** |

The profile matches the dataset's difficulty curve: strongest on *recalling why a preference changed*, weakest on the generative/forward-looking *suggest new ideas* — the type the paper also flags as hardest (near chance for many frontier models). Errors correlate with low retrieval relevance: when the supporting turn falls outside the top-10, the reader picks a plausible-but-wrong option.

> **Comparability caveats.** (1) **Reader differs from the paper** — we use DeepSeek-V4-Pro; the ~50–52% oracle figures are GPT-4.5 / Gemini-1.5. So 69.4% is *not* a strict apples-to-apples "Hebb beats the oracle" claim — it reflects retrieval **plus** a strong reader. A same-reader full-context control would isolate retrieval's contribution. (2) **Dataset version** — this is PersonaMem **v1-32k (589 q)**, not the newer v2 (~5,000 q, different schema); never compare a v1 number against a v2 one. (3) **Infrastructure** — 8/589 (1.4%) questions hit an HTTP read-timeout on a loaded machine and were scored wrong; answered-question accuracy is **70.4%**. (4) `valid_choice_rate` = 98.6% (the reader returned a parseable letter on all non-errored questions).

## Per-competitor comparisons

The only first-party, version-pinned reference is the paper's full-context frontier oracle above (~50–52%). Some memory frameworks report PersonaMem numbers, but their **dataset version (v1 vs v2), question count, and reader/backbone are not pinned**, so they are not apples-to-apples with the table above and we list them only for orientation:

| System | Reported MCQ acc | Caveat |
|---|---|---|
| Hebb Mind (v0.1.7, DeepSeek-V4-Pro reader, top-10) | **69.4%** | v1-32k, 589 q, this page |
| Frontier oracle (GPT-4.5 / Gemini-1.5, full context) | ~50–52% | v1-32k, paper |
| EverMemOS / MemOS / Mem0 / Zep / memU | 53.2 / 50.7 / 43.9 / 43.4 / 38.7 | community-reported; version + backbone **unverified** |

Open a PR if you have a version-pinned public number to add.

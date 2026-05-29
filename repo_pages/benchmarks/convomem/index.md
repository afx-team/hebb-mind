# ConvoMem

[Salesforce/ConvoMem](https://huggingface.co/datasets/Salesforce/ConvoMem) — 75,336 evidence items across 6 categories (user facts, assistant facts, changing facts, abstention, preferences, implicit connections). Each item provides a multi-conversation haystack, a question, a free-text ground-truth answer, and the specific evidence messages from which the answer can be derived.

We evaluate on 600 items (100 per category × 6). MemPalace's published numbers use 250 items (50 per category × 5; they skip `changing_evidence`, whose HF tree has no `1_evidence/` slice). The Hebb run additionally covers `changing_evidence` by falling back to `2_evidence/` for that category — same items, same dataset, broader coverage.

> **Production parity.** Each item's conversation messages are ingested into a dedicated per-scenario partition, one memory per message (matching MemPalace's per-message setup so head-to-head ingestion is symmetric). Retrieval goes through the same `/api/v1/search` the production system uses.

## How we evaluate

**Metric: end-to-end QA accuracy with an LLM judge.** Retrieval brings top-k memories from the question's partition → the judge LLM (`eval/eval.json`'s `llm_model`, currently Kimi-K2.5 with thinking on) generates an answer using only those memories → the same LLM judges the generated answer against the dataset's ground-truth answer using the semantic-equivalence rules in `eval/judge.py`. A question is "correct" iff the judge returns `correct == true`.

**Why this metric** — ConvoMem's published metric is verbatim substring match between `message_evidences` text and retrieved memory contents. We deliberately do *not* report that number for Hebb because it does not measure what users actually care about:

1. **Production ingest is allowed to normalise text.** The `strip_noise` step in `hebb.ingest.noise` removes system tags and tool artifacts; a memory whose stored text differs from the evidence by even one character would score 0 on substring match even when the system clearly "remembers" the fact and can answer the question.
2. **The metric conflates retrieval and reformatting.** A successful system can summarise across multiple retrieved messages without surfacing the evidence verbatim. Substring match punishes synthesis, which is exactly what production-quality answering needs to do.
3. **End-to-end QA directly measures what production users get.** Did the system answer the user's question correctly? That is the only thing that matters.

We therefore use the same generate-then-judge loop (`eval/judge.py`), with the same judge prompt and the same semantic-equivalence rules.

## Hebb Mind on ConvoMem

| Hebb Mind config | QA accuracy | Source |
|---|---|---|
| **v0.1.2 prod-mirror, bge-large-1024, judge = Kimi-K2.5 (thinking on)** | **73.5%** QA acc (600 questions, all 6 categories) | `eval/reports/convomem/v3/run-1/convomem.md` |

Per-category breakdown:

| Category | QA accuracy |
|---|---|
| abstention_evidence | 99.0% |
| assistant_facts_evidence | 94.0% |
| user_evidence | 82.0% |
| changing_evidence | 76.0% |
| preference_evidence | 59.0% |
| implicit_connection_evidence | 31.0% |

`abstention_evidence` (99 %) is where the dataset asks for "I don't know" answers; our judge correctly accepts the system's refusals there. `implicit_connection_evidence` (31 %) is the structurally hardest category — the answer requires bridging two different conversation messages, and our 1-message-per-memory ingest doesn't synthesise the bridge. Closing that gap needs an LLM rerank or query rewrite pass, not more ingest-time rules.

Avg judge confidence on accepted-correct answers: 0.969 — the judge is decisive when it accepts, less so when it rejects (a common LLM-judge pattern). Avg retrieval latency (excludes LLM gen + judge time): 45.5 ms.

## Per-competitor comparisons

MemPalace's ConvoMem number is substring-match recall (92.9 % avg across 5 categories). It is not directly comparable to our QA accuracy — different metric, different question. Per the rationale above we do not include the substring number in our head-to-head: comparing QA accuracy against substring recall would be misleading in both directions.

If we ever publish a same-metric ConvoMem comparison, it will be:

- (a) An end-to-end QA run of MemPalace's pipeline against the same 600 questions through our harness, OR
- (b) Substring recall numbers from both systems on the same per-category sample, clearly labelled as "substring proxy, not QA quality."

Neither is published yet; we are not chasing the substring number for the reasons above.

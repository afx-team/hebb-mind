# LongMemEval

[xiaowu0162/longmemeval](https://huggingface.co/datasets/xiaowu0162/longmemeval) — 500 questions across six categories (knowledge updates, multi-session reasoning, temporal reasoning, single-session user / assistant / preference). Each question carries a long haystack of prior sessions; the dataset names the specific session(s) that contain evidence for the answer.

> **Production parity.** Ingestion calls the same Claude Code hook code paths that fire in real usage (`src/hebb/integrations/claude_code/{write,stop}.py`): one memory per user utterance, one memory per turn round-trip with an ISO timestamp prefix. Retrieval goes through the same `/api/v1/search` endpoint the MCP server, CLI, and Web Console hit. Each question's haystack is loaded into a dedicated per-scenario partition so retrieval is restricted to exactly that question's history — matching the fresh-haystack-per-item protocol the dataset assumes.

## How we evaluate

**Metric: session-level Recall@k.** For each question, retrieve top-k memories, collect the set of `session_id`s they carry in metadata, and check whether that set intersects the question's `answer_session_ids`. A question is "correct" iff `recall_any@k == 1.0`. We report R@1 / R@3 / R@5 / R@10 and NDCG@k. No LLM at scoring time.

**Why this metric** — LongMemEval ships a clean ground-truth field (`answer_session_ids`, the set of haystack sessions that contain evidence). That is the exact signal session-level R@k measures: did retrieval surface a memory from the right session? It is what the dataset's authors intended, and it makes the comparison vs. MemPalace's published R@5 numbers literally apples-to-apples — same metric, same question set, same k.

We **do not** run an LLM judge on this dataset because the dataset provides an unambiguous retrieval-level ground truth; adding a generator-then-judge stage would add LLM-induced noise that masks what the retrieval pipeline is actually doing. The point of LongMemEval, for us, is to isolate retrieval quality. End-to-end QA is what LoCoMo measures (see [LoCoMo (b)](../locomo/#b-end-to-end-qa-accuracy)).

## Hebb Mind on LongMemEval

| Hebb Mind config | R@5 | Source |
|---|---|---|
| **v0.1.2 prod-mirror, bge-large-1024** | **84.4%** R@5 (500 questions, all 6 categories) | `eval/reports/longmemeval/v2/run-3/longmemeval.md` |

Full k-curve (same run):

| k | R@k (any) | NDCG@k |
|---|---|---|
| 1 | 82.8% | 0.828 |
| 3 | 84.4% | 0.764 |
| 5 | 84.4% | 0.757 |
| 10 | 84.4% | 0.757 |

R@k is nearly flat from k=1 to k=10 — when retrieval hits, it hits at rank 1; when it misses, the right session isn't in the top-10 pool either. The bottleneck is base recall (which sessions the embedding+keyword paths can surface for a given query), not the re-ranking layer.

Per-category breakdown:

| Category | R@5 |
|---|---|
| single-session-assistant | 100.0% |
| knowledge-update | 96.2% |
| multi-session | 87.2% |
| single-session-user | 82.9% |
| temporal-reasoning | 79.7% |
| single-session-preference | 36.7% |

The `single-session-preference` floor (36.7%) is where abstract questions ("Can you suggest some accessories that would complement my current photography setup?") meet concrete user statements ("upgrade my camera flash", "getting a new tripod"). Zero token-level overlap → embedding similarity has nothing to bridge. Closing it requires LLM-driven query rewriting or rerank, not more lexical tricks.

## Per-competitor comparisons

- [vs MemPalace](./vs-mempalace) — same metric, full 500 questions
- [vs Zep / Graphiti](./vs-zep) — same metric, published R@5

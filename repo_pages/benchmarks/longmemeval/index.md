# LongMemEval

[xiaowu0162/longmemeval](https://huggingface.co/datasets/xiaowu0162/longmemeval) — 500 questions across six categories (knowledge updates, multi-session reasoning, temporal reasoning, single-session user / assistant / preference). Each question carries a long haystack of prior sessions; the dataset names the specific session(s) that contain evidence for the answer.

> **Production parity.** Ingestion calls the same Claude Code hook code paths that fire in real usage (`src/hebb/integrations/claude_code/{write,stop}.py`): one memory per user utterance, one memory per turn round-trip with an ISO timestamp prefix. Retrieval goes through the same `/api/v1/search` endpoint the MCP server, CLI, and Web Console hit. Each question's haystack is loaded into a dedicated per-scenario partition so retrieval is restricted to exactly that question's history — matching the fresh-haystack-per-item protocol the dataset assumes.

## How we evaluate

LongMemEval admits two very different metrics, and we report **both** — kept separate, because finding the evidence is necessary but not sufficient for answering correctly.

**1. Retrieval Recall@k — isolates the memory layer.** For each question, retrieve top-k memories, collect the `session_id`s they carry, and check whether that set intersects the question's `answer_session_ids`. A question is "correct" iff `recall_any@k == 1.0`; we report R@1 / R@3 / R@5 / R@10 and NDCG@k. No LLM at scoring time. This is exactly the signal LongMemEval's ground truth (`answer_session_ids`) encodes, and it is apples-to-apples with MemPalace's published R@k.

**2. End-to-end QA accuracy — the official LongMemEval metric.** Retrieve → generate an answer → an LLM judge grades it against the gold. This is what Zep and Mem0 report. To keep it comparable and untuned, we use the **official LongMemEval reader prompt** (`src/generation/run_generation.py`) and the **official per-question-type judge prompts** (`get_anscheck_prompt`) verbatim — no benchmark-specific prompt engineering — with DeepSeek-V4-Pro as both reader and judge.

> Recall@k asks "did we find the evidence?"; QA asks "did we answer correctly?". Even an oracle with *perfect* retrieval tops out near 82% QA (GPT-4o), so the two are not interchangeable. We lead with retrieval because it isolates the memory layer, and report QA for head-to-head parity with QA-first systems.

## Hebb Mind on LongMemEval

**v0.1.6, production mirror** — `all-MiniLM-L6-v2` (384-d) embedding + `BAAI/bge-reranker-base` cross-encoder rerank (both shipped defaults), `search_top_k=10`, full 500 questions across all 6 categories.

| k | R@k (any) | NDCG@k |
|---|---|---|
| 1 | 93.4% | 0.934 |
| 3 | 98.0% | 0.938 |
| 5 | **99.0%** | 0.941 |
| 10 | **99.4%** | 0.943 |

Source: `eval/reports/longmemeval/v3/run-14/longmemeval.md`. R@5 (99.0%) is the comparison-grade figure, matching the k MemPalace and Zep publish.

### Effect of cross-encoder reranking

Reranking is on by default in v0.1.6. Holding the ingested corpus and the embedding model fixed and toggling only the reranker:

| Config | R@1 | R@5 | R@10 |
|---|---|---|---|
| `all-MiniLM-L6-v2` only | 89.0% | 98.4% | 98.6% |
| `+ bge-reranker-base` | **93.4%** | **99.0%** | **99.4%** |

The lift concentrates at rank 1 (+4.4pp) and tapers as k grows — the expected signature of a reranker. Base recall already places the correct session inside the top-10 pool for ≥98% of questions, so the cross-encoder's job is mostly to promote it to the top: a precision-at-1 lever, not a recall lever.

### Per-category (R@10)

| Category | R@10 |
|---|---|
| knowledge-update | 100.0% |
| single-session-assistant | 100.0% |
| single-session-preference | 100.0% |
| single-session-user | 100.0% |
| multi-session | 99.2% |
| temporal-reasoning | 98.5% |

`single-session-preference` — abstract recommendation questions ("Can you suggest some accessories that would complement my current photography setup?") against concrete user statements ("upgrade my camera flash", "getting a new tripod"), with near-zero token overlap — used to be the floor of this benchmark. Retrieval there is now at ceiling: the production ingest mirror emits a short synthetic memory per preference phrase (matching `integrations/claude_code/stop.py`), restoring the query→corpus vocabulary overlap that raw embedding similarity could not bridge, and the reranker resolves the residual ordering.

## End-to-end QA accuracy

Same 500 questions, **official reader prompt + official per-type judge** (`get_anscheck_prompt`), DeepSeek-V4-Pro as reader and judge:

| Category | QA accuracy |
|---|---|
| single-session-user | 98.6% |
| single-session-assistant | 92.9% |
| knowledge-update | 80.8% |
| temporal-reasoning | 75.2% |
| single-session-preference | 70.0% |
| multi-session | 67.7% |
| **Overall** | **79.0%** (395 / 500) |

Source: `eval/reports/longmemeval/v3/run-16/longmemeval.md`. Zero judge failures (no API throttling).

This uses the **neutral official reader prompt**, not a benchmark-tuned one — so 79.0% is a *floor* for what the retrieval layer enables, not a prompt-engineered ceiling. It already lands within ~3pp of the GPT-4o oracle upper bound (82.4%, which assumes *perfect* retrieval), because Hebb's retrieval recall is near-ceiling (99.4% @10). For reference, our own restrictive reader prompt scored only 66.6% overall (and 16.7% on preference) — swapping in the neutral official prompt lifted overall +12.4pp and preference +53pp, confirming the gap was prompt over-abstention, not memory.

## Per-competitor comparisons

- [vs MemPalace](./vs-mempalace) — retrieval R@5 (same metric, full 500)
- [vs Zep / Graphiti](./vs-zep) — retrieval R@k **and** end-to-end QA
- [vs Mem0](./vs-mem0) — end-to-end QA accuracy

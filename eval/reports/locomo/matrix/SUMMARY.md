# LoCoMo Retrieval Matrix — embedding × rerank (session R@10)

Full 10 scenarios, 1,978 scored questions (8 empty-evidence adversarial excluded).
Metric: session-level Recall@10 (evidence-session intersection), same as MemPalace.
Mode: raw production-hook mirror (per-utterance + per-turn-pair ingest, 3-path RRF
+ prev/next-turn window). `--skip-qa` (retrieval only). Each config ran in an
isolated server (port 8401, `HEBB_HOME=workdir`); the 8321 daily service was never
touched.

## Results (ranked)

| config | embedding | rerank | hit@10 | mean R@k |
|---|---|---|---|---|
| **bge-large + rerank** | bge-large-en-v1.5 (1024) | bge-reranker-base | **95.75%** | **0.917** |
| minilm + rerank | all-MiniLM-L6-v2 (384) | bge-reranker-base | 94.69% | 0.902 |
| e5-small + rerank | multilingual-e5-small (384) | bge-reranker-base | 94.44% | 0.903 |
| bge-large, no-rerank | bge-large-en-v1.5 (1024) | — | 94.14% | 0.899 |
| e5-small, no-rerank | multilingual-e5-small (384) | — | 92.01% | 0.870 |
| jina-v3, no-rerank | jina-embeddings-v3 (1024) | — | 92.01% | 0.870 |
| minilm, no-rerank | all-MiniLM-L6-v2 (384) | — | 91.41% | 0.865 |
| bge-m3 (both) | bge-m3 (1024) | — | FAILED | — |

`bge-m3` hangs during ingest on this offline CPU box (XLM-RoBERTa-large fp32, no
GPU; db growth stalled, >17 min no progress). Dropped from the sweep.

## Rerank lift (bge-reranker-base, local cross-encoder)

| embedding | no-rerank | + rerank | Δ |
|---|---|---|---|
| bge-large-1024 | 94.14% | 95.75% | **+1.61pp** |
| MiniLM-384 | 91.41% | 94.69% | **+3.28pp** |
| e5-small-384 | 92.01% | 94.44% | **+2.43pp** |

Rerank helps at every tier, and helps the weaker 384-dim embedders most — it
nearly closes the embedding-capacity gap (minilm+rerank 94.69% ≈ bge-large
no-rerank 94.14%).

## vs MemPalace (published R@10, full 1,986q)

| system | hit@10 | mean R@k | embedding |
|---|---|---|---|
| **Hebb bge-large + rerank** | **95.75%** | 0.917 | bge-large-1024 |
| Hebb bge-large, no-rerank | 94.14% | 0.899 | bge-large-1024 |
| MemPalace bge-large hybrid | 92.40% | — | bge-large-1024 |
| Hebb MiniLM + rerank | 94.69% | 0.902 | MiniLM-384 |
| MemPalace hybrid | 92.63% | 0.889 | MiniLM-384 |
| Hebb MiniLM, no-rerank | 91.41% | 0.865 | MiniLM-384 |
| MemPalace raw | 64.93% | 0.602 | MiniLM-384 |

Same-embedding deltas (the honest comparison):

- **bge-large-1024**: Hebb 94.14% (no rerank) vs MemPalace 92.40% hybrid → **+1.74pp**;
  with rerank 95.75% → **+3.35pp**.
- **MiniLM-384**: Hebb 91.41% (no rerank) **−1.22pp** below MemPalace's tuned hybrid
  (92.63%) — our 3-path RRF slightly trails their BM25 hybrid at the weakest tier —
  but rerank flips it to 94.69% → **+2.06pp**.

Takeaway: Hebb's prod-mirror 3-path RRF already leads MemPalace at the bge-large
tier without any rerank; adding the local cross-encoder rerank widens the lead and
also lifts the cheap 384-dim embedders above MemPalace's hybrid. **bge-large +
bge-reranker-base is the best recall strategy** and is carried into the QA and
consolidation phases.

## End-to-end QA (LLM-as-judge, DeepSeek-V4-Pro) — best config

Ran `locomo-qa` on bge-large + bge-reranker-base (port 8407, concurrency 4).
Report: `eval/reports/locomo_qa/locomo-qa/v1/run-2/`.

| metric | value |
|---|---|
| **end-to-end QA accuracy** | **77.1%** (1526/1978) |
| session R@k cross-check | 95.8% (matches matrix 95.75% — same retrieval) |
| avg judge confidence | 0.943 |
| judge failures (API, scored 0) | 40 (~2%; true acc slightly higher) |

QA by category: adversarial 88.3%, open_ended 84.9%, multi_hop 64.5%,
single_hop 64.4%, temporal 33.7%. Temporal (relative-time resolution) is the
weakest; adversarial/open-ended are strongest.

Note: one of the five judge API keys (`…JaD4`) was dead ("服务未授权"); it was
pruned from `eval/eval.json` after this run. The judge model string also needed
the `openai/` provider prefix (`openai/DeepSeek-V4-Pro`) for litellm routing.

## Consolidation — best config, then re-eval

Ran `--mode consolidated --rebuild` on bge-large + rerank: ingest 8755 → LLM
consolidation (**1065/1065 tasks succeeded**, promoting working memories into
typed long-term partitions: preference/semantic/procedural/episodic) → re-eval.
Report: `eval/reports/locomo_consolidated/locomo/v4/run-1/`.

| metric | raw (best) | consolidated | Δ |
|---|---|---|---|
| session R@10 | 95.75% | 87.94% | **−7.81pp** |
| mean recall@k | 0.917 | 0.841 | −0.076 |
| **end-to-end QA** | **77.1%** | **57.6%** | **−19.5pp** |

Consolidated QA by category: adversarial 94.2%, open_ended 56.7%, single_hop
55.5%, temporal 39.3%, multi_hop **16.2%**.

**Finding: consolidation hurts LoCoMo fact-recall.** Merging/summarising
per-utterance memories into abstracted long-term entries destroys the granular,
verbatim detail that fact-recall QA depends on — multi-hop collapses (the linking
facts are summarised away), single-hop and open-ended drop ~20–30pp. Only the
adversarial ("no answer") class is unaffected/slightly up. This is consistent with
the known result that raw-mode hybrid retrieval far outperforms a consolidated
store on benchmark recall: consolidation optimises for long-term retention and
compression, not for maximal verbatim recall on a QA benchmark.

**Bottom line:** for LoCoMo-style fact recall, ship **raw retrieval with
bge-large + bge-reranker-base** (95.75% R@10 / 77.1% QA). Reserve consolidation
for its intended role (bounded long-term memory), not for benchmark QA.

## Isolation / hygiene (requirement: no 8321 pollution, no dup ingest)

Every run used an isolated server (ports 8401/8407, `HEBB_HOME=<workdir>`) with a
per-config wiped `hebb.db`; the 8321 daily `hebb _serve` service was verified
alive and untouched throughout. Ingest dedup is the production-hook mirror
(session-scoped SHA-256 on cleaned text), 8755 memories per full 10-scenario run.
A harness bug was fixed where orphaned eval servers (parent SIGTERM'd) survived
`lsof`-based cleanup and contaminated later configs with a stale model — the
matrix wrappers now kill by command pattern (`--port 8401`) and wait for the port
to free between configs.

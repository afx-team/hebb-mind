# Benchmarks

> **Status:** v0.1.2, work in progress. LoCoMo, LongMemEval, ConvoMem, and MemBench (all 11 categories) are full-coverage; PersonaMem is still a small-sample slice and clearly flagged on its page. Treat PersonaMem as smoke, the other four as real baselines we are committing to improve in the open.

Hebb Mind ships a reproducible eval harness at `eval/` so you (and we) can re-run every number on your own hardware and your own LLM. This page documents what we measure today, what we don't, and how to run it.

> **Production-parity by construction.** Every benchmark in this section drives the same ingestion + retrieval code paths that ship to production — the Claude Code hooks (`write.py` / `stop.py`), the MCP server, and `/api/v1/search`. We never run an eval-only ingestion or scoring pipeline. The numbers are what a user gets, not what an idealised harness gets. Where competitor systems run *different* pipelines in their benchmarks vs production, we call it out on the per-competitor page (see e.g. [LoCoMo vs MemPalace](./locomo/vs-mempalace#production-parity-the-most-important-caveat)).

## Layout

This section is split **dataset first, then per-competitor**. Each dataset has its own folder; inside the folder, the `index` page shows Hebb Mind's own configuration and result, and each `vs-<project>` page covers one same-dataset comparison.

- [LoCoMo](./locomo/) — multi-session conversational QA (session R@k + end-to-end QA)
  - [vs MemPalace](./locomo/vs-mempalace) — same-metric R@10
  - [vs mem0](./locomo/vs-mem0) — TBD (same-harness re-run pending)
  - [vs Letta](./locomo/vs-letta) — TBD
  - [vs Zep](./locomo/vs-zep) — no public LoCoMo number
- [LongMemEval](./longmemeval/) — long-horizon recall (session R@k)
  - [vs MemPalace](./longmemeval/vs-mempalace) — published R@5
  - [vs Zep / Graphiti](./longmemeval/vs-zep) — published R@5
- [ConvoMem](./convomem/) — 6-category evidence retrieval (end-to-end QA judge)
- [MemBench](./membench/) — turn-level retrieval, all 11 categories (Hit@k)
- [PersonaMem](./personamem/) — preference tracking; few public comparisons yet

## What gets measured

Each benchmark exercises a different slice of the memory lifecycle. The diagram below shows where:

```mermaid
flowchart LR
    A[Conversation turns] -->|ingest| B[(Memory store)]
    B -->|consolidate| C[(Consolidated memories)]
    C -->|hybrid search| D[Top-k retrieval]
    D -->|LLM judge| E[Answer + correctness]

    classDef probe fill:#fde68a,stroke:#92400e,color:#1f2937;
    P1[LoCoMo<br/>multi-session QA]:::probe -.probes.-> D
    P2[LongMemEval<br/>long-horizon recall]:::probe -.probes.-> D
    P3[PersonaMem<br/>preference tracking]:::probe -.probes.-> C
```

LoCoMo, LongMemEval, ConvoMem, and MemBench probe the *retrieval + answering* stage; PersonaMem stresses *consolidation* (does the right preference survive a rewrite?). Where we use an LLM judge, absolute numbers move with the judge model — we record it in every report.

## How we score

Picking the right metric per dataset matters more than picking one metric for everything. We use three scoring modes, **one per dataset**, chosen to match what the dataset's ground truth actually looks like:

| Dataset | Metric | Why this metric |
|---|---|---|
| [LoCoMo](./locomo/) | **Session R@k** | Evidence is session-tagged (`evidence: ["D1:3", ...]`) → R@k is the dataset's native signal: did retrieval surface a memory from an evidence session? |
| [LongMemEval](./longmemeval/) | **Session R@k** | Ground truth is `answer_session_ids` — a clean set of session ids. R@k is exactly what the dataset's authors intended; an LLM judge would add noise without measuring anything different about retrieval. |
| [ConvoMem](./convomem/) | **End-to-end QA judge** | Ground truth is a free-text answer. The dataset's published substring-match-on-evidence metric is a noisy proxy that punishes any normalisation; we deliberately do NOT report it. See [the ConvoMem page](./convomem/#how-we-evaluate) for the full rationale. |
| [MemBench](./membench/) | **Turn-level Hit@k** | Ground truth is a turn-index pointer (`target_step_id`). The questions are 4-choice multiple choice → an LLM judge would score 25 % from random guessing alone, conflating retrieval failure with generation luck. |
| [PersonaMem](./personamem/) | **End-to-end QA judge** | Ground truth is a free-text rewrite of an evolving preference; no clean retrieval-level identifier to match against. |

Definitions:

- **Session R@k / Hit@k** — no LLM at scoring time. The question counts as correct iff at least one ground-truth identifier (session id or turn id) appears in the retrieved set's metadata. We also report NDCG@k where the dataset's authors do.
- **End-to-end QA** — retrieve top-k → judge LLM generates an answer using only those memories → same LLM judges the answer against the ground truth using the semantic-equivalence rules in `eval/judge.py`. `is_correct ∈ {0, 1}`. Accuracy is the mean.
- **Avg latency** — wall-clock retrieval time; excludes judge time.
- **avg_top1_relevance** — mean of `relevance_score` from `/api/v1/search` for the top result; directional only.
- **Accuracy by category** — per the dataset's own taxonomy.

Both `temperature` and `top_p` are recorded in every report's config block, so a reviewer can recompute determinism bounds.

## How to reproduce

The harness is a single CLI. From a checkout of the repo:

```bash
# 1. Install dev deps and the benchmark extras
pip install -e ".[eval]"

# 2. Set the judge model (any LiteLLM-supported provider works)
export HEBB_LLM_API_KEY=sk-...
export HEBB_LLM_MODEL=openai/gpt-4o-mini   # or your local Qwen/Kimi/etc.

# 3. Download the datasets you want
python -m eval download --dataset locomo
python -m eval download --dataset longmemeval
python -m eval download --dataset personamem

# 4. Run a benchmark — the harness boots a fresh Hebb Mind server,
#    ingests the conversations, optionally consolidates, then evaluates.
python -m eval run --dataset locomo --mode consolidated --max-scenarios 3
python -m eval run --dataset longmemeval --mode consolidated --max-scenarios 3
python -m eval run --dataset personamem --mode raw --max-scenarios 3

# 5. Reports land under eval/reports/<benchmark>/<eval_version>/run-<N>/<benchmark>.{md,json}
#    eval_version comes from the benchmark class (bumped only when the
#    methodology changes — chunking, scoring metric, etc.). Successive
#    runs of the same protocol pile up as run-1, run-2, ... — no dates
#    in the path, on purpose.
ls eval/reports/locomo/v3/

Drop `--max-scenarios` to run the full dataset. Use `python -m eval list` to see what's available and what's already downloaded; `python -m eval run --dataset all` runs every benchmark in sequence.

The runner cleans the database between benchmarks so results are independent. It does *not* clean between modes — re-run with a different `--mode` and the harness will start a fresh server.

## Honest gaps

- We do **not** publish first-party comparisons against mem0 / Letta / Zep yet. Their harnesses, judges, and scenario counts differ; a fair head-to-head requires re-running each system through *the same* harness, which is on the roadmap.
- The judge is `openai/Kimi-K2.5` for our QA-mode numbers; switching judges shifts absolute accuracy by several points. Always disclose the judge.
- Embedding model dimension (384 vs 1024) is a known confounder — the [mempalace deep-dive](https://github.com/afx-team/hebb-mind/blob/main/docs/analysis/mempalace-benchmark-deep-dive.md) shows ~16 pp swings on LoCoMo single-hop. We default `setup` to BGE; the harness inherits whatever your `hebb.json` specifies.
- We deliberately do not chase MemPalace's ConvoMem substring-match number. See [the ConvoMem page](./convomem/#how-we-evaluate) for why.

If you reproduce on different hardware / a different judge / a larger sample, please open a PR adding a row to the relevant page — that's the fastest way to make these numbers trustworthy.

# Evaluation harness (`eval/`)

A reproducible benchmark harness for Hebb Mind's retrieval and memory quality. Every benchmark runs against an **isolated, ephemeral Hebb Mind server** (its own port, workdir, and `hebb.db`) and drives the **same production code paths** a real user hits — the Claude Code ingest hooks (`integrations/claude_code/{write,stop}.py`) and the `/api/v1/search` endpoint. The numbers are what ships, not an eval-only pipeline.

> **Two homes, on purpose.** This README is the **contributor/operator guide** — what we measure, how to run it, how reports are laid out. The **user-facing** result pages (headline numbers + framework comparisons) live in `repo_pages/benchmarks/` and are published to the docs site. Keep methodology/regeneration notes here; keep polished results there.

## Datasets & metrics

Pick the metric that matches each dataset's ground truth — don't default to LLM-judged QA when a clean retrieval-level identifier exists.

| Dataset | `--dataset` | Metric | `eval_version` | Notes |
|---|---|---|---|---|
| LoCoMo | `locomo` | session **Recall@k** | v4 | evidence is session-tagged; 1,986 q (1,978 scorable) |
| LoCoMo (QA) | `locomo-qa` | end-to-end **QA** | v1 | same retrieval, adds generate + judge |
| LongMemEval | `longmemeval` | session **Recall@k** + end-to-end **QA** | v3 | 500 q; QA uses the official reader + `get_anscheck_prompt` judge |
| LongMemEval (session-doc) | `longmemeval-session` | session **Recall@k** | v1 | one verbatim doc per session variant |
| ConvoMem | `convomem` | end-to-end **QA** judge | v3 | free-text answers; we deliberately skip the noisy substring metric |
| ConvoMem (substring) | `convomem-substring` | substring match | v1 | the dataset's own (noisy) metric, for reference |
| MemBench | `membench` | turn-level **Hit@k** | v1 | ground truth is a turn pointer (`target_step_id`); MCQ → no LLM judge |
| PersonaMem | `personamem` | end-to-end **MCQ accuracy** | v1 | 589 q, 4-option (chance 25%); one partition per `(context, end_index)` cut point; exact-match on the chosen letter, **no LLM judge** |
| MemoryArena | `memoryarena` | — | — | dataset adapter only; not in the runnable set |

`eval_version` is **sticky per methodology** and lives on the benchmark class. Bump it only when the protocol changes (chunking, scoring metric, ingest mirror) — never per run.

## How to run

```bash
# 1. install eval extras
pip install -e ".[eval]"

# 2. judge-LLM credentials — eval/eval.json (model, base_url, api keys, concurrency,
#    search weights). User-provided; do NOT commit real keys. Env overrides: HEBB_LLM_*.

# 3. download a dataset
python -m eval download --dataset longmemeval

# 4. run (writes a fresh report under eval/reports/...)
python -m eval run --dataset longmemeval --mode raw --top-k 10

python -m eval list   # what's available / downloaded
```

**Retrieval config is inherited from your `~/.hebb/hebb.json`** (or a project-root `hebb.json`) via `prepare_workdir` — so the eval matches what you ship. Shipped default: `all-MiniLM-L6-v2` (384-d) + `bge-reranker-base` rerank.

Useful flags on `run`:

- `--mode raw` (no consolidation; always wipes + re-ingests) · `--mode consolidated` (runs consolidation; reuses the db unless `--rebuild`).
- `--skip-qa` — retrieval `Recall@k` only (fast); omit it to also run end-to-end QA.
- `--enable-rerank / --disable-rerank`, `--rerank-model` — override the inherited rerank setting without touching your config.
- `--disable-vector / --disable-fts5 / --disable-graph-search / --disable-lexical-boost / --disable-temporal-boost / --disable-graph-expand` — 3-way-RRF + boost ablations.
- `--max-scenarios N` (+ `--scenario-offset`) — smoke subset / fixed-size batches.

**Isolation (important).** Each benchmark gets its own port (`eval.client.BENCHMARK_PORTS`, `8401–8409`) and its own `eval/workdirs/<name>-<mode>/` (dedicated `hebb.json` + `hebb.db`). The harness pins the server's `HEBB_HOME` to that workdir and **never touches the daily `hebb service` on 8321**. `recall_strengthening_enabled` is forced **off** during eval so retrieval is a fixed snapshot (query order can't perturb scores).

### LongMemEval QA specifics

The QA path follows the official LongMemEval protocol verbatim, so the number is comparable to the leaderboard / Zep / Mem0:

- **Reader** — `LLMJudge.generate_answer_official`, the neutral official `run_generation.py` prompt (no benchmark-specific tuning). Our tuned `_GENERATE_PROMPT` is kept for LoCoMo/ConvoMem.
- **Judge** — `LLMJudge.judge_anscheck`, a verbatim port of `get_anscheck_prompt`: per-question-type grading (preference→rubric, temporal→off-by-one tolerated, knowledge-update→updated value, abstention→`_abs` question ids).

## Reports — layout & how to update

Reports are written to:

```
eval/reports/<benchmark>/<eval_version>/run-N/<benchmark>.{md,json}
```

- `run-N` auto-increments (highest existing + 1) — **no dates in the path**; stacked runs of the same protocol. Cleanup is the operator's call.
- The **JSON** carries per-question `individual_results` + `retrieval_metrics` (`recall_any@k`, `ndcg@k`, `qa_accuracy[_<category>]`); the **MD** is the human-readable summary with the config block.

**To refresh a published number:**

1. Re-run the benchmark → a new `run-N`.
2. Update the figure **and** the `Source:` path in the relevant `repo_pages/benchmarks/<dataset>/*.md` — **and its `zh/` mirror** (per-language pages; don't mix languages in one file).
3. **Commit the referenced `run-N` report** alongside the doc change — public pages cite the report path, so it must be in-tree to resolve. Intermediate/smoke runs stay untracked.

## Adding a benchmark

1. Adapter in `eval/datasets/` producing `EvalScenario` / `EvalQuestion`; register in `ADAPTERS`.
2. Benchmark in `eval/benchmarks/` subclassing `BaseBenchmark` (set `dataset_name`, `eval_version`); register in `BENCHMARKS`.
3. Allocate a port in `eval.client.BENCHMARK_PORTS`.
4. Choose the metric from the table above by what the dataset's ground truth actually is.

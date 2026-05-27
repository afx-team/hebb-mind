# Evaluation Run Plan — May 2026

> **Scope:** add LongMemEval, ConvoMem, and MemBench (noisy-priority) to
> the public benchmark coverage and produce honest vs-MemPalace tables
> for each. Internal-only doc — do not publish to `repo_pages/`.

## Why now

Hebb Mind currently publishes one full-coverage MemPalace comparison
(LoCoMo, `repo_pages/benchmarks/locomo/vs-mempalace.md`) plus a 3-question
LongMemEval stub. MemPalace publishes numbers on **4** datasets
(deep-dive §2: LongMemEval, LoCoMo, ConvoMem, MemBench). Three of those
have no Hebb counterpart yet, so the public story is "we beat them at the
one dataset we picked." This plan closes the gap by running the three
missing datasets through the same prod-parity harness that LoCoMo uses.

## Run isolation (this PR)

Each benchmark runs against its **own** hebb server: own port, own
workdir, own `hebb.db`, own `hebb.json`. The user's project-root
`hebb.json` and `hebb.db` are **never** touched during eval — only
read once at workdir-provisioning time to inherit embedding settings.

| Benchmark | Port | Workdir |
|---|---|---|
| locomo      | 8321 | `eval/workdirs/locomo/` |
| longmemeval | 8322 | `eval/workdirs/longmemeval/` |
| convomem    | 8323 | `eval/workdirs/convomem/` |
| membench    | 8324 | `eval/workdirs/membench/` |
| personamem  | 8325 | `eval/workdirs/personamem/` |
| memoryarena | 8326 | `eval/workdirs/memoryarena/` |

Per-benchmark loop:
1. `prepare_workdir(name, workdir_root, project_root)` — writes a
   fresh `hebb.json` into the workdir (host=0.0.0.0, port=allocated,
   embedding settings inherited from project root).
2. `stop_server(port)` — kill any orphan on that port.
3. `clean_storage(workdir)` — delete the workdir's `hebb.db` (+ WAL/SHM)
   and `knowledge_graph.json`. **Workdir itself is kept** so other
   files (logs, the rewritten `hebb.json`) survive.
4. `start_server(workdir)` with `HEBB_HOME=workdir` so the server
   reads the workdir's `hebb.json` and writes to the workdir's `hebb.db`.
5. `HebbClient("http://localhost:{port}")` for ingest + search.
6. After the dataset finishes, the **next** loop iteration stops this
   server before spinning up its own.

Sequential by design — only one server runs at a time. To inspect what
a benchmark actually ingested, just open `eval/workdirs/<name>/hebb.db`
after the run; nothing is wiped until that benchmark is re-run.

## What just landed (PR scope, this conversation)

| File | Purpose |
|---|---|
| `eval/client.py`               | New `prepare_workdir()` + `BENCHMARK_PORTS`; per-benchmark isolation |
| `eval/cli.py`                  | `run` loop swaps server per dataset; dropped `--url` flag |
| `eval/config.py`               | New `workdir_root` field; dropped `hebb_url` (now derived from port) |
| `eval/datasets/longmemeval.py` | Rewritten — surfaces `answer_session_ids` on `EvalQuestion.metadata` |
| `eval/datasets/convomem.py`    | Rewritten against the real `Salesforce/ConvoMem` evidence-questions schema |
| `eval/datasets/membench.py`    | New — pulls `import-myself/Membench` category JSONs from raw.githubusercontent |
| `eval/datasets/base.py`        | `ConversationTurn` gains optional `metadata: dict` (MemBench `sid`/`global_idx`) |
| `eval/benchmarks/longmemeval_bench.py` | Standalone — prod-hook ingest, session-level R@k (1/3/5/10) + NDCG@k |
| `eval/benchmarks/convomem_bench.py`    | Standalone — per-message ingest, substring evidence recall |
| `eval/benchmarks/membench_bench.py`    | Standalone — per-turn-pair ingest, dual-key (sid + global_idx) Hit@k |
| `tests/test_eval/test_{longmemeval,convomem,membench,workdir}.py` | 30 unit tests, all mocked, all green |

Each bench owns its `setup()` and `run()` — no shared "magic" code path.
The only shared inheritance is `BaseBenchmark.__init__(settings)` plus the
`BenchmarkResult`/`RetrievalResult` dataclasses for the reporter.

## Numbers we're trying to beat (from MemPalace deep-dive §4)

Hebb Mind has no learned weights, so there is **no dev/held-out split**
— we run the full set every time and compare against MemPalace's
full-set numbers. Their dev-tuned ceilings (their `hybrid_v4` on 50
hand-picked questions, etc.) are noted for context only; not our
comparison target.

| Dataset | Slice | MemPalace full-set number we target |
|---|---|---|
| LongMemEval | full 500q, raw embeddings, no rerank | **96.6 % R@5** |
| LongMemEval | full 500q, with Haiku rerank        | 99.4 % R@5 (stretch — adding rerank to Hebb is on roadmap, not in this PR) |
| ConvoMem | 6 cats × 100 items/cat (~600q) | **92.9 % mean recall** |
| MemBench  | movie / noisy, top-5  | **43.4 % Hit@5** (MemPalace's worst slice — biggest reverse window) |
| MemBench  | movie / all 11 cats, top-5 | **80.3 % Hit@5 overall** |

The MemBench-noisy 43.4 % is the most strategically valuable target:
the biggest "reverse window" on the public leaderboard. A meaningful
beat there has the most narrative weight per CPU-hour.

## Run matrix — sequenced

Each row is one `python -m eval run` invocation on the **full dataset**.
Wall-clock budgets assume a single laptop with bge-large (the embedding
the production `hebb setup` defaults to). All runs go through the same
hebb server the user runs in production; the harness boots a fresh
server + cleans `hebb.db` between datasets.

### Phase 1 — first signal (≈ 1 h total)

Order is small → large so the fastest dataset surfaces any harness
bugs first.

| # | Dataset | top-k | Wall-clock | Target |
|---|---|---|---|---|
| 1 | `membench` (noisy / movie only) | 5 | ~10 min | beat 43.4 % Hit@5 |
| 2 | `convomem` (6 cats × 100 items) | 10 | ~30 min | beat 92.9 % mean recall |
| 3 | `longmemeval` (full 500q smoke — abort if R@5 < 80 %) | 10 | ~25 min | sanity-check the ingest path |

If phase 1 surfaces a bug, fix it and rerun affected datasets — there
is no "dev set" to protect, the whole set is the eval.

### Phase 2 — full LongMemEval coverage (≈ 3.5 h, can run overnight)

| # | Dataset | top-k | Wall-clock | Target |
|---|---|---|---|---|
| 4 | `longmemeval` (full 500q, final number) | 10 | ~3.5 h | beat 96.6 % R@5 |
| 5 | `membench` (all 11 cats × movie) | 5 | ~1.5 h | beat 80.3 % overall |

### Phase 3 — ablation only if a number is on the edge

Only run if any phase-2 number lands within ±1 pp of MemPalace's
published score:

- Embedding sweep: re-run the same dataset with `hebb setup --embed bge-base`
  vs default. Already validated on LoCoMo as a ~16 pp lever on
  single-hop.
- `prev_turns`/`next_turns` ablation: the LongMemEval bench currently
  forwards `(2, 2)` matching LoCoMo. Try `(0, 0)` and `(4, 4)`.

## Commands (copy-pastable)

```bash
# Phase 1 — fresh server per dataset, full set each time
python -m eval download --dataset membench
python -m eval run --dataset membench --top-k 5

python -m eval download --dataset convomem
python -m eval run --dataset convomem --top-k 10

python -m eval download --dataset longmemeval
python -m eval run --dataset longmemeval --top-k 10

# Phase 2 — expand MemBench to all 11 categories
# (default adapter is noisy-only; sweep requires either editing the
# adapter constructor or adding a --categories CLI flag — pick one
# before phase 2.)
python -m eval run --dataset membench --top-k 5
```

Reports land under `eval/reports/{dataset}/v{N}/run-{n}/` per
`eval/cli.py`. The `eval_version` of each new bench is recorded in the
file:

| Bench | eval_version |
|---|---|
| longmemeval | v2 (was v1 = generic QA + judge; v2 = prod-hook ingest + session R@k) |
| convomem    | v2 (was v1 = generic; v2 = per-message + substring recall) |
| membench    | v1 |

Numbers from `v1` LongMemEval / ConvoMem must not be compared against v2
— different methodologies, different reports/ subtree.

## Commit checklist for `repo_pages/benchmarks/`

After phase 2 closes, draft these pages following the
`locomo/vs-mempalace.md` template (production-parity callout first,
headline table, same-embedding deltas, where-it-isn't-fair section):

- [ ] `repo_pages/benchmarks/longmemeval/index.md` — replace 3q stub
- [ ] `repo_pages/benchmarks/longmemeval/vs-mempalace.md` — replace placeholder
- [ ] `repo_pages/benchmarks/convomem/index.md` — **new**
- [ ] `repo_pages/benchmarks/convomem/vs-mempalace.md` — **new**
- [ ] `repo_pages/benchmarks/membench/index.md` — **new**
- [ ] `repo_pages/benchmarks/membench/vs-mempalace.md` — **new**
- [ ] `repo_pages/benchmarks/index.md` — update the layout list to
      include the three new datasets and drop the "small-sample slice"
      caveat from LongMemEval

Each `vs-mempalace.md` must include the same prod-parity language LoCoMo
uses: MemPalace's published numbers come from a *benchmark-only*
pipeline (no closet boost, no BM25 hybrid, no neighbor expansion); our
numbers come from the production `/api/v1/search`. Same metric, but the
systems under test are not symmetric.

## Risks / things that could go wrong

1. **ConvoMem HF rate-limit.** `list_repo_files` + per-file `hf_hub_download`
   for 6 categories × 100 items can hit rate limits. The adapter logs
   warnings and continues; the consolidated `convomem.json` is cached
   after first success. Plan B: pre-stage the file with a one-time
   download.
2. **MemBench schema drift.** The `import-myself/Membench` repo could
   change. The adapter handles both `topic-keyed` and `role-keyed`
   shapes and skips items without `QA` / `target_step_id`. Spot-check
   the first download.
3. **Scenario-id matching in MemBench bench.** We restrict retrieved
   memories to the current scenario's `scenario_id` because the harness
   uses one shared partition. If the production search drops
   `scenario_id` from metadata propagation, Hit@k will report 0 across
   the board. Unit test `test_membench_bench_excludes_other_scenarios_results`
   guards this contract.
4. **LongMemEval `answer_session_ids` typing.** The dataset sometimes
   uses int session ids, sometimes str. Both adapter (cast to str at
   load time) and bench (cast at score time) coerce, but if a future
   slice introduces a different shape, R@k will silently collapse to
   0. Watch the `no_evidence_excluded` field in the report.

## What this plan deliberately does NOT do

- **No dev / held-out split.** Hebb Mind has no learned weights —
  splitting the eval set buys no statistical guarantee, just halves the
  signal. Run the full set every time. (See memory
  `no-eval-train-test-split` for the durable rule.)
- **No comparison against MemPalace's dev-tuned ceiling numbers** (e.g.
  the LME `hybrid_v4` 100 % on 50 hand-picked questions). Their
  full-set numbers are what we beat.
- **No ConvoMem substring-match recall in the public docs.** That
  metric punishes any text normalisation in production ingest and
  conflates retrieval with reformatting; it does not measure what
  users care about. ConvoMem is reported as end-to-end QA accuracy
  via the judge. See ``repo_pages/benchmarks/convomem/index.md``
  "How we evaluate" for the rationale.

## Eval-method choice per dataset

One metric per dataset, picked from the shape of the dataset's ground
truth — not a uniform metric forced across all datasets.

| Dataset | Ground truth shape | Metric |
|---|---|---|
| LoCoMo      | session-tagged evidence + free-text answer | (a) session R@k + (b) end-to-end QA |
| LongMemEval | `answer_session_ids` (clean id set)        | session R@k (no judge) |
| ConvoMem    | free-text answer (substring is too noisy)  | end-to-end QA judge |
| MemBench    | `target_step_id` integer pointer; MCQ      | turn-level Hit@k (no judge — MCQ would inflate via guessing) |
| PersonaMem  | free-text answer with consolidated rewrite | end-to-end QA judge |

Public-doc rule: never report a metric that doesn't measure what
users care about for a given dataset, even if the dataset's authors
report it.

## Chinese-language coverage in the retrieval hacks

`lexical_signals.py` and `preference_extractor.py` now accept Chinese
input alongside English:

- Predicate keywords: CJK character bigrams (zero-dep jieba
  approximation) joined with English word tokens
- Quoted phrases: 「」 『』 "" '' ASCII '' "" all recognised
- Person names: 2-3 char CJK runs prefixed by one of the top-100
  Chinese surnames (~85 % census coverage); arbitrary CJK vocabulary
  is NOT misclassified as a name
- PREF_PATTERNS: 21 English + 14 Chinese patterns
  (我喜欢/我打算/我担心/我最近/我以前/小时候/等)
- Assistant-reference triggers: English + Chinese
  (你之前说/你建议/你推荐/我们讨论过/等)

We don't yet have a public Chinese conversational benchmark to tune
against — patterns were authored by surveying common openers in
Chinese personal-memory contexts. Expect refinement once a Chinese
dataset lands.

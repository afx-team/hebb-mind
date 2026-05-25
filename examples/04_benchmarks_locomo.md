# LoCoMo benchmark — current numbers and how to reproduce them

> **Status: v0.1.1, work in progress.** The number below is from a single run
> on three scenarios with default settings. We're publishing it honestly, not
> as a leaderboard claim. Rerun yourself, file an issue if you can't
> reproduce, and please contribute comparison runs against other systems.

## What is LoCoMo?

[LoCoMo](https://arxiv.org/abs/2402.17753) (*Long-Term Conversation Memory*,
Maharana et al., 2024) is a benchmark for very long, multi-session dialogues.
Each scenario contains hundreds of turns spread across many sessions, plus
QA pairs that test recall across categories: `single_hop`, `multi_hop`,
`temporal`, `open_ended`, `adversarial`. It is the de-facto memory benchmark
for AI agents because it punishes naive context-window approaches.

## Hebb Mind on LoCoMo today

Latest run: **`eval/reports/20260419_114835/locomo.md`** (2026-04-19, judge
`openai/Kimi-K2.5`, mode `consolidated`, `top_k=10`, 3 scenarios, 497
questions).

| Metric | Value |
|--------|-------|
| **Overall accuracy** | **37.6%** (187 / 497) |
| Avg latency | 101.7 ms |
| Consolidation success | 234 / 234 |

### Accuracy by category

| Category | Accuracy |
|----------|----------|
| adversarial | 66.1% |
| single_hop | 41.9% |
| open_ended | 35.5% |
| temporal | 28.6% |
| multi_hop | 5.6% |

The multi_hop number is the big known weakness — most failures are temporal
expressions ("Yesterday" vs an exact date). That's a consolidation /
retrieval ranking problem, not a storage one, and it's the next thing on the
roadmap.

## Reproduce it

```bash
# 1. Install dev extras (LoCoMo dataset adapter + judge LLM client)
pip install -e ".[dev]"

# 2. Set a judge LLM key (any LiteLLM-supported provider)
export OPENAI_API_KEY=sk-...

# 3. Download the LoCoMo dataset
python -m eval download --dataset locomo

# 4. Run — the eval harness boots a fresh Hebb Mind server,
#    ingests + consolidates the dataset, then asks the judge model to grade.
python -m eval run --dataset locomo --mode consolidated --max-scenarios 3

# 5. Read the fresh report
ls eval/reports/                              # newest timestamp dir
cat eval/reports/<TIMESTAMP>/locomo.md
```

Useful flags:

- `--mode raw` — skip consolidation (sanity baseline; usually lower accuracy).
- `--top-k 20` — widen retrieval (slower, sometimes more accurate).
- `--llm-model anthropic/claude-3-5-sonnet-latest` — swap the judge.
- `--max-scenarios N` — limit scenarios for a quick smoke test.

Drop `--max-scenarios` for the full ten-scenario run (~30 minutes on a single
machine, depending on your judge model's rate limits).

## How to compare against mem0 / letta / zep

We don't yet ship side-by-side numbers. To produce a fair comparison:

1. Run mem0 / letta / zep against the **same LoCoMo scenarios** with the
   **same judge model and prompt** (`eval/judge.py`).
2. Use `--mode consolidated` for systems that have a consolidation step,
   `--mode raw` for systems that don't, and report both.
3. Open a PR adding a row to a `eval/reports/comparison.md` table — bring
   the raw JSON outputs so others can re-grade.

Tracking issue: **TBD — file one if you start this work and we'll link it
here.** A trustworthy comparison table is the single highest-leverage thing
we can ship next; help wanted.

## Caveats

- A 3-scenario run is fast but noisy; full LoCoMo is 10 scenarios and the
  numbers shift a few points either way.
- The judge model's grading prompt is in `eval/judge.py` — different judges
  give different absolute numbers. Always report the judge.
- LoCoMo measures *recall after consolidation*; it does not measure write
  latency, storage size, or graph quality. Those need their own benchmarks.

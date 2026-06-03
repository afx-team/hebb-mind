<p align="center">
  <h1 align="center"><a href="https://afx-team.github.io/hebb-mind/"><img src="logo.svg" width="40" height="40" alt="Hebb Mind logo" valign="middle"/> Hebb Mind</a></h1>
  <p align="center"><strong>A neuroscience-inspired memory framework for AI agents</strong></p>
  <p align="center"><em>Encode. Consolidate. Activate. Forget.</em></p>
  <p align="center"><a href="https://afx-team.github.io/hebb-mind/">Documentation</a> · <a href="README.md">English</a> | <a href="README_ZH.md">中文</a></p>
</p>

<p align="center">
  <a href="https://afx-team.github.io/hebb-mind/"><img src="https://img.shields.io/badge/docs-afx--team.github.io-blue" alt="Documentation"></a>
  <a href="https://github.com/afx-team/hebb-mind/actions"><img src="https://github.com/afx-team/hebb-mind/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/hebb-mind/"><img src="https://img.shields.io/pypi/v/hebb-mind" alt="PyPI"></a>
  <a href="https://github.com/afx-team/hebb-mind/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
  <img src="https://img.shields.io/pypi/pyversions/hebb-mind" alt="Python">
</p>

---

Hebb Mind gives AI agents a neuroscience-inspired memory loop — **encode → replay → consolidate → forget**. A `pipx install` and one command stand up a local REST + MCP endpoint: SQLite for storage, sentence-transformers for embedding, NetworkX for the tag graph. **Zero external services** — bring an LLM key only when you want consolidation to do its work.


<p align="center">
  <img src="repo_pages/public/architecture-en.jpg" alt="Hebb Mind architecture — agent integrations · hebb CLI · 4-stage memory loop with LLM-driven 7-step consolidation agent · SQLite + pgvector" width="900">
</p>

## Quick Start

### Try in 60 seconds — no API key needed

Ingest and hybrid search work fully offline with the bundled local embedding.

```bash
pipx install hebb-mind
hebb setup              # picks an embedding model based on your OS locale
hebb service install    # registers a background service (launchd / systemd / Task Scheduler)
```

**Don't have `pipx`?** It's the recommended installer for Python CLI tools — isolated venv, automatic PATH, plays nice with PEP 668. Install it once:

```bash
# macOS (Homebrew)
brew install pipx && pipx ensurepath

# Linux — Debian / Ubuntu 23.04+
sudo apt install pipx && pipx ensurepath

# Linux — Fedora
sudo dnf install pipx && pipx ensurepath

# Windows / any platform with Python 3.10+
python -m pip install --user pipx && python -m pipx ensurepath
```

Then **open a new terminal** so the updated `PATH` takes effect, and re-run `pipx install hebb-mind`.

Prefer plain `pip` instead? `python -m venv .venv && source .venv/bin/activate && pip install -U hebb-mind` works fine — `hebb` lives on the venv's `PATH` automatically.

Hebb Mind runs as an OS-managed background service — no foreground process to keep alive, no `start`/`stop` shells to remember. The service is per-user by default and needs no admin/sudo. Use `--scope system` for a system-wide install. See `hebb service --help`.

In another shell:

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H 'Content-Type: application/json' \
  -d '{"content": "User prefers dark mode and compact layout", "tags": ["preference", "ui"]}'

curl -X POST http://localhost:8321/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "UI preferences", "top_k": 5}'
```

Open <http://localhost:8321/> for the Web Console.

<p align="center">
  <img src="repo_pages/public/web-console-hero.jpg" alt="Hebb Mind Web Console — partitioned memories and tag graph" width="760">
</p>

### Full experience (5 min) — enable LLM consolidation

Consolidation, conflict resolution, and tag extraction need an LLM backend. **Without a key, those endpoints are a silent no-op** (a known v0.1.1 gap — see [#consolidation-no-op](https://afx-team.github.io/hebb-mind/troubleshooting.html)).

```bash
hebb config set llm_api_key sk-...
hebb config set llm_model openai/gpt-4o-mini
# For Qwen / GLM / Kimi via LiteLLM:
hebb config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
```

Trigger consolidation manually, or wait for the daily 18:00 job:

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

## Installation Paths

```bash
pipx install hebb-mind                 # recommended (isolated CLI install)
pipx install 'hebb-mind[pg]'           # + PostgreSQL/pgvector
pipx upgrade hebb-mind                 # upgrade later
hebb claude-code install --scope user  # Claude Code: hooks-based auto memory
hebb codex install --scope user        # Codex: MCP memory tools
```

Docker, one-line install, and source build: [Installation Guide](https://afx-team.github.io/hebb-mind/guide/installation.html).

## 30-second Python SDK

<!-- requires v0.1.2 facade — see PR #N -->

```python
from hebb import HebbMind

mem = HebbMind()  # uses ~/.hebb/hebb.json

mem.add("User prefers dark mode", tags=["preference", "ui"], importance=7.5)
mem.add("User uses VS Code with the One Dark theme", tags=["preference", "tools"])

for hit in mem.search("UI preferences", top_k=5):
    print(hit.score, hit.content)
```

The `HebbMind()` facade wraps the REST endpoints above; when no daemon is running locally, it boots an in-process server automatically.

## The memory loop

The same four stages, every day, in roughly the same order the brain runs them:

| Stage | Brain analogue | What happens here | Trigger |
|-------|----------------|-------------------|---------|
| **Encoding** | Hippocampal CA1 captures the moment | New memories land in the working-memory inbox (`mem_hippocampus`) | API write |
| **Replay & consolidation** | Sharp-wave ripples during slow-wave sleep | Agent classifies into a partition, resolves conflicts, writes tags into the knowledge graph | Daily 18:00 / manual |
| **Retrieval** | Pattern completion in CA3 | Three-path hybrid search (vector + keyword + graph), scored on recency / importance / relevance | API search |
| **Forgetting** | Synaptic pruning + the Ebbinghaus curve | Dynamic TTL on access count and importance — neglected memories fade | Periodic |

Walkthroughs: [Memory Lifecycle](https://afx-team.github.io/hebb-mind/concepts/memory-lifecycle.html) · [Hybrid Search](https://afx-team.github.io/hebb-mind/concepts/hybrid-search.html) · [Architecture diagram](https://afx-team.github.io/hebb-mind/#architecture)

## Comparison

Honest summary; full table on the [docs site](https://afx-team.github.io/hebb-mind/#why-hebb-mind).

| Feature | Mem0 | Letta | Zep | **Hebb Mind** |
|---|---|---|---|---|
| Self-hosted Web UI | Cloud only ([discussion](https://github.com/mem0ai/mem0/discussions/3599)) | Cloud only | Cloud only | **Built-in SPA** |
| Knowledge graph | Pluggable ([removed in v3](https://docs.mem0.ai/migration/oss-v2-to-v3)) | No | Yes (Graphiti) | Tag-based (NetworkX) |
| Memory consolidation | Append-only | Sleeptime Agent | Contradiction resolve | **Auto + conflict resolve** |
| Forgetting / decay | No | No | Temporal invalidation | **Dynamic TTL** |
| Zero-config local deploy | Needs API key | Needs API key + DB | Needs Postgres + Neo4j | **SQLite + local embed** |

## Configuration

All config lives in `hebb.json`. Common settings:

```bash
hebb config list
hebb config set llm_model openai/gpt-4o-mini
hebb config set storage_type postgresql
hebb config set pg_url postgresql://user:pass@localhost/hebb
```

Full reference: [Configuration Guide](https://afx-team.github.io/hebb-mind/guide/configuration.html).

## API

REST docs at `http://localhost:8321/docs` once the server is running. Key endpoints:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/memories` | Store a memory |
| `POST` | `/api/v1/search` | Hybrid search |
| `POST` | `/api/v1/admin/consolidate` | Run consolidation now (requires `llm_api_key`) |
| `GET`  | `/api/v1/graph/tags` | List knowledge-graph tags |
| `GET`  | `/api/v1/graph/neighbors/{tag}?depth=2` | Walk the tag graph |

## Benchmarks

**LoCoMo** (1,986 questions across 10 multi-session conversations; 1,978 scorable), session-level Recall@10 — the same metric MemPalace publishes.

| System | Embedding | Rerank | R@10 |
|---|---|---|---|
| **Hebb Mind v0.1.6** | bge-large-1024 | bge-reranker-base | **95.75%** |
| **Hebb Mind v0.1.6** | bge-large-1024 | — | **94.14%** |
| MemPalace hybrid | bge-large-1024 | — | 92.40% |
| **Hebb Mind v0.1.6** | MiniLM-384 | bge-reranker-base | **94.69%** |
| MemPalace hybrid | MiniLM-384 | — | 92.63% |
| **Hebb Mind v0.1.6** | MiniLM-384 | — | 91.41% |

Same-embedding lead: +1.74 pp at bge-large with no rerank, +3.35 pp with rerank; the local cross-encoder even lifts the cheap MiniLM-384 to 94.69%, past MemPalace's tuned hybrid. End-to-end QA (same retrieval + DeepSeek-V4-Pro judge, full 1,978q): **77.1%**.

**LongMemEval** (500 questions, LongMemEval-S) — session-level Recall@k (retrieval, apples-to-apples with MemPalace) and end-to-end QA (official reader + `get_anscheck_prompt` judge, comparable to Zep / Mem0).

| System | Retrieval recall@10 | End-to-end QA | Reader LLM |
|---|---|---|---|
| **Hebb Mind v0.1.6** | **99.4%** | **79.0%** | DeepSeek-V4-Pro (neutral official prompt) |
| Zep | 95.5% | 71.2% | gpt-4o |
| Mem0 | not reported | ~85–94%¹ | gpt-4o (heavily-tuned prompt) |

Retrieval R@5 = **99.0%**, tying MemPalace's best hybrid+rerank config (99.4%) and well above its raw 96.6% — on the same MiniLM-384 embedding. Hebb beats Zep at every retrieval depth (R@1 93.4% vs 75.9%) and leads its QA (79.0% vs 71.2%) with an *untuned* reader prompt; the gap to Mem0 is reader-prompt engineering, not memory — Hebb's retrieval is the stronger layer. <sup>¹ varies by source/setup.</sup>

**MemBench** (ACL 2025; 11 categories, all topics, 11,996 questions) — turn-level Hit@5 against the dataset's `target_step_id` pointer, the metric MemPalace publishes. MCQ ground truth, so no LLM judge (random guessing alone scores 25%).

| Category | Hebb Mind v0.1.6 Hit@5 | MemPalace Hit@5 | Δ |
|---|---|---|---|
| noisy | **79.4%** | 43.4% | +36.0 pp |
| post_processing | **90.3%** | 56.6% | +33.7 pp |
| conditional | **86.0%** | 57.3% | +28.7 pp |
| highlevel_rec | **89.6%** | 76.2% | +13.4 pp |
| **Overall (11 categories)** | **94.6%** | 80.3% | **+14.3 pp** |

MiniLM-384 + bge-reranker-base. Hebb matches MemPalace on the easy categories (within ±4 pp) and wins decisively on all four hard ones — distractors, conditional reasoning, post-processing — exactly where verbatim-embedding retrieval collapses; the lever is the local cross-encoder rerank. Per-category k-curves on the docs site.

Hebb Mind's eval calls the same Claude Code hook code paths (`integrations/claude_code/{write,stop}.py`) and `/api/v1/search` endpoint that the shipped product uses — the numbers above are what a user actually gets in production. Full methodology, per-category breakdowns, and prod-vs-eval-pipeline caveats: [hebb-mind.github.io/benchmarks](https://afx-team.github.io/hebb-mind/benchmarks/).

## Why "Hebb Mind"?

In 1949, psychologist **Donald O. Hebb** proposed a rule that later got distilled into four words:

> **Neurons that fire together, wire together.**

A memory is not a *place* you look something up — it is a *pattern of connection*. Concepts that co-occur get physically linked into **cell assemblies**, and lighting up part of an assembly recalls the rest. Repetition strengthens the wiring; disuse lets it fade. That single rule — Hebbian learning — has shaped most of what came after in memory research and artificial neural networks.

**Hebb Mind runs on that rule.** Its tag knowledge graph *is* a cell assembly: tags that appear together gain an edge, and every time they co-occur that edge grows stronger. Retrieval walks those edges, so a partial cue completes the whole pattern. Consolidation keeps what gets reinforced; forgetting prunes what does not — *fire together, wire together; neglect it, lose it.*

The **hippocampus** has a place here too — it names the working-memory partition (`mem_hippocampus`), the inbox where every new memory lands before consolidation. In the brain, the hippocampus is the gateway that holds new experience until it is wired into long-term cortical memory; in 1957, the patient known as H.M. lost both of his and could never form a new long-term memory again [(Squire, 1992; Tulving, 2002)](#acknowledgments). Today's AI agents are H.M. — every conversation starts from zero. Hebb Mind gives your agent that missing loop.

## Contributing

Setup: `pip install -e ".[dev]" && pytest tests/ -v`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Acknowledgments

**Cognitive neuroscience.** Ebbinghaus, H. (1885). *Über das Gedächtnis*. · **Hebb, D. O. (1949). *The Organization of Behavior*. Wiley** — the namesake; the postulate behind "fire together, wire together." · Tulving, E. (1972). Episodic and semantic memory. · Squire, L. R. (1992). Memory and the hippocampus: a synthesis from findings with rats, monkeys, and humans. *Psychological Review*, 99(2). · O'Reilly, R. C., & McClelland, J. L. (1994). Hippocampal conjunctive encoding, storage, and recall. *Hippocampus*, 4(6). · Wilson, M. A., & McNaughton, B. L. (1994). Reactivation of hippocampal ensemble memories during sleep. *Science*, 265(5172). · Tulving, E. (2002). Episodic memory: from mind to brain. *Annual Review of Psychology*, 53. · Buzsáki, G. (2015). Hippocampal sharp wave-ripple. *Hippocampus*, 25(10).

**AI memory systems.** [Generative Agents](https://arxiv.org/abs/2304.03442) (scoring) · [MemGPT / Letta](https://arxiv.org/abs/2310.08560) (agent-driven memory) · [CoALA](https://arxiv.org/abs/2309.02427) (partition taxonomy) · [Graphiti](https://github.com/getzep/graphiti) (temporal KG). Survey notes in [`reports/papers/`](reports/papers/).

> *"Memory is the scribe of the soul." — Aristotle*
> The brain solved this in deep time. We're just porting the loop.

## License

[MIT](LICENSE)

<p align="center">
  <h1 align="center"><a href="https://afx-team.github.io/hebb-mind/">Hebb Mind</a></h1>
  <p align="center"><strong>A memory framework for AI agents — named for Donald Hebb, built on the rule his work gave us: neurons that fire together, wire together.</strong></p>
  <p align="center"><em>Encode. Replay. Consolidate. Forget. The way brains do.</em></p>
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

In 1957, neurosurgeons removed both hippocampi from a patient known as H.M. to treat his epilepsy. He survived — but lost the ability to form new long-term memories. Each day, every meal, every face was forever new. The hippocampus, it turned out, was the bridge between *what just happened* and *what we know*. Half a century of research [(Squire, 1992; Tulving, 2002)](#acknowledgments) has shown how it does this: it **encodes** fragments of experience, **replays** them during quiet rest [(Wilson & McNaughton, 1994)](#acknowledgments), **consolidates** the important ones into long-term knowledge, and **lets the rest fade** [(Ebbinghaus, 1885)](#acknowledgments).

Today's AI agents are H.M. They start every conversation new.

**Hebb Mind** is a memory framework that gives your agent that missing bridge. `pip install`, one command, and you have a local REST + MCP endpoint that runs the same four-stage loop: encode → replay → consolidate → forget. SQLite for storage, sentence-transformers for the embedding cortex, NetworkX for the tag graph. **Zero external services.** Bring an LLM key only when you want consolidation to do its work.

Where peers diverge: `mem0` is cloud-first and append-only; `letta` needs an external DB and a separate sleeptime agent; `zep` needs Postgres + Neo4j. Hebb Mind runs on a single binary, with one biological loop.

<!-- TODO(asset): screenshot of /index.html web console with sample memories -->
<p align="center">
  <img src="repo_pages/public/web-console-hero.png" alt="Hebb Mind Web Console showing partitioned memories and tag graph" width="760">
</p>

## Quick Start

### Try in 60 seconds — no API key needed

Ingest and hybrid search work fully offline with the bundled local embedding.

```bash
pip install -U hebb-mind
hebb setup        # picks an embedding model based on your OS locale
hebb start        # serves http://localhost:8321/
```

In another shell:

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H 'Content-Type: application/json' \
  -d '{"content": "User prefers dark mode and compact layout", "tags": ["preference", "ui"]}'

curl -X POST http://localhost:8321/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "UI preferences", "top_k": 5}'
```

Open <http://localhost:8321/> for the Web Console. <!-- TODO(asset): repo_pages/public/quickstart-cast.gif (asciinema of the 60-second path) -->

<p align="center">
  <img src="repo_pages/public/quickstart-cast.gif" alt="Asciinema recording: install, setup, start, ingest, search in 60 seconds" width="720">
</p>

### Full experience (5 min) — with LLM consolidation

Consolidation, conflict resolution, and tag extraction need an LLM. Without a key, those endpoints are a **no-op** (this is a known v0.1.1 gap — see [#consolidation-no-op](https://afx-team.github.io/hebb-mind/troubleshooting.html)).

```bash
hebb config set llm_api_key sk-...
hebb config set llm_model openai/gpt-4o-mini
# For Qwen / GLM / Kimi via LiteLLM:
hebb config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
```

Then trigger consolidation manually or wait for the daily 18:00 job:

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

## Why "Hebb Mind"?

In 1949, Canadian psychologist **Donald O. Hebb** (1904–1985) published *The Organization of Behavior* and proposed the rule that became the foundation of how we understand learning in the brain. When one neuron repeatedly takes part in firing another, he argued, the connection between them strengthens. Half a century later it is still taught in four words:

> **Neurons that fire together, wire together.**

Hebb's insight was that a memory is not a *place* you look something up — it is a *pattern of connection*. Concepts that co-occur get physically linked into **cell assemblies**, and lighting up part of an assembly recalls the rest. Repetition strengthens the wiring; disuse lets it fade. That single rule — Hebbian learning — is the ancestor of every artificial neural network and every associative-memory system since.

**Hebb Mind runs on that rule.** Its tag **knowledge graph** *is* a cell assembly: tags that appear together gain an edge, and every time they co-occur that edge grows stronger. Retrieval walks those edges, so a partial cue completes the whole pattern. Consolidation keeps what gets reinforced; forgetting prunes what does not — *fire together, wire together; neglect it, lose it.*

The **hippocampus** has a place here too — it names the working-memory partition (`mem_hippocampus`), the inbox where every new memory lands before consolidation. The name fits the job: in the brain, the hippocampus is the gateway that holds new experience until it is wired into long-term cortical memory. The partition does exactly that.

## Inspired by the brain (not just the name)

Each piece of the system maps to a mechanism cognitive neuroscience has spent fifty years describing. The point isn't fidelity to biology — it's that the brain has already solved the problem of *which* memories to keep, *when* to consolidate them, and *how* to recall them from a partial cue. We borrow the answers.

| Brain mechanism | What the brain does | What Hebb Mind does |
|---|---|---|
| **Sharp-wave ripples & replay** [(Wilson & McNaughton, 1994; Buzsáki, 2015)](#acknowledgments) | During slow-wave sleep the hippocampus replays the day's experiences, transferring them to neocortex. | A daily 18:00 consolidation job replays the working-memory inbox, classifies each item into a partition, resolves conflicts, and writes tags into the knowledge graph. |
| **Multiple memory systems** [(Tulving, 1972; Squire, 1992)](#acknowledgments) | Episodic, semantic, procedural memory live in distinct sub-systems. | Five named partitions — `episodic`, `semantic`, `preference`, `procedural`, `custom` — modeled on the [CoALA](https://arxiv.org/abs/2309.02427) cognitive architecture. |
| **Forgetting curve** [(Ebbinghaus, 1885)](#acknowledgments) | Unrehearsed memories decay exponentially; rehearsal flattens the curve. | TTL = `base × (1 + log(access)) × importance × exp(-decay × days)`. Frequently used memories survive; neglected ones fade. |
| **Pattern separation + completion** [(O'Reilly & McClelland, 1994)](#acknowledgments) | DG distinguishes similar memories; CA3 reconstructs whole memories from partial cues. | Hybrid retrieval combines vector similarity (separation), keyword match, and tag-graph walk (completion) — three paths, one composite score. |

Why this matters in practice: a system that *only* appends never resolves contradictions, and a system that *never forgets* drowns its own retrieval in noise. The brain solved both. So do we.

## Why Hebb Mind? (the engineering view)

- **Zero external services** — `sqlite-vec` for vectors, NetworkX for the tag graph, sentence-transformers for embedding. No Postgres, no Neo4j, no Redis. See [Storage Backends](https://afx-team.github.io/hebb-mind/advanced/storage-backends.html).
- **Honest forgetting** — the Ebbinghaus formula above, applied as a periodic job. See [Forgetting](https://afx-team.github.io/hebb-mind/concepts/forgetting.html).
- **Conflict-resolving consolidation** — the agent doesn't just append; it merges duplicates and overwrites stale facts. See [Consolidation](https://afx-team.github.io/hebb-mind/concepts/consolidation.html).
- **Drop-in for Claude Code** — three-line install gives Claude Code cross-session memory via hooks; one command adds the same as MCP tools to Codex. See [Claude Code Integration](https://afx-team.github.io/hebb-mind/guide/claude-code.html).

## Benchmarks

v0.1.1, single run on the [LoCoMo](https://github.com/snap-research/LoCoMo) long-conversation benchmark:

| Metric | Value |
|---|---|
| Accuracy | **37.6%** (187 / 497) |
| Avg latency | 102 ms / query |
| Best category | Adversarial 66.1% |
| Weakest category | Multi-hop 5.6% |

Multi-hop reasoning over the tag graph is a known weak spot. Full numbers, methodology, and per-category breakdown: [Benchmarks](https://afx-team.github.io/hebb-mind/benchmarks.html). This is a work in progress — comparison runs against `mem0` and `zep` are tracked in [#TBD].

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

The `HebbMind()` facade wraps the same REST endpoints used above; it also boots an in-process server when no daemon is running.

## Installation Paths

```bash
pip install -U hebb-mind               # pip
pip install -U hebb-mind[pg]           # + PostgreSQL/pgvector
hebb cc install --scope user          # Claude Code: hooks-based auto memory
hebb codex install --scope user       # Codex: MCP memory tools
```

Docker, one-line install, and source build: [Installation Guide](https://afx-team.github.io/hebb-mind/guide/installation.html).

## The memory loop

The same four stages, every day, in roughly the same order the brain runs them:

| Stage | Brain analogue | What happens here | Trigger |
|-------|----------------|-------------------|---------|
| **Encoding** | Hippocampal CA1 captures the moment | New memories land in the working-memory inbox (`mem_hippocampus`) | API write |
| **Replay & consolidation** | Sharp-wave ripples during slow-wave sleep | Agent classifies into a partition, resolves conflicts, extracts tags | Daily 18:00 / manual |
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

## Contributing

Setup: `pip install -e ".[dev]" && pytest tests/ -v`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Acknowledgments

**Cognitive neuroscience.** Ebbinghaus, H. (1885). *Über das Gedächtnis*. · **Hebb, D. O. (1949). *The Organization of Behavior*. Wiley** — the namesake; the postulate behind "fire together, wire together." · Tulving, E. (1972). Episodic and semantic memory. · Squire, L. R. (1992). Memory and the hippocampus: a synthesis from findings with rats, monkeys, and humans. *Psychological Review*, 99(2). · O'Reilly, R. C., & McClelland, J. L. (1994). Hippocampal conjunctive encoding, storage, and recall. *Hippocampus*, 4(6). · Wilson, M. A., & McNaughton, B. L. (1994). Reactivation of hippocampal ensemble memories during sleep. *Science*, 265(5172). · Tulving, E. (2002). Episodic memory: from mind to brain. *Annual Review of Psychology*, 53. · Buzsáki, G. (2015). Hippocampal sharp wave-ripple. *Hippocampus*, 25(10).

**AI memory systems.** [Generative Agents](https://arxiv.org/abs/2304.03442) (scoring) · [MemGPT / Letta](https://arxiv.org/abs/2310.08560) (agent-driven memory) · [CoALA](https://arxiv.org/abs/2309.02427) (partition taxonomy) · [Graphiti](https://github.com/getzep/graphiti) (temporal KG). Survey notes in [`reports/papers/`](reports/papers/).

> *"Memory is the scribe of the soul." — Aristotle*
> The brain solved this in deep time. We're just porting the loop.

## License

[MIT](LICENSE)

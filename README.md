<p align="center">
  <h1 align="center">Hippocampus 海马体</h1>
  <p align="center">Neuroscience-inspired memory framework for AI agents</p>
  <p align="center"><a href="README.md">English</a> | <a href="README_ZH.md">中文</a></p>
</p>

<p align="center">
  <a href="https://github.com/afx-team/hippocampus/actions"><img src="https://github.com/afx-team/hippocampus/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/afx-hippocampus/"><img src="https://img.shields.io/pypi/v/afx-hippocampus" alt="PyPI"></a>
  <a href="https://github.com/afx-team/hippocampus/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License"></a>
  <img src="https://img.shields.io/pypi/pyversions/afx-hippocampus" alt="Python">
</p>

---

Hippocampus gives your AI agents a **brain-like memory system**. Just like the human hippocampus consolidates short-term experiences into long-term knowledge, this framework automatically organizes, prioritizes, and forgets memories so your agents stay sharp.

## Why Hippocampus?

| Feature | Mem0 | Letta | Zep | **Hippocampus** |
|---------|------|-------|-----|-----------------|
| Memory consolidation | - | - | - | Automatic |
| Forgetting / decay | - | - | Implicit | Dynamic TTL formula |
| Tag-based knowledge graph | - | - | Partial | Built-in |
| Zero-config deployment | - | - | - | SQLite, one command |
| Vector search optional | - | - | - | Progressive disclosure |
| Multi-model (OpenAI/Claude/Qwen/GLM/Kimi) | Partial | Partial | Partial | Via LiteLLM |

## Architecture

<div align="center">

<table>
<tr>
<td align="center" colspan="5" style="padding:4px 12px; background:#1a1a2e; border-radius:8px; color:#e0e0e0; font-weight:600;">
API / MCP / CLI
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:18px; color:#555;">▼</td></tr>
<tr>
<td align="center" colspan="5" style="padding:8px 16px; background:#16213e; border-radius:8px;">
<b style="color:#00d2ff; font-size:15px;">HIPPOCAMPUS</b><br/>
<span style="color:#888; font-size:12px;">Working Memory Inbox</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; color:#555;">▼&nbsp; Consolidation Agent <span style="color:#666; font-size:11px;">(Agentic RAG · Classify · Conflict Resolve · Tag Extract)</span></td></tr>
<tr>
<td align="center" style="padding:6px 10px; background:#1b4332; border-radius:6px; min-width:90px;">
<b style="color:#52b788;">SEMANTIC</b><br/><span style="color:#888; font-size:11px;">Facts & Knowledge</span>
</td>
<td align="center" style="padding:6px 10px; background:#3c1642; border-radius:6px; min-width:90px;">
<b style="color:#c77dff;">EPISODIC</b><br/><span style="color:#888; font-size:11px;">Events & History</span>
</td>
<td align="center" style="padding:6px 10px; background:#6b2d5b; border-radius:6px; min-width:90px;">
<b style="color:#ff6b6b;">PREFERENCE</b><br/><span style="color:#888; font-size:11px;">Likes & Dislikes</span>
</td>
<td align="center" style="padding:6px 10px; background:#2d3a4a; border-radius:6px; min-width:90px;">
<b style="color:#4ecdc4;">PROCEDURAL</b><br/><span style="color:#888; font-size:11px;">Skills & How-to</span>
</td>
<td align="center" style="padding:6px 10px; background:#3d3d3d; border-radius:6px; min-width:90px;">
<b style="color:#aaa;">CUSTOM</b><br/><span style="color:#888; font-size:11px;">Your Partitions</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; padding-top:4px;">
<span style="color:#555;">▼</span>&nbsp;
<span style="color:#666; font-size:12px;">Hybrid Retrieval</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">Knowledge Graph</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">Forgetting (Dynamic TTL)</span>
</td></tr>
</table>

</div>

## Quick Start

```bash
pip install afx-hippocampus      # Install
hippocampus init                  # Initialize (creates hippocampus.json + SQLite DB)
hippocampus config set llm_api_key sk-your-key-here  # Set LLM key
hippocampus start                 # Start server → http://localhost:8321/
```

Open http://localhost:8321/ for the **Web Console**, or http://localhost:8321/docs for the API docs.

<details>
<summary><b>Alternative install methods</b></summary>

**Docker:**

```bash
git clone https://github.com/afx-team/hippocampus.git && cd hippocampus
docker compose -f docker/docker-compose.yml up
```

**One-line install:**

```bash
curl -fsSL https://raw.githubusercontent.com/afx-team/hippocampus/main/scripts/install.sh | sh
```
</details>

<details>
<summary><b>Try it in 30 seconds</b></summary>

```bash
# Store a memory
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{"content": "User prefers dark mode", "tags": ["preference", "ui"], "importance_score": 7.5}'

# Search memories
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "UI preferences", "top_k": 5}'

# Trigger consolidation manually
curl -X POST http://localhost:8321/api/v1/admin/consolidate

# Explore the knowledge graph
curl http://localhost:8321/api/v1/graph/tags
curl http://localhost:8321/api/v1/graph/neighbors/python?depth=2
```
</details>

## How It Works

Memories flow through four stages — inspired by how the human hippocampus consolidates short-term experiences into long-term knowledge:

| Stage | What Happens | Trigger |
|-------|-------------|---------|
| **Ingest** | New memories land in the working memory inbox (`mem_hippocampus`) | API write |
| **Consolidate** | Agent classifies into partition, resolves conflicts, extracts tags → Knowledge Graph | Periodic / manual |
| **Retrieve** | Three-path hybrid search (vector + keyword + graph) with recency/importance/relevance scoring | API search |
| **Forget** | Dynamic TTL: `base × (1 + log(access)) × importance × exp(-decay × days)` — frequently used memories survive, neglected ones fade | Periodic |

> Full details: [Memory Lifecycle](docs/concepts/memory-lifecycle.md) · [Consolidation](docs/concepts/consolidation.md) · [Hybrid Search](docs/concepts/hybrid-search.md) · [Forgetting](docs/concepts/forgetting.md)

## Configuration

All config lives in **`hippocampus.json`** — no environment variables needed.

```bash
hippocampus config list                    # View all settings
hippocampus config set llm_model openai/gpt-4o  # Change model
hippocampus config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1  # Qwen/GLM/Kimi
```

| Field | Default | Description |
|-------|---------|-------------|
| `llm_model` | `openai/gpt-4o-mini` | LLM model identifier (via LiteLLM) |
| `llm_api_key` | `null` | LLM provider API key (required for consolidation) |
| `llm_base_url` | `null` | Custom LLM API endpoint (for Qwen/GLM/Kimi) |
| `storage_type` | `sqlite` | `sqlite` or `postgresql` |
| `embedding_enabled` | `true` | Set `false` to disable vector search |
| `port` | `8321` | Server port |
| `consolidation_interval_seconds` | `3600` | How often consolidation runs |
| `base_ttl_hours` | `168` | Base memory TTL before decay |

<details>
<summary><b>Storage backends</b></summary>

**SQLite (default)** — zero-config, single file, great for personal use and development.

**PostgreSQL + pgvector** — production-grade, connection pooling, native vector types.

```bash
pip install afx-hippocampus[pg]
hippocampus config set storage_type postgresql
hippocampus config set pg_url postgresql://user:pass@localhost/hippocampus
```
</details>

> Full config reference: [Configuration Guide](docs/guide/configuration.md)

## Supported Models

Via [LiteLLM](https://github.com/BerriAI/litellm), Hippocampus works with any major LLM provider:

| Provider | Model Example | Env Var |
|----------|--------------|---------|
| OpenAI | `openai/gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-3-haiku-20240307` | `ANTHROPIC_API_KEY` |
| Qwen (Alibaba) | `openai/qwen-plus` | `HIPPOCAMPUS_LLM_API_KEY` + `HIPPOCAMPUS_LLM_BASE_URL` |
| GLM (Zhipu) | `openai/glm-4` | `HIPPOCAMPUS_LLM_API_KEY` + `HIPPOCAMPUS_LLM_BASE_URL` |
| Kimi (Moonshot) | `openai/moonshot-v1-8k` | `HIPPOCAMPUS_LLM_API_KEY` + `HIPPOCAMPUS_LLM_BASE_URL` |

## Development

```bash
git clone https://github.com/afx-team/hippocampus.git
cd hippocampus
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/

# Type check
mypy src/hippocampus/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## Roadmap

- [x] Core memory model with 5 brain-inspired partitions
- [x] SQLite + sqlite-vec storage backend
- [x] PostgreSQL + pgvector storage backend
- [x] Memory consolidation agent (Agentic RAG)
- [x] Dynamic forgetting with exponential decay
- [x] Tag-based knowledge graph
- [x] FastAPI REST API
- [x] CLI tooling + Docker deployment
- [x] Built-in Web Console (memory CRUD, search, graph visualization)
- [x] Evaluation benchmarks (LoCoMo, LongMemEval, ConvoMem, PersonaMem)
- [x] MCP server for Claude Code / OpenClaw integration
- [ ] Multi-agent shared memory
- [ ] Emotional tagging and memory importance learning

## Research

This project draws on research from:

- [Generative Agents](https://arxiv.org/abs/2304.03442) — recency-importance-relevance retrieval
- [MemGPT / Letta](https://arxiv.org/abs/2310.08560) — agent-driven memory management
- [CoALA](https://arxiv.org/abs/2309.02427) — episodic/semantic/procedural taxonomy
- [Zep / Graphiti](https://github.com/getzep/graphiti) — temporal knowledge graphs

See [docs/papers/](docs/papers/) for detailed survey notes.

## License

[Apache License 2.0](LICENSE)

---

<p align="center">
  Built by <a href="https://github.com/afx-team">afx-team</a>
</p>

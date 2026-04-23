<p align="center">
  <h1 align="center"><a href="https://afx-team.github.io/hippocampus/">Hippocampus</a></h1>
  <p align="center">Neuroscience-inspired memory framework for AI agents</p>
  <p align="center"><a href="https://afx-team.github.io/hippocampus/">📖 Documentation</a> · <a href="README.md">English</a> | <a href="README_ZH.md">中文</a></p>
</p>

<p align="center">
  <a href="https://afx-team.github.io/hippocampus/"><img src="https://img.shields.io/badge/docs-afx--team.github.io-blue" alt="Documentation"></a>
  <a href="https://github.com/afx-team/hippocampus/actions"><img src="https://github.com/afx-team/hippocampus/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/afx-hippocampus/"><img src="https://img.shields.io/pypi/v/afx-hippocampus" alt="PyPI"></a>
  <a href="https://github.com/afx-team/hippocampus/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
  <img src="https://img.shields.io/pypi/pyversions/afx-hippocampus" alt="Python">
</p>

---

Hippocampus gives your AI agents a **brain-like memory system**. Just like the human hippocampus consolidates short-term experiences into long-term knowledge, this framework automatically organizes, prioritizes, and forgets memories so your agents stay sharp.

## Table of Contents

- [Background & Motivation](#background--motivation)
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Supported Models](#supported-models)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [Acknowledgments](#acknowledgments)
- [License](#license)

## Background & Motivation

Current AI agents treat every conversation as stateless — they forget everything after each session. While existing memory solutions exist, they have significant limitations:

- **Mem0** only adds memories, never consolidates or resolves conflicts
- **Letta** requires a separate "sleeptime agent" and external databases
- **Zep** depends on PostgreSQL + Neo4j, with complex setup

Hippocampus addresses these gaps with a **zero-config, automatic memory lifecycle** inspired by neuroscience. The human hippocampus doesn't just store memories — it classifies, consolidates, and prunes them. This framework brings that same intelligence to AI agents.

| Feature | Mem0 | Letta | Zep | **Hippocampus** |
|---------|------|-------|-----|-----------------|
| Multi-model support | Yes | Yes | Yes | Via [LiteLLM](https://github.com/BerriAI/litellm) |
| Knowledge graph | Partial | No | Yes | Tag-based |
| Web management UI | Yes | Cloud only | Cloud only | Built-in SPA |
| [MCP](https://modelcontextprotocol.io/) Server | Yes | Consumer only | Yes | Built-in, auto-start |
| Memory consolidation | ADD-only | Sleeptime Agent | Contradiction resolve | **Automatic + conflict resolve** |
| Forgetting / decay | No | No | Temporal invalidation | **Dynamic TTL** |
| Zero-config deploy | API key required | API key + DB | Postgres + Neo4j | **SQLite + local embed** |

## Features

- **Brain-inspired memory partitions** — Semantic, Episodic, Preference, Procedural, and Custom partitions modeled after cognitive science ([CoALA framework](https://arxiv.org/abs/2309.02427))
- **Automatic consolidation** — Agentic RAG pipeline classifies, resolves conflicts, and extracts tags into a knowledge graph
- **Dynamic forgetting** — TTL-based decay: frequently used memories survive, neglected ones fade
- **Hybrid retrieval** — Three-path search (vector + keyword + graph) with recency/importance/relevance scoring
- **Zero-config setup** — SQLite + local embedding, no external services required
- **Multi-model support** — Works with OpenAI, Anthropic, Qwen, GLM, Kimi, and 100+ providers via LiteLLM
- **Built-in Web Console** — Memory CRUD, search, and graph visualization in a single-page app
- **MCP Server** — Native integration with Claude Code and other MCP-compatible clients

## Quick Start

```bash
pip install afx-hippocampus      # Install
hippocampus init                  # Initialize (creates hippocampus.json + SQLite DB)
hippocampus config set llm_api_key sk-your-key-here  # Set LLM key
hippocampus start                 # Start server → http://localhost:8321/
```

Open http://localhost:8321/ for the **Web Console**, or http://localhost:8321/docs for the API docs.

## Installation

### pip (recommended)

```bash
pip install afx-hippocampus
```

### Docker

```bash
git clone https://github.com/afx-team/hippocampus.git && cd hippocampus
docker compose -f docker/docker-compose.yml up
```

### One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/afx-team/hippocampus/main/scripts/install.sh | sh
```

### PostgreSQL backend (production)

```bash
pip install afx-hippocampus[pg]
hippocampus config set storage_type postgresql
hippocampus config set pg_url postgresql://user:pass@localhost/hippocampus
```

## Usage

### Store and search memories

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

### How it works

Memories flow through four stages — inspired by how the human hippocampus consolidates short-term experiences into long-term knowledge:

| Stage | What Happens | Trigger |
|-------|-------------|---------|
| **Ingest** | New memories land in the working memory inbox (`mem_hippocampus`) | API write |
| **Consolidate** | Agent classifies into partition, resolves conflicts, extracts tags → Knowledge Graph | Periodic / manual |
| **Retrieve** | Three-path hybrid search (vector + keyword + graph) with recency/importance/relevance scoring | API search |
| **Forget** | Dynamic TTL: `base × (1 + log(access)) × importance × exp(-decay × days)` — frequently used memories survive, neglected ones fade | Periodic |

> Full details: [Memory Lifecycle](https://afx-team.github.io/hippocampus/concepts/memory-lifecycle.html) · [Consolidation](https://afx-team.github.io/hippocampus/concepts/consolidation.html) · [Hybrid Search](https://afx-team.github.io/hippocampus/concepts/hybrid-search.html) · [Forgetting](https://afx-team.github.io/hippocampus/concepts/forgetting.html)

### Architecture

```mermaid
flowchart TB
    subgraph Interface["Interface Layer"]
        direction LR
        A1["REST API"]
        A2["MCP Server"]
        A3["CLI"]
        A4["Web Console"]
    end

    subgraph Core["Hippocampus Core"]
        B1["Working Memory Inbox"]
        B2["Consolidation Agent"]
        B3["Recall Agent · Agentic RAG"]
        B4["Scheduler · APScheduler"]
    end

    subgraph Engine["Processing Engine"]
        direction LR
        C1["Hybrid Retrieval\nVector · FTS · Graph"]
        C2["Knowledge Graph\nTag-based · NetworkX"]
        C3["Scoring\nRecency · Importance · Relevance"]
        C4["Dynamic Forgetting\nEbbinghaus TTL Decay"]
    end

    subgraph Infra["Infrastructure"]
        direction LR
        D1["Storage\nSQLite + sqlite-vec\nPostgreSQL + pgvector"]
        D2["Embedding\nLocal · sentence-transformers\nAPI · LiteLLM"]
        D3["LLM\n100+ providers\nvia LiteLLM"]
    end

    subgraph Parts["Memory Partitions"]
        direction LR
        E1["Semantic"]
        E2["Episodic"]
        E3["Preference"]
        E4["Procedural"]
        E5["Custom"]
    end

    Interface --> Core
    Core --> Engine
    Engine --> Infra
    Infra --> Parts
```

## API Documentation

Hippocampus provides a RESTful API for memory management:

- **Interactive docs**: http://localhost:8321/docs (Swagger UI)
- **Full API reference**: [API Documentation](https://afx-team.github.io/hippocampus/api/)

Key endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/memories` | Store a new memory |
| `GET` | `/api/v1/memories/{id}` | Get memory by ID |
| `DELETE` | `/api/v1/memories/{id}` | Delete a memory |
| `POST` | `/api/v1/search` | Hybrid search |
| `POST` | `/api/v1/admin/consolidate` | Trigger consolidation |
| `GET` | `/api/v1/graph/tags` | List knowledge graph tags |
| `GET` | `/api/v1/graph/neighbors/{tag}` | Explore tag relationships |

## Configuration

All config lives in **`hippocampus.json`** — no environment variables needed.

```bash
hippocampus config list                    # View all settings
hippocampus config set llm_model openai/gpt-4o  # Change model
hippocampus config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1  # Qwen/GLM/Kimi
```

| Field | Default | Description |
|-------|---------|-------------|
| `llm_model` | `openai/gpt-4o-mini` | LLM model identifier (via [LiteLLM](https://github.com/BerriAI/litellm)) |
| `llm_api_key` | `null` | LLM provider API key (required for consolidation) |
| `llm_base_url` | `null` | Custom LLM API endpoint (for Qwen/GLM/Kimi) |
| `storage_type` | `sqlite` | `sqlite` or `postgresql` |
| `embedding_enabled` | `true` | Set `false` to disable vector search |
| `port` | `8321` | Server port |
| `consolidation_interval_seconds` | `3600` | How often consolidation runs |
| `base_ttl_hours` | `168` | Base memory TTL before decay |

> Full config reference: [Configuration Guide](https://afx-team.github.io/hippocampus/guide/configuration.html)

## Supported Models

Via [LiteLLM](https://github.com/BerriAI/litellm), Hippocampus works with any major LLM provider:

| Provider | Model Example | Config |
|----------|--------------|--------|
| OpenAI | `openai/gpt-4o-mini` | `llm_api_key` |
| Anthropic | `anthropic/claude-3-haiku-20240307` | `llm_api_key` |
| Qwen (Alibaba) | `openai/qwen-plus` | `llm_api_key` + `llm_base_url` |
| GLM (Zhipu) | `openai/glm-4` | `llm_api_key` + `llm_base_url` |
| Kimi (Moonshot) | `openai/moonshot-v1-8k` | `llm_api_key` + `llm_base_url` |

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines including development setup, testing, and pull request process.

### Development setup

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

## Acknowledgments

This project builds on research from:

- [Generative Agents](https://arxiv.org/abs/2304.03442) — Recency-importance-relevance retrieval scoring
- [MemGPT / Letta](https://arxiv.org/abs/2310.08560) — Agent-driven memory management
- [CoALA](https://arxiv.org/abs/2309.02427) — Episodic/semantic/procedural taxonomy
- [Zep / Graphiti](https://github.com/getzep/graphiti) — Temporal knowledge graph

See [research notes](https://github.com/afx-team/hippocampus/tree/main/repo_pages/papers/) for detailed survey.

## License

[MIT License](LICENSE)
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

```
          Write memory
               |
               v
    +---------------------+
    |    HIPPOCAMPUS       |     Working memory inbox
    |    (mem_hippocampus) |     All new memories land here
    +---------------------+
               |
          Consolidation Agent (periodic)
          - Recall related memories (Agentic RAG)
          - Classify into partition
          - Resolve conflicts
          - Extract tags -> Knowledge Graph
               |
      +--------+--------+--------+--------+
      v        v        v        v        v
  SEMANTIC  EPISODIC  PREFERENCE PROCEDURAL CUSTOM
   Facts    Events    Likes/     Skills     Your own
            History   Dislikes   How-to     partitions
      |        |        |        |        |
      +--------+--------+--------+--------+
               |
          Forgetting Job (periodic)
          TTL = base * (1 + log(access)) * importance * exp(-decay * days)
               |
               v
          Expired memories removed
```

## Quick Start

```bash
# Install (requires Python >= 3.12)
pip install afx-hippocampus

# Initialize project (creates hippocampus.json + SQLite DB)
hippocampus init

# Configure your LLM API key (required for memory consolidation)
hippocampus config set llm_api_key sk-your-key-here

# Start the server
hippocampus start
```

Open http://localhost:8321/ for the **Web Console**, or http://localhost:8321/docs for the API documentation.

### Docker

```bash
git clone https://github.com/afx-team/hippocampus.git
cd hippocampus
docker compose -f docker/docker-compose.yml up
```

### One-line Install

```bash
curl -fsSL https://raw.githubusercontent.com/afx-team/hippocampus/main/scripts/install.sh | sh
```

## API Usage

### Store a memory

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers dark mode and compact layout",
    "tags": ["preference", "ui"],
    "importance_score": 7.5
  }'
```

### Search memories

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "UI preferences", "top_k": 5}'
```

### Manage partitions

```bash
# List all partitions
curl http://localhost:8321/api/v1/partitions

# Create a custom partition
curl -X POST http://localhost:8321/api/v1/partitions \
  -H "Content-Type: application/json" \
  -d '{"id": "mem_project", "name": "Project Context", "description": "Current project knowledge"}'
```

### Trigger consolidation manually

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

### Explore the knowledge graph

```bash
# List all tags
curl http://localhost:8321/api/v1/graph/tags

# Find tag neighbors
curl http://localhost:8321/api/v1/graph/neighbors/python?depth=2

# Find path between tags
curl "http://localhost:8321/api/v1/graph/path?from=python&to=machine-learning"
```

## Configuration

All configuration lives in a single file: **`hippocampus.json`**. No environment variables needed.

### CLI Config Management

```bash
# View all settings
hippocampus config list

# Get a single value
hippocampus config get llm_model

# Set values (saved to hippocampus.json immediately)
hippocampus config set llm_api_key sk-your-key-here
hippocampus config set llm_model openai/gpt-4o
hippocampus config set llm_base_url https://api.example.com/v1
hippocampus config set port 9000
hippocampus config set embedding_enabled false
```

You can also edit `hippocampus.json` directly or use the **Settings page** in the Web Console.

### hippocampus.json

```json
{
  "storage_type": "sqlite",
  "db_path": "hippocampus.db",
  "embedding_enabled": true,
  "embedding_model": "all-MiniLM-L6-v2",
  "llm_model": "openai/gpt-4o-mini",
  "llm_base_url": null,
  "llm_api_key": "sk-your-key-here",
  "host": "0.0.0.0",
  "port": 8321,
  "consolidation_interval_seconds": 3600,
  "forget_interval_seconds": 1800,
  "base_ttl_hours": 168,
  "decay_factor": 0.693,
  "weight_recency": 1.0,
  "weight_importance": 1.0,
  "weight_relevance": 1.0
}
```

### Key Configuration Fields

| Field | Default | Description |
|-------|---------|-------------|
| `llm_model` | `openai/gpt-4o-mini` | LLM model identifier (via LiteLLM) |
| `llm_api_key` | `null` | LLM provider API key (required for consolidation) |
| `llm_base_url` | `null` | Custom LLM API endpoint (for Qwen/GLM/Kimi) |
| `storage_type` | `sqlite` | `sqlite` or `postgresql` |
| `embedding_enabled` | `true` | Set `false` to disable vector search |
| `port` | `8321` | Server port |
| `consolidation_interval_seconds` | `3600` | How often consolidation runs (seconds) |
| `base_ttl_hours` | `168` | Base memory TTL before decay (hours) |

### Storage Backends

**SQLite (default)** — zero-config, single file, great for personal use and development.

```bash
hippocampus config set storage_type sqlite
hippocampus config set db_path hippocampus.db
```

**PostgreSQL + pgvector** — production-grade, connection pooling, native vector types.

```bash
pip install afx-hippocampus[pg]
hippocampus config set storage_type postgresql
hippocampus config set pg_url postgresql://user:pass@localhost/hippocampus
```

## Memory Lifecycle

1. **Ingest** — New memories are written to the `mem_hippocampus` (working memory) partition via API.

2. **Consolidate** — A periodic agent processes working memories:
   - Uses **Agentic RAG** to recall related historical memories
   - LLM classifies the memory into the right partition (semantic / episodic / preference / procedural)
   - Conflicts with existing memories are detected and resolved
   - Tags are extracted and added to the **knowledge graph**

3. **Retrieve** — Search combines three signals:
   - **Recency** — exponential decay since last access
   - **Importance** — LLM-rated 0-10 score
   - **Relevance** — vector cosine similarity (when enabled)

4. **Forget** — A periodic job computes dynamic TTL for each memory:
   ```
   TTL = base_ttl * (1 + log(access_count)) * (importance / 5) * exp(-decay * days_since_access)
   ```
   Frequently accessed, high-importance memories live longer. Neglected memories fade away.

## Project Structure

```
src/hippocampus/
    config/       # Settings + config loading
    models/       # Pydantic data models
    storage/      # SQLite + PostgreSQL backends (protocol-based)
    embedding/    # Sentence-transformers embedder (optional)
    retrieval/    # Recency-importance-relevance scoring
    graph/        # NetworkX tag knowledge graph
    agents/       # LLM-powered consolidation + recall
    scheduler/    # APScheduler consolidation + forgetting jobs
    server/       # FastAPI REST API
    cli/          # Click CLI (init / start / status)
```

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
- [ ] MCP server for Claude Code / OpenClaw integration
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

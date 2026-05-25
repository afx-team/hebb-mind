# Hebb Mind

Neuroscience-inspired memory framework for AI agents. Open-source under [github.com/afx-team](https://github.com/afx-team), distributed on PyPI as `hebb-mind`.

---

## Priority Hierarchy

When rules conflict, follow this priority order:
1. **MUST** — Non-negotiable constraints (违反则输出无效)
2. **SHOULD** — Strong recommendations (默认遵守，可明确说明理由后偏离)
3. **MAY** — Optional suggestions (视具体情况采用)

---

## Project Context

**Status**: Production (PyPI `hebb-mind` v0.1.1, alpha)
**Domain**: Long-term memory for LLM agents — write, consolidate, recall, forget
**Surfaces**: Python package, Click CLI (`hebb`), FastAPI server, MCP server (stdio), web console, Claude Code + Codex integrations
**Docs site**: VitePress → GitHub Pages at https://afx-team.github.io/hebb-mind/

### Current Focus
- [x] Core memory pipeline (ingest → consolidate → retrieve → forget)
- [x] SQLite + Postgres backends, hybrid search, knowledge graph
- [x] CLI, FastAPI server, MCP server, Claude Code / Codex installers
- [x] VitePress docs site, Docker image, eval suite
- [ ] Public Python facade (`HebbMind` client) — see `reports/analysis/audit-architecture.md`
- [ ] Custom exception hierarchy
- [ ] Storage protocol slim-down + tag pagination fix

---

## Directory Architecture

```
hebb-mind/
├── src/hebb/                 # Python package
│   ├── agents/               # Recall + consolidation agents (LiteLLM-backed)
│   ├── cli/commands/         # Click subcommands: setup, start, stop, doctor, model, service, config, mcp, workspace, init
│   ├── config/               # Pydantic Settings, JSON loader, workspace resolution
│   ├── embedding/            # local (sentence-transformers) + api (LiteLLM) providers, model catalog
│   ├── graph/                # NetworkX-backed tag knowledge graph (JSON-persisted)
│   ├── ingest/               # Conversation parsers (auto-detect format, normalize)
│   ├── integrations/         # claude_code/, codex/ — installers, hooks, transcript parsing
│   ├── mcp/                  # MCP stdio server (write/search/consolidate tools)
│   ├── models/               # Pydantic DTOs (memory, partition, graph, ingest)
│   ├── retrieval/            # Hybrid searcher (vector + keyword + graph), composite scorer
│   ├── scheduler/            # APScheduler: daily consolidation + interval forgetting
│   ├── server/               # FastAPI app + routers (memories, search, partitions, graph, admin, config, health)
│   ├── static/               # Web console (HTML/CSS/JS) mounted at /
│   ├── storage/              # MemoryStore/PartitionStore protocols + sqlite + pg implementations
│   └── utils/                # Service helpers (PID, URL), MCP stdout guard
├── tests/                    # pytest suite (asyncio_mode=auto)
├── eval/                     # LongMemEval / LoCoMo benchmark harness
├── examples/                 # Runnable Python SDK demos
├── repo_pages/               # VitePress docs site → GitHub Pages (PUBLIC-FACING)
│   ├── .vitepress/           # VitePress config
│   ├── {guide,concepts,api,advanced}/  # English docs
│   └── zh/                   # Chinese mirror
├── reports/                  # Internal research outputs (NOT for publication)
│   ├── papers/               # Academic paper notes
│   ├── analysis/             # Audit + project analyses
│   ├── design/               # Architecture and design docs
│   └── surveys/              # Research surveys
└── results/                  # Eval outputs
```

**CRITICAL DISTINCTION**:
- `repo_pages/` = **Public website** (VitePress → GitHub Pages) — curated docs for users
- `reports/` = **Internal research** — raw notes, audits, design drafts (not for publication)

**File Placement Rules**:
| Content Type | Location | Visibility |
|-------------|----------|------------|
| User documentation | `repo_pages/` | Public (GitHub Pages) |
| Paper summaries | `reports/papers/` | Internal |
| Project analysis | `reports/analysis/` | Internal |
| Architecture design | `reports/design/` | Internal |
| Research surveys | `reports/surveys/` | Internal |

**MUST NOT**:
- Put research notes in `repo_pages/` — they go in `reports/`
- Put public docs in `reports/` — they go in `repo_pages/`
- Commit secrets, sensitive analysis, or proprietary data to `repo_pages/` (it gets published)

---

## Code Standards (MUST when implementing)

```python
# MUST: Type hints on all public functions (mypy strict is enabled in pyproject.toml)
def process_memory(memory: Memory) -> ProcessedMemory: ...

# MUST: Docstring with Args, Returns, Raises for public APIs
def retrieve(query: str, k: int = 5) -> list[Memory]:
    """Retrieve top-k relevant memories.

    Args:
        query: Search query string.
        k: Number of results to return.

    Returns:
        Memories sorted by composite score, descending.
    """
```

- **MUST NOT** use relative imports across modules — import from `hebb.<module>`.
- **MUST NOT** hardcode API keys, secrets, or absolute paths outside the user's workspace.
- **MUST NOT** mix Chinese and English in the same document (per-language pages only).
- **MUST** add unit tests for new core logic; E2E for new workflows.
- **SHOULD** use `mermaid` for architecture / data-flow diagrams (renders in VitePress and on GitHub).
- **SHOULD** keep CLI exits via `click.ClickException`; reserve `SystemExit(1)` for unrecoverable failures.

---

## Decision Guidelines

| Decision | YES if | NO if |
|----------|--------|-------|
| New module | Independent lifecycle, clear API boundary, or >500 lines | Just grouping related functions — use a class |
| New abstraction | Pattern repeats 3+ times | Used once or twice — wait for the pattern to stabilize |
| Design doc in `reports/design/` | Affects 2+ modules, new dependency, or API contract change | Local refactor or single-module bug fix |

---

## Engineering Principles

1. **Architecture clarity** — directory structure equals module boundaries.
2. **Semantic naming** — names reveal intent, not implementation.
3. **Multi-model support** — Claude / GPT / Llama / Qwen via LiteLLM; embedding via sentence-transformers or any LiteLLM embedding provider.
4. **Test coverage** — unit tests for logic, E2E for workflows, eval suite for retrieval quality.
5. **Incremental complexity** — start simple, add abstraction only after the pattern stabilizes.

---

## Quality Checklist

Before marking a task complete:

- [ ] File placed in the correct directory (`repo_pages/` vs `reports/`)
- [ ] Naming follows convention
- [ ] Public APIs have type hints + Args/Returns/Raises docstrings
- [ ] Tests added or updated
- [ ] Commit message explains *why*, not *what*
- [ ] No secrets, no absolute personal paths

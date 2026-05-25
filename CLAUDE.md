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

---

## Publication Boundary

- `repo_pages/` is the **public website** (VitePress → GitHub Pages). User-facing docs go here. Never commit secrets, internal analysis, or proprietary data — anything merged is published.
- `reports/` is **internal-only** (papers, analysis, design, surveys). Research notes, audits, and design drafts go here, not in `repo_pages/`.

---

## User Path Ownership (MUST)

The user's complete path — install → first command → background operation → uninstall — **is the product.** Every crossing between environments (shell ↔ GUI app ↔ launchd ↔ systemd ↔ Task Scheduler ↔ a third-party CLI's subprocess) is **the framework's responsibility, never the user's.**

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

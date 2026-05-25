# Architecture Audit — `hebb-mind` v0.1.1

Audit date: 2026-05-15. Source tree: `/Users/xiyue/Projects/alipay/hippocampus/src/hebb/`.
Goal: identify smells that will scare contributors or rot maintenance as the project goes public.

---

## TL;DR — Top 7 issues, ranked by severity

| # | Issue | Where | Severity |
|---|-------|-------|----------|
| 1 | `__version__ = "0.1.0"` in code, but `pyproject.toml` is `0.1.1`; published wheels for both versions sit in `dist/` | `src/hebb/__init__.py:5` vs `pyproject.toml:3`; `dist/hebb_mind-0.1.0*` and `0.1.1*` | Blocker |
| 2 | Two stale egg-info dirs checked in, including a wrong package name (`hebb_ai.egg-info`) — confuses build & users browsing the repo | `src/hebb_mind.egg-info/`, `src/hebb_ai.egg-info/` (both git-tracked) | Blocker |
| 3 | No public Python facade — `from hebb import *` only exposes `__version__`; users must import 6 submodules to assemble a Memory pipeline | `src/hebb/__init__.py` (5 lines) | High |
| 4 | Zero custom exceptions; layers leak `ValueError`, `KeyError`, `Exception`. Catch-all `except Exception` appears 11+ times silently degrading | grep `class.*Error` returns only `ErrorResponse` Pydantic model | High |
| 5 | `consolidate_memory` and `_consolidate_one` in `ConsolidationAgent` are 90% duplicate code (steps 1–7 copy-pasted) — bug magnet | `agents/consolidation_agent.py:64-155` vs `:393-470` | High |
| 6 | `MemoryStore` protocol contains 12 methods including 4 update-oriented sidecars (`update_access`, `update_embedding`, `update_expiry`, `delete_expired`). Adding a backend is closer to 12 steps, not 4 | `storage/base.py:11-41` | High |
| 7 | Three different `is_server_running` implementations + duplicated PID/URL logic across CLI, MCP, and utils | `utils/service.py:44`, `cli/commands/start.py:45`, `mcp/server.py:41` | Medium |

Honorable mentions: SQLite tag filter does WHERE-then-Python intersection and overwrites `total` (`storage/sqlite_store.py:114-118`); embedding dimension stored mutably on `Settings` after startup (`server/app.py:40`); CORS wide-open `allow_origins=["*"]` (`server/app.py:91`); `LocalEmbedder.__init__` does I/O, env-var mutation, and offline-cache probing in 50+ lines and calls a non-existent `get_embedding_dimension()` API on `SentenceTransformer` (correct method is `get_sentence_embedding_dimension`).

---

## Module Map

**`__init__.py`** — 5 lines. Imports `_sqlite_compat` for side-effects, sets `__version__`. No re-exports. Smell: there is no curated public API; new users will wander into `storage.sqlite_store` and discover internal SQL helpers.

**`agents/`** — `LLMClient` (litellm wrapper, 91 lines), `RecallAgent` (64 lines), `ConsolidationAgent` (470 lines, the heavy hitter). Smell: `ConsolidationAgent` reuses the same recall->LLM->write pattern in `consolidate_memory`, `_consolidate_one`, and `_consolidate_session_chunk` with no shared private helper. Three almost-identical "build prompt context" blocks. `_parse_json` in `LLMClient` (`agents/llm_client.py:58-90`) silently returns `{}` on failure — callers never know.

**`cli/`** — Click group `main` with 14 subcommands (`cli/main.py`). Each command is its own module under `cli/commands/`. Smell: heavy use of `raise SystemExit(1)` (15 sites) instead of `click.ClickException` (only 5 commands use it). Mixed exit-code style. Rich console reused via per-module singletons.

**`config/`** — `Settings` Pydantic model (`config/settings.py`), JSON loader (`config/loader.py`), `resolve_workspace` (`config/workspace.py`). Smells: (a) `Settings.embedding_dim` mutated post-construction in `server/app.py:40`; Pydantic supports it but it bypasses validation. (b) `loader._coerce_value` is a hand-rolled type coercer that already exists inside Pydantic — risk of drift. (c) `ignored_types=(property,)` (`config/settings.py:13`) is required because `db_path`/`kg_path` are `@property` on a Pydantic model — works but is unidiomatic. (d) Workspace resolution lives in two places: `find_config_file` (`loader.py:20`) and `resolve_workspace` (`workspace.py:25`) — partial overlap, partially documented.

**`embedding/`** — `EmbeddingProvider` Protocol (`base.py`), `LocalEmbedder` + `NoopEmbedder` (`local.py`), `ApiEmbedder` (`api.py`), `factory.py` (mux), `catalog.py` (model picker, 291 lines). Smells: (a) `LocalEmbedder.__init__` mutates `os.environ["HF_HUB_OFFLINE"]` mid-import and restores it in a `finally` — fragile, not thread-safe (`local.py:54-108`). (b) Calls `self._model.get_embedding_dimension()` (`local.py:107`); the actual sentence-transformers API is `get_sentence_embedding_dimension()`. If this code path is exercised it will raise `AttributeError`. (Test only patches the model so the bug hides.) (c) `embedding/__init__.py` is empty (1 byte) — no facade. (d) `KNOWN_DIMS` table embeds business knowledge in `factory.py` that should live next to `catalog.py`.

**`graph/`** — Single file `knowledge_graph.py` (264 lines). NetworkX in-memory graph persisted to one big JSON. Smells: (a) Save rewrites the entire JSON every consolidation (`save()` called at end of every batch and after every session in `agents/consolidation_agent.py:140, 364, 379`). Not scalable. (b) `_load` swallows ALL exceptions and starts fresh (`graph/knowledge_graph.py:41-43`) — silent data loss. (c) BFS implemented with `queue.pop(0)` (O(n) per pop) — should be `collections.deque`.

**`ingest/`** — Conversation parsers: detector / formats / noise / normalizer / types. Reasonable size (<300 lines). `__init__.py` is just a docstring; no public facade.

**`integrations/`** — `claude_code/` (10 files: install/uninstall/recall/write/stop/transcript/dedup/cli/_client) and `codex/`. Smell: `claude_code` has its own client, dedup, transcript parser, and CLI — substantial logic that duplicates server-side work. `_client.py` is a parallel HTTP client to the one in `mcp/server.py`. Should converge on one shared async client.

**`mcp/`** — Single `server.py` (199 lines). Thin wrapper over REST. Smell: re-implements `_is_server_running`/`_base_url` as private wrappers that immediately delegate to `utils/service.py` (`mcp/server.py:36-50`). Dead indirection.

**`models/`** — Pydantic models split by domain: `memory.py`, `partition.py`, `graph.py`, `ingest.py`, `common.py`. Clean. Smell: `Memory` has 11 fields, no separation between request DTOs and persistence DTOs in `MemoryCreate` (`partition_id` defaults to magic string `"mem_hippocampus"`).

**`retrieval/`** — `searcher.py` (orchestrator, 207 lines), `scorer.py` (40 lines), `query_sanitizer.py` (172 lines). Cleanest module. Smell: `MemorySearcher._graph_search` invents a similarity score with `min(0.5 + 0.5*(w/max(w,5)), 0.9)` — magic constants undocumented (`retrieval/searcher.py:165`).

**`scheduler/`** — `manager.py` (APScheduler wrapper), `consolidation_job.py` (factory function), `forgetting_job.py`. Smell: `consolidation_job.run_consolidation` rebuilds `LLMClient`, `MemorySearcher`, `RecallAgent`, `ConsolidationAgent` on every tick (`scheduler/consolidation_job.py:27-39`) instead of reusing the ones already wired into `app.state`. Forgetting job updates every memory's `expires_at` on every interval (`scheduler/manager.py:94-101`) — N writes per N memories per 30 min. Won't scale beyond ~10k memories.

**`server/`** — FastAPI app + 7 routers. Standard layout. Smell: `server/app.py:91` sets `allow_origins=["*"]` unconditionally; `server/routers/config.py:22, 78` reload settings from disk on every request instead of using `app.state.settings` — config reads are surprisingly expensive (workspace resolution + JSON parse).

**`static/`** — Web console (HTML/CSS/JS). Out of scope here.

**`storage/`** — Two backends (`sqlite_store.py` 312 lines, `pg_store.py` 432 lines), `base.py` Protocol, `factory.py`, two migration modules, `_sqlite_compat.py`. See "Extension point analysis" below.

**`utils/`** — `service.py` (URL/PID/start helpers, 90 lines), `stdio_guard.py` (MCP stdout protection). `__init__.py` is empty. No public exports.

---

## Public API surface analysis

`from hebb import *` exposes exactly: `__version__`. To use the library programmatically (Python, not REST/MCP), a user must:

```python
from hebb.config.loader import load_settings
from hebb.storage.factory import create_stores
from hebb.embedding.factory import create_embedder
from hebb.retrieval.searcher import MemorySearcher
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.models.memory import MemoryCreate, MemoryQuery
```

— six imports from six submodules to wire one pipeline, copying the boilerplate already inside `server/app.py:24-58`. This is the single biggest "scares contributors" signal: there is no `HebbMind()` facade, no `client = HebbMind.from_config(...)`, no `await client.write(...)`, no `await client.search(...)`.

The README sells "use it as a Python library" but the only documented integration paths are CLI, MCP, and HTTP. A library-mode entry point is missing.

Type hints: present on all public functions reviewed. Docstrings: present on Settings fields and most public APIs but inconsistent — `MemorySearcher.search` has no docstring; `ConsolidationAgent.consolidate_memory` has only one line; `KnowledgeGraph` methods are mostly one-liners; CLI commands rely on Click's docstring-as-help.

---

## Extension point analysis

### Storage (CONTRIBUTING.md claims "4 steps")

Reality from `MemoryStore` Protocol (`storage/base.py:11-41`): a new backend must implement **12** methods — `create`, `get`, `list`, `update`, `delete`, `search_by_vector`, `search_by_keyword`, `get_by_partition`, `delete_expired`, `update_access`, `update_embedding`, `update_expiry` — plus 6 methods on `PartitionStore`. Plus a separate migration module, plus factory wiring, plus optional-deps in `pyproject.toml`. Realistic estimate: 18 methods, ~400 LOC, ~1 day. The 4-step claim is misleading.

Smells inside the protocol itself:
- `update_access`, `update_embedding`, `update_expiry`, `update_expiry` should be merged into one `update` or expressed via patch semantics.
- `search_by_vector` returns `list[tuple[Memory, float]]` while pgvector returns cosine similarity in `[0,1]` and SQLite returns `1/(1+L2_distance)` (`sqlite_store.py:206`). Backends produce non-comparable scores under the same name.
- Tag filtering happens in Python after SQL (`sqlite_store.py:114-118`) and silently overwrites the `total` count, so pagination breaks when `tags` is set.
- `MemoryStore.list` signature differs from `PartitionStore.list` (no `offset/limit`); inconsistent pagination contract.

### Embedding

`EmbeddingProvider` (`embedding/base.py`) has 3 methods — clean. But:
- `_create_local_embedder` swallows all exceptions and silently returns a `NoopEmbedder` (`embedding/factory.py:62-64`). User has no way to surface the underlying failure short of grep'ing logs.
- `_detect_api_dimension` does a network probe at startup for unknown models (`embedding/factory.py:85-111`). Slow startup, fails on offline boxes.
- `LocalEmbedder` and `ApiEmbedder` don't share base class; type checker only verifies via Protocol. A new provider needs to read both files to copy patterns.

### LLM

`LLMClient` is the only LLM seam. It is hard-coded to litellm (`agents/llm_client.py:8`). Adding a non-litellm provider (e.g. direct Anthropic SDK, vLLM) requires forking the class. There is no `LLMProvider` Protocol parallel to `EmbeddingProvider`. The "multi-provider via litellm" claim leaks the abstraction.

---

## Type / docstring / error-handling consistency

- **Type hints:** good, 100% on public surface I sampled. `mypy = strict` is enabled in `pyproject.toml:96`. `# type: ignore` appears 4 times — acceptable.
- **Docstrings:** uneven. CLI commands → relies on Click. Storage stores → mostly missing on private methods. Agents → present but thin. CLAUDE.md mandates Args/Returns/Raises; few methods comply.
- **Error handling:** **No custom exception hierarchy.** Layers raise `ValueError`/`KeyError`/`FileNotFoundError`/`ImportError`/`HTTPException`/`ClickException`/`SystemExit` ad-hoc. There is no `HebbMindError`, `StorageError`, `EmbeddingError`, `ConfigError` — meaning library users cannot write `except HebbMindError`. The 11 bare `except Exception` blocks (consolidation agent, embedding factory, graph load, scheduler) are particularly worrying because they swallow and continue.
- **Async/sync split:** mostly async on the data path, sync on the CLI path. Three `asyncio.run()` calls inside CLI commands (`init.py:77`, `setup.py:114`, `model.py:110`) — acceptable but means CLI cannot run inside an event loop.

---

## Concrete refactor recommendations (prioritized)

### P0 — Don't ship without fixing
1. **Sync version**: bump `src/hebb/__init__.py:5` to `0.1.1` (or load from `importlib.metadata`).
2. **Delete checked-in build artifacts**: remove `src/hebb_mind.egg-info/`, `src/hebb_ai.egg-info/`, `build/`, `dist/` from git; they are already in `.gitignore` but were committed at some point.
3. **Add a public facade**: create `HebbMind` class in `src/hebb/client.py` and re-export from `__init__.py`. Even a thin wrapper around `app.state` wiring would unblock library users.
4. **Fix `LocalEmbedder.get_embedding_dimension()` typo** (`local.py:107`) — should be `get_sentence_embedding_dimension()`. This is a latent runtime crash.
5. **Define a tiny exception hierarchy**: `HebbMindError` → `ConfigError`, `StorageError`, `EmbeddingError`, `LLMError`, `IngestError`. Replace bare `Exception` in `embedding/factory.py:62, 107`, `graph/knowledge_graph.py:41`, `agents/consolidation_agent.py:150,315,466`.

### P1 — Before 1.0
6. **De-duplicate consolidation paths**: extract a `_run_consolidation_decision(memory, related)` helper used by both `consolidate_memory` and `_consolidate_one`. ~100 lines of duplicate code disappear.
7. **Slim `MemoryStore` Protocol**: collapse `update_access`/`update_embedding`/`update_expiry` into a single typed `patch(memory_id, fields)` or attach to `update`. Document score normalization contract for `search_by_*`.
8. **Fix tag pagination**: push tag filter into SQL via `json_each` (SQLite) or `tags @> ARRAY[...]` (already done in PG); recompute `total` correctly (`storage/sqlite_store.py:114-120`).
9. **Single `is_server_running`**: delete the duplicates in `cli/commands/start.py:45` and `mcp/server.py:41`. Import from `utils/service.py`.
10. **Consolidate Claude Code HTTP client** (`integrations/claude_code/_client.py`) with `mcp/server.py`'s httpx blocks into one `HebbClient` in `utils/service.py`.

### P2 — Polish
11. **`LLMProvider` Protocol** mirroring `EmbeddingProvider`. Default impl uses litellm; users can plug their own.
12. **Replace BFS list-pop with `deque`** in `graph/knowledge_graph.py:166-175`.
13. **Stop reloading `Settings` per HTTP request** in `server/routers/config.py:22, 78`.
14. **Tighten CORS** — accept origins from `Settings.allowed_origins` (default `["http://localhost"]`).
15. **Move `KNOWN_DIMS`** from `embedding/factory.py:14` into `embedding/catalog.py` (single source of model truth).
16. **Drop empty `__init__.py` files** that say `"""Module docstring."""` and contribute nothing — or actually re-export the module's surface.

---

## "Don't ship without fixing" checklist

- [ ] `__version__` matches `pyproject.toml`
- [ ] Remove `src/*.egg-info/`, `build/`, `dist/` from git history (or at least working tree)
- [ ] Public `HebbMind` facade exposed from package root
- [ ] `LocalEmbedder.get_embedding_dimension` typo fixed
- [ ] Custom exception base class introduced; bare `except Exception:` audited
- [ ] CONTRIBUTING.md "4 steps for a new backend" updated to match reality (or the protocol shrunk)
- [ ] CORS no longer `*` by default
- [ ] Old wheels (`hebb_mind-0.1.0*`) removed from `dist/`

---

## Test coverage signals

22 test files, 2,693 LOC. Coverage is breadth-first:
- Storage: only SQLite path tested; no PG tests — adding PG tests requires a live Postgres or a docker fixture.
- Agents: `test_agents.py` (201 LOC) likely mocks `LLMClient`. Worth verifying it exercises both `consolidate_memory` and `_consolidate_one` paths (currently duplicate logic, only one tested = hidden divergence risk).
- Integrations: `test_hooks_cc.py` is the largest test (502 LOC) — Claude Code is the most-tested surface, ironic since it's also the one with the most duplicated code.
- Embedding: only catalog logic tested; `LocalEmbedder` happy path with a real model is untested (which is why the `get_embedding_dimension` typo never fired).
- No async event-loop integration tests for the scheduler running real jobs.

`asyncio_mode = "auto"` in `pyproject.toml:92` — sensible.

---

## Summary verdict

The architecture is **structurally sound** — clean module boundaries, Protocol-based abstractions, FastAPI lifespan wiring, separate ingest/retrieval/agents/scheduler concerns. A contributor reading the directory tree will understand the layout in five minutes.

What will scare them off is **surface polish**: a stale `__version__`, two checked-in `egg-info` directories (one with the wrong package name!), empty `__init__.py` files that promise modules and deliver nothing, no custom exceptions, near-duplicate code in the consolidation agent, and the absence of any "give me a `HebbMind()` and let me write/search" entry point. These are 1-day fixes individually but their accumulation gives the impression of a private prototype that was renamed and shipped, not a v0.1.1 product.

Fix the P0 list (especially items 1, 2, 3, 5) before you tweet the launch. Everything else can land in 0.2.

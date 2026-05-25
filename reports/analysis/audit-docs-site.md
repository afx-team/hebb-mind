# Documentation Site Audit — `repo_pages/` (VitePress → GitHub Pages)

**Scope.** VitePress site published to https://afx-team.github.io/hebb-mind/. Bar: mem0 / Letta / Zep public docs.

**Inputs.** `repo_pages/.vitepress/config.mts`, `index.md`, `quick-start.md`, all of `{guide,concepts,api,advanced,zh}/`. Cross-checked against `src/hebb/server/routers/`, `src/hebb/cli/`, `src/hebb/models/memory.py`, `src/hebb/config/settings.py`.

---

## TL;DR — Top 7 Gaps (severity)

1. **P0 — Config API endpoints all wrong.** `api/config.md` documents `/api/v1/config*` but code mounts the router at `/api/v1/admin/config*` (`server/app.py:105`). Every curl example 404s.
2. **P0 — Memories list pagination wrong.** Docs say `?skip&limit=20&tag=…`; code is `?offset&limit=50&tags=csv` (`routers/memories.py:23-38`).
3. **P0 — Defaults and response shapes misstated.** Search `top_k` default is 10 not 5 (`models/memory.py:80`); default `embedding_model` in code is `all-MiniLM-L6-v2` dim 384, docs say `BAAI/bge-large-en-v1.5` dim 1024 (`config/settings.py:31`); search response uses `MemorySearchResult{memory, score, recency_score, importance_score_normalized, relevance_score}` not the flat `scores` dict in `api/search.md`.
4. **P1 — Whole CLI/API surface area undocumented.** `hebb doctor`, `service install/uninstall`, `mcp` subcommand, and the `codex` group exist (`cli/main.py:30-43`) but get no page. `POST /api/v1/ingest` (`routers/memories.py:109`) and `test-embedding` / `embedding-status` (`routers/config.py:143-209`) are invisible.
5. **P1 — Missing standard pages.** No troubleshooting, FAQ, migration-from-mem0/Letta/Zep, benchmarks, security model, deployment, web-console, or changelog page. Every competitor ships these.
6. **P1 — Zero mermaid diagrams** despite CLAUDE.md SHOULD-rule. The lifecycle diagram is hand-rolled HTML in `index.md`; another is a coloured `<table>` in `concepts/memory-lifecycle.md`. Neither is reusable, neither prints, neither renders on GitHub.
7. **P2 — No social card / OG image / per-locale meta.** `config.mts` `head:` only sets a favicon. Sharing the URL produces a blank card. zh locale shares EN `<meta>` — bad for Chinese SEO.

---

## IA Assessment

`config.mts:6-52` defines one shared sidebar: Quick Start → Guide → Concepts → API → Advanced. Reasonable order, but missing top-level sections:

- **Tutorials / Recipes** (mem0, Letta both have).
- **Troubleshooting / FAQ** (Zep has both).
- **Operations / Deployment** — Docker is buried in Advanced.
- **Examples** — no end-to-end recipe.
- **Reference → Python SDK / Client** — docs assume `curl` only.

Navbar (`config.mts:79-82`) has only Quick Start and API. Competitors surface Concepts, Examples, GitHub, Discord, Changelog. Search is local — no Algolia DocSearch. There is no `404.md`, no changelog page (despite `v0.1.1` and recent `doctor`/`model`/`service`/`codex` commits), and no edit-on-GitHub fallback for missing pages.

---

## Per-Section Assessment

**`index.md`** — solid hero, install banner, lifecycle, architecture, and competitor table. But >200 lines of inline `<style>`/`<script>` in markdown — should be a Vue component in `.vitepress/theme/`. "Built-in SPA" claim depends on `static/` actually shipping a console; verify before launch. Competitor cells are unsourced.

**`quick-start.md`** — three-step path is correct, but the "under a minute" headline ignores a multi-hundred-MB embedding model download (3-5 min on home internet). `consolidation_time 18:00` example is unquoted and may break in some shells. Mentions `service install` and `stop` without any guide page for them; user has to dig into `api/cli.md`.

**`guide/`** — five files, no recipes. `installation.md` duplicates quick-start instead of going deeper (extras, source build, air-gapped, ARM). `claude-code.md` is the strongest page (mode table, hooks lifecycle, troubleshooting). `codex.md` is 47 lines and hollow. `mcp-integration.md` covers Claude Code/Codex/Claude Desktop/Cursor but ignores Continue, Cline, VS Code Copilot Chat, OpenAI Agents SDK. No `web-console.md`, no `python-sdk.md`.

**`concepts/`** — five files, generally good prose. Missing: importance scoring (a draft already exists in `reports/design/importance-scoring-design.md` but isn't published), embedding-model selection / dimensions, partition-design philosophy, scheduler model. **Internal contradiction:** `memory-lifecycle.md:73` says consolidation runs "every 3600 seconds / 1 hour"; `consolidation.md:49` says "automatically once per day … `consolidation_time` (default `18:00`)". Code (`config/settings.py:53`) and commit `47e1a1e` confirm daily — `memory-lifecycle.md` is wrong. `forgetting.md` formula + worked examples is best-in-class.

**`api/`** — seven hand-written pages. No generated OpenAPI surface even though FastAPI already serves `/docs` and `/openapi.json`. Drift is severe (table below). `cli.md` has a cut-and-paste bug: the `## hebb model` section (line 30) actually contains `init` content ("Created files: hebb.json…") and an `init` example block (lines 47-56). Missing pages: `health-status.md`, `ingest.md`, `embedding-test.md`.

**`advanced/`** — only `storage-backends.md` and `multi-model.md`. `storage-backends.md` has duplicated `## Running as a Background Service` headings (lines 173 and 255), and the docker-compose example ends with a truncated `pg-` (line 156) — copy-paste breaks. Missing: production hardening, observability, backup/restore, scaling, security (current `app.py:91-95` sets `allow_origins=["*"]` and no auth — completely open and undisclosed).

**`zh/` mirror** — structurally complete (every EN page has a zh counterpart of similar name and 80-90% length), but inherits every EN drift verbatim. The locale config (`config.mts:86-105`) overrides only `nav`/`sidebar`, so `<title>` and `<meta>` stay English — Chinese SEO is essentially nil. `zh/quick-start.md:19` adds a "默认工作目录" claim not present in EN — minor.

---

## Specific Drift Between Docs and Code (file:line)

| Doc claim | Reality | Evidence |
|---|---|---|
| `GET/PUT /api/v1/config*` | Mounted at `/api/v1/admin/config*` | `api/config.md` vs `server/app.py:105` |
| `PUT /api/v1/config` returns `{status:"updated", key, value}` | Returns `{key, value, restart_required:bool}` | `api/config.md:80-86` vs `routers/config.py:31-70` |
| `POST .../test-llm` returns `{status, model, message}` | Returns `{success, response, model}` or `{success:false, error}` | `api/config.md:116-143` vs `routers/config.py:90-133` |
| `GET .../config/fields` includes `sensitive` | No `sensitive` field; has `{key,type,description,default}` | `api/config.md:160-178` vs `routers/config.py:212-234` |
| `GET /memories?skip&limit=20&tag` | `?offset&limit=50 (max 200)&tags=csv` | `api/memories.md:11-22` vs `routers/memories.py:23-38` |
| Search `top_k` default 5 | Default 10, max 100 | `api/search.md:16` vs `models/memory.py:80` |
| Search response: flat `scores:{recency,importance,relevance,composite}` | `MemorySearchResult{memory, score, recency_score, importance_score_normalized, relevance_score}` — no `composite` | `api/search.md:64-92` vs `models/memory.py:86-100` |
| Default `embedding_model BAAI/bge-large-en-v1.5` dim 1024 | Resting default `all-MiniLM-L6-v2` dim 384 (setup overrides) | `guide/configuration.md:78-79` vs `config/settings.py:31-32` |
| `GET /admin/stats` returns `partitions` as flat `{id:count}` and `knowledge_graph:{total_tags,total_edges}` | Actual: `partitions: list[{id,name,memory_count,enabled}]`, `graph:{tag_count,edge_count}`, plus `scheduler` | `api/admin.md:65-82` vs `routers/admin.py:60-80` |
| `POST /admin/consolidate` returns `{status:"started", message}` | Returns `{processed, succeeded, failed}` synchronously | `api/admin.md:21-26` vs `routers/admin.py:25-44` |
| `POST /admin/forget` returns `{status:"started", message}` | Returns `{deleted: int}` | `api/admin.md:42-49` vs `routers/admin.py:47-57` |
| `GET /status` exposes `storage_type`, scheduler interval/last_run/next_run | Actual: `{version, scheduler, embedding:{enabled,provider,model,dimension,available}}`; no `storage_type`; scheduler shape comes from `SchedulerManager.get_status` | `api/admin.md:106-141` vs `routers/health.py:22-38` |
| `GET /health` returns `{status:"ok"}` | `{status:"ok", version}` | `api/admin.md:88-103` vs `routers/health.py:17-19` |
| Memory create response shows only `created_at, updated_at` | `Memory` model also has `last_accessed_at, access_count, expires_at, metadata, source` | `api/memories.md:82-93` vs `models/memory.py:55-71` |
| `cli.md` `hebb model` section | Actually contains `init` content (cut-and-paste bug) | `api/cli.md:30-56` |
| Endpoint `POST /api/v1/ingest` undocumented | Exists | `routers/memories.py:109-147` |
| `POST /admin/config/test-embedding`, `GET /admin/config/embedding-status` undocumented | Exist | `routers/config.py:143-209` |
| `hebb doctor`, `service install/uninstall`, `mcp` subcommand, `codex` group not in `cli.md` | Registered in `cli/main.py:30-43` | — |

---

## Missing Pages a User Would Expect

1. Troubleshooting (model download, port conflicts, dim mismatch, "consolidation never runs", LLM 401).
2. FAQ (model swap survival, SQLite→Postgres migration, multi-tenant, cost per 1k memories).
3. Migration from mem0 / Letta / Zep — the home-page comparison table provokes the question; site never answers.
4. Performance / benchmarks — every competitor publishes some.
5. Security model — current CORS is wide open; must say so before public deploy.
6. Deployment guide (Docker promoted out of Advanced; Kubernetes / fly.io / Render recipes).
7. Web Console guide — promised on home page, undocumented.
8. Python SDK / client usage.
9. Changelog / release notes.
10. Contributing.
11. Architecture deep-dive (mermaid).
12. `POST /ingest` conversation ingest end-to-end.

---

## Top 10 Quick Wins

1. Fix every `/api/v1/config` path → `/api/v1/admin/config` in `api/config.md` (and zh mirror).
2. Sync request/response shapes to actual Pydantic models — ideally autogenerate via `vitepress-openapi` from `/openapi.json`.
3. Fix the `cli.md` cut-and-paste so `hebb model` shows model commands; add `doctor`, `service`, `mcp`, `codex`.
4. Add `guide/troubleshooting.md` (6 entries: model download, port, dim mismatch, no recall, consolidation skipped, LLM 401).
5. Add OG meta + social card in `config.mts` `head:` — ~6 lines, 30 min, applies everywhere the URL is shared.
6. Replace inline-HTML diagrams in `index.md` and `concepts/memory-lifecycle.md` with mermaid; CLAUDE.md SHOULD-rule.
7. Run code blocks through CI or at minimum a manual smoke pass — would catch the truncated `pg-` in `storage-backends.md:156`.
8. Reconcile consolidation schedule wording (memory-lifecycle vs consolidation pages).
9. Add Chinese `description` and OG title in zh locale.
10. Surface FastAPI `/docs` and `/openapi.json` from a "Live API" navbar link.

---

## Suggested New IA (sidebar sketch)

```
Quick Start
Get Started
  ├ Installation
  ├ Configuration
  └ Web Console                       (NEW)
Integrations
  ├ Claude Code
  ├ Codex
  ├ Cursor / Continue / Cline         (NEW)
  └ MCP Reference
Concepts
  ├ Memory Lifecycle
  ├ Consolidation
  ├ Forgetting
  ├ Hybrid Search
  ├ Knowledge Graph
  ├ Importance Scoring                (NEW; promote design doc)
  └ Architecture Deep-Dive            (NEW; mermaid)
Recipes / Tutorials                   (NEW top-level)
  ├ Personal assistant
  ├ Ingest a chat export
  ├ Multi-agent shared memory
  └ Migrate from mem0 / Letta / Zep
Reference
  ├ REST API
  │   ├ Memories
  │   ├ Search
  │   ├ Ingest                        (NEW)
  │   ├ Partitions
  │   ├ Knowledge Graph
  │   ├ Admin
  │   ├ Config
  │   └ Health & Status               (NEW)
  ├ CLI                               (split: setup/server/integrations/config)
  └ Configuration Reference           (auto-generated from Settings)
Operations                            (NEW top-level)
  ├ Docker
  ├ systemd / launchd
  ├ PostgreSQL Backend
  ├ Backup & Restore                  (NEW)
  ├ Observability                     (NEW)
  └ Security & Auth                   (NEW)
Advanced
  ├ Multi-model
  └ Storage Backends (deep)
Resources
  ├ Troubleshooting                   (NEW)
  ├ FAQ                               (NEW)
  ├ Benchmarks                        (NEW)
  ├ Changelog                         (NEW)
  └ Contributing                      (NEW)
```

Promotes Operations and Recipes to top-level (currently zero), splits Reference, and adds the four "perceived-maturity" pages every competitor ships: troubleshooting, FAQ, benchmarks, changelog.

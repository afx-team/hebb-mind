# Web Console Restructure — 4 Memory Modules

**Date:** 2026-06-22
**Status:** In progress
**Scope:** web console IA + components + i18n + CSS, plus a lightweight backend forgetting run tracker.

## Problem

The console grew to **8 flat pages** (Dashboard, Memories, Search, Partitions, Graph,
CC Memory, Forgetting, Settings) with no conceptual grouping. Related functions are
scattered: consolidation lives on Dashboard *and* Settings→Lifecycle; recall tuning is
split between Search (per-query) and Settings→Retrieval (global); forgetting tuning is
its own page while its global knobs sit in Settings→Lifecycle and its trigger on
Dashboard. The mental model (write → activate → consolidate → forget) is invisible.

## Target IA (decided with user)

Sidebar = **four memory-lifecycle modules** + a divider + **CC Memory · System · Docs**:

| id | Sidebar (EN / 中文) | Page contents |
|----|--------------------|---------------|
| `manage` | Manage / 记忆管理 | **Overview stat band** (total memories · partitions · graph nodes/edges) on top, then in-page **tabs**: 记忆 (list + add) · 分区 (distribution chart + list + add + edit) · 图谱 (knowledge graph) |
| `activate` | Activate / 记忆激活 | **Recall test** (search w/ weight sliders + results) on top, then **Recall parameters** (recall pipeline toggles · rerank · scoring weights) |
| `consolidate` | Consolidate / 记忆巩固 | **Trigger** (Organize now + pending/auto-next meta + interrupted note) · **Run records** (history w/ live log) · **Consolidation config** (time, concurrency, max tokens, drain-empty) |
| `forget` | Forget / 记忆遗忘 | **Trigger** (Clean up now) · **Forget records** (NEW tracker) · **Global config** (base TTL, decay, sweep interval) · **Per-partition tuning** (curve + matrix + impact + override) |
| `cc-memory` | CC Memory / CC 记忆 | unchanged |
| `system` | System / 系统设置 | LLM · Embedding · Storage · Server (was Settings minus Retrieval/Lifecycle) |
| `docs` | Docs / 文档 | external link |

Decisions: overview folds into Manage top (no standalone Dashboard); 记忆管理 uses
**in-page tabs** (single-layer sidebar, no nested nav); a **lightweight forgetting run
tracker** is added so 记忆遗忘 shows real records.

## Frontend file plan

- **`index.html`** — rewrite sidebar to the 6 items + divider + docs.
- **`js/app.js`** — router parses `#page` and `#page/sub`; passes `sub` to `render(root, sub)`
  for deep-linkable tabs. New `pages` map.
- **NEW `js/components/config-section.js`** — shared config primitives extracted from
  settings.js: `offerRestart`, `buildGenericSection`, `renderInput`, `RESTART_KEYS`,
  `SENSITIVE_KEYS`, `esc`. Reused by activate / consolidate / forget / system.
- **NEW `js/components/manage.js`** — overview band + tabs; delegates tab bodies to
  `renderMemories` / `renderPartitions` / `renderGraph` (refactored to render content
  without their own `.page-header`).
- **NEW `js/components/activate.js`** — search test (from search.js) + recall-param groups.
- **NEW `js/components/consolidate.js`** — trigger + history + config (from dashboard.js + group).
- **NEW `js/components/forget.js`** — trigger + records + global config + per-partition tuning
  (delegates to `renderForgettingTuning` extracted from forgetting.js).
- **`js/components/{memories,partitions,graph}.js`** — drop `.page-header`, expose a compact
  toolbar so they mount cleanly inside Manage tabs.
- **`js/components/forgetting.js`** — export `renderForgettingTuning(container)` (tuning only,
  no page header / trigger).
- **`js/components/settings.js` → `system.js`** — keep LLM + Embedding sections + Storage/Server
  groups; Retrieval/Lifecycle groups move to activate/consolidate/forget.
- **DELETE** `dashboard.js`, `search.js` (migrated); `settings.js` superseded by `system.js`.
- **`js/i18n.js`** — new `nav.*`, `manage.*`, `activate.*`, `consolidate.*`, `forget.*`,
  `system.*`, `forget.records.*` keys in **both** en + zh; reuse existing `maint.*`,
  `search.*`, `forgetting.*`, `settings.group.*` where unchanged.
- **`css/style.css`** — `.console-tabs` (in-page tab bar), `.sidebar-nav-divider`, section
  spacing helpers; reuse existing card/setting/maint/fg styles.

## Backend: forgetting run tracker

Mirror the consolidation tracker, but **simpler** — forgetting is short, synchronous, and
atomic, so no per-run log files / heartbeat / interrupted state.

- **NEW `server/forgetting_tracker.py`** — `ForgettingRun` dataclass (`run_id`, `trigger`,
  `status` done|failed, `started_at`, `finished_at`, `scanned`, `deleted`,
  `partitions_swept`, `error`), JSON manifest (`logs/forgetting/manifest.json`), `MAX_RUNS=20`,
  `init_forgetting_tracker(dir)`, `record_run(...)`, `list_runs()`.
- **`scheduler/manager.py`** `_run_forgetting` — record a run on completion/failure with
  scanned/deleted/partitions counts and `trigger="scheduled"`.
- **`server/routers/admin.py`** `POST /forget` — record a run with `trigger="manual"`.
- **`server/routers/forgetting.py`** — `GET /forgetting/runs` → `{runs: [...]}`.
- **`server/app.py`** lifespan — `init_forgetting_tracker(home/logs/forgetting)`.
- **`js/api.js`** — `listForgettingRuns()`.

## Verification

- Isolated server (port 8404, own workdir) — click every nav item + Manage tab; run a
  consolidate + forget and confirm records appear; toggle EN/ZH + light/dark.
- Adversarial multi-agent review of the diff (correctness, EN/ZH i18n parity, dead refs,
  XSS in new interpolation, design consistency).
- `ruff` + `mypy --strict` + forgetting/admin tests green.

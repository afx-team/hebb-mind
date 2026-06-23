# Per-Partition Forgetting + Tuning UI

**Date:** 2026-06-22
**Status:** Implemented
**Scope:** model-free config change + scheduler + server + web console + docs

## Problem

Forgetting (`scheduler/forgetting_job.py`) is a dynamic-TTL sweep driven by two
**global** knobs — `base_ttl_hours` (168) and `decay_factor` (0.693). Every
partition forgets at the same rate, which is wrong: a facts partition should
retain far longer than a scratch one. There was also no way to *see* the effect
of these knobs before applying them, and at the default decay (~1-day half-life)
the landscape is non-obvious — even a high-importance, frequently-accessed memory
is forgotten in ~4 days if never re-accessed.

Goal: per-partition forgetting parameters, plus a console page that previews the
forgetting **curve** and **matrix** live and writes the chosen params back so the
sweep honors them.

## Decisions

1. **Per-partition params = `base_ttl_hours`, `decay_factor`, `enabled`.**
   The two formula knobs plus an on/off switch (off = never forget that
   partition). `min_ttl`/grace stay global module constants (out of scope).
2. **Stored as config, not data.** Overrides live in `Settings.forgetting_overrides`
   (a `dict[str, PartitionForgettingOverride]`) persisted to `hebb.json`, **not**
   in the partitions table. They are operator policy, so they belong in config —
   this also avoids a DB migration (there is no migration framework) and survives
   DB rebuilds. *(Initial draft put them in the partitions table; pivoted to
   config per user direction — "这些因子…应该用配置的形式".)*
3. **Inherit semantics.** A `null` `base_ttl_hours`/`decay_factor` inherits the
   global default; a missing partition entry inherits everything and is enabled.
4. **Matrix = lifespan heatmap.** Cell = *days until forgotten if never
   re-accessed*, over importance (rows) × access-count (cols), red→green.
5. **Preview = client-side + impact endpoint.** Curve/matrix recompute in the
   browser (zero-latency) from a JS mirror of the formula; a read-only backend
   endpoint reports the real would-forget count against the live population.

## Architecture

```
Console "Forgetting" page
  ├─ lib/forgetting-math.js   (mirror of forgetting_job.py — curve + matrix only)
  ├─ GET    /api/v1/admin/forgetting              global defaults + per-partition view
  ├─ PUT    /api/v1/admin/forgetting/{id}         set override  ─┐
  ├─ DELETE /api/v1/admin/forgetting/{id}         clear override ├─ writes hebb.json
  └─ POST   /api/v1/admin/forgetting/{id}/preview impact count (read-only)
                                                                  │
Settings.forgetting_overrides  ◄── update_forgetting_overrides() (flock'd atomic RMW)
        │  (live app.state.settings, shared with the scheduler — no restart)
        ▼
resolve_forgetting_params(partition_id, settings) → (base_ttl, decay, enabled)
        │  single resolution point
        ├─ scheduler/manager._run_forgetting   (scheduled sweep)
        └─ server/routers/admin POST /forget   (manual sweep)
```

`resolve_forgetting_params` is the one place the override-or-global rule lives, so
the scheduled and manual sweeps can't drift. Both skip a partition when
`enabled` is false (in addition to the existing HIPPOCAMPUS skip). The math
functions (`compute_ttl_hours`/`compute_expires_at`) were already parameterized,
so they are unchanged — only the callers now pass resolved params.

## The "forget day" math

Matrix cell / curve crossing = the day a memory accessed *now* (and never again)
is deleted. At elapsed `E` days the sweep recomputes allowed lifetime
`L(E) = TTL(E)/24` days; deletion happens once `L(E) ≤ E`. `L` decays (floored at
`MIN_TTL_HOURS`) while `E` grows ⇒ one crossover `E*`, found by bisection;
never-accessed memories are floored to the 168h grace window. Computed identically
in `forgetting-math.js` (for the instant viz) and implicitly on the server, where
the impact endpoint reuses the production `compute_expires_at` so the count always
matches the real sweep.

## Files

- **Config:** `config/settings.py` (`PartitionForgettingOverride` + `forgetting_overrides`),
  `config/loader.py` (`update_forgetting_overrides` — flock'd atomic RMW).
- **Resolver + sweep:** `scheduler/forgetting_job.py` (`EffectiveForgettingParams`,
  `resolve_forgetting_params`), `scheduler/manager.py`, `server/routers/admin.py`.
- **API:** `server/routers/forgetting.py` (new router), registered in `server/app.py`.
- **Console:** `static/js/components/forgetting.js`, `static/js/lib/forgetting-math.js`,
  `static/js/{api,app,i18n}.js`, `static/index.html`, `static/css/style.css`.
- **Docs:** `repo_pages/concepts/forgetting.md` (+ `zh/` mirror).
- **Tests:** `tests/unit/scheduler/test_forgetting_overrides.py`,
  `tests/unit/config/test_forgetting_config.py`,
  `tests/integration/server/test_forgetting_router.py`.

## Verification

- 18 new unit/integration tests + all existing forgetting/audit invariants green
  (formula, MIN_TTL floor, neutral-importance, grace, monotonicity, recency-decay
  constant untouched). ruff + mypy --strict clean.
- E2E on an isolated server (port 8403, own workdir): set an override in the
  console → persisted to `hebb.json` → live GET + `resolve_forgetting_params`
  return it; live curve/matrix recompute on slider drag (imp5/acc1 1.9d→1.2d at
  decay 1.5); the JS matrix matched the planned numbers (imp10 row:
  7.0/2.5/3.0/3.4/3.7/4.1 d). 0 console errors.

## Invariants preserved

- `MIN_TTL_HOURS` (24) and `NEW_MEMORY_GRACE_HOURS` (168) stay global constants.
- HIPPOCAMPUS is never swept; the page shows it disabled.
- Per-partition `decay_factor` feeds forgetting only — it is **not** the retrieval
  recency constant `_RECENCY_DECAY_FACTOR`, so retrieval is unaffected.

## Out of scope / future

- Per-partition `min_ttl` / grace.
- Postgres parity for forgetting *params* is moot (params are config, not in any
  table); the partitions table is unchanged in both backends.
- A "what-if over time" simulation beyond the single forget-day projection.

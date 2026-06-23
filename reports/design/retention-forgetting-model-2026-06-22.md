# Design: Retention-score forgetting model

**Status**: Implemented (2026-06-22) — owner signed off on O1 uncapped access, O2 clean break, O3 keep `enabled` + manual trigger. 169 tests pass, JS↔Python mirror exact, console verified.
**Date**: 2026-06-22
**Scope**: Replaces the core forgetting formula (`scheduler/forgetting_job.py`), its config
(`config/settings.py`), the per-partition API (`server/routers/forgetting.py`), the JS math mirror
and the console tuner. Affects 2+ modules + config schema + an API contract → design doc required
(per `CLAUDE.md` Decision Guidelines).
**Decision owner**: 玺越 (chose "采用 retention 模型" on 2026-06-22)

---

## 1. Motivation

The shipped model assigns each memory a dynamic TTL and deletes it once the recomputed allowed-life
no longer exceeds elapsed idle time:

```
TTL_h(idle) = base_ttl · (1 + ln(max(acc,1))) · (eff_imp/5) · exp(−decay · idle_days)
eff_imp = imp>0 ? imp : 5         # importance 0 → neutral 5 (a guard hack)
forget when allowed-life L(idle)=TTL_h/24 crosses idle  (bisection)
+ floors: MIN_TTL_HOURS=24h, NEW_MEMORY_GRACE_HOURS=168h for acc==0
```

On the **shipped defaults** (`base_ttl=168h`, `decay=0.693`, i.e. a 1-day half-life) the lifespan
matrix (importance × access, forget-day if never re-accessed) is:

```
imp\acc |   0     1     2     5    10    25    50   100
   10   | 7.0d  2.5d  3.0d  3.4d  3.7d  3.9d  4.1d  4.2d
    5   | 7.0d  1.9d  2.3d  2.7d  3.0d  3.2d  3.4d  3.5d
    2   | 7.0d  1.2d  1.6d  1.9d  2.1d  2.3d  2.5d  2.6d
```

Three defects (the math is correct; the **model + defaults** are wrong for a long-term store):

1. **Days-scale lifetimes.** The single most important, 100×-accessed memory survives **4.2 days**
   idle. That is cache eviction, not long-term memory. The `exp(−decay·idle)` term (halving the
   budget every day) dominates everything.
2. **Single-access inversion.** Column `acc=0` is **7.0d** everywhere (grace floor) — *longer* than
   `acc=1` (1.2–2.5d). Accessing a memory once **shortens** its life 60–75% vs never touching it.
   Backwards from "use it or lose it"; the cause is the creation-anchored grace applying only to
   `acc==0` while the from-last-access decay clock punishes everything else.
3. **Weak knobs.** importance 2→10 (5×) only ~2× the lifespan; access 1→100 (100×) only ~1.8×. The
   levers that *should* drive retention are flattened by decay.

The model is also the source of the UX complaint that prompted this work — the forgetting **curve**
is a self-referential crossover (allowed-life shrinking *and* being compared to elapsed time on the
same axis), which users do not intuitively read.

### Sibling reference: `whisker` forget_tuner

`whiskerrag` uses the textbook **Ebbinghaus** model, which is monotonic, closed-form, and
long-term-calibrated:

```
retention(idle) = exp(−idle_days / eff_half_life)
eff_half_life   = half_life · (1 + k_conf·confidence + k_access·count/10)
forget when retention < threshold  ⇔  idle > eff_half_life · ln(1/threshold)
```

with per-region defaults (episodic 30d, semantic/procedural 90d, preference 180d, threshold 0.3).
Its matrices span months→years and rise monotonically with both axes.

| Dimension | Hebb (current) | Whisker / proposed |
|---|---|---|
| Form | TTL(idle) crosses idle (bisection) | `exp(−idle/eff_hl)`, closed-form forget point |
| idle counted | twice (elapsed **and** shrinks budget) | once |
| curve | crossover (hard to read) | strength 1→0 + threshold line (textbook) |
| imp/access leverage | weak, logarithmic, swamped by decay | strong, linear, independently weighted |
| threshold | implicit | explicit, interpretable |
| monotonic in access | **No** | Yes |
| defaults | days (≤7d) | months→years, per region |

---

## 2. Proposed model

Adopt the retention-score model, using Hebb's native `importance` (0–10) in place of Whisker's
`confidence` (0–1):

```
eff_half_life_days = half_life_days · (1 + k_importance·(importance/10) + k_access·(access_count/10))
retention(idle_days) = exp(−idle_days / eff_half_life_days)
forget when retention < threshold
  ⇔  idle_days > eff_half_life_days · ln(1/threshold)
expires_at = last_accessed_at + (eff_half_life_days · ln(1/threshold)) days
```

Notes:
- `importance == 0` contributes **0** to the multiplier (no boost) instead of the old "neutral 5"
  hack. The base `half_life_days` floor still protects it, so it is no longer a deletion signal —
  the `NEUTRAL_IMPORTANCE` special case is **removed**.
- `access_count/10` is **uncapped** (Whisker's choice the owner selected): a 100×-accessed memory
  gets a large multiplier and becomes effectively permanent — appropriate for "frequently used =
  worth keeping". (See Open Question O1 for the soft-cap alternative.)
- Monotonic in both importance and access → no inversion, no special acc==0 path.

### Per-region defaults

`REGION_FORGET_DEFAULTS`, keyed by `PartitionType` (Hebb already has the cortical regions):

| Region | `half_life_days` | `k_importance` | `k_access` | `threshold` |
|---|---|---|---|---|
| `mem_episodic` | 30 | 1.0 | 1.0 | 0.3 |
| `mem_semantic` | 90 | 3.0 | 1.5 | 0.3 |
| `mem_procedural` | 90 | 3.0 | 1.5 | 0.3 |
| `mem_preference` | 180 | 4.0 | 1.5 | 0.3 |
| user partitions (global default) | 60 | 2.0 | 1.5 | 0.3 |
| `mem_hippocampus` | — never swept (drained by consolidation) |

### Resulting matrix (vs the current days-scale table above)

```
episodic (hl=30,k_imp=1,k_acc=1):       36d (imp0/acc0)  →  14mo (imp10/acc100)
user default (hl=60,k_imp=2,k_acc=1.5):  2mo            →  3.6y
preference (hl=180,k_imp=4,k_acc=1.5):   7mo            →  11.9y
```

Monotonic across both axes, long-term timescales, strong leverage.

---

## 3. Config & migration

### Settings schema (`config/settings.py`)

Replace the two global scalars and the override model:

```python
# global defaults (fallback for user partitions / unknown regions)
half_life_days: float          = Field(default=60.0,  gt=0,  le=3650)
k_importance:   float          = Field(default=2.0,   ge=0,  le=10)
k_access:       float          = Field(default=1.5,   ge=0,  le=10)
forget_threshold: float        = Field(default=0.3,   gt=0,  lt=1)
forget_min_retention_days: float = Field(default=1.0, ge=0)   # hard floor (replaces MIN_TTL+grace)

class PartitionForgettingOverride(BaseModel):
    half_life_days:   float | None = Field(default=None, gt=0, le=3650)
    k_importance:     float | None = Field(default=None, ge=0, le=10)
    k_access:         float | None = Field(default=None, ge=0, le=10)
    threshold:        float | None = Field(default=None, gt=0, lt=1)
    enabled:          bool         = Field(default=True)
```

Resolution order per partition: **override field → region default (`REGION_FORGET_DEFAULTS`) →
global Settings default**. `resolve_forgetting_params` returns the four resolved values + `enabled`.

### Backward compatibility

Hebb is pre-1.0 (v0.1.x), so a **clean break** is acceptable:
- Old keys (`base_ttl_hours`, `decay_factor`, and override fields of the same name) are **dropped**.
- On config load, if legacy keys are present in `hebb.json`, log a one-time WARNING ("forgetting
  config migrated to the retention model; legacy base_ttl_hours/decay_factor ignored — re-tune per
  partition if needed") and do not attempt a lossy numeric remap (the two models have no faithful
  mapping).
- Per-partition overrides reset to region/global defaults. Document in CHANGELOG.

### Grace / min-TTL

The model removes the need for the creation-grace + 24h-TTL floors: even the weakest cell
(`imp0/acc0`, episodic) is `30·ln(1/0.3) ≈ 36d`. A single `forget_min_retention_days` floor (default
1d) guards pathological low-half-life / high-threshold settings. `NEW_MEMORY_GRACE_HOURS` and the
acc==0 special path are **deleted**.

---

## 4. Blast radius (file-by-file)

**Backend**
- `config/settings.py` — new fields + override model + bounds consts; `REGION_FORGET_DEFAULTS`.
- `config/loader.py` — `update_forgetting_overrides` validates new field names; legacy-key warning.
- `scheduler/forgetting_job.py` — replace `compute_ttl_hours`/`compute_expires_at` with
  `eff_half_life` / retention `compute_expires_at`; `resolve_forgetting_params` returns 4 params;
  delete `NEUTRAL_IMPORTANCE`, `NEW_MEMORY_GRACE_HOURS`, the acc==0 branch.
- `scheduler/manager.py` — `_run_forgetting` passes the 4 resolved params.
- `server/routers/forgetting.py` — `ForgettingParamsInput`, `EffectiveForgetting`, config + preview
  response models gain the 4 fields; preview recomputes with the new formula.
- `server/routers/admin.py` — `_run_forgetting`-equivalent manual sweep passes 4 params.
- `retrieval/searcher.py` — **no code change**; `_RECENCY_DECAY_FACTOR` is an independent module
  constant. Update its comment (it references the now-removed forgetting decay tuning).

**Frontend**
- `static/js/lib/forgetting-math.js` — rewrite as a retention mirror: `effHalfLife`, `retention`,
  `forgetDays = effHalfLife·ln(1/threshold)`; `buildMatrix` (importance×access, forget-day) and
  `buildCurve` (retention decay points + threshold + forget point). Drop the bisection/crossover.
- `static/js/components/forgetting.js` — controls become `half_life_days` / `k_importance` /
  `k_access` / `threshold` sliders (+ inherit + enabled); **curve** → retention decay (y=1→0) with a
  dashed threshold line and a vertical forget line (Whisker-style); **matrix** keeps importance×access
  with the new forget-day; **fix the white-text contrast** (see §5). Keep the already-shipped wins:
  hide non-swept partitions, 0–100 access axis, color legend, the explainer (reworded).
- `static/js/components/forget.js` — global-defaults section keys → the 4 new keys.
- `static/js/i18n.js` — retire `base_ttl`/`decay`/`halflife`/`no_decay`/`curve_desc` wording; add
  `half_life`/`k_importance`/`k_access`/`threshold`/retention-curve strings; EN + ZH, keep parity.
- `static/css/style.css` — threshold/forget-line styling; matrix contrast fix.

**Tests**
- `tests/unit/scheduler/` (forgetting_job formula), `tests/unit/config/test_forgetting_config.py`,
  `tests/unit/scheduler/test_forgetting_overrides.py`, `tests/integration/server/test_forgetting_router.py`,
  `tests/unit/test_audit_distribution.py` — update to the new formula/fields; add a monotonicity test
  (forget-day non-decreasing in importance and in access) and a contrast-sweep check for the matrix ramp.

**Docs**
- `repo_pages/concepts/forgetting.md` + `repo_pages/zh/concepts/forgetting.md` (already dirty) —
  rewrite the formula section to the retention model; CHANGELOG entry for the config break.

---

## 5. Matrix contrast fix (folded-in review finding)

The adversarial review confirmed (HIGH) that the matrix's bold 11.5px **white** cell text fails WCAG
across the yellow→green half of the data-relative ramp (worst 2.48:1 at the degenerate `lo==hi`
case), and the cell text is the *only* place the absolute day count is shown. Fix during the rewrite:
choose cell text color by background luminance — dark text (`var(--bg-primary)`) on the bright
yellow-green band, white on dark cells — or lower ramp lightness to ≤34% and verify all hue steps
clear 4.5:1. Add a contrast-sweep unit check so future ramp tweaks can't regress.

---

## 6. Validation & calibration

No train/test split (Hebb doesn't train a model; per project convention). Validation is analytic +
behavioral:
1. **Unit**: formula matches the closed form; monotonic in importance and access; `enabled=False`
   exempts; floor respected; importance 0 ≠ instant delete.
2. **Mirror parity**: JS `forgetting-math.js` reproduces the Python forget-day within rounding across
   a sweep of (half_life, k_imp, k_access, threshold, importance, access).
3. **Sanity matrices**: regenerate the §2 tables; confirm months→years, no inversion.
4. **Console**: curve + matrix + real-memory impact preview render with 0 console errors; EN/ZH
   parity; contrast passes.
5. **Migration**: a hebb.json with legacy keys loads, warns once, falls back to region/global
   defaults; a sweep runs without deleting anything it shouldn't.

---

## 7. Open questions (need a call before/at implementation)

- **O1 — access cap.** Uncapped `access_count/10` makes 100×-accessed memories effectively permanent
  (preference: 11.9y). Keep uncapped (selected), or add a soft cap (e.g. `min(acc,50)/10`) or the
  diminishing-returns `ln(1+acc)` variant? *Proposed: ship uncapped, revisit if "never forgets"
  complaints appear.*
- **O2 — clean break vs migration.** Confirmed clean break with a one-time warning (no lossy remap).
  Acceptable for v0.1.x? *Proposed: yes.*
- **O3 — keep `enabled` per partition + the manual "clean up now" trigger** unchanged. *Proposed: yes.*

---

## 8. Rollout

1. Land backend (settings + formula + resolve + router + manager/admin) with tests green.
2. Land JS mirror + tuner (curve/matrix/controls) + i18n + css + contrast fix; verify in an isolated
   preview server.
3. Update `repo_pages` concept docs (EN+ZH) + CHANGELOG.
4. One squashed commit on a feature branch; no auto-publish (manual release flow).

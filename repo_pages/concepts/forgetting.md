---
description: "How Hebb Mind's dynamic forgetting decays AI agent memory with an Ebbinghaus retention curve — a half-life stretched by importance and access, forgotten below a threshold."
---

# Dynamic Forgetting

Hebb Mind implements a dynamic forgetting mechanism modeled on the **Ebbinghaus forgetting curve**. Each memory has a **retention** (strength) that decays as it sits idle; once retention falls below a threshold the memory is removed. Importance and repeated access stretch the half-life, so frequently used, high-importance memories persist while neglected, low-value ones fade.

## The Formula

```
eff_half_life = half_life_days * (1 + k_importance * (importance / 10) + k_access * (access_count / 10))
retention(idle_days) = exp(-idle_days / eff_half_life)
forget when retention < threshold   ⇔   idle_days > eff_half_life * ln(1 / threshold)
```

Where:

- **half_life_days** — base characteristic lifetime in days; a neutral memory decays to ~37% retention after this many idle days
- **k_importance** — how strongly importance stretches the half-life (importance is normalized to `importance/10`)
- **k_access** — how strongly repeated access stretches the half-life (`access_count/10`, uncapped)
- **importance** — LLM-rated score from 0 to 10 (0 simply adds no boost — it is *not* a "delete me" signal)
- **access_count** — number of times the memory has been retrieved
- **threshold** — the retention level below which a memory is forgotten (e.g. `0.3`)

A global floor (`forget_min_retention_days`, default 1 day) guarantees no setting can collapse a memory to instant deletion.

## How It Works

The forgetting job runs periodically and evaluates every memory:

1. Computes the effective half-life from the memory's importance and access count
2. Computes the day at which its retention would fall below the threshold (`eff_half_life * ln(1/threshold)`)
3. Removes memories whose retention has already decayed past that point

### Factors That Extend a Memory's Life

- **High access count** — each retrieval raises `access_count`, stretching the half-life (uncapped)
- **High importance** — importance multiplies into the half-life via `k_importance`
- **Recent access** — retention is highest right after access and decays from there

### Factors That Shorten a Memory's Life

- **Never accessed / low importance** — only the base half-life applies (no boost)
- **Long time since last access** — retention decays exponentially toward the threshold

## Per-Region Defaults

The built-in cortical partitions ship with retention defaults calibrated to their role; everything else (user partitions) uses the global defaults:

| Partition | `half_life_days` | `k_importance` | `k_access` | `threshold` |
|-----------|------------------|----------------|------------|-------------|
| `mem_episodic` | 30 | 1.0 | 1.0 | 0.3 |
| `mem_semantic` | 90 | 3.0 | 1.5 | 0.3 |
| `mem_procedural` | 90 | 3.0 | 1.5 | 0.3 |
| `mem_preference` | 180 | 4.0 | 1.5 | 0.3 |
| user partitions (global default) | 60 | 2.0 | 1.5 | 0.3 |
| `mem_hippocampus` | *never swept — drained by consolidation* | | | |

## Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `half_life_days` | `60` | Global base half-life in days |
| `k_importance` | `2.0` | Global importance weight |
| `k_access` | `1.5` | Global access weight |
| `forget_threshold` | `0.3` | Retention level below which a memory is forgotten |
| `forget_min_retention_days` | `1` | Hard floor (days) on any memory's retained lifetime |
| `forget_interval_seconds` | `1800` | How often the forgetting job runs (30 minutes) |

```bash
# Remember longer (120-day base half-life)
hebb config set half_life_days 120

# Forget sooner (raise the threshold)
hebb config set forget_threshold 0.5

# Run forgetting less frequently (every hour)
hebb config set forget_interval_seconds 3600
```

## Per-Partition Forgetting

The values above are **global fallbacks**; built-in regions add their own defaults (table above), and each partition can override any field. These overrides are **operator policy stored in config** (`hebb.json`), not in the database — so they survive a database rebuild.

Overrides live in `forgetting_overrides`, keyed by partition id. A `null` field inherits the region/global default; `enabled: false` exempts the partition from forgetting entirely:

```json
{
  "half_life_days": 60,
  "k_importance": 2.0,
  "k_access": 1.5,
  "forget_threshold": 0.3,
  "forgetting_overrides": {
    "mem_facts":   { "half_life_days": 365, "k_access": 2.0, "threshold": null, "enabled": true },
    "mem_scratch": { "half_life_days": 7,   "enabled": true },
    "mem_pinned":  { "enabled": false }
  }
}
```

Changes take effect on the **next forgetting sweep** — the scheduler reads the live config each tick, so no restart is needed. The `mem_hippocampus` working-memory inbox is never swept (it is drained by consolidation), so it has no retention settings.

### Tuning in the console

The web console's **Forgetting** page lets you tune a partition visually:

- Drag `half-life` / `importance weight` / `access weight` / `threshold` (or toggle forgetting off) per partition.
- A live **retention curve** shows each profile's strength decaying over idle time, marking where it crosses the threshold and is forgotten.
- A live **forgetting matrix** is a heatmap of *days-until-forgotten* across importance × access count, recolored instantly as you tune.
- An **impact** panel reports how many memories in that partition would actually be forgotten under the candidate parameters — computed against the real population with the same math as the sweep.

Saving writes the override back to `hebb.json`.

### API

```bash
# Read global defaults + every partition's override, effective, and inherited values
curl http://localhost:8321/api/v1/admin/forgetting

# Set an override (unset fields inherit the region/global default)
curl -X PUT http://localhost:8321/api/v1/admin/forgetting/mem_facts \
  -H 'Content-Type: application/json' \
  -d '{"half_life_days": 365, "k_access": 2.0, "enabled": true}'

# Clear an override (back to inheriting the region/global default)
curl -X DELETE http://localhost:8321/api/v1/admin/forgetting/mem_facts

# Preview impact without deleting anything
curl -X POST http://localhost:8321/api/v1/admin/forgetting/mem_facts/preview \
  -H 'Content-Type: application/json' -d '{"half_life_days": 14, "enabled": true}'
```

## Manual Trigger

Trigger the forgetting job immediately:

```bash
curl -X POST http://localhost:8321/api/v1/admin/forget
```

## Example Scenarios

**Scenario 1: Frequently accessed, important memory** (semantic region)

Importance 8, accessed 10 times, idle 2 days:

```
eff_half_life = 90 * (1 + 3*(8/10) + 1.5*(10/10)) = 90 * 4.9 = 441 days
retention(2)  = exp(-2 / 441) = 0.995    (≫ 0.3 threshold)
forget at     = 441 * ln(1/0.3) ≈ 531 days
```

Comfortably retained.

**Scenario 2: Neglected, low-importance memory** (episodic region)

Importance 3, accessed once, idle 120 days:

```
eff_half_life = 30 * (1 + 1*(3/10) + 1*(1/10)) = 30 * 1.4 = 42 days
retention(120) = exp(-120 / 42) = 0.057   (< 0.3 threshold)
forget at      = 42 * ln(1/0.3) ≈ 51 days
```

Idle well past its ~51-day forget point — removed on the next sweep.

## Design Rationale

Traditional memory systems either keep everything forever or require manual cleanup. Hebb Mind's dynamic forgetting provides:

- **Automatic cleanup** — no manual memory management needed
- **Adaptive retention** — important, frequently-used memories survive naturally
- **Bounded storage** — database size stays manageable over time
- **Biological plausibility** — a true Ebbinghaus retention curve, monotonic in both importance and access

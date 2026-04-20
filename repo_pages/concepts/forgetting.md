# Dynamic Forgetting

Hippocampus implements a dynamic forgetting mechanism inspired by the **Ebbinghaus forgetting curve**. Memories that are rarely accessed and low in importance gradually decay and are removed, while frequently accessed, high-importance memories persist.

## The Formula

Each memory's time-to-live is computed dynamically:

```
TTL = base_ttl * (1 + log(access_count)) * (importance / 5) * exp(-decay_factor * days_since_access)
```

Where:

- **base_ttl** -- base time-to-live in hours (default: 168 hours / 7 days)
- **access_count** -- number of times the memory has been accessed (retrieved in search results)
- **importance** -- LLM-rated score from 0 to 10
- **decay_factor** -- exponential decay rate (default: 0.693, corresponding to a half-life of 1 day)
- **days_since_access** -- days since the memory was last accessed

## How It Works

The forgetting job runs periodically and evaluates every memory:

1. Computes the dynamic TTL using the formula above
2. Compares the TTL against the time elapsed since the memory was last accessed
3. Removes memories whose TTL has expired

### Factors That Extend a Memory's Life

- **High access count** -- each retrieval increases the `log(access_count)` term, reinforcing the memory
- **High importance score** -- memories rated 8/10 live 60% longer than those rated 5/10
- **Recent access** -- the exponential decay term `exp(-decay * days)` is largest right after access

### Factors That Shorten a Memory's Life

- **Never accessed** -- `log(1) = 0`, so the access bonus is zero
- **Low importance** -- a score of 2/10 gives only 40% of the base TTL
- **Long time since last access** -- the exponential decay rapidly reduces effective TTL

## Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `base_ttl_hours` | `168` | Base TTL in hours (7 days) |
| `decay_factor` | `0.693` | Exponential decay factor |
| `forget_interval_seconds` | `1800` | How often the forgetting job runs (30 minutes) |

```bash
# Memories live longer (14 days base)
hippocampus config set base_ttl_hours 336

# Slower decay (memories fade more gradually)
hippocampus config set decay_factor 0.3

# Run forgetting less frequently (every hour)
hippocampus config set forget_interval_seconds 3600
```

## Manual Trigger

Trigger the forgetting job immediately:

```bash
curl -X POST http://localhost:8321/api/v1/admin/forget
```

## Example Scenarios

**Scenario 1: Frequently accessed, important memory**

A memory with importance 8, accessed 10 times, last accessed 2 days ago:

```
TTL = 168 * (1 + log(10)) * (8/5) * exp(-0.693 * 2)
    = 168 * 3.30 * 1.6 * 0.25
    = 221.8 hours (~9.2 days remaining)
```

This memory is still well within its TTL.

**Scenario 2: Neglected, low-importance memory**

A memory with importance 3, accessed once, last accessed 5 days ago:

```
TTL = 168 * (1 + log(1)) * (3/5) * exp(-0.693 * 5)
    = 168 * 1.0 * 0.6 * 0.031
    = 3.1 hours
```

This memory has effectively expired and will be removed.

## Design Rationale

Traditional memory systems either keep everything forever or require manual cleanup. Hippocampus's dynamic forgetting provides:

- **Automatic cleanup** -- no manual memory management needed
- **Adaptive retention** -- important, frequently-used memories survive naturally
- **Bounded storage** -- database size stays manageable over time
- **Biological plausibility** -- mirrors how human memory works

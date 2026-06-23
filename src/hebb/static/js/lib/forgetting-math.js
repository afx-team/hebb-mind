/**
 * forgetting-math.js — client-side mirror of the server retention-score model.
 *
 * THIS IS A FAITHFUL MIRROR of `src/hebb/scheduler/forgetting_job.py`
 * (`eff_half_life_days` / `retention` / `forget_idle_days` / `compute_expires_at`).
 * It exists only so the tuning UI can redraw the retention curve + lifespan matrix
 * instantly as the sliders move, with no server round-trip. The authoritative math
 * — and the real "how many memories would be forgotten" count — always come from
 * the backend (forgetting_job.py and the /forgetting/{id}/preview endpoint). If the
 * Python formula changes, change this in lockstep.
 *
 *   eff_hl  = half_life · (1 + k_importance·(imp/10) + k_access·(acc/10))
 *   retention(idle) = exp(−idle_days / eff_hl)
 *   forget when retention < threshold  ⇔  idle > eff_hl · ln(1/threshold)
 *   forget_day = max(eff_hl · ln(1/threshold), min_retention_days)   // global floor
 *
 * `params` everywhere is { halfLife, kImp, kAcc, threshold } (days + coefficients).
 */

// Global floor (days) on a retained lifetime; mirrors Settings.forget_min_retention_days.
export const DEFAULT_MIN_RETENTION_DAYS = 1.0;

// A forget day at/above this is reported as "effectively never" (~10 years).
export const NEVER_DAYS = 3650;

// Axes for the lifespan matrix. Access count spans 0–100 so the columns show how
// re-access stretches a memory's life across the full practical range.
export const IMPORTANCE_ROWS = [10, 8, 5, 2, 0];
export const ACCESS_COLS = [0, 1, 2, 5, 10, 25, 50, 100];

/** Effective half-life (days). Mirrors `eff_half_life_days`. */
export function effHalfLifeDays(params, importance, accessCount) {
  return params.halfLife * (1 + params.kImp * (importance / 10) + params.kAcc * (accessCount / 10));
}

/** Retention in [0,1] after `idleDays` of inactivity: exp(−idle/eff_hl). */
export function retention(effHl, idleDays) {
  return effHl > 0 ? Math.exp(-Math.max(idleDays, 0) / effHl) : 0;
}

/**
 * Days until forgotten if never re-accessed: where retention crosses the
 * threshold, floored at `minRetentionDays`. Mirrors `forget_idle_days`.
 */
export function forgetDays(params, importance, accessCount, minRetentionDays = DEFAULT_MIN_RETENTION_DAYS) {
  const eff = effHalfLifeDays(params, importance, accessCount);
  return Math.max(eff * Math.log(1 / params.threshold), minRetentionDays);
}

/** Build the lifespan matrix: rows = importance, cols = access count, cell = forget day. */
export function buildMatrix(params, opts = {}) {
  const enabled = opts.enabled ?? true;
  const minR = opts.minRetentionDays ?? DEFAULT_MIN_RETENTION_DAYS;
  return IMPORTANCE_ROWS.map((importance) => ({
    importance,
    cells: ACCESS_COLS.map((accessCount) => ({
      accessCount,
      days: enabled ? Math.min(forgetDays(params, importance, accessCount, minR), NEVER_DAYS) : NEVER_DAYS,
    })),
  }));
}

/**
 * Build the retention curve: for each representative profile, retention(idle)
 * decaying from 1 over idle time, plus the forget day where it crosses threshold.
 */
export function buildCurve(params, opts = {}) {
  const enabled = opts.enabled ?? true;
  const minR = opts.minRetentionDays ?? DEFAULT_MIN_RETENTION_DAYS;
  const profiles = opts.profiles ?? [
    { label: 'importance 2 · access 1', importance: 2, accessCount: 1 },
    { label: 'importance 5 · access 1', importance: 5, accessCount: 1 },
    { label: 'importance 8 · access 5', importance: 8, accessCount: 5 },
  ];

  const series = profiles.map((p) => {
    const eff = effHalfLifeDays(params, p.importance, p.accessCount);
    const forgetDay = enabled ? Math.max(eff * Math.log(1 / params.threshold), minR) : NEVER_DAYS;
    return { ...p, eff, forgetDay };
  });

  // Horizon: show a bit past the latest finite forget day so every threshold
  // crossing is visible.
  const finite = series.map((s) => s.forgetDay).filter((d) => d < NEVER_DAYS);
  const horizonDays = Math.max(4, (finite.length ? Math.max(...finite) : 30) * 1.4);

  const STEPS = 96;
  for (const s of series) {
    s.points = [];
    for (let i = 0; i <= STEPS; i++) {
      const E = (horizonDays * i) / STEPS;
      s.points.push({ x: E, y: retention(s.eff, E) });
    }
  }

  return { horizonDays, threshold: params.threshold, series, enabled };
}

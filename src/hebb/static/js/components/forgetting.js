/**
 * Forgetting — per-partition forgetting policy tuning (retention-score model).
 *
 * Pick a partition, drag half-life / importance & access weights / threshold (or
 * toggle forgetting off), and watch the retention curve + lifespan matrix recompute
 * instantly (client-side, via lib/forgetting-math.js, a mirror of the server
 * formula), plus a real impact count fetched from /forgetting/{id}/preview. Saving
 * writes the override back to hebb.json so the next sweep honors it.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error } from './toast.js';
import {
  buildCurve,
  buildMatrix,
  forgetDays,
  ACCESS_COLS,
  NEVER_DAYS,
} from '../lib/forgetting-math.js';

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Human day count: ∞ / years / days / hours. */
function fmtDays(d) {
  if (d >= NEVER_DAYS) return '∞';
  if (d >= 365) return (d / 365).toFixed(1) + 'y';
  if (d >= 1) return d.toFixed(d < 10 ? 1 : 0) + 'd';
  return Math.round(d * 24) + 'h';
}

/** Half-life display: whole days, or years past a year. */
function fmtHalfLife(d) {
  if (d >= 365) return (d / 365).toFixed(1) + 'y';
  return Math.round(d) + 'd';
}

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// The four tunable retention params. `field` is the server field name; `key` is
// the local state key. Each renders a slider + number + inherit checkbox.
const PARAMS = [
  { key: 'halfLife', field: 'half_life_days', labelKey: 'forgetting.half_life', sliderMin: 1, sliderMax: 365, numMin: 1, numMax: 3650, step: 1, fmt: fmtHalfLife, hintKey: 'forgetting.half_life_hint' },
  { key: 'kImp', field: 'k_importance', labelKey: 'forgetting.k_importance', sliderMin: 0, sliderMax: 10, numMin: 0, numMax: 10, step: 0.1, fmt: (v) => v.toFixed(1), hintKey: 'forgetting.k_importance_hint' },
  { key: 'kAcc', field: 'k_access', labelKey: 'forgetting.k_access', sliderMin: 0, sliderMax: 10, numMin: 0, numMax: 10, step: 0.1, fmt: (v) => v.toFixed(1), hintKey: 'forgetting.k_access_hint' },
  { key: 'threshold', field: 'threshold', labelKey: 'forgetting.threshold', sliderMin: 0.05, sliderMax: 0.9, numMin: 0.01, numMax: 0.99, step: 0.01, fmt: (v) => Math.round(v * 100) + '%', hintKey: 'forgetting.threshold_hint' },
];

function debounce(fn, ms) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

/* ---------------- Matrix color (data-relative, contrast-safe) ---------------- */

function hslToRgb(h, s, l) {
  s /= 100;
  l /= 100;
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1));
  return [Math.round(255 * f(0)), Math.round(255 * f(8)), Math.round(255 * f(4))];
}
function relLuminance(r, g, b) {
  const lin = (c) => {
    c /= 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/**
 * Cell color for a forget-day count, normalized against THIS matrix's finite
 * range [lo, hi] (log-scaled) so the cells use the full red→green spectrum; ∞ gets
 * a distinct teal. Text color is whichever of white / near-black has the higher contrast against
 * the cell, so the day count (the only place the value is shown) stays legible across the ramp.
 */
function cellColor(days, lo, hi) {
  let h;
  let s;
  const l = days >= NEVER_DAYS ? 30 : 42;
  if (days >= NEVER_DAYS) {
    h = 174;
    s = 50;
  } else {
    const ll = Math.log(1 + lo);
    const lh = Math.log(1 + hi);
    const f = lh > ll ? (Math.log(1 + days) - ll) / (lh - ll) : 0.5;
    const g = Math.min(1, Math.max(0, f));
    h = Math.round(g * 135);
    s = Math.round(72 - g * 20);
  }
  const [r, gn, b] = hslToRgb(h, s, l);
  const lum = relLuminance(r, gn, b);
  const cWhite = 1.05 / (lum + 0.05);
  const cBlack = (lum + 0.05) / 0.05;
  const fg = cWhite >= cBlack ? '#ffffff' : '#0d1117';
  return { bg: `hsl(${h}, ${s}%, ${l}%)`, fg };
}

// Qualitative gradient for the matrix legend bar (sooner → later).
const MATRIX_GRADIENT =
  'linear-gradient(90deg, hsl(0,70%,42%), hsl(34,64%,42%), hsl(68,61%,42%), hsl(101,57%,42%), hsl(135,52%,42%))';

/* ---------------- SVG retention curve ---------------- */

const CURVE_COLORS = ['var(--accent)', 'var(--accent-purple)', 'var(--accent-orange)'];

function drawCurve(data) {
  const W = 480;
  const H = 360;
  const m = { l: 50, r: 18, t: 18, b: 44 };
  const pw = W - m.l - m.r;
  const ph = H - m.t - m.b;
  const { horizonDays, threshold } = data;
  const xs = (E) => m.l + (E / horizonDays) * pw;
  const ys = (v) => m.t + ph - Math.min(Math.max(v, 0), 1) * ph; // retention 0..1

  if (!data.enabled) {
    return `<svg viewBox="0 0 ${W} ${H}" class="fg-curve" role="img">
      <text x="${W / 2}" y="${H / 2}" text-anchor="middle" fill="var(--text-muted)" font-size="13">
        ${esc(t('forgetting.never_note'))}</text></svg>`;
  }

  const yTh = ys(threshold);
  let svg = `<svg viewBox="0 0 ${W} ${H}" class="fg-curve" role="img" aria-label="retention curve">`;

  // Region shading: above the threshold line the memory is retained; below it,
  // forgotten. A retention curve dropping below the line is forgotten at the cross.
  svg += `<rect x="${m.l}" y="${m.t}" width="${pw}" height="${yTh - m.t}" fill="var(--accent-green)" opacity="0.06"/>`;
  svg += `<rect x="${m.l}" y="${yTh}" width="${pw}" height="${ys(0) - yTh}" fill="var(--accent-red)" opacity="0.07"/>`;

  // y gridlines + labels (retention %)
  for (let i = 0; i <= 5; i++) {
    const v = i / 5;
    const y = ys(v);
    svg += `<line x1="${m.l}" y1="${y}" x2="${W - m.r}" y2="${y}" stroke="var(--border)" stroke-width="1" opacity="0.35"/>`;
    svg += `<text x="${m.l - 6}" y="${y + 3}" text-anchor="end" fill="var(--text-muted)" font-size="10">${Math.round(v * 100)}%</text>`;
  }
  // x labels (days)
  for (let i = 0; i <= 4; i++) {
    const E = (horizonDays * i) / 4;
    svg += `<text x="${xs(E)}" y="${H - m.b + 16}" text-anchor="middle" fill="var(--text-muted)" font-size="10">${fmtDays(E)}</text>`;
  }
  // axis titles
  svg += `<text x="${m.l + pw / 2}" y="${H - 4}" text-anchor="middle" fill="var(--text-secondary)" font-size="10.5">${esc(t('forgetting.curve_x'))}</text>`;
  svg += `<text transform="translate(13 ${m.t + ph / 2}) rotate(-90)" text-anchor="middle" fill="var(--text-secondary)" font-size="10.5">${esc(t('forgetting.curve_y'))}</text>`;

  // threshold line + label
  svg += `<line x1="${m.l}" y1="${yTh}" x2="${W - m.r}" y2="${yTh}" stroke="var(--accent-orange)" stroke-width="1.25" stroke-dasharray="5 3" opacity="0.9"/>`;
  svg += `<text x="${W - m.r}" y="${yTh - 5}" text-anchor="end" fill="var(--accent-orange)" font-size="10">${esc(t('forgetting.threshold_line', { pct: Math.round(threshold * 100) }))}</text>`;

  // zone labels
  svg += `<text x="${xs(horizonDays * 0.7)}" y="${ys(0.9)}" text-anchor="middle" fill="var(--accent-green)" font-size="10.5" opacity="0.85">${esc(t('forgetting.zone_retained'))}</text>`;
  svg += `<text x="${xs(horizonDays * 0.7)}" y="${ys(threshold * 0.45)}" text-anchor="middle" fill="var(--accent-red)" font-size="10.5" opacity="0.85">${esc(t('forgetting.zone_forgotten'))}</text>`;

  // series + forget-point markers (where retention crosses the threshold)
  data.series.forEach((s, i) => {
    const color = CURVE_COLORS[i % CURVE_COLORS.length];
    const pts = s.points.map((p) => `${xs(p.x).toFixed(1)},${ys(p.y).toFixed(1)}`).join(' ');
    svg += `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2"/>`;
    if (s.forgetDay < NEVER_DAYS && s.forgetDay <= horizonDays) {
      const fx = xs(s.forgetDay);
      svg += `<line x1="${fx}" y1="${yTh}" x2="${fx}" y2="${ys(0)}" stroke="${color}" stroke-width="1" stroke-dasharray="2 2" opacity="0.6"/>`;
      svg += `<circle cx="${fx}" cy="${yTh}" r="4" fill="${color}" stroke="var(--bg-primary)" stroke-width="1.5"/>`;
    }
  });

  svg += `</svg>`;
  return svg;
}

function curveLegend(data) {
  if (!data.enabled) return '';
  return `<div class="fg-legend">${data.series
    .map((s, i) => {
      const color = CURVE_COLORS[i % CURVE_COLORS.length];
      const forget = s.forgetDay >= NEVER_DAYS ? t('forgetting.never') : t('forgetting.forgets_in', { d: fmtDays(s.forgetDay) });
      return `<span class="fg-legend-item"><span class="fg-swatch" style="background:${color}"></span>${esc(s.label)} · <strong>${esc(forget)}</strong></span>`;
    })
    .join('')}</div>`;
}

/* ---------------- Lifespan matrix ---------------- */

function drawMatrix(matrix) {
  let lo = Infinity;
  let hi = 0;
  for (const row of matrix)
    for (const c of row.cells)
      if (c.days < NEVER_DAYS) {
        if (c.days < lo) lo = c.days;
        if (c.days > hi) hi = c.days;
      }
  if (!Number.isFinite(lo)) lo = 0;

  let html = `<table class="fg-matrix"><thead><tr><th></th>`;
  html += ACCESS_COLS.map((a) => `<th>${a}</th>`).join('');
  html += `</tr></thead><tbody>`;
  for (const row of matrix) {
    const impLabel = row.importance === 0 ? '0*' : String(row.importance);
    html += `<tr><th>${impLabel}</th>`;
    html += row.cells
      .map((c) => {
        const { bg, fg } = cellColor(c.days, lo, hi);
        const title = t('forgetting.cell_title', {
          imp: row.importance,
          acc: c.accessCount,
          life: c.days >= NEVER_DAYS ? t('forgetting.never') : fmtDays(c.days),
        });
        return `<td style="background:${bg};color:${fg}" title="${esc(title)}">${fmtDays(c.days)}</td>`;
      })
      .join('');
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function matrixLegend() {
  return `<div class="fg-matrix-legend">
    <span>${esc(t('forgetting.legend_sooner'))}</span>
    <span class="fg-legend-bar" style="background:${MATRIX_GRADIENT}"></span>
    <span>${esc(t('forgetting.legend_later'))}</span>
    <span class="fg-legend-never"><span class="fg-legend-never-swatch" style="background:hsl(174,50%,30%)"></span>${esc(t('forgetting.never'))}</span>
  </div>`;
}

/* ---------------- Tuning UI ---------------- */

function paramControlHtml(p) {
  return `
    <div class="fg-control" id="fg-${p.key}-control">
      <div class="flex-between">
        <label class="form-label" style="margin:0">${t(p.labelKey)}: <span id="fg-${p.key}-val"></span></label>
        <label class="fg-inherit"><input type="checkbox" id="fg-${p.key}-inherit"> ${t('forgetting.inherit')}</label>
      </div>
      <div class="fg-slider-row">
        <div class="range-group" style="flex:1"><input type="range" id="fg-${p.key}" min="${p.sliderMin}" max="${p.sliderMax}" step="${p.step}"></div>
        <input class="form-input fg-num" id="fg-${p.key}-num" type="number" min="${p.numMin}" max="${p.numMax}" step="${p.step}">
      </div>
      <div class="text-muted fg-hint">${t(p.hintKey)}</div>
    </div>`;
}

/**
 * Mount the per-partition forgetting tuner into `root`. No page header — the
 * Forget page owns the header and composes this below its trigger / records /
 * global-config sections.
 */
export async function renderForgettingTuning(root) {
  root.innerHTML = `<div id="fg-body"><div class="empty-state">${t('common.loading')}</div></div>`;

  let config;
  try {
    config = await api.getForgettingConfig();
  } catch (e) {
    root.querySelector('#fg-body').innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
    return;
  }

  const body = root.querySelector('#fg-body');
  // Only show partitions the sweep actually touches. The working-memory inbox
  // (HIPPOCAMPUS) is drained by consolidation, never by forgetting.
  const partitions = (config.partitions || []).filter((p) => p.swept);
  if (!partitions.length) {
    body.innerHTML = `<div class="empty-state">${t('forgetting.no_swept_partitions')}</div>`;
    return;
  }

  const state = {
    pid: partitions[0].id,
    enabled: true,
    inherit: { halfLife: true, kImp: true, kAcc: true, threshold: true },
    val: { halfLife: 0, kImp: 0, kAcc: 0, threshold: 0 },
  };

  const minR = config.min_retention_days ?? 1.0;
  const intervalMin = Math.max(1, Math.round((config.forget_interval_seconds || 1800) / 60));

  body.innerHTML = `
    <div class="fg-explain">
      <div class="fg-explain-title">${t('forgetting.how_title')}</div>
      <div class="fg-explain-body">${t('forgetting.how_body')}</div>
    </div>

    <div class="card mb-4">
      <div class="fg-row">
        <div class="form-group" style="margin:0">
          <label class="form-label">${t('forgetting.partition')}</label>
          <select class="form-select" id="fg-partition" style="min-width:240px">
            ${partitions
              .map((p) => `<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.id.replace('mem_', ''))}</option>`)
              .join('')}
          </select>
        </div>
        <div class="fg-globals text-muted" id="fg-summary"></div>
      </div>
    </div>

    <div class="card mb-4" id="fg-controls">
      <div class="fg-control-grid">
        <div class="fg-control">
          <div class="flex-between">
            <label class="form-label" style="margin:0">${t('forgetting.enabled')}</label>
            <span class="toggle" id="fg-enabled" role="switch" tabindex="0"></span>
          </div>
          <div class="text-muted fg-hint">${t('forgetting.enabled_hint')}</div>
        </div>
        ${PARAMS.map(paramControlHtml).join('')}
      </div>

      <div class="fg-actions">
        <button class="btn" id="fg-reset">${t('forgetting.reset')}</button>
        <button class="btn btn-primary" id="fg-save">${t('forgetting.save')}</button>
        <span class="text-muted fg-hint">${t('forgetting.apply_note', { n: intervalMin })}</span>
      </div>
    </div>

    <div class="fg-viz">
      <div class="card">
        <h3 class="fg-card-title">${t('forgetting.curve_title')}</h3>
        <p class="text-muted fg-hint">${t('forgetting.curve_desc')}</p>
        <div id="fg-curve"></div>
        <div id="fg-curve-legend"></div>
      </div>
      <div class="card">
        <h3 class="fg-card-title">${t('forgetting.matrix_title')}</h3>
        <p class="text-muted fg-hint">${t('forgetting.matrix_desc')}</p>
        <div class="fg-matrix-wrap"><div class="fg-axis-y">${t('forgetting.importance')}</div><div id="fg-matrix" style="flex:1"></div></div>
        <div class="fg-axis-x text-muted">${t('forgetting.access_count')}</div>
        ${matrixLegend()}
      </div>
    </div>

    <div class="card mt-4">
      <h3 class="fg-card-title">${t('forgetting.impact_title')}</h3>
      <div id="fg-impact"><div class="text-muted fg-hint">${t('common.loading')}</div></div>
    </div>
  `;

  const $ = (sel) => body.querySelector(sel);
  const els = {
    partition: $('#fg-partition'),
    enabled: $('#fg-enabled'),
    reset: $('#fg-reset'),
    save: $('#fg-save'),
    summary: $('#fg-summary'),
    curve: $('#fg-curve'),
    curveLegend: $('#fg-curve-legend'),
    matrix: $('#fg-matrix'),
    impact: $('#fg-impact'),
  };
  // Per-param element handles
  const pEls = {};
  for (const p of PARAMS) {
    pEls[p.key] = {
      slider: $(`#fg-${p.key}`),
      num: $(`#fg-${p.key}-num`),
      val: $(`#fg-${p.key}-val`),
      inherit: $(`#fg-${p.key}-inherit`),
    };
  }

  function currentEntry() {
    return partitions.find((p) => p.id === state.pid);
  }

  function loadEntry(entry) {
    const ov = entry.override;
    state.enabled = ov ? ov.enabled : true;
    for (const p of PARAMS) {
      const ovVal = ov ? ov[p.field] : null;
      state.inherit[p.key] = ovVal == null;
      state.val[p.key] = ovVal != null ? ovVal : entry.inherited[p.field];
    }
  }

  // Resolved params {halfLife,kImp,kAcc,threshold}: inherit → region/global baseline.
  function effectiveParams() {
    const entry = currentEntry();
    const out = {};
    for (const p of PARAMS) out[p.key] = state.inherit[p.key] ? entry.inherited[p.field] : state.val[p.key];
    return out;
  }

  function syncControls() {
    const entry = currentEntry();
    const locked = !state.enabled;
    els.enabled.classList.toggle('on', state.enabled);
    for (const p of PARAMS) {
      const eff = state.inherit[p.key] ? entry.inherited[p.field] : state.val[p.key];
      const el = pEls[p.key];
      el.inherit.checked = state.inherit[p.key];
      el.slider.value = clamp(eff, p.sliderMin, p.sliderMax);
      el.num.value = p.step >= 1 ? Math.round(eff) : eff;
      el.slider.disabled = state.inherit[p.key] || locked;
      el.num.disabled = state.inherit[p.key] || locked;
      el.val.textContent = p.fmt(eff);
    }
    els.reset.disabled = !entry.override;
    // Orientation: forget point of a neutral memory under the effective params.
    const ep = effectiveParams();
    const neutral = forgetDays(ep, 5, 1, minR);
    els.summary.textContent = state.enabled
      ? t('forgetting.summary', { d: fmtDays(neutral) })
      : t('forgetting.summary_off');
  }

  function redrawViz() {
    const ep = effectiveParams();
    const opts = { enabled: state.enabled, minRetentionDays: minR };
    els.curve.innerHTML = drawCurve(buildCurve(ep, opts));
    els.curveLegend.innerHTML = curveLegend(buildCurve(ep, opts));
    els.matrix.innerHTML = drawMatrix(buildMatrix(ep, opts));
  }

  function renderImpact(resp) {
    if (!resp.swept) {
      els.impact.innerHTML = `<div class="text-muted fg-hint">${t('forgetting.impact_disabled')}</div>`;
      return;
    }
    const pct = resp.total ? Math.round((resp.would_forget / resp.total) * 100) : 0;
    let html = `<div class="fg-impact-headline">${t('forgetting.impact_summary', {
      forget: resp.would_forget,
      total: resp.total,
      pct,
    })}</div>`;
    const flagged = resp.sample.filter((s) => s.would_forget);
    const shown = flagged.length ? flagged : resp.sample;
    if (shown.length) {
      html += `<table class="fg-impact-table"><thead><tr>
        <th>${t('forgetting.col_content')}</th><th>${t('forgetting.importance')}</th>
        <th>acc</th><th>${t('forgetting.col_age')}</th><th></th></tr></thead><tbody>`;
      html += shown
        .slice(0, 12)
        .map(
          (s) => `<tr class="${s.would_forget ? 'fg-row-forget' : ''}">
          <td>${esc(s.content)}</td><td>${s.importance_score.toFixed(1)}</td>
          <td>${s.access_count}</td><td>${fmtDays(s.days_since_access)}</td>
          <td>${s.would_forget ? `<span class="tag tag-red">${t('forgetting.forget')}</span>` : `<span class="tag tag-green">${t('forgetting.keep')}</span>`}</td></tr>`
        )
        .join('');
      html += `</tbody></table>`;
    } else {
      html += `<div class="text-muted fg-hint">${t('forgetting.impact_empty')}</div>`;
    }
    els.impact.innerHTML = html;
  }

  // Server payload: a field is null (inherit) unless explicitly overridden.
  function overridePayload() {
    const out = { enabled: state.enabled };
    for (const p of PARAMS) out[p.field] = state.inherit[p.key] ? null : state.val[p.key];
    return out;
  }

  const refreshImpact = debounce(async () => {
    // When the toggle is off the preview comes back swept=false → "forgetting off".
    els.impact.innerHTML = `<div class="text-muted fg-hint">${t('common.loading')}</div>`;
    try {
      const resp = await api.previewForgetting(state.pid, overridePayload());
      renderImpact(resp);
    } catch (e) {
      els.impact.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
    }
  }, 350);

  function onChange({ impact = true } = {}) {
    syncControls();
    redrawViz();
    if (impact) refreshImpact();
  }

  function selectPartition(pid) {
    state.pid = pid;
    loadEntry(currentEntry());
    onChange();
  }

  /* ---- wiring ---- */
  els.partition.onchange = () => selectPartition(els.partition.value);

  els.enabled.onclick = () => {
    state.enabled = !state.enabled;
    onChange();
  };
  els.enabled.onkeydown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      els.enabled.onclick();
    }
  };

  for (const p of PARAMS) {
    const el = pEls[p.key];
    el.inherit.onchange = () => {
      state.inherit[p.key] = el.inherit.checked;
      if (state.inherit[p.key]) state.val[p.key] = currentEntry().inherited[p.field];
      onChange();
    };
    el.slider.oninput = () => {
      state.inherit[p.key] = false;
      state.val[p.key] = clamp(parseFloat(el.slider.value), p.numMin, p.numMax);
      onChange();
    };
    // Number input is authoritative for the full range; commit on change (blur/enter)
    // so re-syncing its value mid-edit doesn't interrupt typing.
    el.num.onchange = () => {
      const v = parseFloat(el.num.value);
      if (Number.isNaN(v)) return syncControls();
      state.inherit[p.key] = false;
      state.val[p.key] = clamp(v, p.numMin, p.numMax);
      onChange();
    };
  }

  els.save.onclick = async () => {
    els.save.disabled = true;
    try {
      await api.setForgettingOverride(state.pid, overridePayload());
      config = await api.getForgettingConfig();
      partitions.length = 0;
      partitions.push(...config.partitions.filter((p) => p.swept));
      success(t('forgetting.saved_ok'));
      selectPartition(state.pid);
    } catch (e) {
      error(e.message);
    } finally {
      els.save.disabled = false;
    }
  };

  els.reset.onclick = async () => {
    try {
      await api.clearForgettingOverride(state.pid);
      config = await api.getForgettingConfig();
      partitions.length = 0;
      partitions.push(...config.partitions.filter((p) => p.swept));
      success(t('forgetting.reset_ok'));
      selectPartition(state.pid);
    } catch (e) {
      error(e.message);
    }
  };

  // initial
  els.partition.value = state.pid;
  selectPartition(state.pid);
}

/**
 * Forget (记忆遗忘) — trigger + records + global config + per-partition tuning.
 *
 * Consolidates everything about forgetting onto one page: the "Clean up now"
 * trigger (was on the Dashboard), the new forgetting run records (sweep history),
 * the global forgetting defaults (base TTL / decay / sweep interval, was under
 * Settings → Lifecycle), and the per-partition tuner with its live curve /
 * matrix / impact preview (the former standalone Forgetting page).
 */

import * as api from '../api.js';
import { t, getLang } from '../i18n.js';
import { success, error, info } from './toast.js';
import { buildGenericSection, esc } from './config-section.js';
import { renderForgettingTuning } from './forgetting.js';

// Built at RENDER time (not module scope) so t() resolves the current language
// on every (re)render — a module-level const would freeze the initial language.
function buildGroupForgetGlobal() {
  return {
    titleKey: 'forget.global_title',
    icon: '&#9203;',
    keys: ['half_life_days', 'k_importance', 'k_access', 'forget_threshold', 'forget_min_retention_days', 'forget_interval_seconds'],
    hints: {
      half_life_days: t('forget.global.hint_half_life'),
      k_importance: t('forget.global.hint_k_importance'),
      k_access: t('forget.global.hint_k_access'),
      forget_threshold: t('forget.global.hint_threshold'),
      forget_min_retention_days: t('forget.global.hint_min_retention'),
      forget_interval_seconds: t('forget.global.hint_forget_interval'),
    },
  };
}

function fmtTime(iso) {
  try {
    const locale = getLang() === 'zh' ? 'zh-CN' : 'en-US';
    return new Date(iso).toLocaleString(locale, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}
function fmtEpoch(ts) {
  if (!ts) return '';
  return fmtTime(new Date(ts * 1000).toISOString());
}

function confirmDialog({ title, body, okLabel, danger = false }) {
  return new Promise((resolve) => {
    const overlay = document.getElementById('modal-overlay');
    overlay.classList.remove('hidden');
    overlay.innerHTML = `
      <div class="modal">
        <h3 class="modal-title">${title}</h3>
        <p class="text-sm text-muted" style="line-height:1.6;">${body}</p>
        <div class="modal-actions">
          <button class="btn" id="cd-cancel">${t('common.cancel')}</button>
          <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" id="cd-ok">${okLabel}</button>
        </div>
      </div>
    `;
    const close = (val) => {
      overlay.classList.add('hidden');
      overlay.innerHTML = '';
      resolve(val);
    };
    overlay.querySelector('#cd-cancel').onclick = () => close(false);
    overlay.querySelector('#cd-ok').onclick = () => close(true);
    overlay.onclick = (e) => { if (e.target === overlay) close(false); };
  });
}

function renderRecords(runs) {
  const list = document.getElementById('forget-records');
  if (!list) return;
  if (!runs.length) {
    list.innerHTML = `<div class="text-sm text-muted" style="padding:4px 0">${t('forget.records.empty')}</div>`;
    return;
  }
  list.innerHTML = runs.map(r => {
    const triggerLabel = r.trigger === 'scheduled'
      ? t('maint.consolidate.trigger_scheduled')
      : t('maint.consolidate.trigger_manual');
    const status = r.status === 'failed' ? 'failed' : 'done';
    const resultText = r.status === 'failed'
      ? esc(r.error || t('forget.records.failed'))
      : t('forget.records.summary', { deleted: r.deleted, scanned: r.scanned });
    return `
      <div class="history-row">
        <div class="history-summary" style="cursor:default">
          <span class="history-status ${status}"></span>
          <span class="history-trigger">${triggerLabel}</span>
          <span class="history-time">${fmtEpoch(r.started_at)}</span>
          <span class="history-result text-sm">${resultText}</span>
        </div>
      </div>
    `;
  }).join('');
}

async function loadRecords() {
  try {
    const res = await api.listForgettingRuns();
    renderRecords(res.runs || []);
  } catch {
    renderRecords([]);
  }
}

export async function renderForget(root) {
  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('forget.title')}</h1>
      <p class="page-subtitle">${t('forget.subtitle')}</p>
    </div>

    <div class="card mb-4">
      <div class="maint-list">
        <div class="maint-card">
          <div class="maint-icon">🧹</div>
          <div class="maint-body">
            <div class="maint-title">${t('maint.forget.title')}<span class="maint-term">${t('maint.forget.term')}</span></div>
            <div class="maint-desc">${t('maint.forget.desc')}</div>
            <div class="maint-meta" id="forget-meta"></div>
          </div>
          <div class="maint-action">
            <button class="btn" id="btn-forget">${t('maint.forget.btn')}</button>
          </div>
        </div>
      </div>
    </div>

    <h2 class="section-heading">${t('forget.records_title')}</h2>
    <div class="card mb-4">
      <div class="history-list" id="forget-records">
        <div class="text-sm text-muted">${t('common.loading')}</div>
      </div>
    </div>

    <h2 class="section-heading">${t('forget.global_title')}</h2>
    <div id="forget-global-config" class="mb-4"></div>

    <h2 class="section-heading">${t('forget.tuning_title')}</h2>
    <div id="forget-tuning"></div>
  `;

  const btnForget = document.getElementById('btn-forget');

  async function loadMeta() {
    try {
      const stats = await api.getStats();
      const forgetNext = stats.scheduler?.jobs?.forgetting_job?.next_run_time;
      const metaEl = document.getElementById('forget-meta');
      if (metaEl) {
        metaEl.textContent = forgetNext ? t('maint.auto_next', { time: fmtTime(forgetNext) }) : t('maint.auto_bg');
      }
    } catch { /* ignore — meta is non-critical */ }
  }

  btnForget.onclick = async () => {
    const ok = await confirmDialog({
      title: t('maint.forget.confirm_title'),
      body: t('maint.forget.confirm_body'),
      okLabel: t('maint.forget.confirm_ok'),
      danger: true,
    });
    if (!ok) return;
    btnForget.disabled = true;
    btnForget.textContent = t('maint.running');
    try {
      const r = await api.triggerForget();
      if (r.deleted > 0) success(t('maint.forget.done', { n: r.deleted }));
      else info(t('maint.forget.none'));
    } catch (e) {
      error(e.message);
    } finally {
      btnForget.textContent = t('maint.forget.btn');
      btnForget.disabled = false;
      await loadRecords();
    }
  };

  await Promise.all([loadMeta(), loadRecords()]);

  /* Global forgetting config */
  const globalRoot = root.querySelector('#forget-global-config');
  try {
    const config = await api.getConfig();
    globalRoot.appendChild(buildGenericSection(buildGroupForgetGlobal(), config));
  } catch (e) {
    globalRoot.innerHTML = `<div class="empty-state">${e.message}</div>`;
  }

  /* Per-partition tuning (curve + matrix + impact + override) */
  await renderForgettingTuning(root.querySelector('#forget-tuning'));
}

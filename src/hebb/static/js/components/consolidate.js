/**
 * Consolidate (记忆巩固) — manual trigger + run records + consolidation config.
 *
 * Brings together what used to be split between the Dashboard (the "Organize
 * now" trigger + live run history) and Settings → Lifecycle (the consolidation
 * tuning knobs). Consolidation runs automatically on a daily cron; this page is
 * for triggering it on demand, watching a run stream its log, and configuring
 * how it behaves.
 */

import * as api from '../api.js';
import { t, getLang } from '../i18n.js';
import { onCleanup } from '../lifecycle.js';
import { success, error, info } from './toast.js';
import { buildGenericSection } from './config-section.js';

let pollTimer = null;
const logCache = {};

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Built at render time (not module scope) so t() resolves the CURRENT language
// on every (re)render — a module-level object would freeze the initial language.
function buildGroupConsolidation() {
  return {
    titleKey: 'consolidate.config_title',
    icon: '&#128260;',
    keys: ['consolidation_time', 'consolidation_concurrency', 'consolidation_max_tokens', 'consolidation_drain_empty_sources'],
    hints: {
      consolidation_drain_empty_sources: t('consolidate.drain_empty_hint'),
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

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function toggleRunLog(runId) {
  const row = document.querySelector(`.history-row[data-run-id="${runId}"]`);
  if (!row) return;
  const logDiv = row.querySelector('.history-log');
  const isExpanded = row.classList.contains('expanded');
  if (isExpanded) {
    row.classList.remove('expanded');
    logDiv.classList.add('hidden');
    return;
  }
  row.classList.add('expanded');
  logDiv.classList.remove('hidden');
  const isRunning = row.querySelector('.history-status.running');
  if (!isRunning && logCache[runId] !== undefined) {
    logDiv.innerHTML = `<pre class="history-log-pre">${logCache[runId] ? esc(logCache[runId]) : t('maint.consolidate.log_empty')}</pre>`;
    return;
  }
  logDiv.innerHTML = `<pre class="history-log-pre" style="color:var(--text-muted)">${t('common.loading')}</pre>`;
  try {
    const res = await api.getConsolidationLog(runId);
    if (!isRunning) logCache[runId] = res.log;
    logDiv.innerHTML = `<pre class="history-log-pre">${res.log ? esc(res.log) : t('maint.consolidate.log_empty')}</pre>`;
  } catch {
    logDiv.innerHTML = `<pre class="history-log-pre" style="color:var(--accent-red)">${t('consolidate.log_load_failed')}</pre>`;
  }
}

function renderHistory(runs) {
  const list = document.getElementById('history-list');
  if (!list) return;
  if (!runs.length) {
    list.innerHTML = `<div class="text-sm text-muted" style="padding:4px 0">${t('maint.consolidate.no_history')}</div>`;
    return;
  }
  list.innerHTML = runs.map(r => {
    const triggerLabel = r.trigger === 'scheduled'
      ? t('maint.consolidate.trigger_scheduled')
      : r.trigger === 'catchup'
        ? t('maint.consolidate.trigger_catchup')
        : t('maint.consolidate.trigger_manual');
    const resultText = r.status === 'running'
      ? t('maint.running')
      : r.status === 'interrupted'
        ? t('maint.consolidate.interrupted')
        : r.status === 'failed'
          ? esc(r.errors?.[0]?.error || t('consolidate.result_failed'))
          : r.failed
            ? t('consolidate.result_fail', { ok: r.succeeded, fail: r.failed })
            : t('consolidate.result_ok', { n: r.succeeded });
    return `
      <div class="history-row" data-run-id="${r.run_id}">
        <div class="history-summary">
          <span class="history-status ${r.status}"></span>
          <span class="history-trigger">${triggerLabel}</span>
          <span class="history-time">${fmtEpoch(r.started_at)}</span>
          <span class="history-result text-sm">${resultText}</span>
          <span class="history-chevron">&#9656;</span>
        </div>
        <div class="history-log hidden"></div>
      </div>
    `;
  }).join('');
  list.querySelectorAll('.history-summary').forEach(el => {
    el.onclick = () => toggleRunLog(el.parentElement.dataset.runId);
  });
}

function renderInterruptedNote(runs) {
  const note = document.getElementById('consolidate-note');
  if (!note) return;
  const latest = runs[0];
  if (latest && latest.status === 'interrupted') {
    note.textContent = t('maint.consolidate.interrupted_note');
    note.classList.remove('hidden');
  } else {
    note.classList.add('hidden');
  }
}

async function loadHistory() {
  try {
    const res = await api.listConsolidationRuns();
    const runs = res.runs || [];
    renderHistory(runs);
    renderInterruptedNote(runs);
    return runs;
  } catch {
    renderHistory([]);
    return [];
  }
}

export async function renderConsolidate(root) {
  stopPolling();
  // Stop the live run poll when this page is unmounted (navigating away while a
  // consolidation is in progress would otherwise keep the 2s interval running).
  onCleanup(stopPolling);

  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('consolidate.title')}</h1>
      <p class="page-subtitle">${t('consolidate.subtitle')}</p>
    </div>

    <div class="card mb-4">
      <div class="maint-list">
        <div class="maint-card maint-card--expandable">
          <div class="maint-icon">🗂️</div>
          <div class="maint-body">
            <div class="maint-title">${t('maint.consolidate.title')}<span class="maint-term">${t('maint.consolidate.term')}</span></div>
            <div class="maint-desc">${t('maint.consolidate.desc')}</div>
            <div class="maint-meta" id="consolidate-meta"></div>
            <div class="maint-note hidden" id="consolidate-note"></div>
          </div>
          <div class="maint-action">
            <button class="btn btn-primary" id="btn-consolidate">${t('maint.consolidate.btn')}</button>
          </div>
        </div>
      </div>
    </div>

    <h2 class="section-heading">${t('consolidate.records_title')}</h2>
    <div class="card mb-4">
      <div class="history-list" id="history-list">
        <div class="text-sm text-muted">${t('common.loading')}</div>
      </div>
    </div>

    <h2 class="section-heading">${t('consolidate.config_title')}</h2>
    <div id="consolidate-config"></div>
  `;

  const btnConsolidate = document.getElementById('btn-consolidate');

  async function loadMeta() {
    try {
      const stats = await api.getStats();
      const jobs = stats.scheduler?.jobs || {};
      const hippo = stats.partitions.find(p => p.id === 'mem_hippocampus');
      const pending = hippo ? hippo.memory_count : 0;

      const consNext = jobs.consolidation_job?.next_run_time;
      const consAuto = consNext ? t('maint.auto_next', { time: fmtTime(consNext) }) : t('maint.auto_bg');
      const pendText = pending > 0
        ? t('maint.consolidate.pending', { n: pending })
        : t('maint.consolidate.none_pending');
      const metaEl = document.getElementById('consolidate-meta');
      if (metaEl) metaEl.textContent = `${consAuto} · ${pendText}`;
      if (!pollTimer) btnConsolidate.disabled = pending === 0;
    } catch (e) {
      error(e.message);
    }
  }

  function startPolling(runId) {
    btnConsolidate.disabled = true;
    btnConsolidate.textContent = t('maint.running');
    stopPolling();

    requestAnimationFrame(() => {
      const row = document.querySelector(`.history-row[data-run-id="${runId}"]`);
      if (row && !row.classList.contains('expanded')) {
        row.classList.add('expanded');
        const logDiv = row.querySelector('.history-log');
        if (logDiv) logDiv.classList.remove('hidden');
      }
    });

    pollTimer = setInterval(async () => {
      try {
        const run = await api.getConsolidationRun(runId);

        const row = document.querySelector(`.history-row[data-run-id="${runId}"]`);
        if (row && row.classList.contains('expanded')) {
          const logDiv = row.querySelector('.history-log');
          if (logDiv) {
            try {
              const res = await api.getConsolidationLog(runId);
              const pre = logDiv.querySelector('.history-log-pre');
              const wasAtBottom = pre
                ? logDiv.scrollTop + logDiv.clientHeight >= logDiv.scrollHeight - 20
                : true;
              logDiv.innerHTML = `<pre class="history-log-pre">${res.log ? esc(res.log) : t('maint.consolidate.log_empty')}</pre>`;
              if (wasAtBottom) logDiv.scrollTop = logDiv.scrollHeight;
            } catch { /* ignore log fetch errors during polling */ }
          }
        }

        if (run.status === 'done' || run.status === 'failed') {
          stopPolling();
          delete logCache[runId];
          if (run.status === 'failed') {
            error(run.errors?.[0]?.error || t('consolidate.failed'));
          } else if (!run.processed) {
            info(t('maint.consolidate.nothing'));
          } else if (run.failed > 0) {
            error(t('maint.consolidate.done_fail', { ok: run.succeeded, fail: run.failed }));
          } else {
            success(t('maint.consolidate.done', { ok: run.succeeded }));
          }
          btnConsolidate.textContent = t('maint.consolidate.btn');
          await loadMeta();
          await loadHistory();
        }
      } catch {
        stopPolling();
        btnConsolidate.textContent = t('maint.consolidate.btn');
        btnConsolidate.disabled = false;
      }
    }, 2000);
  }

  await Promise.all([loadMeta(), loadHistory()]);

  // Reattach to an in-progress run on load.
  try {
    const res = await api.listConsolidationRuns();
    const running = (res.runs || []).find(r => r.status === 'running');
    if (running) startPolling(running.run_id);
  } catch { /* ignore */ }

  btnConsolidate.onclick = async () => {
    btnConsolidate.disabled = true;
    btnConsolidate.textContent = t('maint.running');
    try {
      const r = await api.startConsolidate();
      startPolling(r.run_id);
      await loadHistory();
    } catch (e) {
      error(e.message);
      btnConsolidate.textContent = t('maint.consolidate.btn');
      btnConsolidate.disabled = false;
    }
  };

  /* Consolidation config */
  const configRoot = root.querySelector('#consolidate-config');
  try {
    const config = await api.getConfig();
    configRoot.appendChild(buildGenericSection(buildGroupConsolidation(), config));
  } catch (e) {
    configRoot.innerHTML = `<div class="empty-state">${e.message}</div>`;
  }
}

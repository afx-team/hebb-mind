/**
 * Dashboard — system stats, partition distribution, memory maintenance.
 */

import * as api from '../api.js';
import { t, getLang } from '../i18n.js';
import { success, error, info } from './toast.js';

let pollTimer = null;
const logCache = {};

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
  // Don't cache running runs — log is still growing
  const isRunning = row.querySelector('.history-status.running');
  if (!isRunning && logCache[runId] !== undefined) {
    logDiv.innerHTML = `<pre class="history-log-pre">${logCache[runId] || t('maint.consolidate.log_empty')}</pre>`;
    return;
  }
  logDiv.innerHTML = `<pre class="history-log-pre" style="color:var(--text-muted)">${t('common.loading')}</pre>`;
  try {
    const res = await api.getConsolidationLog(runId);
    if (!isRunning) logCache[runId] = res.log;
    logDiv.innerHTML = `<pre class="history-log-pre">${res.log || t('maint.consolidate.log_empty')}</pre>`;
  } catch {
    logDiv.innerHTML = `<pre class="history-log-pre" style="color:var(--accent-red)">Failed to load log</pre>`;
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
          ? (r.errors?.[0]?.error || 'failed')
          : `${r.succeeded} ok${r.failed ? ', ' + r.failed + ' fail' : ''}`;
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

export async function renderDashboard(root) {
  stopPolling();

  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('dashboard.title')}</h1>
      <p class="page-subtitle">${t('dashboard.subtitle')}</p>
    </div>
    <div class="stats-grid" id="stats-grid">
      <div class="stat-card"><div class="stat-label">${t('dashboard.total_memories')}</div><div class="stat-value blue" id="st-memories">-</div></div>
      <div class="stat-card"><div class="stat-label">${t('dashboard.partitions')}</div><div class="stat-value green" id="st-partitions">-</div></div>
      <div class="stat-card"><div class="stat-label">${t('dashboard.graph_nodes')}</div><div class="stat-value purple" id="st-nodes">-</div></div>
      <div class="stat-card"><div class="stat-label">${t('dashboard.graph_edges')}</div><div class="stat-value yellow" id="st-edges">-</div></div>
    </div>
    <div class="card mb-4">
      <div class="flex-between mb-4">
        <h3 style="font-size:14px;font-weight:600;">${t('dashboard.partition_dist')}</h3>
      </div>
      <div class="bar-chart" id="partition-bars"></div>
    </div>
    <div class="card">
      <div class="mb-4">
        <h3 style="font-size:14px;font-weight:600;">${t('maint.title')}</h3>
        <p class="text-sm text-muted mt-1">${t('maint.subtitle')}</p>
      </div>
      <div class="maint-list">
        <div class="maint-card maint-card--expandable">
          <div class="maint-icon">🗂️</div>
          <div class="maint-body">
            <div class="maint-title">${t('maint.consolidate.title')}<span class="maint-term">${t('maint.consolidate.term')}</span></div>
            <div class="maint-desc">${t('maint.consolidate.desc')}</div>
            <div class="maint-meta" id="consolidate-meta"></div>
            <div class="maint-note hidden" id="consolidate-note"></div>
            <div class="consolidation-history">
              <div class="history-header">${t('maint.consolidate.history')}</div>
              <div class="history-list" id="history-list">
                <div class="text-sm text-muted">${t('common.loading')}</div>
              </div>
            </div>
          </div>
          <div class="maint-action">
            <button class="btn btn-primary" id="btn-consolidate">${t('maint.consolidate.btn')}</button>
          </div>
        </div>
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
  `;

  const btnConsolidate = document.getElementById('btn-consolidate');
  const btnForget = document.getElementById('btn-forget');

  async function loadStats() {
    try {
      const stats = await api.getStats();
      document.getElementById('st-memories').textContent = stats.total_memories;
      document.getElementById('st-partitions').textContent = stats.partitions.length;
      document.getElementById('st-nodes').textContent = stats.graph.tag_count;
      document.getElementById('st-edges').textContent = stats.graph.edge_count;

      const bars = document.getElementById('partition-bars');
      const maxCount = Math.max(1, ...stats.partitions.map(p => p.memory_count));
      bars.innerHTML = stats.partitions.map(p => `
        <div class="bar-row">
          <span class="bar-label" title="${p.id}">${p.name}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${(p.memory_count / maxCount * 100).toFixed(1)}%"></div></div>
          <span class="bar-value">${p.memory_count}</span>
        </div>
      `).join('');

      const jobs = stats.scheduler?.jobs || {};
      const hippo = stats.partitions.find(p => p.id === 'mem_hippocampus');
      const pending = hippo ? hippo.memory_count : 0;

      const consNext = jobs.consolidation_job?.next_run_time;
      const consAuto = consNext ? t('maint.auto_next', { time: fmtTime(consNext) }) : t('maint.auto_bg');
      const pendText = pending > 0
        ? t('maint.consolidate.pending', { n: pending })
        : t('maint.consolidate.none_pending');
      document.getElementById('consolidate-meta').textContent = `${consAuto} · ${pendText}`;
      if (!pollTimer) btnConsolidate.disabled = pending === 0;

      const forgetNext = jobs.forgetting_job?.next_run_time;
      document.getElementById('forget-meta').textContent =
        forgetNext ? t('maint.auto_next', { time: fmtTime(forgetNext) }) : t('maint.auto_bg');
    } catch (e) {
      document.getElementById('st-memories').textContent = '!';
      error(e.message);
    }
  }

  function startPolling(runId) {
    btnConsolidate.disabled = true;
    btnConsolidate.textContent = t('maint.running');
    stopPolling();

    // Auto-expand the running row's log panel
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

        // Live-stream log into the expanded panel
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
              logDiv.innerHTML = `<pre class="history-log-pre">${res.log || t('maint.consolidate.log_empty')}</pre>`;
              if (wasAtBottom) logDiv.scrollTop = logDiv.scrollHeight;
            } catch { /* ignore log fetch errors during polling */ }
          }
        }

        if (run.status === 'done' || run.status === 'failed') {
          stopPolling();
          delete logCache[runId];
          if (run.status === 'failed') {
            error(run.errors?.[0]?.error || 'Consolidation failed');
          } else if (!run.processed) {
            info(t('maint.consolidate.nothing'));
          } else if (run.failed > 0) {
            error(t('maint.consolidate.done_fail', { ok: run.succeeded, fail: run.failed }));
          } else {
            success(t('maint.consolidate.done', { ok: run.succeeded }));
          }
          btnConsolidate.textContent = t('maint.consolidate.btn');
          await loadStats();
          await loadHistory();
        }
      } catch {
        stopPolling();
        btnConsolidate.textContent = t('maint.consolidate.btn');
        btnConsolidate.disabled = false;
      }
    }, 2000);
  }

  await Promise.all([loadStats(), loadHistory()]);

  // Detect in-progress run on page load
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
      await loadStats();
    }
  };
}

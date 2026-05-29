/**
 * Dashboard — system stats, partition distribution, memory maintenance.
 */

import * as api from '../api.js';
import { t, getLang } from '../i18n.js';
import { success, error, info } from './toast.js';

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

export async function renderDashboard(root) {
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
        <div class="maint-card">
          <div class="maint-icon">🗂️</div>
          <div class="maint-body">
            <div class="maint-title">${t('maint.consolidate.title')}<span class="maint-term">${t('maint.consolidate.term')}</span></div>
            <div class="maint-desc">${t('maint.consolidate.desc')}</div>
            <div class="maint-meta" id="consolidate-meta"></div>
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
      btnConsolidate.disabled = pending === 0;

      const forgetNext = jobs.forgetting_job?.next_run_time;
      document.getElementById('forget-meta').textContent =
        forgetNext ? t('maint.auto_next', { time: fmtTime(forgetNext) }) : t('maint.auto_bg');
    } catch (e) {
      document.getElementById('st-memories').textContent = '!';
      error(e.message);
    }
  }

  await loadStats();

  btnConsolidate.onclick = async () => {
    btnConsolidate.disabled = true;
    btnConsolidate.textContent = t('maint.running');
    try {
      const r = await api.triggerConsolidate();
      if (!r.processed) {
        info(t('maint.consolidate.nothing'));
      } else if (r.failed > 0) {
        error(t('maint.consolidate.done_fail', { ok: r.succeeded, fail: r.failed }));
      } else {
        success(t('maint.consolidate.done', { ok: r.succeeded }));
      }
    } catch (e) {
      error(e.message);
    } finally {
      btnConsolidate.textContent = t('maint.consolidate.btn');
      await loadStats();
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

/**
 * Dashboard — system stats, partition distribution, quick actions.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error } from './toast.js';

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
      <div class="flex-between mb-4">
        <h3 style="font-size:14px;font-weight:600;">${t('dashboard.quick_actions')}</h3>
      </div>
      <div class="btn-group">
        <button class="btn" id="btn-consolidate">${t('dashboard.run_consolidation')}</button>
        <button class="btn" id="btn-forget">${t('dashboard.run_forget')}</button>
      </div>
      <div id="action-result" class="mt-4 text-sm text-muted"></div>
    </div>
  `;

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
  } catch (e) {
    document.getElementById('st-memories').textContent = '!';
    error(e.message);
  }

  document.getElementById('btn-consolidate').onclick = async () => {
    const res = document.getElementById('action-result');
    try {
      res.textContent = t('common.loading');
      const r = await api.triggerConsolidate();
      res.textContent = `${r.succeeded} succeeded, ${r.failed} failed`;
      if (r.failed > 0 && Array.isArray(r.errors) && r.errors.length) {
        const sample = r.errors.slice(0, 3).map(e => e.error).join(' | ');
        const more = r.errors.length > 3 ? ` (+${r.errors.length - 3} more)` : '';
        error(`Consolidation: ${r.failed} failed — ${sample}${more}`);
      } else {
        success('Consolidation complete');
      }
    } catch (e) { res.textContent = ''; error(e.message); }
  };
  document.getElementById('btn-forget').onclick = async () => {
    const res = document.getElementById('action-result');
    try {
      res.textContent = t('common.loading');
      const r = await api.triggerForget();
      res.textContent = `${r.deleted} deleted`;
      success('Forget complete');
    } catch (e) { res.textContent = ''; error(e.message); }
  };
}

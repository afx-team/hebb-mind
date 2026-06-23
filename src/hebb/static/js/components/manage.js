/**
 * Manage (记忆管理) — system overview + memories / partitions / graph in tabs.
 *
 * The landing page for working with memory data: a compact stats band on top
 * (total memories · partitions · graph nodes/edges), then in-page tabs that
 * delegate to the memories table (with "+ New Memory"), the partitions view
 * (distribution + "+ New Partition"), and the knowledge graph.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { runCleanups } from '../lifecycle.js';
import { error } from './toast.js';
import { renderMemories } from './memories.js';
import { renderPartitions } from './partitions.js';
import { renderGraph } from './graph.js';

const TABS = [
  { id: 'memories', labelKey: 'manage.tab.memories', render: renderMemories },
  { id: 'partitions', labelKey: 'manage.tab.partitions', render: renderPartitions },
  { id: 'graph', labelKey: 'manage.tab.graph', render: renderGraph },
];

export async function renderManage(root, sub) {
  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('manage.title')}</h1>
      <p class="page-subtitle">${t('manage.subtitle')}</p>
    </div>
    <div class="stats-grid" id="manage-stats">
      <div class="stat-card"><div class="stat-label">${t('dashboard.total_memories')}</div><div class="stat-value blue" id="st-memories">-</div></div>
      <div class="stat-card"><div class="stat-label">${t('dashboard.partitions')}</div><div class="stat-value green" id="st-partitions">-</div></div>
      <div class="stat-card"><div class="stat-label">${t('dashboard.graph_nodes')}</div><div class="stat-value purple" id="st-nodes">-</div></div>
      <div class="stat-card"><div class="stat-label">${t('dashboard.graph_edges')}</div><div class="stat-value yellow" id="st-edges">-</div></div>
    </div>
    <div class="console-tabs" id="manage-tabs"></div>
    <div id="manage-tab-body"></div>
  `;

  /* Overview stats */
  (async () => {
    try {
      const stats = await api.getStats();
      root.querySelector('#st-memories').textContent = stats.total_memories;
      root.querySelector('#st-partitions').textContent = stats.partitions.length;
      root.querySelector('#st-nodes').textContent = stats.graph.tag_count;
      root.querySelector('#st-edges').textContent = stats.graph.edge_count;
    } catch (e) {
      root.querySelector('#st-memories').textContent = '!';
      error(e.message);
    }
  })();

  const tabBar = root.querySelector('#manage-tabs');
  const body = root.querySelector('#manage-tab-body');

  let active = sub && TABS.some((x) => x.id === sub) ? sub : localStorage.getItem('hebb-manage-tab');
  if (!TABS.some((tab) => tab.id === active)) active = TABS[0].id;

  tabBar.innerHTML = TABS.map(
    (tab) => `<button class="console-tab" data-tab="${tab.id}">${t(tab.labelKey)}</button>`
  ).join('');

  async function showTab(id) {
    active = id;
    localStorage.setItem('hebb-manage-tab', id);
    if (location.hash !== `#manage/${id}`) history.replaceState(null, '', `#manage/${id}`);
    tabBar.querySelectorAll('.console-tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === id));
    // Tear down the outgoing tab (e.g. the Graph renderer/observer) before swap.
    runCleanups();
    body.innerHTML = '';
    const tab = TABS.find((x) => x.id === id) || TABS[0];
    await tab.render(body);
  }

  tabBar.querySelectorAll('.console-tab').forEach((btn) => {
    btn.addEventListener('click', () => showTab(btn.dataset.tab));
  });

  await showTab(active);
}

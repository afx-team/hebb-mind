/**
 * Agent Sync — use Hebb Mind as the shared memory hub for agent sessions.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error } from './toast.js';

let hostFilter = '';
let sessions = [];
let loading = false;

const HOSTS = [
  { id: 'claude_code', label: 'Claude Code', tone: 'green' },
  { id: 'codex', label: 'Codex', tone: 'blue' },
];

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtDate(epochSeconds) {
  if (!epochSeconds) return '-';
  return new Date(epochSeconds * 1000).toLocaleString('sv-SE', { dateStyle: 'short', timeStyle: 'short' });
}

function hostLabel(host) {
  return host === 'codex' ? 'Codex' : 'Claude Code';
}

function hostTone(host) {
  return host === 'codex' ? 'blue' : 'green';
}

function visibleSessions() {
  return hostFilter ? sessions.filter(s => s.host === hostFilter) : sessions;
}

function totals(items = visibleSessions()) {
  return items.reduce((acc, s) => {
    acc.sessions += 1;
    acc.turns += s.turn_count || 0;
    acc.synced += s.synced_turns || 0;
    acc.pending += s.unsynced_turns || 0;
    return acc;
  }, { sessions: 0, turns: 0, synced: 0, pending: 0 });
}

function hostTotals(host) {
  return totals(sessions.filter(s => s.host === host));
}

function sourceLabel() {
  return hostFilter ? hostLabel(hostFilter) : t('agent_sync.all_sources');
}

async function load(root) {
  loading = true;
  renderBody(root);
  try {
    sessions = await api.listAgentSessions();
  } catch (e) {
    error(e.message);
    sessions = [];
  } finally {
    loading = false;
    renderBody(root);
  }
}

async function sync(root, ids = []) {
  try {
    const resp = await api.syncAgentSessions({
      host: hostFilter || null,
      ids,
    });
    success(t('agent_sync.synced_ok', {
      created: resp.memories_created,
      skipped: resp.skipped_existing,
    }));
    await load(root);
  } catch (e) {
    error(`${t('agent_sync.sync_failed')}: ${e.message}`);
  }
}

function renderSwitcher(root) {
  root.querySelectorAll('[data-agent-host]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.agentHost === hostFilter);
  });
}

function renderFlow(root) {
  const st = totals();
  root.querySelector('#agent-sync-flow').innerHTML = `
    <section class="agent-flow-panel">
      <div class="agent-flow-label">${t('agent_sync.source_label')}</div>
      <div class="agent-flow-title">${esc(sourceLabel())}</div>
      <div class="agent-flow-meta">
        <span>${st.sessions} ${t('agent_sync.unit.sessions')}</span>
        <span>${st.turns} ${t('agent_sync.unit.turns')}</span>
      </div>
    </section>
    <div class="agent-flow-arrow" aria-hidden="true">→</div>
    <section class="agent-flow-hub">
      <div class="agent-flow-label">${t('agent_sync.hub_label')}</div>
      <div class="agent-hub-name">Hebb Mind</div>
      <div class="agent-hub-metrics">
        <span><strong>${st.synced}</strong>${t('agent_sync.metric.in_hub')}</span>
        <span><strong>${st.pending}</strong>${t('agent_sync.metric.pending')}</span>
      </div>
    </section>
    <div class="agent-flow-arrow" aria-hidden="true">→</div>
    <section class="agent-flow-panel">
      <div class="agent-flow-label">${t('agent_sync.available_label')}</div>
      <div class="agent-targets">
        ${HOSTS.map(host => `
          <span class="agent-target-chip ${host.id === hostFilter || !hostFilter ? 'active' : ''}">
            <span class="agent-dot ${host.tone}"></span>${host.label}
          </span>
        `).join('')}
      </div>
      <div class="agent-flow-meta">${t('agent_sync.shared_ready')}</div>
    </section>
  `;
}

function renderSourceCards(root) {
  root.querySelector('#agent-source-cards').innerHTML = HOSTS.map(host => {
    const st = hostTotals(host.id);
    return `
      <button class="agent-source-card ${hostFilter === host.id ? 'active' : ''}" data-source-card="${host.id}">
        <span class="agent-dot ${host.tone}"></span>
        <span class="agent-source-main">
          <strong>${host.label}</strong>
          <span>${st.sessions} ${t('agent_sync.unit.sessions')} · ${st.pending} ${t('agent_sync.pending_short')}</span>
        </span>
        <span class="agent-source-count">${st.synced}/${st.turns}</span>
      </button>
    `;
  }).join('');
  root.querySelectorAll('[data-source-card]').forEach(btn => {
    btn.onclick = () => {
      hostFilter = btn.dataset.sourceCard;
      renderBody(root);
    };
  });
}

function progressPct(s) {
  if (!s.turn_count) return 0;
  return Math.max(0, Math.min(100, Math.round((s.synced_turns / s.turn_count) * 100)));
}

function renderList(root) {
  const list = root.querySelector('#agent-sync-list');
  if (loading) {
    list.innerHTML = `<div class="empty-state">${t('common.loading')}</div>`;
    return;
  }
  const items = visibleSessions();
  if (!items.length) {
    list.innerHTML = `<div class="empty-state">${t('agent_sync.empty_selected', { agent: sourceLabel() })}</div>`;
    return;
  }
  list.innerHTML = items.map(s => `
    <article class="agent-session-card">
      <div class="agent-session-head">
        <span class="tag tag-${hostTone(s.host)}">${hostLabel(s.host)}</span>
        <strong>${esc(s.project || t('agent_sync.unknown_project'))}</strong>
        <span class="agent-session-time">${fmtDate(s.updated_at)}</span>
      </div>
      <div class="agent-session-body">
        <div class="agent-session-path">${esc(s.path)}</div>
        <div class="agent-session-sync">
          <div class="agent-progress" aria-label="${t('agent_sync.synced')}">
            <span style="width:${progressPct(s)}%"></span>
          </div>
          <div class="agent-session-count">
            <span class="text-mono">${s.synced_turns}/${s.turn_count}</span>
            ${s.unsynced_turns ? `<span class="tag tag-yellow">${s.unsynced_turns} ${t('agent_sync.pending_short')}</span>` : `<span class="tag tag-green">${t('agent_sync.done_short')}</span>`}
          </div>
        </div>
        <button class="btn btn-sm" data-sync-id="${esc(s.id)}" ${s.unsynced_turns ? '' : 'disabled'}>
          ${t('agent_sync.sync_one')}
        </button>
      </div>
    </article>
  `).join('');
  list.querySelectorAll('[data-sync-id]').forEach(btn => {
    btn.onclick = () => sync(root, [btn.dataset.syncId]);
  });
}

function renderBody(root) {
  renderSwitcher(root);
  renderFlow(root);
  renderSourceCards(root);
  const pending = totals().pending;
  const syncAll = root.querySelector('#agent-sync-all');
  if (syncAll) syncAll.disabled = loading || pending === 0;
  const scope = root.querySelector('#agent-sync-scope');
  if (scope) scope.textContent = sourceLabel();
  renderList(root);
}

export async function renderAgentSync(root) {
  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('agent_sync.title')}</h1>
      <p class="page-subtitle">${t('agent_sync.subtitle')}</p>
    </div>
    <div class="agent-hub-toolbar">
      <div class="seg" id="agent-host-switcher">
        <button class="seg-btn" data-agent-host="">${t('agent_sync.host_all')}</button>
        <button class="seg-btn" data-agent-host="claude_code">Claude Code</button>
        <button class="seg-btn" data-agent-host="codex">Codex</button>
      </div>
      <div class="agent-hub-actions">
        <button class="btn" id="agent-sync-refresh">${t('common.refresh')}</button>
        <button class="btn btn-primary" id="agent-sync-all">${t('agent_sync.sync_pending')}</button>
      </div>
    </div>
    <div class="agent-flow" id="agent-sync-flow"></div>
    <div class="agent-source-cards" id="agent-source-cards"></div>
    <div class="agent-session-section">
      <div class="agent-section-head">
        <div>
          <h2>${t('agent_sync.queue_title')}</h2>
          <p>${t('agent_sync.queue_subtitle', { agent: `<span id="agent-sync-scope">${esc(sourceLabel())}</span>` })}</p>
        </div>
      </div>
      <div class="agent-session-list" id="agent-sync-list"></div>
    </div>
  `;
  root.querySelectorAll('[data-agent-host]').forEach(btn => {
    btn.onclick = () => {
      hostFilter = btn.dataset.agentHost;
      renderBody(root);
    };
  });
  root.querySelector('#agent-sync-refresh').onclick = () => load(root);
  root.querySelector('#agent-sync-all').onclick = () => sync(root);
  await load(root);
}

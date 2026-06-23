/**
 * Partitions — distribution chart + card list with inline-editable descriptions.
 * mem_hippocampus cannot be disabled. Rendered as a Manage tab body (no page
 * header of its own); "+ New Partition" lives in the tab toolbar.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error } from './toast.js';

function esc(s) {
  // Escapes the double-quote too — esc() is used inside double-quoted HTML
  // attributes (the inline description-edit input's value="…").
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function renderDistribution(root, list) {
  const bars = root.querySelector('#part-bars');
  if (!bars) return;
  if (!list.length) {
    bars.innerHTML = `<div class="text-sm text-muted">${t('partitions.no_partitions')}</div>`;
    return;
  }
  const maxCount = Math.max(1, ...list.map(p => p.memory_count));
  bars.innerHTML = list.map(p => `
    <div class="bar-row">
      <span class="bar-label" title="${esc(p.id)}">${esc(p.name)}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${(p.memory_count / maxCount * 100).toFixed(1)}%"></div></div>
      <span class="bar-value">${p.memory_count}</span>
    </div>
  `).join('');
}

async function loadList(root) {
  const container = root.querySelector('#part-list');
  container.innerHTML = `<div class="text-muted" style="padding:20px;text-align:center">${t('common.loading')}</div>`;
  try {
    const list = await api.listPartitions();
    renderDistribution(root, list);
    container.innerHTML = list.map(p => {
      const isHippocampus = p.id === 'mem_hippocampus';
      return `
      <div class="partition-card">
        <div class="partition-header">
          <div class="partition-info">
            <div class="partition-title">
              <span class="partition-name">${esc(p.name)}</span>
              <span class="text-mono text-muted" style="font-size:12px">${p.id}</span>
              ${p.is_system ? `<span class="tag tag-green">${t('partitions.system_badge')}</span>` : `<span class="tag">${t('partitions.custom_badge')}</span>`}
            </div>
            <div class="partition-meta text-sm text-muted">${t('memories.count', { n: p.memory_count })}</div>
          </div>
          <div class="partition-actions">
            ${isHippocampus
              ? `<div class="toggle on" style="opacity:0.4;cursor:not-allowed" title="${t('partitions.always_enabled')}"></div>`
              : `<div class="toggle ${p.enabled ? 'on' : ''}" data-id="${p.id}" data-enabled="${p.enabled}"></div>`
            }
            ${p.is_system ? '' : `<button class="btn btn-sm btn-danger btn-del" data-id="${p.id}">${t('memories.delete')}</button>`}
          </div>
        </div>
        <div class="partition-desc-row" data-id="${p.id}">
          <div class="partition-desc-view" title="${t('partitions.desc_label')}">
            ${p.description ? esc(p.description) : `<span style="font-style:italic">${t('partitions.no_desc')}</span>`}
          </div>
          <div class="partition-desc-edit hidden">
            <input class="form-input" type="text" value="${esc(p.description || '')}" placeholder="${t('partitions.desc_placeholder')}">
            <button class="btn btn-sm btn-primary desc-save">${t('common.save')}</button>
            <button class="btn btn-sm desc-cancel">${t('common.cancel')}</button>
          </div>
        </div>
      </div>`;
    }).join('');

    /* Toggle enable/disable */
    container.querySelectorAll('.toggle[data-id]').forEach(el => {
      el.onclick = async () => {
        const enabled = el.dataset.enabled === 'true';
        try {
          await api.updatePartition(el.dataset.id, { enabled: !enabled });
          success(!enabled ? t('partitions.enabled_ok') : t('partitions.disabled_ok'));
          loadList(root);
        } catch (e) { error(e.message); }
      };
    });

    /* Delete */
    container.querySelectorAll('.btn-del').forEach(btn => {
      btn.onclick = async () => {
        if (!confirm(t('partitions.confirm_delete'))) return;
        try {
          await api.deletePartition(btn.dataset.id);
          success(t('partitions.deleted_ok'));
          loadList(root);
        } catch (e) { error(e.message); }
      };
    });

    /* Inline edit description */
    container.querySelectorAll('.partition-desc-row').forEach(row => {
      const id = row.dataset.id;
      const viewEl = row.querySelector('.partition-desc-view');
      const editEl = row.querySelector('.partition-desc-edit');
      const input = editEl.querySelector('input');
      const saveBtn = editEl.querySelector('.desc-save');
      const cancelBtn = editEl.querySelector('.desc-cancel');

      viewEl.onclick = () => {
        viewEl.classList.add('hidden');
        editEl.classList.remove('hidden');
        input.focus();
        input.select();
      };

      cancelBtn.onclick = () => {
        editEl.classList.add('hidden');
        viewEl.classList.remove('hidden');
      };

      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') saveBtn.click();
        if (e.key === 'Escape') cancelBtn.click();
      });

      saveBtn.onclick = async () => {
        const desc = input.value.trim();
        try {
          await api.updatePartition(id, { description: desc });
          success(t('partitions.desc_updated'));
          loadList(root);
        } catch (e) { error(e.message); }
      };
    });

  } catch (e) { error(e.message); }
}

export async function renderPartitions(root) {
  root.innerHTML = `
    <div class="tab-toolbar">
      <span class="text-sm text-muted">${t('partitions.subtitle')}</span>
      <button class="btn btn-primary" id="btn-create-part">${t('partitions.new')}</button>
    </div>
    <div class="card mb-4">
      <h3 style="font-size:14px;font-weight:600;margin-bottom:14px;">${t('dashboard.partition_dist')}</h3>
      <div class="bar-chart" id="part-bars"></div>
    </div>
    <div id="part-list" class="partition-list"></div>
  `;

  await loadList(root);

  root.querySelector('#btn-create-part').onclick = () => {
    const overlay = document.getElementById('modal-overlay');
    overlay.classList.remove('hidden');
    overlay.innerHTML = `
      <div class="modal">
        <h3 class="modal-title">${t('partitions.create_title')}</h3>
        <div class="form-group">
          <label class="form-label">${t('partitions.id_label')} <span class="text-muted">${t('partitions.id_pattern_hint')}</span></label>
          <input class="form-input" id="p-id" placeholder="mem_my_space">
        </div>
        <div class="form-group">
          <label class="form-label">${t('partitions.name_label')}</label>
          <input class="form-input" id="p-name" placeholder="My Space">
        </div>
        <div class="form-group">
          <label class="form-label">${t('partitions.desc_label')} <span class="text-muted">(${t('partitions.desc_hint')})</span></label>
          <textarea class="form-textarea" id="p-desc" rows="2" placeholder="${t('partitions.desc_placeholder')}"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn" id="modal-cancel">${t('common.cancel')}</button>
          <button class="btn btn-primary" id="modal-save">${t('partitions.new_short')}</button>
        </div>
      </div>
    `;
    overlay.querySelector('#modal-cancel').onclick = () => overlay.classList.add('hidden');
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.classList.add('hidden'); });
    overlay.querySelector('#modal-save').onclick = async () => {
      const id = overlay.querySelector('#p-id').value.trim();
      const name = overlay.querySelector('#p-name').value.trim();
      if (!id || !name) { error(t('partitions.id_required')); return; }
      if (!/^mem_[a-z0-9_]+$/.test(id)) { error(t('partitions.id_pattern')); return; }
      try {
        await api.createPartition({ id, name, description: overlay.querySelector('#p-desc').value.trim() });
        overlay.classList.add('hidden');
        success(t('partitions.created_ok'));
        loadList(root);
      } catch (e) { error(e.message); }
    };
  };
}

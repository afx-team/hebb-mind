/**
 * Memories — list, create, edit, delete memories.
 *
 * Rendered as a tab body inside the Manage page (no page header of its own);
 * the "+ New Memory" action lives in the tab toolbar.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error } from './toast.js';

const PAGE_SIZE = 20;
let offset = 0;
let currentPartition = '';

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function fmtDate(d) { return new Date(d).toLocaleString('sv-SE', { dateStyle: 'short', timeStyle: 'short' }); }
function importanceColor(v) { return v >= 7 ? 'var(--accent-red)' : v >= 4 ? 'var(--accent-yellow)' : 'var(--accent-green)'; }

async function loadPartitions(select) {
  try {
    const list = await api.listPartitions();
    select.innerHTML = `<option value="">${t('memories.all_partitions')}</option>` +
      list.map(p => `<option value="${p.id}">${esc(p.name)} (${p.id})</option>`).join('');
    select.value = currentPartition;
  } catch (e) { error(e.message); }
}

async function loadList(root) {
  const list = root.querySelector('#mem-list');
  const info = root.querySelector('#mem-info');
  const pag = root.querySelector('#mem-pagination');
  list.innerHTML = `<div class="text-muted" style="padding:28px;text-align:center">${t('common.loading')}</div>`;
  try {
    const params = { offset, limit: PAGE_SIZE };
    if (currentPartition) params.partition_id = currentPartition;
    const data = await api.listMemories(params);
    info.textContent = t('memories.count', { n: data.total });
    if (!data.items.length) {
      list.innerHTML = `<div class="empty-state">${t('memories.no_memories')}</div>`;
      pag.innerHTML = '';
      return;
    }
    list.innerHTML = data.items.map(m => `
      <div class="mem-card" data-id="${esc(m.id)}">
        <div class="mem-card-head">
          <span class="tag tag-blue">${esc(m.partition_id.replace('mem_', ''))}</span>
          <span class="mem-imp" title="${t('memories.importance')}: ${m.importance_score.toFixed(1)}">
            <span class="mem-imp-dot" style="background:${importanceColor(m.importance_score)}"></span>${m.importance_score.toFixed(1)}
          </span>
          <span class="mem-card-date">${fmtDate(m.created_at)}</span>
          <div class="mem-card-actions">
            <button class="btn btn-sm btn-edit" data-id="${esc(m.id)}">${t('memories.edit')}</button>
            <button class="btn btn-sm btn-danger btn-del" data-id="${esc(m.id)}">${t('memories.delete')}</button>
          </div>
        </div>
        <div class="mem-card-body">${esc(m.content)}</div>
        ${m.tags.length ? `<div class="mem-card-tags">${m.tags.map(tag => `<span class="tag">${esc(tag)}</span>`).join('')}</div>` : ''}
      </div>
    `).join('');

    /* Pagination */
    const totalPages = Math.ceil(data.total / PAGE_SIZE);
    const curPage = Math.floor(offset / PAGE_SIZE) + 1;
    pag.innerHTML = totalPages > 1 ? `
      <button class="btn btn-sm" id="pg-prev" ${curPage <= 1 ? 'disabled' : ''}>${t('common.prev')}</button>
      <span class="text-sm text-muted">${curPage} / ${totalPages}</span>
      <button class="btn btn-sm" id="pg-next" ${curPage >= totalPages ? 'disabled' : ''}>${t('common.next')}</button>
    ` : '';
    pag.querySelector('#pg-prev')?.addEventListener('click', () => { offset = Math.max(0, offset - PAGE_SIZE); loadList(root); });
    pag.querySelector('#pg-next')?.addEventListener('click', () => { offset += PAGE_SIZE; loadList(root); });

    /* Delete */
    list.querySelectorAll('.btn-del').forEach(btn => {
      btn.onclick = async () => {
        if (!confirm(t('memories.confirm_delete'))) return;
        try {
          await api.deleteMemory(btn.dataset.id);
          success(t('memories.deleted_ok'));
          loadList(root);
        } catch (e) { error(e.message); }
      };
    });

    /* Edit */
    list.querySelectorAll('.btn-edit').forEach(btn => {
      btn.onclick = async () => {
        try {
          const m = await api.getMemory(btn.dataset.id);
          showEditModal(m, root);
        } catch (e) { error(e.message); }
      };
    });
  } catch (e) {
    list.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
    pag.innerHTML = '';
    error(e.message);
  }
}

function showModal(title, html, onSave) {
  const overlay = document.getElementById('modal-overlay');
  overlay.classList.remove('hidden');
  overlay.innerHTML = `
    <div class="modal">
      <h3 class="modal-title">${title}</h3>
      ${html}
      <div class="modal-actions">
        <button class="btn" id="modal-cancel">${t('memories.cancel')}</button>
        <button class="btn btn-primary" id="modal-save">${t('memories.save')}</button>
      </div>
    </div>
  `;
  overlay.querySelector('#modal-cancel').onclick = () => overlay.classList.add('hidden');
  overlay.querySelector('#modal-save').onclick = () => onSave(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.classList.add('hidden'); });
}

function showCreateModal(root, partitions) {
  const options = partitions.map(p =>
    `<option value="${p.id}" ${p.id === 'mem_hippocampus' ? 'selected' : ''}>${esc(p.name)}</option>`
  ).join('');
  showModal(t('memories.create_title'), `
    <div class="form-group">
      <label class="form-label">${t('memories.content')}</label>
      <textarea class="form-textarea" id="m-content" rows="4" placeholder="${t('memories.content_placeholder')}"></textarea>
    </div>
    <div class="form-group">
      <label class="form-label">${t('memories.partition')}</label>
      <select class="form-select" id="m-partition">${options}</select>
    </div>
    <div class="form-group">
      <label class="form-label">${t('memories.importance')}: <span id="m-imp-val">5.0</span></label>
      <div class="range-group">
        <input type="range" id="m-importance" min="0" max="10" step="0.5" value="5">
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">${t('memories.tags')}</label>
      <input class="form-input" id="m-tags" placeholder="${t('memories.tags_placeholder')}">
    </div>
  `, async (overlay) => {
    const content = overlay.querySelector('#m-content').value.trim();
    if (!content) { error(t('memories.content_required')); return; }
    try {
      await api.createMemory({
        content,
        partition_id: overlay.querySelector('#m-partition').value,
        importance_score: parseFloat(overlay.querySelector('#m-importance').value),
        tags: overlay.querySelector('#m-tags').value.split(',').map(t => t.trim()).filter(Boolean),
      });
      overlay.classList.add('hidden');
      success(t('memories.created_ok'));
      loadList(root);
    } catch (e) { error(e.message); }
  });
  document.getElementById('m-importance').oninput = (e) => {
    document.getElementById('m-imp-val').textContent = parseFloat(e.target.value).toFixed(1);
  };
}

function showEditModal(m, root) {
  showModal(t('memories.edit_title'), `
    <div class="form-group">
      <label class="form-label">${t('memories.content')}</label>
      <textarea class="form-textarea" id="m-content" rows="4"></textarea>
    </div>
    <div class="form-group">
      <label class="form-label">${t('memories.importance')}: <span id="m-imp-val">${m.importance_score.toFixed(1)}</span></label>
      <div class="range-group">
        <input type="range" id="m-importance" min="0" max="10" step="0.5" value="${m.importance_score}">
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">${t('memories.tags')}</label>
      <input class="form-input" id="m-tags" value="${esc(m.tags.join(', '))}">
    </div>
    <div class="text-sm text-muted mt-4">
      ID: <span class="text-mono">${esc(m.id)}</span><br>
      ${t('memories.created')}: ${fmtDate(m.created_at)}
    </div>
  `, async (overlay) => {
    const content = overlay.querySelector('#m-content').value.trim();
    if (!content) { error(t('memories.content_required')); return; }
    try {
      await api.updateMemory(m.id, {
        content,
        importance_score: parseFloat(overlay.querySelector('#m-importance').value),
        tags: overlay.querySelector('#m-tags').value.split(',').map(s => s.trim()).filter(Boolean),
      });
      overlay.classList.add('hidden');
      success(t('memories.updated_ok'));
      loadList(root);
    } catch (e) { error(e.message); }
  });
  // Set the textarea value via the DOM (not HTML interpolation) so memory content
  // is never parsed as markup — closes the stored-XSS hole on the edit form.
  document.getElementById('m-content').value = m.content;
  document.getElementById('m-importance').oninput = (e) => {
    document.getElementById('m-imp-val').textContent = parseFloat(e.target.value).toFixed(1);
  };
}

export async function renderMemories(root) {
  // Reset paging on (re)mount — this view is torn down/rebuilt on every Manage
  // tab switch, so a stale offset must not survive into a fresh render.
  offset = 0;
  root.innerHTML = `
    <div class="tab-toolbar">
      <div class="flex gap-4" style="align-items:center;">
        <select class="form-select" id="filter-partition" style="max-width:240px"><option value="">${t('memories.all_partitions')}</option></select>
        <span class="text-sm text-muted" id="mem-info">${t('common.loading')}</span>
      </div>
      <button class="btn btn-primary" id="btn-create">${t('memories.new')}</button>
    </div>
    <div id="mem-list" class="mem-list"></div>
    <div class="pagination" id="mem-pagination"></div>
  `;

  const filterSelect = root.querySelector('#filter-partition');
  await loadPartitions(filterSelect);
  filterSelect.onchange = () => { currentPartition = filterSelect.value; offset = 0; loadList(root); };

  root.querySelector('#btn-create').onclick = async () => {
    const partitions = await api.listPartitions();
    showCreateModal(root, partitions);
  };

  await loadList(root);
}

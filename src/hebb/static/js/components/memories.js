/**
 * Memories — list, create, edit, delete memories.
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
function truncate(s, n = 80) { return s.length > n ? s.slice(0, n) + '...' : s; }
function fmtDate(d) { return new Date(d).toLocaleString('sv-SE', { dateStyle: 'short', timeStyle: 'short' }); }
function importanceColor(v) { return v >= 7 ? 'var(--accent-red)' : v >= 4 ? 'var(--accent-yellow)' : 'var(--accent-green)'; }

async function loadPartitions(select) {
  try {
    const list = await api.listPartitions();
    select.innerHTML = '<option value="">All partitions</option>' +
      list.map(p => `<option value="${p.id}">${p.name} (${p.id})</option>`).join('');
    select.value = currentPartition;
  } catch (e) { error(e.message); }
}

async function loadTable(root) {
  const tbody = root.querySelector('#mem-tbody');
  const info = root.querySelector('#mem-info');
  tbody.innerHTML = '<tr><td colspan="6" class="text-muted" style="text-align:center">Loading...</td></tr>';
  try {
    const params = { offset, limit: PAGE_SIZE };
    if (currentPartition) params.partition_id = currentPartition;
    const data = await api.listMemories(params);
    info.textContent = `${data.total} memories`;
    if (!data.items.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No memories found</td></tr>';
      return;
    }
    tbody.innerHTML = data.items.map(m => `
      <tr data-id="${esc(m.id)}">
        <td class="td-truncate" title="${esc(m.content)}">${esc(truncate(m.content))}</td>
        <td><span class="tag tag-blue">${esc(m.partition_id.replace('mem_', ''))}</span></td>
        <td><span style="color:${importanceColor(m.importance_score)}">${m.importance_score.toFixed(1)}</span></td>
        <td>${m.tags.map(tag => `<span class="tag">${esc(tag)}</span>`).join(' ')}</td>
        <td class="text-muted text-sm">${fmtDate(m.created_at)}</td>
        <td>
          <div class="btn-group">
            <button class="btn btn-sm btn-edit" data-id="${esc(m.id)}">${t('memories.edit')}</button>
            <button class="btn btn-sm btn-danger btn-del" data-id="${esc(m.id)}">${t('memories.delete')}</button>
          </div>
        </td>
      </tr>
    `).join('');

    /* Pagination */
    const pag = root.querySelector('#mem-pagination');
    const totalPages = Math.ceil(data.total / PAGE_SIZE);
    const curPage = Math.floor(offset / PAGE_SIZE) + 1;
    pag.innerHTML = `
      <button class="btn btn-sm" id="pg-prev" ${curPage <= 1 ? 'disabled' : ''}>Prev</button>
      <span class="text-sm text-muted">${curPage} / ${totalPages || 1}</span>
      <button class="btn btn-sm" id="pg-next" ${curPage >= totalPages ? 'disabled' : ''}>Next</button>
    `;
    pag.querySelector('#pg-prev')?.addEventListener('click', () => { offset = Math.max(0, offset - PAGE_SIZE); loadTable(root); });
    pag.querySelector('#pg-next')?.addEventListener('click', () => { offset += PAGE_SIZE; loadTable(root); });

    /* Delete */
    tbody.querySelectorAll('.btn-del').forEach(btn => {
      btn.onclick = async () => {
        if (!confirm('Delete this memory?')) return;
        try {
          await api.deleteMemory(btn.dataset.id);
          success('Memory deleted');
          loadTable(root);
        } catch (e) { error(e.message); }
      };
    });

    /* Edit */
    tbody.querySelectorAll('.btn-edit').forEach(btn => {
      btn.onclick = async () => {
        try {
          const m = await api.getMemory(btn.dataset.id);
          showEditModal(m, root);
        } catch (e) { error(e.message); }
      };
    });
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-muted">${e.message}</td></tr>`;
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
        <button class="btn" id="modal-cancel">Cancel</button>
        <button class="btn btn-primary" id="modal-save">Save</button>
      </div>
    </div>
  `;
  overlay.querySelector('#modal-cancel').onclick = () => overlay.classList.add('hidden');
  overlay.querySelector('#modal-save').onclick = () => onSave(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.classList.add('hidden'); });
}

function showCreateModal(root, partitions) {
  const options = partitions.map(p =>
    `<option value="${p.id}" ${p.id === 'mem_hippocampus' ? 'selected' : ''}>${p.name}</option>`
  ).join('');
  showModal('Create Memory', `
    <div class="form-group">
      <label class="form-label">Content</label>
      <textarea class="form-textarea" id="m-content" rows="4" placeholder="Memory content..."></textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Partition</label>
      <select class="form-select" id="m-partition">${options}</select>
    </div>
    <div class="form-group">
      <label class="form-label">Importance: <span id="m-imp-val">5.0</span></label>
      <div class="range-group">
        <input type="range" id="m-importance" min="0" max="10" step="0.5" value="5">
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Tags (comma-separated)</label>
      <input class="form-input" id="m-tags" placeholder="tag1, tag2">
    </div>
  `, async (overlay) => {
    const content = overlay.querySelector('#m-content').value.trim();
    if (!content) { error('Content is required'); return; }
    try {
      await api.createMemory({
        content,
        partition_id: overlay.querySelector('#m-partition').value,
        importance_score: parseFloat(overlay.querySelector('#m-importance').value),
        tags: overlay.querySelector('#m-tags').value.split(',').map(t => t.trim()).filter(Boolean),
      });
      overlay.classList.add('hidden');
      success('Memory created');
      loadTable(root);
    } catch (e) { error(e.message); }
  });
  document.getElementById('m-importance').oninput = (e) => {
    document.getElementById('m-imp-val').textContent = parseFloat(e.target.value).toFixed(1);
  };
}

function showEditModal(m, root) {
  showModal('Edit Memory', `
    <div class="form-group">
      <label class="form-label">Content</label>
      <textarea class="form-textarea" id="m-content" rows="4"></textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Importance: <span id="m-imp-val">${m.importance_score.toFixed(1)}</span></label>
      <div class="range-group">
        <input type="range" id="m-importance" min="0" max="10" step="0.5" value="${m.importance_score}">
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Tags (comma-separated)</label>
      <input class="form-input" id="m-tags" value="${esc(m.tags.join(', '))}">
    </div>
    <div class="text-sm text-muted mt-4">
      ID: <span class="text-mono">${esc(m.id)}</span><br>
      Created: ${fmtDate(m.created_at)} &middot; Accessed: ${esc(m.access_count)}x
    </div>
  `, async (overlay) => {
    const content = overlay.querySelector('#m-content').value.trim();
    if (!content) { error('Content is required'); return; }
    try {
      await api.updateMemory(m.id, {
        content,
        importance_score: parseFloat(overlay.querySelector('#m-importance').value),
        tags: overlay.querySelector('#m-tags').value.split(',').map(s => s.trim()).filter(Boolean),
      });
      overlay.classList.add('hidden');
      success('Memory updated');
      loadTable(root);
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
  root.innerHTML = `
    <div class="page-header flex-between">
      <div>
        <h1 class="page-title">${t('memories.title')}</h1>
        <p class="page-subtitle" id="mem-info">Loading...</p>
      </div>
      <button class="btn btn-primary" id="btn-create">${t('memories.new')}</button>
    </div>
    <div class="flex gap-4 mb-4">
      <select class="form-select" id="filter-partition" style="max-width:240px"><option value="">${t('memories.all_partitions')}</option></select>
    </div>
    <div class="card">
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>${t('memories.content')}</th><th>${t('memories.partition')}</th><th>${t('memories.importance')}</th><th>${t('memories.tags')}</th><th>${t('memories.created')}</th><th></th>
          </tr></thead>
          <tbody id="mem-tbody"></tbody>
        </table>
      </div>
      <div class="pagination" id="mem-pagination"></div>
    </div>
  `;

  const filterSelect = root.querySelector('#filter-partition');
  await loadPartitions(filterSelect);
  filterSelect.onchange = () => { currentPartition = filterSelect.value; offset = 0; loadTable(root); };

  root.querySelector('#btn-create').onclick = async () => {
    const partitions = await api.listPartitions();
    showCreateModal(root, partitions);
  };

  await loadTable(root);
}

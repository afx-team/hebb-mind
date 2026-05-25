/**
 * Partitions — card list with inline-editable descriptions.
 * mem_hippocampus cannot be disabled.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error } from './toast.js';

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function loadList(root) {
  const container = root.querySelector('#part-list');
  container.innerHTML = '<div class="text-muted" style="padding:20px;text-align:center">Loading...</div>';
  try {
    const list = await api.listPartitions();
    container.innerHTML = list.map(p => {
      const isHippocampus = p.id === 'mem_hippocampus';
      return `
      <div class="partition-card">
        <div class="partition-header">
          <div class="partition-info">
            <div class="partition-title">
              <span class="partition-name">${esc(p.name)}</span>
              <span class="text-mono text-muted" style="font-size:12px">${p.id}</span>
              ${p.is_system ? '<span class="tag tag-green">system</span>' : '<span class="tag">custom</span>'}
            </div>
            <div class="partition-meta text-sm text-muted">${p.memory_count} memor${p.memory_count === 1 ? 'y' : 'ies'}</div>
          </div>
          <div class="partition-actions">
            ${isHippocampus
              ? '<div class="toggle on" style="opacity:0.4;cursor:not-allowed" title="Always enabled"></div>'
              : `<div class="toggle ${p.enabled ? 'on' : ''}" data-id="${p.id}" data-enabled="${p.enabled}"></div>`
            }
            ${p.is_system ? '' : `<button class="btn btn-sm btn-danger btn-del" data-id="${p.id}">Delete</button>`}
          </div>
        </div>
        <div class="partition-desc-row" data-id="${p.id}">
          <div class="partition-desc-view" title="Click to edit description">
            ${p.description ? esc(p.description) : `<span style="font-style:italic">${t('partitions.no_desc')}</span>`}
          </div>
          <div class="partition-desc-edit hidden">
            <input class="form-input" type="text" value="${esc(p.description || '')}" placeholder="Describe what memories belong here...">
            <button class="btn btn-sm btn-primary desc-save">Save</button>
            <button class="btn btn-sm desc-cancel">Cancel</button>
          </div>
        </div>
      </div>`;
    }).join('');

    /* Toggle */
    container.querySelectorAll('.toggle[data-id]').forEach(el => {
      el.onclick = async () => {
        const enabled = el.dataset.enabled === 'true';
        try {
          await api.updatePartition(el.dataset.id, { enabled: !enabled });
          success(`Partition ${!enabled ? 'enabled' : 'disabled'}`);
          loadList(root);
        } catch (e) { error(e.message); }
      };
    });

    /* Delete */
    container.querySelectorAll('.btn-del').forEach(btn => {
      btn.onclick = async () => {
        if (!confirm(`Delete partition "${btn.dataset.id}"?`)) return;
        try {
          await api.deletePartition(btn.dataset.id);
          success('Partition deleted');
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
          success('Description updated');
          loadList(root);
        } catch (e) { error(e.message); }
      };
    });

  } catch (e) { error(e.message); }
}

export async function renderPartitions(root) {
  root.innerHTML = `
    <div class="page-header flex-between">
      <div>
        <h1 class="page-title">${t('partitions.title')}</h1>
        <p class="page-subtitle">${t('partitions.subtitle')}</p>
      </div>
      <button class="btn btn-primary" id="btn-create-part">${t('partitions.new')}</button>
    </div>
    <div id="part-list" class="partition-list"></div>
  `;

  await loadList(root);

  root.querySelector('#btn-create-part').onclick = () => {
    const overlay = document.getElementById('modal-overlay');
    overlay.classList.remove('hidden');
    overlay.innerHTML = `
      <div class="modal">
        <h3 class="modal-title">Create Partition</h3>
        <div class="form-group">
          <label class="form-label">ID <span class="text-muted">(pattern: mem_[a-z0-9_]+)</span></label>
          <input class="form-input" id="p-id" placeholder="mem_my_space">
        </div>
        <div class="form-group">
          <label class="form-label">Name</label>
          <input class="form-input" id="p-name" placeholder="My Space">
        </div>
        <div class="form-group">
          <label class="form-label">Description <span class="text-muted">(guides consolidation agent)</span></label>
          <textarea class="form-textarea" id="p-desc" rows="2" placeholder="Describe what kind of memories belong here..."></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn" id="modal-cancel">Cancel</button>
          <button class="btn btn-primary" id="modal-save">Create</button>
        </div>
      </div>
    `;
    overlay.querySelector('#modal-cancel').onclick = () => overlay.classList.add('hidden');
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.classList.add('hidden'); });
    overlay.querySelector('#modal-save').onclick = async () => {
      const id = overlay.querySelector('#p-id').value.trim();
      const name = overlay.querySelector('#p-name').value.trim();
      if (!id || !name) { error('ID and name are required'); return; }
      if (!/^mem_[a-z0-9_]+$/.test(id)) { error('ID must match: mem_[a-z0-9_]+'); return; }
      try {
        await api.createPartition({ id, name, description: overlay.querySelector('#p-desc').value.trim() });
        overlay.classList.add('hidden');
        success('Partition created');
        loadList(root);
      } catch (e) { error(e.message); }
    };
  };
}

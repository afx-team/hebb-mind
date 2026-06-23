/**
 * config-section.js — shared primitives for editing hebb.json config.
 *
 * Extracted from the old monolithic Settings page so the restructured modules
 * (Activate · Consolidate · Forget · System) can each render the config groups
 * that belong to them, with one consistent row layout, restart-handling, and
 * "Save appears only when changed" behavior.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error, info } from './toast.js';

/* Fields that only take effect after a service restart — flagged in the UI. */
export const RESTART_KEYS = new Set([
  'storage_type', 'pg_url', 'pg_pool_min', 'pg_pool_max',
  'embedding_enabled', 'embedding_provider', 'embedding_model', 'embedding_dim',
  'embedding_api_key', 'embedding_base_url', 'hf_endpoint',
  'embedding_api_mode', 'embedding_http_method', 'embedding_http_url',
  'embedding_http_headers', 'embedding_http_body', 'embedding_http_response_path',
  'consolidation_time', 'consolidation_concurrency', 'consolidation_max_tokens',
  'forget_interval_seconds',
  'keyword_search_enabled', 'graph_search_enabled', 'lexical_boost_enabled',
  'temporal_boost_enabled', 'graph_expansion_enabled',
  'rerank_enabled', 'rerank_provider', 'rerank_model', 'rerank_top_n',
  'host', 'port', 'home',
]);

/* Secret values — rendered as password inputs. */
export const SENSITIVE_KEYS = new Set(['llm_api_key', 'pg_url', 'embedding_api_key']);

export function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

/* ====================================================================
   Restart confirmation modal + health polling.
   ==================================================================== */
async function pingHealth(timeoutMs = 1500) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch('/health', { signal: ctrl.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function waitForHealthRecovery(maxSeconds = 30, intervalMs = 1000) {
  const deadline = Date.now() + maxSeconds * 1000;
  while (Date.now() < deadline) {
    if (await pingHealth()) return true;
    await new Promise(r => setTimeout(r, intervalMs));
  }
  return false;
}

export function offerRestart({ onRestarted } = {}) {
  const overlay = document.getElementById('modal-overlay');
  if (!overlay) {
    error(t('config.modal_overlay_missing'));
    return;
  }
  overlay.classList.remove('hidden');
  overlay.innerHTML = `
    <div class="modal" style="max-width:420px">
      <h3 class="modal-title">${t('settings.restart.title')}</h3>
      <p style="font-size:13px;color:var(--text-secondary);line-height:1.6;margin:0 0 8px;">
        ${t('settings.restart.body')}
      </p>
      <p style="font-size:12px;color:var(--text-secondary);line-height:1.5;margin:0;">
        ${t('settings.restart.downtime')}
      </p>
      <div class="modal-actions">
        <button class="btn" id="restart-cancel">${t('settings.restart.later')}</button>
        <button class="btn btn-primary" id="restart-now">${t('settings.restart.now')}</button>
      </div>
    </div>
  `;
  const close = () => { overlay.classList.add('hidden'); overlay.innerHTML = ''; };
  overlay.querySelector('#restart-cancel').onclick = close;
  overlay.querySelector('#restart-now').onclick = async () => {
    const btn = overlay.querySelector('#restart-now');
    btn.disabled = true;
    btn.textContent = t('settings.restart.restarting');
    try {
      await api.restartService();
    } catch (e) {
      error(t('settings.restart.request_failed') + ': ' + e.message);
      close();
      return;
    }
    info(t('settings.restart.issued'));
    const ok = await waitForHealthRecovery(30);
    close();
    if (ok) {
      success(t('settings.restart.ok'));
      if (typeof onRestarted === 'function') {
        try { await onRestarted(); } catch { /* ignore */ }
      }
    } else {
      error(t('settings.restart.timeout'));
    }
  };
}

/* ====================================================================
   Generic config group → a card of editable key/value rows.
   `group` = { titleKey|title, icon, note?, keys[], hints? }
   ==================================================================== */
export function buildGenericSection(group, config) {
  const section = document.createElement('div');
  section.className = 'card mb-4';
  section.innerHTML = `
    <div class="flex-between mb-4">
      <h3 style="font-size:14px;font-weight:600;">
        ${group.icon ? `<span style="margin-right:6px">${group.icon}</span>` : ''}${group.titleKey ? t(group.titleKey) : group.title}
      </h3>
    </div>
    ${group.note ? `<div style="background:var(--bg-tertiary);border-radius:var(--radius-sm);padding:12px 16px;margin-bottom:16px;font-size:13px;color:var(--text-secondary);line-height:1.6;">${group.note}</div>` : ''}
    <div class="settings-fields"></div>
  `;

  const fields = section.querySelector('.settings-fields');
  for (const key of group.keys) {
    const value = config[key];
    const restart = RESTART_KEYS.has(key);
    const hint = group.hints && group.hints[key];
    const row = document.createElement('div');
    row.className = 'setting-row';
    row.innerHTML = `
      <div class="setting-label">
        <div class="setting-key-row">
          <span class="setting-key">${key}</span>
          ${restart ? `<span class="tag tag-yellow" style="font-size:10px">${t('settings.restart_required')}</span>` : ''}
        </div>
        ${hint ? `<span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">${hint}</span>` : ''}
      </div>
      <div class="setting-input-wrap">
        ${renderInput(key, value)}
        <button class="btn btn-sm setting-save hidden" data-key="${key}">${t('common.save')}</button>
      </div>
    `;
    fields.appendChild(row);

    const input = row.querySelector('input, select');
    const saveBtn = row.querySelector('.setting-save');

    if (input) {
      const original = input.type === 'checkbox' ? input.checked : input.value;
      const onchange = () => {
        const current = input.type === 'checkbox' ? input.checked : input.value;
        saveBtn.classList.toggle('hidden', String(current) === String(original));
      };
      input.addEventListener('input', onchange);
      input.addEventListener('change', onchange);

      // The visible switch for a boolean row is the .toggle div; the checkbox is
      // hidden. Wire the div's click to flip the checkbox + fire change (the old
      // Settings page rendered these toggles but never made them clickable).
      if (input.type === 'checkbox') {
        const tg = input.closest('.toggle');
        if (tg) {
          tg.addEventListener('click', () => {
            input.checked = !input.checked;
            tg.classList.toggle('on', input.checked);
            input.dispatchEvent(new Event('change', { bubbles: true }));
          });
        }
      }

      saveBtn.addEventListener('click', async () => {
        const newValue = input.type === 'checkbox' ? String(input.checked) : input.value || 'null';
        try {
          const res = await api.updateConfig(key, newValue);
          saveBtn.classList.add('hidden');
          success(res.restart_required ? t('config.updated_restart', { key }) : t('config.updated', { key }));
          if (res && res.restart_required) {
            offerRestart({ onRestarted: () => window.location.reload() });
          }
        } catch (e) { error(e.message); }
      });
    }
  }

  return section;
}

export function renderInput(key, value) {
  if (typeof value === 'boolean') {
    return `<div class="toggle ${value ? 'on' : ''}" data-bool="true">
      <input type="checkbox" ${value ? 'checked' : ''} style="display:none" data-key="${key}">
    </div>`;
  }
  const type = SENSITIVE_KEYS.has(key) ? 'password' : 'text';
  const displayValue = value == null ? '' : String(value);
  if (key === 'consolidation_time') {
    return `<input class="form-input setting-input" type="time" step="60" value="${esc(displayValue)}" data-key="${key}">`;
  }
  return `<input class="form-input setting-input" type="${type}" value="${esc(displayValue)}" placeholder="null" data-key="${key}">`;
}

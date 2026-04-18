/**
 * Settings — view and edit hippocampus.json configuration.
 * LLM section has a guided setup with connection test.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error } from './toast.js';

/* --- LLM provider presets for the guided UI --- */
const LLM_PRESETS = [
  { label: 'OpenAI', model: 'openai/gpt-4o-mini', url: '', placeholder_key: 'sk-...' },
  { label: 'Anthropic (Claude)', model: 'anthropic/claude-3-haiku-20240307', url: '', placeholder_key: 'sk-ant-...' },
  { label: 'Qwen (Alibaba)', model: 'openai/qwen-plus', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', placeholder_key: 'sk-...' },
  { label: 'GLM (Zhipu)', model: 'openai/glm-4-flash', url: 'https://open.bigmodel.cn/api/paas/v4', placeholder_key: '...' },
  { label: 'DeepSeek', model: 'openai/deepseek-chat', url: 'https://api.deepseek.com/v1', placeholder_key: 'sk-...' },
  { label: 'Kimi (Moonshot)', model: 'openai/moonshot-v1-8k', url: 'https://api.moonshot.cn/v1', placeholder_key: 'sk-...' },
  { label: 'Custom / Self-hosted', model: '', url: '', placeholder_key: '' },
];

/* --- Other config groups (non-LLM) --- */
const OTHER_GROUPS = [
  { title: 'Embedding', icon: '&#128300;', keys: ['embedding_enabled', 'embedding_model', 'embedding_dim'] },
  { title: 'Server', icon: '&#128421;', keys: ['host', 'port'] },
  { title: 'Storage', icon: '&#128451;', keys: ['storage_type', 'db_path', 'pg_url', 'pg_pool_min', 'pg_pool_max'] },
  { title: 'Memory Lifecycle', icon: '&#128260;', keys: ['consolidation_interval_seconds', 'forget_interval_seconds', 'base_ttl_hours', 'decay_factor'] },
  { title: 'Retrieval Weights', icon: '&#9878;', keys: ['weight_recency', 'weight_importance', 'weight_relevance'] },
  { title: 'Other', icon: '&#9881;', keys: ['kg_path'] },
];

const RESTART_KEYS = new Set([
  'storage_type', 'db_path', 'pg_url', 'pg_pool_min', 'pg_pool_max',
  'embedding_enabled', 'embedding_model', 'embedding_dim',
  'host', 'port', 'kg_path',
]);

const SENSITIVE_KEYS = new Set(['llm_api_key', 'pg_url']);

export async function renderSettings(root) {
  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('settings.title')}</h1>
      <p class="page-subtitle">${t('settings.subtitle')}</p>
    </div>
    <div id="settings-groups">Loading...</div>
  `;

  let config;
  try {
    config = await api.getConfig();
  } catch (e) {
    root.querySelector('#settings-groups').innerHTML = `<div class="empty-state">${e.message}</div>`;
    return;
  }

  const container = root.querySelector('#settings-groups');
  container.innerHTML = '';

  /* === LLM Setup Section (special) === */
  container.appendChild(buildLLMSection(config));

  /* === Other groups (generic) === */
  for (const group of OTHER_GROUPS) {
    container.appendChild(buildGenericSection(group, config));
  }
}

/* ====================================================================
   LLM Section — guided setup with provider presets and test button
   ==================================================================== */
function buildLLMSection(config) {
  const section = document.createElement('div');
  section.className = 'card mb-4';

  const isConfigured = config.llm_model && config.llm_api_key;

  section.innerHTML = `
    <div class="flex-between mb-4">
      <h3 style="font-size:14px;font-weight:600;">
        <span style="margin-right:6px">&#129302;</span>LLM Configuration
        ${isConfigured
          ? '<span class="tag tag-green" style="font-size:10px;margin-left:8px">configured</span>'
          : '<span class="tag tag-yellow" style="font-size:10px;margin-left:8px">not configured</span>'}
      </h3>
    </div>
    ${!isConfigured ? `
    <div style="background:var(--bg-tertiary);border-radius:var(--radius-sm);padding:12px 16px;margin-bottom:16px;font-size:13px;color:var(--text-secondary);line-height:1.6;">
      LLM is required for memory consolidation (automatic classification, tag extraction, conflict resolution).
      Choose your provider below, fill in the API key, and click <strong style="color:var(--text-primary)">Test Connection</strong> to verify.
    </div>` : ''}
    <div class="form-group">
      <label class="form-label">Provider</label>
      <select class="form-select" id="llm-preset" style="max-width:320px">
        ${LLM_PRESETS.map((p, i) => `<option value="${i}">${p.label}</option>`).join('')}
      </select>
    </div>
    <div class="setting-row">
      <div class="setting-label">
        <span class="setting-key">llm_model</span>
        <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">Model ID, not URL. Format: provider/model-name</span>
      </div>
      <div class="setting-input-wrap">
        <input class="form-input setting-input" id="llm-model" type="text"
               value="${esc(config.llm_model || '')}" placeholder="openai/gpt-4o-mini">
      </div>
    </div>
    <div class="setting-row">
      <div class="setting-label">
        <span class="setting-key">llm_base_url</span>
        <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">API endpoint URL. Leave empty for official provider</span>
      </div>
      <div class="setting-input-wrap">
        <input class="form-input setting-input" id="llm-base-url" type="text"
               value="${esc(config.llm_base_url || '')}" placeholder="https://api.example.com/v1">
      </div>
    </div>
    <div class="setting-row">
      <div class="setting-label">
        <span class="setting-key">llm_api_key</span>
        <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">Secret key from your LLM provider</span>
      </div>
      <div class="setting-input-wrap">
        <input class="form-input setting-input" id="llm-api-key" type="password"
               value="${esc(config.llm_api_key || '')}" placeholder="sk-...">
        <button class="btn btn-sm" id="llm-key-eye" title="Show / hide API key" style="padding:4px 8px;font-size:16px;line-height:1;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" id="eye-icon">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
          </svg>
        </button>
      </div>
    </div>
    <div style="display:flex;gap:8px;margin-top:16px;align-items:center;">
      <button class="btn btn-primary" id="llm-test">Test Connection</button>
      <button class="btn" id="llm-save">Save</button>
      <span id="llm-status" style="font-size:13px;margin-left:8px;"></span>
    </div>
    <div id="llm-log" class="hidden" style="margin-top:12px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;font-family:var(--font-mono);font-size:12px;line-height:1.6;max-height:200px;overflow-y:auto;white-space:pre-wrap;"></div>
  `;

  const presetSelect = section.querySelector('#llm-preset');
  const modelInput = section.querySelector('#llm-model');
  const urlInput = section.querySelector('#llm-base-url');
  const keyInput = section.querySelector('#llm-api-key');
  const eyeBtn = section.querySelector('#llm-key-eye');
  const testBtn = section.querySelector('#llm-test');
  const saveBtn = section.querySelector('#llm-save');
  const statusEl = section.querySelector('#llm-status');
  const logEl = section.querySelector('#llm-log');

  /* Eye toggle — reveal / hide API key */
  let keyRevealed = false;
  eyeBtn.addEventListener('click', async () => {
    if (keyRevealed) {
      // Hide: switch back to password, restore masked value
      keyInput.type = 'password';
      keyRevealed = false;
      eyeBtn.style.color = '';
    } else {
      // Reveal: fetch real value from server
      try {
        const res = await api.revealConfigValue('llm_api_key');
        if (res.value) {
          keyInput.type = 'text';
          keyInput.value = res.value;
          keyRevealed = true;
          eyeBtn.style.color = 'var(--accent)';
        } else {
          keyInput.type = 'text';
          keyInput.placeholder = '(not set)';
          keyRevealed = true;
          eyeBtn.style.color = 'var(--accent)';
        }
      } catch (e) {
        error('Failed to reveal key: ' + e.message);
      }
    }
  });

  /* Auto-select preset matching current config */
  const currentModel = config.llm_model || '';
  const currentUrl = config.llm_base_url || '';
  let matchIdx = LLM_PRESETS.length - 1; // default to "Custom"
  for (let i = 0; i < LLM_PRESETS.length - 1; i++) {
    if (currentModel === LLM_PRESETS[i].model) { matchIdx = i; break; }
  }
  presetSelect.value = matchIdx;

  /* Preset change fills fields */
  presetSelect.addEventListener('change', () => {
    const p = LLM_PRESETS[presetSelect.value];
    if (p.model) modelInput.value = p.model;
    if (p.url !== undefined) urlInput.value = p.url;
    keyInput.placeholder = p.placeholder_key || 'Your API key';
  });

  /* Test button */
  testBtn.addEventListener('click', async () => {
    const model = modelInput.value.trim();
    const base_url = urlInput.value.trim() || null;
    const api_key = keyInput.value.trim() || null;

    if (!model) { error('Model is required'); return; }
    if (model.startsWith('http://') || model.startsWith('https://')) {
      error('Model field should be a model ID (e.g. openai/gpt-4o-mini), not a URL. Put the URL in llm_base_url.');
      return;
    }
    if (!api_key) { error('API key is required'); return; }

    statusEl.innerHTML = '<span style="color:var(--accent)">Testing...</span>';
    logEl.classList.remove('hidden');
    logEl.textContent = `Testing connection...\nModel: ${model}\nBase URL: ${base_url || '(default)'}\n`;

    try {
      const res = await api.testLLM(model, base_url, api_key);
      if (res.success) {
        statusEl.innerHTML = '<span style="color:var(--accent-green)">&#10003; Connection successful</span>';
        logEl.textContent += `\n[OK] Model responded: "${res.response}"\nActual model: ${res.model}`;
        logEl.style.borderColor = 'var(--accent-green)';
      } else {
        statusEl.innerHTML = '<span style="color:var(--accent-red)">&#10007; Connection failed</span>';
        logEl.textContent += `\n[ERROR] ${res.error}`;
        logEl.style.borderColor = 'var(--accent-red)';
      }
    } catch (e) {
      statusEl.innerHTML = '<span style="color:var(--accent-red)">&#10007; Request failed</span>';
      logEl.textContent += `\n[ERROR] ${e.message}`;
      logEl.style.borderColor = 'var(--accent-red)';
    }
  });

  /* Save button */
  saveBtn.addEventListener('click', async () => {
    try {
      const model = modelInput.value.trim();
      const base_url = urlInput.value.trim();
      const api_key = keyInput.value.trim();

      if (model) await api.updateConfig('llm_model', model);
      await api.updateConfig('llm_base_url', base_url || 'null');
      if (api_key) await api.updateConfig('llm_api_key', api_key);
      success('LLM configuration saved');
    } catch (e) {
      error(e.message);
    }
  });

  return section;
}

/* ====================================================================
   Generic config group builder (for non-LLM sections)
   ==================================================================== */
function buildGenericSection(group, config) {
  const section = document.createElement('div');
  section.className = 'card mb-4';
  section.innerHTML = `
    <div class="flex-between mb-4">
      <h3 style="font-size:14px;font-weight:600;">
        <span style="margin-right:6px">${group.icon}</span>${group.title}
      </h3>
    </div>
    <div class="settings-fields"></div>
  `;

  const fields = section.querySelector('.settings-fields');
  for (const key of group.keys) {
    const value = config[key];
    const restart = RESTART_KEYS.has(key);
    const row = document.createElement('div');
    row.className = 'setting-row';
    row.innerHTML = `
      <div class="setting-label">
        <span class="setting-key">${key}</span>
        ${restart ? '<span class="tag tag-yellow" style="font-size:10px">restart required</span>' : ''}
      </div>
      <div class="setting-input-wrap">
        ${renderInput(key, value)}
        <button class="btn btn-sm setting-save hidden" data-key="${key}">Save</button>
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

      saveBtn.addEventListener('click', async () => {
        const newValue = input.type === 'checkbox' ? String(input.checked) : input.value || 'null';
        try {
          const res = await api.updateConfig(key, newValue);
          saveBtn.classList.add('hidden');
          success(`${key} updated${res.restart_required ? ' (restart to apply)' : ''}`);
        } catch (e) { error(e.message); }
      });
    }
  }

  return section;
}

/* ====================================================================
   Helpers
   ==================================================================== */
function renderInput(key, value) {
  if (typeof value === 'boolean') {
    return `<div class="toggle ${value ? 'on' : ''}" data-bool="true">
      <input type="checkbox" ${value ? 'checked' : ''} style="display:none" data-key="${key}">
    </div>`;
  }
  const type = SENSITIVE_KEYS.has(key) ? 'password' : 'text';
  const displayValue = value === null ? '' : String(value);
  return `<input class="form-input setting-input" type="${type}" value="${esc(displayValue)}" placeholder="null" data-key="${key}">`;
}

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

/**
 * System — infrastructure configuration (LLM · Embedding · Storage · Server).
 *
 * The memory-lifecycle config (recall pipeline, consolidation, forgetting) now
 * lives on the Activate / Consolidate / Forget pages; this page keeps only the
 * provider/storage/server plumbing. LLM and Embedding each have a guided setup
 * with a connection test; Storage and Server are plain key/value groups.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error } from './toast.js';
import { buildGenericSection, offerRestart, esc } from './config-section.js';

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

/* --- Embedding provider presets, split by mode so Local and API are distinct --- */
const EMB_LOCAL_PRESETS = [
  { label: 'bge-large-en-v1.5 (English, 1024d)', model: 'BAAI/bge-large-en-v1.5', dim: 1024 },
  { label: 'bge-m3 (Multilingual, 1024d, 2.2GB)', model: 'BAAI/bge-m3', dim: 1024 },
  { label: 'all-MiniLM-L6-v2 (Fast, 384d, 87MB)', model: 'sentence-transformers/all-MiniLM-L6-v2', dim: 384 },
  { label: 'multilingual-e5-small (Multi, 384d, 470MB)', model: 'intfloat/multilingual-e5-small', dim: 384 },
  { label: 'Custom model…', model: '', dim: '' },
];
const EMB_API_PRESETS = [
  { label: 'OpenAI — text-embedding-3-small', model: 'openai/text-embedding-3-small', url: 'https://api.openai.com/v1', dim: 1536 },
  { label: 'Cohere — embed-multilingual-v3.0', model: 'cohere/embed-multilingual-v3.0', url: 'https://api.cohere.com/v1', dim: 1024 },
  { label: 'Qwen (DashScope)', model: 'openai/text-embedding-v3', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', dim: 1024 },
  { label: 'Custom / Self-hosted', model: '', url: '', dim: '' },
];

const EMB_HTTP_DEFAULTS = {
  method: 'POST',
  url: 'https://api.example.com/v1/embeddings',
  headers: '{\n  "Authorization": "Bearer YOUR_KEY",\n  "Content-Type": "application/json"\n}',
  body: '{\n  "model": "your-embedding-model",\n  "input": {{input}}\n}',
  response_path: 'data.*.embedding',
};

const GROUP_STORAGE = {
  titleKey: 'settings.group.storage',
  icon: '&#128451;',
  keys: ['storage_type', 'pg_url', 'pg_pool_min', 'pg_pool_max'],
  };
const GROUP_WORKSPACE = {
  titleKey: 'settings.group.workspace',
  icon: '&#128193;',
  keys: ['home'],
};
const GROUP_SERVER = {
  titleKey: 'settings.group.server',
  icon: '&#128421;',
  keys: ['host', 'port'],
};

const TABS = [
  { id: 'llm', labelKey: 'settings.tab.llm', build: (config) => [buildLLMSection(config)] },
  { id: 'embedding', labelKey: 'settings.tab.embedding', build: (config) => [buildEmbeddingSection(config)] },
  {
    id: 'storage',
    labelKey: 'settings.tab.storage',
    build: (config) => [buildGenericSection(GROUP_STORAGE, config), buildGenericSection(GROUP_WORKSPACE, config)],
  },
  { id: 'server', labelKey: 'settings.tab.server', build: (config) => [buildGenericSection(GROUP_SERVER, config)] },
];

export async function renderSystem(root, sub) {
  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('system.title')}</h1>
      <p class="page-subtitle">${t('system.subtitle')}</p>
    </div>
    <div class="console-tabs" id="system-tabs"></div>
    <div id="system-panel">${t('common.loading')}</div>
  `;

  let config;
  try {
    config = await api.getConfig();
  } catch (e) {
    root.querySelector('#system-panel').innerHTML = `<div class="empty-state">${e.message}</div>`;
    return;
  }

  const tabBar = root.querySelector('#system-tabs');
  const panel = root.querySelector('#system-panel');

  // Deep-link (#system/embedding) wins; else the remembered tab; else the first.
  let active = sub && TABS.some((x) => x.id === sub) ? sub : localStorage.getItem('hebb-system-tab');
  if (!TABS.some((tab) => tab.id === active)) active = TABS[0].id;

  tabBar.innerHTML = TABS.map(
    (tab) => `<button class="console-tab" data-tab="${tab.id}">${t(tab.labelKey)}</button>`
  ).join('');

  function showTab(id) {
    active = id;
    localStorage.setItem('hebb-system-tab', id);
    if (location.hash !== `#system/${id}`) history.replaceState(null, '', `#system/${id}`);
    tabBar.querySelectorAll('.console-tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === id));
    panel.innerHTML = '';
    const tab = TABS.find((x) => x.id === id) || TABS[0];
    for (const section of tab.build(config)) panel.appendChild(section);
  }

  tabBar.querySelectorAll('.console-tab').forEach((btn) => {
    btn.addEventListener('click', () => showTab(btn.dataset.tab));
  });

  showTab(active);
}

/* ====================================================================
   LLM Section — guided setup with provider presets and test button
   ==================================================================== */
function buildLLMSection(config) {
  const section = document.createElement('div');
  section.className = 'card mb-4';

  const isConfigured = Boolean(config.llm_model);

  section.innerHTML = `
    <div class="flex-between mb-4">
      <h3 style="font-size:14px;font-weight:600;">
        <span style="margin-right:6px">&#129302;</span>${t('settings.llm_title')}
        ${isConfigured
          ? `<span class="tag tag-green" style="font-size:10px;margin-left:8px">${t('settings.configured')}</span>`
          : `<span class="tag tag-yellow" style="font-size:10px;margin-left:8px">${t('settings.not_configured')}</span>`}
      </h3>
    </div>
    ${!isConfigured ? `
    <div style="background:var(--bg-tertiary);border-radius:var(--radius-sm);padding:12px 16px;margin-bottom:16px;font-size:13px;color:var(--text-secondary);line-height:1.6;">
      ${t('settings.llm_guide')}
    </div>` : ''}
    <div class="form-group">
      <label class="form-label">${t('settings.provider')}</label>
      <select class="form-select" id="llm-preset" style="max-width:320px">
        ${LLM_PRESETS.map((p, i) => `<option value="${i}">${p.label}</option>`).join('')}
      </select>
    </div>
    <div class="setting-row">
      <div class="setting-label">
        <span class="setting-key">llm_model</span>
        <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">${t('system.llm.hint_model')}</span>
      </div>
      <div class="setting-input-wrap">
        <input class="form-input setting-input" id="llm-model" type="text"
               value="${esc(config.llm_model || '')}" placeholder="openai/gpt-4o-mini">
      </div>
    </div>
    <div class="setting-row">
      <div class="setting-label">
        <span class="setting-key">llm_base_url</span>
        <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">${t('system.llm.hint_base_url')}</span>
      </div>
      <div class="setting-input-wrap">
        <input class="form-input setting-input" id="llm-base-url" type="text"
               value="${esc(config.llm_base_url || '')}" placeholder="https://api.example.com/v1">
      </div>
    </div>
    <div class="setting-row">
      <div class="setting-label">
        <span class="setting-key">llm_api_key</span>
        <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">${t('system.llm.hint_api_key')}</span>
      </div>
      <div class="setting-input-wrap">
        <input class="form-input setting-input" id="llm-api-key" type="password"
               value="${esc(config.llm_api_key || '')}" placeholder="sk-...">
        <button class="btn btn-sm" id="llm-key-eye" title="${t('system.tooltip.show_hide_key')}" style="padding:4px 8px;font-size:16px;line-height:1;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" id="eye-icon">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
          </svg>
        </button>
      </div>
    </div>
    <div style="display:flex;gap:8px;margin-top:16px;align-items:center;">
      <button class="btn btn-primary" id="llm-test">${t('settings.test')}</button>
      <button class="btn" id="llm-save">${t('common.save')}</button>
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

  let keyRevealed = false;
  eyeBtn.addEventListener('click', async () => {
    if (keyRevealed) {
      keyInput.type = 'password';
      keyRevealed = false;
      eyeBtn.style.color = '';
    } else {
      try {
        const res = await api.revealConfigValue('llm_api_key');
        if (res.value) {
          keyInput.type = 'text';
          keyInput.value = res.value;
          keyRevealed = true;
          eyeBtn.style.color = 'var(--accent)';
        } else {
          keyInput.type = 'text';
          keyInput.placeholder = t('system.placeholder.not_set');
          keyRevealed = true;
          eyeBtn.style.color = 'var(--accent)';
        }
      } catch (e) {
        error(t('system.toast.reveal_key_failed') + e.message);
      }
    }
  });

  const currentModel = config.llm_model || '';
  let matchIdx = LLM_PRESETS.length - 1;
  for (let i = 0; i < LLM_PRESETS.length - 1; i++) {
    if (currentModel === LLM_PRESETS[i].model) { matchIdx = i; break; }
  }
  presetSelect.value = matchIdx;

  presetSelect.addEventListener('change', () => {
    const p = LLM_PRESETS[presetSelect.value];
    if (p.model) modelInput.value = p.model;
    if (p.url !== undefined) urlInput.value = p.url;
    keyInput.placeholder = p.placeholder_key || t('system.llm.placeholder_api_key');
  });

  testBtn.addEventListener('click', async () => {
    const model = modelInput.value.trim();
    const base_url = urlInput.value.trim() || null;
    const api_key = keyInput.value.trim() || null;

    if (!model) { error(t('system.toast.model_required')); return; }
    if (model.startsWith('http://') || model.startsWith('https://')) {
      error(t('system.toast.model_not_url'));
      return;
    }
    if (!api_key) { error(t('system.toast.api_key_required')); return; }

    statusEl.innerHTML = `<span style="color:var(--accent)">${t('settings.testing')}</span>`;
    logEl.classList.remove('hidden');
    logEl.textContent = `${t('system.log.testing_connection')}\n${t('system.log.model')}: ${model}\n${t('system.log.base_url')}: ${base_url || t('system.log.default')}\n`;

    try {
      const res = await api.testLLM(model, base_url, api_key);
      if (res.success) {
        statusEl.innerHTML = `<span style="color:var(--accent-green)">&#10003; ${t('settings.success')}</span>`;
        logEl.textContent += `\n[OK] ${t('system.log.model_responded')}: "${res.response}"\n${t('system.log.actual_model')}: ${res.model}`;
        logEl.style.borderColor = 'var(--accent-green)';
      } else {
        statusEl.innerHTML = `<span style="color:var(--accent-red)">&#10007; ${t('settings.failed')}</span>`;
        logEl.textContent += `\n[ERROR] ${res.error}`;
        logEl.style.borderColor = 'var(--accent-red)';
      }
    } catch (e) {
      statusEl.innerHTML = `<span style="color:var(--accent-red)">&#10007; ${t('settings.failed')}</span>`;
      logEl.textContent += `\n[ERROR] ${e.message}`;
      logEl.style.borderColor = 'var(--accent-red)';
    }
  });

  saveBtn.addEventListener('click', async () => {
    try {
      const model = modelInput.value.trim();
      const base_url = urlInput.value.trim();
      const api_key = keyInput.value.trim();

      if (model) await api.updateConfig('llm_model', model);
      await api.updateConfig('llm_base_url', base_url || 'null');
      if (api_key) await api.updateConfig('llm_api_key', api_key);
      success(t('system.toast.llm_saved'));
    } catch (e) {
      error(e.message);
    }
  });

  return section;
}

/* ====================================================================
   Embedding Section — Local vs API, with a Custom HTTP (JSON) sub-mode
   ==================================================================== */
function buildEmbeddingSection(config) {
  const section = document.createElement('div');
  section.className = 'card mb-4';

  const isEnabled = config.embedding_enabled !== false;
  const provider = config.embedding_provider === 'api' ? 'api' : 'local';
  const apiMode = config.embedding_api_mode === 'custom' ? 'custom' : 'litellm';

  const localModelInit = provider === 'local' ? (config.embedding_model || '') : '';
  const apiModelInit = provider === 'api' && apiMode === 'litellm' ? (config.embedding_model || '') : '';

  const httpMethod = config.embedding_http_method || EMB_HTTP_DEFAULTS.method;
  const httpUrl = config.embedding_http_url || '';
  const httpHeaders = config.embedding_http_headers || EMB_HTTP_DEFAULTS.headers;
  const httpBody = config.embedding_http_body || EMB_HTTP_DEFAULTS.body;
  const httpRespPath = config.embedding_http_response_path || EMB_HTTP_DEFAULTS.response_path;
  const methods = ['POST', 'GET', 'PUT', 'PATCH'];

  section.innerHTML = `
    <div class="flex-between mb-4">
      <h3 style="font-size:14px;font-weight:600;">
        <span style="margin-right:6px">&#128300;</span>${t('settings.embedding_title')}
        <span id="emb-status-badge" style="font-size:10px;margin-left:8px"></span>
      </h3>
    </div>
    <div style="background:var(--bg-tertiary);border-radius:var(--radius-sm);padding:12px 16px;margin-bottom:16px;font-size:13px;color:var(--text-secondary);line-height:1.6;">
      ${t('settings.emb.guide')}
    </div>
    <div class="setting-row">
      <div class="setting-label">
        <span class="setting-key">embedding_enabled</span>
      </div>
      <div class="setting-input-wrap">
        <div class="toggle ${isEnabled ? 'on' : ''}" id="emb-enabled-toggle">
          <input type="checkbox" ${isEnabled ? 'checked' : ''} style="display:none">
        </div>
      </div>
    </div>
    <div id="emb-fields" ${!isEnabled ? 'style="opacity:0.5;pointer-events:none"' : ''}>
      <div class="form-group">
        <label class="form-label">${t('settings.provider')}</label>
        <div class="seg" id="emb-provider-seg">
          <button type="button" class="seg-btn" data-provider="local">${t('system.emb.provider_local')}</button>
          <button type="button" class="seg-btn" data-provider="api">${t('system.emb.provider_api')}</button>
        </div>
      </div>

      <div id="emb-local-panel">
        <div class="form-group">
          <label class="form-label">${t('system.emb.label_preset')}</label>
          <select class="form-select" id="emb-local-preset" style="max-width:480px">
            ${EMB_LOCAL_PRESETS.map((p, i) => `<option value="${i}">${p.label}</option>`).join('')}
          </select>
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-key">embedding_model</span>
            <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">${t('system.emb.hint_local_model')}</span>
          </div>
          <div class="setting-input-wrap">
            <input class="form-input setting-input" id="emb-local-model" type="text"
                   value="${esc(localModelInit)}" placeholder="BAAI/bge-large-en-v1.5">
          </div>
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-key">hf_endpoint</span>
            <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">${t('system.emb.hint_hf_endpoint')}</span>
          </div>
          <div class="setting-input-wrap">
            <input class="form-input setting-input" id="emb-hf-endpoint" type="text"
                   value="${esc(config.hf_endpoint || '')}" placeholder="https://hf-mirror.com">
          </div>
        </div>
      </div>

      <div id="emb-api-panel">
        <div class="form-group">
          <label class="form-label">${t('system.emb.label_api_mode')}</label>
          <div class="seg" id="emb-apimode-seg">
            <button type="button" class="seg-btn" data-mode="litellm">${t('system.emb.mode_standard')}</button>
            <button type="button" class="seg-btn" data-mode="custom">${t('system.emb.mode_custom_http')}</button>
          </div>
        </div>

        <div id="emb-api-standard">
          <div class="form-group">
            <label class="form-label">${t('system.emb.label_preset')}</label>
            <select class="form-select" id="emb-api-preset" style="max-width:480px">
              ${EMB_API_PRESETS.map((p, i) => `<option value="${i}">${p.label}</option>`).join('')}
            </select>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="setting-key">embedding_model</span>
              <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">${t('system.emb.hint_api_model')}</span>
            </div>
            <div class="setting-input-wrap">
              <input class="form-input setting-input" id="emb-api-model" type="text"
                     value="${esc(apiModelInit)}" placeholder="openai/text-embedding-3-small">
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="setting-key">embedding_base_url</span>
              <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">${t('system.emb.hint_base_url')}</span>
            </div>
            <div class="setting-input-wrap">
              <input class="form-input setting-input" id="emb-base-url" type="text"
                     value="${esc(config.embedding_base_url || '')}" placeholder="https://api.openai.com/v1">
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="setting-key">embedding_api_key</span>
              <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">${t('system.emb.hint_api_key')}</span>
            </div>
            <div class="setting-input-wrap">
              <input class="form-input setting-input" id="emb-api-key" type="password"
                     value="${esc(config.embedding_api_key || '')}" placeholder="sk-...">
              <button class="btn btn-sm" id="emb-key-eye" title="${t('system.tooltip.show_hide')}" style="padding:4px 8px;font-size:16px;line-height:1;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <div id="emb-api-custom">
          <div style="background:var(--bg-tertiary);border-radius:var(--radius-sm);padding:12px 16px;margin-bottom:16px;font-size:12.5px;color:var(--text-secondary);line-height:1.6;">
            ${t('settings.emb.custom_help')}
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="setting-key">embedding_http_method</span>
            </div>
            <div class="setting-input-wrap">
              <select class="form-select setting-input" id="emb-http-method" style="max-width:140px">
                ${methods.map((m) => `<option value="${m}" ${m === httpMethod ? 'selected' : ''}>${m}</option>`).join('')}
              </select>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="setting-key">embedding_http_url</span>
            </div>
            <div class="setting-input-wrap">
              <input class="form-input setting-input" id="emb-http-url" type="text"
                     value="${esc(httpUrl)}" placeholder="${esc(EMB_HTTP_DEFAULTS.url)}">
            </div>
          </div>
          <div class="form-group" style="margin-top:12px">
            <label class="form-label" style="display:flex;align-items:center;gap:8px;">
              <span class="setting-key">embedding_http_headers</span>
              <button class="btn btn-sm" id="emb-http-headers-eye" title="${t('system.tooltip.reveal_headers')}" style="padding:2px 6px;font-size:14px;line-height:1;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
              </button>
            </label>
            <textarea class="form-textarea" id="emb-http-headers" spellcheck="false"
                      style="font-family:var(--font-mono);font-size:12.5px" placeholder='{"Authorization": "Bearer ..."}'>${esc(httpHeaders)}</textarea>
          </div>
          <div class="form-group">
            <label class="form-label"><span class="setting-key">embedding_http_body</span> &nbsp;<span class="text-muted text-sm">${t('system.emb.hint_http_body')}</span></label>
            <textarea class="form-textarea" id="emb-http-body" spellcheck="false"
                      style="font-family:var(--font-mono);font-size:12.5px;min-height:120px">${esc(httpBody)}</textarea>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="setting-key">embedding_http_response_path</span>
              <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">${t('system.emb.hint_response_path')}</span>
            </div>
            <div class="setting-input-wrap">
              <input class="form-input setting-input" id="emb-http-response-path" type="text"
                     value="${esc(httpRespPath)}" placeholder="data.*.embedding">
            </div>
          </div>
        </div>
      </div>

      <div style="display:flex;gap:8px;margin-top:16px;align-items:center;">
        <button class="btn btn-primary" id="emb-test">${t('system.emb.test_button')}</button>
        <button class="btn" id="emb-save">${t('common.save')}</button>
        <span id="emb-status" style="font-size:13px;margin-left:8px;"></span>
      </div>
      <div id="emb-progress" class="hidden" style="margin-top:12px;">
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--text-secondary);margin-bottom:4px;">
          <span id="emb-progress-label">${t('system.emb.progress.downloading')}</span>
          <span id="emb-progress-pct" style="font-family:var(--font-mono);"></span>
        </div>
        <div style="background:var(--bg-tertiary);border:1px solid var(--border);border-radius:var(--radius-sm);height:8px;overflow:hidden;">
          <div id="emb-progress-fill" style="background:var(--accent);height:100%;width:0;transition:width 200ms ease;"></div>
        </div>
        <div id="emb-progress-detail" style="font-size:11px;color:var(--text-secondary);margin-top:4px;font-family:var(--font-mono);min-height:14px;"></div>
      </div>
      <div id="emb-log" class="hidden" style="margin-top:12px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;font-family:var(--font-mono);font-size:12px;line-height:1.6;max-height:200px;overflow-y:auto;white-space:pre-wrap;"></div>
    </div>
  `;

  const enabledToggle = section.querySelector('#emb-enabled-toggle');
  const fieldsDiv = section.querySelector('#emb-fields');
  const providerSeg = section.querySelector('#emb-provider-seg');
  const apiModeSeg = section.querySelector('#emb-apimode-seg');
  const localPanel = section.querySelector('#emb-local-panel');
  const apiPanel = section.querySelector('#emb-api-panel');
  const standardPanel = section.querySelector('#emb-api-standard');
  const customPanel = section.querySelector('#emb-api-custom');

  const localPresetSelect = section.querySelector('#emb-local-preset');
  const localModelInput = section.querySelector('#emb-local-model');
  const hfEndpointInput = section.querySelector('#emb-hf-endpoint');
  const apiPresetSelect = section.querySelector('#emb-api-preset');
  const apiModelInput = section.querySelector('#emb-api-model');
  const baseUrlInput = section.querySelector('#emb-base-url');
  const apiKeyInput = section.querySelector('#emb-api-key');
  const keyEyeBtn = section.querySelector('#emb-key-eye');

  const methodSelect = section.querySelector('#emb-http-method');
  const httpUrlInput = section.querySelector('#emb-http-url');
  const httpHeadersInput = section.querySelector('#emb-http-headers');
  const httpHeadersEye = section.querySelector('#emb-http-headers-eye');
  const httpBodyInput = section.querySelector('#emb-http-body');
  const responsePathInput = section.querySelector('#emb-http-response-path');

  const testBtn = section.querySelector('#emb-test');
  const saveBtn = section.querySelector('#emb-save');
  const statusEl = section.querySelector('#emb-status');
  const logEl = section.querySelector('#emb-log');
  const progressEl = section.querySelector('#emb-progress');
  const progressFillEl = section.querySelector('#emb-progress-fill');
  const progressPctEl = section.querySelector('#emb-progress-pct');
  const progressLabelEl = section.querySelector('#emb-progress-label');
  const progressDetailEl = section.querySelector('#emb-progress-detail');

  let currentProvider = provider;
  let currentApiMode = apiMode;

  function fmtBytes(n) {
    if (!n) return '0 B';
    const u = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
  }

  function renderProgress(task) {
    progressEl.classList.remove('hidden');
    const total = task.bytes_total || 0;
    const done = task.bytes_done || 0;
    const pct = total > 0 ? Math.min(100, (done / total) * 100) : 0;
    progressFillEl.style.width = pct + '%';
    if (task.status === 'downloading') {
      progressLabelEl.textContent = t('system.emb.progress.downloading');
      progressPctEl.textContent = total > 0 ? `${pct.toFixed(1)}%` : '';
      progressDetailEl.textContent = total > 0
        ? `${fmtBytes(done)} / ${fmtBytes(total)}${task.current_file ? ' · ' + task.current_file : ''}`
        : (task.current_file || t('system.emb.progress.resolving'));
    } else if (task.status === 'verifying') {
      progressLabelEl.textContent = t('system.emb.progress.verifying');
      progressPctEl.textContent = '';
      progressFillEl.style.width = '100%';
      progressDetailEl.textContent = t('system.emb.progress.verifying_detail');
    } else if (task.status === 'done') {
      progressLabelEl.textContent = t('system.emb.progress.ready');
      progressPctEl.textContent = '';
      progressFillEl.style.background = 'var(--accent-green)';
      progressFillEl.style.width = '100%';
      progressDetailEl.textContent = `dimension=${task.dimension}`;
    } else if (task.status === 'failed') {
      progressLabelEl.textContent = t('system.emb.progress.failed');
      progressFillEl.style.background = 'var(--accent-red)';
      progressDetailEl.textContent = task.error || '';
    }
  }

  function resetProgress() {
    progressEl.classList.add('hidden');
    progressFillEl.style.background = 'var(--accent)';
    progressFillEl.style.width = '0';
    progressPctEl.textContent = '';
    progressDetailEl.textContent = '';
  }

  async function pollDownload(taskId) {
    while (true) {
      let task;
      try {
        task = await api.getTestEmbeddingStatus(taskId);
      } catch (e) {
        throw new Error(t('system.emb.poll_lost_connection') + e.message);
      }
      renderProgress(task);
      if (task.status === 'done' || task.status === 'failed') return task;
      await new Promise(r => setTimeout(r, 500));
    }
  }

  enabledToggle.addEventListener('click', () => {
    const cb = enabledToggle.querySelector('input');
    cb.checked = !cb.checked;
    enabledToggle.classList.toggle('on', cb.checked);
    fieldsDiv.style.opacity = cb.checked ? '' : '0.5';
    fieldsDiv.style.pointerEvents = cb.checked ? '' : 'none';
  });

  function setProvider(p) {
    currentProvider = p;
    providerSeg.querySelectorAll('.seg-btn').forEach(b => b.classList.toggle('active', b.dataset.provider === p));
    localPanel.style.display = p === 'local' ? '' : 'none';
    apiPanel.style.display = p === 'api' ? '' : 'none';
  }
  function setApiMode(m) {
    currentApiMode = m;
    apiModeSeg.querySelectorAll('.seg-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === m));
    standardPanel.style.display = m === 'litellm' ? '' : 'none';
    customPanel.style.display = m === 'custom' ? '' : 'none';
  }
  providerSeg.querySelectorAll('.seg-btn').forEach(b => b.addEventListener('click', () => setProvider(b.dataset.provider)));
  apiModeSeg.querySelectorAll('.seg-btn').forEach(b => b.addEventListener('click', () => setApiMode(b.dataset.mode)));
  setProvider(currentProvider);
  setApiMode(currentApiMode);

  let localMatch = EMB_LOCAL_PRESETS.length - 1;
  for (let i = 0; i < EMB_LOCAL_PRESETS.length - 1; i++) {
    if (localModelInit === EMB_LOCAL_PRESETS[i].model) { localMatch = i; break; }
  }
  localPresetSelect.value = localMatch;
  localPresetSelect.addEventListener('change', () => {
    const p = EMB_LOCAL_PRESETS[localPresetSelect.value];
    if (p.model) localModelInput.value = p.model;
  });

  let apiMatch = EMB_API_PRESETS.length - 1;
  for (let i = 0; i < EMB_API_PRESETS.length - 1; i++) {
    if (apiModelInit === EMB_API_PRESETS[i].model) { apiMatch = i; break; }
  }
  apiPresetSelect.value = apiMatch;
  apiPresetSelect.addEventListener('change', () => {
    const p = EMB_API_PRESETS[apiPresetSelect.value];
    if (p.model) apiModelInput.value = p.model;
    if (p.url !== undefined) baseUrlInput.value = p.url;
  });

  let keyRevealed = false;
  keyEyeBtn.addEventListener('click', async () => {
    if (keyRevealed) {
      apiKeyInput.type = 'password';
      keyRevealed = false;
      keyEyeBtn.style.color = '';
    } else {
      try {
        const res = await api.revealConfigValue('embedding_api_key');
        apiKeyInput.type = 'text';
        apiKeyInput.value = res.value || '';
        apiKeyInput.placeholder = res.value ? '' : t('system.placeholder.not_set');
        keyRevealed = true;
        keyEyeBtn.style.color = 'var(--accent)';
      } catch (e) {
        error(t('system.toast.reveal_key_failed') + e.message);
      }
    }
  });

  httpHeadersEye.addEventListener('click', async () => {
    try {
      const res = await api.revealConfigValue('embedding_http_headers');
      if (res.value) httpHeadersInput.value = res.value;
      httpHeadersEye.style.color = 'var(--accent)';
    } catch (e) {
      error(t('system.toast.reveal_headers_failed') + e.message);
    }
  });

  async function runTest(params, logHeader) {
    resetProgress();
    statusEl.innerHTML = `<span style="color:var(--accent)">${t('settings.testing')}</span>`;
    logEl.classList.remove('hidden');
    logEl.style.borderColor = 'var(--border)';
    logEl.textContent = logHeader;
    testBtn.disabled = true;
    try {
      const res = await api.testEmbedding(params);
      if (res.async && res.task_id) {
        renderProgress({ status: 'downloading', bytes_done: 0, bytes_total: 0, current_file: '' });
        logEl.textContent += `\n[INFO] ${t('system.emb.log.download_started')} (task_id=${res.task_id}).\n`;
        let final;
        try {
          final = await pollDownload(res.task_id);
        } catch (e) {
          statusEl.innerHTML = `<span style="color:var(--accent-red)">&#10007; ${t('system.emb.status.polling_failed')}</span>`;
          logEl.textContent += `\n[ERROR] ${e.message}`;
          logEl.style.borderColor = 'var(--accent-red)';
          return;
        }
        if (final.status === 'done') {
          statusEl.innerHTML = `<span style="color:var(--accent-green)">&#10003; ${t('system.emb.status.ok_dimension')}=${final.dimension}</span>`;
          logEl.textContent += `\n[OK] ${t('system.emb.log.downloaded_verified')}, dimension=${final.dimension}`;
          logEl.style.borderColor = 'var(--accent-green)';
        } else {
          statusEl.innerHTML = `<span style="color:var(--accent-red)">&#10007; ${t('system.emb.status.download_failed')}</span>`;
          logEl.textContent += `\n[ERROR] ${final.error || t('system.emb.log.unknown_error')}`;
          logEl.style.borderColor = 'var(--accent-red)';
        }
      } else if (res.success) {
        statusEl.innerHTML = `<span style="color:var(--accent-green)">&#10003; ${t('system.emb.status.ok_dimension')}=${res.dimension}</span>`;
        logEl.textContent += `\n[OK] ${res.message}`;
        logEl.style.borderColor = 'var(--accent-green)';
      } else {
        statusEl.innerHTML = `<span style="color:var(--accent-red)">&#10007; ${t('settings.failed')}</span>`;
        logEl.textContent += `\n[ERROR] ${res.error}`;
        logEl.style.borderColor = 'var(--accent-red)';
      }
    } catch (e) {
      statusEl.innerHTML = `<span style="color:var(--accent-red)">&#10007; ${t('system.emb.status.request_failed')}</span>`;
      logEl.textContent += `\n[ERROR] ${e.message}`;
      logEl.style.borderColor = 'var(--accent-red)';
    } finally {
      testBtn.disabled = false;
    }
  }

  testBtn.addEventListener('click', async () => {
    if (currentProvider === 'local') {
      const model = localModelInput.value.trim();
      if (!model) { error(t('system.toast.model_required')); return; }
      await runTest({ provider: 'local', model }, `${t('system.emb.log.testing')}\n${t('system.log.provider')}: local\n${t('system.log.model')}: ${model}\n`);
    } else if (currentApiMode === 'custom') {
      const http_url = httpUrlInput.value.trim();
      const http_body = httpBodyInput.value;
      if (!http_url) { error(t('system.toast.url_required_custom')); return; }
      if (!http_body.trim()) { error(t('system.toast.body_required_custom')); return; }
      await runTest(
        {
          provider: 'api',
          api_mode: 'custom',
          http_method: methodSelect.value,
          http_url,
          http_headers: httpHeadersInput.value,
          http_body,
          http_response_path: responsePathInput.value.trim() || 'data.*.embedding',
        },
        `${t('system.emb.log.testing')}\n${t('system.log.provider')}: api (custom HTTP)\n${methodSelect.value} ${http_url}\n`
      );
    } else {
      const model = apiModelInput.value.trim();
      const base_url = baseUrlInput.value.trim() || null;
      const api_key = apiKeyInput.value.trim() || null;
      if (!model) { error(t('system.toast.model_required')); return; }
      if (!base_url) { error(t('system.toast.base_url_required_api')); return; }
      await runTest(
        { provider: 'api', api_mode: 'litellm', model, base_url, api_key },
        `${t('system.emb.log.testing')}\n${t('system.log.provider')}: api (litellm)\n${t('system.log.model')}: ${model}\n${t('system.log.base_url')}: ${base_url}\n`
      );
    }
  });

  async function refreshBadge() {
    const badge = section.querySelector('#emb-status-badge');
    try {
      const st = await api.getEmbeddingStatus();
      if (!st.enabled) {
        badge.className = 'tag tag-yellow';
        badge.textContent = t('system.badge.disabled');
      } else if (st.provider === 'api') {
        badge.className = 'tag tag-green';
        badge.textContent = st.api_mode === 'custom' ? t('system.badge.api_custom_http') : t('system.badge.api');
      } else if (st.cached) {
        badge.className = 'tag tag-green';
        badge.textContent = t('system.badge.local_cached');
      } else {
        badge.className = 'tag tag-yellow';
        badge.textContent = t('system.badge.local_not_downloaded');
      }
    } catch { /* ignore */ }
  }

  saveBtn.addEventListener('click', async () => {
    try {
      const enabled = enabledToggle.querySelector('input').checked;
      let needsRestart = false;
      const collect = (res) => { if (res && res.restart_required) needsRestart = true; };

      collect(await api.updateConfig('embedding_enabled', String(enabled)));
      collect(await api.updateConfig('embedding_provider', currentProvider));

      if (currentProvider === 'local') {
        const model = localModelInput.value.trim();
        if (model) collect(await api.updateConfig('embedding_model', model));
        collect(await api.updateConfig('hf_endpoint', hfEndpointInput.value.trim() || 'null'));
      } else {
        collect(await api.updateConfig('embedding_api_mode', currentApiMode));
        if (currentApiMode === 'custom') {
          collect(await api.updateConfig('embedding_http_method', methodSelect.value || 'POST'));
          collect(await api.updateConfig('embedding_http_url', httpUrlInput.value.trim() || 'null'));
          const headers = httpHeadersInput.value;
          if (headers && !headers.includes('****')) {
            collect(await api.updateConfig('embedding_http_headers', headers.trim() || 'null'));
          }
          collect(await api.updateConfig('embedding_http_body', httpBodyInput.value.trim() || 'null'));
          collect(await api.updateConfig('embedding_http_response_path', responsePathInput.value.trim() || 'data.*.embedding'));
        } else {
          const model = apiModelInput.value.trim();
          if (model) collect(await api.updateConfig('embedding_model', model));
          collect(await api.updateConfig('embedding_base_url', baseUrlInput.value.trim() || 'null'));
          const api_key = apiKeyInput.value.trim();
          if (api_key && !api_key.includes('****')) {
            collect(await api.updateConfig('embedding_api_key', api_key));
          }
        }
      }

      await refreshBadge();
      success(t('system.toast.emb_saved'));
      if (needsRestart) {
        offerRestart({ onRestarted: () => window.location.reload() });
      }
    } catch (e) {
      error(e.message);
    }
  });

  refreshBadge();

  return section;
}

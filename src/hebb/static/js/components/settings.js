/**
 * Settings — view and edit hebb.json configuration.
 * LLM section has a guided setup with connection test.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error, info } from './toast.js';

/* ====================================================================
   Shared: restart confirmation modal + health polling.
   Used by any settings section that writes a restart-required field.
   ==================================================================== */
async function pingHealth(timeoutMs = 1500) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch('/health', { signal: ctrl.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(t);
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
    error('Modal overlay not found in DOM');
    return;
  }
  overlay.classList.remove('hidden');
  overlay.innerHTML = `
    <div class="modal" style="max-width:420px">
      <h3 class="modal-title">Restart service to apply?</h3>
      <p style="font-size:13px;color:var(--text-secondary);line-height:1.6;margin:0 0 8px;">
        One or more fields you changed only take effect after a restart of the Hebb Mind service.
      </p>
      <p style="font-size:12px;color:var(--text-secondary);line-height:1.5;margin:0;">
        Expected downtime: a few seconds. The page will reload when the service is back.
      </p>
      <div class="modal-actions">
        <button class="btn" id="restart-cancel">Later</button>
        <button class="btn btn-primary" id="restart-now">Restart now</button>
      </div>
    </div>
  `;
  const close = () => { overlay.classList.add('hidden'); overlay.innerHTML = ''; };
  overlay.querySelector('#restart-cancel').onclick = close;
  overlay.querySelector('#restart-now').onclick = async () => {
    const btn = overlay.querySelector('#restart-now');
    btn.disabled = true;
    btn.textContent = 'Restarting…';
    try {
      await api.restartService();
    } catch (e) {
      error('Restart request failed: ' + e.message);
      close();
      return;
    }
    info('Restart issued. Waiting for service to come back…');
    const ok = await waitForHealthRecovery(30);
    close();
    if (ok) {
      success('Service restarted');
      if (typeof onRestarted === 'function') {
        try { await onRestarted(); } catch { /* ignore */ }
      }
    } else {
      error('Service did not respond within 30s. Check `hebb status` in a terminal.');
    }
  };
}

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

/* --- Embedding provider presets --- */
const EMB_PRESETS = [
  { label: 'Local — bge-large-en-v1.5 (English, 1024d)', provider: 'local', model: 'BAAI/bge-large-en-v1.5', url: '', dim: 1024 },
  { label: 'Local — bge-m3 (Multilingual, 1024d, 2.2GB)', provider: 'local', model: 'BAAI/bge-m3', url: '', dim: 1024 },
  { label: 'Local — all-MiniLM-L6-v2 (Fast, 384d, 87MB)', provider: 'local', model: 'sentence-transformers/all-MiniLM-L6-v2', url: '', dim: 384 },
  { label: 'Local — multilingual-e5-small (Multi, 384d, 470MB)', provider: 'local', model: 'intfloat/multilingual-e5-small', url: '', dim: 384 },
  { label: 'OpenAI — text-embedding-3-small', provider: 'api', model: 'openai/text-embedding-3-small', url: 'https://api.openai.com/v1', dim: 1536 },
  { label: 'Cohere — embed-multilingual-v3.0', provider: 'api', model: 'cohere/embed-multilingual-v3.0', url: 'https://api.cohere.com/v1', dim: 1024 },
  { label: 'Qwen (DashScope)', provider: 'api', model: 'openai/text-embedding-v3', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', dim: 1024 },
  { label: 'Custom / Self-hosted', provider: 'api', model: '', url: '', dim: '' },
];

/* --- Other config groups (non-LLM, non-Embedding) --- */
const OTHER_GROUPS = [
  { title: 'Server', icon: '&#128421;', keys: ['host', 'port'] },
  { title: 'Storage', icon: '&#128451;', keys: ['storage_type', 'pg_url', 'pg_pool_min', 'pg_pool_max'] },
  { title: 'Workspace', icon: '&#128193;', keys: ['home'] },
  { title: 'Memory Lifecycle', icon: '&#128260;', keys: ['consolidation_time', 'consolidation_concurrency', 'consolidation_max_tokens', 'forget_interval_seconds', 'base_ttl_hours', 'decay_factor'] },
  { title: 'Retrieval Weights', icon: '&#9878;', keys: ['weight_recency', 'weight_importance', 'weight_relevance'] },
];

const RESTART_KEYS = new Set([
  'storage_type', 'pg_url', 'pg_pool_min', 'pg_pool_max',
  'embedding_enabled', 'embedding_provider', 'embedding_model', 'embedding_dim',
  'embedding_api_key', 'embedding_base_url', 'hf_endpoint',
  'consolidation_time', 'consolidation_concurrency', 'consolidation_max_tokens',
  'forget_interval_seconds',
  'host', 'port', 'home',
]);

const SENSITIVE_KEYS = new Set(['llm_api_key', 'pg_url', 'embedding_api_key']);

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

  /* === Embedding Setup Section (special) === */
  container.appendChild(buildEmbeddingSection(config));

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
   Embedding Section — provider presets, local/API toggle, test button
   ==================================================================== */
function buildEmbeddingSection(config) {
  const section = document.createElement('div');
  section.className = 'card mb-4';

  const isEnabled = config.embedding_enabled !== false;
  const isApi = config.embedding_provider === 'api';

  section.innerHTML = `
    <div class="flex-between mb-4">
      <h3 style="font-size:14px;font-weight:600;">
        <span style="margin-right:6px">&#128300;</span>Embedding Configuration
        <span id="emb-status-badge" style="font-size:10px;margin-left:8px"></span>
      </h3>
    </div>
    <div style="background:var(--bg-tertiary);border-radius:var(--radius-sm);padding:12px 16px;margin-bottom:16px;font-size:13px;color:var(--text-secondary);line-height:1.6;">
      Embedding models convert text into vectors for semantic search. Choose a <strong style="color:var(--text-primary)">local</strong> model (downloaded on startup) or a cloud <strong style="color:var(--text-primary)">API</strong> provider.
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
        <label class="form-label">Preset</label>
        <select class="form-select" id="emb-preset" style="max-width:480px">
          ${EMB_PRESETS.map((p, i) => `<option value="${i}">${p.label}</option>`).join('')}
        </select>
      </div>
      <div class="setting-row">
        <div class="setting-label">
          <span class="setting-key">embedding_provider</span>
          <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">local = sentence-transformers, api = cloud service</span>
        </div>
        <div class="setting-input-wrap">
          <select class="form-select setting-input" id="emb-provider" style="max-width:160px">
            <option value="local" ${!isApi ? 'selected' : ''}>local</option>
            <option value="api" ${isApi ? 'selected' : ''}>api</option>
          </select>
        </div>
      </div>
      <div class="setting-row">
        <div class="setting-label">
          <span class="setting-key">embedding_model</span>
          <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">Local: HuggingFace model name &nbsp;|&nbsp; API: litellm model ID</span>
        </div>
        <div class="setting-input-wrap">
          <input class="form-input setting-input" id="emb-model" type="text"
                 value="${esc(config.embedding_model || '')}" placeholder="BAAI/bge-large-en-v1.5">
        </div>
      </div>
      <div id="emb-api-fields" ${!isApi ? 'style="display:none"' : ''}>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-key">embedding_base_url</span>
            <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">Required for API provider</span>
          </div>
          <div class="setting-input-wrap">
            <input class="form-input setting-input" id="emb-base-url" type="text"
                   value="${esc(config.embedding_base_url || '')}" placeholder="https://api.openai.com/v1">
          </div>
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-key">embedding_api_key</span>
            <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">Optional — some services don't require a key</span>
          </div>
          <div class="setting-input-wrap">
            <input class="form-input setting-input" id="emb-api-key" type="password"
                   value="${esc(config.embedding_api_key || '')}" placeholder="sk-...">
            <button class="btn btn-sm" id="emb-key-eye" title="Show / hide" style="padding:4px 8px;font-size:16px;line-height:1;">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
      <div class="setting-row">
        <div class="setting-label">
          <span class="setting-key">hf_endpoint</span>
          <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">HuggingFace mirror for faster model downloads in China</span>
        </div>
        <div class="setting-input-wrap">
          <input class="form-input setting-input" id="emb-hf-endpoint" type="text"
                 value="${esc(config.hf_endpoint || '')}" placeholder="https://hf-mirror.com">
        </div>
      </div>
      <div style="display:flex;gap:8px;margin-top:16px;align-items:center;">
        <button class="btn btn-primary" id="emb-test">Test Embedding</button>
        <button class="btn" id="emb-save">Save</button>
        <span id="emb-status" style="font-size:13px;margin-left:8px;"></span>
      </div>
      <div id="emb-progress" class="hidden" style="margin-top:12px;">
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--text-secondary);margin-bottom:4px;">
          <span id="emb-progress-label">Downloading…</span>
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
  const presetSelect = section.querySelector('#emb-preset');
  const providerSelect = section.querySelector('#emb-provider');
  const modelInput = section.querySelector('#emb-model');
  const apiFieldsDiv = section.querySelector('#emb-api-fields');
  const baseUrlInput = section.querySelector('#emb-base-url');
  const apiKeyInput = section.querySelector('#emb-api-key');
  const eyeBtn = section.querySelector('#emb-key-eye');
  const testBtn = section.querySelector('#emb-test');
  const saveBtn = section.querySelector('#emb-save');
  const statusEl = section.querySelector('#emb-status');
  const logEl = section.querySelector('#emb-log');
  const progressEl = section.querySelector('#emb-progress');
  const progressFillEl = section.querySelector('#emb-progress-fill');
  const progressPctEl = section.querySelector('#emb-progress-pct');
  const progressLabelEl = section.querySelector('#emb-progress-label');
  const progressDetailEl = section.querySelector('#emb-progress-detail');

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
      progressLabelEl.textContent = 'Downloading…';
      progressPctEl.textContent = total > 0 ? `${pct.toFixed(1)}%` : '';
      progressDetailEl.textContent = total > 0
        ? `${fmtBytes(done)} / ${fmtBytes(total)}${task.current_file ? ' · ' + task.current_file : ''}`
        : (task.current_file || 'Resolving model files…');
    } else if (task.status === 'verifying') {
      progressLabelEl.textContent = 'Verifying model…';
      progressPctEl.textContent = '';
      progressFillEl.style.width = '100%';
      progressDetailEl.textContent = 'Loading and running a sample encode';
    } else if (task.status === 'done') {
      progressLabelEl.textContent = 'Ready';
      progressPctEl.textContent = '';
      progressFillEl.style.background = 'var(--accent-green)';
      progressFillEl.style.width = '100%';
      progressDetailEl.textContent = `dimension=${task.dimension}`;
    } else if (task.status === 'failed') {
      progressLabelEl.textContent = 'Failed';
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
    // Returns the terminal task object.
    while (true) {
      let task;
      try {
        task = await api.getTestEmbeddingStatus(taskId);
      } catch (e) {
        throw new Error('Lost connection while polling download: ' + e.message);
      }
      renderProgress(task);
      if (task.status === 'done' || task.status === 'failed') return task;
      await new Promise(r => setTimeout(r, 500));
    }
  }

  /* Toggle enabled */
  enabledToggle.addEventListener('click', () => {
    const cb = enabledToggle.querySelector('input');
    cb.checked = !cb.checked;
    enabledToggle.classList.toggle('on', cb.checked);
    fieldsDiv.style.opacity = cb.checked ? '' : '0.5';
    fieldsDiv.style.pointerEvents = cb.checked ? '' : 'none';
  });

  /* Auto-select preset matching current config */
  const curModel = config.embedding_model || '';
  let matchIdx = EMB_PRESETS.length - 1;
  for (let i = 0; i < EMB_PRESETS.length - 1; i++) {
    if (curModel === EMB_PRESETS[i].model) { matchIdx = i; break; }
  }
  presetSelect.value = matchIdx;

  /* Preset change fills fields */
  presetSelect.addEventListener('change', () => {
    const p = EMB_PRESETS[presetSelect.value];
    providerSelect.value = p.provider;
    if (p.model) modelInput.value = p.model;
    if (p.url !== undefined) baseUrlInput.value = p.url;
    apiFieldsDiv.style.display = p.provider === 'api' ? '' : 'none';
  });

  /* Provider change shows/hides API fields */
  providerSelect.addEventListener('change', () => {
    apiFieldsDiv.style.display = providerSelect.value === 'api' ? '' : 'none';
  });

  /* Eye toggle for API key */
  let keyRevealed = false;
  eyeBtn.addEventListener('click', async () => {
    if (keyRevealed) {
      apiKeyInput.type = 'password';
      keyRevealed = false;
      eyeBtn.style.color = '';
    } else {
      try {
        const res = await api.revealConfigValue('embedding_api_key');
        apiKeyInput.type = 'text';
        apiKeyInput.value = res.value || '';
        apiKeyInput.placeholder = res.value ? '' : '(not set)';
        keyRevealed = true;
        eyeBtn.style.color = 'var(--accent)';
      } catch (e) {
        error('Failed to reveal key: ' + e.message);
      }
    }
  });

  /* Test button */
  testBtn.addEventListener('click', async () => {
    const provider = providerSelect.value;
    const model = modelInput.value.trim();
    const base_url = baseUrlInput.value.trim() || null;
    const api_key = apiKeyInput.value.trim() || null;

    if (!model) { error('Model is required'); return; }
    if (provider === 'api' && !base_url) { error('Base URL is required for API embedding'); return; }

    resetProgress();
    statusEl.innerHTML = '<span style="color:var(--accent)">Testing...</span>';
    logEl.classList.remove('hidden');
    logEl.style.borderColor = 'var(--border)';
    logEl.textContent = `Testing embedding...\nProvider: ${provider}\nModel: ${model}\n`;
    if (provider === 'api') {
      logEl.textContent += `Base URL: ${base_url}\n`;
    }

    testBtn.disabled = true;
    try {
      const res = await api.testEmbedding(provider, model, base_url, api_key);
      if (res.async && res.task_id) {
        // Background download: poll until terminal.
        renderProgress({ status: 'downloading', bytes_done: 0, bytes_total: 0, current_file: '' });
        logEl.textContent += `\n[INFO] First-time download started (task_id=${res.task_id}). Streaming progress…\n`;
        let final;
        try {
          final = await pollDownload(res.task_id);
        } catch (e) {
          statusEl.innerHTML = '<span style="color:var(--accent-red)">&#10007; Polling failed</span>';
          logEl.textContent += `\n[ERROR] ${e.message}`;
          logEl.style.borderColor = 'var(--accent-red)';
          return;
        }
        if (final.status === 'done') {
          statusEl.innerHTML = `<span style="color:var(--accent-green)">&#10003; OK — dimension=${final.dimension}</span>`;
          logEl.textContent += `\n[OK] Downloaded and verified, dimension=${final.dimension}`;
          logEl.style.borderColor = 'var(--accent-green)';
        } else {
          statusEl.innerHTML = '<span style="color:var(--accent-red)">&#10007; Download failed</span>';
          logEl.textContent += `\n[ERROR] ${final.error || 'unknown error'}`;
          logEl.style.borderColor = 'var(--accent-red)';
        }
      } else if (res.success) {
        statusEl.innerHTML = `<span style="color:var(--accent-green)">&#10003; OK — dimension=${res.dimension}</span>`;
        logEl.textContent += `\n[OK] ${res.message}`;
        logEl.style.borderColor = 'var(--accent-green)';
      } else {
        statusEl.innerHTML = '<span style="color:var(--accent-red)">&#10007; Failed</span>';
        logEl.textContent += `\n[ERROR] ${res.error}`;
        logEl.style.borderColor = 'var(--accent-red)';
      }
    } catch (e) {
      statusEl.innerHTML = '<span style="color:var(--accent-red)">&#10007; Request failed</span>';
      logEl.textContent += `\n[ERROR] ${e.message}`;
      logEl.style.borderColor = 'var(--accent-red)';
    } finally {
      testBtn.disabled = false;
    }
  });

  /* Refresh the cached/disabled badge from the live config. */
  async function refreshBadge() {
    const badge = section.querySelector('#emb-status-badge');
    try {
      const st = await api.getEmbeddingStatus();
      if (!st.enabled) {
        badge.className = 'tag tag-yellow';
        badge.textContent = 'disabled';
      } else if (st.provider === 'api') {
        badge.className = 'tag tag-green';
        badge.textContent = 'API';
      } else if (st.cached) {
        badge.className = 'tag tag-green';
        badge.textContent = 'local · cached';
      } else {
        badge.className = 'tag tag-yellow';
        badge.textContent = 'local · not downloaded';
      }
    } catch { /* ignore */ }
  }

  /* Save button */
  saveBtn.addEventListener('click', async () => {
    try {
      const enabled = enabledToggle.querySelector('input').checked;
      const provider = providerSelect.value;
      const model = modelInput.value.trim();
      const base_url = baseUrlInput.value.trim();
      const api_key = apiKeyInput.value.trim();
      const hf_endpoint = section.querySelector('#emb-hf-endpoint').value.trim();

      let needsRestart = false;
      const collect = (res) => { if (res && res.restart_required) needsRestart = true; };

      collect(await api.updateConfig('embedding_enabled', String(enabled)));
      collect(await api.updateConfig('embedding_provider', provider));
      if (model) collect(await api.updateConfig('embedding_model', model));
      collect(await api.updateConfig('embedding_base_url', base_url || 'null'));
      if (api_key && !api_key.includes('****')) {
        collect(await api.updateConfig('embedding_api_key', api_key));
      }
      collect(await api.updateConfig('hf_endpoint', hf_endpoint || 'null'));

      await refreshBadge();
      success('Embedding configuration saved');
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
  if (key === 'consolidation_time') {
    return `<input class="form-input setting-input" type="time" step="60" value="${esc(displayValue)}" data-key="${key}">`;
  }
  return `<input class="form-input setting-input" type="${type}" value="${esc(displayValue)}" placeholder="null" data-key="${key}">`;
}

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

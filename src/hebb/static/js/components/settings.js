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

/* Default starting template for the custom-HTTP (JSON) sub-mode. {{input}} is
   replaced with a JSON array of all texts in the batch. */
const EMB_HTTP_DEFAULTS = {
  method: 'POST',
  url: 'https://api.example.com/v1/embeddings',
  headers: '{\n  "Authorization": "Bearer YOUR_KEY",\n  "Content-Type": "application/json"\n}',
  body: '{\n  "model": "your-embedding-model",\n  "input": {{input}}\n}',
  response_path: 'data.*.embedding',
};

/* --- Config groups, organised into top-level tabs --- */
const GROUP_RECALL = {
  titleKey: 'settings.group.recall',
  icon: '&#128269;',
  keys: ['keyword_search_enabled', 'graph_search_enabled', 'lexical_boost_enabled', 'temporal_boost_enabled', 'graph_expansion_enabled', 'recall_min_score'],
  hints: {
    keyword_search_enabled: 'FTS5 / keyword path in the 3-way RRF recall',
    graph_search_enabled: 'Knowledge-graph tag-match recall path',
    lexical_boost_enabled: 'Predicate / quoted-phrase / person-name surface boost',
    temporal_boost_enabled: 'Date-proximity boost when the query names a time',
    graph_expansion_enabled: 'Expand top-k tags through the graph for related memories',
    recall_min_score: 'Score floor (0–1) for strict recall (Claude Code hook + MCP). Results below are dropped; the console Search page is unaffected. Applies immediately, no restart.',
  },
};
const GROUP_RERANK = {
  titleKey: 'settings.group.rerank',
  icon: '&#127919;',
  keys: ['rerank_enabled', 'rerank_provider', 'rerank_model', 'rerank_top_n'],
  hints: {
    rerank_enabled: 'Cross-encoder pass over the top candidates after hybrid retrieval. Scores are sigmoid-normalised to [0,1].',
    rerank_provider: "'local' = sentence-transformers CrossEncoder",
    rerank_model: 'Model name or HuggingFace repo id',
    rerank_top_n: 'Candidates to rerank before the final top_k (5–200)',
  },
};
const GROUP_WEIGHTS = {
  titleKey: 'settings.group.weights',
  icon: '&#9878;',
  note:
    'When rerank is off, results are ranked by a weighted blend of three normalised [0–1] signals — ' +
    '<strong>relevance</strong> (how well a memory matches the query), <strong>importance</strong>, and ' +
    '<strong>recency</strong>. The weights are normalised before use, so only their <em>ratio</em> matters ' +
    '(1 / 1 / 1 = equal footing; raise one to let it dominate). These are the <strong>global defaults</strong> ' +
    'applied to automatic recall; the Search page sliders override them for a single query. Takes effect ' +
    'immediately — no restart needed.',
  keys: ['weight_recency', 'weight_importance', 'weight_relevance'],
  hints: {
    weight_recency: 'How strongly recent memories are favoured',
    weight_importance: 'How strongly high-importance memories are favoured',
    weight_relevance: 'How strongly query relevance dominates the composite score',
  },
};
const GROUP_LIFECYCLE = {
  titleKey: 'settings.group.lifecycle',
  icon: '&#128260;',
  keys: ['consolidation_time', 'consolidation_concurrency', 'consolidation_max_tokens', 'consolidation_drain_empty_sources', 'forget_interval_seconds', 'base_ttl_hours', 'decay_factor'],
  hints: {
    consolidation_drain_empty_sources: 'Drop working memories the consolidator judged low-value (small talk) so the inbox empties, instead of re-checking them every run. Garbled/failed responses are always kept. Applies on the next run — no restart.',
  },
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

/* Top-level settings tabs. Each `build` returns the section cards to mount. */
const TABS = [
  { id: 'llm', labelKey: 'settings.tab.llm', build: (config) => [buildLLMSection(config)] },
  { id: 'embedding', labelKey: 'settings.tab.embedding', build: (config) => [buildEmbeddingSection(config)] },
  {
    id: 'retrieval',
    labelKey: 'settings.tab.retrieval',
    build: (config) => [
      buildGenericSection(GROUP_RECALL, config),
      buildGenericSection(GROUP_RERANK, config),
      buildGenericSection(GROUP_WEIGHTS, config),
    ],
  },
  { id: 'lifecycle', labelKey: 'settings.tab.lifecycle', build: (config) => [buildGenericSection(GROUP_LIFECYCLE, config)] },
  {
    id: 'storage',
    labelKey: 'settings.tab.storage',
    build: (config) => [buildGenericSection(GROUP_STORAGE, config), buildGenericSection(GROUP_WORKSPACE, config)],
  },
  { id: 'server', labelKey: 'settings.tab.server', build: (config) => [buildGenericSection(GROUP_SERVER, config)] },
];

const RESTART_KEYS = new Set([
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

const SENSITIVE_KEYS = new Set(['llm_api_key', 'pg_url', 'embedding_api_key']);

export async function renderSettings(root) {
  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('settings.title')}</h1>
      <p class="page-subtitle">${t('settings.subtitle')}</p>
    </div>
    <div class="settings-tabs" id="settings-tabs"></div>
    <div id="settings-panel">${t('common.loading')}</div>
  `;

  let config;
  try {
    config = await api.getConfig();
  } catch (e) {
    root.querySelector('#settings-panel').innerHTML = `<div class="empty-state">${e.message}</div>`;
    return;
  }

  const tabBar = root.querySelector('#settings-tabs');
  const panel = root.querySelector('#settings-panel');

  // Remember the last-open tab so a restart-triggered reload returns here.
  let active = localStorage.getItem('hebb-settings-tab');
  if (!TABS.some((tab) => tab.id === active)) active = TABS[0].id;

  tabBar.innerHTML = TABS.map(
    (tab) => `<button class="settings-tab" data-tab="${tab.id}">${t(tab.labelKey)}</button>`
  ).join('');

  function showTab(id) {
    active = id;
    localStorage.setItem('hebb-settings-tab', id);
    tabBar.querySelectorAll('.settings-tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === id));
    panel.innerHTML = '';
    const tab = TABS.find((x) => x.id === id) || TABS[0];
    for (const section of tab.build(config)) panel.appendChild(section);
  }

  tabBar.querySelectorAll('.settings-tab').forEach((btn) => {
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

  // The real gate for LLM usage is the model id; a key is optional for local /
  // proxy models that don't require one. Mirror that here so a keyless model
  // still shows "configured".
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
   Embedding Section — Local vs API, with a Custom HTTP (JSON) sub-mode
   ==================================================================== */
function buildEmbeddingSection(config) {
  const section = document.createElement('div');
  section.className = 'card mb-4';

  const isEnabled = config.embedding_enabled !== false;
  const provider = config.embedding_provider === 'api' ? 'api' : 'local';
  const apiMode = config.embedding_api_mode === 'custom' ? 'custom' : 'litellm';

  // Model is one backend field (embedding_model) shared by both modes; show it
  // in whichever panel is active and let the active panel write it on save.
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
      Embedding models convert text into vectors for semantic search. Run a <strong style="color:var(--text-primary)">local</strong> model (downloaded on startup) or call a cloud <strong style="color:var(--text-primary)">API</strong> service.
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
        <label class="form-label">Provider</label>
        <div class="seg" id="emb-provider-seg">
          <button type="button" class="seg-btn" data-provider="local">Local model</button>
          <button type="button" class="seg-btn" data-provider="api">API service</button>
        </div>
      </div>

      <!-- ── LOCAL ─────────────────────────────────────────────── -->
      <div id="emb-local-panel">
        <div class="form-group">
          <label class="form-label">Preset</label>
          <select class="form-select" id="emb-local-preset" style="max-width:480px">
            ${EMB_LOCAL_PRESETS.map((p, i) => `<option value="${i}">${p.label}</option>`).join('')}
          </select>
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-key">embedding_model</span>
            <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">HuggingFace model name (sentence-transformers)</span>
          </div>
          <div class="setting-input-wrap">
            <input class="form-input setting-input" id="emb-local-model" type="text"
                   value="${esc(localModelInit)}" placeholder="BAAI/bge-large-en-v1.5">
          </div>
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-key">hf_endpoint</span>
            <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">HuggingFace mirror for faster downloads in China</span>
          </div>
          <div class="setting-input-wrap">
            <input class="form-input setting-input" id="emb-hf-endpoint" type="text"
                   value="${esc(config.hf_endpoint || '')}" placeholder="https://hf-mirror.com">
          </div>
        </div>
      </div>

      <!-- ── API ───────────────────────────────────────────────── -->
      <div id="emb-api-panel">
        <div class="form-group">
          <label class="form-label">API mode</label>
          <div class="seg" id="emb-apimode-seg">
            <button type="button" class="seg-btn" data-mode="litellm">Standard (litellm)</button>
            <button type="button" class="seg-btn" data-mode="custom">Custom HTTP (JSON)</button>
          </div>
        </div>

        <!-- Standard / litellm -->
        <div id="emb-api-standard">
          <div class="form-group">
            <label class="form-label">Preset</label>
            <select class="form-select" id="emb-api-preset" style="max-width:480px">
              ${EMB_API_PRESETS.map((p, i) => `<option value="${i}">${p.label}</option>`).join('')}
            </select>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="setting-key">embedding_model</span>
              <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">litellm model ID, e.g. openai/text-embedding-3-small</span>
            </div>
            <div class="setting-input-wrap">
              <input class="form-input setting-input" id="emb-api-model" type="text"
                     value="${esc(apiModelInit)}" placeholder="openai/text-embedding-3-small">
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="setting-key">embedding_base_url</span>
              <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">API endpoint base URL</span>
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

        <!-- Custom HTTP (JSON) -->
        <div id="emb-api-custom">
          <div style="background:var(--bg-tertiary);border-radius:var(--radius-sm);padding:12px 16px;margin-bottom:16px;font-size:12.5px;color:var(--text-secondary);line-height:1.6;">
            Define the request yourself. In the body, <code>{{input}}</code> is replaced with a JSON array of all texts (one batched request); use <code>{{text}}</code> instead for one request per text. The vector(s) are read from the response via the JSON path below (<code>*</code> = array wildcard).
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
              <button class="btn btn-sm" id="emb-http-headers-eye" title="Reveal full headers" style="padding:2px 6px;font-size:14px;line-height:1;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
              </button>
            </label>
            <textarea class="form-textarea" id="emb-http-headers" spellcheck="false"
                      style="font-family:var(--font-mono);font-size:12.5px" placeholder='{"Authorization": "Bearer ..."}'>${esc(httpHeaders)}</textarea>
          </div>
          <div class="form-group">
            <label class="form-label"><span class="setting-key">embedding_http_body</span> &nbsp;<span class="text-muted text-sm">JSON template with {{input}} or {{text}}</span></label>
            <textarea class="form-textarea" id="emb-http-body" spellcheck="false"
                      style="font-family:var(--font-mono);font-size:12.5px;min-height:120px">${esc(httpBody)}</textarea>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              <span class="setting-key">embedding_http_response_path</span>
              <span class="text-muted text-sm" style="display:block;font-family:var(--font);margin-top:2px">Dot path to the vector(s); OpenAI shape = data.*.embedding</span>
            </div>
            <div class="setting-input-wrap">
              <input class="form-input setting-input" id="emb-http-response-path" type="text"
                     value="${esc(httpRespPath)}" placeholder="data.*.embedding">
            </div>
          </div>
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

  /* Provider + API-mode segmented controls */
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

  /* Preset auto-select + change handlers */
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

  /* Eye toggle for the API key (password input) */
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
        apiKeyInput.placeholder = res.value ? '' : '(not set)';
        keyRevealed = true;
        keyEyeBtn.style.color = 'var(--accent)';
      } catch (e) {
        error('Failed to reveal key: ' + e.message);
      }
    }
  });

  /* Reveal full headers (masked JSON blob → full text) */
  httpHeadersEye.addEventListener('click', async () => {
    try {
      const res = await api.revealConfigValue('embedding_http_headers');
      if (res.value) httpHeadersInput.value = res.value;
      httpHeadersEye.style.color = 'var(--accent)';
    } catch (e) {
      error('Failed to reveal headers: ' + e.message);
    }
  });

  /* Run a test for whichever mode is active, reusing the progress/log UI. */
  async function runTest(params, logHeader) {
    resetProgress();
    statusEl.innerHTML = '<span style="color:var(--accent)">Testing...</span>';
    logEl.classList.remove('hidden');
    logEl.style.borderColor = 'var(--border)';
    logEl.textContent = logHeader;
    testBtn.disabled = true;
    try {
      const res = await api.testEmbedding(params);
      if (res.async && res.task_id) {
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
  }

  /* Test button — dispatches on the active provider / API mode */
  testBtn.addEventListener('click', async () => {
    if (currentProvider === 'local') {
      const model = localModelInput.value.trim();
      if (!model) { error('Model is required'); return; }
      await runTest({ provider: 'local', model }, `Testing embedding...\nProvider: local\nModel: ${model}\n`);
    } else if (currentApiMode === 'custom') {
      const http_url = httpUrlInput.value.trim();
      const http_body = httpBodyInput.value;
      if (!http_url) { error('URL is required for custom HTTP embedding'); return; }
      if (!http_body.trim()) { error('Request body is required for custom HTTP embedding'); return; }
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
        `Testing embedding...\nProvider: api (custom HTTP)\n${methodSelect.value} ${http_url}\n`
      );
    } else {
      const model = apiModelInput.value.trim();
      const base_url = baseUrlInput.value.trim() || null;
      const api_key = apiKeyInput.value.trim() || null;
      if (!model) { error('Model is required'); return; }
      if (!base_url) { error('Base URL is required for API embedding'); return; }
      await runTest(
        { provider: 'api', api_mode: 'litellm', model, base_url, api_key },
        `Testing embedding...\nProvider: api (litellm)\nModel: ${model}\nBase URL: ${base_url}\n`
      );
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
        badge.textContent = st.api_mode === 'custom' ? 'API · custom HTTP' : 'API';
      } else if (st.cached) {
        badge.className = 'tag tag-green';
        badge.textContent = 'local · cached';
      } else {
        badge.className = 'tag tag-yellow';
        badge.textContent = 'local · not downloaded';
      }
    } catch { /* ignore */ }
  }

  /* Save button — writes only the fields relevant to the active mode. */
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
        <span style="margin-right:6px">${group.icon}</span>${group.titleKey ? t(group.titleKey) : group.title}
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
          if (res && res.restart_required) {
            offerRestart({ onRestarted: () => window.location.reload() });
          }
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
  const displayValue = value == null ? '' : String(value);
  if (key === 'consolidation_time') {
    return `<input class="form-input setting-input" type="time" step="60" value="${esc(displayValue)}" data-key="${key}">`;
  }
  return `<input class="form-input setting-input" type="${type}" value="${esc(displayValue)}" placeholder="null" data-key="${key}">`;
}

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

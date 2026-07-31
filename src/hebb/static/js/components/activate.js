/**
 * Activate (记忆激活) — recall test + recall parameters in one page.
 *
 * Top: a live search ("activation test") with per-query weight sliders and
 * scored results, exactly like the old Search page. Below: the global recall
 * parameters that used to live under Settings → Retrieval — the recall pipeline
 * toggles, the cross-encoder rerank, and the default scoring weights — so you
 * can test recall and tune the knobs that shape it without leaving the page.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { error } from './toast.js';
import { buildGenericSection } from './config-section.js';

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function truncate(s, n = 200) { return s.length > n ? s.slice(0, n) + '...' : s; }

/* --- Recall-parameter config groups (moved from Settings → Retrieval) ---
 *
 * Built at RENDER time (not at module load) so t() resolves the CURRENT
 * language on every (re)render — module-level t() would freeze the initial
 * language for these display strings.
 */
function groupRecall() {
  return {
    titleKey: 'settings.group.recall',
    icon: '&#128269;',
    keys: ['keyword_search_enabled', 'graph_search_enabled', 'lexical_boost_enabled', 'temporal_boost_enabled', 'graph_expansion_enabled', 'recall_min_score'],
    hints: {
      keyword_search_enabled: t('recall.hint.keyword_search_enabled'),
      graph_search_enabled: t('recall.hint.graph_search_enabled'),
      lexical_boost_enabled: t('recall.hint.lexical_boost_enabled'),
      temporal_boost_enabled: t('recall.hint.temporal_boost_enabled'),
      graph_expansion_enabled: t('recall.hint.graph_expansion_enabled'),
      recall_min_score: t('recall.hint.recall_min_score'),
    },
  };
}
function groupRerank() {
  return {
    titleKey: 'settings.group.rerank',
    icon: '&#127919;',
    keys: ['rerank_enabled', 'rerank_provider', 'rerank_model', 'rerank_top_n', 'rerank_floor_ratio'],
    hints: {
      rerank_enabled: t('recall.hint.rerank_enabled'),
      rerank_provider: t('recall.hint.rerank_provider'),
      rerank_model: t('recall.hint.rerank_model'),
      rerank_top_n: t('recall.hint.rerank_top_n'),
      rerank_floor_ratio: t('recall.hint.rerank_floor_ratio'),
    },
  };
}
function groupWeights() {
  return {
    titleKey: 'settings.group.weights',
    icon: '&#9878;',
    note: t('recall.note_weights'),
    keys: ['weight_recency', 'weight_importance', 'weight_relevance'],
    hints: {
      weight_recency: t('recall.hint.weight_recency'),
      weight_importance: t('recall.hint.weight_importance'),
      weight_relevance: t('recall.hint.weight_relevance'),
    },
  };
}

export async function renderActivate(root) {
  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('activate.title')}</h1>
      <p class="page-subtitle">${t('activate.subtitle')}</p>
    </div>

    <h2 class="section-heading">${t('activate.test_title')}</h2>
    <div class="search-bar">
      <input class="form-input" id="search-input" placeholder="${t('search.placeholder')}" autofocus>
      <button class="btn btn-primary" id="btn-search">${t('search.button')}</button>
    </div>
    <div class="card mb-4">
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;">
        <div class="form-group">
          <label class="form-label">${t('search.relevance')}: <span id="w-rel-val">1.0</span></label>
          <div class="range-group"><input type="range" id="w-rel" min="0" max="3" step="0.1" value="1.0"></div>
        </div>
        <div class="form-group">
          <label class="form-label">${t('search.importance')}: <span id="w-imp-val">1.0</span></label>
          <div class="range-group"><input type="range" id="w-imp" min="0" max="3" step="0.1" value="1.0"></div>
        </div>
        <div class="form-group">
          <label class="form-label">${t('search.recency')}: <span id="w-rec-val">1.0</span></label>
          <div class="range-group"><input type="range" id="w-rec" min="0" max="3" step="0.1" value="1.0"></div>
        </div>
        <div class="form-group">
          <label class="form-label">${t('search.top_k')}</label>
          <input class="form-input" id="top-k" type="number" value="10" min="1" max="100" style="width:80px">
        </div>
      </div>
    </div>
    <div id="search-results" class="mb-4"></div>

    <h2 class="section-heading">${t('activate.params_title')}</h2>
    <div id="activate-params"></div>
  `;

  /* Wire sliders */
  ['rel', 'imp', 'rec'].forEach(k => {
    const slider = root.querySelector(`#w-${k}`);
    const label = root.querySelector(`#w-${k}-val`);
    slider.oninput = () => { label.textContent = parseFloat(slider.value).toFixed(1); };
  });

  async function doSearch() {
    const query = root.querySelector('#search-input').value.trim();
    if (!query) return;
    const results = root.querySelector('#search-results');
    results.innerHTML = `<div class="text-muted" style="padding:20px;text-align:center">${t('common.loading')}</div>`;
    try {
      const resp = await api.searchMemories({
        query,
        top_k: parseInt(root.querySelector('#top-k').value) || 10,
        weight_relevance: parseFloat(root.querySelector('#w-rel').value),
        weight_importance: parseFloat(root.querySelector('#w-imp').value),
        weight_recency: parseFloat(root.querySelector('#w-rec').value),
      });
      const data = resp.results || resp;
      if (!data.length) {
        results.innerHTML = `<div class="empty-state">${t('search.no_results')}</div>`;
        return;
      }
      let html = data.map((r, i) => `
        <div class="result-card">
          <div class="flex-between">
            <div class="result-score">
              #${i + 1} &middot; ${t('search.score')}: <strong>${r.score.toFixed(3)}</strong>
              &middot; <span class="tag tag-blue">${esc(r.memory.partition_id.replace('mem_', ''))}</span>
              ${r.memory.tags.map(tag => `<span class="tag">${esc(tag)}</span>`).join(' ')}
            </div>
          </div>
          <div class="result-content">${esc(truncate(r.memory.content))}</div>
          <div class="score-bars">
            <div class="score-bar-item">
              <div class="score-bar-label">${t('search.relevance_label')} ${r.relevance_score.toFixed(2)}</div>
              <div class="score-bar"><div class="score-bar-fill blue" style="width:${(r.relevance_score * 100).toFixed(1)}%"></div></div>
            </div>
            <div class="score-bar-item">
              <div class="score-bar-label">${t('search.importance_label')} ${r.importance_score_normalized.toFixed(2)}</div>
              <div class="score-bar"><div class="score-bar-fill yellow" style="width:${(r.importance_score_normalized * 100).toFixed(1)}%"></div></div>
            </div>
            <div class="score-bar-item">
              <div class="score-bar-label">${t('search.recency_label')} ${r.recency_score.toFixed(2)}</div>
              <div class="score-bar"><div class="score-bar-fill green" style="width:${(r.recency_score * 100).toFixed(1)}%"></div></div>
            </div>
          </div>
        </div>
      `).join('');
      const related = resp.related || [];
      if (related.length) {
        html += `
          <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border)">
            <h4 style="font-size:13px;color:var(--text-secondary);margin-bottom:12px">
              ${t('search.related')}
            </h4>
            ${related.map(m => `
              <div class="result-card" style="opacity:0.75">
                <div class="result-score">
                  <span class="tag tag-blue">${esc(m.partition_id.replace('mem_', ''))}</span>
                  ${m.tags.map(tag => `<span class="tag">${esc(tag)}</span>`).join(' ')}
                </div>
                <div class="result-content">${esc(truncate(m.content))}</div>
              </div>
            `).join('')}
          </div>`;
      }
      results.innerHTML = html;
    } catch (e) {
      results.innerHTML = `<div class="empty-state">${e.message}</div>`;
      error(e.message);
    }
  }

  root.querySelector('#btn-search').onclick = doSearch;
  root.querySelector('#search-input').addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

  /* Recall parameters (global config) */
  const paramsRoot = root.querySelector('#activate-params');
  try {
    const config = await api.getConfig();
    paramsRoot.appendChild(buildGenericSection(groupRecall(), config));
    paramsRoot.appendChild(buildGenericSection(groupRerank(), config));
    paramsRoot.appendChild(buildGenericSection(groupWeights(), config));
  } catch (e) {
    paramsRoot.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
  }
}

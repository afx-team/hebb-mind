/**
 * Search — semantic memory search with weight tuning.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { error } from './toast.js';

function truncate(s, n = 200) { return s.length > n ? s.slice(0, n) + '...' : s; }

export async function renderSearch(root) {
  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('search.title')}</h1>
      <p class="page-subtitle">${t('search.subtitle')}</p>
    </div>
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
    <div id="search-results"></div>
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
    results.innerHTML = '<div class="text-muted" style="padding:20px;text-align:center">Searching...</div>';
    try {
      const resp = await api.searchMemories({
        query,
        top_k: parseInt(root.querySelector('#top-k').value) || 10,
        weight_relevance: parseFloat(root.querySelector('#w-rel').value),
        weight_importance: parseFloat(root.querySelector('#w-imp').value),
        weight_recency: parseFloat(root.querySelector('#w-rec').value),
      });
      const data = resp.results || resp; // support both SearchResponse and legacy list
      if (!data.length) {
        results.innerHTML = `<div class="empty-state">${t('search.no_results')}</div>`;
        return;
      }
      let html = data.map((r, i) => `
        <div class="result-card">
          <div class="flex-between">
            <div class="result-score">
              #${i + 1} &middot; ${t('search.score')}: <strong>${r.score.toFixed(3)}</strong>
              &middot; <span class="tag tag-blue">${r.memory.partition_id.replace('mem_', '')}</span>
              ${r.memory.tags.map(t => `<span class="tag">${t}</span>`).join(' ')}
            </div>
          </div>
          <div class="result-content">${truncate(r.memory.content)}</div>
          <div class="score-bars">
            <div class="score-bar-item">
              <div class="score-bar-label">Relevance ${r.relevance_score.toFixed(2)}</div>
              <div class="score-bar"><div class="score-bar-fill blue" style="width:${(r.relevance_score * 100).toFixed(1)}%"></div></div>
            </div>
            <div class="score-bar-item">
              <div class="score-bar-label">Importance ${r.importance_score_normalized.toFixed(2)}</div>
              <div class="score-bar"><div class="score-bar-fill yellow" style="width:${(r.importance_score_normalized * 100).toFixed(1)}%"></div></div>
            </div>
            <div class="score-bar-item">
              <div class="score-bar-label">Recency ${r.recency_score.toFixed(2)}</div>
              <div class="score-bar"><div class="score-bar-fill green" style="width:${(r.recency_score * 100).toFixed(1)}%"></div></div>
            </div>
          </div>
        </div>
      `).join('');
      // Related memories from graph expansion
      const related = resp.related || [];
      if (related.length) {
        html += `
          <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border)">
            <h4 style="font-size:13px;color:var(--text-secondary);margin-bottom:12px">
              Related (via knowledge graph)
            </h4>
            ${related.map(m => `
              <div class="result-card" style="opacity:0.75">
                <div class="result-score">
                  <span class="tag tag-blue">${m.partition_id.replace('mem_', '')}</span>
                  ${m.tags.map(t => `<span class="tag">${t}</span>`).join(' ')}
                </div>
                <div class="result-content">${truncate(m.content)}</div>
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
}

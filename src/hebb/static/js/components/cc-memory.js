/**
 * CC Memory — browse, view, and edit Claude Code's file-based memory
 * documents (~/.claude/projects/<slug>/memory/*.md).
 *
 * Files are shown as rendered Markdown; an Edit toggle swaps in a raw
 * textarea that saves back to disk via the API.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error } from './toast.js';

let currentProject = '';
let currentFile = '';
let files = [];      // file list for the current project
let editing = false;

/* ---- helpers ---- */
function escapeHtml(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtDate(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleString('sv-SE', { dateStyle: 'short', timeStyle: 'short' });
}

function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

/* ---- minimal, safe Markdown rendering ---- */
/* Input is HTML-escaped first, so all transforms below only ever emit
 * tags we generate ourselves — user content can never inject markup. */

function inline(escaped) {
  const codes = [];
  // Protect inline-code spans with a sentinel that cannot occur in escaped text.
  let s = escaped.replace(/`([^`]+)`/g, (_, c) => {
    codes.push(c);
    return `@@CODE${codes.length - 1}@@`;
  });
  // [[wikilink]] — open the linked note in this project
  s = s.replace(/\[\[([^\]]+)\]\]/g, (_, name) => {
    const n = name.trim();
    return `<a class="cc-wikilink" data-link="${n}">${n}</a>`;
  });
  // [text](url) — http(s) external, *.md treated as an in-project note
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, url) => {
    const u = url.trim();
    if (/^https?:\/\//.test(u)) {
      return `<a href="${u}" target="_blank" rel="noopener noreferrer">${text}</a>`;
    }
    if (u.endsWith('.md') && !u.includes('/')) {
      return `<a class="cc-wikilink" data-link="${u.replace(/\.md$/, '')}">${text}</a>`;
    }
    return text;
  });
  // **bold**
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // restore inline code
  s = s.replace(/@@CODE(\d+)@@/g, (_, i) => `<code>${codes[i]}</code>`);
  return s;
}

function mdBodyToHtml(body) {
  const escaped = escapeHtml(body);
  const lines = escaped.split('\n');
  const out = [];
  let inCode = false;
  let codeBuf = [];
  let listBuf = [];
  let listType = '';
  let paraBuf = [];

  const flushPara = () => {
    if (paraBuf.length) {
      out.push(`<p>${inline(paraBuf.join(' '))}</p>`);
      paraBuf = [];
    }
  };
  const flushList = () => {
    if (listBuf.length) {
      const items = listBuf.map(li => `<li>${inline(li)}</li>`).join('');
      out.push(`<${listType}>${items}</${listType}>`);
      listBuf = [];
      listType = '';
    }
  };

  for (const line of lines) {
    if (/^```/.test(line)) {
      if (inCode) {
        out.push(`<pre><code>${codeBuf.join('\n')}</code></pre>`);
        codeBuf = [];
        inCode = false;
      } else {
        flushPara();
        flushList();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      codeBuf.push(line);
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushPara();
      flushList();
      const level = heading[1].length;
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      continue;
    }

    const ul = line.match(/^\s*[-*]\s+(.*)$/);
    const ol = line.match(/^\s*\d+\.\s+(.*)$/);
    if (ul || ol) {
      flushPara();
      const wantType = ul ? 'ul' : 'ol';
      if (listType && listType !== wantType) flushList();
      listType = wantType;
      listBuf.push(ul ? ul[1] : ol[1]);
      continue;
    }

    if (line.trim() === '') {
      flushPara();
      flushList();
      continue;
    }

    flushList();
    paraBuf.push(line.trim());
  }

  if (inCode) out.push(`<pre><code>${codeBuf.join('\n')}</code></pre>`);
  flushPara();
  flushList();
  return out.join('\n');
}

function splitFrontmatter(raw) {
  if (!raw.startsWith('---')) return { fm: null, body: raw };
  const m = raw.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!m) return { fm: null, body: raw };
  return { fm: m[1], body: raw.slice(m[0].length) };
}

function renderFrontmatter(fm) {
  const get = (key) => {
    const m = fm.match(new RegExp(`^\\s*${key}:\\s*(.+)$`, 'm'));
    return m ? m[1].trim().replace(/^["']|["']$/g, '') : '';
  };
  const name = get('name');
  const desc = get('description');
  const type = get('type');
  if (!name && !desc && !type) return '';
  const typeBadge = type ? `<span class="tag tag-blue">${escapeHtml(type)}</span>` : '';
  return `
    <div class="cc-frontmatter">
      <div class="cc-fm-head">
        ${name ? `<span class="cc-fm-name">${escapeHtml(name)}</span>` : ''}
        ${typeBadge}
      </div>
      ${desc ? `<div class="cc-fm-desc">${escapeHtml(desc)}</div>` : ''}
    </div>`;
}

function renderMarkdown(raw) {
  const { fm, body } = splitFrontmatter(raw);
  return (fm ? renderFrontmatter(fm) : '') + `<div class="md-body">${mdBodyToHtml(body)}</div>`;
}

/* ---- data loading ---- */
async function loadProjects(root) {
  const select = root.querySelector('#cc-project');
  let projects = [];
  try {
    projects = await api.listCCProjects();
  } catch (e) {
    error(e.message);
  }
  if (!projects.length) {
    select.innerHTML = `<option value="">${t('cc.no_projects')}</option>`;
    root.querySelector('#cc-files').innerHTML = `<div class="empty-state">${t('cc.no_projects')}</div>`;
    root.querySelector('#cc-content').innerHTML = '';
    return;
  }
  select.innerHTML = projects
    .map(p => `<option value="${escapeHtml(p.slug)}">${escapeHtml(p.path)} · ${p.file_count} ${t('cc.files')}</option>`)
    .join('');
  // Keep the prior selection if it still exists, else pick the first (most recent).
  if (!projects.some(p => p.slug === currentProject)) currentProject = projects[0].slug;
  select.value = currentProject;
  await loadFiles(root);
}

async function loadFiles(root) {
  const list = root.querySelector('#cc-files');
  list.innerHTML = `<div class="text-muted text-sm" style="padding:12px">${t('common.loading')}</div>`;
  try {
    files = await api.listCCFiles(currentProject);
  } catch (e) {
    list.innerHTML = `<div class="empty-state">${escapeHtml(e.message)}</div>`;
    return;
  }
  if (!files.length) {
    list.innerHTML = `<div class="empty-state">${t('cc.no_files')}</div>`;
    root.querySelector('#cc-content').innerHTML = `<div class="empty-state">${t('cc.no_files')}</div>`;
    return;
  }
  list.innerHTML = files.map(f => `
    <button class="cc-file-item ${f.name === currentFile ? 'active' : ''}" data-name="${escapeHtml(f.name)}">
      <span class="cc-file-name">${escapeHtml(f.name)}</span>
      ${f.is_index ? `<span class="tag tag-blue">${t('cc.index_badge')}</span>` : ''}
      <span class="cc-file-meta">${fmtSize(f.size)} · ${fmtDate(f.updated_at)}</span>
    </button>
  `).join('');
  list.querySelectorAll('.cc-file-item').forEach(btn => {
    btn.onclick = () => openFile(root, btn.dataset.name);
  });

  // Reset the viewer when the current file is no longer in the list.
  if (!files.some(f => f.name === currentFile)) {
    currentFile = '';
    root.querySelector('#cc-content').innerHTML = `<div class="empty-state">${t('cc.select_file')}</div>`;
  }
}

async function openFile(root, name) {
  editing = false;
  currentFile = name;
  root.querySelectorAll('.cc-file-item').forEach(b => b.classList.toggle('active', b.dataset.name === name));
  const panel = root.querySelector('#cc-content');
  panel.innerHTML = `<div class="text-muted text-sm" style="padding:12px">${t('common.loading')}</div>`;
  let data;
  try {
    data = await api.getCCFile(currentProject, name);
  } catch (e) {
    panel.innerHTML = `<div class="empty-state">${escapeHtml(e.message)}</div>`;
    return;
  }
  renderViewer(root, data);
}

function renderViewer(root, data) {
  const panel = root.querySelector('#cc-content');
  panel.innerHTML = `
    <div class="cc-doc-header flex-between">
      <div>
        <span class="cc-doc-title">${escapeHtml(data.name)}</span>
        <span class="text-muted text-sm">${t('cc.updated')} ${fmtDate(data.updated_at)} · ${fmtSize(data.size)}</span>
      </div>
      <div class="btn-group" id="cc-actions"></div>
    </div>
    <div class="cc-doc-body" id="cc-doc-body"></div>
  `;
  const actions = panel.querySelector('#cc-actions');
  const bodyEl = panel.querySelector('#cc-doc-body');

  if (editing) {
    actions.innerHTML = `
      <button class="btn btn-sm" id="cc-cancel">${t('cc.cancel')}</button>
      <button class="btn btn-sm btn-primary" id="cc-save">${t('cc.save')}</button>
    `;
    bodyEl.innerHTML = `<textarea class="form-textarea cc-editor" id="cc-textarea" spellcheck="false"></textarea>`;
    bodyEl.querySelector('#cc-textarea').value = data.content;
    actions.querySelector('#cc-cancel').onclick = () => { editing = false; renderViewer(root, data); };
    actions.querySelector('#cc-save').onclick = async () => {
      const content = bodyEl.querySelector('#cc-textarea').value;
      try {
        const updated = await api.saveCCFile(currentProject, data.name, content);
        success(t('cc.saved_ok'));
        editing = false;
        renderViewer(root, updated);
        loadFiles(root); // refresh size/mtime in the list
      } catch (e) {
        error(`${t('cc.save_failed')}: ${e.message}`);
      }
    };
  } else {
    actions.innerHTML = `<button class="btn btn-sm" id="cc-edit">${t('cc.edit')}</button>`;
    bodyEl.innerHTML = renderMarkdown(data.content);
    actions.querySelector('#cc-edit').onclick = () => { editing = true; renderViewer(root, data); };
    // Wikilinks open the linked note when it exists in this project.
    bodyEl.querySelectorAll('.cc-wikilink').forEach(a => {
      const target = `${a.dataset.link}.md`;
      const exists = files.some(f => f.name === target);
      if (exists) {
        a.classList.add('cc-wikilink-live');
        a.onclick = (e) => { e.preventDefault(); openFile(root, target); };
      } else {
        a.classList.add('cc-wikilink-dead');
      }
    });
  }
}

/* ---- entry ---- */
export async function renderCCMemory(root) {
  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${t('cc.title')}</h1>
      <p class="page-subtitle">${t('cc.subtitle')}</p>
    </div>
    <div class="flex gap-4 mb-4">
      <select class="form-select" id="cc-project" style="max-width:420px"></select>
    </div>
    <div class="cc-layout">
      <div class="card cc-files" id="cc-files"></div>
      <div class="card cc-content" id="cc-content">
        <div class="empty-state">${t('cc.select_file')}</div>
      </div>
    </div>
  `;
  root.querySelector('#cc-project').onchange = (e) => {
    currentProject = e.target.value;
    currentFile = '';
    editing = false;
    loadFiles(root);
  };
  await loadProjects(root);
}

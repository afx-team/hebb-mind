/**
 * App — SPA router, theme, i18n, page lifecycle.
 */

import * as api from './api.js';
import { t, getLang, setLang } from './i18n.js';
import { runCleanups } from './lifecycle.js';
import { renderManage } from './components/manage.js';
import { renderActivate } from './components/activate.js';
import { renderAgentSync } from './components/agent-sync.js';
import { renderConsolidate } from './components/consolidate.js';
import { renderForget } from './components/forget.js';
import { renderSystem } from './components/system.js';
import { mountUpgradeBanner } from './components/upgrade-banner.js';

const content = document.getElementById('page-content');
const navItems = document.querySelectorAll('.nav-item');
const sidebarToggle = document.getElementById('sidebar-toggle');
const sidebar = document.getElementById('sidebar');
const statusDot = document.querySelector('.status-dot');
const statusText = document.querySelector('.status-text');

const pages = {
  manage: renderManage,
  activate: renderActivate,
  'agent-sync': renderAgentSync,
  consolidate: renderConsolidate,
  forget: renderForget,
  system: renderSystem,
};

const pageAliases = {
  'cc-memory': 'agent-sync',
};

const DEFAULT_PAGE = 'manage';

let currentPage = null;
let currentSub = null;

/* ---- Navigation ---- */
function updateNavLabels() {
  navItems.forEach(el => {
    const key = `nav.${el.dataset.page}`;
    const span = el.querySelector('span');
    if (span) span.textContent = t(key);
  });
}

function navigate(page, sub) {
  const requestedPage = page;
  page = pageAliases[page] || page;
  if (requestedPage !== page) {
    history.replaceState(null, '', sub ? `#${page}/${sub}` : `#${page}`);
  }
  if (!pages[page]) { page = DEFAULT_PAGE; sub = null; }
  currentPage = page;
  currentSub = sub || null;
  navItems.forEach(el => {
    el.classList.toggle('active', el.dataset.page === page);
  });
  // Tear down the outgoing view's timers/observers/renderers before swapping.
  runCleanups();
  content.innerHTML = '';
  pages[page](content, currentSub);
}

function onHash() {
  // Supports "#page" and "#page/sub" (sub = an in-page tab, e.g. #manage/graph).
  const raw = location.hash.replace(/^#/, '');
  const [page, sub] = raw.split('/');
  navigate(page || DEFAULT_PAGE, sub);
}
window.addEventListener('hashchange', onHash);

/* ---- Sidebar collapse ---- */
sidebarToggle.addEventListener('click', () => {
  sidebar.classList.toggle('collapsed');
});

/* ---- Theme toggle ---- */
const themeBtn = document.getElementById('theme-toggle');
const themeIcon = document.getElementById('theme-icon');

// Sun icon paths
const sunIcon = '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
// Moon icon paths
const moonIcon = '<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('hebb-theme', theme);
  themeIcon.innerHTML = theme === 'dark' ? sunIcon : moonIcon;
}

const savedTheme = localStorage.getItem('hebb-theme') || 'dark';
applyTheme(savedTheme);

themeBtn.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  applyTheme(current === 'dark' ? 'light' : 'dark');
});

/* ---- Language toggle ---- */
const langBtn = document.getElementById('lang-toggle');
const langLabel = document.getElementById('lang-label');

function applyLang(lang) {
  setLang(lang);
  langLabel.textContent = lang.toUpperCase();
  updateNavLabels();
  // Re-render current page (and its active sub-tab) to apply translations
  if (currentPage && pages[currentPage]) {
    runCleanups();
    content.innerHTML = '';
    pages[currentPage](content, currentSub);
  }
}

langLabel.textContent = getLang().toUpperCase();
updateNavLabels();

langBtn.addEventListener('click', () => {
  const next = getLang() === 'en' ? 'zh' : 'en';
  applyLang(next);
});

/* ---- Health check ---- */
async function checkHealth() {
  try {
    const data = await api.getHealth();
    statusDot.className = 'status-dot online';
    statusText.textContent = `v${data.version || '?'}`;
  } catch {
    statusDot.className = 'status-dot offline';
    statusText.textContent = 'Offline';
  }
}

/* ---- Init ---- */
checkHealth();
setInterval(checkHealth, 30000);
mountUpgradeBanner();
onHash();

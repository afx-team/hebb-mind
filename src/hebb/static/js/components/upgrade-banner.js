/**
 * Upgrade banner — sits at the top of <main>, polls /api/v1/admin/upgrade
 * every 60s, surfaces when a newer version is available and the user has
 * not skipped it for this version or hidden it for the session.
 *
 * PR-1 surface: read-only. [Upgrade now] is disabled with a tooltip; [Skip
 * this version] stores a sessionStorage marker (PR-2 will wire the real
 * /dismiss endpoint).
 */

import * as api from '../api.js';
import { t } from '../i18n.js';

const POLL_INTERVAL_MS = 60_000;
const SESSION_HIDE_KEY = 'hebb-upgrade-banner-hidden';
const SKIP_KEY_PREFIX = 'hebb-upgrade-skip:'; // suffix is the version string

let bannerEl = null;
let pollTimer = null;

function format(template, vars) {
  return template.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
}

function shouldShow(state) {
  if (!state || !state.available) return false;
  if (!state.latest_version) return false;
  if (state.dismissed_for_version && state.dismissed_for_version === state.latest_version) return false;
  if (sessionStorage.getItem(SESSION_HIDE_KEY) === state.latest_version) return false;
  if (localStorage.getItem(SKIP_KEY_PREFIX + state.latest_version) === '1') return false;
  return true;
}

function render(state) {
  if (!bannerEl) return;
  if (!shouldShow(state)) {
    bannerEl.classList.add('hidden');
    bannerEl.innerHTML = '';
    return;
  }
  const latest = state.latest_version;
  const current = state.current_version || '';

  bannerEl.classList.remove('hidden');
  bannerEl.innerHTML = `
    <div class="upgrade-banner-inner">
      <span class="upgrade-banner-icon" aria-hidden="true">&#10024;</span>
      <span class="upgrade-banner-text">
        <strong>${format(t('upgrade.available'), { latest })}</strong>
        <span class="upgrade-banner-current">${format(t('upgrade.current'), { current })}</span>
      </span>
      <span class="upgrade-banner-actions">
        <button class="btn btn-primary btn-sm" id="upgrade-apply" disabled
                title="${t('upgrade.apply_disabled_tooltip')}">${t('upgrade.apply')}</button>
        <button class="btn btn-sm" id="upgrade-skip">${t('upgrade.skip')}</button>
        <button class="btn-link" id="upgrade-later" aria-label="${t('upgrade.later')}">&times;</button>
      </span>
    </div>
  `;
  bannerEl.querySelector('#upgrade-skip').addEventListener('click', () => {
    // PR-1 placeholder: persist locally. PR-2 will call POST /upgrade/dismiss.
    localStorage.setItem(SKIP_KEY_PREFIX + latest, '1');
    render(state);
  });
  bannerEl.querySelector('#upgrade-later').addEventListener('click', () => {
    sessionStorage.setItem(SESSION_HIDE_KEY, latest);
    render(state);
  });
}

async function refresh() {
  try {
    const state = await api.getUpgradeState();
    render(state);
  } catch {
    // Daemon may be restarting or endpoint not yet available — silently retry on next tick.
  }
}

export function mountUpgradeBanner() {
  if (bannerEl) return;
  const main = document.getElementById('main');
  if (!main) return;
  bannerEl = document.createElement('div');
  bannerEl.id = 'upgrade-banner';
  bannerEl.className = 'upgrade-banner hidden';
  main.insertBefore(bannerEl, main.firstChild);

  refresh();
  pollTimer = setInterval(refresh, POLL_INTERVAL_MS);
}

export function unmountUpgradeBanner() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (bannerEl) {
    bannerEl.remove();
    bannerEl = null;
  }
}

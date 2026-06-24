/**
 * Upgrade banner — sits at the top of <main>, polls /api/v1/admin/upgrade and
 * surfaces when a newer version is available.
 *
 * PR-2 surface: [Upgrade now] is enabled when the install method is
 * auto-upgradable (pip / pipx / uv-tool); it opens a confirm modal, POSTs
 * /apply, then tracks the detached helper across the daemon restart and reloads
 * the console on success. [Skip this version] calls POST /dismiss (server-side,
 * cross-session). [Later] hides for this browser session only.
 */

import * as api from '../api.js';
import { t } from '../i18n.js';
import { success, error, info } from './toast.js';

const POLL_INTERVAL_MS = 60_000;
const PROGRESS_POLL_MS = 2_000;
const PROGRESS_DEADLINE_MS = 300_000; // give the install + restart up to 5 min
const SESSION_HIDE_KEY = 'hebb-upgrade-banner-hidden';
const RELEASES_URL = 'https://github.com/afx-team/hebb-mind/releases';

let bannerEl = null;
let idleTimer = null;
let progressTimer = null;
let tracking = false;
let trackingDeadline = 0;
let lastState = null;

function format(template, vars) {
  return template.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
}

function shouldShow(state) {
  if (!state || !state.available) return false;
  if (!state.latest_version) return false;
  if (state.dismissed_for_version && state.dismissed_for_version === state.latest_version) return false;
  if (sessionStorage.getItem(SESSION_HIDE_KEY) === state.latest_version) return false;
  return true;
}

/* Localized tooltip for a disabled [Upgrade now] button, keyed by install method. */
function refusalTooltip(state) {
  const key = {
    editable: 'upgrade.refuse.editable',
    system: 'upgrade.refuse.system',
    unknown: 'upgrade.refuse.unknown',
  }[state.method];
  if (key) return t(key);
  return state.refusal_reason || t('upgrade.apply_disabled_tooltip');
}

/* ---- render -------------------------------------------------------------- */

function render(state) {
  if (!bannerEl) return;

  // An upgrade in flight (this tab, another tab, or auto mode) always shows
  // progress and starts tracking if we are not already.
  if (state && state.upgrade_in_progress) {
    renderProgress(state);
    if (!tracking) enterProgress();
    return;
  }

  if (!shouldShow(state)) {
    bannerEl.classList.add('hidden');
    bannerEl.innerHTML = '';
    return;
  }

  const latest = state.latest_version;
  const current = state.current_version || '';
  const canUpgrade = state.auto_upgradable === true;
  const applyAttrs = canUpgrade
    ? ''
    : `disabled title="${refusalTooltip(state)}"`;

  bannerEl.classList.remove('hidden');
  bannerEl.innerHTML = `
    <div class="upgrade-banner-inner">
      <span class="upgrade-banner-icon" aria-hidden="true">&#10024;</span>
      <span class="upgrade-banner-text">
        <strong>${format(t('upgrade.available'), { latest })}</strong>
        <span class="upgrade-banner-current">${format(t('upgrade.current'), { current })}</span>
      </span>
      <span class="upgrade-banner-actions">
        <button class="btn btn-primary btn-sm" id="upgrade-apply" ${applyAttrs}>${t('upgrade.apply')}</button>
        <button class="btn btn-sm" id="upgrade-skip">${t('upgrade.skip')}</button>
        <button class="btn-link" id="upgrade-later" aria-label="${t('upgrade.later')}">&times;</button>
      </span>
    </div>
  `;

  const applyBtn = bannerEl.querySelector('#upgrade-apply');
  if (canUpgrade) {
    applyBtn.addEventListener('click', () => confirmApply(state));
  }
  bannerEl.querySelector('#upgrade-skip').addEventListener('click', async () => {
    try {
      const next = await api.dismissUpgrade();
      lastState = next;
      info(t('upgrade.toast.dismissed'));
      render(next);
    } catch (e) {
      error(t('upgrade.toast.dismiss_failed') + ': ' + e.message);
    }
  });
  bannerEl.querySelector('#upgrade-later').addEventListener('click', () => {
    sessionStorage.setItem(SESSION_HIDE_KEY, latest);
    render(state);
  });
}

function renderProgress(state) {
  if (!bannerEl) return;
  const latest = (state && state.latest_version) || '';
  bannerEl.classList.remove('hidden');
  bannerEl.innerHTML = `
    <div class="upgrade-banner-inner">
      <span class="upgrade-banner-icon spin" aria-hidden="true">&#8635;</span>
      <span class="upgrade-banner-text">
        <strong>${format(t('upgrade.progress'), { latest })}</strong>
        <span class="upgrade-banner-current">${t('upgrade.progress_note')}</span>
      </span>
    </div>
  `;
}

/* ---- apply flow ---------------------------------------------------------- */

function confirmApply(state) {
  const overlay = document.getElementById('modal-overlay');
  if (!overlay) {
    error(t('config.modal_overlay_missing'));
    return;
  }
  const latest = state.latest_version;
  const current = state.current_version || '';
  overlay.classList.remove('hidden');
  overlay.innerHTML = `
    <div class="modal" style="max-width:440px">
      <h3 class="modal-title">${t('upgrade.confirm.title')}</h3>
      <p style="font-size:13px;color:var(--text-secondary);line-height:1.6;margin:0 0 8px;">
        ${format(t('upgrade.confirm.body'), { current, latest })}
      </p>
      <p style="font-size:12px;line-height:1.5;margin:0;">
        <a href="${RELEASES_URL}" target="_blank" rel="noopener">${t('upgrade.confirm.changelog')}</a>
      </p>
      <div class="modal-actions">
        <button class="btn" id="upgrade-cancel">${t('upgrade.confirm.cancel')}</button>
        <button class="btn btn-primary" id="upgrade-confirm">${t('upgrade.confirm.ok')}</button>
      </div>
    </div>
  `;
  const close = () => { overlay.classList.add('hidden'); overlay.innerHTML = ''; };
  overlay.querySelector('#upgrade-cancel').onclick = close;
  overlay.querySelector('#upgrade-confirm').onclick = async () => {
    const btn = overlay.querySelector('#upgrade-confirm');
    btn.disabled = true;
    btn.textContent = t('upgrade.confirm.working');
    try {
      const next = await api.applyUpgrade();
      lastState = next;
      close();
      info(t('upgrade.toast.started'));
      renderProgress(next);
      enterProgress();
    } catch (e) {
      btn.disabled = false;
      btn.textContent = t('upgrade.confirm.ok');
      error(t('upgrade.toast.failed') + ': ' + e.message);
    }
  };
}

/* ---- progress tracking across the daemon restart ------------------------- */

function enterProgress() {
  if (tracking) return;
  tracking = true;
  trackingDeadline = Date.now() + PROGRESS_DEADLINE_MS;
  stopTimers();
  progressTimer = setTimeout(progressTick, PROGRESS_POLL_MS);
}

async function progressTick() {
  if (!tracking) return;
  let state = null;
  try {
    state = await api.getUpgradeState();
    lastState = state;
  } catch {
    // Daemon is mid-restart (helper stopped it; new version coming up) —
    // keep polling until it answers again.
  }

  if (state && !state.upgrade_in_progress) {
    finishProgress(state);
    return;
  }
  if (Date.now() > trackingDeadline) {
    finishProgress(null); // timeout
    return;
  }
  progressTimer = setTimeout(progressTick, PROGRESS_POLL_MS);
}

function finishProgress(state) {
  tracking = false;
  stopTimers();
  startIdlePolling();

  if (!state) {
    error(t('upgrade.toast.timeout'));
    // Render WITHOUT the in-progress flag so we don't leave a frozen spinner
    // (lastState may still say upgrade_in_progress=true from before the daemon
    // went unreachable). Falling back to the available banner lets the user retry.
    if (lastState) render({ ...lastState, upgrade_in_progress: false });
    return;
  }

  const last = state.last_upgrade;
  if (last && last.status === 'success') {
    success(format(t('upgrade.toast.success'), { latest: last.to_version || state.current_version || '' }));
    // Hold long enough for the success toast (default ~3s) to be readable.
    setTimeout(() => window.location.reload(), 4000);
    return;
  }
  // Failed (or no record) — surface the reason and fall back to the banner.
  const reason = (last && (last.log_tail || last.status)) || t('upgrade.toast.unknown');
  error(t('upgrade.toast.failed') + ': ' + reason);
  render(state);
}

/* ---- lifecycle ----------------------------------------------------------- */

function stopTimers() {
  if (idleTimer) { clearInterval(idleTimer); idleTimer = null; }
  if (progressTimer) { clearTimeout(progressTimer); progressTimer = null; }
}

function startIdlePolling() {
  if (idleTimer) clearInterval(idleTimer);
  idleTimer = setInterval(refresh, POLL_INTERVAL_MS);
}

async function refresh() {
  try {
    const state = await api.getUpgradeState();
    lastState = state;
    render(state);
  } catch {
    // Daemon may be restarting or endpoint not yet available — retry next tick.
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
  startIdlePolling();
}

export function unmountUpgradeBanner() {
  tracking = false;
  stopTimers();
  if (bannerEl) {
    bannerEl.remove();
    bannerEl = null;
  }
}

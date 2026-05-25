/**
 * Toast notification system.
 */

const container = document.getElementById('toast-container');

export function toast(message, type = 'info', duration = 3000) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.style.animation = 'toastOut 200ms ease forwards';
    setTimeout(() => el.remove(), 200);
  }, duration);
}

export function success(msg) { toast(msg, 'success'); }
export function error(msg) { toast(msg, 'error', 5000); }
export function info(msg) { toast(msg, 'info'); }

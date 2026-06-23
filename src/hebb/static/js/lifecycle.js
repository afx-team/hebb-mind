/**
 * lifecycle.js — page/tab teardown registry.
 *
 * The SPA tears down a view by replacing innerHTML, which silently orphans any
 * resources a page created outside the DOM: timers (setInterval polls),
 * MutationObservers, and WebGL renderers. A page registers its teardown via
 * onCleanup(); the router (app.js navigate / applyLang) and the Manage tab
 * switcher call runCleanups() right before swapping the view, so nothing leaks
 * across navigations or tab switches.
 *
 * Kept dependency-free so any component can import it without a cycle through
 * app.js.
 */

let cleanups = [];

/** Register a teardown callback for the currently-rendering view. */
export function onCleanup(fn) {
  if (typeof fn === 'function') cleanups.push(fn);
}

/** Run and clear all pending teardown callbacks. Safe to call repeatedly. */
export function runCleanups() {
  const pending = cleanups;
  cleanups = [];
  for (const fn of pending) {
    try {
      fn();
    } catch (e) {
      console.error('cleanup error', e);
    }
  }
}

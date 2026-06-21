/* viewer_fullscreen.js — plain (non-module) script
 * Exposes window.ViewerFullscreen for the 3D viewer fullscreen/maximize toggle.
 * Loaded BEFORE each page's ES module (mirrors how shared_inputs.js is loaded).
 *
 * Mechanism: CSS `position:fixed; inset:0` maximize as the baseline (works on
 * iPhone Safari, which lacks element Fullscreen API), with the native Fullscreen
 * API layered on opportunistically for iPad/desktop.
 * Does NOT remount/teardown the three.js scene on toggle — pure layout change.
 */
(function () {
  'use strict';

  var MAXIMIZED_CLASS = 'viewer-maximized';

  /* ── Helper: is the native fullscreen element this wrapper? ─────────────── */
  function _isNativeFullscreen(wrapperEl) {
    var fs = document.fullscreenElement || document.webkitFullscreenElement || null;
    return fs === wrapperEl;
  }

  /* ── Public API ─────────────────────────────────────────────────────────── */

  /**
   * isMaximized(wrapperEl) — true if the wrapper has .viewer-maximized OR is
   * the current native fullscreen element.
   */
  function isMaximized(wrapperEl) {
    return wrapperEl.classList.contains(MAXIMIZED_CLASS) || _isNativeFullscreen(wrapperEl);
  }

  /**
   * toggle(wrapperEl, { onResize }) — flips .viewer-maximized on wrapperEl.
   *
   * ENTER: add class; best-effort requestFullscreen (also webkit prefix).
   * EXIT:  remove class; exit native fullscreen if active.
   * Calls onResize() after the layout change (via requestAnimationFrame) so the
   * renderer re-fits even if the ResizeObserver hasn't fired yet.
   */
  function toggle(wrapperEl, opts) {
    var onResize = (opts && opts.onResize) || function () {};

    if (isMaximized(wrapperEl)) {
      /* EXIT */
      wrapperEl.classList.remove(MAXIMIZED_CLASS);
      /* Exit native fullscreen if this element is the current fullscreen element */
      try {
        if (_isNativeFullscreen(wrapperEl)) {
          var exitFn = document.exitFullscreen || document.webkitExitFullscreen;
          if (exitFn) exitFn.call(document);
        }
      } catch (e) { /* ignore — not critical */ }
    } else {
      /* ENTER */
      wrapperEl.classList.add(MAXIMIZED_CLASS);
      /* Best-effort native fullscreen — must be inside a user gesture */
      try {
        var reqFn = wrapperEl.requestFullscreen || wrapperEl.webkitRequestFullscreen;
        if (reqFn) {
          var p = reqFn.call(wrapperEl);
          /* Swallow promise rejection (permissions policy, etc.) */
          if (p && typeof p.catch === 'function') p.catch(function () {});
        }
      } catch (e) { /* ignore */ }
    }

    /* Call onResize after the layout paint so the renderer gets the new size */
    requestAnimationFrame(function () { onResize(); });
  }

  /**
   * onFullscreenChange(wrapperEl, cb) — register a fullscreenchange listener
   * that calls cb(isMaximizedNow: boolean) so the page can:
   *   1. Sync button aria-pressed / aria-label
   *   2. Remove .viewer-maximized if the user exited native fullscreen via Esc/OS
   *      (keeps CSS class state and native state in sync).
   */
  function onFullscreenChange(wrapperEl, cb) {
    function handler() {
      /* If the user exited native fullscreen (e.g. Esc key), sync the CSS class */
      if (!_isNativeFullscreen(wrapperEl) && wrapperEl.classList.contains(MAXIMIZED_CLASS)) {
        wrapperEl.classList.remove(MAXIMIZED_CLASS);
      }
      cb(isMaximized(wrapperEl));
    }
    document.addEventListener('fullscreenchange', handler);
    document.addEventListener('webkitfullscreenchange', handler);
    /* Return a cleanup function so callers can deregister when the viewer tears down */
    return function () {
      document.removeEventListener('fullscreenchange', handler);
      document.removeEventListener('webkitfullscreenchange', handler);
    };
  }

  /* ── Export ─────────────────────────────────────────────────────────────── */
  window.ViewerFullscreen = {
    toggle: toggle,
    isMaximized: isMaximized,
    onFullscreenChange: onFullscreenChange,
  };
})();

/* nav_menu.js — shared mobile hamburger nav.
 *
 * Loaded as a plain (non-module) script before each page's own script on all
 * six pages, exactly like shared_inputs.js and viewer_fullscreen.js.
 *
 * The <header> markup is hand-copied and kept byte-identical across pages, so
 * the toggle button is INJECTED here rather than pasted into six files — the
 * headers stay identical and there is one place to change the behavior.
 *
 * Progressive enhancement: if this script never runs, .header-nav remains the
 * horizontally-scrolling link row it has always been. Nothing depends on it.
 *
 * All open/closed state lives in the `nav-open` class on <header>; this file
 * sets no inline styles, so the desktop layout is purely the media query's
 * business and can never be left in a broken inline state.
 */
(function () {
  'use strict';

  /* Keep in sync with the `@media (max-width: 860px)` block in style.css. */
  var BREAKPOINT = 860;

  var BARS_ICON =
    '<svg class="nav-toggle-bars" aria-hidden="true" focusable="false" width="22" height="22" ' +
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">' +
    '<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/>' +
    '<line x1="3" y1="18" x2="21" y2="18"/></svg>';

  var CLOSE_ICON =
    '<svg class="nav-toggle-close" aria-hidden="true" focusable="false" width="22" height="22" ' +
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">' +
    '<line x1="5" y1="5" x2="19" y2="19"/><line x1="19" y1="5" x2="5" y2="19"/></svg>';

  function init() {
    var header = document.querySelector('header');
    if (!header) return;

    var inner = header.querySelector('.header-inner');
    var nav = header.querySelector('.header-nav');
    if (!inner || !nav) return;
    if (inner.querySelector('.nav-toggle')) return;   // already wired

    if (!nav.id) nav.id = 'headerNav';

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'nav-toggle';
    btn.setAttribute('aria-label', 'Menu');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', nav.id);
    btn.innerHTML = BARS_ICON + CLOSE_ICON;
    inner.appendChild(btn);

    function isOpen() {
      return header.classList.contains('nav-open');
    }

    function open() {
      header.classList.add('nav-open');
      btn.setAttribute('aria-expanded', 'true');
      btn.setAttribute('aria-label', 'Close menu');
    }

    function close(opts) {
      if (!isOpen()) return;
      header.classList.remove('nav-open');
      btn.setAttribute('aria-expanded', 'false');
      btn.setAttribute('aria-label', 'Menu');
      if (opts && opts.focusButton) btn.focus();
    }

    btn.addEventListener('click', function (e) {
      e.stopPropagation();          // don't trip the outside-click handler below
      if (isOpen()) close();
      else open();
    });

    /* Tapping a destination closes immediately. The navigation itself would
       replace the page anyway, but same-page links (and the active link) would
       otherwise leave the panel hanging open. */
    nav.addEventListener('click', function (e) {
      if (e.target.closest('a')) close();
    });

    /* Outside click / tap. Listens on document so it also catches taps on the
       page body behind the panel. */
    document.addEventListener('click', function (e) {
      if (!isOpen()) return;
      if (!nav.contains(e.target) && !btn.contains(e.target)) close();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen()) {
        /* Only claim Escape when the menu is actually open, so it never steals
           the key from the 3D viewer / lightbox on gallery + figure_maker. */
        e.stopPropagation();
        close({ focusButton: true });
      }
    });

    /* Rotating a phone to landscape (or resizing a desktop window down and back)
       must not strand the panel in its open state above the breakpoint. */
    window.addEventListener('resize', function () {
      if (window.innerWidth > BREAKPOINT) close();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

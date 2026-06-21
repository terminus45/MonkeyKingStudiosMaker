/* auth_client.js — Dev auth shim + authenticated fetch helper.
 * Plain script (non-module), loaded before each page's own script.
 * Exposes window.Auth.
 *
 * ==========================================================================
 * PHASE 1 (DEV SHIM)
 * In dev mode the server accepts either:
 *   X-Dev-User: <auth_id>         (used by this shim)
 *   Authorization: Bearer dev:<auth_id>
 *
 * The auth_id is stored in localStorage so it persists across page loads.
 * Call Auth.devSignIn('any-user-id') to set it, Auth.devSignOut() to clear.
 *
 * ==========================================================================
 * HOW TO REPLACE WITH A REAL VENDOR (Phase 2 / build time)
 *
 * Option A — Clerk (recommended for this no-build-step frontend):
 *   1. Add to each page's <head> (before this script):
 *        <script src="https://<clerk-frontend-api>/npm/@clerk/clerk-js@5/dist/clerk.browser.js"
 *                data-clerk-publishable-key="pk_live_..."></script>
 *   2. Replace the body of this module with:
 *        window.Auth = (function () {
 *          async function ready()   { await Clerk.load(); return Clerk; }
 *          async function token()   { return (await ready()).session?.getToken() ?? null; }
 *          async function authFetch(url, opts) {
 *            var t = await token();
 *            var headers = new Headers((opts || {}).headers || {});
 *            if (t) headers.set('Authorization', 'Bearer ' + t);
 *            return fetch(url, Object.assign({}, opts || {}, { headers: headers }));
 *          }
 *          function isSignedIn() { return !!Clerk?.user; }
 *          function getAuthId()  { return Clerk?.user?.id ?? null; }
 *          function getEmail()   { return Clerk?.user?.primaryEmailAddress?.emailAddress ?? null; }
 *          function getDisplayName() { return Clerk?.user?.fullName ?? Clerk?.user?.id ?? 'You'; }
 *          return { ready, token, authFetch, isSignedIn, getAuthId, getEmail, getDisplayName,
 *                   signIn: () => Clerk.openSignIn(), signOut: () => Clerk.signOut() };
 *        })();
 *   3. Remove all localStorage / dev-header logic below.
 *
 * Option B — Supabase Auth:
 *   Similar pattern using supabase-js from esm.sh CDN; session.access_token as the JWT.
 * ==========================================================================
 */

window.Auth = (function () {
  'use strict';

  var LS_KEY = 'monkeyking_dev_auth_id';
  var _cachedBalance = null;
  var _balanceListeners = [];

  /* ── Identity ── */

  function getAuthId() {
    try { return localStorage.getItem(LS_KEY) || null; } catch (e) { return null; }
  }

  function isSignedIn() {
    return !!getAuthId();
  }

  function getDisplayName() {
    return getAuthId() || 'You';
  }

  function getEmail() {
    return null; // dev shim has no email
  }

  /* devSignIn / devSignOut — call from browser console or account page */
  function devSignIn(authId) {
    if (!authId || typeof authId !== 'string') {
      console.warn('[Auth] devSignIn requires a non-empty string auth id');
      return;
    }
    try { localStorage.setItem(LS_KEY, authId); } catch (e) { /* quota */ }
    window.dispatchEvent(new CustomEvent('auth:changed', { detail: { signedIn: true } }));
  }

  function devSignOut() {
    try { localStorage.removeItem(LS_KEY); } catch (e) { /* quota */ }
    _cachedBalance = null;
    window.dispatchEvent(new CustomEvent('auth:changed', { detail: { signedIn: false } }));
  }

  /* ── Auth-aware fetch ── */

  function authFetch(url, opts) {
    var id = getAuthId();
    var headers = new Headers((opts && opts.headers) ? opts.headers : {});
    if (id) {
      headers.set('X-Dev-User', id);
    }
    return fetch(url, Object.assign({}, opts || {}, { headers: headers }));
  }

  /* ── Wallet balance ── */

  /**
   * Fetch the current coin balance from GET /wallet.
   * Returns a Promise resolving to { balance: Number } or null when signed out / error.
   * Result is cached in-memory; pass force=true to bypass cache.
   */
  function fetchBalance(force) {
    if (!isSignedIn()) return Promise.resolve(null);
    if (!force && _cachedBalance !== null) return Promise.resolve({ balance: _cachedBalance });

    return authFetch('/wallet')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (data && typeof data.balance === 'number') {
          _cachedBalance = data.balance;
          _notifyBalanceListeners(data.balance);
          return data;
        }
        return null;
      })
      .catch(function () { return null; });
  }

  function onBalanceChange(fn) {
    _balanceListeners.push(fn);
    // Return an unsubscribe function
    return function () {
      _balanceListeners = _balanceListeners.filter(function (f) { return f !== fn; });
    };
  }

  function _notifyBalanceListeners(balance) {
    _balanceListeners.forEach(function (fn) {
      try { fn(balance); } catch (e) { /* ignore listener errors */ }
    });
  }

  /* ── Header chip initialisation ── */

  /**
   * initChip(chipEl) — populate the #authChip element on each page header.
   * Call once DOM is ready. If BILLING_ENABLED is off, GET /wallet returns 404
   * and the chip is silently hidden (does not break the page).
   */
  function initChip(chipEl) {
    if (!chipEl) return;

    if (!isSignedIn()) {
      _renderSignInChip(chipEl);
      return;
    }

    // Render skeleton while we fetch balance
    chipEl.innerHTML = '<span class="auth-chip-skeleton"></span>';
    chipEl.style.display = 'flex';

    fetchBalance(true)
      .then(function (data) {
        if (data && typeof data.balance === 'number') {
          _renderBalanceChip(chipEl, data.balance);
        } else {
          // Wallet fetch failed (billing off, or server error) — show sign-in chip
          _renderSignInChip(chipEl);
        }
      })
      .catch(function () {
        _renderSignInChip(chipEl);
      });

    // Update chip when balance changes (e.g. after successful purchase)
    onBalanceChange(function (balance) {
      _renderBalanceChip(chipEl, balance);
    });
  }

  function _renderSignInChip(chipEl) {
    chipEl.className = 'auth-chip auth-chip--signin';
    chipEl.setAttribute('href', 'account.html?intent=signin');
    chipEl.setAttribute('aria-label', 'Sign in to your account');
    chipEl.innerHTML =
      '<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>' +
        '<circle cx="12" cy="7" r="4"/>' +
      '</svg>' +
      '<span>Sign in</span>';
  }

  function _renderBalanceChip(chipEl, balance) {
    var formatted = balance.toLocaleString();
    chipEl.className = 'auth-chip auth-chip--balance';
    chipEl.setAttribute('href', 'account.html');
    chipEl.setAttribute('aria-label', formatted + ' coins — view account');
    chipEl.innerHTML =
      '<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="color:#ff6b35">' +
        '<circle cx="12" cy="12" r="10" opacity=".25"/>' +
        '<text x="12" y="16" text-anchor="middle" font-size="10" font-weight="700" fill="#ff6b35">¢</text>' +
      '</svg>' +
      '<span class="auth-chip-num" style="font-family:\'Space Mono\',monospace">' + formatted + '</span>' +
      '<span class="auth-chip-label"> coins</span>';
  }

  return {
    isSignedIn:     isSignedIn,
    getAuthId:      getAuthId,
    getEmail:       getEmail,
    getDisplayName: getDisplayName,
    devSignIn:      devSignIn,
    devSignOut:     devSignOut,
    authFetch:      authFetch,
    fetchBalance:   fetchBalance,
    onBalanceChange: onBalanceChange,
    initChip:       initChip,
  };
})();

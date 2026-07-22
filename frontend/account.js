/* account.js — Account / Wallet page logic.
 *
 * Depends on: auth_client.js (window.Auth), loaded first.
 * No build step; plain script.
 *
 * Responsibilities:
 *   1. Detect ?return=success or ?return=cancel and show the correct return card.
 *   2. On success: poll GET /wallet until balance increases, then display it.
 *   3. On main view: load balance + transaction history from GET /wallet.
 *   4. Load package catalog from GET /billing/packages and render radio cards.
 *   5. On checkout: POST /billing/checkout and redirect to Stripe URL.
 *   6. Initialise the header auth chip via Auth.initChip().
 *   7. Handle ?intent=signin (dev shim: prompt for an auth_id in the console).
 */

(function () {
  'use strict';

  var API = window.location.origin;

  // ── Helpers ──────────────────────────────────────────────────────────────

  function qs(sel) { return document.querySelector(sel); }

  function formatDate(isoStr) {
    if (!isoStr) return '';
    try {
      var d = new Date(isoStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch (e) { return isoStr; }
  }

  function formatCoins(n) {
    return Number(n).toLocaleString();
  }

  // ── Status dot (ping /billing/packages as a proxy for server liveness) ──

  function initStatusDot() {
    var dot   = qs('#statusDot');
    var label = qs('#statusLabel');
    if (!dot) return;
    fetch(API + '/billing/packages', { method: 'GET' })
      .then(function (r) {
        if (r.ok) {
          dot.className = 'status-dot ok';
          if (label) label.textContent = 'Connected';
        } else {
          dot.className = 'status-dot error';
          if (label) label.textContent = 'Error';
        }
      })
      .catch(function () {
        // Billing may be off — try a simple healthcheck instead
        fetch(API + '/languages')
          .then(function (r) {
            dot.className = r.ok ? 'status-dot ok' : 'status-dot error';
            if (label) label.textContent = r.ok ? 'Connected' : 'Error';
          })
          .catch(function () {
            dot.className = 'status-dot error';
            if (label) label.textContent = 'Offline';
          });
      });
  }

  // ── Wallet fetch ──────────────────────────────────────────────────────────

  function fetchWallet() {
    return Auth.authFetch(API + '/wallet')
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); });
  }

  // ── Render balance ────────────────────────────────────────────────────────

  function renderBalance(balance, history) {
    var numEl = qs('#balanceNumber');
    if (!numEl) return;

    numEl.textContent = formatCoins(balance);
    numEl.className = 'account-balance-number' + (balance === 0 ? ' zero' : '');

    // Last credited line
    var lastEl = qs('#lastCreditedLine');
    if (lastEl && history && history.length > 0) {
      var purchases = history.filter(function (h) { return h.kind === 'purchase'; });
      if (purchases.length > 0) {
        var last = purchases[0];
        lastEl.textContent = 'Last credited: ' + formatDate(last.created_at) +
          ' · +' + formatCoins(last.amount) + ' coins';
      } else {
        lastEl.textContent = 'No credits yet.';
      }
    } else if (lastEl) {
      lastEl.textContent = 'No credits yet.';
    }
  }

  // ── Render transaction history ────────────────────────────────────────────

  function renderHistory(history) {
    var list = qs('#txnList');
    if (!list) return;
    list.innerHTML = '';

    if (!history || history.length === 0) {
      list.innerHTML = '<p class="account-txn-empty">No transactions yet.<br>' +
        '<span style="font-size:.8rem">Buy some coins below to get started!</span></p>';
      return;
    }

    history.forEach(function (row) {
      var isCredit = row.kind === 'purchase' || row.kind === 'refund' || row.kind === 'adjust';
      var amtSign  = isCredit ? '+' : '';
      var chipCls  = isCredit ? 'account-credit-chip' : 'account-debit-chip';
      var desc = row.reason
        ? row.reason.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); })
        : row.kind;

      var div = document.createElement('div');
      div.className = 'account-txn-row';
      div.innerHTML =
        '<span class="account-txn-date">' + formatDate(row.created_at) + '</span>' +
        '<span class="account-txn-desc">' + desc + '</span>' +
        '<span class="' + chipCls + '">' + amtSign + formatCoins(Math.abs(row.amount)) + '</span>';
      list.appendChild(div);
    });
  }

  // ── Load main account data ────────────────────────────────────────────────

  function loadAccount() {
    if (!Auth.isSignedIn()) {
      renderUnauthenticated();
      return;
    }

    fetchWallet()
      .then(function (data) {
        renderBalance(data.balance, data.history);
        renderHistory(data.history);
      })
      .catch(function (status) {
        var numEl = qs('#balanceNumber');
        if (numEl) {
          numEl.innerHTML =
            '— <button class="account-retry-btn" onclick="window.location.reload()" ' +
            'aria-label="Retry loading balance">Retry</button>';
          numEl.className = 'account-balance-number account-balance-error';
        }
        var list = qs('#txnList');
        if (list) {
          list.innerHTML = '<p class="account-txn-empty" style="color:var(--terracotta)">' +
            (status === 503 ? 'Server error — please try again.' :
             status === 401 ? 'Not signed in.' : 'Failed to load transactions.') + '</p>';
        }
      });
  }

  function renderUnauthenticated() {
    var numEl = qs('#balanceNumber');
    if (numEl) numEl.textContent = '—';
    var list = qs('#txnList');
    if (list) {
      list.innerHTML = '<p class="account-txn-empty"><a href="account.html?intent=signin" ' +
        'style="color:var(--mustard)">Sign in</a> to view your balance.</p>';
    }
    var nudge = qs('#signInNudge');
    if (nudge) nudge.style.display = 'block';
    var checkoutBtn = qs('#checkoutBtn');
    if (checkoutBtn) {
      checkoutBtn.disabled = true;
      checkoutBtn.setAttribute('aria-disabled', 'true');
    }
  }

  // ── Package catalog ───────────────────────────────────────────────────────

  var _selectedPkg = null;

  function loadPackages() {
    var group    = qs('#pkgGroup');
    var loading  = qs('#pkgLoading');
    if (!group) return;

    fetch(API + '/billing/packages')
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (data) {
        if (loading) loading.remove();

        var packages = data.packages || [];
        if (packages.length === 0) {
          group.innerHTML = '<p style="color:var(--muted);font-size:.85rem">No packages available.</p>';
          return;
        }

        packages.forEach(function (pkg, i) {
          var card = document.createElement('div');
          card.className = 'pkg-card';
          card.setAttribute('role', 'radio');
          card.setAttribute('aria-checked', 'false');
          card.setAttribute('tabindex', i === 0 ? '0' : '-1');
          card.dataset.pkgId = pkg.id;

          var priceDollars = (pkg.price_cents / 100).toFixed(2);
          var isPopular = pkg.id === 'p10';

          card.innerHTML =
            '<div class="pkg-card-row1">' +
              '<span class="pkg-coins">' + formatCoins(pkg.coins) + ' coins</span>' +
              '<span class="pkg-price">$' + priceDollars + '</span>' +
            '</div>' +
            '<div class="pkg-card-row2">' +
              '<span class="pkg-desc">' + (pkg.tag || '') + '</span>' +
              (isPopular ? '<span class="pkg-star-tag">Most popular</span>' : '') +
            '</div>';

          card.addEventListener('click', function () { selectPackage(card, pkg); });
          card.addEventListener('keydown', function (e) {
            if (e.key === ' ' || e.key === 'Enter') {
              e.preventDefault();
              selectPackage(card, pkg);
            }
            // Arrow key navigation within the radiogroup
            var cards = Array.from(group.querySelectorAll('.pkg-card'));
            var idx   = cards.indexOf(card);
            if (e.key === 'ArrowDown' && idx < cards.length - 1) {
              e.preventDefault();
              cards[idx + 1].focus();
            } else if (e.key === 'ArrowUp' && idx > 0) {
              e.preventDefault();
              cards[idx - 1].focus();
            }
          });

          group.appendChild(card);
        });
      })
      .catch(function () {
        if (loading) loading.textContent = 'Could not load packages.';
      });
  }

  function selectPackage(card, pkg) {
    _selectedPkg = pkg;
    var cards = document.querySelectorAll('.pkg-card');
    cards.forEach(function (c) {
      c.setAttribute('aria-checked', 'false');
      c.setAttribute('tabindex', '-1');
    });
    card.setAttribute('aria-checked', 'true');
    card.setAttribute('tabindex', '0');

    var btn = qs('#checkoutBtn');
    if (btn) {
      btn.disabled = false;
      btn.setAttribute('aria-disabled', 'false');
      var priceDollars = (pkg.price_cents / 100).toFixed(2);
      btn.setAttribute('aria-label',
        'Checkout with Stripe for ' + formatCoins(pkg.coins) + ' coins at $' + priceDollars);
    }
  }

  // ── Checkout ──────────────────────────────────────────────────────────────

  function initCheckout() {
    var btn = qs('#checkoutBtn');
    if (!btn) return;

    btn.addEventListener('click', function () {
      if (!_selectedPkg) return;
      if (!Auth.isSignedIn()) {
        window.location.href = 'account.html?intent=signin';
        return;
      }

      var errEl = qs('#buyError');
      if (errEl) { errEl.textContent = ''; errEl.classList.remove('visible'); }

      btn.disabled = true;
      btn.setAttribute('aria-disabled', 'true');
      btn.textContent = 'Loading…';

      Auth.authFetch(API + '/billing/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ package_id: _selectedPkg.id }),
      })
        .then(function (r) { return r.ok ? r.json() : r.json().then(function (e) { return Promise.reject(e); }); })
        .then(function (data) {
          if (data.url) {
            window.location.href = data.url;
          } else {
            throw new Error('No checkout URL returned.');
          }
        })
        .catch(function (err) {
          btn.disabled = false;
          btn.setAttribute('aria-disabled', 'false');
          btn.textContent = 'Checkout with Stripe →';
          if (errEl) {
            var msg = (err && (err.detail || err.message)) || 'Checkout failed. Please try again.';
            errEl.textContent = msg;
            errEl.classList.add('visible');
          }
        });
    });
  }

  // ── Return state: ?return=success ─────────────────────────────────────────

  function handleReturnSuccess() {
    var view    = qs('#accountView');
    var section = qs('#returnSuccess');
    if (view)    view.style.display    = 'none';
    if (section) section.style.display = '';

    if (!Auth.isSignedIn()) {
      var slot = qs('#returnBalanceSlot');
      if (slot) slot.innerHTML = '<p style="color:var(--muted);font-size:.9rem">Sign in to view your balance.</p>';
      return;
    }

    // Poll GET /wallet every 2 s until balance differs from a baseline (or 30 s pass).
    // We don't know the pre-purchase balance, so we poll for up to 30 s and display
    // whatever balance we find after the first successful fetch.
    var attempts  = 0;
    var maxAttempts = 15; // 15 × 2s = 30s
    var resolvedBalance = null;

    function poll() {
      attempts++;
      fetchWallet()
        .then(function (data) {
          if (resolvedBalance === null || data.balance !== resolvedBalance) {
            // Balance has settled (or this is our first read) — display it.
            resolvedBalance = data.balance;
            showCreditedBalance(data.balance);
          } else if (attempts < maxAttempts) {
            setTimeout(poll, 2000);
          } else {
            // Timeout — show fallback message
            var slot = qs('#returnBalanceSlot');
            if (slot) {
              slot.innerHTML =
                '<p style="color:var(--muted);font-size:.9rem">' +
                'Coins will appear shortly — ' +
                '<button onclick="window.location.reload()" style="background:none;border:none;' +
                'color:var(--mustard);cursor:pointer;font-family:inherit;font-size:.9rem;padding:0">' +
                'refresh this page</button> if needed.</p>';
            }
          }
        })
        .catch(function () {
          if (attempts < maxAttempts) setTimeout(poll, 2000);
        });
    }

    // Kick off first poll immediately, then continue at 2 s intervals if unchanged.
    fetchWallet()
      .then(function (data) {
        resolvedBalance = data.balance;
        // Don't show the balance immediately — wait one poll cycle in case the
        // webhook hasn't fired yet (this is the most common case).
        setTimeout(poll, 2000);
      })
      .catch(function () { setTimeout(poll, 2000); });
  }

  function showCreditedBalance(balance) {
    var slot = qs('#returnBalanceSlot');
    if (!slot) return;
    slot.innerHTML =
      '<div class="balance-credited">' + formatCoins(balance) + '</div>' +
      '<div class="balance-credited-label">coins</div>';
  }

  // ── Return state: ?return=cancel ──────────────────────────────────────────

  function handleReturnCancel() {
    var view    = qs('#accountView');
    var section = qs('#returnCancel');
    if (view)    view.style.display    = 'none';
    if (section) section.style.display = '';
  }

  // ── Dev sign-in prompt (?intent=signin) ───────────────────────────────────

  function handleSignInIntent() {
    // In dev mode, prompt for an auth_id and store it.
    // In production this would be replaced by the Clerk/Supabase hosted redirect.
    var id = prompt(
      '[DEV MODE] Enter any user ID to sign in (e.g. "user_alice"):\n\n' +
      'This dev shim stores the ID in localStorage. Replace with real auth in Phase 2.'
    );
    if (id && id.trim()) {
      Auth.devSignIn(id.trim());
      // Remove the intent param and reload
      var url = new URL(window.location.href);
      url.searchParams.delete('intent');
      window.location.replace(url.toString());
    } else {
      // User cancelled — go to app
      window.location.href = 'book_builder.html';
    }
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', function () {
    // Header auth chip
    Auth.initChip(qs('#authChip'));

    initStatusDot();

    var params = new URLSearchParams(window.location.search);

    // Handle dev sign-in intent
    if (params.get('intent') === 'signin') {
      handleSignInIntent();
      return; // page will reload
    }

    // Handle Stripe return states
    var ret = params.get('return');
    if (ret === 'success') {
      handleReturnSuccess();
      return;
    }
    if (ret === 'cancel') {
      handleReturnCancel();
      return;
    }

    // Normal account view
    loadAccount();
    loadPackages();
    initCheckout();
  });

})();

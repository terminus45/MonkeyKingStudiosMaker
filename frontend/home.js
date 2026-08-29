/* home.js — landing page. Plain (non-module) script, loaded after
   shared_inputs.js at the end of <body>, so #homeDescInput and the status
   elements already exist and no DOMContentLoaded wrapper is needed.
   Spec: design-specs/home-tab.md §4, §8. */
'use strict';

const API = '';   // same-origin

const statusDot   = document.getElementById('statusDot');
const statusLabel = document.getElementById('statusLabel');

// ── Shared inputs ────────────────────────────────────────────────────────────
// Home binds only `character`. `story` and `style` are left untouched in the
// store — bindFields ignores any field absent from the map.
function wireSharedInputListeners() {
  SharedInputs.bindFields(
    { character: 'homeDescInput' },
    { debounce: 300 }
  );
}

// ── Health check ─────────────────────────────────────────────────────────────
// Deliberately simpler than the sibling pages': /health returns only
// {"status":"ok"}, so there is no model name to append, and Home has no
// generation feature whose availability the label would qualify.
async function checkHealth() {
  try {
    await fetch(`${API}/health`);
    statusDot.className = 'status-dot ok';
    statusLabel.textContent = 'Connected';
  } catch {
    statusDot.className = 'status-dot error';
    statusLabel.textContent = 'Server offline';
  }
}

// ── Init ─────────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  wireSharedInputListeners();
})();

setInterval(checkHealth, 30_000);

/* settings.js */
'use strict';

const API = window.location.origin;

// ── DOM refs ────────────────────────────────────────────────────────────────
const statusDot       = document.getElementById('statusDot');
const statusLabel     = document.getElementById('statusLabel');
const settingsSaveAll = document.getElementById('settingsSaveAll');
const settingsSaveLabel = document.getElementById('settingsSaveLabel');
const settingsSpinner = document.getElementById('settingsSpinner');
const settingsStatusMsg = document.getElementById('settingsStatusMsg');

// Key row configuration
const KEY_ROWS = [
  { key: 'ANTHROPIC_API_KEY', inputId: 'key-anthropic', chipId: 'key-anthropic-status' },
  { key: 'GEMINI_API_KEY',    inputId: 'key-gemini',    chipId: 'key-gemini-status'    },
  { key: 'MESHY_API_KEY',     inputId: 'key-meshy',     chipId: 'key-meshy-status'     },
];

// ── Health check ────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const res  = await fetch(`${API}/health`);
    const data = await res.json();
    statusDot.className    = 'status-dot ok';
    statusLabel.textContent = `Connected · ${data.loaded_model?.split('/').pop() ?? 'unknown'}`;
  } catch {
    statusDot.className    = 'status-dot error';
    statusLabel.textContent = 'Server offline';
  }
}

// ── Chip state helpers ──────────────────────────────────────────────────────
function setChipState(chipEl, keyData) {
  if (!keyData) {
    chipEl.dataset.state  = 'unknown';
    chipEl.textContent    = '';
    return;
  }

  if (keyData.set && keyData.source === 'env') {
    chipEl.dataset.state  = 'set-env';
    chipEl.textContent    = '✓ Set (env)';
  } else if (keyData.set && keyData.source === 'config') {
    chipEl.dataset.state  = 'set-config';
    chipEl.textContent    = '✓ Set (config)';
  } else {
    chipEl.dataset.state  = 'not-set';
    chipEl.textContent    = 'Not set';
  }
}

// ── Render key data from API response ───────────────────────────────────────
function applyKeyData(keysObj) {
  KEY_ROWS.forEach(({ key, inputId, chipId }) => {
    const inputEl = document.getElementById(inputId);
    const chipEl  = document.getElementById(chipId);
    const keyData = keysObj[key];

    // Set placeholder to masked value; never prefill the real secret
    if (keyData && keyData.masked) {
      inputEl.placeholder = keyData.masked;
    }

    setChipState(chipEl, keyData);
  });
}

// ── Load keys on page load ──────────────────────────────────────────────────
async function loadKeys() {
  try {
    const res = await fetch(`${API}/settings/keys`);
    if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);
    const data = await res.json();
    applyKeyData(data);
  } catch (err) {
    showStatusMsg(`Could not load key status: ${err.message}`, 'error');
  }
}

// ── Save All ─────────────────────────────────────────────────────────────────
settingsSaveAll.addEventListener('click', async () => {
  hideStatusMsg();
  setSaving(true);

  // Collect only inputs with non-empty values
  const payload = {};
  KEY_ROWS.forEach(({ key, inputId }) => {
    const val = document.getElementById(inputId).value.trim();
    if (val !== '') payload[key] = val;
  });

  try {
    const res = await fetch(`${API}/settings/keys`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);
    const data = await res.json();

    // Clear input values (never show secrets in the field)
    KEY_ROWS.forEach(({ inputId }) => { document.getElementById(inputId).value = ''; });

    applyKeyData(data);
    showStatusMsg('Keys saved successfully!', 'success');
  } catch (err) {
    showStatusMsg(`Save failed: ${err.message}`, 'error');
  } finally {
    setSaving(false);
  }
});

function setSaving(on) {
  settingsSaveAll.disabled = on;
  if (on) {
    settingsSaveLabel.classList.add('hidden');
    settingsSpinner.classList.remove('hidden');
  } else {
    settingsSaveLabel.classList.remove('hidden');
    settingsSpinner.classList.add('hidden');
  }
}

// ── Status message ───────────────────────────────────────────────────────────
let _msgTimer = null;

function showStatusMsg(text, type) {
  settingsStatusMsg.textContent = text;
  settingsStatusMsg.className   = type === 'success' ? 'settings-success-msg' : 'cg-error';
  if (_msgTimer) clearTimeout(_msgTimer);
  _msgTimer = setTimeout(hideStatusMsg, 4000);
}

function hideStatusMsg() {
  settingsStatusMsg.textContent = '';
  settingsStatusMsg.className   = 'cg-error hidden';
}

// ── Eye (show/hide) toggle ────────────────────────────────────────────────────
document.querySelectorAll('.settings-eye-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const targetId  = btn.dataset.target;
    const inputEl   = document.getElementById(targetId);
    const isPressed = btn.getAttribute('aria-pressed') === 'true';

    if (isPressed) {
      // Hide key
      inputEl.type = 'password';
      btn.setAttribute('aria-pressed', 'false');
      btn.setAttribute('aria-label', 'Show API key');
      btn.querySelector('.eye-open').classList.remove('hidden');
      btn.querySelector('.eye-closed').classList.add('hidden');
    } else {
      // Show key
      inputEl.type = 'text';
      btn.setAttribute('aria-pressed', 'true');
      btn.setAttribute('aria-label', 'Hide API key');
      btn.querySelector('.eye-open').classList.add('hidden');
      btn.querySelector('.eye-closed').classList.remove('hidden');
    }
  });
});

// ── Clear (✕) button ─────────────────────────────────────────────────────────
document.querySelectorAll('.settings-clear-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const keyName = btn.dataset.key;
    if (!confirm(`Clear the ${keyName} key? This cannot be undone.`)) return;

    btn.disabled = true;
    try {
      // Clearing = POST the key as an empty string (no DELETE endpoint exists).
      const res = await fetch(`${API}/settings/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [keyName]: '' }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);

      // Refresh all key statuses
      await loadKeys();
      showStatusMsg(`${keyName} cleared.`, 'success');
    } catch (err) {
      showStatusMsg(`Clear failed: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
    }
  });
});

// ── Init ─────────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  await loadKeys();
})();

setInterval(checkHealth, 30_000);

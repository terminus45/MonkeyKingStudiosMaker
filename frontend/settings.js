/* settings.js */
'use strict';

const API = window.location.origin;

// ── DOM refs ────────────────────────────────────────────────────────────────
const statusDot          = document.getElementById('statusDot');
const statusLabel        = document.getElementById('statusLabel');
const settingsSaveAll    = document.getElementById('settingsSaveAll');
const settingsSaveLabel  = document.getElementById('settingsSaveLabel');
const settingsSpinner    = document.getElementById('settingsSpinner');
const settingsStatusMsg  = document.getElementById('settingsStatusMsg');
const settingsCgModel    = document.getElementById('settingsCgModel');
const settingsCgModelStatus = document.getElementById('settingsCgModelStatus');
const settingsCgAspect   = document.getElementById('settingsCgAspect');
const settingsCgAspectStatus = document.getElementById('settingsCgAspectStatus');
const settingsLang       = document.getElementById('settingsLang');
const settingsLangStatus = document.getElementById('settingsLangStatus');
const settingsPages      = document.getElementById('settingsPages');
const settingsPagesStatus = document.getElementById('settingsPagesStatus');

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
    statusLabel.textContent = 'Connected';
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

// ── Gemini model select — Generation Settings ─────────────────────────────────
const CG_DRAFT_KEY = 'monkeyking_cg_draft';

async function loadGeminiModels() {
  try {
    const res = await fetch(`${API}/gemini/models`);
    if (!res.ok) return; // leave hardcoded fallback options in place
    const data = await res.json();
    const models = data.models || [];
    if (models.length === 0) return;

    // Rebuild the select with API data
    settingsCgModel.innerHTML = '';
    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name || m.id;
      settingsCgModel.appendChild(opt);
    });

    // Default to Imagen 4 Fast (cheapest), falling back to the first imagen model;
    // restore saved draft value if available.
    const imagenOpt = models.find(m => m.id === 'imagen-4.0-fast-generate-001')
                   || models.find(m => m.type === 'imagen');
    if (imagenOpt) settingsCgModel.value = imagenOpt.id;

    // Restore from draft — overrides the default if a saved value matches
    try {
      const raw = localStorage.getItem(CG_DRAFT_KEY);
      if (raw) {
        const draft = JSON.parse(raw);
        if (draft.model) {
          settingsCgModel.value = draft.model;
          // If the saved value didn't match any option, fall back to the default
          if (settingsCgModel.value !== draft.model && imagenOpt) {
            settingsCgModel.value = imagenOpt.id;
          }
        }
      }
    } catch { /* corrupted draft */ }
  } catch {
    // Leave hardcoded options in place — silently ignore (matches CG behavior)
  }
}

let _modelSavedTimer = null;

function showModelSavedChip() {
  settingsCgModelStatus.dataset.state = 'set-config';
  settingsCgModelStatus.textContent   = 'Saved';
  if (_modelSavedTimer) clearTimeout(_modelSavedTimer);
  _modelSavedTimer = setTimeout(() => {
    settingsCgModelStatus.dataset.state = 'unknown';
    settingsCgModelStatus.textContent   = '';
  }, 2000);
}

// Persist model selection to the shared draft (read-merge-write preserving ar)
settingsCgModel.addEventListener('change', () => {
  try {
    const raw   = localStorage.getItem(CG_DRAFT_KEY);
    const draft = raw ? JSON.parse(raw) : {};
    draft.model = settingsCgModel.value;
    localStorage.setItem(CG_DRAFT_KEY, JSON.stringify(draft));
  } catch { /* quota / private-mode */ }
  showModelSavedChip();
});

// ── Aspect ratio select — Generation Settings ─────────────────────────────────
let _aspectSavedTimer = null;

function showAspectSavedChip() {
  settingsCgAspectStatus.dataset.state = 'set-config';
  settingsCgAspectStatus.textContent   = 'Saved';
  if (_aspectSavedTimer) clearTimeout(_aspectSavedTimer);
  _aspectSavedTimer = setTimeout(() => {
    settingsCgAspectStatus.dataset.state = 'unknown';
    settingsCgAspectStatus.textContent   = '';
  }, 2000);
}

// Restore the saved aspect ratio on load (default 3:4 from the HTML stays if none).
function restoreAspect() {
  try {
    const raw = localStorage.getItem(CG_DRAFT_KEY);
    if (!raw) return;
    const draft = JSON.parse(raw);
    if (draft.ar) {
      settingsCgAspect.value = draft.ar;
      // If the saved value didn't match any option, fall back to the default
      if (settingsCgAspect.value !== draft.ar) settingsCgAspect.value = '3:4';
    }
  } catch { /* corrupted draft */ }
}

// Persist aspect selection to the shared draft (read-merge-write preserving model)
settingsCgAspect.addEventListener('change', () => {
  try {
    const raw   = localStorage.getItem(CG_DRAFT_KEY);
    const draft = raw ? JSON.parse(raw) : {};
    draft.ar = settingsCgAspect.value;
    localStorage.setItem(CG_DRAFT_KEY, JSON.stringify(draft));
  } catch { /* quota / private-mode */ }
  showAspectSavedChip();
});

// ── Storybook language select — Generation Settings ───────────────────────────
const LANG_KEY = 'monkeyking_bb_lang';
let _langSavedTimer = null;

function showLangSavedChip() {
  settingsLangStatus.dataset.state = 'set-config';
  settingsLangStatus.textContent   = 'Saved';
  if (_langSavedTimer) clearTimeout(_langSavedTimer);
  _langSavedTimer = setTimeout(() => {
    settingsLangStatus.dataset.state = 'unknown';
    settingsLangStatus.textContent   = '';
  }, 2000);
}

// Restore the saved storybook language on load (default zh when absent).
function restoreLang() {
  try {
    const stored = localStorage.getItem(LANG_KEY);
    if (stored) {
      settingsLang.value = stored;
      // If the stored value isn't one of the 3 options, fall back to zh
      if (settingsLang.value !== stored) settingsLang.value = 'zh';
    } else {
      settingsLang.value = 'zh';
    }
  } catch { /* quota / private-mode */ }
}

// Persist language selection to its own key (separate from monkeyking_cg_draft)
settingsLang.addEventListener('change', () => {
  try {
    localStorage.setItem(LANG_KEY, settingsLang.value);
  } catch { /* quota / private-mode */ }
  showLangSavedChip();
});

// ── Book length select — Generation Settings ──────────────────────────────────
const PAGES_KEY = 'monkeyking_bb_pages';
let _pagesSavedTimer = null;

function showPagesSavedChip() {
  settingsPagesStatus.dataset.state = 'set-config';
  settingsPagesStatus.textContent   = 'Saved';
  if (_pagesSavedTimer) clearTimeout(_pagesSavedTimer);
  _pagesSavedTimer = setTimeout(() => {
    settingsPagesStatus.dataset.state = 'unknown';
    settingsPagesStatus.textContent   = '';
  }, 2000);
}

// Restore the saved page count on load (default 11 when absent).
// Applies to new decompose only; open books keep their existing length.
function restorePages() {
  try {
    const stored = localStorage.getItem(PAGES_KEY);
    if (stored) {
      settingsPages.value = stored;
      // If the stored value isn't one of the 3 options, fall back to 11
      if (settingsPages.value !== stored) settingsPages.value = '11';
    } else {
      settingsPages.value = '11';
    }
  } catch { /* quota / private-mode */ }
}

// Persist page count selection to its own key
settingsPages.addEventListener('change', () => {
  try {
    localStorage.setItem(PAGES_KEY, settingsPages.value);
  } catch { /* quota / private-mode */ }
  showPagesSavedChip();
});

// ── Init ─────────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  await loadKeys();
  await loadGeminiModels();
  restoreAspect();
  restoreLang();
  restorePages();
})();

setInterval(checkHealth, 30_000);

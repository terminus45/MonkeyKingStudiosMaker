/* character_generator.js */
'use strict';

const API = window.location.origin;

// ── Shared input field map for this page ────────────────────────────────────
// character = cgDescInput (existing), style = cgStyleInput (existing),
// story     = cgStoryInput (new)
const CG_FIELD_MAP = { character: 'cgDescInput', style: 'cgStyleInput', story: 'cgStoryInput' };

// ── DOM refs ────────────────────────────────────────────────────────────────
const statusDot       = document.getElementById('statusDot');
const statusLabel     = document.getElementById('statusLabel');

const cgDescInput     = document.getElementById('cgDescInput');
const cgStoryInput    = document.getElementById('cgStoryInput');
const cgStyleInput    = document.getElementById('cgStyleInput');
const cgStylePresets  = document.getElementById('cgStylePresets');
const cgModelSelect   = document.getElementById('cgModelSelect');
const cgAspectPresets = document.getElementById('cgAspectPresets');

const cgGenerateBtn   = document.getElementById('cgGenerateBtn');
const cgGenerateLabel = document.getElementById('cgGenerateLabel');
const cgSpinner       = document.getElementById('cgSpinner');
const cgErrorMsg      = document.getElementById('cgErrorMsg');

const cgImageFrame    = document.getElementById('cgImageFrame');
const cgEmptyState    = document.getElementById('cgEmptyState');
const cgLoadingState  = document.getElementById('cgLoadingState');
const cgPortraitImg   = document.getElementById('cgPortraitImg');
const cgActionRow     = document.getElementById('cgActionRow');
const cgDownloadBtn   = document.getElementById('cgDownloadBtn');
const cgUseAsCoverBtn = document.getElementById('cgUseAsCoverBtn');

const cgStrip         = document.getElementById('cgStrip');
const cgStripScroll   = document.getElementById('cgStripScroll');
const cgClearStripBtn = document.getElementById('cgClearStripBtn');

// ── State ───────────────────────────────────────────────────────────────────
let thumbCount = 0;
let currentFilename = null;

// ── Health check ────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const res  = await fetch(`${API}/health`);
    const data = await res.json();
    statusDot.className = 'status-dot ok';
    statusLabel.textContent = `Connected · ${data.loaded_model?.split('/').pop() ?? 'unknown'}`;
  } catch {
    statusDot.className = 'status-dot error';
    statusLabel.textContent = 'Server offline';
  }
}

// ── Populate model select from API ──────────────────────────────────────────
async function loadModels() {
  try {
    const res  = await fetch(`${API}/gemini/models`);
    if (!res.ok) return; // leave hardcoded fallback options in place
    const data = await res.json();
    const models = data.models || [];
    if (models.length === 0) return;

    // Rebuild the select with API data
    cgModelSelect.innerHTML = '';
    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name || m.id;
      cgModelSelect.appendChild(opt);
    });

    // Default to first imagen model, then fall back to index 0
    const imagenOpt = models.find(m => m.type === 'imagen');
    if (imagenOpt) {
      cgModelSelect.value = imagenOpt.id;
    }
  } catch {
    // Leave hardcoded options in place — silently ignore
  }
}

// ── Style preset pills ───────────────────────────────────────────────────────
cgStylePresets.addEventListener('click', e => {
  const btn = e.target.closest('.preset');
  if (!btn) return;

  const suffix = btn.dataset.suffix;

  // Deactivate all
  cgStylePresets.querySelectorAll('.preset').forEach(p => p.classList.remove('active'));

  if (suffix === '') {
    // "Clear" — empty the textarea, no active pill
    cgStyleInput.value = '';
  } else {
    btn.classList.add('active');
    cgStyleInput.value = suffix;
  }
  // Patch shared store for style
  SharedInputs.patch({ style: cgStyleInput.value });
  saveCgDraft();
});

// ── Aspect ratio pills (single-select) ───────────────────────────────────────
cgAspectPresets.addEventListener('click', e => {
  const btn = e.target.closest('.ar-btn');
  if (!btn) return;
  cgAspectPresets.querySelectorAll('.ar-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  saveCgDraft();
});

function getSelectedAR() {
  const active = cgAspectPresets.querySelector('.ar-btn.active');
  return active ? active.dataset.ar : '3:4';
}

// ── Draft persistence — keep only non-shared fields (model/ar) ───────────────
const CG_DRAFT_KEY = 'monkeyking_cg_draft';

function saveCgDraft() {
  try {
    const draft = {
      model:  cgModelSelect.value,
      ar:     getSelectedAR(),
      // prompt and style are NOT saved here — they live in SharedInputs
    };
    localStorage.setItem(CG_DRAFT_KEY, JSON.stringify(draft));
  } catch { /* quota / private-mode */ }
}

function restoreCgDraft() {
  try {
    const raw = localStorage.getItem(CG_DRAFT_KEY);
    if (!raw) return;
    const draft = JSON.parse(raw);
    // Only restore model if the option still exists after loadModels() rebuilt the select
    if (draft.model) {
      cgModelSelect.value = draft.model;
      if (cgModelSelect.value !== draft.model) cgModelSelect.selectedIndex = 0;
    }
    if (draft.ar) {
      cgAspectPresets.querySelectorAll('.ar-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.ar === draft.ar);
      });
    }
  } catch { /* corrupted draft */ }
}

// ── Shared inputs — restore from store, wire live-sync ───────────────────────
function restoreSharedInputs() {
  const s = SharedInputs.read();
  // Set values directly — never dispatch synthetic input events
  cgDescInput.value  = s.character;
  cgStoryInput.value = s.story;
  cgStyleInput.value = s.style;

  // Restore active style preset pill
  cgStylePresets.querySelectorAll('.preset').forEach(p => {
    p.classList.toggle('active', p.dataset.suffix !== '' && p.dataset.suffix === s.style);
  });
}

function wireSharedInputListeners() {
  let _charTimer = null, _storyTimer = null, _styleTimer = null;

  cgDescInput.addEventListener('input', () => {
    clearTimeout(_charTimer);
    _charTimer = setTimeout(() => SharedInputs.patch({ character: cgDescInput.value }), 300);
  });

  cgStoryInput.addEventListener('input', () => {
    clearTimeout(_storyTimer);
    _storyTimer = setTimeout(() => SharedInputs.patch({ story: cgStoryInput.value }), 300);
  });

  cgStyleInput.addEventListener('input', () => {
    clearTimeout(_styleTimer);
    _styleTimer = setTimeout(() => SharedInputs.patch({ style: cgStyleInput.value }), 300);
  });

  // Live cross-tab sync
  SharedInputs.onExternalChange(s => {
    cgDescInput.value  = s.character;
    cgStoryInput.value = s.story;
    cgStyleInput.value = s.style;
    // Re-sync active style preset pill
    cgStylePresets.querySelectorAll('.preset').forEach(p => {
      p.classList.toggle('active', p.dataset.suffix !== '' && p.dataset.suffix === s.style);
    });
  });
}

// Debounced save for model/ar changes
let _cgDraftTimer = null;
function debouncedSaveCgDraft() {
  clearTimeout(_cgDraftTimer);
  _cgDraftTimer = setTimeout(saveCgDraft, 300);
}

cgModelSelect.addEventListener('change', saveCgDraft);

// ── State helpers ───────────────────────────────────────────────────────────
function showEmpty() {
  cgEmptyState.classList.remove('hidden');
  cgEmptyState.removeAttribute('aria-hidden');
  cgLoadingState.classList.add('hidden');
  cgLoadingState.setAttribute('aria-hidden', 'true');
  cgPortraitImg.classList.add('hidden');
  cgPortraitImg.setAttribute('aria-hidden', 'true');
  cgActionRow.classList.add('hidden');
}

function showLoading() {
  cgEmptyState.classList.add('hidden');
  cgEmptyState.setAttribute('aria-hidden', 'true');
  cgLoadingState.classList.remove('hidden');
  cgLoadingState.setAttribute('aria-hidden', 'false');
  cgPortraitImg.classList.add('hidden');
  cgPortraitImg.setAttribute('aria-hidden', 'true');
  cgActionRow.classList.add('hidden');
}

function showImage(filename, description) {
  const src = `${API}/image/${filename}`;
  cgPortraitImg.src = src;
  cgPortraitImg.alt = `Character portrait: ${description.slice(0, 120)}`;
  cgPortraitImg.setAttribute('aria-hidden', 'false');

  cgEmptyState.classList.add('hidden');
  cgEmptyState.setAttribute('aria-hidden', 'true');
  cgLoadingState.classList.add('hidden');
  cgLoadingState.setAttribute('aria-hidden', 'true');
  cgPortraitImg.classList.remove('hidden');
  cgActionRow.classList.remove('hidden');

  // Download link
  cgDownloadBtn.href = src;

  // Cover button data
  cgUseAsCoverBtn.dataset.filename = filename;
  currentFilename = filename;
}

function setGenerating(isGenerating) {
  cgGenerateBtn.disabled = isGenerating;
  cgGenerateBtn.setAttribute('aria-disabled', isGenerating ? 'true' : 'false');
  if (isGenerating) {
    cgGenerateLabel.classList.add('hidden');
    cgSpinner.classList.remove('hidden');
  } else {
    cgGenerateLabel.classList.remove('hidden');
    cgSpinner.classList.add('hidden');
  }
}

function showError(msg) {
  cgErrorMsg.textContent = msg;
  cgErrorMsg.classList.remove('hidden');
}

function hideError() {
  cgErrorMsg.textContent = '';
  cgErrorMsg.classList.add('hidden');
}

// ── Validation shake ─────────────────────────────────────────────────────────
function shakeField(el) {
  const orig = el.style.borderColor;
  el.style.borderColor = 'var(--terracotta)';
  el.focus();
  setTimeout(() => { el.style.borderColor = orig; }, 1500);
}

// ── Session strip ─────────────────────────────────────────────────────────────
function addThumbToStrip(filename, description) {
  thumbCount++;
  const src = `${API}/image/${filename}`;

  const btn = document.createElement('button');
  btn.className = 'cg-strip-thumb';
  btn.setAttribute('role', 'listitem');
  btn.setAttribute('aria-label', `Portrait ${thumbCount}: ${description.slice(0, 80)}`);
  btn.dataset.filename = filename;
  btn.dataset.description = description;

  const img = document.createElement('img');
  img.src = src;
  img.alt = '';
  img.setAttribute('aria-hidden', 'true');
  btn.appendChild(img);

  // Click: restore this image to the main frame
  btn.addEventListener('click', () => {
    setActiveThumb(btn);
    showImage(filename, description);
    cgDownloadBtn.href = src;
    cgUseAsCoverBtn.dataset.filename = filename;
    currentFilename = filename;
  });

  // Prepend so newest is first
  cgStripScroll.prepend(btn);

  // Mark as active, deactivate others
  setActiveThumb(btn);

  // Show the strip on first generation
  cgStrip.classList.remove('hidden');
}

function setActiveThumb(activeBtn) {
  cgStripScroll.querySelectorAll('.cg-strip-thumb').forEach(b => b.classList.remove('active'));
  activeBtn.classList.add('active');
}

cgClearStripBtn.addEventListener('click', () => {
  cgStripScroll.innerHTML = '';
  thumbCount = 0;
  cgStrip.classList.add('hidden');
});

// ── Generate ─────────────────────────────────────────────────────────────────
cgGenerateBtn.addEventListener('click', async () => {
  const character = cgDescInput.value.trim();
  const story     = cgStoryInput.value.trim();
  const style     = cgStyleInput.value.trim();

  // Validate — character is required
  if (!character) {
    shakeField(cgDescInput);
    return;
  }

  hideError();
  setGenerating(true);
  showLoading();

  // Smart combination: weave story into prompt if present
  const prompt = story ? `${character}, in a scene: ${story}` : character;

  const payload = {
    prompt,
    style_prompt:         style,
    provider:             'gemini',
    gemini_model:         cgModelSelect.value,
    gemini_aspect_ratio:  getSelectedAR(),
  };

  try {
    const res = await fetch(`${API}/generate`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error((await res.json()).detail || `Server error ${res.status}`);
    }

    const data = await res.json();
    const filename = data.filename;

    showImage(filename, character);
    addThumbToStrip(filename, character);

    // Fire-and-forget: save to gallery (ignore failures)
    fetch(`${API}/gallery/image`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        filename,
        prompt:       character,
        style_prompt: style,
        model:        cgModelSelect.value,
      }),
    }).catch(() => {/* silently ignore gallery save errors */});
  } catch (err) {
    showEmpty();
    showError(err.message || 'Generation failed. Please try again.');
  } finally {
    setGenerating(false);
  }
});

// ── Use as Book Cover ────────────────────────────────────────────────────────
cgUseAsCoverBtn.addEventListener('click', () => {
  const filename    = cgUseAsCoverBtn.dataset.filename || currentFilename;
  const description = cgDescInput.value.trim();

  if (!filename) return;

  sessionStorage.setItem('cg_cover_filename', JSON.stringify({ filename, description }));

  const origText = cgUseAsCoverBtn.textContent;
  cgUseAsCoverBtn.textContent = 'Copied! Open Book Builder.';
  cgUseAsCoverBtn.disabled = true;
  setTimeout(() => {
    cgUseAsCoverBtn.textContent = origText;
    cgUseAsCoverBtn.disabled = false;
  }, 2000);
});

// ── Init ─────────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  await loadModels();

  // Restore CG-specific settings (model/ar) AFTER loadModels() so the rebuilt
  // select isn't clobbered
  restoreCgDraft();

  // Restore shared inputs (character/story/style) from SharedInputs store
  restoreSharedInputs();

  // 4. Wire live-sync listeners
  wireSharedInputListeners();
})();

// Periodic health ping every 30 s
setInterval(checkHealth, 30_000);

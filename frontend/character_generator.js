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

// Generated images this session — persisted so navigating away and back
// doesn't lose them. Oldest first; `active` is the one shown in the main frame.
const CG_SESSION_KEY = 'monkeyking_cg_session';
let sessionImages = [];   // [{ filename, description }]

function saveSession() {
  try {
    localStorage.setItem(CG_SESSION_KEY, JSON.stringify({
      images: sessionImages,
      active: currentFilename,
    }));
  } catch { /* quota / private-mode */ }
}

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

// ── Generation preferences ───────────────────────────────────────────────────
// Model and aspect ratio are owned by the Settings page (Generation Settings).
// They are persisted in this localStorage draft and read here at generate time.
const CG_DRAFT_KEY = 'monkeyking_cg_draft';

// ── Shared inputs — unified via SharedInputs.bindFields ──────────────────────
// CG_FIELD_MAP declared at top of file; populate:true (default), debounce:300
function wireSharedInputListeners() {
  SharedInputs.bindFields(CG_FIELD_MAP, { debounce: 300 });
}

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
    saveSession();
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
  sessionImages = [];
  currentFilename = null;
  try { localStorage.removeItem(CG_SESSION_KEY); } catch { /* private-mode */ }
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

  // Read generation prefs (model + aspect ratio) from the draft set by Settings.
  // model is used for BOTH the generate payload and the gallery save.
  // Default model must stay in sync with first imagen id in gemini_generator.GEMINI_MODELS.
  const draft = (() => { try { return JSON.parse(localStorage.getItem(CG_DRAFT_KEY) || '{}'); } catch { return {}; } })();
  const model = draft.model || 'imagen-4.0-generate-001';
  const ar    = draft.ar || '3:4';

  hideError();
  setGenerating(true);
  showLoading();

  // Smart combination: weave story into prompt if present
  const prompt = story ? `${character}, in a scene: ${story}` : character;

  const payload = {
    prompt,
    style_prompt:         style,
    provider:             'gemini',
    gemini_model:         model,
    gemini_aspect_ratio:  ar,
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

    // Persist this session image so it survives navigation
    sessionImages.push({ filename, description: character });
    saveSession();

    // Fire-and-forget: save to gallery (ignore failures)
    fetch(`${API}/gallery/image`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        filename,
        prompt:       character,
        story,
        style_prompt: style,
        model,
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

// ── Restore generated images from a previous visit ────────────────────────────
function restoreSession() {
  let s;
  try { s = JSON.parse(localStorage.getItem(CG_SESSION_KEY) || 'null'); } catch { return; }
  if (!s || !Array.isArray(s.images) || s.images.length === 0) return;

  sessionImages = s.images.filter(it => it && it.filename);
  if (sessionImages.length === 0) return;

  // Rebuild the strip oldest→newest (addThumbToStrip prepends, so newest ends up first)
  sessionImages.forEach(it => addThumbToStrip(it.filename, it.description || ''));

  // Show the previously-active image (fall back to the newest)
  const active = sessionImages.find(it => it.filename === s.active)
    || sessionImages[sessionImages.length - 1];
  showImage(active.filename, active.description || '');

  const activeBtn = cgStripScroll.querySelector(
    `.cg-strip-thumb[data-filename="${CSS.escape(active.filename)}"]`
  );
  if (activeBtn) setActiveThumb(activeBtn);
}

// ── Init ─────────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();

  // Restore any images generated earlier this session
  restoreSession();

  // Wire shared input listeners — bindFields populates fields and registers cross-tab sync
  wireSharedInputListeners();
})();

// Periodic health ping every 30 s
setInterval(checkHealth, 30_000);

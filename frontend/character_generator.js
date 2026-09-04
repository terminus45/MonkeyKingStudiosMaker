/* character_generator.js */
'use strict';

const API = window.location.origin;

// ── Shared input field map for this page ────────────────────────────────────
// Standardized IDs matching the canonical shared-inputs block on all 3 pages.
const CG_FIELD_MAP = { character: 'sharedCharacterInput', story: 'sharedStoryInput', style: 'sharedStyleInput' };

// ── DOM refs ────────────────────────────────────────────────────────────────
const statusDot       = document.getElementById('statusDot');
const statusLabel     = document.getElementById('statusLabel');

const sharedCharacterInput = document.getElementById('sharedCharacterInput');
const sharedStoryInput     = document.getElementById('sharedStoryInput');
const sharedStyleInput     = document.getElementById('sharedStyleInput');

const cgGenerateBtn   = document.getElementById('cgGenerateBtn');
const cgGenerateLabel = document.getElementById('cgGenerateLabel');
const cgSpinner       = document.getElementById('cgSpinner');
const cgErrorMsg      = document.getElementById('cgErrorMsg');

const cgImageFrame    = document.getElementById('cgImageFrame');
const cgEmptyState    = document.getElementById('cgEmptyState');
const cgLoadingState  = document.getElementById('cgLoadingState');
const cgLoadingLabel  = document.getElementById('cgLoadingLabel');
const cgPortraitImg   = document.getElementById('cgPortraitImg');
const cgActionRow          = document.getElementById('cgActionRow');
const cgDownloadBtn        = document.getElementById('cgDownloadBtn');
const cgUseAsCoverBtn      = document.getElementById('cgUseAsCoverBtn');
const cgCreateFigureBtn    = document.getElementById('cgCreateFigureBtn');
const cgCreateFigureLabel  = document.getElementById('cgCreateFigureLabel');
const cgCreateFigureSpinner = document.getElementById('cgCreateFigureSpinner');

const cgSeedLine      = document.getElementById('cgSeedLine');
const cgSeedText      = document.getElementById('cgSeedText');
const cgSeedLock      = document.getElementById('cgSeedLock');
const cgRefinePanel   = document.getElementById('cgRefinePanel');
const cgRefineInput   = document.getElementById('cgRefineInput');
const cgRefineHint    = document.getElementById('cgRefineHint');
const cgRefineButtons = [
  document.getElementById('cgRefineTweak'),
  document.getElementById('cgRefineChange'),
  document.getElementById('cgRefineReimagine'),
];

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

// ── In-flight generation job ─────────────────────────────────────────────────
// Generation runs server-side as a job we poll, rather than on one long-held
// HTTP request. A local model can take minutes, and holding a connection open
// that long loses the result whenever the tab is backgrounded or a proxy times
// the connection out — even though the worker finished and wrote the PNG.
// Persisting the job id means navigating away and back re-attaches instead.
// Same shape as figure_maker.js's monkeyking_fm_job.
const CG_JOB_KEY = 'monkeyking_cg_job';
const CG_JOB_MAX_AGE_MS = 30 * 60 * 1000;   // don't resume a job too old to be live
const CG_POLL_MS = 1500;

let _currentJobId = null;   // single-flight guard: a resumed loop and a fresh
                            // Generate must never poll the same UI at once.

function saveJob(job_id, description) {
  try {
    localStorage.setItem(CG_JOB_KEY, JSON.stringify({
      job_id, description, started_at: Date.now(),
    }));
  } catch { /* quota / private-mode */ }
}

function clearJob() {
  try { localStorage.removeItem(CG_JOB_KEY); } catch { /* private-mode */ }
}

function readJob() {
  try { return JSON.parse(localStorage.getItem(CG_JOB_KEY) || 'null'); }
  catch { return null; }
}

function setLoadingProgress(rec) {
  if (!cgLoadingLabel) return;
  const pct = rec && typeof rec.progress === 'number' ? rec.progress : null;
  const verb = rec && rec.stage === 'upscaling'
    ? 'Upscaling your image…' : 'Generating your character…';
  cgLoadingLabel.textContent =
    pct === null || pct === 0 ? verb : `${verb} ${pct}%`;
}

/**
 * Poll a job to completion and drive the UI. Safe to call from either a fresh
 * Generate or a resume; the _currentJobId guard keeps them from overlapping.
 */
async function pollJob(job_id, description) {
  _currentJobId = job_id;
  setGenerating(true);
  showLoading();

  while (_currentJobId === job_id) {
    let rec;
    try {
      const res = await fetch(`${API}/generate/status/${job_id}`);
      if (res.status === 404) {
        // The server forgot the job — most likely it restarted mid-render.
        throw new Error('That generation was lost (did the server restart?). Please try again.');
      }
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      rec = await res.json();
    } catch (err) {
      // A transient network blip must not kill a job that is still running:
      // wait and poll again rather than failing the whole generation.
      if (err instanceof TypeError) {
        await new Promise(r => setTimeout(r, CG_POLL_MS));
        continue;
      }
      clearJob();
      _currentJobId = null;
      showEmpty();
      showError(err.message);
      setGenerating(false);
      return;
    }

    setLoadingProgress(rec);

    if (rec.stage === 'done' && rec.filename) {
      clearJob();
      _currentJobId = null;
      onGenerated(rec.filename, description, rec.model, rec.seed);
      setGenerating(false);
      return;
    }
    if (rec.stage === 'error') {
      clearJob();
      _currentJobId = null;
      showEmpty();
      showError(rec.error || 'Generation failed. Please try again.');
      setGenerating(false);
      return;
    }

    await new Promise(r => setTimeout(r, CG_POLL_MS));
  }
}

// Prompt metadata for the gallery save. Persisted alongside the job so a
// generation resumed in a fresh page load still records the story and style
// it was made with, not blanks.
const CG_META_KEY = 'monkeyking_cg_job_meta';
let _pendingMeta = null;

function savePendingMeta() {
  try { localStorage.setItem(CG_META_KEY, JSON.stringify(_pendingMeta)); }
  catch { /* quota / private-mode */ }
}

function readPendingMeta() {
  if (_pendingMeta) return _pendingMeta;
  try { return JSON.parse(localStorage.getItem(CG_META_KEY) || 'null'); }
  catch { return null; }
}

// ── Seed display + lock ──────────────────────────────────────────────────────
// Only local generations have a seed; the line hides for cloud images so it
// never implies a reproducibility that doesn't exist.
let _lastSeed = null;

function showSeed(seed) {
  _lastSeed = (typeof seed === 'number') ? seed : null;
  if (_lastSeed === null) {
    cgSeedLine.classList.add('hidden');
    cgSeedLock.checked = false;
    return;
  }
  cgSeedText.textContent = `Seed ${_lastSeed}`;
  cgSeedLine.classList.remove('hidden');
}

// ── Refine panel ─────────────────────────────────────────────────────────────
// The model dropdown lists ONLY refine-compatible models for the displayed
// image (from /refine-options, backed by the saved compatibility table),
// pre-selecting the model that made it. The Settings draft model plays no
// role here — an image made locally stays refinable even if Settings now
// points at a cloud model.
const cgRefineModel = document.getElementById('cgRefineModel');
let _refineOptionsFor = null;   // filename the current dropdown belongs to

async function loadRefineOptions(filename) {
  _refineOptionsFor = filename;
  cgRefineModel.innerHTML = '';
  setRefineEnabled(false, 'Checking compatible models…');
  try {
    const res = await fetch(`${API}/image/${filename}/refine-options`);
    if (!res.ok) throw new Error(`Error ${res.status}`);
    const data = await res.json();
    if (_refineOptionsFor !== filename) return;   // user moved on mid-fetch

    const opts = data.options || [];
    if (opts.length === 0) {
      setRefineEnabled(false,
        'No compatible on-device model for this image — add a matching checkpoint to the models folder.');
      return;
    }
    for (const o of opts) {
      const el = document.createElement('option');
      el.value = o.model_id;
      el.textContent = o.tier === 'same-model' ? `${o.name} (made this image)` : o.name;
      cgRefineModel.appendChild(el);
    }
    // Visible, changeable default — the image's own source model when present.
    if (data.source_model && opts.some(o => o.model_id === data.source_model)) {
      cgRefineModel.value = data.source_model;
    }
    setRefineEnabled(true, '');
  } catch {
    if (_refineOptionsFor === filename) {
      setRefineEnabled(false, 'Could not load compatible models — is the server up?');
    }
  }
}

function setRefineEnabled(enabled, hint) {
  cgRefineButtons.forEach(b => { b.disabled = !enabled; });
  cgRefineInput.disabled = !enabled;
  cgRefineModel.disabled = !enabled;
  cgRefineHint.textContent = hint;
}

async function startRefine(strength) {
  const instruction = cgRefineInput.value.trim();
  if (!instruction) { shakeField(cgRefineInput); return; }
  if (!currentFilename) return;

  // The user's explicit choice from the compatibility dropdown — never the
  // Settings draft.
  const model = cgRefineModel.value;
  if (!model) return;
  const description = (cgUseAsCoverBtn.dataset.description || sharedCharacterInput.value.trim());

  hideError();
  _pendingMeta = {
    character: `${description} — ${instruction}`,
    story: '', style: '', model,
  };
  savePendingMeta();

  try {
    const res = await fetch(`${API}/refine/job`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: currentFilename,
        instruction,
        strength,
        model_id: model,
        seed: cgSeedLock.checked && _lastSeed !== null ? _lastSeed : -1,
      }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || `Server error ${res.status}`);
    const { job_id } = await res.json();
    cgRefineInput.value = '';
    saveJob(job_id, _pendingMeta.character);
    pollJob(job_id, _pendingMeta.character);
  } catch (err) {
    showError(err.message || 'Refinement failed. Please try again.');
  }
}

cgRefineButtons.forEach(btn =>
  btn.addEventListener('click', () => startRefine(parseFloat(btn.dataset.strength))));

// ── Upscale panel ────────────────────────────────────────────────────────────
// Real-ESRGAN super-resolution over the displayed image. The server picks
// the upscaler model from the image's own recipe; the client picks only a
// factor. Buttons carry the concrete output size for THIS image, and the
// factor nearest print quality (~3300 px long edge) is pre-highlighted.
const cgUpscalePanel = document.getElementById('cgUpscalePanel');
const cgUpscaleHint  = document.getElementById('cgUpscaleHint');
const cgUpscaleBtns  = [2, 4, 8].map(f => document.getElementById(`cgUpscale${f}`));

let _upscaleStatus = null;   // GET /upscale/status, fetched once at load

async function loadUpscaleStatus() {
  try {
    const res = await fetch(`${API}/upscale/status`);
    if (res.ok) _upscaleStatus = await res.json();
  } catch { /* server unreachable — the panel just stays hidden */ }
}

function suggestedFactor(w, h) {
  const long = Math.max(w, h);
  for (const f of [2, 4, 8]) if (long * f >= 3300) return f;
  return 8;
}

/** Label/enable the buttons for the displayed image's real dimensions. */
function updateUpscalePanel() {
  if (!_upscaleStatus || !_upscaleStatus.available || !currentFilename) {
    cgUpscalePanel.classList.add('hidden');
    return;
  }
  const w = cgPortraitImg.naturalWidth, h = cgPortraitImg.naturalHeight;
  if (!w || !h) { cgUpscalePanel.classList.add('hidden'); return; }
  const suggest = suggestedFactor(w, h);
  cgUpscaleBtns.forEach(btn => {
    const f = parseInt(btn.dataset.factor, 10);
    btn.textContent = `${f}× → ${w * f}×${h * f}`;
    btn.disabled = w * h * f * f > _upscaleStatus.max_output_pixels;
    btn.classList.toggle('suggested', f === suggest && !btn.disabled);
  });
  cgUpscaleHint.textContent = '';
  cgUpscalePanel.classList.remove('hidden');
}

async function startUpscale(factor) {
  if (!currentFilename) return;
  const w = cgPortraitImg.naturalWidth, h = cgPortraitImg.naturalHeight;
  const mp = (w * h * factor * factor) / 1e6;
  if (mp > 40 && !confirm(
      `${factor}× makes a ${w * factor}×${h * factor} image (~${Math.round(mp)} MP) — ` +
      `a very large file some browsers struggle to display. Continue?`)) return;
  const desc = cgUseAsCoverBtn.dataset.description || '';
  try {
    const res = await fetch(`${API}/upscale/job`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ filename: currentFilename, factor }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || `Server error ${res.status}`);
    const { job_id } = await res.json();
    // Same job store and poll loop as generation — survives navigation.
    saveJob(job_id, desc);
    pollJob(job_id, desc);
  } catch (err) {
    showError(err.message || 'Upscale failed. Please try again.');
  }
}

cgUpscaleBtns.forEach(btn =>
  btn.addEventListener('click', () => startUpscale(parseInt(btn.dataset.factor, 10))));

// Output sizes come from the loaded pixels, so refresh whenever they change.
cgPortraitImg.addEventListener('load', updateUpscalePanel);

/** Shared completion path for both a fresh generation and a resumed one. */
function onGenerated(filename, description, model, seed) {
  const meta = readPendingMeta() || {};
  const desc = description || meta.character || '';

  showImage(filename, desc);
  addThumbToStrip(filename, desc);
  showSeed(seed);
  loadRefineOptions(filename);

  sessionImages.push({ filename, description: desc });
  saveSession();

  // Fire-and-forget: save to gallery (ignore failures)
  fetch(`${API}/gallery/image`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      filename,
      prompt:       desc,
      story:        meta.story || '',
      style_prompt: meta.style || '',
      model:        model || meta.model || '',
    }),
  }).catch(() => {/* silently ignore gallery save errors */});

  _pendingMeta = null;
  try { localStorage.removeItem(CG_META_KEY); } catch { /* private-mode */ }
}

/** Re-attach to a generation that was running when the page was left. */
function resumeJobIfAny() {
  const stored = readJob();
  if (!stored || !stored.job_id) return;
  if (!stored.started_at || (Date.now() - stored.started_at) > CG_JOB_MAX_AGE_MS) {
    clearJob();
    return;
  }
  pollJob(stored.job_id, stored.description || '');
}

// ── Health check ────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const res  = await fetch(`${API}/health`);
    const data = await res.json();
    statusDot.className = 'status-dot ok';
    statusLabel.textContent = 'Connected';
  } catch {
    statusDot.className = 'status-dot error';
    statusLabel.textContent = 'Server offline';
  }
}

// ── Generation preferences ───────────────────────────────────────────────────
// Model and aspect ratio are owned by the Settings page (Generation Settings).
// They are persisted in this localStorage draft and read here at generate time.
const CG_DRAFT_KEY = 'monkeyking_cg_draft';

// Auto-expand the collapsible <details> when Story or Style has content.
function autoExpandIfContent() {
  var story   = document.getElementById('sharedStoryInput');
  var style   = document.getElementById('sharedStyleInput');
  var details = document.getElementById('sharedMoreOptions');
  if (details && ((story && story.value.trim()) || (style && style.value.trim()))) {
    details.open = true;
  }
}

// ── Shared inputs — unified via SharedInputs.bindFields ──────────────────────
// CG_FIELD_MAP declared at top of file; populate:true (default), debounce:300
function wireSharedInputListeners() {
  SharedInputs.bindFields(CG_FIELD_MAP, { debounce: 300, onRemote: function() { autoExpandIfContent(); } });
  autoExpandIfContent();
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
  cgUseAsCoverBtn.dataset.description = description;   // refine anchors to this
  currentFilename = filename;

  // Enable the Create Figure button now that a portrait is ready
  cgCreateFigureBtn.disabled = false;
  cgCreateFigureBtn.removeAttribute('aria-disabled');
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
  const character = sharedCharacterInput.value.trim();
  const story     = sharedStoryInput.value.trim();
  const style     = sharedStyleInput.value.trim();

  // Validate — character is required
  if (!character) {
    shakeField(sharedCharacterInput);
    return;
  }

  // Scroll to the bottom so the generating portrait comes into view.
  window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });

  // Read generation prefs (model + aspect ratio) from the draft set by Settings.
  // model is used for BOTH the generate payload and the gallery save.
  // Default model must stay in sync with first imagen id in gemini_generator.GEMINI_MODELS.
  const draft = (() => { try { return JSON.parse(localStorage.getItem(CG_DRAFT_KEY) || '{}'); } catch { return {}; } })();
  const model = draft.model || 'imagen-4.0-fast-generate-001';
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
    // 🔒 keep seed: reuse the displayed image's seed so a tweaked prompt
    // keeps its composition. Local models only; -1 = draw a fresh one.
    seed: (cgSeedLock && cgSeedLock.checked && _lastSeed !== null) ? _lastSeed : -1,
  };

  // Remember what this generation was for, so the gallery save after a
  // resumed job still has the story/style that produced it.
  _pendingMeta = { character, story, style, model };

  try {
    const res = await fetch(`${API}/generate/job`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error((await res.json()).detail || `Server error ${res.status}`);
    }

    const { job_id } = await res.json();
    saveJob(job_id, character);
    savePendingMeta();
    pollJob(job_id, character);      // not awaited: the handler is done here
  } catch (err) {
    showEmpty();
    showError(err.message || 'Generation failed. Please try again.');
    setGenerating(false);
  }
});

// ── Use as Book Cover ────────────────────────────────────────────────────────
cgUseAsCoverBtn.addEventListener('click', () => {
  const filename    = cgUseAsCoverBtn.dataset.filename || currentFilename;
  const description = sharedCharacterInput.value.trim();

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

// ── Create Figure ─────────────────────────────────────────────────────────────
// Starts a Meshy image-to-3D job from the current portrait, writes the job to
// localStorage in the exact shape expected by figure_maker.js saveFmJob(), and
// navigates to Figure Maker where resumeJobIfAny() takes over.
//
// COUPLING NOTE: The localStorage key and payload shape below must stay in sync
// with figure_maker.js:
//   FM_JOB_KEY = 'monkeyking_fm_job'
//   saveFmJob writes: { job_id: string, started_at: number }
cgCreateFigureBtn.addEventListener('click', async () => {
  if (!currentFilename) return; // guard: button should be disabled if no image

  if (!confirm(
    'Create a 3D figure from this picture?\n\n' +
    'This is a paid 3D generation and takes a few minutes. Continue?'
  )) return;

  hideError();

  // Enter in-flight state
  cgCreateFigureBtn.disabled = true;
  cgCreateFigureBtn.setAttribute('aria-disabled', 'true');
  cgCreateFigureLabel.classList.add('hidden');
  cgCreateFigureSpinner.classList.remove('hidden');

  function restoreBtn() {
    cgCreateFigureBtn.disabled = false;
    cgCreateFigureBtn.removeAttribute('aria-disabled');
    cgCreateFigureLabel.classList.remove('hidden');
    cgCreateFigureSpinner.classList.add('hidden');
  }

  try {
    const res = await fetch(`${API}/figure/generate-from-image`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        filename: currentFilename,
        prompt:   sharedCharacterInput.value.trim(),
        style:    sharedStyleInput.value.trim(),
        story:    sharedStoryInput.value.trim(),
      }),
    });

    if (!res.ok) {
      let msg;
      try {
        const body = await res.json();
        if (res.status === 503) {
          msg = 'Meshy key not set — ask a grown-up to add it in Settings (⚙).';
        } else if (res.status === 404) {
          msg = "Couldn't find that portrait on the server. Try regenerating your character.";
        } else {
          msg = body.detail || `Something went wrong (error ${res.status}).`;
        }
      } catch {
        msg = `Something went wrong (error ${res.status}).`;
      }
      restoreBtn();
      showError(msg);
      return;
    }

    const data = await res.json();

    // Write job to localStorage in the exact shape figure_maker.js expects.
    // COUPLING: must match FM_JOB_KEY / saveFmJob shape in figure_maker.js.
    localStorage.setItem('monkeyking_fm_job', JSON.stringify({
      job_id:     data.job_id,
      started_at: Date.now(),
    }));

    // Navigate immediately — figure_maker.js resumeJobIfAny() will pick up the job.
    window.location.href = 'figure_maker.html';

  } catch {
    restoreBtn();
    showError('Network error — check your connection and try again.');
  }
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

  // Refine compatibility is a property of the displayed IMAGE, not of the
  // Settings draft — load the dropdown for whatever restoreSession() put up.
  if (currentFilename) loadRefineOptions(currentFilename);
  else setRefineEnabled(false, 'Generate an image to refine it.');

  // Upscale gating — after status arrives, size the panel for whatever
  // restoreSession() put up (its img may have loaded before status did).
  await loadUpscaleStatus();
  updateUpscalePanel();

  // Re-attach to a generation that was still running when this page was left.
  resumeJobIfAny();
})();

// Periodic health ping every 30 s
setInterval(checkHealth, 30_000);

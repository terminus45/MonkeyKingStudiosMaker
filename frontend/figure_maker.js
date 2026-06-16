/* figure_maker.js — ES module */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';

const API = window.location.origin;

// window.SharedInputs is set by shared_inputs.js (non-module, loaded before this module)
// Field map: standardized IDs matching canonical shared-inputs block on all 3 pages.

// ── DOM refs ────────────────────────────────────────────────────────────────
const statusDot            = document.getElementById('statusDot');
const statusLabel          = document.getElementById('statusLabel');

const fmBoltMascot         = document.getElementById('fmBoltMascot');
const fmBoltText           = document.getElementById('fmBoltText');

const sharedCharacterInput = document.getElementById('sharedCharacterInput');
const sharedStoryInput     = document.getElementById('sharedStoryInput');
const sharedStyleInput     = document.getElementById('sharedStyleInput');
const fmGenerateBtn        = document.getElementById('fmGenerateBtn');
const fmGenerateLabel      = document.getElementById('fmGenerateLabel');
const fmSpinner            = document.getElementById('fmSpinner');
const fmEnhancedPromptBox  = document.getElementById('fmEnhancedPromptBox');
const fmEnhancedPromptText = document.getElementById('fmEnhancedPromptText');
const fmErrorMsg           = document.getElementById('fmErrorMsg');
const fmResetBtn           = document.getElementById('fmResetBtn');

const fmViewerEmpty        = document.getElementById('fmViewerEmpty');
const fmProgressState      = document.getElementById('fmProgressState');
const fmStageLabel         = document.getElementById('fmStageLabel');
const fmProgressBar        = document.getElementById('fmProgressBar');
const fmProgressFill       = document.getElementById('fmProgressFill');
const fmProgressPct        = document.getElementById('fmProgressPct');

const fmViewerFrame        = document.getElementById('fmViewerFrame');
const fmViewer             = document.getElementById('fmViewer');
const fmViewerHint         = document.getElementById('fmViewerHint');
const fmViewerError        = document.getElementById('fmViewerError');
const fmViewerErrorDetail  = document.getElementById('fmViewerErrorDetail');
const fmDownloadGlbBtn     = document.getElementById('fmDownloadGlbBtn');

const fmReportCard         = document.getElementById('fmReportCard');
const fmFilamentTag        = document.getElementById('fmFilamentTag');
const fmReportText         = document.getElementById('fmReportText');
const fmDownloadStlBtn     = document.getElementById('fmDownloadStlBtn');
const fmDownloadGlbBtn2    = document.getElementById('fmDownloadGlbBtn2');

// ── Bolt message map ─────────────────────────────────────────────────────────
const BOLT_MESSAGES = {
  idle:        'What should we build today?',
  idleReset:   "Let's make something new! What should it be?",
  prompting:   'Ooh, great idea! I\'m thinking up the perfect design…',
  preview:     'Sculpting your shape — almost like magic!',
  refine:      'Painting it and adding all the details…',
  downloading: 'Packing it up and bringing it over…',
  analyzing:   'Checking if it\'s ready to print…',
  done:        'Ta-da! Here\'s your very own 3D figure! 🎉',
  error:       'Oops! Something went wobbly. Let\'s try again!',
};

// ── Stage label map (kid-friendly) ──────────────────────────────────────────
const STAGE_LABELS = {
  prompting:   'Dreaming up your idea…',
  preview:     'Sculpting the shape…',
  refine:      'Painting it in…',
  downloading: 'Almost ready…',
  analyzing:   'Checking the details…',
};

// ── State ───────────────────────────────────────────────────────────────────
let _cancelled    = false;
let _currentJobId = null;   // job_id whose poll loop is allowed to update the UI (single-flight guard)
let _glbUrl       = null;
let _stlObjectUrl = null;   // blob URL for the client-side STL export (revoked on teardown)

// three.js refs
let fmRenderer    = null;
let fmAnimId      = null;
let fmControls    = null;
let fmRo          = null;
let autoRotateTimer = null;

// ── Health check ─────────────────────────────────────────────────────────────
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

// ── Bolt mascot ──────────────────────────────────────────────────────────────
function setBoltMessage(key) {
  // Mascot banner was removed; keep this a safe no-op so callers don't need changing.
  if (fmBoltText) fmBoltText.textContent = BOLT_MESSAGES[key] || BOLT_MESSAGES.idle;
}

function setBoltBouncing(on) {
  if (fmBoltMascot) fmBoltMascot.classList.toggle('bolt-bounce', on);
}

// ── State machine helpers ─────────────────────────────────────────────────────
function setGenerating(on) {
  fmGenerateBtn.disabled = on;
  fmGenerateBtn.setAttribute('aria-disabled', on ? 'true' : 'false');
  if (on) {
    fmGenerateLabel.classList.add('hidden');
    fmSpinner.classList.remove('hidden');
  } else {
    fmGenerateLabel.classList.remove('hidden');
    fmSpinner.classList.add('hidden');
  }
}

function setInputsDisabled(on) {
  sharedCharacterInput.disabled = on;
}

function showEmpty() {
  fmViewerEmpty.classList.remove('hidden');
  fmProgressState.classList.add('hidden');
  fmViewerFrame.classList.add('hidden');
}

function showProgress() {
  fmViewerEmpty.classList.add('hidden');
  fmProgressState.classList.remove('hidden');
  fmViewerFrame.classList.add('hidden');
}

function showViewer() {
  fmViewerEmpty.classList.add('hidden');
  fmProgressState.classList.add('hidden');
  fmViewerFrame.classList.remove('hidden');
}

function setProgress(pct) {
  const clamped = Math.max(0, Math.min(100, Math.round(pct)));
  fmProgressFill.style.width = `${clamped}%`;
  fmProgressBar.setAttribute('aria-valuenow', clamped);
  fmProgressPct.textContent  = `${clamped}%`;
}

function setStageLabel(stage) {
  fmStageLabel.textContent = STAGE_LABELS[stage] || 'Working…';
}

function showError(msg) {
  fmErrorMsg.textContent = msg;
  fmErrorMsg.classList.remove('hidden');
}

function hideError() {
  fmErrorMsg.textContent = '';
  fmErrorMsg.classList.add('hidden');
}

// ── In-flight job persistence — lets a running job survive navigation ──────────
const FM_JOB_KEY        = 'monkeyking_fm_job';
const FM_JOB_MAX_AGE_MS = 35 * 60 * 1000;   // don't resume a job older than ~35 min

function saveFmJob(jobId) {
  try {
    localStorage.setItem(FM_JOB_KEY, JSON.stringify({ job_id: jobId, started_at: Date.now() }));
  } catch { /* quota / private-mode */ }
}

function readFmJob() {
  try { return JSON.parse(localStorage.getItem(FM_JOB_KEY) || 'null'); }
  catch { return null; }
}

function clearFmJob() {
  try { localStorage.removeItem(FM_JOB_KEY); } catch { /* private-mode */ }
}

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
// bindFields handles populate + cross-tab sync.
// bindFields must not touch .disabled — setInputsDisabled() owns that.
function wireSharedInputListeners() {
  window.SharedInputs.bindFields(
    { character: 'sharedCharacterInput', story: 'sharedStoryInput', style: 'sharedStyleInput' },
    { debounce: 300, onRemote: function() { autoExpandIfContent(); } }
  );
  autoExpandIfContent();
}

// ── Generate ─────────────────────────────────────────────────────────────────
fmGenerateBtn.addEventListener('click', async () => {
  const prompt = sharedCharacterInput.value.trim();
  if (!prompt) {
    sharedCharacterInput.style.borderColor = 'var(--terracotta)';
    sharedCharacterInput.focus();
    setTimeout(() => { sharedCharacterInput.style.borderColor = ''; }, 1500);
    return;
  }

  hideError();
  _cancelled = false;
  _currentJobId = null;   // supersede any resumed/older poll loop still running

  // Enter generating state
  setGenerating(true);
  setInputsDisabled(true);
  showProgress();
  setProgress(0);
  setBoltBouncing(true);
  setBoltMessage('prompting');
  fmResetBtn.classList.add('hidden');
  fmEnhancedPromptBox.classList.add('hidden');
  fmReportCard.classList.add('hidden');
  teardownViewer();

  let jobId;
  try {
    const res = await fetch(`${API}/figure/generate`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        prompt,
        style: sharedStyleInput.value.trim(),
        story: sharedStoryInput.value.trim(),
      }),
    });

    if (!res.ok) {
      const detail = (await res.json()).detail || `Server error ${res.status}`;
      if (res.status === 503) {
        throw new Error(`Meshy or Anthropic key missing — ask a grown-up to set it in Settings (⚙). Detail: ${detail}`);
      }
      throw new Error(detail);
    }

    const data = await res.json();
    jobId = data.job_id;
    _currentJobId = jobId;
    saveFmJob(jobId);     // persist so the job survives navigation
  } catch (err) {
    enterErrorState(err.message);
    return;
  }

  // Poll loop
  await pollStatus(jobId);
});

async function pollStatus(jobId, isResume = false) {
  if (_cancelled || jobId !== _currentJobId) return;

  try {
    const res = await fetch(`${API}/figure/status/${jobId}`);
    if (!res.ok) {
      const err = new Error((await res.json().catch(() => ({}))).detail || `Error ${res.status}`);
      err.status = res.status;
      throw err;
    }
    const data = await res.json();

    if (_cancelled || jobId !== _currentJobId) return;

    const { stage, progress, enhanced_prompt, glb_filename, report, filament, error } = data;

    // Update bolt
    if (BOLT_MESSAGES[stage]) setBoltMessage(stage);

    // Update stage label + progress bar
    setStageLabel(stage);
    if (typeof progress === 'number') setProgress(progress);

    // Enhanced prompt reveal
    if (enhanced_prompt && fmEnhancedPromptBox.classList.contains('hidden')) {
      fmEnhancedPromptText.textContent = enhanced_prompt;
      fmEnhancedPromptBox.classList.remove('hidden');
    }

    if (stage === 'done') {
      // Success!
      _glbUrl = glb_filename ? `${API}/figure/model/${glb_filename}` : null;
      setProgress(100);
      setBoltBouncing(false);
      setBoltMessage('done');
      enterReadyState({ glb_filename, report, filament });
      return;
    }

    if (stage === 'error') {
      throw new Error(error || 'Generation failed.');
    }

    // Still in progress — poll again
    await new Promise(r => setTimeout(r, 2500));
    await pollStatus(jobId);

  } catch (err) {
    if (_cancelled || jobId !== _currentJobId) return;
    // On resume, a forgotten job (server restarted → 404, or a corrupted stored
    // id → 400) shouldn't look like a crash — show a soft "check the Gallery" notice.
    if (isResume && (err.status === 404 || err.status === 400)) {
      enterMissingJobState();
      return;
    }
    enterErrorState(err.message);
  }
}

function enterReadyState({ glb_filename, report, filament }) {
  _currentJobId = null;
  clearFmJob();
  setGenerating(false);
  setInputsDisabled(false);
  showViewer();

  fmResetBtn.classList.remove('hidden');

  // Show report card
  if (report || filament) {
    fmReportCard.classList.remove('hidden');
    fmReportText.textContent = report || '';

    if (filament) {
      fmFilamentTag.textContent = filament;
      fmFilamentTag.classList.remove('hidden');
      fmFilamentTag.setAttribute('aria-label', `Suggested filament: ${filament}`);
    } else {
      fmFilamentTag.classList.add('hidden');
    }
  }

  // Download buttons
  const glbUrl = glb_filename ? `${API}/figure/model/${glb_filename}` : null;
  if (glbUrl) {
    fmDownloadGlbBtn2.href     = glbUrl;
    fmDownloadGlbBtn2.download = glb_filename;
    fmDownloadGlbBtn2.classList.remove('hidden');

    fmDownloadGlbBtn.href     = glbUrl;
    fmDownloadGlbBtn.download = glb_filename;

    // The STL is exported client-side from the loaded GLB (see mountViewer).
    // Name it after the GLB; it's revealed once the model loads and converts.
    fmDownloadStlBtn.download = glb_filename.replace(/\.glb$/i, '.stl');

    // Load 3D model
    mountViewer(glbUrl);
  }
  // Stays hidden until the viewer finishes loading and the STL export succeeds.
  fmDownloadStlBtn.classList.add('hidden');
}

function enterErrorState(msg) {
  _currentJobId = null;
  clearFmJob();
  setBoltBouncing(false);
  setBoltMessage('error');
  setGenerating(false);
  setInputsDisabled(false);
  showEmpty();
  showError(msg);
  fmResetBtn.classList.remove('hidden');
}

// Soft state when a resumed job can no longer be found on the server (e.g. the
// server restarted). The figure may have finished and been auto-saved, so we
// point at the Gallery rather than declaring failure.
function enterMissingJobState() {
  _currentJobId = null;
  clearFmJob();
  setBoltBouncing(false);
  setBoltMessage('idle');
  setGenerating(false);
  setInputsDisabled(false);
  setProgress(0);
  showEmpty();
  showError("We couldn't find your figure in progress — it may already be finished. Check the Gallery! 🖼");
  fmResetBtn.classList.remove('hidden');
}

// ── Reset ─────────────────────────────────────────────────────────────────────
fmResetBtn.addEventListener('click', () => {
  _cancelled    = true;
  _currentJobId = null;
  _glbUrl       = null;
  clearFmJob();

  // Clear character field and shared store entry
  sharedCharacterInput.value = '';
  window.SharedInputs.patch({ character: '' });

  hideError();
  fmEnhancedPromptBox.classList.add('hidden');
  fmReportCard.classList.add('hidden');
  fmResetBtn.classList.add('hidden');

  setGenerating(false);
  setInputsDisabled(false);
  setProgress(0);

  teardownViewer();
  showEmpty();

  setBoltBouncing(false);
  setBoltMessage('idleReset');
});

// ── three.js viewer ───────────────────────────────────────────────────────────
function teardownViewer() {
  if (autoRotateTimer) { clearTimeout(autoRotateTimer); autoRotateTimer = null; }
  if (fmAnimId)        { cancelAnimationFrame(fmAnimId); fmAnimId = null; }
  if (fmRo)            { fmRo.disconnect(); fmRo = null; }
  if (fmControls)      { fmControls.dispose(); fmControls = null; }
  if (fmRenderer)      { fmRenderer.dispose(); fmRenderer = null; }
  while (fmViewer.firstChild) fmViewer.removeChild(fmViewer.firstChild);
  fmViewerError.classList.add('hidden');

  // Drop the previous STL export — a new model will regenerate it.
  if (_stlObjectUrl) { URL.revokeObjectURL(_stlObjectUrl); _stlObjectUrl = null; }
  fmDownloadStlBtn.classList.add('hidden');
}

function mountViewer(glbUrl) {
  teardownViewer();

  const container = fmViewer;
  const w = container.clientWidth  || 600;
  const h = container.clientHeight || 600;

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(w, h);
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const canvas = renderer.domElement;
  canvas.setAttribute('aria-hidden', 'true');
  container.appendChild(canvas);
  fmRenderer = renderer;

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, w / h, 0.01, 1000);
  camera.position.set(0, 0, 3);

  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
  dirLight.position.set(5, 10, 5);
  scene.add(dirLight);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping   = true;
  controls.dampingFactor   = 0.05;
  controls.autoRotate      = true;
  controls.autoRotateSpeed = 1.5;
  fmControls = controls;

  // Pause auto-rotate on interaction, resume after 10s
  controls.addEventListener('start', () => {
    controls.autoRotate = false;
    // Fade hint on first interaction
    fmViewerHint.classList.add('hint-faded');
    if (autoRotateTimer) clearTimeout(autoRotateTimer);
    autoRotateTimer = setTimeout(() => { if (fmControls) fmControls.autoRotate = true; }, 10000);
  });

  const loader = new GLTFLoader();
  try {
    loader.load(
      glbUrl,
      gltf => {
        const model = gltf.scene;
        scene.add(model);

        // Auto-fit camera to bounding sphere
        const box    = new THREE.Box3().setFromObject(model);
        const center = new THREE.Vector3();
        const sphere = new THREE.Sphere();
        box.getBoundingSphere(sphere);
        box.getCenter(center);
        model.position.sub(center);
        camera.position.set(0, sphere.radius * 0.3, sphere.radius * 2.5);
        controls.target.set(0, 0, 0);
        controls.update();

        // Update aria-label with prompt
        const promptVal = sharedCharacterInput.value.trim();
        if (promptVal) {
          fmViewer.setAttribute('aria-label', `3D model of ${promptVal} — drag to rotate, scroll to zoom`);
        }

        // Export an STL from the loaded geometry so the figure can be 3D-printed.
        // Meshy only returns a GLB, so we convert it in the browser.
        try {
          const stl  = new STLExporter().parse(model, { binary: true });
          const blob = new Blob([stl], { type: 'model/stl' });
          if (_stlObjectUrl) URL.revokeObjectURL(_stlObjectUrl);
          _stlObjectUrl = URL.createObjectURL(blob);
          fmDownloadStlBtn.href = _stlObjectUrl;
          fmDownloadStlBtn.classList.remove('hidden');
        } catch (e) {
          console.error('STL export failed', e);
          fmDownloadStlBtn.classList.add('hidden');
        }
      },
      undefined,
      err => {
        console.error('GLTFLoader error', err);
        fmViewerErrorDetail.textContent = String(err.message || err);
        fmViewerError.classList.remove('hidden');
      }
    );
  } catch (err) {
    fmViewerErrorDetail.textContent = String(err.message || err);
    fmViewerError.classList.remove('hidden');
  }

  // ResizeObserver
  const ro = new ResizeObserver(() => {
    if (!fmRenderer) return;
    const nw = container.clientWidth;
    const nh = container.clientHeight;
    fmRenderer.setSize(nw, nh);
    camera.aspect = nw / nh;
    camera.updateProjectionMatrix();
  });
  ro.observe(container);
  fmRo = ro;

  function animate() {
    fmAnimId = requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();
}

// ── Init ─────────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();

  // Wire shared input listeners — bindFields populates fields and registers cross-tab sync.
  wireSharedInputListeners();

  // Re-attach to a job that was still running when the user navigated away.
  resumeJobIfAny();
})();

// ── Resume an in-flight job after navigation ──────────────────────────────────
// A job started earlier is still running server-side, so re-attach to it instead
// of abandoning it. (This replaces the old "leaving cancels the job" warning.)
function resumeJobIfAny() {
  const stored = readFmJob();
  if (!stored || !stored.job_id) return;

  // Staleness guard — don't resume a job too old to plausibly still be running.
  if (!stored.started_at || (Date.now() - stored.started_at) > FM_JOB_MAX_AGE_MS) {
    clearFmJob();
    return;
  }

  // Restore the in-progress UI shell, then re-attach the poll loop.
  _cancelled    = false;
  _currentJobId = stored.job_id;
  setGenerating(true);
  setInputsDisabled(true);
  showProgress();
  setProgress(0);
  setBoltBouncing(true);
  setBoltMessage('prompting');
  fmResetBtn.classList.add('hidden');
  fmEnhancedPromptBox.classList.add('hidden');
  fmReportCard.classList.add('hidden');

  // Fire-and-forget; the first poll rebuilds progress or jumps straight to the
  // finished result. isResume=true makes a "job not found" fail soft.
  pollStatus(stored.job_id, true);
}

setInterval(checkHealth, 30_000);

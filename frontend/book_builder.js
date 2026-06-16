const API = window.location.origin;

// ── Language registry (mirrors languages.py, minus prompts) ────────────────
const LANG_META = {
  zh: {
    code: 'zh', display_name: '中文', english_name: 'Chinese',
    native_field: 'zh', reading_field: 'pinyin', reading_label: 'Pinyin',
    title_native_field: 'book_title_zh', title_reading_field: 'book_title_pinyin',
    font_class: 'lang-zh',
  },
  ja: {
    code: 'ja', display_name: '日本語', english_name: 'Japanese',
    native_field: 'ja', reading_field: 'romaji', reading_label: 'Romaji',
    title_native_field: 'book_title_ja', title_reading_field: 'book_title_romaji',
    font_class: 'lang-ja',
  },
  ko: {
    code: 'ko', display_name: '한국어', english_name: 'Korean',
    native_field: 'ko', reading_field: 'romanization', reading_label: 'Romanization',
    title_native_field: 'book_title_ko', title_reading_field: 'book_title_romanization',
    font_class: 'lang-ko',
  },
};
const DEFAULT_LANG = 'zh';

function langMeta(code) {
  return LANG_META[code] || LANG_META[DEFAULT_LANG];
}

// ── State ──────────────────────────────────────────────────────────────────
let storyData = null;   // DecomposeResponse from server
let geminiAR = '4:3';  // default: classic storybook shape
let currentLang = DEFAULT_LANG;
// Set true when a Check Readings Apply has been committed; enables staleness tracking.
// Reset on decompose/clear so freshly-generated books start clean.
let lastCheckApplied = false;

// ── DOM refs ───────────────────────────────────────────────────────────────
const sharedStoryInput     = document.getElementById('sharedStoryInput');
const sharedCharacterInput = document.getElementById('sharedCharacterInput');
const sharedStyleInput     = document.getElementById('sharedStyleInput');
const decomposeHint   = document.getElementById('decomposeHint');
const autoGenBtn      = document.getElementById('autoGenBtn');
const autoGenLabel    = document.getElementById('autoGenLabel');
const autoGenSpinner  = document.getElementById('autoGenSpinner');

const step2           = document.getElementById('step2');
const bookTitleDisplay= document.getElementById('bookTitleDisplay');
const bookTitleSub    = document.getElementById('bookTitleSub');
const pageGrid        = document.getElementById('pageGrid');

const step3           = document.getElementById('step3');
const queueBtn        = document.getElementById('queueBtn');
const queueLabel      = document.getElementById('queueLabel');
const queueSpinner    = document.getElementById('queueSpinner');
const stopBtn         = document.getElementById('stopBtn');
const progressWrap    = document.getElementById('progressWrap');
const progressBar     = document.getElementById('progressBar');
const progressText    = document.getElementById('progressText');

const step4           = document.getElementById('step4');
const exportBtn       = document.getElementById('exportBtn');
const printBtn        = document.getElementById('printBtn');
const printLabel      = document.getElementById('printLabel');
const printSpinner    = document.getElementById('printSpinner');
const galleryBtn      = document.getElementById('galleryBtn');
const galleryLabel    = document.getElementById('galleryLabel');
const gallerySpinner  = document.getElementById('gallerySpinner');

const statusDot       = document.getElementById('statusDot');
const statusLabel     = document.getElementById('statusLabel');

const checkReadingsBtn     = document.getElementById('checkReadingsBtn');
const checkReadingsLabel   = document.getElementById('checkReadingsLabel');
const checkReadingsSpinner = document.getElementById('checkReadingsSpinner');
const checkReadingsHint    = document.getElementById('checkReadingsHint');
const checkReadingsOverlay = document.getElementById('checkReadingsOverlay');
const checkReadingsDialog  = document.getElementById('checkReadingsDialog');

// (step1StylePresets removed — preset pills deleted from Step 1)

// ── Language selector ──────────────────────────────────────────────────────
function setLanguage(code, { rerender = true, save = true } = {}) {
  if (!LANG_META[code]) code = DEFAULT_LANG;
  currentLang = code;
  if (rerender && storyData) renderPages(storyData);
  if (save) saveState();
}

// ── Server status ──────────────────────────────────────────────────────────
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

// ── Gemini aspect ratio ────────────────────────────────────────────────────
document.getElementById('geminiAspectPresets').addEventListener('click', e => {
  const btn = e.target.closest('.ar-btn');
  if (!btn) return;
  document.querySelectorAll('.ar-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  geminiAR = btn.dataset.ar;
  saveGenSettings();
});

// ── Gen settings persistence ───────────────────────────────────────────────
const GEN_KEY = 'monkeyking_gen_settings';

function saveGenSettings() {
  localStorage.setItem(GEN_KEY, JSON.stringify({ ar: geminiAR }));
}

function restoreGenSettings() {
  let s;
  try { s = JSON.parse(localStorage.getItem(GEN_KEY) || 'null'); } catch { return; }
  if (!s) return;

  // Accept both old key name (geminiAR) and new key (ar) for back-compat.
  // All other legacy keys (modelNum, canvasW, steps, etc.) are silently ignored.
  const savedAR = s.ar || s.geminiAR;
  if (savedAR) {
    geminiAR = savedAR;
    document.querySelectorAll('.ar-btn').forEach(
      b => b.classList.toggle('active', b.dataset.ar === savedAR)
    );
  }
}

// Export / Import / Reset
document.getElementById('saveGenSettingsBtn').addEventListener('click', () => {
  saveGenSettings();
  const settings = JSON.parse(localStorage.getItem(GEN_KEY) || '{}');
  const blob = new Blob([JSON.stringify(settings, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'gen-settings.json';
  a.click();
  URL.revokeObjectURL(a.href);
});

document.getElementById('loadGenSettingsFile').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    try {
      const incoming = JSON.parse(ev.target.result);
      localStorage.setItem(GEN_KEY, JSON.stringify(incoming));
      restoreGenSettings();
    } catch {
      alert('Invalid settings file.');
    }
  };
  reader.readAsText(file);
  e.target.value = '';
});

document.getElementById('resetGenSettingsBtn').addEventListener('click', () => {
  if (!confirm('Reset generation settings to defaults?')) return;
  localStorage.removeItem(GEN_KEY);
  geminiAR = '4:3';
  document.querySelectorAll('.ar-btn').forEach(
    b => b.classList.toggle('active', b.dataset.ar === '4:3')
  );
});

// ── Decompose ──────────────────────────────────────────────────────────────
autoGenBtn.addEventListener('click', async () => {
  if (await runDecompose()) {
    step3.scrollIntoView({ behavior: 'smooth', block: 'start' });
    queueBtn.click();
  }
});

async function runDecompose() {
  const concept    = sharedStoryInput.value.trim();
  const character  = sharedCharacterInput.value.trim();
  if (!concept && !character) {
    decomposeHint.textContent = 'Add a Character Description or a Story Prompt to begin.';
    sharedCharacterInput.focus();
    return false;
  }

  setDecomposeLoading(true);
  decomposeHint.textContent = 'Claude is writing your storybook… this takes ~20 seconds.';

  try {
    const res = await fetch(`${API}/decompose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        concept,
        style_suffix: sharedStyleInput.value.trim(),
        language: currentLang,
        character,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail ?? res.statusText);
    }
    storyData = await res.json();
    lastCheckApplied = false;
    Object.keys(generatedImages).forEach(k => delete generatedImages[k]);
    decomposeHint.textContent = '';
    renderPages(storyData);
    step2.classList.remove('hidden');
    step4.classList.remove('hidden');
    queueBtn.disabled = false;
    checkReadingsBtn.disabled = false;
    saveState();
    return true;
  } catch (err) {
    decomposeHint.textContent = `Error: ${err.message}`;
    return false;
  } finally {
    setDecomposeLoading(false);
  }
}

function setDecomposeLoading(on) {
  autoGenBtn.disabled   = on;
  checkReadingsBtn.disabled = on;
  autoGenLabel.textContent   = on ? 'Writing…' : '⚡ Generate Story and Pictures';
  autoGenSpinner.classList.toggle('hidden', !on);
}

// ── Render page cards ──────────────────────────────────────────────────────
function renderPages(data) {
  const meta = langMeta(currentLang);
  const titleNative  = data[meta.title_native_field]  ?? '';
  const titleReading = data[meta.title_reading_field] ?? '';
  bookTitleDisplay.textContent = `${titleNative} · ${data.book_title_en}`;
  bookTitleSub.textContent = titleReading;

  pageGrid.innerHTML = '';
  data.pages.forEach(pg => {
    const card = buildCard(pg);
    pageGrid.appendChild(card);
  });
}

function buildCard(pg) {
  const meta = langMeta(currentLang);
  const card = document.createElement('div');
  card.className = 'page-card';
  card.dataset.page = pg.page;

  const nativeVal  = pg[meta.native_field]  ?? '';
  const readingVal = pg[meta.reading_field] ?? '';

  card.innerHTML = `
    <div class="card-thumb-wrap" id="thumb-wrap-${pg.page}">
      <div class="thumb-content" id="thumb-${pg.page}">
        <div class="thumb-placeholder">Page ${pg.page} · no image yet</div>
      </div>
      <div class="card-progress hidden" id="card-progress-${pg.page}">
        <div class="card-progress-track">
          <div class="card-progress-fill" id="card-progress-fill-${pg.page}"></div>
        </div>
        <span class="card-progress-label" id="card-progress-label-${pg.page}">0 / 0</span>
      </div>
      <div class="thumb-upload-overlay" id="upload-overlay-${pg.page}">
        <button class="thumb-regen-btn" data-page="${pg.page}" title="Regenerate this page">↺</button>
        <label class="thumb-upload-btn" title="Upload image for this page">
          ↑ Upload
          <input type="file" accept="image/*" style="display:none" data-page="${pg.page}">
        </label>
      </div>
    </div>
    <div class="card-body">
      <div class="card-page-num">Page ${pg.page}</div>

      <div class="card-field native-field ${meta.font_class}">
        <label>${escHtml(meta.display_name)}</label>
        <textarea rows="2" data-field="${meta.native_field}">${escHtml(nativeVal)}</textarea>
      </div>

      <div class="card-field">
        <label>${escHtml(meta.reading_label)}</label>
        <textarea rows="2" data-field="${meta.reading_field}">${escHtml(readingVal)}</textarea>
      </div>

      <p class="card-readings-stale-hint hidden" id="readings-stale-${pg.page}">
        &#9888; Reading may be out of date — run Check Readings to correct.
      </p>

      <div class="card-field">
        <label>English</label>
        <textarea rows="2" data-field="en">${escHtml(pg.en)}</textarea>
      </div>

      <div class="card-field prompt-field">
        <label>Image Prompt</label>
        <textarea rows="4" data-field="image_prompt">${escHtml(pg.image_prompt)}</textarea>
      </div>
    </div>
    <div class="card-error hidden" id="card-error-${pg.page}"></div>
  `;
  return card;
}

// ── Manual image upload ────────────────────────────────────────────────────
async function uploadImageFile(pageNum, file) {
  if (!file || !file.type.startsWith('image/')) return;
  showThumbSpinner(pageNum);
  try {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API}/upload-image`, { method: 'POST', body: form });
    if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
    const { filename } = await res.json();
    const url = `${API}/image/${filename}`;
    generatedImages[pageNum] = { filename, url };
    showThumbImage(pageNum, url);
    saveState();
  } catch (err) {
    showThumbError(pageNum, err.message);
  }
}

// Wire up file input clicks and drag-and-drop on the page grid (event delegation)
pageGrid.addEventListener('change', e => {
  const input = e.target.closest('input[type="file"][data-page]');
  if (!input || !input.files[0]) return;
  uploadImageFile(parseInt(input.dataset.page), input.files[0]);
  input.value = '';   // reset so same file can be re-selected
});

// ── Gemini model helper ────────────────────────────────────────────────────
// Read the shared model from the CG draft localStorage key (same key used by
// Character Generator and written by Settings). The fallback must stay in
// sync with gemini_generator.GEMINI_MODELS[0].id.
function getGeminiModel() {
  try {
    const d = JSON.parse(localStorage.getItem('monkeyking_cg_draft') || '{}');
    return d.model || 'imagen-4.0-generate-001';
  } catch { return 'imagen-4.0-generate-001'; }
}

// ── Single-page regeneration ───────────────────────────────────────────────
const _regenActive = new Set();

pageGrid.addEventListener('click', e => {
  const btn = e.target.closest('.thumb-regen-btn');
  if (!btn) return;
  if (queueBtn.disabled) return; // block while full queue is running
  const pageNum = parseInt(btn.dataset.page);
  if (_regenActive.has(pageNum)) return;
  generateSinglePage(pageNum);
});

async function generateSinglePage(pageNum) {
  if (_regenActive.has(pageNum)) return;
  _regenActive.add(pageNum);

  const current = readCard(pageNum);
  showThumbSpinner(pageNum);
  showCardProgress(pageNum, 0, 1);

  const genBody = {
    prompt:              current.image_prompt,
    style_prompt:        sharedStyleInput.value.trim(),
    provider:            'gemini',
    gemini_model:        getGeminiModel(),
    gemini_aspect_ratio: geminiAR,
  };

  try {
    const res = await fetch(`${API}/generate/stream`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(genBody),
    });
    if (!res.ok) throw new Error(await parseErrorBody(res));

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buf     = '';
    let   result  = null;

    outer: while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        let evt;
        try { evt = JSON.parse(line.slice(6)); } catch { continue; }
        if (evt.error) throw new Error(evt.error);
        if (evt.done) { result = evt; break outer; }
        showCardProgress(pageNum, evt.step, evt.total);
      }
    }

    if (!result) throw new Error('Stream ended without result.');
    const url = `${API}/image/${result.filename}`;
    generatedImages[pageNum] = { filename: result.filename, url };
    hideCardProgress(pageNum);
    showThumbImage(pageNum, url);
    saveState();
  } catch (err) {
    hideCardProgress(pageNum);
    showThumbError(pageNum, err.message);
  } finally {
    _regenActive.delete(pageNum);
  }
}

pageGrid.addEventListener('dragover', e => {
  const wrap = e.target.closest('.card-thumb-wrap');
  if (!wrap) return;
  e.preventDefault();
  wrap.classList.add('drag-over');
});

pageGrid.addEventListener('dragleave', e => {
  const wrap = e.target.closest('.card-thumb-wrap');
  if (wrap && !wrap.contains(e.relatedTarget)) wrap.classList.remove('drag-over');
});

pageGrid.addEventListener('drop', e => {
  const wrap = e.target.closest('.card-thumb-wrap');
  if (!wrap) return;
  e.preventDefault();
  wrap.classList.remove('drag-over');
  const pageNum = parseInt(wrap.id.replace('thumb-wrap-', ''));
  const file = e.dataTransfer.files[0];
  uploadImageFile(pageNum, file);
});

// Read current card values (user may have edited them).
// characters[] is NOT in the DOM — it is carried forward from storyData so it
// survives save/export round-trips.  When a card is flagged data-readings-stale
// the array is dropped (set to null) so a stale annotation is never exported
// as wrong ruby — it degrades to the deterministic fallback in renderRubyText.
function readCard(pageNum) {
  const card = pageGrid.querySelector(`[data-page="${pageNum}"]`);
  if (!card) return null;
  const meta = langMeta(currentLang);
  const get = f => card.querySelector(`[data-field="${f}"]`)?.value ?? '';

  // Look up the authoritative characters[] from storyData (not the DOM).
  const src = storyData?.pages?.find(p => p.page === pageNum);
  const stale = card.dataset.readingsStale === 'true';
  const characters = stale ? null : (src?.characters ?? null);

  return {
    page: pageNum,
    [meta.native_field]:  get(meta.native_field),
    [meta.reading_field]: get(meta.reading_field),
    en: get('en'),
    image_prompt: get('image_prompt'),
    characters,
  };
}

// ── Image generation queue ─────────────────────────────────────────────────
const generatedImages = {};   // page num → { filename, url }
let stopRequested = false;

stopBtn.addEventListener('click', () => {
  stopRequested = true;
  stopBtn.disabled = true;
  stopBtn.textContent = 'Stopping…';
});

queueBtn.addEventListener('click', async () => {
  if (!storyData) return;
  stopRequested = false;
  setQueueLoading(true);
  progressWrap.classList.remove('hidden');

  const pages = storyData.pages;
  const total  = pages.length;
  let doneCount = 0;

  updateProgress(0, total);

  for (const pg of pages) {
    if (stopRequested) {
      progressText.textContent += ' · stopped';
      break;
    }

    const current = readCard(pg.page);

    showThumbSpinner(pg.page);
    showCardProgress(pg.page, 0, 1);

    try {
      const genBody = {
        prompt:              current.image_prompt,
        style_prompt:        sharedStyleInput.value.trim(),
        provider:            'gemini',
        gemini_model:        getGeminiModel(),
        gemini_aspect_ratio: geminiAR,
      };

      const res = await fetch(`${API}/generate/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(genBody),
      });
      if (!res.ok) throw new Error(await parseErrorBody(res));

      // Read SSE stream
      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let   buf     = '';
      let   result  = null;

      outer: while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let evt;
          try { evt = JSON.parse(line.slice(6)); } catch { continue; }
          if (evt.error) throw new Error(evt.error);
          if (evt.done) { result = evt; break outer; }
          showCardProgress(pg.page, evt.step, evt.total);
          updateAggregateStep(doneCount, total, evt.step, evt.total);
        }
      }

      if (!result) throw new Error('Stream ended without result.');
      const url = `${API}/image/${result.filename}`;
      generatedImages[pg.page] = { filename: result.filename, url };
      hideCardProgress(pg.page);
      showThumbImage(pg.page, url);
      saveState();
    } catch (err) {
      hideCardProgress(pg.page);
      showThumbError(pg.page, err.message);
    }

    doneCount++;
    updateProgress(doneCount, total);
  }

  setQueueLoading(false);
});

function setQueueLoading(on) {
  queueBtn.disabled = on;
  checkReadingsBtn.disabled = on;
  queueLabel.textContent = on ? 'Generating…' : '⚡ Generate All Images';
  queueSpinner.classList.toggle('hidden', !on);
  stopBtn.classList.toggle('hidden', !on);
  stopBtn.disabled = false;
  stopBtn.textContent = '■ Stop';
}

// ── Aggregate progress ─────────────────────────────────────────────────────
function updateProgress(done, total) {
  const pct = total ? (done / total) * 100 : 0;
  progressBar.style.width = `${pct}%`;
  progressText.textContent = `${done} / ${total} images`;
}

function updateAggregateStep(doneImages, totalImages, step, totalSteps) {
  // Blend completed images + fraction through current image
  const overall = ((doneImages + step / totalSteps) / totalImages) * 100;
  progressBar.style.width = `${overall}%`;
  progressText.textContent = `Image ${doneImages + 1} / ${totalImages} · step ${step} / ${totalSteps}`;
}

// ── Per-card progress ──────────────────────────────────────────────────────
function showCardProgress(pageNum, step, total) {
  const bar   = document.getElementById(`card-progress-fill-${pageNum}`);
  const label = document.getElementById(`card-progress-label-${pageNum}`);
  const wrap  = document.getElementById(`card-progress-${pageNum}`);
  if (!bar || !label || !wrap) return;
  const pct = total > 0 ? Math.round((step / total) * 100) : 0;
  bar.style.width   = `${pct}%`;
  label.textContent = `${step} / ${total}`;
  wrap.classList.remove('hidden');
}

function hideCardProgress(pageNum) {
  const wrap = document.getElementById(`card-progress-${pageNum}`);
  if (wrap) wrap.classList.add('hidden');
}

// ── Thumb helpers ──────────────────────────────────────────────────────────
async function parseErrorBody(res) {
  const text = await res.text();
  try {
    const j = JSON.parse(text);
    return j.detail ?? j.message ?? text;
  } catch { return text; }
}

function clearCardError(pageNum) {
  const el = document.getElementById(`card-error-${pageNum}`);
  if (!el) return;
  el.textContent = '';
  el.classList.add('hidden');
}

function showThumbSpinner(pageNum) {
  clearCardError(pageNum);
  const el = document.getElementById(`thumb-${pageNum}`);
  if (!el) return;
  el.innerHTML = `<div class="thumb-spinner"><div class="spinner"></div></div>`;
}

function showThumbImage(pageNum, url) {
  clearCardError(pageNum);
  const el = document.getElementById(`thumb-${pageNum}`);
  if (!el) return;
  el.innerHTML = `<img src="${url}" alt="Page ${pageNum}" style="width:100%;height:100%;object-fit:cover;display:block;">`;
}

function showThumbError(pageNum, msg) {
  const thumb = document.getElementById(`thumb-${pageNum}`);
  if (thumb) thumb.innerHTML = `<div class="thumb-placeholder">⚠ Page ${pageNum} failed</div>`;
  const errEl = document.getElementById(`card-error-${pageNum}`);
  if (errEl) {
    errEl.textContent = msg;
    errEl.classList.remove('hidden');
  }
}

// ── Export storybook HTML ──────────────────────────────────────────────────
printBtn.addEventListener('click', async () => {
  printBtn.disabled = true;
  printLabel.textContent = 'Building…';
  printSpinner.classList.remove('hidden');
  try {
    await openPrintWindow(currentProject(), API);
  } finally {
    printBtn.disabled = false;
    printLabel.textContent = '🖨 Print / Save as PDF';
    printSpinner.classList.add('hidden');
  }
});

exportBtn.addEventListener('click', async () => {
  exportBtn.disabled = true;
  exportBtn.querySelector('span').textContent = 'Building…';
  try {
    await downloadStorybookHTML(currentProject(), API);
  } finally {
    exportBtn.disabled = false;
    exportBtn.querySelector('span').textContent = '📖 Export as HTML';
  }
});

galleryBtn.addEventListener('click', async () => {
  if (!storyData) return;
  galleryBtn.disabled = true;
  galleryLabel.textContent = 'Saving…';
  gallerySpinner.classList.remove('hidden');
  try {
    const res = await fetch(`${API}/gallery`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(currentProject()),
    });
    if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
    const data = await res.json();
    galleryLabel.textContent = '✓ Saved!';
    setTimeout(() => { galleryLabel.textContent = '☁ Save to Gallery'; }, 2000);
  } catch (err) {
    alert(`Gallery save failed: ${err.message}`);
    galleryLabel.textContent = '☁ Save to Gallery';
  } finally {
    galleryBtn.disabled = false;
    gallerySpinner.classList.add('hidden');
  }
});

function currentProject() {
  const editedPages = storyData.pages.map(pg => readCard(pg.page));
  return {
    version:          1,
    saved_at:         new Date().toISOString(),
    concept:          sharedStoryInput.value.trim(),
    character:        sharedCharacterInput.value.trim(),
    style_prompt:     sharedStyleInput.value.trim(),
    story:            { ...storyData, language: currentLang, pages: editedPages },
    generated_images: Object.fromEntries(
      Object.entries(generatedImages).map(([k, v]) => [k, v.filename])
    ),
  };
}



// ── Staleness tracking ─────────────────────────────────────────────────────
// When the user edits a native-field textarea after a Check Readings Apply,
// flag that card as stale so the exported characters[] is dropped.
pageGrid.addEventListener('input', e => {
  if (!lastCheckApplied) return;
  const meta = langMeta(currentLang);
  const ta = e.target.closest(`[data-field="${meta.native_field}"]`);
  if (!ta) return;
  const card = ta.closest('.page-card');
  if (!card) return;
  card.dataset.readingsStale = 'true';
  const pageNum = parseInt(card.dataset.page);
  const hint = document.getElementById(`readings-stale-${pageNum}`);
  if (hint) hint.classList.remove('hidden');
});

// ── Check Readings ─────────────────────────────────────────────────────────
function setCheckReadingsLoading(on) {
  checkReadingsBtn.disabled = on;
  checkReadingsLabel.textContent = on ? 'Checking…' : '✦ Check Readings';
  checkReadingsSpinner.classList.toggle('hidden', !on);
}

checkReadingsBtn.addEventListener('click', async () => {
  if (!storyData) return;

  setCheckReadingsLoading(true);
  checkReadingsHint.textContent = 'Claude is checking your readings… this usually takes ~20 seconds.';

  // Gather current pages using the fixed readCard (includes characters[])
  const pages = storyData.pages.map(pg => readCard(pg.page)).filter(Boolean);

  try {
    const meta = langMeta(currentLang);
    const recheckBody = {
      language: currentLang,
      pages,
      book_title_native:     storyData[meta.title_native_field]  ?? null,
      book_title_reading:    storyData[meta.title_reading_field] ?? null,
      book_title_characters: storyData.book_title_characters     ?? null,
    };
    const res = await fetch(`${API}/recheck-readings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(recheckBody),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      if (res.status === 503) {
        checkReadingsHint.textContent =
          'No Anthropic key set — add it in Settings (⚙) to use this feature.';
      } else {
        checkReadingsHint.textContent = `Error: ${err.detail ?? res.statusText}`;
      }
      return;
    }

    const data = await res.json();
    checkReadingsHint.textContent = '';
    openCheckReadingsModal(data);
  } catch (err) {
    checkReadingsHint.textContent =
      err.message && err.message.includes('fetch')
        ? 'Could not reach the server — check your connection and try again.'
        : `Error: ${err.message}`;
  } finally {
    setCheckReadingsLoading(false);
  }
});

// ── Check Readings modal ───────────────────────────────────────────────────
let _crPendingData = null;   // server response held until Apply / Cancel

function openCheckReadingsModal(data) {
  _crPendingData = data;

  const meta = langMeta(currentLang);
  const returnedPages = data.pages || [];

  // Detect changed pages by comparing returned native + reading against current card values.
  // Also treat a changed characters[] (non-null returned vs. stored) as changed.
  const changedPages = [];
  const unchangedCount = { n: 0 };

  for (const rp of returnedPages) {
    const card = pageGrid.querySelector(`[data-page="${rp.page}"]`);
    const currentNative  = card?.querySelector(`[data-field="${meta.native_field}"]`)?.value?.trim() ?? '';
    const currentReading = card?.querySelector(`[data-field="${meta.reading_field}"]`)?.value?.trim() ?? '';
    const returnedNative  = (rp[meta.native_field]  ?? '').trim();
    const returnedReading = (rp[meta.reading_field] ?? '').trim();

    const src = storyData?.pages?.find(p => p.page === rp.page);
    const charsChanged = rp.characters && JSON.stringify(rp.characters) !== JSON.stringify(src?.characters ?? null);

    if (returnedNative !== currentNative || returnedReading !== currentReading || charsChanged) {
      changedPages.push({ rp, currentNative, currentReading, returnedNative, returnedReading });
    } else {
      unchangedCount.n++;
    }
  }

  // Build modal content
  const titleEl = document.getElementById('checkReadingsDialogTitle');
  const summaryEl = document.getElementById('checkReadingsSummary');
  const bodyEl = document.getElementById('checkReadingsBody');
  const footerEl = document.getElementById('checkReadingsFooter');

  bodyEl.innerHTML = '';
  footerEl.innerHTML = '';

  if (changedPages.length === 0) {
    titleEl.textContent = '✦ Readings Check — all good!';
    summaryEl.textContent = 'Your readings look correct — no corrections found.';
    summaryEl.style.borderBottom = 'none';
    bodyEl.style.display = 'none';

    const closeBtn = document.createElement('button');
    closeBtn.className = 'settings-btn';
    closeBtn.textContent = 'Close';
    closeBtn.addEventListener('click', closeCheckReadingsModal);
    footerEl.appendChild(closeBtn);
  } else {
    titleEl.textContent = `✦ Readings Check — ${changedPages.length} page${changedPages.length !== 1 ? 's' : ''} updated`;
    summaryEl.textContent = unchangedCount.n > 0
      ? `${unchangedCount.n} page${unchangedCount.n !== 1 ? 's' : ''} unchanged`
      : '';
    summaryEl.style.borderBottom = '';
    bodyEl.style.display = '';

    // Native font per language
    const nativeFontStyle = {
      zh: "'Noto Serif SC', 'SimSun', serif",
      ja: "'Noto Serif JP', 'Yu Mincho', serif",
      ko: "'Noto Serif KR', 'Nanum Myeongjo', serif",
    }[currentLang] || "'Noto Serif SC', 'SimSun', serif";

    for (const { rp, currentNative, currentReading, returnedNative, returnedReading } of changedPages) {
      const card = document.createElement('div');
      card.className = 'cr-page-card';
      card.innerHTML = `
        <p class="cr-page-label">Page ${rp.page}</p>
        <div class="cr-field">
          <span class="cr-field-label">Native</span>
          <p class="cr-field-value cr-native" style="font-family:${nativeFontStyle}">${escHtml(returnedNative || currentNative)}</p>
        </div>
        <div class="cr-field">
          <span class="cr-field-label">Before</span>
          <p class="cr-field-value cr-before">${escHtml(currentReading)}</p>
        </div>
        <div class="cr-field">
          <span class="cr-field-label">After</span>
          <p class="cr-field-value cr-after">${escHtml(returnedReading)}</p>
        </div>
      `;
      bodyEl.appendChild(card);
    }

    // Apply button
    const applyBtn = document.createElement('button');
    applyBtn.id = 'checkReadingsApplyBtn';
    applyBtn.className = 'generate-btn';
    applyBtn.textContent = `Apply ${changedPages.length} correction${changedPages.length !== 1 ? 's' : ''}`;
    applyBtn.addEventListener('click', applyCheckReadings);
    footerEl.appendChild(applyBtn);

    // Cancel button
    const cancelBtn = document.createElement('button');
    cancelBtn.id = 'checkReadingsCancelBtn';
    cancelBtn.className = 'generate-btn cr-cancel-btn';
    cancelBtn.textContent = 'Cancel — keep current';
    cancelBtn.addEventListener('click', closeCheckReadingsModal);
    footerEl.appendChild(cancelBtn);
  }

  // Show modal and move focus
  checkReadingsOverlay.classList.remove('hidden');
  checkReadingsDialog.focus();

  // Focus trap
  checkReadingsDialog.addEventListener('keydown', trapFocus);
  document.addEventListener('keydown', handleModalEscape);
}

function closeCheckReadingsModal() {
  checkReadingsOverlay.classList.add('hidden');
  checkReadingsDialog.removeEventListener('keydown', trapFocus);
  document.removeEventListener('keydown', handleModalEscape);
  _crPendingData = null;
  checkReadingsBtn.focus();
}

function handleModalEscape(e) {
  if (e.key === 'Escape') closeCheckReadingsModal();
}

function trapFocus(e) {
  if (e.key !== 'Tab') return;
  const focusable = Array.from(
    checkReadingsDialog.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
  ).filter(el => !el.disabled);
  if (!focusable.length) { e.preventDefault(); return; }
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
}

// Close the modal by clicking the backdrop (outside the dialog box)
checkReadingsOverlay.addEventListener('click', e => {
  if (e.target === checkReadingsOverlay) closeCheckReadingsModal();
});

document.getElementById('checkReadingsCloseBtn').addEventListener('click', closeCheckReadingsModal);

function applyCheckReadings() {
  if (!_crPendingData) return;
  const returnedPages = _crPendingData.pages || [];
  const meta = langMeta(currentLang);

  // Validate page count matches before applying anything
  if (returnedPages.length !== storyData.pages.length) {
    checkReadingsHint.textContent =
      'Unexpected response — page count mismatch. Your story was not changed.';
    closeCheckReadingsModal();
    return;
  }

  // Validate all returned page numbers exist in storyData
  const storyPageNums = new Set(storyData.pages.map(p => p.page));
  for (const rp of returnedPages) {
    if (!storyPageNums.has(rp.page)) {
      checkReadingsHint.textContent =
        'Unexpected response — page number mismatch. Your story was not changed.';
      closeCheckReadingsModal();
      return;
    }
  }

  // Apply corrections
  for (const rp of returnedPages) {
    const sdIdx = storyData.pages.findIndex(p => p.page === rp.page);
    if (sdIdx === -1) continue;

    const returnedNative  = rp[meta.native_field]  ?? '';
    const returnedReading = rp[meta.reading_field] ?? '';

    // Write corrected native + reading + characters into storyData
    storyData.pages[sdIdx][meta.native_field]  = returnedNative;
    storyData.pages[sdIdx][meta.reading_field] = returnedReading;
    if (rp.characters) {
      storyData.pages[sdIdx].characters = rp.characters;
    }

    // Write corrected values into the card textareas
    const card = pageGrid.querySelector(`[data-page="${rp.page}"]`);
    if (card) {
      const nativeTa  = card.querySelector(`[data-field="${meta.native_field}"]`);
      const readingTa = card.querySelector(`[data-field="${meta.reading_field}"]`);
      if (nativeTa)  nativeTa.value  = returnedNative;
      if (readingTa) readingTa.value = returnedReading;

      // Clear stale flag and hint for this card
      delete card.dataset.readingsStale;
      const hint = document.getElementById(`readings-stale-${rp.page}`);
      if (hint) hint.classList.add('hidden');
    }
  }

  // Silently merge title characters if the server returned them (no diff-modal row)
  if (_crPendingData.book_title_characters) {
    storyData.book_title_characters = _crPendingData.book_title_characters;
  }

  lastCheckApplied = true;
  saveState();
  closeCheckReadingsModal();
}

// ── localStorage state persistence ────────────────────────────────────────
const LS_KEY      = 'monkeyking_bb_state';
const LANG_KEY    = 'monkeyking_bb_lang';   // preferred language, survives Clear

// Shared input listeners are wired in init (after reconciliation) via
// SharedInputs.bindFields with debounce:0 and populate:false.
// See wireSharedInputListeners() below.

function saveState() {
  // Always persist the chosen language so it survives a reload even before a story exists.
  try { localStorage.setItem(LANG_KEY, currentLang); } catch { /* quota */ }
  if (!storyData) return;
  const editedPages = storyData.pages.map(pg => readCard(pg.page));
  const state = {
    version:             1,
    concept:             sharedStoryInput.value.trim(),
    character:           sharedCharacterInput.value.trim(),
    style_prompt:        sharedStyleInput.value.trim(),
    story:               { ...storyData, language: currentLang, pages: editedPages },
    generated_images:    Object.fromEntries(
      Object.entries(generatedImages).map(([k, v]) => [k, v.filename])
    ),
  };
  try { localStorage.setItem(LS_KEY, JSON.stringify(state)); } catch { /* quota */ }
}

function clearProject({ keepInputs = false } = {}) {
  localStorage.removeItem(LS_KEY);

  storyData = null;
  lastCheckApplied = false;
  Object.keys(generatedImages).forEach(k => delete generatedImages[k]);

  // keepInputs leaves the shared Character/Style/Story fields (and the shared
  // store) untouched — used when starting a fresh book from synced inputs.
  if (!keepInputs) {
    sharedStoryInput.value     = '';
    sharedCharacterInput.value = '';
    sharedStyleInput.value     = '';
    // Clear the character field in shared store too
    SharedInputs.patch({ character: '' });
  }

  pageGrid.innerHTML      = '';
  step2.classList.add('hidden');
  step4.classList.add('hidden');
  queueBtn.disabled          = true;
  checkReadingsBtn.disabled  = true;
  decomposeHint.textContent  = '';
  checkReadingsHint.textContent = '';
}

// ── Shared inputs — restore and wire live-sync ─────────────────────────────
// Simplified restore: just set the three .value fields from the shared store.
// Called by the reconciliation branches in init (before the live listener is attached).
function restoreSharedInputs() {
  const s = SharedInputs.read();
  // Set values directly — never dispatch synthetic input events
  sharedStoryInput.value     = s.story;
  sharedCharacterInput.value = s.character;
  sharedStyleInput.value     = s.style;
}

// Wire the live listener via bindFields. populate:false because BB populates via
// its own reconciliation branches (restoreProject/restoreState/restoreSharedInputs).
// debounce:0 preserves "value persisted before navigation" guarantee.
// Called AFTER all reconciliation branches complete.
function wireSharedInputListeners() {
  SharedInputs.bindFields(
    { character: 'sharedCharacterInput', story: 'sharedStoryInput', style: 'sharedStyleInput' },
    { debounce: 0, populate: false, onRemote: function() { autoExpandIfContent(); } }
  );
}

// Auto-expand the collapsible <details> when Story or Style has content.
// Called after populate and after each reconciliation branch completes.
function autoExpandIfContent() {
  var story   = document.getElementById('sharedStoryInput');
  var style   = document.getElementById('sharedStyleInput');
  var details = document.getElementById('sharedMoreOptions');
  if (details && ((story && story.value.trim()) || (style && style.value.trim()))) {
    details.open = true;
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  restoreGenSettings();

  // Apply remembered language before restoring state (restoreProject will override
  // if the loaded project specifies its own language).
  const savedLang = localStorage.getItem(LANG_KEY);
  setLanguage(savedLang || DEFAULT_LANG, { rerender: false, save: false });

  // Load a gallery book if linked from Gallery page; otherwise restore localStorage
  const params    = new URLSearchParams(window.location.search);
  const galleryId = params.get('gallery_id');
  if (galleryId) {
    try {
      const res     = await fetch(`${API}/gallery/${encodeURIComponent(galleryId)}`);
      if (!res.ok) throw new Error('Not found');
      const project = await res.json();
      await restoreProject(project);
      // After gallery load, push the loaded values INTO the shared store
      // so other tabs see the loaded book — but never overwrite project load FROM shared store
      SharedInputs.patch({
        story:     sharedStoryInput.value,
        style:     sharedStyleInput.value,
        character: sharedCharacterInput.value,
      });
    } catch (err) {
      console.warn('Could not load gallery book:', err.message);
      // Fall through to shared restore
      restoreSharedInputs();
    }
  } else {
    // 2. Reconcile the saved book (LS_KEY) with the synced cross-tab inputs.
    const savedState = readSavedState();
    const shared     = SharedInputs.read();

    if (savedState && sharedConflictsWithSaved(savedState, shared)) {
      // The saved book and the inputs edited in another tab disagree. Ask the
      // user which to keep instead of silently clobbering one with the other.
      const keepPrevious = confirm(
        'Your saved book here is different from the Character / Style / Story ' +
        'you edited in another tab.\n\n' +
        'OK — Continue your saved book (keep its text).\n' +
        'Cancel — Start a new book using the inputs from the other tab.'
      );
      if (keepPrevious) {
        await restoreState(savedState);
        SharedInputs.patch({
          story:     sharedStoryInput.value,
          style:     sharedStyleInput.value,
          character: sharedCharacterInput.value,
        });
      } else {
        // Start fresh: drop the saved book but keep the synced inputs intact.
        clearProject({ keepInputs: true });
        restoreSharedInputs();
      }
    } else if (savedState) {
      // No conflict — restore the saved book and mirror it to the shared store.
      await restoreState(savedState);
      SharedInputs.patch({
        story:     sharedStoryInput.value,
        style:     sharedStyleInput.value,
        character: sharedCharacterInput.value,
      });
    } else {
      // 3. No saved story — restore from shared store
      restoreSharedInputs();
    }
  }

  // 4. Wire live-sync listeners
  wireSharedInputListeners();

  // 5. Auto-expand collapsible if Story or Style has content after all reconciliation branches
  autoExpandIfContent();
})();

async function restoreProject(project) {
  if (!project.story?.pages) return false;

  // Adopt the project's language (default zh for legacy projects without one).
  // Note: the subsequent saveState() call will write this language back to
  // monkeyking_bb_lang, so the Settings select reflects the opened book's
  // language — this is intentional, not a bug.
  const projectLang = project.story.language || project.language || DEFAULT_LANG;
  setLanguage(projectLang, { rerender: false, save: false });

  sharedStoryInput.value     = project.concept      ?? '';
  sharedCharacterInput.value = project.character    ?? '';
  sharedStyleInput.value     = project.style_prompt  ?? '';
  storyData = project.story;

  Object.keys(generatedImages).forEach(k => delete generatedImages[k]);

  lastCheckApplied = false;
  renderPages(storyData);
  step2.classList.remove('hidden');
  step4.classList.remove('hidden');
  queueBtn.disabled         = false;
  checkReadingsBtn.disabled = false;

  if (project.generated_images) {
    await Promise.allSettled(
      Object.entries(project.generated_images).map(async ([pageNum, filename]) => {
        const url = `${API}/image/${filename}`;
        const res = await fetch(url, { method: 'HEAD' });
        if (res.ok) {
          generatedImages[parseInt(pageNum)] = { filename, url };
          showThumbImage(parseInt(pageNum), url);
        }
      })
    );
  }

  step2.scrollIntoView({ behavior: 'smooth', block: 'start' });
  return true;
}

// Parse the saved Book Builder state (LS_KEY) without applying it. Returns the
// state object, or null if absent/corrupted/lacking a story.
function readSavedState() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const state = JSON.parse(raw);
    if (!state.story?.pages) return null;
    return state;
  } catch { return null; }
}

async function restoreState(state) {
  // state is optional — read it from storage when not supplied.
  if (!state) state = readSavedState();
  if (!state) return false;
  return await restoreProject(state);
}

// True when the synced shared inputs (edited in another tab) hold content that
// differs from the saved book — i.e. restoring the book would silently discard
// the user's newer cross-tab edits.
function sharedConflictsWithSaved(state, shared) {
  const norm = v => (v || '').trim();
  const sStory = norm(shared.story), sChar = norm(shared.character), sStyle = norm(shared.style);
  const sharedHasContent = sStory || sChar || sStyle;
  const differs =
    norm(state.concept)      !== sStory ||
    norm(state.character)    !== sChar  ||
    norm(state.style_prompt) !== sStyle;
  return Boolean(sharedHasContent && differs);
}

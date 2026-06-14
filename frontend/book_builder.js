const API = window.location.origin;

// ── Language registry (mirrors languages.py, minus prompts) ────────────────
const LANG_META = {
  zh: {
    code: 'zh', display_name: '中文', english_name: 'Chinese',
    native_field: 'zh', reading_field: 'pinyin', reading_label: 'Pinyin',
    title_native_field: 'book_title_zh', title_reading_field: 'book_title_pinyin',
    font_class: 'lang-zh',
    native_placeholder: '故事书', reading_placeholder: 'Gùshì shū',
    table_native_aliases: ['汉字', '中文', 'chinese', 'zh', 'hanzi'],
    table_reading_aliases: ['pinyin'],
    table_headers_hint: '(CSV or tab-separated · headers: Page, Pinyin, 汉字, English, Illustration Prompt)',
  },
  ja: {
    code: 'ja', display_name: '日本語', english_name: 'Japanese',
    native_field: 'ja', reading_field: 'romaji', reading_label: 'Romaji',
    title_native_field: 'book_title_ja', title_reading_field: 'book_title_romaji',
    font_class: 'lang-ja',
    native_placeholder: '物語', reading_placeholder: 'monogatari',
    table_native_aliases: ['日本語', 'japanese', 'ja', 'kanji'],
    table_reading_aliases: ['romaji', 'romaji reading', 'hepburn', 'reading'],
    table_headers_hint: '(CSV or tab-separated · headers: Page, Romaji, 日本語, English, Illustration Prompt)',
  },
  ko: {
    code: 'ko', display_name: '한국어', english_name: 'Korean',
    native_field: 'ko', reading_field: 'romanization', reading_label: 'Romanization',
    title_native_field: 'book_title_ko', title_reading_field: 'book_title_romanization',
    font_class: 'lang-ko',
    native_placeholder: '이야기책', reading_placeholder: 'iyagichaek',
    table_native_aliases: ['한국어', 'korean', 'ko', 'hangul'],
    table_reading_aliases: ['romanization', 'romanisation', 'rr'],
    table_headers_hint: '(CSV or tab-separated · headers: Page, Romanization, 한국어, English, Illustration Prompt)',
  },
};
const DEFAULT_LANG = 'zh';

function langMeta(code) {
  return LANG_META[code] || LANG_META[DEFAULT_LANG];
}

// ── State ──────────────────────────────────────────────────────────────────
let storyData = null;   // DecomposeResponse from server
let canvasW = 512, canvasH = 512;
let provider = 'sd';
let geminiAR = '1:1';
let currentLang = DEFAULT_LANG;

// ── DOM refs ───────────────────────────────────────────────────────────────
const conceptInput      = document.getElementById('conceptInput');
const characterInput    = document.getElementById('characterInput');
const stylePromptInput  = document.getElementById('stylePromptInput');
const saveProjectBtn    = document.getElementById('saveProjectBtn');
const clearProjectBtn   = document.getElementById('clearProjectBtn');
const loadProjectFile   = document.getElementById('loadProjectFile');
const decomposeBtn      = document.getElementById('decomposeBtn');
const importTitleEn          = document.getElementById('importTitleEn');
const importTitleNative      = document.getElementById('importTitleNative');
const importTitleReading     = document.getElementById('importTitleReading');
const importTitleNativeLabel = document.getElementById('importTitleNativeLabel');
const importTitleReadingLabel= document.getElementById('importTitleReadingLabel');
const tableHeadersHint  = document.getElementById('tableHeadersHint');
const tableInput        = document.getElementById('tableInput');
const parseTableBtn     = document.getElementById('parseTableBtn');
const parseHint         = document.getElementById('parseHint');
const langToggle        = document.getElementById('langToggle');
const decomposeLabel  = document.getElementById('decomposeLabel');
const decomposeSpinner= document.getElementById('decomposeSpinner');
const decomposeHint   = document.getElementById('decomposeHint');
const autoGenBtn      = document.getElementById('autoGenBtn');
const autoGenLabel    = document.getElementById('autoGenLabel');
const autoGenSpinner  = document.getElementById('autoGenSpinner');

const step2           = document.getElementById('step2');
const bookTitleDisplay= document.getElementById('bookTitleDisplay');
const bookTitleSub    = document.getElementById('bookTitleSub');
const pageGrid        = document.getElementById('pageGrid');

const step3           = document.getElementById('step3');
const modelSel        = document.getElementById('modelSelect');
const genStylePrompt  = document.getElementById('genStylePrompt');
const genNegPrompt    = document.getElementById('genNegPrompt');
const negToggle       = document.getElementById('negToggle');
const stepsEl         = document.getElementById('steps');
const stepsVal        = document.getElementById('stepsVal');
const cfgEl           = document.getElementById('cfg');
const cfgVal          = document.getElementById('cfgVal');
const samplerSel      = document.getElementById('samplerSelect');
const clipSkipSel     = document.getElementById('clipSkipSelect');
const geminiModelSel  = document.getElementById('geminiModelSelect');
const loraSelect      = document.getElementById('loraSelect');
const loraScaleRow    = document.getElementById('loraScaleRow');
const loraScaleEl     = document.getElementById('loraScale');
const loraScaleVal    = document.getElementById('loraScaleVal');
const loraSelect2     = document.getElementById('loraSelect2');
const loraScaleRow2   = document.getElementById('loraScaleRow2');
const loraScaleEl2    = document.getElementById('loraScale2');
const loraScaleVal2   = document.getElementById('loraScaleVal2');
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

// Step 1 style presets (shared-inputs-inline section, id="stylePresets")
const step1StylePresets = document.getElementById('stylePresets');

// ── Language selector ──────────────────────────────────────────────────────
function applyLanguageToUI(code) {
  const meta = langMeta(code);
  // Toggle button highlight
  langToggle.querySelectorAll('.lang-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.lang === code));

  // Import-section labels and placeholders
  importTitleNativeLabel.textContent  = `Book Title (${meta.english_name})`;
  importTitleReadingLabel.textContent = `Title ${meta.reading_label}`;
  importTitleNative.placeholder  = meta.native_placeholder;
  importTitleReading.placeholder = meta.reading_placeholder;
  if (tableHeadersHint) tableHeadersHint.textContent = meta.table_headers_hint;
}

function setLanguage(code, { rerender = true, save = true } = {}) {
  if (!LANG_META[code]) code = DEFAULT_LANG;
  currentLang = code;
  applyLanguageToUI(code);
  if (rerender && storyData) renderPages(storyData);
  if (save) saveState();
}

langToggle.addEventListener('click', e => {
  const btn = e.target.closest('.lang-btn');
  if (!btn) return;
  const code = btn.dataset.lang;
  if (code === currentLang) return;
  // Switching language with an existing story would leave card fields empty
  // (the native/reading field names differ). Confirm before discarding it.
  if (storyData && !confirm('Switching language will clear the current book. Continue?')) return;
  if (storyData) clearProject();
  setLanguage(code);
});

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

async function loadModels() {
  try {
    const res  = await fetch(`${API}/models`);
    const data = await res.json();
    modelSel.innerHTML = '';
    data.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = `${m.id}. ${m.name}${m.loaded ? ' ✓' : ''}`;
      if (m.loaded) opt.selected = true;
      modelSel.appendChild(opt);
    });
  } catch {
    modelSel.innerHTML = '<option value="">Unavailable</option>';
  }
}

async function loadLoras() {
  try {
    const res  = await fetch(`${API}/loras`);
    const data = await res.json();
    const opts = '<option value="">— none —</option>' +
      (data.loras || []).map(l => `<option value="${l.num}">${l.name}</option>`).join('');
    loraSelect.innerHTML  = opts;
    loraSelect2.innerHTML = opts;
    loraScaleRow.classList.toggle('hidden',  !loraSelect.value);
    loraScaleRow2.classList.toggle('hidden', !loraSelect2.value);
  } catch {
    // no loras available — leave dropdown empty
  }
}

loraSelect.addEventListener('change', () => {
  loraScaleRow.classList.toggle('hidden', !loraSelect.value);
});
loraScaleEl.addEventListener('input', () => {
  loraScaleVal.textContent = parseFloat(loraScaleEl.value).toFixed(2);
});
loraSelect2.addEventListener('change', () => {
  loraScaleRow2.classList.toggle('hidden', !loraSelect2.value);
});
loraScaleEl2.addEventListener('input', () => {
  loraScaleVal2.textContent = parseFloat(loraScaleEl2.value).toFixed(2);
});

// ── Style presets (Step 1 shared inputs — stylePresets) ────────────────────
step1StylePresets.addEventListener('click', e => {
  const btn = e.target.closest('.preset');
  if (!btn) return;
  stylePromptInput.value = btn.dataset.suffix;
  // Deactivate all presets in step1, activate clicked
  step1StylePresets.querySelectorAll('.preset').forEach(p => p.classList.remove('active'));
  if (btn.dataset.suffix !== '') btn.classList.add('active');
  // Patch shared store
  SharedInputs.patch({ style: stylePromptInput.value });
});

// ── Step 3 gen style presets ───────────────────────────────────────────────
step3.addEventListener('click', e => {
  const btn = e.target.closest('#genStylePresets .preset');
  if (!btn) return;
  genStylePrompt.value = btn.dataset.suffix;
  saveGenSettings();
});

// ── Negative prompt toggle ─────────────────────────────────────────────────
negToggle.addEventListener('click', () => {
  const open = negToggle.classList.toggle('open');
  genNegPrompt.classList.toggle('collapsed', !open);
});

// ── Size presets + custom dimension inputs ─────────────────────────────────
const widthInput  = document.getElementById('widthInput');
const heightInput = document.getElementById('heightInput');

function setCanvasSize(w, h) {
  canvasW = w; canvasH = h;
  widthInput.value  = w;
  heightInput.value = h;
}

document.getElementById('sizePresets').addEventListener('click', e => {
  const btn = e.target.closest('.size-btn');
  if (!btn) return;
  document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  setCanvasSize(parseInt(btn.dataset.w), parseInt(btn.dataset.h));
});

function onDimInput() {
  const w = Math.max(64, Math.min(2048, parseInt(widthInput.value)  || canvasW));
  const h = Math.max(64, Math.min(2048, parseInt(heightInput.value) || canvasH));
  canvasW = w; canvasH = h;
  document.querySelectorAll('.size-btn').forEach(b => {
    b.classList.toggle('active', parseInt(b.dataset.w) === w && parseInt(b.dataset.h) === h);
  });
}
widthInput.addEventListener('change',  onDimInput);
heightInput.addEventListener('change', onDimInput);

// ── Provider toggle ────────────────────────────────────────────────────────
function setProvider(p, save = true) {
  provider = p;
  document.querySelectorAll('.provider-btn').forEach(b => b.classList.toggle('active', b.dataset.provider === p));
  document.querySelectorAll('.sd-only').forEach(el => el.classList.toggle('hidden', p === 'gemini'));
  document.querySelectorAll('.gemini-only').forEach(el => el.classList.toggle('hidden', p === 'sd'));
  if (save) saveGenSettings();
}
document.querySelectorAll('.provider-btn').forEach(b => b.addEventListener('click', () => setProvider(b.dataset.provider)));

// ── Gemini aspect ratio ────────────────────────────────────────────────────
document.getElementById('geminiAspectPresets').addEventListener('click', e => {
  const btn = e.target.closest('.ar-btn');
  if (!btn) return;
  document.querySelectorAll('.ar-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  geminiAR = btn.dataset.ar;
  saveGenSettings();
});

// ── Sliders ────────────────────────────────────────────────────────────────
stepsEl.addEventListener('input',  () => { stepsVal.textContent = stepsEl.value; });
stepsEl.addEventListener('change', () => { saveGenSettings(); });
cfgEl.addEventListener('input',    () => { cfgVal.textContent  = parseFloat(cfgEl.value).toFixed(1); });
cfgEl.addEventListener('change',   () => { saveGenSettings(); });

// ── Gen settings persistence ───────────────────────────────────────────────
const GEN_KEY = 'monkeyking_gen_settings';   // shared with Image Studio

function saveGenSettings() {
  const settings = {
    modelNum:    modelSel.value,
    canvasW, canvasH,
    steps:       stepsEl.value,
    cfg:         cfgEl.value,
    stylePrompt: genStylePrompt.value,
    negPrompt:   genNegPrompt.value,
    loraNum:     loraSelect.value,
    loraScale:   loraScaleEl.value,
    loraNum2:    loraSelect2.value,
    loraScale2:  loraScaleEl2.value,
    sampler:     samplerSel.value,
    clipSkip:    clipSkipSel.value,
    provider,
    geminiModel: geminiModelSel.value,
    geminiAR,
  };
  localStorage.setItem(GEN_KEY, JSON.stringify(settings));
}

function restoreGenSettings() {
  let s;
  try { s = JSON.parse(localStorage.getItem(GEN_KEY) || 'null'); } catch { return; }
  if (!s) return;
  if (s.modelNum)  modelSel.value = s.modelNum;
  if (s.canvasW && s.canvasH) setCanvasSize(parseInt(s.canvasW), parseInt(s.canvasH));
  if (s.steps) { stepsEl.value = s.steps; stepsVal.textContent = s.steps; }
  if (s.cfg)   { cfgEl.value   = s.cfg;   cfgVal.textContent   = parseFloat(s.cfg).toFixed(1); }
  if (s.stylePrompt !== undefined) genStylePrompt.value = s.stylePrompt;
  if (s.negPrompt   !== undefined) genNegPrompt.value   = s.negPrompt;
  if (s.loraNum) {
    loraSelect.value = s.loraNum;
    loraScaleEl.value = s.loraScale ?? '1.0';
    loraScaleVal.textContent = parseFloat(s.loraScale ?? 1).toFixed(2);
    loraScaleRow.classList.remove('hidden');
  }
  if (s.loraNum2) {
    loraSelect2.value = s.loraNum2;
    loraScaleEl2.value = s.loraScale2 ?? '1.0';
    loraScaleVal2.textContent = parseFloat(s.loraScale2 ?? 1).toFixed(2);
    loraScaleRow2.classList.remove('hidden');
  }
  if (s.sampler)  samplerSel.value  = s.sampler;
  if (s.clipSkip) clipSkipSel.value = s.clipSkip;
  if (s.geminiModel) {
    geminiModelSel.value = s.geminiModel;
    if (!geminiModelSel.value) geminiModelSel.selectedIndex = 0;
  }
  if (s.geminiAR) {
    geminiAR = s.geminiAR;
    document.querySelectorAll('.ar-btn').forEach(b => b.classList.toggle('active', b.dataset.ar === s.geminiAR));
  }
  if (s.provider) setProvider(s.provider, false);
}

// Save on control changes
[modelSel, loraSelect, loraScaleEl, loraSelect2, loraScaleEl2, samplerSel, clipSkipSel, geminiModelSel].forEach(el =>
  el.addEventListener('change', saveGenSettings));
[widthInput, heightInput].forEach(el => el.addEventListener('change', saveGenSettings));
[genStylePrompt, genNegPrompt].forEach(el => el.addEventListener('input', saveGenSettings));

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
  // Reset controls to defaults
  setCanvasSize(512, 512);
  stepsEl.value = 30; stepsVal.textContent = '30';
  cfgEl.value = 7.0;  cfgVal.textContent = '7.0';
  loraSelect.value  = ''; loraScaleEl.value  = '1.0'; loraScaleVal.textContent  = '1.00'; loraScaleRow.classList.add('hidden');
  loraSelect2.value = ''; loraScaleEl2.value = '1.0'; loraScaleVal2.textContent = '1.00'; loraScaleRow2.classList.add('hidden');
});

// ── Decompose ──────────────────────────────────────────────────────────────
decomposeBtn.addEventListener('click', async () => {
  if (await runDecompose()) {
    step2.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
});

autoGenBtn.addEventListener('click', async () => {
  if (await runDecompose()) {
    step3.scrollIntoView({ behavior: 'smooth', block: 'start' });
    queueBtn.click();
  }
});

async function runDecompose() {
  const concept = conceptInput.value.trim();
  if (!concept) { conceptInput.focus(); return false; }

  setDecomposeLoading(true);
  decomposeHint.textContent = 'Claude is writing your storybook… this takes ~20 seconds.';

  try {
    const res = await fetch(`${API}/decompose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        concept,
        style_suffix: stylePromptInput.value.trim(),
        language: currentLang,
        character: characterInput.value.trim(),
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail ?? res.statusText);
    }
    storyData = await res.json();
    Object.keys(generatedImages).forEach(k => delete generatedImages[k]);
    decomposeHint.textContent = '';
    renderPages(storyData);
    step2.classList.remove('hidden');
    step4.classList.remove('hidden');
    queueBtn.disabled = false;
    saveProjectBtn.disabled = false;
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
  decomposeBtn.disabled = on;
  autoGenBtn.disabled   = on;
  decomposeLabel.textContent = on ? 'Writing…' : '✦ Create Story with Claude';
  autoGenLabel.textContent   = on ? 'Writing…' : '⚡ Create Story + Generate Images';
  decomposeSpinner.classList.toggle('hidden', !on);
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
  showCardProgress(pageNum, 0, provider === 'sd' ? parseInt(stepsEl.value) : 1);

  const genBody = {
    prompt:       current.image_prompt,
    style_prompt: genStylePrompt.value.trim(),
    provider,
    width:        canvasW,
    height:       canvasH,
  };
  if (provider === 'sd') {
    genBody.negative_prompt = genNegPrompt.value.trim();
    genBody.model_num       = parseInt(modelSel.value) || undefined;
    genBody.steps           = parseInt(stepsEl.value);
    genBody.guidance_scale  = parseFloat(cfgEl.value);
    genBody.seed            = -1;
    genBody.sampler         = samplerSel.value;
    genBody.clip_skip       = parseInt(clipSkipSel.value);
    if (loraSelect.value)  { genBody.lora_num   = parseInt(loraSelect.value);  genBody.lora_scale   = parseFloat(loraScaleEl.value); }
    if (loraSelect2.value) { genBody.lora_num_2 = parseInt(loraSelect2.value); genBody.lora_scale_2 = parseFloat(loraScaleEl2.value); }
  } else {
    genBody.gemini_model        = geminiModelSel.value;
    genBody.gemini_aspect_ratio = geminiAR;
  }

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

// Read current card values (user may have edited them)
function readCard(pageNum) {
  const card = pageGrid.querySelector(`[data-page="${pageNum}"]`);
  if (!card) return null;
  const meta = langMeta(currentLang);
  const get = f => card.querySelector(`[data-field="${f}"]`)?.value ?? '';
  return {
    page: pageNum,
    [meta.native_field]:  get(meta.native_field),
    [meta.reading_field]: get(meta.reading_field),
    en: get('en'),
    image_prompt: get('image_prompt'),
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
    showCardProgress(pg.page, 0, provider === 'sd' ? parseInt(stepsEl.value) : 1);

    try {
      const genBody = {
        prompt:       current.image_prompt,
        style_prompt: genStylePrompt.value.trim(),
        provider,
        width:        canvasW,
        height:       canvasH,
      };
      if (provider === 'sd') {
        genBody.negative_prompt = genNegPrompt.value.trim();
        genBody.model_num       = parseInt(modelSel.value) || undefined;
        genBody.steps           = parseInt(stepsEl.value);
        genBody.guidance_scale  = parseFloat(cfgEl.value);
        genBody.seed            = -1;
        genBody.sampler         = samplerSel.value;
        genBody.clip_skip       = parseInt(clipSkipSel.value);
        if (loraSelect.value)  { genBody.lora_num   = parseInt(loraSelect.value);  genBody.lora_scale   = parseFloat(loraScaleEl.value); }
        if (loraSelect2.value) { genBody.lora_num_2 = parseInt(loraSelect2.value); genBody.lora_scale_2 = parseFloat(loraScaleEl2.value); }
      } else {
        genBody.gemini_model        = geminiModelSel.value;
        genBody.gemini_aspect_ratio = geminiAR;
      }

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
  saveProjectBtn.disabled = false;
});

function setQueueLoading(on) {
  queueBtn.disabled = on;
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
    concept:          conceptInput.value.trim(),
    character:        characterInput.value.trim(),
    style_prompt:     stylePromptInput.value.trim(),
    story:            { ...storyData, language: currentLang, pages: editedPages },
    generated_images: Object.fromEntries(
      Object.entries(generatedImages).map(([k, v]) => [k, v.filename])
    ),
  };
}


// ── Table import ───────────────────────────────────────────────────────────
parseTableBtn.addEventListener('click', () => {
  const raw = tableInput.value.trim();
  if (!raw) { parseHint.textContent = 'Paste a table first.'; return; }

  const { pages, error } = parseTableCSV(raw);
  if (error) { parseHint.textContent = `Error: ${error}`; return; }

  const meta = langMeta(currentLang);
  storyData = {
    language:                       currentLang,
    book_title_en:                  importTitleEn.value.trim()      || 'Imported Story',
    [meta.title_native_field]:      importTitleNative.value.trim()  || '',
    [meta.title_reading_field]:     importTitleReading.value.trim() || '',
    pages,
  };

  Object.keys(generatedImages).forEach(k => delete generatedImages[k]);
  renderPages(storyData);
  step2.classList.remove('hidden');
  step4.classList.remove('hidden');
  queueBtn.disabled       = false;
  saveProjectBtn.disabled = false;
  saveState();

  parseHint.textContent = `✓ Imported ${pages.length} pages.`;
  step2.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

function parseTableCSV(raw) {
  // Detect delimiter: tab if tabs present, otherwise comma
  const delim = raw.includes('\t') ? '\t' : ',';
  const lines  = raw.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) return { error: 'Need at least a header row and one data row.' };

  const headers = splitRow(lines[0], delim).map(h => h.trim().toLowerCase());
  const meta = langMeta(currentLang);

  // Map header names to standard fields (language-aware for native/reading columns)
  const colIndex = {
    page:         findCol(headers, ['page', 'pg', '#']),
    reading:      findCol(headers, meta.table_reading_aliases),
    native:       findCol(headers, meta.table_native_aliases),
    en:           findCol(headers, ['english', 'en', 'translation']),
    image_prompt: findCol(headers, ['illustration prompt', 'illustration', 'image prompt', 'prompt', 'image_prompt']),
  };

  const missing = Object.entries(colIndex).filter(([, v]) => v === -1).map(([k]) => k);
  if (missing.length) return { error: `Could not find columns: ${missing.join(', ')}` };

  const pages = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = splitRow(lines[i], delim);
    const pageNum = parseInt(cells[colIndex.page]);
    if (isNaN(pageNum)) continue;
    pages.push({
      page:                     pageNum,
      [meta.reading_field]:     (cells[colIndex.reading]      ?? '').trim(),
      [meta.native_field]:      (cells[colIndex.native]       ?? '').trim(),
      en:                       (cells[colIndex.en]           ?? '').trim(),
      image_prompt:             (cells[colIndex.image_prompt] ?? '').trim(),
    });
  }

  if (!pages.length) return { error: 'No valid data rows found.' };
  pages.sort((a, b) => a.page - b.page);
  return { pages };
}

function findCol(headers, candidates) {
  for (const c of candidates) {
    const idx = headers.findIndex(h => h === c || h.includes(c));
    if (idx !== -1) return idx;
  }
  return -1;
}

function splitRow(line, delim) {
  // RFC 4180-style CSV split (handles quoted fields containing the delimiter)
  if (delim === '\t') return line.split('\t').map(c => c.replace(/^"|"$/g, ''));
  const cells = [];
  let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQ && line[i + 1] === '"') { cur += '"'; i++; }
      else inQ = !inQ;
    } else if (ch === delim && !inQ) {
      cells.push(cur); cur = '';
    } else {
      cur += ch;
    }
  }
  cells.push(cur);
  return cells;
}

// ── localStorage state persistence ────────────────────────────────────────
const LS_KEY      = 'monkeyking_bb_state';
const LANG_KEY    = 'monkeyking_bb_lang';   // preferred language, survives Clear

// Patch the shared store immediately on every input. No debounce: a localStorage
// write per keystroke is negligible and SharedInputs.patch() no-ops when nothing
// changed. This guarantees the value is always persisted before the user can
// navigate away (a debounced write would be lost mid-flight on navigation).
conceptInput.addEventListener('input', () => {
  SharedInputs.patch({ story: conceptInput.value });
});
characterInput.addEventListener('input', () => {
  SharedInputs.patch({ character: characterInput.value });
});
stylePromptInput.addEventListener('input', () => {
  SharedInputs.patch({ style: stylePromptInput.value });
});

function saveState() {
  // Always persist the chosen language so it survives a reload even before a story exists.
  try { localStorage.setItem(LANG_KEY, currentLang); } catch { /* quota */ }
  if (!storyData) return;
  const editedPages = storyData.pages.map(pg => readCard(pg.page));
  const state = {
    version:             1,
    concept:             conceptInput.value.trim(),
    character:           characterInput.value.trim(),
    style_prompt:        stylePromptInput.value.trim(),
    import_title_en:     importTitleEn.value.trim(),
    import_title_native: importTitleNative.value.trim(),
    import_title_reading:importTitleReading.value.trim(),
    story:               { ...storyData, language: currentLang, pages: editedPages },
    generated_images:    Object.fromEntries(
      Object.entries(generatedImages).map(([k, v]) => [k, v.filename])
    ),
  };
  try { localStorage.setItem(LS_KEY, JSON.stringify(state)); } catch { /* quota */ }
}

function clearProject() {
  localStorage.removeItem(LS_KEY);

  storyData = null;
  Object.keys(generatedImages).forEach(k => delete generatedImages[k]);

  conceptInput.value       = '';
  characterInput.value     = '';
  stylePromptInput.value   = '';
  importTitleEn.value      = '';
  importTitleNative.value  = '';
  importTitleReading.value = '';
  tableInput.value         = '';

  // Clear the character field in shared store too
  SharedInputs.patch({ character: '' });

  pageGrid.innerHTML      = '';
  step2.classList.add('hidden');
  step4.classList.add('hidden');
  queueBtn.disabled       = true;
  saveProjectBtn.disabled = true;
  decomposeHint.textContent = '';
  parseHint.textContent     = '';
}

clearProjectBtn.addEventListener('click', () => {
  if (!confirm('Clear the current project? This cannot be undone.')) return;
  clearProject();
});

// ── Save / Load project ────────────────────────────────────────────────────
saveProjectBtn.addEventListener('click', saveProject);

function saveProject() {
  if (!storyData) return;

  // Capture any user edits from the card textareas
  const editedPages = storyData.pages.map(pg => readCard(pg.page));

  const project = {
    version: 1,
    saved_at: new Date().toISOString(),
    concept: conceptInput.value.trim(),
    character: characterInput.value.trim(),
    style_prompt: stylePromptInput.value.trim(),
    story: { ...storyData, language: currentLang, pages: editedPages },
    generated_images: Object.fromEntries(
      Object.entries(generatedImages).map(([k, v]) => [k, v.filename])
    ),
  };

  const blob = new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `${storyData.book_title_en.replace(/[^a-z0-9]+/gi, '_')}.monkeyking.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

loadProjectFile.addEventListener('change', async e => {
  const file = e.target.files[0];
  if (!file) return;
  e.target.value = '';
  let project;
  try {
    project = JSON.parse(await file.text());
  } catch {
    alert('Invalid project file.');
    return;
  }
  if (!project.story?.pages) {
    alert('Project file is missing story data.');
    return;
  }
  await restoreProject(project);
});


// ── Shared inputs — restore and wire live-sync ─────────────────────────────
function restoreSharedInputs() {
  const s = SharedInputs.read();
  // Set values directly — never dispatch synthetic input events
  conceptInput.value     = s.story;
  characterInput.value   = s.character;
  stylePromptInput.value = s.style;

  // Restore active style preset pill in step 1
  step1StylePresets.querySelectorAll('.preset').forEach(p => {
    p.classList.toggle('active', p.dataset.suffix !== '' && p.dataset.suffix === s.style);
  });
}

function wireSharedInputListeners() {
  // Live cross-tab sync — set .value directly, do NOT trigger input side-effects
  SharedInputs.onExternalChange(s => {
    conceptInput.value     = s.story;
    characterInput.value   = s.character;
    stylePromptInput.value = s.style;
    step1StylePresets.querySelectorAll('.preset').forEach(p => {
      p.classList.toggle('active', p.dataset.suffix !== '' && p.dataset.suffix === s.style);
    });
  });
}

// ── Init ───────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  await Promise.all([loadModels(), loadLoras()]);
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
        story:     conceptInput.value,
        style:     stylePromptInput.value,
        character: characterInput.value,
      });
    } catch (err) {
      console.warn('Could not load gallery book:', err.message);
      // Fall through to shared restore
      restoreSharedInputs();
    }
  } else {
    // 2. Try to restore full state from LS_KEY (saved story)
    const hadSavedState = await restoreState();
    if (hadSavedState) {
      // restoreProject was called inside restoreState; push loaded values to shared store
      SharedInputs.patch({
        story:     conceptInput.value,
        style:     stylePromptInput.value,
        character: characterInput.value,
      });
    } else {
      // 3. No saved story — restore from shared store
      restoreSharedInputs();
    }
  }

  // 4. Wire live-sync listeners
  wireSharedInputListeners();
})();

async function restoreProject(project) {
  if (!project.story?.pages) return false;

  // Adopt the project's language (default zh for legacy projects without one).
  const projectLang = project.story.language || project.language || DEFAULT_LANG;
  setLanguage(projectLang, { rerender: false, save: false });

  conceptInput.value     = project.concept      ?? '';
  characterInput.value   = project.character    ?? '';
  stylePromptInput.value = project.style_prompt  ?? '';
  storyData = project.story;

  Object.keys(generatedImages).forEach(k => delete generatedImages[k]);

  renderPages(storyData);
  step2.classList.remove('hidden');
  step4.classList.remove('hidden');
  queueBtn.disabled       = false;
  saveProjectBtn.disabled = false;

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

async function restoreState() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return false;
    const state = JSON.parse(raw);
    if (!state.story?.pages) return false;
    importTitleEn.value      = state.import_title_en       ?? '';
    // Accept both new (import_title_native/reading) and legacy (import_title_zh/pinyin) keys.
    importTitleNative.value  = state.import_title_native   ?? state.import_title_zh     ?? '';
    importTitleReading.value = state.import_title_reading  ?? state.import_title_pinyin ?? '';
    return await restoreProject(state);
  } catch { /* corrupted */ }
  return false;
}

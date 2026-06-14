'use strict';

// ── Language registry (mirrors languages.py / book_builder.js) ─────────────
const LANGS = {
  zh: {
    code: 'zh',
    native_field: 'zh',
    reading_field: 'pinyin',
    reading_label: 'Pinyin',
    title_native: 'book_title_zh',
    title_reading: 'book_title_pinyin',
  },
  ja: {
    code: 'ja',
    native_field: 'ja',
    reading_field: 'romaji',
    reading_label: 'Romaji',
    title_native: 'book_title_ja',
    title_reading: 'book_title_romaji',
  },
  ko: {
    code: 'ko',
    native_field: 'ko',
    reading_field: 'romanization',
    reading_label: 'Romanization',
    title_native: 'book_title_ko',
    title_reading: 'book_title_romanization',
  },
};

// ── Persistence ────────────────────────────────────────────────────────────
const STATE_KEY    = 'bb_mobile_state_v1';
const SETTINGS_KEY = 'bb_mobile_settings_v1';

function defaultSettings() {
  return { serverUrl: '', anthropicKey: '', geminiKey: '' };
}

function defaultState() {
  return { lang: 'zh', concept: '', stylePrompt: '', story: null, images: {} };
}

function loadSettings() {
  try { return { ...defaultSettings(), ...JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}') }; }
  catch { return defaultSettings(); }
}

function loadState() {
  try { return { ...defaultState(), ...JSON.parse(localStorage.getItem(STATE_KEY) || '{}') }; }
  catch { return defaultState(); }
}

function persistSettings() {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(cfg));
}

function persistState() {
  try { localStorage.setItem(STATE_KEY, JSON.stringify(st)); } catch {}
}

// ── App state ──────────────────────────────────────────────────────────────
let cfg = loadSettings();
let st  = loadState();
let generatingAll = false;

// ── DOM refs ───────────────────────────────────────────────────────────────
const settingsScreen    = document.getElementById('settingsScreen');
const builderScreen     = document.getElementById('builderScreen');
const setupView         = document.getElementById('setupView');
const storyView         = document.getElementById('storyView');
const screenTitle       = document.getElementById('screenTitle');
const backToSetupBtn    = document.getElementById('backToSetupBtn');
const settingsOpenBtn   = document.getElementById('settingsOpenBtn');
const settingsBackBtn   = document.getElementById('settingsBackBtn');
const serverUrlInput    = document.getElementById('serverUrlInput');
const anthropicKeyInput = document.getElementById('anthropicKeyInput');
const geminiKeyInput    = document.getElementById('geminiKeyInput');
const saveSettingsBtn   = document.getElementById('saveSettingsBtn');
const conceptInput      = document.getElementById('conceptInput');
const styleInput        = document.getElementById('styleInput');
const decomposeBtn      = document.getElementById('decomposeBtn');
const bookTitleArea     = document.getElementById('bookTitleArea');
const pagesContainer    = document.getElementById('pagesContainer');
const generateAllBtn    = document.getElementById('generateAllBtn');
const exportBtn         = document.getElementById('exportBtn');
const newBookBtn        = document.getElementById('newBookBtn');
const loadingOverlay    = document.getElementById('loadingOverlay');
const loadingText       = document.getElementById('loadingText');
const toastEl           = document.getElementById('toast');

// ── Navigation ─────────────────────────────────────────────────────────────
function showSettings() {
  serverUrlInput.value    = cfg.serverUrl;
  anthropicKeyInput.value = cfg.anthropicKey;
  geminiKeyInput.value    = cfg.geminiKey;
  settingsScreen.classList.remove('hidden');
  builderScreen.classList.add('hidden');
}

function hideSettings() {
  settingsScreen.classList.add('hidden');
  builderScreen.classList.remove('hidden');
}

function showSetupView() {
  storyView.classList.add('hidden');
  setupView.classList.remove('hidden');
  screenTitle.textContent = 'Book Builder';
  backToSetupBtn.style.visibility = 'hidden';
  conceptInput.value = st.concept || '';
  styleInput.value   = st.stylePrompt || '';
  syncLangButtons(st.lang || 'zh');
}

function showStoryView() {
  setupView.classList.add('hidden');
  storyView.classList.remove('hidden');
  const lang  = LANGS[st.lang || 'zh'];
  const story = st.story;
  screenTitle.textContent =
    (story[lang.title_reading] || story.book_title_en || 'Your Book').slice(0, 40);
  backToSetupBtn.style.visibility = 'visible';
}

// ── Language selector ──────────────────────────────────────────────────────
function syncLangButtons(code) {
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.lang === code);
  });
}

// ── Settings validation ────────────────────────────────────────────────────
function checkSettings() {
  if (!cfg.serverUrl)    { showToast('Set the Server URL in Settings ⚙', true); return false; }
  if (!cfg.anthropicKey) { showToast('Set your Anthropic API key in Settings ⚙', true); return false; }
  if (!cfg.geminiKey)    { showToast('Set your Gemini API key in Settings ⚙', true); return false; }
  return true;
}

// ── API client ─────────────────────────────────────────────────────────────
function apiBase() {
  return (cfg.serverUrl || '').replace(/\/$/, '');
}

async function apiDecompose(concept, stylePrompt, lang) {
  const r = await fetch(apiBase() + '/decompose', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      concept,
      style_suffix: stylePrompt || '',
      language: lang,
      anthropic_key: cfg.anthropicKey,
    }),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(e.detail || `Server error ${r.status}`);
  }
  return r.json();
}

async function apiGenerateImage(imagePrompt, stylePrompt) {
  const r = await fetch(apiBase() + '/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: imagePrompt,
      style_prompt: stylePrompt || '',
      provider: 'gemini',
      gemini_model: 'imagen-4.0-fast-generate-001',
      gemini_aspect_ratio: '4:3',
      gemini_key: cfg.geminiKey,
      return_base64: true,
    }),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(e.detail || `Server error ${r.status}`);
  }
  const data = await r.json();
  return data.image_base64;
}

// ── Decompose ──────────────────────────────────────────────────────────────
async function doDecompose() {
  if (!checkSettings()) return;
  const concept = conceptInput.value.trim();
  if (!concept) { showToast('Enter a story concept first', true); return; }

  st.concept     = concept;
  st.stylePrompt = styleInput.value.trim();
  persistState();

  showLoading('Generating your story…\nThis takes about 20–30 seconds.');
  decomposeBtn.disabled = true;
  try {
    const story = await apiDecompose(concept, st.stylePrompt, st.lang);
    st.story  = story;
    st.images = {};
    persistState();
    renderStory();
    showStoryView();
  } catch (e) {
    showToast(e.message, true);
  } finally {
    hideLoading();
    decomposeBtn.disabled = false;
  }
}

// ── Render story ───────────────────────────────────────────────────────────
function renderStory() {
  if (!st.story) return;
  const lang  = LANGS[st.lang || 'zh'];
  const story = st.story;

  bookTitleArea.innerHTML = `
    <div class="title-native">${esc(story[lang.title_native] || '')}</div>
    <div class="title-reading">${esc(story[lang.title_reading] || '')}</div>
    <div class="title-en">${esc(story.book_title_en || '')}</div>
  `;

  pagesContainer.innerHTML = '';
  (story.pages || []).forEach(page => pagesContainer.appendChild(buildPageCard(page, lang)));
}

function buildPageCard(page, lang) {
  const num  = page.page;
  const b64  = st.images[num];
  const card = document.createElement('div');
  card.className = 'page-card';
  card.id = `card-${num}`;

  card.innerHTML = `
    <div class="page-card-header">
      <span class="page-num">Page ${num}</span>
      <button class="regen-btn" id="regen-${num}">📷 Generate</button>
    </div>
    <div class="page-image-area" id="imgarea-${num}">
      ${b64
        ? `<img src="data:image/png;base64,${b64}" alt="Page ${num} illustration">`
        : `<div class="page-placeholder">📖</div>`}
    </div>
    <div class="page-text">
      <div class="page-native">${esc(page[lang.native_field] || '')}</div>
      <div class="page-reading">${esc(page[lang.reading_field] || '')}</div>
      <div class="page-en">${esc(page.en || '')}</div>
    </div>
  `;

  card.querySelector(`#regen-${num}`).addEventListener('click', () => generateImage(num));
  return card;
}

// ── Image generation ───────────────────────────────────────────────────────
async function generateImage(pageNum) {
  if (!checkSettings()) return;
  if (!st.story) return;
  const page = (st.story.pages || []).find(p => p.page === pageNum);
  if (!page) return;

  const regenBtn = document.getElementById(`regen-${pageNum}`);
  const imgArea  = document.getElementById(`imgarea-${pageNum}`);
  if (!imgArea) return;

  regenBtn.disabled = true;
  imgArea.innerHTML = `
    <div class="page-generating">
      <div class="spinner"></div>
      <span>Generating…</span>
    </div>
  `;

  const prevErr = document.querySelector(`#card-${pageNum} .page-error`);
  if (prevErr) prevErr.remove();

  try {
    const b64 = await apiGenerateImage(page.image_prompt, st.stylePrompt);
    st.images[pageNum] = b64;
    persistState();
    imgArea.innerHTML = `<img src="data:image/png;base64,${b64}" alt="Page ${pageNum} illustration">`;
  } catch (e) {
    imgArea.innerHTML = `<div class="page-placeholder">⚠️</div>`;
    const errEl = document.createElement('div');
    errEl.className = 'page-error';
    errEl.textContent = e.message;
    document.querySelector(`#card-${pageNum} .page-text`).before(errEl);
  } finally {
    regenBtn.disabled = false;
  }
}

async function generateAll() {
  if (!checkSettings()) return;
  if (!st.story || generatingAll) return;

  generatingAll = true;
  generateAllBtn.disabled = true;
  generateAllBtn.textContent = '⏳ Generating…';

  for (const page of (st.story.pages || [])) {
    await generateImage(page.page);
  }

  generatingAll = false;
  generateAllBtn.disabled = false;
  generateAllBtn.textContent = '🎨 Generate All Images';
  showToast('All images generated!');
}

// ── Export ─────────────────────────────────────────────────────────────────
async function doExport() {
  if (!st.story) return;
  const lang  = LANGS[st.lang || 'zh'];
  const story = st.story;
  const title = story.book_title_en || 'My Book';

  const pagesHtml = (story.pages || []).map(p => {
    const imgTag = st.images[p.page]
      ? `<img src="data:image/png;base64,${st.images[p.page]}"
              style="width:100%;border-radius:10px;display:block">`
      : `<div style="aspect-ratio:4/3;background:#f3f4f6;border-radius:10px;
                     display:flex;align-items:center;justify-content:center;font-size:60px">📖</div>`;
    return `
      <div style="page-break-after:always;padding:24px;max-width:600px;margin:0 auto;
                  font-family:-apple-system,BlinkMacSystemFont,sans-serif">
        <p style="font-size:13px;color:#9ca3af;margin-bottom:12px;
                  text-transform:uppercase;letter-spacing:.5px">Page ${p.page}</p>
        ${imgTag}
        <p style="font-size:26px;margin-top:16px;line-height:1.5">
          ${esc(p[lang.native_field] || '')}</p>
        <p style="font-size:14px;color:#6366f1;font-style:italic;margin-top:4px">
          ${esc(p[lang.reading_field] || '')}</p>
        <p style="font-size:15px;color:#374151;margin-top:8px;line-height:1.5">
          ${esc(p.en || '')}</p>
      </div>`;
  }).join('');

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${esc(title)}</title>
</head>
<body style="margin:0;background:#fff">
  <div style="padding:24px;text-align:center;border-bottom:1px solid #e5e7eb;
              font-family:-apple-system,sans-serif;max-width:600px;margin:0 auto">
    <h1 style="font-size:28px;color:#4f46e5">${esc(story[lang.title_native] || '')}</h1>
    <p style="color:#9ca3af;font-style:italic">${esc(story[lang.title_reading] || '')}</p>
    <p style="font-size:18px;margin-top:8px">${esc(title)}</p>
  </div>
  ${pagesHtml}
</body>
</html>`;

  const blob = new Blob([html], { type: 'text/html' });
  const file = new File([blob], `${title.replace(/\s+/g, '_')}.html`, { type: 'text/html' });

  try {
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title });
      return;
    }
    if (navigator.share) {
      await navigator.share({ title, text: `"${title}" — exported from Book Builder` });
      return;
    }
  } catch (err) {
    if (err.name === 'AbortError') return; // user cancelled
  }

  // Fallback: trigger download
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = file.name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Helpers ────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function showLoading(msg) {
  loadingText.innerHTML = msg.replace(/\n/g, '<br>');
  loadingOverlay.classList.remove('hidden');
}

function hideLoading() {
  loadingOverlay.classList.add('hidden');
}

let _toastTimer;
function showToast(msg, isError = false) {
  toastEl.textContent = msg;
  toastEl.className   = 'toast' + (isError ? ' is-error' : '');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => toastEl.classList.add('hidden'), isError ? 4000 : 2500);
}

// ── Event wiring ───────────────────────────────────────────────────────────
settingsOpenBtn.addEventListener('click', showSettings);
settingsBackBtn.addEventListener('click', hideSettings);
backToSetupBtn.addEventListener('click', showSetupView);

saveSettingsBtn.addEventListener('click', () => {
  cfg.serverUrl    = serverUrlInput.value.trim();
  cfg.anthropicKey = anthropicKeyInput.value.trim();
  cfg.geminiKey    = geminiKeyInput.value.trim();
  persistSettings();
  hideSettings();
  showToast('Settings saved');
});

document.querySelectorAll('.lang-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    st.lang = btn.dataset.lang;
    syncLangButtons(st.lang);
    persistState();
  });
});

decomposeBtn.addEventListener('click', doDecompose);
generateAllBtn.addEventListener('click', generateAll);
exportBtn.addEventListener('click', doExport);

newBookBtn.addEventListener('click', () => {
  if (!window.confirm('Start a new book? The current story will be cleared.')) return;
  st = defaultState();
  persistState();
  showSetupView();
});

// ── Init ───────────────────────────────────────────────────────────────────
function init() {
  const hasSettings = cfg.serverUrl && cfg.anthropicKey && cfg.geminiKey;
  if (!hasSettings) {
    showSettings();
  } else if (st.story) {
    renderStory();
    showStoryView();
  } else {
    showSetupView();
  }
}

init();

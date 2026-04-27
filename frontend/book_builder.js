const API = window.location.origin;

// ── State ──────────────────────────────────────────────────────────────────
let storyData = null;   // DecomposeResponse from server
let canvasW = 768, canvasH = 768;

// ── DOM refs ───────────────────────────────────────────────────────────────
const conceptInput      = document.getElementById('conceptInput');
const stylePromptInput  = document.getElementById('stylePromptInput');
const saveProjectBtn    = document.getElementById('saveProjectBtn');
const clearProjectBtn   = document.getElementById('clearProjectBtn');
const loadProjectFile   = document.getElementById('loadProjectFile');
const decomposeBtn      = document.getElementById('decomposeBtn');
const importTitleEn     = document.getElementById('importTitleEn');
const importTitleZh     = document.getElementById('importTitleZh');
const importTitlePinyin = document.getElementById('importTitlePinyin');
const tableInput        = document.getElementById('tableInput');
const parseTableBtn     = document.getElementById('parseTableBtn');
const parseHint         = document.getElementById('parseHint');
const decomposeLabel  = document.getElementById('decomposeLabel');
const decomposeSpinner= document.getElementById('decomposeSpinner');
const decomposeHint   = document.getElementById('decomposeHint');

const step2           = document.getElementById('step2');
const bookTitleDisplay= document.getElementById('bookTitleDisplay');
const bookTitleSub    = document.getElementById('bookTitleSub');
const pageGrid        = document.getElementById('pageGrid');

const step3           = document.getElementById('step3');
const modelSel        = document.getElementById('modelSelect');
const stepsEl         = document.getElementById('steps');
const stepsVal        = document.getElementById('stepsVal');
const cfgEl           = document.getElementById('cfg');
const cfgVal          = document.getElementById('cfgVal');
const loraSelect      = document.getElementById('loraSelect');
const loraScaleRow    = document.getElementById('loraScaleRow');
const loraScaleEl     = document.getElementById('loraScale');
const loraScaleVal    = document.getElementById('loraScaleVal');
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
    loraSelect.innerHTML = '<option value="">— none —</option>';
    (data.loras || []).forEach(l => {
      const opt = document.createElement('option');
      opt.value = l.num;
      opt.textContent = l.name;
      if (l.loaded) opt.selected = true;
      loraSelect.appendChild(opt);
    });
    loraScaleRow.classList.toggle('hidden', !loraSelect.value);
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

// ── Style presets — fill the style textarea ────────────────────────────────
document.getElementById('stylePresets').addEventListener('click', e => {
  const btn = e.target.closest('.preset');
  if (!btn) return;
  stylePromptInput.value = btn.dataset.suffix;
});

// ── Size presets ───────────────────────────────────────────────────────────
document.getElementById('sizePresets').addEventListener('click', e => {
  const btn = e.target.closest('.size-btn');
  if (!btn) return;
  document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  canvasW = parseInt(btn.dataset.w);
  canvasH = parseInt(btn.dataset.h);
});

// ── Sliders ────────────────────────────────────────────────────────────────
stepsEl.addEventListener('input', () => stepsVal.textContent = stepsEl.value);
cfgEl.addEventListener('input',   () => cfgVal.textContent  = parseFloat(cfgEl.value).toFixed(1));

// ── Decompose ──────────────────────────────────────────────────────────────
decomposeBtn.addEventListener('click', async () => {
  const concept = conceptInput.value.trim();
  if (!concept) { conceptInput.focus(); return; }

  setDecomposeLoading(true);
  decomposeHint.textContent = 'Claude is writing your storybook… this takes ~20 seconds.';

  try {
    const res = await fetch(`${API}/decompose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ concept, style_suffix: stylePromptInput.value.trim() }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail ?? res.statusText);
    }
    storyData = await res.json();
    decomposeHint.textContent = '';
    renderPages(storyData);
    step2.classList.remove('hidden');
    step4.classList.remove('hidden');
    queueBtn.disabled = false;
    saveProjectBtn.disabled = false;
    saveState();
    step2.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    decomposeHint.textContent = `Error: ${err.message}`;
  } finally {
    setDecomposeLoading(false);
  }
});

function setDecomposeLoading(on) {
  decomposeBtn.disabled = on;
  decomposeLabel.textContent = on ? 'Writing…' : '✦ Create Story with Claude';
  decomposeSpinner.classList.toggle('hidden', !on);
}

// ── Render page cards ──────────────────────────────────────────────────────
function renderPages(data) {
  bookTitleDisplay.textContent = `${data.book_title_zh} · ${data.book_title_en}`;
  bookTitleSub.textContent = data.book_title_pinyin;

  pageGrid.innerHTML = '';
  data.pages.forEach(pg => {
    const card = buildCard(pg);
    pageGrid.appendChild(card);
  });
}

function buildCard(pg) {
  const card = document.createElement('div');
  card.className = 'page-card';
  card.dataset.page = pg.page;

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
    </div>
    <div class="card-body">
      <div class="card-page-num">Page ${pg.page}</div>

      <div class="card-field zh-field">
        <label>中文</label>
        <textarea rows="2" data-field="zh">${escHtml(pg.zh)}</textarea>
      </div>

      <div class="card-field">
        <label>Pinyin</label>
        <textarea rows="2" data-field="pinyin">${escHtml(pg.pinyin)}</textarea>
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
  `;
  return card;
}

// Read current card values (user may have edited them)
function readCard(pageNum) {
  const card = pageGrid.querySelector(`[data-page="${pageNum}"]`);
  if (!card) return null;
  const get = f => card.querySelector(`[data-field="${f}"]`)?.value ?? '';
  return {
    page: pageNum,
    zh: get('zh'),
    pinyin: get('pinyin'),
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

    const current    = readCard(pg.page);
    const stylePart  = stylePromptInput.value.trim();
    const prompt     = stylePart
      ? `${current.image_prompt}, ${stylePart}`
      : current.image_prompt;

    showThumbSpinner(pg.page);
    showCardProgress(pg.page, 0, parseInt(stepsEl.value));

    try {
      const genBody = {
        prompt,
        negative_prompt: 'blurry, low quality, watermark, text, deformed, ugly, bad anatomy',
        model_num: parseInt(modelSel.value) || undefined,
        steps: parseInt(stepsEl.value),
        guidance_scale: parseFloat(cfgEl.value),
        width: canvasW,
        height: canvasH,
        seed: -1,
      };
      if (loraSelect.value) {
        genBody.lora_num   = parseInt(loraSelect.value);
        genBody.lora_scale = parseFloat(loraScaleEl.value);
      }

      const res = await fetch(`${API}/generate/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(genBody),
      });
      if (!res.ok) throw new Error(await res.text());

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
          const evt = JSON.parse(line.slice(6));
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
function showThumbSpinner(pageNum) {
  const el = document.getElementById(`thumb-${pageNum}`);
  if (!el) return;
  el.innerHTML = `<div class="thumb-spinner"><div class="spinner"></div></div>`;
}

function showThumbImage(pageNum, url) {
  const el = document.getElementById(`thumb-${pageNum}`);
  if (!el) return;
  el.innerHTML = `<img src="${url}" alt="Page ${pageNum}" style="width:100%;height:100%;object-fit:cover;display:block;">`;
}

function showThumbError(pageNum, msg) {
  const el = document.getElementById(`thumb-${pageNum}`);
  if (!el) return;
  el.innerHTML = `<div class="thumb-placeholder" title="${escHtml(msg)}">⚠ Page ${pageNum} failed</div>`;
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
    style_prompt:     stylePromptInput.value.trim(),
    story:            { ...storyData, pages: editedPages },
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

  storyData = {
    book_title_en:     importTitleEn.value.trim()     || 'Imported Story',
    book_title_zh:     importTitleZh.value.trim()     || '',
    book_title_pinyin: importTitlePinyin.value.trim() || '',
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

  // Map header names to standard fields
  const colIndex = {
    page:         findCol(headers, ['page', 'pg', '#']),
    pinyin:       findCol(headers, ['pinyin']),
    zh:           findCol(headers, ['汉字', 'chinese', 'zh', 'hanzi', '中文']),
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
      page:         pageNum,
      pinyin:       (cells[colIndex.pinyin]       ?? '').trim(),
      zh:           (cells[colIndex.zh]           ?? '').trim(),
      en:           (cells[colIndex.en]           ?? '').trim(),
      image_prompt: (cells[colIndex.image_prompt] ?? '').trim(),
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
const LS_KEY = 'monkeyking_bb_state';

function saveState() {
  if (!storyData) return;
  const editedPages = storyData.pages.map(pg => readCard(pg.page));
  const state = {
    version:            1,
    concept:            conceptInput.value.trim(),
    style_prompt:       stylePromptInput.value.trim(),
    import_title_en:    importTitleEn.value.trim(),
    import_title_zh:    importTitleZh.value.trim(),
    import_title_pinyin:importTitlePinyin.value.trim(),
    story:              { ...storyData, pages: editedPages },
    generated_images:   Object.fromEntries(
      Object.entries(generatedImages).map(([k, v]) => [k, v.filename])
    ),
  };
  try { localStorage.setItem(LS_KEY, JSON.stringify(state)); } catch { /* quota */ }
}

async function restoreState() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return;
    const state = JSON.parse(raw);
    if (!state.story?.pages) return;
    importTitleEn.value      = state.import_title_en      ?? '';
    importTitleZh.value      = state.import_title_zh      ?? '';
    importTitlePinyin.value  = state.import_title_pinyin  ?? '';
    await restoreProject(state);
  } catch { /* corrupted */ }
}

clearProjectBtn.addEventListener('click', () => {
  if (!confirm('Clear the current project? This cannot be undone.')) return;
  localStorage.removeItem(LS_KEY);

  storyData = null;
  Object.keys(generatedImages).forEach(k => delete generatedImages[k]);

  conceptInput.value      = '';
  stylePromptInput.value  = '';
  importTitleEn.value     = '';
  importTitleZh.value     = '';
  importTitlePinyin.value = '';
  tableInput.value        = '';

  pageGrid.innerHTML      = '';
  step2.classList.add('hidden');
  step4.classList.add('hidden');
  queueBtn.disabled       = true;
  saveProjectBtn.disabled = true;
  decomposeHint.textContent = '';
  parseHint.textContent     = '';
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
    style_prompt: stylePromptInput.value.trim(),
    story: { ...storyData, pages: editedPages },
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

// ── Init ───────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  await Promise.all([loadModels(), loadLoras()]);

  // Load a gallery book if linked from Gallery page; otherwise restore localStorage
  const params    = new URLSearchParams(window.location.search);
  const galleryId = params.get('gallery_id');
  if (galleryId) {
    try {
      const res     = await fetch(`${API}/gallery/${encodeURIComponent(galleryId)}`);
      if (!res.ok) throw new Error('Not found');
      const project = await res.json();
      await restoreProject(project);
    } catch (err) {
      console.warn('Could not load gallery book:', err.message);
    }
  } else {
    await restoreState();
  }
})();

async function restoreProject(project) {
  if (!project.story?.pages) return;

  conceptInput.value     = project.concept      ?? '';
  stylePromptInput.value = project.style_prompt  ?? '';
  storyData = project.story;

  Object.keys(generatedImages).forEach(k => delete generatedImages[k]);

  renderPages(storyData);
  step2.classList.remove('hidden');
  step4.classList.remove('hidden');
  queueBtn.disabled       = false;
  saveProjectBtn.disabled = false;

  if (project.generated_images) {
    await Promise.all(
      Object.entries(project.generated_images).map(async ([pageNum, filename]) => {
        const url = `${API}/image/${filename}`;
        try {
          const res = await fetch(url, { method: 'HEAD' });
          if (res.ok) {
            generatedImages[parseInt(pageNum)] = { filename, url };
            showThumbImage(parseInt(pageNum), url);
          }
        } catch { /* image gone */ }
      })
    );
  }

  step2.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

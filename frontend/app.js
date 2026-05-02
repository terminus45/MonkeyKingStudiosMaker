const API = window.location.origin;
const LS_KEY  = 'monkeyking_studio_state';
const GEN_KEY = 'monkeyking_gen_settings';   // shared with Book Builder

// ── State ──────────────────────────────────────────────────────────────────
let canvasW = 512, canvasH = 512;
let history = [];
let provider = 'sd';
let geminiAR = '1:1';

// ── DOM refs ───────────────────────────────────────────────────────────────
const promptEl      = document.getElementById('prompt');
const stylePromptEl = document.getElementById('stylePrompt');
const negEl         = document.getElementById('negPrompt');
const modelSel      = document.getElementById('modelSelect');
const stepsEl       = document.getElementById('steps');
const stepsVal      = document.getElementById('stepsVal');
const cfgEl         = document.getElementById('cfg');
const cfgVal        = document.getElementById('cfgVal');
const seedEl        = document.getElementById('seed');
const generateBtn     = document.getElementById('generateBtn');
const generateLabel   = document.getElementById('generateLabel');
const spinner         = document.getElementById('spinner');
const placeholder     = document.getElementById('placeholder');
const outputImg       = document.getElementById('outputImg');
const genProgress     = document.getElementById('genProgress');
const genProgressBar  = document.getElementById('genProgressBar');
const genProgressLabel= document.getElementById('genProgressLabel');
const outputMeta    = document.getElementById('outputMeta');
const metaSeed      = document.getElementById('metaSeed');
const metaModel     = document.getElementById('metaModel');
const metaSize      = document.getElementById('metaSize');
const downloadBtn   = document.getElementById('downloadBtn');
const reuseBtn      = document.getElementById('reuseBtn');
const gallery       = document.getElementById('gallery');
const refreshBtn    = document.getElementById('refreshBtn');
const loraSelect    = document.getElementById('loraSelect');
const loraScaleRow  = document.getElementById('loraScaleRow');
const loraScaleEl   = document.getElementById('loraScale');
const loraScaleVal  = document.getElementById('loraScaleVal');
const loraSelect2   = document.getElementById('loraSelect2');
const loraScaleRow2 = document.getElementById('loraScaleRow2');
const loraScaleEl2  = document.getElementById('loraScale2');
const loraScaleVal2 = document.getElementById('loraScaleVal2');
const statusDot     = document.getElementById('statusDot');
const statusLabel   = document.getElementById('statusLabel');
const negToggle     = document.getElementById('negToggle');
const samplerSel      = document.getElementById('samplerSelect');
const clipSkipSel     = document.getElementById('clipSkipSelect');
const geminiModelSel  = document.getElementById('geminiModelSelect');

// ── Server status ──────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch(`${API}/health`);
    const data = await res.json();
    statusDot.className = 'status-dot ok';
    statusLabel.textContent = `Connected · ${data.loaded_model?.split('/').pop() ?? 'unknown'}`;
  } catch {
    statusDot.className = 'status-dot error';
    statusLabel.textContent = 'Server offline';
  }
}

// ── Model list ─────────────────────────────────────────────────────────────
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

// ── LoRA ───────────────────────────────────────────────────────────────────
async function loadLoras() {
  try {
    const res  = await fetch(`${API}/loras`);
    const data = await res.json();
    const opts = '<option value="">— none —</option>' +
      (data.loras || []).map(l => `<option value="${l.num}">${l.name}</option>`).join('');
    loraSelect.innerHTML  = opts;
    loraSelect2.innerHTML = opts;
    loraScaleRow.style.display  = loraSelect.value  ? 'flex' : 'none';
    loraScaleRow2.style.display = loraSelect2.value ? 'flex' : 'none';
  } catch {
    // no loras available
  }
}

refreshBtn.addEventListener('click', async () => {
  refreshBtn.classList.add('spinning');
  await Promise.all([loadModels(), loadLoras()]);
  refreshBtn.classList.remove('spinning');
});

loraSelect.addEventListener('change', () => {
  loraScaleRow.style.display = loraSelect.value ? 'flex' : 'none';
});
loraScaleEl.addEventListener('input', () => {
  loraScaleVal.textContent = parseFloat(loraScaleEl.value).toFixed(2);
});
loraSelect2.addEventListener('change', () => {
  loraScaleRow2.style.display = loraSelect2.value ? 'flex' : 'none';
});
loraScaleEl2.addEventListener('input', () => {
  loraScaleVal2.textContent = parseFloat(loraScaleEl2.value).toFixed(2);
});

// ── Style presets — fill the style textarea ────────────────────────────────
document.getElementById('stylePresets').addEventListener('click', e => {
  const btn = e.target.closest('.preset');
  if (!btn) return;
  stylePromptEl.value = btn.dataset.suffix;
  stylePromptEl.dispatchEvent(new Event('input'));
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
  // Deselect any preset that no longer matches
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
stepsEl.addEventListener('input', () => stepsVal.textContent = stepsEl.value);
cfgEl.addEventListener('input',   () => cfgVal.textContent  = parseFloat(cfgEl.value).toFixed(1));

// ── Seed randomise ─────────────────────────────────────────────────────────
document.getElementById('randSeed').addEventListener('click', () => {
  seedEl.value = Math.floor(Math.random() * (2 ** 32 - 1));
});

// ── Negative prompt toggle ─────────────────────────────────────────────────
negToggle.addEventListener('click', () => {
  const open = negToggle.classList.toggle('open');
  negEl.classList.toggle('collapsed', !open);
});

// ── Generate ───────────────────────────────────────────────────────────────
generateBtn.addEventListener('click', generate);

async function generate() {
  const basePrompt = promptEl.value.trim();
  if (!basePrompt) { promptEl.focus(); return; }

  _generating = true;
  setLoading(true);
  showProgress(0, provider === 'sd' ? parseInt(stepsEl.value) : 1);

  try {
    const body = {
      prompt:          basePrompt,
      style_prompt:    stylePromptEl.value.trim(),
      negative_prompt: negEl.value.trim(),
      provider,
      width:           canvasW,
      height:          canvasH,
    };
    if (provider === 'sd') {
      body.model_num      = parseInt(modelSel.value) || undefined;
      body.steps          = parseInt(stepsEl.value);
      body.guidance_scale = parseFloat(cfgEl.value);
      body.seed           = parseInt(seedEl.value);
      body.sampler        = samplerSel.value;
      body.clip_skip      = parseInt(clipSkipSel.value);
      if (loraSelect.value)  { body.lora_num   = parseInt(loraSelect.value);  body.lora_scale   = parseFloat(loraScaleEl.value); }
      if (loraSelect2.value) { body.lora_num_2 = parseInt(loraSelect2.value); body.lora_scale_2 = parseFloat(loraScaleEl2.value); }
    } else {
      body.gemini_model        = geminiModelSel.value;
      body.gemini_aspect_ratio = geminiAR;
    }

    const res = await fetch(`${API}/generate/stream`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail ?? res.statusText);
    }

    // Parse SSE stream
    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buf     = '';
    let   data    = null;

    while (true) {
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
        if (evt.done) { data = evt; break; }
        showProgress(evt.step, evt.total);
      }
      if (data) break;
    }

    if (!data) throw new Error('Stream ended without a result.');

    const imgUrl = `${API}/image/${data.filename}`;
    placeholder.classList.add('hidden');
    outputImg.src = imgUrl;
    outputImg.classList.remove('hidden');
    outputMeta.classList.remove('hidden');

    const modelShort = (data.loaded_model ?? '').split('/').pop().replace('.safetensors', '');
    const isSd = (data.seed ?? -1) >= 0;
    metaSeed.textContent  = isSd ? `Seed: ${data.seed}` : 'Gemini';
    metaModel.textContent = `Model: ${modelShort}`;
    metaSize.textContent  = isSd ? `${canvasW}×${canvasH}` : geminiAR;

    reuseBtn.disabled = !isSd;
    reuseBtn.onclick  = isSd ? () => { seedEl.value = data.seed; } : null;
    downloadBtn.onclick = () => {
      const a = document.createElement('a');
      a.href = imgUrl;
      a.download = data.filename;
      a.click();
    };

    addToGallery(imgUrl, data.seed, modelShort);
    saveState();
    await checkHealth();

  } catch (err) {
    alert(`Generation failed:\n${err.message}`);
  } finally {
    _generating = false;
    setLoading(false);
    hideProgress();
  }
}

function showProgress(step, total) {
  const pct = total > 0 ? Math.round((step / total) * 100) : 0;
  genProgressBar.style.width = `${pct}%`;
  genProgressLabel.textContent = `${step} / ${total}`;
  genProgress.classList.remove('hidden');
}

function hideProgress() {
  genProgress.classList.add('hidden');
}

function setLoading(on) {
  generateBtn.disabled = on;
  generateLabel.textContent = on ? 'Generating…' : 'Generate';
  spinner.classList.toggle('hidden', !on);
}

// ── Gallery ────────────────────────────────────────────────────────────────
function addToGallery(url, seed, model, skipHistoryPush = false) {
  if (!skipHistoryPush) history.unshift({ url, seed, model });

  const empty = gallery.querySelector('.gallery-empty');
  if (empty) empty.remove();

  const img = document.createElement('img');
  img.className = 'gallery-thumb';
  img.src = url;
  img.title = `Seed: ${seed} · ${model}`;
  img.addEventListener('click', () => {
    placeholder.classList.add('hidden');
    outputImg.src = url;
    outputImg.classList.remove('hidden');
    outputMeta.classList.remove('hidden');
    metaSeed.textContent  = `Seed: ${seed}`;
    metaModel.textContent = `Model: ${model}`;
    reuseBtn.onclick = () => { seedEl.value = seed; };
  });

  gallery.prepend(img);
}

// ── Persistence ────────────────────────────────────────────────────────────

// Gen settings (shared with Book Builder via GEN_KEY)
function saveGenSettings() {
  const settings = {
    modelNum:    modelSel.value,
    canvasW, canvasH,
    steps:       stepsEl.value,
    cfg:         cfgEl.value,
    stylePrompt: stylePromptEl.value,
    negPrompt:   negEl.value,
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
  let g;
  try { g = JSON.parse(localStorage.getItem(GEN_KEY) || 'null'); } catch { return; }
  if (!g) return;
  if (g.modelNum) modelSel.value = g.modelNum;
  if (g.canvasW && g.canvasH) setCanvasSize(parseInt(g.canvasW), parseInt(g.canvasH));
  if (g.steps) { stepsEl.value = g.steps; stepsVal.textContent = g.steps; }
  if (g.cfg)   { cfgEl.value   = g.cfg;   cfgVal.textContent   = parseFloat(g.cfg).toFixed(1); }
  if (g.stylePrompt !== undefined) stylePromptEl.value = g.stylePrompt;
  if (g.negPrompt   !== undefined) negEl.value         = g.negPrompt;
  if (g.loraNum) {
    loraSelect.value = g.loraNum;
    loraScaleEl.value = g.loraScale ?? '1.0';
    loraScaleVal.textContent = parseFloat(g.loraScale ?? 1).toFixed(2);
    loraScaleRow.style.display = 'flex';
  }
  if (g.loraNum2) {
    loraSelect2.value = g.loraNum2;
    loraScaleEl2.value = g.loraScale2 ?? '1.0';
    loraScaleVal2.textContent = parseFloat(g.loraScale2 ?? 1).toFixed(2);
    loraScaleRow2.style.display = 'flex';
  }
  if (g.sampler)  samplerSel.value  = g.sampler;
  if (g.clipSkip) clipSkipSel.value = g.clipSkip;
  if (g.geminiModel) geminiModelSel.value = g.geminiModel;
  if (g.geminiAR) {
    geminiAR = g.geminiAR;
    document.querySelectorAll('.ar-btn').forEach(b => b.classList.toggle('active', b.dataset.ar === g.geminiAR));
  }
  if (g.provider) setProvider(g.provider, false);
}

// Page-specific state (prompt, style, neg, seed, history)
function saveState() {
  const state = {
    prompt:      promptEl.value,
    stylePrompt: stylePromptEl.value,
    negPrompt:   negEl.value,
    negOpen:     negToggle.classList.contains('open'),
    seed:        seedEl.value,
    history:     history.slice(0, 30),
  };
  localStorage.setItem(LS_KEY, JSON.stringify(state));
  saveGenSettings();
}

function restoreState() {
  let s;
  try { s = JSON.parse(localStorage.getItem(LS_KEY) || 'null'); } catch { return; }
  if (s) {
    if (s.prompt)      promptEl.value      = s.prompt;
    if (s.stylePrompt) stylePromptEl.value = s.stylePrompt;
    if (s.negPrompt !== undefined) negEl.value = s.negPrompt;
    if (s.negOpen) {
      negToggle.classList.add('open');
      negEl.classList.remove('collapsed');
    }
    if (s.seed !== undefined) seedEl.value = s.seed;
    if (s.history?.length) {
      history = s.history;
      history.forEach(({ url, seed, model }) => addToGallery(url, seed, model, true));
    }
  }
  restoreGenSettings();
}

// Auto-save on every meaningful control change
[promptEl].forEach(el => el.addEventListener('input', saveState));
[stylePromptEl, negEl].forEach(el => el.addEventListener('input', saveGenSettings));
[seedEl].forEach(el => el.addEventListener('change', saveState));
[stepsEl, cfgEl, widthInput, heightInput].forEach(el => el.addEventListener('change', saveGenSettings));
[modelSel, loraSelect, loraScaleEl, loraSelect2, loraScaleEl2, samplerSel, clipSkipSel, geminiModelSel].forEach(el =>
  el.addEventListener('change', saveGenSettings));

// ── Export / Import / Reset settings ───────────────────────────────────────
document.getElementById('saveSettingsBtn').addEventListener('click', () => {
  saveGenSettings();
  const settings = JSON.parse(localStorage.getItem(GEN_KEY) || '{}');
  const blob = new Blob([JSON.stringify(settings, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'gen-settings.json';
  a.click();
  URL.revokeObjectURL(a.href);
});

document.getElementById('loadSettingsFile').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    try {
      localStorage.setItem(GEN_KEY, JSON.stringify(JSON.parse(ev.target.result)));
      restoreGenSettings();
    } catch {
      alert('Invalid settings file.');
    }
  };
  reader.readAsText(file);
  e.target.value = '';
});

document.getElementById('resetSettingsBtn').addEventListener('click', () => {
  if (!confirm('Reset generation settings to defaults?')) return;
  localStorage.removeItem(GEN_KEY);
  location.reload();
});

// ── Generation status polling (reconnect after navigation) ──────────────────
let _pollInterval = null;

async function checkAndReattach() {
  let status;
  try {
    status = await (await fetch(`${API}/status`)).json();
  } catch { return; }

  if (status.generating) {
    // Job is running — show progress and poll until done
    setLoading(true);
    showProgress(status.step, status.total);
    _pollInterval = setInterval(async () => {
      let s;
      try { s = await (await fetch(`${API}/status`)).json(); } catch { return; }
      if (s.generating) {
        showProgress(s.step, s.total);
      } else {
        clearInterval(_pollInterval);
        _pollInterval = null;
        setLoading(false);
        hideProgress();
        if (s.last_filename) {
          const url = `${API}/image/${s.last_filename}`;
          const modelShort = (s.last_model ?? '').split('/').pop().replace('.safetensors', '');
          const wasSd = (s.last_seed ?? -1) >= 0;
          placeholder.classList.add('hidden');
          outputImg.src = url;
          outputImg.classList.remove('hidden');
          outputMeta.classList.remove('hidden');
          metaSeed.textContent  = wasSd ? `Seed: ${s.last_seed}` : 'Gemini';
          metaModel.textContent = `Model: ${modelShort}`;
          metaSize.textContent  = wasSd ? `${canvasW}×${canvasH}` : '—';
          reuseBtn.disabled = !wasSd;
          reuseBtn.onclick  = wasSd ? () => { seedEl.value = s.last_seed; } : null;
          downloadBtn.onclick = () => {
            const a = document.createElement('a');
            a.href = url; a.download = s.last_filename; a.click();
          };
          addToGallery(url, s.last_seed, modelShort);
          saveState();
          await checkHealth();
        }
      }
    }, 600);
  } else if (status.last_filename) {
    // Job finished while we were away — surface the result if not already shown
    const url = `${API}/image/${status.last_filename}`;
    if (!history.some(h => h.url === url)) {
      const modelShort = (status.last_model ?? '').split('/').pop().replace('.safetensors', '');
      const wasSd = (status.last_seed ?? -1) >= 0;
      placeholder.classList.add('hidden');
      outputImg.src = url;
      outputImg.classList.remove('hidden');
      outputMeta.classList.remove('hidden');
      metaSeed.textContent  = wasSd ? `Seed: ${status.last_seed}` : 'Gemini';
      metaModel.textContent = `Model: ${modelShort}`;
      metaSize.textContent  = wasSd ? `${canvasW}×${canvasH}` : '—';
      reuseBtn.disabled = !wasSd;
      reuseBtn.onclick  = wasSd ? () => { seedEl.value = status.last_seed; } : null;
      downloadBtn.onclick = () => {
        const a = document.createElement('a');
        a.href = url; a.download = status.last_filename; a.click();
      };
      addToGallery(url, status.last_seed, modelShort);
      saveState();
    }
  }
}

// Warn before leaving mid-generation
let _generating = false;
window.addEventListener('beforeunload', e => {
  if (_generating) { e.preventDefault(); e.returnValue = ''; }
});

// ── Init ───────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  await Promise.all([loadModels(), loadLoras()]);
  restoreState();
  await checkAndReattach();
})();

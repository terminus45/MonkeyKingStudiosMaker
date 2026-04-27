const API = window.location.origin;

// ── State ──────────────────────────────────────────────────────────────────
let canvasW = 1024, canvasH = 576;
let history = [];

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
const statusDot     = document.getElementById('statusDot');
const statusLabel   = document.getElementById('statusLabel');
const negToggle     = document.getElementById('negToggle');

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
    loraSelect.innerHTML = '<option value="">— none —</option>';
    (data.loras || []).forEach(l => {
      const opt = document.createElement('option');
      opt.value = l.num;
      opt.textContent = l.name;
      if (l.loaded) opt.selected = true;
      loraSelect.appendChild(opt);
    });
    loraScaleRow.style.display = loraSelect.value ? 'flex' : 'none';
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

// ── Style presets — fill the style textarea ────────────────────────────────
document.getElementById('stylePresets').addEventListener('click', e => {
  const btn = e.target.closest('.preset');
  if (!btn) return;
  stylePromptEl.value = btn.dataset.suffix;
  stylePromptEl.dispatchEvent(new Event('input'));
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

// ── Seed randomise ─────────────────────────────────────────────────────────
document.getElementById('randSeed').addEventListener('click', () => {
  seedEl.value = Math.floor(Math.random() * 2 ** 32);
});

// ── Negative prompt toggle ─────────────────────────────────────────────────
negToggle.addEventListener('click', () => {
  const open = negToggle.classList.toggle('open');
  negEl.classList.toggle('collapsed', !open);
});

// ── Generate ───────────────────────────────────────────────────────────────
generateBtn.addEventListener('click', generate);

async function generate() {
  const basePrompt  = promptEl.value.trim();
  if (!basePrompt) { promptEl.focus(); return; }
  const stylePart   = stylePromptEl.value.trim();
  const fullPrompt  = stylePart ? `${basePrompt}, ${stylePart}` : basePrompt;

  setLoading(true);
  showProgress(0, parseInt(stepsEl.value));

  try {
    const body = {
      prompt:          fullPrompt,
      negative_prompt: negEl.value.trim(),
      model_num:       parseInt(modelSel.value) || undefined,
      steps:           parseInt(stepsEl.value),
      guidance_scale:  parseFloat(cfgEl.value),
      width:           canvasW,
      height:          canvasH,
      seed:            parseInt(seedEl.value),
    };
    if (loraSelect.value) {
      body.lora_num   = parseInt(loraSelect.value);
      body.lora_scale = parseFloat(loraScaleEl.value);
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
        const evt = JSON.parse(line.slice(6));
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
    metaSeed.textContent  = `Seed: ${data.seed}`;
    metaModel.textContent = `Model: ${modelShort}`;
    metaSize.textContent  = `${canvasW}×${canvasH}`;

    reuseBtn.onclick = () => { seedEl.value = data.seed; };
    downloadBtn.onclick = () => {
      const a = document.createElement('a');
      a.href = imgUrl;
      a.download = data.filename;
      a.click();
    };

    addToGallery(imgUrl, data.seed, modelShort);
    await checkHealth();

  } catch (err) {
    alert(`Generation failed:\n${err.message}`);
  } finally {
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
function addToGallery(url, seed, model) {
  history.unshift({ url, seed, model });

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

// ── Init ───────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();
  await Promise.all([loadModels(), loadLoras()]);
})();

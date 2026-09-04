/* gallery.js — ES module */
// three.js is loaded lazily (only when the 3D viewer modal opens) so that the
// gallery listings still work even if the three.js CDN is unreachable.
let _three = null;
async function loadThree() {
  if (_three) return _three;
  const [THREE, gltf, orbit, roomEnv, stl] = await Promise.all([
    import('three'),
    import('three/addons/loaders/GLTFLoader.js'),
    import('three/addons/controls/OrbitControls.js'),
    import('three/addons/environments/RoomEnvironment.js'),
    import('three/addons/exporters/STLExporter.js'),
  ]);
  _three = {
    THREE,
    GLTFLoader: gltf.GLTFLoader,
    OrbitControls: orbit.OrbitControls,
    RoomEnvironment: roomEnv.RoomEnvironment,
    STLExporter: stl.STLExporter,
  };
  return _three;
}

const API = window.location.origin;

// ── DOM refs ────────────────────────────────────────────────────────────────
const statusDot           = document.getElementById('statusDot');
const statusLabel         = document.getElementById('statusLabel');
const refreshBtn          = document.getElementById('refreshBtn');

const tabButtons          = document.querySelectorAll('.gallery-tab');
const panelImages         = document.getElementById('panel-images');
const panelBooks          = document.getElementById('panel-books');
const panelModels         = document.getElementById('panel-models');

const imagesGrid          = document.getElementById('imagesGrid');
const imagesEmpty         = document.getElementById('imagesEmpty');
const booksGrid           = document.getElementById('booksGrid');
const booksEmpty          = document.getElementById('booksEmpty');
const modelsGrid          = document.getElementById('modelsGrid');
const modelsEmpty         = document.getElementById('modelsEmpty');

const modelViewerModal      = document.getElementById('modelViewerModal');
const modelViewerBackdrop   = document.getElementById('modelViewerBackdrop');
const modelViewerClose      = document.getElementById('modelViewerClose');
const modelViewerTitle      = document.getElementById('modelViewerTitle');
const modelViewerCanvas     = document.getElementById('modelViewerCanvas');
const modelViewerDownload   = document.getElementById('modelViewerDownload');
const modelViewerStl        = document.getElementById('modelViewerStl');
const modelViewerFullscreen = document.getElementById('modelViewerFullscreen');

// The .model-viewer-content div is the MAXIMIZED element (wraps header + canvas + footer).
const modelViewerContent    = modelViewerModal.querySelector('.model-viewer-content');

const imageViewerModal    = document.getElementById('imageViewerModal');
const imageViewerBackdrop = document.getElementById('imageViewerBackdrop');
const imageViewerClose    = document.getElementById('imageViewerClose');
const imageViewerImg      = document.getElementById('imageViewerImg');
const imageViewerCaption  = document.getElementById('imageViewerCaption');

// ── State ───────────────────────────────────────────────────────────────────
let activeTab = 'none';
let _loadedImages = [];   // last-fetched Images-tab records, for lineage lookups
const panelLoaded = { images: false, books: false, models: false };
let lastViewBtn = null;

// three.js modal state
let modalRenderer    = null;
let modalAnimId      = null;
let modalControls    = null;
let modalRo          = null;
let modalEnvMap      = null;
let _modalStlUrl     = null;   // blob URL for the client-side STL export (revoked on teardown)
let autoRotateTimer  = null;
let _modalFsCleanup  = null;   // cleanup fn returned by ViewerFullscreen.onFullscreenChange

// ── Helpers ─────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

// ── Health ──────────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const res  = await fetch(`${API}/health`);
    const data = await res.json();
    statusDot.className    = 'status-dot ok';
    statusLabel.textContent = 'Connected';
  } catch {
    statusDot.className    = 'status-dot error';
    statusLabel.textContent = 'Server offline';
  }
}

// ── Tab switching ────────────────────────────────────────────────────────────
function activateTab(tab) {
  if (activeTab === tab) return;
  activeTab = tab;

  tabButtons.forEach(btn => {
    const isActive = btn.dataset.tab === tab;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    btn.tabIndex = isActive ? 0 : -1;
  });

  panelImages.classList.toggle('hidden', tab !== 'images');
  panelBooks.classList.toggle('hidden',  tab !== 'books');
  panelModels.classList.toggle('hidden', tab !== 'models');

  if (!panelLoaded[tab]) {
    loadPanel(tab);
  }

  try { localStorage.setItem('gallery_active_tab', tab); } catch {}
}

tabButtons.forEach(btn => {
  btn.addEventListener('click', () => activateTab(btn.dataset.tab));

  btn.addEventListener('keydown', e => {
    const tabs = Array.from(tabButtons);
    const idx  = tabs.indexOf(btn);
    let next   = -1;
    if (e.key === 'ArrowRight') next = (idx + 1) % tabs.length;
    if (e.key === 'ArrowLeft')  next = (idx - 1 + tabs.length) % tabs.length;
    if (e.key === 'Home')       next = 0;
    if (e.key === 'End')        next = tabs.length - 1;
    if (next >= 0) {
      e.preventDefault();
      tabs[next].focus();
      activateTab(tabs[next].dataset.tab);
    }
  });
});

// ── Panel loaders ────────────────────────────────────────────────────────────
async function loadPanel(tab) {
  if (tab === 'images') await loadImages();
  else if (tab === 'books') await loadBooks();
  else if (tab === 'models') await loadModels();
}

// ── Images panel ─────────────────────────────────────────────────────────────

// Upscale gating — fetched once at init; when the engine isn't available
// (no local extras / no weights) the cards simply don't grow the button.
let _upscaleStatus = null;

async function loadUpscaleStatus() {
  try {
    const res = await fetch(`${API}/upscale/status`);
    if (res.ok) _upscaleStatus = await res.json();
  } catch { /* server unreachable — no button */ }
}

/**
 * 2x a saved image. One factor only: each result is itself a gallery image
 * with lineage, so "go larger" is just pressing 2x again on the result.
 * The worker gallery-saves server-side, so the finished image lands as a
 * new card even if the user leaves mid-job; this poll is only for the
 * refresh-when-done nicety.
 */
async function upscaleImage(e, img, card) {
  const btn = e.currentTarget;
  const thumb = card.querySelector('.image-card-thumb img');
  const w = thumb ? thumb.naturalWidth : 0, h = thumb ? thumb.naturalHeight : 0;
  if (_upscaleStatus && w && h && w * h * 4 > _upscaleStatus.max_output_pixels) {
    alert(`This image is already ${w}×${h} — 2× would exceed the ` +
          `${Math.round(_upscaleStatus.max_output_pixels / 1e6)} MP limit.`);
    return;
  }
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = '⏳ 0%';
  try {
    const res = await fetch(`${API}/upscale/job`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ filename: img.filename, factor: 2 }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);
    const { job_id } = await res.json();
    for (;;) {
      await new Promise(r => setTimeout(r, 1500));
      const s = await fetch(`${API}/generate/status/${job_id}`);
      if (!s.ok) throw new Error('The job was lost (did the server restart?). Check back shortly — finished upscales still appear here.');
      const rec = await s.json();
      if (rec.stage === 'done') break;
      if (rec.stage === 'error') throw new Error(rec.error || 'Upscale failed.');
      btn.textContent = `⏳ ${rec.progress || 0}%`;
    }
    await loadImages();          // the new card appears at the top
  } catch (err) {
    alert(`Upscale failed: ${err.message}`);
    btn.disabled = false;
    btn.textContent = label;
  }
}
async function loadImages() {
  panelLoaded.images = true;
  imagesEmpty.textContent = 'Loading…';
  imagesEmpty.style.display = 'block';
  imagesGrid.querySelectorAll('.image-card').forEach(c => c.remove());

  try {
    const res = await fetch(`${API}/gallery/images`);
    if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);
    const data   = await res.json();
    const images = data.images || [];
    _loadedImages = images;   // kept for lineage lookups in the info panel

    if (images.length === 0) {
      imagesEmpty.textContent = 'No saved images yet — make one in the Character Generator!';
      return;
    }
    imagesEmpty.style.display = 'none';
    images.forEach(img => imagesGrid.appendChild(buildImageCard(img)));
  } catch (err) {
    imagesEmpty.textContent = `Could not load images: ${err.message}`;
  }
}

function buildImageCard(img) {
  const card = document.createElement('div');
  card.className = 'image-card';
  card.dataset.filename = img.filename;

  const promptText = img.prompt || '';
  const altText    = promptText ? `Character portrait: ${promptText.slice(0, 80)}` : 'Character portrait';
  const dateStr    = formatDate(img.created_at);

  card.innerHTML = `
    <div class="image-card-thumb">
      <img src="${API}/image/${escHtml(img.filename)}" alt="${escHtml(altText)}" loading="lazy">
    </div>
    <div class="image-card-info">
      <p class="image-card-prompt" title="${escHtml(promptText)}">${escHtml(promptText || '—')}</p>
      <p class="image-card-date">${escHtml(dateStr)}</p>
    </div>
    <div class="book-actions">
      <button
        class="book-action-btn"
        data-action="view-image"
        aria-label="View this picture larger"
      >🔍 View Pic</button>
      <button
        class="book-action-btn book-action-btn--figure"
        data-action="make-figure"
        aria-label="Make a 3D figure from this picture"
      >🧸 Make Figure</button>
      <button
        class="book-action-btn"
        data-action="reuse-image"
        aria-label="Reuse this prompt in the Character Generator"
      >↺ Reuse</button>
      ${_upscaleStatus && _upscaleStatus.available ? `
      <button
        class="book-action-btn"
        data-action="upscale-image"
        aria-label="Double this image's resolution"
        title="Double the resolution — press again on the result to go larger"
      >🔎 2×</button>` : ''}
      <button
        class="book-action-btn"
        data-action="image-info"
        aria-label="Show generation details"
      >ⓘ Info</button>
      <a
        class="book-action-btn"
        href="${API}/image/${escHtml(img.filename)}"
        download="character-${escHtml(img.filename)}"
        aria-label="Download image"
        style="text-decoration:none;"
      >↓ Download</a>
      <button
        class="book-action-btn danger"
        data-action="delete-image"
        aria-label="Delete image"
      >🗑</button>
    </div>
  `;

  card.querySelector('[data-action="view-image"]').addEventListener('click', () => openImageViewer(img));
  card.querySelector('[data-action="make-figure"]').addEventListener('click', e => makeFigureFromImage(e, img));
  card.querySelector('[data-action="reuse-image"]').addEventListener('click', () => reuseImagePrompt(img));
  const upBtn = card.querySelector('[data-action="upscale-image"]');
  if (upBtn) upBtn.addEventListener('click', e => upscaleImage(e, img, card));
  card.querySelector('[data-action="image-info"]').addEventListener('click', () => openImageViewer(img, { withMeta: true }));
  card.querySelector('[data-action="delete-image"]').addEventListener('click', e => deleteImage(e, img.id, card));
  return card;
}

// Load a saved image's prompt/style/model back into the Character Generator,
// then navigate there. Prompt + style flow through the shared-inputs store;
// the model is merged into the Character Generator's own draft.
function reuseImagePrompt(img) {
  if (window.SharedInputs) {
    window.SharedInputs.patch({
      character: img.prompt || '',
      story: img.story || '',
      style: img.style_prompt || '',
    });
  }
  if (img.model) {
    try {
      const draft = JSON.parse(localStorage.getItem('monkeyking_cg_draft') || '{}');
      draft.model = img.model;
      localStorage.setItem('monkeyking_cg_draft', JSON.stringify(draft));
    } catch { /* quota / private-mode / corrupted draft */ }
  }
  window.location.href = 'character_generator.html';
}

async function deleteImage(e, imageId, card) {
  if (!confirm('Delete this image from the gallery?')) return;
  const btn = e.currentTarget;
  btn.disabled = true;
  try {
    const res = await fetch(`${API}/gallery/image/${encodeURIComponent(imageId)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);
    card.remove();
    if (!imagesGrid.querySelector('.image-card')) {
      imagesEmpty.textContent = 'No saved images yet — make one in the Character Generator!';
      imagesEmpty.style.display = 'block';
    }
  } catch (err) {
    alert(`Delete failed: ${err.message}`);
    btn.disabled = false;
  }
}

// ── Make Figure ──────────────────────────────────────────────────────────────
// Same flow as the Character Generator's "Create Figure" button: start a Meshy
// image-to-3D job from the saved picture + its original prompt, stash the job id,
// then hand off to Figure Maker (resumeJobIfAny picks it up).
//
// COUPLING NOTE: the localStorage key/shape below must stay in sync with
// figure_maker.js FM_JOB_KEY / saveFmJob — mirrors character_generator.js.
async function makeFigureFromImage(e, img) {
  if (!confirm(
    'Make a 3D figure from this picture?\n\n' +
    'This is a paid 3D generation and takes a few minutes. Continue?'
  )) return;
  const btn = e.currentTarget;
  const originalLabel = btn.textContent;
  btn.disabled = true;
  btn.textContent = '⏳ Starting…';

  function restoreBtn() {
    btn.disabled = false;
    btn.textContent = originalLabel;
  }

  try {
    const res = await fetch(`${API}/figure/generate-from-image`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        filename: img.filename,
        prompt:   img.prompt || '',
        style:    img.style_prompt || '',
        story:    img.story || '',
      }),
    });

    if (!res.ok) {
      let msg;
      try {
        const body = await res.json();
        if (res.status === 503) {
          msg = 'Meshy key not set — ask a grown-up to add it in Settings (⚙).';
        } else if (res.status === 404) {
          msg = "Couldn't find that picture on the server. It may have been cleaned up.";
        } else if (res.status === 400) {
          // /figure/generate-from-image only accepts generated portraits
          // ([a-f0-9]{32}.png); anything else is rejected before Meshy is called.
          msg = "This picture can't be turned into a figure. Try one made in the Character Generator.";
        } else {
          msg = body.detail || `Something went wrong (error ${res.status}).`;
        }
      } catch {
        msg = `Something went wrong (error ${res.status}).`;
      }
      restoreBtn();
      alert(msg);
      return;
    }

    const data = await res.json();

    // Carry the saved prompt/story/style into the shared inputs so Figure Maker
    // shows the context this figure was built from.
    if (window.SharedInputs) {
      window.SharedInputs.patch({
        character: img.prompt || '',
        story:     img.story || '',
        style:     img.style_prompt || '',
      });
    }

    localStorage.setItem('monkeyking_fm_job', JSON.stringify({
      job_id:     data.job_id,
      started_at: Date.now(),
    }));

    window.location.href = 'figure_maker.html';

  } catch {
    restoreBtn();
    alert('Network error — check your connection and try again.');
  }
}

// ── Image lightbox ───────────────────────────────────────────────────────────
// Sizing is pure CSS (85vw wide, capped at 82vh tall) so the picture keeps its
// aspect ratio and a tall portrait can't run off the bottom of the screen.
let _imgViewerLastFocus = null;

function openImageViewer(img, opts) {
  const promptText = img.prompt || '';
  // Property assignment, not innerHTML — no escaping needed, and no HTML sink.
  imageViewerImg.src = `${API}/image/${img.filename}`;
  imageViewerImg.alt = promptText ? `Character portrait: ${promptText}` : 'Character portrait';
  imageViewerCaption.textContent = promptText;
  imageViewerCaption.style.display = promptText ? 'block' : 'none';

  const metaBox = document.getElementById('imageViewerMeta');
  metaBox.classList.add('hidden');
  metaBox.textContent = '';
  if (opts && opts.withMeta) renderImageMeta(img, metaBox);

  _imgViewerLastFocus = document.activeElement;
  imageViewerModal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  imageViewerClose.focus();
}

// ── Generation details panel (ⓘ Info) ────────────────────────────────────────
// Built entirely with createElement/textContent — meta values come from user
// prompts and must never reach an HTML sink.
async function renderImageMeta(img, box) {
  let meta = img.meta || null;
  if (!meta) {
    // Legacy record or manifest predating metadata — the PNG itself may know.
    try {
      const res = await fetch(`${API}/image/${img.filename}/meta`);
      if (res.ok) meta = await res.json();
    } catch { /* offline — fall through to the empty message */ }
  }

  box.textContent = '';
  box.classList.remove('hidden');

  if (!meta || Object.keys(meta).length === 0) {
    const p = document.createElement('p');
    p.className = 'image-viewer-meta-empty';
    p.textContent = 'No generation details recorded — this image predates metadata.';
    box.appendChild(p);
    return;
  }

  const rows = [
    ['Model',    meta.model_id],
    ['Backend',  meta.backend],
    ['Seed',     meta.seed],
    ['Sampler',  meta.sampler],
    ['Steps',    meta.steps],
    ['Guidance', meta.guidance],
    ['Size',     meta.width && meta.height ? `${meta.width}×${meta.height}` : null],
    ['Hires',    meta.hires && meta.hires.ran
                   ? `${meta.hires.width}×${meta.hires.height} @ ${meta.hires.denoise}`
                   : null],
    ['Refined from', meta.parent_filename || null],
    ['Prompt',   meta.prompt_final],
  ];
  const table = document.createElement('table');
  table.className = 'image-viewer-meta-table';
  for (const [label, value] of rows) {
    if (value === null || value === undefined || value === '') continue;
    const tr = document.createElement('tr');
    const th = document.createElement('th');
    th.textContent = label;
    const td = document.createElement('td');
    td.textContent = String(value);
    tr.append(th, td);
    table.appendChild(tr);
  }
  box.appendChild(table);

  // Lineage: jump to the parent image if it is in the loaded set.
  if (meta.parent_filename) {
    const parentRec = (_loadedImages || []).find(r => r.filename === meta.parent_filename);
    if (parentRec) {
      const btn = document.createElement('button');
      btn.className = 'settings-btn';
      btn.textContent = '↰ View original';
      btn.addEventListener('click', () => openImageViewer(parentRec, { withMeta: true }));
      box.appendChild(btn);
    }
  }

  // Regenerate — only ever offered when the recipe is honestly reproducible.
  if (meta.reproducible) {
    const btn = document.createElement('button');
    btn.className = 'settings-btn';
    btn.textContent = '🎲 Regenerate';
    btn.title = 'Re-render from this exact recipe (same seed and settings)';
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        const res = await fetch(`${API}/regenerate/job`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: img.filename }),
        });
        if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);
        btn.textContent = '✓ Started — refresh Images in a minute';
      } catch (err) {
        btn.textContent = `⚠ ${err.message}`;
        btn.disabled = false;
      }
    });
    box.appendChild(btn);
  }
}

function closeImageViewer() {
  imageViewerModal.classList.add('hidden');
  document.body.style.overflow = '';
  // Drop the src so a large picture isn't held in memory while the modal is shut.
  imageViewerImg.src = '';
  if (_imgViewerLastFocus && _imgViewerLastFocus.focus) _imgViewerLastFocus.focus();
  _imgViewerLastFocus = null;
}

imageViewerClose.addEventListener('click', closeImageViewer);
imageViewerBackdrop.addEventListener('click', closeImageViewer);

// ── Books panel ──────────────────────────────────────────────────────────────
async function loadBooks() {
  panelLoaded.books = true;
  booksEmpty.textContent = 'Loading…';
  booksEmpty.style.display = 'block';
  booksGrid.querySelectorAll('.book-card').forEach(c => c.remove());

  try {
    const res   = await fetch(`${API}/gallery`);
    if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);
    const data  = await res.json();
    const books = data.books || [];

    if (books.length === 0) {
      booksEmpty.textContent = 'No saved storybooks yet — build one in the Book Builder!';
      return;
    }
    booksEmpty.style.display = 'none';
    books.forEach(book => booksGrid.appendChild(buildBookCard(book)));
  } catch (err) {
    booksEmpty.textContent = `Could not load books: ${err.message}`;
  }
}

function buildBookCard(book) {
  const card = document.createElement('div');
  card.className = 'book-card';

  const coverSrc  = book.cover_image ? `${API}/image/${book.cover_image}` : null;
  const isTextOnly = book.include_art === false;
  const coverHTML = coverSrc
    ? `<img src="${coverSrc}" alt="cover" loading="lazy">`
    : isTextOnly
      ? `<div class="book-cover-placeholder">📝</div>`
      : `<div class="book-cover-placeholder">📖</div>`;

  const date        = book.saved_at
    ? new Date(book.saved_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
    : '';
  const imagesLabel = `${book.images_generated} / ${book.page_count} images`;
  const langClass   = `lang-${book.language || 'zh'}`;

  card.innerHTML = `
    <div class="book-cover">${coverHTML}</div>
    <div class="book-info">
      <div class="book-title-native ${langClass}">${escHtml(book.title_native || '')}</div>
      <div class="book-title-en">${escHtml(book.title_en)}</div>
      <div class="book-meta">${date} · ${imagesLabel}</div>
    </div>
    <div class="book-actions">
      <button class="book-action-btn" data-action="open"   data-id="${book.id}">✏ Open</button>
      <button class="book-action-btn" data-action="pdf"    data-id="${book.id}">🖨 PDF</button>
      <button class="book-action-btn danger" data-action="delete" data-id="${book.id}">🗑</button>
    </div>
  `;

  card.querySelector('[data-action="open"]').addEventListener('click',   () => openBook(book.id));
  card.querySelector('[data-action="pdf"]').addEventListener('click',    e  => downloadPDF(e, book.id));
  card.querySelector('[data-action="delete"]').addEventListener('click', e  => deleteBook(e, book.id, card));

  return card;
}

function openBook(bookId) {
  window.location.href = `book_builder.html?gallery_id=${encodeURIComponent(bookId)}`;
}

async function downloadPDF(e, bookId) {
  const btn = e.currentTarget;
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const res     = await fetch(`${API}/gallery/${bookId}`);
    const project = await res.json();
    // window.openPrintWindow is exposed by storybook_print.js (loaded as plain script)
    await window.openPrintWindow(project, API);
  } catch (err) {
    alert(`Failed to load book: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = '🖨 PDF';
  }
}

async function deleteBook(e, bookId, card) {
  if (!confirm('Delete this storybook from the gallery?')) return;
  const btn = e.currentTarget;
  btn.disabled = true;
  try {
    const res = await fetch(`${API}/gallery/${bookId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error((await res.json()).detail);
    card.remove();
    if (!booksGrid.querySelector('.book-card')) {
      booksEmpty.textContent = 'No saved storybooks yet — build one in the Book Builder!';
      booksEmpty.style.display = 'block';
    }
  } catch (err) {
    alert(`Delete failed: ${err.message}`);
    btn.disabled = false;
  }
}

// ── 3D Models panel ──────────────────────────────────────────────────────────
async function loadModels() {
  panelLoaded.models = true;
  modelsEmpty.textContent = 'Loading…';
  modelsEmpty.style.display = 'block';
  modelsGrid.querySelectorAll('.model-card').forEach(c => c.remove());

  try {
    const res    = await fetch(`${API}/gallery/models`);
    if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);
    const data   = await res.json();
    const models = data.models || [];

    if (models.length === 0) {
      modelsEmpty.textContent = 'No saved 3D models yet — sculpt one in the Figure Maker!';
      return;
    }
    modelsEmpty.style.display = 'none';
    models.forEach(m => modelsGrid.appendChild(buildModelCard(m)));
  } catch (err) {
    modelsEmpty.textContent = `Could not load models: ${err.message}`;
  }
}

function buildModelCard(model) {
  const card = document.createElement('div');
  card.className = 'model-card';

  const thumbSrc = model.thumbnail_filename ? `${API}/image/${model.thumbnail_filename}` : null;
  const thumbHTML = thumbSrc
    ? `<img src="${escHtml(thumbSrc)}" alt="3D model preview: ${escHtml((model.prompt || '').slice(0, 60))}" loading="lazy"><div class="model-thumb-placeholder" aria-hidden="true">🧊</div>`
    : `<div class="model-thumb-placeholder" aria-hidden="true">🧊</div>`;

  const glbUrl       = model.glb_filename ? `${API}/figure/model/${model.glb_filename}` : '#';
  const promptText   = model.prompt || 'Untitled model';
  const filamentHTML = model.filament
    ? `<span class="model-filament-tag" aria-label="Suggested filament: ${escHtml(model.filament)}">${escHtml(model.filament)}</span>`
    : '';
  const dateStr = formatDate(model.created_at);

  card.innerHTML = `
    <div class="model-card-thumb">${thumbHTML}</div>
    <div class="model-card-info">
      <p class="model-card-title">${escHtml(promptText)}</p>
      <div class="model-card-meta">
        ${filamentHTML}
        <span class="model-card-date">${escHtml(dateStr)}</span>
      </div>
    </div>
    <div class="book-actions">
      <button
        class="book-action-btn"
        data-action="view-model"
        aria-label="View 3D model: ${escHtml(promptText.slice(0, 60))}"
      >🧊 View 3D</button>
      <a
        class="book-action-btn"
        href="${escHtml(glbUrl)}"
        download="${escHtml(model.glb_filename || 'model.glb')}"
        aria-label="Download GLB file"
        style="text-decoration:none;"
      >↓ GLB</a>
      <button
        class="book-action-btn"
        data-action="stl"
        aria-label="Download STL file for 3D printing"
      >↓ STL</button>
      <button
        class="book-action-btn danger"
        data-action="delete-model"
        aria-label="Delete this 3D model"
      >🗑</button>
    </div>
  `;

  const viewBtn = card.querySelector('[data-action="view-model"]');
  viewBtn.addEventListener('click', () => openModelViewer(glbUrl, promptText, viewBtn));
  card.querySelector('[data-action="stl"]').addEventListener('click', e =>
    downloadModelStl(glbUrl, model.glb_filename, e.currentTarget));
  card.querySelector('[data-action="delete-model"]').addEventListener('click', e => deleteModel(e, model.id, card));

  return card;
}

// Download an STL for a gallery model WITHOUT opening the viewer: load the GLB
// headlessly (three.js + GLTFLoader), export STL client-side (no server round-trip,
// no stored file — the GLB is the source of truth), and trigger a download.
async function downloadModelStl(glbUrl, glbFilename, btn) {
  if (!glbUrl || glbUrl === '#') return;
  const orig = btn.textContent;
  btn.textContent = '…';
  btn.setAttribute('aria-disabled', 'true');
  let url = null;
  try {
    const { GLTFLoader, STLExporter } = await loadThree();
    const gltf = await new GLTFLoader().loadAsync(glbUrl);
    const stlData = new STLExporter().parse(gltf.scene, { binary: true });
    const blob = new Blob([stlData], { type: 'model/stl' });
    url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (glbFilename || 'model.glb').replace(/\.glb$/i, '.stl');
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (err) {
    console.error('STL export failed', err);
    alert('Could not prepare the STL (the 3D viewer failed to load). Try opening "View 3D" instead.');
  } finally {
    if (url) setTimeout(() => URL.revokeObjectURL(url), 10000);
    btn.textContent = orig;
    btn.removeAttribute('aria-disabled');
  }
}

async function deleteModel(e, modelId, card) {
  if (!confirm('Delete this 3D model from the gallery?')) return;
  const btn = e.currentTarget;
  btn.disabled = true;
  try {
    const res = await fetch(`${API}/gallery/model/${encodeURIComponent(modelId)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);
    card.remove();
    if (!modelsGrid.querySelector('.model-card')) {
      modelsEmpty.textContent = 'No saved 3D models yet — sculpt one in the Figure Maker!';
      modelsEmpty.style.display = 'block';
    }
  } catch (err) {
    alert(`Delete failed: ${err.message}`);
    btn.disabled = false;
  }
}

// ── 3D viewer modal ──────────────────────────────────────────────────────────
function openModelViewer(glbUrl, title, triggerBtn) {
  lastViewBtn = triggerBtn;
  modelViewerTitle.textContent  = title;
  modelViewerDownload.href      = glbUrl;
  modelViewerDownload.download  = glbUrl.split('/').pop() || 'model.glb';

  modelViewerModal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  modelViewerClose.focus();

  mountModalViewer(glbUrl);
}

function closeModelViewer() {
  // Force-exit fullscreen/maximized first so the page isn't stranded in
  // fullscreen mode with a torn-down scene.
  if (window.ViewerFullscreen && window.ViewerFullscreen.isMaximized(modelViewerContent)) {
    window.ViewerFullscreen.toggle(modelViewerContent, { onResize: function () {} });
  }
  modelViewerModal.classList.add('hidden');
  document.body.style.overflow = '';
  teardownModalViewer();
  if (lastViewBtn) lastViewBtn.focus();
}

function teardownModalViewer() {
  if (autoRotateTimer) { clearTimeout(autoRotateTimer); autoRotateTimer = null; }
  if (modalAnimId)     { cancelAnimationFrame(modalAnimId); modalAnimId = null; }
  if (modalRo)         { modalRo.disconnect(); modalRo = null; }
  if (modalControls)   { modalControls.dispose(); modalControls = null; }
  if (modalEnvMap)     { modalEnvMap.dispose(); modalEnvMap = null; }
  if (modalRenderer)   { modalRenderer.dispose(); modalRenderer = null; }
  // Remove all canvas children EXCEPT the fullscreen button (which lives in the HTML
  // and must persist for future openings — only the renderer canvas is dynamic).
  Array.from(modelViewerCanvas.childNodes).forEach(node => {
    if (node !== modelViewerFullscreen) modelViewerCanvas.removeChild(node);
  });
  // Hide the fullscreen button and deregister the fullscreenchange listener.
  modelViewerFullscreen.classList.add('hidden');
  if (_modalFsCleanup) { _modalFsCleanup(); _modalFsCleanup = null; }

  // Drop the client-side STL export — it's regenerated when the next model loads.
  if (_modalStlUrl) { URL.revokeObjectURL(_modalStlUrl); _modalStlUrl = null; }
  modelViewerStl.classList.add('hidden');
}

// Clear the canvas's dynamic children (loading text / old renderer canvas) while
// PRESERVING the static fullscreen button — `container.textContent = …` would delete it.
function _setModalCanvasMsg(msg) {
  Array.from(modelViewerCanvas.childNodes).forEach(node => {
    if (node !== modelViewerFullscreen) modelViewerCanvas.removeChild(node);
  });
  if (msg) {
    const p = document.createElement('p');
    p.className = 'model-viewer-loading';
    p.textContent = msg;
    modelViewerCanvas.appendChild(p);
  }
}

async function mountModalViewer(glbUrl) {
  teardownModalViewer();

  const container = modelViewerCanvas;

  // Load three.js on demand. If the CDN is unreachable, fall back gracefully —
  // the user can still download the GLB from the modal footer.
  let THREE, GLTFLoader, OrbitControls, RoomEnvironment, STLExporter;
  // NOTE: do NOT use container.textContent to set/clear — the fullscreen button is
  // a static child of this container and textContent would delete it permanently.
  _setModalCanvasMsg('Loading 3D viewer…');
  try {
    ({ THREE, GLTFLoader, OrbitControls, RoomEnvironment, STLExporter } = await loadThree());
  } catch (err) {
    console.error('Failed to load three.js', err);
    _setModalCanvasMsg('Could not load the 3D viewer (are you offline?). You can still download the GLB below.');
    return;
  }
  // The modal may have been closed while three.js was loading.
  if (modelViewerModal.classList.contains('hidden')) return;
  _setModalCanvasMsg('');

  const w = container.clientWidth  || 720;
  const h = container.clientHeight || 340;

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(w, h);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  const canvas = renderer.domElement;
  canvas.setAttribute('aria-hidden', 'true');
  container.appendChild(canvas);
  modalRenderer = renderer;

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, w / h, 0.01, 1000);
  camera.position.set(0, 0, 3);

  // Image-based lighting (procedural studio room) so PBR materials read as bright as
  // Meshy's studio-lit thumbnail instead of looking dark/flat under direct lights.
  const pmrem = new THREE.PMREMGenerator(renderer);
  modalEnvMap = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = modalEnvMap;
  pmrem.dispose();

  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
  dirLight.position.set(5, 10, 5);
  scene.add(dirLight);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping   = true;
  controls.dampingFactor   = 0.05;
  controls.autoRotate      = true;
  controls.autoRotateSpeed = 1.5;
  modalControls = controls;

  controls.addEventListener('start', () => {
    controls.autoRotate = false;
    if (autoRotateTimer) clearTimeout(autoRotateTimer);
    autoRotateTimer = setTimeout(() => { if (modalControls) modalControls.autoRotate = true; }, 10000);
  });

  // Shared resize routine for this viewer instance.
  function applyModalResize() {
    if (!modalRenderer) return;
    const nw = container.clientWidth;
    const nh = container.clientHeight;
    modalRenderer.setSize(nw, nh);
    camera.aspect = nw / nh;
    camera.updateProjectionMatrix();
  }

  const loader = new GLTFLoader();
  loader.load(
    glbUrl,
    gltf => {
      const model = gltf.scene;
      scene.add(model);

      const box    = new THREE.Box3().setFromObject(model);
      const center = new THREE.Vector3();
      const sphere = new THREE.Sphere();
      box.getBoundingSphere(sphere);
      box.getCenter(center);
      model.position.sub(center);
      camera.position.set(0, sphere.radius * 0.3, sphere.radius * 2.5);
      controls.target.set(0, 0, 0);
      controls.update();

      // Export an STL from the loaded GLB (client-side, like Figure Maker) so the
      // model can be downloaded for 3D printing straight from the Gallery.
      try {
        const stlData = new STLExporter().parse(model, { binary: true });
        const blob    = new Blob([stlData], { type: 'model/stl' });
        if (_modalStlUrl) URL.revokeObjectURL(_modalStlUrl);
        _modalStlUrl = URL.createObjectURL(blob);
        modelViewerStl.href = _modalStlUrl;
        modelViewerStl.download = (modelViewerDownload.download || 'model.glb').replace(/\.glb$/i, '.stl');
        modelViewerStl.classList.remove('hidden');
      } catch (e) {
        console.error('STL export failed', e);
        modelViewerStl.classList.add('hidden');
      }

      // Reveal the fullscreen button now that a model is confirmed loaded.
      modelViewerFullscreen.classList.remove('hidden');

      // Wire the fullscreen button.
      if (window.ViewerFullscreen) {
        function _syncModalFsBtn(maximized) {
          modelViewerFullscreen.setAttribute('aria-pressed', maximized ? 'true' : 'false');
          modelViewerFullscreen.setAttribute('aria-label', maximized ? 'Exit fullscreen' : 'Enter fullscreen');
          modelViewerFullscreen.classList.toggle('is-fullscreen', maximized);
        }

        modelViewerFullscreen.onclick = () => {
          window.ViewerFullscreen.toggle(modelViewerContent, { onResize: applyModalResize });
          _syncModalFsBtn(window.ViewerFullscreen.isMaximized(modelViewerContent));
        };

        // Register fullscreenchange listener to sync when user exits via OS/Esc.
        if (_modalFsCleanup) _modalFsCleanup();
        _modalFsCleanup = window.ViewerFullscreen.onFullscreenChange(modelViewerContent, (maximized) => {
          _syncModalFsBtn(maximized);
          applyModalResize();
        });

        _syncModalFsBtn(window.ViewerFullscreen.isMaximized(modelViewerContent));
      }
    },
    undefined,
    err => { console.error('GLTFLoader error in modal', err); }
  );

  const ro = new ResizeObserver(() => { applyModalResize(); });
  ro.observe(container);
  modalRo = ro;

  function animate() {
    modalAnimId = requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();
}

// Modal event listeners
modelViewerClose.addEventListener('click', closeModelViewer);
modelViewerBackdrop.addEventListener('click', closeModelViewer);

document.addEventListener('keydown', e => {
  // The image lightbox sits above the 3D modal (z-index 110 vs 100), so it
  // claims Escape first when open.
  if (!imageViewerModal.classList.contains('hidden')) {
    if (e.key === 'Escape') { closeImageViewer(); }
    return;
  }
  if (modelViewerModal.classList.contains('hidden')) return;
  // Ctrl+M toggles fullscreen (only once a model is loaded → button visible).
  if (e.ctrlKey && !e.metaKey && !e.altKey && (e.key === 'm' || e.key === 'M')) {
    if (!modelViewerFullscreen.classList.contains('hidden')) {
      e.preventDefault();
      modelViewerFullscreen.click();
    }
    return;
  }
  if (e.key === 'Escape') {
    // FIX ESCAPE ORDERING: if fullscreen/maximized is active, exit that first.
    // The browser's native fullscreen API may intercept Esc itself (before this
    // handler fires), in which case onFullscreenChange already synced the state.
    // We guard here for the CSS-overlay path (no native API, or after native already exited).
    if (window.ViewerFullscreen && window.ViewerFullscreen.isMaximized(modelViewerContent)) {
      window.ViewerFullscreen.toggle(modelViewerContent, { onResize: function () {} });
      return;   // do NOT close the modal — user must press Esc again
    }
    closeModelViewer();
    return;
  }
  // Focus trap — includes the fullscreen button when it is visible
  if (e.key === 'Tab') {
    const focusable = [modelViewerClose, modelViewerDownload];
    if (!modelViewerStl.classList.contains('hidden')) {
      focusable.push(modelViewerStl);
    }
    if (!modelViewerFullscreen.classList.contains('hidden')) {
      focusable.push(modelViewerFullscreen);
    }
    const first = focusable[0];
    const last  = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault(); first.focus();
    }
  }
});

// ── Refresh button ───────────────────────────────────────────────────────────
refreshBtn.addEventListener('click', () => {
  panelLoaded[activeTab] = false;
  loadPanel(activeTab);
});

// ── Init ─────────────────────────────────────────────────────────────────────
(async () => {
  await checkHealth();

  // Before the first card renders — buildImageCard reads the flag.
  await loadUpscaleStatus();

  // Determine starting tab from URL param or localStorage
  const urlTab   = new URLSearchParams(window.location.search).get('tab');
  let startTab   = urlTab || null;
  if (!startTab) {
    try { startTab = localStorage.getItem('gallery_active_tab'); } catch {}
  }
  startTab = startTab || 'images';

  activateTab(startTab);
})();

setInterval(checkHealth, 30_000);

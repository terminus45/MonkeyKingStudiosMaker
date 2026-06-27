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

// ── State ───────────────────────────────────────────────────────────────────
let activeTab = 'none';
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
        data-action="reuse-image"
        aria-label="Reuse this prompt in the Character Generator"
      >↺ Reuse</button>
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

  card.querySelector('[data-action="reuse-image"]').addEventListener('click', () => reuseImagePrompt(img));
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
  const coverHTML = coverSrc
    ? `<img src="${coverSrc}" alt="cover" loading="lazy">`
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

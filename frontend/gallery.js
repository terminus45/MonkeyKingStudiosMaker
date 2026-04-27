const API = window.location.origin;

const galleryGrid = document.getElementById('galleryGrid');
const emptyMsg    = document.getElementById('emptyMsg');
const refreshBtn  = document.getElementById('refreshBtn');
const statusDot   = document.getElementById('statusDot');
const statusLabel = document.getElementById('statusLabel');

// ── Health ─────────────────────────────────────────────────────────────────
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

// ── Load gallery ───────────────────────────────────────────────────────────
async function loadGallery() {
  emptyMsg.textContent = 'Loading…';
  emptyMsg.style.display = 'block';
  galleryGrid.querySelectorAll('.book-card').forEach(c => c.remove());

  try {
    const res  = await fetch(`${API}/gallery`);
    const data = await res.json();
    const books = data.books || [];

    if (books.length === 0) {
      emptyMsg.textContent = 'No saved storybooks yet. Build one in the Book Builder!';
      return;
    }

    emptyMsg.style.display = 'none';
    books.forEach(book => galleryGrid.appendChild(buildBookCard(book)));
  } catch {
    emptyMsg.textContent = 'Could not reach server.';
  }
}

// ── Build card ─────────────────────────────────────────────────────────────
function buildBookCard(book) {
  const card = document.createElement('div');
  card.className = 'book-card';

  const coverSrc = book.cover_image
    ? `${API}/image/${book.cover_image}`
    : null;

  const coverHTML = coverSrc
    ? `<img src="${coverSrc}" alt="cover" loading="lazy">`
    : `<div class="book-cover-placeholder">📖</div>`;

  const date = book.saved_at
    ? new Date(book.saved_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
    : '';

  const imagesLabel = `${book.images_generated} / ${book.page_count} images`;

  card.innerHTML = `
    <div class="book-cover">${coverHTML}</div>
    <div class="book-info">
      <div class="book-title-zh">${escHtml(book.title_zh)}</div>
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

// ── Actions ────────────────────────────────────────────────────────────────
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
    await openPrintWindow(project, API);
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
    if (!galleryGrid.querySelector('.book-card')) {
      emptyMsg.textContent = 'No saved storybooks yet. Build one in the Book Builder!';
      emptyMsg.style.display = 'block';
    }
  } catch (err) {
    alert(`Delete failed: ${err.message}`);
    btn.disabled = false;
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
refreshBtn.addEventListener('click', loadGallery);

(async () => {
  await checkHealth();
  await loadGallery();
})();

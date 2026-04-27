/* Shared storybook HTML builder used by book_builder.js and gallery.js */

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function blobToDataURL(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

async function fetchImagesAsBase64(generatedImages, apiBase) {
  const imageB64 = {};
  await Promise.all(
    Object.entries(generatedImages).map(async ([pageNum, filename]) => {
      if (!filename) return;
      try {
        const res  = await fetch(`${apiBase}/image/${filename}`);
        const blob = await res.blob();
        imageB64[parseInt(pageNum)] = await blobToDataURL(blob);
      } catch {
        imageB64[parseInt(pageNum)] = null;
      }
    })
  );
  return imageB64;
}

// ── Pinyin syllable splitter ───────────────────────────────────────────────
// Used to generate per-character data for books that predate the characters field.

const _PY_INITIALS = ['zh','ch','sh','b','p','m','f','d','t','n','l','g','k','h','j','q','x','z','c','s','r','y','w'];
const _PY_VOWELS   = new Set([...'aeiouüāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ']);

function _isVowel(c) { return _PY_VOWELS.has(c.toLowerCase()); }

function _isCJK(c) {
  const cp = c.codePointAt(0);
  return (cp >= 0x4E00 && cp <= 0x9FFF)
      || (cp >= 0x3400 && cp <= 0x4DBF)
      || (cp >= 0x20000 && cp <= 0x2A6DF)
      || (cp >= 0xF900 && cp <= 0xFAFF);
}

function _nextSyllable(s) {
  const low = s.toLowerCase();
  let i = 0;
  for (const init of _PY_INITIALS) {
    if (low.startsWith(init) && init.length < s.length && _isVowel(s[init.length])) {
      i = init.length; break;
    }
  }
  if (!_isVowel(s[i])) return null;
  while (i < s.length && _isVowel(s[i])) i++;
  if (low.startsWith('ng', i))                                          i += 2;
  else if (s[i] === 'n' && (i + 1 >= s.length || !_isVowel(s[i+1]))) i++;
  else if (s[i] === 'r' && (i + 1 >= s.length || !_isVowel(s[i+1]))) i++;
  return i > 0 ? s.slice(0, i) : null;
}

function _splitPinyinSyllables(pinyin) {
  const syllables = [];
  for (const token of pinyin.trim().split(/\s+/)) {
    const clean = token.replace(/[^a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]/g, '');
    let rest = clean;
    while (rest.length) {
      const syl = _nextSyllable(rest);
      if (!syl) { rest = rest.slice(1); continue; }
      syllables.push(syl);
      rest = rest.slice(syl.length);
    }
  }
  return syllables;
}

function _buildCharacters(zh, pinyin) {
  const syllables = _splitPinyinSyllables(pinyin);
  let si = 0;
  return [...(zh || '')].map(c => _isCJK(c) ? { c, p: syllables[si++] || '' } : { c, p: '' });
}

// ── Ruby text renderer ─────────────────────────────────────────────────────

function renderZhPinyin(pg) {
  const chars = (pg.characters && pg.characters.length)
    ? pg.characters
    : _buildCharacters(pg.zh, pg.pinyin);

  const ruby = chars.map(({c, p}) =>
    p ? `<ruby>${escHtml(c)}<rt>${escHtml(p)}</rt></ruby>`
      : escHtml(c)
  ).join('');
  return `<p class="text-ruby">${ruby}</p>`;
}

function buildStorybookHTML(story, pages, imageB64, printMode = false) {
  const coverImg = imageB64[1]
    ? `<img src="${imageB64[1]}" alt="cover" class="cover-img">`
    : '';

  const pageSpread = pages.map(pg => {
    const img = imageB64[pg.page]
      ? `<img src="${imageB64[pg.page]}" alt="Page ${pg.page}" class="page-img">`
      : `<div class="page-img-placeholder">No image</div>`;
    return `
    <div class="page-spread">
      <div class="spread-left">${img}</div>
      <div class="spread-right">
        <div class="page-num">Page ${pg.page}</div>
        ${renderZhPinyin(pg)}
        <p class="text-en">${escHtml(pg.en)}</p>
      </div>
    </div>`;
  }).join('\n');

  const printScript = printMode ? `
<script>
  window.addEventListener('load', () => { setTimeout(() => window.print(), 400); });
<\/script>` : '';

  return `<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escHtml(story.book_title_en)}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #fff; color: #111; }
  .book { max-width: 900px; margin: 0 auto; }

  .cover {
    min-height: 100vh;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    background: #fff;
    padding: 3rem 2rem; text-align: center;
    border-bottom: 2px solid #000;
  }
  .cover-img { max-width: 480px; width: 100%; border-radius: 4px; margin-bottom: 2rem; }
  .cover-title-zh { font-size: 4rem; color: #000; letter-spacing: .1em;
    font-family: 'Noto Serif SC','SimSun',serif; }
  .cover-title-pinyin { font-size: 1.4rem; color: #555; margin: .5rem 0; }
  .cover-title-en { font-size: 1.9rem; color: #000; font-weight: 700; margin-top: .25rem; }

  .page-spread {
    display: grid; grid-template-columns: 1fr 1fr;
    min-height: 100vh; background: #fff;
    border-bottom: 1px solid #ccc;
  }
  .spread-left { display: flex; align-items: center; justify-content: center;
    background: #f4f4f4; border-right: 1px solid #ccc; }
  .page-img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .page-img-placeholder { width: 100%; height: 100%; min-height: 320px;
    display: flex; align-items: center; justify-content: center;
    background: repeating-linear-gradient(
      45deg, #f0f0f0 0px, #f0f0f0 10px, #e8e8e8 10px, #e8e8e8 20px);
    color: #bbb; font-size: 1rem; border: 2px dashed #ccc; }
  .spread-right { padding: 3rem 2.5rem;
    display: flex; flex-direction: column; justify-content: center; gap: 2rem; }
  .page-num { font-size: .8rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .1em; color: #999; }
  .text-ruby { font-size: 2.8rem; line-height: 3.2;
    font-family: 'Noto Serif SC','SimSun',serif; color: #000; }
  ruby { ruby-align: center; }
  rt { font-size: .38em; color: #555; font-family: 'Segoe UI', system-ui, sans-serif;
    font-weight: 400; letter-spacing: 0; }
  .text-en { font-size: 1.7rem; line-height: 1.6; color: #111;
    border-top: 1px solid #e0e0e0; padding-top: 1.25rem; }

  @media (max-width: 600px) {
    .page-spread { grid-template-columns: 1fr; }
    .cover-title-zh { font-size: 2.5rem; }
    .text-ruby { font-size: 2rem; }
    .text-en { font-size: 1.3rem; }
  }
  @page { size: A4 landscape; margin: 0; }
  @media print {
    *, *::before, *::after { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    body { background: #fff; }
    .book { max-width: 100%; }
    .cover, .page-spread {
      page-break-after: always; break-after: page;
      page-break-inside: avoid; break-inside: avoid;
    }
  }
</style>
${printScript}
</head>
<body>
<div class="book">
  <div class="cover">
    ${coverImg}
    <h1 class="cover-title-zh">${escHtml(story.book_title_zh)}</h1>
    <p class="cover-title-pinyin">${escHtml(story.book_title_pinyin)}</p>
    <p class="cover-title-en">${escHtml(story.book_title_en)}</p>
  </div>
  ${pageSpread}
</div>
</body>
</html>`;
}

async function openPrintWindow(project, apiBase) {
  const story    = project.story;
  const pages    = story.pages;
  const imageB64 = await fetchImagesAsBase64(project.generated_images || {}, apiBase);
  const html     = buildStorybookHTML(story, pages, imageB64, true);
  const win      = window.open('', '_blank');
  win.document.write(html);
  win.document.close();
}

function downloadStorybookHTML(project, apiBase) {
  return fetchImagesAsBase64(project.generated_images || {}, apiBase).then(imageB64 => {
    const story = project.story;
    const html  = buildStorybookHTML(story, story.pages, imageB64, false);
    const blob  = new Blob([html], { type: 'text/html' });
    const url   = URL.createObjectURL(blob);
    const a     = document.createElement('a');
    a.href      = url;
    a.download  = `${story.book_title_en.replace(/[^a-z0-9]+/gi, '_')}_storybook.html`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  });
}

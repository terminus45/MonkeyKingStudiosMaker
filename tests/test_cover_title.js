/* Node test for storybook_print.js renderRubyTitle (per-character ruby cover title).
 *
 * Exercises the three branches of renderRubyTitle(story, langCode):
 *   Branch 1 (language-neutral): story.book_title_characters present -> ruby for
 *            each annotated char, showReadingLine === false. Works for zh/ja/ko.
 *   Branch 2 (zh fallback): no book_title_characters but native + reading -> ruby
 *            built from the deterministic pinyin splitter, showReadingLine === false.
 *   Branch 3 (ja/ko fallback): no book_title_characters -> plain native <h1>,
 *            showReadingLine === true, NO <ruby>.
 * Plus: punctuation / empty-p entries render as plain text (no empty <rt>).
 *
 * Same vm-sandbox technique as tests/test_storybook_print_fallback.js — the source
 * file is browser-oriented (no exports), so we load it into a vm sandbox with light
 * browser stubs and a tail that exports the functions under test. No app code changed.
 *
 * Run:  node tests/test_cover_title.js
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = path.join(__dirname, '..', 'frontend', 'storybook_print.js');

function loadPrintModule() {
  const code = fs.readFileSync(SRC, 'utf8');
  const wrapped =
    code +
    '\n;module.exports = { renderRubyTitle, _buildCharacters, _splitPinyinSyllables, escHtml };\n';

  const sandbox = {
    module: { exports: {} },
    window: {},
    document: {},
    FileReader: function () {},
    console,
  };
  vm.createContext(sandbox);
  vm.runInContext(wrapped, sandbox, { filename: 'storybook_print.js' });
  return sandbox.module.exports;
}

// ── tiny test harness ───────────────────────────────────────────────────────
let passed = 0;
let failed = 0;
const failures = [];

function check(name, cond, detail) {
  if (cond) {
    passed++;
    console.log('  PASS  ' + name);
  } else {
    failed++;
    failures.push(name + (detail ? ' :: ' + detail : ''));
    console.log('  FAIL  ' + name + (detail ? ' :: ' + detail : ''));
  }
}

const P = loadPrintModule();

// Count <ruby> openers and <rt> openers in a chunk of html.
const rubyCount = h => (h.match(/<ruby>/g) || []).length;
const rtCount   = h => (h.match(/<rt>/g) || []).length;
// No empty rt elements ever emitted.
const noEmptyRt = h => !/<rt><\/rt>/.test(h);

console.log('storybook_print.js renderRubyTitle tests\n');

// ── Branch 1: language-neutral book_title_characters (zh) ───────────────────
{
  const story = {
    book_title_zh: '汉字',
    book_title_pinyin: 'hàn zì',
    book_title_characters: [{ c: '汉', p: 'hàn' }, { c: '字', p: 'zì' }],
  };
  const { titleHtml, showReadingLine } = P.renderRubyTitle(story, 'zh');
  check('B1 zh: titleHtml has <ruby>', titleHtml.includes('<ruby>'), titleHtml);
  check('B1 zh: ruby per annotated char (2)', rubyCount(titleHtml) === 2, titleHtml);
  check('B1 zh: <rt> readings present (2)', rtCount(titleHtml) === 2, titleHtml);
  check('B1 zh: hàn + zì rendered', titleHtml.includes('hàn') && titleHtml.includes('zì'), titleHtml);
  check('B1 zh: showReadingLine === false', showReadingLine === false, String(showReadingLine));
}

// ── Branch 1: language-neutral works for ja (uses book_title_characters, not splitter) ─
{
  const story = {
    book_title_ja: '猫の本',
    book_title_romaji: 'neko no hon',
    book_title_characters: [
      { c: '猫', p: 'ねこ' },
      { c: 'の', p: '' },
      { c: '本', p: 'ほん' },
    ],
  };
  const { titleHtml, showReadingLine } = P.renderRubyTitle(story, 'ja');
  check('B1 ja: titleHtml has <ruby>', titleHtml.includes('<ruby>'), titleHtml);
  // Two annotated chars (猫, 本); の has empty p -> plain text, no ruby.
  check('B1 ja: ruby only for annotated chars (2)', rubyCount(titleHtml) === 2, titleHtml);
  check('B1 ja: readings ねこ + ほん present',
        titleHtml.includes('ねこ') && titleHtml.includes('ほん'), titleHtml);
  check('B1 ja: empty-p char rendered plain (の present, no empty <rt>)',
        titleHtml.includes('の') && noEmptyRt(titleHtml), titleHtml);
  check('B1 ja: showReadingLine === false', showReadingLine === false, String(showReadingLine));
}

// ── Branch 1: language-neutral works for ko too ─────────────────────────────
{
  const story = {
    book_title_ko: '책',
    book_title_romanization: 'chaek',
    book_title_characters: [{ c: '책', p: 'chaek' }],
  };
  const { titleHtml, showReadingLine } = P.renderRubyTitle(story, 'ko');
  check('B1 ko: has <ruby> with reading', titleHtml.includes('<ruby>') && titleHtml.includes('chaek'), titleHtml);
  check('B1 ko: showReadingLine === false', showReadingLine === false, String(showReadingLine));
}

// ── Branch 1: empty book_title_characters array does NOT take branch 1 ───────
{
  // Empty array -> `.length` falsy -> must fall through to ja/ko branch 3.
  const story = {
    book_title_ja: 'ねこ',
    book_title_romaji: 'neko',
    book_title_characters: [],
  };
  const { titleHtml, showReadingLine } = P.renderRubyTitle(story, 'ja');
  check('B1 ja empty[]: falls through (NO <ruby>)', !titleHtml.includes('<ruby>'), titleHtml);
  check('B1 ja empty[]: showReadingLine === true', showReadingLine === true, String(showReadingLine));
}

// ── Branch 2: zh fallback via splitter (no book_title_characters) ───────────
{
  const story = {
    book_title_zh: '小猫的故事',
    book_title_pinyin: 'xiǎo māo de gù shi',
    // book_title_characters absent
  };
  const { titleHtml, showReadingLine } = P.renderRubyTitle(story, 'zh');
  check('B2 zh: built from splitter (has <ruby>)', titleHtml.includes('<ruby>'), titleHtml);
  // 5 CJK chars -> 5 ruby.
  check('B2 zh: ruby count == CJK chars (5)', rubyCount(titleHtml) === 5, titleHtml);
  check('B2 zh: first char 小 + syllable xiǎo present',
        titleHtml.includes('小') && titleHtml.includes('xiǎo'), titleHtml);
  check('B2 zh: showReadingLine === false', showReadingLine === false, String(showReadingLine));
}

// ── Branch 2: zh with punctuation -> punctuation gets no <rt> ────────────────
{
  const story = {
    book_title_zh: '猫，狗',
    book_title_pinyin: 'māo, gǒu',
  };
  const { titleHtml } = P.renderRubyTitle(story, 'zh');
  // 2 CJK chars get ruby; the ，comma is plain.
  check('B2 zh punct: ruby only for CJK (2)', rubyCount(titleHtml) === 2, titleHtml);
  check('B2 zh punct: comma rendered plain, no empty <rt>',
        titleHtml.includes('，') && noEmptyRt(titleHtml), titleHtml);
}

// ── Branch 3: ja fallback -> plain native <h1>, reading line shown ──────────
{
  const story = {
    book_title_ja: 'ねこのぼうけん',
    book_title_romaji: 'neko no bouken',
    // no book_title_characters
  };
  const { titleHtml, showReadingLine } = P.renderRubyTitle(story, 'ja');
  check('B3 ja: NO <ruby>', !titleHtml.includes('<ruby>'), titleHtml);
  check('B3 ja: native title present', titleHtml.includes('ねこのぼうけん'), titleHtml);
  check('B3 ja: <h1> wrapper present', titleHtml.includes('<h1'), titleHtml);
  check('B3 ja: showReadingLine === true', showReadingLine === true, String(showReadingLine));
}

// ── Branch 3: ko fallback -> plain native, reading line shown ───────────────
{
  const story = {
    book_title_ko: '고양이의 모험',
    book_title_romanization: 'goyangiui moheom',
  };
  const { titleHtml, showReadingLine } = P.renderRubyTitle(story, 'ko');
  check('B3 ko: NO <ruby>', !titleHtml.includes('<ruby>'), titleHtml);
  check('B3 ko: native title present', titleHtml.includes('고양이의 모험'), titleHtml);
  check('B3 ko: showReadingLine === true', showReadingLine === true, String(showReadingLine));
}

// ── Branch 1: HTML metacharacters in title chars are escaped ────────────────
{
  const story = {
    book_title_zh: 'x',
    book_title_pinyin: 'x',
    book_title_characters: [{ c: '<b>', p: '&"' }],
  };
  const { titleHtml } = P.renderRubyTitle(story, 'zh');
  check('B1 escape: metachars escaped (no raw <b>)',
        titleHtml.includes('&lt;b&gt;') && !titleHtml.includes('<b>'), titleHtml);
}

console.log('\n----------------------------------------');
console.log(`storybook_print.js renderRubyTitle: ${passed} passed, ${failed} failed`);
if (failed) {
  console.log('FAILURES:');
  failures.forEach(f => console.log('  - ' + f));
  process.exit(1);
}
process.exit(0);

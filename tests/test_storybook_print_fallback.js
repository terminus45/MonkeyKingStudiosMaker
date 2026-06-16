/* Node test for storybook_print.js renderRubyText fallback.
 *
 * Proves the stale-drop degradation path is safe: when book_builder.js drops
 * characters[] (null) because data-readings-stale="true", the print renderer
 * still produces sensible output.
 *
 *   - zh: null/empty characters -> ruby rebuilt from native + reading via the
 *         pinyin syllable splitter (_buildCharacters / _splitPinyinSyllables).
 *   - ja/ko: null characters -> plain native text, NO <ruby> markup.
 *
 * The source file (frontend/storybook_print.js) is browser-oriented (no exports,
 * references window/document/FileReader). The functions under test are pure, so
 * we load the source into a vm sandbox with light browser stubs and a tail that
 * exports the functions we need. No application code is modified.
 *
 * Run:  node tests/test_storybook_print_fallback.js
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = path.join(__dirname, '..', 'frontend', 'storybook_print.js');

function loadPrintModule() {
  const code = fs.readFileSync(SRC, 'utf8');
  // Append an explicit export of the pure functions we want to test.
  const wrapped =
    code +
    '\n;module.exports = { renderRubyText, _buildCharacters, _splitPinyinSyllables, escHtml };\n';

  const sandbox = {
    module: { exports: {} },
    // Light stubs so any incidental top-level reference would not throw.
    // (Top level only declares functions/consts; these are defensive.)
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

console.log('storybook_print.js fallback tests\n');

// ── zh: null characters -> ruby rebuilt from native+reading ─────────────────
{
  const pg = {
    zh: '小猫在睡觉。',
    pinyin: 'xiǎo māo zài shuì jiào.',
    characters: null,
  };
  const html = P.renderRubyText(pg, 'zh');
  check('zh/null: produces <ruby> markup', html.includes('<ruby>'), html);
  check('zh/null: contains an <rt> reading', html.includes('<rt>'), html);
  // each CJK char should appear; first syllable should be attached
  check('zh/null: first char + syllable present',
        html.includes('小') && html.includes('xiǎo'), html);
  // punctuation 。 should render without a reading (no rt right after it is hard
  // to assert positionally; assert it appears and total ruby count == CJK count)
  const rubyCount = (html.match(/<ruby>/g) || []).length;
  check('zh/null: ruby count == CJK char count (5)', rubyCount === 5,
        'rubyCount=' + rubyCount + ' html=' + html);
}

// ── zh: empty-array characters -> same fallback as null ─────────────────────
{
  const pg = { zh: '猫。', pinyin: 'māo.', characters: [] };
  const html = P.renderRubyText(pg, 'zh');
  check('zh/empty[]: falls back to splitter (has <ruby>)', html.includes('<ruby>'), html);
  check('zh/empty[]: 猫 gets reading māo',
        html.includes('māo'), html);
}

// ── zh: undefined characters (key absent) -> fallback ───────────────────────
{
  const pg = { zh: '好。', pinyin: 'hǎo.' };
  const html = P.renderRubyText(pg, 'zh');
  check('zh/undefined: falls back (has <ruby>)', html.includes('<ruby>'), html);
}

// ── ja: null characters -> plain native text, NO ruby ───────────────────────
{
  const pg = { ja: 'ねこがねる。', romaji: 'neko ga neru.', characters: null };
  const html = P.renderRubyText(pg, 'ja');
  check('ja/null: NO <ruby> markup', !html.includes('<ruby>'), html);
  check('ja/null: NO <rt> markup', !html.includes('<rt>'), html);
  check('ja/null: native text present', html.includes('ねこがねる'), html);
}

// ── ko: null characters -> plain native text, NO ruby ───────────────────────
{
  const pg = { ko: '고양이가 잔다.', romanization: 'goyangiga janda.', characters: null };
  const html = P.renderRubyText(pg, 'ko');
  check('ko/null: NO <ruby> markup', !html.includes('<ruby>'), html);
  check('ko/null: native text present', html.includes('고양이가'), html);
}

// ── ja/ko WITH characters present -> ruby IS rendered (control) ──────────────
{
  const pg = {
    ja: '猫', romaji: 'neko',
    characters: [{ c: '猫', p: 'ねこ' }],
  };
  const html = P.renderRubyText(pg, 'ja');
  check('ja/with-characters: ruby IS rendered', html.includes('<ruby>') && html.includes('ねこ'), html);
}

// ── splitter sanity ─────────────────────────────────────────────────────────
{
  const syl = P._splitPinyinSyllables('xiǎo māo zài');
  check('splitter: xiǎo māo zài -> 3 syllables',
        Array.isArray(syl) && syl.length === 3, JSON.stringify(syl));
}

// ── _buildCharacters maps CJK->syllable and punctuation->'' ─────────────────
{
  const chars = P._buildCharacters('小猫。', 'xiǎo māo.');
  check('_buildCharacters: 3 entries', chars.length === 3, JSON.stringify(chars));
  check('_buildCharacters: punctuation has empty reading',
        chars[2].c === '。' && chars[2].p === '', JSON.stringify(chars));
  check('_buildCharacters: first CJK gets a syllable',
        chars[0].p && chars[0].p.length > 0, JSON.stringify(chars));
}

// ── escaping: native text with HTML metacharacters is escaped (ja plain path) ─
{
  const pg = { ja: 'a<b>&"', romaji: '', characters: null };
  const html = P.renderRubyText(pg, 'ja');
  check('ja/null: HTML metachars escaped',
        html.includes('&lt;b&gt;') && html.includes('&amp;') && !html.includes('<b>'), html);
}

console.log('\n----------------------------------------');
console.log(`storybook_print.js fallback: ${passed} passed, ${failed} failed`);
if (failed) {
  console.log('FAILURES:');
  failures.forEach(f => console.log('  - ' + f));
  process.exit(1);
}
process.exit(0);

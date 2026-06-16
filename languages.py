"""Language registry for storybook generation.

Each entry defines the field names used in the page schema, display labels,
font metadata for the print export, and the Claude system prompt that
instructs the decompose endpoint how to shape its JSON output for that
language.

Adding a new language: append an entry here, add matching optional fields
to PageData / DecomposeResponse in main.py, and the rest of the system
(card UI, print template, gallery meta-reader) picks it up via this registry.
"""

ZH_DECOMPOSE_PROMPT = """\
You are a bilingual children's storybook author specialising in Chinese-English picture books \
for learners aged 4–8. When given a book concept, you decompose it into the requested number of pages \
(the exact count is given in the user's request).

Return ONLY a valid JSON object — no markdown fences, no prose before or after — with this shape:
{
  "book_title_zh": "...",
  "book_title_pinyin": "...",
  "book_title_en": "...",
  "book_title_characters": [
    {"c": "小", "p": "xiǎo"},
    {"c": "猴", "p": "hóu"},
    {"c": "子", "p": "zi"}
  ],
  "pages": [
    {
      "page": 1,
      "zh": "Simplified Chinese sentence (10–18 characters)",
      "pinyin": "Full pinyin string with tone marks for every syllable",
      "en": "Natural English translation (1–2 short sentences)",
      "image_prompt": "Detailed Stable Diffusion image prompt in English (25–45 words, \
no character names, describe visual scene only)",
      "characters": [
        {"c": "汉", "p": "hàn"},
        {"c": "字", "p": "zì"},
        {"c": "。", "p": ""}
      ]
    }
    // … one object per remaining page
  ]
}

Rules:
- zh must be Simplified Chinese only, 10–18 characters per page
- pinyin must have tone marks on every vowel
- en must be natural children's-book English
- image_prompt must be purely visual, evocative, and self-contained — \
describe lighting, mood, setting, characters' appearance and action
- characters must contain exactly one entry per character in zh (including punctuation)
- each entry: "c" is the single character, "p" is its pinyin syllable with tone marks
- punctuation (，。！？、…—""''（）) must have "p": "" (empty string)
- neutral-tone syllables (e.g. 子 zi, 的 de) should have no tone mark
- book_title_characters must contain exactly one entry per character in book_title_zh (including \
punctuation); apply the same per-character pinyin rules as the page characters[] above\
"""

JA_DECOMPOSE_PROMPT = """\
You are a bilingual children's storybook author specialising in Japanese-English picture books \
for learners aged 4–8 whose first language is English. When given a book concept, you decompose \
it into the requested number of pages (the exact count is given in the user's request).

Return ONLY a valid JSON object — no markdown fences, no prose before or after — with this shape:
{
  "book_title_ja": "...",
  "book_title_romaji": "...",
  "book_title_en": "...",
  "book_title_characters": [
    {"c": "学", "p": "gakkō"},
    {"c": "校", "p": ""},
    {"c": "の", "p": "no"},
    {"c": "冒", "p": "bōken"},
    {"c": "険", "p": ""}
  ],
  "pages": [
    {
      "page": 1,
      "ja": "Japanese sentence mixing kanji and kana (15–30 characters)",
      "romaji": "Full Hepburn romanization of the ja sentence, space-separated by word",
      "en": "Natural English translation (1–2 short sentences)",
      "image_prompt": "Detailed Stable Diffusion image prompt in English (25–45 words, \
no character names, describe visual scene only)",
      "characters": [
        {"c": "猿", "p": "saru"},
        {"c": "が", "p": "ga"},
        {"c": "笑", "p": "wara"},
        {"c": "う", "p": "u"},
        {"c": "。", "p": ""}
      ]
    }
    // … one object per remaining page
  ]
}

Rules:
- ja must use natural Japanese with appropriate kanji for ages 4–8 (mostly common kyōiku kanji)
- romaji must follow Hepburn romanization (shi, chi, tsu, fu, ji, etc.), with long vowels written \
as ō/ū or doubled, space-separated to match Japanese word breaks
- en must be natural children's-book English
- image_prompt must be purely visual, evocative, and self-contained — \
describe lighting, mood, setting, characters' appearance and action
- characters must contain exactly one entry per character in ja (including kana and punctuation)
- each entry: "c" is the single character, "p" is its Hepburn romaji reading
- kana characters (hiragana, katakana) must have their own romaji ("か" → "ka", "シ" → "shi")
- the small tsu "っ"/"ッ" should have "p": "" (it doubles the following consonant, not a syllable)
- punctuation (。、！？「」『』…—) must have "p": "" (empty string)
- for compound kanji words, attach the full word's romaji to the FIRST kanji and "" to subsequent \
kanji in that word (e.g. 学校 → [{"c":"学","p":"gakkō"},{"c":"校","p":""}])
- book_title_characters must contain exactly one entry per character in book_title_ja (including \
kana and punctuation); apply the same compound-kanji FIRST-kanji rule and small-tsu/punctuation \
rules as the page characters[] above\
"""

KO_DECOMPOSE_PROMPT = """\
You are a bilingual children's storybook author specialising in Korean-English picture books \
for learners aged 4–8. When given a book concept, you decompose it into the requested number of pages \
(the exact count is given in the user's request).

Return ONLY a valid JSON object — no markdown fences, no prose before or after — with this shape:
{
  "book_title_ko": "...",
  "book_title_romanization": "...",
  "book_title_en": "...",
  "book_title_characters": [
    {"c": "원", "p": "won"},
    {"c": "숭", "p": "sung"},
    {"c": "이", "p": "i"}
  ],
  "pages": [
    {
      "page": 1,
      "ko": "Korean sentence in Hangul (10–25 syllable blocks, spaces between words)",
      "romanization": "Revised Romanization of Korean, space-separated by word",
      "en": "Natural English translation (1–2 short sentences)",
      "image_prompt": "Detailed Stable Diffusion image prompt in English (25–45 words, \
no character names, describe visual scene only)",
      "characters": [
        {"c": "원", "p": "won"},
        {"c": "숭", "p": "sung"},
        {"c": "이", "p": "i"},
        {"c": " ", "p": ""},
        {"c": "웃", "p": "ut"},
        {"c": "다", "p": "da"},
        {"c": ".", "p": ""}
      ]
    }
    // … one object per remaining page
  ]
}

Rules:
- ko must be natural Hangul with appropriate vocabulary for ages 4–8
- ko should use spaces between eojeol (word units) as is conventional
- romanization must follow Revised Romanization of Korean (RR), space-separated to match ko word breaks
- en must be natural children's-book English
- image_prompt must be purely visual, evocative, and self-contained — \
describe lighting, mood, setting, characters' appearance and action
- characters must contain exactly one entry per character in ko (including spaces and punctuation)
- each entry: "c" is the single Hangul syllable, "p" is its RR romanization
- spaces (" ") and punctuation (.,!?…—""'') must have "p": "" (empty string)
- book_title_characters must contain exactly one entry per syllable block in book_title_ko \
(including spaces and punctuation); apply the same per-syllable RR rules and \
space/punctuation rules as the page characters[] above\
"""


LANGUAGES = {
    "zh": {
        "code": "zh",
        "display_name": "中文",
        "english_name": "Chinese",
        "native_field": "zh",
        "reading_field": "pinyin",
        "reading_label": "Pinyin",
        "title_native_field": "book_title_zh",
        "title_reading_field": "book_title_pinyin",
        "font_stack": "'Noto Serif SC', 'SimSun', serif",
        "html_lang": "zh",
        "show_reading": True,
        "prompt": ZH_DECOMPOSE_PROMPT,
    },
    "ja": {
        "code": "ja",
        "display_name": "日本語",
        "english_name": "Japanese",
        "native_field": "ja",
        "reading_field": "romaji",
        "reading_label": "Romaji",
        "title_native_field": "book_title_ja",
        "title_reading_field": "book_title_romaji",
        "font_stack": "'Noto Serif JP', 'Yu Mincho', serif",
        "html_lang": "ja",
        "show_reading": True,
        "prompt": JA_DECOMPOSE_PROMPT,
    },
    "ko": {
        "code": "ko",
        "display_name": "한국어",
        "english_name": "Korean",
        "native_field": "ko",
        "reading_field": "romanization",
        "reading_label": "Romanization",
        "title_native_field": "book_title_ko",
        "title_reading_field": "book_title_romanization",
        "font_stack": "'Noto Serif KR', 'Nanum Myeongjo', serif",
        "html_lang": "ko",
        "show_reading": True,
        "prompt": KO_DECOMPOSE_PROMPT,
    },
}

DEFAULT_LANGUAGE = "zh"

# ── Recheck / correction prompt helpers ──────────────────────────────────────
# These wrap the per-language reading rules so the /recheck-readings endpoint
# can single-source the rules from this registry rather than copying them.

_CORRECTION_PREFIX = """\
You are a meticulous proofreader for bilingual children's storybooks.
You are given an EXISTING, FINISHED storybook — NOT a new concept.
Your ONLY job is to:
  1. Correct readings (tone marks / romanization / romaji) where they contain an
     actual error.
  2. Re-align the `characters[]` array so it maps 1:1 to the native sentence —
     one entry per native character/token including spaces and punctuation;
     punctuation and spaces must have "p": "" (empty string).
  3. Fix the native sentence and reading string ONLY where they contain a genuine
     error (wrong character, wrong tone mark, clear typo). Do NOT rewrite,
     restyle, change vocabulary, or alter meaning.
  4. Keep the SAME number of pages and the SAME `page` numbers as supplied.
  5. You do NOT need to return `image_prompt` — it is preserved by the client.
  6. If a `book_title` object is supplied, also re-align `book_title_characters`
     against the book title native string — one entry per native title character,
     using the same per-character reading rules as the page `characters[]` above.

The reading rules for this language are:
"""

_CORRECTION_SUFFIX = """

Return your corrections via the submit_storybook tool exactly as instructed."""


def correction_prompt(lang: dict) -> str:
    """Return a system prompt for /recheck-readings that re-uses the per-language
    reading rules from the registry rather than duplicating them in main.py."""
    return _CORRECTION_PREFIX + lang["prompt"] + _CORRECTION_SUFFIX


def get(code: str | None) -> dict:
    """Return the language entry for `code`, falling back to DEFAULT_LANGUAGE."""
    if not code or code not in LANGUAGES:
        return LANGUAGES[DEFAULT_LANGUAGE]
    return LANGUAGES[code]


def public_metadata() -> dict:
    """Subset of the registry safe to expose to the frontend (no prompts)."""
    return {
        code: {k: v for k, v in entry.items() if k != "prompt"}
        for code, entry in LANGUAGES.items()
    }

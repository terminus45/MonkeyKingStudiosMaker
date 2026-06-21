# Security & Architecture Backlog

> Source: read-only architecture + cyber sweep run **2026-06-21** (architect-agent +
> cyber-architect, no code changes). The **trivial** items were fixed in the same pass;
> this doc captures everything **deferred for later revisiting**.
>
> Calibration: this is a self-hosted, currently single-user app. None of the deferred
> items are Critical/High *as a localhost tool*. Most graduate to High the moment the
> app is multi-user or network-exposed — which aligns with the planned Clerk/Supabase +
> Stripe phase. **That auth milestone is the natural forcing function for the High items.**

## ✅ Already fixed in the sweep (for the record)

- **S2** — `HOST` now defaults to `127.0.0.1` (loopback); set `HOST=0.0.0.0` to re-enable
  LAN/phone access. Wildcard CORS removed — now opt-in via `CORS_ALLOW_ORIGINS` (comma list).
  `config.py`, `main.py`, `start.sh`.
- **S8** — `Pillow>=10.4.0` and `reportlab>=4.2.0` pinned; `start.sh` now `chmod 600 .env`
  and loads it via `set -a; . ./.env; set +a` (handles spaces/special chars). `.env` perms
  tightened to `0600` on disk.
- **A5** — removed the permanent "Connected · unknown" label; all 5 pages show "Connected"
  (the `loaded_model` from `/health` was always null — dead SD remnant).
- **A6** — removed the unused `/status` endpoint + `_gen_status`/`_status_update` (zero
  frontend consumers; `/figure/status` and `/practice-sheet/status` are separate routes).

---

## 🔒 Security — deferred

### S1 — No authentication on cost-bearing endpoints (HIGH when exposed)
- **What:** every route is unauthenticated; `/decompose`, `/figure/generate`,
  `/practice-sheet`, `/generate*` spend real Claude/Gemini/Meshy credits.
  `main.py` `/decompose`, `/figure/generate`, `/practice-sheet`, `/generate`.
- **Effort:** Medium (1–2 days). **Impact:** anyone who reaches the port drains billing +
  reads/deletes all gallery content.
- **Plan:** this is the **auth phase** (Clerk/Supabase per the roadmap memo). Interim
  cheap option: a shared-secret header middleware + per-IP rate limit on the 4 paid routes.
- **Depends on / unblocks:** S3, S4 (gate the same endpoints once auth exists).

### S3 — Unbounded in-memory job stores + uncapped worker threads (MEDIUM)
- **What:** `_figure_jobs` (`main.py:~840`) and `_practice_jobs` (`main.py:~1321`) never
  evict; each `/figure/generate` and `/practice-sheet` spawns an unbounded daemon thread.
- **Effort:** Small (hours). **Impact:** memory/thread exhaustion can hang the single
  process (which also serves the frontend).
- **Plan:** TTL/size-capped store (OrderedDict + timestamp sweep on create) **+** a worker
  semaphore / max-in-flight queue. Pairs naturally with **A1** below (same data structures).

### S4 — Gallery content served + enumerated unauthenticated (MEDIUM)
- **What:** `/gallery`, `/gallery/images`, `/gallery/models`, `/image/{file}`,
  `/figure/model/{file}` list and serve all stored content. Random 32-hex filenames don't
  help because the list endpoints enumerate them.
- **Effort:** Small (once auth exists). **Impact:** all child-adjacent storybooks /
  portraits / 3D models readable by any caller (privacy-sensitive).
- **Plan:** gate behind S1 auth.

### S5 — Verbose error detail leaked to clients (MEDIUM)
- **What:** raw exception strings / Claude output / upstream API bodies returned to caller.
  `/generate` `detail=str(e)`; `/decompose` & `/recheck-readings` echo unparsed model
  output + JSON-decode errors; `meshy_generator.py` RuntimeErrors propagate verbatim.
- **Effort:** Small. **Impact:** recon aid (internal paths, upstream structure). No key leak.
- **Plan:** generic client message; log details server-side.

### S6 — Prompt injection weakens child-safety guardrail (LOW)
- **What:** user `concept`/`character`/`style`/figure prompt/recheck text interpolated
  directly into LLM system/user messages; can override `SAFETY_STYLE_SUFFIX`.
  `main.py` `/decompose`, `_enhance_figure_prompt`, recheck path.
- **Effort:** Small. **Impact:** defeat content guardrail; **no host RCE** — the
  practice-sheet code-execution path runs in Anthropic's sandbox (correct boundary).
- **Plan:** harden guardrail phrasing / structurally separate user text from instructions.

### S7 — `download_model` follows redirects with no host allow-list (LOW)
- **What:** `meshy_generator.py:~214` fetches the Meshy-returned GLB/thumbnail URL with
  `follow_redirects=True`, no host allow-list. URL is Meshy-supplied (not direct user
  input), so SSRF-shaped, not classic SSRF.
- **Effort:** Small. **Impact:** server-side fetch to attacker host only if Meshy/DNS
  subverted. **Plan:** restrict to expected Meshy/CDN hosts or drop cross-host redirects.

### Info — No HTTPS / no security headers
- Plain HTTP; `/settings/keys` POSTs keys in cleartext; no HSTS / X-Content-Type-Options /
  X-Frame-Options / CSP. Fine on localhost. **Plan (only if exposed):** TLS reverse proxy +
  security-headers middleware.

### Follow-up not completed in the sweep
- **Run `pip-audit -r requirements.txt`** against the live venv (no network in the sweep;
  no JS lockfile — three.js is a CDN import map, optionally pin with SRI hashes).

---

## 🏗 Architecture — deferred

### A1 — Job stores never evicted + lost on restart; practice-sheet has no soft resume (MEDIUM)
- **What:** same dicts as S3. Figure Maker has a client soft-fallback
  (`resumeJobIfAny`, 35-min cap); practice-sheet resume just 404s after a restart.
- **Effort:** Small. **Plan:** do together with **S3** (cap + TTL); add a practice-sheet
  "check the Gallery / regenerate" soft fallback mirroring Figure Maker.

### A2 — Generated files never cleaned up (MEDIUM)
- **What:** PNGs/GLBs/PDFs in `output/**` accumulate forever; manifest deletes are
  intentionally manifest-only (files may be shared). Practice PDFs one-per-job.
- **Effort:** Small–Medium. **Plan:** retention policy / orphan sweep that respects the
  shared-file semantics (only delete a file when no manifest references it).

### A3 — Language registry duplicated 4× (MEDIUM)
- **What:** `languages.py` `LANGUAGES` (source of truth), `book_builder.js` `LANG_META`,
  `storybook_print.js` `PRINT_LANG`, and `settings.html` `#settingsLang` options. Adding a
  language = 5 coordinated edits. `GET /languages` (`public_metadata()`) already exists but
  no frontend consumes it.
- **Effort:** Medium. **Plan:** have the JS pages fetch `/languages` once and cache; retire
  the hand-copied `LANG_META`/`PRINT_LANG`. Watch: `PRINT_LANG` carries `font_stack` that
  `LANG_META` lacks — ensure `public_metadata()` exposes everything both need.

### A4 — Pinyin syllable splitter duplicated JS ↔ Python, no shared test (MEDIUM)
- **What:** `storybook_print.js` `_splitPinyinSyllables`/`_buildCharacters` re-ported in
  `practice_sheet_local.py` `_split_pinyin_syllables`/`_derive_characters`. Must produce
  identical output for the legacy-book fallback to render consistently across print export
  and local practice sheet.
- **Effort:** Small (golden-vector test) → Medium (consolidate). **Plan:** add a shared
  golden-vector fixture first to lock behavior, then consider consolidation.

### A7 — "Identical" shared-inputs HTML has drifted (LOW)
- **What:** `figure_maker.html` adds `maxlength="500"` on `#sharedCharacterInput`; the other
  two pages don't. Documented invariant ("literally identical") is broken; harmless today
  (sync works; Figure Maker just caps length).
- **Effort:** Trivial — **but needs a product decision:** add `maxlength` to all three
  (caps Book Builder / CG character input too) **or** remove it from Figure Maker (loses the
  Meshy-prompt cap). Deferred pending that call.

### A8 — Dead compat fields on `GenerateRequest`/`GenerateResponse` (LOW)
- **What:** `negative_prompt`, `provider`, `return_base64`, `loaded_model` are removed-feature
  remnants (`main.py` request/response models). `width`/`height` are semi-live (feed
  `_fit_aspect_ratio` only when `aspect_ratio` is unset). After A5, `loaded_model` in the
  response is fully unread by the frontend.
- **Effort:** Trivial. **Risk:** kept "for stale-client compat" — removing re-introduces the
  risk a mobile client still sends/reads them. **Plan:** confirm no client sends these, then
  drop; keep `width`/`height` until `aspect_ratio` is guaranteed everywhere.

### A9 — Figure-maker status poll is unbounded async self-recursion (LOW)
- **What:** `figure_maker.js:~310` `pollStatus` awaits a 2.5s sleep then
  `await pollStatus(jobId)`. Correct (each `await` unwinds the stack) but fragile; relies on
  `_currentJobId`/`_cancelled` guards for cancellation. **Effort:** Trivial. **Plan:** convert
  to a flat `while` loop. No current bug — purely a robustness cleanup.

---

## Suggested ordering when revisited

1. **Auth phase (S1)** — unblocks S3/S4 gating; the strategic milestone.
2. **Resource caps (S3 + A1)** — same data structures; do as one change.
3. **Hygiene (S5 error sanitization, A2 file retention)** — independent, low-risk.
4. **De-duplication (A3 language registry, A4 pinyin golden test)** — maintainability.
5. **Cleanups (A7 decision, A8, A9, S6, S7)** — opportunistic, batch when touching those files.

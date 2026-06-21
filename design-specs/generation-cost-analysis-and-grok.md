# Generation Cost Analysis + Grok Image Model Evaluation

> Produced **2026-06-21** by `financials-agent` (per-action cost + Imagen/Grok comparison)
> and `architect-agent` (feasibility of adding Grok as a selectable image model), orchestrated
> by `product-manager`. Analysis only — no code changed.
>
> **All dollar figures are estimates from live provider pricing fetched 2026-06-21 plus
> assumed token counts** (decompose/recheck/practice-sheet are output-token-bound and were
> not measured against real invoices). Treat ranges as ranges. Sources listed at the end.

## 1. Per-action generation cost (every button, every tab)

| Tab | Button | Provider / model | Billed calls / click | Est. cost / action |
|---|---|---|---|---|
| Book Builder | Build storybook (decompose) | Claude Opus 4.8, cached prompt | 1 | **$0.07–$0.18** |
| Book Builder | Generate image (per page) | Imagen 4 Fast (default, selectable) | 1 | **$0.02** |
| Book Builder | Check Readings | Claude Opus 4.8, cached prompt | 1 | **$0.06–$0.20** |
| Book Builder | Create Practice Sheet (cloud) | Claude Opus 4.8 + code-execution tool | ~2–6 turns + container | **$0.15–$0.55** |
| Book Builder | Generate Practice Locally | ReportLab in-process | 0 | **~$0.00** |
| Character Generator | Generate portrait | Imagen 4 Fast (default, selectable) | 1 | **$0.02** |
| Character Generator | Build figure from image | Meshy image-to-3D + Haiku report | 1 Meshy + 1 Haiku | **$0.40–$0.60** |
| Figure Maker | Build my figure | Haiku rewrite + Meshy preview + Meshy refine + Haiku report | 2 Meshy + 2 Haiku | **$0.42–$0.62** |

### Cost to build one full book
Profile: 1 decompose + 11 page images (Imagen Fast) + 1 recheck.

| Component | Calc | Cost |
|---|---|---|
| Decompose | 1 × ($0.07–$0.18) | $0.07–$0.18 |
| 11 page images | 11 × $0.02 | $0.22 |
| Recheck | 1 × ($0.06–$0.20) | $0.06–$0.20 |
| **Total / book** | | **$0.35–$0.60** (≈$0.45 typical) |

A "power session" that also makes a cloud practice sheet (+$0.15–$0.55) and a 3D figure
(+$0.42–$0.62) reaches **~$1.00–$1.75**. **The single 3D figure ≈ the entire book.**

### Code facts behind the numbers (file:line)
- Decompose — `claude-opus-4-8`, `max_tokens=16384`, forced tool, system prompt cached
  (`cache_control: ephemeral`) — `main.py:389`. Cached block ≈ per-language prompt ~2–3k tok.
- Recheck — `claude-opus-4-8`, `max_tokens=16384`, cached — `main.py:503`. `image_prompt`
  stripped client-side.
- Image — default `imagen-4.0-fast-generate-001`, user-selectable — `gemini_generator.py:22,56`.
- Figure (text) — Haiku rewrite `max_tokens=512` (`main.py:903`) → Meshy preview
  (`should_remesh=True`, `target_polycount=200000`, `meshy_generator.py:71`) → Meshy refine
  (`meshy_generator.py:105`) → Haiku report `max_tokens=256` (`main.py:942`). **4 billed calls.**
- Figure (image) — Meshy image-to-3D `ai_model="latest"`, `should_texture=True`,
  `target_polycount=200000` (`meshy_generator.py:156`) + Haiku report.
- Practice cloud — `claude-opus-4-8`, `max_tokens=8000`, code-execution server tool, ≤6
  turns / 150s — `practice_sheet.py:28,90`. Container time free ≤1,550 hrs/mo/org.
- Practice local — no API, in-process ReportLab — `practice_sheet_local.py`. COGS ≈ $0.

### Key assumptions (the conclusion hinges on these)
1. Decompose/recheck output ~2.5k–7k tok. 2× higher → ~$0.12–$0.40/call; book → ~$0.70.
2. Meshy ~20–30 credits/full figure @ $0.02/credit. 2× → figure $0.80–$1.20 (**most fragile
   number** — verify against a real Meshy invoice; lowering `TARGET_POLYCOUNT` de-risks it).
3. Container hours modeled as $0 under the free allowance.

## 2. Image-generation cost: Imagen vs Grok

| Model | Per image | Per 11-image book | Notes |
|---|---|---|---|
| **Imagen 4 Fast** (current default) | **$0.02** | **$0.22** | Cheapest. ~2.7s/img, SynthID watermark. `gemini_generator.py:56`. |
| Imagen 4 Standard | $0.04 | $0.44 | Better detail; selectable. |
| Imagen 4 Ultra | $0.06 | $0.66 | Native 2K; selectable. |
| Gemini 2.5 Flash Image | ~$0.04 | ~$0.44 | Token-priced; selectable. |
| **Grok grok-2-image** | **$0.07** | **$0.77** | xAI premium — **3.5× Imagen Fast**, most expensive. |
| Grok base (grok-imagine-image) | $0.02 | $0.22 | Only *ties* Imagen Fast — no cost advantage. |

**Conclusion: there is no cost case for Grok.** `grok-2-image` is 3.5× pricier than the current
default; Grok's cheapest tier merely matches Imagen Fast. The only justification to add Grok is
**quality/style differentiation**, which was not evaluated here. Recommendation: **keep Imagen
Fast as default**; treat Standard/Ultra (and any future Grok tier) as premium-credit upsells.

## 3. Architect review — adding Grok as a selectable image model

**Feasibility: Go with changes.** **Approval status: Needs revision** — two design decisions
must be settled in this spec before `developer-agent` starts (see Open Decisions). The seam is
favorable: the dormant `provider` field (`main.py:74`) was kept for exactly this, the model
registry already has a `type` discriminator (`gemini_generator.py:21`), and the model id flows
from one localStorage draft to both call sites.

### Recommended shape
- **New `grok_generator.py`** — stateless `generate(...) -> PIL.Image` matching the Gemini
  signature, **lazy `import httpx`** at call time (mirrors `meshy_generator.py`; xAI's image API
  is OpenAI-compatible at `https://api.x.ai/v1/images/generations`, so no new SDK), its own
  `GROK_MODELS = [{id, name, type}]` list with per-image cost in the label, and its own error
  mapping. Decode the URL/b64 response to a `PIL.Image` to satisfy the existing provider-agnostic
  `save_image` (`gemini_generator.py:12`).
- **Do NOT** branch inside `gemini_generator.generate()` — it is Gemini-typed and its error
  handling is built around `google.genai.errors`. Folding xAI in would couple two SDKs and two
  error taxonomies behind one lazy import.
- **One dispatch helper in `main.py`**, used by BOTH `/generate` (`:116`) and `/generate/stream`
  (`:155`), resolving provider by **registry membership of the model id** (combined Gemini+Grok
  `{id→provider}` map), with default-to-Gemini fallback for unknown ids (back-compat for old
  drafts). The two call sites currently duplicate the generation block — factor dispatch into one
  helper so they can't drift (R2).

### Required changes (end to end)
1. `grok_generator.py` (new) — as above.
2. Dispatch helper in `main.py`, shared by both image call sites.
3. `GenerateRequest` (`main.py:70`) — add `xai_key: Optional[str] = None`; keep `provider` as a
   *hint*, not authority.
4. Keys — `KEY_NAMES += "XAI_API_KEY"` (`settings_store.py:15`) auto-wires `get_key`/`set_keys`/
   `status`/Settings persistence; add `XAI_API_KEY` to `config.py` and `.env.example`.
5. Aspect ratio — Grok path explicitly ignores `gemini_aspect_ratio`; UI disables/hides the
   aspect selector for Grok models (see Open Decision #1).
6. Settings UI (`settings.html`/`settings.js:202`) — add xAI key input + status row; merge Grok
   models into the dropdown, preserving the cost-suffix convention.
7. Missing-key behavior — add a pre-flight **503** for the Grok path (image path currently
   surfaces missing-key as a **500** via `gemini_generator.py:38`; decide whether to retrofit
   Gemini for parity). Apply at both call sites.
8. Model list endpoint — extend `/gemini/models` (or add `/image/models`) to return Grok entries;
   keep `/gemini/models` working for stale clients if renamed.
9. Docs — update CLAUDE.md (API-key precedence list, image data-flow, the "always 'gemini'"
   comment on `provider`).
10. Gallery `model` field — no code change (free-text record); confirm the Reuse round-trip
    writes a Grok id back into `draft.model`.

### Risks
- **R1 (Medium) — Aspect-ratio divergence.** Imagen honors 5 ratios; Grok returns a fixed shape.
  A silent no-op selector would produce inconsistent page shapes within one book
  (`book_builder.js:390` always sends the ratio). Needs an explicit UX decision.
- **R2 (Medium) — Two call-site drift.** `/generate` and `/generate/stream` duplicate the
  generation block — centralize dispatch.
- **R3 (Low) — Settings HTML + docs** need the new key field + enumeration update.
- **R4 (Low) — Single-dropdown UX** mixing providers; honor the per-image cost-label convention.

### Backward-compat (safe)
Saved drafts keep `gemini_model` (routes to Gemini via fallback); gallery `model` is free-text;
`GenerateResponse` and the SSE done-event shape `{done, filename, seed, loaded_model}` are
provider-agnostic and unchanged.

### Open decisions (block implementation)
1. **Aspect-ratio UX for Grok** — hide/disable the selector when a Grok model is chosen, or
   document it as ignored. Must not be silent, given multi-page book consistency.
2. **Provider disambiguation** — recommended: dispatch on registry membership of the model id
   and treat the client `provider` field as a hint only (robust against stale clients sending
   `provider:'gemini'` with a Grok id). Confirm vs reviving `provider` as authoritative.

## 4. Opportunities & risks (financial)

**Cost savings (ranked):** steer Chinese users to the local practice sheet (saves $0.15–$0.55/sheet);
lower hardcoded `TARGET_POLYCOUNT=200000` / make texture optional (`meshy_generator.py:15`, ~30–50%
off figure credits); cap decompose/recheck `max_tokens` from 16384 → ~8000; keep Imagen Fast as
default (½ the cost of Standard/Flash); verify prompt-cache hit rate within the 5-min TTL.

**Profit levers:** promote the 3D figure as the premium upsell (highest-ticket action); package
cheap page-image top-ups (≈60% margin); offer Imagen Ultra/Gemini Flash as premium-credit tiers.

**Financial risks (ranked):** unauthenticated, uncapped paid endpoints on a shared key (unbounded
$/day — cross-ref `security-architecture-backlog.md` S1/S3); single-key blast radius; thin 3D-figure
margin (~22% worst case) exposed to Meshy price changes; sold-but-unredeemed credits are a liability,
not profit.

## Sources (fetched 2026-06-21)
- Claude pricing — https://platform.claude.com/docs/en/about-claude/pricing ·
  https://www.finout.io/blog/claude-opus-4.8-pricing-2026-everything-you-need-to-know
- Imagen 4 tiers — https://theplanettools.ai/blog/google-imagen-4-models-fast-standard-ultra-guide-2026 ·
  https://www.buildmvpfast.com/api-costs/ai-image
- Grok image — https://mem0.ai/blog/xai-grok-api-pricing · https://wavespeed.ai/models/x-ai/grok-2-image
- Meshy — https://www.meshy.ai/pricing · https://help.meshy.ai/en/articles/10000507-how-many-credits-does-each-generation-task-cost
</content>

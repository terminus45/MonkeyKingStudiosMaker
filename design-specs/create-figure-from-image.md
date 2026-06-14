# Design Spec: Create Figure from Image

**Feature:** "Create Figure" button on the Character Generator page — starts a Meshy image-to-3D job from the current portrait, writes the job to localStorage, and navigates to Figure Maker where the existing resume flow takes over.

**Branch context:** `feature/figure-maker-settings-gallery-split`

---

## 1. Code audit findings (design dependencies)

### 1.1 `resumeJobIfAny()` already drives the full progress UI on load

`resumeJobIfAny()` (figure_maker.js, lines 552–578) does the following when it finds a valid stored job:

1. Sets `_cancelled = false` and `_currentJobId = stored.job_id`.
2. Calls `setGenerating(true)` — disables the Generate button and shows the spinner.
3. Calls `setInputsDisabled(true)`.
4. Calls `showProgress()` — hides the empty state and viewer, shows the progress bar.
5. Calls `setProgress(0)` and `setBoltMessage('prompting')`.
6. Hides the reset button, enhanced-prompt box, and report card.
7. Immediately fires `pollStatus(stored.job_id, true)`.

The first `pollStatus` call reads the live stage and progress from the server and updates the UI within one tick (~35 ms round-trip). The user arriving from Character Generator will therefore see the progress bar and stage label within roughly one server round-trip — no blank/empty state flash, and no code change to Figure Maker is needed for the happy path.

### 1.2 `_currentJobId` single-flight guard prevents races

`_currentJobId` is module-level. When `resumeJobIfAny()` sets it, any concurrent poll loop from a previous Generate press is immediately invalidated (the guard at the top of `pollStatus`: `if (_cancelled || jobId !== _currentJobId) return`). A CG-originated job written to localStorage before navigation and consumed by `resumeJobIfAny()` therefore cannot race with a user subsequently pressing "Build my figure!" — the Generate handler sets `_currentJobId = null` first (line 205), then assigns the new job id, stomping the resumed one. This is the correct behaviour: the user deliberately started a new text-based job.

### 1.3 `FM_JOB_KEY` shape

```
localStorage['monkeyking_fm_job'] = JSON.stringify({ job_id: string, started_at: number })
```

`started_at` must be `Date.now()` at the moment the CG writes the key, not the server timestamp, because `resumeJobIfAny()` computes age client-side.

### 1.4 SharedInputs is NOT involved in the image-to-3D hand-off

`POST /figure/generate-from-image` receives `filename` (not a text prompt), so the shared-input fields (Character / Story / Style) play no role in triggering the job. The character description (`cgDescInput.value`) is passed only to populate the print report — it is not required for the Meshy task itself. No SharedInputs write is needed or desirable: the fields already contain the correct values from when the portrait was generated.

### 1.5 Stage vocabulary — image-to-3D mapping

The existing text-to-3D flow uses a two-stage Meshy pipeline (`preview` → `refine`). Image-to-3D uses a single Meshy task. The backend worker will need to map that single task's progress onto the existing stage keys. Recommended mapping (no new keys required):

| Backend worker phase | Use existing stage key | Kid-facing label (already in `STAGE_LABELS`) |
|---|---|---|
| Starting Meshy task | `prompting` | "Dreaming up your idea…" |
| Meshy task in progress (0–100 %) | `preview` | "Sculpting the shape…" |
| Downloading GLB | `downloading` | "Almost ready…" |
| Generating print report | `analyzing` | "Checking the details…" |
| Complete | `done` | (handled by `enterReadyState`) |

Rationale: `preview` ("Sculpting the shape") is the most honest description of what Meshy does with a photo — it builds a mesh from the image. The `refine` key is intentionally skipped, which is fine; the frontend never asserts a strict ordering of stages. The bolt message for `preview` ("Sculpting your shape — almost like magic!") is also well-suited. No new entries are needed in `BOLT_MESSAGES` or `STAGE_LABELS`.

---

## 2. Button — placement, label, styling, states

### 2.1 Placement in `.cg-action-row`

The action row currently contains two buttons in source order:

1. `#cgDownloadBtn` — anchor styled as `.settings-btn`, label "↓ Download"
2. `#cgUseAsCoverBtn` — button styled as `.settings-btn`, label "📖 Use as Book Cover"

The new "Create Figure" button is inserted as the **third item**, after `#cgUseAsCoverBtn`.

Visual result: a horizontal row of three ghost-style buttons — Download · Use as Book Cover · Create Figure — left-aligned, wrapping to a second line on narrow viewports (`.cg-action-row` already has `flex-wrap: wrap` and `gap: .5rem`).

### 2.2 Label and icon

```
🧩 Create Figure
```

The 🧩 icon is already used in the Figure Maker nav link and the "Build my figure!" generate button. Consistent with the navigation icon — no new icon family introduced.

### 2.3 Styling recommendation — use a highlighted variant of `.settings-btn`

The Download and Use as Book Cover buttons perform low-stakes, reversible actions. Create Figure triggers an irreversible multi-minute job and a page navigation. It warrants modest visual distinction without introducing a new component class.

Recommended treatment: add a modifier class `.settings-btn--accent` in `style.css` (or `character_generator.css` if scoped):

```
background: rgba(255, 107, 53, .15);
border-color: rgba(255, 107, 53, .45);
color: rgba(255, 107, 53, .90);
```

On hover:
```
background: rgba(255, 107, 53, .28);
border-color: rgba(255, 107, 53, .75);
color: #ff6b35;
```

This reuses the existing `--mustard` / `--teal` token (`#ff6b35`) already used for focus rings, active nav, and the primary generate button — no new colour is introduced. The button remains visually subordinate to the full-width `generate-btn` above it. The sibling buttons keep their neutral `.settings-btn` styling so the hierarchy is Download (neutral) · Cover (neutral) · Create Figure (warm accent).

Flag: `style.css` currently has `.settings-btn--muted` (terracotta danger tint). The new `.settings-btn--accent` follows the same pattern. The developer-agent should add it to `style.css`, not `character_generator.css`, because it will be useful if future pages need a positive-accent secondary button.

### 2.4 HTML skeleton

```html
<button
  class="settings-btn settings-btn--accent"
  id="cgCreateFigureBtn"
  aria-label="Turn this portrait into a 3D figure in Figure Maker"
  disabled
>
  <span id="cgCreateFigureLabel">🧩 Create Figure</span>
  <div class="spinner hidden" id="cgCreateFigureSpinner" aria-hidden="true"></div>
</button>
```

Notes:
- `disabled` is the default because `cgActionRow` is hidden until an image is ready; by the time the row is revealed, the button will have been enabled by `showImage()`. However, the disabled default ensures it is never accidentally interactive before `showImage()` runs.
- The spinner reuses the `.spinner` class from `style.css` (18 px, white border-top, `spin` keyframe). Because `.settings-btn` has `min-height: 36px`, the 18 px spinner fits without layout shift.
- `aria-label` provides destination context that the button text alone does not ("in Figure Maker").

### 2.5 States

| State | Visual |
|---|---|
| Default (image ready) | Warm-accent ghost button, enabled. |
| Hover | Border and text intensify to full `#ff6b35`. |
| Focus-visible | `outline: 2px solid #ff6b35; outline-offset: 2px` — matches `.cg-strip-thumb:focus-visible`. |
| In-flight (request sent, no response yet) | Label span hidden, spinner visible, button `disabled`, `aria-disabled="true"`. Text is "🧩 Create Figure" → spinner. No text change to "Starting…" is needed because the spinner is self-explanatory and adding live text creates two competing `aria-live` regions. The existing `#cgErrorMsg` region will announce any error. |
| Error | Button re-enabled, spinner hidden, error displayed in `#cgErrorMsg` (see section 3). |
| Success | Never re-enabled on this page — navigation fires immediately. |

---

## 3. Click flow and state machine

### 3.1 Precondition check

At click time, check `currentFilename` (the module-level variable, also mirrored in `cgUseAsCoverBtn.dataset.filename`). If null, do nothing — the button should not be reachable in this state because `cgActionRow` is hidden when no image exists.

### 3.2 In-flight sequence

```
1. hideError()
2. cgCreateFigureBtn.disabled = true
3. cgCreateFigureBtn.setAttribute('aria-disabled', 'true')
4. cgCreateFigureLabel.classList.add('hidden')
5. cgCreateFigureSpinner.classList.remove('hidden')

6. POST /figure/generate-from-image
   body: {
     filename: currentFilename,
     prompt:   cgDescInput.value.trim()   // for print report only
   }

7a. On success (200, { job_id }):
    localStorage['monkeyking_fm_job'] = JSON.stringify({ job_id, started_at: Date.now() })
    window.location.href = 'figure_maker.html'
    (button stays disabled — page is navigating away)

7b. On error: → section 3.3
```

### 3.3 Error handling

Re-enable the button (reverse step 2–5), then call `showError(message)` on `#cgErrorMsg` — exactly the same function already used for generation errors. The `#cgErrorMsg` element has `role="alert"` and `aria-live="assertive"`, so screen readers announce it without additional work.

Error message strings:

| Condition | User-facing message |
|---|---|
| HTTP 503 | "Meshy key not set — ask a grown-up to add it in Settings (⚙)." |
| HTTP 404 (filename not found) | "Couldn't find that portrait on the server. Try regenerating your character." |
| Network failure | "Network error — check your connection and try again." |
| Any other HTTP error | The `detail` field from the JSON response, or "Something went wrong (error N)." |

The 503 message pattern directly matches Figure Maker's existing 503 handler (figure_maker.js line 233) and is consistent in tone.

### 3.4 Navigation timing

`window.location.href = 'figure_maker.html'` fires synchronously after writing localStorage. No `setTimeout` or `await` is needed — the localStorage write is synchronous and the navigation is immediate. The Figure Maker page's `init()` IIFE calls `resumeJobIfAny()` after `wireSharedInputListeners()`, so the key will be present when it is read.

---

## 4. Hand-off — exact localStorage interaction

### 4.1 What Character Generator writes

```js
// Written by character_generator.js, cgCreateFigureBtn click handler, on 200 response:
localStorage.setItem('monkeyking_fm_job', JSON.stringify({
  job_id:     data.job_id,   // string, e.g. "abc123"
  started_at: Date.now()     // Unix ms timestamp
}));
```

This is byte-for-byte identical to the shape `saveFmJob()` writes in figure_maker.js (lines 168–172). The CG does not call `saveFmJob()` directly (it is not available cross-page) — it writes the same shape manually. The developer-agent should consider extracting `FM_JOB_KEY` and the shape into a shared constant comment so it stays in sync; a full shared module is unnecessary.

### 4.2 What Figure Maker reads

`resumeJobIfAny()` calls `readFmJob()` which reads `localStorage['monkeyking_fm_job']` and parses it. It checks:
- `stored.job_id` is truthy.
- `stored.started_at` is present and `(Date.now() - stored.started_at) <= FM_JOB_MAX_AGE_MS` (35 min).

A job started from CG will never fail the staleness check — the navigation takes under one second.

### 4.3 No conflict with Figure Maker's own Generate button

If the user lands on Figure Maker from CG and then presses "Build my figure!", the Generate handler (figure_maker.js line 194) sets `_currentJobId = null` (line 205) before assigning the new job id (line 241). This invalidates any poll loop started by `resumeJobIfAny()`. The user sees the new text-based job replace the image-based one — correct behaviour. The old CG job is still running server-side but the frontend has abandoned it; the backend will auto-save to the gallery on completion regardless, so no user data is lost.

---

## 5. Figure Maker arrival UX

### 5.1 What the user sees on load (no code change to Figure Maker needed)

On arrival from CG, `resumeJobIfAny()` fires and immediately transitions the UI to the progress state. The sequence is:

1. Empty state hidden.
2. Progress bar shown at 0%.
3. Stage label: "Dreaming up your idea…" (`prompting` key).
4. Generate button disabled, spinner visible.
5. First `pollStatus` call goes out.
6. Within ~1 poll cycle (2.5 s max), the stage and progress update to the actual server state.

There is no intermediate empty/idle flash because `resumeJobIfAny()` runs inside the `init` IIFE synchronously after `wireSharedInputListeners()`, before the first paint is committed to screen by the browser. The transition to `showProgress()` happens before the user sees anything.

### 5.2 One minor UX gap — no context about how the job started

When the user arrives from CG, the Character Description textarea on Figure Maker will be pre-populated with whatever is in `SharedInputs` (the character description from CG is already synced there). This is correct and free. However, the enhanced-prompt box (`#fmEnhancedPromptBox`) only appears when `pollStatus` receives `enhanced_prompt` in the response — for an image-to-3D job there may be no Claude-enhanced prompt. The backend should omit `enhanced_prompt` from the status response for image-to-3D jobs, and the existing `if (enhanced_prompt && ...)` guard in `pollStatus` handles this gracefully (no box shown). No change needed.

### 5.3 Confirm: no change to figure_maker.js or figure_maker.html required

`resumeJobIfAny()` already handles this flow completely. The spec requires zero changes to the Figure Maker frontend.

---

## 6. Stage labels for the image-to-3D flow

Reuse existing keys with no new additions. The kid-facing experience:

| What Meshy is doing | Stage key | Progress bar label | Bolt mascot message |
|---|---|---|---|
| Job submitted, starting | `prompting` | "Dreaming up your idea…" | "Ooh, great idea! I'm thinking up the perfect design…" |
| Photo-to-mesh in progress | `preview` | "Sculpting the shape…" | "Sculpting your shape — almost like magic!" |
| GLB downloading | `downloading` | "Almost ready…" | "Packing it up and bringing it over…" |
| Print report generating | `analyzing` | "Checking the details…" | "Checking if it's ready to print…" |
| Complete | `done` | (viewer shown) | "Ta-da! Here's your very own 3D figure! 🎉" |

Rationale: "Sculpting the shape" is accurate regardless of whether the input was text or a photo — Meshy is building a 3D mesh either way. "Dreaming up your idea" during `prompting` is slightly less accurate (there is no Claude prompt-enhancement step for image-to-3D), but the stage is brief and the kid-facing label is warm and acceptable. The `refine` stage is simply absent, which the frontend handles with no code change.

The backend worker for `generate-from-image` should emit the same `stage`/`progress` fields as the text-based worker. No new stage vocabulary is needed, and no changes to `BOLT_MESSAGES` or `STAGE_LABELS` in figure_maker.js are needed.

---

## 7. Edge cases

### 7.1 User navigates back to Character Generator mid-job

The back button returns to CG. The Figure Maker job is still running server-side and still persisted in `localStorage['monkeyking_fm_job']`. The CG page has no awareness of an in-flight figure job — it shows normally. If the user presses "Create Figure" again on a different portrait, the new `job_id` overwrites the old one in localStorage. When the user next visits Figure Maker, it resumes the newer job. The older job completes silently server-side and is auto-saved to the gallery.

No special UI is required on the CG side to surface this. The button should not be disabled between CG visits.

### 7.2 User presses "Create Figure" a second time on the same portrait

The second click fires a second `POST /figure/generate-from-image`. This creates a second job server-side (distinct `job_id`). The second job's id overwrites the first in localStorage. On navigation, Figure Maker resumes the second job. The first job completes server-side and auto-saves. This is acceptable — no guard is needed.

### 7.3 Stale job (older than 35 minutes)

If the user generates a portrait, does not click "Create Figure", leaves the browser open overnight, and then clicks "Create Figure" the next morning: the job is started fresh, `started_at` is `Date.now()`, and the staleness check passes. The 35-minute cap only applies to jobs that are already in localStorage before the CG writes a new one.

### 7.4 Server forgot the job (restart after navigation)

`pollStatus` is called with `isResume = true` by `resumeJobIfAny()`. On a 404 or 400 response, `enterMissingJobState()` fires — it shows the soft fallback error: "We couldn't find your figure in progress — it may already be finished. Check the Gallery! 🖼". This is the existing behaviour for text-based resumed jobs and requires no change. The gallery may contain the completed model if the server had finished before restarting.

### 7.5 No Meshy API key set (503 from backend)

The backend returns HTTP 503. The CG shows the specific error message: "Meshy key not set — ask a grown-up to add it in Settings (⚙)." The gear icon in the top-left of the CG header links to `settings.html`. No additional UI is needed.

### 7.6 Portrait file not found on server (404)

Possible if the server's `output/` directory was cleared after generation. The CG shows: "Couldn't find that portrait on the server. Try regenerating your character."

---

## 8. Accessibility and kid-friendliness

### 8.1 Button accessibility

- `aria-label="Turn this portrait into a 3D figure in Figure Maker"` gives screen-reader users full context without depending on icon or adjacent text.
- In the loading state, add `aria-disabled="true"` in addition to `disabled` for redundancy (matches the pattern used by `cgGenerateBtn`, line 122 in character_generator.js).
- The spinner has `aria-hidden="true"` — it is decorative; the button's `disabled` state is the functional signal.
- Focus ring: `outline: 2px solid #ff6b35; outline-offset: 2px` — consistent with `.cg-strip-thumb:focus-visible`.

### 8.2 Error announcement

`#cgErrorMsg` already has `role="alert"` and `aria-live="assertive"`. No additional ARIA work needed for errors.

### 8.3 Kid-friendliness

- The button label "Create Figure" is concrete and action-oriented. Children understand "figure" from the Figure Maker nav link (🧩 Figure Maker) and the "Build my figure!" generate button.
- The 503 error message uses "ask a grown-up" — consistent with Figure Maker's existing 503 message (figure_maker.js line 233: "ask a grown-up to set it in Settings").
- Error messages are short, specific, and avoid technical jargon.

### 8.4 Touch target

`.settings-btn` has `min-height: 36px`. The Create Figure button will match. This meets the WCAG 2.5.8 minimum (24 × 24 px) and the iOS HIG recommendation (44 px) with the flex-row padding context. If the developer-agent wants to meet 44 px strictly, adding `min-height: 44px` only to `#cgCreateFigureBtn` is acceptable.

### 8.5 Colour contrast

The `.settings-btn--accent` accent colour is `rgba(255, 107, 53, .90)` text on `rgba(255, 107, 53, .15)` background (dark panel background `#0f1129` underneath). The effective contrast between `#ff6b35` text and the near-black composite background exceeds 4.5:1 — WCAG AA for normal text. The developer-agent should verify with a contrast tool if the exact alpha compositing is in question; falling back to solid `#ff6b35` text on `#0f1129` background (no tint on the button background) is always safe.

---

## 9. Files that will change

### Frontend (developer-agent owns these)

| File | Change |
|---|---|
| `frontend/character_generator.html` | Add `#cgCreateFigureBtn` to `#cgActionRow`, after `#cgUseAsCoverBtn`. |
| `frontend/character_generator.js` | Add DOM ref for `#cgCreateFigureBtn` and `#cgCreateFigureSpinner`. Add click handler: validate → in-flight state → POST → write localStorage → navigate. Add `showImage()` update to enable the button. |
| `frontend/style.css` | Add `.settings-btn--accent` modifier (warm-orange ghost variant). |

### Backend (architect-agent validates, developer-agent implements)

| File | Change |
|---|---|
| `main.py` | Add `POST /figure/generate-from-image` endpoint. Accept `{ filename, prompt? }`. Validate filename exists in `OUTPUT_DIR`. Start a new background worker that calls the image-to-3D Meshy flow. Return `{ job_id }`. |
| `meshy_generator.py` | Add image-to-3D Meshy API call (single task, not preview→refine). Accept an image URL or base64. Map task progress to the existing stage vocabulary (`prompting` → `preview` → `downloading` → `analyzing` → `done`). |

### No change required

| File | Reason |
|---|---|
| `frontend/figure_maker.js` | `resumeJobIfAny()` already handles the hand-off completely. No new stage keys needed. |
| `frontend/figure_maker.html` | No markup changes. |
| `frontend/figure_maker.css` | No style changes. |
| `frontend/shared_inputs.js` | SharedInputs plays no role in this flow. |
| `frontend/character_generator.css` | `.cg-action-row` already handles `flex-wrap` and `gap`. `.settings-btn--accent` goes in `style.css`. |

---

## 10. Design flag — inconsistency to call out

The existing `.settings-btn` in `style.css` (line 334) does not have a `gap` property, yet it uses `display: inline-flex` and `align-items: center`. The spinner and label inside `#cgCreateFigureBtn` need a gap between them. The developer-agent should add `gap: .45rem` to the button's internal flex container — either inline on the element or by adding `gap: .45rem` to `.settings-btn` globally (which is safe since the only content in other `.settings-btn` elements is text, and adding gap to an element with a single text node has no visual effect).

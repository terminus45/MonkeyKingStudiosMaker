# Clark's Rocket Studio — Web App

A summary of the design and functionality of the front-end application (`apps/web`).

## What it is

A kid-friendly 3D model generator. Clark (age 6) types what he wants to build in plain English; the app turns that into a high-quality generation prompt, asks Meshy.AI to create a 3D model, analyzes it for print quality, and shows it in an interactive 3D viewer. The same React codebase powers both a desktop/server web app and a Capacitor-wrapped iOS app.

## Tech stack

- **React 18 + Vite + TypeScript**
- **Tailwind CSS** (utility classes only — no inline styles or CSS modules)
- **react-three-fiber** + **drei** + **three.js** for the 3D viewer and (in standalone mode) STL geometry analysis
- **react-dropzone** for STL file uploads
- **@capacitor/core** + **@capacitor/filesystem** for the iOS app (native HTTP and on-device storage)
- State via **React Context + useReducer** — no Redux/Zustand, no React Router

## Two runtime modes

The single most important design fact: the web app runs in one of two modes, selected at **build time** by the `VITE_STANDALONE` env flag. This is why several services exist in duplicate.

| | **Server mode** (default) | **Standalone mode** (`VITE_STANDALONE=true`, the iOS app) |
|---|---|---|
| Who calls Claude / Meshy | Node backend (`apps/server`) via `/api/*` | The browser directly (`src/services/{claude,meshy,generation}.ts`) |
| API keys | server `.env` / `config.json` | device `localStorage` |
| STL analysis | server Python trimesh | Three.js (`src/services/stlAnalysis.ts`) |
| Saved models | server filesystem | Capacitor Filesystem gallery (`src/services/modelStore.ts`) |
| Progress reporting | `GenerationProgress` polls `/api/generate/:id/status` | `generation.ts` dispatches progress directly; no polling |

Components branch on `const STANDALONE = import.meta.env.VITE_STANDALONE === 'true'`. In bundled **server** mode, `main.tsx` installs a `fetch` interceptor that prepends `VITE_API_URL` to relative `/api/*` and `/generated/*` requests so loaders and uploads reach the backend.

## State management

Two context providers wrap the app (`App.tsx` → `DebugProvider` → `AppProvider` → `HomeView`):

**`AppContext`** — the primary view state machine (`src/context/AppContext.tsx`).
- Views: `idle → generating → ready`.
- Key actions:
  - `SUBMIT_PROMPT` → `generating`, stores the prompt, clears prior model.
  - `GEN_STARTED` (server) → sets `currentJobId`, which starts polling.
  - `GEN_ENHANCED` (standalone) → sets the AI-enhanced prompt **without** a `jobId`, so polling is skipped.
  - `GEN_PROGRESS` → updates the progress bar + stage label.
  - `MODEL_READY` → `ready`, stores the model + analysis.
  - `GEN_ERROR` → back to `idle`, resets job/progress/stage, shows an error mascot message.
  - `RETEXTURE_STARTED`, `LOCAL_STL_READY`, `RESET`.

**`DebugContext`** — an in-browser event log (last 200 entries). `useDebug().log()` records every fetch and pipeline step; it's threaded through `generation.ts` and `ModelViewer` so on-device failures are diagnosable. Surfaced by the collapsible `DebugPanel`.

## View hierarchy & components

All views render conditionally on `state.view` inside `HomeView`:

```
HomeView
  ├── header: 📚 GalleryView (saved models) + ⚙️ SettingsView (API keys / printer)
  ├── MascotZone          — "Bolt" the robot mascot + contextual speech bubble
  ├── PromptInput         — text field + quick-pick chips (idle state)
  ├── GenerationProgress  — progress bar + stage label (generating state)
  ├── ModelViewer         — interactive 3D viewer (ready state)
  ├── RefineInput         — retexture controls (ready state)
  ├── IdeaPanel           — model title + suggested filament tag (ready state)
  ├── STLReviewPanel      — print-readiness analysis (ready state)
  ├── StlUploadButton     — upload an existing STL to analyze
  └── DebugPanel          — collapsible event log (dev aid; not shown to Clark)
```

## Core user flows

### 1. Generate a model
1. Clark types a prompt or taps a quick-pick chip in `PromptInput`.
2. Claude (`MESHY_PROMPT`) rewrites it into a strong Meshy prompt. **Rules**: the enhanced prompt always *begins with Clark's own words* (spelling-cleaned, then expanded) and always *ends with a size constraint* ("under 6 inches / 152 mm tall, compact and chunky proportions") so prints stay small.
3. Meshy runs a two-stage async job: **preview** (untextured mesh) → **refine** (textured GLB + STL).
4. The result is analyzed (Three.js geometry or trimesh) and interpreted by Claude (`STL_ANALYSIS`) into a kid/parent-friendly print report.
5. `GenerationProgress` shows live progress through stages: `prompting → preview → refine → downloading → analyzing → done`.

### 2. Refine / retexture
`RefineInput` changes the model's **look** — color, material, surface style — not its shape. It calls Meshy's v1 text-to-texture API: the geometry (STL + analysis) is reused, only the GLB is regenerated. Quick-pick chips: red, wooden, shiny gold, galaxy swirl. Each retexture becomes a new saved entry so different texturings can be compared.

### 3. Upload an existing STL
`StlUploadButton` accepts a dropped/selected STL and runs it through the same analysis + print-report path without generating anything.

### 4. Saved-model gallery (standalone)
Every generation and retexture is **auto-saved** to on-device storage (Capacitor Filesystem). The 📚 gallery lists saved models newest-first; tapping one reopens it in the viewer with its print report. Models remain retexturable after reopening.

### 5. Settings
The ⚙️ screen manages API keys (and, in server mode, printer config). Standalone stores keys in `localStorage`; server mode persists them to `config.json` and applies them without a restart. Secrets are masked with show/hide toggles.

## The 3D model viewer (`ModelViewer.tsx`)

- Renders the textured **GLB** via `GLTFLoader` (preferred) or **STL** via `STLLoader` inside a react-three-fiber `<Canvas>`.
- `<Bounds fit clip observe margin={1.2}>` frames the **whole model with padding** by default (no manual camera position, so it auto-fits on resize and model swap).
- `OrbitControls` with auto-rotate: rotation stops when the user interacts and **resumes 10 seconds after the last interaction** (idle timer cleared on unmount and on model swap).
- Responsive sizing: `h-[60svh]` (min 360 / max 560px) on mobile, `lg:h-[600px] xl:h-[680px]` on desktop; on desktop the "ready" layout gives the viewer the larger column (`lg:grid-cols-[7fr_4fr]`).
- A `ViewerErrorBoundary` catches loader failures and shows the error + URL inline instead of crashing, and logs to the debug panel.

## Standalone services layer (`src/services/`)

- **`claude.ts`** — direct Anthropic calls from the browser (`anthropic-dangerous-direct-browser-access`), key from `localStorage`. JSON parsing tolerates markdown/narration.
- **`meshy.ts`** — direct Meshy calls; each `fetch` is wrapped with an operation tag (e.g. `[meshy.getTask] …`) for traceable errors.
- **`generation.ts`** — orchestrates the full pipeline and dispatches progress. Enforces **one run at a time** via a module-level `AbortController` (`cancelGeneration()` is fired from `GenerationProgress` unmount, i.e. on `RESET`), with cancellation checks at every stage so a cancelled run can't fire `MODEL_READY` after the user navigated away.
- **`stlAnalysis.ts`** — Three.js geometry analysis (face count, bounding box, support heuristics) replacing Python trimesh.
- **`modelStore.ts`** — the gallery: saves GLB + STL bytes + a JSON index to Capacitor Filesystem; load/list/delete.

## Mobile / iOS specifics (Capacitor)

- The app is served under `https://localhost` (`iosScheme: 'https'`) — needed because custom `capacitor://` origins have stricter cross-origin rules.
- **CORS workaround**: Meshy's CDN doesn't send CORS headers for the WebView origin, so model files are downloaded via `CapacitorHttp` (native, no CORS) and wrapped in same-origin `blob:` URLs for the viewer. CapacitorHttp returns binary as a **base64 string**, which is decoded to bytes before becoming a Blob.
- Retexture needs the original public Meshy CDN URL (`CurrentModel.sourceGlbUrl`), distinct from the local `blob:` `glbUrl` used only for display, because Meshy fetches the source server-side.
- iOS safe areas handled via `viewport-fit=cover` + `env(safe-area-inset-*)`.

## Design system

- **Colors**: dark navy background `#0a0b1a` (`bg-navy-800` surfaces), orange accent `#ff6b35`, white text.
- **Type**: Nunito for UI, Space Mono for labels/codes.
- **UX principles**: Clark sees colors and simple choices only — material/nozzle logic is hidden and auto-routed. Touch targets are ≥44pt for the mobile app. The mascot "Bolt" narrates each workflow moment in friendly, short messages.

## Shared types

`apps/web/src/types.ts` is kept in sync with `apps/server/src/types.ts` (no shared package). Web-only additions: `CurrentModel` (incl. `sourceGlbUrl`), `ApiResponse<T>`, `JobRecord`, `TrimeshAnalysis`, `ModelFormat`.

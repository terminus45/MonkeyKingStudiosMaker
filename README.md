# 齐天大圣 · MonkeyKing BookBuilder Bot

An AI-powered tool for creating bilingual Chinese–English children's storybooks with locally-generated illustrations. Write a story concept, let Claude decompose it into a fully structured book, generate illustrations with Stable Diffusion, and export a print-ready PDF — all from a single web interface running entirely on your own machine.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Features

- **AI Story Authoring** — Describe a story concept; Claude (claude-opus-4-7) decomposes it into 10 pages with Simplified Chinese text, pinyin (per-character, tone-marked), and natural English translations
- **Character-level Pinyin Alignment** — Ruby text renders each pinyin syllable directly above its Chinese character, perfect for early readers
- **Local Image Generation** — Stable Diffusion (SD 1.5 and SDXL) generates illustrations for each page with real-time step-progress bars
- **LoRA Support** — Drop `.safetensors` LoRA files into `models/LORAs/` to apply custom styles (ink art, watercolor, cinematic, etc.)
- **Multi-model Switching** — Load any `.safetensors`, `.ckpt`, or HuggingFace hub model at runtime from the UI
- **Book Builder** — Edit text, swap image prompts, regenerate individual pages, and track overall progress
- **CSV / Table Import** — Paste a spreadsheet table (tab or comma-separated) to import existing page content without calling the API
- **Project Save / Load** — Save the full project (text + image references) to a `.monkeyking.json` file and reload it later to skip regeneration
- **Gallery** — Browse previously saved storybooks, reopen them in the editor, or generate print PDFs directly from the gallery
- **Print-ready PDF Export** — A4 landscape layout with the illustration on the left page and bilingual text on the right, ink-optimised (black and white, no colored backgrounds)
- **localStorage Persistence** — Book Builder state survives page navigation automatically; Clear button to start fresh

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI · Uvicorn |
| Image generation | 🤗 Diffusers · PyTorch · PEFT (LoRA) |
| AI authoring | Anthropic Claude API (claude-opus-4-7) |
| Frontend | Vanilla HTML / CSS / JS — no build step |
| Storage | Local filesystem (JSON + PNG) |

---

## Project Structure

```
BookBuilderBot/
├── main.py              # FastAPI app — API routes + serves frontend
├── generator.py         # Stable Diffusion pipeline wrapper
├── config.py            # Environment-based configuration
├── requirements.txt
├── start.sh             # One-command launch
├── stopServer.sh        # Graceful shutdown
├── .env.example         # Environment variable template
├── frontend/
│   ├── index.html       # Image Studio (single-image generator)
│   ├── book_builder.html
│   ├── gallery.html
│   ├── style.css        # Shared design tokens + layout
│   ├── book_builder.css
│   ├── gallery.css
│   ├── app.js           # Image Studio logic
│   ├── book_builder.js  # Book Builder logic
│   ├── gallery.js       # Gallery logic
│   └── storybook_print.js  # Shared PDF/HTML export + pinyin splitter
├── models/              # Place model files here
│   └── LORAs/           # Place LoRA files here
├── output/              # Generated images (git-ignored)
└── gallery/             # Saved book JSON files (git-ignored)
```

---

## Setup

### 1. Clone

```bash
git clone https://github.com/terminus45/MonkeyKingBookBuilder.git
cd MonkeyKingBookBuilder
```

### 2. Python environment

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...   # Required for story generation
DEVICE=cpu                      # or: mps (Apple Silicon), cuda (NVIDIA)
MODEL_ID=runwayml/stable-diffusion-v1-5
MODEL_CACHE_DIR=./models
OUTPUT_DIR=./output
```

### 4. Add a model

Place a `.safetensors` or `.ckpt` file in `models/`, or let the default SD 1.5 model download automatically on first run.

```
models/
├── my_model.safetensors
└── LORAs/
    └── my_lora.safetensors
```

### 5. Start

```bash
./start.sh
```

Open **http://localhost:8000** in your browser.

---

## Usage

### Image Studio
A single-image playground. Enter a scene prompt, pick a style preset or write your own, select a model and optional LoRA, and generate. Watch step-by-step progress inline. Images are saved to `output/` and shown in a session history strip.

### Book Builder

1. **Concept** — Type a story idea (e.g. *"Sun Wukong learns to share with the forest animals"*) and click **Create Story with Claude**. Claude writes 10 pages with Chinese, pinyin, English, and image prompts.
2. **Edit** — Review and edit any field on the page cards before generating.
3. **Generate** — Choose your model, canvas size, LoRA, and click **Generate All Images**. Per-page and aggregate progress bars update in real time. Use **Stop** to pause.
4. **Export** — Export as a self-contained HTML file or open the print dialog for a PDF. Export is available at any time — pages without images show a placeholder.

### CSV Import
Instead of using Claude, paste a tab- or comma-separated table with columns `Page`, `Pinyin`, `汉字`, `English`, `Illustration Prompt` into the import panel.

### Gallery
Saved books appear in the Gallery with their cover image, title, and image count. From there you can reopen a book in the editor, generate a PDF, or delete it.

---

## Supported Models

| Type | Format | Notes |
|---|---|---|
| SD 1.5 | `.safetensors`, `.ckpt` | Files < 4 GB |
| SDXL | `.safetensors` | Files ≥ 4 GB, auto-detected |
| HuggingFace hub | Directory (`models--org--name`) | Downloaded via `diffusers` |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Server status and loaded model |
| GET | `/models` | List available models |
| POST | `/load` | Load a model by ID or number |
| GET | `/loras` | List available LoRAs |
| POST | `/generate/stream` | SSE image generation with step progress |
| POST | `/decompose` | Claude story decomposition |
| GET | `/image/{filename}` | Serve a generated image |
| GET | `/gallery` | List saved storybooks |
| POST | `/gallery` | Save a storybook |
| GET | `/gallery/{id}` | Load a saved storybook |
| DELETE | `/gallery/{id}` | Delete a saved storybook |

---

## Requirements

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/) for story generation
- A machine with enough RAM to run Stable Diffusion (8 GB+ recommended; Apple Silicon MPS supported)

---

## License

MIT

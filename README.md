# 齐天大圣 · MonkeyKing Studios

An AI-powered tool for creating multilingual children's storybooks. Write a story concept, let Claude decompose it into a structured 10-page book, generate illustrations with Google Imagen/Gemini, create 3D printable figures with Meshy, and export a print-ready PDF — all from a single web interface.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Features

- **AI Story Authoring** — Describe a story concept; Claude (claude-opus-4-7) decomposes it into 10 pages with native language text, romanization, and English translations
- **Multi-Language Support** — Chinese (Simplified + Pinyin), Japanese (+ Romaji), Korean (+ Romanization)
- **Cloud Image Generation** — Google Imagen 4 and Gemini 2.5 Flash generate illustrations for each page via the Gemini API
- **Character Generator** — Create character portraits with Gemini; auto-saved to the gallery
- **Figure Maker** — Kid-friendly Meshy.AI text-to-3D pipeline: Claude rewrites your prompt, Meshy generates the GLB, export STL for 3D printing
- **Book Builder** — Edit text, swap image prompts, regenerate individual pages, choose aspect ratio (1:1, 4:3, 16:9…), and track overall progress
- **Gallery** — Tabbed view for saved images, books, and 3D models; reopen or print from the gallery
- **Settings** — Manage API keys (Anthropic / Gemini / Meshy) and default Gemini model from the in-app Settings page — no restart required
- **CSV / Table Import** — Paste a spreadsheet table to import existing page content
- **Project Save / Load** — Save the full project (text + image references) to a `.monkeyking.json` file
- **Print-ready PDF Export** — A4 landscape layout with illustration on the left, bilingual text on the right

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI · Uvicorn |
| Image generation | Google Gemini API (Imagen 4 / Gemini 2.5 Flash) |
| 3D figure generation | Meshy.AI REST API |
| AI authoring | Anthropic Claude API (claude-opus-4-7) |
| Frontend | Vanilla HTML / CSS / JS — no build step |
| Storage | Local filesystem (JSON + PNG + GLB) |

---

## Project Structure

```
BookBuilderBot/
├── main.py                   # FastAPI app — API routes + serves frontend
├── gemini_generator.py       # Gemini/Imagen image generation
├── meshy_generator.py        # Meshy.AI 3D figure generation
├── config.py                 # Environment-based configuration
├── settings_store.py         # Server-side API key store (config.json)
├── languages.py              # Multi-language registry
├── requirements.txt
├── start.sh                  # One-command launch
├── stopServer.sh             # Graceful shutdown
├── .env.example              # Environment variable template
├── frontend/
│   ├── book_builder.html/js  # Full storybook workflow
│   ├── character_generator.html/js  # Character portrait generator
│   ├── figure_maker.html/js  # 3D figure generator
│   ├── gallery.html/js       # Tabbed gallery
│   ├── settings.html/js      # API key management
│   ├── shared_inputs.js      # Cross-tab shared inputs (Character/Style/Story)
│   ├── style.css             # Shared design tokens + layout
│   └── storybook_print.js    # PDF/HTML export
├── output/                   # Generated images (git-ignored)
├── output/figures/           # Generated GLB models (git-ignored)
└── gallery/                  # Saved book JSON + manifests (git-ignored)
```

---

## Setup

### 1. Clone

```bash
git clone https://github.com/terminus45/MonkeyKingStudiosMaker.git
cd MonkeyKingStudiosMaker
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
ANTHROPIC_API_KEY=sk-ant-...       # Required for story decomposition and Figure Maker
GEMINI_API_KEY=AIza...             # Required for image generation (Imagen / Gemini)
MESHY_API_KEY=msy_...              # Required for Figure Maker 3D generation
OUTPUT_DIR=./output
```

You can also set API keys at runtime from the **Settings** page (gear icon, top-left) — no restart required.

### 4. Start

```bash
./start.sh
```

Open **http://localhost:8000** in your browser.

---

## Usage

### Book Builder

1. **Concept** — Type a story idea and character description, choose a language, and click **Generate Story with Claude**. Claude writes 10 pages with native language text, romanization, English, and image prompts.
2. **Edit** — Review and edit any field on the page cards before generating.
3. **Generate** — Choose your page shape (aspect ratio) and click **Generate All Images**. Gemini/Imagen generates each page illustration. Use **Stop** to pause.
4. **Export** — Export as a self-contained HTML file or open the print dialog for a PDF.

The Gemini model used for generation is set in **Settings** → Generation Settings.

### Character Generator

Generate a character portrait for your story using Google Imagen. The portrait auto-saves to the gallery and can be turned into a 3D figure via **"Make 3D Figure"**.

### Figure Maker

Describe a figure in plain language; Claude enhances the prompt and Meshy.AI renders a textured 3D model. Download as GLB or export to STL for 3D printing (client-side conversion via three.js STLExporter).

### Gallery

Three tabs: **Images** (character portraits), **Books** (saved storybooks), **3D Models** (Meshy figures). Each has reopen/print/delete actions.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Server status |
| GET | `/status` | Current generation status |
| GET | `/gemini/models` | List available Gemini models |
| POST | `/generate` | Generate an image (Gemini) |
| POST | `/generate/stream` | SSE image generation with progress |
| POST | `/decompose` | Claude story decomposition |
| GET | `/image/{filename}` | Serve a generated image |
| GET | `/gallery` | List saved storybooks |
| POST | `/gallery` | Save a storybook |
| GET | `/gallery/{id}` | Load a saved storybook |
| DELETE | `/gallery/{id}` | Delete a saved storybook |
| GET | `/gallery/images` | List saved character images |
| POST | `/gallery/image` | Register a new image |
| GET | `/gallery/models` | List saved 3D models |
| POST | `/figure/generate` | Start a 3D figure generation job |
| GET | `/figure/status/{job_id}` | Poll figure job status |
| GET | `/figure/model/{filename}` | Serve a generated GLB |
| GET | `/settings/keys` | Get masked API key status |
| POST | `/settings/keys` | Update API keys |

---

## Requirements

- Python 3.10+
- [Anthropic API key](https://console.anthropic.com/) — story decomposition, Figure Maker prompt enhancement
- [Google Gemini API key](https://aistudio.google.com/) — image generation (Imagen 4 / Gemini 2.5 Flash)
- [Meshy API key](https://www.meshy.ai/) — 3D figure generation (optional)

---

## License

MIT

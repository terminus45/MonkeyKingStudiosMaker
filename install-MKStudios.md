# Installing Monkey King Studios

A guide to get **Monkey King Studios** running on your own machine. It's written so you can either follow it by hand or **hand the whole file to Claude Code** and say *"install this app by following install-MKStudios.md"* — the steps are explicit and ordered, with verification checks and fixes for the common failure points.

The app is a single-process **FastAPI server** that serves both the REST API and the static web UI. All generation is through cloud APIs (Google Gemini/Imagen for images, Meshy.AI for 3D, Anthropic Claude for story text). **There is no local AI model, no GPU requirement, and no large download** — installation is fast and light.

---

## 🤖 For Claude Code (read this first)

If you are an AI agent installing this app, follow the **Steps** below in order. Rules:

1. Run each command from the **repository root** (the folder containing `main.py` and `start.sh`).
2. After each step, run its **Verify** check before moving on. If a check fails, see **Troubleshooting** — do not continue past a failed step.
3. **Do not** install `torch`, `diffusers`, `transformers`, or any ML/GPU packages — they were removed from this project. `requirements.txt` is the complete and only dependency list.
4. The server **starts fine with no API keys**. Do not block installation on keys; set them last (Step 5) or tell the user they can add them later in the in-app **Settings** page.
5. `start.sh` runs in the foreground with `--reload` (it does not return). To verify the server in an automated/non-interactive context, start it in the background, poll `GET /health`, then stop it — see Step 6.
6. Never commit or print the contents of `.env` or `config.json` (they hold secrets).

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.10+** | Check with `python3 --version`. |
| **git** | To clone the repo. |
| **Repo access** | The repository is private — you need a GitHub account with access (`gh auth login`, or an SSH key / personal access token). |
| **~200 MB disk** | For the Python virtual environment and dependencies. No model files. |

No Node.js, no GPU, no CUDA, no Xcode.

---

## Steps

### 1. Clone the repository

```bash
git clone https://github.com/terminus45/MonkeyKingStudiosMaker.git
cd MonkeyKingStudiosMaker
```

**Verify:** `ls main.py start.sh requirements.txt` lists all three files.

> If the clone fails with an auth error, the repo is private — authenticate first with `gh auth login` (GitHub CLI) or configure an SSH key, then retry.

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate          # Windows (PowerShell): venv\Scripts\Activate.ps1
```

**Verify:** `which python` (macOS/Linux) or `where python` (Windows) points inside `.../MonkeyKingStudiosMaker/venv/`.

> `start.sh` will auto-activate `venv/` on launch if it exists, but you need it active now to install into it.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs only: `fastapi`, `uvicorn[standard]`, `pydantic`, `Pillow`, `anthropic`, `google-genai`, `httpx`, `python-multipart`. It takes well under a minute on a normal connection.

**Verify:** `python -c "import fastapi, uvicorn, anthropic, google.genai, httpx, PIL; print('deps ok')"` prints `deps ok`.

### 4. Create the environment file (optional but recommended)

```bash
cp .env.example .env
```

`.env` holds host/port and optional API keys. You can leave the key values as-is for now — the app boots without them and you can enter keys in the UI later (Step 5). `.env` is gitignored, so your secrets stay local.

**Verify:** `ls .env` succeeds.

### 5. Add API keys (do this whenever — boot does not require them)

Keys can be provided **two ways** (resolution order at every call: per-request override → `config.json` → environment variable):

- **In `.env`** — edit the three lines:
  ```
  ANTHROPIC_API_KEY=sk-ant-...
  GEMINI_API_KEY=AIza...
  MESHY_API_KEY=msy_...
  ```
- **In the app** — start the server, open **Settings** (gear icon, top-left of any page), paste keys, Save. These persist server-side to `config.json` (gitignored) and apply without a restart.

Which key powers what:

| Key | Feature |
|---|---|
| `GEMINI_API_KEY` | Character Generator + Book Builder image generation (Imagen / Gemini) |
| `ANTHROPIC_API_KEY` | Book Builder story decomposition + Figure Maker print reports |
| `MESHY_API_KEY` | Figure Maker 3D models + "Create Figure" from a portrait |

Get keys from: [Anthropic Console](https://console.anthropic.com/) · [Google AI Studio](https://aistudio.google.com/apikey) · [Meshy](https://www.meshy.ai/).

Each feature shows a friendly "add your key in Settings" message until its key is set; the rest of the app keeps working.

### 6. Run the server

**Normal use (foreground):**
```bash
./start.sh
```
Then open **http://localhost:8000** — it redirects to the Book Builder.

Stop it with `Ctrl-C`, or from another terminal: `./stopServer.sh`.

**Automated/agent verification (background + health check):**
```bash
./start.sh > /tmp/mks.log 2>&1 &
sleep 4
curl -s http://localhost:8000/health        # expect: {"status":"ok"}
./stopServer.sh
```

**Verify:** `GET /health` returns `{"status":"ok"}`. If so, installation is complete.

---

## Quick smoke test (optional)

With the server running and a `GEMINI_API_KEY` set:

1. Open http://localhost:8000 → **Character Generator**.
2. Type a character description (e.g. "a friendly cartoon monkey king") and click **Generate Character**.
3. A portrait should appear within a few seconds. If it does, the Gemini path is wired correctly end-to-end.

---

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `git clone` → permission denied / not found | Private repo. Run `gh auth login` or set up SSH, then retry. |
| `python3: command not found` | Install Python 3.10+ (macOS: `brew install python`; Debian/Ubuntu: `sudo apt install python3 python3-venv`). |
| `pip install` errors on a package | Ensure the venv is active (Step 2) and pip is current: `pip install --upgrade pip`, then retry. |
| Port 8000 already in use | `./stopServer.sh`, or set `PORT=8080` in `.env` and restart (open the matching URL). |
| A feature says "add your key in Settings" | That feature's API key isn't set — add it in **Settings** or `.env` (Step 5). Not an install failure. |
| Tempted to install `torch`/`diffusers` | Don't — they were removed. The app uses cloud APIs only; `requirements.txt` is complete. |
| `permission denied: ./start.sh` | `chmod +x start.sh stopServer.sh`, then retry. |

---

## What gets created at runtime

These are gitignored and created on first use — a fresh clone starts empty:

- `output/` — generated images and downloaded GLB files (`output/figures/`)
- `gallery/` — saved storybooks, plus `images.json` / `models.json` manifests
- `config.json` — API keys saved via the Settings page
- `.env` — your local environment file
- `venv/` — the Python virtual environment

---

## TL;DR

```bash
git clone https://github.com/terminus45/MonkeyKingStudiosMaker.git
cd MonkeyKingStudiosMaker
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # optional; or add keys in-app under Settings
./start.sh                  # → http://localhost:8000
```

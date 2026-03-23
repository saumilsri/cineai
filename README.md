# CineAI

Local-first LLM video editor. Upload a video, describe how you want it edited, get a re-cut version back with dead air removed, B-roll inserted, and background music added.

Powered by Ollama (local models) — no API keys needed.

## How It Works

1. **Upload** a video through the web UI
2. **Describe** what you want: *"make this faster paced and more engaging"*
3. CineAI **analyzes** the video (keyframes, transcript, scene detection)
4. An LLM **breaks it down** into moments and **plans edits** (what to cut, where to add B-roll, what music to use)
5. FFmpeg **executes** the edit plan
6. **Download** your edited video

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose
- [Ollama](https://ollama.com/) installed with models pulled:

```bash
ollama pull llava
ollama pull llama3.2
```

### Run

```bash
git clone https://github.com/saumilsri/cineai.git
cd cineai
cp .env.example .env
docker-compose up --build
```

Open [http://localhost:3000](http://localhost:3000)

### Run Without Docker

**Backend:**

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Make sure Ollama is running (`ollama serve`) and FFmpeg is installed.

## Configuration

All settings are in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_VLM_MODEL` | `llava` | Vision model for frame analysis |
| `OLLAMA_LLM_MODEL` | `llama3.2` | Text model for planning |
| `PEXELS_API_KEY` | *(empty)* | Optional — for stock B-roll footage |
| `JOBS_DIR` | `./jobs` | Where job data is stored |
| `MUSIC_DIR` | `./music` | Bundled music tracks directory |

## B-Roll

CineAI supports two B-roll sources:

- **Pexels API** — Set `PEXELS_API_KEY` in `.env` to auto-fetch stock clips matching the LLM's suggestions
- **Local clips** — Place video files in a folder and reference them during upload

## Music

Place `.mp3`, `.wav`, or `.ogg` files in the `backend/music/` directory. The LLM will pick a track name from what's available. A few royalty-free tracks are recommended.

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full technical breakdown.

## License

MIT

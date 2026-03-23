# CineAI Architecture

**Local-first LLM video editor.**

Upload a video, describe how you want it edited in plain language, and get back a re-cut version with dead air removed, B-roll inserted, and background music mixed in. The entire pipeline runs locally via Ollama -- no cloud API keys required.

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  FRONTEND  (React 19 + TypeScript + Tailwind)                          │
│                                                                          │
│  UploadZone ──► ProcessingView (SSE) ──► ResultView (video + summary)  │
│       │                                        │                         │
│       └──── POST /api/jobs ────────────────────┘                         │
│                    GET /api/jobs/{id}/stream (SSE)                        │
│                    GET /api/jobs/{id}/download                            │
└───────────────────────────┬──────────────────────────────────────────────┘
                            │  HTTP / SSE
┌───────────────────────────▼──────────────────────────────────────────────┐
│  BACKEND  (Python 3.11+ / FastAPI)                                      │
│                                                                          │
│  api/routes.py ──► _process() pipeline orchestrator                     │
│       │                                                                  │
│       ├── pipeline/extractor.py     FFmpeg + PySceneDetect               │
│       ├── pipeline/transcriber.py   faster-whisper                       │
│       ├── pipeline/analyzer.py      Ollama LLaVA (VLM)                   │
│       ├── pipeline/planner.py       Ollama LLM (text)                    │
│       ├── pipeline/editor.py        FFmpeg rendering                     │
│       │                                                                  │
│       ├── broll/pexels.py           Pexels stock footage API             │
│       └── broll/local.py            Local clip file matching             │
│                                                                          │
│  providers/ollama.py ◄── providers/base.py (abstract)                   │
└───────────────────────────┬──────────────────────────────────────────────┘
                            │  HTTP (async httpx)
┌───────────────────────────▼──────────────────────────────────────────────┐
│  OLLAMA  (localhost:11434)                                               │
│                                                                          │
│  llava    ──  vision-language model (frame analysis)                     │
│  llama3.2 ──  text model (moment breakdown + edit planning)              │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline: Step by Step

When the user uploads a video and submits a prompt, the backend runs an async pipeline that progresses through six stages. Each stage updates the job status, which the frontend receives via SSE.

### Stage 1 -- Extraction (5-15%)

**Module:** `pipeline/extractor.py`

Three FFmpeg operations run in sequence, plus scene detection:

| Operation | Tool | Command | Output |
|-----------|------|---------|--------|
| Keyframes | FFmpeg | `ffmpeg -y -i {video} -vf fps=1/{interval} {dir}/frame_%04d.jpg` | 1 JPEG per 2 seconds |
| Audio | FFmpeg | `ffmpeg -y -i {video} -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav` | 16kHz mono WAV |
| Duration | ffprobe | `ffprobe -v error -show_entries format=duration -of csv=p=0 {video}` | Float (seconds) |
| Scenes | PySceneDetect | `ContentDetector()` with default threshold | List of cut timestamps |

Scene detection is non-critical -- if it fails (e.g. codec not supported by OpenCV), the pipeline continues without it.

**Output:** `list[tuple[float, str]]` of (timestamp, frame_path) pairs, a WAV file path, a duration float, and optionally a list of scene boundary timestamps.

### Stage 2 -- Transcription (20-35%)

**Module:** `pipeline/transcriber.py`

Uses faster-whisper running locally on CPU with int8 quantization. The model (`base` by default, configurable) is loaded once and cached for the process lifetime.

```
audio.wav ──► WhisperModel.transcribe(beam_size=5)
         ──► [{"start": 0.0, "end": 2.3, "text": "Welcome to..."}, ...]
```

Empty-text segments are filtered out. The raw dicts are converted to `TranscriptSegment` Pydantic models in the route handler.

### Stage 3 -- VLM Frame Analysis (40-55%)

**Module:** `pipeline/analyzer.py`

Each keyframe JPEG is sent sequentially to Ollama's LLaVA model with this prompt:

> *"Describe what is happening in this video frame in one sentence. Note any emotions, actions, or notable objects."*

The image is base64-encoded and sent via `POST /api/generate` with the `images` field. Each call has a 180-second timeout to account for slow hardware.

If a single frame fails (network error, timeout, etc.), it's logged and recorded as `[analysis failed]` -- it doesn't abort the entire pipeline.

**Output:** `list[FrameDescription]` with `timestamp_sec` and `description` per frame.

### Stage 4 -- Planning (60-75%)

**Module:** `pipeline/planner.py`

This is two LLM calls in sequence, both to the text model (llama3.2 by default):

**4a. Moment Breakdown**

The combined analysis (transcript + frame descriptions + scene boundaries + duration) is formatted into a structured prompt. The system prompt instructs the LLM to return a JSON array covering the full timeline:

```json
[
  {"start": 0.0,  "end": 4.2,  "description": "Host introduces topic",      "energy": "medium", "type": "content"},
  {"start": 4.2,  "end": 8.5,  "description": "Awkward pause, looks at notes", "energy": "low",  "type": "dead_air"},
  {"start": 8.5,  "end": 15.0, "description": "Main point delivered with enthusiasm", "energy": "high", "type": "highlight"}
]
```

Each moment has:
- `start` / `end` -- time range in seconds
- `description` -- what's happening
- `energy` -- `low` | `medium` | `high`
- `type` -- `content` | `dead_air` | `transition` | `highlight`

**Fallback:** If JSON parsing fails, a single fallback moment covering the full duration is returned.

**4b. Edit Plan Generation**

The moment breakdown + user prompt + duration are sent to the LLM. The system prompt instructs it to return a JSON object:

```json
{
  "cuts": [
    {"start": 4.2, "end": 8.5, "reason": "dead air - awkward pause"}
  ],
  "broll_insertions": [
    {"insert_at": 15.0, "duration": 3.0, "search_query": "technology abstract", "source": "stock"}
  ],
  "music": {
    "track": "upbeat-chill",
    "volume": 0.15,
    "fade_in": 2.0,
    "fade_out": 3.0
  }
}
```

**Fallback:** If JSON parsing fails, the planner auto-generates a basic plan that cuts all `dead_air` moments with default music config.

Both LLM calls handle the common case where Ollama wraps JSON in markdown code fences -- a `_extract_json()` helper strips ` ```json ... ``` ` wrappers before parsing.

### Stage 5 -- B-Roll Fetching (78%)

**Modules:** `broll/pexels.py`, `broll/local.py`

For each `BRollInsertion` in the edit plan:

1. If `source == "local"`, search the `user_broll/` directory in the job folder for clips whose filenames match the `search_query` keywords. Falls back to random selection.
2. If no local match (or `source == "stock"`), and a Pexels API key is configured, search the Pexels Video API for the `search_query`, download the smallest resolution file.
3. If neither source yields a clip, that insertion is skipped silently.

**Pexels API details:**
- Endpoint: `GET https://api.pexels.com/videos/search`
- Auth: `Authorization: {api_key}` header
- Selects smallest file by width from the first result
- Free tier: 200 requests/month

### Stage 6 -- Rendering (80-100%)

**Module:** `pipeline/editor.py`

Three sequential FFmpeg operations, each producing an intermediate MP4:

**6a. Cuts** (`apply_cuts`)

Converts the list of cuts into "keep" segments (the inverse), then builds an FFmpeg `filter_complex`:

```
[0:v]trim=start=0:end=4.2,setpts=PTS-STARTPTS[v0];
[0:v]trim=start=8.5:end=30.0,setpts=PTS-STARTPTS[v1];
[0:a]atrim=start=0:end=4.2,asetpts=PTS-STARTPTS[a0];
[0:a]atrim=start=8.5:end=30.0,asetpts=PTS-STARTPTS[a1];
[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]
```

Encoding: H.264 (`libx264`, preset `fast`, CRF 23) + AAC (128kbps).

If no cuts exist, the source file is copied as-is.

**6b. B-Roll Insertion** (`insert_broll`)

For each B-roll insertion point, the main video is split into segments, and each B-roll clip is:
- Trimmed to the specified duration
- Scaled to match the source video resolution (with letterboxing to preserve aspect ratio)
- Stripped of audio (`-an`)

All segments (main + B-roll interleaved) are written to a concat list file and joined via FFmpeg's concat demuxer. The temporary work directory is cleaned up after.

**6c. Music Mixing** (`mix_music`)

The background music track is overlaid on the edited video:

```
Input 0: edited video (video + original audio)
Input 1: music file (looped with -stream_loop -1)

Filter: [1:a] volume → fade_in → fade_out → [music]
        [0:a][music] amix (duration=first) → [outa]

Output: video stream copied, audio re-encoded as AAC 128k
```

The music auto-loops if shorter than the video. Volume, fade-in, and fade-out durations come from the edit plan's `MusicConfig`.

If the music file doesn't exist, this step is skipped and the video is passed through unchanged.

---

## Job Lifecycle

```
                    POST /api/jobs
                         │
                         ▼
    ┌─────────┐    ┌────────────┐    ┌──────────────┐    ┌───────────┐
    │ PENDING  │───►│ EXTRACTING │───►│ TRANSCRIBING │───►│ ANALYZING │
    └─────────┘    └────────────┘    └──────────────┘    └───────────┘
                                                               │
                         ┌─────────────────────────────────────┘
                         ▼
                   ┌──────────┐    ┌────────────────┐    ┌───────────┐
                   │ PLANNING │───►│ FETCHING_BROLL │───►│ RENDERING │
                   └──────────┘    └────────────────┘    └───────────┘
                                                               │
                              ┌────────────────────────────────┤
                              ▼                                ▼
                         ┌────────┐                      ┌────────┐
                         │  DONE  │                      │ FAILED │
                         └────────┘                      └────────┘
```

Each status transition writes the job JSON to `jobs/{id}/job.json` and is emitted via SSE. Progress percentages are approximate:

| Stage | Status | Progress |
|-------|--------|----------|
| Upload received | `pending` | 0% |
| FFmpeg extraction + scene detect | `extracting` | 5-15% |
| Whisper transcription | `transcribing` | 20-35% |
| LLaVA frame analysis | `analyzing` | 40-55% |
| Moment breakdown + edit plan | `planning` | 60-75% |
| B-roll download | `fetching_broll` | 78% |
| FFmpeg cuts + splice + music | `rendering` | 80-100% |

If any stage throws an unhandled exception, the job transitions to `failed` with the error message.

---

## Data Models

All models are Pydantic v2 (`BaseModel`), defined in `app/models.py`.

### Video Analysis

```
VideoAnalysis
├── duration_sec: float
├── frame_descriptions: list[FrameDescription]
│   ├── timestamp_sec: float
│   └── description: str
├── transcript: list[TranscriptSegment]
│   ├── start: float
│   ├── end: float
│   └── text: str
└── scene_boundaries: list[SceneBoundary]
    ├── timestamp_sec: float
    └── type: str  ("cut")
```

### Moments

```
Moment
├── start: float
├── end: float
├── description: str
├── energy: "low" | "medium" | "high"
└── type: "content" | "dead_air" | "transition" | "highlight"
```

### Edit Plan

```
EditPlan
├── cuts: list[Cut]
│   ├── start: float
│   ├── end: float
│   └── reason: str
├── broll_insertions: list[BRollInsertion]
│   ├── insert_at: float
│   ├── duration: float  (default 3.0)
│   ├── search_query: str
│   └── source: "stock" | "local"
└── music: MusicConfig
    ├── track: str  (default "upbeat-chill")
    ├── volume: float  (default 0.15, range 0.0–1.0)
    ├── fade_in: float  (default 2.0s)
    └── fade_out: float  (default 3.0s)
```

### Job

```
Job
├── id: str  (12-char hex UUID)
├── status: pending | extracting | transcribing | analyzing | planning | fetching_broll | rendering | done | failed
├── progress_pct: int  (0–100)
├── status_message: str
├── created_at: datetime
├── prompt: str
├── source_video: str  (path)
├── output_video: str  (URL path)
├── analysis: VideoAnalysis?
├── moments: list[Moment]
├── edit_plan: EditPlan?
└── error: str?
```

Jobs are stored both in-memory (`_jobs` dict) and on disk (`jobs/{id}/job.json`). On restart, jobs can be loaded from disk via `GET /api/jobs/{id}`.

---

## API Reference

### `POST /api/jobs`

Create a new editing job. Multipart form upload.

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `video` | File | Yes | -- |
| `prompt` | string | No | `"Make this faster paced and more engaging"` |

**Response:**
```json
{"job_id": "a1b2c3d4e5f6"}
```

### `GET /api/jobs/{id}/stream`

SSE endpoint. Emits `data: {...}\n\n` events as the job progresses.

**Progress event:**
```json
{"status": "analyzing", "progress": 45, "message": "Analyzing frames with VLM..."}
```

**Completion event (includes full results):**
```json
{
  "status": "done",
  "progress": 100,
  "message": "Complete",
  "output_video": "/jobs/a1b2c3d4e5f6/output.mp4",
  "moments": [{"start": 0.0, "end": 4.2, "description": "...", "energy": "medium", "type": "content"}],
  "edit_plan": {"cuts": [...], "broll_insertions": [...], "music": {...}}
}
```

**Failure event:**
```json
{"status": "failed", "error": "RuntimeError: FFmpeg failed: ..."}
```

### `GET /api/jobs/{id}`

Poll fallback. Returns the full `Job` model as JSON.

### `GET /api/jobs/{id}/download`

Returns the output MP4 as a file download with `Content-Disposition: attachment`.

### `GET /api/music`

List available background music tracks from the `music/` directory.

```json
{"tracks": [{"name": "upbeat-chill", "filename": "upbeat-chill.mp3"}]}
```

---

## Provider Abstraction (BYOM)

The `providers/base.py` defines an abstract interface:

```python
class LLMProvider(ABC):
    async def generate(self, prompt: str, system: str = "") -> str: ...
    async def generate_with_image(self, prompt: str, image_path: str, system: str = "") -> str: ...
```

`OllamaProvider` implements this by calling Ollama's HTTP API at `POST {base_url}/api/generate`. Images are sent as base64 in the `images` array field.

Two separate provider instances are created per job -- one with the VLM model (llava) for frame analysis, one with the text model (llama3.2) for planning. Both use `stream: false` for simplicity.

To add a new provider (e.g. OpenAI, Anthropic, Google), implement `LLMProvider` and wire it up in the route handler based on config.

---

## Frontend Architecture

Three-phase single-page app:

**Phase 1 -- Upload** (`UploadZone.tsx`)
- Drag-and-drop zone accepting video files (MP4, MOV, AVI, MKV)
- Text area for edit prompt with sensible default
- Submits as `multipart/form-data` to `POST /api/jobs`

**Phase 2 -- Processing** (`ProcessingView.tsx`)
- Opens SSE connection to `GET /api/jobs/{id}/stream`
- Shows a progress bar + step-by-step checklist (6 stages)
- Displays the moment breakdown as it becomes available, color-coded by type:
  - Red: dead_air
  - Amber: highlight
  - Blue: transition
  - Default: content
- Energy levels shown as badges

**Phase 3 -- Result** (`ResultView.tsx`)
- Inline `<video>` player for the output
- Download button (`GET /api/jobs/{id}/download`)
- Three-column summary: cuts made, B-roll added, music config
- Full moment breakdown timeline with dead_air segments shown struck-through

State management is plain React hooks (`useState`, `useCallback`). No external state library.

---

## Configuration

All settings are loaded from environment variables via pydantic-settings (`app/config.py`). Copy `.env.example` to `.env`.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OLLAMA_BASE_URL` | string | `http://localhost:11434` | Ollama API base URL |
| `OLLAMA_VLM_MODEL` | string | `llava` | Model for frame analysis |
| `OLLAMA_LLM_MODEL` | string | `llama3.2` | Model for text planning |
| `PEXELS_API_KEY` | string | *(empty)* | Pexels API key for stock B-roll |
| `JOBS_DIR` | path | `./jobs` | Job data storage directory |
| `MUSIC_DIR` | path | `./music` | Background music directory |
| `UPLOAD_MAX_SIZE_MB` | int | `500` | Max upload size |
| `KEYFRAME_INTERVAL_SEC` | float | `2.0` | Seconds between keyframe extractions |
| `WHISPER_MODEL_SIZE` | string | `base` | faster-whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`) |

---

## Job Directory Layout

Each job creates a directory under `JOBS_DIR`:

```
jobs/{job_id}/
├── job.json            # Serialized Job model (updated at each stage)
├── source.mp4          # Uploaded original video
├── audio.wav           # Extracted audio (16kHz mono)
├── frames/             # Extracted keyframes
│   ├── frame_0001.jpg
│   ├── frame_0002.jpg
│   └── ...
├── broll/              # Downloaded stock B-roll clips
│   ├── stock_0.mp4
│   └── ...
├── cut.mp4             # Intermediate: after cuts applied
├── broll_out.mp4       # Intermediate: after B-roll insertion
└── output.mp4          # Final rendered video
```

---

## Deployment

### Docker Compose (recommended)

```yaml
services:
  ollama:     # GPU-accelerated model server
  backend:    # FastAPI on port 8000
  frontend:   # nginx on port 3000, proxies /api → backend
```

The frontend nginx config proxies `/api/*` and `/jobs/*` to the backend, so the browser only talks to port 3000.

### Local Development

1. Run Ollama: `ollama serve` (pull `llava` and `llama3.2` first)
2. Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`
3. Frontend: `cd frontend && npm install && npm run dev`

The Vite dev server proxies `/api` and `/jobs` to `localhost:8000`.

---

## Error Handling Strategy

| Scenario | Behavior |
|----------|----------|
| Scene detection fails | Warning logged, pipeline continues without scene data |
| Single frame VLM analysis fails | Frame recorded as `[analysis failed]`, pipeline continues |
| Moment breakdown JSON parse fails | Fallback: single moment covering full duration |
| Edit plan JSON parse fails | Fallback: cut all `dead_air` moments, default music config |
| Pexels API fails or no key | B-roll insertion skipped for that entry |
| Music file not found | Music mixing skipped, video passed through |
| FFmpeg encoding fails | Job marked `failed` with FFmpeg stderr |
| Any unhandled exception | Job marked `failed` with exception message |

---

## Known Limitations (Prototype)

- **Single job at a time.** Jobs run as background asyncio tasks in the same process. No queue, no workers.
- **In-memory job registry.** The `_jobs` dict is lost on restart (though jobs can be reloaded from disk JSON).
- **Sequential frame analysis.** Each keyframe is sent to LLaVA one at a time. For a 60-second video, that's ~30 LLM calls.
- **No auth.** Anyone with network access to port 3000 can upload and process.
- **No cleanup.** Job directories and intermediate files accumulate indefinitely.
- **B-roll insertion shifts timestamps.** The edit plan's `insert_at` times reference the *original* video timeline, but cuts have already shortened it. This can cause slight misalignment.
- **LLM output quality varies.** Smaller local models may produce malformed JSON or poor edit decisions. The fallback paths handle parsing failures, but the edits themselves may be suboptimal.

---

## Future Work

- [ ] Concurrent frame analysis (batch VLM calls)
- [ ] Worker queue (Redis/Celery) for parallel jobs
- [ ] OpenAI / Anthropic / Google provider implementations
- [ ] User-uploaded B-roll directory in the UI
- [ ] Music track selector in the UI
- [ ] Preview edits before rendering
- [ ] Style presets (fast-paced, cinematic, social media, etc.)
- [ ] Undo / re-plan with different prompt
- [ ] Authentication and job history

# CineAI - LLM Video Editor Architecture
## Hybrid Approach: Multimodal VLM + Autonomous Agent

**Date:** March 23, 2026  
**Approach:** Combine Vision-Language Models (Approach 2) with Autonomous Editing Agent (Approach 4)  
**Target:** Open-source, bring-your-own-model (BYOM)

---

## Core Concept

**CineAI** understands video content semantically (VLM) and acts as an autonomous editor that iteratively refines edits based on goals.

**Example Workflow:**
```
User: "Make this interview more engaging, remove dead air, add B-roll"
  ↓
VLM analyzes video → identifies boring segments, speaker emotions
  ↓
Agent plans edits → scene cuts, B-roll insertion points
  ↓
Agent executes → FFmpeg processing
  ↓
Agent evaluates → "Engagement score improved 40%"
  ↓
User approves/refines
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACE                           │
│  (React/Vue frontend - web or electron desktop)             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    API LAYER (FastAPI)                     │
│  - REST endpoints for video upload, job status, results      │
│  - WebSocket for real-time progress                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   AGENT ORCHESTRATOR                       │
│  - Planning Agent (Claude/GPT-4/Gemini)                    │
│  - Evaluation Agent                                        │
│  - Task queue (Redis/RQ)                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  VISION-LANGUAGE MODULE                    │
│  - Keyframe extraction (FFmpeg)                            │
│  - VLM analysis (GPT-4V/Gemini/Qwen-VL)                    │
│  - Content understanding (scenes, emotions, objects)       │
│  - Transcription (Whisper)                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  VIDEO PROCESSING ENGINE                   │
│  - FFmpeg wrapper (Python moviepy or C++ binding)        │
│  - Scene detection (PySceneDetect)                         │
│  - Audio processing (pydub, librosa)                     │
│  - B-roll injection                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    STORAGE LAYER                           │
│  - Local: Filesystem                                     │
│  - Cloud: S3/MinIO (optional)                              │
│  - Database: PostgreSQL (jobs, metadata)                   │
└──────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. VLM Analysis Pipeline

```python
class VLMAnalyzer:
    def analyze_video(self, video_path: str) -> VideoAnalysis:
        # Extract keyframes every N seconds
        frames = extract_keyframes(video_path, interval=2.0)
        
        # Transcribe audio
        transcript = whisper.transcribe(video_path)
        
        # Analyze each frame with VLM
        for frame in frames:
            description = vlm.describe(frame)
            objects = vlm.detect_objects(frame)
            emotions = vlm.detect_emotions(frame)
            
        return VideoAnalysis(
            scenes=detect_scenes(frames),
            transcript=transcript,
            visual_descriptions=descriptions,
            emotional_arc=emotions
        )
```

**Supported VLMs:**
- OpenAI GPT-4V (cloud)
- Google Gemini Pro Vision (cloud)
- Qwen-VL (local/self-hosted)
- LLaVA (local)

### 2. Autonomous Agent Loop

```python
class EditingAgent:
    def edit(self, video: Video, goal: str) -> EditedVideo:
        context = {
            'analysis': vlm_analyzer.analyze(video),
            'goal': goal,
            'constraints': user_constraints
        }
        
        # Planning phase
        plan = planning_llm.generate_edit_plan(context)
        
        # Execution phase
        for step in plan.steps:
            result = execute_step(step)
            
            # Evaluation
            quality = evaluation_llm.assess(result, goal)
            
            if quality.score < threshold:
                # Refine
                plan = planning_llm.refine(plan, quality.feedback)
                
        return final_video
```

### 3. Command System

Natural language → Structured commands

```python
class EditCommand:
    REMOVE_SILENCE = "remove_silence"
    TRIM = "trim"
    ADD_TRANSITION = "add_transition"
    ADD_B_ROLL = "add_b_roll"
    ADJUST_PACING = "adjust_pacing"
    
@dataclass
class Command:
    type: EditCommand
    params: dict
    start_time: float
    end_time: float
```

---

## Open-Source Model Support (BYOM)

Users bring their own API keys or run local models:

```yaml
# config.yaml
models:
  vision_language:
    provider: "openai"  # or "google", "ollama", "local"
    model: "gpt-4o"
    api_key: "${OPENAI_API_KEY}"
    
  planning:
    provider: "anthropic"
    model: "claude-3-5-sonnet"
    api_key: "${ANTHROPIC_API_KEY}"
    
  transcription:
    provider: "openai"
    model: "whisper-1"
```

**Supported Providers:**
- OpenAI
- Anthropic
- Google (Gemini)
- Ollama (local)
- vLLM (self-hosted)

---

## Project Structure

```
cine-ai/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entry
│   │   ├── api/
│   │   │   ├── jobs.py          # Job management endpoints
│   │   │   ├── videos.py        # Video upload/status
│   │   │   └── websocket.py     # Progress updates
│   │   ├── core/
│   │   │   ├── config.py        # Settings
│   │   │   ├── models.py        # SQLAlchemy models
│   │   │   └── exceptions.py
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── planner.py       # Planning agent
│   │   │   ├── executor.py      # Command execution
│   │   │   └── evaluator.py     # Quality assessment
│   │   ├── vlm/
│   │   │   ├── __init__.py
│   │   │   ├── analyzer.py      # Video analysis
│   │   │   └── providers.py     # VLM provider abstractions
│   │   └── video/
│   │       ├── __init__.py
│   │       ├── processor.py     # FFmpeg wrapper
│   │       ├── scene_detector.py
│   │       └── effects.py       # Transitions, etc.
│   ├── alembic/                 # DB migrations
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── api/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── README.md
├── LICENSE
└── .env.example
```

---

## MVP Scope

**Phase 1 (Weeks 1-2): Core Pipeline**
- [ ] Video upload + storage
- [ ] Keyframe extraction
- [ ] VLM analysis (GPT-4V)
- [ ] Simple commands: trim, remove silence
- [ ] FFmpeg execution

**Phase 2 (Weeks 3-4): Agent Loop**
- [ ] Planning agent
- [ ] Evaluation agent
- [ ] Iterative refinement
- [ ] Natural language interface

**Phase 3 (Month 2): Polish**
- [ ] Frontend UI
- [ ] BYOM config
- [ ] Multiple VLM support
- [ ] B-roll injection

**Phase 4 (Month 3): Advanced**
- [ ] Style learning
- [ ] Workflow templates
- [ ] Export presets

---

## Tech Stack

**Backend:**
- Python 3.11+
- FastAPI (API)
- SQLAlchemy + PostgreSQL (DB)
- Redis (queue)
- FFmpeg (video processing)
- OpenAI/Anthropic SDKs

**Frontend:**
- React + TypeScript
- Tailwind CSS
- WebSocket for real-time updates

**Infrastructure:**
- Docker + Docker Compose
- Optional: Kubernetes for scale

---

## Differentiation

| Feature | Descript | Runway | CineAI |
|---------|----------|---------|---------|
| Semantic understanding | Partial | Limited | Full VLM analysis |
| Autonomous editing | No | No | Yes (agent loop) |
| BYOM | No | No | Yes |
| Iterative refinement | No | No | Yes |
| Explainability | Limited | Limited | Full reasoning |

---

## Next Steps

1. **Set up repo structure**
2. **Implement video upload + storage**
3. **Build VLM analysis pipeline**
4. **Create simple command executor**
5. **Add planning agent**
6. **Build frontend**

**Start:** Backend API + VLM pipeline

---

## API Design

```python
# POST /api/videos
{
  "file": "interview.mp4",
  "settings": {
    "vlm_provider": "openai",
    "analysis_depth": "detailed"
  }
}

# POST /api/jobs
{
  "video_id": "vid_123",
  "prompt": "Make this more engaging, remove dead air",
  "constraints": {
    "max_duration": 300,
    "keep_speaker": ["Alice"]
  }
}

# GET /api/jobs/{id}/status
{
  "status": "processing",
  "progress": 45,
  "current_step": "Planning edits...",
  "estimated_completion": "2026-03-23T15:00:00Z"
}
```

---

## License

MIT - Open source, contributions welcome.

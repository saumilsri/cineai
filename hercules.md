# Hercules Notes - CineAI Review

**Date:** March 23, 2026  
**Reviewed:** Backend pipeline, API routes, frontend components

---

## Code Review Summary

**Overall:** Solid MVP structure. Clean separation of concerns, good async handling, FastAPI setup is proper.

**What's Working:**
- FastAPI with lifespan context manager for startup tasks
- SSE streaming for real-time progress updates
- Pipeline stages: Extract → Transcribe → Analyze → Plan → Render
- B-roll fetching with fallback (Pexels API)
- Music mixing support
- Job persistence (JSON files)

**Issues Found:**

### 1. VLM Provider Single-Threaded
**File:** `app/pipeline/analyzer.py`  
**Problem:** Sequential frame analysis. With 100 frames and 3s per VLM call = 5 minutes just for analysis.

**Fix:** Batch or parallelize VLM calls:
```python
# Use asyncio.gather with semaphore
semaphore = asyncio.Semaphore(5)  # Limit concurrent calls

tasks = [analyze_with_semaphore(semaphore, ts, path, provider) for ts, path in frames]
descriptions = await asyncio.gather(*tasks)
```

### 2. No Retry Logic
**File:** `app/providers/ollama.py`  
**Problem:** If Ollama crashes or times out, entire job fails.

**Fix:** Add exponential backoff retry:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential())
async def generate_with_image(...)
```

### 3. Scene Detection Failure Handling
**File:** `app/pipeline/routes.py`, line ~103  
**Current:** Logs warning but continues without scene boundaries.

**Suggestion:** This is fine for MVP, but note that scene detection improves edit quality significantly.

### 4. Memory Leak Risk
**File:** `_jobs` dict in routes.py  
**Problem:** Jobs stay in memory forever. With 100 jobs, that's memory pressure.

**Fix:** Add TTL or LRU cache:
```python
from functools import lru_cache
# Or clear old jobs periodically
```

### 5. No Validation on Upload
**File:** `routes.py` create_job  
**Problem:** Accepts any file. Could upload malicious files.

**Fix:** Check file type:
```python
if not video.filename.endswith(('.mp4', '.mov', '.avi')):
    raise HTTPException(400, "Invalid video format")
```

### 6. Hardcoded Timeouts
**File:** Multiple  
**VLM timeout:** 180s may be too short for large models on slow hardware.

**Suggestion:** Make configurable or adaptive.

---

## Architecture Strengths

1. **Pipeline Pattern:** Clean stage separation, easy to extend
2. **Provider Abstraction:** Can swap Ollama for OpenAI easily
3. **Progress Streaming:** SSE is perfect for long-running jobs
4. **Job Persistence:** JSON files survive restarts
5. **Docker Setup:** Ready for containerization

---

## Recommended Test Plan

### Unit Tests
```python
# 1. Test each pipeline stage independently
- extractor.extract_keyframes() with sample video
- transcriber.transcribe() with sample audio
- analyzer.analyze_frames() with mock VLM
- planner.generate_edit_plan() with mock LLM

# 2. Test provider fallback
- Ollama unavailable → should fail gracefully
- Timeout handling
- Retry logic
```

### Integration Tests
```python
# 1. Full pipeline with 10-second test video
# 2. Test SSE progress streaming
# 3. Test concurrent jobs
# 4. Test error recovery
```

### Manual Tests
1. **Upload flow:**
   - Upload 10s video → should extract frames
   - Upload 1min video → should complete in reasonable time
   - Upload 10min video → test with your patience

2. **VLM integration:**
   - Test with Ollama (local)
   - Test with OpenAI (if you add provider)
   - Verify frame descriptions make sense

3. **Edit quality:**
   - Test "remove silence" → verify cuts
   - Test "add B-roll" → verify inserts
   - Test with/without scene detection

4. **Edge cases:**
   - Silent video (no audio)
   - Very dark video (VLM struggles)
   - Corrupted video file

### Performance Tests
1. **Memory usage:** Monitor during 5min video processing
2. **Concurrent jobs:** 3 jobs at once
3. **VLM speed:** Benchmark frames/sec with your Ollama setup

---

## Quick Wins

1. **Add parallel VLM calls** - 5x speedup on analysis
2. **Add retry logic** - More robust
3. **Add file validation** - Security
4. **Add memory cleanup** - Stability
5. **Add timing logs** - Debug performance

---

## Suggested Next Features

**Priority 1:**
- OpenAI/Anthropic provider (faster than Ollama)
- Edit plan preview (show what will be cut before rendering)
- Cancel job endpoint

**Priority 2:**
- Templates ("YouTube style", "TikTok style")
- Undo/redo for edits
- Export to YouTube API

**Priority 3:**
- Style learning (learn from your past edits)
- Collaborative editing
- Real-time preview

---

## Deployment Notes

**For Testing:**
```bash
# Local dev
cd backend
pip install -r requirements.txt
python -m app.main

# With Docker
docker-compose up --build
```

**For Production:**
- Use S3/MinIO for storage (not local filesystem)
- Redis for job queue (not in-memory dict)
- Separate VLM service (don't run on API server)
- Add monitoring (Prometheus/Grafana)

---

## Questions for You

1. Have you tested with a real video yet? What was the latency?
2. Is Ollama fast enough on your Pi, or should we prioritize OpenAI provider?
3. What's the longest video you plan to process?
4. Do you want me to implement any of the fixes above?

---

**Verdict:** Good MVP. Core architecture is sound. Focus on making VLM calls faster and adding retry logic for robustness.

- Hercules

"""API routes: upload video, start processing job, stream progress, download result."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import traceback
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse

from app.config import settings
from app.models import (
    EditPlan,
    Job,
    JobStatus,
    MusicConfig,
    SceneBoundary,
    TranscriptSegment,
    VideoAnalysis,
)
from app.providers.ollama import OllamaProvider
from app.pipeline import extractor, transcriber, analyzer, planner, editor
from app.broll import pexels, local

logger = logging.getLogger(__name__)
router = APIRouter()

_jobs: dict[str, Job] = {}


def _persist_job(job: Job) -> None:
    job_dir = job.job_dir(settings.jobs_dir)
    (job_dir / "job.json").write_text(job.model_dump_json(indent=2))


def _update(job: Job, status: JobStatus, pct: int, msg: str) -> None:
    job.status = status
    job.progress_pct = pct
    job.status_message = msg
    _persist_job(job)
    logger.info("[%s] %s — %s (%d%%)", job.id, status.value, msg, pct)


# ── Upload + start job ──────────────────────────────────────────────

@router.post("/jobs")
async def create_job(
    video: UploadFile = File(...),
    prompt: str = Form("Make this faster paced and more engaging"),
):
    job = Job(prompt=prompt)
    job_dir = job.job_dir(settings.jobs_dir)

    video_path = job_dir / "source.mp4"
    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)
    job.source_video = str(video_path)

    _jobs[job.id] = job
    _persist_job(job)

    asyncio.get_event_loop().create_task(_process(job))

    return {"job_id": job.id}


# ── SSE progress stream ─────────────────────────────────────────────

@router.get("/jobs/{job_id}/stream")
async def stream_progress(job_id: str):
    async def event_generator():
        prev = ""
        while True:
            job = _jobs.get(job_id)
            if job is None:
                yield _sse({"error": "job not found"})
                return

            payload = {
                "status": job.status.value,
                "progress": job.progress_pct,
                "message": job.status_message,
            }
            serialized = json.dumps(payload, sort_keys=True)
            if serialized != prev:
                yield _sse(payload)
                prev = serialized

            if job.status in (JobStatus.DONE, JobStatus.FAILED):
                if job.status == JobStatus.DONE:
                    yield _sse({
                        "status": "done",
                        "progress": 100,
                        "message": "Complete",
                        "output_video": f"/jobs/{job.id}/output.mp4",
                        "moments": [m.model_dump(mode="json") for m in job.moments],
                        "edit_plan": job.edit_plan.model_dump(mode="json") if job.edit_plan else None,
                    })
                else:
                    yield _sse({"status": "failed", "error": job.error or "Unknown error"})
                return

            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ── Job status (poll fallback) ───────────────────────────────────────

@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        job_file = settings.jobs_dir / job_id / "job.json"
        if job_file.exists():
            job = Job.model_validate_json(job_file.read_text())
            _jobs[job_id] = job
    if not job:
        raise HTTPException(404, "Job not found")
    return job.model_dump(mode="json")


# ── Download result ──────────────────────────────────────────────────

@router.get("/jobs/{job_id}/download")
async def download_result(job_id: str):
    out = settings.jobs_dir / job_id / "output.mp4"
    if not out.exists():
        raise HTTPException(404, "Output not ready")
    return FileResponse(str(out), media_type="video/mp4", filename=f"cineai_{job_id}.mp4")


# ── Available music tracks ───────────────────────────────────────────

@router.get("/music")
async def list_music():
    tracks = []
    music_dir = settings.music_dir
    if music_dir.is_dir():
        for f in sorted(music_dir.iterdir()):
            if f.suffix.lower() in {".mp3", ".wav", ".ogg", ".m4a"}:
                tracks.append({"name": f.stem, "filename": f.name})
    return {"tracks": tracks}


# ── Pipeline execution ───────────────────────────────────────────────

async def _process(job: Job) -> None:
    try:
        job_dir = job.job_dir(settings.jobs_dir)
        video_path = job.source_video

        vlm = OllamaProvider(settings.ollama_base_url, settings.ollama_vlm_model, timeout=180.0)
        llm = OllamaProvider(settings.ollama_base_url, settings.ollama_llm_model, timeout=180.0)

        # 1 — Extract
        _update(job, JobStatus.EXTRACTING, 5, "Extracting keyframes and audio...")
        frames_dir = str(job_dir / "frames")
        audio_path = str(job_dir / "audio.wav")

        frames = await asyncio.to_thread(
            extractor.extract_keyframes, video_path, frames_dir, settings.keyframe_interval_sec
        )
        await asyncio.to_thread(extractor.extract_audio, video_path, audio_path)
        duration = await asyncio.to_thread(extractor.get_video_duration, video_path)

        try:
            scene_times = await asyncio.to_thread(extractor.detect_scenes, video_path)
        except Exception:
            logger.warning("Scene detection failed, continuing without it")
            scene_times = []

        _update(job, JobStatus.EXTRACTING, 15, f"Extracted {len(frames)} frames")

        # 2 — Transcribe
        _update(job, JobStatus.TRANSCRIBING, 20, "Transcribing audio...")
        raw_transcript = await asyncio.to_thread(
            transcriber.transcribe, audio_path, settings.whisper_model_size
        )
        transcript_segments = [TranscriptSegment(**seg) for seg in raw_transcript]
        _update(job, JobStatus.TRANSCRIBING, 35, f"Transcribed {len(transcript_segments)} segments")

        # 3 — VLM analysis
        _update(job, JobStatus.ANALYZING, 40, "Analyzing frames with VLM...")
        frame_descs = await analyzer.analyze_frames(frames, vlm)
        _update(job, JobStatus.ANALYZING, 55, f"Analyzed {len(frame_descs)} frames")

        analysis = VideoAnalysis(
            duration_sec=duration,
            frame_descriptions=frame_descs,
            transcript=transcript_segments,
            scene_boundaries=[SceneBoundary(timestamp_sec=t) for t in scene_times],
        )
        job.analysis = analysis

        # 4 — Moment breakdown + edit plan
        _update(job, JobStatus.PLANNING, 60, "Generating moment breakdown...")
        moments = await planner.generate_moments(analysis, llm)
        job.moments = moments
        _update(job, JobStatus.PLANNING, 70, f"Identified {len(moments)} moments, planning edits...")

        edit_plan = await planner.generate_edit_plan(moments, job.prompt, duration, llm)
        job.edit_plan = edit_plan
        _update(job, JobStatus.PLANNING, 75, f"Edit plan: {len(edit_plan.cuts)} cuts, {len(edit_plan.broll_insertions)} B-roll")

        # 5 — Fetch B-roll
        broll_clips: list[tuple[float, float, str]] = []
        if edit_plan.broll_insertions:
            _update(job, JobStatus.FETCHING_BROLL, 78, "Fetching B-roll clips...")
            broll_dir = job_dir / "broll"
            broll_dir.mkdir(exist_ok=True)

            for i, ins in enumerate(edit_plan.broll_insertions):
                clip_path = None
                if ins.source == "local":
                    user_broll = job_dir / "user_broll"
                    if user_broll.is_dir():
                        clip_path = local.find_clip(str(user_broll), ins.search_query)

                if clip_path is None and settings.pexels_api_key:
                    out_path = str(broll_dir / f"stock_{i}.mp4")
                    clip_path = await pexels.search_and_download(
                        ins.search_query, out_path, settings.pexels_api_key
                    )

                if clip_path:
                    broll_clips.append((ins.insert_at, ins.duration, clip_path))

        # 6 — Render
        _update(job, JobStatus.RENDERING, 80, "Applying cuts...")
        cut_output = str(job_dir / "cut.mp4")
        await asyncio.to_thread(editor.apply_cuts, video_path, edit_plan.cuts, cut_output)

        current = cut_output

        if broll_clips:
            _update(job, JobStatus.RENDERING, 85, "Inserting B-roll...")
            broll_output = str(job_dir / "broll_out.mp4")
            await asyncio.to_thread(editor.insert_broll, current, broll_clips, broll_output)
            current = broll_output

        _update(job, JobStatus.RENDERING, 90, "Mixing background music...")
        music_path = _resolve_music(edit_plan.music)
        final_output = str(job_dir / "output.mp4")
        await asyncio.to_thread(editor.mix_music, current, music_path, edit_plan.music, final_output)

        job.output_video = f"/jobs/{job.id}/output.mp4"
        _update(job, JobStatus.DONE, 100, "Complete")

    except Exception as e:
        logger.exception("Job %s failed", job.id)
        job.error = f"{type(e).__name__}: {e}"
        _update(job, JobStatus.FAILED, job.progress_pct, f"Failed: {e}")


def _resolve_music(config: MusicConfig) -> str:
    music_dir = settings.music_dir
    for ext in (".mp3", ".wav", ".ogg", ".m4a"):
        candidate = music_dir / f"{config.track}{ext}"
        if candidate.is_file():
            return str(candidate)

    if music_dir.is_dir():
        for f in sorted(music_dir.iterdir()):
            if f.suffix.lower() in {".mp3", ".wav", ".ogg", ".m4a"}:
                return str(f)

    return str(music_dir / f"{config.track}.mp3")

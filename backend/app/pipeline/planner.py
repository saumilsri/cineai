"""LLM-backed moment breakdown and edit planning via Ollama."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.models import (
    Cut,
    EditPlan,
    Moment,
    MomentType,
    MusicConfig,
    VideoAnalysis,
)
from app.providers.ollama import OllamaProvider

logger = logging.getLogger(__name__)

_MOMENTS_SYSTEM = """You analyze video metadata and return ONLY a JSON array (no markdown, no prose).
Each element must be an object with:
- start, end: numbers (seconds, inclusive-ish ranges)
- description: short string
- energy: one of "low", "medium", "high"
- type: one of "content", "dead_air", "transition", "highlight"
Cover the full timeline. Mark pauses/silence as dead_air; scene changes as transition; peaks as highlight."""

_EDIT_PLAN_SYSTEM = """You are a video editor assistant. Return ONLY a JSON object (no markdown, no prose) with:
- cuts: array of {start, end, reason} — segments to REMOVE (seconds)
- broll_insertions: array of {insert_at, duration, search_query, source} — source usually "stock"
- music: {track, volume, fade_in, fade_out} — volume 0.0–1.0
Use the moment breakdown and the user's goals. Keep cuts within 0..duration_sec."""


def _extract_json(text: str) -> str:
    s = text.strip()
    m = re.match(r"^```(?:json)?\s*\r?\n?", s, re.IGNORECASE)
    if m:
        s = s[m.end() :]
    s = s.rstrip()
    if s.endswith("```"):
        s = s[: -3].rstrip()
    return s.strip()


def _format_transcript(analysis: VideoAnalysis) -> str:
    lines: list[str] = []
    for seg in analysis.transcript:
        lines.append(f"  [{seg.start:.2f}s – {seg.end:.2f}s] {seg.text}")
    return "\n".join(lines) if lines else "  (none)"


def _format_frames(analysis: VideoAnalysis) -> str:
    lines: list[str] = []
    for f in analysis.frame_descriptions:
        lines.append(f"  [{f.timestamp_sec:.2f}s] {f.description}")
    return "\n".join(lines) if lines else "  (none)"


def _format_scenes(analysis: VideoAnalysis) -> str:
    lines: list[str] = []
    for b in analysis.scene_boundaries:
        lines.append(f"  [{b.timestamp_sec:.2f}s] type={b.type}")
    return "\n".join(lines) if lines else "  (none)"


def _build_moments_prompt(analysis: VideoAnalysis) -> str:
    return f"""Video duration: {analysis.duration_sec:.2f} seconds

Transcript segments:
{_format_transcript(analysis)}

Frame descriptions (sampled):
{_format_frames(analysis)}

Scene boundaries:
{_format_scenes(analysis)}

Return the JSON array of moments now."""


def _moments_fallback(analysis: VideoAnalysis) -> list[Moment]:
    end = max(float(analysis.duration_sec), 0.0)
    return [
        Moment(
            start=0.0,
            end=end if end > 0.0 else 0.0,
            description="Full video (fallback: could not parse LLM moments)",
        )
    ]


async def generate_moments(
    analysis: VideoAnalysis, provider: OllamaProvider
) -> list[Moment]:
    prompt = _build_moments_prompt(analysis)
    raw = await provider.generate(prompt, system=_MOMENTS_SYSTEM)
    cleaned = _extract_json(raw)
    try:
        data: Any = json.loads(cleaned)
        if not isinstance(data, list):
            raise ValueError("LLM moments JSON must be an array")
        moments = [Moment.model_validate(item) for item in data]
        if not moments:
            logger.warning("LLM returned empty moments array; using fallback")
            return _moments_fallback(analysis)
        return moments
    except (json.JSONDecodeError, ValueError, ValidationError) as e:
        logger.warning("Failed to parse moments from LLM: %s", e)
        return _moments_fallback(analysis)


def _moments_to_json(moments: list[Moment]) -> str:
    payload = [m.model_dump(mode="json") for m in moments]
    return json.dumps(payload, indent=2)


def _build_edit_plan_prompt(
    moments: list[Moment], user_prompt: str, duration_sec: float
) -> str:
    return f"""Total duration: {duration_sec:.2f} seconds

User goals:
{user_prompt}

Moment breakdown (JSON):
{_moments_to_json(moments)}

Return the edit plan JSON object now."""


def _fallback_edit_plan_from_dead_air(moments: list[Moment]) -> EditPlan:
    cuts = [
        Cut(start=m.start, end=m.end, reason="dead_air")
        for m in moments
        if m.type == MomentType.DEAD_AIR
    ]
    return EditPlan(cuts=cuts)


async def generate_edit_plan(
    moments: list[Moment],
    user_prompt: str,
    duration_sec: float,
    provider: OllamaProvider,
) -> EditPlan:
    prompt = _build_edit_plan_prompt(moments, user_prompt, duration_sec)
    raw = await provider.generate(prompt, system=_EDIT_PLAN_SYSTEM)
    cleaned = _extract_json(raw)
    try:
        data: Any = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("LLM edit plan JSON must be an object")
        return EditPlan.model_validate(data)
    except (json.JSONDecodeError, ValueError, ValidationError) as e:
        logger.warning("Failed to parse edit plan from LLM: %s", e)
        return _fallback_edit_plan_from_dead_air(moments)

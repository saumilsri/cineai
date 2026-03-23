from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Video analysis
# ---------------------------------------------------------------------------

class FrameDescription(BaseModel):
    timestamp_sec: float
    description: str


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class SceneBoundary(BaseModel):
    timestamp_sec: float
    type: str = "cut"


class VideoAnalysis(BaseModel):
    duration_sec: float = 0.0
    frame_descriptions: list[FrameDescription] = []
    transcript: list[TranscriptSegment] = []
    scene_boundaries: list[SceneBoundary] = []


# ---------------------------------------------------------------------------
# Moment breakdown
# ---------------------------------------------------------------------------

class EnergyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MomentType(str, Enum):
    CONTENT = "content"
    DEAD_AIR = "dead_air"
    TRANSITION = "transition"
    HIGHLIGHT = "highlight"


class Moment(BaseModel):
    start: float
    end: float
    description: str
    energy: EnergyLevel = EnergyLevel.MEDIUM
    type: MomentType = MomentType.CONTENT


# ---------------------------------------------------------------------------
# Edit plan
# ---------------------------------------------------------------------------

class Cut(BaseModel):
    start: float
    end: float
    reason: str = ""


class BRollInsertion(BaseModel):
    insert_at: float
    duration: float = 3.0
    search_query: str = ""
    source: str = "stock"  # "stock" | "local"


class MusicConfig(BaseModel):
    track: str = "upbeat-chill"
    volume: float = 0.15
    fade_in: float = 2.0
    fade_out: float = 3.0


class EditPlan(BaseModel):
    cuts: list[Cut] = []
    broll_insertions: list[BRollInsertion] = []
    music: MusicConfig = MusicConfig()


# ---------------------------------------------------------------------------
# Job tracking
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    FETCHING_BROLL = "fetching_broll"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"


class Job(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: JobStatus = JobStatus.PENDING
    progress_pct: int = 0
    status_message: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    prompt: str = "Make this faster paced and more engaging"
    source_video: str = ""
    output_video: str = ""

    analysis: Optional[VideoAnalysis] = None
    moments: list[Moment] = []
    edit_plan: Optional[EditPlan] = None
    error: Optional[str] = None

    def job_dir(self, base: Path) -> Path:
        d = base / self.id
        d.mkdir(parents=True, exist_ok=True)
        return d

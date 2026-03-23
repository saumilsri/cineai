"""Video/audio extraction and scene detection via FFmpeg and PySceneDetect."""

import subprocess
import logging
from pathlib import Path

from scenedetect import ContentDetector, VideoOpenFailure, detect

logger = logging.getLogger(__name__)


def _run_ffmpeg(args: list[str], *, tool: str = "ffmpeg") -> None:
    """Run FFmpeg or ffprobe; raise RuntimeError with stderr on failure."""
    logger.debug("Running %s: %s", tool, args)
    try:
        subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        msg = stderr or str(e)
        logger.error("%s failed: %s", tool, msg)
        raise RuntimeError(f"{tool} failed: {msg}") from e


def extract_keyframes(
    video_path: str,
    output_dir: str,
    interval_sec: float = 2.0,
) -> list[tuple[float, str]]:
    """Extract one JPEG per ``interval_sec`` using FFmpeg fps filter."""
    if interval_sec <= 0:
        raise ValueError("interval_sec must be positive")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pattern = str(out / "frame_%04d.jpg")
    vf = f"fps=1/{interval_sec}"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vf",
        vf,
        pattern,
    ]
    _run_ffmpeg(cmd, tool="ffmpeg")

    frames = sorted(out.glob("frame_*.jpg"), key=lambda p: p.name)
    return [(i * interval_sec, str(p.resolve())) for i, p in enumerate(frames)]


def extract_audio(video_path: str, output_path: str) -> str:
    """Extract 16 kHz mono PCM WAV (Whisper-friendly)."""
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(dest),
    ]
    _run_ffmpeg(cmd, tool="ffmpeg")
    return str(dest.resolve())


def detect_scenes(video_path: str) -> list[float]:
    """Return timestamps (seconds) at scene cuts using ContentDetector defaults."""
    try:
        scene_list = detect(video_path, ContentDetector())
    except VideoOpenFailure as e:
        logger.error("Could not open video for scene detection: %s", e)
        raise RuntimeError(f"Scene detection failed: could not open video: {e}") from e

    # First scene starts at 0; cuts are starts of subsequent scenes.
    return [start.get_seconds() for start, _ in scene_list[1:]]


def get_video_duration(video_path: str) -> float:
    """Return container duration in seconds via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        video_path,
    ]
    logger.debug("Running ffprobe: %s", cmd)
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        msg = stderr or str(e)
        logger.error("ffprobe failed: %s", msg)
        raise RuntimeError(f"ffprobe failed: {msg}") from e

    out = (result.stdout or "").strip()
    if not out:
        raise RuntimeError("ffprobe returned no duration")
    try:
        return float(out)
    except ValueError as e:
        raise RuntimeError(f"ffprobe returned invalid duration: {out!r}") from e

"""Execute edit steps via FFmpeg: cuts, B-roll splice, and background music mix."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from app.models import BRollInsertion, Cut, EditPlan, MusicConfig

logger = logging.getLogger(__name__)


def apply_cuts(video_path: str, cuts: list[Cut], output_path: str) -> str:
    if not cuts:
        shutil.copy2(video_path, output_path)
        return output_path

    duration = _get_duration(video_path)

    sorted_cuts = sorted(cuts, key=lambda c: c.start)

    keeps: list[tuple[float, float]] = []
    pos = 0.0
    for cut in sorted_cuts:
        if cut.start > pos:
            keeps.append((pos, cut.start))
        pos = max(pos, cut.end)
    if pos < duration:
        keeps.append((pos, duration))

    if not keeps:
        raise RuntimeError("All content was cut")

    parts_v = []
    parts_a = []
    for i, (s, e) in enumerate(keeps):
        parts_v.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
        parts_a.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]")

    n = len(keeps)
    concat_in = "".join(f"[v{i}][a{i}]" for i in range(n))
    concat = f"{concat_in}concat=n={n}:v=1:a=1[outv][outa]"

    filter_complex = ";".join(parts_v + parts_a + [concat])

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-filter_complex",
        filter_complex,
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        output_path,
    ]
    _run_ffmpeg(cmd)
    return output_path


def insert_broll(
    video_path: str,
    broll_clips: list[tuple[float, float, str]],
    output_path: str,
) -> str:
    if not broll_clips:
        shutil.copy2(video_path, output_path)
        return output_path

    sorted_clips = sorted(broll_clips, key=lambda x: x[0])

    work_dir = Path(output_path).parent / "broll_work"
    work_dir.mkdir(exist_ok=True)

    duration = _get_duration(video_path)
    segments: list[str] = []
    pos = 0.0

    for i, (insert_at, broll_dur, clip_path) in enumerate(sorted_clips):
        if insert_at > pos:
            seg_path = str(work_dir / f"main_{i}.mp4")
            _extract_segment(video_path, pos, insert_at, seg_path)
            segments.append(seg_path)

        broll_seg = str(work_dir / f"broll_{i}.mp4")
        _prepare_broll_clip(clip_path, broll_dur, broll_seg, video_path)
        segments.append(broll_seg)

        pos = insert_at

    if pos < duration:
        seg_path = str(work_dir / "main_final.mp4")
        _extract_segment(video_path, pos, duration, seg_path)
        segments.append(seg_path)

    concat_file = str(work_dir / "concat.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"file '{seg}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        output_path,
    ]
    _run_ffmpeg(cmd)

    shutil.rmtree(work_dir, ignore_errors=True)
    return output_path


def mix_music(
    video_path: str,
    music_path: str,
    music_config: MusicConfig,
    output_path: str,
) -> str:
    if not Path(music_path).is_file():
        logger.warning("Music file not found: %s, skipping", music_path)
        shutil.copy2(video_path, output_path)
        return output_path

    duration = _get_duration(video_path)
    vol = music_config.volume
    fade_in = music_config.fade_in
    fade_out = music_config.fade_out
    fade_out_start = max(0.0, duration - fade_out)

    music_filter = (
        f"[1:a]volume={vol},"
        f"afade=t=in:st=0:d={fade_in},"
        f"afade=t=out:st={fade_out_start}:d={fade_out}[music];"
        f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[outa]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-stream_loop",
        "-1",
        "-i",
        music_path,
        "-filter_complex",
        music_filter,
        "-map",
        "0:v",
        "-map",
        "[outa]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        output_path,
    ]
    _run_ffmpeg(cmd)
    return output_path


def _run_ffmpeg(cmd: list[str]) -> None:
    logger.debug("FFmpeg command: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("FFmpeg stderr: %s", result.stderr)
        raise RuntimeError(f"FFmpeg failed: {result.stderr[:500]}")


def _get_duration(video_path: str) -> float:
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
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def _extract_segment(video_path: str, start: float, end: float, output_path: str) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-ss",
        str(start),
        "-to",
        str(end),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        output_path,
    ]
    _run_ffmpeg(cmd)


def _prepare_broll_clip(
    clip_path: str,
    duration: float,
    output_path: str,
    ref_video: str,
) -> None:
    """Trim and normalize broll clip to match reference video resolution."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=p=0:s=x",
        ref_video,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    resolution = result.stdout.strip()  # e.g. "1920x1080"
    if "x" not in resolution:
        raise RuntimeError(f"Could not parse reference video resolution: {resolution!r}")
    w, h = resolution.split("x", 1)

    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        clip_path,
        "-t",
        str(duration),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-an",
        output_path,
    ]
    _run_ffmpeg(cmd)

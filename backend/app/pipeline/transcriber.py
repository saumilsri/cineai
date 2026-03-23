"""Local audio transcription via faster-whisper (model cached after first load)."""

from __future__ import annotations

import logging
from pathlib import Path

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

_model: WhisperModel | None = None


def transcribe(audio_path: str, model_size: str = "base") -> list[dict[str, float | str]]:
    global _model

    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if _model is None:
        logger.info("Loading faster-whisper model %r (device=cpu, compute_type=int8)", model_size)
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, _info = _model.transcribe(str(path), beam_size=5)

    out: list[dict[str, float | str]] = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        out.append({"start": segment.start, "end": segment.end, "text": text})
    return out

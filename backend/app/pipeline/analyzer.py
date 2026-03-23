"""VLM-based keyframe analysis using Ollama LLaVA."""

import logging

from app.models import FrameDescription
from app.providers.ollama import OllamaProvider

logger = logging.getLogger(__name__)

FRAME_PROMPT = (
    "Describe what is happening in this video frame in one sentence. "
    "Note any emotions, actions, or notable objects."
)


async def analyze_frames(
    frames: list[tuple[float, str]],
    provider: OllamaProvider,
) -> list[FrameDescription]:
    """Send each keyframe to VLM and return timestamped descriptions.
    
    Args:
        frames: list of (timestamp_sec, image_path) from extractor
        provider: OllamaProvider configured with a VLM model like llava
    """
    descriptions: list[FrameDescription] = []

    for i, (ts, path) in enumerate(frames):
        logger.info("Analyzing frame %d/%d (%.1fs)", i + 1, len(frames), ts)
        try:
            text = await provider.generate_with_image(FRAME_PROMPT, path)
            descriptions.append(FrameDescription(
                timestamp_sec=ts,
                description=text.strip(),
            ))
        except Exception:
            logger.exception("Failed to analyze frame at %.1fs", ts)
            descriptions.append(FrameDescription(
                timestamp_sec=ts,
                description="[analysis failed]",
            ))

    return descriptions

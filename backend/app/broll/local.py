import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def find_clip(broll_dir: str, query: str = "") -> str | None:
    """Find a B-roll clip from a local directory. 
    
    If query is provided, tries to match filenames containing query keywords.
    Falls back to random selection if no match found.
    """
    d = Path(broll_dir)
    if not d.is_dir():
        logger.warning("B-roll directory does not exist: %s", broll_dir)
        return None

    clips = [f for f in d.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS]
    if not clips:
        logger.info("No video clips found in %s", broll_dir)
        return None

    # Try keyword matching
    if query:
        keywords = query.lower().split()
        for clip in clips:
            name = clip.stem.lower()
            if any(kw in name for kw in keywords):
                logger.info("Matched local B-roll: %s for query '%s'", clip.name, query)
                return str(clip)

    # Random fallback
    chosen = random.choice(clips)
    logger.info("Random local B-roll pick: %s", chosen.name)
    return str(chosen)

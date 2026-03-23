import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

PEXELS_VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"


async def search_and_download(
    query: str,
    output_path: str,
    api_key: str,
    duration_range: tuple[int, int] = (3, 15),
) -> str | None:
    """Search Pexels for a video matching query, download the smallest file, return path or None."""
    if not api_key:
        logger.warning("No Pexels API key configured, skipping stock B-roll")
        return None

    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 5, "size": "small"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(PEXELS_VIDEO_SEARCH_URL, headers=headers, params=params)
        if resp.status_code != 200:
            logger.error("Pexels API error: %s", resp.text)
            return None

        data = resp.json()
        videos = data.get("videos", [])
        if not videos:
            logger.info("No Pexels results for query: %s", query)
            return None

        # Pick first video, get the smallest file
        video = videos[0]
        files = video.get("video_files", [])
        if not files:
            return None

        # Sort by width (smallest first) to get a lightweight clip
        files.sort(key=lambda f: f.get("width", 9999))
        download_url = files[0]["link"]

        logger.info("Downloading B-roll from Pexels: %s", download_url)
        dl_resp = await client.get(download_url, follow_redirects=True, timeout=60.0)
        dl_resp.raise_for_status()

        out = Path(output_path)
        out.write_bytes(dl_resp.content)
        return str(out)

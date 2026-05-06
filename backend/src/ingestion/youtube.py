"""YouTube video downloader using yt-dlp."""
import os
import asyncio
from pathlib import Path
from typing import Optional, Callable
import yt_dlp
from loguru import logger


def _progress_hook(callback: Optional[Callable] = None):
    def hook(d: dict):
        if d["status"] == "downloading" and callback:
            pct = d.get("_percent_str", "0%").strip().replace("%", "")
            try:
                callback(float(pct))
            except ValueError:
                pass
    return hook


def download_video(
    url: str,
    output_dir: Path,
    session_id: str,
    progress_callback: Optional[Callable] = None,
    max_height: int = 1080,
) -> Path:
    """Download video from YouTube (or any yt-dlp-supported site).

    Returns path to downloaded MP4 file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / f"{session_id}_input.%(ext)s")

    ydl_opts = {
        "format": f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={max_height}][ext=mp4]/best",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_progress_hook(progress_callback)],
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
    }

    logger.info(f"Downloading: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "video")
        duration = info.get("duration", 0)
        logger.info(f"Downloaded: '{title}' ({duration}s)")

    output_path = output_dir / f"{session_id}_input.mp4"
    if not output_path.exists():
        # yt-dlp may use different extension
        for f in output_dir.glob(f"{session_id}_input.*"):
            output_path = f
            break

    return output_path


def get_video_info(url: str) -> dict:
    """Return metadata without downloading."""
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "title": info.get("title", ""),
            "duration": info.get("duration", 0),
            "thumbnail": info.get("thumbnail", ""),
            "channel": info.get("channel", ""),
            "view_count": info.get("view_count", 0),
            "description": info.get("description", "")[:500],
        }


async def download_video_async(
    url: str,
    output_dir: Path,
    session_id: str,
    progress_callback: Optional[Callable] = None,
) -> Path:
    """Async wrapper for download_video."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: download_video(url, output_dir, session_id, progress_callback)
    )

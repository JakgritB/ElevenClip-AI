"""YouTube video downloader using yt-dlp."""
import asyncio
import subprocess
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
        "format": (
            f"bestvideo[vcodec^=avc1][height<={max_height}]+bestaudio/"
            f"bestvideo[vcodec^=avc][height<={max_height}]+bestaudio/"
            f"bestvideo[vcodec!^=av01][height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]/best"
        ),
        "format_sort": ["vcodec:h264"],
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_progress_hook(progress_callback)],
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
        # Use iOS/Android clients to bypass datacenter IP bot-detection
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "android", "tv_embedded"],
            }
        },
    }
    _inject_cookies(ydl_opts)

    logger.info(f"Downloading: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "video")
        duration = info.get("duration", 0)
        logger.info(f"Downloaded: '{title}' ({duration}s)")

    output_path = output_dir / f"{session_id}_input.mp4"
    if not output_path.exists():
        for f in output_dir.glob(f"{session_id}_input.*"):
            output_path = f
            break

    # Safety: transcode AV1 → h264 if yt-dlp still picked it
    output_path = _ensure_h264(output_path)
    return output_path


def _ensure_h264(video_path: Path) -> Path:
    """Transcode to h264 if video codec is AV1 (not supported by PySceneDetect on this server)."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True,
    )
    codec = probe.stdout.strip().lower()
    if codec not in ("av1", "av01"):
        return video_path

    logger.warning(f"AV1 detected ({video_path.name}), transcoding to h264...")
    out = video_path.with_name(video_path.stem + "_h264.mp4")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-c:v", "libx264", "-preset", "fast",
         "-crf", "23", "-c:a", "aac", "-b:a", "128k", str(out)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        logger.info(f"Transcoded to h264: {out.name}")
        return out
    logger.error(f"Transcode failed: {result.stderr[-200:]}")
    return video_path


_COOKIES_PATH = Path("/root/cookies.txt")


def _inject_cookies(opts: dict) -> None:
    """Add cookiefile to ydl_opts if cookies.txt exists on server."""
    if _COOKIES_PATH.exists():
        opts["cookiefile"] = str(_COOKIES_PATH)
        logger.debug(f"Using cookies: {_COOKIES_PATH}")


def get_video_info(url: str) -> dict:
    """Return metadata without downloading."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extractor_args": {
            "youtube": {"player_client": ["ios", "android", "tv_embedded"]}
        },
    }
    _inject_cookies(ydl_opts)
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

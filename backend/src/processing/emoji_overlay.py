"""Emoji and text overlay utilities for HRE pipeline."""
import subprocess
from pathlib import Path
from loguru import logger


def add_emoji_overlay(
    video_path: Path,
    emoji: str,
    output_path: Path,
    x: str = "w-100",
    y: str = "50",
    size: int = 80,
    start_sec: float = 0.0,
    end_sec: float = 3.0,
) -> Path:
    """Add emoji text overlay to video using ffmpeg drawtext."""
    escaped = emoji.replace("'", "\\'").replace(":", "\\:")

    vf = (
        f"drawtext=text='{escaped}'"
        f":fontsize={size}:x={x}:y={y}"
        f":enable='between(t,{start_sec},{end_sec})'"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264", "-c:a", "copy",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and output_path.exists():
        return output_path
    logger.warning(f"Emoji overlay failed: {result.stderr[-200:]}")
    return video_path  # fallback to original

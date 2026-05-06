"""Extract video clips using ffmpeg-python."""
import asyncio
import subprocess
from pathlib import Path
from loguru import logger


def extract_clip(
    video_path: Path,
    start: float,
    end: float,
    output_path: Path,
    use_hw_encode: bool = True,
) -> Path:
    """Cut a clip from video_path between start and end seconds.

    Uses AMD AMF hardware encoder when available, falls back to libx264.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Try hardware encoding (AMD AMF/VCE) first
    encoders = ["h264_amf", "libx264"] if use_hw_encode else ["libx264"]

    for encoder in encoders:
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-to", str(end),
            "-i", str(video_path),
            "-c:v", encoder,
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            if encoder == "h264_amf":
                logger.info(f"Encoded with AMD AMF: {output_path.name}")
            return output_path
        elif encoder == "h264_amf":
            logger.debug("AMD AMF not available, falling back to libx264")

    raise RuntimeError(f"All encoders failed for clip {output_path.name}")


def burn_subtitles(
    clip_path: Path,
    ass_path: Path,
    output_path: Path,
    use_hw_encode: bool = True,
) -> Path:
    """Burn ASS subtitles into video using ffmpeg.

    Returns path to output video with burned-in subtitles.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ass_str = str(ass_path).replace("\\", "/").replace(":", "\\:")

    encoders = ["h264_amf", "libx264"] if use_hw_encode else ["libx264"]

    for encoder in encoders:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip_path),
            "-vf", f"ass='{ass_str}'",
            "-c:v", encoder,
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return output_path
        elif encoder == "h264_amf":
            logger.debug("AMD AMF burn-sub failed, using libx264")

    raise RuntimeError(f"Subtitle burn-in failed for {clip_path.name}\n{result.stderr[-500:]}")


def extract_all_clips(
    video_path: Path,
    selected_clips: list[dict],
    output_dir: Path,
    session_id: str,
) -> list[dict]:
    """Extract all selected clips from video. Returns list with added 'clip_path'."""
    results = []
    for i, clip in enumerate(selected_clips):
        out_path = output_dir / f"{session_id}_clip_{i+1:02d}_raw.mp4"
        try:
            extract_clip(video_path, clip["start"], clip["end"], out_path)
            results.append({**clip, "clip_index": i + 1, "clip_path": str(out_path)})
            logger.info(f"Extracted clip {i+1}: {clip['start']:.1f}s–{clip['end']:.1f}s → {out_path.name}")
        except Exception as e:
            logger.error(f"Failed to extract clip {i+1}: {e}")
            results.append({**clip, "clip_index": i + 1, "clip_path": None, "error": str(e)})
    return results


async def extract_all_clips_async(
    video_path: Path,
    selected_clips: list[dict],
    output_dir: Path,
    session_id: str,
) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: extract_all_clips(video_path, selected_clips, output_dir, session_id)
    )

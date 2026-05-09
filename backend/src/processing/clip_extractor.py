"""Extract video clips using ffmpeg-python."""
import asyncio
import subprocess
from pathlib import Path
from loguru import logger


def _face_center_expr(face_bbox: list | None) -> str | None:
    """Return a crop expression x-center from Qwen's normalized face bbox."""
    if not face_bbox or len(face_bbox) != 4:
        return None
    try:
        x1, _, x2, _ = [float(v) for v in face_bbox]
    except Exception:
        return None

    # Qwen prompt asks for normalized percentages. Older comments said pixels,
    # so keep a conservative pixel fallback, but prefer normalized handling.
    face_cx = (x1 + x2) / 2.0
    if max(abs(x1), abs(x2)) <= 1.5:
        face_cx = min(1.0, max(0.0, face_cx))
        return f"{face_cx:.4f}*iw-540"
    if 0 <= face_cx <= 1080:
        return f"({face_cx:.1f}/1080)*iw-540"
    return None


def extract_clip(
    video_path: Path,
    start: float,
    end: float,
    output_path: Path,
    use_hw_encode: bool = True,
    vertical: bool = True,
    face_bbox: list = None,
    **kwargs,
) -> Path:
    """Cut a clip and convert to 9:16 vertical (1080x1920) for TikTok.

    face_bbox: [x1, y1, x2, y2] in pixels from Qwen2.5-VL — used to center
    the crop on the face. Falls back to center crop when None.
    Uses AMD AMF hardware encoder when available.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    encoders = ["h264_amf", "libx264"] if use_hw_encode else ["libx264"]

    # 9:16 vertical conversion filter
    vf_filters = []
    if vertical:
        aspect_mode = kwargs.get("aspect_mode", "crop")
        if aspect_mode == "letterbox":
            # Fit entire 16:9 frame into 9:16, black bars top+bottom
            vf_filters.append(
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
            )
        else:
            # Crop: scale to 1920 height first, then center-crop to 1080 wide
            # Optionally center on face_bbox x when available
            face_expr = _face_center_expr(face_bbox)
            if face_expr:
                crop = f"scale=-1:1920,crop=1080:1920:max(0\\,min(iw-1080\\,{face_expr})):0"
            else:
                crop = "scale=-1:1920,crop=1080:1920:(iw-1080)/2:0"
            vf_filters.append(crop)

    for encoder in encoders:
        cmd = ["ffmpeg", "-y", "-ss", str(start), "-to", str(end), "-i", str(video_path)]
        if vf_filters:
            cmd += ["-vf", ",".join(vf_filters)]
        cmd += ["-c:v", encoder, "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            if encoder == "h264_amf":
                logger.info(f"Encoded 9:16 with AMD AMF: {output_path.name}")
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
    aspect_mode: str = "crop",
) -> list[dict]:
    """Extract all selected clips from video. Returns list with added 'clip_path'."""
    results = []
    for i, clip in enumerate(selected_clips):
        out_path = output_dir / f"{session_id}_clip_{i+1:02d}_raw.mp4"
        face_bbox = clip.get("vision_analysis", {}).get("face_bbox")
        try:
            extract_clip(video_path, clip["start"], clip["end"], out_path, face_bbox=face_bbox, aspect_mode=aspect_mode)
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
    aspect_mode: str = "crop",
) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: extract_all_clips(video_path, selected_clips, output_dir, session_id, aspect_mode)
    )

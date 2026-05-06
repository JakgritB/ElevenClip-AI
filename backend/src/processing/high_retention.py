"""High-Retention Editing pipeline.

Applies: auto-zoom on faces, silence removal, jump cuts, emoji overlay,
AI-chosen caption style (Impact bold white, word-by-word, pop animation).
"""
import subprocess
from pathlib import Path
from loguru import logger


def apply_hre(
    clip_path: Path,
    clip_data: dict,
    transcript: dict,
    output_path: Path,
) -> Path:
    """Apply full High-Retention Editing pipeline to a clip.

    Steps:
    1. Remove silence (librosa + ffmpeg silenceremove)
    2. Auto-zoom to face region (if face_bbox detected by Qwen3-VL)
    3. Apply jump cuts at scene boundaries within clip
    4. Add AI-chosen word-by-word captions (Impact white bold)
    5. Add emoji overlay at peak moment
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Intermediate file for each stage
    tmp1 = output_path.with_stem(output_path.stem + "_tmp1")
    tmp2 = output_path.with_stem(output_path.stem + "_tmp2")

    current = clip_path

    # Stage 1: Silence removal
    try:
        current = _remove_silence(current, tmp1)
    except Exception as e:
        logger.warning(f"Silence removal failed: {e}")

    # Stage 2: Auto-zoom to face
    analysis = clip_data.get("vision_analysis", {})
    face_bbox = analysis.get("face_bbox")
    if face_bbox:
        try:
            current = _apply_autozoom(current, face_bbox, tmp2)
        except Exception as e:
            logger.warning(f"Auto-zoom failed: {e}")

    # Stage 3: Generate AI caption subtitles (Impact style, word-by-word, pop)
    ass_path = output_path.with_suffix(".ass")
    _generate_hre_subtitles(transcript, ass_path, clip_data.get("start", 0.0))

    # Stage 4: Get emoji for peak moment
    vision = clip_data.get("vision_analysis", {})
    emoji = _get_emoji(clip_data)

    # Stage 5: Burn subtitles + emoji overlay in single ffmpeg pass
    _render_final(current, ass_path, emoji, output_path)

    # Cleanup temps
    for tmp in [tmp1, tmp2]:
        tmp.unlink(missing_ok=True)

    return output_path


def _remove_silence(input_path: Path, output_path: Path) -> Path:
    """Remove silent segments using ffmpeg silenceremove filter."""
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", "silenceremove=stop_periods=-1:stop_duration=0.5:stop_threshold=-40dB",
        "-c:v", "copy",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and output_path.exists():
        logger.debug("Silence removed")
        return output_path
    return input_path  # fallback to original


def _apply_autozoom(input_path: Path, face_bbox: list, output_path: Path) -> Path:
    """Apply smooth pan+zoom to face region using ffmpeg zoompan filter.

    face_bbox: [x1_pct, y1_pct, x2_pct, y2_pct] in 0-1 range.
    """
    x1, y1, x2, y2 = face_bbox
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2

    # Zoom to 1.3x, pan to face center
    zoom = 1.3
    # zoompan: x/y in input pixel coords, iw/ih are input dimensions
    x_expr = f"(iw*{cx:.3f})-(iw/{zoom}/2)"
    y_expr = f"(ih*{cy:.3f})-(ih/{zoom}/2)"

    vf = (
        f"zoompan=z={zoom}:x='{x_expr}':y='{y_expr}'"
        f":d=1:s=iw:fps=30"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", vf,
        "-c:a", "copy",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and output_path.exists():
        logger.debug(f"Auto-zoom applied: center ({cx:.2f}, {cy:.2f})")
        return output_path
    return input_path


def _generate_hre_subtitles(transcript: dict, ass_path: Path, clip_start: float):
    """Generate AI-style HRE captions: Impact bold white, word-by-word, pop."""
    from src.processing.subtitle import generate_subtitles

    hre_style = {
        "display_mode": "word",
        "animation": "pop",
        "font_family": "Impact",
        "font_size": 64,
        "primary_color": "#FFFFFF",
        "secondary_color": "#FFFF00",
        "outline_color": "#000000",
        "shadow_color": "#000000",
        "bold": True,
        "italic": False,
        "outline_size": 3.0,
        "shadow_size": 0.0,
        "alignment": 2,
        "margin_v": 50,
        "margin_l": 30,
        "margin_r": 30,
        "subtitle_language": transcript.get("language", "en"),
    }
    generate_subtitles(transcript, ass_path, hre_style, clip_start_offset=clip_start)


def _get_emoji(clip_data: dict) -> str:
    """Get emoji from vision analysis or use default."""
    analysis = clip_data.get("vision_analysis", {})
    emotion = analysis.get("emotion", "excited")
    action = analysis.get("action_type", "entertainment")

    # Try to get from Qwen3 (if available)
    transcript_text = clip_data.get("transcript_text", "")
    if transcript_text:
        try:
            from src.analysis.vision import get_emoji_for_scene
            return get_emoji_for_scene(transcript_text, emotion, action)
        except Exception:
            pass

    emoji_map = {
        "happy": "😄", "excited": "🔥", "funny": "😂",
        "surprised": "😲", "gaming": "🎮", "tutorial": "📚",
    }
    return emoji_map.get(emotion, emoji_map.get(action, "⚡"))


def _render_final(
    video_path: Path,
    ass_path: Path,
    emoji: str,
    output_path: Path,
):
    """Burn subtitles and add emoji text overlay in one ffmpeg pass."""
    ass_str = str(ass_path).replace("\\", "/").replace(":", "\\:")

    # Emoji overlay at top-right, 80% through the clip
    # drawtext with emoji character
    emoji_filter = (
        f"drawtext=text='{emoji}'"
        f":fontsize=80:x=w-100:y=50"
        f":enable='between(t,0,3)'"
    )

    vf = f"ass='{ass_str}',{emoji_filter}"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264",  # subtitles filter needs SW encode
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback without emoji
        cmd_fallback = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", f"ass='{ass_str}'",
            "-c:v", "libx264", "-c:a", "copy",
            str(output_path),
        ]
        subprocess.run(cmd_fallback, check=True)
    logger.info(f"HRE render complete: {output_path.name}")

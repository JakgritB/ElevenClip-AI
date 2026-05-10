"""Extract video clips using ffmpeg-python."""
import asyncio
import subprocess
from pathlib import Path
from loguru import logger


ANALYSIS_FRAME_WIDTH = 640.0


def _normalise_bbox(face_bbox: list | None) -> list[float] | None:
    if not face_bbox or len(face_bbox) != 4:
        return None
    try:
        coords = [float(v) for v in face_bbox]
    except Exception:
        return None
    if max(abs(v) for v in coords) > 1.5:
        # Legacy pixel fallback is handled by _face_center_expr.
        return None
    x1, y1, x2, y2 = coords
    x1, x2 = sorted((min(1.0, max(0.0, x1)), min(1.0, max(0.0, x2))))
    y1, y2 = sorted((min(1.0, max(0.0, y1)), min(1.0, max(0.0, y2))))
    if x2 - x1 < 0.02 or y2 - y1 < 0.02:
        return None
    return [x1, y1, x2, y2]


def _outer_subject_x(x1: float, x2: float) -> float:
    """Aim toward the face side when a person box covers torso/background too."""
    center = (x1 + x2) / 2.0
    width = x2 - x1
    if width < 0.18:
        return center
    if center > 0.54 or x2 > 0.64:
        return x1 * 0.32 + x2 * 0.68
    if center < 0.46 or x1 < 0.36:
        return x1 * 0.68 + x2 * 0.32
    return center


def _detect_face_bbox(video_path: Path, start: float, end: float) -> list[float] | None:
    """Detect a real face in sampled source frames before the 9:16 crop.

    Qwen's scene-level bbox can focus on the product/screen instead of the
    presenter. A lightweight OpenCV pass gives the cropper a concrete face
    target when there is a person in frame.
    """
    try:
        import cv2
    except Exception as exc:
        logger.debug(f"OpenCV face crop skipped: {exc}")
        return None

    cascade_paths = [
        Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml",
        Path(cv2.data.haarcascades) / "haarcascade_profileface.xml",
    ]
    cascades = [cv2.CascadeClassifier(str(p)) for p in cascade_paths if p.exists()]
    cascades = [c for c in cascades if not c.empty()]
    if not cascades:
        return None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    duration = max(0.2, float(end) - float(start))
    sample_times = [
        float(start) + duration * r
        for r in (0.12, 0.25, 0.40, 0.55, 0.72, 0.88)
    ]
    best_bbox: list[float] | None = None
    best_score = 0.0

    try:
        for t in sample_times:
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            fh, fw = frame.shape[:2]
            if fw <= 0 or fh <= 0:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            candidates: list[tuple[int, int, int, int]] = []

            for cascade in cascades:
                faces = cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.08,
                    minNeighbors=4,
                    minSize=(max(36, fw // 40), max(36, fh // 40)),
                )
                candidates.extend(tuple(map(int, face)) for face in faces)

                flipped = cv2.flip(gray, 1)
                flipped_faces = cascade.detectMultiScale(
                    flipped,
                    scaleFactor=1.08,
                    minNeighbors=4,
                    minSize=(max(36, fw // 40), max(36, fh // 40)),
                )
                for x, y, w, h in flipped_faces:
                    candidates.append((fw - int(x) - int(w), int(y), int(w), int(h)))

            for x, y, w, h in candidates:
                area = w * h
                if area <= 0:
                    continue
                face_cx = (x + w / 2) / fw
                face_cy = (y + h / 2) / fh
                # Prefer speaker-size faces, avoid tiny false positives near corners.
                centrality = 1.0 - min(0.6, abs(face_cy - 0.36))
                score = area * centrality
                if score > best_score:
                    pad_x = w * 0.28
                    pad_y = h * 0.40
                    best_bbox = [
                        max(0.0, (x - pad_x) / fw),
                        max(0.0, (y - pad_y) / fh),
                        min(1.0, (x + w + pad_x) / fw),
                        min(1.0, (y + h + pad_y) / fh),
                    ]
                    best_score = score
    finally:
        cap.release()

    if best_bbox:
        logger.info(
            "OpenCV face crop target: "
            f"x={((best_bbox[0] + best_bbox[2]) / 2):.2f} "
            f"y={((best_bbox[1] + best_bbox[3]) / 2):.2f}"
        )
    return best_bbox


def _face_center_expr(face_bbox: list | None, bias_outer: bool = False) -> str | None:
    """Return a crop expression x-center from Qwen's normalized face bbox."""
    if not face_bbox or len(face_bbox) != 4:
        return None
    try:
        x1, _, x2, _ = [float(v) for v in face_bbox]
    except Exception:
        return None

    # Qwen is prompted for normalized values, but often returns pixel boxes from
    # the 640px analysis frames. Treat those as 640-wide before falling back.
    if max(abs(x1), abs(x2)) <= 1.5:
        x1, x2 = sorted((min(1.0, max(0.0, x1)), min(1.0, max(0.0, x2))))
        face_cx = _outer_subject_x(x1, x2) if bias_outer else (x1 + x2) / 2.0
        return f"{face_cx:.4f}*iw-540"
    if 0 <= x1 <= ANALYSIS_FRAME_WIDTH * 1.25 and 0 <= x2 <= ANALYSIS_FRAME_WIDTH * 1.25:
        x1, x2 = sorted((x1 / ANALYSIS_FRAME_WIDTH, x2 / ANALYSIS_FRAME_WIDTH))
        x1, x2 = min(1.0, max(0.0, x1)), min(1.0, max(0.0, x2))
        face_cx = _outer_subject_x(x1, x2)
        return f"{face_cx:.4f}*iw-540"
    return None


def _safe_fit_filter() -> str:
    """Keep the full source frame visible on a blurred 9:16 background."""
    return (
        "[0:v]split=2[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=luma_radius=28:luma_power=1,"
        "eq=brightness=-0.08:saturation=0.85[bg];"
        "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[vout]"
    )


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

    face_bbox: [x1, y1, x2, y2] normalized from Qwen2.5-VL. Before cropping,
    the extractor samples real frames and prefers an OpenCV face box so a
    presenter stays visible even when Qwen focused on a product or screen.
    Uses AMD AMF hardware encoder when available.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    encoders = ["h264_amf", "libx264"] if use_hw_encode else ["libx264"]

    # 9:16 vertical conversion filter
    vf_filters = []
    filter_complex = None
    if vertical:
        aspect_mode = kwargs.get("aspect_mode", "crop")
        if aspect_mode == "safe_fit":
            filter_complex = _safe_fit_filter()
        elif aspect_mode == "letterbox":
            # Fit entire 16:9 frame into 9:16, black bars top+bottom
            vf_filters.append(
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
            )
        else:
            # Crop: scale to 1920 height first, then center-crop to 1080 wide
            # Center on a detected real face first, then Qwen's face bbox.
            detected_face_bbox = _detect_face_bbox(video_path, start, end)
            if detected_face_bbox:
                face_expr = _face_center_expr(detected_face_bbox)
            else:
                normalized_bbox = _normalise_bbox(face_bbox)
                face_expr = (
                    _face_center_expr(normalized_bbox)
                    or _face_center_expr(face_bbox, bias_outer=True)
                )
            if face_expr:
                crop = f"scale=-1:1920,crop=1080:1920:max(0\\,min(iw-1080\\,{face_expr})):0"
            else:
                crop = "scale=-1:1920,crop=1080:1920:(iw-1080)/2:0"
            vf_filters.append(crop)

    for encoder in encoders:
        cmd = ["ffmpeg", "-y", "-ss", str(start), "-to", str(end), "-i", str(video_path)]
        if filter_complex:
            cmd += ["-filter_complex", filter_complex, "-map", "[vout]", "-map", "0:a?"]
        elif vf_filters:
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

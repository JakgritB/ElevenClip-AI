"""High-Retention Editing pipeline — per-segment AI decisions.

Each 3-5s segment gets its own zoom direction, subtitle position,
subtitle mode, and caption color driven by Qwen2.5-VL analyzing one
frame plus the local transcript for that segment.

Pipeline per clip:
  1. Segment clip at speech pauses (3-5s chunks)
  2. Extract midpoint frame from each segment
  3. Qwen2.5-VL analyzes each frame → zoom + subtitle decisions
  4. ffmpeg filter_complex: per-segment zoompan + concat
  5. ASS subtitles with per-segment alignment/color/mode override tags
"""
import json
import subprocess
import tempfile
from pathlib import Path
from loguru import logger


# ─── Video metadata ────────────────────────────────────────────────────────────

def _probe_dimensions(video_path: Path) -> tuple[int, int]:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0",
         str(video_path)],
        capture_output=True, text=True,
    )
    try:
        w, h = map(int, probe.stdout.strip().split(","))
        return w, h
    except Exception:
        return 1080, 1920


def _probe_duration(video_path: Path) -> float:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True,
    )
    try:
        return float(probe.stdout.strip())
    except Exception:
        return 0.0


def _has_audio_stream(video_path: Path) -> bool:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0",
         str(video_path)],
        capture_output=True, text=True,
    )
    return bool(probe.stdout.strip())


# ─── Segmentation ─────────────────────────────────────────────────────────────

def _segment_clip(
    duration: float,
    transcript: dict,
    clip_start: float,
    max_seg: float = 4.5,
) -> list[dict]:
    """Divide clip into segments at speech pauses, max_seg seconds each."""
    words: list[dict] = []
    for seg in transcript.get("segments", []):
        words.extend(seg.get("words", []))

    if clip_start > 0:
        words = [
            {**w, "start": max(0.0, w["start"] - clip_start),
                  "end":   max(0.0, w["end"]   - clip_start)}
            for w in words
        ]
    words = [w for w in words if w["end"] > 0 and w["start"] < duration]

    # Collect pause midpoints as candidate cut times
    cuts = [0.0]
    for i in range(len(words) - 1):
        gap = words[i + 1]["start"] - words[i]["end"]
        if gap > 0.2:
            cuts.append((words[i]["end"] + words[i + 1]["start"]) / 2.0)
    cuts.append(duration)
    cuts = sorted(set(cuts))

    # Merge short intervals, split long ones
    segs: list[dict] = []
    start = 0.0
    for cut in cuts[1:]:
        seg_len = cut - start
        if seg_len < 1.5 and cut < duration:
            continue  # too short — extend to next cut
        if seg_len > max_seg:
            t = start
            while t + max_seg < cut:
                segs.append({"start": t, "end": t + max_seg})
                t += max_seg
            if cut - t > 0.5:
                segs.append({"start": t, "end": cut})
            start = cut
        else:
            segs.append({"start": start, "end": cut})
            start = cut

    # Fallback: split evenly if not enough segments
    if len(segs) < 2:
        n = max(2, round(duration / 4.0))
        d = duration / n
        segs = [{"start": i * d, "end": min((i + 1) * d, duration)} for i in range(n)]

    return segs


# ─── Frame extraction ─────────────────────────────────────────────────────────

def _extract_frame(video_path: Path, t: float, out_path: Path) -> bool:
    cmd = [
        "ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(video_path),
        "-vframes", "1", "-q:v", "3", str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    return result.returncode == 0 and out_path.exists()


def _extract_segment_frames(video_path: Path, seg: dict, seg_idx: int, tmp_dir: Path) -> list[Path]:
    """Extract a few representative frames so HRE decisions see motion, not one random still."""
    start = float(seg["start"])
    end = float(seg["end"])
    duration = max(0.1, end - start)
    times = [
        start + duration * 0.25,
        start + duration * 0.50,
        start + duration * 0.75,
    ]
    frames: list[Path] = []
    for j, t in enumerate(times):
        frame_path = tmp_dir / f"seg_{seg_idx:03d}_{j}.jpg"
        if _extract_frame(video_path, min(max(start, t), max(start, end - 0.05)), frame_path):
            frames.append(frame_path)
    return frames


def _detect_face_bbox_in_image(image_path: Path) -> list[float] | None:
    """Detect a human face in one frame and return a normalized padded bbox."""
    try:
        import cv2
    except Exception:
        return None

    image = cv2.imread(str(image_path))
    if image is None:
        return None

    fh, fw = image.shape[:2]
    if fw <= 0 or fh <= 0:
        return None

    cascade_paths = [
        Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml",
        Path(cv2.data.haarcascades) / "haarcascade_profileface.xml",
    ]
    cascades = [cv2.CascadeClassifier(str(p)) for p in cascade_paths if p.exists()]
    cascades = [c for c in cascades if not c.empty()]
    if not cascades:
        return None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    candidates: list[tuple[int, int, int, int]] = []
    min_size = (max(34, fw // 46), max(34, fh // 46))

    for cascade in cascades:
        faces = cascade.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=4,
            minSize=min_size,
        )
        candidates.extend(tuple(map(int, face)) for face in faces)

        flipped = cv2.flip(gray, 1)
        flipped_faces = cascade.detectMultiScale(
            flipped,
            scaleFactor=1.08,
            minNeighbors=4,
            minSize=min_size,
        )
        for x, y, w, h in flipped_faces:
            candidates.append((fw - int(x) - int(w), int(y), int(w), int(h)))

    best: tuple[int, int, int, int] | None = None
    best_score = 0.0
    for x, y, w, h in candidates:
        area = w * h
        if area <= 0:
            continue
        face_cy = (y + h / 2) / fh
        centrality = 1.0 - min(0.55, abs(face_cy - 0.38))
        score = area * centrality
        if score > best_score:
            best = (x, y, w, h)
            best_score = score

    if not best:
        return None

    x, y, w, h = best
    pad_x = w * 0.34
    pad_y_top = h * 0.46
    pad_y_bottom = h * 0.70
    return [
        max(0.0, (x - pad_x) / fw),
        max(0.0, (y - pad_y_top) / fh),
        min(1.0, (x + w + pad_x) / fw),
        min(1.0, (y + h + pad_y_bottom) / fh),
    ]


def _detect_segment_face_bbox(frame_paths: list[Path]) -> list[float] | None:
    """Pick the strongest face box across the sampled frames for a segment."""
    best_bbox: list[float] | None = None
    best_area = 0.0
    for frame_path in frame_paths:
        bbox = _detect_face_bbox_in_image(frame_path)
        if not bbox:
            continue
        area = max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
        if area > best_area:
            best_bbox = bbox
            best_area = area

    if best_bbox:
        logger.info(
            "HRE face zoom target: "
            f"x={((best_bbox[0] + best_bbox[2]) / 2):.2f} "
            f"y={((best_bbox[1] + best_bbox[3]) / 2):.2f}"
        )
    return best_bbox


def _apply_detected_face_override(analysis: dict, face_bbox: list[float] | None) -> dict:
    if not face_bbox:
        return analysis
    x1, y1, x2, y2 = face_bbox
    face_cx = (x1 + x2) / 2.0
    face_cy = (y1 + y2) / 2.0
    return {
        **analysis,
        "face_detected": True,
        "subject_bbox": face_bbox,
        "face_cx": face_cx,
        "face_cy": face_cy,
        "zoom_anchor_x": face_cx,
        "zoom_anchor_y": face_cy,
    }


# ─── Per-segment AI analysis ──────────────────────────────────────────────────

def _analyze_segment(
    video_path: Path,
    seg: dict,
    seg_idx: int,
    n_total: int,
    transcript: dict,
    clip_start: float,
    tmp_dir: Path,
) -> dict:
    from src.analysis.vision import analyze_frames_for_hre, _default_hre_analysis

    frame_paths = _extract_segment_frames(video_path, seg, seg_idx, tmp_dir)
    if not frame_paths:
        return _default_hre_analysis(seg_idx, n_total)

    words_all: list[dict] = []
    for s in transcript.get("segments", []):
        words_all.extend(s.get("words", []))

    abs_start = seg["start"] + clip_start
    abs_end   = seg["end"]   + clip_start
    context = " ".join(
        w.get("word", w.get("text", ""))
        for w in words_all
        if w.get("start", 0) < abs_end and w.get("end", 0) > abs_start
    ).strip()

    analysis = analyze_frames_for_hre(frame_paths, context, seg_idx, n_total)
    return _apply_detected_face_override(analysis, _detect_segment_face_bbox(frame_paths))


# ─── Zoom expression builders ─────────────────────────────────────────────────

def _build_zoom_exprs(
    analysis: dict,
    w: int,
    h: int,
) -> tuple[str, str, str]:
    """Return (z_expr, x_expr, y_expr) for ffmpeg zoompan from HRE analysis.
    Note: \\, escapes comma inside ffmpeg filter expressions.
    """
    direction     = analysis.get("zoom_direction", "in")
    speed         = analysis.get("zoom_speed", "slow")
    zoom_anchor_x = _clamp_float(analysis.get("zoom_anchor_x"), _clamp_float(analysis.get("face_cx"), 0.5))
    zoom_anchor_y = _clamp_float(analysis.get("zoom_anchor_y"), _clamp_float(analysis.get("face_cy"), 0.38))

    if direction == "in":
        if speed == "fast":
            z_expr, max_zoom = "min(1.0+on*0.0100\\,1.45)", 1.45
        else:
            z_expr, max_zoom = "min(1.0+on*0.0035\\,1.28)", 1.28
    elif direction == "out":
        if speed == "fast":
            z_expr, max_zoom = "max(1.45-on*0.0100\\,1.0)", 1.45
        else:
            z_expr, max_zoom = "max(1.28-on*0.0040\\,1.0)", 1.28
    else:  # hold
        z_expr, max_zoom = "1.08", 1.08

    if direction == "in" and max_zoom > 1.05:
        x_expr = f"max(0\\,min(iw-iw/zoom\\,iw*{zoom_anchor_x:.3f}-iw/zoom/2))"
        y_expr = f"max(0\\,min(ih-ih/zoom\\,ih*{zoom_anchor_y:.3f}-ih/zoom/2))"
    else:
        x_expr = "iw/2-(iw/zoom/2)"
        if direction == "in":
            y_bias = min(zoom_anchor_y, 0.5) if zoom_anchor_y < 0.55 else 0.38
            y_expr = f"max(0\\,min(ih-ih/zoom\\,ih*{y_bias:.2f}-(ih/zoom/2)))"
        else:
            y_expr = "ih/2-(ih/zoom/2)"

    return z_expr, x_expr, y_expr


# ─── Per-segment zoom via filter_complex ──────────────────────────────────────

def _apply_per_segment_zoom(
    input_path: Path,
    segments: list[dict],
    analyses: list[dict],
    w: int,
    h: int,
    output_path: Path,
    has_audio: bool = True,
) -> Path:
    """Apply different zoompan to each segment, concat into single stream."""
    filter_parts: list[str] = []
    v_labels: list[str] = []
    a_labels: list[str] = []

    for i, (seg, analysis) in enumerate(zip(segments, analyses)):
        s = f"{seg['start']:.3f}"
        e = f"{seg['end']:.3f}"
        z, x, y = _build_zoom_exprs(analysis, w, h)
        zp = f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={w}x{h}:fps=30"
        filter_parts.append(
            f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS,fps=30,{zp},setpts=PTS-STARTPTS[v{i}]"
        )
        v_labels.append(f"[v{i}]")
        if has_audio:
            filter_parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]")
            a_labels.append(f"[a{i}]")

    n = len(segments)
    filter_parts.append("".join(v_labels) + f"concat=n={n}:v=1:a=0[vout]")
    if has_audio:
        filter_parts.append("".join(a_labels) + f"concat=n={n}:v=0:a=1[aout]")

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter_complex", ";".join(filter_parts),
        "-map", "[vout]",
    ]
    if has_audio:
        cmd += ["-map", "[aout]", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-movflags", "+faststart", str(output_path)]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode == 0 and output_path.exists():
        logger.info(f"Per-segment zoom: {n} segments, {w}x{h}")
        return output_path
    logger.warning(f"Per-segment zoom failed: {result.stderr[-800:]}")
    return input_path


# ─── Per-segment ASS subtitles ────────────────────────────────────────────────

_ASS_COLORS = {
    "white":  "&H00FFFFFF",
    "yellow": "&H0000FFFF",
    "cyan":   "&H00FFFF00",
    "orange": "&H000066FF",
    "green":  "&H0000FF00",
    "red":    "&H000000FF",
}

_POSITIONS = {"top", "bottom", "left", "right", "center", "free"}
_MODES = {"word", "phrase", "sentence"}
_EMPHASIS = {"pop", "punch", "calm"}
_ANCHORS = set(range(1, 10))


def _ts(t: float) -> str:
    total_cs = max(0, int(round(t * 100)))
    h = total_cs // 360000
    total_cs %= 360000
    m = total_cs // 6000
    total_cs %= 6000
    s = total_cs // 100
    cs = total_cs % 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _pick(value: object, allowed: set[str], fallback: str) -> str:
    v = str(value or "").strip().lower()
    return v if v in allowed else fallback


def _clamp_float(value: object, fallback: float, low: float = 0.0, high: float = 1.0) -> float:
    try:
        return min(high, max(low, float(value)))
    except Exception:
        return fallback


def _clamp_int(value: object, fallback: int, allowed: set[int]) -> int:
    try:
        v = int(value)
    except Exception:
        return fallback
    return v if v in allowed else fallback


def _normalise_bbox(value: object) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        coords = [float(v) for v in value]
    except Exception:
        return None
    if max(abs(v) for v in coords) > 1.5:
        return None
    x1, y1, x2, y2 = coords
    x1, x2 = sorted((min(1.0, max(0.0, x1)), min(1.0, max(0.0, x2))))
    y1, y2 = sorted((min(1.0, max(0.0, y1)), min(1.0, max(0.0, y2))))
    if x2 - x1 < 0.02 or y2 - y1 < 0.02:
        return None
    return [x1, y1, x2, y2]


def _caption_anchor_for(x: float, y: float) -> int:
    if y < 0.34:
        return 8 if 0.30 <= x <= 0.70 else 7 if x < 0.5 else 9
    if y > 0.66:
        return 2 if 0.30 <= x <= 0.70 else 1 if x < 0.5 else 3
    return 5 if 0.34 <= x <= 0.66 else 4 if x < 0.5 else 6


def _safe_caption_point(subject_x: float, subject_y: float, seg_idx: int) -> tuple[float, float, int]:
    """Pick a varied but readable empty-ish zone opposite the main subject."""
    left_side = subject_x < 0.50
    high_subject = subject_y < 0.42
    low_subject = subject_y > 0.62

    candidates = [
        (0.68 if left_side else 0.32, 0.72 if high_subject else 0.24 if low_subject else 0.76),
        (0.72 if left_side else 0.28, 0.50),
        (0.50, 0.18 if subject_y > 0.45 else 0.82),
        (0.50, 0.72),
    ]
    x, y = candidates[seg_idx % len(candidates)]
    return x, y, _caption_anchor_for(x, y)


def _word_caption_point(subject_x: float, subject_y: float, seg_idx: int) -> tuple[float, float, int]:
    """Put highlight words in punchy mid-frame zones instead of ordinary subtitle zones."""
    candidates = [
        (0.50, 0.42),
        (0.50, 0.26),
        (0.28 if subject_x > 0.55 else 0.72, 0.46),
        (0.30 if subject_x > 0.50 else 0.70, 0.58),
    ]
    x, y = candidates[seg_idx % len(candidates)]
    if abs(x - subject_x) < 0.18 and abs(y - subject_y) < 0.18:
        x = 0.25 if subject_x > 0.5 else 0.75
    return x, y, _caption_anchor_for(x, y)


def _normalise_analysis(analysis: dict, seg_idx: int, n_total: int) -> dict:
    """Validate model output and fill HRE fields used by the renderer."""
    an = dict(analysis or {})
    subject_bbox = _normalise_bbox(an.get("subject_bbox"))
    energy = _pick(an.get("energy_level"), {"high", "medium", "low"}, "medium")
    moment = _pick(
        an.get("moment_type"),
        {"hook", "punchline", "context", "reaction", "transition"},
        "context",
    )

    fallback_mode = "word" if energy == "high" or moment in {"hook", "punchline", "reaction"} else "sentence"
    if energy == "medium" and moment not in {"context", "transition"}:
        fallback_mode = "phrase"

    if subject_bbox:
        subject_x = (subject_bbox[0] + subject_bbox[2]) / 2.0
        subject_y = (subject_bbox[1] + subject_bbox[3]) / 2.0
    else:
        subject_x = _clamp_float(an.get("face_cx"), 0.5)
        subject_y = _clamp_float(an.get("face_cy"), 0.38)

    pos = _pick(an.get("subtitle_position"), _POSITIONS, "free")
    mode = _pick(an.get("subtitle_mode"), _MODES, fallback_mode)
    emphasis = _pick(an.get("subtitle_emphasis"), _EMPHASIS, "punch" if mode == "word" else "calm")
    color = _pick(an.get("subtitle_color"), set(_ASS_COLORS), "white")
    zoom_direction = _pick(an.get("zoom_direction"), {"in", "out", "hold"}, "in")
    zoom_speed = _pick(an.get("zoom_speed"), {"fast", "slow"}, "slow")

    face_cx = _clamp_float(an.get("face_cx"), subject_x)
    face_cy = _clamp_float(an.get("face_cy"), subject_y)
    zoom_anchor_x = _clamp_float(an.get("zoom_anchor_x"), face_cx)
    zoom_anchor_y = _clamp_float(an.get("zoom_anchor_y"), face_cy)

    fallback_x, fallback_y, fallback_anchor = _safe_caption_point(subject_x, subject_y, seg_idx)
    caption_x = _clamp_float(an.get("caption_x"), fallback_x, 0.10, 0.90)
    caption_y = _clamp_float(an.get("caption_y"), fallback_y, 0.12, 0.88)
    caption_anchor = _clamp_int(an.get("caption_anchor"), fallback_anchor, _ANCHORS)
    caption_max_width_pct = _clamp_float(
        an.get("caption_max_width_pct"),
        0.58 if mode != "sentence" else 0.72,
        0.35,
        0.82,
    )

    if mode == "sentence":
        caption_x = 0.50
        caption_y = _clamp_float(an.get("caption_y"), 0.70, 0.64, 0.74)
        caption_anchor = 2
        caption_max_width_pct = max(caption_max_width_pct, 0.68)
    elif mode == "word":
        word_x, word_y, word_anchor = _word_caption_point(subject_x, subject_y, seg_idx)
        if caption_y > 0.66 or (abs(caption_x - subject_x) < 0.14 and abs(caption_y - subject_y) < 0.14):
            caption_x, caption_y, caption_anchor = word_x, word_y, word_anchor
        caption_max_width_pct = min(caption_max_width_pct, 0.56)

    if subject_bbox:
        x1, y1, x2, y2 = subject_bbox
        overlaps_subject = (x1 - 0.08) <= caption_x <= (x2 + 0.08) and (y1 - 0.08) <= caption_y <= (y2 + 0.08)
        if overlaps_subject:
            if mode == "sentence":
                caption_x, caption_y, caption_anchor = 0.50, 0.70, 2
            elif mode == "word":
                caption_x, caption_y, caption_anchor = _word_caption_point(subject_x, subject_y, seg_idx + 1)
            else:
                caption_x, caption_y, caption_anchor = fallback_x, fallback_y, fallback_anchor

    if seg_idx == 0:
        zoom_direction, zoom_speed = "in", "fast"
        if mode == "sentence":
            mode = "word"
        if emphasis == "calm":
            emphasis = "punch"

    if mode == "word" or moment in {"hook", "punchline", "reaction"}:
        zoom_direction = "in"
        zoom_speed = "fast" if energy == "high" else "slow"
        emphasis = "punch" if emphasis == "calm" else emphasis
    elif mode == "sentence" and moment in {"context", "transition"}:
        zoom_direction = "hold"
        zoom_speed = "slow"
        emphasis = "calm"

    return {
        **an,
        "zoom_direction": zoom_direction,
        "zoom_speed": zoom_speed,
        "face_detected": bool(an.get("face_detected", False)),
        "face_cx": face_cx,
        "face_cy": face_cy,
        "subject_bbox": subject_bbox,
        "zoom_anchor_x": zoom_anchor_x,
        "zoom_anchor_y": zoom_anchor_y,
        "subtitle_position": pos,
        "caption_x": caption_x,
        "caption_y": caption_y,
        "caption_anchor": caption_anchor,
        "caption_max_width_pct": caption_max_width_pct,
        "subtitle_mode": mode,
        "subtitle_emphasis": emphasis,
        "subtitle_color": color,
        "energy_level": energy,
        "moment_type": moment,
    }


def _build_hre_plan(segments: list[dict], analyses: list[dict]) -> list[dict]:
    plan = []
    n_total = len(segments)
    for i, (seg, analysis) in enumerate(zip(segments, analyses)):
        an = _normalise_analysis(analysis, i, n_total)
        plan.append({**an, "segment_index": i, "start": seg["start"], "end": seg["end"]})

    # If the model repeats the same caption treatment for every segment, rotate
    # through safe defaults so HRE visibly changes across the clip.
    if len(plan) > 1 and len({(round(p["caption_x"], 2), round(p["caption_y"], 2), p["subtitle_mode"]) for p in plan}) == 1:
        positions = ["free", "free", "free", "free", "free", "free"]
        coords = [(0.50, 0.76), (0.50, 0.18), (0.28, 0.56), (0.72, 0.52), (0.50, 0.82), (0.50, 0.22)]
        modes = ["word", "sentence", "phrase", "word", "sentence", "phrase"]
        for i, p in enumerate(plan):
            p["subtitle_position"] = positions[i % len(positions)]
            p["caption_x"], p["caption_y"] = coords[i % len(coords)]
            p["caption_anchor"] = _caption_anchor_for(p["caption_x"], p["caption_y"])
            p["subtitle_mode"] = modes[i % len(modes)]
            if p["subtitle_mode"] == "word":
                p["subtitle_emphasis"] = "punch"

    return plan


def _ass_escape(text: str) -> str:
    return (
        text.replace("{", "(")
        .replace("}", ")")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )


def _wrap_text(text: str, max_chars: int) -> str:
    text = _ass_escape(text)
    if len(text) <= max_chars:
        return text

    words = text.split()
    if len(words) <= 1:
        return r"\N".join(text[i:i + max_chars] for i in range(0, len(text), max_chars))

    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and len(candidate) > max_chars:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)

    if len(lines) <= 2:
        return r"\N".join(lines)
    return r"\N".join([lines[0], " ".join(lines[1:])])


def _collect_clip_words(transcript: dict, clip_start: float, duration: float) -> list[dict]:
    words: list[dict] = []
    for seg in transcript.get("segments", []):
        seg_start = float(seg.get("start", clip_start)) - clip_start
        seg_end = float(seg.get("end", clip_start)) - clip_start
        for word in seg.get("words", []):
            text = str(word.get("word", word.get("text", ""))).strip()
            if not text:
                continue
            start = float(word.get("start", seg_start + clip_start)) - clip_start
            end = float(word.get("end", word.get("start", seg_end + clip_start))) - clip_start
            if end <= start:
                end = start + 0.24
            if end <= 0 or start >= duration:
                continue
            words.append({
                "start": max(0.0, start),
                "end": min(duration, end),
                "text": text,
            })
    return sorted(words, key=lambda w: (w["start"], w["end"]))


def _segment_text(transcript: dict, clip_start: float, seg: dict) -> str:
    parts: list[str] = []
    for item in transcript.get("segments", []):
        start = float(item.get("start", clip_start)) - clip_start
        end = float(item.get("end", clip_start)) - clip_start
        if start < seg["end"] and end > seg["start"]:
            text = str(item.get("text", "")).strip()
            if text:
                parts.append(text)
    return " ".join(parts).strip()


def _words_in_segment(words: list[dict], seg: dict) -> list[dict]:
    return [
        w for w in words
        if w["start"] < seg["end"] and w["end"] > seg["start"]
    ]


def _display_text(text: str, mode: str, emphasis: str) -> str:
    text = text.strip()
    if mode == "sentence" and emphasis == "calm":
        return text
    return text.upper()


def _append_event(events: list[dict], start: float, end: float, text: str, plan: dict) -> None:
    start = max(float(plan["start"]), start)
    end = min(float(plan["end"]), end)
    if end - start < 0.08 or not text.strip():
        return
    events.append({
        "start": start,
        "end": end,
        "text": text.strip(),
        "plan": plan,
    })


def _word_events(words: list[dict], seg: dict, plan: dict) -> list[dict]:
    events: list[dict] = []
    cursor = seg["start"]
    min_d = 0.14 if plan["energy_level"] == "high" else 0.18
    max_d = 0.72 if plan["energy_level"] == "high" else 0.95

    for i, word in enumerate(words):
        start = max(seg["start"], word["start"], cursor)
        next_start = words[i + 1]["start"] if i + 1 < len(words) else seg["end"]
        natural_end = max(word["end"], start + min_d)
        end = min(seg["end"], natural_end, start + max_d)
        if next_start > start:
            end = min(end, max(start + min_d, next_start - 0.015))
        if end <= start:
            end = min(seg["end"], start + min_d)

        _append_event(events, start, end, word["text"], plan)
        cursor = end + 0.015
        if cursor >= seg["end"]:
            break

    return events


def _line_events(
    words: list[dict],
    seg: dict,
    plan: dict,
    max_words: int,
    max_duration: float,
    max_chars: int,
) -> list[dict]:
    events: list[dict] = []
    i = 0
    cursor = seg["start"]

    while i < len(words) and cursor < seg["end"] - 0.08:
        group: list[dict] = []
        start = max(seg["start"], words[i]["start"], cursor)
        end = start
        chars = 0

        while i < len(words):
            word = words[i]
            proposed_end = min(seg["end"], max(word["end"], word["start"] + 0.2))
            proposed_chars = chars + len(word["text"]) + (1 if group else 0)
            if group and (
                len(group) >= max_words
                or proposed_end - start > max_duration
                or proposed_chars > max_chars
            ):
                break
            group.append(word)
            chars = proposed_chars
            end = max(end, proposed_end)
            i += 1

        if not group:
            i += 1
            continue

        end = min(seg["end"], max(end, start + 0.55))
        text = " ".join(w["text"] for w in group)
        _append_event(events, start, end, text, plan)
        cursor = end + 0.04

    return events


def _fallback_text_events(text: str, seg: dict, plan: dict) -> list[dict]:
    if not text:
        return []

    mode = plan["subtitle_mode"]
    if mode == "word":
        chunk_size = 1
    elif mode == "phrase":
        chunk_size = 3
    else:
        chunk_size = 7

    units = text.split()
    if len(units) <= 1 and len(text) > 20:
        step = 10 if mode == "word" else 24 if mode == "phrase" else 36
        units = [text[i:i + step] for i in range(0, len(text), step)]

    chunks = [" ".join(units[i:i + chunk_size]) for i in range(0, len(units), chunk_size)]
    chunks = [c for c in chunks if c.strip()]
    if not chunks:
        return []

    events: list[dict] = []
    seg_d = max(0.1, seg["end"] - seg["start"])
    dur = seg_d / len(chunks)
    for i, chunk in enumerate(chunks):
        start = seg["start"] + i * dur
        end = seg["start"] + (i + 1) * dur
        _append_event(events, start, end, chunk, plan)
    return events


def _build_subtitle_events(
    transcript: dict,
    clip_start: float,
    duration: float,
    segments: list[dict],
    plan: list[dict],
) -> list[dict]:
    words = _collect_clip_words(transcript, clip_start, duration)
    events: list[dict] = []

    for seg, seg_plan in zip(segments, plan):
        seg_words = _words_in_segment(words, seg)
        mode = seg_plan["subtitle_mode"]

        if seg_words and mode == "word":
            seg_events = _word_events(seg_words, seg, seg_plan)
        elif seg_words and mode == "phrase":
            seg_events = _line_events(seg_words, seg, seg_plan, max_words=3, max_duration=1.7, max_chars=28)
        elif seg_words:
            seg_events = _line_events(seg_words, seg, seg_plan, max_words=7, max_duration=2.8, max_chars=44)
        else:
            seg_events = []

        if not seg_events:
            seg_events = _fallback_text_events(_segment_text(transcript, clip_start, seg), seg, seg_plan)
        events.extend(seg_events)

    events = sorted(events, key=lambda ev: (ev["start"], ev["end"]))

    # ASS draws all active events at once; keep one visible caption event at a
    # time so word/phrase/sentence modes never stack on top of each other.
    cleaned: list[dict] = []
    cursor = 0.0
    for ev in events:
        start = max(ev["start"], cursor)
        end = min(duration, ev["end"])
        if end - start < 0.08:
            continue
        cleaned.append({**ev, "start": start, "end": end})
        cursor = end + 0.01
    return cleaned


def _subtitle_tag(plan: dict) -> tuple[str, int]:
    mode = plan["subtitle_mode"]
    energy = plan["energy_level"]
    emphasis = plan["subtitle_emphasis"]
    color = _ASS_COLORS.get(plan["subtitle_color"], "&H00FFFFFF")
    alignment = int(plan.get("caption_anchor", 5))
    x = round(_clamp_float(plan.get("caption_x"), 0.5, 0.08, 0.92) * 1080)
    y = round(_clamp_float(plan.get("caption_y"), 0.75, 0.10, 0.90) * 1920)
    max_width_px = max(360, min(886, int(_clamp_float(plan.get("caption_max_width_pct"), 0.62, 0.35, 0.82) * 1080)))

    if mode == "sentence":
        font_size = 54 if energy != "high" else 60
    elif mode == "phrase":
        font_size = 68 if energy != "low" else 62
    else:
        font_size = 96 if energy == "high" else 84

    if alignment in {4, 5, 6}:
        font_size = max(54, font_size - 4)

    max_chars = max(8, min(34, int(max_width_px / (font_size * 0.58))))

    base = (
        f"{{\\an{alignment}\\pos({x},{y})\\1c{color}&\\fs{font_size}"
        "\\b1\\bord5\\shad1\\q2\\fad(30,70)}"
    )
    if emphasis == "punch" or mode == "word":
        base += "{\\fscx132\\fscy132\\frz-2\\t(0,140,\\fscx100\\fscy100\\frz0)}"
    elif emphasis == "pop":
        base += "{\\fscx118\\fscy118\\t(0,120,\\fscx100\\fscy100)}"
    return base, max_chars


def _generate_per_segment_subtitles(
    transcript: dict,
    ass_path: Path,
    clip_start: float,
    segments: list[dict],
    analyses: list[dict],
) -> None:
    """Write one ASS file from the HRE plan.

    The important rule is that HRE can change style every segment, but it must
    never emit simultaneous caption events at the same timestamp.
    """
    duration = max((float(seg["end"]) for seg in segments), default=0.0)
    plan = _build_hre_plan(segments, analyses)
    events = _build_subtitle_events(transcript, clip_start, duration, segments, plan)

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Noto Sans,82,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,"
        "-1,0,0,0,100,100,0,0,1,5,1,2,40,40,200,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for ev in events:
        seg_plan = ev["plan"]
        tag, max_chars = _subtitle_tag(seg_plan)
        text = _display_text(ev["text"], seg_plan["subtitle_mode"], seg_plan["subtitle_emphasis"])
        text = _wrap_text(text, max_chars)

        lines.append(
            f"Dialogue: 0,{_ts(ev['start'])},{_ts(ev['end'])},"
            f"Default,,0,0,0,,{tag}{text}"
        )

    ass_path.write_text("\n".join(lines), encoding="utf-8")
    plan_path = ass_path.with_suffix(".hre_plan.json")
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug(f"ASS: {len(events)} events across {len(segments)} HRE segments")


# ─── Emoji ─────────────────────────────────────────────────────────────────────

def _get_emoji(clip_data: dict, analyses: list[dict] | None = None) -> str:
    if analyses:
        energy_rank = {"high": 3, "medium": 2, "low": 1}
        best = max(analyses, key=lambda a: energy_rank.get(a.get("energy_level", "low"), 1))
        moment_emoji = {
            "hook": "🔥", "punchline": "😂", "reaction": "😲",
            "context": "💡", "transition": "✨",
        }
        if emoji := moment_emoji.get(best.get("moment_type", "")):
            return emoji

    a = clip_data.get("vision_analysis", {})
    emotion = a.get("emotion", "excited")
    action  = a.get("action_type", "entertainment")
    transcript_text = clip_data.get("transcript_text", "")
    if transcript_text:
        try:
            from src.analysis.vision import get_emoji_for_scene
            return get_emoji_for_scene(transcript_text, emotion, action)
        except Exception:
            pass

    fb = {"happy": "😄", "excited": "🔥", "funny": "😂", "surprised": "😲",
          "gaming": "🎮", "tutorial": "📚", "angry": "😤", "sad": "😢"}
    return fb.get(emotion, fb.get(action, "⚡"))


# ─── Final render ─────────────────────────────────────────────────────────────

def _render_final(
    video_path: Path,
    ass_path: Path,
    emoji: str,
    output_path: Path,
) -> None:
    ass_str = str(ass_path).replace("\\", "/").replace(":", "\\:")
    emoji_filter = (
        f"drawtext=text='{emoji}':fontsize=80:x=w-100:y=50"
        f":enable='between(t\\,0\\,3)'"
    )
    vf = f"ass='{ass_str}',{emoji_filter}"

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", vf, "-c:v", "libx264", "-c:a", "copy",
        "-movflags", "+faststart", str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        cmd2 = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", f"ass='{ass_str}'",
            "-c:v", "libx264", "-c:a", "copy", str(output_path),
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=300)
        if result2.returncode != 0:
            logger.error(f"HRE render failed: {result2.stderr[-300:]}")
            return
    logger.info(f"HRE render complete → {output_path.name}")


# ─── Main pipeline ────────────────────────────────────────────────────────────

def apply_hre(
    clip_path: Path,
    clip_data: dict,
    transcript: dict,
    output_path: Path,
) -> Path:
    """Apply per-segment AI-driven HRE with varied zoom and caption plans."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clip_start = clip_data.get("start", 0.0)

    with tempfile.TemporaryDirectory() as _tmp:
        tmp_dir    = Path(_tmp)
        tmp_zoomed = tmp_dir / "zoomed.mp4"

        w, h      = _probe_dimensions(clip_path)
        duration  = _probe_duration(clip_path)
        if duration <= 0:
            duration = float(clip_data.get("end", clip_start + 30)) - clip_start
        has_audio = _has_audio_stream(clip_path)

        # 1. Segment at speech pauses
        segments = _segment_clip(duration, transcript, clip_start)
        n = len(segments)
        logger.info(
            f"HRE clip {clip_data.get('index', '?')}: "
            f"{duration:.1f}s → {n} segments (AI analyzing each)"
        )

        # 2. Qwen2.5-VL analyzes each segment
        analyses = [
            _analyze_segment(clip_path, seg, i, n, transcript, clip_start, tmp_dir)
            for i, seg in enumerate(segments)
        ]
        plan = _build_hre_plan(segments, analyses)

        for i, (seg, an) in enumerate(zip(segments, plan)):
            logger.info(
                f"  [{seg['start']:.1f}s-{seg['end']:.1f}s] "
                f"zoom={an.get('zoom_direction')}({an.get('zoom_speed')}) "
                f"sub={an.get('subtitle_position')}/{an.get('subtitle_mode')}/"
                f"{an.get('subtitle_color')} "
                f"type={an.get('moment_type')} energy={an.get('energy_level')}"
            )

        # 3. Per-segment zoom via filter_complex
        zoomed = _apply_per_segment_zoom(
            clip_path, segments, plan, w, h, tmp_zoomed, has_audio=has_audio
        )

        # 4. Per-segment ASS subtitles
        ass_path = output_path.with_suffix(".ass")
        _generate_per_segment_subtitles(transcript, ass_path, clip_start, segments, plan)

        # 5. Emoji from highest-energy segment
        emoji = _get_emoji(clip_data, plan)

        # 6. Render
        _render_final(zoomed, ass_path, emoji, output_path)

    return output_path

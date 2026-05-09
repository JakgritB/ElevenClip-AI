"""High-Retention Editing pipeline — per-segment AI decisions.

Each 3-5s segment gets its own zoom direction, subtitle position,
and caption color driven by Qwen2.5-VL analyzing one frame per segment.

Pipeline per clip:
  1. Segment clip at speech pauses (3-5s chunks)
  2. Extract midpoint frame from each segment
  3. Qwen2.5-VL analyzes each frame → zoom + subtitle decisions
  4. ffmpeg filter_complex: per-segment zoompan + concat
  5. ASS subtitles with per-segment alignment/color/size override tags
"""
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
    from src.analysis.vision import analyze_frame_for_hre, _default_hre_analysis

    mid_t = (seg["start"] + seg["end"]) / 2.0
    frame_path = tmp_dir / f"seg_{seg_idx:03d}.jpg"

    if not _extract_frame(video_path, mid_t, frame_path):
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

    return analyze_frame_for_hre(frame_path, context, seg_idx, n_total)


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
    face_detected = bool(analysis.get("face_detected", False))
    face_cx       = float(analysis.get("face_cx") or 0.5)
    face_cy       = float(analysis.get("face_cy") or 0.38)

    if direction == "in":
        if speed == "fast":
            z_expr, max_zoom = "min(1.2+n*0.0014\\,1.6)", 1.6
        else:
            z_expr, max_zoom = "min(1.05+n*0.0006\\,1.35)", 1.35
    elif direction == "out":
        if speed == "fast":
            z_expr, max_zoom = "max(1.6-n*0.0016\\,1.0)", 1.6
        else:
            z_expr, max_zoom = "max(1.4-n*0.0010\\,1.0)", 1.4
    else:  # hold
        z_expr, max_zoom = "1.1", 1.1

    if face_detected and direction == "in" and max_zoom > 1.05:
        raw_cx = int(face_cx * w - w / (max_zoom * 2))
        raw_cy = int(face_cy * h - h / (max_zoom * 2))
        safe_cx = max(0, min(w - int(w / max_zoom), raw_cx))
        safe_cy = max(0, min(h - int(h / max_zoom), raw_cy))
        ctr_x = w / 2 - w / (max_zoom * 2)
        ctr_y = h / 2 - h / (max_zoom * 2)
        x_expr = (
            f"(iw/2-(iw/zoom/2))+({safe_cx}-{ctr_x:.1f})*(zoom-1)/({max_zoom}-1)"
        )
        y_expr = (
            f"(ih/2-(ih/zoom/2))+({safe_cy}-{ctr_y:.1f})*(zoom-1)/({max_zoom}-1)"
        )
    else:
        x_expr = "iw/2-(iw/zoom/2)"
        if direction == "in":
            y_bias = min(face_cy, 0.5) if face_cy < 0.55 else 0.38
            y_expr = f"ih*{y_bias:.2f}-(ih/zoom/2)"
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
        filter_parts.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS,{zp}[v{i}]")
        v_labels.append(f"[v{i}]")
        if has_audio:
            filter_parts.append(f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS[a{i}]")
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


def _ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:06.3f}"


def _generate_per_segment_subtitles(
    transcript: dict,
    ass_path: Path,
    clip_start: float,
    segments: list[dict],
    analyses: list[dict],
) -> None:
    """Write ASS with per-segment alignment, color, and font-size overrides."""
    events: list[dict] = []

    # Word-level events
    for seg in transcript.get("segments", []):
        for w in seg.get("words", []):
            t0 = max(0.0, float(w.get("start", 0)) - clip_start)
            t1 = max(0.0, float(w.get("end",   0)) - clip_start)
            text = w.get("word", w.get("text", "")).strip()
            if text and t1 > 0:
                events.append({"start": t0, "end": max(t1, t0 + 0.08), "text": text})

    # Sentence-level fallback (split into 3-word chunks)
    if not events:
        for seg in transcript.get("segments", []):
            t0 = max(0.0, float(seg.get("start", 0)) - clip_start)
            t1 = max(0.0, float(seg.get("end",   0)) - clip_start)
            text = seg.get("text", "").strip()
            if not text or t1 <= 0:
                continue
            wlist = text.split()
            chunk = 3
            n_ch = max(1, (len(wlist) + chunk - 1) // chunk)
            dur = (t1 - t0) / n_ch
            for j in range(n_ch):
                events.append({
                    "start": t0 + j * dur,
                    "end":   t0 + (j + 1) * dur,
                    "text":  " ".join(wlist[j * chunk:(j + 1) * chunk]),
                })

    def get_an(t: float) -> dict:
        for seg, an in zip(segments, analyses):
            if seg["start"] <= t < seg["end"]:
                return an
        return analyses[-1] if analyses else {}

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
        "Style: Default,Impact,90,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,"
        "-1,0,0,0,100,100,0,0,1,4,0,2,40,40,200,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for ev in events:
        an      = get_an(ev["start"])
        color   = _ASS_COLORS.get(an.get("subtitle_color", "white"), "&H00FFFFFF")
        pos     = an.get("subtitle_position", "bottom")
        energy  = an.get("energy_level", "medium")
        moment  = an.get("moment_type", "context")

        alignment = 8 if pos == "top" else 2
        margin_v  = 120 if pos == "top" else 200
        fs = (108 if energy == "high" or moment in ("hook", "punchline")
              else 80 if energy == "low" else 92)

        # Pop animation: start 130% scale, shrink to 100% in 120ms
        pop = "{\\fscx130\\fscy130\\t(0,120,\\fscx100\\fscy100)}"
        tag = f"{{\\an{alignment}\\1c{color}&\\fs{fs}\\b1}}{pop}"

        lines.append(
            f"Dialogue: 0,{_ts(ev['start'])},{_ts(ev['end'])},"
            f"Default,,0,0,{margin_v},,{tag}{ev['text'].upper()}"
        )

    ass_path.write_text("\n".join(lines), encoding="utf-8")
    logger.debug(f"ASS: {len(events)} events across {len(segments)} segments")


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
    """Apply per-segment AI-driven HRE: each 3-5s chunk gets its own zoom + subtitle style."""
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

        for i, (seg, an) in enumerate(zip(segments, analyses)):
            logger.info(
                f"  [{seg['start']:.1f}s-{seg['end']:.1f}s] "
                f"zoom={an.get('zoom_direction')}({an.get('zoom_speed')}) "
                f"sub={an.get('subtitle_position')}/{an.get('subtitle_color')} "
                f"type={an.get('moment_type')} energy={an.get('energy_level')}"
            )

        # 3. Per-segment zoom via filter_complex
        zoomed = _apply_per_segment_zoom(
            clip_path, segments, analyses, w, h, tmp_zoomed, has_audio=has_audio
        )

        # 4. Per-segment ASS subtitles
        ass_path = output_path.with_suffix(".ass")
        _generate_per_segment_subtitles(transcript, ass_path, clip_start, segments, analyses)

        # 5. Emoji from highest-energy segment
        emoji = _get_emoji(clip_data, analyses)

        # 6. Render
        _render_final(zoomed, ass_path, emoji, output_path)

    return output_path

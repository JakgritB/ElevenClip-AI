"""Generate ASS subtitles using pysubs2.

Supports: word-by-word, sentence, karaoke, fade, pop, typewriter animations.
Full ASS spec: font, size, 4-color layers, border, shadow, position, alignment.
Handles Thai/Chinese character-level splitting.
"""
from pathlib import Path
from typing import Optional
import re
import pysubs2
from pysubs2 import SSAFile, SSAEvent, SSAStyle
from loguru import logger

# Languages that split by character rather than word
CHAR_LEVEL_LANGUAGES = {"th", "zh", "ja", "km", "lo"}

# Default font per language
DEFAULT_FONTS = {
    "th": "Noto Sans Thai",
    "zh": "Noto Sans SC",
    "zh-tw": "Noto Sans TC",
    "ja": "Noto Sans JP",
    "ko": "Noto Sans KR",
    "en": "Montserrat",
    "default": "Noto Sans",
}

# Animation presets (ASS override tags)
def _fade_tags(fade_in_ms: int = 200, fade_out_ms: int = 200) -> str:
    return f"{{\\fade({fade_in_ms},{fade_out_ms})}}"

def _pop_tags() -> str:
    return "{\\t(0,100,\\fscx120\\fscy120)\\t(100,200,\\fscx100\\fscy100)}"

def _typewriter_per_char(char: str, delay_ms: int) -> str:
    return f"{{\\alpha&HFF&\\t({delay_ms},{delay_ms+80},\\alpha&H00&)}}{char}"

def _bounce_tags() -> str:
    return "{\\t(0,150,\\frz-5)\\t(150,300,\\frz5)\\t(300,400,\\frz0)}"


def _color_to_ass(hex_color: str, alpha: int = 0) -> str:
    """Convert #RRGGBB hex to ASS &HAABBGGRR format."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    else:
        r, g, b = "FF", "FF", "FF"
    aa = f"{alpha:02X}"
    return f"&H{aa}{b}{g}{r}"


def build_style(
    font_family: str = "Noto Sans",
    font_size: int = 72,
    primary_color: str = "#FFFFFF",
    secondary_color: str = "#FFFF00",
    outline_color: str = "#000000",
    shadow_color: str = "#000000",
    primary_alpha: int = 0,
    outline_alpha: int = 0,
    shadow_alpha: int = 80,
    bold: bool = True,
    italic: bool = False,
    underline: bool = False,
    outline_size: float = 4.0,
    shadow_size: float = 2.0,
    alignment: int = 2,  # 2=bottom-center, 8=top-center
    margin_l: int = 40,
    margin_r: int = 40,
    margin_v: int = 250,
    scale_x: int = 100,
    scale_y: int = 100,
    spacing: float = 0.0,
    angle: float = 0.0,
) -> SSAStyle:
    style = SSAStyle()
    style.fontname = font_family
    style.fontsize = font_size
    style.primarycolor = pysubs2.Color(*_hex_to_rgba(primary_color, primary_alpha))
    style.secondarycolor = pysubs2.Color(*_hex_to_rgba(secondary_color, 0))
    style.outlinecolor = pysubs2.Color(*_hex_to_rgba(outline_color, outline_alpha))
    style.backcolor = pysubs2.Color(*_hex_to_rgba(shadow_color, shadow_alpha))
    style.bold = bold
    style.italic = italic
    style.underline = underline
    style.outline = outline_size
    style.shadow = shadow_size
    style.alignment = alignment
    style.marginl = margin_l
    style.marginr = margin_r
    style.marginv = margin_v
    style.scalex = scale_x
    style.scaley = scale_y
    style.spacing = spacing
    style.angle = angle
    style.borderstyle = 1  # outline + shadow
    return style


def _hex_to_rgba(hex_color: str, alpha_0_255: int = 0):
    """Convert #RRGGBB to (R, G, B, A) where A=0 is opaque."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    else:
        r, g, b = 255, 255, 255
    return r, g, b, alpha_0_255


def generate_subtitles(
    transcript: dict,
    output_path: Path,
    style_config: dict,
    clip_start_offset: float = 0.0,
    clip_end_offset: Optional[float] = None,
) -> Path:
    """Generate .ass subtitle file from transcript.

    Args:
        transcript: Output from whisper.py
        output_path: Where to save the .ass file
        style_config: Dict with font/color/animation settings from frontend
        clip_start_offset: Shift all timestamps (for sub-clips from longer video)
        clip_end_offset: Optional absolute end timestamp for clipping events
    """
    subs = SSAFile()
    subs.info["PlayResX"] = "1080"
    subs.info["PlayResY"] = "1920"
    subs.info["ScaledBorderAndShadow"] = "yes"
    subs.info["WrapStyle"] = "0"

    display_mode = style_config.get("display_mode", "word")  # "word" or "sentence"
    animation = style_config.get("animation", "none")  # none|fade|karaoke|pop|typewriter|bounce
    subtitle_lang = style_config.get("subtitle_language", "en")
    char_level = transcript.get("char_level", False) or subtitle_lang in CHAR_LEVEL_LANGUAGES

    font_family = style_config.get("font_family") or DEFAULT_FONTS.get(subtitle_lang, DEFAULT_FONTS["default"])

    style = build_style(
        font_family=font_family,
        font_size=style_config.get("font_size", 72),
        primary_color=style_config.get("primary_color", "#FFFFFF"),
        secondary_color=style_config.get("secondary_color", "#FFFF00"),
        outline_color=style_config.get("outline_color", "#000000"),
        shadow_color=style_config.get("shadow_color", "#000000"),
        primary_alpha=style_config.get("primary_alpha", 0),
        outline_alpha=style_config.get("outline_alpha", 0),
        shadow_alpha=style_config.get("shadow_alpha", 80),
        bold=style_config.get("bold", True),
        italic=style_config.get("italic", False),
        underline=style_config.get("underline", False),
        outline_size=style_config.get("outline_size", 4.0),
        shadow_size=style_config.get("shadow_size", 2.0),
        alignment=style_config.get("alignment", 2),
        margin_l=style_config.get("margin_l", 40),
        margin_r=style_config.get("margin_r", 40),
        margin_v=style_config.get("margin_v", 250),
        scale_x=style_config.get("scale_x", 100),
        scale_y=style_config.get("scale_y", 100),
        spacing=style_config.get("spacing", 0.0),
        angle=style_config.get("angle", 0.0),
    )
    subs.styles["Default"] = style

    segments = transcript.get("segments", [])

    clip_duration = None
    if clip_end_offset is not None:
        clip_duration = max(0.1, clip_end_offset - clip_start_offset)

    for seg in segments:
        words = seg.get("words", [])
        seg_end = seg["end"] - clip_start_offset
        if seg_end <= 0:
            continue  # segment ends before clip starts — skip entirely

        seg_start = max(0.0, seg["start"] - clip_start_offset)
        if clip_duration is not None:
            if seg_start >= clip_duration:
                continue
            seg_end = min(seg_end, clip_duration)

        if display_mode == "sentence" or not words:
            _add_text_events(subs, seg["text"], seg_start, seg_end, animation, style_config, display_mode)
        else:
            if animation == "karaoke":
                _add_karaoke_line(subs, words, seg_start, seg_end, clip_start_offset, char_level)
            else:
                before = len(subs)
                _add_word_events(subs, words, seg_start, seg_end, animation, char_level, style_config, clip_start_offset)
                if len(subs) == before:
                    _add_text_events(subs, seg["text"], seg_start, seg_end, animation, style_config, display_mode)

    if len(subs) == 0 and transcript.get("text"):
        fallback_end = clip_duration if clip_duration is not None else 30.0
        _add_text_events(subs, transcript["text"], 0.0, fallback_end, animation, style_config, display_mode)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    subs.save(str(output_path), encoding="utf-8")
    logger.info(f"Generated {len(subs)} subtitle events → {output_path.name}")
    return output_path


def _add_sentence_event(subs, text, start, end, animation, style_config):
    text = text.strip()
    if not text or end <= start:
        return
    tags = ""
    if animation == "fade":
        fi = style_config.get("fade_in_ms", 200)
        fo = style_config.get("fade_out_ms", 200)
        tags = _fade_tags(fi, fo)
    elif animation == "pop":
        tags = _pop_tags()
    elif animation == "bounce":
        tags = _bounce_tags()

    event = SSAEvent(
        start=pysubs2.make_time(s=start),
        end=pysubs2.make_time(s=end),
        text=tags + text,
    )
    subs.append(event)


def _split_text_chunks(text: str, max_words: int, max_chars: int) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []

    chunks: list[str] = []
    sentences = re.split(r"(?<=[.!?。！？])\s+", text)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        words = sentence.split()
        if not words:
            chunks.extend(sentence[i:i + max_chars].strip() for i in range(0, len(sentence), max_chars))
            continue

        current: list[str] = []
        for word in words:
            candidate = " ".join([*current, word])
            if current and (len(current) >= max_words or len(candidate) > max_chars):
                chunks.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            chunks.append(" ".join(current))

    return [chunk for chunk in chunks if chunk]


def _merge_chunks_to_count(chunks: list[str], target_count: int) -> list[str]:
    """Merge adjacent chunks so fallback subtitles fit the available time."""
    if target_count <= 0 or len(chunks) <= target_count:
        return chunks

    total_chars = sum(len(chunk) for chunk in chunks) + max(0, len(chunks) - 1)
    target_chars = max(1, int(total_chars / target_count + 0.5))
    merged: list[str] = []
    cursor = 0

    while cursor < len(chunks) and len(merged) < target_count:
        slots_left_after_this = target_count - len(merged) - 1
        current = [chunks[cursor]]
        cursor += 1

        while cursor < len(chunks) and (len(chunks) - cursor) > slots_left_after_this:
            candidate = " ".join([*current, chunks[cursor]])
            if len(candidate) > target_chars and current:
                break
            current.append(chunks[cursor])
            cursor += 1

        merged.append(" ".join(current))

    if cursor < len(chunks):
        merged[-1] = " ".join([merged[-1], *chunks[cursor:]])

    return merged


def _add_text_events(subs, text, start, end, animation, style_config, display_mode):
    """Fallback for transcript segments without word timestamps.

    Keep normal subtitles readable by splitting long transcript text into
    short timed chunks instead of showing a whole paragraph at once.
    """
    if end <= start:
        return

    if display_mode == "word":
        chunks = _split_text_chunks(text, max_words=3, max_chars=28)
    else:
        chunks = _split_text_chunks(text, max_words=8, max_chars=48)

    if not chunks:
        return

    duration = end - start
    min_slot = 0.55 if display_mode == "word" else 1.10
    max_events = max(1, int(duration / min_slot))
    chunks = _merge_chunks_to_count(chunks, max_events)

    slot = duration / len(chunks)
    if len(chunks) == 1:
        event_len = min(duration, 3.2 if display_mode == "word" else 4.0)
    else:
        event_len = max(0.35, min(slot - 0.06, 3.0 if display_mode == "word" else 3.8))

    for i, chunk in enumerate(chunks):
        ev_start = start + slot * i
        next_start = start + slot * (i + 1) if i < len(chunks) - 1 else end
        ev_end = min(end, next_start - 0.04, ev_start + event_len)
        if ev_end <= ev_start:
            continue
        _add_sentence_event(subs, chunk, ev_start, ev_end, animation, style_config)


def _add_word_events(subs, words, seg_start, seg_end, animation, char_level, style_config, clip_offset=0.0):
    """Add one SSAEvent per word (word-by-word mode)."""
    unit_list = []
    for w in words:
        if char_level:
            for ch in w["word"]:
                unit_list.append({"word": ch, "start": w["start"], "end": w["end"], "synthetic": w.get("synthetic", False)})
        else:
            unit_list.append(w)

    if any(unit.get("synthetic") for unit in unit_list):
        _add_grouped_word_events(subs, unit_list, seg_end, animation, style_config, clip_offset)
        return

    for i, unit in enumerate(unit_list):
        start = unit["start"] - clip_offset
        end = (unit["end"] - clip_offset) if unit["end"] > unit["start"] else start + 0.3
        if end <= 0 or start >= seg_end:
            continue
        start = max(0.0, start)
        end = min(seg_end, max(start + 0.25, end))

        tags = ""
        if animation == "fade":
            fi = style_config.get("fade_in_ms", 150)
            fo = style_config.get("fade_out_ms", 100)
            tags = _fade_tags(fi, fo)
        elif animation == "pop":
            tags = _pop_tags()
        elif animation == "typewriter":
            delay = int((start - seg_start) * 1000)
            tags = _typewriter_per_char("", delay)

        event = SSAEvent(
            start=pysubs2.make_time(s=start),
            end=pysubs2.make_time(s=end),
            text=tags + unit["word"].strip(),
        )
        subs.append(event)


def _add_grouped_word_events(subs, units, seg_end, animation, style_config, clip_offset=0.0):
    """Use short phrase events for estimated timestamps so captions stay readable."""
    i = 0
    while i < len(units):
        unit = units[i]
        start = unit["start"] - clip_offset
        if start >= seg_end:
            break
        if (unit["end"] - clip_offset) <= 0:
            i += 1
            continue

        start = max(0.0, start)
        group = []
        end = start

        while i < len(units):
            unit = units[i]
            unit_start = unit["start"] - clip_offset
            unit_end = (unit["end"] - clip_offset) if unit["end"] > unit["start"] else unit_start + 0.25
            if unit_end <= 0:
                i += 1
                continue
            if unit_start >= seg_end:
                break

            word = unit["word"].strip()
            candidate = " ".join([*group, word])
            candidate_end = min(seg_end, max(unit_end, start + 0.45))

            if group and (len(group) >= 3 or len(candidate) > 30 or candidate_end - start > 1.35):
                break

            group.append(word)
            end = candidate_end
            i += 1

        if not group:
            i += 1
            continue

        _add_sentence_event(subs, " ".join(group), start, end, animation, style_config)


def _strip_ass_tags(text: str) -> str:
    """Remove ASS override tags before sending editable text to the UI."""
    return re.sub(r"\{[^{}]*\}", "", text).strip()


def subtitle_events_from_ass(ass_path: Path) -> list[dict]:
    """Return subtitle events in seconds for the editor timeline."""
    if not ass_path.exists():
        return []

    subs = SSAFile.load(str(ass_path))
    events = []
    for idx, event in enumerate(subs):
        text = _strip_ass_tags(event.text)
        if not text:
            continue
        events.append({
            "index": idx,
            "text": text,
            "start": round(event.start / 1000, 3),
            "end": round(event.end / 1000, 3),
        })
    return events


def normalize_subtitle_timing(ass_path: Path, gap_ms: int = 40) -> Path:
    """Clamp ASS events so two normal subtitles never render at the same time."""
    if not ass_path.exists():
        return ass_path

    subs = SSAFile.load(str(ass_path))
    changed = False
    for idx, event in enumerate(subs):
        if event.end <= event.start:
            event.end = event.start + 250
            changed = True

        if idx >= len(subs) - 1:
            continue

        next_event = subs[idx + 1]
        latest_end = next_event.start - gap_ms
        if event.end > latest_end:
            event.end = max(event.start + 1, latest_end)
            changed = True

    if changed:
        subs.save(str(ass_path), encoding="utf-8")
    return ass_path


def _add_karaoke_line(subs, words, seg_start, seg_end, clip_offset, char_level):
    """Add karaoke-style line: full line visible, words highlight in sequence."""
    karaoke_text = ""
    for w in words:
        duration_cs = int((w["end"] - w["start"]) * 100)
        word_text = w["word"].strip()
        if char_level:
            for ch in word_text:
                karaoke_text += f"{{\\kf{duration_cs // max(len(word_text), 1)}}}{ch}"
        else:
            karaoke_text += f"{{\\kf{duration_cs}}}{word_text} "

    event = SSAEvent(
        start=pysubs2.make_time(s=seg_start),
        end=pysubs2.make_time(s=seg_end),
        text=karaoke_text.strip(),
    )
    subs.append(event)


def update_subtitle_event(
    ass_path: Path,
    event_index: int,
    updates: dict,
) -> Path:
    """Update a single subtitle event (for editor patches)."""
    subs = SSAFile.load(str(ass_path))
    if event_index >= len(subs):
        raise IndexError(f"Event index {event_index} out of range")

    evt = subs[event_index]
    if "text" in updates:
        evt.text = updates["text"]
    if "start" in updates:
        evt.start = pysubs2.make_time(s=updates["start"])
    if "end" in updates:
        evt.end = pysubs2.make_time(s=updates["end"])

    subs.save(str(ass_path), encoding="utf-8")
    return ass_path


def apply_global_style_override(ass_path: Path, style_config: dict) -> Path:
    """Re-apply global style overrides to all events (for live preview)."""
    subs = SSAFile.load(str(ass_path))
    new_style = build_style(**{k: v for k, v in style_config.items() if k in build_style.__code__.co_varnames})
    subs.styles["Default"] = new_style
    subs.save(str(ass_path), encoding="utf-8")
    return ass_path

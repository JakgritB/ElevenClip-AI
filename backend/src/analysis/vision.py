"""Qwen2.5-VL multimodal scene analysis via vLLM OpenAI-compatible API.

Sends video frames + transcript text together (true multimodal fusion).
Outputs: excitement_score, face_bbox, action_type, humor_level, emotion.
All scenes analyzed concurrently — vLLM handles GPU batching internally.
"""
import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Optional
from loguru import logger

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")

ANALYSIS_PROMPT = """You are a TikTok content expert analyzing a livestream segment for highlight potential.
Analyze the provided video frames and transcript text together as a unified multimodal signal.

Respond ONLY with valid JSON matching this exact schema — no markdown, no explanation:
{{
  "excitement_score": <0.0-1.0>,
  "humor_level": <0.0-1.0>,
  "emotion": "<neutral|happy|surprised|angry|sad|excited|funny>",
  "action_type": "<talking|gaming|reaction|tutorial|entertainment|sports|other>",
  "has_face": <true|false>,
  "face_bbox": [<x1_pct>, <y1_pct>, <x2_pct>, <y2_pct>] or null,
  "highlight_reason": "<one sentence: why this IS or isn't a good TikTok highlight>",
  "tiktok_potential": <0.0-1.0>
}}

Channel context: {channel_description}
Requested clip style: {clip_style}
"""


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_scene(
    scene: dict,
    transcript_text: str = "",
    channel_description: str = "",
    clip_style: str = "entertaining",
) -> dict:
    """Analyze a single scene using Qwen2.5-VL (vision + text multimodal fusion).

    Sends up to 3 representative frames + transcript context to vLLM.
    Returns analysis dict with excitement_score, face_bbox, etc.
    """
    try:
        from openai import OpenAI

        client = OpenAI(base_url=VLLM_BASE_URL, api_key=VLLM_API_KEY)
        frame_paths = scene.get("frame_paths", [])
        if not frame_paths:
            return _default_analysis()

        content = []

        # Add up to 3 frames as base64 images
        for frame_path in frame_paths[:3]:
            if Path(frame_path).exists():
                b64 = _encode_image(frame_path)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })

        if not content:
            return _default_analysis()

        prompt = ANALYSIS_PROMPT.format(
            channel_description=channel_description or "General content creator",
            clip_style=clip_style,
        )
        if transcript_text.strip():
            prompt += f"\n\nTranscript for this segment:\n\"{transcript_text.strip()}\""

        content.append({"type": "text", "text": prompt})

        response = client.chat.completions.create(
            model=VLLM_MODEL,
            messages=[{"role": "user", "content": content}],
            max_tokens=300,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]

        analysis = json.loads(raw.strip())
        logger.debug(
            f"Scene [{scene['start']:.1f}s-{scene['end']:.1f}s]: "
            f"excitement={analysis.get('excitement_score', 0):.2f} "
            f"tiktok={analysis.get('tiktok_potential', 0):.2f} | "
            f"{analysis.get('highlight_reason', '')[:60]}"
        )
        try:
            from src.gpu.vllm_manager import vllm_touch
            vllm_touch()
        except Exception:
            pass
        return analysis

    except Exception as e:
        logger.warning(f"Vision analysis failed at {scene.get('start', 0):.1f}s: {e}")
        return _default_analysis()


async def analyze_scenes_batch_async(
    scenes_with_frames: list[dict],
    transcript_segments: list[dict],
    channel_description: str = "",
    clip_style: str = "entertaining",
) -> list[dict]:
    """Analyze all scenes concurrently.

    Sends all vLLM requests in parallel — the server queues and batches them
    internally, giving full GPU utilization on AMD MI300X.
    Each result includes 'vision_analysis' and 'transcript_text' for scoring.
    """
    loop = asyncio.get_running_loop()

    async def _analyze_one(scene: dict) -> dict:
        scene_text = " ".join(
            seg["text"] for seg in transcript_segments
            if seg["start"] < scene["end"] and seg["end"] > scene["start"]
        )
        analysis = await loop.run_in_executor(
            None,
            lambda s=scene, t=scene_text: analyze_scene(s, t, channel_description, clip_style),
        )
        return {**scene, "vision_analysis": analysis, "transcript_text": scene_text}

    results = await asyncio.gather(*[_analyze_one(s) for s in scenes_with_frames])
    logger.info(f"Vision analysis complete: {len(results)} scenes")
    return list(results)


def _default_analysis() -> dict:
    """Fallback analysis when vLLM is unavailable (keeps pipeline running)."""
    return {
        "excitement_score": 0.5,
        "humor_level": 0.3,
        "emotion": "neutral",
        "action_type": "talking",
        "has_face": False,
        "face_bbox": None,
        "highlight_reason": "Vision model unavailable — using audio+text signals only",
        "tiktok_potential": 0.4,
    }


HRE_SEGMENT_PROMPT = """Analyze these video frames for high-retention TikTok editing decisions.

Segment {seg_idx} of {n_total}. Transcript: "{context}"

Respond ONLY with valid JSON — no markdown:
{{
  "zoom_direction": "<in|out|hold>",
  "zoom_speed": "<fast|slow>",
  "face_detected": <true|false>,
  "face_cx": <0.0-1.0>,
  "face_cy": <0.0-1.0>,
  "subject_bbox": [<x1>, <y1>, <x2>, <y2>] or null,
  "zoom_anchor_x": <0.0-1.0>,
  "zoom_anchor_y": <0.0-1.0>,
  "subtitle_position": "<top|bottom|left|right|center>",
  "caption_x": <0.10-0.90>,
  "caption_y": <0.12-0.88>,
  "caption_anchor": <1-9>,
  "caption_max_width_pct": <0.35-0.82>,
  "subtitle_mode": "<word|phrase|sentence>",
  "subtitle_emphasis": "<pop|punch|calm>",
  "subtitle_color": "<white|yellow|cyan|orange|green>",
  "energy_level": "<high|medium|low>",
  "moment_type": "<hook|punchline|context|reaction|transition>"
}}

Rules:
- Primary priority: keep the speaker/person visible. If a person exists, subject_bbox and zoom_anchor must target the person/face before products/screens.
- If there is no person, target the product/object being discussed.
- For key statements, punchlines, surprising claims, numbers, product names, or memorable highlight words:
  zoom_direction=in, zoom_speed=fast or slow, subtitle_mode=word, subtitle_emphasis=punch, energy_level=high.
- For normal explanatory speech:
  zoom_direction=hold, zoom_speed=slow, subtitle_mode=sentence, subtitle_emphasis=calm, energy_level=medium or low.
- Use zoom OUT only as breathing room after an intense/key moment.
- Sentence captions should sit around center-bottom: caption_x about 0.50, caption_y about 0.68-0.74, caption_anchor=2.
- Word highlight captions can sit center, mid-upper, mid-left, or mid-right with larger text, as long as they avoid the face/product.
- subtitle WORD: short hooks, reactions, punchlines, important keywords
- subtitle PHRASE: fast but understandable speech, 2-4 words at a time
- subtitle SENTENCE: explanation, normal conversation, low/medium energy
- subject_bbox: main face/person/product/object box in normalized frame coordinates, or null if unclear
- zoom_anchor_x/y: center of the face/person/product to keep important content in frame; never choose a blank wall/window
- caption_x/y: choose an actually empty readable area in this frame, not just fixed top/bottom
- caption_anchor: ASS anchor 1-9 matching caption_x/y (1 bottom-left, 5 center, 9 top-right)
- caption_max_width_pct: smaller when the empty space is narrow; captions must stay fully inside the 9:16 frame
- Keep captions away from face, product, hands, and important screen/object regions.
- Avoid choosing the exact same caption_x/y and subtitle_mode for every segment.
- face_cx/face_cy: face center as 0.0-1.0 fraction of frame
"""


def analyze_frames_for_hre(
    frame_paths: list["Path"],
    context: str = "",
    seg_idx: int = 0,
    n_total: int = 1,
) -> dict:
    """Per-segment HRE: zoom, caption placement, caption mode, and color."""
    try:
        from openai import OpenAI

        client = OpenAI(base_url=VLLM_BASE_URL, api_key=VLLM_API_KEY)
        valid_frames = [Path(p) for p in frame_paths[:3] if Path(p).exists()]
        if not valid_frames:
            return _default_hre_analysis(seg_idx, n_total)

        content = []
        for frame_path in valid_frames:
            b64 = _encode_image(str(frame_path))
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        prompt = HRE_SEGMENT_PROMPT.format(
            seg_idx=seg_idx, n_total=n_total, context=context[:320]
        )
        content.append({"type": "text", "text": prompt})
        response = client.chat.completions.create(
            model=VLLM_MODEL,
            messages=[{
                "role": "user",
                "content": content,
            }],
            max_tokens=380,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]

        analysis = {**_default_hre_analysis(seg_idx, n_total), **json.loads(raw.strip())}
        logger.debug(
            f"HRE seg {seg_idx}/{n_total}: "
            f"zoom={analysis.get('zoom_direction')}({analysis.get('zoom_speed')}) "
            f"caption=({analysis.get('caption_x')},{analysis.get('caption_y')}) "
            f"sub={analysis.get('subtitle_position')}/{analysis.get('subtitle_mode')}/"
            f"{analysis.get('subtitle_color')} "
            f"type={analysis.get('moment_type')}"
        )
        try:
            from src.gpu.vllm_manager import vllm_touch
            vllm_touch()
        except Exception:
            pass
        return analysis

    except Exception as e:
        logger.warning(f"HRE frame analysis failed (seg {seg_idx}): {e}")
        return _default_hre_analysis(seg_idx, n_total)


def analyze_frame_for_hre(
    frame_path: "Path",
    context: str = "",
    seg_idx: int = 0,
    n_total: int = 1,
) -> dict:
    """Backward-compatible wrapper for callers that provide one frame."""
    return analyze_frames_for_hre([frame_path], context, seg_idx, n_total)


def _default_hre_analysis(seg_idx: int = 0, n_total: int = 1) -> dict:
    """Fallback with varied decisions based on position in clip."""
    if seg_idx == 0:
        zoom_dir, zoom_speed, moment = "in", "fast", "hook"
    elif seg_idx == n_total - 1:
        zoom_dir, zoom_speed, moment = "out", "slow", "transition"
    elif seg_idx % 3 == 1:
        zoom_dir, zoom_speed, moment = "hold", "slow", "context"
    else:
        zoom_dir, zoom_speed, moment = "in", "slow", "reaction"

    _colors    = ["yellow", "white", "cyan", "orange", "white", "yellow"]
    _positions = ["bottom", "top", "left", "bottom", "right", "top"]
    _coords    = [(0.50, 0.76), (0.50, 0.18), (0.28, 0.56), (0.50, 0.72), (0.72, 0.56), (0.50, 0.20)]
    _anchors   = [2, 8, 4, 2, 6, 8]
    _modes     = ["word", "sentence", "phrase", "word", "sentence", "phrase"]
    _emphasis  = ["punch", "calm", "pop", "punch", "calm", "pop"]
    caption_x, caption_y = _coords[seg_idx % len(_coords)]

    return {
        "zoom_direction":    zoom_dir,
        "zoom_speed":        zoom_speed,
        "face_detected":     False,
        "face_cx":           0.5,
        "face_cy":           0.38,
        "subject_bbox":      None,
        "zoom_anchor_x":     0.5,
        "zoom_anchor_y":     0.38,
        "subtitle_position": _positions[seg_idx % len(_positions)],
        "caption_x":         caption_x,
        "caption_y":         caption_y,
        "caption_anchor":    _anchors[seg_idx % len(_anchors)],
        "caption_max_width_pct": 0.62,
        "subtitle_mode":     _modes[seg_idx % len(_modes)],
        "subtitle_emphasis": _emphasis[seg_idx % len(_emphasis)],
        "subtitle_color":    _colors[seg_idx % len(_colors)],
        "energy_level":      "medium",
        "moment_type":       moment,
    }


def get_emoji_for_scene(scene_text: str, emotion: str, action_type: str) -> str:
    """Use the configured Qwen2.5-VL model as a text prompt to select an emoji."""
    try:
        from openai import OpenAI
        client = OpenAI(base_url=VLLM_BASE_URL, api_key=VLLM_API_KEY)

        response = client.chat.completions.create(
            model=VLLM_MODEL,
            messages=[{"role": "user", "content": (
                f"Select ONE emoji for this TikTok moment.\n"
                f"Emotion: {emotion}\nAction: {action_type}\n"
                f"Text: \"{scene_text[:200]}\"\n"
                f"Reply with ONLY the emoji character, nothing else."
            )}],
            max_tokens=5,
            temperature=0.3,
        )
        emoji = response.choices[0].message.content.strip()
        if len(emoji) <= 4:
            return emoji
    except Exception:
        pass

    emoji_map = {
        "happy": "😄", "excited": "🔥", "funny": "😂",
        "surprised": "😲", "angry": "😤", "sad": "😢",
        "neutral": "💡", "gaming": "🎮", "tutorial": "📚",
        "entertainment": "✨", "reaction": "😱",
    }
    return emoji_map.get(emotion) or emoji_map.get(action_type, "⚡")

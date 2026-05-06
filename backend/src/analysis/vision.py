"""Qwen3-VL multimodal scene analysis via vLLM OpenAI-compatible API.

Sends video frames + transcript text together (true multimodal fusion).
Outputs: excitement_score, face_bbox, action_type, humor_level, emotion.
"""
import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Optional
from loguru import logger

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen3-VL-7B-Instruct")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")

ANALYSIS_PROMPT = """You are a TikTok content expert analyzing a livestream segment.
Analyze the provided video frames and transcript text together.

Respond ONLY with valid JSON matching this exact schema:
{
  "excitement_score": 0.0-1.0,
  "humor_level": 0.0-1.0,
  "emotion": "neutral|happy|surprised|angry|sad|excited|funny",
  "action_type": "talking|gaming|reaction|tutorial|entertainment|sports|other",
  "has_face": true/false,
  "face_bbox": [x1_pct, y1_pct, x2_pct, y2_pct] or null,
  "highlight_reason": "one sentence why this is or isn't a good highlight",
  "tiktok_potential": 0.0-1.0
}

Context about this channel: {channel_description}
Clip style requested: {clip_style}
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
    """Analyze a single scene using Qwen3-VL (vision + text fusion).

    Args:
        scene: Scene dict with 'frame_paths', 'start', 'end'
        transcript_text: Whisper transcript for this time window
        channel_description: User-provided channel context
        clip_style: User's desired clip style

    Returns: Analysis dict with excitement_score, face_bbox, etc.
    """
    try:
        from openai import OpenAI

        client = OpenAI(base_url=VLLM_BASE_URL, api_key=VLLM_API_KEY)

        frame_paths = scene.get("frame_paths", [])
        if not frame_paths:
            return _default_analysis()

        # Build multimodal message: images + transcript text together
        content = []

        # Add frames
        for frame_path in frame_paths[:3]:  # max 3 frames per scene
            if Path(frame_path).exists():
                b64 = _encode_image(frame_path)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })

        # Add transcript as text context (true multimodal fusion)
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
            max_tokens=256,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        analysis = json.loads(raw)
        logger.debug(f"Scene [{scene['start']:.1f}s]: score={analysis.get('excitement_score', 0):.2f} | {analysis.get('highlight_reason', '')[:60]}")
        return analysis

    except Exception as e:
        logger.warning(f"Vision analysis failed for scene at {scene.get('start', 0):.1f}s: {e}")
        return _default_analysis()


def analyze_scenes_batch(
    scenes_with_frames: list[dict],
    transcript_segments: list[dict],
    channel_description: str = "",
    clip_style: str = "entertaining",
) -> list[dict]:
    """Analyze all scenes. Match transcript segments to scenes by time."""
    results = []
    for scene in scenes_with_frames:
        # Find overlapping transcript segments for this scene
        scene_text = " ".join(
            seg["text"] for seg in transcript_segments
            if seg["start"] < scene["end"] and seg["end"] > scene["start"]
        )

        analysis = analyze_scene(scene, scene_text, channel_description, clip_style)
        results.append({**scene, "vision_analysis": analysis})

    return results


async def analyze_scenes_batch_async(
    scenes_with_frames: list[dict],
    transcript_segments: list[dict],
    channel_description: str = "",
    clip_style: str = "entertaining",
) -> list[dict]:
    """Async wrapper - runs scene analysis in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: analyze_scenes_batch(
            scenes_with_frames, transcript_segments, channel_description, clip_style
        )
    )


def _default_analysis() -> dict:
    """Fallback analysis when vLLM is unavailable."""
    return {
        "excitement_score": 0.5,
        "humor_level": 0.3,
        "emotion": "neutral",
        "action_type": "talking",
        "has_face": False,
        "face_bbox": None,
        "highlight_reason": "Unable to analyze (model unavailable)",
        "tiktok_potential": 0.4,
    }


def get_emoji_for_scene(scene_text: str, emotion: str, action_type: str) -> str:
    """Use Qwen3 text-only to select a contextually appropriate emoji."""
    try:
        from openai import OpenAI
        client = OpenAI(base_url=VLLM_BASE_URL, api_key=VLLM_API_KEY)

        prompt = f"""Select ONE emoji that best matches this TikTok moment.
Emotion: {emotion}
Action: {action_type}
Text: "{scene_text[:200]}"
Reply with ONLY the emoji character, nothing else."""

        response = client.chat.completions.create(
            model=VLLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0.3,
        )
        emoji = response.choices[0].message.content.strip()
        # Validate it's a single emoji
        if len(emoji) <= 4:
            return emoji
    except Exception:
        pass

    # Fallback mapping
    emoji_map = {
        "happy": "😄", "excited": "🔥", "funny": "😂",
        "surprised": "😲", "angry": "😤", "sad": "😢",
        "neutral": "💡", "gaming": "🎮", "tutorial": "📚",
    }
    return emoji_map.get(emotion, emoji_map.get(action_type, "⚡"))

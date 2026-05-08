"""Qwen3-VL multimodal scene analysis via vLLM OpenAI-compatible API.

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

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")
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
    """Analyze a single scene using Qwen3-VL (vision + text multimodal fusion).

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


def get_emoji_for_scene(scene_text: str, emotion: str, action_type: str) -> str:
    """Use Qwen3 text-only to select a contextually appropriate emoji."""
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

"""Multi-signal highlight scoring: Vision + Audio energy + Text keywords."""
import math
from pathlib import Path
from loguru import logger


# Style-specific keyword boosts
STYLE_KEYWORDS = {
    "funny": ["haha", "lol", "funny", "joke", "laugh", "omg", "what", "no way", "ตลก", "ฮา", "โอ้โห", "搞笑", "哈哈"],
    "serious": ["important", "key", "must", "critical", "สำคัญ", "ต้อง", "หลัก", "重要", "关键"],
    "educational": ["learn", "tip", "trick", "how", "why", "เรียน", "วิธี", "ทำไม", "学习", "方法", "技巧"],
    "gaming": ["win", "lose", "boss", "kill", "score", "level", "ชนะ", "แพ้", "赢", "输"],
    "entertainment": ["wow", "amazing", "incredible", "unbelievable", "เจ๋ง", "เยี่ยม", "厉害", "太棒了"],
}


def compute_audio_energy(audio_path: Path, scenes: list[dict]) -> list[float]:
    """Compute RMS energy per scene using librosa."""
    try:
        import librosa
        import numpy as np

        y, sr = librosa.load(str(audio_path), sr=16000, mono=True)
        energies = []

        for scene in scenes:
            start_sample = int(scene["start"] * sr)
            end_sample = int(scene["end"] * sr)
            segment = y[start_sample:end_sample]
            if len(segment) == 0:
                energies.append(0.0)
                continue
            rms = float(np.sqrt(np.mean(segment ** 2)))
            energies.append(rms)

        # Normalize to 0-1
        if max(energies) > 0:
            max_e = max(energies)
            energies = [e / max_e for e in energies]

        return energies

    except ImportError:
        logger.warning("librosa not installed, using uniform audio energy")
        return [0.5] * len(scenes)
    except Exception as e:
        logger.error(f"Audio energy computation failed: {e}")
        return [0.5] * len(scenes)


def compute_text_score(transcript_text: str, clip_style: str) -> float:
    """Score transcript text based on style keywords (0-1)."""
    if not transcript_text:
        return 0.3

    text_lower = transcript_text.lower()
    keywords = STYLE_KEYWORDS.get(clip_style.lower(), [])
    if not keywords:
        return 0.3

    hits = sum(1 for kw in keywords if kw in text_lower)
    score = min(1.0, hits / max(len(keywords) * 0.2, 1))
    return max(0.1, score)


def score_scenes(
    scenes_analyzed: list[dict],
    audio_path: Path,
    clip_style: str = "entertaining",
    target_duration: int = 60,
) -> list[dict]:
    """Compute final highlight scores for all scenes.

    Final score = 0.40 × vision + 0.35 × audio_energy + 0.25 × text_keywords
    """
    # Audio energy per scene
    audio_energies = compute_audio_energy(audio_path, scenes_analyzed)

    scored = []
    for i, scene in enumerate(scenes_analyzed):
        analysis = scene.get("vision_analysis", {})

        vision_score = (
            analysis.get("excitement_score", 0.5) * 0.5 +
            analysis.get("tiktok_potential", 0.5) * 0.3 +
            analysis.get("humor_level", 0.3) * 0.2
        )

        audio_score = audio_energies[i]

        # Text from transcript segments overlapping this scene
        transcript_text = scene.get("transcript_text", "")
        text_score = compute_text_score(transcript_text, clip_style)

        final_score = (
            0.40 * vision_score +
            0.35 * audio_score +
            0.25 * text_score
        )

        # Penalize very short or very long scenes relative to target
        duration = scene["duration"]
        duration_penalty = 1.0 - abs(duration - target_duration) / max(target_duration * 2, 1)
        duration_penalty = max(0.5, duration_penalty)

        scored.append({
            **scene,
            "vision_score": round(vision_score, 3),
            "audio_score": round(audio_score, 3),
            "text_score": round(text_score, 3),
            "final_score": round(final_score * duration_penalty, 3),
        })

    scored.sort(key=lambda s: s["final_score"], reverse=True)
    logger.info(f"Top scene: {scored[0]['start']:.1f}s score={scored[0]['final_score']:.3f}" if scored else "No scenes")
    return scored


def select_top_clips(
    scored_scenes: list[dict],
    count: int,
    target_duration: int,
    min_gap_sec: float = 30.0,
) -> list[dict]:
    """Select top-N non-overlapping clips.

    Merges adjacent high-scoring scenes to reach target_duration.
    Ensures clips don't overlap (min_gap_sec between selections).
    """
    selected = []
    used_ranges = []

    for scene in scored_scenes:
        if len(selected) >= count:
            break

        # Check overlap with already selected clips
        overlaps = any(
            abs(scene["start"] - used_start) < min_gap_sec
            for used_start in used_ranges
        )
        if overlaps:
            continue

        # Adjust clip boundaries to match target_duration
        clip = _adjust_clip_duration(scene, target_duration)
        selected.append(clip)
        used_ranges.append(clip["start"])

    logger.info(f"Selected {len(selected)}/{count} clips")
    return sorted(selected, key=lambda c: c["start"])


def _adjust_clip_duration(scene: dict, target_sec: int) -> dict:
    """Expand or shrink a scene to approximately target_sec."""
    current_dur = scene["end"] - scene["start"]
    if abs(current_dur - target_sec) < 5:
        return scene

    # Center the target window on the scene midpoint
    mid = (scene["start"] + scene["end"]) / 2
    half = target_sec / 2
    new_start = max(0, mid - half)
    new_end = new_start + target_sec

    return {**scene, "start": new_start, "end": new_end, "duration": target_sec}

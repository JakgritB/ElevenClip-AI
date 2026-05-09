"""Speech-to-text using insanely-fast-whisper with ROCm support.

Word-level timestamps for subtitle generation.
Supports transcription (same language) and translation (→ English then to target).
"""
import asyncio
import subprocess
import json
import os
from pathlib import Path
from typing import Optional
from loguru import logger

# Language codes supported by Whisper
WHISPER_LANGUAGES = {
    "thai": "th",
    "english": "en",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "portuguese": "pt",
    "russian": "ru",
    "arabic": "ar",
    "hindi": "hi",
    "vietnamese": "vi",
    "indonesian": "id",
    "malay": "ms",
}

# Languages that need character-level splitting (no word spaces)
CHAR_LEVEL_LANGUAGES = {"th", "zh", "ja", "km", "lo", "my"}


def extract_audio(video_path: Path, audio_path: Path) -> Path:
    """Extract mono 16kHz audio from video using ffmpeg."""
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-ac", "1", "-ar", "16000",
        "-vn", "-f", "wav", str(audio_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr}")
    return audio_path


def transcribe(
    audio_path: Path,
    clip_language: str = "auto",
    subtitle_language: str = "en",
    model_size: str = "large-v3",
    device: str = "cuda",
    batch_size: int = 16,
) -> dict:
    """Transcribe audio and return word-level timestamps.

    Returns:
        {
            "text": str,
            "segments": [{"start": float, "end": float, "text": str, "words": [...]}],
            "language": str,
            "char_level": bool,
        }
    """
    clip_lang_code = WHISPER_LANGUAGES.get(clip_language.lower(), None)
    sub_lang_code = WHISPER_LANGUAGES.get(subtitle_language.lower(), "en")

    # Determine whisper task
    task = "transcribe"
    if clip_lang_code and sub_lang_code and clip_lang_code != sub_lang_code:
        if sub_lang_code == "en":
            task = "translate"  # Whisper built-in translate → English
        else:
            task = "transcribe"  # Transcribe first, then translate via Qwen3

    logger.info(f"Whisper: task={task}, clip_lang={clip_lang_code}, sub_lang={sub_lang_code}, model={model_size}")

    try:
        from transformers import pipeline
        import torch

        # AMD ROCm: float16 triggers HIPBLAS_STATUS_INTERNAL_ERROR on some models.
        # Use float32 for stability; bfloat16 as middle ground if available.
        if device == "cuda":
            try:
                name = torch.cuda.get_device_name(0).lower()
                is_amd = any(k in name for k in ("amd", "radeon", "instinct", "mi"))
            except Exception:
                is_amd = True  # default safe
            dtype = torch.bfloat16 if is_amd else torch.float16
        else:
            dtype = torch.float32

        def _build_pipe(dt):
            return pipeline(
                "automatic-speech-recognition",
                model=f"openai/whisper-{model_size}",
                torch_dtype=dt,
                device=device,
                model_kwargs={"attn_implementation": "sdpa"},
            )

        try:
            pipe = _build_pipe(dtype)
        except Exception:
            logger.warning("Whisper: falling back to float32")
            pipe = _build_pipe(torch.float32)

        generate_kwargs = {"task": task}
        if clip_lang_code:
            generate_kwargs["language"] = clip_lang_code

        try:
            result = pipe(
                str(audio_path),
                batch_size=batch_size,
                return_timestamps="word",
                generate_kwargs=generate_kwargs,
            )
        except RuntimeError as e:
            if "HIPBLAS" in str(e) or "CUDA" in str(e):
                # GPU error — retry on CPU with smaller batch
                logger.warning(f"GPU error in Whisper, retrying on CPU: {e}")
                pipe_cpu = pipeline(
                    "automatic-speech-recognition",
                    model=f"openai/whisper-{model_size}",
                    torch_dtype=torch.float32,
                    device="cpu",
                )
                result = pipe_cpu(
                    str(audio_path),
                    batch_size=1,
                    return_timestamps="word",
                    generate_kwargs=generate_kwargs,
                )
            else:
                raise

        segments = _build_segments(result, sub_lang_code)
        char_level = sub_lang_code in CHAR_LEVEL_LANGUAGES

        return {
            "text": result.get("text", ""),
            "segments": segments,
            "language": clip_lang_code or "auto",
            "char_level": char_level,
            "task": task,
        }

    except ImportError:
        logger.warning("transformers not available, using stub transcription")
        return _stub_transcription(str(audio_path))


def _build_segments(whisper_result: dict, target_lang: str) -> list:
    """Convert Whisper output to segment list with word timestamps."""
    segments = []
    chunks = whisper_result.get("chunks", [])

    if not chunks:
        # Fallback: single segment
        return [{"start": 0.0, "end": 30.0, "text": whisper_result.get("text", ""), "words": []}]

    current_seg = {"start": None, "end": None, "text": "", "words": []}
    SEGMENT_GAP = 1.5  # seconds gap to split into new segment

    for chunk in chunks:
        ts = chunk.get("timestamp", [0, 0])
        start, end = (ts[0] or 0.0), (ts[1] or ts[0] or 0.0)
        text = chunk.get("text", "").strip()

        if not text:
            continue

        if current_seg["start"] is None:
            current_seg["start"] = start

        if current_seg["words"] and start - current_seg["end"] > SEGMENT_GAP:
            segments.append(current_seg)
            current_seg = {"start": start, "end": end, "text": text, "words": []}
        else:
            current_seg["text"] += (" " if current_seg["text"] else "") + text

        current_seg["words"].append({"word": text, "start": start, "end": end})
        current_seg["end"] = end

    if current_seg["start"] is not None:
        segments.append(current_seg)

    return segments


def _stub_transcription(audio_path: str) -> dict:
    """Return minimal stub when Whisper is unavailable (dev/CPU mode)."""
    return {
        "text": "[Transcription not available — Whisper model not loaded]",
        "segments": [{"start": 0.0, "end": 5.0, "text": "Sample subtitle", "words": [
            {"word": "Sample", "start": 0.0, "end": 0.5},
            {"word": "subtitle", "start": 0.6, "end": 1.0},
        ]}],
        "language": "en",
        "char_level": False,
        "task": "transcribe",
    }


async def transcribe_async(
    audio_path: Path,
    clip_language: str = "auto",
    subtitle_language: str = "en",
    model_size: str = "large-v3",
    device: str = "cuda",
) -> dict:
    """Async wrapper for transcribe."""
    loop = asyncio.get_event_loop()
    from src.gpu.rocm_utils import get_optimal_batch_size
    batch_size = get_optimal_batch_size("whisper")
    return await loop.run_in_executor(
        None,
        lambda: transcribe(audio_path, clip_language, subtitle_language, model_size, device, batch_size)
    )

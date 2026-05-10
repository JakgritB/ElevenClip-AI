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
            task = "transcribe"  # Non-English targets keep transcription in the selected language.

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

        def _call_asr(pipe_obj, bs, gk, timestamps="word"):
            return pipe_obj(
                str(audio_path),
                batch_size=max(1, bs),
                return_timestamps=timestamps,
                generate_kwargs=gk,
            )

        def _ensure_timestamp_chunks(pipe_obj, bs, gk, result):
            if result.get("chunks"):
                return result
            if not result.get("text"):
                return result
            logger.warning("Whisper returned no word timestamps; retrying with chunk timestamps")
            try:
                retry = _call_asr(pipe_obj, max(1, bs // 2), gk, timestamps=True)
                return retry if retry.get("chunks") else result
            except Exception as e:
                logger.warning(f"Whisper chunk timestamp retry failed: {str(e)[:120]}")
                return result

        def _run_on_cpu(gk):
            logger.warning("Whisper: running on CPU (GPU unavailable or OOM)")
            pipe_cpu = pipeline(
                "automatic-speech-recognition",
                model=f"openai/whisper-{model_size}",
                torch_dtype=torch.float32,
                device="cpu",
            )
            result_cpu = _call_asr(pipe_cpu, 1, gk, timestamps="word")
            return _ensure_timestamp_chunks(pipe_cpu, 1, gk, result_cpu)

        generate_kwargs = {"task": task}
        if clip_lang_code:
            generate_kwargs["language"] = clip_lang_code

        # Check free VRAM — if GPU is nearly full, go straight to CPU
        use_gpu = device == "cuda"
        if use_gpu:
            try:
                free_bytes = torch.cuda.mem_get_info(0)[0]
                if free_bytes < 8 * 1024 ** 3:  # < 8 GB free
                    logger.warning(f"Whisper: only {free_bytes/1024**3:.1f} GB free — using CPU")
                    use_gpu = False
            except Exception:
                pass

        pipe = None
        try:
            if not use_gpu:
                result = _run_on_cpu(generate_kwargs)
            else:
                pipe = pipeline(
                    "automatic-speech-recognition",
                    model=f"openai/whisper-{model_size}",
                    torch_dtype=dtype,
                    device=device,
                    model_kwargs={"attn_implementation": "sdpa"},
                )
                result = _call_asr(pipe, batch_size, generate_kwargs, timestamps="word")
                result = _ensure_timestamp_chunks(pipe, batch_size, generate_kwargs, result)
        except (RuntimeError, Exception) as e:
            err = str(e)
            if any(k in err for k in ("HIPBLAS", "HIP", "out of memory", "OutOfMemory", "CUDA")):
                logger.warning(f"GPU error in Whisper ({err[:120]}), retrying on CPU")
                result = _run_on_cpu(generate_kwargs)
            else:
                raise
        finally:
            if pipe is not None:
                del pipe
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass

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


def _expand_chunk_words(text: str, start: float, end: float, target_lang: str) -> list[dict]:
    """Create word-ish timings when Whisper only gives chunk timestamps."""
    duration = max(0.08, end - start)
    if target_lang in CHAR_LEVEL_LANGUAGES:
        units = [ch for ch in text if ch.strip()]
    else:
        units = text.split()

    if len(units) <= 1:
        return [{"word": text, "start": start, "end": end}]

    weights = [max(1, len(unit.strip())) for unit in units]
    total = sum(weights)
    cursor = start
    words = []
    for i, (unit, weight) in enumerate(zip(units, weights)):
        if i == len(units) - 1:
            unit_end = end
        else:
            unit_end = min(end, cursor + duration * (weight / total))
        if unit_end <= cursor:
            unit_end = min(end, cursor + 0.08)
        words.append({"word": unit, "start": cursor, "end": unit_end, "synthetic": True})
        cursor = unit_end
    return words


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

        current_seg["words"].extend(_expand_chunk_words(text, start, end, target_lang))
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

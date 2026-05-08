"""ElevenClip AI — FastAPI Backend.

Endpoints:
  POST /api/video-info          — get YouTube metadata (no download)
  POST /api/process             — full pipeline (download/upload → clips)
  WS   /ws/progress/{session}   — real-time pipeline progress
  GET  /api/clips/{session}     — list generated clips
  PATCH /api/clips/{session}/{index}/subtitles — update subtitle event
  PATCH /api/clips/{session}/{index}/style     — apply global style override
  POST /api/clips/{session}/{index}/render     — burn-in subtitles → download
  GET  /downloads/{session}/{filename}         — serve output files
"""
import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from loguru import logger

from src.gpu.rocm_utils import get_device, log_gpu_status
from src.ingestion.youtube import download_video_async, get_video_info
from src.transcription.whisper import transcribe_async, extract_audio
from src.analysis.scene_detector import detect_scenes, sample_frames
from src.analysis.vision import analyze_scenes_batch_async
from src.analysis.highlight_scorer import score_scenes, select_top_clips
from src.processing.clip_extractor import extract_all_clips_async, burn_subtitles
from src.processing.subtitle import generate_subtitles, update_subtitle_event, apply_global_style_override
from src.processing.high_retention import apply_hre

app = FastAPI(title="ElevenClip AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORK_DIR = Path(os.getenv("WORK_DIR", "/tmp/elevnclip"))
WORK_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/downloads", StaticFiles(directory=str(WORK_DIR)), name="downloads")

# In-memory session store + WebSocket registry
sessions: dict[str, dict] = {}
ws_connections: dict[str, WebSocket] = {}
ws_queues: dict[str, list[dict]] = {}  # buffer progress messages until WS connects


# ─── Startup ──────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    log_gpu_status()
    # Pre-populate demo session so /editor?session=demo always works
    sessions["demo"] = {"status": "done", "clips": _build_demo_clips()}


def _build_demo_clips() -> list[dict]:
    return [
        {
            "index": 1, "start": 0.0, "end": 45.0, "duration": 45.0, "score": 0.91,
            "clip_path": None, "final_path": None, "ass_path": None,
            "download_url": None, "raw_url": None,
            "highlight_reason": "High-energy moment with peak audience reaction",
            "vision_analysis": {"excitement_score": 0.92, "tiktok_potential": 0.89, "emotion": "excited", "action_type": "gaming"},
        },
        {
            "index": 2, "start": 90.0, "end": 150.0, "duration": 60.0, "score": 0.83,
            "clip_path": None, "final_path": None, "ass_path": None,
            "download_url": None, "raw_url": None,
            "highlight_reason": "Funny reaction — peak humor level detected",
            "vision_analysis": {"excitement_score": 0.78, "tiktok_potential": 0.85, "emotion": "funny", "action_type": "reaction"},
        },
        {
            "index": 3, "start": 210.0, "end": 270.0, "duration": 60.0, "score": 0.76,
            "clip_path": None, "final_path": None, "ass_path": None,
            "download_url": None, "raw_url": None,
            "highlight_reason": "Educational highlight with strong engagement signal",
            "vision_analysis": {"excitement_score": 0.70, "tiktok_potential": 0.80, "emotion": "happy", "action_type": "tutorial"},
        },
    ]


# ─── WebSocket Progress ────────────────────────────────────────────────────

@app.websocket("/ws/progress/{session_id}")
async def ws_progress(websocket: WebSocket, session_id: str):
    await websocket.accept()
    ws_connections[session_id] = websocket

    # Flush messages that were sent before the WS connected
    for msg in ws_queues.pop(session_id, []):
        try:
            await websocket.send_json(msg)
        except Exception:
            break

    try:
        while True:
            await asyncio.sleep(30)  # keep-alive
    except WebSocketDisconnect:
        ws_connections.pop(session_id, None)


async def send_progress(session_id: str, stage: str, pct: int, message: str = ""):
    payload = {"stage": stage, "pct": pct, "message": message}
    sessions.setdefault(session_id, {})["last_progress"] = payload

    ws = ws_connections.get(session_id)
    if ws:
        try:
            await ws.send_json(payload)
            return
        except Exception:
            ws_connections.pop(session_id, None)

    # WS not yet connected — buffer for flush on connect
    ws_queues.setdefault(session_id, []).append(payload)


# ─── Models ───────────────────────────────────────────────────────────────

class VideoInfoRequest(BaseModel):
    url: str

class ProcessSettings(BaseModel):
    youtube_url: Optional[str] = None
    channel_description: str = ""
    clip_style: str = "entertaining"
    target_duration: int = 60
    clip_count: int = 3
    clip_language: str = "auto"
    subtitle_language: str = "en"
    mode: str = "normal"  # "normal" | "hre"
    style_config: dict = {}

class SubtitlePatch(BaseModel):
    event_index: int
    updates: dict  # {text, start, end}

class GlobalStylePatch(BaseModel):
    style_config: dict


# ─── Routes ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "device": get_device()}


@app.post("/api/video-info")
async def video_info(req: VideoInfoRequest):
    try:
        return get_video_info(req.url)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/process")
async def process(
    settings_json: str = Form(...),
    file: Optional[UploadFile] = File(None),
):
    """Main pipeline endpoint. Returns session_id immediately; progress via WebSocket."""
    settings = ProcessSettings(**json.loads(settings_json))
    session_id = str(uuid.uuid4())
    session_dir = WORK_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    sessions[session_id] = {"status": "starting", "clips": []}

    # Read file bytes NOW — UploadFile becomes invalid once the response is sent
    file_bytes: Optional[bytes] = None
    file_name: Optional[str] = None
    if file:
        file_bytes = await file.read()
        file_name = file.filename or "upload.mp4"

    asyncio.create_task(_run_pipeline(session_id, session_dir, settings, file_bytes, file_name))
    return {"session_id": session_id}


# ─── Pipeline ─────────────────────────────────────────────────────────────

async def _run_pipeline(
    session_id: str,
    session_dir: Path,
    settings: ProcessSettings,
    file_bytes: Optional[bytes],
    file_name: Optional[str],
):
    loop = asyncio.get_running_loop()
    frames_dir = session_dir / "frames"

    try:
        # ── 1. Acquire video ──────────────────────────────────────────────
        await send_progress(session_id, "download", 5, "Acquiring video...")

        if settings.youtube_url:
            def pct_cb(p):
                asyncio.run_coroutine_threadsafe(
                    send_progress(session_id, "download", max(5, int(p * 0.28)), f"Downloading {p:.0f}%"),
                    loop,
                )
            video_path = await download_video_async(
                settings.youtube_url, session_dir, session_id, pct_cb
            )
        elif file_bytes:
            suffix = Path(file_name).suffix if file_name else ".mp4"
            video_path = session_dir / f"{session_id}_input{suffix}"
            await loop.run_in_executor(None, video_path.write_bytes, file_bytes)
        else:
            raise ValueError("No video source provided")

        await send_progress(session_id, "download", 30, "Video ready")

        # ── 2. Extract audio ─────────────────────────────────────────────
        await send_progress(session_id, "audio", 32, "Extracting audio (16kHz mono)...")
        audio_path = session_dir / f"{session_id}_audio.wav"
        await loop.run_in_executor(None, lambda: extract_audio(video_path, audio_path))

        # ── 3+4. Scene detection AND Whisper transcription IN PARALLEL ───
        # Scene detection runs on CPU; Whisper runs on AMD GPU. True concurrency.
        await send_progress(session_id, "scenes", 35, "Scene detection + Whisper transcription (parallel on AMD ROCm)...")
        device = get_device()

        scenes_future = loop.run_in_executor(None, lambda: detect_scenes(video_path))
        transcript_task = transcribe_async(
            audio_path,
            clip_language=settings.clip_language,
            subtitle_language=settings.subtitle_language,
            device=device,
        )
        scenes, transcript = await asyncio.gather(scenes_future, transcript_task)

        await send_progress(
            session_id, "transcribe", 58,
            f"Whisper: {len(transcript.get('segments', []))} segments | SceneDetect: {len(scenes)} scenes"
        )

        # Frame sampling (after scenes list is known)
        scenes_with_frames = await loop.run_in_executor(
            None, lambda: sample_frames(video_path, scenes, frames_dir)
        )

        # ── 5. Qwen3-VL multimodal analysis (concurrent requests to vLLM) ─
        n_scenes = len(scenes_with_frames)
        await send_progress(session_id, "vision", 60, f"Qwen3-VL analyzing {n_scenes} scenes (vision + audio + text fusion)...")
        scenes_analyzed = await analyze_scenes_batch_async(
            scenes_with_frames,
            transcript.get("segments", []),
            channel_description=settings.channel_description,
            clip_style=settings.clip_style,
        )
        await send_progress(session_id, "vision", 76, f"Multimodal analysis complete: {n_scenes} scenes scored")

        # ── 6. Multi-signal scoring ─────────────────────────────────────
        await send_progress(session_id, "scoring", 77, "Scoring: 0.40×vision + 0.35×audio_energy + 0.25×text_keywords")
        scored = score_scenes(scenes_analyzed, audio_path, settings.clip_style, settings.target_duration)
        selected = select_top_clips(scored, settings.clip_count, settings.target_duration)

        # ── 7. Extract clips (AMD AMF hardware encoder) ─────────────────
        await send_progress(session_id, "cutting", 81, f"Cutting {len(selected)} clips (h264_amf)...")
        clips = await extract_all_clips_async(video_path, selected, session_dir, session_id)

        # ── 8. Subtitles / HRE (all clips in parallel) ─────────────────
        await send_progress(session_id, "subtitles", 86, "Generating subtitles (parallel)...")

        subtitle_tasks = []
        final_clips = []

        for clip in clips:
            if not clip.get("clip_path"):
                continue
            clip_path = Path(clip["clip_path"])
            i = clip["clip_index"]

            clip_transcript = {
                **transcript,
                "segments": [
                    s for s in transcript.get("segments", [])
                    if s["start"] < clip["end"] and s["end"] > clip["start"]
                ],
            }

            ass_path = session_dir / f"{session_id}_clip_{i:02d}.ass"
            final_path = session_dir / f"{session_id}_clip_{i:02d}_final.mp4"

            if settings.mode == "hre":
                subtitle_tasks.append(loop.run_in_executor(
                    None,
                    lambda cp=clip_path, cd=clip, tr=clip_transcript, fp=final_path:
                        apply_hre(cp, cd, tr, fp)
                ))
            else:
                def _gen_and_burn(cp=clip_path, ap=ass_path, tr=clip_transcript, cs=clip["start"], fp=final_path):
                    generate_subtitles(tr, ap, settings.style_config, clip_start_offset=cs)
                    burn_subtitles(cp, ap, fp)
                subtitle_tasks.append(loop.run_in_executor(None, _gen_and_burn))

            final_clips.append({
                "index": i,
                "start": clip["start"],
                "end": clip["end"],
                "duration": clip["end"] - clip["start"],
                "score": clip.get("final_score", 0),
                "clip_path": str(clip_path),
                "final_path": str(final_path),
                "ass_path": str(ass_path) if settings.mode == "normal" else None,
                "download_url": f"/downloads/{session_id}/{final_path.name}",
                "raw_url": f"/downloads/{session_id}/{clip_path.name}",
                "vision_analysis": clip.get("vision_analysis", {}),
                "highlight_reason": clip.get("vision_analysis", {}).get("highlight_reason", ""),
            })

        if subtitle_tasks:
            await asyncio.gather(*subtitle_tasks)

        sessions[session_id] = {"status": "done", "clips": final_clips}
        await send_progress(session_id, "done", 100, f"Done! {len(final_clips)} clips ready for download.")

    except Exception as e:
        logger.exception(f"Pipeline failed [{session_id}]")
        sessions[session_id] = {"status": "error", "error": str(e), "clips": []}
        await send_progress(session_id, "error", 0, f"Pipeline error: {e}")


# ─── Editor API ───────────────────────────────────────────────────────────

@app.get("/api/clips/{session_id}")
async def get_clips(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@app.patch("/api/clips/{session_id}/{clip_index}/subtitles")
async def patch_subtitle(session_id: str, clip_index: int, patch: SubtitlePatch):
    clip = _get_clip_or_404(session_id, clip_index)
    if not clip.get("ass_path"):
        raise HTTPException(404, "No subtitle file for this clip")
    update_subtitle_event(Path(clip["ass_path"]), patch.event_index, patch.updates)
    return {"ok": True}


@app.patch("/api/clips/{session_id}/{clip_index}/style")
async def patch_global_style(session_id: str, clip_index: int, patch: GlobalStylePatch):
    clip = _get_clip_or_404(session_id, clip_index)
    if not clip.get("ass_path"):
        raise HTTPException(404, "No subtitle file for this clip")
    apply_global_style_override(Path(clip["ass_path"]), patch.style_config)
    return {"ok": True}


@app.post("/api/clips/{session_id}/{clip_index}/render")
async def render_clip(session_id: str, clip_index: int):
    clip = _get_clip_or_404(session_id, clip_index)

    clip_path = Path(clip["clip_path"])
    ass_path = Path(clip["ass_path"]) if clip.get("ass_path") else None
    final_path = clip_path.parent / f"{clip_path.stem}_edited.mp4"

    if ass_path and ass_path.exists():
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: burn_subtitles(clip_path, ass_path, final_path))
    else:
        final_path = Path(clip["final_path"])

    download_url = f"/downloads/{session_id}/{final_path.name}"
    clip["download_url"] = download_url
    clip["final_path"] = str(final_path)
    return {"download_url": download_url}


def _get_clip_or_404(session_id: str, clip_index: int) -> dict:
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    clip = next((c for c in session.get("clips", []) if c["index"] == clip_index), None)
    if not clip:
        raise HTTPException(404, f"Clip {clip_index} not found")
    return clip


if __name__ == "__main__":
    import uvicorn
    log_gpu_status()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

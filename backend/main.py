"""ElevenClip AI — FastAPI Backend.

Endpoints:
  POST /api/video-info          — get YouTube metadata (no download)
  POST /api/process             — full pipeline (download/upload → clips)
  WS   /ws/progress/{session}   — real-time pipeline progress
  GET  /api/clips/{session}     — list generated clips
  PATCH /api/clips/{session}/{index}/subtitles — update subtitle event
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
from fastapi.responses import FileResponse
from pydantic import BaseModel
from loguru import logger

from src.gpu.rocm_utils import get_device, log_gpu_status
from src.ingestion.youtube import download_video_async, get_video_info
from src.ingestion.uploader import save_upload
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

# Mount downloads directory for static file serving
app.mount("/downloads", StaticFiles(directory=str(WORK_DIR)), name="downloads")

# In-memory session store (replace with Redis for production)
sessions: dict[str, dict] = {}
ws_connections: dict[str, WebSocket] = {}


# ─── WebSocket Progress ────────────────────────────────────────────────────

@app.websocket("/ws/progress/{session_id}")
async def ws_progress(websocket: WebSocket, session_id: str):
    await websocket.accept()
    ws_connections[session_id] = websocket
    try:
        while True:
            await asyncio.sleep(30)  # keep alive
    except WebSocketDisconnect:
        ws_connections.pop(session_id, None)


async def send_progress(session_id: str, stage: str, pct: int, message: str = ""):
    ws = ws_connections.get(session_id)
    if ws:
        try:
            await ws.send_json({"stage": stage, "pct": pct, "message": message})
        except Exception:
            pass
    sessions.setdefault(session_id, {})["last_progress"] = {"stage": stage, "pct": pct}


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
    updates: dict  # {text, start, end, ...}

class GlobalStylePatch(BaseModel):
    style_config: dict


# ─── Routes ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    device = get_device()
    return {"status": "ok", "device": device}


@app.post("/api/video-info")
async def video_info(req: VideoInfoRequest):
    try:
        info = get_video_info(req.url)
        return info
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/process")
async def process(
    settings_json: str = Form(...),
    file: Optional[UploadFile] = File(None),
):
    """Main pipeline endpoint. Returns session_id immediately; streams progress via WS."""
    settings = ProcessSettings(**json.loads(settings_json))
    session_id = str(uuid.uuid4())
    session_dir = WORK_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = session_dir / "frames"

    sessions[session_id] = {"status": "starting", "clips": []}
    log_gpu_status()

    # Run pipeline in background
    asyncio.create_task(_run_pipeline(session_id, session_dir, frames_dir, settings, file))
    return {"session_id": session_id}


async def _run_pipeline(
    session_id: str,
    session_dir: Path,
    frames_dir: Path,
    settings: ProcessSettings,
    file: Optional[UploadFile],
):
    try:
        # 1. Acquire video
        await send_progress(session_id, "download", 5, "Acquiring video...")
        if settings.youtube_url:
            def pct_cb(p): asyncio.create_task(send_progress(session_id, "download", int(p * 0.3), f"Downloading {p:.0f}%"))
            video_path = await download_video_async(settings.youtube_url, session_dir, session_id, pct_cb)
        elif file:
            video_path = await save_upload(file, session_dir, session_id)
        else:
            raise ValueError("No video source provided")

        await send_progress(session_id, "download", 30, "Video ready")

        # 2. Extract audio
        await send_progress(session_id, "audio", 32, "Extracting audio...")
        audio_path = session_dir / f"{session_id}_audio.wav"
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: extract_audio(video_path, audio_path)
        )

        # 3. Scene detection (fast, local — runs in parallel with transcription start)
        await send_progress(session_id, "scenes", 35, "Detecting scenes...")
        scenes = await asyncio.get_event_loop().run_in_executor(
            None, lambda: detect_scenes(video_path)
        )
        scenes_with_frames = await asyncio.get_event_loop().run_in_executor(
            None, lambda: sample_frames(video_path, scenes, frames_dir)
        )

        # 4. Transcription (parallel with scene detection was above; now sequential)
        await send_progress(session_id, "transcribe", 40, "Transcribing audio (ROCm)...")
        device = get_device()
        transcript = await transcribe_async(
            audio_path,
            clip_language=settings.clip_language,
            subtitle_language=settings.subtitle_language,
            device=device,
        )
        await send_progress(session_id, "transcribe", 60, f"Transcribed {len(transcript.get('segments', []))} segments")

        # 5. Vision analysis — Qwen3-VL multimodal (frames + transcript text)
        await send_progress(session_id, "vision", 62, "Analyzing with Qwen3-VL (multimodal)...")
        scenes_analyzed = await analyze_scenes_batch_async(
            scenes_with_frames,
            transcript.get("segments", []),
            channel_description=settings.channel_description,
            clip_style=settings.clip_style,
        )
        await send_progress(session_id, "vision", 75, "Vision analysis complete")

        # 6. Scoring + selection
        await send_progress(session_id, "scoring", 76, "Scoring highlights...")
        scored = score_scenes(scenes_analyzed, audio_path, settings.clip_style, settings.target_duration)
        selected = select_top_clips(scored, settings.clip_count, settings.target_duration)

        # 7. Extract clips
        await send_progress(session_id, "cutting", 80, f"Cutting {len(selected)} clips...")
        clips = await extract_all_clips_async(video_path, selected, session_dir, session_id)

        # 8. Subtitle generation / HRE
        await send_progress(session_id, "subtitles", 85, "Generating subtitles...")
        final_clips = []
        for clip in clips:
            if not clip.get("clip_path"):
                continue
            clip_path = Path(clip["clip_path"])
            i = clip["clip_index"]

            # Get transcript for this clip's time window
            clip_transcript = {
                **transcript,
                "segments": [
                    s for s in transcript.get("segments", [])
                    if s["start"] < clip["end"] and s["end"] > clip["start"]
                ],
            }

            if settings.mode == "hre":
                final_path = session_dir / f"{session_id}_clip_{i:02d}_final.mp4"
                out = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda cp=clip_path, cd=clip, tr=clip_transcript, fp=final_path:
                        apply_hre(cp, cd, tr, fp)
                )
            else:
                ass_path = session_dir / f"{session_id}_clip_{i:02d}.ass"
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda ap=ass_path, tr=clip_transcript, cs=clip["start"]:
                        generate_subtitles(tr, ap, settings.style_config, clip_start_offset=cs)
                )
                final_path = session_dir / f"{session_id}_clip_{i:02d}_final.mp4"
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda cp=clip_path, ap=ass_path, fp=final_path:
                        burn_subtitles(cp, ap, fp)
                )

            final_clips.append({
                "index": i,
                "start": clip["start"],
                "end": clip["end"],
                "duration": clip["end"] - clip["start"],
                "score": clip.get("final_score", 0),
                "clip_path": str(clip_path),
                "final_path": str(final_path),
                "ass_path": str(session_dir / f"{session_id}_clip_{i:02d}.ass") if settings.mode == "normal" else None,
                "download_url": f"/downloads/{session_id}/{final_path.name}",
                "raw_url": f"/downloads/{session_id}/{clip_path.name}",
                "vision_analysis": clip.get("vision_analysis", {}),
                "highlight_reason": clip.get("vision_analysis", {}).get("highlight_reason", ""),
            })

        sessions[session_id] = {"status": "done", "clips": final_clips}
        await send_progress(session_id, "done", 100, f"Generated {len(final_clips)} clips!")

    except Exception as e:
        logger.exception(f"Pipeline failed for session {session_id}")
        sessions[session_id] = {"status": "error", "error": str(e), "clips": []}
        await send_progress(session_id, "error", 0, f"Error: {e}")


@app.get("/api/clips/{session_id}")
async def get_clips(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@app.patch("/api/clips/{session_id}/{clip_index}/subtitles")
async def patch_subtitle(session_id: str, clip_index: int, patch: SubtitlePatch):
    """Update a single subtitle event in the .ass file."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    clips = session.get("clips", [])
    clip = next((c for c in clips if c["index"] == clip_index), None)
    if not clip or not clip.get("ass_path"):
        raise HTTPException(404, "Clip or subtitle file not found")

    ass_path = Path(clip["ass_path"])
    update_subtitle_event(ass_path, patch.event_index, patch.updates)
    return {"ok": True}


@app.patch("/api/clips/{session_id}/{clip_index}/style")
async def patch_global_style(session_id: str, clip_index: int, patch: GlobalStylePatch):
    """Apply global style override to all subtitle events."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    clips = session.get("clips", [])
    clip = next((c for c in clips if c["index"] == clip_index), None)
    if not clip or not clip.get("ass_path"):
        raise HTTPException(404, "Clip or subtitle file not found")

    ass_path = Path(clip["ass_path"])
    apply_global_style_override(ass_path, patch.style_config)
    return {"ok": True}


@app.post("/api/clips/{session_id}/{clip_index}/render")
async def render_clip(session_id: str, clip_index: int):
    """Re-burn subtitles after editor changes."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    clips = session.get("clips", [])
    clip = next((c for c in clips if c["index"] == clip_index), None)
    if not clip:
        raise HTTPException(404, "Clip not found")

    clip_path = Path(clip["clip_path"])
    ass_path = Path(clip["ass_path"]) if clip.get("ass_path") else None
    session_dir = clip_path.parent
    final_path = session_dir / f"{clip_path.stem}_edited.mp4"

    if ass_path and ass_path.exists():
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: burn_subtitles(clip_path, ass_path, final_path)
        )
    else:
        final_path = Path(clip["final_path"])

    download_url = f"/downloads/{session_id}/{final_path.name}"
    for c in clips:
        if c["index"] == clip_index:
            c["download_url"] = download_url
            c["final_path"] = str(final_path)
    return {"download_url": download_url}


if __name__ == "__main__":
    import uvicorn
    log_gpu_status()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

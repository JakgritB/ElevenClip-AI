---
title: ElevenClip AI
emoji: ✂️
colorFrom: red
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# ElevenClip AI ✂️

> **AMD Developer Hackathon 2026 — Track 3: Vision & Multimodal AI**

Turn livestream recordings or uploaded videos into TikTok-ready highlight clips using **true multimodal AI** — vision, audio, and text analyzed simultaneously on AMD Instinct MI300X.

[![HuggingFace Space](https://img.shields.io/badge/🤗-HuggingFace%20Space-yellow)](https://huggingface.co/spaces/lablab-ai-amd-developer-hackathon/ElevenClip-AI)
[![AMD ROCm](https://img.shields.io/badge/AMD-ROCm%206.3-red)](https://rocm.docs.amd.com/)
[![Qwen2.5-VL](https://img.shields.io/badge/Qwen2.5--VL-7B%20Instruct-blue)](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Demo

> Try it live: [HuggingFace Space](https://huggingface.co/spaces/lablab-ai-amd-developer-hackathon/ElevenClip-AI)

---

## What It Does

ElevenClip AI ingests an uploaded video and automatically finds the best moments to clip for TikTok using three AI modalities working together. The backend also keeps optional yt-dlp/YouTube support, but the public demo focuses on uploads because public video platforms can trigger anti-bot restrictions.

| Modality | Model | What it detects |
|---|---|---|
| **Vision** | Qwen2.5-VL-7B on ROCm | Excitement, faces, action type, humor, TikTok potential |
| **Audio** | insanely-fast-whisper (ROCm) | Word-level transcript + language detection |
| **Audio Signal** | librosa | RMS energy → loud/quiet moments |
| **Vision+Text** | Qwen2.5-VL (multimodal) | Frame + transcript context fused together |
| **Text** | Python keyword scorer + Qwen2.5-VL text prompt | Style keyword matching, emoji selection |

### Highlight Scoring Formula

```
final_score = 0.40 × vision_score + 0.35 × audio_energy + 0.25 × text_keywords

where:
  vision_score = 0.5 × excitement + 0.3 × tiktok_potential + 0.2 × humor_level
```

---

## AI Pipeline

```
┌─ Input ──────────────────────────────────────────────────────────┐
│  Uploaded video file (YouTube backend support is optional)       │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─ Audio Extraction (ffmpeg) ──────────────────────────────────────┐
│  16kHz mono WAV for Whisper                                      │
└──────────────────────────────────────────────────────────────────┘
           │
    ┌──────┴──────┐
    │             │  ← PARALLEL on AMD GPU ─────────────────────────
    ▼             ▼
┌─ Scene     ┌─ Whisper ROCm ────────────────────────────────────┐
│  Detection │  insanely-fast-whisper (SDPA attention, 4.45×)    │
│  PyScene   │  → transcript + word-level timestamps             │
│  Detect    │  → auto language detection                        │
└─────┬──────┴───────────────────────────────────────────────────┘
      │                    │
      ▼                    ▼
┌─ Frame Sampling ──────────────────────────────────────────────────┐
│  3 frames per scene (20%, 50%, 80% of scene)                     │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼  ← CONCURRENT requests to vLLM ──────────────────────
┌─ Qwen2.5-VL Multimodal Analysis ───────────────────────────────────┐
│  Input per scene: [frame1] [frame2] [frame3] + transcript text   │
│  Output: excitement_score, tiktok_potential, face_bbox,          │
│          emotion, action_type, humor_level, highlight_reason     │
│  All scenes sent concurrently — vLLM batches on AMD MI300X       │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─ Multi-Signal Scoring ────────────────────────────────────────────┐
│  score = 0.40×vision + 0.35×audio_energy + 0.25×text_keywords   │
│  Select top-N non-overlapping clips (min 30s gap)                │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─ Branch ──────────────────────────────────────────────────────────┐
│                                                                   │
│  Normal Mode              HRE (High-Retention Editing)           │
│  ─────────────            ──────────────────────────────         │
│  • pysubs2 ASS            • Silence removal (ffmpeg)             │
│  • User style config      • Auto-zoom to face (zoompan)          │
│  • Font/color/animation   • Jump cuts at boundaries              │
│  • Karaoke/pop/fade       • Qwen2.5-VL emoji selection          │
│  • AMD AMF encode         • Impact bold captions                 │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─ Editor (/editor) ────────────────────────────────────────────────┐
│  • Per-clip subtitle timeline editing                            │
│  • Global style override (live preview)                          │
│  • Re-render + download MP4                                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## AMD GPU Optimizations

- **ROCm 6.3** — all model inference on AMD Instinct MI300X
- **vLLM** — serves Qwen2.5-VL with continuous batching and PagedAttention
- **SDPA attention** — PyTorch 2.0 Scaled Dot-Product Attention for Whisper (4.45× faster on ROCm)
- **float16 inference** — 7B model fits in ~14 GB VRAM, leaves 50+ GB for large videos
- **h264_amf** — AMD VCE hardware encoder for clip extraction (falls back to libx264)
- **Parallel pipeline** — scene detection (CPU) + Whisper (GPU) run simultaneously
- **Concurrent vLLM requests** — all scenes sent to Qwen2.5-VL in parallel; server batches them

---

## Two Output Modes

### Normal Subtitles
Full creative control over:
- Font family (Noto Sans Thai, Noto Sans SC, Montserrat, Impact, ...)
- Font size, bold/italic/underline
- 4-layer ASS colors: primary, secondary, outline, shadow
- Display mode: word-by-word or sentence
- Animation: Fade / Karaoke / Pop / Typewriter / Bounce
- Alignment (3×3 grid) + margin sliders
- Per-subtitle-line style overrides in the editor

### High-Retention Editing (HRE)
AI chooses everything:
- Silence removal (`ffmpeg silenceremove`)
- Auto-zoom to face region (`ffmpeg zoompan` using Qwen2.5-VL face_bbox)
- Jump cuts at scene boundaries
- Qwen2.5-VL selects contextually-appropriate emoji overlay
- Impact 64px bold white captions, word-by-word, pop animation

---

## Multilingual Support

| Layer | Coverage |
|---|---|
| UI language | ไทย · English · 中文 |
| Video input language | Auto-detect + 15+ (Whisper) |
| Subtitle output language | Thai (Noto Sans Thai) · Chinese (Noto Sans SC) · Japanese (Noto Sans JP) · Korean (Noto Sans KR) · English + more |
| Cross-lingual | Whisper translate → English when English subtitles are requested; multilingual transcription/subtitle timing uses Whisper language support |
| Character-level splitting | Thai and Chinese use character-level subtitle timing (no word spaces) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Vision AI | **Qwen2.5-VL-7B-Instruct** (Apache 2.0) via vLLM |
| Speech-to-Text | **insanely-fast-whisper** with PyTorch SDPA on ROCm |
| Audio Analysis | **librosa** — RMS energy per scene |
| Scene Detection | **PySceneDetect** — ContentDetector |
| Video Download | **yt-dlp** |
| Video Processing | **ffmpeg** (AMD AMF hardware encode) |
| Subtitle Engine | **pysubs2** — full ASS format with karaoke tags |
| GPU | **AMD Instinct MI300X** via ROCm 6.3 |
| Frontend | **Next.js 16.2.4** App Router + Tailwind CSS |
| Backend | **FastAPI** + WebSocket (real-time progress) |
| Deployment | HuggingFace Spaces public demo + AMD GPU Cloud backend |

---

## Judge Demo

Public visitors can open the HuggingFace Space and click **Try Demo** to see a simulated flow without using AMD GPU credits. Full AMD MI300X generation is protected by an access code shared only in the lablab.ai submission notes for judges.

Recommended judging flow:
1. Open the HuggingFace Space.
2. Click **Try Demo** for the instant public demo.
3. Enter the judge access code from the lablab.ai submission notes to run real generation on AMD GPU Cloud.
4. Upload a short MP4 sample for the real run.

---

## Local Development

For the real development/demo path, run the frontend locally and point it at the AMD GPU Cloud backend:

```env
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://129.212.178.101:8080
NEXT_PUBLIC_DEMO_ENABLED=true
NEXT_PUBLIC_DEMO_ONLY=false
```

```bash
cd frontend
npm install
npm run dev  # http://localhost:3000
```

The AMD GPU Cloud backend runs FastAPI on `:8080` and vLLM/Qwen2.5-VL on `:8000`. For development without a GPU, the backend can still run with fallback stubs (stubbed Whisper, fallback vision scores).

---

## Safe Public Demo Setup

ElevenClip AI supports three deployment modes:

| Mode | Frontend runs on | Backend/vLLM runs on | Use when |
|---|---|---|---|
| Local dev | Your laptop (`localhost:3000`) | AMD GPU Cloud (`129.212.178.101:8080`) | Iterating quickly while using MI300X remotely |
| HF public shell | HuggingFace Space CPU | AMD GPU Cloud | Public hackathon page, real generation gated by access code |
| HF self-contained GPU | HuggingFace Space | HuggingFace Space GPU | Only if the Space has suitable ROCm/AMD GPU hardware |

For the current CPU Basic HuggingFace Space, use it as the public UI and keep real generation on AMD GPU Cloud:

```env
# frontend/.env.local for local development
NEXT_PUBLIC_API_URL=http://129.212.178.101:8080
NEXT_PUBLIC_DEMO_ENABLED=true
NEXT_PUBLIC_DEMO_ONLY=false
```

On the AMD GPU Cloud backend, protect expensive GPU endpoints before exposing the demo:

```bash
export DEMO_ACCESS_CODE="share-this-only-with-judges"
export MAX_CONCURRENT_JOBS=1
export MAX_UPLOAD_MB=300
export VLLM_IDLE_TIMEOUT=300
```

When `DEMO_ACCESS_CODE` is set, `/api/process`, `/api/video-info`, and vLLM start/stop endpoints require the `X-Demo-Key` header. The frontend shows a Demo Access Code field and sends that header automatically. Leave `DEMO_ACCESS_CODE` unset only for private/local testing.

For a self-contained HuggingFace GPU Space, leave `NEXT_PUBLIC_API_URL=""` so nginx routes `/api`, `/ws`, and `/downloads` to FastAPI inside the same Space. Only use this mode if the Space hardware is actually GPU-capable.

For the public HuggingFace Space, set `NEXT_PUBLIC_DEMO_ONLY=true`. Visitors can open the UI and run the simulated demo without touching AMD GPU credits. Judges can enter the access code to run real generation against the protected AMD GPU Cloud backend.

The current Docker setup keeps `NEXT_PUBLIC_API_URL=""` so the browser calls the HF Space on the same origin, then FastAPI forwards real judge requests to `REMOTE_BACKEND_URL`. This avoids browser mixed-content blocking from an HTTPS Space calling an HTTP AMD Cloud IP directly.

```env
# HF Space / Docker runtime
NEXT_PUBLIC_API_URL=
NEXT_PUBLIC_DEMO_ONLY=true
REMOTE_BACKEND_URL=http://129.212.178.101:8080
```

---

## Hackathon Compliance

| Requirement | Status |
|---|---|
| Track 3: Vision & Multimodal AI | ✅ Qwen2.5-VL processes frames + audio simultaneously |
| AMD Developer Cloud | ✅ All inference on AMD Instinct MI300X via ROCm 6.3 |
| ROCm acceleration | ✅ vLLM + SDPA Whisper + h264_amf encoder |
| Qwen partner integration | ✅ Qwen2.5-VL as primary multimodal model and text/emoji prompt model |
| HuggingFace Space | ✅ `lablab-ai-amd-developer-hackathon/ElevenClip-AI` |
| Public GitHub repo | ✅ `JakgritB/ElevenClip-AI` |
| Ship It challenge | ✅ Social posts tagging @AIatAMD + @lablab |
| MIT license | ✅ |

---

## License

MIT — see [LICENSE](LICENSE)

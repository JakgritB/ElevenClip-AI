# ElevenClip AI ✂️

> **AMD Developer Hackathon 2026 — Track 3: Vision & Multimodal AI**

Turn any livestream or YouTube video into TikTok-ready highlight clips using **true multimodal AI** — vision, audio, and text analyzed simultaneously on AMD Instinct MI300X.

[![HuggingFace Space](https://img.shields.io/badge/🤗-HuggingFace%20Space-yellow)](https://huggingface.co/spaces/lablab-ai-amd-developer-hackathon/ElevenClip-AI)
[![AMD ROCm](https://img.shields.io/badge/AMD-ROCm%206.3-red)](https://rocm.docs.amd.com/)
[![Qwen3-VL](https://img.shields.io/badge/Qwen3--VL-7B%20Instruct-blue)](https://huggingface.co/Qwen/Qwen3-VL-7B-Instruct)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Demo

> Try it live: [HuggingFace Space](https://huggingface.co/spaces/lablab-ai-amd-developer-hackathon/ElevenClip-AI)

---

## What It Does

ElevenClip AI ingests a livestream/YouTube video and automatically finds the best moments to clip for TikTok using three AI modalities working together:

| Modality | Model | What it detects |
|---|---|---|
| **Vision** | Qwen3-VL-7B on ROCm | Excitement, faces, action type, humor, TikTok potential |
| **Audio** | insanely-fast-whisper (ROCm) | Word-level transcript + language detection |
| **Audio Signal** | librosa | RMS energy → loud/quiet moments |
| **Vision+Text** | Qwen3-VL (multimodal) | Frame + transcript context fused together |
| **Text** | Qwen3 (text-only) | Style keyword matching, emoji selection |

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
│  YouTube URL or uploaded video file                              │
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
┌─ Qwen3-VL Multimodal Analysis ───────────────────────────────────┐
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
│  • Karaoke/pop/fade       • Qwen3 emoji selection                │
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
- **vLLM** — serves Qwen3-VL with continuous batching and PagedAttention
- **SDPA attention** — PyTorch 2.0 Scaled Dot-Product Attention for Whisper (4.45× faster on ROCm)
- **float16 inference** — 7B model fits in ~14 GB VRAM, leaves 50+ GB for large videos
- **h264_amf** — AMD VCE hardware encoder for clip extraction (falls back to libx264)
- **Parallel pipeline** — scene detection (CPU) + Whisper (GPU) run simultaneously
- **Concurrent vLLM requests** — all scenes sent to Qwen3-VL in parallel; server batches them

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
- Auto-zoom to face region (`ffmpeg zoompan` using Qwen3-VL face_bbox)
- Jump cuts at scene boundaries
- Qwen3 selects contextually-appropriate emoji overlay
- Impact 64px bold white captions, word-by-word, pop animation

---

## Multilingual Support

| Layer | Coverage |
|---|---|
| UI language | ไทย · English · 中文 |
| Video input language | Auto-detect + 15+ (Whisper) |
| Subtitle output language | Thai (Noto Sans Thai) · Chinese (Noto Sans SC) · Japanese (Noto Sans JP) · Korean (Noto Sans KR) · English + more |
| Cross-lingual | Whisper translate → English, then Qwen3 translate to target |
| Character-level splitting | Thai and Chinese use character-level subtitle timing (no word spaces) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Vision AI | **Qwen3-VL-7B-Instruct** (Apache 2.0) via vLLM |
| Speech-to-Text | **insanely-fast-whisper** with PyTorch SDPA on ROCm |
| Audio Analysis | **librosa** — RMS energy per scene |
| Scene Detection | **PySceneDetect** — ContentDetector |
| Video Download | **yt-dlp** |
| Video Processing | **ffmpeg** (AMD AMF hardware encode) |
| Subtitle Engine | **pysubs2** — full ASS format with karaoke tags |
| GPU | **AMD Instinct MI300X** via ROCm 6.3 |
| Frontend | **Next.js 14** App Router + Tailwind CSS + shadcn/ui |
| Backend | **FastAPI** + WebSocket (real-time progress) |
| Deployment | HuggingFace Spaces — Docker (AMD GPU Space) |

---

## Local Development

```bash
# 1. Start vLLM (Qwen3-VL) — requires AMD GPU with ROCm
pip install torch --index-url https://download.pytorch.org/whl/rocm6.2
pip install vllm --extra-index-url https://download.pytorch.org/whl/rocm6.2
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-VL-7B-Instruct \
  --port 8001 --device rocm --dtype float16

# 2. Start backend
cd backend
pip install -r requirements.txt
python main.py  # :8000

# 3. Start frontend
cd frontend
npm install
npm run dev  # :3000
```

For development without a GPU, the pipeline runs with fallback stubs (stubbed Whisper, fallback vision scores).

---

## Hackathon Compliance

| Requirement | Status |
|---|---|
| Track 3: Vision & Multimodal AI | ✅ Qwen3-VL processes frames + audio simultaneously |
| AMD Developer Cloud | ✅ All inference on AMD Instinct MI300X via ROCm 6.3 |
| ROCm acceleration | ✅ vLLM + SDPA Whisper + h264_amf encoder |
| Qwen partner integration | ✅ Qwen3-VL as primary vision model, Qwen3 for text/emoji |
| HuggingFace Space | ✅ `lablab-ai-amd-developer-hackathon/ElevenClip-AI` |
| Public GitHub repo | ✅ `JakgritB/ElevenClip-AI` |
| Ship It challenge | ✅ Social posts tagging @AIatAMD + @lablab |
| MIT license | ✅ |

---

## License

MIT — see [LICENSE](LICENSE)

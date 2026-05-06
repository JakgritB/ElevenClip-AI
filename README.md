# ElevenClip AI ✂️

> **AMD Developer Hackathon 2026 — Track 3: Vision & Multimodal AI**

Turn any livestream or YouTube video into TikTok-ready highlight clips in minutes, powered by AMD ROCm GPU acceleration and multimodal AI.

[![HuggingFace Space](https://img.shields.io/badge/🤗-HuggingFace%20Space-yellow)](https://huggingface.co/spaces/lablab-ai-amd-developer-hackathon/ElevenClip-AI)
[![AMD ROCm](https://img.shields.io/badge/AMD-ROCm%20GPU-red)](https://rocm.docs.amd.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 🎬 What It Does

1. **Input**: Upload a video file or paste a YouTube URL
2. **AI Analysis** (Multimodal — Vision + Audio + Text simultaneously):
   - Qwen3-VL analyzes video frames + transcript together
   - Whisper ROCm transcribes audio with word-level timestamps
   - librosa measures audio energy per scene
3. **Highlight Selection**: Multi-signal fusion scoring picks the best moments
4. **Output**: Styled MP4 clips with burned-in subtitles, ready for TikTok

## 🤖 Two Modes

| Mode | Description |
|---|---|
| **Normal Subtitles** | Full control: choose font, colors, animation, position |
| **⚡ High-Retention Editing** | AI-driven: auto-zoom, silence removal, jump cuts, emoji overlay |

## 🌐 Multilingual Support

- **UI**: ไทย / English / 中文
- **Video languages**: Auto-detect + 15+ languages via Whisper
- **Subtitle languages**: Thai (Noto Sans Thai), Chinese (Noto Sans SC), English, +15 more
- Proper font auto-selection per language

## 🔧 Tech Stack

| Component | Technology |
|---|---|
| Vision AI | **Qwen3-VL** (Alibaba, Apache 2.0) via vLLM |
| Speech-to-Text | **insanely-fast-whisper** with AMD ROCm |
| Audio Analysis | **librosa** |
| Scene Detection | **PySceneDetect** |
| Video Processing | **ffmpeg** + MoviePy |
| Subtitle Engine | **pysubs2** (ASS format, karaoke support) |
| GPU Acceleration | **AMD Instinct MI300X** via ROCm 6.3 |
| Frontend | **Next.js 14** + shadcn/ui + Tailwind CSS |
| Backend | **FastAPI** + WebSocket progress streaming |
| Deployment | HuggingFace Spaces (Docker) |

## 📊 Multimodal AI Pipeline

```
Video → Scene Detection (PySceneDetect)
      → Audio (Whisper ROCm) → transcript + word timestamps
      → Audio Energy (librosa) → loud moment detection
      → Vision+Text Fusion (Qwen3-VL) → excitement score, face bbox, emotion
      → Multi-signal Score (0.4×vision + 0.35×audio + 0.25×text)
      → Top-N clip selection
      → Subtitle generation (pysubs2 ASS)
      → HRE: auto-zoom + silence removal + jump cuts + emoji
```

## 🛠️ Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py  # runs on :8000

# Frontend
cd frontend
npm install
npm run dev  # runs on :3000
```

## 🚀 AMD GPU Setup

```bash
# Install ROCm PyTorch
pip install torch --index-url https://download.pytorch.org/whl/rocm6.2

# Install vLLM for Qwen3-VL
pip install vllm --extra-index-url https://download.pytorch.org/whl/rocm6.2

# Start vLLM server
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-VL-7B-Instruct \
  --port 8001 --device rocm
```

## 🏆 Hackathon Details

- **Event**: AMD Developer Hackathon 2026
- **Track**: Track 3 — Vision & Multimodal AI
- **Partners**: AMD Developer Cloud, HuggingFace, Qwen/Alibaba Cloud
- **HF Space**: [ElevenClip-AI](https://huggingface.co/spaces/lablab-ai-amd-developer-hackathon/ElevenClip-AI)

## License

MIT — see [LICENSE](LICENSE)

# ElevenClip AI — HuggingFace Spaces (AMD ROCm) — Qwen2.5-VL-7B
FROM rocm/pytorch:rocm6.3_ubuntu22.04_py3.10_pytorch_release_2.3.0

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# ─── Backend Python dependencies ───────────────────────────────────────────
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# vLLM with ROCm support (installed separately from main requirements)
RUN pip install --no-cache-dir \
    "vllm>=0.6.0" \
    --extra-index-url https://download.pytorch.org/whl/rocm6.2

COPY backend/ /app/backend/

# ─── Frontend (Next.js) ────────────────────────────────────────────────────
COPY frontend/package*.json /app/frontend/
RUN cd /app/frontend && npm ci --production=false

COPY frontend/ /app/frontend/

# API URL is relative (same origin) in production
ENV NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_DEMO_ENABLED="true"

RUN cd /app/frontend && npm run build

# ─── Runtime directories ───────────────────────────────────────────────────
RUN mkdir -p /tmp/elevnclip /root/.cache/huggingface

# ─── Startup ──────────────────────────────────────────────────────────────
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 7860

CMD ["/app/start.sh"]

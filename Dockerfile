# ElevenClip AI — HuggingFace Spaces (AMD ROCm)
FROM rocm/pytorch:rocm6.3_ubuntu22.04_py3.10_pytorch_release_2.3.0

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    nginx \
    curl \
    git \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ─── Backend Python dependencies ───────────────────────────────────────────
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# vLLM with ROCm support
RUN pip install --no-cache-dir \
    "vllm>=0.6.0" \
    --extra-index-url https://download.pytorch.org/whl/rocm6.2

COPY backend/ /app/backend/

# ─── Frontend (Next.js standalone build) ──────────────────────────────────
COPY frontend/package*.json /app/frontend/
RUN cd /app/frontend && npm ci --production=false

COPY frontend/ /app/frontend/

# Relative API URL — nginx proxies /api/* and /ws/* to FastAPI :8080
ENV NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_DEMO_ENABLED="true"
ENV NEXT_PUBLIC_DEMO_ONLY="true"
ENV REMOTE_BACKEND_URL="http://129.212.178.101:8080"

RUN cd /app/frontend && npm run build

# ─── nginx config ──────────────────────────────────────────────────────────
COPY nginx.conf /app/nginx.conf

# ─── Runtime directories ───────────────────────────────────────────────────
RUN mkdir -p /tmp/elevnclip /root/.cache/huggingface /root/ElevenClip-AI/demo_videos

# ─── Startup ──────────────────────────────────────────────────────────────
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 7860

# vLLM managed on-demand by vllm_manager.py (not started at container startup)
ENV VLLM_ON_DEMAND="true"
ENV VLLM_PORT="8000"
ENV VLLM_IDLE_TIMEOUT="300"
ENV VLLM_DOCKER_CONTAINER=""

CMD ["/app/start.sh"]

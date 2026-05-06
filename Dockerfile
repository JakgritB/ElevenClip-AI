# ElevenClip AI — HuggingFace Spaces Dockerfile (AMD ROCm)
FROM rocm/pytorch:rocm6.3_ubuntu22.04_py3.10_pytorch_release_2.3.0

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# ─── Backend ───────────────────────────────────────────────────
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Install vLLM with ROCm
RUN pip install --no-cache-dir \
    "vllm>=0.6.0" \
    --extra-index-url https://download.pytorch.org/whl/rocm6.2

COPY backend/ /app/backend/

# ─── Frontend (pre-built) ──────────────────────────────────────
COPY frontend/package*.json /app/frontend/
RUN cd /app/frontend && npm ci --production=false

COPY frontend/ /app/frontend/
ENV NEXT_PUBLIC_API_URL=""
RUN cd /app/frontend && npm run build

# ─── vLLM model cache dir ─────────────────────────────────────
RUN mkdir -p /tmp/elevnclip /root/.cache/huggingface

# ─── Startup script ───────────────────────────────────────────
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 7860

CMD ["/app/start.sh"]

#!/bin/bash
set -e

echo "=== ElevenClip AI ==="
rocm-smi --showproductname 2>/dev/null | grep -v "^$" || echo "(no ROCm — CPU mode)"

# ── 1. nginx on :7860  ────────────────────────────────────────────────────────
# Proxies /api /ws /downloads → FastAPI :8080  |  / → Next.js :3000
echo "[1/3] nginx reverse proxy on :7860..."
cp /app/nginx.conf /etc/nginx/sites-enabled/default 2>/dev/null \
  || cp /app/nginx.conf /etc/nginx/conf.d/elevnclip.conf
nginx

# ── 2. Next.js standalone on :3000  ──────────────────────────────────────────
echo "[2/3] Next.js on :3000..."
cd /app/frontend/.next/standalone && node server.js --port 3000 &
NEXTJS_PID=$!

# ── 3. FastAPI on :8080  ──────────────────────────────────────────────────────
# vLLM starts on-demand via vllm_manager.py when the first job arrives.
echo "[3/3] FastAPI on :8080 (vLLM starts on first job)..."
export VLLM_ON_DEMAND=true
export VLLM_PORT=8000
export VLLM_IDLE_TIMEOUT=300
cd /app && uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8080 \
    --workers 1 \
    --log-level info

# ── Cleanup  ──────────────────────────────────────────────────────────────────
trap "nginx -s stop; kill $NEXTJS_PID 2>/dev/null; exit" SIGTERM SIGINT

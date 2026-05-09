#!/bin/bash
set -e

echo "=== ElevenClip AI ==="
rocm-smi --showproductname 2>/dev/null | grep -v "^$" || echo "(no ROCm — CPU mode)"

# ── 1. Next.js standalone on :3000  ──────────────────────────────────────────
echo "[1/3] Next.js on :3000..."
cd /app/frontend/.next/standalone
HOSTNAME=0.0.0.0 PORT=3000 node server.js &
NEXTJS_PID=$!

# ── 2. FastAPI on :8080  ──────────────────────────────────────────────────────
# vLLM starts on-demand via vllm_manager.py when the first job arrives.
echo "[2/3] FastAPI on :8080 (vLLM starts on first job)..."
export PYTHONPATH=/app/backend:/app
export VLLM_ON_DEMAND=true
export VLLM_PORT=8000
export VLLM_IDLE_TIMEOUT=300
cd /app && uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8080 \
    --workers 1 \
    --log-level info &
FASTAPI_PID=$!

# ── 3. nginx on :7860  ────────────────────────────────────────────────────────
# Proxies /api /ws /downloads → FastAPI :8080  |  / → Next.js :3000
echo "[3/3] nginx reverse proxy on :7860..."
rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf
cp /app/nginx.conf /etc/nginx/conf.d/elevnclip.conf
nginx -t
nginx -g "daemon off;" &
NGINX_PID=$!

# ── Cleanup  ──────────────────────────────────────────────────────────────────
trap "kill $NGINX_PID $FASTAPI_PID $NEXTJS_PID 2>/dev/null; exit" SIGTERM SIGINT
wait -n "$NGINX_PID" "$FASTAPI_PID" "$NEXTJS_PID"

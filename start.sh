#!/bin/bash
set -e

echo "=== ElevenClip AI ==="
echo "GPU: $(rocm-smi --showproductname 2>/dev/null | grep -v '^$' || echo 'CPU mode')"

# ── Start vLLM (Qwen2.5-VL) on AMD ROCm ─────────────────────────────────────
if command -v rocm-smi &> /dev/null; then
    echo "[1/3] Starting Qwen2.5-VL via vLLM on AMD ROCm..."
    vllm serve "Qwen/Qwen2.5-VL-7B-Instruct" \
        --port 8001 \
        --max-model-len 8192 \
        --trust-remote-code \
        --dtype float16 \
        --gpu-memory-utilization 0.7 \
        --limit-mm-per-prompt "image=3" &
    VLLM_PID=$!

    echo "Waiting for Qwen2.5-VL model to load (up to 10 minutes)..."
    READY=0
    for i in $(seq 1 120); do
        if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
            echo "vLLM ready after $((i * 5))s"
            READY=1
            break
        fi
        echo "  vLLM loading... ($((i * 5))s / 600s max)"
        sleep 5
    done

    if [ "$READY" -eq 0 ]; then
        echo "WARNING: vLLM did not respond in 600s — continuing without vision model"
        echo "  Pipeline will use audio+text signals only (fallback mode)"
    fi
else
    echo "No ROCm detected — running in CPU mode (no vision model)"
fi

# ── Start Next.js frontend ──────────────────────────────────────────────────
echo "[2/3] Starting Next.js frontend on :3000..."
cd /app/frontend && node server.js --port 3000 &
NEXTJS_PID=$!

# ── Start FastAPI backend ────────────────────────────────────────────────────
echo "[3/3] Starting FastAPI backend on :7860..."
cd /app && uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 7860 \
    --workers 1 \
    --log-level info

# Cleanup on exit
trap "kill $VLLM_PID $NEXTJS_PID 2>/dev/null; exit" SIGTERM SIGINT

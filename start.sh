#!/bin/bash
set -e

echo "Starting ElevenClip AI..."
echo "GPU: $(rocm-smi --showproductname 2>/dev/null || echo 'CPU mode')"

# Start vLLM server for Qwen3-VL (background)
if command -v rocm-smi &> /dev/null; then
    echo "Starting Qwen3-VL via vLLM (ROCm)..."
    python -m vllm.entrypoints.openai.api_server \
        --model "Qwen/Qwen3-VL-7B-Instruct" \
        --port 8001 \
        --device rocm \
        --max-model-len 8192 \
        --trust-remote-code \
        --dtype float16 &
    VLLM_PID=$!
    echo "vLLM started (PID $VLLM_PID), waiting 30s..."
    sleep 30
fi

# Start Next.js (frontend) in background
echo "Starting Next.js frontend..."
cd /app/frontend && node server.js --port 3000 &

# Start FastAPI backend (serves on :7860, also proxies static Next.js)
echo "Starting FastAPI backend on :7860..."
cd /app && uvicorn backend.main:app --host 0.0.0.0 --port 7860 --workers 1

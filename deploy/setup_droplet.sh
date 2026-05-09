#!/bin/bash
# ElevenClip AI — Full AMD Droplet Setup Script
# Run once after fresh boot: bash /root/setup_droplet.sh
set -e

LOG=/tmp/elevnclip_setup.log
exec > >(tee -a "$LOG") 2>&1

echo "=== ElevenClip AI Droplet Setup $(date) ==="

# ── 1. Update repo ────────────────────────────────────────────────────────────
echo "[1/5] Pulling latest code..."
cd /root/ElevenClip-AI
git pull origin master

# ── 2. Python venv + pip install ─────────────────────────────────────────────
echo "[2/5] Installing Python dependencies..."
if [ ! -f /root/venv/bin/activate ]; then
    python3 -m venv /root/venv
fi
source /root/venv/bin/activate
pip install --upgrade pip -q
pip install -r backend/requirements.txt -q
echo "PACKAGES_DONE"

# ── 3. Start vLLM inside Docker container ────────────────────────────────────
echo "[3/5] Starting vLLM with Qwen2.5-VL-7B-Instruct..."
docker start rocm 2>/dev/null || true
sleep 3

# Kill any stale vllm process
docker exec rocm bash -c "pkill -f 'vllm serve' 2>/dev/null || true"
sleep 2

# Start vLLM detached
docker exec -d rocm bash -c '
    vllm serve Qwen/Qwen2.5-VL-7B-Instruct \
        --port 8000 \
        --dtype float16 \
        --trust-remote-code \
        --max-model-len 4096 \
        --gpu-memory-utilization 0.7 \
        --limit-mm-per-prompt "image=3" \
        > /tmp/vllm.log 2>&1
'
echo "vLLM started in background (downloading model, may take 5-15 min)"

# ── 4. Start FastAPI backend on port 8080 ────────────────────────────────────
echo "[4/5] Starting FastAPI backend on :8080..."
pkill -f "uvicorn backend.main" 2>/dev/null || true
sleep 1

cd /root/ElevenClip-AI
VLLM_BASE_URL=http://localhost:8000/v1 \
VLLM_MODEL=Qwen/Qwen2.5-VL-7B-Instruct \
WORK_DIR=/tmp/elevnclip \
NEXT_PUBLIC_API_URL=http://localhost:8080 \
nohup /root/venv/bin/uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8080 \
    --workers 1 \
    --log-level info \
    > /tmp/fastapi.log 2>&1 &

echo "FastAPI PID: $!"
echo "FASTAPI_STARTED"

# ── 5. Poll vLLM health ───────────────────────────────────────────────────────
echo "[5/5] Waiting for vLLM to load model..."
for i in $(seq 1 180); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "vLLM READY after $((i * 5))s!"
        echo "VLLM_READY"
        break
    fi
    if [ $((i % 12)) -eq 0 ]; then
        echo "  Still loading... $((i * 5))s elapsed"
        docker exec rocm bash -c "tail -3 /tmp/vllm.log 2>/dev/null"
    fi
    sleep 5
done

echo ""
echo "=== Setup complete! ==="
echo "  FastAPI:  http://129.212.178.101:8080"
echo "  vLLM API: http://129.212.178.101:8000/v1"
echo "  Logs:     /tmp/fastapi.log | docker exec rocm cat /tmp/vllm.log"

#!/bin/bash
pkill -f uvicorn 2>/dev/null
sleep 1
cd /root/ElevenClip-AI/backend
export VLLM_BASE_URL=http://localhost:8000/v1
export VLLM_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
export WORK_DIR=/tmp/elevnclip
mkdir -p /tmp/elevnclip
nohup /root/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1 > /tmp/fastapi.log 2>&1 &
echo "FastAPI PID: $!"

"""On-demand vLLM process manager.

Starts vLLM when first needed, shuts it down after idle.
Set VLLM_ON_DEMAND=false to use an externally managed vLLM instead.
Set VLLM_IDLE_TIMEOUT=300 (seconds) to control the idle shutdown window.
"""
import os
import subprocess
import threading
import time

import requests
from loguru import logger

VLLM_MODEL   = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")
VLLM_PORT    = int(os.getenv("VLLM_PORT", "8000"))
IDLE_TIMEOUT = int(os.getenv("VLLM_IDLE_TIMEOUT", "300"))   # 5 min default
ON_DEMAND    = os.getenv("VLLM_ON_DEMAND", "true").lower() == "true"


class _VLLMManager:
    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._last_used = 0.0
        threading.Thread(target=self._watchdog, daemon=True, name="vllm-watchdog").start()

    # ── Public ────────────────────────────────────────────────────────────

    def is_running(self) -> bool:
        if not ON_DEMAND:
            return self._check_health()
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                return False
            return self._check_health()

    def ensure_running(self, progress_cb=None) -> None:
        """Start vLLM if not running. Blocks until healthy (max 3 min)."""
        if not ON_DEMAND:
            return
        with self._lock:
            if self._proc and self._proc.poll() is None and self._check_health():
                self._last_used = time.time()
                return
            self._start(progress_cb)

    def stop(self) -> None:
        if not ON_DEMAND:
            return
        with self._lock:
            self._stop_locked()

    def touch(self) -> None:
        """Reset idle timer — call after each successful vLLM API call."""
        self._last_used = time.time()

    def status(self) -> dict:
        running = self.is_running()
        idle = round(time.time() - self._last_used, 1) if self._last_used else None
        return {
            "running":      running,
            "on_demand":    ON_DEMAND,
            "idle_seconds": idle,
            "idle_timeout": IDLE_TIMEOUT,
            "model":        VLLM_MODEL,
        }

    # ── Internal ──────────────────────────────────────────────────────────

    def _health_url(self) -> str:
        return f"http://localhost:{VLLM_PORT}/health"

    def _check_health(self) -> bool:
        try:
            return requests.get(self._health_url(), timeout=2).status_code == 200
        except Exception:
            return False

    def _start(self, progress_cb=None) -> None:
        logger.info("vLLM: starting on demand…")
        if progress_cb:
            progress_cb("Starting AI model (Qwen3-VL)… ~2 min first time")

        import sys
        self._proc = subprocess.Popen(
            [
                sys.executable, "-m", "vllm.entrypoints.openai.api_server",
                "--model", VLLM_MODEL,
                "--device", "rocm",
                "--port", str(VLLM_PORT),
                "--gpu-memory-utilization", "0.85",
                "--max-model-len", "4096",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        deadline = time.time() + 200
        tick = 0
        while time.time() < deadline:
            time.sleep(5)
            tick += 1
            if self._proc.poll() is not None:
                err = self._proc.stderr.read().decode()[-600:]
                raise RuntimeError(f"vLLM exited during startup: {err}")
            if self._check_health():
                self._last_used = time.time()
                logger.info(f"vLLM ready after {tick * 5}s")
                return
            if progress_cb and tick % 6 == 0:
                progress_cb(f"AI model loading… {tick * 5}s")

        raise RuntimeError("vLLM did not start within 200s")

    def _stop_locked(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
            logger.info("vLLM stopped")

    def _watchdog(self) -> None:
        while True:
            time.sleep(60)
            if not ON_DEMAND or IDLE_TIMEOUT <= 0:
                continue
            with self._lock:
                if (self._proc
                        and self._proc.poll() is None
                        and self._last_used > 0
                        and time.time() - self._last_used > IDLE_TIMEOUT):
                    logger.info(
                        f"vLLM idle {IDLE_TIMEOUT}s → shutting down to save GPU credits"
                    )
                    self._stop_locked()


_manager = _VLLMManager()


# ── Module-level helpers ──────────────────────────────────────────────────────

def ensure_vllm_running(progress_cb=None) -> None:
    _manager.ensure_running(progress_cb)


def vllm_touch() -> None:
    _manager.touch()


def vllm_stop() -> None:
    _manager.stop()


def vllm_is_running() -> bool:
    return _manager.is_running()


def vllm_status() -> dict:
    return _manager.status()

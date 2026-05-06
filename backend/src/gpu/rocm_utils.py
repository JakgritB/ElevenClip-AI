"""AMD ROCm device management and monitoring."""
import os
import subprocess
from loguru import logger


def get_device() -> str:
    """Return 'cuda' (ROCm uses cuda device name in PyTorch) or 'cpu'."""
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"GPU detected: {device_name}")
            return "cuda"
    except ImportError:
        pass
    logger.warning("No GPU available, falling back to CPU")
    return "cpu"


def get_vram_gb() -> float:
    """Return available VRAM in GB."""
    try:
        import torch
        if torch.cuda.is_available():
            total = torch.cuda.get_device_properties(0).total_memory
            return round(total / 1024**3, 1)
    except Exception:
        pass
    return 0.0


def get_gpu_utilization() -> dict:
    """Return GPU utilization stats via rocm-smi."""
    try:
        result = subprocess.run(
            ["rocm-smi", "--showuse", "--showmemuse", "--csv"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                headers = lines[0].split(",")
                values = lines[1].split(",")
                return dict(zip(headers, values))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: PyTorch memory stats
    try:
        import torch
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / 1024**3
            reserved = torch.cuda.memory_reserved(0) / 1024**3
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            return {
                "vram_used_gb": round(allocated, 2),
                "vram_reserved_gb": round(reserved, 2),
                "vram_total_gb": round(total, 2),
                "vram_pct": round(allocated / total * 100, 1) if total > 0 else 0,
            }
    except Exception:
        pass
    return {}


def get_optimal_batch_size(model_type: str = "whisper") -> int:
    """Return optimal batch size based on available VRAM."""
    vram = get_vram_gb()
    if model_type == "whisper":
        if vram >= 48:
            return 32
        elif vram >= 24:
            return 16
        elif vram >= 16:
            return 8
        return 4
    elif model_type == "vision":
        if vram >= 80:
            return 8
        elif vram >= 48:
            return 4
        return 1
    return 1


def log_gpu_status():
    stats = get_gpu_utilization()
    if stats:
        logger.info(f"GPU stats: {stats}")
    else:
        logger.info(f"GPU: {get_device()} | VRAM: {get_vram_gb()} GB")

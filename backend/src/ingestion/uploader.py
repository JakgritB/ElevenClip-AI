"""Handle file upload from user."""
import shutil
from pathlib import Path
from fastapi import UploadFile
from loguru import logger

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
MAX_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB


async def save_upload(
    file: UploadFile,
    output_dir: Path,
    session_id: str,
) -> Path:
    """Save uploaded video file to disk."""
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}. Allowed: {ALLOWED_EXTENSIONS}")

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / f"{session_id}_input{suffix}"

    size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            size += len(chunk)
            if size > MAX_SIZE_BYTES:
                dest.unlink(missing_ok=True)
                raise ValueError("File too large (max 2 GB)")
            f.write(chunk)

    logger.info(f"Saved upload: {dest} ({size / 1024 / 1024:.1f} MB)")
    return dest

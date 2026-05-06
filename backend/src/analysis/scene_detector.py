"""Scene detection using PySceneDetect."""
from pathlib import Path
from typing import Optional
from loguru import logger


def detect_scenes(
    video_path: Path,
    threshold: float = 27.0,
    min_scene_len_sec: float = 2.0,
) -> list[dict]:
    """Detect scene cuts and return list of scenes with timestamps.

    Returns:
        [{"start": float, "end": float, "duration": float}, ...]
    """
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector

        video = open_video(str(video_path))
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=threshold))

        logger.info(f"Running scene detection on: {video_path.name}")
        scene_manager.detect_scenes(video, show_progress=False)
        scene_list = scene_manager.get_scene_list()

        scenes = []
        for start_tc, end_tc in scene_list:
            start = start_tc.get_seconds()
            end = end_tc.get_seconds()
            duration = end - start
            if duration >= min_scene_len_sec:
                scenes.append({"start": start, "end": end, "duration": duration})

        logger.info(f"Detected {len(scenes)} scenes")
        return scenes

    except ImportError:
        logger.warning("scenedetect not installed, using fixed-interval fallback")
        return _fixed_interval_scenes(video_path, interval_sec=5.0)
    except Exception as e:
        logger.error(f"Scene detection failed: {e}")
        return _fixed_interval_scenes(video_path, interval_sec=5.0)


def _fixed_interval_scenes(video_path: Path, interval_sec: float = 5.0) -> list[dict]:
    """Fallback: split video into fixed-interval scenes."""
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True
    )
    try:
        total = float(result.stdout.strip())
    except ValueError:
        total = 300.0

    scenes = []
    t = 0.0
    while t < total:
        end = min(t + interval_sec, total)
        scenes.append({"start": t, "end": end, "duration": end - t})
        t = end
    return scenes


def sample_frames(
    video_path: Path,
    scenes: list[dict],
    output_dir: Path,
    frames_per_scene: int = 3,
) -> list[dict]:
    """Extract representative frames from each scene for vision analysis.

    Returns scenes with added 'frame_paths' key.
    """
    import subprocess
    output_dir.mkdir(parents=True, exist_ok=True)

    result_scenes = []
    for i, scene in enumerate(scenes):
        mid = scene["start"] + scene["duration"] / 2
        frame_paths = []

        # Sample frames at start, middle, end of scene
        timestamps = [
            scene["start"] + scene["duration"] * 0.2,
            mid,
            scene["start"] + scene["duration"] * 0.8,
        ][:frames_per_scene]

        for j, ts in enumerate(timestamps):
            frame_path = output_dir / f"scene_{i:04d}_frame_{j}.jpg"
            cmd = [
                "ffmpeg", "-y", "-ss", str(ts), "-i", str(video_path),
                "-vframes", "1", "-q:v", "2", "-vf", "scale=640:-1",
                str(frame_path)
            ]
            subprocess.run(cmd, capture_output=True)
            if frame_path.exists():
                frame_paths.append(str(frame_path))

        result_scenes.append({**scene, "index": i, "frame_paths": frame_paths})

    return result_scenes

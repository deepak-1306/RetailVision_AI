"""
Video preprocessing: validate an uploaded CCTV clip, extract metadata,
and yield sampled frames at a fixed FPS for the detection stage.

Kept dependency-light (OpenCV only) so it runs identically in the API
container and the Celery worker container.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


@dataclass
class VideoMetadata:
    fps: float
    width: int
    height: int
    frame_count: int
    duration_seconds: float


@dataclass
class SampledFrame:
    index: int          # index within the sampled sequence
    frame_number: int    # original frame number in the source video
    timestamp: float     # seconds into the video
    image: np.ndarray    # BGR frame


class VideoPreprocessor:
    """Loads a video file and exposes metadata + a frame sampling iterator."""

    def __init__(self, video_path: str, sample_fps: float = 5.0):
        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        self.sample_fps = sample_fps

    def get_metadata(self) -> VideoMetadata:
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {self.video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps else 0.0
        cap.release()
        return VideoMetadata(fps=fps, width=width, height=height,
                              frame_count=frame_count, duration_seconds=duration)

    def iter_sampled_frames(self) -> Iterator[SampledFrame]:
        """Yield frames sampled at self.sample_fps, regardless of source FPS."""
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {self.video_path}")

        source_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        step = max(int(round(source_fps / self.sample_fps)), 1)

        frame_number = 0
        sampled_index = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_number % step == 0:
                timestamp = frame_number / source_fps
                yield SampledFrame(
                    index=sampled_index,
                    frame_number=frame_number,
                    timestamp=timestamp,
                    image=frame,
                )
                sampled_index += 1
            frame_number += 1
        cap.release()

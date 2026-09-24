"""
Live streaming inference session.

Wraps the *same* YOLOv11 detector, ByteTrack tracker, and Video Swin
Transformer behaviour classifier used by the offline batch pipeline
(`ai/pipeline/run_pipeline.py`) so that live camera frames pushed over the
`/api/v1/live/ws` WebSocket get bounding boxes, stable track IDs, and
behaviour labels in real time -- with zero duplication of detection /
tracking / behaviour-recognition logic.

One `LiveStreamSession` is created per connected WebSocket client (i.e. per
live camera feed) and lives for the duration of that connection. Frames are
pushed in one at a time via `process_jpeg_frame()`, which mirrors the inner
loop of `run_pipeline()` but operates on a single frame instead of an
iterator over a whole video file, and keeps a small `_last_behaviour` cache
per track so a label persists on screen between the classifier's
observation windows instead of flickering to "analyzing" every frame.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from ai.behaviour.behaviour_classifier import (
    BEHAVIOUR_LABELS,
    TrackObservation,
    VideoSwinBehaviourClassifier,
)
from ai.behaviour.zones import DEFAULT_SHELF_ZONES
from ai.detection.yolo_detector import YoloDetector
from ai.tracking.byte_tracker import ByteTracker
from app.core.config import settings

# Behaviours worth surfacing as a discrete "event" in the live activity feed
# (as opposed to steady-state states like "viewing" / "analyzing").
_NOTABLE_BEHAVIOURS = {
    "picking",
    "picking_and_returning",
    "picking_and_putting_back",
    "touching",
}


class LiveStreamSession:
    """Stateful per-connection wrapper around the detect -> track -> classify chain."""

    def __init__(self, store_zone: Optional[str] = None):
        self.store_zone = store_zone

        self.detector = YoloDetector(
            weights_path=settings.YOLO_WEIGHTS_PATH,
            confidence_threshold=settings.YOLO_CONFIDENCE_THRESHOLD,
            iou_threshold=settings.YOLO_IOU_THRESHOLD,
            device=settings.DEVICE,
        )
        self.tracker = ByteTracker(
            track_thresh=settings.BYTETRACK_TRACK_THRESH,
            match_thresh=settings.BYTETRACK_MATCH_THRESH,
            track_buffer=settings.BYTETRACK_TRACK_BUFFER,
        )

        swin_weights = settings.VIDEO_SWIN_WEIGHTS_PATH
        has_swin_weights = bool(swin_weights and Path(swin_weights).exists())
        self.classifier = VideoSwinBehaviourClassifier(
            weights_path=swin_weights if has_swin_weights else None,
            clip_len=settings.VIDEO_SWIN_CLIP_LEN,
            frame_stride=settings.VIDEO_SWIN_FRAME_STRIDE,
            device=settings.DEVICE,
        )

        # track_id -> last known behaviour label, so the UI shows a sticky
        # label instead of blanking out between classification windows.
        self._last_behaviour: dict[int, dict] = {}
        # track_id -> last behaviour_type we already emitted an event for,
        # so the activity feed logs a *change* in behaviour, not every frame.
        self._last_emitted: dict[int, str] = {}

        self._stream_start = time.monotonic()
        self._last_process_time = self._stream_start
        self._ema_fps = 0.0
        self.frame_count = 0
        self.total_unique_tracks: set[int] = set()

    # ---------------------------------------------------------------- info
    def engine_info(self) -> dict:
        return {
            "video_swin_active": getattr(self.classifier, "_has_weights", False),
            "behaviour_labels": BEHAVIOUR_LABELS,
            "shelf_zones": [z.name for z in DEFAULT_SHELF_ZONES],
            "max_stream_width": settings.LIVE_STREAM_MAX_WIDTH,
            "target_fps": settings.LIVE_STREAM_TARGET_FPS,
        }

    # --------------------------------------------------------------- reset
    def reset(self) -> None:
        """Clear tracking/behaviour state (e.g. after the client swaps cameras)."""
        self.tracker = ByteTracker(
            track_thresh=settings.BYTETRACK_TRACK_THRESH,
            match_thresh=settings.BYTETRACK_MATCH_THRESH,
            track_buffer=settings.BYTETRACK_TRACK_BUFFER,
        )
        self._last_behaviour.clear()
        self._last_emitted.clear()
        self._stream_start = time.monotonic()
        self._last_process_time = self._stream_start
        self.frame_count = 0
        self.total_unique_tracks.clear()

    def close(self) -> None:
        self._last_behaviour.clear()
        self._last_emitted.clear()

    # ------------------------------------------------------------- helpers
    def _resize_if_needed(self, frame: np.ndarray) -> np.ndarray:
        max_width = settings.LIVE_STREAM_MAX_WIDTH
        h, w = frame.shape[:2]
        if w <= max_width:
            return frame
        scale = max_width / w
        return cv2.resize(frame, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)

    # ------------------------------------------------------------- process
    def process_jpeg_frame(self, jpeg_bytes: bytes) -> dict:
        """Decode one JPEG frame and run detection + tracking + behaviour recognition."""
        now = time.monotonic()

        buffer = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if frame is None:
            return {"type": "error", "message": "Could not decode frame"}

        frame = self._resize_if_needed(frame)
        h, w = frame.shape[:2]
        self.frame_count += 1
        timestamp = now - self._stream_start

        detections = self.detector.detect(frame)
        tracks = self.tracker.update(detections)

        track_payloads = []
        behaviour_counts: dict[str, int] = {}
        events: list[dict] = []

        for track in tracks:
            self.total_unique_tracks.add(track.track_id)
            obs = TrackObservation(
                track_id=track.track_id,
                timestamp=timestamp,
                bbox=track.bbox,
                frame_width=w,
                frame_height=h,
            )
            segment = self.classifier.observe(obs)
            if segment is not None:
                self._last_behaviour[track.track_id] = {
                    "behaviour_type": segment.behaviour_type,
                    "confidence": round(segment.confidence, 2),
                    "shelf_zone": segment.shelf_zone,
                }

            behaviour_info = self._last_behaviour.get(
                track.track_id,
                {"behaviour_type": "analyzing", "confidence": 0.0, "shelf_zone": "Unzoned"},
            )
            behaviour_type = behaviour_info["behaviour_type"]
            behaviour_counts[behaviour_type] = behaviour_counts.get(behaviour_type, 0) + 1

            # emit a one-shot "event" the first time a track flips into a
            # notable behaviour, so the frontend can show a live activity feed
            if (
                behaviour_type in _NOTABLE_BEHAVIOURS
                and self._last_emitted.get(track.track_id) != behaviour_type
            ):
                events.append(
                    {
                        "track_id": track.track_id,
                        "behaviour_type": behaviour_type,
                        "shelf_zone": behaviour_info["shelf_zone"],
                        "confidence": behaviour_info["confidence"],
                        "timestamp": round(timestamp, 2),
                    }
                )
            self._last_emitted[track.track_id] = behaviour_type

            x1, y1, x2, y2 = track.bbox
            track_payloads.append(
                {
                    "track_id": track.track_id,
                    "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                    "behaviour_type": behaviour_type,
                    "behaviour_confidence": behaviour_info["confidence"],
                    "shelf_zone": behaviour_info["shelf_zone"],
                }
            )

        # exponential moving-average FPS so the readout doesn't jitter frame to frame
        elapsed = max(now - self._last_process_time, 1e-6)
        instant_fps = 1.0 / elapsed
        self._ema_fps = instant_fps if self._ema_fps == 0 else (0.8 * self._ema_fps + 0.2 * instant_fps)
        self._last_process_time = now

        return {
            "type": "detections",
            "frame_width": w,
            "frame_height": h,
            "timestamp": round(timestamp, 2),
            "processing_fps": round(self._ema_fps, 1),
            "person_count": len(track_payloads),
            "total_unique_visitors": len(self.total_unique_tracks),
            "behaviour_counts": behaviour_counts,
            "tracks": track_payloads,
            "events": events,
            "shelf_zones": [
                {"name": z.name, "x1": z.x1, "y1": z.y1, "x2": z.x2, "y2": z.y2}
                for z in DEFAULT_SHELF_ZONES
            ],
            "engine": "video_swin_transformer"
            if getattr(self.classifier, "_has_weights", False)
            else "video_swin_transformer_heuristic_fallback",
            "store_zone": self.store_zone,
        }

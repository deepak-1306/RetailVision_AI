"""
Annotated frame preview endpoint.

Provides two endpoints:
  GET /videos/{video_id}/frame-count   → total frame count + fps
  GET /videos/{video_id}/frame/{n}     → JPEG of frame N with detections,
                                          track IDs, and behaviour labels drawn on

The detector and tracker are cached per video_id in a module-level dict so
successive scrub/play requests reuse the same stateful tracker instead of
creating a new one (and therefore losing track continuity) for every call.
A simple LRU-cap of 4 cached sessions prevents unbounded memory growth.
"""
from __future__ import annotations

import io
import threading
from collections import OrderedDict
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.behaviour import BehaviourEvent
from app.models.user import User
from app.models.video import Video
from ai.detection.yolo_detector import YoloDetector
from ai.tracking.byte_tracker import ByteTracker

router = APIRouter(prefix="/videos", tags=["Frame Preview"])

# Palette — one bright colour per track_id (mod 20)
_PALETTE = [
    (255, 56, 56), (255, 157, 151), (255, 112, 31), (255, 178, 29),
    (207, 210, 49), (72, 249, 10), (146, 204, 23), (61, 219, 134),
    (26, 147, 52), (0, 212, 187), (44, 153, 168), (0, 194, 255),
    (52, 69, 147), (100, 115, 255), (0, 24, 236), (132, 56, 255),
    (82, 0, 133), (203, 56, 255), (255, 149, 200), (255, 55, 199),
]


def _colour(track_id: int) -> tuple:
    return _PALETTE[track_id % len(_PALETTE)]


# ── per-video session cache ──────────────────────────────────────────────────

class _VideoSession:
    """Holds an open cv2.VideoCapture + stateful detector/tracker for one video.

    A threading.Lock serialises all VideoCapture reads so that concurrent HTTP
    requests for the same video don't trigger the libavcodec pthread assertion
    crash: `Assertion fctx->async_lock failed at libavcodec/pthread_frame.c:173`
    """

    def __init__(self, video_path: str):
        self._lock = threading.Lock()
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.detector = YoloDetector(
            weights_path=settings.YOLO_WEIGHTS_PATH,
            confidence_threshold=settings.YOLO_CONFIDENCE_THRESHOLD,
            iou_threshold=settings.YOLO_IOU_THRESHOLD,
            device=settings.DEVICE,
        )
        # One tracker instance per video so track IDs stay stable across calls
        self.tracker = ByteTracker(
            track_thresh=settings.BYTETRACK_TRACK_THRESH,
            match_thresh=settings.BYTETRACK_MATCH_THRESH,
            track_buffer=settings.BYTETRACK_TRACK_BUFFER,
        )
        # frame_index → list of active tracks at that frame
        self._frame_cache: dict[int, list] = {}

    def get_annotated_frame(self, frame_index: int, behaviour_map: dict[int, str]) -> bytes:
        """Return a JPEG-encoded annotated frame at the given index.
        Thread-safe: acquires self._lock before touching VideoCapture.
        """
        with self._lock:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("Could not read frame")

        detections = self.detector.detect(frame)
        tracks = self.tracker.update(detections)
        self._frame_cache[frame_index] = tracks

        h, w = frame.shape[:2]
        for track in tracks:
            x1, y1, x2, y2 = (int(v) for v in track.bbox)
            colour = _colour(track.track_id)
            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)
            label = f"#{track.track_id}"
            behaviour = behaviour_map.get(track.track_id)
            if behaviour:
                label += f" {behaviour.replace('_', ' ')}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), colour, -1)
            cv2.putText(frame, label, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
        return buf.tobytes()

    def close(self):
        with self._lock:
            self.cap.release()


_MAX_SESSIONS = 4
_sessions: OrderedDict[str, _VideoSession] = OrderedDict()


def _get_session(video_id: str, video_path: str) -> _VideoSession:
    if video_id in _sessions:
        _sessions.move_to_end(video_id)
        return _sessions[video_id]
    if len(_sessions) >= _MAX_SESSIONS:
        _, old = _sessions.popitem(last=False)
        old.close()
    session = _VideoSession(video_path)
    _sessions[video_id] = session
    return session


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_owned_video(db: Session, video_id: str, user: User) -> Video:
    video = db.query(Video).filter(Video.id == video_id, Video.owner_id == user.id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


def _build_behaviour_map(db: Session, video_id: str, timestamp: float) -> dict[int, str]:
    """Build track_id → behaviour label for the given timestamp from processed BehaviourEvents."""
    from app.models.job import ProcessingJob, JobStatus
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.video_id == video_id, ProcessingJob.status == JobStatus.COMPLETED)
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )
    if not job:
        return {}
    
    # Only map behaviours that are actively occurring at this timestamp
    events = db.query(BehaviourEvent).filter(
        BehaviourEvent.job_id == job.id,
        BehaviourEvent.start_time_seconds <= timestamp,
        BehaviourEvent.end_time_seconds >= timestamp
    ).all()
    
    mapping: dict[int, str] = {}
    for e in events:
        mapping[e.track_id] = e.behaviour_type.value
    return mapping


# ── endpoints ────────────────────────────────────────────────────────────────

@router.get("/{video_id}/frame-count")
def get_frame_count(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    video = _get_owned_video(db, video_id, current_user)
    try:
        session = _get_session(video_id, video.storage_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"count": session.total_frames, "fps": session.fps, "video_id": video_id}


@router.get("/{video_id}/frame/{frame_index}")
def get_frame(
    video_id: str,
    frame_index: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    video = _get_owned_video(db, video_id, current_user)
    try:
        session = _get_session(video_id, video.storage_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if frame_index < 0 or frame_index >= session.total_frames:
        raise HTTPException(status_code=400, detail="frame_index out of range")

    timestamp = frame_index / session.fps
    behaviour_map = _build_behaviour_map(db, video_id, timestamp)
    try:
        jpeg = session.get_annotated_frame(frame_index, behaviour_map)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(content=jpeg, media_type="image/jpeg")

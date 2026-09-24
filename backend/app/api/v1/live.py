"""
Live video streaming endpoints.

Exposes a WebSocket (`/api/v1/live/ws`) that a browser (or any client) can
push camera frames to and receive, in real time, YOLOv11 person detections
with stable ByteTrack IDs plus a Video Swin Transformer behaviour label
(viewing / touching / picking / etc.) for each tracked customer -- the same
CV/behaviour stack used by the offline upload-and-process pipeline, just
run one frame at a time instead of over a stored video file.

Protocol
--------
Client connects to:  wss://<host>/api/v1/live/ws?token=<jwt-access-token>&store_zone=<optional label>

The server immediately sends a `{"type": "ready", ...}` message describing
which behaviour engine is active plus the configured shelf zones.

The client then sends binary WebSocket frames, each one a single JPEG-encoded
image. For every frame received, the server replies with a JSON message:

    {
      "type": "detections",
      "frame_width": 960, "frame_height": 540,
      "timestamp": 12.34, "processing_fps": 18.2,
      "person_count": 2, "total_unique_visitors": 5,
      "behaviour_counts": {"viewing": 1, "picking": 1},
      "tracks": [
        {"track_id": 1, "bbox": [x1,y1,x2,y2],
         "behaviour_type": "viewing", "behaviour_confidence": 0.78,
         "shelf_zone": "Zone B - Center Shelf"}
      ],
      "events": [{"track_id": 1, "behaviour_type": "picking", ...}],
      "shelf_zones": [{"name": "...", "x1": 0, "y1": 0, "x2": 0.33, "y2": 1}],
      "engine": "video_swin_transformer" | "video_swin_transformer_heuristic_fallback"
    }

The client may also send small text control messages:
  - `{"type": "reset"}` clears tracking state (e.g. after switching cameras)
  - `{"type": "ping"}` gets a `{"type": "pong"}` reply (keepalive/RTT probe)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.live_stream_service import LiveStreamSession

router = APIRouter(prefix="/live", tags=["Live Stream"])


def _authenticate_ws_user(token: str | None, db: Session) -> User | None:
    """Validate the JWT access token passed as a query param.

    Browsers cannot attach an Authorization header to a native WebSocket
    handshake, so the live-stream client authenticates by passing the same
    access token issued by /auth/login as a `?token=` query parameter
    instead. This reuses the exact same token verification the REST API
    uses (app.core.security.decode_token) -- no new auth mechanism.
    """
    if not token:
        return None
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


@router.get("/status")
def live_status() -> dict:
    """Lets the frontend show which behaviour-recognition engine is live before connecting."""
    has_swin_weights = bool(
        settings.VIDEO_SWIN_WEIGHTS_PATH and Path(settings.VIDEO_SWIN_WEIGHTS_PATH).exists()
    )
    return {
        "detector": "YOLOv11 (COCO person class)",
        "tracker": "ByteTrack",
        "behaviour_engine": "Video Swin Transformer",
        "video_swin_active": has_swin_weights,
        "video_swin_note": (
            "Fine-tuned Swin3D checkpoint loaded."
            if has_swin_weights
            else "No fine-tuned checkpoint at VIDEO_SWIN_WEIGHTS_PATH -- running the same "
            "explainable heuristic fallback used by the offline pipeline until one is provided."
        ),
        "max_stream_width": settings.LIVE_STREAM_MAX_WIDTH,
        "target_fps": settings.LIVE_STREAM_TARGET_FPS,
    }


@router.websocket("/ws")
async def live_stream_ws(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    store_zone: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> None:
    user = _authenticate_ws_user(token, db)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    session = LiveStreamSession(store_zone=store_zone)
    started_at = time.monotonic()

    try:
        await websocket.send_json({"type": "ready", **session.engine_info()})

        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            frame_bytes = message.get("bytes")
            if frame_bytes is not None:
                result = session.process_jpeg_frame(frame_bytes)
                result["elapsed_seconds"] = round(time.monotonic() - started_at, 2)
                await websocket.send_json(result)
                continue

            text = message.get("text")
            if text:
                try:
                    control = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if control.get("type") == "reset":
                    session.reset()
                    await websocket.send_json({"type": "reset_ack"})
                elif control.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        session.close()

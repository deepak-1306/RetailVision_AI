"""
Annotated video generator.

Reads the ORIGINAL uploaded video frame-by-frame, overlays detection/
behaviour results and writes a NEW annotated MP4.

Robust design:
  - Streams frames directly into bundled FFmpeg subprocess (libx264, yuv420p, +faststart).
  - 100% browser-compatible (no Code 4 unsupported codec errors).
  - Zero RAM bloat (frame-by-frame streaming).
  - Handles 1080p, 4K videos gracefully by scaling down to max 854x480.
  - Accurately scales bounding box coordinates so annotations align with video content.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, Optional

import cv2
import imageio_ffmpeg
import numpy as np

from ai.behaviour.behaviour_classifier import BehaviourSegment

ProgressCallback = Optional[Callable[[str, int], None]]

_MAX_OUTPUT_WIDTH  = 1280
_MAX_OUTPUT_HEIGHT = 720

_PALETTE = [
    (255, 56, 56),   (255, 157, 151), (255, 112, 31),  (255, 178, 29),
    (207, 210, 49),  (72, 249, 10),   (146, 204, 23),  (61, 219, 134),
    (26, 147, 52),   (0, 212, 187),   (44, 153, 168),  (0, 194, 255),
    (52, 69, 147),   (100, 115, 255), (0, 24, 236),    (132, 56, 255),
    (82, 0, 133),    (203, 56, 255),  (255, 149, 200), (255, 55, 199),
]

_BEHAVIOUR_DISPLAY = {
    "viewing":                  "VIEWING",
    "touching":                 "TOUCHING",
    "picking":                  "PICKING",
    "picking_and_returning":    "PICK+RETURN",
    "picking_and_putting_back": "PICK+PUT BACK",
    "no_interest_in_buying":    "NO INTEREST",
    "turning_towards_shelf":    "TURNING",
}

_BEHAVIOUR_COLOUR = {
    "viewing":                  (200, 100, 255),
    "touching":                 (50, 200, 80),
    "picking":                  (50, 180, 255),
    "picking_and_returning":    (50, 50, 240),
    "picking_and_putting_back": (50, 120, 255),
    "no_interest_in_buying":    (140, 140, 140),
    "turning_towards_shelf":    (200, 200, 50),
}


def _colour(track_id: int) -> tuple:
    return _PALETTE[track_id % len(_PALETTE)]


def _intent_colour_bgr(label: str) -> tuple:
    return {"high": (50, 210, 50), "medium": (50, 160, 255), "low": (60, 60, 200)}.get(label, (100, 100, 100))


def _draw_text_bg(frame: np.ndarray, text: str, x: int, y: int,
                  bg: tuple, fg: tuple = (255, 255, 255),
                  scale: float = 0.45, thick: int = 1) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), bl = cv2.getTextSize(text, font, scale, thick)
    p = 3
    cv2.rectangle(frame, (x - p, y - th - p - bl), (x + tw + p, y + bl + p), bg, -1)
    cv2.putText(frame, text, (x, y), font, scale, fg, thick, cv2.LINE_AA)


def _build_track_state(
    segments: list[BehaviourSegment],
    predictions: dict[int, tuple[float, str]],
) -> dict[int, list[dict]]:
    state: dict[int, list[dict]] = {}
    for seg in sorted(segments, key=lambda s: s.start_time):
        score, label = predictions.get(seg.track_id, (0.0, "low"))
        state.setdefault(seg.track_id, []).append({
            "start": seg.start_time, "end": seg.end_time,
            "bbox": seg.bbox, "behaviour": seg.behaviour_type,
            "zone": seg.shelf_zone, "intent_label": label, "intent_score": score,
        })
    return state


def _active_tracks_at(track_state: dict, timestamp: float, lookahead: float = 0.5) -> list[dict]:
    active = []
    for track_id, segs in track_state.items():
        best, best_dist = None, float("inf")
        for seg in segs:
            if (seg["start"] - lookahead) <= timestamp <= (seg["end"] + lookahead):
                dist = abs(timestamp - (seg["start"] + seg["end"]) / 2)
                if dist < best_dist:
                    best_dist = dist
                    best = seg
        if best is not None:
            active.append({"track_id": track_id, **best})
    return active


def _scale_dims(width: int, height: int) -> tuple[int, int]:
    scale = min(_MAX_OUTPUT_WIDTH / width, _MAX_OUTPUT_HEIGHT / height, 1.0)
    return int(width * scale) & ~1, int(height * scale) & ~1


def _annotate_frame(
    frame: np.ndarray,
    timestamp: float,
    active: list[dict],
    frame_number: int,
    total_frames: int,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> np.ndarray:
    h, w = frame.shape[:2]

    for info in active:
        tid = info["track_id"]
        beh = info["behaviour"]
        raw_x1, raw_y1, raw_x2, raw_y2 = info["bbox"]

        # Scale coordinates accurately to match frame dimensions
        x1 = max(0, int(raw_x1 * scale_x))
        y1 = max(0, int(raw_y1 * scale_y))
        x2 = min(w - 1, int(raw_x2 * scale_x))
        y2 = min(h - 1, int(raw_y2 * scale_y))

        if x2 <= x1 + 2 or y2 <= y1 + 2:
            continue

        box_col = _colour(tid)
        beh_col = _BEHAVIOUR_COLOUR.get(beh, (180, 180, 180))
        beh_name = _BEHAVIOUR_DISPLAY.get(beh, beh.upper()[:14])

        # Bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_col, 2)

        # Corner accents
        corner = min(10, (x2 - x1) // 4, (y2 - y1) // 4)
        for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
            cv2.rectangle(frame,(cx,cy),(cx+dx*corner,cy+dy*3),box_col,-1)
            cv2.rectangle(frame,(cx,cy),(cx+dx*3,cy+dy*corner),box_col,-1)

        # Behaviour label
        label_y = max(y1 - 4, 22)
        _draw_text_bg(frame, beh_name, x1, label_y, beh_col)

        # ID label
        _draw_text_bg(frame, f"ID:{tid}", x1, max(label_y - 16, 6), (30, 30, 30))

        # Zone
        zone = info.get("zone", "")
        if zone and zone != "Unzoned":
            _draw_text_bg(frame, zone, x1, min(h - 4, y2 + 14), (50, 50, 50), (180, 180, 180), 0.36)

        # Intent badge
        intent = info["intent_label"].upper()
        score = info.get("intent_score", 0.0)
        ic = _intent_colour_bgr(info["intent_label"])
        _draw_text_bg(frame, f"INTENT:{intent} ({score:.0f}%)", max(x1, x2 - 110), min(h - 4, y2 + 28), ic, (255,255,255), 0.36)

    # HUD
    hud_h, hud_w = 40, 240
    if h > hud_h + 8 and w > hud_w + 8:
        roi = frame[4:4 + hud_h, 4:4 + hud_w]
        hud = np.full_like(roi, 20)
        cv2.putText(hud, f"T:{timestamp:.1f}s  {len(active)} person(s)", (6, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 230, 255), 1, cv2.LINE_AA)
        cv2.putText(hud, "RetailVision AI", (6, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.34, (100, 180, 100), 1, cv2.LINE_AA)
        pct = frame_number / max(total_frames - 1, 1)
        cv2.rectangle(hud, (6, 35), (6 + int(228 * pct), 39), (80, 200, 120), -1)
        cv2.rectangle(hud, (6, 35), (234, 39), (60, 60, 60), 1)
        frame[4:4 + hud_h, 4:4 + hud_w] = cv2.addWeighted(roi, 0.2, hud, 0.8, 0)

    return frame


def generate_annotated_video(
    input_video_path: str,
    output_video_path: str,
    segments: list[BehaviourSegment],
    predictions: dict[int, tuple[float, str]],
    progress_cb: ProgressCallback = None,
) -> str:
    """
    Generate a 100% browser-compatible H.264 MP4 with faststart.
    """
    def _cb(status: str, pct: int) -> None:
        if progress_cb:
            progress_cb(status, pct)

    _cb("annotating_video", 0)

    cap = cv2.VideoCapture(str(input_video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {input_video_path}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_frames == 0 or src_w == 0 or src_h == 0:
        cap.release()
        raise RuntimeError(f"Invalid video: frames={total_frames} w={src_w} h={src_h}")

    # Optimize annotation frame rate: if video is >= 20fps, annotate at 12 fps for 2-3x speedup
    target_fps = 12.0 if src_fps >= 20.0 else src_fps
    frame_step = max(int(round(src_fps / target_fps)), 1)
    effective_fps = src_fps / frame_step

    out_w, out_h = _scale_dims(src_w, src_h)
    scale_x = out_w / src_w
    scale_y = out_h / src_h
    do_resize = (out_w != src_w or out_h != src_h)

    Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)
    track_state = _build_track_state(segments, predictions)
    lookahead = 1.5  # wider window ensures bboxes still show when frame rate doesn't align with segment timestamps

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{out_w}x{out_h}",
        "-pix_fmt", "bgr24",
        "-r", f"{effective_fps:.2f}",
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "ultrafast",
        "-crf", "24",
        "-movflags", "+faststart",
        str(output_video_path),
    ]

    # CRITICAL: stdout and stderr MUST be DEVNULL to prevent OS pipe buffer deadlocks!
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    report_every = max(total_frames // 20, 1)
    frame_number = 0
    written_frames = 0

    try:
        while True:
            if frame_number % frame_step == 0:
                ret, frame = cap.read()
                if not ret:
                    break

                if do_resize:
                    frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LINEAR)

                timestamp = frame_number / src_fps
                active = _active_tracks_at(track_state, timestamp, lookahead)
                annotated = _annotate_frame(frame, timestamp, active, frame_number, total_frames, scale_x, scale_y)

                if proc.stdin:
                    proc.stdin.write(annotated.tobytes())
                written_frames += 1
            else:
                # Fast grab without full image decoding for skipped frames
                if not cap.grab():
                    break

            frame_number += 1
            if frame_number % report_every == 0:
                pct = int(100 * frame_number / max(total_frames, 1))
                _cb("annotating_video", min(pct, 95))

    finally:
        cap.release()
        if proc.stdin:
            try:
                proc.stdin.close()
            except Exception:
                pass
        proc.wait(timeout=30)

    _cb("annotating_video", 95)

    out_path = Path(output_video_path)
    if not out_path.exists() or out_path.stat().st_size < 500:
        raise RuntimeError(f"FFmpeg encoding produced an invalid or empty file: {output_video_path}")

    _cb("annotating_video", 100)
    return str(output_video_path)


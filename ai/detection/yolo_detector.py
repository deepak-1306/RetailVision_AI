"""
YOLOv11 person detector.

Wraps Ultralytics YOLO to detect customers (the COCO 'person' class) in each
sampled frame. Detections feed the ByteTrack multi-object tracker downstream.

The model weights are auto-downloaded by ultralytics on first use
(default: the lightweight `yolo11n.pt` checkpoint) unless a custom
YOLO_WEIGHTS_PATH is configured (e.g. a retail-fine-tuned checkpoint dropped
into ai/weights/).

Key design decisions
---------------------
* Adaptive imgsz: high-resolution CCTV / 4K input frames are sent to YOLO at
  a larger inference resolution (up to 1280) so that small/distant shoppers
  are correctly detected.  For standard-def or HD footage the cost is minimal.
* conf=0.10 default: retail CCTV footage often has partial occlusions and
  fisheye distortion — a low threshold is required to catch these cases; the
  ByteTrack tracker and behaviour heuristics downstream filter out noise.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

_COCO_PERSON_CLASS_ID = 0


@dataclass
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int = _COCO_PERSON_CLASS_ID
    class_name: str = "person"

    @property
    def xywh(self) -> tuple[float, float, float, float]:
        return self.x1, self.y1, self.x2 - self.x1, self.y2 - self.y1


def _adaptive_imgsz(frame_w: int, frame_h: int, device: str = "cpu") -> int:
    """
    Choose the YOLO inference resolution based on the source frame size and compute device.
    For CPU inference, snaps to 480 for real-time speed and low RAM footprint.
    For CUDA/GPU inference, scales up to 960/1280 for distant shopper detection.
    """
    if device == "cpu":
        return 480
    long_side = max(frame_w, frame_h)
    if long_side >= 3000:       # 4K / UHD
        return 1280
    elif long_side >= 1920:     # Full HD
        return 960
    elif long_side >= 1280:     # HD
        return 768
    else:                       # SD / 480p
        return 480


class YoloDetector:
    """Lazily loads the YOLOv11 model on first inference call."""

    def __init__(
        self,
        weights_path: str = "yolo11n.pt",
        confidence_threshold: float = 0.15,
        iou_threshold: float = 0.45,
        device: str = "cpu",
    ):
        self.weights_path = weights_path
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.device = device
        self._model = None

    def _load_model(self):
        if self._model is None:
            from ultralytics import YOLO  # imported lazily: heavy dependency
            self._model = YOLO(self.weights_path)
        return self._model

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run inference on a single BGR frame, returning 'person' detections."""
        model = self._load_model()

        h, w = frame.shape[:2]
        imgsz = _adaptive_imgsz(w, h, self.device)

        results = model.predict(
            source=frame,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            classes=[_COCO_PERSON_CLASS_ID],
            device=self.device,
            imgsz=imgsz,
            agnostic_nms=True,   # class-agnostic NMS helps with overlapping people
            verbose=False,
        )

        detections: List[Detection] = []
        if not results:
            return detections

        boxes = results[0].boxes
        if boxes is None:
            return detections

        frame_area = h * w
        for box in boxes:
            xyxy = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            bw   = xyxy[2] - xyxy[0]
            bh   = xyxy[3] - xyxy[1]
            # Reject detections smaller than 0.2% of frame area (noise)
            if bw * bh < frame_area * 0.002:
                continue
            # Reject non-person shapes (too wide or too short relative to height)
            ar = bw / max(bh, 1.0)
            if ar > 1.8:   # wider than tall: likely misfire
                continue
            detections.append(
                Detection(x1=xyxy[0], y1=xyxy[1], x2=xyxy[2], y2=xyxy[3], confidence=conf)
            )
        return detections

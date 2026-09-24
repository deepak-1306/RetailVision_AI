"""
Lightweight ByteTrack-style multi-object tracker.

Implements the core ByteTrack idea -- associate high- and low-confidence
detections to existing tracks via IoU matching, using a constant-velocity
motion prediction between frames -- in pure NumPy so the pipeline has no
hard dependency on external tracking frameworks. This keeps the module
self-contained and easy to reason about while preserving the two-stage
(high-conf / low-conf) association strategy that distinguishes ByteTrack
from vanilla SORT.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np

from ai.detection.yolo_detector import Detection


def _iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter_w, inter_h = max(0.0, inter_x2 - inter_x1), max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


def _spatial_similarity(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    """
    Combines Intersection-over-Union (IoU) with normalized centroid distance.
    If a customer walks fast or frames are sampled at intervals, IoU may drop
    near zero while centroid distance remains within human body dimensions.
    This metric avoids dropping track identity during normal movement.
    """
    iou = _iou(box_a, box_b)
    
    cx_a = (box_a[0] + box_a[2]) / 2.0
    cy_a = (box_a[1] + box_a[3]) / 2.0
    w_a = max(1.0, box_a[2] - box_a[0])
    h_a = max(1.0, box_a[3] - box_a[1])
    diag_a = (w_a**2 + h_a**2) ** 0.5

    cx_b = (box_b[0] + box_b[2]) / 2.0
    cy_b = (box_b[1] + box_b[3]) / 2.0
    w_b = max(1.0, box_b[2] - box_b[0])
    h_b = max(1.0, box_b[3] - box_b[1])
    diag_b = (w_b**2 + h_b**2) ** 0.5

    avg_diag = (diag_a + diag_b) / 2.0
    center_dist = ((cx_a - cx_b)**2 + (cy_a - cy_b)**2) ** 0.5
    
    # Normalized proximity score [0.0, 1.0]
    # Max allowed distance between frames is 2.5 times the person's diagonal
    max_dist = avg_diag * 3.5   # widened from 2.5x: handles fast movement at 5fps
    dist_score = max(0.0, 1.0 - (center_dist / max_dist))

    if iou > 0.0:
        return 0.6 * iou + 0.4 * dist_score
    else:
        # Pure proximity when bounding boxes do not overlap
        return 0.5 * dist_score


@dataclass
class Track:
    track_id: int
    bbox: tuple[float, float, float, float]  # x1,y1,x2,y2
    velocity: tuple[float, float] = (0.0, 0.0)
    hits: int = 1
    age: int = 0
    time_since_update: int = 0
    history: List[tuple[float, float, float, float]] = field(default_factory=list)

    def predict(self) -> tuple[float, float, float, float]:
        # Decay velocity if not updated recently to avoid drifting off-screen
        decay = 0.85 ** min(self.time_since_update, 10)
        vx, vy = self.velocity[0] * decay, self.velocity[1] * decay
        x1, y1, x2, y2 = self.bbox
        return x1 + vx, y1 + vy, x2 + vx, y2 + vy

    def update(self, bbox: tuple[float, float, float, float]) -> None:
        old_cx = (self.bbox[0] + self.bbox[2]) / 2
        old_cy = (self.bbox[1] + self.bbox[3]) / 2
        new_cx = (bbox[0] + bbox[2]) / 2
        new_cy = (bbox[1] + bbox[3]) / 2
        # Smooth velocity with exponential moving average
        new_vx = new_cx - old_cx
        new_vy = new_cy - old_cy
        self.velocity = (
            0.6 * self.velocity[0] + 0.4 * new_vx,
            0.6 * self.velocity[1] + 0.4 * new_vy,
        )
        # Smooth bbox coordinates with alpha-lerp to reduce single-frame jitter
        alpha = 0.75   # weight on new detection
        self.bbox = (
            alpha * bbox[0] + (1 - alpha) * self.bbox[0],
            alpha * bbox[1] + (1 - alpha) * self.bbox[1],
            alpha * bbox[2] + (1 - alpha) * self.bbox[2],
            alpha * bbox[3] + (1 - alpha) * self.bbox[3],
        )
        self.hits += 1
        self.time_since_update = 0
        self.history.append(self.bbox)


class ByteTracker:
    """
    Frame-by-frame multi-object tracker with spatial continuity and
    lost-track re-identification recovery.
    """

    def __init__(
        self,
        track_thresh: float = 0.35,
        match_thresh: float = 0.25,
        track_buffer: int = 90,
    ):
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.track_buffer = track_buffer
        self._tracks: List[Track] = []
        self._next_id = 1

    def update(self, detections: List[Detection]) -> List[Track]:
        high_conf = [d for d in detections if d.confidence >= self.track_thresh]
        low_conf = [d for d in detections if d.confidence < self.track_thresh]

        # Predict motion for existing active tracks
        predicted = {t.track_id: t.predict() for t in self._tracks}

        # Active tracks that were updated recently (<= 15 frames)
        recent_tracks = [t for t in self._tracks if t.time_since_update <= 15]
        # Older / lost tracks still in buffer
        lost_tracks = [t for t in self._tracks if t.time_since_update > 15]

        unmatched_tracks = list(recent_tracks)
        matched_track_ids: set[int] = set()
        unmatched_high_dets: list[Detection] = []

        # ---- Stage 1: match high-confidence detections to predicted tracks ----
        # Compute full similarity matrix to find optimal greedy matches
        matches = []
        for d_idx, det in enumerate(high_conf):
            det_box = (det.x1, det.y1, det.x2, det.y2)
            for track in unmatched_tracks:
                pred_box = predicted[track.track_id]
                sim = _spatial_similarity(pred_box, det_box)
                if sim >= self.match_thresh:
                    matches.append((sim, d_idx, track))

        # Sort matches descending by similarity
        matches.sort(key=lambda x: x[0], reverse=True)
        matched_dets = set()
        matched_tracks = set()

        for sim, d_idx, track in matches:
            if d_idx in matched_dets or track.track_id in matched_tracks:
                continue
            det = high_conf[d_idx]
            track.update((det.x1, det.y1, det.x2, det.y2))
            matched_track_ids.add(track.track_id)
            matched_dets.add(d_idx)
            matched_tracks.add(track.track_id)
            if track in unmatched_tracks:
                unmatched_tracks.remove(track)

        for d_idx, det in enumerate(high_conf):
            if d_idx not in matched_dets:
                unmatched_high_dets.append(det)

        # ---- Stage 2: match low-confidence detections to remaining tracks ----
        for det in low_conf:
            det_box = (det.x1, det.y1, det.x2, det.y2)
            best_track, best_sim = None, 0.0
            for track in unmatched_tracks:
                pred_box = predicted[track.track_id]
                sim = _spatial_similarity(pred_box, det_box)
                if sim > best_sim:
                    best_sim, best_track = sim, track
            if best_track is not None and best_sim >= self.match_thresh * 0.8:
                best_track.update(det_box)
                matched_track_ids.add(best_track.track_id)
                unmatched_tracks.remove(best_track)

        # ---- Stage 3: RE-IDENTIFICATION & RECOVERY of lost tracks ----
        # For any unmatched high-confidence detection, check if it matches a lost track
        # before creating a new track ID. This prevents Customer 1 turning into Customer 2/3/6.
        all_unmatched_candidates = list(unmatched_tracks) + list(lost_tracks)
        still_unmatched_dets = []

        for det in unmatched_high_dets:
            det_box = (det.x1, det.y1, det.x2, det.y2)
            best_track, best_sim = None, 0.0
            for track in all_unmatched_candidates:
                # Compare against last known bbox as well as predicted
                sim_last = _spatial_similarity(track.bbox, det_box)
                sim_pred = _spatial_similarity(predicted.get(track.track_id, track.bbox), det_box)
                sim = max(sim_last, sim_pred)
                if sim > best_sim:
                    best_sim, best_track = sim, track

            # Threshold for recovering a lost track: relaxed spatial similarity
            if best_track is not None and best_sim >= 0.18:
                best_track.update(det_box)
                matched_track_ids.add(best_track.track_id)
                if best_track in all_unmatched_candidates:
                    all_unmatched_candidates.remove(best_track)
            else:
                still_unmatched_dets.append(det)

        # ---- Stage 4: New track creation only for genuinely new entities ----
        for det in still_unmatched_dets:
            new_track = Track(track_id=self._next_id, bbox=(det.x1, det.y1, det.x2, det.y2))
            self._next_id += 1
            self._tracks.append(new_track)
            matched_track_ids.add(new_track.track_id)

        # ---- Age out stale tracks beyond track_buffer ----
        alive_tracks: List[Track] = []
        for track in self._tracks:
            if track.track_id not in matched_track_ids:
                track.time_since_update += 1
                track.age += 1
            if track.time_since_update <= self.track_buffer:
                alive_tracks.append(track)
        self._tracks = alive_tracks

        return [t for t in self._tracks if t.time_since_update == 0]

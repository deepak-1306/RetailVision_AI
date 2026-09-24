"""
End-to-end orchestration of the RetailVision AI computer-vision + ML
pipeline:

  Video Preprocessing -> YOLOv11 Detection -> ByteTrack Tracking ->
  Video Swin Behaviour Recognition -> Feature Engineering ->
  XGBoost Purchase Intent -> Recommendation Engine

This module has no FastAPI/Celery/DB imports -- it is pure pipeline logic
that accepts primitive config values and returns plain dataclasses, so it
can be unit tested and reused independently of the web framework. The
Celery task in backend/app/tasks/pipeline_task.py is a thin adapter that
calls `run_pipeline()` and persists the result to the database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ai.behaviour.behaviour_classifier import (
    BehaviourSegment,
    TrackObservation,
    VideoSwinBehaviourClassifier,
)
from ai.detection.yolo_detector import YoloDetector
from ai.ml.feature_engineering import CustomerFeatures, build_customer_features, group_segments_by_track
from ai.ml.purchase_intent_model import PurchaseIntentModel
from ai.preprocessing.video_preprocessor import VideoMetadata, VideoPreprocessor
from ai.recommendation.recommendation_engine import RecommendationItem, ZoneStats, generate_recommendations
from ai.tracking.byte_tracker import ByteTracker

ProgressCallback = Optional[Callable[[str, int], None]]


@dataclass
class PipelineConfig:
    yolo_weights_path: str = "yolo11n.pt"
    yolo_confidence_threshold: float = 0.15
    yolo_iou_threshold: float = 0.45
    bytetrack_track_thresh: float = 0.25
    bytetrack_match_thresh: float = 0.20
    bytetrack_track_buffer: int = 90
    video_swin_weights_path: str | None = None
    video_swin_clip_len: int = 32
    video_swin_frame_stride: int = 2
    frame_sample_fps: float = 5.0   # Raised from 3.0: more observations per track
    device: str = "cpu"
    xgboost_model_path: str = "./ai/weights/purchase_intent_xgb.json"


@dataclass
class PipelineResult:
    metadata: VideoMetadata
    behaviour_segments: list  # list[BehaviourSegment]
    raw_segments: list  # list[BehaviourSegment] (fine-grained frame observations for annotation)
    customer_features: dict[int, CustomerFeatures]
    predictions: dict[int, tuple[float, str]]  # track_id -> (score, label)
    zone_stats: list[ZoneStats]
    recommendations: list[RecommendationItem]


def _report(cb: ProgressCallback, status: str, progress: int) -> None:
    if cb:
        cb(status, progress)


def run_pipeline(video_path: str, config: PipelineConfig, progress_cb: ProgressCallback = None) -> PipelineResult:
    # ---- Stage 1: preprocessing ----
    _report(progress_cb, "preprocessing", 5)
    preprocessor = VideoPreprocessor(video_path, sample_fps=config.frame_sample_fps)
    metadata = preprocessor.get_metadata()

    # ---- Stage 2 & 3: detection + tracking (run together, frame by frame) ----
    _report(progress_cb, "detecting", 15)
    detector = YoloDetector(
        weights_path=config.yolo_weights_path,
        confidence_threshold=config.yolo_confidence_threshold,
        iou_threshold=config.yolo_iou_threshold,
        device=config.device,
    )
    tracker = ByteTracker(
        track_thresh=config.bytetrack_track_thresh,
        match_thresh=config.bytetrack_match_thresh,
        track_buffer=config.bytetrack_track_buffer,
    )
    classifier = VideoSwinBehaviourClassifier(
        weights_path=config.video_swin_weights_path,
        clip_len=config.video_swin_clip_len,
        frame_stride=config.video_swin_frame_stride,
        device=config.device,
    )

    _report(progress_cb, "tracking", 30)
    raw_segments = []
    total_expected_frames = max(int(metadata.duration_seconds * config.frame_sample_fps), 1)

    for i, sampled_frame in enumerate(preprocessor.iter_sampled_frames()):
        detections = detector.detect(sampled_frame.image)
        tracks = tracker.update(detections)

        for track in tracks:
            obs = TrackObservation(
                track_id=track.track_id,
                timestamp=sampled_frame.timestamp,
                bbox=track.bbox,
                frame_width=metadata.width,
                frame_height=metadata.height,
            )
            segment = classifier.observe(obs)
            if segment is not None:
                raw_segments.append(segment)

        if i % max(total_expected_frames // 10, 1) == 0:
            pct = 30 + int(40 * min(i / total_expected_frames, 1.0))
            _report(progress_cb, "classifying_behaviour", min(pct, 70))

    # ---- Track Stitching: Merge fragmented tracks of the same customer ----
    raw_segments = _stitch_tracks(raw_segments, max_time_gap=15.0)

    # ---- Temporal Episode Aggregation: Coalesce frame-level observations into discrete action episodes ----
    episodes = aggregate_episodes(raw_segments)

    # ---- Stage 4: feature engineering ----
    _report(progress_cb, "predicting_intent", 75)
    grouped = group_segments_by_track(episodes)
    customer_features = {
        track_id: build_customer_features(track_id, segs) for track_id, segs in grouped.items()
    }

    # ---- Stage 5: purchase intent prediction ----
    intent_model = PurchaseIntentModel(config.xgboost_model_path)
    predictions = {
        track_id: intent_model.predict(features) for track_id, features in customer_features.items()
    }

    # ---- Stage 6: recommendation engine (aggregate by shelf zone) ----
    _report(progress_cb, "generating_recommendations", 88)
    zone_stats = _aggregate_zone_stats(episodes, predictions)
    recommendations = generate_recommendations(zone_stats)

    _report(progress_cb, "completed", 100)

    return PipelineResult(
        metadata=metadata,
        behaviour_segments=episodes,
        raw_segments=raw_segments,
        customer_features=customer_features,
        predictions=predictions,
        zone_stats=zone_stats,
        recommendations=recommendations,
    )


def _aggregate_zone_stats(segments, predictions: dict[int, tuple[float, str]]) -> list[ZoneStats]:
    zones: dict[str, dict] = {}
    track_zone: dict[int, str] = {}

    for seg in segments:
        zone = seg.shelf_zone
        track_zone[seg.track_id] = zone
        z = zones.setdefault(zone, {
            "viewing_count": 0, "touching_count": 0, "picking_count": 0,
            "return_count": 0, "put_back_count": 0, "no_interest_count": 0,
            "turning_count": 0, "customers": set(),
        })
        z["customers"].add(seg.track_id)

        bt = seg.behaviour_type
        if bt == "viewing":
            z["viewing_count"] += 1
        elif bt == "touching":
            z["touching_count"] += 1
        elif bt == "picking":
            z["picking_count"] += 1
        elif bt == "picking_and_putting_back":
            z["picking_count"] += 1
            z["put_back_count"] += 1
        elif bt == "picking_and_returning":
            z["picking_count"] += 1
            z["return_count"] += 1
        elif bt == "no_interest_in_buying":
            z["no_interest_count"] += 1
        elif bt == "turning_towards_shelf":
            z["turning_count"] += 1

    # If no segments at all, return a synthetic "no activity" zone so the
    # recommendation engine can still emit the fallback recommendation.
    if not zones:
        return []

    result: list[ZoneStats] = []
    for zone_name, z in zones.items():
        customer_ids = z["customers"]
        scores = [predictions[tid][0] for tid in customer_ids if tid in predictions]
        avg_intent = sum(scores) / len(scores) if scores else 0.0
        result.append(ZoneStats(
            shelf_zone=zone_name,
            viewing_count=z["viewing_count"],
            touching_count=z["touching_count"],
            picking_count=z["picking_count"],
            return_count=z["return_count"],
            put_back_count=z["put_back_count"],
            no_interest_count=z["no_interest_count"],
            turning_count=z["turning_count"],
            avg_purchase_intent=round(avg_intent, 1),
            customer_count=len(customer_ids),
        ))
    return result


def _stitch_tracks(segments: list, max_time_gap: float = 15.0) -> list:
    """
    Post-process segments to stitch fragmented track IDs representing the same customer.
    If track B starts after track A ends (or during tracker coasting handoffs) and their boundary
    bboxes are spatially close, remap all occurrences of track B's ID to track A's ID.
    """
    if not segments:
        return segments

    from dataclasses import replace

    # Group segments by track
    track_segs: dict[int, list] = {}
    for s in segments:
        track_segs.setdefault(s.track_id, []).append(s)

    # Calculate time and bbox ranges
    track_ranges: dict[int, tuple[float, float, tuple, tuple]] = {}
    for tid, segs in track_segs.items():
        segs.sort(key=lambda s: s.start_time)
        first_seg, last_seg = segs[0], segs[-1]
        track_ranges[tid] = (first_seg.start_time, last_seg.end_time, first_seg.bbox, last_seg.bbox)

    remap: dict[int, int] = {tid: tid for tid in track_segs}

    def get_root(tid: int) -> int:
        while remap[tid] != tid:
            remap[tid] = remap[remap[tid]]
            tid = remap[tid]
        return tid

    sorted_tids = sorted(track_ranges.keys(), key=lambda tid: track_ranges[tid][0])

    for i in range(len(sorted_tids)):
        tid_a = sorted_tids[i]
        root_a = get_root(tid_a)
        start_a, end_a, _, last_box_a = track_ranges[tid_a]
        cx_a = (last_box_a[0] + last_box_a[2]) / 2.0
        cy_a = (last_box_a[1] + last_box_a[3]) / 2.0
        w_a = max(1.0, last_box_a[2] - last_box_a[0])
        h_a = max(1.0, last_box_a[3] - last_box_a[1])
        diag_a = (w_a**2 + h_a**2) ** 0.5

        for j in range(i + 1, len(sorted_tids)):
            tid_b = sorted_tids[j]
            root_b = get_root(tid_b)
            if root_a == root_b:
                continue

            start_b, end_b, first_box_b, _ = track_ranges[tid_b]
            gap = start_b - end_a

            if gap > max_time_gap:
                break
            # Allow tracker coasting overlap during handoffs (up to 3.0s overlap)
            if gap < -3.0:
                continue

            cx_b = (first_box_b[0] + first_box_b[2]) / 2.0
            cy_b = (first_box_b[1] + first_box_b[3]) / 2.0
            w_b = max(1.0, first_box_b[2] - first_box_b[0])
            h_b = max(1.0, first_box_b[3] - first_box_b[1])
            diag_b = (w_b**2 + h_b**2) ** 0.5
            avg_diag = (diag_a + diag_b) / 2.0

            dist = ((cx_a - cx_b)**2 + (cy_a - cy_b)**2) ** 0.5
            max_allowed = max(avg_diag * 5.0, 500.0)  # wider for shelf re-ID

            if dist <= max_allowed:
                remap[root_b] = root_a
                break

    stitched = []
    for seg in segments:
        root_id = get_root(seg.track_id)
        if root_id != seg.track_id:
            stitched.append(replace(seg, track_id=root_id))
        else:
            stitched.append(seg)

    return stitched


def aggregate_episodes(
    segments: list[BehaviourSegment],
) -> list[BehaviourSegment]:
    """
    Coalesce consecutive frame-level observations into discrete, cohesive
    behaviour episodes with authentic start and end timestamps.
    """
    if not segments:
        return []

    grouped: dict[int, list[BehaviourSegment]] = {}
    for s in segments:
        grouped.setdefault(s.track_id, []).append(s)

    episodes: list[BehaviourSegment] = []

    for tid, segs in grouped.items():
        if not segs:
            continue
        segs.sort(key=lambda s: s.start_time)

        # Majority smoothing: look ±2 neighbours (window of 5) to suppress flicker
        smoothed_types = [s.behaviour_type for s in segs]
        n = len(segs)
        if n >= 5:
            for k in range(2, n - 2):
                window = [smoothed_types[k - 2], smoothed_types[k - 1],
                          smoothed_types[k],
                          smoothed_types[k + 1], smoothed_types[k + 2]]
                majority = max(set(window), key=window.count)
                if window.count(majority) >= 4:   # 4/5 agreement
                    smoothed_types[k] = majority
        elif n >= 3:
            for k in range(1, n - 1):
                prev_t = smoothed_types[k - 1]
                curr_t = smoothed_types[k]
                next_t = smoothed_types[k + 1]
                if prev_t == next_t and curr_t != prev_t:
                    smoothed_types[k] = prev_t

        cur_type = smoothed_types[0]
        cur_start = segs[0].start_time
        cur_end = segs[0].end_time
        cur_confs = [segs[0].confidence]
        cur_zone = segs[0].shelf_zone
        cur_bbox = segs[0].bbox

        track_episodes: list[BehaviourSegment] = []

        for idx in range(1, n):
            b_type = smoothed_types[idx]
            s = segs[idx]

            # If same behaviour and continuous in time (gap <= 0.5s)
            # Tightened from 0.8s to avoid merging two distinct short actions
            if b_type == cur_type and (s.start_time - cur_end) <= 0.5:
                cur_end = max(cur_end, s.end_time)
                cur_confs.append(s.confidence)
                if s.shelf_zone != "Unzoned":
                    cur_zone = s.shelf_zone
                cur_bbox = s.bbox
            else:
                track_episodes.append(BehaviourSegment(
                    track_id=tid,
                    behaviour_type=cur_type,
                    start_time=round(cur_start, 2),
                    end_time=round(max(cur_end, cur_start + 0.2), 2),
                    confidence=round(sum(cur_confs) / max(len(cur_confs), 1), 2),
                    shelf_zone=cur_zone,
                    bbox=cur_bbox,
                ))
                cur_type = b_type
                cur_start = s.start_time
                cur_end = s.end_time
                cur_confs = [s.confidence]
                cur_zone = s.shelf_zone
                cur_bbox = s.bbox

        # Flush final episode
        track_episodes.append(BehaviourSegment(
            track_id=tid,
            behaviour_type=cur_type,
            start_time=round(cur_start, 2),
            end_time=round(max(cur_end, cur_start + 0.2), 2),
            confidence=round(sum(cur_confs) / max(len(cur_confs), 1), 2),
            shelf_zone=cur_zone,
            bbox=cur_bbox,
        ))

        episodes.extend(track_episodes)

    # Sort all episodes chronologically
    episodes.sort(key=lambda s: (s.start_time, s.track_id))
    return episodes

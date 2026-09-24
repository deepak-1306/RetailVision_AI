"""
Feature engineering: aggregate a track's raw behaviour segments into the
fixed feature vector consumed by the XGBoost purchase-intent model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ai.behaviour.behaviour_classifier import BehaviourSegment

FEATURE_NAMES = [
    "dwell_time_seconds",
    "touch_count",
    "pick_count",
    "return_count",
    "viewing_duration_seconds",
    "num_behaviour_transitions",
    "avg_segment_confidence",
]


@dataclass
class CustomerFeatures:
    track_id: int
    dwell_time_seconds: float
    touch_count: int
    pick_count: int
    return_count: int
    viewing_duration_seconds: float
    num_behaviour_transitions: int
    avg_segment_confidence: float

    def as_vector(self) -> list[float]:
        return [
            self.dwell_time_seconds,
            float(self.touch_count),
            float(self.pick_count),
            float(self.return_count),
            self.viewing_duration_seconds,
            float(self.num_behaviour_transitions),
            self.avg_segment_confidence,
        ]


def build_customer_features(track_id: int, segments: Iterable[BehaviourSegment]) -> CustomerFeatures:
    segments = sorted(segments, key=lambda s: s.start_time)
    if not segments:
        return CustomerFeatures(track_id, 0.0, 0, 0, 0, 0.0, 0, 0.0)

    dwell_time = sum(s.end_time - s.start_time for s in segments)
    touch_count = sum(
        1 for s in segments
        if s.behaviour_type in ("touching", "picking", "picking_and_putting_back", "picking_and_returning")
    )
    pick_count = sum(1 for s in segments if s.behaviour_type == "picking")
    return_count = sum(
        1 for s in segments
        if s.behaviour_type in ("picking_and_returning", "picking_and_putting_back")
    )
    viewing_duration = sum(s.end_time - s.start_time for s in segments if s.behaviour_type == "viewing")

    transitions = sum(
        1 for i in range(1, len(segments)) if segments[i].behaviour_type != segments[i - 1].behaviour_type
    )
    avg_confidence = sum(s.confidence for s in segments) / len(segments)

    return CustomerFeatures(
        track_id=track_id,
        dwell_time_seconds=round(dwell_time, 2),
        touch_count=touch_count,
        pick_count=pick_count,
        return_count=return_count,
        viewing_duration_seconds=round(viewing_duration, 2),
        num_behaviour_transitions=transitions,
        avg_segment_confidence=round(avg_confidence, 3),
    )


def group_segments_by_track(segments: Iterable[BehaviourSegment]) -> dict[int, list[BehaviourSegment]]:
    grouped: dict[int, list[BehaviourSegment]] = {}
    for seg in segments:
        grouped.setdefault(seg.track_id, []).append(seg)
    return grouped

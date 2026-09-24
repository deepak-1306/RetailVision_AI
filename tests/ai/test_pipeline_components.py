"""
Unit tests for the pure-Python AI pipeline components that don't require a
GPU, a real video file, or network access (detection/classification model
weights are exercised separately -- see ai/behaviour and ai/detection for
how they're lazily loaded).
"""
from ai.behaviour.behaviour_classifier import HeuristicBehaviourClassifier, TrackObservation
from ai.ml.feature_engineering import build_customer_features, group_segments_by_track
from ai.recommendation.recommendation_engine import ZoneStats, generate_recommendations
from ai.tracking.byte_tracker import ByteTracker
from ai.detection.yolo_detector import Detection


def test_bytetrack_assigns_stable_ids_across_frames():
    tracker = ByteTracker()
    frame1 = [Detection(x1=100, y1=100, x2=160, y2=220, confidence=0.9)]
    frame2 = [Detection(x1=105, y1=102, x2=165, y2=222, confidence=0.88)]

    tracks1 = tracker.update(frame1)
    tracks2 = tracker.update(frame2)

    assert len(tracks1) == 1
    assert len(tracks2) == 1
    assert tracks1[0].track_id == tracks2[0].track_id


def test_heuristic_classifier_produces_valid_behaviour_labels():
    clf = HeuristicBehaviourClassifier()
    segments = []
    for i in range(8):
        obs = TrackObservation(
            track_id=1, timestamp=i * 0.5,
            bbox=(100, 100, 150 + i * 3, 200 + i * 3),
            frame_width=1280, frame_height=720,
        )
        seg = clf.observe(obs)
        if seg:
            segments.append(seg)

    assert len(segments) > 0
    valid_labels = {
        "viewing", "touching", "picking", "picking_and_returning",
        "picking_and_putting_back", "no_interest_in_buying", "turning_towards_shelf",
    }
    assert all(s.behaviour_type in valid_labels for s in segments)


def test_recommendation_engine_flags_high_view_low_pick():
    stats = [ZoneStats(
        shelf_zone="Zone A", viewing_count=20, touching_count=2, picking_count=1,
        return_count=0, no_interest_count=0, avg_purchase_intent=30.0, customer_count=20,
    )]
    recs = generate_recommendations(stats)
    assert any(r.trigger_pattern == "high_view_low_pick" for r in recs)


def test_feature_engineering_groups_by_track():
    from ai.behaviour.behaviour_classifier import BehaviourSegment

    segments = [
        BehaviourSegment(track_id=1, behaviour_type="picking", start_time=0, end_time=1, confidence=0.8, shelf_zone="A", bbox=(0, 0, 1, 1)),
        BehaviourSegment(track_id=1, behaviour_type="viewing", start_time=1, end_time=3, confidence=0.7, shelf_zone="A", bbox=(0, 0, 1, 1)),
        BehaviourSegment(track_id=2, behaviour_type="no_interest_in_buying", start_time=0, end_time=1, confidence=0.6, shelf_zone="B", bbox=(0, 0, 1, 1)),
    ]
    grouped = group_segments_by_track(segments)
    assert set(grouped.keys()) == {1, 2}
    features_1 = build_customer_features(1, grouped[1])
    assert features_1.pick_count == 1
    assert features_1.viewing_duration_seconds == 2


def test_aggregate_episodes_produces_realistic_non_overlapping_intervals():
    from ai.behaviour.behaviour_classifier import BehaviourSegment
    from ai.pipeline.run_pipeline import aggregate_episodes

    # Simulate 20 raw frame classifications (sampled every 0.2s)
    raw = []
    for i in range(10):  # 0.0s to 2.0s: viewing
        raw.append(BehaviourSegment(1, "viewing", i * 0.2, (i + 1) * 0.2, 0.85, "Shelf A", (100, 100, 200, 200)))
    for i in range(10, 20):  # 2.0s to 4.0s: picking_and_putting_back
        raw.append(BehaviourSegment(1, "picking_and_putting_back", i * 0.2, (i + 1) * 0.2, 0.80, "Shelf A", (100, 100, 200, 200)))

    episodes = aggregate_episodes(raw)
    assert len(episodes) == 2
    # Episode 1
    assert episodes[0].behaviour_type == "viewing"
    assert episodes[0].start_time == 0.0
    assert episodes[0].end_time == 2.0
    # Episode 2
    assert episodes[1].behaviour_type == "picking_and_putting_back"
    assert episodes[1].start_time == 2.0
    assert episodes[1].end_time == 4.0
    # No repetitive 0.0s intervals!
    assert episodes[1].start_time != 0.0


def test_stitch_tracks_merges_fragmented_customer_ids():
    from ai.behaviour.behaviour_classifier import BehaviourSegment
    from ai.pipeline.run_pipeline import _stitch_tracks

    # Single customer initially tracked as track 1 (0-3s), lost briefly, reacquired as track 2 (4-7s)
    raw = [
        BehaviourSegment(1, "viewing", 0.0, 3.0, 0.8, "Shelf A", (100, 100, 200, 300)),
        BehaviourSegment(2, "touching", 4.0, 7.0, 0.8, "Shelf A", (110, 105, 210, 305)),
    ]
    stitched = _stitch_tracks(raw, max_time_gap=10.0)
    # Both segments should be remapped to track 1
    assert all(s.track_id == 1 for s in stitched)


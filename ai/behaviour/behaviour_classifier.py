"""
Behaviour recognition stage  -  Enhanced v2.

VideoSwinBehaviourClassifier loads a fine-tuned neural checkpoint and
classifies fixed-length clips around each tracked customer into one of the
seven target behaviours. Falls back to HeuristicBehaviourClassifier when
weights are absent.

v2 improvements
----------------
* Feature vector 16 -> 24 dimensions (trajectory curvature, path-length ratio,
  bbox-height trend, jerk, hold-frames ratio, area entropy).
* Temporal momentum: per-track rolling buffer of last 5 neural predictions
  -> confidence-weighted majority vote removes single-frame flicker.
* Adaptive ensemble fusion: soft blend instead of hard 0.55 threshold.
* Stricter physical sanity guards (combined speed + dwell + area checks).
* Heuristic: height-normalised speed, lean-forward (h_trend) touching signal,
  wider short window (12) and long window (40).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from ai.behaviour.zones import DEFAULT_SHELF_ZONES, resolve_zone
from ai.tracking.byte_tracker import Track  # noqa: F401 (kept for import compat)

BEHAVIOUR_LABELS = [
    "viewing",
    "touching",
    "picking",
    "picking_and_returning",
    "picking_and_putting_back",
    "no_interest_in_buying",
    "turning_towards_shelf",
]

# Must match train_action_classifier.py INPUT_DIM after retraining
ENHANCED_INPUT_DIM = 24


@dataclass
class TrackObservation:
    """One sampled-frame observation of a track."""
    track_id: int
    timestamp: float
    bbox: tuple
    frame_width: int
    frame_height: int


@dataclass
class BehaviourSegment:
    track_id: int
    behaviour_type: str
    start_time: float
    end_time: float
    confidence: float
    shelf_zone: str
    bbox: tuple


# ---------------------------------------------------------------------------
class HeuristicBehaviourClassifier:
    """
    Rule-based classifier with improved windows and height-normalised speed.

    SHORT_WINDOW = 12 frames  (~2.4s @ 5 fps)
    LONG_WINDOW  = 40 frames  (~8 s   @ 5 fps)
    """

    SHORT_WINDOW = 12
    LONG_WINDOW  = 40

    def __init__(self):
        self._short: Dict[int, List[TrackObservation]] = {}
        self._long:  Dict[int, List[TrackObservation]] = {}

    # helpers -----------------------------------------------------------------
    @staticmethod
    def _ca(bbox):
        x1, y1, x2, y2 = bbox
        return (x1 + x2) / 2, (y1 + y2) / 2, max(0.0, (x2 - x1)) * max(0.0, (y2 - y1))

    @staticmethod
    def _sma(series, w=5):
        out = []
        for i in range(len(series)):
            s = max(0, i - w + 1)
            out.append(sum(series[s:i + 1]) / (i - s + 1))
        return out

    # observe -----------------------------------------------------------------
    def observe(self, obs: TrackObservation) -> Optional[BehaviourSegment]:
        sh = self._short.setdefault(obs.track_id, [])
        sh.append(obs)
        if len(sh) > self.SHORT_WINDOW:
            sh.pop(0)
        lo = self._long.setdefault(obs.track_id, [])
        lo.append(obs)
        if len(lo) > self.LONG_WINDOW:
            lo.pop(0)
        if len(sh) < 5:
            return None
        return self._classify(sh, lo)

    # classify ----------------------------------------------------------------
    def _classify(self, short, long_hist):
        first_s, last = short[0], short[-1]
        fw = max(last.frame_width, 1)
        fh = max(last.frame_height, 1)

        cx_last, cy_last, _ = self._ca(last.bbox)
        shelf_zone = resolve_zone(cx_last / fw, cy_last / fh, DEFAULT_SHELF_ZONES)

        cx0, cy0, _ = self._ca(first_s.bbox)
        cx1, cy1, _ = self._ca(last.bbox)
        dwell_s     = max(0.1, last.timestamp - first_s.timestamp)
        disp_s      = math.hypot(cx1 - cx0, cy1 - cy0)
        norm_disp_s = (disp_s / fh) * 100.0
        speed_s     = norm_disp_s / dwell_s

        # Height-normalised speed handles cameras at different distances
        person_h   = max(last.bbox[3] - last.bbox[1], fh * 0.05)
        speed_norm = (disp_s / person_h) / max(dwell_s, 0.1)

        ar_s     = [(o.bbox[2] - o.bbox[0]) / max(o.bbox[3] - o.bbox[1], 1.0) for o in short]
        h_s      = [(o.bbox[3] - o.bbox[1]) for o in short]
        ar_min, ar_max = min(ar_s), max(ar_s)
        h_min,  h_max  = min(h_s),  max(h_s)
        ar_rel_var     = (ar_max - ar_min) / max(ar_min, 0.05)
        h_rel_var      = (h_max  - h_min)  / max(h_min, 1.0)
        turn_indicator = ar_rel_var / max(h_rel_var, 0.03)
        is_turning     = (ar_rel_var >= 0.28 and turn_indicator >= 1.8) or (ar_rel_var >= 0.35)

        # Lean-forward: height growing means person moved toward shelf
        h_trend = (h_s[-1] - h_s[0]) / max(h_s[0], 1.0)

        compound_label, compound_conf = None, 0.0
        if len(long_hist) >= 8:
            compound_label, compound_conf = self._check_compound_pick(long_hist, fh)

        if compound_label is not None:
            behaviour, confidence = compound_label, compound_conf
        elif speed_norm >= 4.5 or speed_s >= 6.5:
            if is_turning:
                behaviour, confidence = "turning_towards_shelf", 0.85
            else:
                behaviour, confidence = "no_interest_in_buying", 0.88
        else:
            raw_a  = [self._ca(o.bbox)[2] for o in short]
            sm_a   = self._sma(raw_a, w=3)
            max_a  = max(sm_a); min_a = min(sm_a); area_last = sm_a[-1]
            peak_g = (max_a - min_a) / max(min_a, 1.0)
            post_s = (max_a - area_last) / max(max_a, 1.0)
            leaning = h_trend > 0.05

            if dwell_s >= 0.8 and speed_s < 4.5 and peak_g >= 0.22 and post_s < 0.10:
                behaviour, confidence = "picking", 0.88
            elif dwell_s >= 0.4 and speed_s < 5.0 and (peak_g >= 0.15 or leaning) and post_s >= 0.12:
                behaviour, confidence = "touching", 0.83
            elif is_turning:
                behaviour, confidence = "turning_towards_shelf", 0.86
            elif speed_s < 5.0 and dwell_s >= 0.4:
                behaviour, confidence = "viewing", 0.90
            else:
                behaviour, confidence = "no_interest_in_buying", 0.75

        step_dt   = max(0.05, min(last.timestamp - short[-2].timestamp if len(short) >= 2 else 0.2, 1.0))
        seg_start = max(0.0, last.timestamp - step_dt)
        return BehaviourSegment(last.track_id, behaviour,
                                round(seg_start, 2), round(last.timestamp, 2),
                                confidence, shelf_zone, last.bbox)

    def _check_compound_pick(self, history, fh):
        raw = [self._ca(o.bbox)[2] for o in history]
        sm  = self._sma(raw, w=4)
        n   = len(sm)
        if n < 8:
            return None, 0.0
        max_a = max(sm); min_a = min(sm); peak_idx = sm.index(max_a); area_now = sm[-1]
        peak_g    = (max_a - min_a) / max(min_a, 1.0)
        post_s    = (max_a - area_now) / max(max_a, 1.0)
        rel_peak  = peak_idx / max(n - 1, 1)
        if peak_g < 0.20 or post_s < 0.16 or not (0.15 <= rel_peak <= 0.85):
            return None, 0.0
        hold_thresh  = min_a + 0.70 * (max_a - min_a)
        hold_secs    = sum(1 for a in sm if a >= hold_thresh) * 0.25
        dwell_total  = history[-1].timestamp - history[0].timestamp
        if hold_secs >= 2.0 or dwell_total >= 3.5:
            return "picking_and_returning", 0.88
        return "picking_and_putting_back", 0.85


# ---------------------------------------------------------------------------
class VideoSwinBehaviourClassifier:
    """
    Neural + heuristic ensemble classifier.

    v2 enhancements:
      - 24-dim feature vector
      - Temporal momentum (last-5 predictions, confidence-weighted majority vote)
      - Soft confidence blending (alpha-interpolation based on margin)
      - Three-tier physical sanity layer
    """

    _MOMENTUM_LEN     = 5
    _NEURAL_THRESHOLD = 0.52

    def __init__(self, weights_path=None, clip_len=32, frame_stride=2, device="cpu"):
        self.weights_path = weights_path
        self.clip_len     = clip_len
        self.frame_stride = frame_stride
        self.device       = device
        self._model       = None
        self._input_dim   = ENHANCED_INPUT_DIM
        self._fallback    = HeuristicBehaviourClassifier()
        self._has_weights = bool(weights_path and Path(weights_path).exists())
        self._momentum: Dict[int, deque] = {}

    # model loading -----------------------------------------------------------
    def _load_model(self):
        if self._model is None and self.weights_path and Path(self.weights_path).exists():
            import torch
            from ai.behaviour.train_action_classifier import (
                RetailActionNeuralNet, INPUT_DIM, NUM_CLASSES
            )
            for dim in (ENHANCED_INPUT_DIM, INPUT_DIM):
                try:
                    m     = RetailActionNeuralNet(input_dim=dim, num_classes=NUM_CLASSES)
                    state = torch.load(self.weights_path, map_location=self.device, weights_only=True)
                    m.load_state_dict(state)
                    m.eval()
                    self._model     = m.to(self.device)
                    self._input_dim = dim
                    break
                except Exception:
                    continue
            if self._model is None:
                print("[behaviour_classifier] All weight-load attempts failed.")
        return self._model

    # feature extraction ------------------------------------------------------
    def _extract_features(self, history):
        """
        Extract 24-dim kinematic + geometric feature vector.

        Indices 0-15 (original):
          avg_speed, max_speed, speed_var, dwell_time, norm_disp,
          peak_growth, post_shrink, max_area_pos, aspect_ratio,
          ar_rel_var, shelf_prox, reversals, h_rel_var, turn_indicator,
          stillness, interaction

        Indices 16-23 (new):
          path_length_ratio, trajectory_curve, jerk, h_trend,
          dwell_density, area_entropy, hold_frames_ratio, bbox_aspect_trend
        """
        fb    = self._fallback
        first, last = history[0], history[-1]
        raw_areas  = [fb._ca(o.bbox)[2] for o in history]
        sm_areas   = fb._sma(raw_areas)

        cx0, cy0, _ = fb._ca(first.bbox)
        cx1, cy1, _ = fb._ca(last.bbox)
        fw = max(last.frame_width, 1); fh = max(last.frame_height, 1)

        shelf_zone  = resolve_zone(cx1 / fw, cy1 / fh, DEFAULT_SHELF_ZONES)
        shelf_prox  = 1.0 if shelf_zone != "Unzoned" else 0.0

        disp        = math.hypot(cx1 - cx0, cy1 - cy0)
        norm_disp   = (disp / fh) * 100.0
        dwell_time  = max(0.1, last.timestamp - first.timestamp)

        area_now    = sm_areas[-1]; max_area = max(sm_areas); min_area = min(sm_areas)
        peak_idx    = sm_areas.index(max_area)
        peak_growth = (max_area - min_area) / max(min_area, 1.0)
        post_shrink = (max_area - area_now) / max(max_area, 1.0)
        max_area_pos = peak_idx / max(len(sm_areas) - 1, 1)

        speeds, headings, centers = [], [], []
        for i in range(1, len(history)):
            c0 = fb._ca(history[i - 1].bbox)
            c1 = fb._ca(history[i].bbox)
            dt = max(0.01, history[i].timestamp - history[i - 1].timestamp)
            dx, dy = c1[0] - c0[0], c1[1] - c0[1]
            speeds.append((math.hypot(dx, dy) / fh * 100.0) / dt)
            headings.append((dx, dy))
            centers.append((c1[0], c1[1]))

        avg_speed = sum(speeds) / max(len(speeds), 1) if speeds else norm_disp / dwell_time
        max_speed = max(speeds) if speeds else avg_speed
        speed_var = float(np.var(speeds)) if len(speeds) > 1 else 1.0
        stillness = sum(1 for s in speeds if s < 5.0) / max(len(speeds), 1) if speeds else 0.5

        reversals = 0
        for i in range(1, len(headings)):
            h0, h1 = headings[i - 1], headings[i]
            dot = h0[0] * h1[0] + h0[1] * h1[1]
            m0, m1 = math.hypot(*h0), math.hypot(*h1)
            if m0 > 2.0 and m1 > 2.0 and (dot / (m0 * m1)) < -0.3:
                reversals += 1

        ar_s  = [(o.bbox[2] - o.bbox[0]) / max(o.bbox[3] - o.bbox[1], 1.0) for o in history]
        h_s   = [(o.bbox[3] - o.bbox[1]) for o in history]
        ar_min, ar_max = min(ar_s), max(ar_s)
        h_min,  h_max  = min(h_s),  max(h_s)
        ar_rel_var   = (ar_max - ar_min) / max(ar_min, 0.05)
        h_rel_var    = (h_max  - h_min)  / max(h_min,  1.0)
        turn_indicator = ar_rel_var / max(h_rel_var, 0.03)

        w = last.bbox[2] - last.bbox[0]; h = last.bbox[3] - last.bbox[1]
        aspect_ratio = max(0.1, w / max(h, 1.0))
        interaction  = min(1.0, peak_growth * 1.5 + (1.0 - stillness) * 0.3)

        # ---- new features 16-23 ----
        if len(centers) >= 2:
            path_len = sum(
                math.hypot(centers[i][0] - centers[i-1][0], centers[i][1] - centers[i-1][1])
                for i in range(1, len(centers))
            )
            path_length_ratio = min(path_len / max(disp, 1.0), 10.0)
        else:
            path_length_ratio = 1.0

        angles = []
        for i in range(1, len(headings)):
            h0, h1 = headings[i - 1], headings[i]
            m0, m1 = math.hypot(*h0), math.hypot(*h1)
            if m0 > 1.0 and m1 > 1.0:
                cos_a = max(-1.0, min(1.0, (h0[0] * h1[0] + h0[1] * h1[1]) / (m0 * m1)))
                angles.append(math.acos(cos_a))
        trajectory_curve = float(np.mean(angles)) if angles else 0.0

        jerk = float(np.var([abs(speeds[i] - speeds[i-1]) for i in range(1, len(speeds))])) \
               if len(speeds) >= 2 else 0.0
        h_trend_val = (h_s[-1] - h_s[0]) / max(h_s[0], 1.0) if len(h_s) >= 2 else 0.0

        area_diffs = [abs(raw_areas[i] - raw_areas[i-1]) for i in range(1, len(raw_areas))]
        if area_diffs:
            tot   = sum(area_diffs) + 1e-9
            probs = [d / tot for d in area_diffs]
            area_entropy = -sum(p * math.log(p + 1e-12) for p in probs if p > 0)
        else:
            area_entropy = 0.0

        hold_thresh      = min_area + 0.70 * max(max_area - min_area, 1.0)
        hold_frames_ratio = sum(1 for a in sm_areas if a >= hold_thresh) / max(len(sm_areas), 1)
        bbox_aspect_trend = (ar_s[-1] - ar_s[0]) / max(ar_s[0], 0.05) if len(ar_s) >= 2 else 0.0

        return [
            float(avg_speed), float(max_speed), float(speed_var), float(dwell_time),
            float(norm_disp), float(peak_growth), float(post_shrink), float(max_area_pos),
            float(aspect_ratio), float(ar_rel_var), float(shelf_prox), float(reversals),
            float(h_rel_var), float(turn_indicator), float(stillness), float(interaction),
            float(path_length_ratio), float(trajectory_curve), float(jerk), float(h_trend_val),
            float(stillness),          # dwell_density (same semantic as stillness)
            float(area_entropy), float(hold_frames_ratio), float(bbox_aspect_trend),
        ]

    # temporal smoothing -------------------------------------------------------
    def _momentum_vote(self, track_id, raw_idx, probs):
        buf = self._momentum.setdefault(track_id, deque(maxlen=self._MOMENTUM_LEN))
        buf.append((raw_idx, probs))
        weights = np.zeros(len(BEHAVIOUR_LABELS))
        for _, pv in buf:
            weights += pv
        best = int(np.argmax(weights))
        conf = float(weights[best] / max(weights.sum(), 1e-9))
        return BEHAVIOUR_LABELS[best], conf

    # main entry point ---------------------------------------------------------
    def observe(self, obs: TrackObservation) -> Optional[BehaviourSegment]:
        fallback_seg = self._fallback.observe(obs)
        if fallback_seg is None:
            return None
        model = self._load_model()
        if model is None:
            return fallback_seg

        try:
            import torch
            history = self._fallback._long.get(obs.track_id, [])
            if len(history) < 5:
                return fallback_seg

            feat = self._extract_features(history)
            dim  = self._input_dim
            if len(feat) < dim:   feat = feat + [0.0] * (dim - len(feat))
            elif len(feat) > dim: feat = feat[:dim]

            x = torch.tensor([feat], dtype=torch.float32, device=self.device)
            with torch.no_grad():
                probs = torch.softmax(model(x), dim=1).cpu().numpy()[0]

            raw_idx          = int(np.argmax(probs))
            nn_label, nn_conf = self._momentum_vote(obs.track_id, raw_idx, probs)

            # physical sanity guards
            avg_speed = feat[0]; dwell = feat[3]; peak_gr = feat[5]; post_shr = feat[6]
            if avg_speed >= 12.0 and dwell < 1.0 and nn_label in (
                    "picking", "picking_and_putting_back", "picking_and_returning", "touching"):
                nn_label = "no_interest_in_buying"; nn_conf = max(nn_conf, 0.85)
            if peak_gr < 0.08 and nn_label == "picking":
                nn_label = "viewing"; nn_conf = max(nn_conf, 0.75)
            if post_shr >= 0.30 and avg_speed < 4.0 and nn_label == "picking":
                nn_label = "picking_and_putting_back"; nn_conf = max(nn_conf, 0.80)

            # adaptive ensemble
            h_conf = fallback_seg.confidence
            if nn_conf >= self._NEURAL_THRESHOLD:
                alpha       = min(1.0, (nn_conf - self._NEURAL_THRESHOLD) / 0.3)
                final_label = nn_label
                final_conf  = alpha * nn_conf + (1.0 - alpha) * h_conf
            else:
                final_label = fallback_seg.behaviour_type
                final_conf  = max(nn_conf, h_conf)

            return BehaviourSegment(obs.track_id, final_label,
                                    fallback_seg.start_time, fallback_seg.end_time,
                                    round(final_conf, 2),
                                    fallback_seg.shelf_zone, fallback_seg.bbox)
        except Exception:
            return fallback_seg

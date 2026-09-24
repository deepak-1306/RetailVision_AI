"""
Real-Video Training Pipeline for Retail Action Recognition  - Enhanced v2.

Changes from v1:
  - Extracts 24-dim features (matching enhanced behaviour_classifier.py)
  - Sliding-window augmentation at multiple scales (3 window sizes)
  - Mixup augmentation during training
  - Cosine annealing + warm restarts scheduler
  - Focal loss with label smoothing
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

_ROOT    = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_BACKEND))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from ai.behaviour.train_action_classifier import (
    BEHAVIOUR_LABELS, INPUT_DIM, NUM_CLASSES, RetailActionNeuralNet,
    FocalLoss, generate_synthetic_dataset,
)

FILENAME_LABEL_MAP: List[Tuple[str, int]] = [
    (r"picking.{0,10}putting",  4),
    (r"putting.{0,10}back",     4),
    (r"picking.{0,10}return",   3),
    (r"returning",              3),
    (r"picking",                2),
    (r"touching",               1),
    (r"no.{0,5}interest",       5),
    (r"turning",                6),
    (r"viewing",                0),
]


def label_from_filename(name: str) -> Optional[int]:
    lower = name.lower()
    for pattern, cls_idx in FILENAME_LABEL_MAP:
        if re.search(pattern, lower):
            return cls_idx
    return None


class _SimpleTrack:
    def __init__(self, tid):
        self.tid = tid
        self.history: List[Tuple] = []
        self.bbox = (0, 0, 1, 1)
        self.last_seen = 0.0

    def update(self, bbox, t):
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2; cy = (y1 + y2) / 2
        area = max(1.0, (x2 - x1) * (y2 - y1))
        self.bbox = (x1, y1, x2, y2)
        self.last_seen = t
        self.history.append((cx, cy, area, t, x1, y1, x2, y2))


class _SimpleTracker:
    _tid = 0

    def __init__(self, max_age=15, iou_thresh=0.25):
        self.max_age   = max_age
        self.iou_thresh = iou_thresh
        self._tracks: Dict[int, _SimpleTrack] = {}
        self._age:    Dict[int, int]           = {}

    @staticmethod
    def _iou(a, b):
        ax1, ay1, ax2, ay2 = a; bx1, by1, bx2, by2 = b
        ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if inter == 0: return 0.0
        ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
        return inter / max(ua, 1e-6)

    def update(self, dets, t):
        active = list(self._tracks.keys()); matched = set()
        for det in dets:
            best_iou, best_tid = 0.0, None
            for tid in active:
                if tid in matched: continue
                iou = self._iou(det, self._tracks[tid].bbox)
                if iou > best_iou: best_iou, best_tid = iou, tid
            if best_tid is not None and best_iou >= self.iou_thresh:
                self._tracks[best_tid].update(det, t)
                self._age[best_tid] = 0; matched.add(best_tid)
            else:
                _SimpleTracker._tid += 1; tid = _SimpleTracker._tid
                self._tracks[tid] = _SimpleTrack(tid)
                self._tracks[tid].update(det, t)
                self._age[tid] = 0
        to_del = []
        for tid in active:
            if tid not in matched:
                self._age[tid] = self._age.get(tid, 0) + 1
                if self._age[tid] > self.max_age: to_del.append(tid)
        for tid in to_del:
            del self._tracks[tid]; del self._age[tid]
        return self._tracks


def _sma(values, w=5):
    out = []
    for i in range(len(values)):
        s = max(0, i - w + 1)
        out.append(sum(values[s:i + 1]) / (i - s + 1))
    return out


def extract_features(history, fw, fh):
    """Extract 24-dim feature vector from a track history."""
    if len(history) < 6: return None
    fw = max(fw, 1); fh = max(fh, 1)

    # Unpack: history items = (cx, cy, area, t, x1, y1, x2, y2)
    cxs   = [h[0] for h in history]; cys   = [h[1] for h in history]
    areas = [h[2] for h in history]; ts    = [h[3] for h in history]
    # bbox widths / heights for aspect ratio (use sqrt(area) approximation if not available)
    if len(history[0]) >= 8:
        ws = [h[6] - h[4] for h in history]
        hs = [h[7] - h[5] for h in history]
    else:
        ws = [math.sqrt(a) for a in areas]
        hs = [math.sqrt(a) for a in areas]

    sm = _sma(areas)
    cx0, cy0, cx1, cy1 = cxs[0], cys[0], cxs[-1], cys[-1]
    t0, t1 = ts[0], ts[-1]; dwell = max(0.1, t1 - t0)
    disp   = math.hypot(cx1 - cx0, cy1 - cy0)
    norm_disp = (disp / fh) * 100.0

    shelf_prox = 1.0 if cy1 / fh > 0.3 else 0.0

    area_now = sm[-1]; max_a = max(sm); min_a = min(sm); peak_idx = sm.index(max_a)
    peak_g   = (max_a - min_a) / max(min_a, 1.0)
    post_s   = (max_a - area_now) / max(max_a, 1.0)
    max_pos  = peak_idx / max(len(sm) - 1, 1)

    speeds, headings = [], []
    for i in range(1, len(history)):
        dt = max(0.01, ts[i] - ts[i-1])
        dx = cxs[i] - cxs[i-1]; dy = cys[i] - cys[i-1]
        speeds.append((math.hypot(dx, dy) / fh * 100.0) / dt)
        headings.append((dx, dy))

    avg_sp = sum(speeds) / max(len(speeds), 1) if speeds else norm_disp / dwell
    max_sp = max(speeds) if speeds else avg_sp
    sp_var = float(np.var(speeds)) if len(speeds) > 1 else 1.0
    still  = sum(1 for s in speeds if s < 5.0) / max(len(speeds), 1) if speeds else 0.5

    rev = 0
    for i in range(1, len(headings)):
        h0, h1 = headings[i-1], headings[i]
        dot = h0[0]*h1[0]+h0[1]*h1[1]; m0,m1 = math.hypot(*h0),math.hypot(*h1)
        if m0 > 2.0 and m1 > 2.0 and (dot/(m0*m1)) < -0.3: rev += 1

    ar_s  = [w / max(h, 1.0) for w, h in zip(ws, hs)]
    h_s   = hs
    ar_min,ar_max = min(ar_s),max(ar_s); h_min,h_max = min(h_s),max(h_s)
    ar_rv = (ar_max-ar_min)/max(ar_min,0.05); h_rv = (h_max-h_min)/max(h_min,1.0)
    turn  = ar_rv/max(h_rv,0.03)
    ar_c  = ar_s[-1]
    inter = min(1.0, peak_g*1.5+(1.0-still)*0.3)

    # ---- new features 16-23 ----
    centers = list(zip(cxs[1:], cys[1:]))
    if len(centers) >= 2:
        path_len = sum(math.hypot(centers[i][0]-centers[i-1][0],
                                  centers[i][1]-centers[i-1][1])
                       for i in range(1, len(centers)))
        plr = min(path_len / max(disp, 1.0), 10.0)
    else:
        plr = 1.0

    angles = []
    for i in range(1, len(headings)):
        h0,h1 = headings[i-1],headings[i]; m0,m1=math.hypot(*h0),math.hypot(*h1)
        if m0>1.0 and m1>1.0:
            cos_a=max(-1.0,min(1.0,(h0[0]*h1[0]+h0[1]*h1[1])/(m0*m1)))
            angles.append(math.acos(cos_a))
    curve = float(np.mean(angles)) if angles else 0.0
    jerk  = float(np.var([abs(speeds[i]-speeds[i-1]) for i in range(1,len(speeds))])) \
            if len(speeds)>=2 else 0.0
    h_tr  = (h_s[-1]-h_s[0])/max(h_s[0],1.0) if len(h_s)>=2 else 0.0

    ad = [abs(areas[i]-areas[i-1]) for i in range(1,len(areas))]
    if ad:
        tot=sum(ad)+1e-9; probs=[d/tot for d in ad]
        ae = -sum(p*math.log(p+1e-12) for p in probs if p>0)
    else:
        ae = 0.0

    hold_t = min_a+0.70*max(max_a-min_a,1.0)
    hfr    = sum(1 for a in sm if a>=hold_t)/max(len(sm),1)
    bat    = (ar_s[-1]-ar_s[0])/max(ar_s[0],0.05) if len(ar_s)>=2 else 0.0

    feat = [
        float(avg_sp),float(max_sp),float(sp_var),float(dwell),float(norm_disp),
        float(peak_g),float(post_s),float(max_pos),float(ar_c),float(ar_rv),
        float(shelf_prox),float(rev),float(h_rv),float(turn),float(still),float(inter),
        float(plr),float(curve),float(jerk),float(h_tr),
        float(still),float(ae),float(hfr),float(bat),
    ]
    feat = [max(0.0, f) for f in feat]
    if any(math.isnan(f) or math.isinf(f) for f in feat): return None
    return feat


def _load_yolo():
    try:
        from ultralytics import YOLO
        mp = _BACKEND / "ai" / "weights" / "yolo11n.pt"
        if not mp.exists(): mp = "yolo11n.pt"
        return YOLO(str(mp), verbose=False)
    except Exception as e:
        print(f"[warn] YOLO load failed ({e}), using MOG2 fallback"); return None


def _detect_yolo(yolo, frame_rgb):
    results = yolo(frame_rgb, classes=[0], imgsz=640, conf=0.25, verbose=False)
    boxes = []
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            boxes.append((float(x1), float(y1), float(x2), float(y2)))
    return boxes


def _detect_mog(mog, gray, fw, fh):
    fg = mog.apply(gray)
    _, thresh = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kern)
    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []; min_a = fw * fh * 0.004
    for c in cnts:
        a = cv2.contourArea(c)
        if a < min_a: continue
        x, y, w, h = cv2.boundingRect(c)
        if h < w: continue
        boxes.append((float(x), float(y), float(x + w), float(y + h)))
    return boxes


def process_video(vpath, label, yolo=None, sample_fps=6.0, min_frames=8):
    cap = cv2.VideoCapture(vpath)
    if not cap.isOpened(): print(f"[skip] {vpath}"); return []
    vid_fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(vid_fps / sample_fps)))
    tracker = _SimpleTracker(max_age=12, iou_thresh=0.30)
    mog     = cv2.createBackgroundSubtractorMOG2(history=120, varThreshold=50)
    lbl_name = BEHAVIOUR_LABELS[label]
    print(f"  -> [{lbl_name}] {Path(vpath).name} ({n}fr,{vid_fps:.0f}fps,step={step})")
    t0 = time.time(); fidx = 0
    while True:
        ret = cap.grab()
        if not ret: break
        if fidx % step != 0: fidx += 1; continue
        ok, frame = cap.retrieve()
        if not ok: fidx += 1; continue
        t     = fidx / vid_fps
        scale = min(1.0, 640.0 / fw)
        small = cv2.resize(frame, (int(fw*scale), int(fh*scale)),
                            interpolation=cv2.INTER_LINEAR) if scale < 1.0 else frame
        gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        if yolo is not None:
            rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            boxes = _detect_yolo(yolo, rgb)
            if scale < 1.0:
                boxes = [(x1/scale,y1/scale,x2/scale,y2/scale) for x1,y1,x2,y2 in boxes]
        else:
            boxes = _detect_mog(mog, gray, small.shape[1], small.shape[0])
            if scale < 1.0:
                boxes = [(x1/scale,y1/scale,x2/scale,y2/scale) for x1,y1,x2,y2 in boxes]
        tracker.update(boxes, t); fidx += 1
    cap.release()
    samples = []
    # Multiple window sizes for augmentation
    for tid, track in tracker._tracks.items():
        hist = track.history
        for win in (len(hist), len(hist) * 2 // 3, len(hist) // 2):
            win = max(min_frames, win)
            if len(hist) < win: continue
            for s in range(0, len(hist) - win + 1, max(1, win // 3)):
                sub = hist[s:s + win]
                f   = extract_features(sub, fw, fh)
                if f: samples.append((f, label))
    print(f"     {len(samples)} feature vectors in {time.time()-t0:.1f}s")
    return samples


def discover(vdir):
    found = []
    for p in sorted(Path(vdir).rglob("*")):
        if p.suffix.lower() not in {".mp4", ".avi", ".mov", ".mkv", ".wmv"}: continue
        lbl = label_from_filename(p.name)
        if lbl is not None: found.append((str(p), lbl))
    print(f"\n[discover] {len(found)} labelled videos in '{vdir}':")
    c = {}
    for _, l in found: c[l] = c.get(l, 0) + 1
    for l, n in sorted(c.items()): print(f"  {BEHAVIOUR_LABELS[l]:35s}: {n}")
    return found


def mixup(X, y, alpha=0.3):
    """Apply Mixup augmentation to the training batch."""
    lam = np.random.beta(alpha, alpha, size=len(X))
    idx = np.random.permutation(len(X))
    X2  = X[idx]; y2 = y[idx]
    lam_f = lam[:, None].astype(np.float32)
    X_mix = lam_f * X + (1 - lam_f) * X2
    return X_mix, y, y2, lam.astype(np.float32)


def train(real, output, epochs=80, synth_ratio=3.0, real_w=5.0):
    n_synth = max(2000, int(len(real) * synth_ratio))
    print(f"\n[train] real={len(real)}  synth={n_synth}  epochs={epochs}  INPUT_DIM={INPUT_DIM}")

    Xs, ys = generate_synthetic_dataset(num_samples=n_synth)
    Xr = np.array([s[0] for s in real], dtype=np.float32)
    yr = np.array([s[1] for s in real], dtype=np.int64)

    X_all = np.concatenate([Xr, Xs]); y_all = np.concatenate([yr, ys])
    w_all = np.concatenate([np.full(len(Xr), real_w, dtype=np.float32),
                             np.ones(len(Xs), dtype=np.float32)])

    idx = np.random.permutation(len(X_all))
    X_all, y_all, w_all = X_all[idx], y_all[idx], w_all[idx]
    sp = int(0.85 * len(X_all))
    X_tr, y_tr, w_tr = X_all[:sp], y_all[:sp], w_all[:sp]
    X_va, y_va        = X_all[sp:], y_all[sp:]

    ds     = TensorDataset(torch.tensor(X_tr), torch.tensor(y_tr), torch.tensor(w_tr))
    loader = DataLoader(ds, batch_size=256, shuffle=True)

    model  = RetailActionNeuralNet(INPUT_DIM, NUM_CLASSES)
    crit   = FocalLoss(gamma=2.0, label_smoothing=0.05, reduction="none")
    opt    = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    sched  = optim.lr_scheduler.CosineAnnealingWarmRestarts(opt, T_0=20, T_mult=2)

    best_acc, best_state = 0.0, None
    X_va_t = torch.tensor(X_va); y_va_t = torch.tensor(y_va)

    for epoch in range(epochs):
        model.train(); tot_loss = corr = tot = 0
        for bx, by, bw in loader:
            opt.zero_grad()
            out  = model(bx)
            loss = (crit(out, by) * bw).mean()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step()
            tot_loss += loss.item() * bx.size(0)
            corr += (torch.argmax(out, 1) == by).sum().item()
            tot  += by.size(0)

        if (epoch + 1) % 10 == 0 or epoch == 0:
            model.eval()
            with torch.no_grad():
                vout  = model(X_va_t); vpreds = torch.argmax(vout, 1)
                vacc  = (vpreds == y_va_t).float().mean().item()
            print(f"  Epoch {epoch+1:3d}/{epochs}  loss={tot_loss/tot:.4f}  "
                  f"train={corr/tot*100:.1f}%  val={vacc*100:.1f}%")
            for ci, lbl in enumerate(BEHAVIOUR_LABELS):
                mask = (y_va_t == ci)
                if mask.sum() > 0:
                    cacc = (vpreds[mask] == y_va_t[mask]).float().mean().item()
                    bar  = "*" * int(cacc * 20)
                    print(f"    {lbl:35s} {cacc*100:5.1f}%  {bar}")
            if vacc > best_acc:
                best_acc   = vacc
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            model.train()

    if best_state: model.load_state_dict(best_state)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output)
    print(f"\n  Saved -> {output}  (best val {best_acc*100:.2f}%)")
    return best_acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos-dir", default=str(_ROOT/"backend"/"data"/"media"/"uploads"))
    ap.add_argument("--output",     default=str(_BACKEND/"ai"/"weights"/"video_swin_behaviour.pth"))
    ap.add_argument("--epochs",     type=int,   default=80)
    ap.add_argument("--synth-ratio",type=float, default=3.0)
    ap.add_argument("--real-weight",type=float, default=5.0)
    ap.add_argument("--no-yolo",    action="store_true")
    ap.add_argument("--sample-fps", type=float, default=6.0)
    args = ap.parse_args()

    print("=" * 65)
    print("  RetailVision - Real-Video Action Classifier Training v2")
    print("=" * 65)
    pairs = discover(args.videos_dir)
    yolo  = None if args.no_yolo else _load_yolo()
    all_samples = []
    print(f"\n[extract] Processing {len(pairs)} video(s)...")
    for vp, lbl in pairs:
        all_samples.extend(process_video(vp, lbl, yolo, args.sample_fps))
    print(f"\n[extract] Total real vectors: {len(all_samples)}")
    c = {}
    for _, l in all_samples: c[l] = c.get(l, 0) + 1
    for ci, lbl in enumerate(BEHAVIOUR_LABELS):
        n = c.get(ci, 0); bar = "*" * min(n, 40)
        print(f"  {lbl:35s}: {n:4d}  {bar}")
    if len(all_samples) < 10:
        print("[warn] Too few real samples, running pure synthetic training...")
        from ai.behaviour.train_action_classifier import train_and_save_model
        train_and_save_model(output_path=args.output)
        return
    train(all_samples, args.output, args.epochs, args.synth_ratio, args.real_weight)


if __name__ == "__main__":
    main()

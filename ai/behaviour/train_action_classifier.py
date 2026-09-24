"""
PyTorch Neural Network for Retail Customer Behaviour Recognition  - Enhanced v2.

Changes from v1:
  - INPUT_DIM 16 -> 24 (matches enhanced feature extractor in behaviour_classifier.py)
  - Deeper network: 24->128->256->128->64->7 with SELU + AlphaDropout
  - Focal loss to hard-mine confused class pairs (picking vs viewing etc.)
  - Label smoothing to prevent overconfidence
  - Improved synthetic data generation for new 8 extra features
"""
from __future__ import annotations

import os
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

BEHAVIOUR_LABELS = [
    "viewing",
    "touching",
    "picking",
    "picking_and_returning",
    "picking_and_putting_back",
    "no_interest_in_buying",
    "turning_towards_shelf",
]

NUM_CLASSES = len(BEHAVIOUR_LABELS)
INPUT_DIM   = 24   # ENHANCED - was 16


class FocalLoss(nn.Module):
    """Focal loss for class-imbalanced action recognition."""
    def __init__(self, gamma=2.0, label_smoothing=0.05, reduction="mean"):
        super().__init__()
        self.gamma = gamma
        self.ls    = label_smoothing
        self.reduction = reduction

    def forward(self, logits, targets):
        n_cls = logits.size(1)
        # Label smoothing
        with torch.no_grad():
            smooth = torch.full_like(logits, self.ls / (n_cls - 1))
            smooth.scatter_(1, targets.unsqueeze(1), 1.0 - self.ls)
        log_p  = torch.log_softmax(logits, dim=1)
        p      = torch.exp(log_p)
        focal  = (1 - p) ** self.gamma
        loss   = -(focal * smooth * log_p).sum(dim=1)
        if self.reduction == "mean":   return loss.mean()
        if self.reduction == "none":   return loss
        return loss.sum()


class RetailActionNeuralNet(nn.Module):
    """
    4-layer SELU MLP with residual skip connection.

    Architecture: 24 -> 128 -> 256 -> 128 -> 64 -> 7
    Uses SELU + AlphaDropout (self-normalising variant) for stable CPU training.
    """

    def __init__(self, input_dim: int = INPUT_DIM, num_classes: int = NUM_CLASSES):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.SELU(inplace=True),
            nn.AlphaDropout(0.10),
        )
        self.block1 = nn.Sequential(
            nn.Linear(128, 256),
            nn.SELU(inplace=True),
            nn.AlphaDropout(0.15),
            nn.Linear(256, 128),
            nn.SELU(inplace=True),
        )
        self.block2 = nn.Sequential(
            nn.Linear(128, 64),
            nn.SELU(inplace=True),
        )
        self.head = nn.Linear(64, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        s  = self.stem(x)
        s  = s + self.block1(s)   # residual
        s  = self.block2(s)
        return self.head(s)


def _noise(rng, lo, hi):
    return rng.uniform(lo, hi)


def generate_synthetic_dataset(num_samples: int = 200_000):
    """
    Physics-grounded synthetic dataset for 24-dimensional features.

    Original 16 features + 8 new ones:
      [16] path_length_ratio  - 1.0 = straight; >2 = circuitous (browsing)
      [17] trajectory_curve   - mean angular change (rad)
      [18] jerk               - variance of speed differences
      [19] h_trend            - positive = leaning toward shelf
      [20] dwell_density      - fraction of frames with low speed (=stillness)
      [21] area_entropy       - random jitter = low; structured = high
      [22] hold_frames_ratio  - fraction above 70% peak
      [23] bbox_aspect_trend  - positive = turning body
    """
    rng = np.random.default_rng(42)
    X, y = [], []
    spc  = num_samples // NUM_CLASSES

    for cls in range(NUM_CLASSES):
        for _ in range(spc):
            f  = np.zeros(INPUT_DIM, dtype=np.float32)
            ni = lambda lo, hi: _noise(rng, lo, hi)

            if cls == 0:   # viewing
                speed=ni(0.1,4.5); dwell=ni(2.0,35.0); disp=ni(0.5,12.0)
                peak_g=ni(0.0,0.09); shrink=ni(0.0,0.05); max_pos=ni(0.5,1.0)
                ar=ni(0.44,0.65); ar_var=ni(0.01,0.11); h_var=ni(0.01,0.03)
                still=ni(0.88,1.0); inter=ni(0.0,0.05); rev=0; shelf=1.0
                plr=ni(1.0,2.5); curve=ni(0.0,0.3); jerk=ni(0.0,0.5)
                h_tr=ni(-0.02,0.04); ae=ni(0.5,1.5); hfr=ni(0.0,0.2); bat=ni(-0.05,0.05)

            elif cls == 1:  # touching
                speed=ni(1.0,5.5); dwell=ni(1.0,7.0); disp=ni(3.0,18.0)
                peak_g=ni(0.10,0.28); shrink=ni(0.02,0.12); max_pos=ni(0.5,0.9)
                ar=ni(0.47,0.68); ar_var=ni(0.04,0.16); h_var=ni(0.01,0.05)
                still=ni(0.58,0.85); inter=ni(0.38,0.65); rev=int(rng.integers(0,2)); shelf=1.0
                plr=ni(1.2,3.0); curve=ni(0.2,0.8); jerk=ni(1.0,5.0)
                h_tr=ni(0.03,0.12); ae=ni(1.0,2.5); hfr=ni(0.1,0.4); bat=ni(-0.1,0.1)

            elif cls == 2:  # picking (sustained hold)
                speed=ni(1.0,7.0); dwell=ni(2.0,15.0); disp=ni(3.0,22.0)
                peak_g=ni(0.20,0.65); shrink=ni(0.0,0.08); max_pos=ni(0.65,1.0)
                ar=ni(0.40,0.85); ar_var=ni(0.05,0.65); h_var=ni(0.01,0.10)
                still=ni(0.40,0.85); inter=ni(0.65,0.98); rev=int(rng.integers(0,3)); shelf=1.0
                plr=ni(1.1,2.0); curve=ni(0.1,0.5); jerk=ni(0.5,3.0)
                h_tr=ni(0.05,0.20); ae=ni(1.5,3.0); hfr=ni(0.4,0.9); bat=ni(-0.1,0.2)

            elif cls == 3:  # picking_and_returning
                speed=ni(1.5,9.0); dwell=ni(3.5,22.0); disp=ni(5.0,35.0)
                peak_g=ni(0.20,0.65); shrink=ni(0.20,0.65); max_pos=ni(0.20,0.70)
                ar=ni(0.40,0.85); ar_var=ni(0.06,0.70); h_var=ni(0.01,0.12)
                still=ni(0.35,0.80); inter=ni(0.65,1.0); rev=int(rng.integers(2,9)); shelf=1.0
                plr=ni(1.5,4.0); curve=ni(0.4,1.2); jerk=ni(2.0,8.0)
                h_tr=ni(0.04,0.15); ae=ni(2.0,4.0); hfr=ni(0.25,0.65); bat=ni(-0.2,0.2)

            elif cls == 4:  # picking_and_putting_back
                speed=ni(1.5,9.0); dwell=ni(1.0,4.5); disp=ni(4.0,25.0)
                peak_g=ni(0.18,0.60); shrink=ni(0.20,0.65); max_pos=ni(0.20,0.70)
                ar=ni(0.40,0.80); ar_var=ni(0.05,0.65); h_var=ni(0.01,0.10)
                still=ni(0.40,0.80); inter=ni(0.60,0.98); rev=int(rng.integers(0,3)); shelf=1.0
                plr=ni(1.2,3.0); curve=ni(0.3,1.0); jerk=ni(1.5,6.0)
                h_tr=ni(0.03,0.12); ae=ni(1.8,3.5); hfr=ni(0.15,0.50); bat=ni(-0.15,0.15)

            elif cls == 5:  # no_interest_in_buying
                speed=ni(20.0,90.0); dwell=ni(0.1,1.8); disp=ni(35.0,220.0)
                peak_g=ni(0.0,0.06); shrink=ni(0.0,0.06); max_pos=ni(0.0,1.0)
                ar=ni(0.35,0.60); ar_var=ni(0.01,0.18); h_var=ni(0.01,0.06)
                still=ni(0.0,0.12); inter=ni(0.0,0.06); rev=0; shelf=float(rng.choice([0.0,0.0,0.0,0.3]))
                plr=ni(1.0,1.5); curve=ni(0.0,0.2); jerk=ni(5.0,20.0)
                h_tr=ni(-0.05,0.05); ae=ni(0.1,0.8); hfr=ni(0.0,0.1); bat=ni(-0.05,0.05)

            else:           # turning_towards_shelf
                speed=ni(3.0,20.0); dwell=ni(0.5,3.5); disp=ni(5.0,45.0)
                peak_g=ni(0.05,0.25); shrink=ni(0.0,0.10); max_pos=ni(0.1,0.9)
                ar=ni(0.44,0.88); ar_var=ni(0.25,0.95); h_var=ni(0.01,0.04)
                still=ni(0.15,0.55); inter=ni(0.02,0.25); rev=int(rng.integers(0,2)); shelf=1.0
                plr=ni(1.0,2.0); curve=ni(0.5,1.5); jerk=ni(1.0,4.0)
                h_tr=ni(-0.05,0.05); ae=ni(0.5,1.5); hfr=ni(0.0,0.2); bat=ni(0.15,0.60)

            turn_indicator = ar_var / max(h_var, 0.03)
            f[0]=speed; f[1]=speed*ni(1.1,1.6); f[2]=ni(0.3,8.0); f[3]=dwell; f[4]=disp
            f[5]=peak_g; f[6]=shrink; f[7]=max_pos; f[8]=ar; f[9]=ar_var
            f[10]=shelf; f[11]=float(rev); f[12]=h_var; f[13]=turn_indicator
            f[14]=still; f[15]=inter
            f[16]=plr; f[17]=curve; f[18]=jerk; f[19]=h_tr
            f[20]=still; f[21]=ae; f[22]=hfr; f[23]=bat
            f += rng.normal(0, 0.02, size=INPUT_DIM).astype(np.float32)
            f  = np.clip(f, 0.0, None)
            X.append(f); y.append(cls)

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int64)


def train_and_save_model(output_path: str = "./ai/weights/video_swin_behaviour.pth"):
    print("--> Generating 24-dim synthetic dataset (200K samples)...")
    X, y = generate_synthetic_dataset(num_samples=200_000)

    idx = np.arange(len(X)); np.random.shuffle(idx)
    X, y = X[idx], y[idx]

    split  = int(0.85 * len(X))
    X_tr   = torch.tensor(X[:split]); y_tr = torch.tensor(y[:split])
    X_va   = torch.tensor(X[split:]); y_va = torch.tensor(y[split:])

    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(X_tr, y_tr), batch_size=512, shuffle=True)

    model     = RetailActionNeuralNet(INPUT_DIM, NUM_CLASSES)
    criterion = FocalLoss(gamma=2.0, label_smoothing=0.05)
    optimizer = optim.AdamW(model.parameters(), lr=0.002, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=40)

    best_val, best_state = 0.0, None
    model.train()
    for epoch in range(40):
        tot_loss = correct = total = 0
        for bx, by in loader:
            optimizer.zero_grad()
            out  = model(bx)
            loss = criterion(out, by)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            tot_loss += loss.item() * bx.size(0)
            correct  += (torch.argmax(out, 1) == by).sum().item()
            total    += by.size(0)
        scheduler.step()

        if (epoch + 1) % 5 == 0 or epoch == 0:
            model.eval()
            with torch.no_grad():
                vout  = model(X_va)
                vpred = torch.argmax(vout, 1)
                vacc  = (vpred == y_va).float().mean().item()
            if vacc > best_val:
                best_val   = vacc
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            print(f"  Epoch {epoch+1}/40 loss={tot_loss/total:.4f} "
                  f"train={correct/total*100:.1f}% val={vacc*100:.1f}%")
            model.train()

    if best_state:
        model.load_state_dict(best_state)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_path)
    print(f"--> Saved -> {output_path}  (best val {best_val*100:.2f}%)")


if __name__ == "__main__":
    train_and_save_model()

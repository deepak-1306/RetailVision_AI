"""
Bootstraps the XGBoost purchase-intent model on synthetically generated,
domain-informed training data, and saves it to XGBOOST_MODEL_PATH.

Rationale
---------
A production system would train this on historical (behaviour-features ->
actual purchase) labels joined from POS data. That labeled dataset doesn't
exist for a fresh deployment, so this script generates a synthetic dataset
whose label function encodes retail domain knowledge (more picks, more
dwell time, more touches, and fewer returns => higher purchase probability)
with realistic noise. This lets the XGBoost model + the rest of the pipeline
run end-to-end immediately; swap in `X, y` built from real POS-linked data
to retrain for production use, with zero changes to `purchase_intent_model.py`.

Run directly:  python -m ai.ml.train_purchase_intent
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xgboost as xgb

from ai.ml.feature_engineering import FEATURE_NAMES


def _generate_synthetic_dataset(n_samples: int = 10000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)

    dwell_time = rng.gamma(shape=2.0, scale=8.0, size=n_samples)          # seconds (mean ~16s)
    touch_count = rng.poisson(lam=1.5, size=n_samples).astype(float)
    pick_count = rng.poisson(lam=0.8, size=n_samples).astype(float)
    return_count = rng.poisson(lam=0.5, size=n_samples).astype(float)
    viewing_duration = rng.gamma(shape=1.5, scale=5.0, size=n_samples)
    num_transitions = rng.poisson(lam=2.5, size=n_samples).astype(float)
    avg_confidence = rng.uniform(0.65, 0.98, size=n_samples)

    X = np.column_stack([
        dwell_time, touch_count, pick_count, return_count,
        viewing_duration, num_transitions, avg_confidence,
    ])

    # Domain-calibrated latent "purchase propensity" score
    z = (
        0.05 * dwell_time
        + 0.65 * touch_count
        + 2.40 * pick_count
        - 1.60 * return_count
        + 0.08 * viewing_duration
        - 0.05 * num_transitions
        + 0.50 * avg_confidence
        - 2.40
    )
    prob = 1 / (1 + np.exp(-z))
    noise = rng.normal(0, 0.03, size=n_samples)
    prob = np.clip(prob + noise, 0.02, 0.98)
    y = (rng.uniform(0, 1, size=n_samples) < prob).astype(int)

    return X, y


def train_and_save(output_path: str) -> None:
    X, y = _generate_synthetic_dataset()

    dtrain = xgb.DMatrix(X, label=y, feature_names=FEATURE_NAMES)
    params = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "max_depth": 4,
        "eta": 0.1,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "seed": 42,
    }
    booster = xgb.train(params, dtrain, num_boost_round=150)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(output_path)
    print(f"Purchase intent model trained on {len(y)} synthetic samples and saved to {output_path}")


if __name__ == "__main__":
    import sys
    out_path = sys.argv[1] if len(sys.argv) > 1 else "./ai/weights/purchase_intent_xgb.json"
    train_and_save(out_path)

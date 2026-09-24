"""
XGBoost purchase-intent predictor.

Given a customer's aggregated behaviour features (dwell time, touch/pick/
return counts, viewing duration, ...), predicts a 0-100 purchase intent
score. Lazily loads the trained booster from XGBOOST_MODEL_PATH; if no
trained model file is found yet, it bootstraps one on the fly via
`train_purchase_intent.train_and_save` (synthetic domain-informed data --
see that module's docstring) so the API never fails on a fresh checkout.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xgboost as xgb

from ai.ml.feature_engineering import CustomerFeatures, FEATURE_NAMES


def _label_from_score(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


class PurchaseIntentModel:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._booster: xgb.Booster | None = None

    def _ensure_model(self) -> xgb.Booster:
        if self._booster is not None:
            return self._booster

        if not Path(self.model_path).exists():
            from ai.ml.train_purchase_intent import train_and_save
            train_and_save(self.model_path)

        booster = xgb.Booster()
        booster.load_model(self.model_path)
        self._booster = booster
        return booster

    def predict(self, features: CustomerFeatures) -> tuple[float, str]:
        booster = self._ensure_model()
        vector = np.array([features.as_vector()], dtype=float)
        dmatrix = xgb.DMatrix(vector, feature_names=FEATURE_NAMES)
        prob = float(booster.predict(dmatrix)[0])
        score = round(prob * 100, 1)
        return score, _label_from_score(score)

from __future__ import annotations

from pydantic import BaseModel


class PurchaseIntentOut(BaseModel):
    id: str
    job_id: str
    track_id: int
    dwell_time_seconds: float
    touch_count: int
    pick_count: int
    return_count: int
    viewing_duration_seconds: float
    purchase_intent_score: float
    intent_label: str

    class Config:
        from_attributes = True


class PurchaseIntentSummary(BaseModel):
    average_score: float
    high_intent_customers: int
    medium_intent_customers: int
    low_intent_customers: int
    total_customers: int

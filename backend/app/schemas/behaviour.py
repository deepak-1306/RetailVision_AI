from __future__ import annotations

from pydantic import BaseModel

from app.models.behaviour import BehaviourType


class BehaviourEventOut(BaseModel):
    id: str
    job_id: str
    track_id: int
    behaviour_type: BehaviourType
    start_time_seconds: float
    end_time_seconds: float
    confidence: float
    shelf_zone: str | None

    class Config:
        from_attributes = True


class BehaviourDistributionItem(BaseModel):
    behaviour_type: str
    count: int
    percentage: float


class CustomerJourneyItem(BaseModel):
    track_id: int
    events: list[BehaviourEventOut]
    total_dwell_seconds: float

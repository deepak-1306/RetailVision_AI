from __future__ import annotations

from pydantic import BaseModel


class RecommendationOut(BaseModel):
    id: str
    job_id: str
    shelf_zone: str | None
    trigger_pattern: str
    priority: str
    title: str
    description: str
    affected_customers: int

    class Config:
        from_attributes = True

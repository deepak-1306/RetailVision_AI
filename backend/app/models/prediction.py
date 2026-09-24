from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class PurchaseIntentPrediction(Base):
    __tablename__ = "purchase_intent_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("processing_jobs.id"), nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    dwell_time_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    touch_count: Mapped[int] = mapped_column(Integer, default=0)
    pick_count: Mapped[int] = mapped_column(Integer, default=0)
    return_count: Mapped[int] = mapped_column(Integer, default=0)
    viewing_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    purchase_intent_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100
    intent_label: Mapped[str] = mapped_column(String(50), default="low")  # low | medium | high
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    job: Mapped["ProcessingJob"] = relationship(back_populates="predictions")

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("processing_jobs.id"), nullable=False)
    shelf_zone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trigger_pattern: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. "high_view_low_pick"
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low | medium | high
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_customers: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    job: Mapped["ProcessingJob"] = relationship(back_populates="recommendations")

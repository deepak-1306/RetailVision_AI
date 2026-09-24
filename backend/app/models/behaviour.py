from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class BehaviourType(str, enum.Enum):
    VIEWING = "viewing"
    TOUCHING = "touching"
    PICKING = "picking"
    PICKING_AND_RETURNING = "picking_and_returning"
    PICKING_AND_PUTTING_BACK = "picking_and_putting_back"
    NO_INTEREST = "no_interest_in_buying"
    TURNING_TOWARDS_SHELF = "turning_towards_shelf"


class BehaviourEvent(Base):
    __tablename__ = "behaviour_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("processing_jobs.id"), nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)  # ByteTrack customer track ID
    behaviour_type: Mapped[BehaviourType] = mapped_column(Enum(BehaviourType), nullable=False)
    start_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    shelf_zone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bbox_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    job: Mapped["ProcessingJob"] = relationship(back_populates="behaviours")

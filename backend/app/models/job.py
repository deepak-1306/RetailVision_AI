from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Enum, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PREPROCESSING = "preprocessing"
    DETECTING = "detecting"
    TRACKING = "tracking"
    CLASSIFYING_BEHAVIOUR = "classifying_behaviour"
    PREDICTING_INTENT = "predicting_intent"
    GENERATING_RECOMMENDATIONS = "generating_recommendations"
    ANNOTATING_VIDEO = "annotating_video"
    GENERATING_INSIGHTS = "generating_insights"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey("videos.id"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    annotated_video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="jobs")
    behaviours: Mapped[list["BehaviourEvent"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    predictions: Mapped[list["PurchaseIntentPrediction"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="job", cascade="all, delete-orphan")

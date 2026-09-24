from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.job import JobStatus


class JobOut(BaseModel):
    id: str
    video_id: str
    status: JobStatus
    progress: int
    error_message: str | None
    annotated_video_path: str | None = None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True

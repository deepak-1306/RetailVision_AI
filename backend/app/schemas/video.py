from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class VideoOut(BaseModel):
    id: str
    filename: str
    original_name: str
    duration_seconds: float | None
    fps: float | None
    width: int | None
    height: int | None
    store_zone: str | None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class VideoUploadResponse(BaseModel):
    video: VideoOut
    job_id: str

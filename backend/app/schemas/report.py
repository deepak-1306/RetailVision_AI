from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReportOut(BaseModel):
    id: str
    job_id: str
    file_path: str
    summary: str | None
    llm_insights: str | None
    generated_at: datetime

    class Config:
        from_attributes = True

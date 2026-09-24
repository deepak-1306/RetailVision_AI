from __future__ import annotations

from pydantic import BaseModel


class InsightQuestion(BaseModel):
    job_id: str
    question: str


class InsightAnswer(BaseModel):
    question: str
    answer: str

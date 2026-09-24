from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.jobs import _get_owned_job
from app.db.session import get_db
from app.models.user import User
from app.schemas.insight import InsightAnswer, InsightQuestion
from app.services.insight_service import answer_question, generate_summary

router = APIRouter(prefix="/insights", tags=["LLM Business Insights"])


@router.get("/{job_id}/summary")
def get_summary(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    _get_owned_job(db, job_id, current_user)
    return {"job_id": job_id, "summary": generate_summary(db, job_id)}


@router.post("/ask", response_model=InsightAnswer)
def ask_question(payload: InsightQuestion, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> InsightAnswer:
    _get_owned_job(db, payload.job_id, current_user)
    answer = answer_question(db, payload.job_id, payload.question)
    return InsightAnswer(question=payload.question, answer=answer)

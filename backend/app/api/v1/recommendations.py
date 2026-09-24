from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.jobs import _get_owned_job
from app.db.session import get_db
from app.models.recommendation import Recommendation
from app.models.user import User
from app.schemas.recommendation import RecommendationOut

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/{job_id}", response_model=list[RecommendationOut])
def list_recommendations(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[Recommendation]:
    _get_owned_job(db, job_id, current_user)
    return (
        db.query(Recommendation)
        .filter(Recommendation.job_id == job_id)
        .order_by(Recommendation.priority.asc())
        .all()
    )

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.jobs import _get_owned_job
from app.db.session import get_db
from app.models.prediction import PurchaseIntentPrediction
from app.models.user import User
from app.schemas.prediction import PurchaseIntentOut, PurchaseIntentSummary
from app.services.analytics_service import get_purchase_intent_summary

router = APIRouter(prefix="/predictions", tags=["Purchase Intent"])


@router.get("/{job_id}", response_model=list[PurchaseIntentOut])
def list_predictions(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[PurchaseIntentPrediction]:
    _get_owned_job(db, job_id, current_user)
    return (
        db.query(PurchaseIntentPrediction)
        .filter(PurchaseIntentPrediction.job_id == job_id)
        .order_by(PurchaseIntentPrediction.purchase_intent_score.desc())
        .all()
    )


@router.get("/{job_id}/summary", response_model=PurchaseIntentSummary)
def prediction_summary(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    _get_owned_job(db, job_id, current_user)
    return get_purchase_intent_summary(db, job_id)

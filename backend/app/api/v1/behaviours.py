from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.jobs import _get_owned_job
from app.db.session import get_db
from app.models.behaviour import BehaviourEvent
from app.models.user import User
from app.schemas.behaviour import BehaviourDistributionItem, BehaviourEventOut, CustomerJourneyItem
from app.services.analytics_service import get_behaviour_distribution

router = APIRouter(prefix="/behaviours", tags=["Behaviour Analytics"])


@router.get("/{job_id}/timeline", response_model=list[BehaviourEventOut])
def get_timeline(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BehaviourEvent]:
    _get_owned_job(db, job_id, current_user)
    return (
        db.query(BehaviourEvent)
        .filter(BehaviourEvent.job_id == job_id)
        .order_by(BehaviourEvent.start_time_seconds.asc())
        .all()
    )


@router.get("/{job_id}/second-by-second")
def get_second_by_second(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns a second-by-second breakdown of all customer actions.
    Each entry contains the second timestamp, a list of active actions
    (track_id, behaviour_type, confidence, shelf_zone) at that second.
    """
    _get_owned_job(db, job_id, current_user)
    events = (
        db.query(BehaviourEvent)
        .filter(BehaviourEvent.job_id == job_id)
        .order_by(BehaviourEvent.start_time_seconds.asc())
        .all()
    )

    if not events:
        return []

    max_time = int(max(e.end_time_seconds for e in events)) + 1

    result = []
    for sec in range(max_time):
        t = float(sec)
        active_at_sec = []
        for e in events:
            if e.start_time_seconds <= t <= e.end_time_seconds:
                # behaviour_type may be a BehaviourType enum or a raw str depending on DB backend
                btype = e.behaviour_type.value if hasattr(e.behaviour_type, "value") else str(e.behaviour_type)
                active_at_sec.append({
                    "track_id": e.track_id,
                    "behaviour_type": btype,
                    "behaviour_label": btype.replace("_", " ").title(),
                    "confidence": round(e.confidence, 2),
                    "shelf_zone": e.shelf_zone or "Unzoned",
                })
        if active_at_sec:
            result.append({"second": sec, "timestamp": f"{sec}s", "actions": active_at_sec})

    return result


@router.get("/{job_id}/distribution", response_model=list[BehaviourDistributionItem])
def get_distribution(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[dict]:
    _get_owned_job(db, job_id, current_user)
    return get_behaviour_distribution(db, job_id)


@router.get("/{job_id}/customer-journey", response_model=list[CustomerJourneyItem])
def get_customer_journey(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[dict]:
    _get_owned_job(db, job_id, current_user)
    events = (
        db.query(BehaviourEvent)
        .filter(BehaviourEvent.job_id == job_id)
        .order_by(BehaviourEvent.track_id.asc(), BehaviourEvent.start_time_seconds.asc())
        .all()
    )
    grouped: dict[int, list[BehaviourEvent]] = {}
    for e in events:
        grouped.setdefault(e.track_id, []).append(e)

    journeys = []
    for track_id, evs in grouped.items():
        total_dwell = sum(e.end_time_seconds - e.start_time_seconds for e in evs)
        journeys.append({"track_id": track_id, "events": evs, "total_dwell_seconds": round(total_dwell, 2)})
    return journeys

"""
Shared helpers that turn raw ORM rows (BehaviourEvent, PurchaseIntentPrediction,
Recommendation) into the aggregate structures used by the dashboard API,
the PDF report, and the LLM insight generator -- so all three stay
consistent with each other.
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from app.models.behaviour import BehaviourEvent
from app.models.prediction import PurchaseIntentPrediction
from app.models.recommendation import Recommendation


def get_behaviour_distribution(db: Session, job_id: str) -> list[dict]:
    events = db.query(BehaviourEvent).filter(BehaviourEvent.job_id == job_id).all()
    counts = Counter(e.behaviour_type.value for e in events)
    total = sum(counts.values()) or 1
    return [
        {"behaviour_type": k, "count": v, "percentage": round(100 * v / total, 1)}
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
    ]


def get_purchase_intent_summary(db: Session, job_id: str) -> dict:
    preds = db.query(PurchaseIntentPrediction).filter(PurchaseIntentPrediction.job_id == job_id).all()
    if not preds:
        return {
            "average_score": 0.0, "high_intent_customers": 0,
            "medium_intent_customers": 0, "low_intent_customers": 0, "total_customers": 0,
        }
    avg = sum(p.purchase_intent_score for p in preds) / len(preds)
    return {
        "average_score": round(avg, 1),
        "high_intent_customers": sum(1 for p in preds if p.intent_label == "high"),
        "medium_intent_customers": sum(1 for p in preds if p.intent_label == "medium"),
        "low_intent_customers": sum(1 for p in preds if p.intent_label == "low"),
        "total_customers": len(preds),
    }


def get_zone_summaries(db: Session, job_id: str) -> list[dict]:
    events = db.query(BehaviourEvent).filter(BehaviourEvent.job_id == job_id).all()
    zones: dict[str, Counter] = {}
    for e in events:
        zone = e.shelf_zone or "Unzoned"
        zones.setdefault(zone, Counter())[e.behaviour_type.value] += 1
    return [{"shelf_zone": z, **dict(c)} for z, c in zones.items()]


def get_recommendations_dicts(db: Session, job_id: str) -> list[dict]:
    recs = db.query(Recommendation).filter(Recommendation.job_id == job_id).all()
    return [
        {
            "shelf_zone": r.shelf_zone, "trigger_pattern": r.trigger_pattern,
            "priority": r.priority, "title": r.title, "description": r.description,
            "affected_customers": r.affected_customers,
        }
        for r in recs
    ]

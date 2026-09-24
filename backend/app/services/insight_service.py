from __future__ import annotations

from sqlalchemy.orm import Session

from ai.llm.insight_generator import JobAnalyticsContext, LLMInsightGenerator
from app.core.config import settings
from app.services.analytics_service import (
    get_behaviour_distribution,
    get_purchase_intent_summary,
    get_recommendations_dicts,
    get_zone_summaries,
)


def build_context(db: Session, job_id: str) -> JobAnalyticsContext:
    dist = {item["behaviour_type"]: item["count"] for item in get_behaviour_distribution(db, job_id)}
    return JobAnalyticsContext(
        behaviour_distribution=dist,
        zone_summaries=get_zone_summaries(db, job_id),
        purchase_intent_summary=get_purchase_intent_summary(db, job_id),
        recommendations=get_recommendations_dicts(db, job_id),
    )


def get_generator() -> LLMInsightGenerator:
    return LLMInsightGenerator(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
    )


def generate_summary(db: Session, job_id: str) -> str:
    context = build_context(db, job_id)
    return get_generator().generate_summary(context)


def answer_question(db: Session, job_id: str, question: str) -> str:
    context = build_context(db, job_id)
    return get_generator().answer_question(context, question)

"""
LLM Business Insight Generator.

Wraps the Anthropic API to turn structured job analytics (behaviour
distribution, purchase-intent summary, and recommendations) into a narrative
business summary, and to answer free-form manager questions such as
"Why are customers abandoning products?" grounded in that same data.

Falls back to a deterministic templated summary when no ANTHROPIC_API_KEY is
configured, so the rest of the pipeline (and the dashboard) keeps working in
an offline/demo environment without requiring API credentials.
"""
from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class JobAnalyticsContext:
    behaviour_distribution: dict[str, int]
    zone_summaries: list[dict]
    purchase_intent_summary: dict
    recommendations: list[dict]


SYSTEM_PROMPT = (
    "You are a retail business analyst embedded in RetailVision AI, a retail "
    "CCTV analytics platform. You are given structured analytics extracted "
    "from a computer-vision pipeline (customer behaviour counts, per-shelf "
    "zone statistics, purchase-intent scores, and generated recommendations) "
    "for a single store camera session. Write in a clear, concise, "
    "action-oriented tone for a busy store manager. Ground every claim in "
    "the provided data -- do not invent numbers. Keep responses focused and "
    "practical."
)


def _context_to_prompt(context: JobAnalyticsContext, question: str | None = None) -> str:
    payload = {
        "behaviour_distribution": context.behaviour_distribution,
        "zone_summaries": context.zone_summaries,
        "purchase_intent_summary": context.purchase_intent_summary,
        "recommendations": context.recommendations,
    }
    base = f"Store analytics data:\n{json.dumps(payload, indent=2)}\n\n"
    if question:
        return base + f"Manager question: {question}\nAnswer the question using only the data above."
    return base + (
        "Write a 3-5 sentence executive summary of what happened in this session, "
        "the most important pattern you notice, and the single highest-impact "
        "action the manager should take tomorrow."
    )


def _fallback_summary(context: JobAnalyticsContext) -> str:
    dist = context.behaviour_distribution
    total = sum(dist.values()) or 1
    top_behaviour = max(dist, key=dist.get) if dist else "viewing"
    intent = context.purchase_intent_summary
    lines = [
        f"This session logged {total} behaviour events across {len(context.zone_summaries)} shelf zone(s), "
        f"with '{top_behaviour.replace('_', ' ')}' as the most common customer behaviour.",
        f"Average purchase intent was {intent.get('average_score', 0):.0f}/100, with "
        f"{intent.get('high_intent_customers', 0)} high-intent, {intent.get('medium_intent_customers', 0)} "
        f"medium-intent, and {intent.get('low_intent_customers', 0)} low-intent customers detected.",
    ]
    if context.recommendations:
        top_rec = context.recommendations[0]
        lines.append(
            f"Highest-priority action: {top_rec.get('title')} — {top_rec.get('description')}"
        )
    return " ".join(lines)


def _fallback_qa(context: JobAnalyticsContext, question: str) -> str:
    q = question.lower()
    
    if "abandon" in q or "no interest" in q or "putting back" in q:
        dist = context.behaviour_distribution
        putting_back = dist.get("picking_and_putting_back", 0)
        no_interest = dist.get("no_interest_in_buying", 0)
        return (f"Based on the data, there were {putting_back} instances of customers picking and putting items back, "
                f"and {no_interest} instances of customers showing no interest. "
                "This typically suggests price sensitivity or dissatisfaction with the product information on the shelf.")
        
    if "optimization" in q or "shelf" in q or "zone" in q:
        if not context.zone_summaries:
            return "There is no specific shelf zone data available for this session."
        
        # Find zone with lowest purchase intent or highest 'putting back' rate
        worst_zone = min(context.zone_summaries, key=lambda z: z.get("high_intent_customers", 0) - z.get("low_intent_customers", 0))
        return (f"The shelf zone '{worst_zone.get('shelf_zone', 'Unknown')}' appears to need the most optimization. "
                f"It had {worst_zone.get('low_intent_customers', 0)} low-intent interactions compared to only "
                f"{worst_zone.get('high_intent_customers', 0)} high-intent interactions.")
                
    if "tomorrow" in q or "manager" in q or "action" in q or "should do" in q:
        if not context.recommendations:
            return "No specific AI recommendations were generated for this session to act upon."
        
        top_rec = context.recommendations[0]
        return (f"The highest priority action for tomorrow is: {top_rec.get('title')}. "
                f"Specifically, {top_rec.get('description')} "
                f"This affects {top_rec.get('affected_customers', 0)} customers.")
                
    if "intent" in q or "purchase" in q or "buy" in q:
        intent = context.purchase_intent_summary
        return (f"The average purchase intent score across all tracked customers is {intent.get('average_score', 0):.1f}/100. "
                f"We observed {intent.get('high_intent_customers', 0)} high intent, {intent.get('medium_intent_customers', 0)} medium intent, "
                f"and {intent.get('low_intent_customers', 0)} low intent customers.")
                
    return ("(Offline AI Mode) I can't fully parse that question without an active internet connection to the LLM. "
            "However, based on the summary: " + _fallback_summary(context))


class LLMInsightGenerator:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6", max_tokens: int = 1500):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    def _call_anthropic(self, user_prompt: str) -> str | None:
        if not self.api_key:
            return None
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
            return "\n".join(parts).strip() or None
        except Exception:
            # Network/auth/SDK errors should never break the pipeline --
            # fall back to the templated summary instead.
            return None

    def generate_summary(self, context: JobAnalyticsContext) -> str:
        prompt = _context_to_prompt(context)
        result = self._call_anthropic(prompt)
        return result or _fallback_summary(context)

    def answer_question(self, context: JobAnalyticsContext, question: str) -> str:
        prompt = _context_to_prompt(context, question=question)
        result = self._call_anthropic(prompt)
        if result:
            return result
        return _fallback_qa(context, question)

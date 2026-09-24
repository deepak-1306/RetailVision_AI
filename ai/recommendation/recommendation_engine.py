"""
Rule-based retail recommendation engine.

Maps aggregate behaviour + purchase-intent patterns per shelf zone to
concrete merchandising actions. Fires on ANY detected activity — even
single-event occurrences — so every processed video produces output.

Actions tracked:
  viewing               -> store viewing / browsing shelf
  touching              -> briefly feeling/touching product
  picking               -> lifting product off shelf
  picking_and_putting_back -> quick rejection
  picking_and_returning -> examined then returned
  no_interest_in_buying -> walked past without stopping
  turning_towards_shelf -> turned body toward shelf but didn't engage
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ZoneStats:
    shelf_zone: str
    viewing_count: int
    touching_count: int
    picking_count: int
    return_count: int = 0
    put_back_count: int = 0
    no_interest_count: int = 0
    turning_count: int = 0
    avg_purchase_intent: float = 0.0
    customer_count: int = 0


@dataclass
class RecommendationItem:
    shelf_zone: str
    trigger_pattern: str
    priority: str
    title: str
    description: str
    affected_customers: int


def generate_recommendations(zone_stats: list[ZoneStats]) -> list[RecommendationItem]:
    recommendations: list[RecommendationItem] = []

    for stats in zone_stats:
        if stats.customer_count == 0:
            continue

        total_interactions = (
            stats.viewing_count + stats.touching_count + stats.picking_count +
            stats.return_count + stats.put_back_count +
            stats.no_interest_count + stats.turning_count
        )

        zone_recs = 0

        # ── 1. High viewing, low picking → Visibility / conversion problem ──────
        if stats.viewing_count >= 1 and stats.picking_count < stats.viewing_count:
            conv_rate = stats.picking_count / max(stats.viewing_count, 1)
            if conv_rate < 0.6 or stats.viewing_count >= 2:
                recommendations.append(RecommendationItem(
                    shelf_zone=stats.shelf_zone,
                    trigger_pattern="high_view_low_pick",
                    priority="high",
                    title=f"Boost product conversion in {stats.shelf_zone}",
                    description=(
                        f"{stats.viewing_count} customer(s) engaged in 'store viewing' in {stats.shelf_zone}, "
                        f"but only {stats.picking_count} actually picked up a product "
                        f"(conversion: {conv_rate:.0%}). "
                        "Consider improving eye-level placement, adding shelf-talkers, "
                        "using better packaging contrast, or offering a 'Try Me' tester to "
                        "bridge the gap between visual interest and physical engagement."
                    ),
                    affected_customers=stats.viewing_count,
                ))
                zone_recs += 1

        # ── 2. Touching without picking → Tactile or packaging friction ─────────
        if stats.touching_count >= 1:
            touch_to_pick = stats.picking_count / max(stats.touching_count, 1)
            priority = "critical" if touch_to_pick < 0.3 else "high"
            recommendations.append(RecommendationItem(
                shelf_zone=stats.shelf_zone,
                trigger_pattern="high_touch_low_pick",
                priority=priority,
                title=f"Fix tactile friction causing product rejection in {stats.shelf_zone}",
                description=(
                    f"{stats.touching_count} customer(s) 'touched' items in {stats.shelf_zone} "
                    f"without 'picking' them up ({stats.touching_count} touches → {stats.picking_count} picks). "
                    "This signals a gap between expectation and physical reality. Common causes: "
                    "packaging that's hard to grip, confusion about which variant to select, or "
                    "a product that feels cheap relative to its displayed price. "
                    "Consider opening a display model, revising packaging ergonomics, or adding "
                    "clear variant labels to reduce drop-off at the touch stage."
                ),
                affected_customers=stats.touching_count,
            ))
            zone_recs += 1

        # ── 3. Picking and Putting Back (quick) → Immediate price/label shock ───
        if stats.put_back_count >= 1:
            put_back_rate = stats.put_back_count / max(stats.picking_count, 1)
            priority = "critical" if put_back_rate >= 0.4 or stats.put_back_count >= 2 else "high"
            recommendations.append(RecommendationItem(
                shelf_zone=stats.shelf_zone,
                trigger_pattern="picking_and_putting_back",
                priority=priority,
                title=f"Address instant product rejection in {stats.shelf_zone}",
                description=(
                    f"{stats.put_back_count} 'picking and putting back' event(s) detected in {stats.shelf_zone}. "
                    "Quick put-backs (within seconds of picking) signal an immediate mismatch between "
                    "expectation and reality — most commonly caused by sticker shock, unclear pricing, "
                    "or a misleading front-of-pack claim. "
                    "Audit your price point visibility, ensure the shelf price tag is right next to the product, "
                    "and verify that the product visual matches what customers see on the shelf."
                ),
                affected_customers=stats.put_back_count,
            ))
            zone_recs += 1

        # ── 4. Picking and Returning (considered then returned) → Hesitation ────
        if stats.return_count >= 1:
            return_rate = stats.return_count / max(stats.picking_count, 1)
            priority = "high" if return_rate >= 0.4 or stats.return_count >= 2 else "medium"
            recommendations.append(RecommendationItem(
                shelf_zone=stats.shelf_zone,
                trigger_pattern="picking_and_returning",
                priority=priority,
                title=f"Reduce buyer hesitation in {stats.shelf_zone}",
                description=(
                    f"{stats.return_count} customer(s) in {stats.shelf_zone} engaged in 'picking and returning' — "
                    "they examined the product at length before putting it back. "
                    "This is deeper hesitation: they want the product but aren't fully convinced. "
                    "Common causes: absence of ingredient/nutrition info, lack of social proof (reviews), "
                    "unclear usage instructions, or competitive alternative nearby. "
                    "Add a QR code linking to reviews, place comparison charts on the shelf, or "
                    "have staff proactively assist customers in this zone."
                ),
                affected_customers=stats.return_count,
            ))
            zone_recs += 1

        # ── 5. Turning toward shelf without engaging → Poor visual hook ─────────
        if stats.turning_count >= 1:
            turn_to_view = stats.viewing_count / max(stats.turning_count, 1)
            priority = "high" if turn_to_view < 0.3 else "medium"
            recommendations.append(RecommendationItem(
                shelf_zone=stats.shelf_zone,
                trigger_pattern="turning_to_shelf_dropoff",
                priority=priority,
                title=f"Strengthen initial shelf hook in {stats.shelf_zone}",
                description=(
                    f"{stats.turning_count} customer(s) 'turned toward the shelf' in {stats.shelf_zone} "
                    f"but {round((1 - turn_to_view) * 100)}% failed to stop and view. "
                    "You captured their physical attention (body rotation) but the display failed to hold them. "
                    "This is a prime opportunity: the customer already directed their body toward the shelf. "
                    "Add brighter shelf lighting (warm LED spots), a bold hero product at eye level, "
                    "contrasting shelf-talkers, or a 'New Arrival' flag to convert that turn into a dwell."
                ),
                affected_customers=stats.turning_count,
            ))
            zone_recs += 1

        # ── 6. No interest in buying → Layout / traffic flow problem ────────────
        if stats.no_interest_count >= 1:
            no_interest_rate = stats.no_interest_count / max(stats.customer_count, 1)
            priority = "high" if no_interest_rate >= 0.5 or stats.no_interest_count >= 3 else "medium"
            recommendations.append(RecommendationItem(
                shelf_zone=stats.shelf_zone,
                trigger_pattern="no_interest",
                priority=priority,
                title=f"Rethink shelf layout and traffic flow in {stats.shelf_zone}",
                description=(
                    f"{stats.no_interest_count} of {stats.customer_count} customer(s) walked through "
                    f"{stats.shelf_zone} with 'no interest in buying' ({no_interest_rate:.0%} pass-through rate). "
                    "These customers are physically present but completely disengaged with the display. "
                    "Try moving a high-demand anchor product (e.g. a popular brand) to this zone to "
                    "create a 'halo effect', refresh the planogram, use end-cap features, or place "
                    "promotional signage 2–3 metres before the zone to prime customer attention in advance."
                ),
                affected_customers=stats.no_interest_count,
            ))
            zone_recs += 1

        # ── 7. Strong pick rate + high intent → Maintain and cross-sell ─────────
        total_picks = stats.picking_count
        if total_picks >= 1 and stats.avg_purchase_intent > 50:
            recommendations.append(RecommendationItem(
                shelf_zone=stats.shelf_zone,
                trigger_pattern="high_engagement_high_intent",
                priority="low",
                title=f"Maintain stock and expand cross-sells in {stats.shelf_zone}",
                description=(
                    f"{stats.shelf_zone} shows strong customer engagement: {total_picks} pick(s) with "
                    f"an average purchase intent of {stats.avg_purchase_intent:.0f}/100. "
                    "This zone is actively converting. Protect it by ensuring consistent replenishment, "
                    "never letting it go out of stock. Leverage its success by placing high-margin "
                    "complementary products directly adjacent to capture impulse cross-sells from "
                    "already-motivated buyers."
                ),
                affected_customers=stats.customer_count,
            ))
            zone_recs += 1

        # ── 8. Fallback: activity seen but no specific rule triggered ────────────
        if zone_recs == 0 and total_interactions > 0:
            recommendations.append(RecommendationItem(
                shelf_zone=stats.shelf_zone,
                trigger_pattern="baseline_activity",
                priority="low",
                title=f"Monitor and baseline customer flow in {stats.shelf_zone}",
                description=(
                    f"{stats.customer_count} customer(s) interacted with {stats.shelf_zone}, "
                    f"producing {stats.viewing_count} views, {stats.touching_count} touches, "
                    f"and {stats.picking_count} picks across the session. "
                    "Engagement appears balanced without acute friction points at this time. "
                    "Continue monitoring to build a performance baseline, then set improvement "
                    "targets for conversion rate and dwell time over the next 4 weeks."
                ),
                affected_customers=stats.customer_count,
            ))

    # ── Global fallback: if zero zone data produced recommendations ──────────────
    if not recommendations:
        recommendations.append(RecommendationItem(
            shelf_zone="All Zones",
            trigger_pattern="insufficient_data",
            priority="low",
            title="Upload longer footage for richer insights",
            description=(
                "The analysed video segment did not produce enough customer interaction events to "
                "generate zone-specific recommendations. For best results, upload footage of at least "
                "60–120 seconds that captures customers actively interacting with your shelving displays. "
                "Ensure the camera angle is perpendicular to the shelf and provides a clear, unobstructed "
                "view of both the products and the customers' hands and bodies."
            ),
            affected_customers=0,
        ))

    # Sort by priority: critical → high → medium → low
    _PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(key=lambda r: _PRIORITY_ORDER.get(r.priority.lower(), 99))
    return recommendations

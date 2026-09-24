"""
PDF report generation using ReportLab.

Produces a downloadable executive report combining behaviour distribution,
purchase-intent summary, per-zone stats, recommendations, and the LLM
narrative summary for a single processing job.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from app.core.config import settings


def generate_pdf_report(
    job_id: str,
    video_name: str,
    behaviour_distribution: list[dict],
    purchase_intent_summary: dict,
    zone_summaries: list[dict],
    recommendations: list[dict],
    llm_summary: str,
) -> str:
    output_path = str(Path(settings.REPORT_DIR) / f"{job_id}_report.pdf")
    Path(settings.REPORT_DIR).mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             topMargin=2 * cm, bottomMargin=2 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], textColor=colors.HexColor("#1E293B"))
    heading_style = ParagraphStyle("HeadingStyle", parent=styles["Heading2"], textColor=colors.HexColor("#4F46E5"),
                                    spaceBefore=14, spaceAfter=6)
    body_style = ParagraphStyle("BodyStyle", parent=styles["BodyText"], leading=15)

    story = []
    story.append(Paragraph("RetailVision AI — Customer Behaviour Report", title_style))
    story.append(Paragraph(f"Video: {video_name}", body_style))
    story.append(Paragraph(f"Job ID: {job_id}", body_style))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph(llm_summary, body_style))

    story.append(Paragraph("Purchase Intent Summary", heading_style))
    pi = purchase_intent_summary
    pi_table_data = [
        ["Average Score", "High Intent", "Medium Intent", "Low Intent", "Total Customers"],
        [f"{pi.get('average_score', 0):.1f}/100", pi.get("high_intent_customers", 0),
         pi.get("medium_intent_customers", 0), pi.get("low_intent_customers", 0),
         pi.get("total_customers", 0)],
    ]
    story.append(_styled_table(pi_table_data))

    story.append(Paragraph("Behaviour Distribution", heading_style))
    behaviour_table_data = [["Behaviour", "Count", "Percentage"]]
    for item in behaviour_distribution:
        behaviour_table_data.append([
            item["behaviour_type"].replace("_", " ").title(), item["count"], f"{item['percentage']}%"
        ])
    story.append(_styled_table(behaviour_table_data))

    story.append(Paragraph("Shelf Zone Summary", heading_style))
    if zone_summaries:
        keys = sorted({k for z in zone_summaries for k in z.keys() if k != "shelf_zone"})
        zone_table_data = [["Zone"] + [k.replace("_", " ").title() for k in keys]]
        for z in zone_summaries:
            zone_table_data.append([z.get("shelf_zone", "Unzoned")] + [z.get(k, 0) for k in keys])
        story.append(_styled_table(zone_table_data))
    else:
        story.append(Paragraph("No zone data available.", body_style))

    story.append(Paragraph("AI Recommendations", heading_style))
    if recommendations:
        for rec in recommendations:
            story.append(Paragraph(
                f"<b>[{rec['priority'].upper()}] {rec['title']}</b> — {rec['description']}",
                body_style,
            ))
            story.append(Spacer(1, 0.2 * cm))
    else:
        story.append(Paragraph("No recommendations generated for this session.", body_style))

    doc.build(story)
    return output_path


def _styled_table(data: list[list]) -> Table:
    table = Table(data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table

"""Aggregate clinician feedback and validation events for the admin dashboard."""

from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Recommendation, RecommendationReport
from app.models.validation import ReportFeedback, ValidationEvent
from app.schemas.validation import ValidationDashboardRead, ValidationEventRead

_SECTION_LABELS: dict[str, str] = {
    "report_confidence": "Report Confidence",
    "biological_reasoning_summary": "Biological Reasoning Summary",
    "patient_summary": "Patient Summary",
    "biological_systems": "Biological Systems",
    "evidence_overview": "Evidence Overview",
    "evidence_synthesis": "Evidence Synthesis",
    "evidence_passport": "Evidence Passport",
    "differential_explanations": "Differential Biological Explanations",
    "missing_information": "Missing Information",
    "patient_evidence_gaps": "Evidence Gaps",
    "supporting_literature": "Supporting Literature",
    "methodology": "How This Report Was Generated",
    "lab_trends": "Lab Trends",
}


def _section_label(section_name: str | None) -> str | None:
    if not section_name:
        return None
    return _SECTION_LABELS.get(section_name, section_name.replace("_", " ").title())


def _top_counter(counter: Counter, total: int) -> tuple[str | None, float | None]:
    if not counter or total <= 0:
        return None, None
    name, count = counter.most_common(1)[0]
    return name, round(count / total * 100, 1)


async def build_validation_dashboard(db: AsyncSession) -> ValidationDashboardRead:
    reports_generated = int(await db.scalar(select(func.count()).select_from(RecommendationReport)) or 0)
    reports_reviewed = int(await db.scalar(select(func.count()).select_from(ReportFeedback)) or 0)

    avg_usefulness = await db.scalar(select(func.avg(ReportFeedback.clinical_usefulness_score)))
    avg_trust = await db.scalar(select(func.avg(ReportFeedback.trust_score)))
    avg_time_saved = await db.scalar(
        select(func.avg(ReportFeedback.estimated_time_saved_minutes)).where(
            ReportFeedback.estimated_time_saved_minutes.is_not(None)
        )
    )

    would_use_rows = await db.execute(
        select(ReportFeedback.would_use_again).where(ReportFeedback.would_use_again.is_not(None))
    )
    would_use_values = [row[0] for row in would_use_rows.all()]
    would_use_again_percent = None
    if would_use_values:
        positive = sum(1 for v in would_use_values if v in {"yes", "probably"})
        would_use_again_percent = round(positive / len(would_use_values) * 100, 1)

    useful_rows = await db.execute(
        select(ReportFeedback.most_useful_section).where(ReportFeedback.most_useful_section.is_not(None))
    )
    least_rows = await db.execute(
        select(ReportFeedback.least_useful_section).where(ReportFeedback.least_useful_section.is_not(None))
    )
    useful_counter = Counter(row[0] for row in useful_rows.all())
    least_counter = Counter(row[0] for row in least_rows.all())
    useful_total = sum(useful_counter.values())
    least_total = sum(least_counter.values())
    most_useful, most_useful_pct = _top_counter(useful_counter, useful_total)
    least_useful, least_useful_pct = _top_counter(least_counter, least_total)

    event_rows = await db.execute(
        select(ValidationEvent.section_name, func.count())
        .where(ValidationEvent.section_name.is_not(None))
        .group_by(ValidationEvent.section_name)
        .order_by(func.count().desc())
        .limit(1)
    )
    opened = event_rows.first()
    most_opened_section = _section_label(opened[0]) if opened else None

    confidence_counter: Counter[str] = Counter()
    insight_reports = await db.execute(
        select(RecommendationReport.report_insights).where(RecommendationReport.report_insights.is_not(None))
    )
    for (insights,) in insight_reports.all():
        if not insights:
            continue
        assessment = insights.get("overall_confidence_assessment") or {}
        label = assessment.get("confidence_label")
        if label:
            confidence_counter[label] += 1
    confidence_total = sum(confidence_counter.values())
    confidence_distribution = {
        label: round(count / confidence_total * 100, 1)
        for label, count in confidence_counter.items()
    } if confidence_total else {}

    biomarker_counter: Counter[str] = Counter()
    for (insights,) in insight_reports.all():
        if not insights:
            continue
        missing = insights.get("missing_information") or {}
        for marker in missing.get("suggested_biomarkers") or []:
            biomarker_counter[marker] += 1
    most_requested = [
        {"biomarker_name": name, "count": count}
        for name, count in biomarker_counter.most_common(8)
    ]

    disputed: Counter[str] = Counter()
    low_agreement = await db.execute(
        select(ReportFeedback.report_id).where(ReportFeedback.reasoning_agreement.in_(("partially", "no")))
    )
    disputed_report_ids = [row[0] for row in low_agreement.all()]
    if disputed_report_ids:
        rec_rows = await db.execute(
            select(Recommendation.intervention_name, func.count())
            .where(Recommendation.report_id.in_(disputed_report_ids))
            .group_by(Recommendation.intervention_name)
            .order_by(func.count().desc())
            .limit(8)
        )
        disputed = Counter({name: count for name, count in rec_rows.all()})

    comments_rows = await db.execute(
        select(ReportFeedback.free_text_feedback, ReportFeedback.safety_concerns, ReportFeedback.created_at)
        .where(
            (ReportFeedback.free_text_feedback.is_not(None))
            | (ReportFeedback.safety_concerns.is_not(None))
        )
        .order_by(ReportFeedback.created_at.desc())
        .limit(20)
    )
    free_text = []
    for comment, safety, created_at in comments_rows.all():
        text = comment or safety
        if text:
            free_text.append({"text": text, "created_at": created_at.isoformat()})

    recent_event_rows = await db.execute(
        select(ValidationEvent).order_by(ValidationEvent.created_at.desc()).limit(15)
    )
    recent_events = [
        ValidationEventRead(
            id=event.id,
            report_id=event.report_id,
            event_type=event.event_type,
            section_name=event.section_name,
            created_at=event.created_at,
        )
        for event in recent_event_rows.scalars().all()
    ]

    return ValidationDashboardRead(
        reports_generated=reports_generated,
        reports_reviewed=reports_reviewed,
        average_usefulness_score=round(float(avg_usefulness), 2) if avg_usefulness is not None else None,
        average_trust_score=round(float(avg_trust), 2) if avg_trust is not None else None,
        average_time_saved_minutes=round(float(avg_time_saved), 1) if avg_time_saved is not None else None,
        would_use_again_percent=would_use_again_percent,
        most_useful_section=_section_label(most_useful),
        most_useful_section_percent=most_useful_pct,
        least_useful_section=_section_label(least_useful),
        least_useful_section_percent=least_useful_pct,
        most_opened_section=most_opened_section,
        report_confidence_distribution=confidence_distribution,
        most_requested_biomarkers=most_requested,
        disputed_recommendations=[
            {"intervention_name": name, "low_agreement_count": count}
            for name, count in disputed.most_common(8)
        ],
        free_text_feedback=free_text,
        recent_events=recent_events,
    )


def serialize_event_metadata(metadata: dict | None) -> str | None:
    if not metadata:
        return None
    return json.dumps(metadata)
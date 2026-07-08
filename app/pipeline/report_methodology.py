"""User-facing methodology — how HerbaGraph reached this report."""

from __future__ import annotations

_ABNORMAL_STATUSES = frozenset({"critical_low", "low", "high", "critical_high"})


def _abnormal_findings(biomarker_summary: dict) -> list[dict]:
    return [
        m
        for m in biomarker_summary.get("measured_biomarkers", [])
        if m.get("status") in _ABNORMAL_STATUSES
    ]


def _status_phrase(status: str | None) -> str:
    mapping = {
        "low": "low",
        "critical_low": "critically low",
        "high": "high",
        "critical_high": "critically high",
    }
    return mapping.get(status or "", "outside reference range")


def build_report_methodology(
    biomarker_summary: dict,
    biological_systems: list[dict],
    pathway_activations: list[dict],
    recommendations: list[dict],
    citations: list[dict] | None = None,
) -> dict:
    """Seven-step transparent workflow tying report sections together."""
    abnormal = _abnormal_findings(biomarker_summary)
    total = biomarker_summary.get("total_biomarkers", 0)
    active_systems = [s for s in biological_systems if (s.get("signal_level") or 0) > 0]
    active_pathways = [p for p in pathway_activations if (p.get("activation_score") or 0) > 0]
    citations = citations or []

    if abnormal:
        mapping_bits = [
            f"{item['biomarker_name']} was identified as {_status_phrase(item.get('status'))} relative to the reference range"
            for item in abnormal[:3]
        ]
        biomarker_detail = "; ".join(mapping_bits) + "."
    elif total:
        biomarker_detail = (
            f"{total} biomarker(s) were mapped to the catalog; none were outside reference range in this panel."
        )
    else:
        biomarker_detail = "No biomarkers were parsed from the uploaded file."

    if active_systems:
        system_names = ", ".join(s["system_name"] for s in active_systems[:3])
        system_detail = f"Signals mapped to {system_names}."
    else:
        system_detail = "Seven biological systems were screened; no abnormal pathway signal was detected."

    if active_pathways:
        pathway_names = ", ".join(p.get("pathway_name") or p.get("pathway_code", "") for p in active_pathways[:3])
        pathway_detail = f"Activated pathways included {pathway_names}."
    else:
        pathway_detail = "No internal pathways met activation thresholds for this panel."

    study_types: set[str] = set()
    for citation in citations:
        if citation.get("study_type"):
            study_types.add(str(citation["study_type"]).replace("_", " "))
    if study_types:
        grading_detail = "Studies were classified by design: " + ", ".join(sorted(study_types)[:5]) + "."
    else:
        grading_detail = "Retrieved studies were scored for design quality (meta-analysis, RCT, observational, etc.)."

    rec_count = len(recommendations)
    evidence_detail = (
        f"HerbaGraph searched its evidence graph and external literature sources for {rec_count} surfaced consideration(s)."
        if rec_count
        else "HerbaGraph searched its evidence graph and external literature sources; no considerations met routing thresholds."
    )

    steps = [
        {
            "step": 1,
            "title": "Lab Extraction",
            "description": "Uploaded lab values were parsed, OCR-normalized where needed, and converted to structured biomarker rows.",
        },
        {
            "step": 2,
            "title": "Biomarker Mapping",
            "description": biomarker_detail,
        },
        {
            "step": 3,
            "title": "Biological System Mapping",
            "description": f"{system_detail} {pathway_detail}".strip(),
        },
        {
            "step": 4,
            "title": "Evidence Retrieval",
            "description": evidence_detail,
        },
        {
            "step": 5,
            "title": "Evidence Grading",
            "description": grading_detail,
        },
        {
            "step": 6,
            "title": "Safety Review",
            "description": "Potential safety flags, contraindications, and medication context were checked against the safety knowledge graph.",
        },
        {
            "step": 7,
            "title": "Evidence Passport",
            "description": (
                "Each surfaced consideration received an Evidence Passport with strength, limitations, applicable population, and research gaps."
                if rec_count
                else "Evidence Passport cards are generated when evidence-backed considerations are surfaced."
            ),
        },
    ]

    return {
        "heading": "How This Report Was Generated",
        "subheading": "Platform methodology: transparent workflow from labs to evidence summaries",
        "steps": steps,
        "ties_together": [
            "Report Confidence",
            "Biological Reasoning Summary",
            "Evidence Passport",
            "Differential Biological Explanations",
            "Evidence Gaps",
        ],
    }
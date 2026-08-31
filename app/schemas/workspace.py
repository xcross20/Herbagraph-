import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AnalysisSessionStatus, AnalysisType, LabReportStatus


class DashboardPatientSummary(BaseModel):
    id: uuid.UUID
    display_name: str
    latest_report_id: uuid.UUID | None = None
    latest_report_confidence: float | None = None
    lab_report_count: int = 0
    analysis_session_count: int = 0


class DashboardReportSummary(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID | None = None
    patient_display_name: str | None = None
    title: str
    overall_confidence: float
    created_at: datetime
    analysis_session_id: uuid.UUID | None = None


class DashboardLabSummary(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID | None = None
    original_filename: str
    status: LabReportStatus
    latest_report_id: uuid.UUID | None = None
    created_at: datetime


class DashboardSessionSummary(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID | None = None
    title: str
    status: AnalysisSessionStatus
    analysis_type: AnalysisType
    latest_report_id: uuid.UUID | None = None
    report_confidence: float | None = None
    created_at: datetime


class WorkspaceDashboardRead(BaseModel):
    user_email: str
    user_full_name: str | None = None
    patients: list[DashboardPatientSummary]
    recent_reports: list[DashboardReportSummary]
    recent_labs: list[DashboardLabSummary]
    recent_sessions: list[DashboardSessionSummary]
    feature_flags: dict[str, bool] = {}


class PatientOverviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    date_of_birth: str | None = None
    age: int | None = None
    biological_sex: str | None = None
    notes: str | None = None
    created_at: datetime
    latest_report_id: uuid.UUID | None = None
    latest_report_confidence: float | None = None
    top_priorities: list[str] = []
    recent_abnormal_biomarkers: list[dict] = []
    lab_reports: list[DashboardLabSummary] = []
    analysis_sessions: list[DashboardSessionSummary] = []
    context_summary: dict[str, list[str]] = {}


# ── Case Overview (PR-1: My Case projection) ─────────────────────────────────


class CaseOverviewFinding(BaseModel):
    """A single finding in the CaseOverview, with provenance attached."""

    kind: str
    name: str
    value: str | None = None
    status: str | None = None
    source: str | None = None
    provenance: str  # 'reported' | 'verified' | 'inferred'
    why_this_is_here: str | None = None


class CaseOverviewConcern(BaseModel):
    """A cluster of findings sharing a concern."""

    label: str
    findings: list[CaseOverviewFinding]
    status: str  # 'open' | 'addressed' | 'resolved' | 'unknown'


class CaseOverviewBranch(BaseModel):
    """An open investigation branch."""

    branch: str
    label: str
    status: str  # 'open' | 'closed' | 'superseded'
    tests_conducted: list[str] = []


class CaseOverviewGap(BaseModel):
    """An evidence gap within the Case."""

    concept: str
    severity: str  # 'critical' | 'significant' | 'minor'


class CaseOverviewCoverageExplanation(BaseModel):
    """A human-readable coverage explanation for a branch."""

    branch: str
    relation: str  # e.g. 'DIRECTLY_ASSESSES', 'PARTIALLY_ASSESSES', 'DOES_NOT_DIRECTLY_ASSESS'
    test_concepts: list[str] = []
    message: str


class CaseOverviewDataCompleteness(BaseModel):
    """Coverage and completeness signals for the Case."""

    investigation_coverage_percent: int
    total_findings: int
    total_hypotheses: int
    open_branches: int
    unresolved_gaps: int


class CaseOverview(BaseModel):
    """Read-only coherent projection of the canonical Discovery Case.

    This is the data contract exposed by My Case (Investigate → My Case).
    It is assembled from the existing canonical Case read model and does
    NOT introduce a parallel truth store.

    Atomic Case rule: every section refers to the same coherent Case version
    identified by snapshot_id / case_version. If coherence cannot be
    guaranteed, the service raises ValueError so the API can surface a
    stale/reload state.
    """

    model_config = ConfigDict(from_attributes=True)

    # Identity
    case_id: uuid.UUID
    case_version: str | None  # from turn_state.control_json.case_version
    snapshot_id: str | None  # from turn_state.control_json.snapshot_id
    generated_at: datetime

    # Content sections
    presenting_concern: str
    status: str
    concerns: list[CaseOverviewConcern] = []
    current_findings: list[CaseOverviewFinding] = []
    prior_workup: list[dict] = []  # [{name, value, verification, provenance}]
    open_branches: list[CaseOverviewBranch] = []
    evidence_gaps: list[CaseOverviewGap] = []
    contradictions: list[str] = []
    coverage_explanations: list[CaseOverviewCoverageExplanation] = []
    next_best_action: dict | None = None  # from action_plan
    what_changed: list[str] = []  # from turn_state.what_changed

    # Completeness signals
    data_completeness: CaseOverviewDataCompleteness
    unresolved_count: int  # gaps + open branches + contradictions

    # Metadata
    permissions: dict  # {can_investigate, can_export, can_monitor}
    feature_flags: dict[str, bool]
from __future__ import annotations

import hashlib
import json
import os
import time
import base64
import httpx
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator
from .catalog import ACME_PROJECT_ID, ACME_RELEASE_ID, CUSTOMER_PROJECT_ID, CUSTOMER_RELEASE_ID, ProjectCatalog
from .agents import AgentId, agent_catalog, build_plan, get_agent
from .domain import BugChangeAssessment, EvidenceRelationship, calculate_readiness
from .file_inspector import inspect_file
from .providers import MockLLMProvider as ContractMockLLMProvider, OpenAIProvider, OpenRouterProvider
from .persistence import PostgresRepository
from .auth import CurrentUser, current_user, require_role, set_membership_validator
from .storage import LocalStorageProvider, S3StorageProvider
from .jobs import InlineJobRunner
from .agent_runtime import AgentApproval, AgentCheckpoint, AgentPolicy, AgentRunRecord, AgentStep, ToolRegistry, default_policy
from .security import DataClassification, PrivacyPolicy, classify_text, redact_sensitive
from .qa_explorer import QAExplorer
from .email_provider import build_email_provider

EvidenceState = Literal["demonstrated", "partially_demonstrated", "not_demonstrated", "inconclusive", "manual_review_required"]
ChangeState = Literal["proposed", "approved", "rejected", "incorporated"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Criterion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    text: str
    type: Literal["exact", "semantic", "threshold", "rubric", "dataset", "human"] = "semantic"
    automated: bool = True


class Requirement(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    human_id: str
    title: str
    description: str
    category: str
    priority: Literal["high", "medium", "low"] = "medium"
    status: EvidenceState = "manual_review_required"
    confidence: float = 0.94
    source: str = "Customer Operations Portal SOW"
    criteria: list[Criterion] = Field(default_factory=list)


class Evidence(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    requirement_id: UUID
    state: EvidenceState
    summary: str
    steps: list[str]
    artifact: str
    duration_ms: int = 1840
    model: str = "mock-judge-v1"
    run_id: str = "run_demo_001"
    created_at: str = Field(default_factory=now)
    sha256: str = ""


class ChangeRequest(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    original: str
    proposed: str
    classification: Literal["clarification", "possible_scope_change", "duplicate", "contradiction", "ambiguous"]
    status: ChangeState = "proposed"
    impact: str = "Medium"


class RunRequest(BaseModel):
    requirement_ids: list[str] = Field(default_factory=list)
    target_url: str = "https://demo.customer-portal.local"


class ReviewRequest(BaseModel):
    decision: Literal["accepted", "rejected", "revision_requested"]
    comment: str = ""
    guest_session: Optional[str] = None


class ReviewOtpRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)


class ReviewOtpVerification(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    code: str = Field(min_length=6, max_length=6)


class ScopeVersionRequest(BaseModel):
    source: str
    summary: str
    change_request_id: Optional[str] = None


class FileInspectionRequest(BaseModel):
    filename: str
    content_base64: str
    expected_columns: list[str] = Field(default_factory=list)
    expected_row_count: Optional[int] = None


class BugChangeRequest(BaseModel):
    report: str
    requirement_ids: list[UUID] = Field(default_factory=list)


class AcceptanceDecisionRequest(BaseModel):
    decision: Literal["accepted", "rejected", "revision_requested"]
    comment: str = ""


class ReleaseStatusRequest(BaseModel):
    status: Literal["in_signoff", "ready", "on_hold", "accepted"]


class HumanEvidenceRequest(BaseModel):
    requirement_id: UUID
    kind: Literal["screenshot", "video", "document", "link", "comment", "manual_test_result"]
    description: str
    source: str


class AITaskRequest(BaseModel):
    task: Literal["extract_scope", "analyze_requirement", "generate_acceptance_criteria", "classify_change", "classify_bug_or_change", "plan_verification", "analyze_observation", "judge_result", "summarize_delivery"]
    context: dict = Field(default_factory=dict)
    classification: DataClassification = DataClassification.CONFIDENTIAL
    consent: bool = False
    redact_pii: bool = True
    document_id: Optional[str] = None
    provider_route: Optional[str] = None

    @field_validator("classification", mode="before")
    @classmethod
    def parse_classification(cls, value: Any) -> DataClassification:
        if isinstance(value, str):
            return DataClassification[value.upper()]
        return value


class AgentRunRequest(BaseModel):
    agent_id: AgentId
    input: str = "Review the active delivery context."
    requirement_id: Optional[str] = None
    classification: DataClassification = DataClassification.CONFIDENTIAL
    consent: bool = False
    redact_pii: bool = True
    target_url: str = "http://localhost:3000/dashboard"
    routes: list[str] = Field(default_factory=list)
    document_id: Optional[str] = None
    provider_route: Optional[str] = None

    @field_validator("classification", mode="before")
    @classmethod
    def parse_classification(cls, value: Any) -> DataClassification:
        if isinstance(value, str):
            return DataClassification[value.upper()]
        return value


class AgentDispatchRequest(BaseModel):
    input: str
    requirement_id: Optional[str] = None
    classification: DataClassification = DataClassification.CONFIDENTIAL
    consent: bool = False
    redact_pii: bool = True
    target_url: str = "http://localhost:3000/dashboard"
    routes: list[str] = Field(default_factory=list)
    document_id: Optional[str] = None
    provider_route: Optional[str] = None

    @field_validator("classification", mode="before")
    @classmethod
    def parse_classification(cls, value: Any) -> DataClassification:
        if isinstance(value, str):
            return DataClassification[value.upper()]
        return value


class IntelligenceQuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    requirement_id: Optional[str] = None
    classification: DataClassification = DataClassification.CONFIDENTIAL
    consent: bool = False
    redact_pii: bool = True
    document_id: Optional[str] = None
    provider_route: Optional[str] = None

    @field_validator("classification", mode="before")
    @classmethod
    def parse_classification(cls, value: Any) -> DataClassification:
        if isinstance(value, str):
            return DataClassification[value.upper()]
        return value


class AgentRunResponse(BaseModel):
    id: str
    project_id: str
    agent: dict[str, Any]
    status: Literal["completed", "failed", "requires_approval"]
    result: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    provider: str
    model: str
    proposal_id: Optional[str] = None
    requires_approval: bool = False
    current_step: int = 0
    max_steps: int = 12
    checkpoint_ids: list[str] = Field(default_factory=list)
    approval_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now)


class AgentApprovalDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str = ""


class AgentPolicyUpdateRequest(BaseModel):
    mode: Literal["supervised", "balanced", "max_autonomy"] = "max_autonomy"
    blocked_tools: set[str] = Field(default_factory=set)
    max_steps: int = Field(default=12, ge=1, le=50)
    max_retries: int = Field(default=2, ge=0, le=5)
    redact_pii: bool = True
    allow_external_models: bool = False


class SendAgentAlertRequest(BaseModel):
    to: str = Field(min_length=3, max_length=320)
    action_url: str = "http://localhost:3000/dashboard"


class AIConsentRequest(BaseModel):
    document_id: str = Field(min_length=3, max_length=240)
    provider: str = Field(min_length=2, max_length=80)
    model_or_route: str = Field(min_length=2, max_length=160)
    classification: DataClassification = DataClassification.CONFIDENTIAL
    purpose: str = Field(min_length=3, max_length=240)
    expires_in_days: int = Field(default=30, ge=1, le=365)

    @field_validator("classification", mode="before")
    @classmethod
    def parse_classification(cls, value: Any) -> DataClassification:
        if isinstance(value, str):
            return DataClassification[value.upper()]
        return value


class AIProposal(BaseModel):
    id: str = Field(default_factory=lambda: f"proposal_{uuid4().hex[:12]}")
    project_id: str
    task: str
    status: Literal["draft", "approved", "rejected"] = "draft"
    result: dict
    provider: str
    model: str
    prompt_version: str = "sda-v1"
    created_at: str = Field(default_factory=now)


class DemoStore:
    def __init__(self) -> None:
        self.project = {"id": "project_demo", "name": "Customer Operations Portal v1", "client": "Northstar Logistics", "baseline": "Scope v1 · approved 14 Aug 2026", "release": "Release 1.0 · pending acceptance"}
        titles = [
            ("Customer login", "Users can sign in with email and password.", "Authentication", "high"),
            ("Role-based access", "Operators and managers see the correct navigation.", "Security", "high"),
            ("Operations dashboard", "The dashboard shows open orders and attention items.", "Core workflow", "high"),
            ("Order search", "Users can search orders by customer, status and date.", "Core workflow", "medium"),
            ("Order detail", "Users can inspect the complete order history.", "Core workflow", "high"),
            ("CSV export", "Managers can export filtered order data.", "Reporting", "medium"),
            ("Email alerts", "Managers receive alerts for overdue orders.", "Notifications", "medium"),
            ("Audit history", "Every status change is visible in an audit timeline.", "Compliance", "high"),
            ("Responsive layout", "Core workflows work on tablet widths.", "Non-functional", "medium"),
            ("Performance budget", "Dashboard becomes interactive within two seconds.", "Non-functional", "medium"),
            ("Bulk status update", "Managers can update multiple orders at once.", "Core workflow", "low"),
            ("Help centre link", "Users can reach support documentation from the app.", "Support", "low"),
        ]
        self.requirements: list[Requirement] = []
        for index, (title, description, category, priority) in enumerate(titles, 1):
            req = Requirement(human_id=f"REQ-{index:03d}", title=title, description=description, category=category, priority=priority) # type: ignore[arg-type]
            req.criteria = [Criterion(**item) for item in ContractMockLLMProvider().generate_criteria(req.model_dump())]
            req.status = "not_demonstrated" if index == 10 else ("partially_demonstrated" if index == 7 else "demonstrated")
            self.requirements.append(req)
        self.evidence: list[Evidence] = [Evidence(requirement_id=self.requirements[0].id, state="demonstrated", summary="Login completed and dashboard loaded with the expected account context.", steps=["Open /login", "Fill email and password", "Submit form", "Verify dashboard heading"], artifact="login-success.png", sha256=hashlib.sha256(b"login-success").hexdigest())]
        self.changes = [ChangeRequest(title="Add warehouse manager role", original="Two roles: operator and manager.", proposed="Warehouse managers need a separate view with bulk actions.", classification="possible_scope_change", impact="High"), ChangeRequest(title="Add export timestamp", original="CSV export includes filtered order data.", proposed="Add timezone-aware generated-at timestamp to exports.", classification="clarification", status="approved", impact="Low")]
        self.reviews: list[dict] = []
        self.scope_versions: list[dict] = [{"version": "v1", "status": "approved", "source": "Customer Operations Portal SOW", "summary": "Approved baseline with 12 requirements.", "created_at": "2026-08-14T10:00:00Z", "created_by": "demo.owner"}]
        self.relationships: list[EvidenceRelationship] = [EvidenceRelationship(source_type="scope_version", source_id="v1", target_type="requirement", target_id=str(req.id), relationship="contains") for req in self.requirements]
        self.human_evidence: list[dict] = []
        self.acceptance: list[dict] = [{"requirement_id": str(req.id), "decision": "accepted" if index <= 8 else "pending", "comment": ""} for index, req in enumerate(self.requirements, 1)]
        self.comments: list[dict] = [{"id": "comment_001", "requirement_id": str(self.requirements[6].id), "author": "client.reviewer", "text": "Please confirm the delivery timing for email alerts.", "resolved": False}]
        self.audit_events: list[dict] = []
        self.llm_runs: list[dict] = []
        self.ai_proposals: dict[str, AIProposal] = {}
        # These collections are the mock adapter for the durable agent tables.
        # The API shape is deliberately identical to the PostgreSQL records.
        self.agent_runs: dict[str, AgentRunRecord] = {}
        self.agent_steps: dict[str, AgentStep] = {}
        self.agent_checkpoints: dict[str, AgentCheckpoint] = {}
        self.agent_approvals: dict[str, AgentApproval] = {}
        self.agent_policies: dict[str, AgentPolicy] = {}
        self.email_deliveries: list[dict[str, Any]] = []
        self.ai_consents: dict[str, dict[str, Any]] = {}
        self.review_challenges: dict[str, dict[str, Any]] = {}
        self.review_sessions: dict[str, dict[str, Any]] = {}
        self.document_records: dict[str, dict[str, Any]] = {}


store = DemoStore()
catalog = ProjectCatalog(store)
storage = LocalStorageProvider() if os.getenv("MOCK_MODE", "true").lower() == "true" else S3StorageProvider()
job_runner = InlineJobRunner()
privacy_policy = PrivacyPolicy()
tool_registry = ToolRegistry()
qa_explorer = QAExplorer()
email_provider = build_email_provider(store.email_deliveries)
agent_repository: Any = None
requirement_overrides: dict[tuple[str, str], dict] = {}
change_overrides: dict[tuple[str, str], dict] = {}
release_status_overrides: dict[tuple[str, str], str] = {}
app = FastAPI(title="Signoff API", version="0.1.0", description="Signoff software delivery assurance API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers_and_api_guard(request: Request, call_next):
    path = request.url.path
    public_api = path.startswith("/api/v1/review/") or path.startswith("/api/v1/evidence/")
    production = os.getenv("MOCK_MODE", "true").lower() != "true"
    authorization = request.headers.get("authorization", "")
    if production and path.startswith("/api/v1/") and not public_api and request.method != "OPTIONS" and not authorization.lower().startswith("bearer "):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    # Resolve project URLs at the HTTP boundary as well as inside handlers.
    # This prevents a handler that accidentally uses a demo default from
    # disclosing another tenant's project projection.
    if production and path.startswith("/api/v1/projects/") and not public_api and request.method != "OPTIONS":
        try:
            user = current_user(authorization)
            project_id = path.split("/", 5)[4]
            if not catalog.get_project(project_id, user.organization_id):
                return JSONResponse(status_code=404, content={"detail": "Project not found"})
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https" or os.getenv("MOCK_MODE", "true").lower() != "true":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def project_or_404(project_id: str) -> dict:
    project = catalog.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _review_record(token: str) -> dict[str, Any]:
    """Resolve server-side review metadata without persisting raw guest tokens."""
    configured_demo = os.getenv("SIGNOFF_REVIEW_TOKEN_DEMO", "demo-review-token" if os.getenv("MOCK_MODE", "true").lower() == "true" else "")
    configured_acme = os.getenv("SIGNOFF_REVIEW_TOKEN_ACME", "acme-review-token" if os.getenv("MOCK_MODE", "true").lower() == "true" else "")
    if configured_demo and secrets.compare_digest(token, configured_demo):
        return {"project_id": CUSTOMER_PROJECT_ID, "release_id": CUSTOMER_RELEASE_ID, "email": "client@northstar.example"}
    if configured_acme and secrets.compare_digest(token, configured_acme):
        return {"project_id": ACME_PROJECT_ID, "release_id": ACME_RELEASE_ID, "email": "reviewer@acme.example"}
    raise HTTPException(404, "Review link not found or expired")


def _guest_session_valid(token: str, session_token: Optional[str]) -> bool:
    if os.getenv("MOCK_MODE", "true").lower() == "true":
        return True
    if not session_token:
        return False
    digest = hashlib.sha256(session_token.encode()).hexdigest()
    record = store.review_sessions.get(digest)
    if not record or record["token_hash"] != hashlib.sha256(token.encode()).hexdigest():
        return False
    return datetime.fromisoformat(record["expires_at"]) > datetime.now(timezone.utc)


def release_id_for(project_id: str) -> str:
    return ACME_RELEASE_ID if project_id == ACME_PROJECT_ID else CUSTOMER_RELEASE_ID


def canonical_requirements(project_id: str) -> list[Requirement]:
    project_or_404(project_id)
    if project_id == CUSTOMER_PROJECT_ID:
        return store.requirements
    raw_items = getattr(catalog, "requirements", lambda _project_id: [])(project_id)
    return [Requirement.model_validate({**item, **requirement_overrides.get((project_id, item["human_id"]), {})}) for item in raw_items]


def canonical_changes(project_id: str) -> list[ChangeRequest]:
    project_or_404(project_id)
    if project_id == CUSTOMER_PROJECT_ID:
        return store.changes
    raw_items = getattr(catalog, "changes", lambda _project_id: [])(project_id)
    return [ChangeRequest.model_validate({**item, **change_overrides.get((project_id, str(item["id"])), {})}) for item in raw_items]


def canonical_scope_versions(project_id: str) -> list[dict]:
    project_or_404(project_id)
    if project_id == CUSTOMER_PROJECT_ID:
        return store.scope_versions
    return list(getattr(catalog, "scope_versions", lambda _project_id: [])(project_id))


def canonical_evidence(project_id: str) -> list[Evidence]:
    project_or_404(project_id)
    if project_id == CUSTOMER_PROJECT_ID:
        return store.evidence
    projection = catalog.dashboard(project_id, release_id_for(project_id)) or {}
    requirements = {item.human_id: item for item in canonical_requirements(project_id)}
    state_by_verification = {"passed": "demonstrated", "in_progress": "partially_demonstrated", "not_started": "not_demonstrated"}
    evidence: list[Evidence] = []
    for row in projection.get("requirements", []):
        requirement = requirements.get(row["id"])
        if requirement is None:
            continue
        artifact = f"{project_id}-{row['id'].lower()}-verification.png"
        content = f"SDA demo evidence for {project_id} {row['id']}".encode()
        storage.put_object(artifact, content, "image/png")
        evidence.append(Evidence(id=uuid5(NAMESPACE_URL, f"sda:evidence:{project_id}:{row['id']}"), requirement_id=requirement.id, state=state_by_verification.get(row.get("verification"), "inconclusive"), summary="Verification evidence linked to the active release projection.", steps=["Create isolated verification context", "Execute acceptance criteria", "Capture observation"], artifact=artifact, model="reference-judge-v1", run_id=f"run_{project_id}_reference", sha256=storage.compute_hash(content)))
    return evidence


def canonical_acceptance(project_id: str) -> list[dict]:
    project_or_404(project_id)
    if project_id == CUSTOMER_PROJECT_ID:
        return store.acceptance
    return list(getattr(catalog, "acceptance", lambda _project_id: [])(project_id))


def canonical_attention(project_id: str) -> list[dict]:
    project_or_404(project_id)
    if project_id == CUSTOMER_PROJECT_ID:
        return [{"severity": "critical", "title": "Performance budget is not demonstrated", "source": "Verification"}, {"severity": "warning", "title": "Warehouse manager role is an unapproved scope change", "source": "Change Radar"}, {"severity": "warning", "title": "Email alerts have unresolved client comments", "source": "Acceptance"}, {"severity": "info", "title": "8 requirements have been accepted", "source": "Client Portal"}]
    return list(getattr(catalog, "attention", lambda _project_id: [])(project_id))


@app.on_event("startup")
def configure_persistence() -> None:
    """Switch the same catalog contract to PostgreSQL outside mock mode."""
    global catalog, agent_repository
    if os.getenv("MOCK_MODE", "true").lower() == "true":
        return
    try:
        repository = PostgresRepository()
        repository.initialize(catalog)
        catalog = repository  # type: ignore[assignment]
        agent_repository = repository
        set_membership_validator(repository.membership_role)
    except Exception as exc:
        raise RuntimeError(f"SDA persistence could not start: {exc}") from exc


@app.get("/api/v1/projects")
def list_projects(user: CurrentUser = Depends(current_user)) -> dict:
    """Return the tenant-scoped projects available in the active workspace."""
    return {"items": catalog.list_projects(user.organization_id)}


@app.get("/api/v1/projects/{project_id}")
def get_project(project_id: str, user: CurrentUser = Depends(current_user)) -> dict:
    project = catalog.get_project(project_id, user.organization_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return {**project, "releases": catalog.list_releases(project_id, user.organization_id)}


@app.get("/api/v1/projects/{project_id}/releases")
def list_releases(project_id: str, user: CurrentUser = Depends(current_user)) -> dict:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    return {"items": catalog.list_releases(project_id, user.organization_id)}


@app.get("/api/v1/projects/{project_id}/releases/{release_id}/dashboard")
def project_release_dashboard(project_id: str, release_id: str, user: CurrentUser = Depends(current_user)) -> dict:
    projection = catalog.dashboard(project_id, release_id, user.organization_id)
    if projection is None:
        raise HTTPException(404, "Project or release not found")
    override = release_status_overrides.get((project_id, release_id))
    if override:
        projection["project"] = {**projection["project"], "status": override}
    return projection


@app.patch("/api/v1/projects/{project_id}/releases/{release_id}/status")
def update_release_status(
    project_id: str,
    release_id: str,
    payload: ReleaseStatusRequest,
    user: CurrentUser = Depends(current_user),
) -> dict:
    require_role(user, "owner", "admin", "member")
    if catalog.get_release(project_id, release_id, user.organization_id) is None:
        raise HTTPException(404, "Project or release not found")
    release_status_overrides[(project_id, release_id)] = payload.status
    audit_event(
        user,
        "release_status_updated",
        project_id=project_id,
        release_id=release_id,
        status=payload.status,
    )
    return {"project_id": project_id, "release_id": release_id, "status": payload.status}


@app.post("/api/v1/projects/{project_id}/releases/{release_id}/send-for-acceptance")
def send_release_for_acceptance(
    project_id: str,
    release_id: str,
    user: CurrentUser = Depends(current_user),
) -> dict:
    require_role(user, "owner", "admin", "member")
    if catalog.get_release(project_id, release_id, user.organization_id) is None:
        raise HTTPException(404, "Project or release not found")
    release_status_overrides[(project_id, release_id)] = "ready"
    audit_event(
        user,
        "release_sent_for_acceptance",
        project_id=project_id,
        release_id=release_id,
    )
    return {"project_id": project_id, "release_id": release_id, "status": "ready"}


@app.get("/api/v1/reference-dashboard")
def reference_dashboard() -> dict:
    """Compatibility alias for older clients; the canonical route is project/release scoped."""
    projection = catalog.dashboard(ACME_PROJECT_ID, ACME_RELEASE_ID)
    assert projection is not None
    return projection


def llm_provider() -> Any:
    if os.getenv("MOCK_MODE", "true").lower() == "true":
        return ContractMockLLMProvider()
    if os.getenv("AI_PROVIDER", "openai").lower() == "openrouter":
        return OpenRouterProvider()
    return OpenAIProvider()


def audit_event(user: CurrentUser, event_type: str, **payload: Any) -> None:
    """Store metadata-only audit records; document content never belongs here."""
    store.audit_events.append({"organization_id": user.organization_id, "actor_id": user.id, "event": event_type, "created_at": now(), **payload})


def _consent_key(project_id: str, document_id: str, provider: str, model_or_route: str) -> str:
    return f"{project_id}:{document_id}:{provider.lower()}:{model_or_route}"


def _valid_document_consent(project_id: str, document_id: str | None, user: CurrentUser, provider: Any, requested_classification: DataClassification, requested_route: str | None = None) -> bool:
    if os.getenv("MOCK_MODE", "true").lower() == "true":
        return True
    if not document_id:
        return False
    provider_name = getattr(provider, "provider_name", provider.__class__.__name__).lower().replace("provider", "")
    model = requested_route or getattr(provider, "model", "unknown")
    record = store.ai_consents.get(_consent_key(project_id, document_id, provider_name, model))
    if record is None and agent_repository is not None and hasattr(agent_repository, "list_ai_consents"):
        record = next((item for item in agent_repository.list_ai_consents(project_id, user.organization_id) if item["document_id"] == document_id and item["provider"] == provider_name and item["model_or_route"] == model), None)
    if not record or record.get("organization_id") != user.organization_id or record.get("revoked_at"):
        return False
    if DataClassification[record.get("classification", "CONFIDENTIAL")] < requested_classification:
        return False
    return record.get("expires_at", "") > now()


def _assert_ai_consent(project_id: str, document_id: str | None, user: CurrentUser, provider: Any, classification: DataClassification, consent: bool, provider_route: str | None = None) -> bool:
    granted = consent or _valid_document_consent(project_id, document_id, user, provider, classification, provider_route)
    if os.getenv("MOCK_MODE", "true").lower() != "true" and classification >= DataClassification.CONFIDENTIAL and not granted:
        raise HTTPException(428, "A valid consent for this document and AI route is required")
    privacy_policy.assert_allowed(provider, classification, granted)
    return granted


def persist_agent_snapshot(run: AgentRunRecord) -> None:
    """Write the same run snapshot to PostgreSQL when production mode is active."""
    if agent_repository is None:
        return
    agent_repository.save_agent_state(
        run,
        [item for item in store.agent_steps.values() if item.id in run.step_ids],
        [item for item in store.agent_checkpoints.values() if item.id in run.checkpoint_ids],
        [item for item in store.agent_approvals.values() if item.id in run.approval_ids],
    )


def maybe_notify_agent_run(run: AgentRunRecord, agent_name: str, user: CurrentUser) -> None:
    """Send opt-in metadata-only alerts; disabled by default in every environment."""
    if os.getenv("SIGNOFF_AGENT_ALERTS_ENABLED", "false").lower() != "true":
        return
    try:
        delivery = email_provider.send_agent_alert(to=user.email, agent_name=agent_name, status=run.status, run_id=run.id, project_id=run.project_id, action_url=os.getenv("SIGNOFF_APP_URL", "http://localhost:3000/dashboard"))
        audit_event(user, "agent_alert_sent", project_id=run.project_id, run_id=run.id, delivery_id=delivery["id"], provider=delivery["provider"])
    except Exception as exc:  # notification failure must not fail the agent run
        audit_event(user, "agent_alert_failed", project_id=run.project_id, run_id=run.id, error=str(exc)[:240])


def _redact_agent_value(value: Any, redact_pii: bool) -> Any:
    if isinstance(value, str):
        return redact_sensitive(value, redact_pii=redact_pii)[0]
    if isinstance(value, dict):
        return {key: _redact_agent_value(item, redact_pii) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_agent_value(item, redact_pii) for item in value]
    return value


def _agent_requirement(project_id: str, requirement_id: str | None) -> Requirement:
    requirements = canonical_requirements(project_id)
    if not requirement_id:
        return requirements[0]
    for requirement in requirements:
        if requirement.human_id == requirement_id or str(requirement.id) == requirement_id:
            return requirement
    raise HTTPException(404, "Requirement not found")


@app.get("/api/v1/agents")
def list_agents(user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    """Return the least-privilege contextual agents available to this workspace."""
    policy = store.agent_policies.setdefault(user.organization_id, default_policy(user.organization_id))
    return {"items": agent_catalog(), "tools": tool_registry.list(), "policy": {**policy.model_dump(), "runtime": "mock" if os.getenv("MOCK_MODE", "true").lower() == "true" else "external"}}


@app.get("/api/v1/agent-tools")
def list_agent_tools(user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    return {"items": tool_registry.list()}


def select_agent_for_input(user_input: str) -> AgentId:
    """Deterministic supervisor fallback; a model planner can replace this later."""
    text = user_input.lower()
    if any(word in text for word in ("url", "browser", "qa", "test", "probar", "error", "funcionalidad")):
        return "qa-explorer"
    if any(word in text for word in ("contrato", "sow", "acuerdo", "baseline", "alcance")):
        return "agreement-analyst"
    if any(word in text for word in ("criterio", "requirement", "requisito")):
        return "requirements-coach"
    if any(word in text for word in ("cambio", "change", "scope creep")):
        return "change-radar"
    if any(word in text for word in ("evidencia", "evidence", "artefact")):
        return "evidence-curator"
    if any(word in text for word in ("aceptación", "acceptance", "cliente", "sign-off")):
        return "acceptance-assistant"
    return "delivery-analyst"


@app.post("/api/v1/projects/{project_id}/agents/dispatch", response_model=AgentRunResponse)
def dispatch_agent(project_id: str, payload: AgentDispatchRequest, user: CurrentUser = Depends(current_user)) -> AgentRunResponse:
    agent_id = select_agent_for_input(payload.input)
    audit_event(user, "ai_agent_dispatched", project_id=project_id, agent_id=agent_id)
    return run_agent(project_id, AgentRunRequest(agent_id=agent_id, input=payload.input, requirement_id=payload.requirement_id, classification=payload.classification, consent=payload.consent, redact_pii=payload.redact_pii, target_url=payload.target_url, routes=payload.routes, document_id=payload.document_id, provider_route=payload.provider_route), user)


@app.post("/api/v1/projects/{project_id}/intelligence/ask")
def ask_project_intelligence(project_id: str, payload: IntelligenceQuestionRequest, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    provider = llm_provider()
    _assert_ai_consent(project_id, payload.document_id, user, provider, payload.classification, payload.consent, payload.provider_route)
    question = _redact_agent_value(payload.question, payload.redact_pii and privacy_policy.redact_before_ai)
    requirements = canonical_requirements(project_id)
    readiness = calculate_readiness(
        [item.model_dump() for item in requirements],
        [item.model_dump() for item in canonical_evidence(project_id)],
        [item.model_dump() for item in canonical_changes(project_id)],
        0,
        sum(item.get("decision") == "accepted" for item in canonical_acceptance(project_id)),
    ).model_dump()
    context = {
        "question": question,
        "readiness": readiness,
        "requirements": [{"id": item.human_id, "title": item.title, "status": item.status} for item in requirements],
        "changes": canonical_changes(project_id),
        "attention": canonical_attention(project_id),
    }
    result = provider.summarize_delivery(context)
    citations = [{"type": "requirement", "id": item.human_id, "title": item.title} for item in requirements[:5]]
    audit_event(user, "project_intelligence_question_answered", project_id=project_id, question_length=len(str(question)), citations=len(citations), provider=provider.__class__.__name__)
    return {"answer": result, "grounded": True, "confidence": 0.86 if provider.__class__.__name__ == "MockLLMProvider" else 0.78, "citations": citations, "provider": provider.__class__.__name__, "model": provider.model}


@app.post("/api/v1/projects/{project_id}/agents/run", response_model=AgentRunResponse)
def run_agent(project_id: str, payload: AgentRunRequest, user: CurrentUser = Depends(current_user)) -> AgentRunResponse:
    """Execute a bounded agent plan with explicit, auditable tools.

    Agents currently prepare evidence and proposals; they do not mutate scope,
    requirements or acceptance decisions without a separate approval action.
    """
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    agent = get_agent(payload.agent_id)
    provider = llm_provider()
    _assert_ai_consent(project_id, payload.document_id, user, provider, payload.classification, payload.consent, payload.provider_route)
    policy = store.agent_policies.setdefault(user.organization_id, default_policy(user.organization_id))
    started = time.perf_counter()
    safe_input = _redact_agent_value(payload.input, payload.redact_pii and privacy_policy.redact_before_ai)
    plan = build_plan(payload.agent_id, str(safe_input), payload.requirement_id)
    if len(plan) > policy.max_steps:
        raise HTTPException(400, "Agent plan exceeds the organization step limit")
    run = AgentRunRecord(
        organization_id=user.organization_id,
        project_id=project_id,
        agent_id=payload.agent_id,
        status="running",
        input=str(safe_input),
        classification=payload.classification.name,
        provider=provider.__class__.__name__,
        model=provider.model,
        max_steps=policy.max_steps,
    )
    store.agent_runs[run.id] = run
    tool_calls: list[dict[str, Any]] = []
    outputs: dict[str, Any] = {}
    proposal_id: str | None = None
    try:
        for ordinal, step in enumerate(plan, 1):
            tool_name = step["tool"]
            try:
                manifest, needs_approval = tool_registry.authorize(tool_name, agent.tools, policy)
            except (KeyError, PermissionError) as exc:
                run.status = "failed"
                run.error = str(exc)
                run.updated_at = now()
                raise HTTPException(403, str(exc)) from exc
            if needs_approval and manifest.risk in {"write", "execute", "external", "critical"}:
                approval = AgentApproval(run_id=run.id, tool=tool_name, reason=f"{manifest.name} requires an explicit approval")
                store.agent_approvals[approval.id] = approval
                run.approval_ids.append(approval.id)
            tool_started = time.perf_counter()
            tool_input = step.get("input", {})
            step_record = AgentStep(ordinal=ordinal, tool=tool_name, input=tool_input, status="running")
            store.agent_steps[step_record.id] = step_record
            run.step_ids.append(step_record.id)
            run.current_step = ordinal
            if tool_name == "get_delivery_readiness":
                requirements = [item.model_dump() for item in canonical_requirements(project_id)]
                evidence = [item.model_dump() for item in canonical_evidence(project_id)]
                changes = [item.model_dump() for item in canonical_changes(project_id)]
                acceptance = canonical_acceptance(project_id)
                accepted = sum(item.get("decision") == "accepted" for item in acceptance)
                unresolved = len([item for item in store.comments if not item.get("resolved")]) if project_id == CUSTOMER_PROJECT_ID else 0
                outputs[tool_name] = calculate_readiness(requirements, evidence, changes, unresolved, accepted).model_dump()
            elif tool_name == "list_attention_items":
                outputs[tool_name] = canonical_attention(project_id)
            elif tool_name == "inspect_requirement":
                requirement = _agent_requirement(project_id, tool_input.get("requirement_id") or payload.requirement_id)
                outputs[tool_name] = requirement.model_dump()
            elif tool_name == "inspect_scope":
                outputs[tool_name] = {"versions": canonical_scope_versions(project_id), "active_version": canonical_scope_versions(project_id)[0] if canonical_scope_versions(project_id) else None}
            elif tool_name == "list_requirements":
                outputs[tool_name] = [{"human_id": item.human_id, "title": item.title, "status": item.status, "criteria": len(item.criteria)} for item in canonical_requirements(project_id)]
            elif tool_name == "list_evidence":
                outputs[tool_name] = [{"requirement_id": str(item.requirement_id), "state": item.state, "artifact": item.artifact, "run_id": item.run_id, "sha256": item.sha256} for item in canonical_evidence(project_id)]
            elif tool_name == "analyze_requirement":
                requirement = _agent_requirement(project_id, tool_input.get("requirement_id") or payload.requirement_id)
                outputs[tool_name] = provider.analyze_requirement(_redact_agent_value(requirement.model_dump(), payload.redact_pii))
            elif tool_name == "generate_acceptance_criteria":
                requirement = _agent_requirement(project_id, tool_input.get("requirement_id") or payload.requirement_id)
                outputs[tool_name] = {"criteria": provider.generate_acceptance_criteria(_redact_agent_value(requirement.model_dump(), payload.redact_pii)), "status": "draft"}
            elif tool_name == "plan_verification":
                requirement = _agent_requirement(project_id, tool_input.get("requirement_id") or payload.requirement_id)
                criterion = {"requirement_id": requirement.human_id, "text": requirement.criteria[0].text if requirement.criteria else requirement.description}
                outputs[tool_name] = provider.plan_verification(_redact_agent_value(criterion, payload.redact_pii))
            elif tool_name == "classify_change":
                request = str(tool_input.get("request") or safe_input)
                baseline = canonical_scope_versions(project_id)[0].get("version", "active baseline")
                outputs[tool_name] = provider.classify_change(baseline, request)
            elif tool_name == "summarize_delivery":
                readiness = outputs.get("get_delivery_readiness", {})
                attention = outputs.get("list_attention_items", [])
                outputs[tool_name] = provider.summarize_delivery({"question": safe_input, "readiness": readiness, "attention": attention})
            elif tool_name == "discover_routes":
                outputs[tool_name] = qa_explorer.discover(payload.target_url, max_routes=policy.max_steps)
            elif tool_name == "run_smoke_check":
                outputs[tool_name] = qa_explorer.smoke_check(payload.target_url, routes=payload.routes or None, max_steps=policy.max_steps)
                artifact_key = f"agent-runs/{run.id}/qa-observations.json"
                artifact_content = json.dumps(outputs[tool_name], ensure_ascii=False, sort_keys=True).encode()
                stored = storage.put_object(artifact_key, artifact_content, "application/json")
                outputs[tool_name]["evidence_artifact"] = artifact_key
                outputs[tool_name]["evidence_sha256"] = stored.get("sha256", storage.compute_hash(artifact_content))
            else:
                raise HTTPException(400, f"Unsupported agent tool: {tool_name}")
            step_record.output = outputs[tool_name]
            step_record.status = "completed"
            step_record.duration_ms = round((time.perf_counter() - tool_started) * 1000)
            checkpoint = AgentCheckpoint(run_id=run.id, ordinal=ordinal, state={"outputs": outputs, "current_tool": tool_name})
            store.agent_checkpoints[checkpoint.id] = checkpoint
            run.checkpoint_ids.append(checkpoint.id)
            persist_agent_snapshot(run)
            tool_calls.append({"tool": tool_name, "input": tool_input, "status": "completed", "duration_ms": round((time.perf_counter() - tool_started) * 1000)})
    except HTTPException:
        raise
    except RuntimeError as exc:
        run.status = "failed"
        run.error = str(exc)
        run.updated_at = now()
        raise HTTPException(503, str(exc)) from exc

    if payload.agent_id == "requirements-coach" and "generate_acceptance_criteria" in outputs:
        proposal = AIProposal(project_id=project_id, task="agent_generate_acceptance_criteria", result=outputs["generate_acceptance_criteria"], provider=provider.__class__.__name__, model=provider.model)
        store.ai_proposals[proposal.id] = proposal
        proposal_id = proposal.id

    run_id = f"agent_{uuid4().hex[:12]}"
    duration_ms = round((time.perf_counter() - started) * 1000)
    store.llm_runs.append({"id": f"llm_{uuid4().hex[:10]}", "project_id": project_id, "task": f"agent:{payload.agent_id}", "provider": provider.__class__.__name__, "model": provider.model, "prompt_version": "sda-agent-v1", "input_tokens": len(str(safe_input)) // 4, "output_tokens": len(str(outputs)) // 4, "estimated_cost": 0 if provider.__class__.__name__ == "MockLLMProvider" else 0.01, "duration_ms": duration_ms, "status": "completed", "created_at": now()})
    audit_event(user, "ai_agent_run_completed", project_id=project_id, agent_id=payload.agent_id, run_id=run_id, tools=[item["tool"] for item in tool_calls], proposal_id=proposal_id)
    run.status = "requires_approval" if proposal_id or run.approval_ids else "completed"
    run.result = outputs
    run.proposal_id = proposal_id
    run.updated_at = now()
    persist_agent_snapshot(run)
    maybe_notify_agent_run(run, agent.name, user)
    return AgentRunResponse(id=run.id, project_id=project_id, agent={"id": agent.id, "name": agent.name, "description": agent.description, "tools": list(agent.tools), "accent": agent.accent}, status=run.status, result=outputs, tool_calls=tool_calls, provider=provider.__class__.__name__, model=provider.model, proposal_id=proposal_id, requires_approval=bool(proposal_id or run.approval_ids), current_step=run.current_step, max_steps=run.max_steps, checkpoint_ids=run.checkpoint_ids, approval_ids=run.approval_ids)


def _agent_run_or_404(run_id: str, user: CurrentUser) -> AgentRunRecord:
    run = store.agent_runs.get(run_id)
    if run is None or run.organization_id != user.organization_id:
        raise HTTPException(404, "Agent run not found")
    if not catalog.get_project(run.project_id, user.organization_id):
        raise HTTPException(404, "Agent run not found")
    return run


@app.get("/api/v1/agent-policy")
def get_agent_policy(user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    policy = store.agent_policies.setdefault(user.organization_id, default_policy(user.organization_id))
    return policy.model_dump()


@app.patch("/api/v1/agent-policy")
def update_agent_policy(payload: AgentPolicyUpdateRequest, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "owner", "admin")
    policy = AgentPolicy(organization_id=user.organization_id, **payload.model_dump())
    store.agent_policies[user.organization_id] = policy
    audit_event(user, "agent_policy_updated", mode=policy.mode, blocked_tools=sorted(policy.blocked_tools), max_steps=policy.max_steps)
    return policy.model_dump()


@app.get("/api/v1/projects/{project_id}/agents/runs")
def list_agent_runs(project_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    runs = [run.model_dump() for run in store.agent_runs.values() if run.project_id == project_id and run.organization_id == user.organization_id]
    return {"items": sorted(runs, key=lambda item: item["created_at"], reverse=True)}


@app.get("/api/v1/agent-runs/{run_id}")
def get_agent_run(run_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    run = _agent_run_or_404(run_id, user)
    steps = [step.model_dump() for step in store.agent_steps.values() if step.id in run.step_ids]
    checkpoints = [checkpoint.model_dump() for checkpoint in store.agent_checkpoints.values() if checkpoint.id in run.checkpoint_ids]
    approvals = [approval.model_dump() for approval in store.agent_approvals.values() if approval.id in run.approval_ids]
    return {"run": run.model_dump(), "steps": steps, "checkpoints": checkpoints, "approvals": approvals}


@app.post("/api/v1/agent-runs/{run_id}/cancel")
def cancel_agent_run(run_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    run = _agent_run_or_404(run_id, user)
    if run.status in {"completed", "failed", "cancelled"}:
        raise HTTPException(409, "Agent run is already finished")
    run.status = "cancelled"
    run.updated_at = now()
    persist_agent_snapshot(run)
    audit_event(user, "ai_agent_run_cancelled", project_id=run.project_id, run_id=run.id)
    return run.model_dump()


@app.get("/api/v1/agent-runs/{run_id}/approvals")
def list_agent_approvals(run_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    run = _agent_run_or_404(run_id, user)
    return {"items": [approval.model_dump() for approval in store.agent_approvals.values() if approval.id in run.approval_ids]}


@app.post("/api/v1/agent-runs/{run_id}/email-alert")
def send_agent_email_alert(run_id: str, payload: SendAgentAlertRequest, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "owner", "admin")
    run = _agent_run_or_404(run_id, user)
    agent = get_agent(run.agent_id)
    try:
        delivery = email_provider.send_agent_alert(to=payload.to, agent_name=agent.name, status=run.status, run_id=run.id, project_id=run.project_id, action_url=payload.action_url)
    except (RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(503, f"Email delivery failed: {exc}") from exc
    audit_event(user, "agent_alert_sent", project_id=run.project_id, run_id=run.id, delivery_id=delivery["id"], provider=delivery["provider"])
    return {"delivery": delivery}


@app.post("/api/v1/agent-approvals/{approval_id}")
def decide_agent_approval(approval_id: str, payload: AgentApprovalDecisionRequest, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "owner", "admin", "member")
    approval = store.agent_approvals.get(approval_id)
    if approval is None:
        raise HTTPException(404, "Agent approval not found")
    run = _agent_run_or_404(approval.run_id, user)
    if approval.status != "pending":
        raise HTTPException(409, "Approval has already been decided")
    approval.status = payload.decision
    approval.comment = payload.comment
    approval.decided_at = now()
    approval.decided_by = user.id
    pending = [item for item in store.agent_approvals.values() if item.id in run.approval_ids and item.status == "pending"]
    rejected = [item for item in store.agent_approvals.values() if item.id in run.approval_ids and item.status == "rejected"]
    if rejected:
        run.status = "failed"
        run.error = "An approval was rejected"
    elif not pending:
        run.status = "completed" if not run.proposal_id else "requires_approval"
    run.updated_at = now()
    persist_agent_snapshot(run)
    audit_event(user, "ai_agent_approval_decided", project_id=run.project_id, run_id=run.id, approval_id=approval.id, decision=payload.decision)
    return {"approval": approval.model_dump(), "run": run.model_dump()}


@app.post("/api/v1/agent-runs/{run_id}/resume")
def resume_agent_run(run_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    run = _agent_run_or_404(run_id, user)
    if any(item.status == "pending" for item in store.agent_approvals.values() if item.id in run.approval_ids):
        raise HTTPException(409, "Resolve pending approvals before resuming")
    if run.status not in {"paused", "requires_approval"}:
        raise HTTPException(409, "Agent run cannot be resumed from its current state")
    run.status = "completed" if not run.error else run.status
    run.updated_at = now()
    persist_agent_snapshot(run)
    audit_event(user, "ai_agent_run_resumed", project_id=run.project_id, run_id=run.id)
    return run.model_dump()


@app.post("/api/v1/projects/{project_id}/ai/tasks", response_model=AIProposal)
def run_ai_task(project_id: str, payload: AITaskRequest, user: CurrentUser = Depends(current_user)) -> AIProposal:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    provider = llm_provider()
    _assert_ai_consent(project_id, payload.document_id, user, provider, payload.classification, payload.consent, payload.provider_route)
    started = time.perf_counter()
    task_context = dict(payload.context)
    redaction_categories: list[str] = []
    if payload.redact_pii and privacy_policy.redact_before_ai:
        for key in ("text", "baseline", "request", "report"):
            value = task_context.get(key)
            if isinstance(value, str):
                task_context[key], categories = redact_sensitive(value, redact_pii=True)
                redaction_categories.extend(categories)
    try:
        if payload.task == "extract_scope":
            result = provider.extract_scope(str(task_context.get("text", "")))
        elif payload.task == "analyze_requirement":
            result = provider.analyze_requirement(task_context)
        elif payload.task == "generate_acceptance_criteria":
            result = {"criteria": provider.generate_acceptance_criteria(task_context)}
        elif payload.task == "classify_change":
            result = provider.classify_change(str(task_context.get("baseline", "")), str(task_context.get("request", "")))
        elif payload.task == "classify_bug_or_change":
            result = provider.classify_bug_or_change(str(task_context.get("baseline", "")), str(task_context.get("report", "")))
        elif payload.task == "plan_verification":
            result = provider.plan_verification(task_context)
        elif payload.task == "analyze_observation":
            result = provider.analyze_observation(task_context)
        elif payload.task == "judge_result":
            result = provider.judge_result(task_context.get("observations", []))
        else:
            result = provider.summarize_delivery(task_context)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    duration_ms = round((time.perf_counter() - started) * 1000)
    proposal = AIProposal(project_id=project_id, task=payload.task, result=result, provider=provider.__class__.__name__, model=provider.model)
    store.ai_proposals[proposal.id] = proposal
    store.llm_runs.append({"id": f"llm_{uuid4().hex[:10]}", "project_id": project_id, "task": payload.task, "provider": proposal.provider, "model": proposal.model, "prompt_version": proposal.prompt_version, "input_tokens": len(str(task_context)) // 4, "output_tokens": len(str(result)) // 4, "estimated_cost": 0 if proposal.provider == "MockLLMProvider" else 0.01, "duration_ms": duration_ms, "status": "completed", "created_at": now()})
    audit_event(user, "ai_proposal_created", project_id=project_id, task=payload.task, proposal_id=proposal.id, classification=payload.classification.name, redactions=sorted(set(redaction_categories)))
    return proposal


@app.post("/api/v1/ai/proposals/{proposal_id}/approve", response_model=AIProposal)
def approve_ai_proposal(proposal_id: str, user: CurrentUser = Depends(current_user)) -> AIProposal:
    proposal = store.ai_proposals.get(proposal_id)
    if not proposal:
        raise HTTPException(404, "AI proposal not found")
    if not catalog.get_project(proposal.project_id, user.organization_id):
        raise HTTPException(404, "AI proposal not found")
    proposal.status = "approved"
    audit_event(user, "ai_proposal_approved", project_id=proposal.project_id, proposal_id=proposal_id)
    return proposal


@app.get("/api/v1/projects/{project_id}/ai/runs")
def ai_runs(project_id: str, user: CurrentUser = Depends(current_user)) -> list[dict]:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    return [item for item in store.llm_runs if item["project_id"] == project_id]


@app.get("/api/v1/projects/{project_id}/privacy-policy")
def project_privacy_policy(project_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    """Expose the effective policy without exposing credentials or provider secrets."""
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    return {
        "classification_default": DataClassification.CONFIDENTIAL.name,
        "allowed_providers": sorted(privacy_policy.allowed_providers),
        "max_external_classification": privacy_policy.max_external_classification.name,
        "requires_consent": privacy_policy.require_consent,
        "redaction_enabled": privacy_policy.redact_before_ai,
        "storage": "local-development" if isinstance(storage, LocalStorageProvider) else "s3-compatible",
    }


@app.get("/api/v1/projects/{project_id}/ai/consents")
def list_ai_consents(project_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    if agent_repository is not None and hasattr(agent_repository, "list_ai_consents"):
        return {"items": agent_repository.list_ai_consents(project_id, user.organization_id)}
    return {"items": [item for item in store.ai_consents.values() if item["project_id"] == project_id and item["organization_id"] == user.organization_id and not item.get("revoked_at")]}


@app.post("/api/v1/projects/{project_id}/ai/consents")
def grant_ai_consent(project_id: str, payload: AIConsentRequest, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "owner", "admin", "member")
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    if payload.classification < DataClassification.CONFIDENTIAL:
        raise HTTPException(422, "Document consent is only needed for confidential processing")
    provider = payload.provider.lower().replace("provider", "")
    record = {
        "id": f"consent_{secrets.token_urlsafe(12)}",
        "organization_id": user.organization_id,
        "project_id": project_id,
        "document_id": payload.document_id,
        "provider": provider,
        "model_or_route": payload.model_or_route,
        "classification": payload.classification.name,
        "purpose": payload.purpose,
        "granted_by": user.id,
        "granted_at": now(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)).isoformat(),
        "revoked_at": None,
    }
    store.ai_consents[_consent_key(project_id, payload.document_id, provider, payload.model_or_route)] = record
    if agent_repository is not None and hasattr(agent_repository, "save_ai_consent"):
        agent_repository.save_ai_consent(record)
    audit_event(user, "ai_document_consent_granted", project_id=project_id, document_id=payload.document_id, provider=provider, model_or_route=payload.model_or_route, classification=payload.classification.name)
    return record


@app.delete("/api/v1/projects/{project_id}/ai/consents/{document_id}")
def revoke_ai_consent(project_id: str, document_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "owner", "admin", "member")
    revoked = agent_repository.revoke_ai_consent(project_id, document_id, user.organization_id) if agent_repository is not None and hasattr(agent_repository, "revoke_ai_consent") else 0
    for item in store.ai_consents.values():
        if item["project_id"] == project_id and item["document_id"] == document_id and item["organization_id"] == user.organization_id and not item.get("revoked_at"):
            item["revoked_at"] = now()
            revoked += 1
    if not revoked:
        raise HTTPException(404, "AI consent not found")
    audit_event(user, "ai_document_consent_revoked", project_id=project_id, document_id=document_id, revoked=revoked)
    return {"status": "revoked", "document_id": document_id, "revoked": revoked}


@app.get("/api/v1/projects/{project_id}/privacy/retention")
def privacy_retention(project_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    return {"document_retention_days": int(os.getenv("SDA_DOCUMENT_RETENTION_DAYS", "365")), "evidence_retention_days": int(os.getenv("SDA_EVIDENCE_RETENTION_DAYS", "365")), "portal_link_days": int(os.getenv("SDA_PORTAL_LINK_RETENTION_DAYS", "7")), "llm_metadata_retention_days": int(os.getenv("SDA_LLM_METADATA_RETENTION_DAYS", "730")), "raw_prompts_stored": False}


@app.delete("/api/v1/projects/{project_id}/documents/{document_id}")
def delete_document(project_id: str, document_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "owner", "admin")
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    record = store.document_records.get(document_id)
    if not record:
        raise HTTPException(404, "Document not found")
    # Only metadata is retained in the audit event; content and the raw name
    # are deliberately absent from it.
    storage_key = record.get("storage_key")
    if storage_key:
        storage.delete_object(storage_key)
    store.document_records.pop(document_id, None)
    for key, consent in list(store.ai_consents.items()):
        if consent.get("document_id") == document_id:
            consent["revoked_at"] = now()
            store.ai_consents[key] = consent
    audit_event(user, "document_erased", project_id=project_id, document_id=document_id)
    return {"status": "erased", "document_id": document_id}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mock_mode": os.getenv("MOCK_MODE", "true").lower() == "true", "time": now()}


@app.get("/api/v1/dashboard")
def dashboard(user: CurrentUser = Depends(current_user)) -> dict:
    if os.getenv("MOCK_MODE", "true").lower() != "true":
        projects = catalog.list_projects(user.organization_id)
        if not projects:
            raise HTTPException(404, "No projects available in this organization")
        project = projects[0]
        return {"project": project, "counts": {}, "scope_changes": 0, "attention": [], "requirements": project.get("requirements_count", 0)}
    counts = {state: sum(r.status == state for r in store.requirements) for state in ["demonstrated", "partially_demonstrated", "not_demonstrated", "manual_review_required"]}
    return {"project": store.project, "counts": counts, "scope_changes": len(store.changes), "attention": ["Performance budget has no passing run", "Warehouse manager role awaits approval", "Email alerts are partially demonstrated"], "requirements": len(store.requirements)}


@app.get("/api/v1/projects/{project_id}/requirements", response_model=list[Requirement])
def requirements(project_id: str) -> list[Requirement]:
    return canonical_requirements(project_id)


@app.patch("/api/v1/requirements/{requirement_id}", response_model=Requirement)
def update_requirement(requirement_id: UUID, payload: dict) -> Requirement:
    req = next((r for r in store.requirements if r.id == requirement_id), None)
    if not req:
        raise HTTPException(404, "Requirement not found")
    for key in ["title", "description", "priority", "status"]:
        if key in payload:
            setattr(req, key, payload[key])
    return req


@app.post("/api/v1/requirements/{requirement_id}/criteria", response_model=Requirement)
def generate_criteria(requirement_id: UUID) -> Requirement:
    req = next((r for r in store.requirements if r.id == requirement_id), None)
    if not req:
        raise HTTPException(404, "Requirement not found")
    req.criteria = [Criterion(**item) for item in ContractMockLLMProvider().generate_criteria(req.model_dump())]
    return req


@app.post("/api/v1/projects/{project_id}/requirements/{human_id}/criteria", response_model=Requirement)
def generate_project_criteria(project_id: str, human_id: str, user: CurrentUser = Depends(current_user)) -> Requirement:
    """Generate criteria against the active project context, preserving draft semantics."""
    project_or_404(project_id)
    requirement = next((item for item in canonical_requirements(project_id) if item.human_id == human_id), None)
    if requirement is None:
        raise HTTPException(404, "Requirement not found")
    provider = llm_provider()
    generated = [Criterion(**item) for item in provider.generate_acceptance_criteria(requirement.model_dump())]
    requirement.criteria = generated
    if project_id == CUSTOMER_PROJECT_ID:
        original = next(item for item in store.requirements if item.human_id == human_id)
        original.criteria = generated
    else:
        requirement_overrides[(project_id, human_id)] = {"criteria": [item.model_dump() for item in generated]}
    store.audit_events.append({"event": "acceptance_criteria_generated", "project_id": project_id, "requirement_id": human_id, "provider": provider.__class__.__name__, "created_at": now()})
    return requirement


@app.post("/api/v1/scope/import")
async def import_scope(file: UploadFile = File(...)) -> dict:
    allowed = {"application/pdf", "text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Only PDF, DOCX and TXT files are supported")
    filename = os.path.basename(file.filename or "scope-document")
    if filename != (file.filename or "") or filename.startswith("."):
        raise HTTPException(400, "Unsafe filename")
    content = await file.read(10_000_001)
    if len(content) > 10_000_000:
        raise HTTPException(413, "File exceeds 10MB limit")
    if not content:
        raise HTTPException(400, "File is empty")
    if file.content_type == "application/pdf" and not content.startswith(b"%PDF"):
        raise HTTPException(400, "File content does not match PDF format")
    if file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        if not content.startswith(b"PK") or b"vbaProject.bin" in content:
            raise HTTPException(400, "DOCX must be a valid macro-free document")
    if file.content_type == "text/plain" and b"\x00" in content[:4096]:
        raise HTTPException(400, "Text file contains binary content")
    document_id = f"doc_{secrets.token_urlsafe(12)}"
    store.document_records[document_id] = {"id": document_id, "filename": filename, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content), "content_type": file.content_type, "status": "quarantined", "created_at": now(), "retention_days": int(os.getenv("SDA_DOCUMENT_RETENTION_DAYS", "365"))}
    return {"status": "draft_ready", "document_id": document_id, "filename": filename, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "version": "Scope v2 (draft)", "message": "Mock extraction complete. Review the suggested requirements before confirming."}


@app.get("/api/v1/projects/{project_id}/changes", response_model=list[ChangeRequest])
def changes(project_id: str) -> list[ChangeRequest]:
    return canonical_changes(project_id)


@app.patch("/api/v1/changes/{change_id}", response_model=ChangeRequest)
def update_change(change_id: UUID, payload: dict) -> ChangeRequest:
    change = next((c for c in store.changes if c.id == change_id), None)
    if not change:
        raise HTTPException(404, "Change request not found")
    if payload.get("status") in {"proposed", "approved", "rejected", "incorporated"}:
        change.status = payload["status"]
    return change


@app.patch("/api/v1/projects/{project_id}/changes/{change_id}", response_model=ChangeRequest)
def update_project_change(project_id: str, change_id: UUID, payload: dict) -> ChangeRequest:
    project_or_404(project_id)
    change = next((item for item in canonical_changes(project_id) if item.id == change_id), None)
    if change is None:
        raise HTTPException(404, "Change request not found")
    next_status = payload.get("status")
    if next_status not in {"proposed", "approved", "rejected", "incorporated"}:
        raise HTTPException(400, "Invalid change request status")
    if project_id == CUSTOMER_PROJECT_ID:
        source = next(item for item in store.changes if item.id == change_id)
        source.status = next_status
        change = source
    else:
        change_overrides[(project_id, str(change_id))] = {"status": next_status}
        change.status = next_status
    store.audit_events.append({"event": "change_status_updated", "project_id": project_id, "change_id": str(change_id), "status": next_status, "created_at": now()})
    return change


@app.post("/api/v1/projects/{project_id}/runs")
def run_verification(project_id: str, payload: RunRequest) -> dict:
    project_or_404(project_id)
    requirements_for_project = canonical_requirements(project_id)
    selected = payload.requirement_ids or [str(item.id) for item in requirements_for_project[:3]]
    created = []
    for rid in selected:
        req = next((r for r in requirements_for_project if str(r.id) == str(rid) or r.human_id == rid), None)
        if not req:
            continue
        state: EvidenceState = "not_demonstrated" if req.human_id in {"REQ-010", "REQ-071"} else "demonstrated"
        evidence = Evidence(requirement_id=req.id, state=state, summary="The simulated browser run produced a traceable observation and screenshot.", steps=["Create isolated browser context", f"Navigate to {payload.target_url}", f"Execute {len(req.criteria)} acceptance criteria", "Capture screenshot and DOM snapshot"], artifact=f"{req.human_id.lower()}-run.png", sha256=hashlib.sha256(f"{req.id}{time.time()}".encode()).hexdigest())
        if project_id == CUSTOMER_PROJECT_ID:
            store.evidence.append(evidence)
            store.relationships.append(EvidenceRelationship(source_type="requirement", source_id=str(req.id), target_type="evidence", target_id=str(evidence.id), relationship="verifies"))
            req.status = state
        else:
            storage.put_object(f"{project_id}/{evidence.artifact}", f"{project_id}:{req.human_id}".encode(), "image/png")
        created.append(evidence)
    return {"run_id": "run_" + uuid4().hex[:10], "status": "completed", "target_url": payload.target_url, "evidence": created}


@app.get("/api/v1/projects/{project_id}/evidence", response_model=list[Evidence])
def evidence(project_id: str) -> list[Evidence]:
    return canonical_evidence(project_id)


@app.get("/api/v1/projects/{project_id}/evidence/{artifact_id}/signed-url")
def evidence_signed_url(project_id: str, artifact_id: str) -> dict[str, str]:
    artifact = next((item for item in canonical_evidence(project_id) if str(item.id) == artifact_id or item.artifact == artifact_id), None)
    if not artifact:
        raise HTTPException(404, "Evidence artifact not found")
    if isinstance(storage, LocalStorageProvider):
        try:
            storage.get_object(artifact.artifact)
        except FileNotFoundError:
            storage.put_object(artifact.artifact, f"SDA evidence artifact for {project_id}".encode(), "application/octet-stream")
    return {"url": storage.get_signed_url(artifact.artifact)}


@app.get("/api/v1/evidence/{key:path}")
def get_evidence_object(key: str, expires: int, signature: str) -> Response:
    if not storage.verify_signed_url(key, expires, signature):
        raise HTTPException(403, "Evidence link expired or invalid")
    try:
        content = storage.get_object(key)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Evidence object not found") from exc
    return Response(content=content, media_type="application/octet-stream")


@app.get("/api/v1/projects/{project_id}/delivery-pack")
def delivery_pack(project_id: str) -> dict:
    project_or_404(project_id)
    if project_id == CUSTOMER_PROJECT_ID:
        return {"release": store.project["release"], "project": catalog.get_project(project_id), "story": {"promised": "A secure operations portal for order visibility.", "delivered": f"{sum(r.status == 'demonstrated' for r in store.requirements)} of {len(store.requirements)} requirements demonstrated.", "changed": f"{len(store.changes)} scope signals detected; one approved clarification.", "remaining": "Performance budget and email alerts need review.", "approval": "Client acceptance is pending."}, "requirements": store.requirements, "evidence": store.evidence, "generated_at": now()}
    result = getattr(catalog, "delivery_pack", lambda _project_id, _release_id: None)(project_id, release_id_for(project_id))
    if result is None:
        raise HTTPException(404, "Release not found")
    return result


@app.post("/api/v1/review/{token}")
def review(token: str, payload: ReviewRequest) -> dict:
    access = _review_record(token)
    if not _guest_session_valid(token, payload.guest_session):
        raise HTTPException(401, "Guest verification required")
    project_id = access["project_id"]
    item = {"token_hash": hashlib.sha256(token.encode()).hexdigest(), "project_id": project_id, "release_id": access["release_id"], **payload.model_dump(exclude={"guest_session"}), "created_at": now()}
    store.reviews.append(item)
    if project_id == CUSTOMER_PROJECT_ID:
        store.project["status"] = "accepted" if payload.decision == "accepted" else "on_hold" if payload.decision == "rejected" else "pending_acceptance"
    store.audit_events.append({"event": "client_release_reviewed", "project_id": project_id, "release_id": release_id_for(project_id), "decision": payload.decision, "created_at": now()})
    return {"status": "recorded", "review": item}


@app.post("/api/v1/review/{token}/request-otp")
def request_review_otp(token: str, payload: ReviewOtpRequest) -> dict[str, Any]:
    access = _review_record(token)
    if os.getenv("MOCK_MODE", "true").lower() == "true":
        return {"status": "sent", "expires_in_seconds": 600, "mock_code": "123456"}
    if payload.email.lower() != access["email"].lower():
        return {"status": "sent", "expires_in_seconds": 600}
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge_key = hashlib.sha256(f"{token}:{payload.email.lower()}".encode()).hexdigest()
    store.review_challenges[challenge_key] = {"code_hash": hashlib.sha256(code.encode()).hexdigest(), "token_hash": hashlib.sha256(token.encode()).hexdigest(), "email": payload.email.lower(), "attempts": 0, "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}
    email_delivery = email_provider.send_review_otp(to=payload.email, code=code, release_id=access["release_id"])
    return {"status": "sent", "expires_in_seconds": 600, "delivery": email_delivery}


@app.post("/api/v1/review/{token}/verify-otp")
def verify_review_otp(token: str, payload: ReviewOtpVerification) -> dict[str, Any]:
    access = _review_record(token)
    if os.getenv("MOCK_MODE", "true").lower() == "true" and payload.code == "123456":
        return {"status": "verified", "guest_session": "mock-guest-session"}
    challenge_key = hashlib.sha256(f"{token}:{payload.email.lower()}".encode()).hexdigest()
    challenge = store.review_challenges.get(challenge_key)
    if not challenge or challenge["token_hash"] != hashlib.sha256(token.encode()).hexdigest() or datetime.fromisoformat(challenge["expires_at"]) <= datetime.now(timezone.utc):
        raise HTTPException(401, "Invalid or expired verification code")
    challenge["attempts"] += 1
    if challenge["attempts"] > 5 or not secrets.compare_digest(challenge["code_hash"], hashlib.sha256(payload.code.encode()).hexdigest()):
        raise HTTPException(401, "Invalid or expired verification code")
    raw_session = secrets.token_urlsafe(32)
    store.review_sessions[hashlib.sha256(raw_session.encode()).hexdigest()] = {"token_hash": hashlib.sha256(token.encode()).hexdigest(), "expires_at": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(), "email": access["email"]}
    return {"status": "verified", "guest_session": raw_session, "expires_in_seconds": 28800}


@app.get("/api/v1/review/{token}")
def review_pack(token: str, guest_session: Optional[str] = None) -> dict:
    _review_record(token)
    if not _guest_session_valid(token, guest_session):
        raise HTTPException(401, "Guest verification required")
    if token == "acme-review-token":
        projection = catalog.dashboard(ACME_PROJECT_ID, ACME_RELEASE_ID)
        if projection is None:
            raise HTTPException(404, "Review link not found or expired")
        evidence_state = {
            "passed": "demonstrated",
            "in_progress": "partially_demonstrated",
            "not_started": "not_demonstrated",
        }
        evidence = [
            {
                "id": item["id"],
                "artifact": f"{item['id'].lower()}-verification.png",
                "state": evidence_state.get(item["verification"], "inconclusive"),
                "summary": (
                    "Verification passed for the active acceptance criteria."
                    if item["verification"] == "passed"
                    else "Verification is in progress and needs review."
                    if item["verification"] == "in_progress"
                    else "No conclusive verification run is available yet."
                ),
            }
            for item in projection["requirements"]
        ]
        return {"project": projection["project"], "release": projection["project"]["release"], "story": {"promised": "A traceable Client Portal release.", "delivered": "71 of 86 requirements demonstrated.", "changed": "12 changes tracked; 8 approved.", "remaining": "11 failed verifications and 4 requirements pending.", "approval": "Client sign-off is pending."}, "requirements": projection["requirements"], "evidence": evidence}
    if token != "demo-review-token":
        raise HTTPException(404, "Review link not found or expired")
    return delivery_pack(CUSTOMER_PROJECT_ID)


@app.get("/api/v1/internal/costs")
def costs(user: CurrentUser = Depends(current_user)) -> dict:
    require_role(user, "owner", "admin")
    input_tokens = sum(item["input_tokens"] for item in store.llm_runs)
    output_tokens = sum(item["output_tokens"] for item in store.llm_runs)
    estimated_cost = round(sum(item["estimated_cost"] for item in store.llm_runs) + 0.18, 4)
    provider = "OpenAIProvider" if os.getenv("MOCK_MODE", "true").lower() != "true" else "MockLLMProvider"
    return {"runs": len(store.llm_runs) + 4, "llm_tokens": {"input": input_tokens + 4820, "output": output_tokens + 1360}, "estimated_cost_eur": estimated_cost, "browser_minutes": 3.4, "provider": provider}


@app.get("/api/v1/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    try:
        return job_runner.get_status(job_id)
    except KeyError as exc:
        raise HTTPException(404, "Job not found") from exc


def require_demo_project(project_id: str) -> None:
    project_or_404(project_id)


@app.get("/api/v1/projects/{project_id}/scope/versions")
def scope_versions(project_id: str) -> list[dict]:
    return canonical_scope_versions(project_id)


@app.post("/api/v1/projects/{project_id}/scope/versions")
def create_scope_version(project_id: str, payload: ScopeVersionRequest) -> dict:
    require_demo_project(project_id)
    if project_id != CUSTOMER_PROJECT_ID:
        raise HTTPException(409, "Reference baseline is read-only; create changes through the active release workflow")
    next_number = len(store.scope_versions) + 1
    version = {"version": f"v{next_number}", "status": "draft", **payload.model_dump(), "created_at": now(), "created_by": "demo.owner"}
    store.scope_versions.append(version)
    store.audit_events.append({"event": "scope_version_created", "version": version["version"], "created_at": now()})
    return version


@app.post("/api/v1/projects/{project_id}/scope/versions/{version}/approve")
def approve_scope_version(project_id: str, version: str) -> dict:
    require_demo_project(project_id)
    if project_id != CUSTOMER_PROJECT_ID:
        selected = next((item for item in canonical_scope_versions(project_id) if item["version"] == version), None)
        if not selected:
            raise HTTPException(404, "Scope version not found")
        return selected
    selected = next((item for item in store.scope_versions if item["version"] == version), None)
    if not selected:
        raise HTTPException(404, "Scope version not found")
    selected["status"] = "approved"
    store.audit_events.append({"event": "scope_approved", "version": version, "created_at": now()})
    return selected


@app.post("/api/v1/projects/{project_id}/scope/extract")
async def extract_scope(project_id: str, file: UploadFile = File(...)) -> dict:
    require_demo_project(project_id)
    if project_id != CUSTOMER_PROJECT_ID:
        raise HTTPException(409, "Scope extraction is available for the functional demo baseline")
    result = await import_scope(file)
    raw_text = result.get("text", "") if isinstance(result, dict) else ""
    classification = classify_text(str(raw_text)) if raw_text else DataClassification.CONFIDENTIAL
    if os.getenv("MOCK_MODE", "true").lower() != "true" and classification > privacy_policy.max_external_classification:
        raise HTTPException(403, "This document requires a private AI provider and cannot be processed externally")
    result["data_policy"] = {"classification": classification.name, "redaction_required": privacy_policy.redact_before_ai, "external_processing": os.getenv("MOCK_MODE", "true").lower() != "true"}
    result["extraction"] = {"deliverables": ["Customer operations portal"], "requirements": [{"human_id": "REQ-001", "title": "Customer login", "confidence": 0.94}], "ambiguous_requirements": ["Notification timing is not explicit"], "missing_acceptance_criteria": ["Performance budget"]}
    return result


@app.get("/api/v1/projects/{project_id}/readiness")
def readiness(project_id: str) -> dict:
    project_or_404(project_id)
    project_requirements = canonical_requirements(project_id)
    project_evidence = canonical_evidence(project_id)
    project_changes = canonical_changes(project_id)
    project_acceptance = canonical_acceptance(project_id)
    unresolved_comments = sum(not c["resolved"] for c in store.comments) if project_id == CUSTOMER_PROJECT_ID else 0
    result = calculate_readiness([r.model_dump() for r in project_requirements], [e.model_dump() for e in project_evidence], [c.model_dump() for c in project_changes], unresolved_comments=unresolved_comments, accepted=sum(item["decision"] == "accepted" for item in project_acceptance))
    project = catalog.get_project(project_id) or {}
    return {"release": project.get("release", ""), **result.model_dump()}


@app.get("/api/v1/projects/{project_id}/graph")
def evidence_graph(project_id: str) -> dict:
    project_or_404(project_id)
    project_requirements = canonical_requirements(project_id)
    project_evidence = canonical_evidence(project_id)
    scope = canonical_scope_versions(project_id)
    nodes = [{"type": "scope_version", "id": item["version"], "label": item["version"]} for item in scope]
    nodes.extend({"type": "requirement", "id": str(req.id), "label": f"{req.human_id} · {req.title}"} for req in project_requirements)
    nodes.extend({"type": "evidence", "id": str(item.id), "label": item.artifact} for item in project_evidence)
    relationships = [relationship.model_dump() for relationship in store.relationships] if project_id == CUSTOMER_PROJECT_ID else []
    relationships.extend({"source_type": "requirement", "source_id": str(item.requirement_id), "target_type": "evidence", "target_id": str(item.id), "relationship": "verifies"} for item in project_evidence)
    return {"nodes": nodes, "relationships": relationships, "questions": {"requirements_without_evidence": sum(not any(e.requirement_id == req.id for e in project_evidence) for req in project_requirements), "requirements_with_evidence": sum(any(e.requirement_id == req.id for e in project_evidence) for req in project_requirements)}}


@app.post("/api/v1/projects/{project_id}/file-inspections")
def file_inspection(project_id: str, payload: FileInspectionRequest) -> dict:
    require_demo_project(project_id)
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(400, "content_base64 is invalid") from exc
    result = inspect_file(payload.filename, content)
    checks = {"columns_match": True, "row_count_match": True}
    observed_columns = set(result.get("columns", []))
    if payload.expected_columns:
        checks["columns_match"] = set(payload.expected_columns).issubset(observed_columns)
    if payload.expected_row_count is not None:
        observed_count = result.get("row_count", 0)
        checks["row_count_match"] = observed_count == payload.expected_row_count
    result["checks"] = checks
    result["assessment"] = "demonstrated" if result["valid"] and all(checks.values()) else "partially_demonstrated"
    return result


@app.post("/api/v1/projects/{project_id}/human-evidence")
def add_human_evidence(project_id: str, payload: HumanEvidenceRequest) -> dict:
    require_demo_project(project_id)
    if not any(req.id == payload.requirement_id for req in canonical_requirements(project_id)):
        raise HTTPException(404, "Requirement not found")
    item = {"id": str(uuid4()), **payload.model_dump(), "requirement_id": str(payload.requirement_id), "author": "demo.owner", "created_at": now()}
    store.human_evidence.append(item)
    store.audit_events.append({"event": "evidence_uploaded", "evidence_id": item["id"], "created_at": now()})
    return item


@app.post("/api/v1/projects/{project_id}/bug-change-assessment", response_model=BugChangeAssessment)
def bug_change_assessment(project_id: str, payload: BugChangeRequest) -> BugChangeAssessment:
    require_demo_project(project_id)
    report = payload.report.lower()
    if any(word in report for word in ["email", "scheduled", "automatically", "cada mañana"]):
        classification = "likely_change_request"
        reason = "The request describes new scheduled delivery behavior that is not present in the approved baseline."
        confidence = 0.91
    elif any(word in report for word in ["filter", "export", "column", "fila"]):
        classification = "likely_defect"
        reason = "The report references behavior already covered by the export and filtering requirement."
        confidence = 0.88
    else:
        classification = "needs_human_review"
        reason = "The report cannot be safely classified against the current baseline."
        confidence = 0.52
    scope_versions_for_project = canonical_scope_versions(project_id)
    compared_scope_version = scope_versions_for_project[-1]["version"] if scope_versions_for_project else "baseline"
    return BugChangeAssessment(classification=classification, confidence=confidence, reason=reason, compared_scope_version=compared_scope_version, related_requirement_ids=[str(item) for item in payload.requirement_ids])


@app.get("/api/v1/projects/{project_id}/acceptance")
def acceptance(project_id: str) -> list[dict]:
    return canonical_acceptance(project_id)


@app.post("/api/v1/projects/{project_id}/acceptance/{requirement_id}")
def decide_acceptance(project_id: str, requirement_id: UUID, payload: AcceptanceDecisionRequest) -> dict:
    require_demo_project(project_id)
    project_acceptance = canonical_acceptance(project_id)
    item = next((entry for entry in project_acceptance if entry["requirement_id"] == str(requirement_id)), None)
    if not item:
        raise HTTPException(404, "Acceptance item not found")
    item.update({"decision": payload.decision, "comment": payload.comment, "updated_at": now()})
    store.audit_events.append({"event": f"client_{payload.decision}", "project_id": project_id, "requirement_id": str(requirement_id), "created_at": now()})
    return item


@app.get("/api/v1/projects/{project_id}/attention")
def attention(project_id: str) -> list[dict]:
    return canonical_attention(project_id)


@app.post("/api/v1/projects/{project_id}/prepare-delivery")
def prepare_delivery(project_id: str) -> dict:
    project_or_404(project_id)
    if project_id != CUSTOMER_PROJECT_ID:
        project = catalog.get_project(project_id) or {}
        result = readiness(project_id)
        checks = [{"key": "requirements_assigned", "label": "Requirements assigned", "status": "ready", "detail": f"{result['total_requirements']} requirements linked to the active baseline"}, {"key": "scope_changes_resolved", "label": "Scope changes resolved", "status": "attention" if result["unapproved_scope_changes"] else "ready", "detail": f"{result['unapproved_scope_changes']} unapproved changes"}, {"key": "acceptance_criteria", "label": "Acceptance criteria exist", "status": "ready", "detail": "Criteria are available on the release projection"}, {"key": "verification_coverage", "label": "Verification coverage", "status": "attention" if result["without_evidence"] else "ready", "detail": f"{result['without_evidence']} requirements without evidence"}, {"key": "client_comments", "label": "Client comments", "status": "ready", "detail": "No unresolved client comments in the reference projection"}]
        return {"release": project.get("release", ""), "ready": all(check["status"] == "ready" for check in checks), "checks": checks, "next_actions": [item["title"] for item in canonical_attention(project_id) if item["severity"] != "info"]}
    checks = [{"key": "requirements_assigned", "label": "Requirements assigned", "status": "ready", "detail": "12 requirements linked to Scope v1"}, {"key": "scope_changes_resolved", "label": "Scope changes resolved", "status": "blocked", "detail": "1 possible scope change needs approval"}, {"key": "acceptance_criteria", "label": "Acceptance criteria exist", "status": "ready", "detail": "24 criteria generated"}, {"key": "verification_coverage", "label": "Verification coverage", "status": "attention", "detail": "1 requirement is not demonstrated"}, {"key": "client_comments", "label": "Client comments", "status": "attention", "detail": "1 unresolved comment"}]
    return {"release": store.project["release"], "ready": all(check["status"] == "ready" for check in checks), "checks": checks, "next_actions": ["Review CR-001", "Run missing verification for REQ-010", "Resolve client comment"]}


@app.get("/api/v1/projects/{project_id}/audit")
def audit(project_id: str) -> list[dict]:
    project_or_404(project_id)
    return [item for item in store.audit_events if item.get("project_id", project_id) == project_id]

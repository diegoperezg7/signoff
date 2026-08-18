from __future__ import annotations

import hashlib
import os
import time
import base64
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from .catalog import ACME_PROJECT_ID, ACME_RELEASE_ID, CUSTOMER_PROJECT_ID, CUSTOMER_RELEASE_ID, ProjectCatalog
from .domain import BugChangeAssessment, EvidenceRelationship, calculate_readiness
from .file_inspector import inspect_file
from .providers import MockLLMProvider as ContractMockLLMProvider, OpenAIProvider
from .persistence import PostgresRepository
from .auth import CurrentUser, current_user, require_role
from .storage import LocalStorageProvider, S3StorageProvider
from .jobs import InlineJobRunner
from .security import DataClassification, PrivacyPolicy, classify_text, redact_sensitive

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


store = DemoStore()
catalog = ProjectCatalog(store)
storage = LocalStorageProvider() if os.getenv("MOCK_MODE", "true").lower() == "true" else S3StorageProvider()
job_runner = InlineJobRunner()
privacy_policy = PrivacyPolicy()
requirement_overrides: dict[tuple[str, str], dict] = {}
change_overrides: dict[tuple[str, str], dict] = {}
release_status_overrides: dict[tuple[str, str], str] = {}
app = FastAPI(title="SDA API", version="0.1.0", description="Software Delivery Assurance API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def project_or_404(project_id: str) -> dict:
    project = catalog.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


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
    global catalog
    if os.getenv("MOCK_MODE", "true").lower() == "true":
        return
    try:
        repository = PostgresRepository()
        repository.initialize(catalog)
        catalog = repository  # type: ignore[assignment]
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
    return OpenAIProvider()


def audit_event(user: CurrentUser, event_type: str, **payload: Any) -> None:
    """Store metadata-only audit records; document content never belongs here."""
    store.audit_events.append({"organization_id": user.organization_id, "actor_id": user.id, "event": event_type, "created_at": now(), **payload})


@app.post("/api/v1/projects/{project_id}/ai/tasks", response_model=AIProposal)
def run_ai_task(project_id: str, payload: AITaskRequest, user: CurrentUser = Depends(current_user)) -> AIProposal:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    provider = llm_provider()
    privacy_policy.assert_allowed(provider, payload.classification, payload.consent)
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mock_mode": os.getenv("MOCK_MODE", "true").lower() == "true", "time": now()}


@app.get("/api/v1/dashboard")
def dashboard() -> dict:
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
    content = await file.read()
    if len(content) > 10_000_000:
        raise HTTPException(413, "File exceeds 10MB limit")
    return {"status": "draft_ready", "filename": file.filename, "bytes": len(content), "version": "Scope v2 (draft)", "message": "Mock extraction complete. Review the suggested requirements before confirming."}


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
    if token not in {"demo-review-token", "acme-review-token"}:
        raise HTTPException(404, "Review link not found or expired")
    project_id = CUSTOMER_PROJECT_ID if token == "demo-review-token" else ACME_PROJECT_ID
    item = {"token": token, "project_id": project_id, "release_id": release_id_for(project_id), **payload.model_dump(), "created_at": now()}
    store.reviews.append(item)
    if project_id == CUSTOMER_PROJECT_ID:
        store.project["status"] = "accepted" if payload.decision == "accepted" else "on_hold" if payload.decision == "rejected" else "pending_acceptance"
    store.audit_events.append({"event": "client_release_reviewed", "project_id": project_id, "release_id": release_id_for(project_id), "decision": payload.decision, "created_at": now()})
    return {"status": "recorded", "review": item}


@app.get("/api/v1/review/{token}")
def review_pack(token: str) -> dict:
    if token == "acme-review-token":
        projection = catalog.dashboard(ACME_PROJECT_ID, ACME_RELEASE_ID)
        if projection is None:
            raise HTTPException(404, "Review link not found or expired")
        return {"project": projection["project"], "release": projection["project"]["release"], "story": {"promised": "A traceable Client Portal release.", "delivered": "71 of 86 requirements demonstrated.", "changed": "12 changes tracked; 8 approved.", "remaining": "11 failed verifications and 4 requirements pending.", "approval": "Client sign-off is pending."}, "requirements": projection["requirements"], "evidence": [{"id": item["id"], "artifact": f"{item['id'].lower()}-verification.png", "summary": "Verification evidence linked to this requirement."} for item in projection["requirements"]]}
    if token != "demo-review-token":
        raise HTTPException(404, "Review link not found or expired")
    return delivery_pack(CUSTOMER_PROJECT_ID)


@app.get("/api/v1/internal/costs")
def costs() -> dict:
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
